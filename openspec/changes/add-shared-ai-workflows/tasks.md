## 1. Define Shared AI Workflow Contracts

- [x] 1.1 Add typed request and response schemas for analysis briefing, risk explanation, scenario explanation, and Research source summary.
- [x] 1.2 Extend the shared Gemini adapter to select a workflow-specific prompt, structured response schema, context, and tool allowlist without adding sub-agent orchestration or cross-request memory.
- [x] 1.3 Build workflow-scoped evidence catalogs and resolve metric citations from server-owned snapshot/comparison data.
- [x] 1.4 Preserve common timeout, retry, safe error, request ID, and demo provenance behavior across all workflows.

## 2. Add Snapshot-Backed Explanations

- [x] 2.1 Add Overview briefing and Risk explanation API flows that load the requested saved analysis and pass only its validated snapshot context to the shared service.
- [x] 2.2 Extend grounded citations for annualized return, drawdown, volatility, holdings, risk shares, asset volatility, and selected correlations where present.
- [x] 2.3 Add backend response handling so invalid metric references or unavailable metrics cannot be rendered as invented values.

## 3. Explain Quant-Calculated What-If Results

- [x] 3.1 Add a scenario explanation request containing portfolio ID, saved analysis ID, validated proposed weights, and the user's explanation request.
- [x] 3.2 Verify the saved snapshot belongs to the requested portfolio and that its allocation is the comparison baseline before invoking the quant provider.
- [x] 3.3 Run the existing quant comparison on the server and pass its baseline, proposed, delta, provenance, and assumptions to the scenario workflow.
- [x] 3.4 Resolve scenario citations from backend comparison values and ensure the AI response cannot apply or persist proposed holdings.

## 4. Add Curated Research Source Summaries

- [x] 4.1 Map Research source selections to the existing curated public issuer/disclosure URLs and send only the selected source to the Research workflow.
- [x] 4.2 Enable URL Context only for Research source summaries and preserve grounding indices, source links, and retrieval status in the response.
- [x] 4.3 Return a partial or unavailable result when retrieval evidence is missing or source retrieval fails.

## 5. Connect Workspace UI

- [x] 5.1 Add on-demand AI briefing and risk explanation entry points with analysis identity, status, metric citations, warnings, and demo labels.
- [x] 5.2 Connect What-if trade-off explanation to the proposed allocation and server-calculated comparison context, and preserve the existing explicit apply confirmation.
- [x] 5.3 Add a Research summarize action for curated sources with source links, evidence, retrieval status, and accessible loading/error states.
- [x] 5.4 Keep Ask Panda on the shared service and show consistent workflow status, unavailable, retry, citation, and disclaimer behavior.

## 6. Document and Validate the Workflows

- [x] 6.1 Add focused backend and frontend tests for workflow isolation, citations, scenario alignment, Research grounding, and failure states.
- [x] 6.2 Update backend and product documentation to describe the shared service, workflow-specific permissions, demo limitations, and AI boundaries.
