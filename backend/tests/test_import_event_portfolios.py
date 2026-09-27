from datetime import datetime, timezone

import mongomock

from backend.migrations.import_event_portfolios import import_records
from backend.schemas import PortfolioInput
from backend.storage import PortfolioStore
from backend.mongo_store import MongoPortfolioStore


def source(record_id="portfolio-event", owner="owner-a", symbols=("SPY",), name="Event portfolio"):
    return {
        "_id": record_id,
        "owner_id": owner,
        "payload": {
            "portfolio_id": record_id,
            "name": name,
            "holdings": [{"symbol": symbol, "weight": 1 / len(symbols)} for symbol in symbols],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def test_import_preserves_owner_id_and_25_holding_legacy_portfolio(tmp_path):
    store = PortfolioStore(tmp_path / "portfolios.sqlite")
    symbols = tuple(f"S{i}" for i in range(25))
    record = source(symbols=symbols)
    assert import_records(store, [record]) == {
        "candidate": 1, "imported": 0, "already_imported": 0,
        "owner_conflict": 0, "content_conflict": 0, "invalid_source": 0,
        "skipped_unowned_or_deleted": 0,
    }
    assert store.get(record["_id"], record["owner_id"]) is None
    assert import_records(store, [record], apply=True)["imported"] == 1
    assert len(store.get(record["_id"], record["owner_id"]).holdings) == 25
    assert store.get(record["_id"], "owner-b") is None
    assert import_records(store, [record], apply=True)["already_imported"] == 1
    assert len(store.list_for_owner("owner-a")) == 1


def test_import_does_not_overwrite_different_owner_or_allocation(tmp_path):
    store = PortfolioStore(tmp_path / "portfolios.sqlite")
    existing = store.create(PortfolioInput(name="Main", holdings=[{"symbol": "SPY", "weight": 1.0}]), "owner-a")
    foreign = source(record_id=existing.portfolio_id, owner="owner-b")
    changed = source(record_id=existing.portfolio_id, owner="owner-a", name="Changed")
    assert import_records(store, [foreign, changed], apply=True)["owner_conflict"] == 1
    assert import_records(store, [changed], apply=True)["content_conflict"] == 1
    assert store.get(existing.portfolio_id, "owner-a").name == "Main"


def test_import_rejects_payload_id_mismatch(tmp_path):
    store = PortfolioStore(tmp_path / "portfolios.sqlite")
    record = source()
    record["payload"]["portfolio_id"] = "different"
    assert import_records(store, [record], apply=True)["invalid_source"] == 1


def test_shared_event_lookup_obeys_main_owner_and_revision(tmp_path):
    main = PortfolioStore(tmp_path / "portfolios.sqlite")
    first = main.create(PortfolioInput(name="Original", holdings=[{"symbol": "SPY", "weight": 1.0}]), "owner-a")
    event = MongoPortfolioStore(database=mongomock.MongoClient()["test"], portfolio_repository=main)
    assert [item.portfolio_id for item in event.list_portfolios("owner-a")] == [first.portfolio_id]
    assert event.get_portfolio("owner-b", first.portfolio_id) is None
    assert event.get_portfolio("owner-a", first.portfolio_id).revision == 1
    updated = main.update(first.portfolio_id, "owner-a", PortfolioInput(name="Updated", holdings=[{"symbol": "SPY", "weight": 1.0}]))
    assert updated.revision == 2
    assert event.get_portfolio("owner-a", first.portfolio_id).name == "Updated"
    assert event.get_portfolio("owner-a", first.portfolio_id).revision == 2
