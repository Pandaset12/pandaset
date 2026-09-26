import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowPath,
  Check,
  Scale,
  InformationCircle as Info,
} from "../components/icons";
import type { Asset } from "../../../quant/data";
import { pct, pp } from "../../../quant/analytics";
import {
  comparePortfolio,
  createRequestGuard,
  type AnalysisResponse,
  type WhatIfResponse,
} from "../api/portfolio";
import { AssetMark, PageHeading, SectionTitle, Modal } from "../components/UI";
import { LineChart } from "../components/LineChart";
import { parsePercentageDraft, workspaceAsset } from "../workspace/holdings";
import {
  PERCENT_SCALE,
  parsePercentage,
  isValidSymbol,
  normalizeSymbol,
} from "../components/onboarding/portfolioDraft";

export default function WhatIf({
  analysis,
  holdings,
  weights,
  onApply,
  onExplainScenario,
  query,
}: {
  analysis: AnalysisResponse;
  holdings: Asset[];
  weights: number[];
  onApply: (weights: number[], symbols: string[]) => Promise<boolean>;
  onExplainScenario: (weights: number[], symbols: string[]) => void;
  query: URLSearchParams;
}) {
  const [scenarioAssets, setScenarioAssets] = useState(holdings);
  const [newSymbol, setNewSymbol] = useState("");
  const [draftText, setDraftText] = useState(() => {
    const next = [...weights];
    const reduced = holdings.findIndex(
      (asset) => asset.symbol === query.get("reduce"),
    );
    if (reduced >= 0 && next.length > 1) {
      const amount = Math.min(10, next[reduced]);
      next[reduced] -= amount;
      next[reduced === 0 ? 1 : 0] += amount;
    }
    return next.map(String);
  });
  const [comparison, setComparison] = useState<{
    weights: number[];
    response: WhatIfResponse;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [applying, setApplying] = useState(false);
  const requestId = useRef(createRequestGuard());
  useEffect(() => () => requestId.current.invalidate(), []);
  const draft = draftText.map((text) => {
    const units = parsePercentage(text, true);
    return units === null ? Number.NaN : units / PERCENT_SCALE;
  });
  const total = draftText.reduce(
    (sum, text) => sum + (parsePercentage(text, true) ?? 0) / PERCENT_SCALE,
    0,
  );
  const symbols = scenarioAssets.map(({ symbol }) => symbol);
  const valid = parsePercentageDraft(draftText) !== null;
  const changed = draft.some((value, index) => value !== (weights[index] ?? 0));
  const stale =
    !!comparison &&
    draft.some((value, index) => value !== comparison.weights[index]);
  const available = comparison && !stale ? comparison.response : null;
  const metric = (value: number | null | undefined) =>
    value === null || value === undefined ? "Unavailable" : pct(value);

  function preset(kind: "reduce" | "bonds" | "balanced") {
    const next = [...weights];
    if (kind === "reduce") {
      const largestRisk = Object.entries(analysis.risk_contribution)
        .filter(([, value]) => value !== null)
        .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
      const index = scenarioAssets.findIndex(
        (asset) => asset.symbol === largestRisk?.[0],
      );
      if (index < 0) return;
      const target = scenarioAssets.findIndex(
        (_, candidate) => candidate !== index,
      );
      if (target < 0) return;
      const amount = Math.min(10, next[index]);
      next[index] -= amount;
      next[target] += amount;
    } else if (kind === "bonds") {
      const bond = scenarioAssets.findIndex((asset) => asset.symbol === "TLT");
      if (bond < 0) return;
      const index = next.reduce(
        (best, value, i) => (i !== bond && value > next[best] ? i : best),
        0,
      );
      if (index === bond) return;
      const amount = Math.min(15, next[index]);
      next[index] -= amount;
      next[bond] += amount;
    } else {
      const share = Math.floor((100 / next.length) * 1000000) / 1000000;
      next.forEach((_, index) => {
        next[index] =
          index === next.length - 1 ? 100 - share * (next.length - 1) : share;
      });
    }
    setDraftText(next.map(String));
  }

  async function calculate() {
    if (!valid || !changed || busy) return;
    const id = requestId.current.begin();
    setBusy(true);
    setError("");
    try {
      const response = await comparePortfolio(
        analysis.portfolio_id,
        draft,
        symbols,
      );
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
    if (await onApply(comparison.weights, symbols)) setConfirm(false);
    setApplying(false);
  }

  return (
    <>
      <PageHeading
        title="Scenario comparison"
        description="Try a different allocation. Compare the backend’s historical estimates side by side."
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
            scenarioAssets.length < 2 ||
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
          disabled={
            busy ||
            !scenarioAssets.some((asset) => asset.symbol === "TLT") ||
            scenarioAssets.length < 2
          }
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
      <div className="scenario-workspace">
        <section className="scenario-editor">
          <SectionTitle eyebrow="01 / ADJUST" title="Build your scenario">
            <button
              className="text-button"
              aria-label="Reset scenario"
              disabled={busy}
              onClick={() => {
                setScenarioAssets(holdings);
                setDraftText(weights.map(String));
                setComparison(null);
              }}
            >
              <ArrowPath size={16} />
              Reset
            </button>
          </SectionTitle>
          <div className="editor-table-head">
            <span>Holding</span>
            <span>Current</span>
            <span>Proposed</span>
          </div>
          <div className="allocation-editor">
            {scenarioAssets.map((asset, index) => (
              <div className="editor-row" key={asset.symbol}>
                <div className="editor-asset">
                  <AssetMark asset={asset} small />
                  <strong>{asset.symbol}</strong>
                </div>
                <span className="current-weight">{weights[index] ?? 0}%</span>
                <div className="weight-input">
                  <input
                    type="text"
                    inputMode="decimal"
                    aria-label={`${asset.symbol} proposed allocation`}
                    aria-invalid={
                      parsePercentage(draftText[index], true) === null
                    }
                    value={draftText[index]}
                    disabled={busy}
                    onChange={(event) =>
                      setDraftText(
                        draftText.map((value, i) =>
                          i === index ? event.target.value : value,
                        ),
                      )
                    }
                  />
                  <span>%</span>
                </div>
              </div>
            ))}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const symbol = normalizeSymbol(newSymbol);
              if (!isValidSymbol(symbol) || symbols.includes(symbol)) return;
              setScenarioAssets((current) => [
                ...current,
                workspaceAsset(symbol),
              ]);
              setDraftText((current) => [...current, "0"]);
              setComparison(null);
              setNewSymbol("");
            }}
          >
            <label htmlFor="scenario-add-symbol">
              Add a ticker to this scenario
            </label>
            <input
              id="scenario-add-symbol"
              value={newSymbol}
              onChange={(event) => setNewSymbol(event.target.value)}
              aria-label="Ticker to add"
            />
            <button type="submit" className="text-button">
              Add holding
            </button>
          </form>
          <div
            className={`allocation-total ${valid ? "valid" : "invalid"}`}
            aria-live="polite"
          >
            <span>Total allocation</span>
            <strong>{Number(total.toFixed(6))}%</strong>
          </div>
          {!valid && (
            <p className="field-error" role="alert">
              {draftText.some((value) => parsePercentage(value, true) === null)
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
              ? "Change an allocation to request a backend comparison."
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
                {stale ? "Comparison is stale" : "Backend comparison"}
              </span>
            )}
          </SectionTitle>
          {available && current && proposed ? (
            <>
              <div className="comparison-summary">
                <span className="eyebrow">ANNUALIZED VOLATILITY · BACKEND</span>
                <div className="volatility-change">
                  <span>{pct(current.portfolio_volatility)}</span>
                  <ArrowRight size={26} />
                  <strong>{pct(proposed.portfolio_volatility)}</strong>
                  <span className="delta-pill">
                    {pp(available.delta.portfolio_volatility)}
                  </span>
                </div>
                <p>
                  Difference convention: {available.difference_convention}. Both
                  portfolios use the same available sample.
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
                  <tr>
                    <th>Annualized return</th>
                    <td>{metric(current.annualized_return)}</td>
                    <td>{metric(proposed.annualized_return)}</td>
                    <td>{metric(available.delta.annualized_return)}</td>
                  </tr>
                  <tr>
                    <th>Largest drawdown</th>
                    <td>{metric(current.max_drawdown)}</td>
                    <td>{metric(proposed.max_drawdown)}</td>
                    <td>{metric(available.delta.max_drawdown)}</td>
                  </tr>
                  <tr>
                    <th>Largest holding</th>
                    <td>{largest(weights, holdings)}</td>
                    <td>{largest(comparedWeights, scenarioAssets)}</td>
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
                  onClick={() => onExplainScenario(draft, symbols)}
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
                Adjust the weights and request a backend comparison using the
                same available dates.
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

function largest(allocation: number[], holdings: Asset[]) {
  const index = allocation.indexOf(Math.max(...allocation));
  return `${holdings[index].symbol} · ${allocation[index]}%`;
}
function largestWeight(allocation: number[]) {
  return Math.max(...allocation) / 100;
}
