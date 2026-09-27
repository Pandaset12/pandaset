## Context

The v1 provider switch in `backend/providers.py` chooses fictional sample prices or `TwelveDataPriceProvider` for analysis, market history, and allocation What-if. The gated v2 event lab constructs `TwelveDataPriceProvider` at startup, fetches 252 aligned return observations for holdings and SPY/TLT/GLD, and pins those prices into each saved analysis. Event runs use the pinned snapshot. `backend/alpaca_quotes.py` already supplies a separate IEX latest-snapshot strip; its prices are not inputs to the quant engine.

Alpaca's [historical stock-bars API](https://docs.alpaca.markets/us/reference/stockbars) supports `timeframe=1Day`, `adjustment=all`, explicit `feed=iex|sip`, and `next_page_token`. It sorts multi-symbol results by symbol and the page limit is shared across symbols, so one response cannot be treated as complete coverage. Alpaca's [market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) distinguishes IEX from consolidated SIP history. Public display and retention must be checked against the applicable [Alpaca agreements](https://alpaca.markets/disclosures) for the deployment.

## Goals / Non-Goals

**Goals:**

- Use Alpaca adjusted daily closes for every vendor-backed quant path: v1 analysis, market history and allocation What-if, and v2 analysis snapshots that power event scenarios.
- Preserve aligned history, explicit failures, provenance, owner-scoped saved analyses, sample-mode behavior, and the separate latest-quotes display.
- Remove active Twelve Data integration and configuration, and give deployments an explicit migration path.

**Non-Goals:**

- Change quant formulas, turn scenario estimates into forecasts, or use intraday/latest-trade prices as historical closes.
- Rewrite historical OpenSpec records or silently recalculate already saved analyses and runs.
- Assume that possession of Alpaca API keys grants SIP entitlement, public-display rights, or cache rights.

## Decisions

1. **Create `backend/alpaca_history.py` implementing the existing `prices(symbols, lookback_days)` boundary.** It returns a `pandas.DataFrame` of positive adjusted daily closes indexed by complete US trading-session dates plus provenance attributes. Request `1Day`, `adjustment=all`, an explicit configured feed, ascending order, and a bounded end before the current incomplete New York session. Follow every page token until all requested symbols have enough observations or a bounded coverage failure is certain. Normalize bar timestamps to New York session dates; reject duplicate dates, invalid values, insufficient observations, and unaligned date vectors. Preserve the existing 1–25 symbol and 1–1000 return-observation limits. This keeps quant code and API response shapes stable. Alternative: reuse `alpaca_quotes.py`; rejected because snapshots carry no adjusted daily history.
2. **Require `ALPACA_HISTORY_FEED=iex|sip` whenever vendor history is selected or the event lab is enabled.** Keep `MARKET_DATA_PROVIDER=sample` as the v1 default and add `alpaca` as its only vendor value. Reuse the existing server-only `ALPACA_API_KEY` and `ALPACA_API_SECRET`; quote snapshots remain `feed=iex` and stay visibly separate. Report actual feed, `adjustment=all`, retrieval time, latest session, freshness, and `alpaca_adjusted_daily` source in analysis and market-history provenance. Do not silently switch from IEX to SIP or vice versa. Alternative: let Alpaca choose its default feed; rejected because entitlement and data scope would become implicit.
3. **Route both workflows through the new provider.** In v1, update `get_provider` and health/error mapping; `EngineQuantProvider.simulate` continues to obtain a fresh or permitted cached union of saved and proposed symbols. In v2, construct the Alpaca history provider at startup and use it in `_aligned_histories`, including the fresh retry when holding and factor snapshots straddle a session boundary. Event runs continue to consume saved price snapshots. Existing Twelve Data snapshots remain readable with their original provenance; a new analysis is required to create an Alpaca-backed event run. Alternative: rewrite saved snapshots; rejected because it would change the evidence behind completed results.
4. **Make cache rights explicit and isolate cache entries by provider, feed, adjustment, and requested window.** Preserve provenance through `CachedPriceProvider`; bypass the short-lived preflight cache and persistent v2 cache when retention rights are unconfirmed. Use an Alpaca-specific durable cache path only when rights are confirmed. Never read an old Twelve Data cache as Alpaca data. Map 401/403, 429, malformed responses, and missing coverage to distinct existing API error classes without fictional fallback. Alternative: reuse the Twelve Data cache file; rejected because its identity and terms differ.
5. **Update release and verification surfaces.** Replace Twelve Data key/readiness/rights flags, health labels, backend errors, `.env.example`, current READMEs, provider guide, and release gates. Replace vendor-specific backend and frontend test fixtures, add pagination/feed/adjustment/alignment/error/cache tests, and cover v1 What-if plus v2 snapshot-to-run behavior. Remove the obsolete draft Twelve Data adapter and update draft notes. Reconcile the in-progress event-lab planning artifacts with this superseding provider decision; keep completed historical change artifacts as records.

## Risks / Trade-offs

- **IEX coverage or prices differ from consolidated SIP** → Label the selected feed everywhere, test representative holdings and factor ETFs, and fail closed on gaps; require an entitled SIP feed if IEX cannot meet the analysis contract.
- **Multi-symbol pagination or partial sessions yield biased histories** → Consume page tokens to completion and exclude the current incomplete session before validating common dates.
- **Rate limits and repeated analysis calls** → Bound page requests, use cache only when permitted, map rate-limit errors clearly, and run a representative quota smoke check before enabling the event lab.
- **Public display or retention exceeds agreement terms** → Gate public event-lab use on documented Alpaca permissions and keep vendor-history caching disabled until retention is confirmed. Verify rights for any public v1 deployment and the existing quote strip as well.
- **Old and new analyses coexist** → Preserve each snapshot's provider provenance; show its saved source and require fresh analysis for a new Alpaca-backed scenario.

## Migration Plan

1. Add and verify the Alpaca history adapter and provider-agnostic error/cache behavior with mocked responses, then verify a representative entitled account against supported symbols and SPY/TLT/GLD.
2. Deploy the new code with v1 still in sample mode and v2 disabled. Configure Alpaca credentials and explicit history feed; establish the applicable display and retention rights before enabling public vendor-backed features or caches.
3. Switch vendor-backed v1 deployments to `MARKET_DATA_PROVIDER=alpaca`, create new v2 analyses after the event lab is enabled, and inspect health, provenance, coverage, and What-if results. Remove Twelve Data secrets/settings from deployment and retire its cache only after confirming old records remain readable.
4. If Alpaca coverage or entitlement is inadequate, return v1 to sample mode and disable v2 event-lab creation. Existing saved analyses/runs remain readable; there is no automatic fallback from a failing Alpaca request to fictional data.

## Open Questions

- Which Alpaca feed is licensed and sufficiently complete for the approved stock/ETF universe, especially the factor proxies: IEX or SIP? The design requires an explicit choice and fails closed if it cannot supply aligned history.
- What written Alpaca terms cover public display of bars, derived metrics, IEX snapshots, and short-lived or durable retention for this deployment? Public enablement and caching stay gated until resolved.
