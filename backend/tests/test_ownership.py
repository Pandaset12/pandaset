import sqlite3
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.config import Settings, get_settings
from backend.main import create_app
from backend.providers import SamplePriceProvider, EngineQuantProvider, get_provider
from backend.storage import PortfolioStore
from backend.schemas import PortfolioInput


@pytest.fixture
def client(tmp_path, monkeypatch):
    users = {"owner": str(uuid4()), "other": str(uuid4())}

    def verify(_url, *, headers, timeout):
        class Response:
            status_code = 200 if headers["Authorization"] in {"Bearer owner", "Bearer other"} else 401

            def json(self):
                return {"id": users[headers["Authorization"].split()[1]]}

        return Response()

    monkeypatch.setattr("backend.auth.httpx.get", verify)
    settings = Settings(_env_file=None, storage_path=tmp_path / "portfolios.sqlite3",
                        supabase_url="https://example.supabase.co", supabase_anon_key="test-publishable")
    with TestClient(create_app(settings)) as api:
        yield api, users


def test_auth_and_portfolio_ownership(client):
    api, users = client
    payload = {"name": "Investor", "holdings": [{"symbol": "SPY", "weight": 1.0}]}
    assert api.get("/api/v1/portfolios").status_code == 401
    assert api.get("/api/v1/quotes", params={"symbols": "AAPL"}).status_code == 401
    assert api.get("/api/v1/portfolios", headers={"Authorization": "Bearer bad"}).status_code == 401
    owner = {"Authorization": "Bearer owner"}
    other = {"Authorization": "Bearer other"}
    created = api.post("/api/v1/portfolios", json=payload, headers=owner)
    assert created.status_code == 201
    portfolio_id = created.json()["portfolio_id"]
    assert "owner_id" not in created.json()
    assert api.app.state.store.list_for_owner(users["owner"])[0].portfolio_id == portfolio_id
    assert len(api.get("/api/v1/portfolios", headers=owner).json()) == 1
    assert api.get("/api/v1/portfolios", headers=other).json() == []
    assert api.get(f"/api/v1/portfolios/{portfolio_id}", headers=owner).status_code == 200
    assert api.get(f"/api/v1/portfolios/{portfolio_id}", headers=other).status_code == 404
    for method, path, body in [
        ("get", "metrics", None),
        ("post", "briefing", {"portfolio_revision": 1}),
        ("post", "risk/explanation", {"portfolio_revision": 1}),
        ("post", "what-if", {"holdings": payload["holdings"]}),
        ("post", "what-if/explanation", {"portfolio_revision": 1, "proposed_weights": {"SPY": 1.0}}),
    ]:
        response = getattr(api, method)(f"/api/v1/portfolios/{portfolio_id}/{path}", json=body, headers=other) if method == "post" else api.get(f"/api/v1/portfolios/{portfolio_id}/{path}", headers=other)
        assert response.status_code == 404, (path, response.text)

    legacy_paths = [
        ("get", f"/api/portfolios/{portfolio_id}/analytics", None),
        ("post", "/api/what-if", {"portfolio_id": portfolio_id, "proposed_weights": {"SPY": 1.0}}),
    ]
    for method, path, body in legacy_paths:
        call = getattr(api, method)
        unauthenticated = call(path, json=body) if body else call(path)
        assert unauthenticated.status_code == 401, (path, unauthenticated.text)
        response = call(path, json=body, headers=other) if body else call(path, headers=other)
        assert response.status_code == 404, (path, response.text)
        response = call(path, json=body, headers=owner) if body else call(path, headers=owner)
        assert response.status_code == 200, (path, response.text)


