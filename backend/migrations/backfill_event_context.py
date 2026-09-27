"""Pin legacy event drafts and runs before retiring standalone analyses.

Dry run by default. Back up MongoDB and drain running jobs before --apply.
The script does not delete analysis records or completed results.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from typing import Any


REQUIRED = ("allocation_snapshot", "price_snapshot", "analysis_snapshot", "model_version", "proposed_weights")


def _complete(context: dict[str, Any]) -> bool:
    return all(context.get(field) for field in REQUIRED)


def _valid_context(context: dict[str, Any]) -> bool:
    if not _complete(context) or not isinstance(context.get("portfolio_revision"), int):
        return False
    prices = context["price_snapshot"]
    metrics = context["analysis_snapshot"]
    allocation = context["allocation_snapshot"]
    dates = prices.get("dates") or []
    holdings = prices.get("holding_prices") or {}
    factors = prices.get("factor_prices") or {}
    symbols = {item.get("symbol") for item in allocation.get("holdings", [])}
    proposed = set(context["proposed_weights"])
    if (metrics.get("data_mode") != "live" or len(dates) < 127
            or len(dates) != metrics.get("observation_count", -1) + 1
            or dates != sorted(set(dates))
            or set(holdings) != symbols | proposed
            or set(factors) != {"SPY", "TLT", "GLD"}):
        return False
    return all(len(series) == len(dates) and all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and value > 0 for value in series
    ) for series in [*holdings.values(), *factors.values()])


def _valid_completed_result(result: dict[str, Any] | None) -> bool:
    cases = (result or {}).get("cases")
    if not isinstance(cases, list) or len(cases) != 6:
        return False
    expected = {(case, horizon) for case in ("mild", "central", "severe")
                for horizon in ("1m", "3m")}
    return {(item.get("case"), item.get("horizon")) for item in cases
            if isinstance(item, dict)} == expected and all(
        isinstance(item.get(side), dict)
        and isinstance(item[side].get("estimated_return"), (int, float))
        and math.isfinite(item[side]["estimated_return"])
        for item in cases for side in ("current", "proposed", "delta")
    )


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _analysis_for(db, record: dict[str, Any], analysis_id: str | None) -> dict[str, Any] | None:
    if not analysis_id:
        return None
    return db["analyses"].find_one({"_id": analysis_id, "owner_id": record["owner_id"],
                                    "portfolio_id": record["portfolio_id"]})


def backfill_records(db, *, apply: bool = False) -> dict[str, int]:
    """Return aggregate outcomes; only conditional owner-scoped updates are written."""
    counts: Counter[str] = Counter()
    drafts = db["scenario_drafts"]
    runs = db["scenario_runs"]
    for draft in drafts.find({"deleted_at": {"$exists": False}}):
        if not draft.get("owner_id") or not draft.get("portfolio_id"):
            counts["invalid_drafts"] += 1
            continue
        if _valid_context(draft.get("context") or {}):
            counts["already_pinned_drafts"] += 1
            continue
        if draft.get("status") in {"initializing", "pending", "queued", "running"}:
            counts["active_drafts_to_drain"] += 1
            continue
        analysis = _analysis_for(db, draft, (draft.get("request") or {}).get("analysis_id"))
        if not analysis:
            counts["unresolved_drafts"] += 1
            continue
        context = {
            "portfolio_revision": (analysis.get("allocation_snapshot") or {}).get("revision"),
            "allocation_snapshot": deepcopy(analysis.get("allocation_snapshot")),
            "price_snapshot": deepcopy(analysis.get("price_snapshot")),
            "analysis_snapshot": deepcopy(analysis.get("metrics")),
            "model_version": analysis.get("model_version"),
            "proposed_weights": deepcopy((draft.get("request") or {}).get("proposed_weights")
                                         or (analysis.get("metrics") or {}).get("weights")),
        }
        if not _valid_context(context):
            counts["unresolved_drafts"] += 1
            continue
        counts["candidate_drafts"] += 1
        if apply:
            guard = {"_id": draft["_id"], "owner_id": draft["owner_id"],
                     "status": draft.get("status"), "deleted_at": {"$exists": False}}
            guard["context"] = draft["context"] if "context" in draft else {"$exists": False}
            result = drafts.update_one(guard,
                                       {"$set": {"context": context},
                                        "$unset": {"request.analysis_id": ""}})
            counts["pinned_drafts" if result.modified_count else "concurrent_drafts"] += 1

    for run in runs.find({"deleted_at": {"$exists": False}}):
        if not run.get("owner_id") or not run.get("portfolio_id"):
            counts["invalid_runs"] += 1
            continue
        if run.get("status") in {"initializing", "pending", "queued", "running"}:
            counts["active_runs_to_drain"] += 1
            continue
        if run.get("status") == "completed" and not _valid_completed_result(run.get("result")):
            counts["invalid_completed_results"] += 1
            continue
        result_fingerprint = _fingerprint(run.get("result")) if run.get("status") == "completed" else None
        if _valid_context(run):
            counts["already_pinned_runs"] += 1
            if result_fingerprint:
                counts["verified_completed_results"] += 1
            continue
        analysis = _analysis_for(db, run, run.get("analysis_id"))
        if not analysis:
            counts["unresolved_runs"] += 1
            continue
        context = {
            "portfolio_revision": (analysis.get("allocation_snapshot") or {}).get("revision"),
            "allocation_snapshot": deepcopy(analysis.get("allocation_snapshot")),
            "price_snapshot": deepcopy(analysis.get("price_snapshot")),
            "analysis_snapshot": deepcopy(analysis.get("metrics")),
            "model_version": analysis.get("model_version"),
            "proposed_weights": deepcopy(run.get("proposed_weights")
                                         or (analysis.get("metrics") or {}).get("weights")),
        }
        if not _valid_context(context):
            counts["unresolved_runs"] += 1
            continue
        counts["candidate_runs"] += 1
        if apply:
            guard = {"_id": run["_id"], "owner_id": run["owner_id"],
                     "status": run.get("status"), "deleted_at": {"$exists": False}}
            guard["allocation_snapshot"] = (run["allocation_snapshot"] if "allocation_snapshot" in run
                                            else {"$exists": False})
            result = runs.update_one(guard,
                                     {"$set": context})
            counts["pinned_runs" if result.modified_count else "concurrent_runs"] += 1
            if result_fingerprint and result.modified_count:
                saved = runs.find_one({"_id": run["_id"], "owner_id": run["owner_id"]})
                if saved and _fingerprint(saved.get("result")) == result_fingerprint:
                    counts["verified_completed_results"] += 1
                else:
                    counts["result_mismatches"] += 1
    return {key: counts[key] for key in (
        "candidate_drafts", "pinned_drafts", "already_pinned_drafts", "active_drafts_to_drain",
        "unresolved_drafts", "invalid_drafts", "concurrent_drafts", "candidate_runs",
        "pinned_runs", "already_pinned_runs", "active_runs_to_drain", "unresolved_runs",
        "invalid_runs", "invalid_completed_results", "concurrent_runs",
        "verified_completed_results", "result_mismatches",
    )}


def main() -> None:
    from pymongo import MongoClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI"))
    parser.add_argument("--mongo-db", default=os.getenv("MONGODB_DATABASE", "portfoliolens"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.mongo_uri:
        parser.error("--mongo-uri or MONGODB_URI is required")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        report = backfill_records(client[args.mongo_db], apply=args.apply)
    print(json.dumps({"mode": "apply" if args.apply else "dry_run", **report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
