"""Read-only inventory for unifying main and event portfolios.

Run with ``python -m backend.migrations.unified_inventory --sqlite PATH --mongo-uri URI``.
The command performs only SQLite SELECT and Mongo find operations. Do not put
credentials in command history on a shared host; an environment variable is
accepted as the default Mongo URI.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable


def _allocation(payload: dict[str, Any]) -> tuple[str, tuple[tuple[str, float], ...]]:
    holdings = payload.get("holdings") or []
    return (
        str(payload.get("name", "")).strip(),
        tuple(sorted((str(item["symbol"]).upper(), float(item["weight"])) for item in holdings)),
    )


def inventory_records(
    main_portfolios: Iterable[dict[str, Any]],
    event_portfolios: Iterable[dict[str, Any]],
    analyses: Iterable[dict[str, Any]],
    drafts: Iterable[dict[str, Any]],
    runs: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Count migration states without exposing owner identifiers or editing records."""
    counts: Counter[str] = Counter()
    main = {item["portfolio_id"]: item for item in main_portfolios if item.get("owner_id")}
    events = [item for item in event_portfolios if item.get("owner_id") and not item.get("deleted_at")]
    analysis_by_id = {item["_id"]: item for item in analyses if item.get("owner_id")}
    counts["main_owned_portfolios"] = len(main)
    counts["event_owned_portfolios"] = len(events)

    for event in events:
        payload = event.get("payload") or {}
        existing = main.get(event["_id"])
        if len(payload.get("holdings") or []) > 8:
            counts["over_main_symbol_limit"] += 1
        if existing is None:
            counts["portfolio_import_candidates"] += 1
        elif existing["owner_id"] != event["owner_id"]:
            counts["cross_owner_id_conflicts"] += 1
        elif _allocation(existing["payload"]) != _allocation(payload):
            counts["allocation_or_name_conflicts"] += 1
        else:
            counts["already_imported"] += 1

    for kind, records in (("draft", drafts), ("run", runs)):
        for item in records:
            if not item.get("owner_id") or item.get("deleted_at"):
                continue
            counts[f"{kind}s"] += 1
            if item.get("status") in {"initializing", "pending", "running"}:
                counts[f"active_{kind}s"] += 1
            analysis_id = (item.get("request") or {}).get("analysis_id") if kind == "draft" else item.get("analysis_id")
            if not analysis_id:
                counts[f"{kind}s_without_analysis_id"] += 1
                continue
            analysis = analysis_by_id.get(analysis_id)
            if analysis is None or analysis.get("owner_id") != item["owner_id"] or analysis.get("portfolio_id") != item.get("portfolio_id"):
                counts[f"{kind}s_with_missing_or_foreign_analysis"] += 1
            if kind == "run" and all(item.get(field) for field in ("allocation_snapshot", "price_snapshot", "analysis_snapshot", "model_version")):
                counts["runs_with_pinned_context"] += 1

    return {key: counts[key] for key in (
        "main_owned_portfolios", "event_owned_portfolios", "portfolio_import_candidates",
        "already_imported", "cross_owner_id_conflicts", "allocation_or_name_conflicts",
        "over_main_symbol_limit", "drafts", "active_drafts", "drafts_without_analysis_id",
        "drafts_with_missing_or_foreign_analysis", "runs", "active_runs",
        "runs_without_analysis_id", "runs_with_missing_or_foreign_analysis",
        "runs_with_pinned_context",
    )}


def read_main_portfolios(path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT portfolio_id, owner_id, payload FROM portfolios WHERE owner_id IS NOT NULL").fetchall()
    return [{"portfolio_id": row[0], "owner_id": row[1], "payload": json.loads(row[2])} for row in rows]


def main() -> None:
    from pymongo import MongoClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI"))
    parser.add_argument("--mongo-db", default=os.getenv("MONGODB_DATABASE", "portfoliolens"))
    args = parser.parse_args()
    if not args.mongo_uri:
        parser.error("--mongo-uri or MONGODB_URI is required")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        db = client[args.mongo_db]
        report = inventory_records(
            read_main_portfolios(args.sqlite),
            db["portfolios"].find({}), db["analyses"].find({}),
            db["scenario_drafts"].find({}), db["scenario_runs"].find({}),
        )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
