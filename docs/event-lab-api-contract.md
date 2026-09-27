# Event research API contract

All routes use `/api/v2`, require a Supabase bearer token, and derive ownership from the verified token. The optional event service needs configured MongoDB, adjusted Alpaca history, and its existing access and provider-rights gates. Errors use `{ "error": { "code", "message", "request_id" } }`. The main `/api/v1/portfolios` store remains authoritative for portfolio identity and edits.

## Portfolio and templates

- `GET /portfolios` lists the caller's portfolios from the main owner-scoped repository. It is read-only; create and edit through `/api/v1/portfolios`.
- `GET /instruments?q=...` searches the approved universe.
- `GET /events/templates?portfolio_id=...&proposed_symbol=...` lists eligible templates and issuer targets across the current/proposed symbol union. Event research accepts at most eight distinct symbols.

## Drafts and runs

- `POST /scenarios/drafts` accepts `{portfolio_id, portfolio_revision, template_id, situation_id?, target_symbol?, description?, question?, proposed_weights?}` plus an optional `Idempotency-Key`. The backend verifies the main portfolio owner and revision, aligns current/proposed holding and factor price histories, checks coverage, and saves the exact allocation, price, provenance, and model context in the draft. It returns `202 {draft_id,status}`. An identical key and request returns the original pinned draft even if later prices change; conflicting reuse returns 409.
- `GET /scenarios/drafts?portfolio_id=...` and `GET /scenarios/drafts/{id}` return owner-scoped status, pinned allocation/revision and price window, sourced facts, missing evidence, proposed shocks and units, and confirmation state. They do not expose analysis IDs.
- `POST /scenarios/drafts/{id}/confirm` accepts the draft revision and reviewed mild/central/severe shocks for `1m` and `3m`. It validates factor and issuer bounds and creates or returns one run pinned to the draft's inputs.
- `GET /scenarios/runs?portfolio_id=...` and `GET /scenarios/runs/{id}` return owner-scoped saved outcomes, including one- and three-month current/proposed cases, confirmed assumptions, evidence, missing facts, model version, price provenance, and the original allocation revision. Saved results do not recalculate when a portfolio or vendor price changes.
- Cancel and delete operations remain available for owner-owned drafts and runs; deleting a run removes its chat.
- `GET /scenarios/runs/{id}/messages` and `POST /scenarios/runs/{id}/messages` read/write saved run chat. A request to change assumptions creates a new draft requiring review and never mutates the saved run.

Drafts/runs have queued, running, completed or failed states, bounded retries, leases, idempotency keys, and timestamps. Conditional probabilities remain omitted until the separate calibration gate passes. Research evidence comes from approved sources, while the quant engine performs all portfolio calculations.

For existing installations, use the [inventory and release procedure](unified-what-if-release.md) to import Mongo-only portfolios and backfill legacy drafts/runs before retiring old analysis data.
