# API and Gemini integration update

## Quant integration on quant-backend-integration

The default `EngineQuantProvider` now calls `analyze_portfolio()` and
`compare_portfolios()`. It reads the existing
`drafts/data_pipeline/sample_prices.json` fixture: seven fictional daily price
rows for NVDA, SPY, JPM and TLT. All results carry `data_mode=demo`,
`data_source=synthetic_fixture`, unknown freshness, and an explicit fictional-price
warning. UTC midnight represents the sample session date, not a market close.
No live data service is called.

The adapter explicitly maps cumulative return, annualized portfolio/asset
volatility, signed risk shares, correlations, observation count and end date.
Quant warnings and assumptions survive snapshot persistence. Null risk shares
and correlations remain null; numeric citations exclude nulls. Weight tolerance
is 1e-10 with no renormalization. Correlation validation allows 1e-10 roundoff
without clipping values.

What-if resolves the saved portfolio, fetches the union of symbols once, and
zero-fills absent weights only. Both reports use identical prices. It returns
`current_analysis` and `proposed_analysis` as AnalyticsSnapshot payloads, with
`delta.portfolio_return` and `delta.portfolio_volatility` taken from the engine's
proposed-minus-baseline differences. Comparisons do not change or save holdings.
Unsupported sample symbols fail as provider errors (502).

To switch to real history, replace the sample loader and its demo-specific
provenance mapping with a verified adjusted-close adapter supplying complete,
aligned history for every requested symbol, source/freshness and agreed session
timestamp semantics. The draft market provider is not activated or verified;
credentials, plan coverage and an end-to-end real-history acceptance run remain
outstanding. Changing the data-mode label alone is insufficient.

Install dependencies from the repository root with `pip install -r
backend/requirements-dev.txt`; this also installs the local quant package.
Run `python -m pytest backend/tests -q` and
`python -m pytest quant_engine/tests -q` using that environment.

The design and review notes below describe the pre-integration baseline; the
status above supersedes their pending-quant statements.

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
- api_v1.py: portfolio creation/read, analysis creation/read, what-if and ask routes.
  V1 errors use error.code/message. Legacy error envelopes stay compatible.
- gemini_service.py and prompts/analyst.txt: bounded calls, a validated JSON
  qualitative explanation and cited metric identifiers. The backend renders numeric
  facts and rejects numeric model prose. Citation values come from the snapshot,
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

## Interface decisions and rollout gates

Quant functions now exist: `analyze_portfolio(prices, weights, **options)`
and `compare_portfolios(prices, baseline_weights, proposed_weights, **options)`.
See docs/QUANT_REVIEW.md for their tested contract and reproducible mismatches.
They are not wired into this branch yet.

Proposed call ownership to confirm with the team:
1. The application orchestration/provider asks Backend #1 for adjusted prices,
   aligned dates and provenance for the portfolio's symbol set.
2. The application calls the pure quant Python module with those prices and
   validated weights; the quant module never fetches data or writes databases.
3. The application validates/maps the report, then saves an immutable snapshot
   through the shared portfolio store. Gemini reads only that saved snapshot.
4. For what-if, obtain the union of symbols and a common observation window,
   add zero weights for absent holdings, then map the comparison result to the
   frontend contract. Do not fill missing prices.

Storage is still SQLite. The recovered MongoDB material is only an inactive
design/dependency draft; docs/MONGODB_HANDOFF.md lists the store methods to
implement. Do not equate configuration placeholders with a connected database.

Before a shared/public rollout, confirm:
- Single-instance SQLite with a persistent volume, or a tested MongoDB adapter.
- Authentication/portfolio ownership and quota limits, or a protected demo
  environment with restricted access. No such access controls are implemented
  by the application yet.
- Frontend handling of demo/live data mode, explanation status, nullable
  metrics, request IDs and source metadata.
- A real custom-portfolio -> quant analysis -> persistent snapshot -> Gemini
  acceptance run, including mismatched-number rejection and upstream outages.

Current request IDs and safe structured error logs support diagnosis; they are
not a substitute for authentication, persistence or upstream integration.
