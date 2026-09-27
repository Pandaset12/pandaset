import json
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from backend import api_v1
from backend.alpaca_quotes import AlpacaQuotesUnavailable, fetch_alpaca_quotes
from backend.config import Settings
from backend.main import create_app


def test_snapshot_adapter_parses_last_trade_and_iex_quote(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = (
        b'{"AAPL":{"latestTrade":{"p":201.25,"t":"2026-09-26T14:30:00Z"},'
        b'"latestQuote":{"bp":201.2,"ap":201.3,"t":"2026-09-26T14:30:01Z"}}}'
    )
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr("backend.alpaca_quotes.urlopen", fake_urlopen)
    result = fetch_alpaca_quotes(["AAPL"], "key", "secret", 4)

    assert result == {
        "feed": "IEX", "source": "alpaca", "quotes": [{
            "symbol": "AAPL", "last_price": 201.25,
            "last_trade_at": "2026-09-26T14:30:00Z", "bid": 201.2,
            "ask": 201.3, "quote_at": "2026-09-26T14:30:01Z",
        }],
    }
    assert captured["request"].get_header("Apca-api-key-id") == "key"
    assert captured["request"].get_header("Apca-api-secret-key") == "secret"
    assert captured["timeout"] == 4


@pytest.mark.parametrize("price", ["not-a-price", "NaN", "Infinity", -1, 0])
def test_invalid_last_trade_price_becomes_provider_error(monkeypatch, price):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = (
        f'{{"AAPL":{{"latestTrade":{{"p":"{price}"}}}}}}'.encode()
    )
    monkeypatch.setattr("backend.alpaca_quotes.urlopen", lambda *_args, **_kwargs: response)

    with pytest.raises(AlpacaQuotesUnavailable, match="invalid snapshot"):
        fetch_alpaca_quotes(["AAPL"], "key", "secret")


def make_client(tmp_path, *, key=None, secret=None):
    settings = Settings(
        _env_file=None,
        storage_path=tmp_path / "alpaca.sqlite3",
        alpaca_api_key=key,
        alpaca_api_secret=secret,
    )
    app = create_app(settings)
    app.dependency_overrides[api_v1.current_user_id] = lambda: "test-user"
    return TestClient(app)


def test_quotes_endpoint_requires_backend_credentials(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get("/api/v1/quotes", params={"symbols": "AAPL"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ALPACA_NOT_CONFIGURED"


@pytest.mark.parametrize("symbols", [["AAPL", "aapl"], ["AAPL/EVIL"], [""], ["A" * 21]])
def test_quotes_endpoint_rejects_invalid_symbol_lists(tmp_path, symbols):
    with make_client(tmp_path, key="key", secret="secret") as client:
        response = client.get("/api/v1/quotes", params=[("symbols", symbol) for symbol in symbols])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_QUOTES_REQUEST"


def test_quotes_endpoint_calls_alpaca_only_from_backend(tmp_path, monkeypatch):
    def fake_fetch(symbols, key, secret, timeout):
        assert (symbols, key, secret, timeout) == (["AAPL", "MSFT"], "key", "secret", 10)
        return {"feed": "IEX", "source": "alpaca", "quotes": []}

    monkeypatch.setattr(api_v1, "fetch_alpaca_quotes", fake_fetch)
    with make_client(tmp_path, key="key", secret="secret") as client:
        response = client.get("/api/v1/quotes", params=[("symbols", "aapl"), ("symbols", "msft")])

    assert response.status_code == 200
    assert response.json() == {"feed": "IEX", "source": "alpaca", "quotes": []}


def test_quotes_endpoint_maps_invalid_upstream_timestamps_to_safe_error(tmp_path, monkeypatch):
    monkeypatch.setattr(api_v1, "fetch_alpaca_quotes", lambda *_args: {
        "feed": "IEX", "source": "alpaca", "quotes": [{
            "symbol": "AAPL", "last_price": 201.25, "last_trade_at": "not-a-timestamp",
            "bid": None, "ask": None, "quote_at": None,
        }],
    })
    with make_client(tmp_path, key="key", secret="secret") as client:
        response = client.get("/api/v1/quotes", params={"symbols": "AAPL"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ALPACA_QUOTES_UNAVAILABLE"


@pytest.mark.parametrize("count, status", [(9, 200), (25, 200), (26, 422)])
def test_quotes_support_event_lab_holdings_limit(tmp_path, monkeypatch, count, status):
    calls = []

    def fetch(symbols, *_args):
        calls.append(symbols)
        return {"feed": "IEX", "source": "alpaca", "quotes": [{"symbol": s} for s in symbols]}

    monkeypatch.setattr(api_v1, "fetch_alpaca_quotes", fetch)
    symbols = [f"T{index}" for index in range(count)]
    with make_client(tmp_path, key="key", secret="secret") as client:
        response = client.get("/api/v1/quotes", params=[("symbols", s) for s in symbols])
    assert response.status_code == status
    assert calls == ([symbols] if status == 200 else [])
    if status == 200:
        assert len(response.json()["quotes"]) == count


@pytest.mark.parametrize("payload", [
    b"not JSON", b"\xff", b"[]", b'{"AAPL":[]}',
    b'{"AAPL":{"latestTrade":[]}}', b'{"AAPL":{"latestQuote":false}}',
    b'{"AAPL":{"latestTrade":{"p":true}}}',
])
def test_malformed_vendor_responses_fail_safely(monkeypatch, payload):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = payload
    monkeypatch.setattr("backend.alpaca_quotes.urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(AlpacaQuotesUnavailable):
        fetch_alpaca_quotes(["AAPL"], "key", "secret")


def test_invalid_utf8_is_safe_502_at_api_boundary(tmp_path, monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"\xff"
    monkeypatch.setattr("backend.alpaca_quotes.urlopen", lambda *_args, **_kwargs: response)
    with make_client(tmp_path, key="key", secret="secret") as client:
        result = client.get("/api/v1/quotes", params={"symbols": "AAPL"})
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "ALPACA_QUOTES_UNAVAILABLE"


def test_bid_ask_require_a_timestamp(tmp_path, monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"AAPL":{"latestQuote":{"bp":100,"ap":101}}}'
    monkeypatch.setattr("backend.alpaca_quotes.urlopen", lambda *_args, **_kwargs: response)
    with make_client(tmp_path, key="key", secret="secret") as client:
        result = client.get("/api/v1/quotes", params={"symbols": "AAPL"})
    assert result.status_code == 502


def test_missing_snapshots_preserve_requested_symbols_without_invented_prices(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"AAPL":null}'
    monkeypatch.setattr("backend.alpaca_quotes.urlopen", lambda *_args, **_kwargs: response)
    result = fetch_alpaca_quotes(["AAPL", "MSFT"], "key", "secret")
    assert [quote["symbol"] for quote in result["quotes"]] == ["AAPL", "MSFT"]
    assert all(quote["last_price"] is None and quote["last_trade_at"] is None for quote in result["quotes"])


@pytest.mark.parametrize("error", [
    HTTPError("https://example.invalid", code, "sensitive vendor text", None, None)
    for code in [401, 403, 429, 500]
] + [URLError("sensitive vendor text"), TimeoutError("sensitive vendor text")])
def test_vendor_failures_return_safe_502_without_credentials(tmp_path, monkeypatch, error):
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("backend.alpaca_quotes.urlopen", fail)
    with make_client(tmp_path, key="private-key", secret="private-secret") as client:
        response = client.get("/api/v1/quotes", params={"symbols": "AAPL"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ALPACA_QUOTES_UNAVAILABLE"
    assert "private-key" not in response.text
    assert "private-secret" not in response.text
    assert "sensitive vendor text" not in response.text


@pytest.mark.parametrize("trade", [
    {"p": 123}, {"t": "2026-09-25T14:30:00Z"},
    {"p": 123, "t": 1234567890}, {"p": 123, "t": "2026-09-25T14:30:00"},
    {"p": 123, "t": "1234567890"},
])
def test_trade_requires_price_and_explicit_timezone(tmp_path, monkeypatch, trade):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"AAPL": {"latestTrade": trade}}).encode()
    monkeypatch.setattr("backend.alpaca_quotes.urlopen", lambda *_args, **_kwargs: response)
    with make_client(tmp_path, key="key", secret="secret") as client:
        result = client.get("/api/v1/quotes", params={"symbols": "AAPL"})
    assert result.status_code == 502


@pytest.mark.parametrize("key, secret", [(" ", "secret"), ("key", ""), (None, "secret")])
def test_incomplete_credentials_never_call_vendor(tmp_path, monkeypatch, key, secret):
    monkeypatch.setattr(api_v1, "fetch_alpaca_quotes", lambda *_args: pytest.fail("Must not call vendor"))
    with make_client(tmp_path, key=key, secret=secret) as client:
        response = client.get("/api/v1/quotes", params={"symbols": "AAPL"})
    assert response.status_code == 503
