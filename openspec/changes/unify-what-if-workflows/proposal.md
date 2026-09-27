## Why

Enabling the event-aware lab currently replaces the main dashboard with a second workspace, portfolio list, and onboarding flow. Users want to keep every page and saved portfolio from the main experience, compare allocations quickly, and optionally research an event from the same What-if page without managing or seeing separate analyses.

## What Changes

- Keep the main Overview, Risk & exposure, Research, navigation, portfolio picker, and onboarding as the only workspace. Make the selected main portfolio authoritative for both What-if paths; do not require a duplicate event portfolio.
- Combine the existing allocation comparison and event-aware research in one What-if page with a shared proposed allocation. The quick comparison remains available without event research; the event path adds sourced evidence, editable assumptions, confirmation, and saved results.
- Remove the event workspace's separate “New portfolio” and manual “Refresh/Create analysis” controls, the visible “Backend analysis” panel and raw analysis IDs, and automatic whole-app switching to the second shell. Keep concise market-data provenance and modeled-result labels where users need them.
- **BREAKING:** Retire standalone saved-analysis records and analysis-ID based API contracts in both workflows. Calculate dashboard and allocation results on demand. Freeze the exact allocation, aligned adjusted prices, dates, provenance, model version, and confirmed assumptions within each durable event draft/run so saved results remain reproducible.
- Preserve current owner isolation, approved-source search, provider-failure behavior, event access gates, and explicit user action before applying an allocation. Migrate existing event drafts/runs before removing records they reference.

## Capabilities

### New Capabilities

- `single-portfolio-workspace`: One main dashboard shell and owner-scoped portfolio source across Overview, Risk, Research, and What-if, including event access and migration behavior.
- `combined-what-if`: One What-if experience for fast allocation comparison and optional researched event scenarios, sharing the selected portfolio and proposed allocation.
- `on-demand-calculations`: Automatically calculated dashboard and comparison results without standalone saved analyses, with consistent AI context and immutable inputs retained only in durable event drafts/runs.

### Modified Capabilities

None. The related event-lab requirements are still change-local rather than synchronized into `openspec/specs/`; this change supersedes their separate-workspace and analysis-ID assumptions.

## Impact

React routing and workspace components in `frontend/src/App.tsx`, `EventApplication.tsx`, `pages/WhatIf.tsx`, and `pages/EventWhatIf.tsx`; v1/v2 portfolio, calculation, AI, and event APIs; SQLite and MongoDB storage contracts; event workers and quant input preparation; migration of existing portfolios, analyses, drafts, and runs; frontend/backend tests and release documentation. The Tavily, DeepSeek, Gemini, Alpaca, Supabase, MongoDB, rights, and calibration gates remain in force for event research and results.
