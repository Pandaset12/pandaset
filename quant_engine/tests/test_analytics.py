import json
import numpy as np
import pandas as pd
import pytest
from quant_engine import analyze_portfolio


def test_full_report(prices):
    report = analyze_portfolio(prices, {"A": .5, "B": .5}, periods_per_year=2, top_k=1)
    p = report["portfolio"]
    assert p["cumulative_return"] == pytest.approx(.05)
    assert p["geometric_annualized_return"] == pytest.approx(.05)
    assert p["annualized_arithmetic_mean_return"] == pytest.approx(.05)
    assert p["annualized_volatility"] == pytest.approx(.05)
    assert p["sharpe_ratio"] == pytest.approx(1)
    assert p["sortino_ratio"] is None
    assert p["maximum_drawdown"] == pytest.approx(0)
    assert report["matrices"]["sample_covariance"]["A"]["B"] == pytest.approx(-.01)
    assert sum(a["component_risk_contribution"] for a in report["assets"].values()) == pytest.approx(.05)
    assert sum(a["percentage_risk_contribution"] for a in report["assets"].values()) == pytest.approx(1)
    assert json.loads(json.dumps(report, allow_nan=False)) == report


def test_column_order_and_determinism(prices):
    first = analyze_portfolio(prices, {"A": .6, "B": .4})
    assert first == analyze_portfolio(prices[["B", "A"]], {"B": .4, "A": .6})
    assert first == analyze_portfolio(prices, {"A": .6, "B": .4})


def test_constant_prices_json(prices):
    prices.loc[:, :] = 100.
    report = analyze_portfolio(prices, {"A": .5, "B": .5})
    assert report["portfolio"]["annualized_volatility"] == 0
    assert report["portfolio"]["sharpe_ratio"] is None
    assert report["portfolio"]["sortino_ratio"] is None
    assert report["portfolio"]["diversification_ratio"] is None
    assert report["assets"]["A"]["component_risk_contribution"] is None
    assert report["matrices"]["correlation"]["A"]["A"] is None
    assert report["warnings"]
    json.dumps(report, allow_nan=False)


def test_one_asset_and_zero_weight(prices):
    one = analyze_portfolio(prices[["A"]], {"A": 1.})
    assert one["assets"]["A"]["percentage_risk_contribution"] == pytest.approx(1)
    assert one["portfolio"]["diversification_ratio"] == pytest.approx(1)
    two = analyze_portfolio(prices, {"A": 1., "B": 0.})
    assert two["assets"]["B"]["component_risk_contribution"] == 0
    assert two["portfolio"] == one["portfolio"]


def test_zero_variance_asset(prices):
    prices["B"] = 100.
    report = analyze_portfolio(prices, {"A": .5, "B": .5})
    assert report["matrices"]["correlation"]["A"]["B"] is None
    assert report["assets"]["B"]["annualized_volatility"] == 0
    assert report["assets"]["B"]["percentage_risk_contribution"] == 0
    json.dumps(report, allow_nan=False)
