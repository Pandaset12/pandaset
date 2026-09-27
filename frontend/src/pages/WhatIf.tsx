import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowPath,
  Check,
  Scale,
  InformationCircle as Info,
} from "../components/icons";
import { assets } from "../../../quant/data";
import {
  pct,
  pp,
  showAnnualizedReturn,
  transferAllocation,
} from "../../../quant/analytics";
import { observationCount, SampleContext } from "../components/AnalysisContext";
import {
  comparePortfolio,
  createRequestGuard,
  type AnalysisResponse,
  type WhatIfResponse,
} from "../api/portfolio";
import { AssetMark, PageHeading, SectionTitle, Modal } from "../components/UI";
import { LineChart } from "../components/LineChart";

export default function WhatIf({
  analysis,
  weights,
  onApply,
  onExplainScenario,
  query,
}: {
  analysis: AnalysisResponse;
  weights: number[];
  onApply: (weights: number[]) => Promise<boolean>;
  onExplainScenario: (weights: number[]) => void;
  query: URLSearchParams;
}) {
  const [draft, setDraft] = useState(() => {
    const next = [...weights];
    const reduced = assets.findIndex(
      (asset) => asset.symbol === query.get("reduce"),
    );
    if (reduced >= 0) {
      const amount = Math.min(10, next[reduced]);
      next[reduced] -= amount;
      next[reduced === 5 ? 4 : 5] += amount;
    }
    return next;
  });
  const [comparison, setComparison] = useState<{
    weights: number[];
    response: WhatIfResponse;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [applying, setApplying] = useState(false);
  const [transferFrom, setTransferFrom] = useState(() =>
    weights.indexOf(Math.max(...weights)),
  );
  const [transferTo, setTransferTo] = useState(5);
  const [transferAmount, setTransferAmount] = useState("5");
  const [selectedPreset, setSelectedPreset] = useState("");
  const requestId = useRef(createRequestGuard());
  useEffect(() => () => requestId.current.invalidate(), []);
  const total = draft.reduce((sum, value) => sum + value, 0);
  const valid =
    draft.length === assets.length &&
    draft.every(
      (value) => Number.isFinite(value) && value >= 0 && value <= 100,
    ) &&
    Math.abs(total - 100) < 0.001;
  const changed = draft.some((value, index) => value !== weights[index]);
  const stale =
    !!comparison &&
    draft.some((value, index) => value !== comparison.weights[index]);
  const available = comparison && !stale ? comparison.response : null;
  const transferValue = Number(transferAmount);
  const canTransfer =
    valid &&
    transferFrom !== transferTo &&
    Number.isFinite(transferValue) &&
    transferValue > 0 &&
    transferValue <= draft[transferFrom] &&
    draft[transferTo] + transferValue <= 100;
  const draftChanges = assets.flatMap((asset, index) =>
    draft[index] === weights[index]
      ? []
      : [{ asset, current: weights[index], proposed: draft[index] }],
  );
  const metric = (value: number | null | undefined) =>
    value === null || value === undefined ? "Unavailable" : pct(value);

  function preset(kind: "reduce" | "bonds" | "balanced") {
    const next = [...weights];
    if (kind === "reduce") {
      const largestRisk = Object.entries(analysis.risk_contribution)
        .filter(
          ([symbol, value]) =>
            value !== null && (analysis.weights[symbol] ?? 0) > 0,
        )
        .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
      const index = assets.findIndex(
        (asset) => asset.symbol === largestRisk?.[0],
      );
      if (index < 0) return;
      const amount = Math.min(10, next[index]);
      const shifted = transferAllocation(
        next,
        index,
        index === 4 ? 5 : 4,
        amount,
      );
      setDraft(shifted);
      setSelectedPreset("Less single-stock risk");
      return;
    } else if (kind === "bonds") {
      const index = next.reduce(
        (best, value, i) => (i !== 5 && value > next[best] ? i : best),
        0,
      );
      const amount = Math.min(15, next[index]);
      const shifted = transferAllocation(next, index, 5, amount);
      setDraft(shifted);
      setSelectedPreset("More Treasury exposure");
      return;
    } else
      assets.forEach((_, index) => {
        next[index] = index < 5 ? 16 : index === 5 ? 20 : 0;
      });
    setDraft(next);
    setSelectedPreset("A more balanced mix");
  }

  function moveWeight() {
    if (!canTransfer) return;
    setDraft(
      transferAllocation(draft, transferFrom, transferTo, transferValue),
    );
    setSelectedPreset("");
  }

  async function calculate() {
    if (!valid || !changed || busy) return;
    const id = requestId.current.begin();
    setBusy(true);
    setError("");
    try {
      const response = await comparePortfolio(analysis.portfolio_id, draft);
      if (requestId.current.isCurrent(id))
        setComparison({ weights: [...draft], response });
    } catch (reason) {
      if (requestId.current.isCurrent(id))
        setError(
          reason instanceof Error
            ? reason.message
            : "The comparison service is unavailable.",
        );
    } finally {
      if (requestId.current.isCurrent(id)) setBusy(false);
    }
  }

  const current = available?.current_analysis;
  const proposed = available?.proposed_analysis;
  const currentPath = current?.series?.portfolio_index;
  const proposedPath = proposed?.series?.portfolio_index;
  const comparedWeights = comparison?.weights ?? draft;
  const chartReady =
    !!currentPath &&
    !!proposedPath &&
    currentPath.length === proposedPath.length &&
    currentPath.every((value): value is number => value !== null) &&
    proposedPath.every((value): value is number => value !== null);

  async function applyScenario() {
    if (!comparison || stale) return;
    setApplying(true);
    if (await onApply(comparison.weights)) setConfirm(false);
    setApplying(false);
  }

  return (
    <>
      <PageHeading
        title="Scenario comparison"
        description="Try a different allocation. Compare modeled results across the same fictional dates."
      >
        <span className="scenario-badge">
          <span />
          Hypothetical portfolio
        </span>
      </PageHeading>
      <div className="scenario-presets">
        <span>START WITH A QUESTION</span>
        <button
          disabled={
            busy ||
            !Object.values(analysis.risk_contribution).some(
              (value) => value !== null,
            )
          }
          onClick={() => preset("reduce")}
        >
          Less single-stock risk
          <ArrowRight size={14} />
        </button>
        <button
          disabled={busy || weights[5] === 100}
          onClick={() => preset("bonds")}
        >
          More Treasury exposure
          <ArrowRight size={14} />
        </button>
        <button disabled={busy} onClick={() => preset("balanced")}>
          A more balanced mix
          <ArrowRight size={14} />
        </button>
      </div>
      {draftChanges.length > 0 && (
        <div className="scenario-changes" aria-live="polite">
          <strong>{selectedPreset || "Proposed shifts"}</strong>
          <ul>
            {draftChanges.map(({ asset, current, proposed }) => (
              <li key={asset.symbol}>
                {asset.symbol} {current}% → {proposed}%
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="scenario-workspace">
        <section className="scenario-editor">
          <SectionTitle eyebrow="01 / ADJUST" title="Build your scenario">
            <button
              className="text-button"
              aria-label="Reset scenario"
              disabled={busy}
              onClick={() => {
                setDraft([...weights]);
                setSelectedPreset("");
              }}
            >
              <ArrowPath size={16} />
              Reset
            </button>
          </SectionTitle>
          <div className="allocation-transfer">
            <strong>Move an allocation</strong>
            <div>
              <label>
                From
                <select
                  value={transferFrom}
                  disabled={busy}
                  onChange={(event) =>
                    setTransferFrom(Number(event.target.value))
                  }
                >
                  {assets.map((asset, index) => (
                    <option key={asset.symbol} value={index}>
                      {asset.symbol} · {draft[index]}%
                    </option>
                  ))}
                </select>
              </label>
              <label>
                To
                <select
                  value={transferTo}
                  disabled={busy}
                  onChange={(event) =>
                    setTransferTo(Number(event.target.value))
                  }
                >
                  {assets.map((asset, index) => (
                    <option key={asset.symbol} value={index}>
                      {asset.symbol} · {draft[index]}%
                    </option>
                  ))}
                </select>
              </label>
              <label className="transfer-amount">
                Percentage points
                <input
                  type="number"
                  min="0.1"
                  max={draft[transferFrom]}
                  step="0.1"
                  inputMode="decimal"
                  value={transferAmount}
                  disabled={busy}
                  onChange={(event) => setTransferAmount(event.target.value)}
                />
              </label>
            </div>
            <button
              className="button subtle"
              disabled={!canTransfer || busy}
              onClick={moveWeight}
            >
              Move {canTransfer ? transferValue : ""} points
              <ArrowRight size={16} />
            </button>
            <p>
              Moves keep the total at 100%. You can also edit each row below.
            </p>
          </div>
          <div className="editor-table-head">
            <span>Holding</span>
            <span>Current</span>
            <span>Proposed</span>
          </div>
          <div className="allocation-editor">
            {assets.map((asset, index) => (
              <div className="editor-row" key={asset.symbol}>
                <div className="editor-asset">
                  <AssetMark asset={asset} small />
                  <strong>{asset.symbol}</strong>
                </div>
                <span className="current-weight">{weights[index]}%</span>
                <div className="weight-input">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    inputMode="decimal"
                    aria-label={`${asset.symbol} proposed allocation`}
                    aria-invalid={draft[index] < 0 || draft[index] > 100}
                    value={draft[index]}
                    disabled={busy}
                    onChange={(event) => {
                      setDraft(
                        draft.map((value, i) =>
                          i === index ? Number(event.target.value) : value,
                        ),
                      );
                      setSelectedPreset("");
                    }}
                  />
                  <span>%</span>
                </div>
              </div>
            ))}
          </div>
          <div
            className={`allocation-total ${valid ? "valid" : "invalid"}`}
            aria-live="polite"
          >
            <span>Total allocation</span>
            <strong>{Number(total.toFixed(2))}%</strong>
          </div>
          {!valid && (
            <p className="field-error" role="alert">
              {draft.some((value) => value < 0 || value > 100)
                ? "Each allocation must be between 0% and 100%."
                : `${total < 100 ? "Allocate" : "Remove"} ${Math.abs(100 - total).toFixed(1)}% to reach 100%.`}
            </p>
          )}
          <button
            className="button dark full"
            onClick={() => void calculate()}
            disabled={!valid || !changed || busy}
          >
            {busy ? (
              <>
                <ArrowPath size={16} className="spin" />
                Comparing…
              </>
            ) : (
              <>
                Compare portfolios
                <ArrowRight size={17} />
              </>
            )}
          </button>
          {error && (
            <div className="api-state" role="alert">
              <p>{error}</p>
              <button
                className="button subtle"
                onClick={() => void calculate()}
                disabled={busy || !valid}
              >
                Retry comparison
              </button>
            </div>
          )}
          <p className="editor-note">
            {!changed
              ? "Change an allocation to compare modeled results."
              : "The active portfolio stays unchanged until you apply a successful comparison."}
          </p>
        </section>
        <section className="scenario-results" aria-busy={busy}>
          <SectionTitle
            eyebrow="02 / COMPARE"
            title={
              available ? "The trade-offs, in view." : "What could change?"
            }
          >
            {comparison && (
              <span className={`results-status ${stale ? "stale" : ""}`}>
                {stale ? "Comparison is stale" : "Modeled comparison"}
              </span>
            )}
          </SectionTitle>
          {available && current && proposed ? (
            <>
              <div className="comparison-summary">
                <span className="eyebrow">MODELED ANNUALIZED VOLATILITY</span>
                <div className="volatility-change">
                  <span>{pct(current.portfolio_volatility)}</span>
                  <ArrowRight size={26} />
                  <strong>{pct(proposed.portfolio_volatility)}</strong>
                  <span className="delta-pill">
                    {pp(available.delta.portfolio_volatility)}
                  </span>
                </div>
                <SampleContext analysis={analysis} />
                <p>
                  Change means proposed minus current. Both portfolios use the
                  same dates.
                </p>
              </div>
              <table className="scenario-comparison">
                <thead>
                  <tr>
                    <th>Metric · available history</th>
                    <th>Current</th>
                    <th>Proposed</th>
                    <th>Change</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th>Sample return</th>
                    <td>{metric(current.portfolio_return)}</td>
                    <td>{metric(proposed.portfolio_return)}</td>
                    <td>{metric(available.delta.portfolio_return)}</td>
                  </tr>
                  {showAnnualizedReturn(observationCount(analysis)) && (
                    <tr>
                      <th>Annualized return</th>
                      <td>{metric(current.annualized_return)}</td>
                      <td>{metric(proposed.annualized_return)}</td>
                      <td>{metric(available.delta.annualized_return)}</td>
                    </tr>
                  )}
                  <tr>
                    <th>Largest drawdown</th>
                    <td>{metric(current.max_drawdown)}</td>
                    <td>{metric(proposed.max_drawdown)}</td>
                    <td>{metric(available.delta.max_drawdown)}</td>
                  </tr>
                  <tr>
                    <th>Largest holding</th>
                    <td>{largest(weights)}</td>
                    <td>{largest(comparedWeights)}</td>
                    <td>
                      {pp(
                        largestWeight(comparedWeights) - largestWeight(weights),
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
              {chartReady && proposed.series && (
                <LineChart
                  dates={proposed.series.dates}
                  series={proposedPath as number[]}
                  secondary={currentPath as number[]}
                  label="Proposed"
                  secondaryLabel="Current"
                  compact
                />
              )}
              <div className="scenario-result-actions">
                <button
                  className="text-button"
                  disabled={busy || stale || !comparison || !valid}
                  onClick={() => onExplainScenario(draft)}
                >
                  <Scale size={16} />
                  Explain the trade-offs
                </button>
                <button
                  className="button dark"
                  disabled={busy || stale || !comparison}
                  onClick={() => setConfirm(true)}
                >
                  Use this allocation
                  <ArrowRight size={16} />
                </button>
              </div>
            </>
          ) : stale ? (
            <div className="scenario-empty">
              <h3>Draft changed after the comparison.</h3>
              <p>
                Run the comparison again to see results for the current
                allocation.
              </p>
              <button
                className="button dark"
                disabled={!valid || busy}
                onClick={() => void calculate()}
              >
                Compare updated allocation
                <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <div className="scenario-empty">
              <div className="scenario-illustration" aria-hidden="true">
                <div>
                  <i style={{ height: "75%" }} />
                  <i style={{ height: "47%" }} />
                </div>
                <div>
                  <i style={{ height: "55%" }} />
                  <i style={{ height: "68%" }} />
                </div>
                <div>
                  <i style={{ height: "35%" }} />
                  <i style={{ height: "46%" }} />
                </div>
              </div>
              <h3>
                A different mix.
                <br />A different risk profile.
              </h3>
              <p>
                Adjust the weights and compare using the same available dates.
              </p>
              <div className="comparison-preview">
                <span>
                  Current volatility
                  <strong>{pct(analysis.portfolio_volatility)}</strong>
                </span>
                <ArrowRight size={22} />
                <span>
                  Proposed volatility<strong>—</strong>
                </span>
              </div>
            </div>
          )}
          <div className="scenario-disclaimer">
            <Info size={15} />
            <p>
              Results use {analysis.lookback_days} available fictional daily
              return observations. The demo fixture contains short history; no
              longer period is inferred or extrapolated. No forecast, trading
              costs, or taxes are included.
            </p>
          </div>
        </section>
      </div>
      {confirm && comparison && (
        <Modal
          title="Use this allocation?"
          onClose={applying ? () => undefined : () => setConfirm(false)}
        >
          <p className="note-body">
            PandaSet will create and analyze the new sample allocation, then
            replace the active portfolio after the backend confirms it. This
            does not place trades or connect to a brokerage.
          </p>
          <div className="modal-actions">
            <button
              className="button subtle"
              disabled={applying}
              onClick={() => setConfirm(false)}
            >
              Keep exploring
            </button>
            <button
              className="button dark"
              disabled={applying}
              onClick={() => void applyScenario()}
            >
              {applying ? "Saving…" : "Use sample allocation"}
              <Check size={16} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function largest(allocation: number[]) {
  const index = allocation.indexOf(Math.max(...allocation));
  return `${assets[index].symbol} · ${allocation[index]}%`;
}
function largestWeight(allocation: number[]) {
  return Math.max(...allocation) / 100;
}
