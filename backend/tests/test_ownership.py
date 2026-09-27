import sqlite3
from contextlib import contextmanager
from threading import Event, Thread, current_thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.config import Settings, get_settings
from backend.main import create_app
from backend.storage import PortfolioStore, SnapshotNotFound, StalePortfolio
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
        ("post", "analysis", None),
        ("get", "analyses/nonexistent", None),
        ("post", "ask", {"analysis_id": "nonexistent", "question": "Risk?"}),
        ("post", "briefing", {"analysis_id": "nonexistent"}),
        ("post", "risk/explanation", {"analysis_id": "nonexistent"}),
        ("post", "what-if", {"holdings": payload["holdings"]}),
        ("post", "what-if/explanation", {"analysis_id": "nonexistent", "proposed_weights": {"SPY": 1.0}}),
    ]:
        response = getattr(api, method)(f"/api/v1/portfolios/{portfolio_id}/{path}", json=body, headers=other) if method == "post" else api.get(f"/api/v1/portfolios/{portfolio_id}/{path}", headers=other)
        assert response.status_code == 404, (path, response.text)

    legacy_paths = [
        ("get", f"/api/portfolios/{portfolio_id}/analytics", None),
        ("post", "/api/analyst", {"portfolio_id": portfolio_id, "question": "Risk?"}),
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


def test_update_preserves_identity_and_owner_and_invalidates_old_analyses(client):
    api, users = client
    owner = {"Authorization": "Bearer owner"}
    other = {"Authorization": "Bearer other"}
    created = api.post("/api/v1/portfolios", json={
        "name": "Original", "holdings": [{"symbol": "SPY", "weight": 1.0}],
    }, headers=owner).json()
    portfolio_id = created["portfolio_id"]
    path = f"/api/v1/portfolios/{portfolio_id}"
    analysis = api.post(path + "/analysis", headers=owner)
    assert analysis.status_code == 200, analysis.text
    analysis_id = analysis.json()["analysis_id"]
    old_metrics, _ = api.app.state.store.get_analysis(portfolio_id, analysis_id)

    replacement = {"name": "Updated", "holdings": [{"symbol": "TLT", "weight": 1.0}]}
    assert api.put(path, json=replacement).status_code == 401
    assert api.put(path, json=replacement, headers=other).status_code == 404
    assert api.put(path, json={"name": "Bad", "holdings": []}, headers=owner).status_code == 422
    for _ in range(2):
        updated_response = api.put(path, json=replacement, headers=owner)
        assert updated_response.status_code == 200, updated_response.text
        updated = updated_response.json()
        assert updated["portfolio_id"] == portfolio_id
        assert updated["created_at"] == created["created_at"]
        assert updated["holdings"] == replacement["holdings"]
        assert len(api.get("/api/v1/portfolios", headers=owner).json()) == 1
    assert api.get(path, headers=owner).json()["holdings"] == replacement["holdings"]
    assert api.get(path, headers=other).status_code == 404
    assert api.get(path + f"/analyses/{analysis_id}", headers=owner).status_code == 404
    with pytest.raises(StalePortfolio):
        api.app.state.store.save_analysis(old_metrics, users["owner"])
    refreshed = api.post(path + "/analysis", headers=owner)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["weights"] == {"TLT": 1.0}


def test_preflight_history_is_reused_by_following_analysis(client, monkeypatch):
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
    analysis = api.post(f"/api/v1/portfolios/{created.json()['portfolio_id']}/analysis", headers=headers)
    assert analysis.status_code == 200, analysis.text
    assert calls == [(("SPY",), 252), (("TLT",), 252)]


def test_alpaca_preflight_is_reused_by_analysis_when_cache_rights_confirmed(client, monkeypatch):
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
    analysis = api.post(f"/api/v1/portfolios/{created.json()['portfolio_id']}/analysis", headers=headers)
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["data_mode"] == "live"
    assert analysis.json()["observation_count"] == 252
    assert calls == [("SPY",)]


def test_alpaca_analysis_uses_each_saved_portfolios_symbols_and_weights(client, monkeypatch):
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
        response = api.post(
            f"/api/v1/portfolios/{created.json()['portfolio_id']}/analysis",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        analyses.append(response.json())

    assert calls == [("SPY",), ("SPY", "TLT")]
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
def test_alpaca_analysis_failures_never_save_sample_results(client, monkeypatch, failure, status, code):
    from backend.alpaca_history import AlpacaHistoryProvider, CoverageError, RateLimitError

    api, _ = client
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
    headers = {"Authorization": "Bearer owner"}
    created = api.post("/api/v1/portfolios", json={
        "name": "Unavailable", "holdings": [{"symbol": "SPY", "weight": 1.0}],
    }, headers=headers)
    assert created.status_code == 201
    response = api.post(
        f"/api/v1/portfolios/{created.json()['portfolio_id']}/analysis",
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
    assert calls == [("SPY", "TLT")]
    assert payload["current_analysis"]["data_source"] == "alpaca_adjusted_daily"
    assert payload["proposed_analysis"]["data_source"] == "alpaca_adjusted_daily"
    assert any("IEX" in note for note in payload["proposed_analysis"]["notes"])


def test_concurrent_update_cannot_leave_an_old_analysis_after_commit(client, monkeypatch):
    api, users = client
    headers = {"Authorization": "Bearer owner"}
    created = api.post("/api/v1/portfolios", json={"name": "Before", "holdings": [
        {"symbol": "SPY", "weight": 1.0},
    ]}, headers=headers).json()
    portfolio_id = created["portfolio_id"]
    response = api.post(f"/api/v1/portfolios/{portfolio_id}/analysis", headers=headers)
    assert response.status_code == 200
    metrics, _ = api.app.state.store.get_analysis(portfolio_id, response.json()["analysis_id"])
    store = api.app.state.store
    original_connection = store.connection
    selected = Event()
    resume = Event()
    update_started = Event()
    outcome = {}

    @contextmanager
    def paused_connection():
        with original_connection() as connection:
            class ConnectionProxy:
                def execute(self, sql, parameters=()):
                    result = connection.execute(sql, parameters)
                    if current_thread().name == "save-old-analysis" and sql.startswith("SELECT payload FROM portfolios"):
                        selected.set()
                        assert resume.wait(5)
                    return result

            yield ConnectionProxy()

    monkeypatch.setattr(store, "connection", paused_connection)

    def save_old():
        outcome["analysis"] = store.save_analysis(metrics, users["owner"])[0]

    def update():
        update_started.set()
        outcome["updated"] = store.update(portfolio_id, users["owner"], PortfolioInput(
            name="After", holdings=[{"symbol": "TLT", "weight": 1.0}],
        ))

    saver = Thread(target=save_old, name="save-old-analysis")
    updater = Thread(target=update, name="update-portfolio")
    saver.start()
    assert selected.wait(5)
    updater.start()
    assert update_started.wait(5)
    assert updater.is_alive()
    resume.set()
    saver.join(5)
    updater.join(5)
    assert not saver.is_alive() and not updater.is_alive()
    assert outcome["updated"].weights == {"TLT": 1.0}
    with pytest.raises(SnapshotNotFound):
        store.get_analysis(portfolio_id, outcome["analysis"])
