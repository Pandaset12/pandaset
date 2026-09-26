"""Validated public API and strict JSON report construction."""
import math
import numpy as np

from .validation import validate_prices, validate_weights, positive_integer, annual_rate
from .returns import asset_returns, portfolio_returns, cumulative_returns
from .risk import covariance, correlation, asset_volatility, portfolio_risk
from .performance import (annualized_return, annualized_arithmetic_mean, sharpe_ratio,
                          sortino_ratio, maximum_drawdown)
from .diversification import concentration, diversification_ratio


def _json_safe(value, warnings, path="report"):
    if isinstance(value, dict):
        return {str(k): _json_safe(v, warnings, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, warnings, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            warnings.append(f"{path}: nonfinite result represented as null")
            return None
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def analyze_portfolio(prices, weights, *, periods_per_year=252,
                      annual_risk_free_rate=0.0, annual_target_return=0.0, top_k=3):
    """Analyze a long-only, fully invested, constantly rebalanced portfolio.

    Rates, weights, returns, volatility and drawdown use decimal fractions.
    See docs/methodology.md for formulas and the complete input contract.
    """
    prices = validate_prices(prices)
    # Canonical internal ordering makes even reduction order deterministic.
    prices = prices.reindex(columns=sorted(prices.columns))
    weights = validate_weights(weights, prices.columns)
    periods_per_year = positive_integer(periods_per_year, "periods_per_year")
    top_k = positive_integer(top_k, "top_k")
    annual_risk_free_rate = annual_rate(annual_risk_free_rate, "annual_risk_free_rate")
    annual_target_return = annual_rate(annual_target_return, "annual_target_return")
    returns = asset_returns(prices)
    portfolio = portfolio_returns(returns, weights)
    sample, annual = covariance(returns, periods_per_year)
    corr = correlation(sample)
    vol = asset_volatility(annual)
    sigma, marginal, component, percentage = portfolio_risk(
        annual, weights, returns=returns, periods_per_year=periods_per_year)
    asset_cumulative = cumulative_returns(returns)
    portfolio_cumulative = cumulative_returns(portfolio)
    warnings = []
    if sigma == 0:
        warnings.append("Zero portfolio volatility: risk contributions and diversification ratio are undefined")
    zero_assets = vol.index[vol == 0].tolist()
    if zero_assets:
        warnings.append(f"Zero asset variance: correlations involving {zero_assets} are undefined")
    sharpe = sharpe_ratio(portfolio, periods_per_year, annual_risk_free_rate)
    sortino = sortino_ratio(portfolio, periods_per_year, annual_target_return)
    if sharpe is None:
        warnings.append("Sharpe ratio undefined: zero excess-return standard deviation")
    if sortino is None:
        warnings.append("Sortino ratio undefined: zero downside deviation")
    result = {
        "metadata": {
            "assets": list(prices.columns),
            "start_date": prices.index[0].isoformat(),
            "end_date": prices.index[-1].isoformat(),
            "return_observations": len(returns),
            "periods_per_year": periods_per_year,
            "annual_risk_free_rate": annual_risk_free_rate,
            "annual_target_return": annual_target_return,
            "units": "decimal fractions; risk percentages are fractions of total volatility",
            "assumptions": ["long-only, fully invested", "constant weights, rebalanced each observation",
                            "no transaction costs or taxes", "caller-supplied adjusted prices and common calendar",
                            "sample covariance (ddof=1); annual scaling assumes negligible serial correlation"],
        },
        "weights": weights.to_dict(),
        "series": {
            "dates": [d.isoformat() for d in returns.index],
            "asset_returns": {a: returns[a].tolist() for a in prices.columns},
            "portfolio_returns": portfolio.tolist(),
            "asset_cumulative_returns": {a: asset_cumulative[a].tolist() for a in prices.columns},
            "portfolio_cumulative_returns": portfolio_cumulative.tolist(),
        },
        "assets": {
            a: {"cumulative_return": asset_cumulative[a].iloc[-1],
                "geometric_annualized_return": annualized_return(returns[a], periods_per_year),
                "annualized_arithmetic_mean_return": annualized_arithmetic_mean(returns[a], periods_per_year),
                "annualized_volatility": vol[a],
                "marginal_risk_contribution": marginal[a],
                "component_risk_contribution": component[a],
                "percentage_risk_contribution": percentage[a]}
            for a in prices.columns
        },
        "matrices": {"sample_covariance": sample.to_dict(orient="index"),
                     "annualized_covariance": annual.to_dict(orient="index"),
                     "correlation": corr.to_dict(orient="index")},
        "portfolio": {
            "cumulative_return": portfolio_cumulative.iloc[-1],
            "geometric_annualized_return": annualized_return(portfolio, periods_per_year),
            "annualized_arithmetic_mean_return": annualized_arithmetic_mean(portfolio, periods_per_year),
            "annualized_volatility": sigma,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "maximum_drawdown": maximum_drawdown(portfolio),
            **concentration(weights, top_k),
            "diversification_ratio": diversification_ratio(weights, vol, sigma),
        },
    }
    result = _json_safe(result, warnings)
    result["warnings"] = warnings
    return result
