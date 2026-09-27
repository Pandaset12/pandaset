"""Server-side adapter for Alpaca's IEX stock snapshot endpoint."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class AlpacaQuotesUnavailable(Exception):
    """Alpaca could not provide a valid quote response."""


def _number(value, *, positive: bool = False):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("Invalid market price")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0) or (not positive and result < 0):
        raise ValueError("Invalid market price")
    return result


def fetch_alpaca_quotes(
    symbols: list[str], api_key: str, api_secret: str, timeout_seconds: float = 10,
) -> dict:
    query = urlencode({"symbols": ",".join(symbols), "feed": "iex"})
    request = Request(
        f"https://data.alpaca.markets/v2/stocks/snapshots?{query}",
        headers={
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read())
    except HTTPError as exc:
        if exc.code in (401, 403):
            message = "Alpaca rejected the credentials or IEX feed request."
        elif exc.code == 429:
            message = "Alpaca rate limit reached. Try again shortly."
        else:
            message = f"Alpaca snapshot request failed with HTTP {exc.code}."
        raise AlpacaQuotesUnavailable(message) from exc
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeError, OSError) as exc:
        raise AlpacaQuotesUnavailable("Alpaca market data is temporarily unavailable.") from exc

    if not isinstance(payload, dict):
        raise AlpacaQuotesUnavailable("Alpaca returned an invalid snapshot response.")

    quotes = []
    try:
        for symbol in symbols:
            snapshot = payload.get(symbol)
            if snapshot is None:
                quotes.append({
                    "symbol": symbol, "last_price": None, "last_trade_at": None,
                    "bid": None, "ask": None, "quote_at": None,
                })
                continue
            if not isinstance(snapshot, dict):
                raise ValueError("Invalid snapshot")
            trade = snapshot.get("latestTrade")
            quote = snapshot.get("latestQuote")
            trade = {} if trade is None else trade
            quote = {} if quote is None else quote
            if not isinstance(trade, dict) or not isinstance(quote, dict):
                raise ValueError("Invalid trade or quote")
            quotes.append({
                "symbol": symbol,
                "last_price": _number(trade.get("p"), positive=True),
                "last_trade_at": trade.get("t"),
                "bid": _number(quote.get("bp")),
                "ask": _number(quote.get("ap")),
                "quote_at": quote.get("t"),
            })
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise AlpacaQuotesUnavailable("Alpaca returned an invalid snapshot response.") from exc

    return {"feed": "IEX", "source": "alpaca", "quotes": quotes}
