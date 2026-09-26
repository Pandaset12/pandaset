import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.config import Settings
from backend.main import create_app
from backend.providers import demo_metrics
from backend.schemas import AnalyticsSnapshot


@pytest.mark.parametrize("changes", [
    {"data_mode": "live"},
    {"asset_volatility": {"NVDA": -0.2}},
    {"asset_volatility": {"NVDA": 0.2}},
    {"correlation_matrix": {"NVDA": {"NVDA": 1.0}}},
    {"risk_contribution": {"NVDA": float("nan"), "SPY": 0.27, "JPM": 0.18, "TLT": 0.14}},
])
def test_inconsistent_provider_values_are_rejected(changes):
    data = demo_metrics().model_dump()
    data.update(changes)
    with pytest.raises(ValidationError):
        AnalyticsSnapshot.model_validate(data)


def test_live_metrics_require_and_accept_explicit_provenance():
    data = demo_metrics().model_dump()
    data.update(data_mode="live", data_as_of="2026-09-25T20:00:00Z",
                observation_count=252, data_source="test-provider")
    metrics = AnalyticsSnapshot.model_validate(data)
    assert metrics.data_as_of.tzinfo is not None
    data["data_as_of"] = "2026-09-25T20:00:00"
    with pytest.raises(ValidationError):
        AnalyticsSnapshot.model_validate(data)


def test_legacy_nan_input_returns_422_instead_of_serialization_500(tmp_path):
    app = create_app(Settings(_env_file=None, storage_path=tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        result = client.post("/api/what-if", content='{"proposed_weights":{"NVDA":NaN}}',
                             headers={"Content-Type": "application/json"})
    assert result.status_code == 422
    assert "input" not in result.json()["detail"][0]
