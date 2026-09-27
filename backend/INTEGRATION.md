# Current API integration contract

This describes the integrated backend after the quant, Twelve Data, and Supabase
portfolio-persistence and event-lab changes on main. The older findings in
[QUANT_REVIEW.md](docs/QUANT_REVIEW.md) are historical, not pending implementation.

## V1 request flow

1. Supabase verifies the request's Bearer token and supplies the investor ID.
2. The API reads that investor's portfolio from SQLite. Another investor's ID
   returns 404, including on legacy portfolio routes.
3. `EngineQuantProvider` reads aligned daily prices from the selected provider
   and invokes the pure Python `analyze_portfolio()` function.
4. The API validates portfolio identity, weights, units, provenance, and quant
   output, then atomically saves a snapshot if the allocation is still current.
5. Ask, Briefing, and Risk read the requested saved analysis. Gemini explains
   those metrics; it does not replace the calculated values or save holdings.

What-if obtains one common price history for the saved/proposed symbol union and
calls `compare_portfolios()`. The API accepts at most eight symbols across that
union. Comparison does not mutate holdings; saving an edit is a separate
owner-authenticated PUT. If the allocation changes, the store atomically deletes
old analyses. A concurrent stale analysis save returns 409.

## Prices and quantitative output

`MARKET_DATA_PROVIDER=sample` uses the fictional JSON price fixture through the
real quant engine. `MARKET_DATA_PROVIDER=twelvedata` uses
`TwelveDataPriceProvider` with a server-side key and adjusted daily closes.
Vendor errors never silently switch to sample data. See
[Twelve Data setup](docs/TWELVE_DATA.md) for coverage and deployment requirements.
The inactive `DemoQuantProvider` serves precomputed legacy regression fixtures;
it is not the application's default provider.

The adapter preserves nullable correlations/risk shares, signed risk
contributions, source, session dates, observation counts, warnings, and
assumptions. Weights must sum to one within 1e-10 and are not renormalized.
UTC midnight is a historical session label, not an exchange closing instant.
Daily historical analytics are not actual brokerage P&L or news attribution.

Successful per-symbol histories are cached for 60 seconds in the API process.
Preflight and immediate analysis reuse an analysis-length window. Failures are
not cached; workers do not share this cache. Tiger Data is not connected.

## Optional live quotes

`GET /api/v1/quotes` verifies the investor's Supabase session and requests Alpaca
IEX snapshots for up to 25 symbols. Both `ALPACA_API_KEY` and `ALPACA_API_SECRET`
stay on the backend. This display-only feed does not replace Twelve Data history,
recalculate risk, or change saved analyses. Quote timestamps identify the last
trade; they are not the portfolio analysis date.

Missing credentials return 503/`ALPACA_NOT_CONFIGURED`, and the frontend hides
the optional strip and stops polling until it remounts. Provider failures return
safe 502 errors without falling back to sample prices. Missing optional Alpaca
keys do not degrade the core `/health` result; validate quotes separately with
the read-only check documented in [README.md](README.md).

## Storage and identity

Supabase Auth provides identity. V1 stores portfolios and analysis snapshots in
SQLite. Configure the frontend and backend for the same Supabase project. V1
uses a nonblank legacy anon key when configured, otherwise the publishable key.
No service-role key is required. Legacy demo/unowned rows are preserved but never
assigned to a signed-in investor. The initial `demo` ID is not a usable personal
portfolio.

SQLite must use a persistent volume for a hosted v1 instance; those records are
not shared across independent instances. V2 separately implements owner-scoped
MongoDB portfolios, analyses, scenario jobs, and chat in `mongo_store.py`.
Enabling the event lab does not migrate or expose existing v1 portfolios through
v2. The storage boundaries and potential v1 migration requirements are listed in
[MONGODB_HANDOFF.md](docs/MONGODB_HANDOFF.md).

## V2 event lab

The gated `/api/v2` routes preserve Supabase token verification, the internal
user allowlist/public-release gates, adjusted Twelve Data inputs, Mongo-backed
jobs and snapshots, and the event worker. Scenario research uses Tavily and
DeepSeek; Gemini proposes assumptions and explains quant-engine results.
See [README.md](README.md#authenticated-event-lab-apiv2),
[the v2 contract](../docs/event-lab-api-contract.md), and
[release gates](../docs/event-lab-release-gates.md) for setup and acceptance.

## V1 Gemini boundary

Portfolio explanations are qualitative text plus exact metric IDs. The backend
rejects unknown IDs and numeric prose, then renders numeric facts from the saved
snapshot or comparison. This guard does not prove qualitative accuracy or detect
every possible numerical paraphrase. Tests cover malformed output, invented
numbers, timeouts, model fallback, and safe unavailable responses.

Ask uses no web tools by default. Explicit `web_search: true` enables Search and
URL Context; explicit `source_urls` enables URL Context alone. Briefing, Risk,
and What-if use their calculated context without web tools. Research summarizes
an allowlisted issuer source using URL Context and requires successful retrieval.

`ANALYST_MODE=demo` returns a labelled offline response. In Gemini mode a failed
call returns `status: unavailable`; HTTP 200 alone is not AI success. Numeric
citations refer to backend facts; external evidence retains the original source
indices and raw grounding text. Ask cannot execute trades, change holdings, or
run a natural-language What-if request.

## Readiness and verification

Health reports missing auth configuration and missing credentials for selected
Gemini/Twelve Data modes. An enabled lab with missing settings adds
`EVENT_LAB_NOT_CONFIGURED`; whitespace-only credentials are missing. Event
readiness also requires successful event-store initialization during startup.
If that initialization fails, status remains degraded even when every credential
is present and `configuration_issues` is empty. V1 can still serve requests.
No vendor calls, fresh Mongo pings, key validation, model-access checks, or quota
checks run from `/health`.
Use [README.md](README.md) for authenticated request examples and configuration.
Use [VERIFICATION.md](VERIFICATION.md) for the tested scope and remaining live checks.

Before the shared demo, verify a real signed-in user's create/edit -> analysis ->
snapshot -> AI explanation -> reload flow in the configured deployment. Check
`data_mode`, dates, sources, and AI `status`, plus explicit upstream failures.
Market history and Research summaries are public routes; application rate limits
are still absent. The deployment owner must account for vendor capacity and
persistent storage. Passing mocked tests is not proof of live credentials.
