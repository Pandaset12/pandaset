import { useState, useRef, useEffect } from "react";
import {
  ArrowRight,
  RotateCcw,
  Plus,
  Minus,
  Check,
  Sparkles,
  LoaderCircle,
  Info,
  X,
} from "lucide-react";
import { assets } from "../data";
import { analyze, validateWeights, pct, pp } from "../analytics";
import {
  AssetMark,
  PageHeading,
  SectionTitle,
  Modal,
  Empty,
} from "../components/UI";
import { LineChart } from "../components/LineChart";
export default function WhatIf({
  weights,
  onApply,
  onAsk,
  query,
}: {
  weights: number[];
  onApply: (w: number[]) => void;
  onAsk: (q?: string) => void;
  query: URLSearchParams;
}) {
  const initial = () => {
    const copy = [...weights];
    const reduce = assets.findIndex((a) => a.symbol === query.get("reduce"));
    if (reduce >= 0) {
      const amount = Math.min(10, copy[reduce]);
      copy[reduce] -= amount;
      copy[reduce === 5 ? 4 : 5] += amount;
    }
    return copy;
  };
  const [draft, setDraft] = useState(initial);
  const [result, setResult] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [addAsset, setAddAsset] = useState("");
  const [visible, setVisible] = useState(() =>
    assets.map(
      (a, i) => weights[i] > 0 || a.symbol === query.get("asset") || i === 5,
    ),
  );
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  const total = draft.reduce((s, v) => s + v, 0);
  const valid = validateWeights(draft);
  const current = analyze(weights);
  const proposed = result ? analyze(result) : null;
  const stale = !!result && draft.some((v, i) => v !== result[i]);
  const changed = draft.some((v, i) => v !== weights[i]);
  const singleStocks = assets
    .map((asset, i) => ({ asset, i }))
    .filter(
      ({ asset, i }) =>
        weights[i] > 0 && ["Technology", "Financials"].includes(asset.sector),
    );
  const largestOverall = (allocation: number[]) => {
    const index = allocation.indexOf(Math.max(...allocation));
    return {
      label: `${assets[index].symbol} · ${pct(allocation[index] / 100)}`,
      weightPoints: allocation[index],
    };
  };
  const largestSingleStock = (allocation: number[]) => {
    const largest = assets
      .map((asset, i) => ({ asset, weight: allocation[i] }))
      .filter(
        ({ asset, weight }) =>
          weight > 0 && ["Technology", "Financials"].includes(asset.sector),
      )
      .sort((a, b) => b.weight - a.weight)[0];
    return largest
      ? {
          label: `${largest.asset.symbol} · ${pct(largest.weight / 100)}`,
          weightPoints: largest.weight,
        }
      : { label: "None · 0.0%", weightPoints: 0 };
  };
  const concentrationRows = result
    ? [
        {
          label: "Largest individual stock",
          before: largestSingleStock(weights),
          after: largestSingleStock(result),
        },
        {
          label: "Largest overall holding",
          before: largestOverall(weights),
          after: largestOverall(result),
        },
      ]
    : [];
  function preset(kind: string) {
    const next = [...weights];
    if (kind === "reduce") {
      if (!singleStocks.length) return;
      const from = singleStocks.reduce((best, entry) =>
        current.risk[entry.i] > current.risk[best.i] ? entry : best,
      ).i;
      const amount = Math.min(10, next[from]);
      next[from] -= amount;
      next[4] += amount;
    } else if (kind === "bonds") {
      const from = next.reduce(
        (best, weight, i) => (i !== 5 && weight > next[best] ? i : best),
        0,
      );
      const amount = Math.min(15, next[from]);
      next[from] -= amount;
      next[5] += amount;
    } else {
      assets.forEach((_, i) => {
        next[i] = i < 5 ? 16 : i === 5 ? 20 : 0;
      });
    }
    setDraft(next);
    setVisible(next.map((v) => v > 0));
    setResult(null);
  }
  function calculate() {
    if (!valid || !changed) return;
    setBusy(true);
    timer.current = setTimeout(() => {
      setResult([...draft]);
      setBusy(false);
    }, 300);
  }
  const added = assets.map((a, i) => ({ a, i })).filter(({ i }) => !visible[i]);
  return (
    <>
      <PageHeading
        eyebrow="THE SCENARIO LAB"
        title="A change, before the change."
        description="Try a different allocation. See how the trade-offs compare."
      >
        <span className="scenario-badge">
          <span />
          Hypothetical portfolio
        </span>
      </PageHeading>
      <div className="scenario-presets">
        <span>START WITH A QUESTION</span>
        <button
          disabled={busy || !singleStocks.length}
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
        <button disabled={busy} onClick={() => preset("equal")}>
          A more balanced mix
          <ArrowRight size={14} />
        </button>
      </div>
      <div className="scenario-workspace">
        <section className="scenario-editor">
          <SectionTitle eyebrow="01 / ADJUST" title="Build your scenario">
            <button
              className="icon-button"
              aria-label="Reset scenario"
              disabled={busy}
              onClick={() => {
                setDraft([...weights]);
                setVisible(weights.map((v) => v > 0));
                setResult(null);
              }}
            >
              <RotateCcw size={17} />
            </button>
          </SectionTitle>
          <div className="editor-table-head">
            <span>Holding</span>
            <span>Current</span>
            <span>Proposed</span>
          </div>
          <div className="allocation-editor">
            {assets.map(
              (a, i) =>
                visible[i] && (
                  <div className="editor-row" key={a.symbol}>
                    <div className="editor-asset">
                      <AssetMark asset={a} small />
                      <strong>{a.symbol}</strong>
                    </div>
                    <span className="current-weight">{weights[i]}%</span>
                    <div className="weight-input">
                      <button
                        aria-label={`Decrease ${a.symbol} allocation`}
                        disabled={draft[i] <= 0 || busy}
                        onClick={() =>
                          setDraft(
                            draft.map((v, j) =>
                              j === i ? Math.max(0, v - 1) : v,
                            ),
                          )
                        }
                      >
                        <Minus size={12} />
                      </button>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        inputMode="decimal"
                        aria-label={`${a.symbol} proposed allocation`}
                        aria-invalid={draft[i] < 0 || draft[i] > 100}
                        value={draft[i]}
                        disabled={busy}
                        onChange={(e) =>
                          setDraft(
                            draft.map((v, j) =>
                              j === i ? Number(e.target.value) : v,
                            ),
                          )
                        }
                      />
                      <span>%</span>
                      <button
                        aria-label={`Increase ${a.symbol} allocation`}
                        disabled={draft[i] >= 100 || busy}
                        onClick={() =>
                          setDraft(
                            draft.map((v, j) =>
                              j === i ? Math.min(100, v + 1) : v,
                            ),
                          )
                        }
                      >
                        <Plus size={12} />
                      </button>
                    </div>
                    <button
                      className="remove-asset"
                      aria-label={`Remove ${a.symbol} from scenario`}
                      disabled={busy}
                      onClick={() => {
                        setDraft(draft.map((v, j) => (j === i ? 0 : v)));
                        setVisible(
                          visible.map((v, j) => (j === i ? false : v)),
                        );
                      }}
                    >
                      <X size={13} />
                    </button>
                  </div>
                ),
            )}
          </div>
          {visible.every((v) => !v) && (
            <Empty title="Start with an asset">
              Add a holding below to build your scenario.
            </Empty>
          )}
          {added.length > 0 && (
            <div className="add-asset">
              <select
                value={addAsset}
                aria-label="Asset to add"
                disabled={busy}
                onChange={(e) => setAddAsset(e.target.value)}
              >
                <option value="">Add an asset…</option>
                {added.map(({ a }) => (
                  <option key={a.symbol} value={a.symbol}>
                    {a.symbol} · {a.short}
                  </option>
                ))}
              </select>
              <button
                className="icon-button bordered"
                aria-label="Add selected asset"
                disabled={!addAsset || busy}
                onClick={() => {
                  setVisible(
                    visible.map((v, i) => v || assets[i].symbol === addAsset),
                  );
                  setAddAsset("");
                }}
              >
                <Plus size={17} />
              </button>
            </div>
          )}
          <div
            className={`allocation-total ${valid ? "valid" : "invalid"}`}
            aria-live="polite"
          >
            <span>Total allocation</span>
            <strong>
              {Number(total.toFixed(2))}%{" "}
              {valid ? <Check size={16} /> : <Info size={16} />}
            </strong>
          </div>
          {!valid && (
            <p className="field-error" role="alert">
              {draft.some((v) => v < 0 || v > 100)
                ? "Each allocation must be between 0% and 100%."
                : `${total < 100 ? "Allocate" : "Remove"} ${Math.abs(100 - total).toFixed(1)}% to reach 100%.`}
            </p>
          )}
          <button
            className="button dark full"
            onClick={calculate}
            disabled={!valid || !changed || busy}
          >
            {busy ? (
              <>
                <LoaderCircle size={16} className="spin" />
                Calculating…
              </>
            ) : (
              <>
                Compare portfolios
                <ArrowRight size={17} />
              </>
            )}
          </button>
          <p className="editor-note">
            {!changed
              ? "Change an allocation or choose a starting question."
              : "Your current portfolio stays unchanged until you choose to use this scenario."}
          </p>
        </section>
        <section className="scenario-results" aria-busy={busy}>
          <SectionTitle
            eyebrow="02 / COMPARE"
            title={proposed ? "The trade-offs, in view." : "What could change?"}
          >
            {proposed && (
              <span className={`results-status ${stale ? "stale" : ""}`}>
                {stale ? "Changes not calculated" : "Scenario calculated"}
              </span>
            )}
          </SectionTitle>
          {proposed ? (
            <>
              <div className="comparison-summary">
                <span className="eyebrow">ESTIMATED ANNUALIZED VOLATILITY</span>
                <div className="volatility-change">
                  <span>{pct(current.volatility)}</span>
                  <ArrowRight size={26} />
                  <strong>{pct(proposed.volatility)}</strong>
                  <span className="delta-pill">
                    {pp(proposed.volatility - current.volatility)}
                  </span>
                </div>
                <p>
                  {proposed.volatility < current.volatility
                    ? "This mix had lower estimated volatility in the sample."
                    : "This mix had higher estimated volatility in the sample."}{" "}
                  {proposed.return < current.return
                    ? "Its modeled return was also lower."
                    : "Its modeled return was also higher."}
                </p>
              </div>
              <table className="scenario-comparison">
                <thead>
                  <tr>
                    <th>Metric · past year</th>
                    <th>Current</th>
                    <th>Proposed</th>
                    <th>Change</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Modeled return", current.return, proposed.return],
                    [
                      "Largest drawdown",
                      current.maxDrawdown,
                      proposed.maxDrawdown,
                    ],
                  ].map(([label, before, after]) => (
                    <tr key={String(label)}>
                      <th>{label}</th>
                      <td>{pct(Number(before))}</td>
                      <td>{pct(Number(after))}</td>
                      <td>{pp(Number(after) - Number(before))}</td>
                    </tr>
                  ))}
                  {concentrationRows.map(({ label, before, after }) => (
                    <tr key={label}>
                      <th>{label}</th>
                      <td>{before.label}</td>
                      <td>{after.label}</td>
                      <td>
                        {pp((after.weightPoints - before.weightPoints) / 100)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="scenario-concentration-note">
                Individual stocks are listed separately. The overall holding row
                also includes funds, such as VTI and TLT.
              </p>
              <LineChart
                series={proposed.path}
                secondary={current.path}
                label="Proposed"
                secondaryLabel="Current"
                compact
              />
              <div className="scenario-result-actions">
                <button
                  className="text-button"
                  onClick={() =>
                    onAsk(
                      `Explain this scenario: volatility changes from ${pct(current.volatility)} to ${pct(proposed.volatility)}, and sample return changes from ${pct(current.return)} to ${pct(proposed.return)}.`,
                    )
                  }
                >
                  <Sparkles size={16} />
                  Explain the trade-offs
                </button>
                <button
                  className="button dark"
                  disabled={stale || busy}
                  onClick={() => setConfirm(true)}
                >
                  Use this allocation
                  <ArrowRight size={16} />
                </button>
              </div>
            </>
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
                Adjust the weights on the left to compare volatility,
                concentration, and modeled performance.
              </p>
              <div className="comparison-preview">
                <span>
                  Current volatility<strong>{pct(current.volatility)}</strong>
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
              Calculations use the same illustrative 252-day return sample for
              both portfolios, with constant weights. This is a comparison of a
              sample period, not a forecast. Trading costs and taxes are
              excluded.
            </p>
          </div>
        </section>
      </div>
      {confirm && result && (
        <Modal title="Use this allocation?" onClose={() => setConfirm(false)}>
          <p className="note-body">
            This applies the scenario throughout PortfolioLens for this browser
            session. Reloading restores the example portfolio. It does not place
            trades or connect to a brokerage.
          </p>
          <div className="modal-actions">
            <button className="button subtle" onClick={() => setConfirm(false)}>
              Keep exploring
            </button>
            <button
              className="button dark"
              onClick={() => {
                onApply(result);
                setConfirm(false);
              }}
            >
              Use sample allocation
              <Check size={16} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
