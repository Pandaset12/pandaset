## Context

The backend has one optional Gemini adapter for Ask Panda. It receives a question and an immutable analytics snapshot, requests structured qualitative prose and metric identifiers, then validates citations and renders numeric facts from the snapshot. The quant provider independently calculates analyses and baseline/proposed what-if comparisons. The Research workspace links to curated issuer sources but does not ingest them. The current backend API accepts validated HTTPS source URLs and can enable URL Context.

The application is a sample-data research demo. Source, freshness, assumptions, and demo labels must remain visible; Gemini is optional and its failure must not make deterministic results unavailable. This change adds contextual AI affordances to the existing workspaces while keeping one shared model integration and no sub-agent orchestration.

## Goals / Non-Goals

**Goals:**
- Reuse one backend Gemini client, timeout/retry handling, safe error mapping, and observability across multiple task-specific workflows.
- Provide on-demand Overview briefings and Risk explanations grounded in a saved analysis.
- Explain an actual quant-engine what-if comparison using its baseline, proposed metrics, and deltas.
- Summarize only a user-selected, curated public source in Research, with source evidence.
- Keep model context, output schema, and tool permissions specific to each workflow.
- Preserve sample-data provenance and allow users to see quantitative results when AI is unavailable.

**Non-Goals:**
- Multiple Gemini agents, sub-agents, autonomous planning, or persistent cross-tab conversation memory.
- AI-generated allocations, automatic application of portfolio changes, trade execution, or personalized buy/sell recommendations.
- AI calculation or correction of portfolio metrics, live market news feeds, issuer fundamentals ingestion, or brokerage connectivity.
- Free-form URL crawling. Research summaries use the curated public source links already associated with an asset.

## Decisions

### One shared model adapter with task-specific workflows

Keep the Gemini SDK client lifecycle, timeout, retries, and upstream error handling in one shared service. Add explicit workflow handlers such as `analysis_briefing`, `risk_explanation`, `scenario_explanation`, and `research_summary`. Each handler defines a typed input context, prompt, JSON response schema, evidence allowlist, and permitted Gemini tools. Each interaction is a bounded model call; no prior tab conversation is implicitly included.

**Alternative considered:** create a separate agent per tab. Rejected because the initial workflows share a model connection and safety boundary; separate agent loops would duplicate configuration and make behavior harder to keep consistent.

### Quant calculations run before narrative generation

Analysis and risk workflows use the saved `AnalyticsSnapshot`. Scenario explanation accepts the saved portfolio/analysis identity and proposed weights, validates them on the server, and obtains the comparison from `QuantProvider.simulate` before calling Gemini. The backend does not accept browser-supplied metric values as evidence. The AI receives a compact, typed comparison context containing baseline, proposed, delta, data provenance, and assumptions.

**Alternative considered:** ask Gemini to estimate the result from weights or explain only the baseline snapshot. Rejected because the model cannot be the source of financial calculations, and baseline-only context omits the scenario results the user is viewing.

### Resolve numeric citations on the server

For metric workflows, Gemini returns qualitative prose and exact evidence identifiers. The backend resolves identifiers against a workflow-scoped catalog built from the saved snapshot or comparison and renders the numeric values itself. Scenario identifiers distinguish baseline, proposed, and delta values. Unsupported identifiers and numeric model prose produce an unavailable AI response while preserving quant output.

For Research, use only selected curated source URLs and URL Context. Preserve source order, grounding supports, retrieval status, and links with the response. Do not treat a summary claim without returned source evidence as sourced.

**Alternative considered:** let Gemini write formatted numbers directly. Rejected because model prose can alter values or introduce unsupported quantitative claims.

### Keep tool permissions narrow by workflow

Overview, Risk, and scenario explanation receive no web tools. Research summary alone may use URL Context, limited to the selected curated URLs. Google Search remains off for these workflows; adding broad discovery is a separate product decision.

**Alternative considered:** enable Search and URL Context for all requests. Rejected because portfolio explanations do not need external retrieval and source research should remain user-directed and attributable.

### Keep UI integration contextual and optional

Add on-demand entry points in Overview and Risk, connect the existing What-if trade-off action to its actual comparison result, and add a summarize action for curated Research sources. Every view displays workflow status, citations/evidence, warnings, and demo provenance. AI failure shows an unavailable state alongside the already available deterministic results; it does not substitute a generated success message.

Natural-language allocation editing is excluded from this release. Existing controls continue to define proposed weights, and the user explicitly applies a successful scenario.

## Risks / Trade-offs

- [A structured, cited answer can still contain an inaccurate qualitative explanation] → Keep explanations narrow, pass assumptions and warnings, show evidence, and avoid presenting prose as a calculation.
- [Additional AI calls add latency and model cost] → Make workflows user-triggered, avoid duplicate calls for unchanged context, and reuse the shared client policy.
- [Sample outputs may look like real investment analysis] → Carry `data_mode`, source, freshness, warnings, and assumptions into every workflow and label demo answers in the UI.
- [Scenario context could become detached from the active allocation] → Identify the saved analysis and proposed weights in the request; recompute the comparison server-side before asking Gemini.
- [Source retrieval may fail or omit grounding] → Show retrieval status and links, preserve evidence indices, and render a safe unavailable/partial response without claiming a sourced summary.
- [Curated issuer URLs can change or become unavailable] → Treat retrieval failures as normal and retain the existing static editorial primer.

## Migration Plan

1. Complete or reconcile the existing frontend-to-backend integration work before adding new AI entry points; keep existing Ask Panda behavior available.
2. Add workflow-specific schemas, prompts, evidence catalogs, and orchestration over the shared Gemini service.
3. Add the scenario explanation request so the backend validates proposed weights and supplies its own quant comparison to Gemini.
4. Add Overview, Risk, What-if, and Research UI actions with consistent loading, complete, demo, unavailable, source, and retry states.
5. If rollout exposes an issue, hide the new entry points and retain the existing deterministic workflows; no quant formulas or persisted analysis records need migration.

## Open Questions

- Should the Overview briefing run only on user request, or also load automatically after a new analysis? Initial design: user-requested to control latency and cost.
- Should Research summarize one selected source at a time or allow a small set of curated sources? Initial design: one source per request, with the API limit unchanged as a safety ceiling.
