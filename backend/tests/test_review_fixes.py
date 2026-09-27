import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from google.genai import types

from backend import gemini_service
from backend.config import Settings
from backend.main import create_app
from backend.providers import DemoQuantProvider, get_provider


class ModelClient:
    def __init__(self, payload):
        self.aio = self
        self.models = SimpleNamespace(generate_content=AsyncMock(return_value=types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(parts=[types.Part(text=json.dumps(payload))]))],
        )))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def test_forged_number_in_model_prose_is_not_returned_by_v1(tmp_path, monkeypatch):
    client = ModelClient({"explanation": "NVDA contributes 99% of risk.",
                          "cited_fields": ["risk_contribution.NVDA"]})
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **_: client)
    app = create_app(Settings(_env_file=None, analyst_mode="gemini", gemini_api_key="test-only",
                              storage_path=tmp_path / "test.sqlite3"))
    app.dependency_overrides[get_provider] = DemoQuantProvider
    with TestClient(app) as api:
        snapshot = api.post("/api/v1/portfolios/demo/analysis").json()
        response = api.post("/api/v1/portfolios/demo/ask", json={
            "analysis_id": snapshot["analysis_id"], "question": "Explain risk",
        })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["error_code"] == "GEMINI_UNAVAILABLE"
    assert "99%" not in data["answer"]
    assert "41.0%" in data["answer"]
    assert data["metrics"]["risk_contribution"]["NVDA"] == .41


def test_valid_prose_uses_backend_rendered_numbers_and_no_web_tools_by_default(tmp_path, monkeypatch):
    client = ModelClient({"explanation": "NVDA is the largest risk contributor in this snapshot.",
                          "cited_fields": ["risk_contribution.NVDA", "weights.NVDA"]})
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **_: client)
    app = create_app(Settings(_env_file=None, analyst_mode="gemini", gemini_api_key="test-only",
                              storage_path=tmp_path / "test.sqlite3"))
    app.dependency_overrides[get_provider] = DemoQuantProvider
    with TestClient(app) as api:
        snapshot = api.post("/api/v1/portfolios/demo/analysis").json()
        response = api.post("/api/v1/portfolios/demo/ask", json={
            "analysis_id": snapshot["analysis_id"], "question": "Explain risk",
        })
        health = api.get("/health").json()
    data = response.json()
    assert data["status"] == "complete"
    assert "41.0%" in data["answer"] and "30.0%" in data["answer"]
    assert data["answer"].startswith("FICTIONAL DEMO DATA.")
    assert client.models.generate_content.call_args.kwargs["config"].tools is None
    assert health["analyst_mode"] == "gemini"
    assert health["data_mode"] == "demo"
    assert health["market_data_provider"] == "sample"
    assert health["market_data_ready"] is True
    assert health["storage_backend"] == "sqlite"
    assert health["authentication_enabled"] is False


def test_provider_failure_has_correlated_safe_logs_and_client_request_id(tmp_path, caplog):
    class FailingProvider(DemoQuantProvider):
        def analyze(self, portfolio):
            raise RuntimeError("secret-upstream-credential")

    app = create_app(Settings(_env_file=None, storage_path=tmp_path / "test.sqlite3"))
    app.dependency_overrides[get_provider] = FailingProvider
    with caplog.at_level(logging.WARNING, logger="portfoliolens"):
        with TestClient(app) as api:
            response = api.post("/api/v1/portfolios/demo/analysis",
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
