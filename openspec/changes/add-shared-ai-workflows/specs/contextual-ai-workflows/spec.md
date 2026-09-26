## ADDED Requirements

### Requirement: Shared task-scoped AI workflows
The system SHALL use one shared Gemini service for contextual AI workflows and SHALL select an explicit workflow-specific prompt, input schema, output schema, and tool allowlist for each request. The system SHALL NOT spawn sub-agents or infer context from another tab or previous request.

#### Scenario: Workflow context is isolated
- **WHEN** a user requests an explanation from any workspace
- **THEN** the system sends only that workflow's validated context and permitted tools to the shared Gemini service

#### Scenario: Gemini is unavailable
- **WHEN** the model is unconfigured, times out, fails, or returns invalid structured output
- **THEN** the system reports an unavailable AI result while preserving the deterministic analysis or comparison already available

### Requirement: Metric-grounded analysis and risk explanations
Overview briefings and Risk explanations SHALL use the active saved analysis snapshot as their quantitative evidence. The AI response SHALL reference metric identifiers from a workflow-scoped allowlist, and the backend SHALL resolve displayed numeric facts from that snapshot. Missing metrics SHALL remain unavailable rather than being inferred as zero.

#### Scenario: Explain a saved analysis
- **WHEN** a user requests an Overview briefing or Risk explanation for an active saved analysis
- **THEN** the response is associated with that analysis ID, includes its demo/live provenance and warnings, and displays only backend-resolved citations

#### Scenario: A requested metric is missing
- **WHEN** the model or workflow requests a metric absent from the saved snapshot
- **THEN** the backend rejects that citation and returns an unavailable AI result without fabricating a value

### Requirement: Quant-grounded scenario explanations
What-if explanations SHALL be based on a server-calculated comparison for the saved portfolio and validated proposed weights. The backend SHALL provide baseline, proposed, and delta values from the quant provider to the AI workflow, and SHALL resolve any displayed numbers from that comparison. An AI explanation SHALL NOT apply the proposed allocation.

#### Scenario: Explain a valid comparison
- **WHEN** a user requests an explanation for a non-stale What-if comparison
- **THEN** the backend validates the saved analysis and proposed allocation, obtains the comparison from the quant provider, and returns an explanation associated with those comparison results

#### Scenario: Proposed weights are invalid or comparison is unavailable
- **WHEN** proposed weights fail validation or the quant provider cannot calculate the comparison
- **THEN** the system does not ask Gemini to estimate the result and returns the relevant validation or unavailable state

#### Scenario: User applies a scenario
- **WHEN** the user chooses to use a proposed allocation
- **THEN** the existing explicit confirmation flow creates the active analysis, and no AI response can apply it on the user's behalf

### Requirement: Source-grounded Research summaries
Research summaries SHALL use only curated public source URLs selected by the user from the Research workspace. The Research workflow SHALL use URL Context without enabling Google Search, and SHALL preserve source links and available grounding/retrieval metadata with its response.

#### Scenario: Summarize a selected source
- **WHEN** a user requests a summary for a curated issuer or public-disclosure source
- **THEN** the workflow summarizes retrieved content and returns the source URL and available grounding or retrieval status for display

#### Scenario: Source retrieval fails or has no evidence
- **WHEN** URL Context cannot retrieve the selected source or returns no usable evidence
- **THEN** the UI identifies the summary as unavailable or partial and does not present unsupported claims as sourced facts

### Requirement: Visible provenance and workflow status
Each contextual AI response SHALL identify its workflow and associated analysis or source, preserve demo/live provenance, and expose complete, demo, or unavailable status with relevant warnings and citations/evidence. AI-generated text SHALL remain separate from quant-engine metrics.

#### Scenario: Display a demo-backed explanation
- **WHEN** an AI workflow receives fictional sample inputs
- **THEN** its result is visibly labeled as sample/demo data and retains the snapshot's source, freshness, and assumptions

#### Scenario: Display a complete explanation
- **WHEN** a workflow returns valid output
- **THEN** the UI shows the explanation, workflow status, metric citations or source evidence, and applicable disclaimer/warnings
