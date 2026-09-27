from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend import api_v1
from backend.config import Settings
from backend.main import create_app
from backend.research_sources import RESEARCH_SOURCES, curated_research_source
from backend.schemas import ScenarioExplanationRequest
from backend.gemini_service import GeminiUnavailable


def test_workflow_endpoints_return_scoped_demo_responses(tmp_path):
    settings = Settings(_env_file=None, analyst_mode="demo", storage_path=tmp_path / "workflows.sqlite3")
    with TestClient(create_app(settings)) as client:
        metrics = client.get("/api/v1/portfolios/demo/metrics").json()

        for route, workflow in (
            ("briefing", "analysis_briefing"),
            ("risk/explanation", "risk_explanation"),
        ):
            response = client.post(
                f"/api/v1/portfolios/demo/{route}",
                json={"portfolio_revision": metrics["portfolio_revision"]},
            )
            assert response.status_code == 200
            assert response.json()["workflow"] == workflow
            assert response.json()["status"] == "demo"
            assert response.json()["portfolio_revision"] == metrics["portfolio_revision"]
            assert response.json()["metrics"]["portfolio_id"] == "demo"
            assert "not called" in " ".join(response.json()["warnings"]).lower()

        research = client.post(
            "/api/v1/research/NVDA/summary", json={"source_id": "issuer"}
        )
        assert research.status_code == 200
        assert research.json()["workflow"] == "research_summary"
        assert research.json()["status"] == "demo"
        assert research.json()["source_url"] == RESEARCH_SOURCES["NVDA"]["issuer"]["url"]
        assert research.json()["url_retrievals"] == []
        unknown = client.post(
            "/api/v1/research/UNKNOWN/summary", json={"source_id": "issuer"}
        )
        assert unknown.status_code == 404


def test_unavailable_briefing_and_risk_return_different_saved_metrics(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None, analyst_mode="gemini", gemini_api_key="test-only",
        storage_path=tmp_path / "unavailable.sqlite3",
    )
    monkeypatch.setattr(
        api_v1, "generate_analysis_workflow",
        AsyncMock(side_effect=GeminiUnavailable("Gemini is busy right now.")),
    )
    with TestClient(create_app(settings)) as client:
        payload = {"portfolio_revision": 1}
        briefing = client.post("/api/v1/portfolios/demo/briefing", json=payload).json()
        risk = client.post("/api/v1/portfolios/demo/risk/explanation", json=payload).json()

    assert briefing["status"] == risk["status"] == "unavailable"
    assert briefing["error_code"] == risk["error_code"] == "GEMINI_UNAVAILABLE"
    assert briefing["answer"] != risk["answer"]
    assert "largest holding" in briefing["answer"]
    assert "estimated portfolio volatility" in risk["answer"]
    assert {item["field"] for item in briefing["citations"]} != {
        item["field"] for item in risk["citations"]
    }


def test_scenario_request_is_validated_and_does_not_mutate_portfolio(tmp_path):
    settings = Settings(_env_file=None, analyst_mode="demo", storage_path=tmp_path / "scenario.sqlite3")
    with TestClient(create_app(settings)) as client:
        before = client.get("/api/v1/portfolios/demo").json()
        metrics = client.get("/api/v1/portfolios/demo/metrics").json()
        proposed_weights = dict(metrics["weights"])
        proposed_weights["NVDA"] -= 0.05
        proposed_weights["JPM"] += 0.05

        response = client.post(
            "/api/v1/portfolios/demo/what-if/explanation",
            json={"portfolio_revision": 1, "proposed_weights": proposed_weights},
        )
        assert response.status_code == 200, response.text
        assert response.json()["workflow"] == "scenario_explanation"
        assert response.json()["status"] == "demo"
        assert client.get("/api/v1/portfolios/demo").json() == before


def test_scenario_explanation_enforces_saved_and_proposed_symbol_union(tmp_path):
    settings = Settings(_env_file=None, analyst_mode="demo", storage_path=tmp_path / "scenario-limit.sqlite3")
    symbols = ["NVDA", "MSFT", "AAPL", "JPM", "VTI", "TLT", "AMD", "GLD"]
    with TestClient(create_app(settings)) as client:
        created = client.post("/api/v1/portfolios", json={
            "name": "Eight symbols",
            "holdings": [{"symbol": symbol, "weight": 0.125} for symbol in symbols],
        })
        assert created.status_code == 201, created.text
        portfolio_id = created.json()["portfolio_id"]
        response = client.post(
            f"/api/v1/portfolios/{portfolio_id}/what-if/explanation",
            json={
                "portfolio_revision": 1,
                "proposed_weights": {"SPY": 1.0},
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SYMBOL_LIMIT_EXCEEDED"


def test_research_sources_are_allowlisted_and_unknown_symbols_are_rejected():
    for symbol, sources in RESEARCH_SOURCES.items():
        assert curated_research_source(symbol.lower(), "issuer") == sources["issuer"]
    assert curated_research_source("UNKNOWN", "issuer") is None


def test_scenario_weights_are_normalized_but_never_rescaled():
    request = ScenarioExplanationRequest(
        portfolio_revision=1,
        proposed_weights={" nvda ": 0.5, "JPM": 0.5},
    )
    assert request.proposed_weights == {"NVDA": 0.5, "JPM": 0.5}
    with pytest.raises(ValidationError):
        ScenarioExplanationRequest(
            portfolio_revision=1,
            proposed_weights={"NVDA": 0.6, "JPM": 0.5},
        )


def test_unavailable_research_summary_preserves_retrieval_evidence(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        analyst_mode="gemini",
        gemini_api_key="test-only",
        storage_path=tmp_path / "research.sqlite3",
    )
    evidence = {
        "sources": [{"web": {"uri": "https://investor.nvidia.com/"}}],
        "grounding_supports": [],
        "url_retrievals": [{
            "retrieved_url": "https://investor.nvidia.com/",
            "url_retrieval_status": "URL_RETRIEVAL_STATUS_UNAVAILABLE",
        }],
    }
    gateway = AsyncMock(
        side_effect=GeminiUnavailable("The source could not be retrieved.", evidence=evidence)
    )
    monkeypatch.setattr(api_v1, "generate_research_summary", gateway)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/research/NVDA/summary", json={"source_id": "issuer"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["sources"] == evidence["sources"]
    assert data["url_retrievals"] == evidence["url_retrievals"]
