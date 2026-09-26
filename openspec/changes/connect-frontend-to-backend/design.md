## Context

The frontend currently has a typed client that creates a portfolio and requests an analysis. Overview exposes this as an optional demo-analysis card, while its main metrics and chart still use quant/analytics.ts. Risk, What-if, Research price charts, and Ask Panda also calculate or answer from frontend sample data. The backend already exposes portfolio, analysis, what-if, and ask endpoints and calls the Python quant engine. Its analysis response contains summary fields but no dated series, and all price inputs still come from the fictional fixture.

The goal is to complete frontend/API integration against the current demo provider. This change does not add real market data, a new vendor, or public multi-user access. All demo values must remain visibly labeled as demo data.

## Goals / Non-Goals

**Goals:**
- Make one active backend portfolio and its immutable saved analysis the shared source for portfolio metrics across routes.
- Return enough dated portfolio and asset series for charts and historical comparisons to use backend results.
- Connect portfolio editing, risk, what-if, Ask Panda, and Research market-history views to the v1 API.
- Preserve source, freshness, warnings, nullable metric behavior, and explicit demo labeling in the UI.
- Give each API-backed view loading, error, empty, and unavailable states.

**Non-Goals:**
- Replace the fictional sample prices with a real provider. That needs a separate provider and data-rights decision.
- Add Tiger Data, MongoDB, authentication, account ownership, or portfolio sharing.
- Replace editorial research primers or issuer links with generated news or fundamentals.
- Change the Python quant formulas or make calculations in the browser authoritative.

## Decisions

### Keep API access in a typed frontend client

Extend frontend/src/api/portfolio.ts with typed functions for portfolio creation, analysis, what-if, ask, and requested market-history series. Keep percentage-to-decimal conversion at this boundary. Parse the API error envelope into a user-safe error type that retains status and request ID when present.

**Alternative considered:** call fetch from each page. Rejected because it duplicates request, unit conversion, and error handling and makes response changes harder to coordinate.

### Store the active portfolio and analysis in app-level state

App.tsx owns the active portfolio, latest saved analysis ID, analysis payload, pending state, and error state. On startup it creates/analyzes the sample portfolio. Applying an edit or scenario creates a portfolio for the new allocation and obtains a new immutable analysis. A monotonically increasing request token (or abort signal) prevents an old response from replacing newer state.

**Alternative considered:** maintain separate page-local analyses. Rejected because navigation could display mismatched snapshots or weights.

### Extend the backend analysis contract with display series

Add an explicit series object to the saved analysis response: session dates, portfolio cumulative value normalized to 1, per-asset cumulative values, and any return attribution series required by existing Overview charts. Expose required overview metrics such as annualized return and maximum drawdown from the quant report. Preserve analysis_id, weights, data mode, source, freshness, warnings, assumptions, and nullable metrics. Store this data in the same immutable snapshot so Ask Panda, retrieval, and the UI refer to identical analysis inputs.

Add a market-history response for requested supported symbols and lookback, with the same dates, normalized asset series, and provenance fields. This supports Research comparisons for assets outside the active portfolio. The demo adapter may serve its current fixture; the response must continue to say demo and synthetic_fixture.

**Alternative considered:** leave charts on frontend calculations while moving only headline metrics. Rejected because it would preserve two different calculation sources in one view.

### Adapt screens by responsibility

- Overview uses the active saved analysis for headline metrics, holdings contributions, and dated portfolio/benchmark series.
- Risk uses backend risk contributions, per-asset volatility, and correlation values. Null values render as unavailable rather than zero.
- What-if calls the existing compare endpoint, renders current/proposed reports from that response, marks results stale after draft edits, and creates a new active portfolio/analysis only when the user applies the scenario.
- Ask Panda sends the active analysis_id and question to the API. It displays demo, complete, and unavailable states, citations, and warnings from the response.
- Research keeps its editorial primers and issuer links, while price charts/comparisons use the market-history API and current backend provenance.

### Do not silently revert to local analytics

If the API is unavailable, show an actionable error or unavailable state. Do not fill an API failure with local TypeScript metrics under the same labels. Static editorial content may remain available. The global data badge and analysis details are derived from backend provenance when an analysis is loaded.

## Risks / Trade-offs

- [The current fixture has only a short history] → Keep demo warnings visible; represent requested ranges beyond available dates as unavailable and do not extrapolate.
- [Series increase response size] → Return only the requested symbol set and window; do not include raw OHLC fields unless a view needs them.
- [Saved portfolios and analyses accumulate in SQLite] → Reuse the active portfolio within a session where possible; edits that require a new immutable portfolio create a new record. Add retention only if actual usage requires it.
- [The Research page covers symbols outside the current portfolio] → Add a separate validated market-history read for the supported symbol universe rather than attaching unrelated symbols to portfolio weights.
- [Gemini may be unconfigured or fail] → Render the backend's partial metrics and unavailable status; never fabricate a successful answer in the UI.

## Migration Plan

1. Extend backend response schemas and mapping while preserving existing response fields and routes.
2. Add frontend client methods and tests against the documented response contracts.
3. Move screen data consumption to shared app-level backend state and connect What-if and Ask endpoints.
4. Verify all routes against the local backend with the demo fixture and clearly labeled provenance.

Rollback is a code revert. No database migration is required because analysis snapshots are JSON payloads; older snapshots may lack series and must be treated as incomplete/unavailable by the updated UI rather than interpreted as empty data.

## Open Questions

- Which sample window should the app request by default once a real provider is selected? Until then, use the complete available demo fixture and disclose its short history.
- Should Ask Panda use the API's current configured mode (demo by default) or should this frontend integration require Gemini to be enabled? The UI must support both regardless.
- The existing account-value display is illustrative and not returned by the API. Keep it clearly labeled as a sample balance, or remove it from backend-backed performance views until user-provided account value is designed.
