## 1. Expand the Backend Analysis Contract

- [x] 1.1 Define the dated portfolio and per-asset series, contribution, and aggregate metric fields required by the frontend.
- [x] 1.2 Extend backend schemas, quant report mapping, and saved snapshot serialization to preserve the new response fields and provenance.
- [x] 1.3 Add a validated market-history endpoint for supported symbols and requested lookback, returning aligned dates, series, and provenance.
- [x] 1.4 Add backend tests for complete series, unsupported symbols, null metrics, stale or short history, and demo provenance.

## 2. Build Shared Frontend API State

- [x] 2.1 Extend the typed API client for analysis retrieval, market history, what-if comparisons, and Ask Panda; retain weight conversion and safe API errors.
- [x] 2.2 Move active portfolio and saved analysis state into App and load the initial sample portfolio through the API.
- [x] 2.3 Make edit and apply flows create/analyze the new allocation and reject stale responses from superseded requests.
- [x] 2.4 Add accessible loading, error, retry, and unavailable states without silently substituting frontend calculations.

## 3. Connect the Workspaces

- [x] 3.1 Render Overview metrics, attribution, and charts from the saved backend analysis and its dated series.
- [x] 3.2 Render Risk contributions, volatility, and correlation data from the same analysis; preserve undefined values as unavailable.
- [x] 3.3 Submit What-if requests to the backend, render baseline/proposed/delta results, and mark comparisons stale after draft edits.
- [x] 3.4 Send Ask Panda questions with the active analysis ID and render answer status, citations, warnings, and disclaimer.
- [x] 3.5 Load Research asset price charts and comparisons from the market-history endpoint while keeping curated primers identified as editorial content.

## 4. Verify the Integrated Flow

- [x] 4.1 Add frontend tests for API payload conversion, app state transitions, stale requests, and backend error handling.
- [x] 4.2 Verify a portfolio can load, analyze, navigate across all workspaces, run What-if, and ask a question using the same analysis IDs.
- [x] 4.3 Verify demo source labels, short-history behavior, null metrics, keyboard access, and retry states across the affected views.
