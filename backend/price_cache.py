"""Short-lived, per-symbol price reuse across preflight and analysis requests."""

from threading import RLock
from time import monotonic

import pandas as pd


class _MisalignedHistory(Exception):
    pass


class RecentPriceCache:
    def __init__(self, ttl_seconds: float = 60):
        self.ttl_seconds = ttl_seconds
        self.lock = RLock()
        self.entries: dict[str, tuple[float, int, pd.Series]] = {}

    def prices(self, provider, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        # The provider's default history window also covers analysis. Holding the
        # lock through a miss prevents simultaneous requests from duplicating it.
        with self.lock:
            now = monotonic()
            requested_window = max(lookback_days, 252)
            for symbol in symbols:
                cached = self.entries.get(symbol)
                if cached is None or cached[0] <= now or cached[1] < requested_window:
                    frame = provider.prices([symbol], lookback_days=requested_window)
                    self.entries[symbol] = (monotonic() + self.ttl_seconds, requested_window, frame[symbol].copy())
            series = [self.entries[symbol][2] for symbol in symbols]
            if any(not item.index.equals(series[0].index) for item in series[1:]):
                raise _MisalignedHistory()
            return pd.concat(series, axis=1).tail(lookback_days + 1).copy()


class CachedPriceProvider:
    def __init__(self, provider, cache: RecentPriceCache):
        self.provider = provider
        self.cache = cache

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        try:
            return self.cache.prices(self.provider, symbols, lookback_days)
        except _MisalignedHistory:
            # Preserve the source provider's alignment checks and error mapping.
            return self.provider.prices(symbols, lookback_days=lookback_days)
