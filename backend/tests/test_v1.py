import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.providers import DemoQuantProvider, ProviderUnavailable, demo_metrics, get_provider


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, analyst_mode="demo", storage_path=tmp_path / "test.sqlite3")


@pytest.fixture
def client(settings):
    app = create_app(settings)
    # Retain regression coverage of the precomputed fixture provider.
    app.dependency_overrides[get_provider] = DemoQuantProvider
    with TestClient(app) as value:
        yield value


def create_demo(client):
    holdings = client.get("/api/v1/portfolios/demo").json()["holdings"]
    result = client.post("/api/v1/portfolios", json={"name": " My portfolio ", "holdings": holdings})
    assert result.status_code == 201
    return result.json()["portfolio_id"]


def analyze(client, portfolio_id="demo"):
    result = client.get(f"/api/v1/portfolios/{portfolio_id}/metrics")
    assert result.status_code == 200, result.text
    return result.json()


def test_current_metrics_complete_demo_flow(client):
    portfolio_id = create_demo(client)
    analysis = analyze(client, portfolio_id)
    assert analysis["concentration"] == {"largest_position": "SPY", "largest_weight": 0.4}
    assert analysis["as_of"] is None
    assert analysis["portfolio_return"] is None
    assert analysis["correlation_matrix"] is None
    assert analysis["observation_count"] is None
    assert analysis["data_quality"]["source"] == "synthetic_fixture"
    assert "analysis_id" not in analysis
    with client.app.state.store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 0


def test_portfolio_survives_app_restart_and_metrics_recompute(settings):
    with TestClient(create_app(settings)) as first:
        portfolio_id = create_demo(first)
        analysis = analyze(first, portfolio_id)
    with TestClient(create_app(settings)) as second:
        result = second.get(f"/api/v1/portfolios/{portfolio_id}/metrics")
        assert result.status_code == 200
        assert result.json()["weights"] == analysis["weights"]
        assert result.json()["portfolio_revision"] == analysis["portfolio_revision"]


@pytest.mark.parametrize("holdings", [
    [{"symbol": "NVDA", "weight": 0.5}, {"symbol": " nvda ", "weight": 0.5}],
    [{"symbol": "NVDA", "weight": 0.6}, {"symbol": "JPM", "weight": 0.5}],
    [{"symbol": "NVDA", "weight": -0.1}, {"symbol": "JPM", "weight": 1.1}],
    [{"symbol": " ", "weight": 1.0}],
    [{"symbol": "NVDA", "weight": True}],
])
def test_invalid_allocations_use_consistent_error_shape(client, holdings):
    result = client.post("/api/v1/portfolios", json={"name": "Bad input", "holdings": holdings})
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "INVALID_INPUT"
    assert "detail" not in result.json()


def test_custom_allocation_never_gets_demo_risk_numbers(client):
    portfolio = client.post("/api/v1/portfolios", json={
        "name": "Single asset", "holdings": [{"symbol": " aapl ", "weight": 1.0}],
    })
    assert portfolio.status_code == 201
    assert portfolio.json()["holdings"] == [{"symbol": "AAPL", "weight": 1.0}]
    portfolio_id = portfolio.json()["portfolio_id"]
    result = client.get(f"/api/v1/portfolios/{portfolio_id}/metrics")
    assert result.status_code == 501
    assert result.json()["error"]["code"] == "QUANT_INTEGRATION_PENDING"


def test_v1_what_if_is_explicitly_pending_and_does_not_modify_portfolio(client):
    before = client.get("/api/v1/portfolios/demo").json()
    result = client.post("/api/v1/portfolios/demo/what-if", json={
        "holdings": [{"symbol": "JPM", "weight": 1.0}],
    })
    assert result.status_code == 501
    assert result.json()["error"]["code"] == "QUANT_INTEGRATION_PENDING"
    assert client.get("/api/v1/portfolios/demo").json() == before


@pytest.mark.parametrize("failure", ["wrong_portfolio", "bad_weights", "bad_risk", "provider_error"])
def test_bad_provider_outputs_are_not_returned_as_valid_metrics(client, failure):
    class BadProvider(DemoQuantProvider):
        def analyze(self, portfolio):
            result = super().analyze(portfolio)
            if failure == "wrong_portfolio":
                result.portfolio_id = "somebody_else"
            elif failure == "bad_weights":
                result.weights["NVDA"] = 0.8
            elif failure == "bad_risk":
                result.risk_contribution["NVDA"] = 99.0
            else:
                raise ProviderUnavailable("private upstream details must not appear")
            return result

    client.app.dependency_overrides[get_provider] = BadProvider
    response = client.get("/api/v1/portfolios/demo/metrics")
    assert response.status_code == 502
    assert "private upstream" not in response.text


def test_negative_risk_contribution_is_preserved(client):
    class DiversifyingProvider(DemoQuantProvider):
        def analyze(self, portfolio):
            result = super().analyze(portfolio)
            result.risk_contribution = {"NVDA": 1.1, "SPY": -0.1, "JPM": 0, "TLT": 0}
            return result

    client.app.dependency_overrides[get_provider] = DiversifyingProvider
    assert analyze(client)["risk_contribution"]["SPY"] == -0.1


def test_fixture_reads_are_isolated():
    first = demo_metrics()
    first.weights["NVDA"] = 0.99
    first.notes.append("mutated")
    assert demo_metrics().weights["NVDA"] == 0.3
    assert "mutated" not in demo_metrics().notes
