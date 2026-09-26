import pandas as pd
import pytest
from quant_engine.diversification import concentration, diversification_ratio


def test_equal_weights():
    result = concentration(pd.Series([.25] * 4), 2)
    assert result == {"hhi": .25, "effective_number_of_holdings": 4.,
                      "largest_position_weight": .25, "top_k": 2, "top_k_position_weight": .5}


def test_concentration_and_top_k():
    w = pd.Series({"A": .7, "B": .2, "C": .1})
    result = concentration(w, 2)
    assert result["hhi"] == pytest.approx(.54)
    assert result["effective_number_of_holdings"] == pytest.approx(1 / .54)
    assert result["largest_position_weight"] == .7
    assert result["top_k_position_weight"] == pytest.approx(.9)
    assert concentration(w, 9)["top_k_position_weight"] == pytest.approx(1)


def test_diversification():
    w = pd.Series({"A": .6, "B": .4})
    vol = pd.Series({"B": .3, "A": .2})
    assert diversification_ratio(w, vol, .0288 ** .5) == pytest.approx(2 ** .5)
    assert diversification_ratio(w, vol, 0) is None
