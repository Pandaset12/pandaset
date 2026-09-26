# PortfolioLens visual system

## Direction

An investment research desk with editorial clarity: open page structures, precise financial ledgers, expressive serif headings, and a restrained forest-green palette. Top navigation keeps the four workflows within reach. Panels have different forms according to their purpose: a white plotting surface, a dark insight panel, an open risk analysis, a compact research directory, and a two-column scenario editor.

## Tokens

| Role | Value |
| --- | --- |
| Primary ink | `#233d33` |
| Deep forest | `#173e35` |
| Chart green | `#245a43` |
| Accent | `#e5eea3` |
| Page surface | `#f7f8f4` |
| Panel surface | `#ffffff` |
| Rules | `#dfe4da` |
| Secondary text | `#5b6b53` / `#69736b` |
| Negative values | `#a54834` |
| Panel corners | 7px |
| Button corners | 5px |
| Standard spacing | 8, 12, 16, 24, 32px |

Instrument Serif supplies the editorial hierarchy; DM Sans supplies controls, prose, and financial values. Numeric columns use tabular figures. Font sizes use rem units; metadata is generally 12px at the default browser size. Thin rules separate related values. Shadows are reserved for raised controls and modal overlays.

## Data visualization

- Solid forest lines show the primary series; dashed gray lines show the comparison.
- SVG viewboxes follow the measured container width, preserving readable axis labels on small screens.
- Charts have descriptive accessible names and keyboard-operable timeline sliders with date/value readouts.
- Paired bars compare capital weights with covariance-based risk contributions.
- Return contributions use a common linear scale and a zero baseline, including negative-only portfolios.
- Correlation cells use a neutral diagonal, green positive relationships, and warm negative relationships. Every cell includes its numeric value and an accessible asset-pair name.
- Allocation groups have text labels and percentages beside the color encoding.

## Interactions

Related workflows use direct links: holding to research, concentration to scenario, and company research to allocation testing. Tabs retain a visible selected state. Native dialogs trap focus, close with Escape, and restore the triggering focus. A skip link moves focus into the active workspace. Focus outlines remain visible, and reduced-motion preferences disable transitions and animation.

Scenario calculations explicitly separate draft input from calculated results. Invalid totals disable calculation; changed inputs mark existing results as stale and disable application. Applying a scenario updates the sample portfolio and returns to the overview with a status message.

## Responsive behavior

At smaller widths, navigation moves to a second header row, the risk insight stacks below the performance plot, and the scenario editor stacks above results. The research directory becomes a horizontal asset strip. Dense tables scroll within their own containers. Chart labels preserve their size rather than shrinking with a desktop-sized plot.

## States

Hover and focus treatments use borders and tonal changes. Selected controls use a raised white surface or an underline. Loading indicators appear during calculation and analyst responses. Search has clear empty states and reset actions. Weight-validation errors appear next to the allocation total. Disabled actions remain visible. Rendering failures show a recovery action. Sample data and the guided analyst are explicitly identified.
