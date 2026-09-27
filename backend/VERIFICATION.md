# API/Gemini self-review verification

Reviewed against main `37bf1e4`, including authenticated portfolio persistence,
Twelve Data history, the v2 event lab, and optional Alpaca IEX quotes. This update
changes only backend files and docs.

## Fixes verified

- Reject local/internal source domains with trailing DNS root dots and domains
  with empty labels. Valid public HTTPS domains with one root dot remain accepted.
  The shared validator covers both legacy Analyst and v1 Ask requests.
- Treat whitespace-only credentials as missing, including the new event-lab
  dependencies. Preserve v1's publishable-key fallback and legacy anon-key
  precedence. Unconfigured auth returns 503 before sending a token upstream.
- Health reports missing auth configuration and missing keys required by the
  selected analyst/data modes. It returns additive readiness flags and issue
  codes, retains HTTP 200 for a running process, and never calls a vendor.
  An enabled but unconfigured event lab is degraded; configured credentials
  cannot hide a failed event-store startup. V2 routes, startup/shutdown, allowlist
  and public-release gates remain intact.
- Update startup/API examples, storage handoff, and integration documentation to
  reflect authenticated portfolios, the connected quant engine, optional Twelve
  Data, v1 SQLite, and v2 MongoDB storage. Ask's prompt now distinguishes its own
  snapshot-only behavior from the separate working What-if endpoint.
- Retain one complete set of main's N+1 price fixtures, observation-count,
  alignment, and preflight-cache assertions. The overlapping fixture fixes are
  already integrated through PR #17; both test files now match main exactly.
  Provider coverage/alignment checks remain intact.
- Preserve Alpaca quote configuration, authentication, response validation, and
  missing-credential behavior. Quotes remain optional and separate from the
  historical inputs used by the quant engine and saved analyses.

## Automated checks

| Check | Result |
| --- | --- |
| Backend suite | 211 passed |
| Python quant suite | 88 passed |
| Frontend/TypeScript suite (`npm test`) | 72 passed |
| Production build (`npm run build`) | Passed |
| Dependency consistency (`pip check`) | Passed |
| Backend Python compilation | Passed |
| Git whitespace checks | Passed |

Readiness regressions cover missing and whitespace-only keys, v1's actual Auth
request key selection, v2 startup success, and Mongo connection/index/worker
startup failures with cleanup. Event startup tests use in-memory `mongomock`,
stubbed token verification, and a stubbed worker; they do not prove real Mongo
availability or live event jobs. Existing tests cover saved snapshot identity, persistence, invalid
allocations/provider output, safe error envelopes and request IDs, Gemini
numeric/citation validation, model fallback, timeouts, tool selection, ownership,
atomic portfolio edits, and cache reuse. The integrated quote tests cover
authentication, incomplete credentials, the 25-symbol limit, malformed vendor
responses, safe errors, and explicit trade timestamps. One existing upstream
Starlette/httpx deprecation warning remains; it does not fail the suite.
No frontend source was changed.

## Running API checks

Started real Uvicorn processes on isolated local ports and temporary SQLite
files. Authentication used a separate local HTTP stub with two synthetic user
IDs; prices were the fictional sample fixture. No real credentials were used.
The test processes were stopped after these checks.

- Missing/invalid sessions return 401. A different synthetic owner receives 404
  for the portfolio and its analysis.
- Create a 74.5% SPY / 25.5% NVDA portfolio (201), calculate/save/read its analysis
  (200), and ask about that exact saved analysis.
- Compare an alternative allocation (200) without changing saved holdings.
- Edit the existing portfolio (200), preserve its ID/creation time, reject the
  stale analysis (404), and save a new analysis for the edited allocation.
- Restart the API and reload the edited portfolio and exact saved snapshot.
- Reject `https://localhost./` at both legacy Analyst and v1 Ask (422).
- In demo mode, Ask explicitly returns `status: demo`.
- In Gemini mode without a key, health reports degraded/GEMINI_NOT_CONFIGURED;
  Ask returns HTTP 200 with `status: unavailable` and that same error code.
- In Twelve Data mode without a key, health reports degraded and public history
  returns 502. The API never substitutes fictional prices for a vendor failure.
- Optional quotes require authentication (401 without a session). With a valid
  stub session but no Alpaca credentials they return 503/`ALPACA_NOT_CONFIGURED`;
  the sample portfolio flow still completes and core health remains healthy
  when its own required settings are present.

## Remaining live acceptance checks

This review does not validate a real Supabase login, Gemini key/model/search call,
Twelve Data or Alpaca account/quota, Tavily/DeepSeek/FRED credentials, hosted persistence,
MongoDB deployment, or Tiger Data. Those services require the team's configured
environment. Health checks configuration presence and event-store initialization
at startup; it does not recheck credential validity or vendor reachability.

Before the demo, run the authenticated create/edit -> real-data analysis -> saved
snapshot -> AI explanation -> reload flow. Inspect market date/source/freshness,
AI `status: complete`, evidence for explicit Search/URL requests, and upstream
failure behavior. Keep deployment request limits and persistent SQLite storage
with the deployment owner's checklist; they are not supplied by these fixes.
For v2, additionally follow the event-lab release gates for authenticated Mongo
persistence, source retrieval, queued jobs/restart recovery, and saved run chat.
For optional IEX quotes, run the documented read-only Alpaca check with configured
server-side credentials and verify the authenticated UI in the deployment.

Search stays off by default with explicit opt-in. This patch does not change the
team's model choices, quant formulas, market-data provider behavior, database
selection, frontend, or portfolio editing workflows.
