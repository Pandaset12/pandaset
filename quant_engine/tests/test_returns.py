import numpy as np
import pandas as pd
import pytest
from quant_engine.returns import asset_returns, portfolio_returns, cumulative_returns


def test_known_returns(prices):
    r = asset_returns(prices)
    np.testing.assert_allclose(r["A"], [.1, -.1])
    np.testing.assert_allclose(r["B"], [0, .1])
    p = portfolio_returns(r, pd.Series({"B": .5, "A": .5}))
    np.testing.assert_allclose(p, [.05, 0], atol=1e-15)
    assert cumulative_returns(r)["A"].iloc[-1] == pytest.approx(-.01)
    assert cumulative_returns(p).iloc[-1] == pytest.approx(.05)


def test_constant_weight_not_buy_and_hold(prices):
    r = asset_returns(prices)
    p = portfolio_returns(r, pd.Series({"A": .5, "B": .5}))
    # Constant weights return 5%; buying equal initial holdings returns 4.5%.
    assert cumulative_returns(p).iloc[-1] == pytest.approx(.05)
    buy_hold = .5 * (99 / 100 - 1) + .5 * (110 / 100 - 1)
    assert buy_hold == pytest.approx(.045)
