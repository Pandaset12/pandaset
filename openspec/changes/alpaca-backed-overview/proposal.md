## Why

Overview already displays optional Alpaca IEX prices, and its saved portfolio analysis can use Alpaca adjusted daily history. The standard workspace still defaults to sample history, while several Overview labels and fallback holding descriptions imply sample data even when Alpaca is selected. Users need a clear account of which results come from their entered holdings and which market-data feed produced them.

## What Changes

- Make the Overview contract explicit: saved user-entered symbols and allocation weights drive portfolio calculations; the selected backend history provider supplies prices. Latest IEX quotes remain a separately labeled display.
- Make Overview copy and source details follow analysis provenance, including its historical date and feed, without calling daily-history calculations real-time portfolio value or brokerage P&L.
- Replace the fixed four-ticker technology allocation tile and sample-only fallback holding description with information valid for any supported user-entered ticker.
- Keep the chart's VTI line only when the saved analysis actually contains VTI history; do not silently add an unrelated benchmark or substitute a quote for historical data.
- Document and verify the Alpaca-backed deployment path, missing-configuration and coverage behavior, and an opt-in live feed check. Keep fictional sample mode available and visibly labeled for local/demo use.

## Capabilities

### New Capabilities

- `overview-market-data`: Source-aware Overview presentation and user-portfolio-driven analysis when Alpaca history is selected.

### Modified Capabilities

None. There are no main specs under `openspec/specs/`; this change builds on the in-progress `alpaca-adjusted-history` change without changing its provider contract.

## Impact

The standard workspace's Overview, shared analysis/source labels, fallback holding metadata, focused frontend tests, and backend configuration/deployment guidance. Existing v1 analysis and quote endpoints remain the data boundary. No Alpaca credentials move to the frontend, and no brokerage account, transaction, or position sync is introduced.
