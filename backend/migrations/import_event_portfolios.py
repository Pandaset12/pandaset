"""Import event-only portfolios into the main owner-scoped SQLite store.

Dry run by default. Pass --apply after reviewing the read-only inventory and
backing up both stores. Existing IDs are never overwritten.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from backend.schemas import Portfolio
from backend.storage import PortfolioImportConflict, PortfolioStore


class ReadOnlyImportStore:
    def __init__(self, path: Path):
        self.path = path

    def inspect_import(self, portfolio: Portfolio, owner_id: str) -> str:
        with sqlite3.connect(f"file:{self.path}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "SELECT payload, owner_id FROM portfolios WHERE portfolio_id = ?",
                (portfolio.portfolio_id,),
            ).fetchone()
        return PortfolioStore._import_state(row, portfolio, owner_id)


def import_records(store: PortfolioStore, records: Iterable[dict[str, Any]], *, apply: bool = False) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        owner_id = record.get("owner_id")
        if not isinstance(owner_id, str) or not owner_id.strip() or record.get("deleted_at"):
            counts["skipped_unowned_or_deleted"] += 1
            continue
        try:
            portfolio = Portfolio.model_validate(record["payload"])
            if portfolio.portfolio_id != record.get("_id"):
                raise ValueError("Portfolio payload ID differs from document ID.")
        except (KeyError, ValueError):
            counts["invalid_source"] += 1
            continue
        state = store.inspect_import(portfolio, owner_id)
        if state != "candidate" or not apply:
            counts[state] += 1
            continue
        try:
            counts[store.import_existing(portfolio, owner_id)] += 1
        except PortfolioImportConflict as exc:
            # Another process may have inserted the ID after inspection.
            counts[str(exc)] += 1
    return {key: counts[key] for key in (
        "candidate", "imported", "already_imported", "owner_conflict",
        "content_conflict", "invalid_source", "skipped_unowned_or_deleted",
    )}


def main() -> None:
    from pymongo import MongoClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, type=Path)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI"))
    parser.add_argument("--mongo-db", default=os.getenv("MONGODB_DATABASE", "portfoliolens"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.mongo_uri:
        parser.error("--mongo-uri or MONGODB_URI is required")
    store = PortfolioStore(args.sqlite) if args.apply else ReadOnlyImportStore(args.sqlite)
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        report = import_records(store, client[args.mongo_db]["portfolios"].find({}), apply=args.apply)
    print(json.dumps({"mode": "apply" if args.apply else "dry_run", **report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
