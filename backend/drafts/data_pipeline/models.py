from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class DataError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def normalize_symbols(symbols: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(item.strip().upper() for item in symbols))
    if not normalized or len(normalized) > 100 or any(not item for item in normalized):
        raise DataError("INVALID_SYMBOLS", "Supply between 1 and 100 nonempty symbols.")
    return normalized


class PriceBar(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
    symbol: str = Field(min_length=1, max_length=20)
    # UTC midnight is a session-date label, not the exchange closing instant.
    time: AwareDatetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    adj_close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    currency: Literal["USD"] = "USD"
    source: str
    data_mode: Literal["synthetic", "live"]
    adjustment: Literal["splits_and_dividends"] = "splits_and_dividends"
    fetched_at: AwareDatetime

    @field_validator("symbol")
    @classmethod
    def clean_symbol(cls, value):
        value = value.strip().upper()
        if not value:
            raise ValueError("Symbol cannot be blank.")
        return value

    @field_validator("time")
    @classmethod
    def session_timestamp(cls, value):
        value = value.astimezone(timezone.utc)
        if (value.hour, value.minute, value.second, value.microsecond) != (0, 0, 0, 0):
            raise ValueError("Daily bars use UTC midnight as the session-date label.")
        return value

    @model_validator(mode="after")
    def valid_ohlc(self):
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError("Raw OHLC prices are inconsistent.")
        return self


class PriceBatch(BaseModel):
    bars: list[PriceBar]
    source: str
    retrieval: Literal["refreshed", "cache", "stale_cache"]
    requested_start: date
    requested_end: date
    latest_sessions: dict[str, date]
    warnings: list[str] = Field(default_factory=list)


class QuantInputs(BaseModel):
    symbols: list[str]
    weights: list[float]
    dates: list[date]
    adjusted_prices: list[list[float]]
    observations: int
    return_observations: int
    source: str
    data_mode: Literal["synthetic", "live"]
    price_basis: Literal["splits_and_dividends"] = "splits_and_dividends"
    warnings: list[str]


def normalize_bars(rows: list[PriceBar | dict]) -> list[PriceBar]:
    """O(n) deduplication followed by one O(n log n) chronological sort."""
    unique = {}
    for row in rows:
        bar = PriceBar.model_validate(row)
        key = (bar.symbol, bar.time)
        previous = unique.get(key)
        if previous and previous != bar:
            raise DataError("CONFLICTING_PRICES", "Conflicting observations for the same symbol/date.")
        unique[key] = bar
    return sorted(unique.values(), key=lambda bar: (bar.time, bar.symbol))
