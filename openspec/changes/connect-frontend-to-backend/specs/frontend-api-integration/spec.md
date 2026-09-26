## ADDED Requirements

### Requirement: Shared backend portfolio analysis
The frontend SHALL use one active backend portfolio and saved analysis as the source for quantitative portfolio results across the Overview, Risk, What-if, and Ask Panda workspaces. The frontend SHALL keep percentage-to-decimal conversion at the API boundary and SHALL associate each result with its portfolio and analysis IDs.

#### Scenario: Initial portfolio analysis loads
- **WHEN** the app starts and the backend is available
- **THEN** the frontend creates or loads the sample portfolio, requests an analysis, and records the returned portfolio ID, analysis ID, metrics, and provenance in shared app state

#### Scenario: A newer request supersedes an older request
- **WHEN** the active weights change while an earlier analysis request is still pending
- **THEN** the frontend SHALL ignore the older response and SHALL display only results that match the latest active portfolio and analysis request

#### Scenario: Backend is unavailable
- **WHEN** a backend request fails
- **THEN** the relevant view SHALL show an error or unavailable state and SHALL NOT present local TypeScript calculations as backend results

### Requirement: Analysis response supplies chartable history
The backend SHALL include a dated, normalized portfolio series and per-asset series for the requested analysis window in the saved analysis response. The response SHALL include aggregate metrics used by portfolio screens, and SHALL retain source, data mode, freshness, assumptions, warnings, and nullable values with the saved analysis.

#### Scenario: Overview renders backend analysis
- **WHEN** a complete saved analysis is available
- **THEN** Overview SHALL render its portfolio metrics, contributions, and historical chart from that response and SHALL identify demo data as demo data

#### Scenario: Analysis history is shorter than the selected range
- **WHEN** the selected period exceeds the dated series returned by the backend
- **THEN** the frontend SHALL show the available range or an unavailable state and SHALL NOT fabricate or extrapolate observations

#### Scenario: Optional analysis metric is null
- **WHEN** the backend returns a null metric or null series value
- **THEN** the frontend SHALL render it as unavailable and SHALL NOT coerce it to zero

### Requirement: Risk workspace uses saved analysis
The Risk workspace SHALL render portfolio risk contributions, asset volatility, and correlation values from the active backend analysis. Undefined correlation or risk values SHALL remain visibly unavailable.

#### Scenario: Risk data matches active analysis
- **WHEN** the user opens Risk for an active portfolio
- **THEN** the displayed weights and risk metrics SHALL refer to the same portfolio ID and analysis ID

### Requirement: What-if uses backend comparison
The What-if workspace SHALL submit valid proposed weights to the backend comparison endpoint and SHALL render baseline, proposed, and delta metrics from the returned comparison. Applying a scenario SHALL create or analyze the applied allocation and replace the active analysis only after the backend returns a matching result.

#### Scenario: Valid scenario is compared
- **WHEN** the user requests a comparison for valid proposed weights
- **THEN** the UI SHALL display the backend's baseline and proposed metrics from the same comparison response

#### Scenario: Draft changes after comparison
- **WHEN** the user edits scenario weights after a comparison completes
- **THEN** the previous comparison SHALL be marked stale and SHALL NOT be presented as analysis of the edited weights

#### Scenario: Invalid scenario is submitted
- **WHEN** proposed weights are negative, non-finite, or do not sum to one hundred percent at the UI boundary
- **THEN** the frontend SHALL prevent submission and explain the allocation validation error

### Requirement: Ask Panda uses the active analysis snapshot
Ask Panda SHALL send questions with the active analysis ID and SHALL display the response status, answer, citations, warnings, and disclaimer returned by the backend.

#### Scenario: Demo answer is returned
- **WHEN** the backend answers in demo mode
- **THEN** Ask Panda SHALL label the answer as a demo response and SHALL display its citations and warnings

#### Scenario: Explanation is unavailable
- **WHEN** the backend returns an unavailable status or request error
- **THEN** Ask Panda SHALL show that the explanation is unavailable while keeping the saved analysis accessible

### Requirement: Research market history uses the API
Research price charts and asset comparisons SHALL use dated market-history responses from the backend for the selected supported symbols. Curated research primers and issuer links MAY remain local editorial content and SHALL be identified as such.

#### Scenario: Selected asset history loads
- **WHEN** the user opens a supported asset in Research
- **THEN** the chart SHALL use the backend's dated series and display its data mode and source

#### Scenario: History is unavailable for a symbol
- **WHEN** the backend has no valid aligned history for a selected symbol
- **THEN** Research SHALL show an unavailable state and SHALL NOT substitute a frontend-generated return path

### Requirement: API-backed workspaces expose request state
Every API-backed workspace SHALL expose pending and failure states accessibly and SHALL allow recovery or retry when appropriate.

#### Scenario: Request is pending
- **WHEN** a portfolio, analysis, comparison, history, or Ask request is in progress
- **THEN** the UI SHALL expose a visible loading state and prevent duplicate submissions for that operation

#### Scenario: Request fails and can be retried
- **WHEN** a recoverable backend request fails
- **THEN** the UI SHALL explain the failure without exposing secrets or raw server exceptions and SHALL offer a retry action
