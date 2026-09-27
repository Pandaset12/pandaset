import type { AnalysisResponse } from "../api/portfolio";
import { showAnnualizedReturn } from "../../../quant/analytics";

export function observationCount(analysis: AnalysisResponse) {
  return analysis.observation_count ?? analysis.lookback_days;
}

export function historySourceLabel(analysis: AnalysisResponse) {
  if (analysis.data_mode === "demo") return "Fictional sample history";
  if (analysis.data_quality.source === "alpaca_adjusted_daily")
    return "Alpaca adjusted daily history";
  return "Market daily history";
}

export function historySessionLabel(analysis: AnalysisResponse) {
  if (!analysis.as_of) return "Date unavailable";
  const date = new Date(analysis.as_of);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function SampleContext({ analysis }: { analysis: AnalysisResponse }) {
  const count = observationCount(analysis);
  return (
    <p
      className={`sample-context ${showAnnualizedReturn(count) ? "" : "limited"}`}
    >
      <strong>
        {analysis.data_mode === "demo"
          ? "Illustrative model"
          : "Modeled result"}
      </strong>
      <span>
        {" · "}
        {historySourceLabel(analysis)} · {count} daily return observations
      </span>
      {!showAnnualizedReturn(count) && (
        <span> · Short history; estimates may change substantially.</span>
      )}
    </p>
  );
}

export function AnalysisDetails({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <details className="analysis-details">
      <summary>Analysis details</summary>
      <div>
        <p>
          {analysis.data_mode === "demo"
            ? "Illustrative sample"
            : "Modeled analysis"}
          {" · "}
          {observationCount(analysis)} daily return observations through{" "}
          {historySessionLabel(analysis)}
        </p>
        <dl>
          <div>
            <dt>Source</dt>
            <dd>{historySourceLabel(analysis)}</dd>
          </div>
          <div>
            <dt>Freshness</dt>
            <dd>{analysis.data_quality.freshness}</dd>
          </div>
          <div>
            <dt>Analysis ID</dt>
            <dd>{analysis.analysis_id}</dd>
          </div>
          <div>
            <dt>Portfolio ID</dt>
            <dd>{analysis.portfolio_id}</dd>
          </div>
        </dl>
        {analysis.data_quality.warnings.map((warning) => (
          <p key={warning}>{warning}</p>
        ))}
      </div>
    </details>
  );
}
