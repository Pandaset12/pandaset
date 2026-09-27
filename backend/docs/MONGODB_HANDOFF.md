# MongoDB handoff

## Recovered work and current status

The earlier data-layer work stopped at the initial provider/schema draft.
Its design proposed `mongo_store.py` for users/holdings, and its dependency file
listed `pymongo`. No MongoDB adapter implementation was found in the earlier
conversation, workspace files or repository history.

The recovered Python modules in `backend/drafts/` remain inactive. Current main
now separately implements `backend/mongo_store.py` for the gated v2 event lab:
owner-scoped portfolios, immutable analyses, drafts/runs, jobs, and run chat.
V2 requires configured MongoDB and verifies identity through Supabase. See
[the v2 contract](../../docs/event-lab-api-contract.md) and
[release gates](../../docs/event-lab-release-gates.md).

V1 still uses `backend/storage.py` (SQLite). Enabling v2 does not migrate v1
records or make its Mongo API a drop-in replacement for the SQLite store.

## Requirements if the team migrates v1 storage

Preserve the behavior of `backend/storage.py` if adding shared storage to v1:

- `seed_demo(metrics)`: idempotently seed the unassigned legacy demo portfolio.
- `create(PortfolioInput, owner_id) -> Portfolio`: save an owned portfolio.
- `get(portfolio_id, owner_id) -> Portfolio | None`.
- `list_for_owner(owner_id) -> list[Portfolio]`.
- `update(portfolio_id, owner_id, PortfolioInput) -> Portfolio | None`: preserve
  identity and creation time, and atomically invalidate old analyses on an allocation change.
- `save_analysis(AnalyticsSnapshot, owner_id) -> (analysis_id, created_at)`:
  atomically verify ownership/current weights and save an immutable snapshot;
  raise `StalePortfolio` when the portfolio has changed. Questions never recalculate it.
- `get_analysis(portfolio_id, analysis_id) -> (AnalyticsSnapshot, created_at)`:
  require both IDs and report missing/mismatched snapshots consistently.

The API verifies portfolio ownership before snapshot reads. A replacement store
must preserve that boundary and the atomic update/save behavior, including under
concurrent requests. Legacy unowned records must not be assigned to arbitrary users.

Suggested collections are `portfolios` and `analyses`, using stable string IDs
and a lookup index on portfolio/analysis IDs. Keep the source, market timestamp,
observed period, assumptions and warnings with every snapshot. Return validated
API models rather than raw database documents.

Historical prices remain the data teammate's Tiger Data responsibility.
MongoDB storage does not supply price history or implement the quant formulas.

## Coordination still needed

1. Decide whether v1 stays on persistent SQLite or should migrate to shared
   storage; coordinate schema/collection use with the implemented v2 store.
2. Preserve the current Supabase-verified user ID and ownership checks; never
   accept an owner ID supplied by a portfolio request body.
3. Provide connection configuration through server-side environment variables;
   never commit actual connection strings, passwords or data exports.
4. Define v1 migration, failure/timeout behavior, and store selection explicitly.
   V2 already selects its Mongo store when the event-lab configuration is ready.
5. Test persistence, snapshot lookup, duplicate handling and unavailable-database
   behavior against a dedicated test database before claiming live integration.

No MongoDB database, collection, credential or deployment was changed in this review.
