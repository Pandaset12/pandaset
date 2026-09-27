## 1. Inventory and migration safety

- [ ] 1.1 Map every frontend, API, worker, and storage reference to v1/v2 analysis IDs, and record the current portfolio and event-draft/run schemas.
- [ ] 1.2 Add a dry-run inventory for owner-scoped Mongo-only portfolios, ID conflicts, and event drafts/runs that depend on analysis records; report counts without changing data.
- [ ] 1.3 Implement and test an idempotent migration of Mongo-only portfolios into the main portfolio repository, preserving ownership and resolving conflicts without overwrite.
- [ ] 1.4 Define the release checks for the authoritative portfolio store's deployment topology and the retention period for legacy analysis backups.

## 2. Shared portfolio and calculation contracts

- [ ] 2.1 Expose a shared owner-verified portfolio access boundary to both standard and event APIs, including a stable portfolio revision on allocation edits.
- [ ] 2.2 Add on-demand current-metrics and aligned quick-comparison contracts that return observation dates, provider provenance, and modeled-result metadata without persisting analyses.
- [ ] 2.3 Update Overview, Risk, Research, and standard What-if data loading to use the new contracts and invalidate in-memory metrics on portfolio or market-data revision changes.
- [ ] 2.4 Update AI explanation contracts and consumers to return and display the exact metric context used, rejecting stale portfolio revisions without analysis IDs.
- [ ] 2.5 Test owner isolation, aligned comparison windows, provider failures, sample/model labels, and AI metric consistency for the new contracts.

## 3. Immutable event context

- [ ] 3.1 Align adjusted-price history for the current/proposed symbol union and factor proxies; support zero weights for absent positions and validate the eight-symbol limit, issuer eligibility, and complete coverage before research starts.
- [ ] 3.2 Make event draft creation verify the selected main portfolio owner and atomically pin its name, revision, both allocations, aligned prices, dates, provenance, and model version.
- [ ] 3.3 Make research, confirmation, and calculation workers use draft/run-pinned context and confirmed assumptions without dereferencing an analysis record or fetching newer prices.
- [ ] 3.4 Backfill legacy event drafts/runs with independent input context; report unresolved references and verify completed results before analysis storage is removed.
- [ ] 3.5 Test saved-run reproducibility after portfolio and price changes, plus cross-owner access, migration retries, missing history, and incomplete evidence.

## 4. One What-if interface

- [ ] 4.1 Remove the v2 portfolio probe as a whole-app mode switch and keep the main dashboard shell, navigation, onboarding, and selected portfolio for event-enabled users.
- [ ] 4.2 Integrate an optional researched-event path into the main What-if page using its proposed allocation while keeping quick comparison and explicit apply behavior.
- [ ] 4.3 Add review of evidence, missing facts, shocks and units, confirmation, one- and three-month results, saved runs, and a stale-draft state when the editor or selected portfolio changes.
- [ ] 4.4 Remove the duplicate event portfolio/analysis controls, “Backend analysis” panel, and raw analysis IDs while retaining useful provenance and modeled-result labels.
- [ ] 4.5 Verify desktop and mobile layouts, keyboard navigation, loading/empty/error states, and availability of main pages when event services fail or access is denied.

## 5. Retire analysis persistence and release

- [ ] 5.1 Stop new v1/v2 standalone analysis writes after all dashboard, AI, and event consumers use the replacement contracts.
- [ ] 5.2 Remove legacy analysis-ID endpoints, storage access, and duplicate event portfolio UI after migration checks; preserve recoverable backups for the agreed retention period.
- [ ] 5.3 Run frontend tests, backend and quant tests, type-check/build, OpenSpec validation, and a reference audit showing no active analysis-ID dependency.
- [ ] 5.4 Exercise the migration and rollback plan against representative legacy data, including unresolved records and in-flight drafts, then record release results and limitations.
