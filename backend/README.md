# Pandaset application API + Gemini

The backend owns the frontend API, input validation, on-demand calculations,
event-run input snapshots, Gemini prompts, and error handling. Market ingestion, Tiger Data,
MongoDB infrastructure and financial formulas belong to the data/quant teammates.
See [the shared HLD](../PortfolioLens-HLD.md) and [integration design](INTEGRATION.md).

The default v1 provider connects the quant engine to fictional sample prices for
an offline demo. V1 can use adjusted daily end-of-day prices from Alpaca
when `MARKET_DATA_PROVIDER=alpaca`; see [setup guide](docs/ALPACA_HISTORY.md).
The gated v2 event lab requires adjusted Alpaca history.
Gemini is optional for v1 and designs v2 scenario assumptions. V2 event research
uses Tavily retrieval and DeepSeek fact extraction.

## Authenticated event lab (`/api/v2`)

The event lab is disabled by default. Copy `backend/.env.example` to the ignored
`backend/.env`, then set `EVENT_LAB_ENABLED=true`, the Supabase project origin and
publishable key, `SUPABASE_SIGNING_MODE`, Mongo URI, Alpaca key and secret,
`ALPACA_HISTORY_FEED`, Gemini key,
`TAVILY_API_KEY`, and `DEEPSEEK_API_KEY`. All v2 routes verify a bearer access
token and derive the Mongo owner from its verified subject. Both APIs use the
same owner-scoped portfolio in SQLite. Event drafts request adjusted daily
history from Alpaca and never substitute demo prices.

For an internal release, keep `EVENT_LAB_PUBLIC_ENABLED=false` and populate
`EVENT_LAB_ALLOWED_USER_IDS` with a comma-separated list of invited Supabase
user UUIDs. An empty list denies every account. Public enablement additionally
requires the explicit rights and source flags in `backend/.env.example` and the
recorded checks in `docs/event-lab-release-gates.md`. `EVENT_LAB_PROBABILITY_ENABLED`
does not by itself release probabilities; the quant engine also needs accepted
held-out calibration evidence. Current v2 runs omit conditional ranges and show
the reason while returning deterministic cases.

The scenario workflow is: save a portfolio, compare a proposed allocation,
choose an event area and suggested situation or describe a custom one, create a draft,
review cited facts and proposed shocks, confirm the
shocks, then poll the run. Mongo stores queued jobs, leases, attempts, pinned
event inputs, and run chat so work can resume after a process restart. The `rates`
factor means **TLT adjusted return**, not a yield change. FRED yield observations
are contextual evidence. Tavily searches only curated official hosts and news
hosts listed in `APPROVED_NEWS_DOMAINS`; search snippets are not evidence. A
page is cited only after Tavily Extract returns its content. DeepSeek converts
that content into bounded facts with checked evidence IDs. Failed extraction
stops draft preparation. Current-event searches filter out pages without a
recent detected date; an explicitly historical question can retrieve older pages.
Search and extraction use basic depth, at most five search results and three
extracted pages per draft. Gemini proposes shocks for user review, with DeepSeek
as a bounded fallback when Gemini fails or is rate limited. The quant engine
calculates the final numbers. V2 error responses use
`{"error":{"code":"...","message":"...","request_id":"..."}}`.

## Run locally

Requires Python 3.11 or newer; verified locally with Python 3.12.
Run all commands from the repository root.

Windows PowerShell (activation is unnecessary):
~~~powershell
py -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\.venv\Scripts\python.exe -m pip install -e quant_engine
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
~~~

macOS/Linux:
~~~sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python -m pip install -e quant_engine
backend/.venv/bin/python -m uvicorn backend.main:app --reload
~~~

