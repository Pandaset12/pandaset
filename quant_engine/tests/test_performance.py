import numpy as np
import pandas as pd
import pytest
from quant_engine.performance import (annualized_return, annualized_arithmetic_mean,
                                     sharpe_ratio, sortino_ratio, maximum_drawdown, periodic_rate)


def test_known_annualization():
    r = pd.Series([.1, -.1])
    assert annualized_return(r, 4) == pytest.approx(.99 ** 2 - 1)
    assert annualized_arithmetic_mean(r, 4) == pytest.approx(0)


def test_known_ratios():
    r = pd.Series([.1, -.05])
    assert sharpe_ratio(r, 2) == pytest.approx(1 / 3)
    assert sortino_ratio(r, 2) == pytest.approx(1)
    assert periodic_rate(.21, 2) == pytest.approx(.1)
    assert sharpe_ratio(r, 2, .21) == pytest.approx(-1)
    # Excess returns are 0 and -.15; all two observations enter downside mean.
    assert sortino_ratio(r, 2, .21) == pytest.approx(-1)


@pytest.mark.parametrize("r,expected", [([.1, -.1], .1), ([-.2, .1], .2),
                                         ([.1, .2], 0), ([.2, -.5, .1, .9], .5)])
def test_drawdown(r, expected):
    assert maximum_drawdown(pd.Series(r)) == pytest.approx(expected)


def test_undefined_ratios():
    assert sharpe_ratio(pd.Series([0., 0., 0.])) is None
    assert sharpe_ratio(pd.Series([.125, .125])) is None
    assert sharpe_ratio(pd.Series([.1, .1, .1])) is None
    assert sortino_ratio(pd.Series([0., 0.])) is None
    assert sortino_ratio(pd.Series([.1, .2])) is None
    assert np.isfinite(sortino_ratio(pd.Series([-.1, -.1])))
