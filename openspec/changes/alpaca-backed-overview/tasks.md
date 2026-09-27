## 1. Overview presentation

- [x] 1.1 Update `frontend/src/pages/Overview.tsx`, `frontend/src/App.tsx`, and shared analysis details so sample and Alpaca analyses have source-aware historical labels, a clear as-of session, and modeled-return language; keep the IEX latest-price strip separate.
- [x] 1.2 Replace the fixed four-ticker technology allocation tile with an allocation metric derived from the selected analysis's actual holdings and weights.
- [x] 1.3 Make unknown-ticker display metadata neutral in `frontend/src/workspace/holdings.ts`, and make `verifyPortfolioHistory()` failures in `frontend/src/api/portfolio.ts` provider-neutral and recoverable.
- [x] 1.4 Confirm the VTI comparison appears only when the saved analysis contains VTI history, and keep “On your radar” notes explicitly editorial and filtered by current holdings.

## 2. Behavior verification

- [x] 2.1 Add focused frontend tests for Overview in sample and Alpaca modes, including source/as-of labels, quote separation, missing values, and no sample wording on Alpaca results.
- [x] 2.2 Add frontend cases for an arbitrary supported ticker, an allocation change, a portfolio without VTI, and an allocation summary that reflects the actual holdings.
- [x] 2.3 Add or extend backend v1 integration tests showing two different saved user allocations produce corresponding Alpaca-backed analyses and that missing configuration, rate limits, and incomplete history never fall back to sample results.

## 3. Rollout

- [x] 3.1 Update deployment guidance for server-side `MARKET_DATA_PROVIDER=alpaca`, key/secret/feed selection, data rights, historical versus latest-price labels, and expected quote-polling load; keep sample mode documented.
- [ ] 3.2 With rotated local credentials, run the existing opt-in Alpaca history check for representative holdings and factor ETFs; record selected feed, coverage, entitlement, and quota observations without storing secrets or prices. Complete the corresponding live-check task in `replace-twelve-data-with-alpaca` only after this succeeds.
- [x] 3.3 Run backend tests, `npm test`, `npm run build`, and strict OpenSpec validation; inspect Overview at desktop and mobile widths plus keyboard, empty, missing-quote, and provider-error states.
