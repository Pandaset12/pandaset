# PandaSet visual system

## Direction

An investment research desk with editorial clarity: open page structures, precise financial ledgers, expressive serif headings, and a dark evergreen palette warmed by restrained brass. Near-black evergreen anchors the canvas; progressively lighter forest and olive surfaces separate panels and controls. Brass marks primary actions, selection, and the portfolio series. Sage identifies positive values, and terracotta identifies losses. Top navigation keeps the four workflows within reach. Panels have different forms according to their purpose: a dark plotting surface, a dark insight panel, an open risk analysis, a compact research directory, and a two-column scenario editor.

## Tokens

| Role             | Value               |
| ---------------- | ------------------- |
| Page background  | `#0d1210`           |
| Panel surface    | `#151d19`           |
| Focus panel      | `#1b241e`           |
| Raised surface   | `#222c25`           |
| Selected surface | `#303b2f`           |
| Primary text     | `#eeece4`           |
| Secondary text   | `#a4aea5`           |
| Rules            | `#3c4940`           |
| Brass accent     | `#c2a36b`           |
| Filled action    | `#786037`           |
| Positive values  | `#7fa487`           |
| Negative values  | `#d07d72`           |
| Panel corners    | 7px                 |
| Button corners   | 5px                 |
| Standard spacing | 8, 12, 16, 24, 32px |

Instrument Serif supplies the editorial hierarchy; DM Sans supplies controls, prose, and financial values. Numeric columns use tabular figures. Font sizes use rem units; metadata is generally 12px at the default browser size. Thin rules separate related values. Shadows are reserved for raised controls and modal overlays.

## Data visualization

- Solid brass lines show the primary series; dashed sage-gray lines show the comparison.
- SVG viewboxes follow the measured container width, preserving readable axis labels on small screens.
- Charts have descriptive accessible names and keyboard-operable timeline sliders with date/value readouts.
- Paired bars compare capital weights with covariance-based risk contributions.
- Return contributions use a common linear scale and a zero baseline, including negative-only portfolios.
- Correlation cells use a raised neutral diagonal, brass positive relationships, and terracotta negative relationships. Every cell includes its numeric value and an accessible asset-pair name.
- Allocation groups have text labels and percentages beside the color encoding.

## Interactions

Related workflows use direct links: holding to research, concentration to scenario, and company research to allocation testing. Tabs retain a visible selected state. Native dialogs trap focus, close with Escape, and restore the triggering focus. A skip link moves focus into the active workspace. Focus outlines remain visible, and reduced-motion preferences disable transitions and animation.

Scenario calculations explicitly separate draft input from calculated results. Invalid totals disable calculation; changed inputs mark existing results as stale and disable application. Applying a scenario updates the sample portfolio and returns to the overview with a status message.

## Responsive behavior

At smaller widths, navigation moves to a second header row, the risk insight stacks below the performance plot, and the scenario editor stacks above results. The research directory becomes a horizontal asset strip. Dense tables scroll within their own containers. Chart labels preserve their size rather than shrinking with a desktop-sized plot.

## States

Hover and focus treatments use brass outlines and tonal changes. Selected controls use a raised evergreen surface or a brass underline. Loading indicators appear during calculation and analyst responses. Search has clear empty states and reset actions. Weight-validation errors appear next to the allocation total. Disabled actions remain visible. Rendering failures show a recovery action. Sample data and the guided analyst are explicitly identified.
