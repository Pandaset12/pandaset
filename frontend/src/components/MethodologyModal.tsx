import { InformationCircle as Info } from "./icons";
import { Modal } from "./UI";
import type { AnalysisResponse } from "../api/portfolio";
import { observationCount } from "./AnalysisContext";

export function MethodologyModal({
  analysis,
  onClose,
}: {
  analysis: AnalysisResponse | null;
  onClose: () => void;
}) {
  return (
    <Modal title="The numbers behind the view" onClose={onClose}>
      <div className="method-intro">
        <Info size={20} />
        <p>
          Pandaset models portfolio results from the available price history.
          Results are estimates, not executed trades. The active analysis shows
          its price source and freshness.
        </p>
      </div>
      <dl className="method-list">
        <dt>Sample period</dt>
        <dd>
          {analysis
            ? `${observationCount(analysis)} daily return observations in the active ${analysis.data_mode === "demo" ? "fictional" : "modeled"} analysis. Research history can cover a different period.`
            : "The active observation count appears with each analysis after it loads."}
        </dd>
        <dt>Portfolio model</dt>
        <dd>
          Constant daily allocations, with no deposits, withdrawals, fees, or
          taxes. Portfolio values are illustrative.
        </dd>
        <dt>Risk & correlation</dt>
        <dd>
          Volatility uses the sample covariance matrix, annualized by 252
          trading days. Risk contributions sum to 100%; they can be negative for
          diversifying positions.
        </dd>
        <dt>Returns & drawdown</dt>
        <dd>
          Returns compound daily. Return contribution uses each day’s allocation
          and preceding portfolio growth. Drawdown is the largest decline from
          an earlier peak in the sample.
        </dd>
        <dt>Research & explanations</dt>
        <dd>
          Research primers link to official sources. Explanations, when
          available, describe supplied evidence; they do not change the modeled
          portfolio figures.
        </dd>
      </dl>
    </Modal>
  );
}
