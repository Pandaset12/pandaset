from collections import deque
from datetime import date, datetime, time as day_time, timezone
from decimal import Decimal
from pathlib import Path
import json
from threading import Lock
import time
from typing import Protocol

import httpx
from pydantic import SecretStr, ValidationError

from .models import DataError, PriceBar, normalize_bars


class MarketProvider(Protocol):
    source: str
    def fetch(self, symbols: list[str], start: date, end: date) -> list[PriceBar]: ...
    def close(self) -> None: ...


class FixtureProvider:
    source = "synthetic_fixture"

    def fetch(self, symbols, start, end):
        fixture = json.loads((Path(__file__).parent / "sample_prices.json").read_text("utf-8"))
        if set(symbols) - fixture["prices"].keys():
            raise DataError("NO_DATA", "The fixture contains only NVDA, SPY, JPM, and TLT.")
        fetched_at = datetime.now(timezone.utc)
        rows = []
        for symbol in symbols:
            for session, value in zip(fixture["dates"], fixture["prices"][symbol], strict=True):
                session = date.fromisoformat(session)
                if start <= session <= end:
                    rows.append(PriceBar(
                        symbol=symbol, time=datetime.combine(session, day_time(), timezone.utc),
                        open=value, high=value, low=value, close=value, adj_close=value,
                        volume=1000, source=self.source, data_mode="synthetic", fetched_at=fetched_at,
                    ))
        return rows

    def close(self):
        pass


class TwelveDataProvider:
    """Fetch raw OHLC and split/dividend-adjusted close separately."""
    source = "twelvedata"

    def __init__(self, api_key: SecretStr, client=None, credits_per_minute=8):
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=20)
        self.owns_client = client is None
        self.credits_per_minute = credits_per_minute
        self.calls = deque()
        self.lock = Lock()

    def _reserve_credit(self):
        with self.lock:
            now = time.monotonic()
            while self.calls and self.calls[0] <= now - 60:
                self.calls.popleft()
            if len(self.calls) >= self.credits_per_minute:
                raise DataError("RATE_LIMITED", "Market-data minute quota is exhausted; retry later.")
            self.calls.append(now)

    def _request(self, symbol, start, end, adjust):
        params = dict(
            symbol=symbol, interval="1day", start_date=start.isoformat(), end_date=end.isoformat(),
            outputsize=5000, order="asc", country="United States", adjust=adjust,
            apikey=self.api_key.get_secret_value(),
        )
        for attempt in range(2):
            self._reserve_credit()
            try:
                response = self.client.get("https://api.twelvedata.com/time_series", params=params)
                if response.status_code == 429:
                    raise DataError("RATE_LIMITED", "Market provider rate limit reached.")
                if response.status_code >= 500 and attempt == 0:
                    time.sleep(0.25)
                    continue
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                if attempt == 0:
                    time.sleep(0.25)
                    continue
                raise DataError("PROVIDER_UNAVAILABLE", "Market provider request failed.") from None
            if payload.get("status") == "error":
                code = payload.get("code")
                raise DataError(
                    "RATE_LIMITED" if code == 429 else "PROVIDER_REJECTED",
                    "Provider rejected this request; check symbol, key, plan permissions and quota.",
                )
            meta = payload.get("meta", {})
            if meta.get("symbol", "").upper() != symbol or meta.get("currency") != "USD":
                raise DataError("INVALID_PROVIDER_DATA", "Unexpected instrument or currency returned.")
            rows = payload.get("values")
            if not isinstance(rows, list) or not rows:
                raise DataError("NO_DATA", "Provider returned no daily prices in the requested window.")
            if len(rows) >= 5000:
                raise DataError("INCOMPLETE_HISTORY", "Response may be truncated; use a smaller date window.")
            return rows
        raise DataError("PROVIDER_UNAVAILABLE", "Market provider request failed.")

    def fetch(self, symbols, start, end):
        bars = []
        fetched_at = datetime.now(timezone.utc)
        for symbol in symbols:
            raw = self._request(symbol, start, end, "none")
            adjusted = self._request(symbol, start, end, "all")
            try:
                raw_dates = [row["datetime"] for row in raw]
                adjusted_dates = [row["datetime"] for row in adjusted]
                if len(set(raw_dates)) != len(raw_dates) or len(set(adjusted_dates)) != len(adjusted_dates):
                    raise DataError("CONFLICTING_PRICES", "Provider returned duplicate session dates.")
                if set(raw_dates) != set(adjusted_dates):
                    raise DataError("INCOMPLETE_HISTORY", "Raw and adjusted price dates do not match.")
                adjusted_by_date = {row["datetime"]: row["close"] for row in adjusted}
                for row in raw:
                    session = date.fromisoformat(row["datetime"])
                    bars.append(PriceBar(
                        symbol=symbol, time=datetime.combine(session, day_time(), timezone.utc),
                        open=Decimal(row["open"]), high=Decimal(row["high"]), low=Decimal(row["low"]),
                        close=Decimal(row["close"]), adj_close=Decimal(adjusted_by_date[row["datetime"]]),
                        volume=row["volume"], source=self.source, data_mode="live", fetched_at=fetched_at,
                    ))
            except (KeyError, ValueError, ValidationError, ArithmeticError):
                raise DataError("INVALID_PROVIDER_DATA", "Provider returned invalid daily price fields.") from None
        return normalize_bars(bars)

    def close(self):
        if self.owns_client:
            self.client.close()
