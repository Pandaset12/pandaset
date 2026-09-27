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
        self.entries: dict[tuple[type, str, str, str, str], tuple[float, int, pd.Series, dict]] = {}

    def prices(self, provider, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        # The provider's default history window also covers analysis. Holding the
        # lock through a miss prevents simultaneous requests from duplicating it.
        with self.lock:
            now = monotonic()
            requested_window = max(lookback_days, 252)
            source = (type(provider), getattr(provider, "_api_key", ""),
                      getattr(provider, "feed", ""), getattr(provider, "adjustment", ""))
            hits = []
            for symbol in symbols:
                cache_key = (*source, symbol)
                cached = self.entries.get(cache_key)
                if cached is None or cached[0] <= now or cached[1] < requested_window:
                    frame = provider.prices([symbol], lookback_days=requested_window)
                    self.entries[cache_key] = (monotonic() + self.ttl_seconds, requested_window,
                                               frame[symbol].copy(), frame.attrs.get("provenance", {}).copy())
                else:
                    hits.append(symbol)
            series = [self.entries[(*source, symbol)][2] for symbol in symbols]
            if any(not item.index.equals(series[0].index) for item in series[1:]):
                raise _MisalignedHistory()
            frame = pd.concat(series, axis=1).tail(lookback_days + 1).copy()
            provenance = max(
                (self.entries[(*source, symbol)][3] for symbol in symbols),
                key=lambda item: item.get("retrieved_at", ""),
            ).copy()
            if provenance:
                provenance["cache_symbols"] = hits
                if "session_date" in provenance and len(frame.index):
                    provenance["session_date"] = frame.index[-1].date().isoformat()
                frame.attrs["provenance"] = provenance
            return frame


class CachedPriceProvider:
    def __init__(self, provider, cache: RecentPriceCache, *, enabled: bool = True):
        self.provider = provider
        self.cache = cache
        self.enabled = enabled

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        if not self.enabled:
            return self.provider.prices(symbols, lookback_days=lookback_days)
        try:
            return self.cache.prices(self.provider, symbols, lookback_days)
        except _MisalignedHistory:
            # Preserve the source provider's alignment checks and error mapping.
            return self.provider.prices(symbols, lookback_days=lookback_days)
