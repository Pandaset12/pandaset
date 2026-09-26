# Verification

Checked September 26, 2026 against the local frontend.

## Automated checks

- `npm test`: seven tests covering linked return attribution, risk contribution reconciliation, single-asset calculations, allocation validation, correlation properties, fixture alignment, and scenario isolation.
- `npm run build`: TypeScript checking and optimized Vite build.

## Browser checks

- All four routes inspected at desktop and mobile sizes. Document width matched viewport width at 320, 390, and 768 pixels; desktop layout inspected at 1440 pixels.
- Overview period changes, empty search and recovery, return-driver view, and portfolio editing checked. Allocations totaling 101% were rejected; a valid edit updated downstream metrics.
- Risk matrix pair selection and allocation grouping checked.
- Research asset comparison and source links checked.
- Scenario validation, presets, calculation, stale-result blocking, confirmation, application to the overview, and asset addition/removal checked. Presets move single-stock allocation into VTI and increase TLT allocation from another holding.
- Contextual analyst responses reflected current sample calculations.
- Keyboard skip link, chart controls, dialog Escape handling, and focus restoration checked.
- Meaningful overview text contrast checked against computed colors. Responsive chart labels and narrow allocation controls visually inspected.
- Final browser console check returned no warnings or errors.

These checks are targeted functional and visual verification, not a complete assistive-technology or WCAG audit.

## Integration limits

Market observations and research metrics are illustrative. The analyst is a curated, calculation-aware demo, with no connected language-model service. No brokerage, market-data, or news API is connected. Portfolio edits last for the current browser session and reset on reload. Scenario results model historical sample returns with constant daily weights; they are not forecasts or executed trades.
