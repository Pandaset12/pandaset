from backend.migrations.unified_inventory import inventory_records


def portfolio(record_id, owner, name="Core", weight=1.0):
    return {
        "_id": record_id,
        "owner_id": owner,
        "payload": {"name": name, "holdings": [{"symbol": "SPY", "weight": weight}]},
    }


def test_inventory_is_read_only_and_counts_conflicts_and_dangling_references():
    main = [{"portfolio_id": "existing", "owner_id": "owner-a", "payload": portfolio("existing", "owner-a")["payload"]}]
    events = [
        portfolio("existing", "owner-a"),
        portfolio("new", "owner-a"),
        portfolio("existing", "owner-b"),
        portfolio("existing", "owner-a", name="Changed"),
    ]
    analyses = [{"_id": "analysis-a", "owner_id": "owner-a", "portfolio_id": "existing"}]
    drafts = [
        {"owner_id": "owner-a", "portfolio_id": "existing", "status": "pending", "request": {"analysis_id": "analysis-a"}},
        {"owner_id": "owner-b", "portfolio_id": "existing", "status": "ready", "request": {"analysis_id": "analysis-a"}},
    ]
    runs = [{"owner_id": "owner-a", "portfolio_id": "existing", "analysis_id": "gone", "status": "completed"}]
    report = inventory_records(main, events, analyses, drafts, runs)
    assert report["portfolio_import_candidates"] == 1
    assert report["already_imported"] == 1
    assert report["cross_owner_id_conflicts"] == 1
    assert report["allocation_or_name_conflicts"] == 1
    assert report["active_drafts"] == 1
    assert report["drafts_with_missing_or_foreign_analysis"] == 1
    assert report["runs_with_missing_or_foreign_analysis"] == 1
    assert events[0]["payload"]["name"] == "Core"