Open [interactive API docs](http://127.0.0.1:8000/docs) or
[health](http://127.0.0.1:8000/health). Health reports configuration and whether
the enabled event store initialized; it does not make live vendor checks.

The server and public sample-price history can start without vendor keys.
The v1 market-data provider defaults to fictional sample prices. V1 portfolio
routes require `SUPABASE_URL` and either `SUPABASE_PUBLISHABLE_KEY` or the legacy
`SUPABASE_ANON_KEY` to verify the bearer session and scope SQLite portfolios and
current metrics to the user, even in demo mode. Copy `backend/.env.example`
to the ignored `backend/.env` and use the frontend's Supabase project. Requests
carry the investor's access token in `Authorization: Bearer <access_token>`.

V1 uses ignored `backend/data/portfoliolens.sqlite3` as the authoritative portfolio store. The gated v2 event routes use that same portfolio identity and owner-scoped MongoDB drafts/runs.
See the [unified migration guide](../docs/unified-what-if-release.md) before enabling event research for existing v2 users.
Tiger Data is not connected.

## First frontend flow

Sign in through the frontend, or use the interactive docs' **Try it out** buttons
with your session's Bearer token in the `authorization` header field. Keep the
token local. Do not paste it into issues or commit it.

1. `POST /api/v1/portfolios` creates a portfolio owned by the current investor:
   `{"name":"My portfolio","holdings":[{"symbol":"SPY","weight":1.0}]}`.
   Copy its `portfolio_id`; `GET /api/v1/portfolios` lists your saved portfolios.
2. `GET /api/v1/portfolios/{portfolio_id}/metrics` calculates the selected
   portfolio's current metrics. A briefing or risk explanation takes its
   `portfolio_revision` and recomputes the exact metric context on demand.
The legacy seeded `demo` portfolio is unassigned and is not accessible to investor
accounts; create an owned portfolio for manual testing. Any valid allocation
using NVDA, MSFT, AAPL, JPM, VTI, TLT, AMD, GLD, or SPY can be analyzed and compared
using seven fictional price rows (six daily returns). Unsupported symbols return 404; prices are never
invented or filled. Weights must total one within 1e-10 and are never renormalized.
Portfolios and proposed allocations accept at most eight symbols; a what-if comparison
also requires the combined saved/proposed symbol set to stay within eight.
Undefined risk shares and correlation cells remain `null`. The UTC midnight `as_of`
is a sample session-date label, not a live quote or exchange closing timestamp.

## Routes and error handling

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/health` | Process/configuration status |
| POST | `/api/v1/portfolios` | Validate and save `name` plus `holdings`; returns 201 |
| GET | `/api/v1/portfolios` | List portfolios owned by the authenticated investor |
| PUT | `/api/v1/portfolios/{id}` | Replace the authenticated owner's portfolio name and holdings; retains ID and creation time |
| GET | `/api/v1/portfolios/{id}` | Read saved portfolio |
| GET | `/api/v1/portfolios/{id}/metrics` | Calculate current metrics without saving an analysis |
| GET | `/api/v1/quotes?symbols=AAPL&symbols=MSFT` | Optional Alpaca IEX latest-trade snapshots; separate from daily portfolio analysis |
| GET | `/api/v1/assets/search?q=Apple` | Authenticated company/symbol lookup; sample symbols in demo mode, read-only Alpaca US equity directory in Alpaca mode |
| POST | `/api/v1/portfolios/{id}/what-if` | Compare saved and proposed holdings on the selected market-data history |
| POST | `/api/v1/portfolios/{id}/briefing` | Explain metrics for the selected portfolio revision |
| POST | `/api/v1/portfolios/{id}/risk/explanation` | Explain risk for the selected portfolio revision |
| POST | `/api/v1/portfolios/{id}/what-if/explanation` | Recalculate and explain a proposed allocation on aligned history |
| POST | `/api/v1/research/{symbol}/summary` | Summarize the allowlisted issuer source for a supported symbol |

Holdings use `{"symbol":"NVDA","weight":0.3}`. Weights are finite long-only
decimals and must sum to 1 (tolerance 1e-10). Duplicate symbols are rejected
after normalization. We never silently rescale inputs.

V1 errors use `{"error":{"code":"...","message":"..."}}`. Input errors are
422, missing/invalid sessions 401, unconfigured auth 503, missing or another
investor's objects 404, a portfolio changed during analysis 409, and provider
errors 502. The inactive precomputed test provider can also return 501.
AI failures on the contextual workflow routes return HTTP 200
with `status: "unavailable"`, an `error_code` when available, and warnings.
Current metrics or the selected Research source remain accessible. Quant-provider
failures on What-if routes still use HTTP errors. The frontend must check
`status`; HTTP 200 does not imply that an AI explanation succeeded.

Every application response includes a server-generated `X-Request-ID`.
V1 errors also include `error.request_id`. Provider, storage, AI and unexpected
failures emit JSON logs with that ID, error code, exception type and stack
locations. Raw exception messages, prompts, credentials and upstream payloads
are not logged. CORS exposes the ID header so the frontend can report it.

The initial `/api/portfolios/{id}/analytics` and `/api/what-if` routes remain
deprecated compatibility routes. They retain their `detail` error envelope.
New frontend work should use v1.

## Enable Gemini

Copy `backend/.env.example` to `backend/.env` if it does not already exist.
Set `ANALYST_MODE=gemini` and `GEMINI_API_KEY`, then restart the server.
Only `backend/.env` is loaded automatically; the root example environment file
is not used by this service. Never commit actual keys.

| Setting | Default / purpose |
| --- | --- |
| ANALYST_MODE | `demo` or `gemini` |
| GEMINI_API_KEY | Server-side key; required in Gemini mode |
| GEMINI_MODEL | `gemini-3.8-flash`; confirm team account access |
| GEMINI_FALLBACK_MODEL | `gemini-3.5-flash-lite`; tried after non-quota Gemini failures. Set empty to disable. |
| GEMINI_TIMEOUT_SECONDS | 45 per model; maximum 120 |
| CORS_ORIGINS | Comma-separated frontend origins; localhost ports 3000 and 5173 |
| STORAGE_PATH | Optional override for the SQLite file |
| ALPACA_API_KEY / ALPACA_API_SECRET | Server-side credentials for optional history and IEX quote snapshots; never expose them to the frontend |
| ALPACA_HISTORY_FEED | Explicit `iex` or entitled `sip` selection for adjusted daily history; separate from IEX quote snapshots |
| ALPACA_ASSETS_BASE_URL | Read-only stock-directory host, paper by default; use `https://api.alpaca.markets` with live account credentials |
| ALPACA_DISPLAY_RIGHTS_CONFIRMED / ALPACA_CACHE_RIGHTS_CONFIRMED | Public event-lab display and history-retention gates; default false |

The Overview's optional live-price strip polls the authenticated
`/api/v1/quotes` endpoint every 15 seconds while the page is visible. It accepts
1–25 unique symbols (at most 20 characters each). This quote limit is independent
of the eight-symbol portfolio and What-if limit.
It uses Alpaca's free IEX feed, which covers one exchange rather than consolidated
US market activity; it is labeled IEX and is not used by the quant engine or
saved risk metrics. A successful free API call does not itself establish public
display rights: verify Alpaca's applicable market-data agreements before showing
prices to judges or other users. When keys are absent, `ALPACA_NOT_CONFIGURED`
hides this optional strip and stops polling until it remounts (for example after
a reload or portfolio change). Vendor outages show an unavailable state instead;
the strip never substitutes sample prices.

The vendor socket timeout is capped at 10 seconds (or a smaller configured
`MARKET_DATA_TIMEOUT_SECONDS`); the browser cancels after 20 seconds and when
switching portfolios or leaving the page. Failed refreshes back off to 30 then
60 seconds. Previously received prices remain visible with an explicit warning.
Trade timestamps identify the last IEX trade, not the time the page refreshed;
they may be old outside trading hours or for thinly traded instruments. A missing
trade is shown as unavailable. There is no quote persistence or shared quote
cache, so each active client consumes vendor requests. Restrict demo access and
add server-side rate limiting before an unrestricted public rollout.

For a read-only live credential check (two symbols; no trading API calls):

~~~powershell
.\backend\.venv\Scripts\python.exe -m backend.check_alpaca_quotes
~~~

The command reads ignored `backend/.env`; `--env-file <path>` selects another
local file. It prints only the feed, symbols, last prices, and trade timestamps,
and exits nonzero on an error or missing trades. Do not put keys on the command
line. Mocked unit tests do not contact Alpaca; this opt-in check does. Successful
vendor access does not verify production sign-in, deployment, or display rights.

All Gemini-backed actions use one server-side adapter with a versioned,
workflow-specific prompt and JSON response schema. The primary model has a
bounded timeout and at most two HTTP attempts. If it fails or returns an invalid
response, the adapter tries the configured fallback model with the same prompt,
context, validation, and timeout. The fallback is skipped in demo mode, without
an API key, when its model name matches the primary, or after a 429 rate-limit
response. On 429, the adapter honors the provider's `Retry-After` or retry delay
when present (otherwise 60 seconds), pauses new Gemini requests locally, and
returns a specific rate-limit message. The event worker leaves queued drafts
untouched during that pause and does not immediately rerun a draft that hit 429;
deterministic calculation runs continue. An exhausted fallback
returns the existing safe partial response for v1 or fails the v2 draft;
sequential attempts can take up to twice `GEMINI_TIMEOUT_SECONDS`. Each action
receives only its scoped context:
Overview and Risk get one validated snapshot; What-if gets the server-calculated
baseline, proposal, differences, and assumptions; Research gets one curated
source URL.
Portfolio workflows return qualitative `explanation` and `cited_fields`. The
backend renders numerical facts from those IDs using its own snapshot or
comparison catalog. These are single requests without sub-agents or
cross-request memory.

Numeric literals (including Unicode numerals) and common English number words
in model prose are rejected. A failed validation produces the existing safe
partial response. Tests cover invented numbers accompanied by valid citation IDs.
This is a conservative guard, not proof that every qualitative statement is true
or that all possible numerical paraphrases are detected. It can also reject
otherwise harmless number-like prose. Live answer quality still needs review.

**Tool access is workflow-scoped.** Briefing, Risk, and What-if use no web
tools. Research enables URL Context only, for the hardcoded official issuer URL
selected in the Research page; it does not use Google Search. Research does not
crawl pages in the background. Choose a model supporting structured output and
the URL Context tool.

Research responses include retrieval status and source evidence. Text offsets
refer to `grounding_text` (the original model response), not the parsed answer.
The frontend must handle [URL retrieval status](https://ai.google.dev/gemini-api/docs/generate-content/url-context).

Enabling Gemini does not enable live prices. Quant calculations run through the
provider before any scenario explanation. The explanation route cannot apply or
save proposed holdings. Persisting an allocation is a separate authenticated
`PUT /api/v1/portfolios/{id}` action. Daily P&L
attribution and natural-language execution of what-if calculations remain
unsupported.

## Team integration checklist

- **Quant (Nel A):** `EngineQuantProvider` calls both public functions. The adapter
  handles output fields, undefined values, correlation roundoff, weight precision
  and what-if asset unions. Formulas remain unchanged in the quant module.
  `DemoQuantProvider` remains available only for precomputed-fixture regression tests.
- **Data/infrastructure (Vincent):** supply normalized adjusted-close price access,
  source/freshness metadata, and durable MongoDB storage for event drafts and runs.
  Confirm the main portfolio store has one writer and a persistent volume. Event
  input snapshots require a timezone-aware market timestamp, observation count and source.
- **Frontend (Meirzhan):** agree on current-metric and portfolio-revision payloads, null metrics, partial
  AI responses, citation display and frontend origins. Use `/docs` for the
  actual request/response schema.
- **Team:** provide the server-side Gemini key/model/quota, decide natural-language
  what-if execution scope, and confirm the DigitalOcean deployment/environment
  owner. Complete live integration testing before presenting real portfolio results.

## Tests

~~~powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
~~~

On macOS/Linux use `backend/.venv/bin/python` instead. Tests use temporary
databases and mocked Gemini responses; they do not require external services.
They cover persistence, snapshot matching, malformed input/provider output,
Gemini timeouts and malformed answers, evidence indices and compatibility routes.
Passing them does not verify a live Gemini key, market API, MongoDB or Tiger Data.

Main files: `api_v1.py` (routes), `schemas.py` (contracts), `storage.py`
(local persistence), `providers.py` (integration boundary), `gemini_service.py`
(Gemini adapter), and `prompts/` (versioned workflow instructions).

## Recovered data-layer drafts

Earlier Backend #1 files are preserved under [drafts/](drafts/README.md) for
team handoff. Those drafts contained a MongoDB proposal, not an implementation.
The current event lab separately implements `mongo_store.py`; v1 retains SQLite.
The draft Python modules are not imported by the API. See
[MongoDB handoff](docs/MONGODB_HANDOFF.md) for the two storage boundaries.

## Runtime state and deployment boundary

`analyst_mode` tells you whether Gemini is selected; `metrics.data_mode`
tells you whether the financial inputs are fictional or live. Gemini answering
a fictional fixture is still a demo. `status: complete` means the explanation
completed, not that live financial services are connected. Health also exposes
the current data mode, storage backend and authentication configuration.

`GET /health` keeps HTTP 200 for a running server but reports `status: degraded`
when required configuration is missing or the enabled event store failed to
initialize. `configuration_issues` lists
`AUTH_NOT_CONFIGURED`, `GEMINI_NOT_CONFIGURED` (in Gemini mode), and/or
`MARKET_DATA_NOT_CONFIGURED` (in Alpaca mode), plus
`EVENT_LAB_NOT_CONFIGURED` when the enabled lab lacks required configuration.
Whitespace-only keys do not count as configured. `analyst_ready`,
`market_data_ready`, and `authentication_enabled` describe nonblank configuration,
not successful vendor requests. Event readiness additionally requires the Mongo
store to have initialized during startup. A startup failure can therefore leave
`configuration_issues` empty while `status` is `degraded` and `event_lab_ready`
is false. Health does not probe vendors or recheck Mongo connectivity on each
request; it cannot confirm key validity, model access, quotas, or ongoing uptime.

The documented local command binds to loopback. Portfolio endpoints enforce
Supabase authentication and ownership. Market history and curated Research
summary endpoints remain public, and application quota rate limiting is not
implemented. The deployment owner should account for those public vendor calls.

SQLite needs persistent storage if used for a hosted demo. Do not assume an
ephemeral filesystem survives rebuilds or is shared across replicas. Confirm a
single-instance persistent volume for the main portfolio store. Event drafts
and runs use configured MongoDB; verify its deployment persistence separately.
Legacy Mongo-only portfolios require the reviewed import described in
[the unified release guide](../docs/unified-what-if-release.md).
## Investor ownership

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `backend/.env` to the same project used by frontend authentication. V1 also accepts a legacy `SUPABASE_ANON_KEY`; when it is set, that key takes precedence for v1 Supabase Auth requests. The backend validates Bearer tokens through Supabase Auth. New portfolios are owned by the authenticated user; legacy SQLite rows are retained with no owner and are not returned to investors. `/api/v1/portfolios` lists only the caller's portfolios. No Supabase service role secret is needed.

Updating a portfolio preserves its `portfolio_id`, `owner_id`, and original `created_at` and increments its revision. Current metrics and AI explanations reject stale revisions. Event drafts and runs retain their pinned allocation and price context across later edits. Legacy analysis rows are read only during the migration period and must be backed up before cleanup.

Market-history preflight and subsequent analysis reuse successful per-symbol daily price frames for 60 seconds. The cache obtains an analysis-length window even when preflight requests only two days, so the immediate analysis does not fetch those symbols again. Failed history requests are not cached. The cache lives in the API process; separate workers have separate caches.
