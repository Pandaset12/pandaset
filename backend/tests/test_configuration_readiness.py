import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.auth import current_user_id
from backend.config import Settings
from backend.main import create_app


@pytest.mark.parametrize("configured,expected", [
    ("AUTO", "auto"),
    (" Legacy ", "legacy"),
    ("asymmetric", "asymmetric"),
])
def test_supabase_signing_mode_accepts_case_variants_from_environment(
    monkeypatch, configured, expected,
):
    monkeypatch.setenv("SUPABASE_SIGNING_MODE", configured)
    assert Settings(_env_file=None).supabase_signing_mode == expected


def test_supabase_signing_mode_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("SUPABASE_SIGNING_MODE", "unknown")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("overrides,issues", [
    ({}, ["AUTH_NOT_CONFIGURED"]),
    ({"supabase_url": "https://example.supabase.co", "supabase_anon_key": "test-only"}, []),
    ({"supabase_url": "https://example.supabase.co", "supabase_publishable_key": "test-publishable"}, []),
    ({"analyst_mode": "gemini"}, ["AUTH_NOT_CONFIGURED", "GEMINI_NOT_CONFIGURED"]),
    ({"market_data_provider": "alpaca"}, ["AUTH_NOT_CONFIGURED", "MARKET_DATA_NOT_CONFIGURED"]),
    ({"analyst_mode": "gemini", "market_data_provider": "alpaca",
      "supabase_url": "https://example.supabase.co", "supabase_anon_key": "test-only",
      "gemini_api_key": "test-gemini", "alpaca_api_key": "test-key",
      "alpaca_api_secret": "test-secret", "alpaca_history_feed": "iex"}, []),
])
def test_health_reports_configuration_readiness_without_calling_vendors(tmp_path, monkeypatch, overrides, issues):
    def unexpected_request(*args, **kwargs):
        pytest.fail("Health must not make upstream requests or spend API credits")

    monkeypatch.setattr("backend.auth.httpx.get", unexpected_request)
    monkeypatch.setattr("backend.gemini_service.genai.Client", unexpected_request)
    monkeypatch.setattr("backend.alpaca_history.AlpacaHistoryProvider._fetch", unexpected_request)
    configuration = {
        "analyst_mode": "demo", "market_data_provider": "sample",
        "supabase_url": "", "supabase_anon_key": "", "supabase_publishable_key": "",
        "gemini_api_key": "", "alpaca_api_key": "", "alpaca_api_secret": "",
        "event_lab_enabled": False,
        **overrides,
    }
    settings = Settings(_env_file=None, storage_path=tmp_path / "health.sqlite3", **configuration)
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == ("degraded" if issues else "ok")
    assert payload["configuration_issues"] == issues
    assert payload["analyst_ready"] is ("GEMINI_NOT_CONFIGURED" not in issues)
    assert payload["authentication_enabled"] is ("AUTH_NOT_CONFIGURED" not in issues)
    assert payload["market_data_ready"] is ("MARKET_DATA_NOT_CONFIGURED" not in issues)
    assert "test-gemini" not in response.text
    assert "test-key" not in response.text
    assert "test-secret" not in response.text
    assert "test-only" not in response.text
    assert "test-publishable" not in response.text


def test_whitespace_only_credentials_are_missing_configuration(tmp_path):
    settings = Settings(_env_file=None, storage_path=tmp_path / "blank.sqlite3",
                        analyst_mode="gemini", market_data_provider="alpaca",
                        gemini_api_key="   ", alpaca_api_key="\t", alpaca_api_secret="  ",
                        alpaca_history_feed="iex",
                        supabase_url="https://example.supabase.co", supabase_anon_key="  ",
                        supabase_publishable_key="\t", event_lab_enabled=False)
    assert settings.has_gemini_key is False
    assert settings.has_alpaca_history is False
    assert settings.authentication_enabled is False
    assert Settings(_env_file=None, supabase_url="  ", supabase_anon_key="test-only",
                    supabase_publishable_key="").authentication_enabled is False
    with TestClient(create_app(settings)) as client:
        health = client.get("/health").json()
    assert health["status"] == "degraded"
    assert health["configuration_issues"] == [
        "AUTH_NOT_CONFIGURED", "GEMINI_NOT_CONFIGURED", "MARKET_DATA_NOT_CONFIGURED",
    ]


def test_blank_auth_configuration_returns_unavailable_before_contacting_supabase(monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("Unconfigured auth must not send a token upstream")

    monkeypatch.setattr("backend.auth.httpx.get", unexpected_request)
    settings = Settings(_env_file=None, supabase_url="https://example.supabase.co",
                        supabase_anon_key="  ", supabase_publishable_key="")
    with pytest.raises(HTTPException) as error:
        current_user_id(authorization="Bearer test-session", settings=settings)
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "AUTH_NOT_CONFIGURED"


@pytest.mark.parametrize("anon_key,publishable_key,expected", [
    ("", "test-publishable", "test-publishable"),
    ("  ", " test-publishable ", "test-publishable"),
    (" test-anon ", "test-publishable", "test-anon"),
])
def test_v1_auth_preserves_publishable_fallback_and_anon_precedence(
    monkeypatch, anon_key, publishable_key, expected,
):
    owner = "00000000-0000-4000-8000-000000000001"
    calls = []

    def user_response(url, *, headers, timeout):
        calls.append((url, headers))
        return httpx.Response(200, json={"id": owner})

    monkeypatch.setattr("backend.auth.httpx.get", user_response)
    settings = Settings(_env_file=None, supabase_url="https://example.supabase.co",
                        supabase_anon_key=anon_key, supabase_publishable_key=publishable_key)
    assert current_user_id(authorization="Bearer test-session", settings=settings) == owner
    assert calls == [("https://example.supabase.co/auth/v1/user", {
        "apikey": expected, "Authorization": "Bearer test-session",
    })]
