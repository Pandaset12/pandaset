## 1. Identity and storage

- [x] 1.1 Verify Supabase tokens in Python for configured signing mode and reject missing or invalid tokens.
- [x] 1.2 Add owner-scoped Mongo portfolios, analyses, drafts, runs, chat, and idempotency indexes.
- [x] 1.3 Connect authenticated onboarding to portfolio listing, creation, selection, and analysis.

## 2. Market and event evidence

- [x] 2.1 Reconcile Twelve Data provider for up to 25 classified holdings, adjusted-price provenance, quota-aware caching, and explicit failures.
- [x] 2.2 Add versioned macro, sector, and issuer templates and FRED/current-source evidence with timestamps and missing statuses.

## 3. Quant engine

- [x] 3.1 Estimate factor and issuer sensitivities from aligned adjusted-price history.
- [x] 3.2 Calculate comparable current/proposed mild, central, and severe cases at one and three months.
- [x] 3.3 Add seeded conditional central-case ranges with complete-coverage gate.
- [x] 3.4 Document and evaluate held-out calibration; fail closed for probabilities if not accepted.

## 4. Agent coordinator and APIs

- [x] 4.1 Add bounded Gemini research/design roles and grounded source status preservation.
- [x] 4.2 Add authenticated instrument, template, draft, confirmation, run, progress, cancellation, and deletion APIs with durable jobs and limits.
- [x] 4.3 Add run-specific chat grounded in stored evidence/calculations and revision drafts.

## 5. What-if Lab interface

- [x] 5.1 Replace fixed-asset state with authenticated selected-portfolio data.
- [x] 5.2 Add event list/chat, assumption confirmation, and separated sourced/assumed/calculated/conditional results.
- [ ] 5.3 Verify responsive, keyboard, empty, unavailable, and error states; preserve explicit allocation apply.

## 6. Release checks

- [x] 6.1 Verify ownership isolation, data coverage, source failures, invalid agent output, immutable snapshots, idempotency, and chat revisions.
- [x] 6.2 Run build and focused tests, complete code review, and repair findings.
- [x] 6.3 Document licensing, news approval, capacity, cost, security, calibration, and labeling gates before public enablement.
