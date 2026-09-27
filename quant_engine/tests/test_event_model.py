import json

import numpy as np
import pandas as pd
import pytest

from quant_engine.event_model import run_event_scenarios


def _history(n=300, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n + 1)
    factor = rng.normal(0, 0.006, n)
    residual = rng.normal(0, 0.008, (n, 2))
    asset_returns = np.column_stack((1.2 * factor, 0.5 * factor)) + residual
    prices = pd.DataFrame(np.vstack((np.ones(2), np.cumprod(1 + asset_returns, axis=0))),
                          index=dates, columns=["A", "B"])
    factors = pd.DataFrame({"market": factor}, index=dates[1:])
    return prices, factors


def _shocks():
    return {
        case: {horizon: {"factors": {"market": factor_shock * multiplier},
                         "issuers": {"A": 0.5 * multiplier}}
               for horizon, factor_shock in (("1m", -0.05), ("3m", -0.08))}
        for case, multiplier in (("mild", 0.5), ("central", 1.0), ("severe", 1.5))
    }


def _run(prices=None, factors=None, **kwargs):
    base_prices, base_factors = _history()
    return run_event_scenarios(prices if prices is not None else base_prices,
                               {"A": 0.6, "B": 0.4}, {"A": 0.2, "B": 0.8},
                               factors if factors is not None else base_factors,
                               _shocks(), **kwargs)


def test_six_confirmed_cases_use_same_holding_impacts_and_contribution_identity():
    result = _run()
    assert len(result["cases"]) == 6
    for case in result["cases"]:
        impacts = case["holding_impacts"]
        assert case["current"]["holding_contributions"]["A"] == pytest.approx(0.6 * impacts["A"])
        assert case["proposed"]["holding_contributions"]["A"] == pytest.approx(0.2 * impacts["A"])
        assert case["delta"]["estimated_return"] == pytest.approx(
            case["proposed"]["estimated_return"] - case["current"]["estimated_return"])
        assert sum(case["current"]["holding_contributions"].values()) == pytest.approx(
            case["current"]["estimated_return"])
    assert result["cases"][0]["current"]["estimated_return"] > result["cases"][2]["current"]["estimated_return"]
    assert result["probabilities"] == {"status": "omitted", "reason": "no_held_out_event_labels", "central": {}}
    json.dumps(result, allow_nan=False)


def test_incomplete_factor_dates_keep_deterministic_cases_but_omit_probabilities():
    prices, factors = _history()
    result = _run(prices, factors.drop(factors.index[10]))
    assert len(result["cases"]) == 6
    assert result["coverage"]["missing_factor_dates"] == 1
    assert result["coverage"]["factor_alignment_complete"] is False
    assert result["probabilities"]["reason"] == "incomplete_factor_alignment"


def test_unconfirmed_or_nonfinite_shocks_are_rejected():
    prices, factors = _history()
    shocks = _shocks()
    del shocks["mild"]["3m"]
    with pytest.raises(ValueError, match="1m and 3m"):
        run_event_scenarios(prices, {"A": 0.6, "B": 0.4}, {"A": 0.2, "B": 0.8}, factors, shocks)
    shocks = _shocks()
    shocks["central"]["1m"]["issuers"]["A"] = float("nan")
    with pytest.raises(ValueError, match="finite and real"):
        run_event_scenarios(prices, {"A": 0.6, "B": 0.4}, {"A": 0.2, "B": 0.8}, factors, shocks)


def test_calibration_requires_verified_nonoverlapping_heldout_events():
    prices, factors = _history()
    result = _run(prices, factors, calibration_events=[{"as_of": "2015-01-02"}])
    assert result["calibration"]["status"] == "failed"
    assert result["calibration"]["reason"] == "insufficient_held_out_events"
    assert result["probabilities"]["reason"] == "insufficient_held_out_events"


def test_verified_heldout_backtest_can_enable_seeded_central_ranges():
    prices, factors = _history(n=2400, seed=3)
    events = []
    for position in range(1480, 1480 + 12 * 63, 63):
        central_shocks = {}
        for horizon, days in (("1m", 21), ("3m", 63)):
            realized_factor_change = float(factors.iloc[position:position + days]["market"].sum())
            central_shocks[horizon] = {"factors": {"market": realized_factor_change}, "issuers": {}}
        events.append({"as_of": str(prices.index[position].date()), "verified": True,
                       "source": "test event ledger", "central_shocks": central_shocks})
    first = _run(prices, factors, seed=19, calibration_events=events)
    second = _run(prices, factors, seed=19, calibration_events=events)
    assert first["calibration"]["event_count"] == 12
    assert first["calibration"]["status"] == "passed", first["calibration"]
    assert first["probabilities"]["status"] == "available"
    assert first["probabilities"] == second["probabilities"]
    for horizon in ("1m", "3m"):
        for name in ("current", "proposed"):
            range_ = first["probabilities"]["central"][horizon][name]
            assert range_["p10"] <= range_["p50"] <= range_["p90"]
            assert 0 <= range_["probability_of_loss"] <= 1
