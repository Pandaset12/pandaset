# Unified What-if dependency inventory

This inventory records the pre-migration contracts for `unify-what-if-workflows`. It is a code map, not a record of production data.

| Area | Current analysis-ID dependency | Replacement boundary |
| --- | --- | --- |
| Main app and API client (`frontend/src/App.tsx`, `api/portfolio.ts`) | Creates a v1 analysis on portfolio load; stores `AnalysisResponse` with `analysis_id`; sends it to AI actions. | Fetch owner-scoped current metrics without persistence and hold one revision-bound response in memory. |
| Main pages (`pages/Overview.tsx`, `Risk.tsx`, `Research.tsx`, `WhatIf.tsx`) | Consume the active analysis response through app props. Quick What-if simulation uses a separate v1 request. | Keep pages, route, and comparison; supply current metrics and a matched quick comparison. |
| Main AI UI (`components/AIWorkflowModal.tsx`, `AnalysisContext.tsx`) | Requires and displays analysis IDs. | Show data period and provenance, and bind explanations to the returned metric context. |
| Event app (`frontend/src/EventApplication.tsx`, `api/eventLab.ts`) | Owns another portfolio picker and creates/lists v2 analyses; refresh control and AI actions reference a saved ID. | Remove whole-app switch and secondary picker; integrate event controls into main What-if. |
| Event pages (`pages/EventOverview.tsx`, `EventRisk.tsx`, `EventResearch.tsx`, `EventWhatIf.tsx`) | V2 analysis props drive duplicate pages; event drafts, revisions, and saved-run UI use analysis IDs. | Reuse main pages; keep event review, confirmation, and runs on the integrated What-if page with pinned context. |
| V1 HTTP (`backend/api_v1.py`, `schemas.py`) | POST analysis writes SQLite; GET analyses reads it; briefing/risk/scenario AI requests contain `analysis_id`. | Current-metrics and comparison responses with portfolio revision, provider dates, and metric context; no public analysis ID. |
| V1 storage (`backend/storage.py`) | `analyses` table holds `analysis_id`, `portfolio_id`, timestamp, JSON metrics. Update/delete remove rows. | `portfolios` remains authoritative and owner-scoped; retire analysis writes/reads after migration. |
| V2 HTTP (`backend/event_api.py`, `event_schemas.py`) | Separate portfolio CRUD and analyses endpoints; draft/confirm/chat revision resolve `analysis_id`. | Resolve the same main portfolio owner; embed inputs in drafts/runs. |
| V2 storage (`backend/mongo_store.py`) | `portfolios`, `analyses`, and `analysis_counters` collections; `create_draft` validates an analysis and `create_run` copies it. | Migrate v2-only portfolios; retain Mongo drafts/runs/messages and their immutable input context, then retire separate portfolio/analysis writes. |
| Event workers (`backend/event_jobs.py`) | Research worker dereferences draft's analysis; run worker uses the copied analysis/price snapshots and emits an analysis ID. | Research and run workers consume context pinned in the draft/run and emit provenance without an analysis ID. |
| AI services (`backend/gemini_service.py`) | Analysis/scenario prompts accept an optional analysis ID as context metadata. | Bind prompts to revision and returned metrics, without an analysis identifier. |

## Persisted schemas before migration

- **Main portfolio:** SQLite `portfolios(portfolio_id, payload, owner_id)`. The JSON payload is `Portfolio`: name, holdings, ID, and creation time. There is no stable edit revision yet. Legacy unowned rows are not returned to authenticated investors.
- **Main analysis:** SQLite `analyses(analysis_id, portfolio_id, created_at, metrics)`; metric JSON is `AnalyticsSnapshot`. Portfolio update deletes analyses when weights change.
- **Event portfolio:** Mongo `portfolios` document with `_id`, `owner_id`, `payload` (`EventPortfolio` name/holdings/ID/creation time), created/updated timestamps, and optional tombstone.
- **Event analysis:** Mongo `analyses` document with `_id`, `owner_id`, `portfolio_id`, sequence, metrics, allocation snapshot, adjusted-price snapshot with dates/provenance, and model version.
- **Event draft:** Mongo `scenario_drafts` document with owner, portfolio ID, status, request containing `analysis_id`/template/situation/proposed weights, proposal, confirmed shocks, revision, attempts, idempotency metadata, and timestamps. Research workers currently read its referenced analysis.
- **Event run:** Mongo `scenario_runs` document with owner, portfolio/draft/analysis IDs, confirmed shocks, copies of allocation/price/metric snapshots, model version, proposed weights, proposal, result, status, attempts, idempotency metadata, and timestamps. Saved-run reads currently require the event portfolio to remain visible.

## Migration invariants

Inventory and migration operate on owner-scoped records only. A missing referenced analysis, mismatched owner, conflicting portfolio ID, incomplete price snapshot, or active draft must be surfaced rather than silently discarded. Preserve a recoverable backup before retiring storage. The main portfolio's visible sample and modeled-result disclosures remain in the UI.
