## Why

PortfolioLens now shows optional Alpaca IEX snapshots, but standard analysis and both What-if workflows still depend on Twelve Data for historical prices. Using Alpaca for adjusted daily history would give these workflows one market-data provider while preserving the distinction between latest quotes and calculation inputs.

## What Changes

- Add a server-side Alpaca historical-bars provider that supplies adjusted daily closing prices, complete aligned dates, explicit feed and adjustment provenance, and clear coverage, quota, and upstream failures.
- Route standard portfolio analysis, market history, allocation What-if, and the event lab's saved analysis snapshots through Alpaca history. Event scenario runs continue to use their immutable saved price snapshots.
- Keep the fictional sample provider as the default for the standard workspace and keep the existing Alpaca latest-quotes endpoint separate from quant calculations.
- Replace Twelve Data configuration, readiness checks, cache-rights gates, user-facing provider messages, tests, and current setup/release documentation. Retire the active Twelve Data adapter and obsolete draft adapter.
- Require an explicit Alpaca feed choice and confirmation of the applicable display and retention rights before public event-lab use. Existing saved analyses retain their recorded source; users create new analyses to use Alpaca history.
- **BREAKING:** `MARKET_DATA_PROVIDER=twelvedata` and `TWELVE_DATA_*` settings cease to select a working provider. Deployments must configure Alpaca credentials and select `MARKET_DATA_PROVIDER=alpaca` for vendor-backed standard analysis.

## Capabilities

### New Capabilities

- `alpaca-adjusted-history`: Alpaca-backed, provenance-rich daily history for standard and event-lab analytics, including fail-closed coverage and migration behavior.

### Modified Capabilities

None. There are no main specs under `openspec/specs/`; this capability supersedes the vendor-specific assumptions in the in-progress event-lab change.

## Impact

Backend provider adapters, provider selection and caching, v1 and v2 analytics paths, configuration and health, event-lab release gates, API/fixture tests, and setup documentation. Frontend API response shapes and quant formulas remain the same, but source labels and tests change. Deployment requires review of Alpaca feed entitlement and data-display/cache terms.
