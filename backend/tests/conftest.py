import pytest
from fastapi.testclient import TestClient

from backend.auth import current_user_id


@pytest.fixture(autouse=True)
def legacy_demo_investor(request, monkeypatch):
    """Keep pre-auth analytics tests focused on their existing behavior."""
    if request.module.__name__.endswith("test_ownership"):
        return
    original_enter = TestClient.__enter__

    def enter(client):
        client.app.dependency_overrides[current_user_id] = lambda: "legacy-test-investor"
        result = original_enter(client)
        with client.app.state.store.connection() as db:
            db.execute("UPDATE portfolios SET owner_id = ? WHERE portfolio_id = 'demo' AND owner_id IS NULL", ("legacy-test-investor",))
        return result

    monkeypatch.setattr(TestClient, "__enter__", enter)
