import json
from datetime import datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest

from backend.alpaca_history import AlpacaHistoryProvider, CoverageError, RateLimitError
from backend.market_data_errors import ProviderUnavailable


def bar(day, close):
    return {"t": f"{day}T12:00:00Z", "c": close}


def response(payload):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return json.dumps(payload).encode()
    return Response()


def test_paginated_adjusted_daily_history_and_provenance(monkeypatch):
    calls = []
    pages = [
        {"bars": {"AAPL": [bar("2024-01-02", 100), bar("2024-01-03", 102)]}, "next_page_token": "next"},
        {"bars": {"MSFT": [bar("2024-01-02", 200), bar("2024-01-03", 203)]}, "next_page_token": None},
    ]

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return response(pages[len(calls) - 1])

    monkeypatch.setattr("backend.alpaca_history.urlopen", fake_urlopen)
    frame = AlpacaHistoryProvider("key", "secret", "iex", timeout_seconds=7).prices(["aapl", "msft"], 1)
    first = parse_qs(urlsplit(calls[0][0].full_url).query)
    second = parse_qs(urlsplit(calls[1][0].full_url).query)
    assert first["symbols"] == ["AAPL,MSFT"]
    assert first["timeframe"] == ["1Day"]
    assert first["adjustment"] == ["all"]
    assert first["feed"] == ["iex"]
    assert second["page_token"] == ["next"]
    assert calls[0][1] == 7
    assert calls[0][0].get_header("Apca-api-key-id") == "key"
    assert frame["AAPL"].tolist() == [100.0, 102.0]
    assert frame["MSFT"].tolist() == [200.0, 203.0]
    assert frame.attrs["provenance"]["data_source"] == "alpaca_adjusted_daily"
    assert frame.attrs["provenance"]["feed"] == "iex"


def test_missing_configuration_does_not_contact_alpaca(monkeypatch):
    monkeypatch.setattr("backend.alpaca_history.urlopen", lambda *_args, **_kwargs: pytest.fail("Unexpected call"))
    with pytest.raises(ProviderUnavailable, match="ALPACA_HISTORY_FEED"):
        AlpacaHistoryProvider("key", "secret", None).prices(["AAPL"])


@pytest.mark.parametrize("payload, error", [
    ({"bars": {"AAPL": [bar("2024-01-02", 100)]}}, CoverageError),
    ({"bars": {"AAPL": [bar("2024-01-02", 100), bar("2024-01-02", 101)]}}, ProviderUnavailable),
    ({"bars": {"AAPL": [bar("2024-01-02", 0), bar("2024-01-03", 101)]}}, ProviderUnavailable),
    ({"bars": {"AAPL": [bar("2024-01-02", 100), bar("2024-01-03", 101)],
               "MSFT": [bar("2024-01-02", 200), bar("2024-01-04", 201)]}}, CoverageError),
    ({"bars": "bad"}, ProviderUnavailable),
])
def test_invalid_or_unaligned_history_fails(monkeypatch, payload, error):
    monkeypatch.setattr("backend.alpaca_history.urlopen", lambda *_args, **_kwargs: response(payload))
    symbols = ["AAPL", "MSFT"] if isinstance(payload.get("bars"), dict) and "MSFT" in payload["bars"] else ["AAPL"]
    with pytest.raises(error):
        AlpacaHistoryProvider("key", "secret", "iex").prices(symbols, 1)


def test_current_incomplete_session_is_excluded(monkeypatch):
    today = datetime.now(ZoneInfo("America/New_York")).date()
    old = (today - timedelta(days=2)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    payload = {"bars": {"AAPL": [bar(old, 100), bar(yesterday, 101), bar(today.isoformat(), 999)]}}
    monkeypatch.setattr("backend.alpaca_history.urlopen", lambda *_args, **_kwargs: response(payload))
    frame = AlpacaHistoryProvider("key", "secret", "iex").prices(["AAPL"], 1)
    assert frame["AAPL"].tolist() == [100.0, 101.0]


@pytest.mark.parametrize("status,error", [(401, ProviderUnavailable), (403, ProviderUnavailable), (429, RateLimitError)])
def test_http_failures_are_explicit(monkeypatch, status, error):
    def fail(request, timeout):
        raise HTTPError(request.full_url, status, "error", None, None)
    monkeypatch.setattr("backend.alpaca_history.urlopen", fail)
    with pytest.raises(error):
        AlpacaHistoryProvider("key", "secret", "iex").prices(["AAPL"], 1)


def test_cache_requires_rights_and_isolated_by_feed(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="durable cache path"):
        AlpacaHistoryProvider("key", "secret", "iex", cache_allowed=True)
    payload = {"bars": {"AAPL": [bar("2024-01-02", 100), bar("2024-01-03", 101)]}}
    calls = []
    def fetch(request, timeout):
        calls.append(request.full_url)
        return response(payload)
    monkeypatch.setattr("backend.alpaca_history.urlopen", fetch)
    path = tmp_path / "history.sqlite3"
    iex = AlpacaHistoryProvider("key", "secret", "iex", cache_allowed=True, cache_path=path)
    assert iex.prices(["AAPL"], 1).attrs["provenance"]["cache_symbols"] == []
    assert iex.prices(["AAPL"], 1).attrs["provenance"]["cache_symbols"] == ["AAPL"]
    sip = AlpacaHistoryProvider("key", "secret", "sip", cache_allowed=True, cache_path=path)
    sip.prices(["AAPL"], 1)
    other_account = AlpacaHistoryProvider("other-key", "secret", "iex", cache_allowed=True, cache_path=path)
    other_account.prices(["AAPL"], 1)
    assert len(calls) == 3
