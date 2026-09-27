# PortfolioLens application API + Gemini

The backend owns the frontend API, input validation, analysis orchestration,
saved snapshots, Gemini prompts, and error handling. Market ingestion, Tiger Data,
MongoDB infrastructure and financial formulas belong to the data/quant teammates.
See [the shared HLD](../PortfolioLens-HLD.md) and [integration design](INTEGRATION.md).

The default provider connects the quant engine to fictional sample prices for an
offline demo. Real market data is optional and uses adjusted daily end-of-day prices from Twelve Data, not intraday quotes; see [setup guide](docs/TWELVE_DATA.md). Gemini is optional and needs a team API key.

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
[health](http://127.0.0.1:8000/health). Health confirms the API process/configuration,
not connectivity to Gemini, databases, or real quant services.

No environment file or API key is needed in default demo mode. Portfolios and
immutable analysis snapshots are stored in ignored `backend/data/portfoliolens.sqlite3`.
This local store is permitted by the HLD for the first demo; MongoDB integration
is still pending. There is no login or multi-user authorization in this starter.

## First frontend flow

Use the interactive docs' **Try it out** buttons:

1. `GET /api/v1/portfolios/demo` loads the seeded portfolio.
2. `POST /api/v1/portfolios/demo/analysis` creates a saved analysis. Copy its
   `analysis_id`.
3. `POST /api/v1/portfolios/demo/ask` with:
~~~json
{
  "analysis_id": "paste-the-returned-analysis-id",
  "question": "What is my biggest risk?",
  "web_search": false,
  "source_urls": []
}
~~~

The default answer has `status: "demo"` and explicitly labels the fixture as
fictional. It is a deterministic snapshot summary, not an arbitrary-question AI.
The seeded allocation is NVDA 30%, SPY 40%, JPM 20%, TLT 10%. Any valid allocation
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
| PUT | `/api/v1/portfolios/{id}` | Replace the authenticated owner's portfolio name and holdings; retains ID and creation time |
| GET | `/api/v1/portfolios/{id}` | Read saved portfolio |
| POST | `/api/v1/portfolios/{id}/analysis` | Validate provider output and save a snapshot |
| GET | `/api/v1/portfolios/{id}/analyses/{analysis_id}` | Read that snapshot |
| GET | `/api/v1/quotes?symbols=AAPL&symbols=MSFT` | Optional Alpaca IEX latest-trade snapshots; separate from daily portfolio analysis |
| POST | `/api/v1/portfolios/{id}/ask` | Explain exactly the selected saved snapshot |
| POST | `/api/v1/portfolios/{id}/what-if` | Compare saved and proposed holdings on the selected market-data history |
| POST | `/api/v1/portfolios/{id}/briefing` | Write a briefing from one saved analysis |
| POST | `/api/v1/portfolios/{id}/risk/explanation` | Explain risk using one saved analysis |
| POST | `/api/v1/portfolios/{id}/what-if/explanation` | Recalculate and explain a proposal against a saved analysis |
| POST | `/api/v1/research/{symbol}/summary` | Summarize the allowlisted issuer source for a supported symbol |

Holdings use `{"symbol":"NVDA","weight":0.3}`. Weights are finite long-only
decimals and must sum to 1 (tolerance 1e-10). Duplicate symbols are rejected
after normalization. We never silently rescale inputs.

V1 errors use `{"error":{"code":"...","message":"..."}}`. Input errors are
422, missing objects 404, pending quant integration 501, and provider errors 502.
AI failures on Ask Panda and the contextual workflow routes return HTTP 200
with `status: "unavailable"`, an `error_code` when available, and warnings.
Saved metrics or the selected Research source remain accessible. Quant-provider
failures on What-if routes still use HTTP errors. The frontend must check
`status`; HTTP 200 does not imply that an AI explanation succeeded.

Every application response includes a server-generated `X-Request-ID`.
V1 errors also include `error.request_id`. Provider, storage, AI and unexpected
failures emit JSON logs with that ID, error code, exception type and stack
locations. Raw exception messages, prompts, credentials and upstream payloads
are not logged. CORS exposes the ID header so the frontend can report it.

The initial `/api/portfolios/{id}/analytics`, `/api/analyst` and
`/api/what-if` routes remain deprecated compatibility routes. They retain their
`detail` error envelope and older AI error HTTP statuses. New frontend work
should use v1.

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
| GEMINI_FALLBACK_MODEL | `gemini-3.5-flash-lite`; tried after a failed Gemini response. Set empty to disable. |
| GEMINI_TIMEOUT_SECONDS | 45 per model; maximum 120 |
| CORS_ORIGINS | Comma-separated frontend origins; localhost ports 3000 and 5173 |
| STORAGE_PATH | Optional override for the SQLite file |
| ALPACA_API_KEY / ALPACA_API_SECRET | Optional server-side credentials for real-time IEX quote snapshots; never expose them to the frontend |

The Overview's optional live-price strip polls `/api/v1/quotes` every 15 seconds.
It uses Alpaca's free IEX feed, which covers one exchange rather than consolidated
US market activity; it is labeled IEX and is not used by the quant engine or
saved risk metrics. A successful free API call does not itself establish public
display rights: verify Alpaca's applicable market-data agreements before showing
prices to judges or other users. When keys are absent or the vendor is unavailable,
the strip reports quotes as unavailable; it never substitutes sample prices.

All Gemini-backed actions use one server-side adapter with a versioned,
workflow-specific prompt and JSON response schema. The primary model has a
bounded timeout and at most two HTTP attempts. If it fails or returns an invalid
response, the adapter tries the configured fallback model with the same prompt,
context, validation, and timeout. The fallback is skipped in demo mode, without
an API key, or when its model name matches the primary. An exhausted fallback
returns the existing safe partial response; sequential attempts can take up to
twice `GEMINI_TIMEOUT_SECONDS`. Each action receives only its scoped context:
Ask Panda gets its selected snapshot and explicitly requested web inputs;
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

**Tool access is workflow-scoped.** Ask Panda has no web tools by default;
explicit `web_search: true` enables Google Search and URL Context, and explicit
`source_urls` enable URL Context alone. Briefing, Risk, and What-if use no web
tools. Research enables URL Context only, for the hardcoded official issuer URL
selected in the Research page; it does not use Google Search. Research does not
crawl pages in the background. Choose a model supporting structured output and
the URL Context tool.

The response includes `sources`, `grounding_supports`, `url_retrievals` and
`search_suggestions_html`. Preserve source array order: grounding indices refer
to it. Text offsets refer to `grounding_text` (the original JSON model response),
**not** the parsed `answer`. The frontend must handle Google's
[search display requirements](https://ai.google.dev/gemini-api/docs/generate-content/google-search)
and [URL retrieval status](https://ai.google.dev/gemini-api/docs/generate-content/url-context).

Enabling Gemini does not enable live prices. Quant calculations run through the
provider before any scenario explanation. The explanation route cannot apply or
save proposed holdings; the existing explicit frontend confirmation remains the
only way to apply a scenario to the current browser session. Daily P&L
attribution and natural-language execution of what-if calculations remain
unsupported.

## Team integration checklist

- **Quant (Nel A):** `EngineQuantProvider` calls both public functions. The adapter
  handles output fields, undefined values, correlation roundoff, weight precision
  and what-if asset unions. Formulas remain unchanged in the quant module.
  `DemoQuantProvider` remains available only for precomputed-fixture regression tests.
- **Data/infrastructure (Vincent):** supply normalized adjusted-close price access,
  source/freshness metadata, and the MongoDB portfolio/snapshot adapter. Agree on
  where the API invokes data loading before calling the quant function. Live
  snapshots require a timezone-aware market timestamp, observation count and source.
- **Frontend (Meirzhan):** agree on v1 payloads, analysis IDs, null metrics, partial
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
(Gemini adapter), `prompts/analyst.txt` (versioned instructions).

## Recovered data-layer drafts

Earlier Backend #1 files are preserved under [drafts/](drafts/README.md) for
team handoff. MongoDB was only a proposed design plus a dependency; no working
MongoDB adapter existed to restore. The drafts are not imported by the API.
See [MongoDB handoff](docs/MONGODB_HANDOFF.md) for the existing storage interface
and remaining work. SQLite remains the active local store.

## Runtime state and deployment boundary

`analyst_mode` tells you whether Gemini is selected; `metrics.data_mode`
tells you whether the financial inputs are fictional or live. Gemini answering
a fictional fixture is still a demo. `status: complete` means the explanation
completed, not that live financial services are connected. Health also exposes
the current data mode, storage backend and authentication status.

The documented local command binds to loopback. The starter does not implement
authentication, ownership checks or quota rate limiting. It is not ready for
unrestricted public access. Before a shared deployment, agree on a protected
demo environment or implement authentication/access controls and request limits.

SQLite needs persistent storage if used for a hosted demo. Do not assume an
ephemeral filesystem survives rebuilds or is shared across replicas. Confirm a
single-instance persistent volume or complete the team's MongoDB adapter before
claiming durable shared persistence. See the rollout gates in
[INTEGRATION.md](INTEGRATION.md).
# Investor ownership

Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `backend/.env` to the same project used by frontend authentication. The backend validates Bearer tokens through Supabase Auth. New portfolios are owned by the authenticated user; legacy SQLite rows are retained with no owner and are not returned to investors. `/api/v1/portfolios` lists only the caller's portfolios. No Supabase service role secret is needed.

Updating a portfolio preserves its `portfolio_id`, `owner_id`, and original `created_at`. When its allocation changes, saved analyses for that portfolio are deleted in the same SQLite transaction. Old analysis IDs then return 404; the client creates a fresh analysis for the new allocation. An analysis computed before an update cannot be saved afterward.

Market-history preflight and subsequent analysis reuse successful per-symbol daily price frames for 60 seconds. The cache obtains an analysis-length window even when preflight requests only two days, so the immediate analysis does not fetch those symbols again. Failed history requests are not cached. The cache lives in the API process; separate workers have separate caches.
