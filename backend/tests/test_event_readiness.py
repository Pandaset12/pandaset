from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ConnectionFailure

from backend.auth import AuthenticatedUser
from backend.config import Settings
from backend.main import create_app


def test_event_lab_defaults_on_without_bypassing_readiness_or_public_gates():
    settings = Settings(_env_file=None)
    assert settings.event_lab_enabled is True
    assert settings.event_lab_ready is False
    assert settings.event_lab_public_enabled is False
    assert settings.event_lab_public_ready is False
    assert Settings(_env_file=None, event_lab_enabled=False).event_lab_enabled is False


def event_settings(tmp_path, **overrides):
    values = {
        "storage_path": tmp_path / "event-health.sqlite3",
        "analyst_mode": "demo", "market_data_provider": "sample",
        "supabase_url": "https://example.supabase.co", "supabase_anon_key": "",
        "supabase_publishable_key": "test-publishable",
        "mongo_uri": "mongodb://unused", "mongo_database": "event_readiness",
        "alpaca_api_key": "test-key", "alpaca_api_secret": "test-secret",
        "alpaca_history_feed": "iex", "gemini_api_key": "test-gemini",
        "tavily_api_key": "test-tavily", "deepseek_api_key": "test-deepseek",
        "fred_api_key": "", "approved_news_domains": "",
        "alpaca_display_rights_confirmed": False,
        "alpaca_cache_rights_confirmed": True,
        "event_lab_enabled": True, "event_lab_allowed_user_ids": "owner-a",
        "event_lab_public_enabled": False, "event_lab_probability_enabled": False,
        **overrides,
    }
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("field", [
    "supabase_url", "supabase_publishable_key", "mongo_uri",
    "alpaca_api_key", "alpaca_api_secret",
    "gemini_api_key", "tavily_api_key", "deepseek_api_key",
])
def test_whitespace_event_credentials_do_not_enable_startup(tmp_path, field):
    assert event_settings(tmp_path).event_lab_ready is True
    assert event_settings(tmp_path, **{field: " \t "}).event_lab_ready is False


def test_event_startup_requires_history_feed_and_cache_rights(tmp_path):
    assert event_settings(tmp_path, alpaca_history_feed=None).event_lab_ready is False
    assert event_settings(tmp_path, alpaca_cache_rights_confirmed=False).event_lab_ready is False


def test_event_public_readiness_preserves_release_gates(tmp_path):
    values = {
        "event_lab_public_enabled": True,
        "alpaca_display_rights_confirmed": True,
        "alpaca_cache_rights_confirmed": True,
        "approved_news_domains": "example.com", "fred_api_key": "test-fred",
    }
    assert event_settings(tmp_path).event_lab_public_ready is False
    assert event_settings(tmp_path, **values).event_lab_public_ready is True
    for field in ("event_lab_public_enabled", "alpaca_display_rights_confirmed",
                  "alpaca_cache_rights_confirmed"):
        assert event_settings(tmp_path, **{**values, field: False}).event_lab_public_ready is False
    for field in ("fred_api_key", "approved_news_domains"):
        assert event_settings(tmp_path, **{**values, field: " \t "}).event_lab_public_ready is False


def test_enabled_event_lab_missing_config_degrades_health_without_startup(tmp_path, monkeypatch):
    def unexpected_startup(*args, **kwargs):
        pytest.fail("Incomplete event configuration must not initialize external services")

    monkeypatch.setattr("backend.main.MongoClient", unexpected_startup)
    monkeypatch.setattr("backend.main.SupabaseTokenVerifier", unexpected_startup)
    with TestClient(create_app(event_settings(tmp_path, mongo_uri="  "))) as client:
        response = client.get("/health")
        health = response.json()
    assert response.status_code == 200
    assert health["status"] == "degraded"
    assert health["configuration_issues"] == ["EVENT_LAB_NOT_CONFIGURED"]
    assert health["event_lab_ready"] is False
    assert health["event_storage_backend"] == "unavailable"


