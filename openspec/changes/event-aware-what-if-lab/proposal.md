## Why

The current What-if Lab uses a fixed fictional portfolio and cannot ground an event discussion in a user's holdings or reproducible market data. Users need authenticated, reviewable event scenarios whose numbers come from a deterministic model and whose factual context has citations.

## What Changes

- Add authenticated, owner-scoped manual portfolios and immutable analysis and scenario snapshots for up to 25 supported holdings.
- Add licensed real-data ingestion with symbol classification, adjusted-price provenance, explicit coverage failures, and durable caching within provider terms.
- Add curated event templates, dated FRED and approved-source evidence, and bounded Gemini research and scenario-design roles.
- Require user confirmation of every shock before computing mild, central, and severe one- and three-month cases.
- Add seeded conditional outcome ranges and loss probabilities only when complete validated history and calibration permit them.
- Add asynchronous drafts and runs, saved run chat, cancellation and deletion, and a responsive What-if Lab UI.
- Gate public use on data licensing, security, calibration, vendor capacity, and clear hypothetical labels.

## Capabilities

### New Capabilities

- `authenticated-portfolios`: Token verification, owner-scoped persistence, portfolio selection, and immutable snapshots.
- `market-and-event-evidence`: Supported instruments, adjusted historical prices, curated templates, FRED observations, and cited current context.
- `event-scenario-model`: Confirmed shocks, deterministic scenario calculations, and conditional probability ranges.
- `event-agent-workflow`: Bounded research and scenario design, asynchronous jobs, chat, and lifecycle APIs.
- `what-if-lab-ui`: Portfolio onboarding, event selection and chat, assumption review, and results.

### Modified Capabilities

None.

## Impact

Python API, storage, provider and quant modules; React app routing and What-if workflow; Supabase Auth, MongoDB, Twelve Data, FRED, Gemini, and approved news-source configuration. Public enablement remains gated by external data rights and a documented calibration report.
