import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from quant_engine import analyze_portfolio, compare_portfolios

from backend.config import Settings
from backend.gemini_service import metric_catalog
from backend.main import create_app
from backend.providers import EngineQuantProvider, SamplePriceProvider, get_provider, map_quant_report
from backend.schemas import AnalyticsSnapshot


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(
        _env_file=None, analyst_mode="demo", storage_path=tmp_path / "test.sqlite3",
    ))) as api:
        yield api


def create(client, weights):
    response = client.post("/api/v1/portfolios", json={
        "name": "Quant integration", "holdings": [
            {"symbol": symbol, "weight": weight} for symbol, weight in weights.items()
        ],
    })
    assert response.status_code == 201, response.text
    return response.json()["portfolio_id"]


def test_creation_analysis_mapping_persistence_and_ask(client):
    weights = {"NVDA": 0.6, "TLT": 0.4}
    portfolio_id = create(client, weights)
    report = analyze_portfolio(SamplePriceProvider().prices(sorted(weights)), weights)
    response = client.post(f"/api/v1/portfolios/{portfolio_id}/analysis")
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert analysis["weights"] == weights
    assert analysis["portfolio_return"] == report["portfolio"]["cumulative_return"]
    assert analysis["annualized_return"] == report["portfolio"]["geometric_annualized_return"]
    assert analysis["max_drawdown"] == report["portfolio"]["maximum_drawdown"]
    assert analysis["portfolio_volatility"] == report["portfolio"]["annualized_volatility"]
    assert analysis["asset_volatility"] == {
        symbol: asset["annualized_volatility"] for symbol, asset in report["assets"].items()
    }
    assert analysis["risk_contribution"] == {
        symbol: asset["percentage_risk_contribution"] for symbol, asset in report["assets"].items()
    }
    assert analysis["correlation_matrix"] == report["matrices"]["correlation"]
    assert analysis["return_contribution"] == {
        symbol: asset["return_contribution"] for symbol, asset in report["assets"].items()
    }
    assert analysis["series"]["dates"] == ["2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"]
    assert analysis["series"]["portfolio_index"][0] == 1.0
    assert len(analysis["series"]["portfolio_index"]) == 7
    assert analysis["series"]["asset_index"]["NVDA"][-1] == pytest.approx(1 + report["assets"]["NVDA"]["cumulative_return"])
    assert analysis["observation_count"] == analysis["lookback_days"] == 6
    assert analysis["as_of"] == "2026-09-25T00:00:00Z"
    assert analysis["data_mode"] == "demo"
    assert analysis["data_quality"]["source"] == "synthetic_fixture"
    assert analysis["data_quality"]["freshness"] == "unknown"
    assert set(report["warnings"]) <= set(analysis["data_quality"]["warnings"])
    assert set(report["metadata"]["assumptions"]) <= set(analysis["assumptions"])
    assert client.get(f"/api/v1/portfolios/{portfolio_id}/analyses/{analysis['analysis_id']}").json() == analysis
    answer = client.post(f"/api/v1/portfolios/{portfolio_id}/ask", json={
        "analysis_id": analysis["analysis_id"], "question": "Explain this snapshot",
    })
    assert answer.status_code == 200
    assert answer.json()["metrics"]["portfolio_return"] == analysis["portfolio_return"]
    assert client.get("/health").json()["quant_integration"] == "quant_engine_sample_prices"


@pytest.mark.parametrize("weights", [
    {"NVDA": 0.24, "MSFT": 0.20, "AAPL": 0.16, "JPM": 0.12, "VTI": 0.18, "TLT": 0.10},
    {"AMD": 0.5, "GLD": 0.5},
])
def test_frontend_portfolios_have_sample_prices(client, weights):
    portfolio_id = create(client, weights)
    response = client.post(f"/api/v1/portfolios/{portfolio_id}/analysis")
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert analysis["portfolio_id"] == portfolio_id
    assert analysis["weights"] == weights
    assert analysis["data_mode"] == "demo"
    assert analysis["observation_count"] == 6


