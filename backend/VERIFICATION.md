# Review verification - 2026-09-26

Scope: Backend #2 application API and Gemini adapter on Windows / Python 3.12.14.

Verified:
- Installed the declared dependencies in a fresh virtual environment.
- `python -m pytest backend/tests -q`: **41 passed** in the existing environment
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
