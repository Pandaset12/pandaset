from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from backend import main
from backend.config import Settings, get_settings
from backend.gemini_service import extract_evidence
from backend.providers import DemoQuantProvider, get_provider


@pytest.fixture
def client(tmp_path):
    app = main.create_app(Settings(
        _env_file=None, analyst_mode="demo", storage_path=tmp_path / "test.sqlite3"
    ))
    app.dependency_overrides[get_provider] = DemoQuantProvider
    with TestClient(app) as test_client:
        yield test_client


def test_demo_is_explicit_and_has_no_fake_sources(client):
    response = client.post(
        "/api/analyst",
        json={"question": "What's my biggest risk?", "web_search": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["analyst_mode"] == "demo"
    assert data["metrics"]["data_mode"] == "demo"
    assert data["sources"] == []
    assert any("not called" in note for note in data["warnings"])


def test_blank_question_and_private_url_rejected(client):
    assert client.post("/api/analyst", json={"question": "  "}).status_code == 422
    response = client.post(
        "/api/analyst",
        json={"question": "Read this", "source_urls": ["https://127.0.0.1/"]},
    )
    assert response.status_code == 422


def test_unknown_portfolio_is_not_silently_replaced_by_demo(client):
    assert client.get("/api/portfolios/missing/analytics").status_code == 404


def test_what_if_does_not_invent_results_or_change_saved_weights(client):
    before = client.get("/api/portfolios/demo/analytics").json()
    response = client.post(
        "/api/what-if",
        json={"proposed_weights": {"NVDA": 0.15, "SPY": 0.40, "JPM": 0.35, "TLT": 0.10}},
    )
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "quant_integration_pending"
    assert client.get("/api/portfolios/demo/analytics").json() == before
    assert client.post(
        "/api/what-if", json={"proposed_weights": {"NVDA": 0.5, "JPM": 0.6}}
    ).status_code == 422


def test_gemini_text_cannot_overwrite_backend_numbers(client, monkeypatch):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, analyst_mode="gemini", gemini_api_key="test-only"
    )
    gateway = AsyncMock(return_value={"answer": "Text with a different number: 99%."})
    monkeypatch.setattr(main, "generate_answer", gateway)
    response = client.post("/api/analyst", json={"question": "Explain risk"})
    assert response.status_code == 200
    assert response.json()["metrics"]["risk_contribution"]["NVDA"] == 0.41
    gateway.assert_awaited_once()


def test_missing_gemini_key_returns_configuration_error(client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, analyst_mode="gemini", gemini_api_key=None
    )
    response = client.post("/api/analyst", json={"question": "Explain risk"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "gemini_not_configured"


def test_citation_indices_and_failed_url_retrieval_are_preserved():
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                grounding_metadata=types.GroundingMetadata(
                    grounding_chunks=[
                        types.GroundingChunk(),
                        types.GroundingChunk(
                            web=types.GroundingChunkWeb(
                                uri="https://www.sec.gov/", title="SEC"
                            )
                        ),
                    ],
                    grounding_supports=[
                        types.GroundingSupport(
                            grounding_chunk_indices=[1],
                            segment=types.Segment(start_index=0, end_index=5, text="Claim"),
                        )
                    ],
                    search_entry_point=types.SearchEntryPoint(rendered_content="<div>Search</div>"),
                ),
                url_context_metadata=types.UrlContextMetadata(
                    url_metadata=[
                        types.UrlMetadata(
                            retrieved_url="https://www.sec.gov/",
                            url_retrieval_status="URL_RETRIEVAL_STATUS_ERROR",
                        )
                    ]
                ),
            )
        ]
    )
    evidence = extract_evidence(response)
    assert len(evidence["sources"]) == 2
    assert evidence["sources"][1]["web"]["title"] == "SEC"
    assert evidence["grounding_supports"][0]["grounding_chunk_indices"] == [1]
    assert evidence["url_retrievals"][0]["url_retrieval_status"] == "URL_RETRIEVAL_STATUS_ERROR"
