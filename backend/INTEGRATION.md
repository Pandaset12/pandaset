# API and Gemini integration update

## HLD

Goal: implement the API contract in PortfolioLens-HLD.md with a reproducible
offline demo and a testable Gemini boundary.

Flow: validated holdings -> portfolio store -> provider -> saved analysis ->
question with analysis_id -> Gemini or explicit fallback. A question reads the
specified snapshot, so it does not fetch prices or recalculate risk.

Use SQLite for the local demo because it is included in Python and survives
restarts. MongoDB and the team's quant/data modules remain external integration
work. Do not introduce a second financial calculation engine or invent missing
returns, correlations, or timestamps.

Keep the initial /api routes as deprecated compatibility endpoints. New frontend
work uses /api/v1. Document additive fields and unavailable metrics explicitly.

## LLD

- schemas.py: validate normalized holdings, totals, snapshot provenance and API
  responses. Weights are decimals; risk contributions are relative volatility
  contributions and may be negative.
- storage.py: parameterized SQLite queries for portfolios and immutable analysis
  snapshots. Lookups require both portfolio_id and analysis_id.
- providers.py: analyze(Portfolio) is the replacement boundary for the team's
  synchronous Python quant/data modules; sync calls run in FastAPI's thread pool.
  Cache only the static fixture and return deep copies.
- main.py: portfolio creation/read, analysis creation/read, what-if and ask routes.
  V1 errors use error.code/message. Legacy error envelopes stay compatible.
- gemini_service.py and prompts/analyst.txt: bounded calls, a validated JSON
  answer and cited metric identifiers. Citation values come from the snapshot,
  not the model. Preserve source indices and original grounding text.

The analysis response uses the HLD field names. Unknown portfolio_return,
asset_volatility, correlation_matrix, observation_count and as_of are null.
Additional portfolio_id, created_at, weights, data_mode, units and assumptions
make the demo's provenance explicit. An ask response includes the HLD's answer,
citations and disclaimer plus status, metrics, warnings and web evidence.

Failure behavior: validation 422, missing portfolio/snapshot 404, unavailable
quant integration 501, provider failure 502. AI failures return a successful
partial response with status=unavailable and the saved metrics; they never
silently switch to fabricated calculations. A custom allocation cannot reuse
the demo's fixture values.

Validation: portfolio -> analysis -> ask flow; persistence across app restarts;
snapshot/portfolio matching; duplicate and invalid weights; malformed provider
data; missing metric citations; Gemini timeout/invalid output; source indices;
and existing legacy tests. Live Gemini remains unverified without credentials.
