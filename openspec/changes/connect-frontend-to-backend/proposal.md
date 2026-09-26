## Why

The frontend now has an API client and can request one demo analysis from Overview, but the visible dashboard still calculates its main metrics locally. Risk, Research, What-if, and Ask Panda also use frontend sample logic, so screens can disagree and backend capabilities are not part of the normal user flow. This change completes the UI-to-API connection while clearly labeling the backend's current fictional data.

## What Changes

- Keep the active portfolio and saved analysis in shared frontend state and use backend responses as the source for portfolio calculations.
- Extend analysis data to include the dated portfolio and asset series and metrics required by performance, risk, and research visualizations.
- Connect portfolio editing, risk and correlation views, asset history comparisons, What-if, and Ask Panda to the v1 API.
- Show data mode, provenance, warnings, and loading, error, and unavailable states consistently.
- Keep curated research primers as editorial content; do not present them as dynamically sourced market news.
- Keep the current backend demo provider in scope as the integration target, but do not add a live market-data vendor or claim the data is real.

## Capabilities

### New Capabilities
- `frontend-api-integration`: Shared backend-backed portfolio analysis and interactions across the frontend workspaces.

### Modified Capabilities
- None.

## Impact

- Frontend: `frontend/src/App.tsx`, `frontend/src/api/portfolio.ts`, Overview, Risk, Research, What-if, Ask Panda, and chart components.
- Backend API: `backend/api_v1.py`, `backend/schemas.py`, and provider/report mapping in `backend/providers.py` to return the series and analysis fields required by the UI.
- Quant integration: preserve the Python quant engine as the source of calculated portfolio results; expose its existing report series through the API.
- Tests: frontend API/state tests and backend response-contract tests.
- No new external market-data provider, storage service, or live-data claim is introduced.
