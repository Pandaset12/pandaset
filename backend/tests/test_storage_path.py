from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.schemas import PortfolioInput
from backend.storage import PortfolioStore


def test_default_storage_path_is_independent_of_worktree(tmp_path, monkeypatch):
    monkeypatch.delenv("STORAGE_PATH", raising=False)
    first = tmp_path / "checkout-one"
    second = tmp_path / "checkout-two"
    first.mkdir()
    second.mkdir()

    monkeypatch.chdir(first)
    first_settings = Settings(_env_file=None)
    monkeypatch.chdir(second)
    second_settings = Settings(_env_file=None)

    expected = Path.home() / ".pandaset" / "portfolios.sqlite3"
    assert first_settings.storage_path == second_settings.storage_path == expected
    assert first_settings.storage_path_source == second_settings.storage_path_source == "default"


def test_explicit_path_keeps_existing_owner_scoped_portfolios(tmp_path, monkeypatch, caplog):
    path = tmp_path / "existing.sqlite3"
    existing = PortfolioStore(path)
    saved = existing.create(
        PortfolioInput(name="Saved", holdings=[{"symbol": "AAPL", "weight": 1.0}]),
        "owner-a",
    )
    monkeypatch.setenv("STORAGE_PATH", str(path))
    settings = Settings(_env_file=None)

    assert settings.storage_path == path
    assert settings.storage_path_source == "override"
    with caplog.at_level("INFO", logger="uvicorn.error"):
        with TestClient(create_app(settings)) as client:
            assert client.get("/health").status_code == 200
            assert str(path) not in client.get("/health").text
    assert f"Portfolio storage: {path} (override)" in caplog.text

    restarted = PortfolioStore(Settings(_env_file=None).storage_path)
    assert [item.portfolio_id for item in restarted.list_for_owner("owner-a")] == [saved.portfolio_id]
    assert restarted.list_for_owner("owner-b") == []
