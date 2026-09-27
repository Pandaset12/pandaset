import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.config import Settings
from backend.main import create_app
from backend.schemas import QuestionInput


@pytest.mark.parametrize("url", [
    "https://localhost/", "https://localhost./", "https://LOCALHOST.:443/",
    "https://api.localhost./", "https://api.local./", "https://api.internal./",
    "https://api.internal../", "https://example..com/", "https://example.com../",
    "https://127.0.0.1./", "https://[::1]/", "https://8.8.8.8/",
    "https://user:password@example.com/", "http://example.com/",
])
def test_non_public_or_malformed_source_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        QuestionInput(question="Read this source", source_urls=[url])


@pytest.mark.parametrize("url", ["https://example.com/report", "https://www.example.com./report"])
def test_public_https_domain_and_root_dot_remain_supported(url):
    request = QuestionInput(question="Read this source", source_urls=[url])
    assert str(request.source_urls[0]) == url
    assert request.web_search is False


@pytest.mark.parametrize("path,extra", [
    ("/api/analyst", {}),
    ("/api/v1/portfolios/demo/ask", {"analysis_id": "not-read"}),
])
def test_api_rejects_local_root_dot_before_ai_or_snapshot_access(tmp_path, monkeypatch, path, extra):
    def unexpected_request(*args, **kwargs):
        pytest.fail("Rejected sources must not reach Gemini")

    monkeypatch.setattr("backend.gemini_service.genai.Client", unexpected_request)
    settings = Settings(_env_file=None, analyst_mode="gemini", gemini_api_key="test-only",
                        storage_path=tmp_path / "sources.sqlite3")
    with TestClient(create_app(settings)) as client:
        response = client.post(path, json={
            "question": "Read this source", "source_urls": ["https://localhost./"], **extra,
        })
    assert response.status_code == 422
    assert response.headers["X-Request-ID"]
