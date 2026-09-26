# API/search verification - 2026-09-26

Scope: Backend application API and Gemini search fixes, integrated with the
team's uploaded shared AI workflows at 78f9aa2. Python 3.12 on Windows.
The review branch is backend-v3-gemini-search.

## Executed checks

- Backend regression suite: **114 passed**.
- Python quant-engine suite: **83 passed**; financial formulas are unchanged.
- Frontend/API client and TypeScript quant tests: **19 passed**.
- Production TypeScript/Vite build: passed.
- Python dependency consistency: passed.
- Real local Uvicorn HTTP smoke: portfolio creation (201), quant analysis,
  saved analysis retrieval, offline ask, and what-if (200), unknown portfolio
  (404), and trailing-dot local URL rejection (422). OpenAPI declares the Ask
  search default as true.
- The teammate's shared AI branch was also checked separately before combining
  the changes: its 74 backend tests passed.
- The live verifier's CLI and missing-key preflight were exercised. No key was
  configured, so it stopped without making a Gemini request.

The backend suite emits one upstream Starlette/httpx deprecation warning.

## What the automated tests establish

An Ask request that omits web_search passes Google Search and URL Context to
the shared SDK adapter alongside the JSON output schema. Explicit false passes
neither tool unless source_urls are provided, in which case URL Context alone
is enabled. Other workflow tool permissions are unchanged.

Regression tests cover trailing-dot local/private hostnames, Unicode dot
normalization, IP literals, credentials, and malformed empty hostname labels.
They also check the actual v1 route before the SDK boundary, immutable snapshot
metrics, unavailable responses on SDK failure, and preservation of source
indices, retrieval status, search queries and search display metadata.

These are mocked SDK tests. They do not prove that Google accepted a live
request or returned usable grounding.

## Live verification still pending

No configured Gemini key was available during this review. We have **not**
verified status=complete, real grounding sources/supports, actual Google Search
queries, successful URL retrieval, or the intentional invalid-model failure
against the team's Google account.

Run the opt-in verifier after configuring backend/.env:

~~~powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.verify_gemini_live --output backend/data/live-search-report.json
~~~

It starts its own API processes and temporary database, creates a demo analysis,
and tests default search, opt-out, explicit URLs with and without search, and an
upstream failure. See README.md for evidence expectations and exit codes. Review
the returned source/support records and answer text; HTTP 200 alone is not a pass.

## Team handoff

- Gemini: provide the local server key, confirm model/quota, run and inspect the
  live verification report. Keep credentials out of Git and chat.
- Frontend: Ask Panda already calls the API, but its current chat component does
  not render the returned search grounding or Google's search suggestions.
  Connect those displays and respect grounding_text offsets before presenting
  grounded answers as a finished feature.
- Data/infrastructure: the active price provider still reads fictional samples.
  Real adjusted historical prices, freshness/source metadata, MongoDB and Tiger
  Data remain unconnected. Coordinate ownership before replacing that provider.
- Deployment: hosted persistence and access controls remain team rollout work.

This report supersedes the older scaffold verification: quant and frontend API
integration now exist, and Ask search now defaults on. Live market data and live
Gemini/search validation must still be reported separately.
