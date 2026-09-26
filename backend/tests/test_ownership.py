import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.storage import PortfolioStore, StalePortfolio


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
