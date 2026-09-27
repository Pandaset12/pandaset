import mongomock
from datetime import date, timedelta

from backend.migrations.backfill_event_context import backfill_records


def test_backfill_is_dry_run_idempotent_and_owner_scoped():
    db = mongomock.MongoClient()["migration"]
    dates = [(date(2025, 1, 1) + timedelta(days=index)).isoformat() for index in range(127)]
    context = {
        "allocation_snapshot": {"name": "Core", "revision": 1, "holdings": [{"symbol": "SPY", "weight": 1.0}]},
        "price_snapshot": {"dates": dates, "holding_prices": {"SPY": [100.0] * 127},
                           "factor_prices": {symbol: [100.0] * 127 for symbol in ("SPY", "TLT", "GLD")}},
        "metrics": {"weights": {"SPY": 1.0}, "data_mode": "live", "observation_count": 126},
        "model_version": "event-v1",
    }
    result = {"cases": [{"case": case, "horizon": horizon,
                         **{side: {"estimated_return": 0.01} for side in ("current", "proposed", "delta")}}
                        for case in ("mild", "central", "severe") for horizon in ("1m", "3m")]}
    db.analyses.insert_one({"_id": "analysis-a", "owner_id": "owner-a", "portfolio_id": "portfolio-a", **context})
    db.scenario_drafts.insert_many([
        {"_id": "draft-a", "owner_id": "owner-a", "portfolio_id": "portfolio-a", "status": "ready",
         "request": {"analysis_id": "analysis-a", "template_id": "fed_policy"}},
        {"_id": "draft-b", "owner_id": "owner-b", "portfolio_id": "portfolio-a", "status": "ready",
         "request": {"analysis_id": "analysis-a"}},
        {"_id": "draft-active", "owner_id": "owner-a", "portfolio_id": "portfolio-a", "status": "running",
         "request": {"analysis_id": "analysis-a"}},
    ])
    db.scenario_runs.insert_many([
        {"_id": "run-a", "owner_id": "owner-a", "portfolio_id": "portfolio-a", "status": "completed",
         "analysis_id": "analysis-a", "result": result},
        {"_id": "run-b", "owner_id": "owner-b", "portfolio_id": "portfolio-a", "status": "completed",
         "analysis_id": "analysis-a", "result": result},
    ])
    preview = backfill_records(db)
    assert preview["candidate_drafts"] == preview["candidate_runs"] == 1
    assert preview["active_drafts_to_drain"] == 1
    assert preview["unresolved_drafts"] == preview["unresolved_runs"] == 1
    assert "context" not in db.scenario_drafts.find_one({"_id": "draft-a"})
    assert backfill_records(db, apply=True)["pinned_drafts"] == 1
    assert db.scenario_drafts.find_one({"_id": "draft-a"})["context"]["allocation_snapshot"]["name"] == "Core"
    assert "analysis_id" not in db.scenario_drafts.find_one({"_id": "draft-a"})["request"]
    assert db.scenario_runs.find_one({"_id": "run-a"})["result"] == result
    assert backfill_records(db, apply=True)["verified_completed_results"] == 1
    again = backfill_records(db, apply=True)
    assert again["already_pinned_drafts"] == again["already_pinned_runs"] == 1
    assert again["pinned_drafts"] == again["pinned_runs"] == 0
