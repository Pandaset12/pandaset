# Review verification - 2026-09-26

Scope: Backend #2 application API and Gemini adapter on Windows / Python 3.12.14.

Verified:
- Installed the declared dependencies in a fresh virtual environment.
- `python -m pytest backend/tests -q`: **50 passed** in the existing environment
  and the fresh environment.
- `python -m pip check`: no broken requirements.
- Python compilation completed successfully.
- Started a real Uvicorn process in the fresh environment with an isolated database.
  Health, interactive docs and OpenAPI returned 200. Creating a portfolio returned
  201; analysis creation, saved-analysis retrieval and demo ask returned 200.
  Unsupported what-if returned 501; an unknown portfolio returned 404.
- The smoke process was stopped after testing; it used a separate port and did
  not replace any existing local server.

The test runner emits one upstream Starlette/httpx deprecation warning. It does
not fail the tests.

Not verified: live Gemini responses/search, live market data, the team quant
module, MongoDB, Tiger Data, hosted deployment, or frontend-to-backend integration.
Gemini boundary tests use mocked SDK responses. The default analytics are
explicitly fictional fixture values.

The remote `codex/frontend` branch currently uses local sample calculations and
canned chat replies. Connecting it to v1 and reconciling the demo allocations
remains team integration work. Frontend weights are percentages (30); API weights
are decimals (0.30). Convert them at the frontend API boundary.

## Quant review and recovered-draft follow-up

The isolated quant-engine checkout at 500c77c passed all 83 tests with NumPy
2.5.3 and pandas 3.0.6. This does not mean it is integrated into this API.
Compatibility probes reproduced issues documented in docs/QUANT_REVIEW.md.

The restored draft fixture reader loaded 28 fictional daily bars across four
symbols, with timezone-aware dates and consistent price metadata. This smoke
check did not call the live provider or either database. The backend test suite
was rerun after restoring the inactive drafts.

## Review fixes

Search now defaults off. Gemini returns qualitative prose plus metric IDs;
numeric facts are rendered by the backend. Regression tests reject fabricated
numeric prose despite a valid citation, test explicit versus default web tools,
and verify safe fallbacks. Qualitative answer accuracy still requires live QA.

Response request IDs correlate with structured error logs. Tests cover provider
and unexpected failures, validation responses, unique IDs, CORS visibility and
omission of secret-bearing exception messages. Access control, hosted storage
and the real quant/data provider remain unimplemented integration work.
