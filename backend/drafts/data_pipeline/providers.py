"""Fictional fixture reader retained from the inactive data-pipeline draft."""

import json
from datetime import date, datetime, time as day_time, timezone
from pathlib import Path
from typing import Protocol

from .models import DataError, PriceBar


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
