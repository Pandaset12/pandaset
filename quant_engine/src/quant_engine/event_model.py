"""Auditable, event-conditioned portfolio estimates.

Factor shocks are cumulative changes in the same units as daily factor changes.
Issuer shocks are multiples of a holding's factor-adjusted residual volatility.
All fitted sensitivities come from aligned adjusted-price histories; no LLM output
is accepted as a calculated return or probability.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype

from .returns import asset_returns
from .validation import validate_prices, validate_weights

MODEL_VERSION = "event-linear-residual-bootstrap-v1"
CASES = ("mild", "central", "severe")
HORIZONS = {"1m": 21, "3m": 63}
MIN_FIT_OBSERVATIONS = 126
MIN_CALIBRATION_EVENTS = 12
BOOTSTRAP_DRAWS = 2000


@dataclass(frozen=True)
class _Fit:
    betas: np.ndarray
    residuals: np.ndarray
    residual_daily_volatility: np.ndarray
    r_squared: np.ndarray
    assets: tuple[str, ...]
    factors: tuple[str, ...]
    observations: int


def _validate_factor_returns(factor_returns: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(factor_returns, pd.DataFrame) or factor_returns.empty:
        raise ValueError("factor_returns must be a nonempty DataFrame")
    if not isinstance(factor_returns.index, pd.DatetimeIndex):
        raise ValueError("factor_returns must have a DatetimeIndex")
    if (factor_returns.index.hasnans or not factor_returns.index.is_unique
            or not factor_returns.index.is_monotonic_increasing):
        raise ValueError("factor dates must be nonmissing, unique, and increasing")
    if (not factor_returns.columns.is_unique or
            any(not isinstance(name, str) or not name for name in factor_returns.columns)):
        raise ValueError("factor labels must be unique nonempty strings")
    if any(is_bool_dtype(dtype) for dtype in factor_returns.dtypes):
        raise ValueError("factor changes must be real numbers")
    try:
        values = factor_returns.to_numpy(dtype=float, na_value=np.nan)
    except (TypeError, ValueError) as exc:
        raise ValueError("factor changes must be real numbers") from exc
    if not np.isfinite(values).all():
        raise ValueError("factor changes must be finite and have no missing values")
    return factor_returns.astype(float).copy().reindex(sorted(factor_returns.columns), axis=1)


def _fit(asset_daily: pd.DataFrame, factor_daily: pd.DataFrame) -> _Fit:
    aligned_assets, aligned_factors = asset_daily.align(factor_daily, join="inner", axis=0)
    n = len(aligned_assets)
    if n < MIN_FIT_OBSERVATIONS:
        raise ValueError(f"at least {MIN_FIT_OBSERVATIONS} aligned daily returns are required")
    x = aligned_factors.to_numpy(dtype=float)
    y = aligned_assets.to_numpy(dtype=float)
    x_center = x - x.mean(axis=0)
    y_center = y - y.mean(axis=0)
    scale = x_center.std(axis=0, ddof=1)
    if (scale <= 0).any():
        raise ValueError("each factor must vary in the aligned history")
    standardized = x_center / scale
    if np.linalg.matrix_rank(standardized) < standardized.shape[1]:
        raise ValueError("aligned factor history is rank deficient")
    if np.linalg.cond(standardized) > 1e8:
        raise ValueError("aligned factor history is too ill-conditioned")
    standardized_betas = np.linalg.lstsq(standardized, y_center, rcond=None)[0]
    betas = standardized_betas / scale[:, None]
    residuals = y_center - x_center @ betas
    residual_vol = residuals.std(axis=0, ddof=1)
    total_ss = np.sum(y_center * y_center, axis=0)
    residual_ss = np.sum(residuals * residuals, axis=0)
    r_squared = np.where(total_ss > 0, 1 - residual_ss / np.where(total_ss > 0, total_ss, 1), 0)
    if not np.isfinite(betas).all() or not np.isfinite(residual_vol).all():
        raise ValueError("nonfinite fitted sensitivity")
    return _Fit(betas, residuals, residual_vol, r_squared,
                tuple(aligned_assets.columns), tuple(aligned_factors.columns), n)


def _validate_shock(shock: Mapping, factors: tuple[str, ...], assets: tuple[str, ...]) -> dict:
    if not isinstance(shock, Mapping) or set(shock) != {"factors", "issuers"}:
        raise ValueError("each confirmed shock needs factors and issuers mappings")
    factor_shocks, issuer_shocks = shock["factors"], shock["issuers"]
    if not isinstance(factor_shocks, Mapping) or set(factor_shocks) != set(factors):
        raise ValueError("confirmed factor shocks must exactly match fitted factors")
    if not isinstance(issuer_shocks, Mapping) or not set(issuer_shocks).issubset(assets):
        raise ValueError("issuer shocks must be keyed by known asset symbols")
    for name, value in list(factor_shocks.items()) + list(issuer_shocks.items()):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value):
            raise ValueError(f"shock for {name} must be finite and real")
    return {"factors": {name: float(factor_shocks[name]) for name in factors},
            "issuers": {name: float(issuer_shocks[name]) for name in assets if name in issuer_shocks}}


def _validate_case_shocks(shocks: Mapping, factors: tuple[str, ...], assets: tuple[str, ...]) -> dict:
    if not isinstance(shocks, Mapping) or set(shocks) != set(CASES):
        raise ValueError("confirmed_shocks must contain mild, central, and severe cases")
    validated = {}
    for case in CASES:
        if not isinstance(shocks[case], Mapping) or set(shocks[case]) != set(HORIZONS):
            raise ValueError(f"{case} must contain 1m and 3m shocks")
        validated[case] = {
            horizon: _validate_shock(shocks[case][horizon], factors, assets)
            for horizon in HORIZONS
        }
    return validated


def _asset_impacts(fit: _Fit, shock: Mapping, days: int) -> np.ndarray:
    factor_vector = np.array([shock["factors"][name] for name in fit.factors])
    issuer_vector = np.array([shock["issuers"].get(name, 0) for name in fit.assets])
    impacts = factor_vector @ fit.betas + issuer_vector * fit.residual_daily_volatility * np.sqrt(days)
    if not np.isfinite(impacts).all() or (impacts < -1).any():
        raise ValueError("confirmed shocks imply an invalid asset return below -100%")
    return impacts


def _portfolio_result(impacts: np.ndarray, weights: pd.Series, assets: tuple[str, ...]) -> dict:
    contributions = weights.to_numpy() * impacts
    return {"estimated_return": float(contributions.sum()),
            "holding_contributions": {asset: float(value) for asset, value in zip(assets, contributions)}}


def _bootstrap(fit: _Fit, impacts: np.ndarray, weights: pd.Series,
               days: int, rng: np.random.Generator, draws: int) -> dict:
    # Sample aligned daily residual vectors together to preserve cross-holding dependence.
    sampled = rng.integers(0, fit.observations, size=(draws, days))
    portfolio_noise = fit.residuals @ weights.to_numpy()
    outcomes = float(impacts @ weights.to_numpy()) + portfolio_noise[sampled].sum(axis=1)
    if not np.isfinite(outcomes).all() or (outcomes < -1).any():
        raise ValueError("bootstrap produced a return below -100%")
    quantiles = np.quantile(outcomes, (0.1, 0.5, 0.9))
    return {"p10": float(quantiles[0]), "p50": float(quantiles[1]),
            "p90": float(quantiles[2]), "probability_of_loss": float(np.mean(outcomes < 0))}


def _calibration_report(prices: pd.DataFrame, returns: pd.DataFrame,
                        factors: pd.DataFrame, current: pd.Series, proposed: pd.Series,
                        events: Sequence | None, seed: int) -> dict:
    report = {"model_version": MODEL_VERSION, "status": "failed", "reason": None,
              "event_count": 0, "holdout_start": None, "metrics": {},
              "thresholds": {"minimum_events": MIN_CALIBRATION_EVENTS,
                             "p10_p90_coverage": [0.60, 0.95],
                             "maximum_loss_brier": 0.30,
                             "maximum_median_absolute_error": 0.20}}
    if not events:
        report["reason"] = "no_held_out_event_labels"
        return report
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        report["reason"] = "invalid_event_labels"
        return report
    # Origins are in the final 40% only, with at least one year of prior training.
    holdout_start = max(252, int(len(returns) * 0.6))
    report["holdout_start"] = str(prices.index[holdout_start].date()) if holdout_start < len(prices) else None
    if len(events) < MIN_CALIBRATION_EVENTS:
        report["reason"] = "insufficient_held_out_events"
        return report
    positions = []
    try:
        for event in events:
            if not isinstance(event, Mapping) or not event.get("verified") or not event.get("source"):
                raise ValueError("unverified_event_labels")
            date = pd.Timestamp(event["as_of"])
            if date not in prices.index:
                raise ValueError("event_date_missing_from_prices")
            position = int(prices.index.get_loc(date))
            if position < holdout_start or position + max(HORIZONS.values()) >= len(prices):
                raise ValueError("event_outside_heldout_window")
            if not isinstance(event.get("central_shocks"), Mapping):
                raise ValueError("event_missing_central_shocks")
            positions.append((position, event))
        positions.sort(key=lambda entry: entry[0])
        if any(b[0] - a[0] < 63 for a, b in zip(positions, positions[1:])):
            raise ValueError("heldout_events_overlap")
        if len({position for position, _ in positions}) != len(positions):
            raise ValueError("duplicate_heldout_events")
    except (KeyError, TypeError, ValueError) as exc:
        report["reason"] = str(exc) if isinstance(exc, ValueError) else "invalid_event_labels"
        return report
    records: dict[str, list[tuple[float, float, float]]] = {
        f"{horizon}_{name}": [] for horizon in HORIZONS for name in ("current", "proposed")
    }
    for event_number, (position, event) in enumerate(positions):
        try:
            training_returns = returns.iloc[:position]
            training_factors = factors.loc[factors.index.isin(training_returns.index)]
            if len(training_factors) != len(training_returns):
                raise ValueError("incomplete_training_factor_alignment")
            fit = _fit(training_returns, training_factors)
            if set(event["central_shocks"]) != set(HORIZONS):
                raise ValueError("event_missing_horizon_shock")
            for horizon, days in HORIZONS.items():
                shock = _validate_shock(event["central_shocks"][horizon], fit.factors, fit.assets)
                impacts = _asset_impacts(fit, shock, days)
                realized_assets = prices.iloc[position + days].to_numpy() / prices.iloc[position].to_numpy() - 1
                for portfolio_number, (name, weights) in enumerate((("current", current), ("proposed", proposed))):
                    rng = np.random.default_rng(seed + event_number * 8 + portfolio_number * 2 + days)
                    forecast = _bootstrap(fit, impacts, weights, days, rng, BOOTSTRAP_DRAWS)
                    realized = float(realized_assets @ weights.to_numpy())
                    records[f"{horizon}_{name}"].append((
                        float(forecast["p10"] <= realized <= forecast["p90"]),
                        (forecast["probability_of_loss"] - float(realized < 0)) ** 2,
                        abs(forecast["p50"] - realized),
                    ))
        except (KeyError, TypeError, ValueError, np.linalg.LinAlgError) as exc:
            report["reason"] = f"heldout_backtest_failed: {exc}"
            return report
    report["event_count"] = len(positions)
    passed = True
    for key, samples in records.items():
        values = np.array(samples)
        coverage = float(values[:, 0].mean())
        brier = float(values[:, 1].mean())
        median_error = float(np.median(values[:, 2]))
        metric_passed = 0.60 <= coverage <= 0.95 and brier <= 0.30 and median_error <= 0.20
        report["metrics"][key] = {"p10_p90_coverage": coverage, "loss_brier": brier,
                                  "median_absolute_error": median_error, "passed": metric_passed}
        passed = passed and metric_passed
    report["status"] = "passed" if passed else "failed"
    report["reason"] = None if passed else "backtest_thresholds_failed"
    return report


def run_event_scenarios(
    adjusted_prices: pd.DataFrame,
    current_weights: Mapping,
    proposed_weights: Mapping,
    factor_returns: pd.DataFrame,
    confirmed_shocks: Mapping,
    *,
    seed: int = 0,
    calibration_events: Sequence | None = None,
) -> dict:
    """Calculate confirmed event cases and gated central conditional ranges.

    `factor_returns` contains daily factor changes on dates of holding returns.
    Each case has explicit `1m` and `3m` shocks, each with `factors` (cumulative
    factor changes) and `issuers` (holding residual-volatility multiples). The
    shocks must have been confirmed upstream; this function does not invent them.
    `calibration_events` are verified, nonoverlapping heldout origins whose actual
    outcomes are read from adjusted_prices. Without a passing report, no ranges
    or loss probabilities are returned.
    """
    if isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    prices = validate_prices(adjusted_prices).reindex(sorted(adjusted_prices.columns), axis=1)
    current = validate_weights(current_weights, prices.columns)
    proposed = validate_weights(proposed_weights, prices.columns)
    factors = _validate_factor_returns(factor_returns)
    returns = asset_returns(prices)
    aligned_dates = returns.index.intersection(factors.index)
    fit = _fit(returns, factors)
    validated_shocks = _validate_case_shocks(confirmed_shocks, fit.factors, fit.assets)
    alignment_complete = returns.index.equals(factors.index)
    cases = []
    for case in CASES:
        for horizon, days in HORIZONS.items():
            shock = validated_shocks[case][horizon]
            impacts = _asset_impacts(fit, shock, days)
            before = _portfolio_result(impacts, current, fit.assets)
            after = _portfolio_result(impacts, proposed, fit.assets)
            cases.append({"case": case, "horizon": horizon, "horizon_trading_days": days,
                          "confirmed_shocks": shock,
                          "holding_impacts": {asset: float(value) for asset, value in zip(fit.assets, impacts)},
                          "current": before, "proposed": after,
                          "delta": {"estimated_return": after["estimated_return"] - before["estimated_return"],
                                    "holding_contributions": {
                                        asset: after["holding_contributions"][asset] - before["holding_contributions"][asset]
                                        for asset in fit.assets}}})
    calibration = _calibration_report(prices, returns, factors, current, proposed,
                                      calibration_events, int(seed))
    omission = None
    if not alignment_complete:
        omission = "incomplete_factor_alignment"
    elif fit.observations < 252:
        omission = "insufficient_residual_history"
    elif calibration["status"] != "passed":
        omission = calibration["reason"] or "calibration_failed"
    probabilities = {"status": "omitted", "reason": omission, "central": {}}
    if omission is None:
        try:
            central = {}
            for horizon, days in HORIZONS.items():
                impacts = _asset_impacts(fit, validated_shocks["central"][horizon], days)
                central[horizon] = {
                    "current": _bootstrap(fit, impacts, current, days,
                                          np.random.default_rng(int(seed) + days), BOOTSTRAP_DRAWS),
                    "proposed": _bootstrap(fit, impacts, proposed, days,
                                           np.random.default_rng(int(seed) + days), BOOTSTRAP_DRAWS),
                }
            probabilities = {"status": "available", "reason": None, "central": central,
                             "seed": int(seed), "draws": BOOTSTRAP_DRAWS}
        except ValueError:
            probabilities = {"status": "omitted", "reason": "invalid_bootstrap_outcomes", "central": {}}
    return {"model_version": MODEL_VERSION,
            "assumptions": [
                "Adjusted daily holding prices and factor changes are aligned by date without filling.",
                "Factor betas use centered ordinary least squares; no expected drift is added.",
                "Issuer shocks are multiples of each holding's factor-adjusted residual daily volatility scaled by the square root of horizon trading days.",
                "Portfolio impacts are fixed starting weights times additive holding impacts; costs, taxes, and trading are excluded.",
                "Conditional ranges sample aligned residual vectors with a fixed seed and hold confirmed central shocks constant.",
                "All results are hypothetical estimates, not live prices or forecasts.",
            ],
            "coverage": {"adjusted_price_histories_complete": True,
                         "holding_count": len(fit.assets),
                         "price_return_observations": len(returns),
                         "aligned_observations": len(aligned_dates),
                         "missing_factor_dates": len(returns.index.difference(factors.index)),
                         "factor_alignment_complete": alignment_complete,
                         "sensitivity_minimum_observations": MIN_FIT_OBSERVATIONS,
                         "probability_minimum_observations": 252},
            "sensitivities": {
                asset: {"factor_betas": {factor: float(fit.betas[j, i])
                                         for j, factor in enumerate(fit.factors)},
                        "issuer_residual_daily_volatility": float(fit.residual_daily_volatility[i]),
                        "issuer_residual_1m_sensitivity": float(fit.residual_daily_volatility[i] * np.sqrt(21)),
                        "issuer_residual_3m_sensitivity": float(fit.residual_daily_volatility[i] * np.sqrt(63)),
                        "r_squared": float(fit.r_squared[i]),
                        "aligned_observations": fit.observations}
                for i, asset in enumerate(fit.assets)},
            "cases": cases, "calibration": calibration, "probabilities": probabilities}
