## ADDED Requirements

### Requirement: Current metrics are calculated without saved analyses
The backend SHALL calculate current portfolio metrics on selection, reload, and successful portfolio edits and return metrics, observation period, and provenance directly to the main pages. Neither standard nor event workflows SHALL create or require a standalone saved-analysis record or public analysis identifier. The frontend SHALL keep reusable results only in memory and MUST invalidate them when the portfolio or market-data revision changes.

#### Scenario: Open an owned portfolio
- **WHEN** an authenticated user opens an owned portfolio
- **THEN** Overview and Risk receive current modeled metrics without creating an analysis record

#### Scenario: Edit portfolio
- **WHEN** a user successfully updates the selected portfolio allocation
- **THEN** subsequent dashboard and comparison results use the updated revision rather than cached metrics from the old allocation

### Requirement: Data failures and provenance remain explicit
The calculation contracts SHALL identify the data provider, observation window, and modeled nature of results. A provider failure MUST surface an unavailable or retryable error and MUST NOT silently substitute illustrative data for live-provider output. Existing visible sample-data and modeled-result labels SHALL remain where applicable.

#### Scenario: Price provider fails
- **WHEN** adjusted prices cannot be retrieved for the requested portfolio
- **THEN** the page shows a calculation error without displaying newly fabricated or stale values as current

### Requirement: AI explanations use the displayed calculation
An AI explanation request SHALL either calculate from, or verify, the same portfolio revision and metric context shown with its answer. Its response SHALL include the metrics and provenance used, and the UI SHALL update the explanation and related values atomically or reject a stale request. An analysis ID MUST NOT be required.

#### Scenario: Portfolio changes during explanation
- **WHEN** the selected portfolio revision changes while an explanation is pending
- **THEN** the old explanation is rejected or displayed only with its original metrics and revision, never attached to new metrics

### Requirement: Event drafts and runs hold immutable inputs
At draft creation, the event service MUST verify ownership and persist the portfolio name and revision, current and proposed allocations, aligned adjusted-price inputs, dates, provider provenance, and model version together as durable draft context. A confirmed run SHALL retain that context plus confirmed shocks, evidence, and computed results. Workers MUST use pinned context rather than a standalone analysis or a fresh price fetch, and saved runs MUST remain unchanged by later portfolio edits or market data.

#### Scenario: Prices change after draft creation
- **WHEN** prices are updated after a draft is created but before its run is confirmed
- **THEN** the run uses the draft's pinned prices and records their original observation period

#### Scenario: Portfolio changes after a saved run
- **WHEN** a user edits the portfolio after saving an event run
- **THEN** reopening the run returns its original inputs and results

### Requirement: Legacy analysis references are retired safely
The migration SHALL make existing drafts and runs independent of saved-analysis references before removing standalone analysis storage or analysis-ID API contracts. It MUST preserve owner isolation, completed results, and the input context required to reproduce each retained run. Records that cannot be migrated without losing required context SHALL be reported and held for explicit resolution rather than silently deleted.

#### Scenario: Migrate a legacy run
- **WHEN** a legacy run references an analysis that contains its input history
- **THEN** migration copies or verifies the required immutable context into the run and the run remains readable without the analysis record

#### Scenario: Missing referenced analysis
- **WHEN** a legacy draft or run references an unavailable analysis
- **THEN** migration reports that record and does not delete or falsely mark it as fully migrated
