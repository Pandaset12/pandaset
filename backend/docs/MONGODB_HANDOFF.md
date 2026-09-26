# MongoDB handoff

## Recovered work and current status

The earlier data-layer work stopped at the initial provider/schema draft.
Its design proposed `mongo_store.py` for users/holdings, and its dependency file
listed `pymongo`. No MongoDB adapter implementation was found in the earlier
conversation, workspace files or repository history.

The recovered files are in `backend/drafts/` and are explicitly inactive.
The working API currently persists portfolios and analysis snapshots with
SQLite. Restoring the drafts does not configure or connect MongoDB.

## Interface to implement with Backend #1

Preserve the behavior of `backend/storage.py` when adding the shared store:

- `seed_demo(metrics)`: idempotently seed the labeled demo portfolio.
- `create(PortfolioInput) -> Portfolio`: save a portfolio and return its ID.
- `get(portfolio_id) -> Portfolio | None`.
- `save_analysis(AnalyticsSnapshot) -> (analysis_id, created_at)`: save an
  immutable snapshot; questions must not overwrite or recalculate it.
- `get_analysis(portfolio_id, analysis_id) -> (AnalyticsSnapshot, created_at)`:
  require both IDs and report missing/mismatched snapshots consistently.

Suggested collections are `portfolios` and `analyses`, using stable string IDs
and a lookup index on portfolio/analysis IDs. Keep the source, market timestamp,
observed period, assumptions and warnings with every snapshot. Return validated
API models rather than raw database documents.

Historical prices remain the data teammate's Tiger Data responsibility.
MongoDB storage does not supply price history or implement the quant formulas.

## Coordination still needed

1. Confirm the collection schema, database name and owner of the MongoDB adapter.
2. Agree on user identity/ownership checks if login is in scope. The current
   starter has no authentication and must not imply multi-user access control.
3. Provide connection configuration through server-side environment variables;
   never commit actual connection strings, passwords or data exports.
4. Decide the failure/timeout behavior and when the API should select the shared
   store instead of local SQLite.
5. Test persistence, snapshot lookup, duplicate handling and unavailable-database
   behavior against a dedicated test database before claiming live integration.

No MongoDB database, collection, credential or deployment was changed in this review.
