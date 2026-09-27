# Event Lab API contract

All routes below use `/api/v2` and require a Supabase bearer token. Ownership is derived from the verified token, never accepted from a request body. The feature is disabled until its backend configuration is complete. All errors use `{ "error": { "code", "message", "request_id" } }`.

## Portfolio and evidence

- `GET /portfolios` lists the authenticated user's portfolios.
- `POST /portfolios` accepts `{name, holdings:[{symbol,weight}]}`; at most 25 unique supported symbols and weights summing to one.
- `GET /portfolios/{id}` and `DELETE /portfolios/{id}` are owner scoped.
- `POST /portfolios/{id}/analysis` stores an immutable allocation and adjusted-price snapshot with provenance and returns its analysis ID. A new call creates a new snapshot.
- `GET /portfolios/{id}/analyses?limit=10` lists the owner's saved analyses newest first so saved runs remain browsable when the market-data vendor is unavailable.
- `GET /portfolios/{id}/analyses/{analysis_id}` reads that immutable snapshot.
- `GET /instruments?q=...` searches the approved universe. `GET /events/templates` lists versioned macro, sector, and issuer templates.

## Scenario lifecycle

- `POST /scenarios/drafts` accepts `{portfolio_id, analysis_id, template_id, question?}` and an `Idempotency-Key` header. Returns `202 {draft_id,status}`. A duplicate key scoped to the same owner and request body returns the same draft; conflicting reuse returns 409.
- `GET /scenarios/drafts/{id}` returns status, sourced facts and missing evidence, all proposed factor and issuer shocks with units, validation errors, and cancellation state.
- `POST /scenarios/drafts/{id}/confirm` accepts the draft revision and user-confirmed `{mild,central,severe}` shocks, each with `1m` and `3m`. Returns `202 {run_id,status}`. The server validates supported factors, bounds, and coverage before creating a run.
- `GET /scenarios/runs/{id}` returns progress or immutable results: sourced facts, confirmed assumptions, deterministic cases, conditional ranges or an omission reason, coverage, model version, and price snapshot provenance.
- `POST /scenarios/drafts/{id}/cancel` and `POST /scenarios/runs/{id}/cancel` stop queued work or mark active work cancelled.
- `DELETE /scenarios/drafts/{id}` and `DELETE /scenarios/runs/{id}` remove owner-owned records; run deletion removes its chat.
- `GET /scenarios/runs/{id}/messages` and `POST /scenarios/runs/{id}/messages` read/write saved run chat. A request to change weights or shocks returns a new draft requiring review, never mutates the saved run.

The job store holds queued/running/completed/failed/cancelled states, attempt count, lease, idempotency key, and timestamps. Workers claim jobs atomically, retry transient failures within a fixed bound, and resume expired leases after restart. Per-user active jobs and message counts are capped.
