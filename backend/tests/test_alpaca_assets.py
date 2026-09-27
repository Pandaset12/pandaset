import json
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend import alpaca_assets, api_v1
from backend.alpaca_assets import AssetLookupUnavailable, search_alpaca_assets, search_catalog
from backend.config import Settings
from backend.main import create_app


CATALOG = [
    {"symbol": "AAPX", "name": "Apple Daily ETF"},
    {"symbol": "AAPL", "name": "Apple Inc. Common Stock"},
    {"symbol": "GOOG", "name": "Alphabet Inc. Class C"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Class A"},
    {"symbol": "AMZP", "name": "Amazon Strategy ETF"},
    {"symbol": "AMZN", "name": "Amazon.com, Inc. Common Stock"},
]


def test_company_search_ranks_primary_symbols_and_google_share_classes():
    assert search_catalog(CATALOG, "apple")[0]["symbol"] == "AAPL"
    assert [item["symbol"] for item in search_catalog(CATALOG, "Google")] == ["GOOGL", "GOOG"]
    assert search_catalog(CATALOG, "Amazon")[0]["symbol"] == "AMZN"
    assert search_catalog(CATALOG, "AMZN")[0]["symbol"] == "AMZN"


def test_alpaca_assets_are_read_only_filtered_and_cached_in_memory(monkeypatch):
    payload = [
        {"symbol": "AAPL", "name": "Apple Inc.", "status": "active", "class": "us_equity"},
        {"symbol": "OLD", "name": "Old Inc.", "status": "inactive", "class": "us_equity"},
        {"symbol": "BTCUSD", "name": "Bitcoin", "status": "active", "class": "crypto"},
    ]
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(payload).encode()
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return response

    monkeypatch.setattr(alpaca_assets, "urlopen", fake_urlopen)
    monkeypatch.setattr(alpaca_assets, "_cache", None)
    assert search_alpaca_assets("Apple", "key", "secret", "https://paper-api.alpaca.markets", 5) == [
        {"symbol": "AAPL", "name": "Apple Inc."}
    ]
    assert search_alpaca_assets("AAPL", "key", "secret", "https://paper-api.alpaca.markets", 5)[0]["symbol"] == "AAPL"
    assert len(calls) == 1
    assert calls[0][0].full_url.endswith("/v2/assets?status=active&asset_class=us_equity")
    assert calls[0][0].get_header("Apca-api-key-id") == "key"
    assert calls[0][1] == 5


def test_alpaca_asset_auth_failure_has_safe_error(monkeypatch):
    def reject(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(alpaca_assets, "urlopen", reject)
    monkeypatch.setattr(alpaca_assets, "_cache", None)
    with pytest.raises(AssetLookupUnavailable, match="rejected access"):
        search_alpaca_assets("Apple", "key", "secret", "https://paper-api.alpaca.markets", 5)


def test_stock_search_requires_auth_and_uses_the_selected_provider(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, storage_path=tmp_path / "assets.sqlite3")
    app = create_app(settings)
    with TestClient(app) as client:
        app.dependency_overrides.pop(api_v1.current_user_id, None)
        assert client.get("/api/v1/assets/search", params={"q": "Apple"}).status_code == 401
        app.dependency_overrides[api_v1.current_user_id] = lambda: "owner"
        sample = client.get("/api/v1/assets/search", params={"q": "Apple"})
        assert sample.status_code == 200
        assert sample.json()["results"][0]["symbol"] == "AAPL"

        live_settings = settings.model_copy(update={
            "market_data_provider": "alpaca",
            "alpaca_api_key": SecretStr("key"),
            "alpaca_api_secret": SecretStr("secret"),
        })
        app.dependency_overrides[api_v1.get_settings] = lambda: live_settings
        observed = []

        def lookup(query, key, secret, base_url, timeout):
            observed.append((query, key, secret, base_url, timeout))
            return [{"symbol": "AMZN", "name": "Amazon.com, Inc."}]

        monkeypatch.setattr(api_v1, "search_alpaca_assets", lookup)
        result = client.get("/api/v1/assets/search", params={"q": "Amazon"})
        assert result.status_code == 200
        assert result.json()["results"] == [{"symbol": "AMZN", "name": "Amazon.com, Inc."}]
        assert observed == [("Amazon", "key", "secret", "https://paper-api.alpaca.markets", 10)]
