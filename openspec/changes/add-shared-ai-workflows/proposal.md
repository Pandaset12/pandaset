## Why

PandaSet has an optional Gemini explanation path, but AI is not available in the Overview, Risk, What-if, or Research workflows where users encounter the underlying information. Add contextual explanations and source summaries while keeping portfolio calculations deterministic, traceable to the quant engine, and clearly labeled as sample data.

## What Changes

- Add one shared backend AI service with workflow-specific prompts, inputs, output schemas, and tool permissions; do not create autonomous or delegated sub-agents.
- Add on-demand Overview briefings and Risk explanations grounded in the active saved analysis.
- Add What-if trade-off explanations grounded in the backend's baseline/proposed comparison and metric deltas.
- Allow Research users to request a summary of selected public issuer or disclosure pages, preserving source links and retrieval evidence.
- Show workflow status, metric citations or source evidence, sample-data labels, and safe unavailable states consistently.
- Keep numeric calculations in the quant engine. AI does not calculate or overwrite metrics, change allocations, execute trades, or provide personalized buy/sell recommendations.

## Capabilities

### New Capabilities
- `contextual-ai-workflows`: Shared, task-scoped AI explanations and source summaries across the portfolio workspaces.

### Modified Capabilities

## Impact

- Backend AI orchestration, request/response schemas, and v1 API routes in `backend/gemini_service.py`, `backend/api_v1.py`, and `backend/schemas.py`.
- Frontend entry points and response rendering in Overview, Risk, What-if, Research, and shared AI UI components.
- Existing quant-engine analysis and comparison reports remain the source of portfolio metrics; no new model or data-provider dependency is introduced.
- Research URL Context uses explicitly selected public HTTPS sources and returns evidence for display; this does not add a market-news feed or live financial data.