def stub_event_services(monkeypatch, *, failure=None):
    mongo = mongomock.MongoClient()
    close_mongo = Mock(wraps=mongo.close)
    monkeypatch.setattr(mongo, "close", close_mongo)
    mongo_factory = Mock(return_value=mongo)
    verifier = Mock()
    verifier.verify.side_effect = lambda token: AuthenticatedUser(user_id=token, claims={"sub": token})
    verifier_factory = Mock(return_value=verifier)
    worker = Mock()
    worker.stop = AsyncMock()
    monkeypatch.setattr("backend.main.MongoClient", mongo_factory)
    monkeypatch.setattr("backend.main.SupabaseTokenVerifier", verifier_factory)
    monkeypatch.setattr("backend.main.EventWorker", Mock(return_value=worker))

    if failure == "mongo":
        mongo_factory.side_effect = ConnectionFailure("Synthetic connection failure")
    elif failure == "store":
        monkeypatch.setattr("backend.main.MongoPortfolioStore",
                            Mock(side_effect=ConnectionFailure("Synthetic index failure")))
    elif failure == "worker":
        worker.start.side_effect = RuntimeError("Synthetic worker startup failure")

    def unexpected_vendor_call(*args, **kwargs):
        pytest.fail("Startup/readiness checks must not query AI or market-data vendors")

    monkeypatch.setattr("backend.alpaca_history.AlpacaHistoryProvider._fetch", unexpected_vendor_call)
    monkeypatch.setattr("backend.gemini_service.genai.Client", unexpected_vendor_call)
    return SimpleNamespace(close_mongo=close_mongo, worker=worker,
                           verifier=verifier, verifier_factory=verifier_factory)


@pytest.mark.parametrize("failure", ["mongo", "store", "worker"])
def test_event_startup_failure_keeps_v1_available_but_health_degraded(tmp_path, monkeypatch, failure):
    services = stub_event_services(monkeypatch, failure=failure)
    with TestClient(create_app(event_settings(tmp_path))) as client:
        health = client.get("/health").json()
        assert health["status"] == "degraded"
        assert health["configuration_issues"] == []
        assert health["authentication_enabled"] is True
        assert health["event_lab_ready"] is False
        assert health["event_lab_public_ready"] is False
        assert health["event_authentication_enabled"] is False
        assert health["event_data_mode"] == "unavailable"
        assert health["event_storage_backend"] == "unavailable"
        assert client.post("/api/v1/portfolios", json={
            "name": "V1 remains available", "holdings": [{"symbol": "SPY", "weight": 1.0}],
        }).status_code == 201
        response = client.get("/api/v2/portfolios", headers={"Authorization": "Bearer owner-a"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AUTH_UNAVAILABLE"
    services.verifier.http_client.close.assert_called_once()
    assert services.close_mongo.call_count == (0 if failure == "mongo" else 1)
    assert services.worker.stop.await_count == (1 if failure == "worker" else 0)


def test_event_startup_preserves_v2_routes_health_and_shutdown(tmp_path, monkeypatch):
    services = stub_event_services(monkeypatch)
    with TestClient(create_app(event_settings(tmp_path))) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok"
        assert health["configuration_issues"] == []
        assert health["event_lab_ready"] is True
        assert health["event_authentication_enabled"] is True
        assert health["event_lab_public_ready"] is False
        assert health["event_data_mode"] == "live"
        assert health["event_storage_backend"] == "mongo"
        assert health["legacy_data_mode"] == "demo"
        assert health["legacy_storage_backend"] == "sqlite"
        assert client.get("/api/v2/portfolios").status_code == 401
        assert client.get("/api/v2/portfolios", headers={"Authorization": "Bearer owner-a"}).status_code == 200
        assert client.get("/api/v2/portfolios", headers={"Authorization": "Bearer owner-b"}).status_code == 403
        services.worker.start.assert_called_once()
    services.verifier_factory.assert_called_once_with(
        "https://example.supabase.co", "test-publishable", signing_mode="asymmetric",
    )
    services.worker.stop.assert_awaited_once()
    services.close_mongo.assert_called_once()
    services.verifier.http_client.close.assert_called_once()
