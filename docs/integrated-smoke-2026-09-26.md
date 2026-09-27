# Integrated smoke test — September 26, 2026

Initial baseline: `main` at `5ccba9b`; then incorporated `5d66be8` (Nel's
What-if layout fix) and `00882a3` (Alpaca Overview and company-name search).
Final automated, live API, and browser scenario checks use `00882a3` plus this fix.
The subsequent auth-screen-only update through `73df823` was also merged;
all 80 frontend tests and the production build were rerun successfully. That
does not extend this report to real Supabase authentication.
Tested locally with the real Alpaca account,
`MARKET_DATA_PROVIDER=alpaca`, `ALPACA_HISTORY_FEED=iex`, and isolated SQLite
storage. History caching was left disabled. No keys or local test harnesses are
included in this change.

## Result

No blocking 500s or fictional-price fallback reproduced in the tested standard
workspace. The initial smoke found two incorrect source labels: holdings outside the built-in
library (tested with SPY) claimed to use sample prices, and the ticker preflight
error did the same. The later `00882a3` update independently corrected both.
Its newer provider messaging and company lookup are retained unchanged; this PR
keeps a regression test against invented source labels.

The follow-up found a stale-data bug after **Use this allocation**: the new
portfolio became active, but the old comparison stayed visible, mixing its old
baseline metrics with the new current holdings. The parent workspace now keys
What-if by the analysis ID as well as the route, clearing the old comparison
when the analysis changes. The regression test failed before this fix and passed
afterward; real Alpaca compare/apply/reload was also rechecked successfully.
Nel's `WhatIf.tsx` and layout CSS are unchanged by this PR. No quant formulas,
auth implementation, or Event Lab code changed.

This is **not a full deployment sign-off**. Only Alpaca credentials were available
locally. Auth used a synthetic upstream user response against the real v1 API
ownership checks; the browser dashboard used a separate local test-session entry
point. Actual Supabase login/session refresh and the production mode selector
were not exercised. Gemini was configured in Gemini mode without a key to test
failure behavior. Event Lab was disabled, not tested as a working live service.

## Checks

| Flow | Result |
| --- | --- |
| Landing → `app.html` | Landing and link work. The real app correctly shows missing Supabase setup instructions in this environment. |
| Portfolio create | API create and browser onboarding pass, including direct-entry SPY at 100%. |
| Edit/reload | Browser edit from AAPL/MSFT 60/40 to 65/35 persists after reload and recalculates metrics. |
| Saved snapshots | Read-back matches the saved analysis. Edits invalidate old snapshots. Recreating the API app with the same SQLite file preserves portfolio and snapshot. |
| Ownership | No bearer token: 401. Different synthetic owner: 404 for portfolio and analysis. Not a real Supabase test. |
| Overview | Real IEX last-trade prices/timestamps render separately from adjusted-history risk calculations. |
| Company search | Real authenticated `/assets/search?q=Apple` returns AAPL first. No trading operations were used. |
| Risk | Saved allocation, risk contributions and correlation matrix render from the live analysis. |
| Research | 252-return histories load. All eight built-in tickers return aligned history together; direct-entry SPY and comparison history also load. Source identifies `alpaca_adjusted_daily` and IEX. |
| Allocation What-if | API comparisons with changed weights and a new symbol pass without mutating saved holdings. Browser five-point transfer passes. Added AAPL to a single-holding SPY portfolio, compared/applied 74.5/25.5, then 70.5/29.5. Repeated with 70/30 after merging `00882a3`. Old results disappear after application and the new allocation survives reload. |
| Gemini actions | Ask, briefing, risk explanation, scenario explanation and research summary return explicit unavailable states with `GEMINI_NOT_CONFIGURED`, not invented AI success or 500s. Briefing fallback also verified in browser. |
| Missing Alpaca keys | Analysis returns safe 502; optional quotes return 503. No sample fallback. |
| Unknown ticker | History returns 404, not a 500. |
| Event Lab | Disabled v2 path returns 503. No real Mongo, jobs, event analysis or event chat tested. |
| Browser checks | Corrected Research copy verified at desktop/mobile sizes; no horizontal overflow at the mobile check and no captured console errors/warnings. |

The last completed market session was September 25, 2026. Latest IEX trades also
reported September 25. These are expected weekend timestamps, not evidence of a
continuously updating weekend feed. Daily history is not an intraday risk model.

## Automated validation

- Backend: 226 tests passed.
- Python quant engine: 88 tests passed.
- Frontend/TypeScript quant: 80 tests passed after incorporating `00882a3`
  (72 on the initial baseline).
- Production build, backend compilation, changed-file Prettier checks
  (`--end-of-line auto` for this Windows checkout) and
  `git diff --check`: passed.
- The scenario regression test failed before the state-reset fix and passed
  afterward. The initial provenance assertions also reproduced the old labels;
  the latest main corrections and retained regression check pass.

## Still needed on the judging setup

1. Supply the real frontend/backend Supabase configuration and use a test
   account: sign in, create/edit/reload, sign out/back in, and check a second
   account cannot read the first account's records. Confirm storage survives a
   deployment restart, not just a local app restart.
2. With Gemini configured, run each action and verify `status: complete`, the
   selected analysis ID, citations and explicitly requested source evidence.
   Missing-key fallback passing does not validate a real model/key/quota.
3. If Event Lab will be shown, test it in the configured environment: owner-scoped
   portfolio/analysis persistence, event draft/confirm, worker completion,
   saved-run reload and chat. Keep it disabled if those dependencies/release
   gates are unavailable. See [Event Lab release gates](event-lab-release-gates.md).
4. Recheck the final deployed What-if build. Single-holding/add-symbol/fractional
   compare/apply flows passed locally; the eight-symbol union is covered by the
   automated suite. A minor horizontal overflow (400px content at a 390px viewport)
   remains on the mobile What-if page; controls were usable. Left layout to Nel.
   The comparison table also still calls the historical-period result "Sample
   return"; "Period return" would be clearer, but this was not fictional input.
5. Confirm applicable Alpaca display/retention rights before external judging;
   this test does not establish those rights or change the release-gate settings.

Use the existing [Alpaca history setup](../backend/docs/ALPACA_HISTORY.md) for
server-side credentials. The Vite startup URL and API proxy instructions alone
do not provide Supabase, Gemini or Event Lab configuration.
