import json
import pytest
from quant_engine import compare_portfolios


def test_comparison(prices):
    result = compare_portfolios(prices, {"A": .5, "B": .5}, {"A": 1., "B": 0.}, periods_per_year=2)
    delta = result["portfolio_metric_differences"]
    assert delta["cumulative_return"] == pytest.approx(-.06)
    assert delta["maximum_drawdown"] == pytest.approx(.1)
    assert delta["hhi"] == pytest.approx(.5)
    assert delta["sortino_ratio"] is None
    assert result["baseline"]["series"]["dates"] == result["proposed"]["series"]["dates"]
    assert "top_k" not in delta
    json.dumps(result, allow_nan=False)


def test_identical_portfolios(prices):
    result = compare_portfolios(prices, {"A": .5, "B": .5}, {"B": .5, "A": .5})
    assert all(v is None or v == 0 for v in result["portfolio_metric_differences"].values())
