"""Adjusted daily closes from Twelve Data, with opt-in licensed disk caching.

The caller must confirm its Twelve Data plan permits retention before enabling
the cache. A failed vendor request is never replaced with fictional prices.
"""

import json
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable


class CoverageError(MarketHistoryNotFound, ProviderUnavailable):
    """An allowed symbol lacks the requested complete, aligned history."""


class RateLimitError(ProviderUnavailable):
    """The vendor rejected a request because its request quota was reached."""


class TwelveDataPriceProvider:
    data_mode = "live"
    data_source = "twelve_data_adjusted_daily"
    freshness = "unknown"

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 15,
        *,
        cache_path: Path | None = None,
        cache_allowed: bool = False,
        cache_ttl: timedelta = timedelta(hours=18),
    ):
        if timeout_seconds <= 0 or cache_ttl <= timedelta(0):
            raise ValueError("Timeout and cache TTL must be positive.")
        if cache_allowed and cache_path is None:
            raise ValueError("A durable cache path is required when caching is enabled.")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._cache_path = Path(cache_path) if cache_allowed else None
        self._cache_ttl = cache_ttl
        if self._cache_path is not None:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._db() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS adjusted_daily_history "
                    "(symbol TEXT PRIMARY KEY, received_at TEXT NOT NULL, rows_json TEXT NOT NULL)"
                )

    def _db(self):
        if self._cache_path is None:
            raise RuntimeError("Caching is disabled.")
        return sqlite3.connect(self._cache_path, timeout=5)

    def _cached(self, symbol: str, count: int) -> tuple[list[tuple[date, float]], datetime] | None:
        if self._cache_path is None:
            return None
        try:
            with self._db() as db:
                row = db.execute(
                    "SELECT received_at, rows_json FROM adjusted_daily_history WHERE symbol=?",
                    (symbol,),
                ).fetchone()
            if row is None:
                return None
            received_at = datetime.fromisoformat(row[0])
            if datetime.now(timezone.utc) - received_at > self._cache_ttl:
                return None
            points = [(date.fromisoformat(day), float(close)) for day, close in json.loads(row[1])]
            if len(points) < count or any(not math.isfinite(close) or close <= 0 for _, close in points):
                return None
            return points[-count:], received_at
        except (sqlite3.Error, ValueError, TypeError, OverflowError):
            return None

    def _save(self, symbol: str, points: list[tuple[date, float]], received_at: datetime) -> None:
        if self._cache_path is None:
            return
        # Cache failure must not turn a valid upstream result into a data error.
        try:
            with self._db() as db:
                db.execute(
                    "INSERT OR REPLACE INTO adjusted_daily_history VALUES (?, ?, ?)",
                    (symbol, received_at.isoformat(), json.dumps([(day.isoformat(), close) for day, close in points])),
                )
        except sqlite3.Error:
            pass

    def _fetch(self, symbols: list[str], outputsize: int) -> dict:
        params = urlencode({
            "symbol": ",".join(symbols),
            "interval": "1day",
            "outputsize": outputsize,
            "adjust": "all",
            "timezone": "UTC",
            "apikey": self._api_key,
        })
        request = Request(
            f"https://api.twelvedata.com/time_series?{params}",
            headers={"Accept": "application/json", "User-Agent": "PortfolioLens/1.0"},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise RateLimitError("Twelve Data request quota was reached.") from exc
            if exc.code == 404:
                raise CoverageError("Twelve Data has no history for one or more requested symbols.") from exc
            raise ProviderUnavailable("Twelve Data rejected the history request.") from exc
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailable("Twelve Data could not be reached or returned invalid data.") from exc
        if not isinstance(payload, dict):
            raise ProviderUnavailable("Twelve Data returned an invalid response.")
        return payload

    @staticmethod
    def _error(payload: dict) -> None:
        if payload.get("status") != "error":
            return
        code = payload.get("code")
        message = str(payload.get("message", "")).lower()
        if str(code) == "404":
            raise CoverageError("Twelve Data has no history for one or more requested symbols.")
        if code in (429, 4290) or "limit" in message or "credit" in message or "quota" in message:
            raise RateLimitError("Twelve Data request quota was reached.")
        raise ProviderUnavailable("Twelve Data rejected the history request.")

    @classmethod
    def _series(cls, payload: dict, symbol: str) -> dict:
        cls._error(payload)
        if isinstance(payload.get("values"), list):
            meta = payload.get("meta") or {}
            item = payload if str(meta.get("symbol", symbol)).upper() == symbol else None
        else:
            candidates = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            item = next((value for key, value in candidates.items() if str(key).upper() == symbol), None)
        if not isinstance(item, dict):
            raise CoverageError(f"Twelve Data has no history for {symbol}.")
        cls._error(item)
        if not isinstance(item.get("values"), list):
            raise CoverageError(f"Twelve Data has no usable history for {symbol}.")
        return item

    @staticmethod
    def _points(item: dict, symbol: str, count: int) -> list[tuple[date, float]]:
        observations: dict[date, float] = {}
        for row in item["values"]:
            if not isinstance(row, dict):
                raise ProviderUnavailable(f"Twelve Data returned malformed history for {symbol}.")
            try:
                day = date.fromisoformat(str(row["datetime"])[:10])
                close = float(row["close"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderUnavailable(f"Twelve Data returned malformed history for {symbol}.") from exc
            if not math.isfinite(close) or close <= 0 or day in observations:
                raise ProviderUnavailable(f"Twelve Data returned invalid prices for {symbol}.")
            observations[day] = close
        points = sorted(observations.items())
        if len(points) < count:
            raise CoverageError(f"Twelve Data has only {len(points) - 1} return observations for {symbol}; {count - 1} required.")
        return points[-count:]

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        normalized = [symbol.strip().upper() for symbol in symbols]
        if not self._api_key:
            raise ProviderUnavailable("Twelve Data is selected but TWELVE_DATA_API_KEY is not configured.")
        if not normalized or len(normalized) > 25 or len(set(normalized)) != len(normalized):
            raise ValueError("History requests require one to 25 unique symbols.")
        if not 1 <= lookback_days <= 1000:
            raise ValueError("Requested history window is outside the supported range.")
        count = lookback_days + 1
        by_symbol: dict[str, list[tuple[date, float]]] = {}
        received: dict[str, datetime] = {}
        cache_hits: list[str] = []
        for symbol in normalized:
            cached = self._cached(symbol, count)
            if cached is not None:
                by_symbol[symbol], received[symbol] = cached
                cache_hits.append(symbol)
        def fetch_symbols(requested: list[str]) -> None:
            for start in range(0, len(requested), 8):
                batch = requested[start:start + 8]
                payload = self._fetch(batch, count)
                self._error(payload)
                fetched_at = datetime.now(timezone.utc)
                for symbol in batch:
                    points = self._points(self._series(payload, symbol), symbol, count)
                    by_symbol[symbol] = points
                    received[symbol] = fetched_at
                    self._save(symbol, points, fetched_at)

        fetch_symbols([symbol for symbol in normalized if symbol not in by_symbol])

        def aligned() -> bool:
            first = [day for day, _ in by_symbol[normalized[0]]]
            return all([day for day, _ in by_symbol[symbol]] == first for symbol in normalized[1:])

        # A cached series may be one session behind a newly fetched symbol.
        # Refresh those cached series once before reporting a coverage failure.
        if cache_hits and not aligned():
            fetch_symbols(cache_hits)
            cache_hits = []

        common_dates = [day for day, _ in by_symbol[normalized[0]]]
        if not aligned():
            raise CoverageError("Twelve Data histories do not share the same trading dates.")
        frame = pd.DataFrame(
            {symbol: [close for _, close in by_symbol[symbol]] for symbol in normalized},
            index=pd.to_datetime(common_dates, utc=True),
        )
        frame.index.name = "date"
        latest = common_dates[-1]
        frame.attrs["provenance"] = {
            "data_mode": self.data_mode,
            "data_source": self.data_source,
            "adjustment": "all",
            "session_date": latest.isoformat(),
            "retrieved_at": max(received.values()).isoformat(),
            "freshness": "stale" if (datetime.now(timezone.utc).date() - latest).days > 5 else "fresh",
            "cache_symbols": cache_hits,
            "warnings": ["Adjusted daily end-of-day closes; not intraday quotes."],
        }
        return frame
