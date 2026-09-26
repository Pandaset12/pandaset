"""Twelve Data daily-price adapter; never exposes credentials or upstream payloads."""
import json
import math
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable


class TwelveDataPriceProvider:
    data_mode = "live"
    data_source = "twelve_data_adjusted_daily"
    freshness = "unknown"

    def __init__(self, api_key: str, timeout_seconds: float = 15):
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def _fetch(self, symbols: list[str], outputsize: int) -> dict:
        params = urlencode({
            "symbol": ",".join(symbols), "interval": "1day",
            "outputsize": outputsize, "adjust": "all", "timezone": "UTC",
            "apikey": self._api_key,
        })
        request = Request(
            f"https://api.twelvedata.com/time_series?{params}",
            headers={"Accept": "application/json", "User-Agent": "PortfolioLens/1.0"},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderUnavailable("Twelve Data could not be reached or returned invalid data.") from exc
        if not isinstance(payload, dict):
            raise ProviderUnavailable("Twelve Data returned an invalid response.")
        return payload

    @staticmethod
    def _series(payload: dict, symbol: str) -> dict:
        if isinstance(payload.get("values"), list):
            meta = payload.get("meta") or {}
            if str(meta.get("symbol", symbol)).upper() == symbol:
                item = payload
            else:
                item = None
        else:
            candidates = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            item = next((value for key, value in candidates.items() if str(key).upper() == symbol), None)
        if item is None:
            raise MarketHistoryNotFound(f"Twelve Data has no history for {symbol}.")
        if not isinstance(item, dict) or item.get("status") == "error" or not isinstance(item.get("values"), list):
            raise ProviderUnavailable(f"Twelve Data has no usable history for {symbol}.")
        return item

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        normalized = [symbol.strip().upper() for symbol in symbols]
        if not self._api_key:
            raise ProviderUnavailable("Twelve Data is selected but TWELVE_DATA_API_KEY is not configured.")
        if not normalized or len(normalized) > 8 or len(set(normalized)) != len(normalized):
            raise ProviderUnavailable("Twelve Data requests require one to eight unique symbols.")
        if not 1 <= lookback_days <= 1000:
            raise ProviderUnavailable("Requested history window is outside the supported range.")

        payload = self._fetch(normalized, lookback_days + 1)
        if payload.get("status") == "error":
            raise ProviderUnavailable("Twelve Data rejected the history request.")
        columns, common_dates = {}, None
        for symbol in normalized:
            rows = self._series(payload, symbol)["values"]
            observations = {}
            for row in rows:
                if not isinstance(row, dict):
                    raise ProviderUnavailable(f"Twelve Data returned malformed history for {symbol}.")
                try:
                    stamp = date.fromisoformat(str(row.get("datetime"))[:10])
                    close = float(row.get("close"))
                except (TypeError, ValueError):
                    raise ProviderUnavailable(f"Twelve Data returned malformed history for {symbol}.") from None
                if not math.isfinite(close) or close <= 0 or stamp in observations:
                    raise ProviderUnavailable(f"Twelve Data returned invalid prices for {symbol}.")
                observations[stamp] = close
            dates = sorted(observations)
            if len(dates) < 2:
                raise ProviderUnavailable(f"Twelve Data returned fewer than two prices for {symbol}.")
            if common_dates is not None and dates != common_dates:
                raise ProviderUnavailable("Twelve Data histories do not share the same trading dates.")
            common_dates = dates
            columns[symbol] = [observations[stamp] for stamp in dates]

        frame = pd.DataFrame(columns, index=pd.to_datetime(common_dates, utc=True))
        frame.index.name = "date"
        return frame
