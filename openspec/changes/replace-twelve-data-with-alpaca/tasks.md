## 1. Historical provider and configuration

- [ ] 1.1 Add `backend/alpaca_history.py` with authenticated `1Day` historical-bar requests, `adjustment=all`, explicit `iex|sip` feed, complete-session cutoff, bounded pagination, and a 1–25 symbol/1–1000 return-observation contract.
- [ ] 1.2 Validate positive closes, unique session dates, full per-symbol coverage, and aligned holding/factor histories; attach source, feed, adjustment, session date, retrieval time, freshness, and warning provenance; map credentials/entitlement, rate-limit, malformed-data, and coverage failures.
- [ ] 1.3 Replace Twelve Data settings in `backend/config.py` and `backend/.env.example` with Alpaca history feed and rights flags, using the existing server-side Alpaca credentials; retain sample as the v1 default and fail clearly on stale `twelvedata` selection.
- [ ] 1.4 Adapt `backend/price_cache.py` and the optional durable history cache so entries are isolated by provider/feed/adjustment, frame provenance survives cache hits, and no Alpaca history is cached without confirmed retention rights.

## 2. Standard analysis and What-if

- [ ] 2.1 Switch `backend/providers.py` to Alpaca history for selected v1 analysis, market history, and allocation What-if while keeping sample mode and `backend/alpaca_quotes.py` separate.
- [ ] 2.2 Update `backend/api_v1.py` provider error text and mapping, and `backend/main.py` health/readiness fields so missing configuration and provider failures are accurately reported without fixture fallback.
- [ ] 2.3 Verify a v1 What-if proposal that adds a symbol uses one aligned Alpaca history matrix for baseline and proposal, and preserves source/feed provenance in both results.

## 3. Event lab and saved analyses

- [ ] 3.1 Replace v2 provider construction in `backend/main.py` and fetch/retry typing in `backend/event_api.py` with Alpaca history for holdings and SPY/TLT/GLD; preserve explicit coverage failures and the gated startup behavior.
- [ ] 3.2 Preserve immutable saved snapshots and original Twelve Data provenance for pre-migration records in `backend/event_api.py`, `backend/event_jobs.py`, and storage; create Alpaca-backed scenarios only from newly created Alpaca analyses.
- [ ] 3.3 Replace vendor-specific event-lab display/cache readiness flags and enforce the public release gates for Alpaca, with no provider request or cache use when the required configuration or rights are absent.

## 4. Verification

- [ ] 4.1 Replace `backend/tests/test_twelve_data.py` and vendor cases in `test_market_event_data.py` with mocked Alpaca history tests for request parameters, pagination across symbols, incomplete sessions, normalization, adjustment/feed provenance, invalid bars, insufficient and misaligned history, 401/403/429, and outages.
- [ ] 4.2 Update `backend/tests/test_ownership.py`, `test_review_fixes.py`, `test_event_api.py`, and cache tests for Alpaca selection, health, event snapshots, rights, and old-record readability.
- [ ] 4.3 Update frontend vendor fixtures including `frontend/tests/event-lab-model.test.ts`; test the standard and event What-if source labels and ensure the live-quotes strip remains separate from calculated results.
- [ ] 4.4 Run backend tests, `npm test`, and `npm run build`; perform opt-in Alpaca credential/entitlement checks for representative holdings and factor ETFs before vendor-backed release, recording feed, coverage, and quota observations without logging secrets.

## 5. Cleanup, documentation, and rollout

- [ ] 5.1 Remove the active `backend/twelve_data.py` adapter, its tests, and obsolete `backend/drafts/data_pipeline/providers.py` Twelve Data adapter; update draft notes and ensure no active runtime import or configuration path remains.
- [ ] 5.2 Replace Twelve Data instructions in `README.md`, `backend/README.md`, `backend/docs/TWELVE_DATA.md`, `docs/event-lab-release-gates.md`, and user-facing provider labels with Alpaca history setup, explicit feed scope, rights checks, caching policy, and saved-analysis migration guidance.
- [ ] 5.3 Reconcile the in-progress `event-aware-what-if-lab` proposal, design, and tasks with this provider decision while retaining completed historical OpenSpec artifacts as records.
- [ ] 5.4 Document deployment and rollback: start with sample mode and v2 disabled, select and verify the entitled Alpaca feed, enable rights-gated features, create new analyses, and preserve old snapshots when retiring Twelve Data credentials and caches.
