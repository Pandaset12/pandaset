from fastapi.testclient import TestClient

from backend.auth import current_user_id
from backend.config import Settings
from backend.main import create_app
from backend.market_data_errors import ProviderUnavailable
from backend.providers import get_provider


def test_current_metrics_and_comparison_are_on_demand(tmp_path):
    app = create_app(Settings(_env_file=None, storage_path=tmp_path / "portfolios.sqlite3"))
    with TestClient(app) as client:
        created = client.post("/api/v1/portfolios", json={
            "name": "Core", "holdings": [{"symbol": "NVDA", "weight": 0.6}, {"symbol": "TLT", "weight": 0.4}],
        })
        assert created.status_code == 201, created.text
        portfolio_id = created.json()["portfolio_id"]
        metrics = client.get(f"/api/v1/portfolios/{portfolio_id}/metrics")
        assert metrics.status_code == 200, metrics.text
        assert metrics.json()["portfolio_revision"] == 1
        assert metrics.json()["data_quality"]["source"] == "synthetic_fixture"
        assert metrics.json()["data_mode"] == "demo"
        assert any("FICTIONAL" in warning for warning in metrics.json()["data_quality"]["warnings"])
        assert "analysis_id" not in metrics.json()
        comparison = client.post(f"/api/v1/portfolios/{portfolio_id}/what-if", json={
            "holdings": [{"symbol": "NVDA", "weight": 0.4}, {"symbol": "TLT", "weight": 0.6}],
        })
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["portfolio_revision"] == 1
        assert comparison.json()["modeled_result"] is True
        assert comparison.json()["current_analysis"]["data_as_of"] == comparison.json()["proposed_analysis"]["data_as_of"]
        with app.state.store.connection() as connection:
            assert connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 0

        briefing = client.post(f"/api/v1/portfolios/{portfolio_id}/briefing", json={"portfolio_revision": 1})
        assert briefing.status_code == 200, briefing.text
        assert briefing.json()["metrics"]["portfolio_revision"] == 1
        assert briefing.json()["metrics"]["portfolio_return"] == metrics.json()["portfolio_return"]
        assert "analysis_id" not in briefing.json()

        scenario = client.post(f"/api/v1/portfolios/{portfolio_id}/what-if/explanation", json={
            "portfolio_revision": 1, "proposed_weights": {"NVDA": 0.4, "TLT": 0.6},
        })
        assert scenario.status_code == 200, scenario.text
        assert scenario.json()["comparison"]["current_analysis"]["data_as_of"] == comparison.json()["current_analysis"]["data_as_of"]

        stale = client.post(f"/api/v1/portfolios/{portfolio_id}/briefing", json={"portfolio_revision": 2})
        assert stale.status_code == 409


def test_current_metrics_are_owner_scoped_and_never_fall_back_on_provider_failure(tmp_path):
    app = create_app(Settings(_env_file=None, storage_path=tmp_path / "portfolios.sqlite3"))
    with TestClient(app) as client:
        app.dependency_overrides[current_user_id] = lambda: "owner-a"
        created = client.post("/api/v1/portfolios", json={
            "name": "Core", "holdings": [{"symbol": "SPY", "weight": 1.0}],
        })
        assert created.status_code == 201
        portfolio_id = created.json()["portfolio_id"]
        app.dependency_overrides[current_user_id] = lambda: "owner-b"
        assert client.get(f"/api/v1/portfolios/{portfolio_id}/metrics").status_code == 404
        app.dependency_overrides[current_user_id] = lambda: "owner-a"

        class FailedProvider:
            def analyze(self, portfolio):
                raise ProviderUnavailable("Failed upstream")

        app.dependency_overrides[get_provider] = FailedProvider
        result = client.get(f"/api/v1/portfolios/{portfolio_id}/metrics")
        assert result.status_code == 502
        assert result.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        with app.state.store.connection() as connection:
            assert connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 0
