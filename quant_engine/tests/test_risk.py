import numpy as np
import pandas as pd
import pytest
from quant_engine.risk import covariance, correlation, asset_volatility, portfolio_risk


def test_known_sample_covariance():
    r = pd.DataFrame({"A": [-.1, 0, .1], "B": [.1, 0, -.1]})
    sample, annual = covariance(r, 4)
    np.testing.assert_allclose(sample, [[.01, -.01], [-.01, .01]])
    np.testing.assert_allclose(annual, [[.04, -.04], [-.04, .04]])
    np.testing.assert_allclose(asset_volatility(annual), [.2, .2])
    np.testing.assert_allclose(correlation(sample), [[1, -1], [-1, 1]])


def test_known_diagonal_risk():
    matrix = pd.DataFrame([[.04, 0], [0, .09]], index=["A", "B"], columns=["A", "B"])
    sigma, marginal, component, percentage = portfolio_risk(matrix, pd.Series({"B": .4, "A": .6}))
    assert sigma == pytest.approx(np.sqrt(.0288))
    np.testing.assert_allclose(marginal, np.array([.024, .036]) / np.sqrt(.0288))
    np.testing.assert_allclose(component, [np.sqrt(.0288) / 2] * 2)
    np.testing.assert_allclose(percentage, [.5, .5])
    assert component.sum() == pytest.approx(sigma)
    assert percentage.sum() == pytest.approx(1)


def test_identical_assets():
    r = pd.DataFrame({"A": [-.1, .2, .05], "B": [-.1, .2, .05]})
    sample, annual = covariance(r)
    np.testing.assert_allclose(correlation(sample), np.ones((2, 2)))
    sigma, _, _, _ = portfolio_risk(annual, pd.Series({"A": .3, "B": .7}))
    assert sigma == pytest.approx(asset_volatility(annual)["A"])


def test_risk_invariants_and_direct_series():
    r = pd.DataFrame({"A": [-.1, .2, .03, -.05], "B": [.02, -.03, .1, .04]})
    _, annual = covariance(r, 12)
    w = pd.Series({"A": .4, "B": .6})
    sigma, _, component, percentage = portfolio_risk(annual, w)
    assert sigma == pytest.approx(r.dot(w).std(ddof=1) * np.sqrt(12))
    assert component.sum() == pytest.approx(sigma)
    assert percentage.sum() == pytest.approx(1)


def test_zero_volatility_risk():
    matrix = pd.DataFrame(np.zeros((2, 2)), index=["A", "B"], columns=["A", "B"])
    sigma, marginal, component, percentage = portfolio_risk(matrix, pd.Series({"A": .5, "B": .5}))
    assert sigma == 0
    assert all(v.isna().all() for v in [marginal, component, percentage])
    assert correlation(matrix).isna().all().all()


def test_constant_nonzero_returns_have_exact_zero_covariance():
    sample, annual = covariance(pd.DataFrame({"A": [.1] * 3, "B": [.2] * 3}))
    np.testing.assert_array_equal(sample, np.zeros((2, 2)))
    np.testing.assert_array_equal(annual, np.zeros((2, 2)))


def test_perfect_hedge_zero_portfolio_volatility():
    matrix = pd.DataFrame([[.04, -.04], [-.04, .04]], index=["A", "B"], columns=["A", "B"])
    sigma, marginal, component, percentage = portfolio_risk(matrix, pd.Series({"A": .5, "B": .5}))
    assert sigma == 0
    assert all(v.isna().all() for v in [marginal, component, percentage])


def test_negative_hedging_contribution():
    matrix = pd.DataFrame([[.04, -.03], [-.03, .09]], index=["A", "B"], columns=["A", "B"])
    sigma, _, component, percentage = portfolio_risk(matrix, pd.Series({"A": .9, "B": .1}))
    assert component["B"] < 0
    assert component.sum() == pytest.approx(sigma)
    assert percentage.sum() == pytest.approx(1)
