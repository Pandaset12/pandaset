import numpy as np
import pandas as pd
import pytest
from quant_engine import analyze_portfolio


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, 0, -1])
def test_invalid_prices(prices, value):
    prices.iloc[1, 0] = value
    with pytest.raises(ValueError, match="finite, positive"):
        analyze_portfolio(prices, {"A": .5, "B": .5})


@pytest.mark.parametrize("weights", [{"A": 1}, {"A": .5, "C": .5}, {"A": -.1, "B": 1.1},
                                    {"A": .2, "B": .2}, {"A": np.nan, "B": .5},
                                    {"A": True, "B": 0}, {"A": "0.5", "B": .5}, [.5, .5],
                                    pd.Series([.5, .5], index=["A", "A"])])
def test_invalid_weights(prices, weights):
    with pytest.raises(ValueError):
        analyze_portfolio(prices, weights)


@pytest.mark.parametrize("kind", ["reversed", "duplicate_date", "nat", "non_date", "duplicate_asset",
                                 "empty_asset", "strings", "bool", "complex", "too_short", "no_assets"])
def test_invalid_structure(prices, kind):
    if kind == "reversed":
        prices = prices.iloc[::-1]
    elif kind == "duplicate_date":
        prices.index = [prices.index[0]] * 3
    elif kind == "nat":
        prices.index = pd.DatetimeIndex(["2026-01-01", None, "2026-01-03"])
    elif kind == "non_date":
        prices.index = range(3)
    elif kind == "duplicate_asset":
        prices.columns = ["A", "A"]
    elif kind == "empty_asset":
        prices.columns = ["A", ""]
    elif kind == "strings":
        prices = prices.astype(str)
    elif kind == "bool":
        prices = prices.astype(bool)
    elif kind == "complex":
        prices = prices.astype(complex)
    elif kind == "too_short":
        prices = prices.iloc[:2]
    elif kind == "no_assets":
        prices = prices.iloc[:, :0]
    with pytest.raises(ValueError):
        analyze_portfolio(prices, {"A": .5, "B": .5})


@pytest.mark.parametrize("kwargs", [{"periods_per_year": 0}, {"periods_per_year": 2.5},
                                    {"periods_per_year": True}, {"top_k": 0}, {"top_k": False},
                                    {"annual_risk_free_rate": -1}, {"annual_target_return": np.inf}])
def test_invalid_parameters(prices, kwargs):
    with pytest.raises(ValueError):
        analyze_portfolio(prices, {"A": .5, "B": .5}, **kwargs)


def test_no_mutation_or_normalization(prices):
    before = prices.copy(deep=True)
    weights = {"B": .5, "A": .5 + 1e-12}
    result = analyze_portfolio(prices, weights)
    pd.testing.assert_frame_equal(prices, before)
    assert result["weights"] == weights


def test_nullable_missing_rejected(prices):
    prices = prices.astype("Float64")
    prices.iloc[1, 0] = pd.NA
    with pytest.raises(ValueError):
        analyze_portfolio(prices, {"A": .5, "B": .5})
