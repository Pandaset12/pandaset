"""Adjusted daily Alpaca stock bars for portfolio calculations."""

import json
import hashlib
import math
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable


NEW_YORK = ZoneInfo("America/New_York")
MAX_PAGES = 100


class CoverageError(MarketHistoryNotFound, ProviderUnavailable):
    """A requested symbol lacks complete aligned history."""


class RateLimitError(ProviderUnavailable):
    """Alpaca rejected a request because of its rate limit."""


class AlpacaHistoryProvider:
    data_mode = "live"
    data_source = "alpaca_adjusted_daily"
    freshness = "unknown"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        feed: str | None,
        timeout_seconds: float = 15,
        *,
        cache_path: Path | None = None,
        cache_allowed: bool = False,
        cache_ttl: timedelta = timedelta(hours=18),
    ):
        if timeout_seconds <= 0 or cache_ttl <= timedelta(0):
            raise ValueError("Timeout and cache TTL must be positive.")
        if feed is not None and feed not in ("iex", "sip"):
            raise ValueError("ALPACA_HISTORY_FEED must be iex or sip.")
        if cache_allowed and cache_path is None:
            raise ValueError("A durable cache path is required when caching is enabled.")
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()
        self._cache_account = hashlib.sha256(self._api_key.encode("utf-8")).hexdigest()
        self.feed = feed
        self.adjustment = "all"
        self._timeout_seconds = timeout_seconds
        self._cache_path = Path(cache_path) if cache_allowed else None
        self._cache_ttl = cache_ttl
        if self._cache_path is not None:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._db() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS adjusted_daily_history "
                    "(account_id TEXT NOT NULL, feed TEXT NOT NULL, adjustment TEXT NOT NULL, "
                    "symbol TEXT NOT NULL, received_at TEXT NOT NULL, rows_json TEXT NOT NULL, "
                    "PRIMARY KEY(account_id, feed, adjustment, symbol))"
                )

    def _db(self):
        if self._cache_path is None:
            raise RuntimeError("Caching is disabled.")
        return sqlite3.connect(self._cache_path, timeout=5)

    def _cached(self, symbol: str, count: int, cutoff: date):
        if self._cache_path is None:
            return None
        try:
            with self._db() as db:
                row = db.execute(
                    "SELECT received_at, rows_json FROM adjusted_daily_history "
                    "WHERE account_id=? AND feed=? AND adjustment=? AND symbol=?",
                    (self._cache_account, self.feed, self.adjustment, symbol),
                ).fetchone()
            if row is None:
                return None
            received_at = datetime.fromisoformat(row[0])
            if datetime.now(timezone.utc) - received_at > self._cache_ttl:
                return None
            points = [(date.fromisoformat(day), float(close)) for day, close in json.loads(row[1])]
            if (len(points) < count or points[-1][0] >= cutoff
                    or any(left[0] >= right[0] for left, right in zip(points, points[1:]))
                    or any(not math.isfinite(close) or close <= 0 for _, close in points)):
                return None
            return points[-count:], received_at
        except (sqlite3.Error, ValueError, TypeError, OverflowError):
            return None

    def _save(self, symbol: str, points: list[tuple[date, float]], received_at: datetime):
        if self._cache_path is None:
            return
        try:
            with self._db() as db:
                db.execute(
                    "INSERT OR REPLACE INTO adjusted_daily_history VALUES (?, ?, ?, ?, ?, ?)",
                    (self._cache_account, self.feed, self.adjustment, symbol, received_at.isoformat(),
                     json.dumps([(day.isoformat(), close) for day, close in points])),
                )
        except sqlite3.Error:
            pass

    def _fetch(self, symbols: list[str], start: date, end: datetime, page_token: str | None):
        params = {
            "symbols": ",".join(symbols), "timeframe": "1Day", "adjustment": "all",
            "feed": self.feed, "start": start.isoformat(), "end": end.isoformat(),
            "limit": 10000, "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token
        request = Request(
            f"https://data.alpaca.markets/v2/stocks/bars?{urlencode(params)}",
            headers={"APCA-API-KEY-ID": self._api_key,
                     "APCA-API-SECRET-KEY": self._api_secret,
                     "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise RateLimitError("Alpaca history rate limit was reached.") from exc
            if exc.code in (401, 403):
                raise ProviderUnavailable("Alpaca rejected the credentials or selected history feed.") from exc
            if exc.code == 404:
                raise CoverageError("Alpaca has no history for one or more requested symbols.") from exc
            raise ProviderUnavailable(f"Alpaca history request failed with HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailable("Alpaca history is unavailable or returned invalid data.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("bars"), dict):
            raise ProviderUnavailable("Alpaca returned a malformed history response.")
        return payload

    @staticmethod
    def _points(rows: list, symbol: str, cutoff: date, count: int):
        observations: dict[date, float] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ProviderUnavailable(f"Alpaca returned malformed history for {symbol}.")
            try:
                stamp = datetime.fromisoformat(str(row["t"]).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("Missing timezone")
                day = stamp.astimezone(NEW_YORK).date()
                if isinstance(row["c"], bool):
                    raise ValueError("Boolean close")
                close = float(row["c"])
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ProviderUnavailable(f"Alpaca returned malformed history for {symbol}.") from exc
            if day >= cutoff:
                continue
            if not math.isfinite(close) or close <= 0 or day in observations:
                raise ProviderUnavailable(f"Alpaca returned invalid or duplicate prices for {symbol}.")
            observations[day] = close
        points = sorted(observations.items())
        if len(points) < count:
            raise CoverageError(
                f"Alpaca has only {len(points) - 1} return observations for {symbol}; {count - 1} required."
            )
        return points[-count:]

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        if not self._api_key or not self._api_secret or not self.feed:
            raise ProviderUnavailable("Alpaca history requires ALPACA_API_KEY, ALPACA_API_SECRET, and ALPACA_HISTORY_FEED.")
        normalized = [symbol.strip().upper() for symbol in symbols]
        if not normalized or len(normalized) > 25 or len(set(normalized)) != len(normalized):
            raise ValueError("History requests require one to 25 unique symbols.")
        if not 1 <= lookback_days <= 1000:
            raise ValueError("Requested history window is outside the supported range.")
        count = lookback_days + 1
        now = datetime.now(NEW_YORK)
        cutoff = now.date()
        end = datetime.combine(cutoff, time.min, NEW_YORK).astimezone(timezone.utc)
        start = cutoff - timedelta(days=max(30, count * 4))
        by_symbol: dict[str, list[tuple[date, float]]] = {}
        received: dict[str, datetime] = {}
        cache_hits: list[str] = []
        for symbol in normalized:
            cached = self._cached(symbol, count, cutoff)
            if cached is not None:
                by_symbol[symbol], received[symbol] = cached
                cache_hits.append(symbol)

        def fetch_symbols(requested: list[str]):
            if not requested:
                return
            rows = {symbol: [] for symbol in requested}
            token = None
            seen = set()
            for _ in range(MAX_PAGES):
                payload = self._fetch(requested, start, end, token)
                bars = payload["bars"]
                for symbol, items in bars.items():
                    if symbol not in rows or not isinstance(items, list):
                        raise ProviderUnavailable("Alpaca returned malformed symbol history.")
                    rows[symbol].extend(items)
                token = payload.get("next_page_token")
                if token is None:
                    break
                if not isinstance(token, str) or not token or token in seen:
                    raise ProviderUnavailable("Alpaca returned an invalid history page token.")
                seen.add(token)
            else:
                raise ProviderUnavailable("Alpaca history exceeded the pagination limit.")
            fetched_at = datetime.now(timezone.utc)
            for symbol in requested:
                points = self._points(rows[symbol], symbol, cutoff, count)
                by_symbol[symbol] = points
                received[symbol] = fetched_at
                self._save(symbol, points, fetched_at)

        fetch_symbols([symbol for symbol in normalized if symbol not in by_symbol])

        def aligned() -> bool:
            first = [day for day, _ in by_symbol[normalized[0]]]
            return all([day for day, _ in by_symbol[symbol]] == first for symbol in normalized[1:])

        if cache_hits and not aligned():
            fetch_symbols(cache_hits)
            cache_hits = []
        if not aligned():
            raise CoverageError("Alpaca histories do not share the same trading dates.")
        dates = [day for day, _ in by_symbol[normalized[0]]]
        frame = pd.DataFrame(
            {symbol: [close for _, close in by_symbol[symbol]] for symbol in normalized},
            index=pd.to_datetime(dates, utc=True),
        )
        frame.index.name = "date"
        frame.attrs["provenance"] = {
            "data_mode": self.data_mode, "data_source": self.data_source,
            "feed": self.feed, "adjustment": self.adjustment,
            "session_date": dates[-1].isoformat(),
            "retrieved_at": max(received.values()).isoformat(),
            "freshness": "stale" if (cutoff - dates[-1]).days > 5 else "fresh",
            "cache_symbols": cache_hits,
            "warnings": [f"Alpaca {self.feed.upper()} adjusted daily closes; not intraday quotes."],
        }
        return frame
