"""Read-only Alpaca stock-symbol lookup for portfolio entry."""

import hashlib
import json
import re
import time
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AssetLookupUnavailable(Exception):
    """The stock directory cannot be searched right now."""


_CACHE_SECONDS = 15 * 60
_lock = Lock()
_cache: tuple[str, float, list[dict[str, str]]] | None = None
_GOOGLE_SYMBOLS = {"GOOGL": 0, "GOOG": 1}
_SYMBOL = re.compile(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*\Z", re.ASCII)


def _fetch_catalog(api_key: str, api_secret: str, base_url: str, timeout: float) -> list[dict[str, str]]:
    request = Request(
        base_url.rstrip("/") + "/v2/assets?status=active&asset_class=us_equity",
        headers={
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code in (401, 403):
            message = "Alpaca rejected access to its stock directory."
        elif exc.code == 429:
            message = "Alpaca stock search is rate limited. Try again shortly."
        else:
            message = f"Alpaca stock search failed with HTTP {exc.code}."
        raise AssetLookupUnavailable(message) from exc
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
        raise AssetLookupUnavailable("Alpaca stock search is temporarily unavailable.") from exc
    if not isinstance(payload, list):
        raise AssetLookupUnavailable("Alpaca returned an invalid stock directory.")
    catalog = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol, name = item.get("symbol"), item.get("name")
        if (item.get("status") != "active" or item.get("class") != "us_equity"
                or not isinstance(symbol, str) or not isinstance(name, str)
                or len(symbol) > 20 or not _SYMBOL.fullmatch(symbol) or not name.strip()):
            continue
        catalog.append({"symbol": symbol, "name": name.strip()[:160]})
    if not catalog:
        raise AssetLookupUnavailable("Alpaca returned an empty stock directory.")
    return catalog


def search_catalog(catalog: list[dict[str, str]], query: str, limit: int = 8) -> list[dict[str, str]]:
    term = query.strip().casefold()
    if not term:
        return []

    def score(item: dict[str, str]):
        symbol = item["symbol"].casefold()
        name = item["name"].casefold()
        if symbol == term:
            return (0, 0, symbol)
        if term == "google" and item["symbol"] in _GOOGLE_SYMBOLS:
            return (1, _GOOGLE_SYMBOLS[item["symbol"]], symbol)
        if symbol.startswith(term):
            return (2, 0, symbol)
        if name.startswith(term):
            return (3, 0, symbol)
        if re.search(r"\b" + re.escape(term), name):
            return (4, 0, symbol)
        return (5, 0, symbol)

    matches = [item for item in catalog
               if term in item["symbol"].casefold() or term in item["name"].casefold()
               or (term == "google" and item["symbol"] in _GOOGLE_SYMBOLS)]
    return sorted(matches, key=score)[:limit]


def search_alpaca_assets(
    query: str, api_key: str, api_secret: str, base_url: str, timeout: float,
) -> list[dict[str, str]]:
    global _cache
    identity = hashlib.sha256((base_url + "\0" + api_key + "\0" + api_secret).encode()).hexdigest()
    with _lock:
        if _cache is None or _cache[0] != identity or _cache[1] <= time.monotonic():
            catalog = _fetch_catalog(api_key, api_secret, base_url, timeout)
            _cache = (identity, time.monotonic() + _CACHE_SECONDS, catalog)
        else:
            catalog = _cache[2]
    return search_catalog(catalog, query)
