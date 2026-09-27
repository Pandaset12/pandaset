import pandas as pd

from backend.price_cache import CachedPriceProvider, RecentPriceCache


def test_preflight_and_analysis_share_prices_without_changing_requested_window():
    class CountingPrices:
        data_mode = "live"

        def __init__(self):
            self.calls = []

        def prices(self, symbols, lookback_days=252):
            self.calls.append((tuple(symbols), lookback_days))
            dates = pd.date_range("2020-01-01", periods=lookback_days + 1, tz="UTC")
            return pd.DataFrame({symbols[0]: range(len(dates))}, index=dates)

    source = CountingPrices()
    prices = CachedPriceProvider(source, RecentPriceCache())
    assert len(prices.prices(["SPY"], lookback_days=2)) == 3
    assert len(prices.prices(["SPY"])) == 253
    assert source.calls == [(("SPY",), 252)]
    assert len(prices.prices(["SPY"], lookback_days=1000)) == 1001
    assert len(prices.prices(["SPY"])) == 253
    assert source.calls == [(("SPY",), 252), (("SPY",), 1000)]
    assert prices.data_mode == "live"
