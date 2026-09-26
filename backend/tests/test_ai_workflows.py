from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend import api_v1
from backend.api_v1 import scenario_matches_snapshot
from backend.config import Settings
from backend.main import create_app
from backend.providers import demo_metrics
from backend.research_sources import RESEARCH_SOURCES, curated_research_source
from backend.schemas import ScenarioExplanationRequest
from backend.gemini_service import GeminiUnavailable


def test_workflow_endpoints_return_scoped_demo_responses(tmp_path):
    settings = Settings(_env_file=None, analyst_mode="demo", storage_path=tmp_path / "workflows.sqlite3")
    with TestClient(create_app(settings)) as client:
        analysis = client.post("/api/v1/portfolios/demo/analysis").json()
        analysis_id = analysis["analysis_id"]

        for route, workflow in (
            ("briefing", "analysis_briefing"),
            ("risk/explanation", "risk_explanation"),
        ):
            response = client.post(
                f"/api/v1/portfolios/demo/{route}",
                json={"analysis_id": analysis_id},
            )
            assert response.status_code == 200
            assert response.json()["workflow"] == workflow
            assert response.json()["status"] == "demo"
            assert response.json()["analysis_id"] == analysis_id
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


def test_scenario_request_is_validated_and_does_not_mutate_portfolio(tmp_path):
    settings = Settings(_env_file=None, analyst_mode="demo", storage_path=tmp_path / "scenario.sqlite3")
    with TestClient(create_app(settings)) as client:
        before = client.get("/api/v1/portfolios/demo").json()
        analysis = client.post("/api/v1/portfolios/demo/analysis").json()
        proposed_weights = dict(analysis["weights"])
        proposed_weights["NVDA"] -= 0.05
        proposed_weights["JPM"] += 0.05

        response = client.post(
            "/api/v1/portfolios/demo/what-if/explanation",
            json={"analysis_id": analysis["analysis_id"], "proposed_weights": proposed_weights},
        )
        assert response.status_code == 200, response.text
        assert response.json()["workflow"] == "scenario_explanation"
        assert response.json()["status"] == "demo"
        assert client.get("/api/v1/portfolios/demo").json() == before


def test_scenario_evidence_must_match_the_saved_snapshot():
    metrics = demo_metrics()
    comparison = {
        "current_analysis": metrics.model_dump(mode="json"),
        "proposed_analysis": metrics.model_dump(mode="json"),
        "delta": {},
    }
    assert scenario_matches_snapshot(
        metrics, comparison, {**metrics.weights, "AMD": 0.0}
    )

    comparison["current_analysis"]["portfolio_volatility"] += 0.01
    assert not scenario_matches_snapshot(metrics, comparison, metrics.weights)

    comparison["current_analysis"] = metrics.model_dump(mode="json")
    comparison["current_analysis"]["risk_contribution"]["NVDA"] += 0.01
    comparison["current_analysis"]["risk_contribution"]["SPY"] -= 0.01
    assert not scenario_matches_snapshot(metrics, comparison, metrics.weights)


def test_research_sources_are_allowlisted_and_unknown_symbols_are_rejected():
    for symbol, sources in RESEARCH_SOURCES.items():
        assert curated_research_source(symbol.lower(), "issuer") == sources["issuer"]
    assert curated_research_source("UNKNOWN", "issuer") is None


def test_scenario_weights_are_normalized_but_never_rescaled():
    request = ScenarioExplanationRequest(
        analysis_id="analysis-1",
        proposed_weights={" nvda ": 0.5, "JPM": 0.5},
    )
    assert request.proposed_weights == {"NVDA": 0.5, "JPM": 0.5}
    with pytest.raises(ValidationError):
        ScenarioExplanationRequest(
            analysis_id="analysis-1",
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
