import { InformationCircle as Info } from "./icons";
import { Modal } from "./UI";

export function MethodologyModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="The numbers behind the view" onClose={onClose}>
      <div className="method-intro">
        <Info size={20} />
        <p>
          PandaSet is an interactive interface demo. Prices, returns, and
          portfolio values are illustrative, not live market data.
        </p>
      </div>
      <dl className="method-list">
        <dt>Sample period</dt>
        <dd>
          252 synthetic daily returns ending September 25, 2026. Every page uses
          the same observations.
        </dd>
        <dt>Portfolio model</dt>
        <dd>
          Constant daily allocations, with no deposits, withdrawals, fees, or
          taxes. Displayed value is a sample balance of $128,450.
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
          Research primers link to official sources. The analyst uses curated
          explanations and computed metrics; Gemini and news feeds are not
          connected.
        </dd>
      </dl>
    </Modal>
  );
}
