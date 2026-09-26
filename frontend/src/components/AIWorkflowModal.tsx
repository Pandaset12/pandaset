import { useEffect, useRef, useState } from "react";
import { ArrowPath, ArrowUpRight, InformationCircle } from "./icons";
import { Modal } from "./UI";
import {
  createRequestGuard,
  requestAnalysisBriefing,
  requestResearchSummary,
  requestRiskExplanation,
  requestScenarioExplanation,
  type AIWorkflowResponse,
} from "../api/portfolio";

export type AIWorkflowAction =
  | { workflow: "analysis_briefing" }
  | { workflow: "risk_explanation"; question: string }
  | {
      workflow: "scenario_explanation";
      proposedWeights: number[];
      symbols: string[];
    }
  | { workflow: "research_summary"; symbol: string };

const workflowTitles = {
  analysis_briefing: "Portfolio briefing",
  risk_explanation: "Risk explanation",
  scenario_explanation: "Scenario trade-offs",
  research_summary: "Source summary",
} satisfies Record<AIWorkflowAction["workflow"], string>;

function citationLabel(field: string) {
  return field
    .replaceAll("baseline.", "current · ")
    .replaceAll("proposed.", "proposed · ")
    .replaceAll("delta.", "change · ")
    .replaceAll("_", " ")
    .replaceAll(".", " · ");
}

function citationValue(field: string, value: number) {
  return field.includes("correlation.")
    ? value.toFixed(3)
    : new Intl.NumberFormat("en-US", {
        style: "percent",
        maximumFractionDigits: 2,
      }).format(value);
}

function sourceUrl(source: Record<string, unknown>) {
  const web = source.web;
  if (!web || typeof web !== "object") return null;
  const uri = (web as Record<string, unknown>).uri;
  return typeof uri === "string" ? uri : null;
}

function retrievalStatus(response: AIWorkflowResponse) {
  const first = response.url_retrievals[0];
  if (!first) return "No retrieval metadata was returned.";
  const status = first.url_retrieval_status;
  return typeof status === "string"
    ? status.replaceAll("URL_RETRIEVAL_STATUS_", "").toLowerCase()
    : "Retrieval metadata received.";
}

export function AIWorkflowModal({
  action,
  portfolioId,
  analysisId,
  onClose,
}: {
  action: AIWorkflowAction;
  portfolioId: string;
  analysisId: string;
  onClose: () => void;
}) {
  const [response, setResponse] = useState<AIWorkflowResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestGuard = useRef(createRequestGuard());

  async function load() {
    const id = requestGuard.current.begin();
    setBusy(true);
    setError("");
    setResponse(null);
    try {
      const result =
        action.workflow === "analysis_briefing"
          ? await requestAnalysisBriefing(portfolioId, analysisId)
          : action.workflow === "risk_explanation"
            ? await requestRiskExplanation(
                portfolioId,
                analysisId,
                action.question,
              )
            : action.workflow === "scenario_explanation"
              ? await requestScenarioExplanation(
                  portfolioId,
                  analysisId,
                  action.proposedWeights,
                  action.symbols,
                )
              : await requestResearchSummary(action.symbol);
      if (requestGuard.current.isCurrent(id)) setResponse(result);
    } catch (reason) {
      if (requestGuard.current.isCurrent(id)) {
        setError(
          reason instanceof Error
            ? reason.message
            : "The AI workflow is unavailable.",
        );
      }
    } finally {
      if (requestGuard.current.isCurrent(id)) setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    return () => requestGuard.current.invalidate();
  }, []);

  const title = workflowTitles[action.workflow];
  return (
    <Modal title={title} onClose={onClose}>
      <div className="analyst-mode">
        <InformationCircle size={15} />
        <span>
          {action.workflow === "research_summary"
            ? `${action.symbol} · selected issuer source`
            : `Saved analysis ${analysisId} · backend-calculated context`}
        </span>
      </div>
      <section className="ai-workflow-result" aria-busy={busy}>
        {busy && (
          <p className="analyst-loading" role="status">
            <ArrowPath size={15} className="spin" />
            Preparing {title.toLowerCase()}…
          </p>
        )}
        {error && (
          <div className="api-state" role="alert">
            <p>{error}</p>
            <button
              className="text-button"
              onClick={() => void load()}
              disabled={busy}
            >
              Retry <ArrowPath size={14} />
            </button>
          </div>
        )}
        {response && (
          <>
            <span className="label-chip">
              {response.status === "demo"
                ? "DEMO · AI NOT CALLED"
                : response.status.toUpperCase()}
            </span>
            <p className="workflow-answer">{response.answer}</p>
            {response.status === "unavailable" && (
              <button
                className="text-button"
                onClick={() => void load()}
                disabled={busy}
              >
                Retry <ArrowPath size={14} />
              </button>
            )}
            {response.citations.length > 0 && (
              <div className="ask-response-details">
                <strong>Metric citations</strong>
                <ul>
                  {response.citations.map((citation) => (
                    <li key={citation.field}>
                      {citationLabel(citation.field)}:{" "}
                      {citationValue(citation.field, citation.value)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {response.source_url && (
              <div className="ask-response-details">
                <strong>Selected source</strong>
                <p>
                  <a
                    href={response.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {response.source_url} <ArrowUpRight size={12} />
                  </a>
                </p>
                <p className="small-text muted">
                  URL Context: {retrievalStatus(response)}
                </p>
              </div>
            )}
            {response.sources.length > 0 && (
              <div className="ask-response-details">
                <strong>Grounding sources</strong>
                <ul>
                  {response.sources.map((source, index) => {
                    const url = sourceUrl(source);
                    return url ? (
                      <li key={`${url}-${index}`}>
                        <a href={url} target="_blank" rel="noreferrer">
                          {url}
                        </a>
                      </li>
                    ) : null;
                  })}
                </ul>
              </div>
            )}
            {response.warnings.map((warning) => (
              <p className="small-text muted" key={warning}>
                {warning}
              </p>
            ))}
            <p className="small-text muted">{response.disclaimer}</p>
          </>
        )}
      </section>
      <p className="analyst-footnote">
        {action.workflow === "research_summary"
          ? "The summary uses the selected issuer source and its retrieval metadata. Open the source to review the original page."
          : "AI text explains supplied evidence; portfolio values come from the backend analysis and remain unchanged."}
      </p>
    </Modal>
  );
}
