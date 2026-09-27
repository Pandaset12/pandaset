import type { AnalysisResponse } from "../api/portfolio";
import { showAnnualizedReturn } from "../../../quant/analytics";

export function observationCount(analysis: AnalysisResponse) {
  return analysis.observation_count ?? analysis.lookback_days;
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
        {count} {analysis.data_mode === "demo" ? "fictional " : ""}daily return
        observations
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
          {observationCount(analysis)} daily return observations
        </p>
        <dl>
          <div>
            <dt>Source</dt>
            <dd>{analysis.data_quality.source}</dd>
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