def test_legacy_sqlite_migrates_without_assigning_owner(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE portfolios (portfolio_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT INTO portfolios VALUES ('legacy', '{}')")
    store = PortfolioStore(path)
    assert store.list_for_owner(str(uuid4())) == []
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT owner_id FROM portfolios WHERE portfolio_id='legacy'").fetchone() == (None,)


def test_update_preserves_identity_and_owner_and_increments_revision(client):
    api, _ = client
    owner = {"Authorization": "Bearer owner"}
    other = {"Authorization": "Bearer other"}
    created = api.post("/api/v1/portfolios", json={
        "name": "Original", "holdings": [{"symbol": "SPY", "weight": 1.0}],
    }, headers=owner).json()
    portfolio_id = created["portfolio_id"]
    path = f"/api/v1/portfolios/{portfolio_id}"
    metrics = api.get(path + "/metrics", headers=owner)
    assert metrics.status_code == 200, metrics.text
    assert metrics.json()["portfolio_revision"] == 1

    replacement = {"name": "Updated", "holdings": [{"symbol": "TLT", "weight": 1.0}]}
    assert api.put(path, json=replacement).status_code == 401
    assert api.put(path, json=replacement, headers=other).status_code == 404
    assert api.put(path, json={"name": "Bad", "holdings": []}, headers=owner).status_code == 422
    for revision in (2, 3):
        updated_response = api.put(path, json=replacement, headers=owner)
        assert updated_response.status_code == 200, updated_response.text
        updated = updated_response.json()
        assert updated["portfolio_id"] == portfolio_id
        assert updated["created_at"] == created["created_at"]
        assert updated["holdings"] == replacement["holdings"]
        assert updated["revision"] == revision
        assert len(api.get("/api/v1/portfolios", headers=owner).json()) == 1
    assert api.get(path, headers=owner).json()["holdings"] == replacement["holdings"]
    assert api.get(path, headers=other).status_code == 404
    assert api.post(path + "/briefing", json={"portfolio_revision": 1}, headers=owner).status_code == 409
    refreshed = api.get(path + "/metrics", headers=owner)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["weights"] == {"TLT": 1.0}
    assert refreshed.json()["portfolio_revision"] == 3


def test_delete_requires_owner_and_removes_portfolio(client):
    api, users = client
    owner = {"Authorization": "Bearer owner"}
    other = {"Authorization": "Bearer other"}
    created = api.post("/api/v1/portfolios", json={
        "name": "Delete me", "holdings": [{"symbol": "SPY", "weight": 1.0}],
    }, headers=owner).json()
    path = f"/api/v1/portfolios/{created['portfolio_id']}"
    assert api.delete(path).status_code == 401
    assert api.delete(path, headers=other).status_code == 404
    assert api.get(path, headers=owner).status_code == 200
    assert api.delete(path, headers=owner).status_code == 204
    assert api.get(path, headers=owner).status_code == 404
    assert api.delete(path, headers=owner).status_code == 404
    assert api.get("/api/v1/portfolios", headers=owner).json() == []
    assert api.get(path + "/metrics", headers=owner).status_code == 404
    assert api.app.state.store.list_for_owner(users["other"]) == []


def test_create_and_update_reject_missing_history_before_persistence(client):
    api, _ = client
    owner = {"Authorization": "Bearer owner"}
    for symbol in ("AAPL", "MSFT", "SPY", "JPM"):
        response = api.post("/api/v1/portfolios", json={
            "name": symbol, "holdings": [{"symbol": symbol, "weight": 1.0}],
        }, headers=owner)
        assert response.status_code == 201, response.text
    original = api.get("/api/v1/portfolios", headers=owner).json()
    for symbol in ("SPACE", "BALLSS"):
        rejected = api.post("/api/v1/portfolios", json={
            "name": symbol, "holdings": [{"symbol": symbol, "weight": 1.0}],
        }, headers=owner)
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "UNSUPPORTED_PORTFOLIO_SYMBOL"
        update = api.put(f"/api/v1/portfolios/{original[0]['portfolio_id']}", json={
            "name": symbol, "holdings": [{"symbol": symbol, "weight": 1.0}],
        }, headers=owner)
        assert update.status_code == 422
    assert api.get("/api/v1/portfolios", headers=owner).json() == original


def test_provider_outage_does_not_persist_unverified_portfolio(client, monkeypatch):
    from backend.market_data_errors import ProviderUnavailable
    from backend.providers import SamplePriceProvider

    api, _ = client
    owner = {"Authorization": "Bearer owner"}

    def unavailable(self, symbols, lookback_days=252):
        raise ProviderUnavailable("Upstream unavailable")

    monkeypatch.setattr(SamplePriceProvider, "prices", unavailable)
    response = api.post("/api/v1/portfolios", json={
        "name": "Not saved", "holdings": [{"symbol": "SPY", "weight": 1.0}],
    }, headers=owner)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "MARKET_HISTORY_UNAVAILABLE"
    assert api.get("/api/v1/portfolios", headers=owner).json() == []


def test_preflight_history_is_reused_by_following_metrics(client, monkeypatch):
    from backend.providers import SamplePriceProvider

    api, _ = client
    calls = []
    original = SamplePriceProvider.prices

    def counted(self, symbols, lookback_days=252):
        calls.append((tuple(symbols), lookback_days))
        return original(self, symbols, lookback_days)

    monkeypatch.setattr(SamplePriceProvider, "prices", counted)
    headers = {"Authorization": "Bearer owner"}
    for symbol in ("SPY", "TLT"):
        assert api.get("/api/v1/market-history", params={"symbols": [symbol], "lookback_days": 2}).status_code == 200
    created = api.post("/api/v1/portfolios", json={"name": "Cached", "holdings": [
        {"symbol": "SPY", "weight": 0.5}, {"symbol": "TLT", "weight": 0.5},
    ]}, headers=headers)
    assert created.status_code == 201
    analysis = api.get(f"/api/v1/portfolios/{created.json()['portfolio_id']}/metrics", headers=headers)
    assert analysis.status_code == 200, analysis.text
    assert calls == [(("SPY",), 252), (("TLT",), 252)]


def test_alpaca_preflight_is_reused_by_metrics_when_cache_rights_confirmed(client, monkeypatch):
    import pandas as pd
    from backend.alpaca_history import AlpacaHistoryProvider

    api, _ = client
    sample_settings = api.app.dependency_overrides[get_settings]()
    live_settings = sample_settings.model_copy(update={
        "market_data_provider": "alpaca",
        "alpaca_api_key": SecretStr("test-key"),
        "alpaca_api_secret": SecretStr("test-secret"),
        "alpaca_history_feed": "iex",
        "alpaca_cache_rights_confirmed": True,
    })
    monkeypatch.setitem(api.app.dependency_overrides, get_settings, lambda: live_settings)
    calls = []

    def fetch(self, symbols, start, end, page_token):
        calls.append(tuple(symbols))
        return {"bars": {symbol: [
            {"t": day.strftime("%Y-%m-%dT12:00:00Z"), "c": 100 + index}
            for index, day in enumerate(pd.bdate_range(end="2026-09-25", periods=253))
        ] for symbol in symbols}, "next_page_token": None}

    monkeypatch.setattr(AlpacaHistoryProvider, "_fetch", fetch)
    preflight = api.get("/api/v1/market-history", params={"symbols": ["SPY"], "lookback_days": 2})
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["data_mode"] == "live"
    assert preflight.json()["observation_count"] == 2
    headers = {"Authorization": "Bearer owner"}
    created = api.post("/api/v1/portfolios", json={"name": "Live", "holdings": [
        {"symbol": "SPY", "weight": 1.0},
    ]}, headers=headers)
    assert created.status_code == 201, created.text
    analysis = api.get(f"/api/v1/portfolios/{created.json()['portfolio_id']}/metrics", headers=headers)
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["data_mode"] == "live"
    assert analysis.json()["observation_count"] == 252
    assert calls == [("SPY",)]


def test_alpaca_metrics_use_each_saved_portfolios_symbols_and_weights(client, monkeypatch):
    import pandas as pd
    from backend.alpaca_history import AlpacaHistoryProvider

    api, _ = client
    settings = api.app.dependency_overrides[get_settings]().model_copy(update={
        "market_data_provider": "alpaca",
        "alpaca_api_key": SecretStr("test-key"),
        "alpaca_api_secret": SecretStr("test-secret"),
        "alpaca_history_feed": "iex",
    })
    monkeypatch.setitem(api.app.dependency_overrides, get_settings, lambda: settings)
    calls = []

    def fetch(self, symbols, start, end, page_token):
        calls.append(tuple(symbols))
        dates = pd.bdate_range(end="2026-09-25", periods=253)
        return {"bars": {symbol: [
            {"t": day.strftime("%Y-%m-%dT12:00:00Z"),
             "c": 100 + index * (1 if symbol == "SPY" else 2)}
            for index, day in enumerate(dates)
        ] for symbol in symbols}, "next_page_token": None}

    monkeypatch.setattr(AlpacaHistoryProvider, "_fetch", fetch)
    headers = {"Authorization": "Bearer owner"}
    portfolios = [
        [{"symbol": "SPY", "weight": 1.0}],
        [{"symbol": "SPY", "weight": 0.25}, {"symbol": "TLT", "weight": 0.75}],
    ]
    analyses = []
    for index, holdings in enumerate(portfolios):
        created = api.post("/api/v1/portfolios", json={
            "name": f"Saved {index}", "holdings": holdings,
        }, headers=headers)
        assert created.status_code == 201, created.text
        response = api.get(
            f"/api/v1/portfolios/{created.json()['portfolio_id']}/metrics",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        analyses.append(response.json())

    assert calls == [("SPY",), ("SPY",), ("SPY", "TLT"), ("SPY", "TLT")]
    assert analyses[0]["weights"] == {"SPY": 1.0}
    assert analyses[1]["weights"] == {"SPY": 0.25, "TLT": 0.75}
    assert set(analyses[0]["series"]["asset_index"]) == {"SPY"}
    assert set(analyses[1]["series"]["asset_index"]) == {"SPY", "TLT"}
    assert analyses[0]["portfolio_return"] != analyses[1]["portfolio_return"]
    assert all(result["data_mode"] == "live" for result in analyses)
    assert all(result["data_quality"]["source"] == "alpaca_adjusted_daily" for result in analyses)
    assert all(any("IEX" in note for note in result["data_quality"]["warnings"])
               for result in analyses)


@pytest.mark.parametrize("failure,status,code", [
    ("missing_config", 502, "PROVIDER_UNAVAILABLE"),
    ("rate_limit", 429, "PROVIDER_RATE_LIMIT"),
    ("incomplete", 404, "MARKET_HISTORY_NOT_FOUND"),
])
def test_alpaca_metric_failures_never_save_sample_results(client, monkeypatch, failure, status, code):
    from backend.alpaca_history import AlpacaHistoryProvider, CoverageError, RateLimitError

    api, _ = client
    headers = {"Authorization": "Bearer owner"}
    created = api.post("/api/v1/portfolios", json={
        "name": "Unavailable", "holdings": [{"symbol": "SPY", "weight": 1.0}],
    }, headers=headers)
    assert created.status_code == 201
    settings = api.app.dependency_overrides[get_settings]().model_copy(update={
        "market_data_provider": "alpaca",
        "alpaca_api_key": SecretStr("" if failure == "missing_config" else "test-key"),
        "alpaca_api_secret": SecretStr("test-secret"),
        "alpaca_history_feed": "iex",
    })
    monkeypatch.setitem(api.app.dependency_overrides, get_settings, lambda: settings)

    def fetch(self, symbols, start, end, page_token):
        if failure == "missing_config":
            pytest.fail("Unconfigured Alpaca analysis must not contact the provider")
        if failure == "rate_limit":
            raise RateLimitError("Alpaca history rate limit was reached.")
        raise CoverageError("Alpaca history is incomplete.")

    monkeypatch.setattr(AlpacaHistoryProvider, "_fetch", fetch)
    response = api.get(
        f"/api/v1/portfolios/{created.json()['portfolio_id']}/metrics",
        headers=headers,
    )
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    with api.app.state.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 0


def test_what_if_uses_aligned_alpaca_history_for_added_holding(client, monkeypatch):
    import pandas as pd
    from backend.alpaca_history import AlpacaHistoryProvider

    api, _ = client
    settings = api.app.dependency_overrides[get_settings]().model_copy(update={
        "market_data_provider": "alpaca",
        "alpaca_api_key": SecretStr("test-key"),
        "alpaca_api_secret": SecretStr("test-secret"),
        "alpaca_history_feed": "iex",
    })
    monkeypatch.setitem(api.app.dependency_overrides, get_settings, lambda: settings)
    calls = []

    def fetch(self, symbols, start, end, page_token):
        calls.append(tuple(symbols))
        dates = pd.bdate_range(end="2026-09-25", periods=253)
        return {"bars": {symbol: [
            {"t": day.strftime("%Y-%m-%dT12:00:00Z"), "c": 100 + index * (1 if symbol == "SPY" else 2)}
            for index, day in enumerate(dates)
        ] for symbol in symbols}, "next_page_token": None}

    monkeypatch.setattr(AlpacaHistoryProvider, "_fetch", fetch)
    headers = {"Authorization": "Bearer owner"}
    created = api.post("/api/v1/portfolios", json={"name": "What-if", "holdings": [
        {"symbol": "SPY", "weight": 1.0},
    ]}, headers=headers)
    assert created.status_code == 201, created.text
    result = api.post(f"/api/v1/portfolios/{created.json()['portfolio_id']}/what-if", json={
        "holdings": [{"symbol": "SPY", "weight": 0.5}, {"symbol": "TLT", "weight": 0.5}],
    }, headers=headers)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert calls == [("SPY",), ("SPY", "TLT")]
    assert payload["current_analysis"]["data_source"] == "alpaca_adjusted_daily"
    assert payload["proposed_analysis"]["data_source"] == "alpaca_adjusted_daily"
    assert any("IEX" in note for note in payload["proposed_analysis"]["notes"])


def test_metrics_reject_a_portfolio_edit_during_calculation(client):
    api, users = client
    headers = {"Authorization": "Bearer owner"}
    created = api.post("/api/v1/portfolios", json={"name": "Before", "holdings": [
        {"symbol": "SPY", "weight": 1.0},
    ]}, headers=headers).json()
    selected, resume = Event(), Event()
    store = api.app.state.store

    class BlockingProvider(EngineQuantProvider):
        def analyze(self, portfolio):
            selected.set()
            assert resume.wait(5)
            return super().analyze(portfolio)

    api.app.dependency_overrides[get_provider] = lambda: BlockingProvider(store, SamplePriceProvider())
    outcome = {}

    def calculate():
        outcome["response"] = api.get(f"/api/v1/portfolios/{created['portfolio_id']}/metrics", headers=headers)

    worker = Thread(target=calculate)
    worker.start()
    assert selected.wait(5)
    store.update(created["portfolio_id"], users["owner"], PortfolioInput(name="After", holdings=[
        {"symbol": "TLT", "weight": 1.0},
    ]))
    resume.set()
    worker.join(5)
    assert not worker.is_alive()
    assert outcome["response"].status_code == 409
    assert outcome["response"].json()["error"]["code"] == "PORTFOLIO_CHANGED"
