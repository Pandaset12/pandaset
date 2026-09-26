"""Regression inputs for the five numerical audit failures."""
import math

import numpy as np
import pandas as pd
import pytest

from quant_engine import analyze_portfolio
from quant_engine.performance import annualized_return, maximum_drawdown, sharpe_ratio, sortino_ratio
from quant_engine.returns import portfolio_returns
from quant_engine.risk import covariance, portfolio_risk
from quant_engine.validation import validate_weights


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_covariance_never_becomes_zero_volatility(bad):
    matrix = pd.DataFrame([[bad]], index=["A"], columns=["A"])
    with pytest.raises(ValueError, match="covariance must be finite"):
        portfolio_risk(matrix, pd.Series({"A": 1.}))


def test_overflowed_covariance_is_explicitly_rejected():
    prices = pd.DataFrame({"A": [1e-200, 1., 2.]},
                          index=pd.date_range("2026-01-01", periods=3))
    with np.errstate(over="ignore", invalid="ignore"):
        with pytest.raises(ValueError, match="covariance exceeds"):
            analyze_portfolio(prices, {"A": 1.})


def test_small_positive_variance_lost_in_rounded_covariance():
    epsilon = 2. ** -30
    returns = pd.DataFrame({"A": [.125, -.125, .125, -.125],
                            "B": [-.125 + epsilon, .125 + epsilon,
                                  -.125 - epsilon, .125 - epsilon]})
    weights = pd.Series({"A": .5, "B": .5})
    _, annual = covariance(returns, 1)
    # The original quadratic form is exactly zero on this rounded matrix.
    assert weights.dot(annual.dot(weights)) == 0
    sigma, _, component, percentage = portfolio_risk(
        annual, weights, returns=returns, periods_per_year=1)
    assert sigma > 0
    assert sigma == pytest.approx(epsilon / math.sqrt(3), rel=1e-14, abs=0)
    assert component.sum() == pytest.approx(sigma, rel=1e-14, abs=0)
    assert percentage.sum() == pytest.approx(1)


def test_nearly_hedged_public_report_retains_positive_volatility():
    epsilon = 2. ** -30
    returns = np.array([[.125, -.125 + epsilon], [-.125, .125 + epsilon],
                        [.125, -.125 - epsilon], [-.125, .125 - epsilon]])
    prices = pd.DataFrame(np.vstack([np.ones(2), np.cumprod(1 + returns, axis=0)]),
                          columns=["A", "B"], index=pd.date_range("2026-01-01", periods=5))
    report = analyze_portfolio(prices, {"A": .5, "B": .5}, periods_per_year=1)
    direct = np.std(report["series"]["portfolio_returns"], ddof=1)
    assert report["portfolio"]["annualized_volatility"] > 0
    assert report["portfolio"]["annualized_volatility"] == pytest.approx(direct, rel=1e-7, abs=0)


@pytest.mark.parametrize("exponent", [20, 50])
def test_near_hedge_precision_across_scales(exponent):
    epsilon = 2. ** -exponent
    returns = pd.DataFrame({"A": [.125, -.125, .125, -.125],
                            "B": [-.125 + epsilon, .125 + epsilon,
                                  -.125 - epsilon, .125 - epsilon]})
    weights = pd.Series({"A": .5, "B": .5})
    _, annual = covariance(returns, 1)
    sigma, _, component, percentage = portfolio_risk(
        annual, weights, returns=returns, periods_per_year=1)
    assert sigma == pytest.approx(epsilon / math.sqrt(3), rel=1e-14, abs=0)
    assert component.sum() == pytest.approx(sigma, rel=1e-14, abs=0)
    assert percentage.sum() == pytest.approx(1)


def test_weight_tolerance_cannot_create_return_below_minus_one():
    weights = validate_weights({"A": 1 + 5e-11}, ["A"])
    returns = pd.DataFrame({"A": [-1 + 1e-12, .1]})
    assert returns.dot(weights).iloc[0] < -1
    with pytest.raises(ValueError, match="portfolio returns"):
        portfolio_returns(returns, weights)
    prices = pd.DataFrame({"A": [1., 1e-12, 1.1e-12]},
                          index=pd.date_range("2026-01-01", periods=3))
    with pytest.raises(ValueError, match="portfolio returns"):
        analyze_portfolio(prices, weights)


@pytest.mark.parametrize("bad", [-1.00000000001, -1., np.nan, np.inf])
def test_geometric_annualization_does_not_skip_invalid_observations(bad):
    with pytest.raises(ValueError, match="returns must be finite and greater than -1"):
        annualized_return(pd.Series([bad, .1]), 2)


def test_drawdown_after_wealth_overflow_and_recovery():
    returns = pd.Series([1.] * 1100 + [-.5, 1., -.25])
    assert maximum_drawdown(returns) == pytest.approx(.5, rel=1e-14)


def test_drawdown_after_wealth_underflow():
    assert maximum_drawdown(pd.Series([-.5] * 1100 + [1.] * 1100)) == 1.


def test_large_risk_free_rate_does_not_erase_return_variation():
    returns = pd.Series([.1, .2, .3])
    ratio = sharpe_ratio(returns, 1, 1e20)
    assert ratio == pytest.approx((.2 - 1e20) / .1)


def test_unrepresentable_sharpe_is_explicitly_rejected():
    with pytest.raises(ValueError, match="Sharpe ratio exceeds"):
        sharpe_ratio(pd.Series([.1, .2, .3]), 1, np.finfo(float).max)


@pytest.mark.parametrize("target", [1e200, np.finfo(float).max])
def test_extreme_target_does_not_overflow_downside_squares(target):
    assert sortino_ratio(pd.Series([.1, .2, .3]), 1, target) == pytest.approx(-1.)


def test_small_downside_squares_do_not_underflow():
    assert sortino_ratio(pd.Series([-1e-200, 1e-200, -1e-200]), 1) == pytest.approx(-1 / math.sqrt(6))


def test_unrepresentable_sortino_does_not_claim_zero_downside():
    with pytest.raises(ValueError, match="Sortino ratio exceeds"):
        sortino_ratio(pd.Series([-1e-300, 1e300]), 1)


def test_representable_volatility_with_underflowing_variance():
    matrix = pd.DataFrame([[1., 0.], [0., 0.]], index=["A", "B"], columns=["A", "B"])
    sigma, marginal, component, percentage = portfolio_risk(matrix, pd.Series({"A": 1e-200, "B": 1.}))
    assert sigma == pytest.approx(1e-200, rel=1e-14, abs=0)
    assert marginal["A"] == pytest.approx(1)
    assert component.sum() == pytest.approx(sigma, rel=1e-14, abs=0)
    assert percentage.sum() == pytest.approx(1)
