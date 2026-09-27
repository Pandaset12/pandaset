## Context

The standard workspace stores user-entered portfolio symbols and weights in v1 SQLite. `Application.loadAnalysis()` posts the selected portfolio to `/api/v1/portfolios/{id}/analysis`; `EngineQuantProvider` uses the configured sample or Alpaca historical-price provider and saves the resulting snapshot. Overview renders that response. A separate authenticated `/api/v1/quotes` request already supplies Alpaca IEX latest trades for the quote strip. The migration change `replace-twelve-data-with-alpaca` established these backend paths but deliberately left sample history as the default; its live account check remains outstanding.

Overview still says “sample” in several places for every mode. Unknown holdings receive a sample-only description, and a technology allocation tile counts only NVDA, MSFT, AAPL, and AMD. The VTI overlay comes from `analysis.series.asset_index.VTI`, which exists only when VTI is in the saved portfolio. Curated research notes are editorial content selected by matching holding symbols.

## Goals / Non-Goals

**Goals:**

- Show modeled returns, chart, risk, and contributions calculated from the selected user's saved symbols and exact allocation weights using Alpaca adjusted daily history when that provider is configured.
- Make the historical source, feed scope, as-of date, and modeled nature of those results clear; keep latest IEX trades visibly separate.
- Make every Overview metric and fallback holding description truthful for arbitrary supported user-entered symbols.
- Preserve explicit sample-mode labeling and existing unavailable states.

**Non-Goals:**

- Fetch Alpaca data directly from the browser or store credentials there.
- Sync Alpaca brokerage accounts, positions, trades, cost basis, or actual investment P&L.
- Use intraday quotes in historical return/risk calculations, add a new benchmark feed, or turn curated notes into live news.
- Rebuild the historical provider or change its feed/adjustment rules from `alpaca-adjusted-history`.

## Decisions

### Reuse the existing backend analysis boundary

The Overview continues to consume `AnalysisResponse` from the saved user portfolio. Deployment selects `MARKET_DATA_PROVIDER=alpaca` with server-side key, secret, and explicit `ALPACA_HISTORY_FEED`; local/demo mode may keep `sample`. The UI derives historical state from `data_mode`, `data_quality.source`, `data_quality.freshness`, `data_quality.warnings`, and `as_of`. Feed information is shown from the provider's existing human-readable provenance warning in Analysis details; no logic parses that text. This avoids a second data path and a response/storage migration. An additive structured feed field can be proposed separately if the feed must drive UI behavior.

Alternative considered: have Overview call Alpaca itself or recalculate from the latest quote strip. That would expose credentials or mix point-in-time trades with adjusted daily returns.

### Match copy to the actual data source

Use “sample” only for `data_mode=demo`. For Alpaca analysis, label the chart and metrics as modeled from adjusted daily history through the `as_of` session date; retain the separate “Latest available prices · Alpaca IEX” strip. Avoid “live portfolio value” and “realized return.” The header badge distinguishes sample history from market history rather than suggesting intraday recalculation.

Alternative considered: retain the existing `LIVE DATA` badge and add a footnote. It leaves the most prominent label ambiguous next to a frequently refreshed quote strip.

### Use user-portfolio-derived generic metrics

Replace the fixed technology allocation tile with a metric calculated from `analysis.weights`, such as the largest holding and its allocation. Keep the portfolio's entered weights as the only quantitative allocation source. For unknown tickers, show a neutral symbol/name and sector placeholder; omit the false sample-history description. Keep curated “On your radar” notes explicitly editorial and show only notes matching holdings.

Alternative considered: infer sector classification or company fundamentals from price bars. Alpaca historical bars do not contain that metadata, so the inferred tile could misstate arbitrary tickers.

### Keep the benchmark conditional

Render the VTI secondary line only when `analysis.series.asset_index.VTI` is present and aligned. Do not request VTI merely to populate a comparison visual. The primary portfolio index remains available without VTI.

Alternative considered: fetch VTI independently for every Overview. That adds rate-limit load, alignment questions, and a product decision about benchmark selection.

## Risks / Trade-offs

- [Sample and Alpaca values appear together] → Derive all historical labels from the selected analysis; keep the IEX quote strip isolated and labeled.
- [An unsupported user ticker lacks full Alpaca history] → Reuse explicit coverage errors and prevent creation of a misleading analysis or fallback to fictional prices.
- [Unknown tickers lack sector/name metadata] → Display the entered symbol neutrally and avoid unsupported sector claims.
- [Many visible Overview tabs consume quote quota] → Retain visibility-aware polling/backoff, evaluate expected concurrency against the account limit during rollout, and avoid unapproved quote retention.
- [Account entitlement, feed coverage, or display rights are unknown] → Keep market-backed release gated on the existing opt-in live check and rights review.

## Migration Plan

1. Update Overview and shared holding/source presentation; keep sample mode working for local/demo use.
2. Add frontend and API-level tests for user-specific allocations, Alpaca versus sample provenance, missing/partial history, quote separation, and arbitrary tickers.
3. Configure Alpaca only through the deployment's server-side environment. Run the existing opt-in history check with rotated credentials and confirm the chosen feed, coverage, quota, and applicable display/retention rights before enabling vendor-backed Overview use.
4. Roll back by selecting sample mode and clearly labeling new sample analyses; leave previously saved analyses readable with their original provenance.

## Open Questions

- Whether the product later needs an independent market benchmark for portfolios that do not hold VTI. This proposal leaves that comparison absent.
- Expected concurrent Overview viewers and the corresponding quote-polling budget for the chosen Alpaca plan.
