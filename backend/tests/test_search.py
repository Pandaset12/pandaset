import json

import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types
from pydantic import ValidationError

from backend import gemini_service
from backend.config import Settings
from backend.main import create_app
from backend.schemas import AnalystRequest, AskRequest
from backend.tests.test_gemini import FakeClient, response_with_text


@pytest.mark.parametrize("request_type,extra", [
    (AnalystRequest, {}), (AskRequest, {"analysis_id": "saved"}),
])
@pytest.mark.parametrize("url", [
    "https://localhost./",
    "https://LOCALHOST./",
    "https://sub.localhost./",
    "https://service.local./",
    "https://metadata.google.internal./",
    "https://localhost\u3002/",
    "https://localhost../",
    "https://example.com../",
    "https://127.0.0.1./",
    "https://169.254.169.254./",
    "https://[::1]/",
    "http://www.sec.gov/",
    "https://user:password@www.sec.gov/",
])
def test_local_hosts_and_ambiguous_urls_are_rejected(request_type, extra, url):
    with pytest.raises(ValidationError):
        request_type(question="Read this source", source_urls=[url], **extra)


@pytest.mark.parametrize("url", [
    "https://www.sec.gov/", "https://www.sec.gov./", "https://example.com/research?q=earnings",
])
def test_public_domains_with_optional_dns_root_dot_are_accepted(url):
    assert AskRequest(question="Read source", analysis_id="saved", source_urls=[url]).source_urls


@pytest.fixture
def api(tmp_path):
    app = create_app(Settings(
        _env_file=None, analyst_mode="gemini", gemini_api_key="test-only",
        storage_path=tmp_path / "search.sqlite3",
    ))
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("options,search,url_context", [
    ({}, True, True),
    ({"web_search": True}, True, True),
    ({"web_search": False}, False, False),
    ({"source_urls": ["https://www.sec.gov/"]}, True, True),
    ({"web_search": False, "source_urls": ["https://www.sec.gov/"]}, False, True),
])
def test_saved_analysis_ask_passes_tool_policy_to_sdk(api, monkeypatch, options, search, url_context):
    client = FakeClient(response_with_text(json.dumps({
        "explanation": "This fictional snapshot illustrates portfolio volatility.",
        "cited_fields": ["portfolio_volatility"],
    })))
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **_: client)
    analysis = api.post("/api/v1/portfolios/demo/analysis").json()
    response = api.post("/api/v1/portfolios/demo/ask", json={
        "analysis_id": analysis["analysis_id"], "question": "Explain current context", **options,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["analysis_id"] == analysis["analysis_id"]
    assert body["metrics"]["portfolio_volatility"] == analysis["portfolio_volatility"]
    call = client.models.generate_content.call_args.kwargs
    tools = call["config"].tools or []
    assert any(tool.google_search is not None for tool in tools) == search
    assert any(tool.url_context is not None for tool in tools) == url_context
    assert call["config"].response_mime_type == "application/json"
    assert json.loads(call["contents"])["source_urls"] == options.get("source_urls", [])
    assert client.closed


def test_grounding_and_search_metadata_survive_api_response(api, monkeypatch):
    raw = json.dumps({"explanation": "Sourced news provides context for this demo.", "cited_fields": []})
    sdk_response = response_with_text(raw)
    sdk_response.candidates[0].grounding_metadata = types.GroundingMetadata(
        web_search_queries=["latest Federal Reserve news"],
        grounding_chunks=[types.GroundingChunk(web=types.GroundingChunkWeb(
            uri="https://www.federalreserve.gov/", title="Federal Reserve",
        ))],
        grounding_supports=[types.GroundingSupport(
            grounding_chunk_indices=[0], segment=types.Segment(text="Sourced news"),
        )],
        search_entry_point=types.SearchEntryPoint(rendered_content="<div>Search</div>"),
    )
    sdk_response.candidates[0].url_context_metadata = types.UrlContextMetadata(
        url_metadata=[types.UrlMetadata(
            retrieved_url="https://www.federalreserve.gov/",
            url_retrieval_status="URL_RETRIEVAL_STATUS_SUCCESS",
        )],
    )
    client = FakeClient(sdk_response)
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **_: client)
    analysis = api.post("/api/v1/portfolios/demo/analysis").json()
    response = api.post("/api/v1/portfolios/demo/ask", json={
        "analysis_id": analysis["analysis_id"], "question": "What is in the news?",
    })
    data = response.json()
    assert data["status"] == "complete"
    assert data["grounding_text"] == raw
    assert data["web_search_queries"] == ["latest Federal Reserve news"]
    assert data["sources"][0]["web"]["title"] == "Federal Reserve"
    assert data["grounding_supports"][0]["grounding_chunk_indices"] == [0]
    assert data["search_suggestions_html"] == "<div>Search</div>"
    assert data["url_retrievals"][0]["url_retrieval_status"] == "URL_RETRIEVAL_STATUS_SUCCESS"


def test_invalid_local_url_is_rejected_before_gemini_is_called(api, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **_: client)
    analysis = api.post("/api/v1/portfolios/demo/analysis").json()
    response = api.post("/api/v1/portfolios/demo/ask", json={
        "analysis_id": analysis["analysis_id"], "question": "Read source",
        "source_urls": ["https://metadata.google.internal./"],
    })
    assert response.status_code == 422
    client.models.generate_content.assert_not_awaited()


def test_upstream_sdk_error_keeps_snapshot_and_has_no_fake_evidence(api, monkeypatch):
    client = FakeClient(side_effect=errors.ServerError(
        503, {"error": {"message": "private upstream detail", "status": "UNAVAILABLE"}},
    ))
    monkeypatch.setattr(gemini_service.genai, "Client", lambda **_: client)
    analysis = api.post("/api/v1/portfolios/demo/analysis").json()
    response = api.post("/api/v1/portfolios/demo/ask", json={
        "analysis_id": analysis["analysis_id"], "question": "Search current news",
    })
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "unavailable"
    assert data["error_code"] == "GEMINI_UNAVAILABLE"
    assert data["metrics"]["portfolio_volatility"] == analysis["portfolio_volatility"]
    assert not data["web_search_queries"] and not data["sources"] and not data["grounding_supports"]
    assert "private upstream detail" not in response.text
    assert client.closed
