import json
import logging
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.providers import DemoQuantProvider, get_provider


def test_provider_failure_has_correlated_safe_logs_and_client_request_id(tmp_path, caplog):
    class FailingProvider(DemoQuantProvider):
        def analyze(self, portfolio):
            raise RuntimeError("secret-upstream-credential")

    app = create_app(Settings(_env_file=None, storage_path=tmp_path / "test.sqlite3"))
    app.dependency_overrides[get_provider] = FailingProvider
    with caplog.at_level(logging.WARNING, logger="portfoliolens"):
        with TestClient(app) as api:
            response = api.get("/api/v1/portfolios/demo/metrics",
                                headers={"Origin": "http://localhost:5173", "X-Request-ID": "untrusted"})
    assert response.status_code == 502
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32 and request_id != "untrusted"
    assert response.json()["error"]["request_id"] == request_id
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]
    records = [json.loads(record.message) for record in caplog.records if record.name == "portfoliolens"]
    record = next(r for r in records if r["code"] == "PROVIDER_UNAVAILABLE")
    assert record["request_id"] == request_id
    assert record["exception_type"] == "RuntimeError"
    assert record["frames"][-1]["function"] == "analyze"
    assert "secret-upstream-credential" not in response.text
    assert "secret-upstream-credential" not in caplog.text


def test_unhandled_failure_is_safe_and_request_ids_are_unique(tmp_path, monkeypatch, caplog):
    app = create_app(Settings(_env_file=None, storage_path=tmp_path / "test.sqlite3"))
    with TestClient(app) as api:
        def fail_read(*args):
            raise RuntimeError("private-storage-value")
        monkeypatch.setattr(app.state.store, "get", fail_read)
        with caplog.at_level(logging.WARNING, logger="portfoliolens"):
            response = api.get("/api/v1/portfolios/demo")
        health = api.get("/health")
        invalid = api.post("/api/v1/portfolios", json={"holdings": []})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert invalid.status_code == 422
    assert invalid.json()["error"]["request_id"] == invalid.headers["X-Request-ID"]
    assert len({r.headers["X-Request-ID"] for r in [response, health, invalid]}) == 3
    assert "private-storage-value" not in response.text + caplog.text


def test_live_health_reports_missing_alpaca_history_configuration(tmp_path):
    app = create_app(Settings(_env_file=None, market_data_provider="alpaca",
                              storage_path=tmp_path / "test.sqlite3"))
    with TestClient(app) as api:
        health = api.get("/health").json()
    assert health["status"] == "degraded"
    assert health["quant_integration"] == "quant_engine_alpaca"
    assert health["market_data_provider"] == "alpaca"
    assert health["market_data_ready"] is False
    assert health["data_mode"] == "live"
