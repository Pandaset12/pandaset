"""Representative dry-run, cutover, retry, and backup-restore rehearsal."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import shutil

import mongomock

from backend.migrations.backfill_event_context import backfill_records
from backend.migrations.import_event_portfolios import import_records
from backend.migrations.unified_inventory import inventory_records, read_main_portfolios
from backend.mongo_store import MongoPortfolioStore
from backend.schemas import PortfolioInput
from backend.storage import PortfolioStore


def test_unified_cutover_and_rollback_rehearsal(tmp_path: Path):
    main_path = tmp_path / "main.sqlite"
    main = PortfolioStore(main_path)
    original = main.create(PortfolioInput(name="Original", holdings=[{"symbol": "SPY", "weight": 1.0}]), "owner-a")
    backup_path = tmp_path / "main-before.sqlite"
    shutil.copy2(main_path, backup_path)

    db = mongomock.MongoClient()["event-before"]
    legacy_portfolio = {
        "_id": "portfolio-event", "owner_id": "owner-b",
        "payload": {"portfolio_id": "portfolio-event", "name": "Event-only",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "holdings": [{"symbol": "AAPL", "weight": 1.0}]},
    }
    db.portfolios.insert_one(deepcopy(legacy_portfolio))
    dates = [(date(2025, 1, 1) + timedelta(days=index)).isoformat() for index in range(127)]
    db.analyses.insert_one({
        "_id": "analysis-legacy", "owner_id": "owner-b", "portfolio_id": "portfolio-event",
        "allocation_snapshot": {**legacy_portfolio["payload"], "revision": 1},
        "price_snapshot": {"dates": dates, "holding_prices": {"AAPL": [100.0] * 127},
                           "factor_prices": {symbol: [100.0] * 127 for symbol in ("SPY", "TLT", "GLD")},
                           "provenance": {"data_source": "historical-test"}},
        "metrics": {"weights": {"AAPL": 1.0}, "data_mode": "live", "observation_count": 126},
        "model_version": "event-v1",
    })
    db.scenario_drafts.insert_many([
        {"_id": "draft-ready", "owner_id": "owner-b", "portfolio_id": "portfolio-event",
         "status": "ready", "idempotency_key": "legacy-ready", "request": {"analysis_id": "analysis-legacy"}},
        {"_id": "draft-active", "owner_id": "owner-b", "portfolio_id": "portfolio-event",
         "status": "running", "idempotency_key": "legacy-active", "request": {"analysis_id": "analysis-legacy"}},
        {"_id": "draft-unresolved", "owner_id": "owner-b", "portfolio_id": "portfolio-event",
         "status": "ready", "idempotency_key": "legacy-unresolved", "request": {"analysis_id": "missing"}},
    ])
    saved_result = {"cases": [
        {"case": case, "horizon": horizon,
         **{side: {"estimated_return": 0.01} for side in ("current", "proposed", "delta")}}
        for case in ("mild", "central", "severe") for horizon in ("1m", "3m")
    ]}
    db.scenario_runs.insert_one({
        "_id": "run-complete", "owner_id": "owner-b", "portfolio_id": "portfolio-event",
        "draft_id": "draft-ready", "status": "completed", "idempotency_key": "legacy-run",
        "analysis_id": "analysis-legacy",
        "result": deepcopy(saved_result),
    })
    source = list(db.portfolios.find({}))
    inventory = inventory_records(read_main_portfolios(main_path), source,
                                  list(db.analyses.find({})), list(db.scenario_drafts.find({})),
                                  list(db.scenario_runs.find({})))
    assert inventory["portfolio_import_candidates"] == 1
    assert inventory["active_drafts"] == 1
    assert inventory["drafts_with_missing_or_foreign_analysis"] == 1
    assert import_records(main, source)["candidate"] == 1
    assert main.get("portfolio-event", "owner-b") is None
    assert backfill_records(db)["candidate_drafts"] == 1
    assert "context" not in db.scenario_drafts.find_one({"_id": "draft-ready"})

    assert import_records(main, source, apply=True)["imported"] == 1
    applied = backfill_records(db, apply=True)
    assert applied["pinned_drafts"] == applied["pinned_runs"] == 1
    assert applied["verified_completed_results"] == 1
    assert applied["active_drafts_to_drain"] == applied["unresolved_drafts"] == 1
    assert import_records(main, source, apply=True)["already_imported"] == 1
    repeated = backfill_records(db, apply=True)
    assert repeated["already_pinned_drafts"] == repeated["already_pinned_runs"] == 1
    assert repeated["pinned_drafts"] == repeated["pinned_runs"] == 0
    assert db.scenario_runs.find_one({"_id": "run-complete"})["result"] == saved_result
    assert db.analyses.count_documents({}) == 1

    # New readers need only the imported portfolio and saved event context.
    db.analyses.delete_many({})
    event = MongoPortfolioStore(database=db, portfolio_repository=main)
    assert event.get_draft("owner-b", "draft-ready")["context"]["price_snapshot"]["provenance"]["data_source"] == "historical-test"
    assert event.get_run("owner-b", "run-complete")["result"] == saved_result
    assert event.get_run("owner-a", "run-complete") is None

    # A consistent pre-cutover backup can restore the old portfolio state.
    rollback_path = tmp_path / "rollback.sqlite"
    shutil.copy2(backup_path, rollback_path)
    rollback = PortfolioStore(rollback_path)
    assert rollback.get(original.portfolio_id, "owner-a").name == "Original"
    assert rollback.get("portfolio-event", "owner-b") is None