def test_what_if_union_and_deltas_use_saved_baseline_without_mutation(client):
    portfolio_id = create(client, {"NVDA": 1.0})
    before = client.get(f"/api/v1/portfolios/{portfolio_id}").json()
    expected = compare_portfolios(SamplePriceProvider().prices(["NVDA", "TLT"]),
                                 {"NVDA": 1.0, "TLT": 0.0}, {"NVDA": 0.0, "TLT": 1.0})
    response = client.post(f"/api/v1/portfolios/{portfolio_id}/what-if", json={
        "holdings": [{"symbol": "TLT", "weight": 1.0}],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    for field, source in [("current_analysis", "baseline"), ("proposed_analysis", "proposed")]:
        assert result[field] == map_quant_report(expected[source], portfolio_id).model_dump(mode="json")
    assert result["delta"] == {
        "portfolio_return": expected["portfolio_metric_differences"]["cumulative_return"],
        "portfolio_volatility": expected["portfolio_metric_differences"]["annualized_volatility"],
        "annualized_return": expected["portfolio_metric_differences"]["geometric_annualized_return"],
        "max_drawdown": (expected["proposed"]["portfolio"]["maximum_drawdown"]
                         - expected["baseline"]["portfolio"]["maximum_drawdown"]),
    }
    assert client.get(f"/api/v1/portfolios/{portfolio_id}").json() == before
    legacy = client.post("/api/what-if", json={
        "portfolio_id": portfolio_id, "proposed_weights": {"TLT": 1.0},
    })
    assert legacy.status_code == 200
    assert legacy.json() == result


def test_undefined_metrics_and_warnings_survive_storage_and_citations(client):
    class ConstantPrices:
        def prices(self, symbols):
            return pd.DataFrame({symbol: [100.0] * 4 for symbol in symbols},
                                index=pd.date_range("2026-09-21", periods=4, tz="UTC"))

    provider = EngineQuantProvider(client.app.state.store, ConstantPrices())
    client.app.dependency_overrides[get_provider] = lambda: provider
    portfolio_id = create(client, {"NVDA": 1.0})
    response = client.post(f"/api/v1/portfolios/{portfolio_id}/analysis")
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert analysis["risk_contribution"] == {"NVDA": None}
    assert analysis["correlation_matrix"] == {"NVDA": {"NVDA": None}}
    saved, _ = client.app.state.store.get_analysis(portfolio_id, analysis["analysis_id"])
    assert saved.notes == analysis["data_quality"]["warnings"]
    assert any("undefined" in warning for warning in saved.notes)
    assert "risk_contribution.NVDA" not in metric_catalog(saved)
    json.dumps(saved.model_dump(mode="json"), allow_nan=False)
    answer = client.post(f"/api/v1/portfolios/{portfolio_id}/ask", json={
        "analysis_id": analysis["analysis_id"], "question": "Explain risk",
    })
    assert answer.status_code == 200
    assert answer.json()["citations"] == []


def test_correlation_roundoff_is_preserved_but_invalid_values_rejected():
    report = analyze_portfolio(SamplePriceProvider().prices(["NVDA"]), {"NVDA": 1.0})
    report["matrices"]["correlation"]["NVDA"]["NVDA"] = 1.0000000000000002
    mapped = map_quant_report(report, "test")
    assert mapped.correlation_matrix["NVDA"]["NVDA"] == 1.0000000000000002
    payload = mapped.model_dump()
    payload["correlation_matrix"]["NVDA"]["NVDA"] = 1.001
    with pytest.raises(ValidationError):
        AnalyticsSnapshot.model_validate(payload)


def test_weight_tolerance_matches_engine_without_normalization(client):
    holdings = [{"symbol": "NVDA", "weight": 0.5}, {"symbol": "TLT", "weight": 0.5000005}]
    assert client.post("/api/v1/portfolios", json={"name": "Invalid", "holdings": holdings}).status_code == 422
    assert client.post("/api/v1/portfolios/demo/what-if", json={"holdings": holdings}).status_code == 422
    weights = {"NVDA": 0.5, "TLT": 0.50000000005}
    portfolio_id = create(client, weights)
    response = client.post(f"/api/v1/portfolios/{portfolio_id}/analysis")
    assert response.status_code == 200
    assert response.json()["weights"] == weights


def test_missing_sample_history_fails_instead_of_fabricating_prices(client):
    portfolio_id = create(client, {"UNKNOWN": 1.0})
    assert client.post(f"/api/v1/portfolios/{portfolio_id}/analysis").status_code == 502
    response = client.post("/api/v1/portfolios/demo/what-if", json={
        "holdings": [{"symbol": "UNKNOWN", "weight": 1.0}],
    })
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


def test_market_history_is_aligned_limited_and_explicitly_demo(client):
    response = client.get("/api/v1/market-history", params={"symbols": ["nvda", "VTI"], "lookback_days": 2})
    assert response.status_code == 200, response.text
    history = response.json()
    assert history["symbols"] == ["NVDA", "VTI"]
    assert history["dates"] == ["2026-09-23", "2026-09-24", "2026-09-25"]
    assert history["asset_index"]["NVDA"][0] == history["asset_index"]["VTI"][0] == 1.0
    assert all(len(values) == len(history["dates"]) for values in history["asset_index"].values())
    assert history["requested_lookback_days"] == 2
    assert history["observation_count"] == 2
    assert history["data_mode"] == "demo"
    assert history["data_source"] == "synthetic_fixture"
    assert history["freshness"] == "unknown"
    assert "FICTIONAL" in history["warnings"][0]


def test_market_history_rejects_unsupported_and_malformed_requests(client):
    unsupported = client.get("/api/v1/market-history", params={"symbols": ["UNKNOWN"]})
    assert unsupported.status_code == 404
    assert unsupported.json()["error"]["code"] == "MARKET_HISTORY_UNAVAILABLE"
    duplicate = client.get("/api/v1/market-history", params={"symbols": ["nvda", "NVDA"]})
    assert duplicate.status_code == 422


def test_short_market_history_returns_available_rows_without_extrapolation(client):
    response = client.get("/api/v1/market-history", params={"symbols": ["GLD"], "lookback_days": 252})
    assert response.status_code == 200
    history = response.json()
    assert history["observation_count"] == 6
    assert len(history["dates"]) == 7
