import { useState } from "react";
import {
  ArrowUpRight,
  ChatBubbleLeftRight,
  InformationCircle as Info,
  RectangleStack as Layers,
} from "../components/icons";
import { assets } from "../../../quant/data";
import { analyze, correlationMatrix, pct } from "../../../quant/analytics";
import {
  AssetMark,
  PageHeading,
  SectionTitle,
  NextStep,
} from "../components/UI";
export default function Risk({
  weights,
  onAsk,
  onMethod,
}: {
  weights: number[];
  onAsk: (q?: string) => void;
  onMethod: () => void;
}) {
  const metrics = analyze(weights);
  const active = assets
    .map((a, i) => ({ a, i }))
    .filter(({ i }) => weights[i] > 0)
    .sort((a, b) => metrics.risk[b.i] - metrics.risk[a.i]);
  const [pair, setPair] = useState<[number, number]>([0, 1]);
  const [view, setView] = useState<"sectors" | "holdings">("sectors");
  const top = assets[metrics.topRisk];
  const selectedPositions = pair.map((assetIndex) =>
    active.findIndex(({ i }) => i === assetIndex),
  );
  const hasSelectedPair =
    selectedPositions[0] >= 0 &&
    selectedPositions[1] >= 0 &&
    selectedPositions[0] !== selectedPositions[1];
  const selectedOrder = hasSelectedPair
    ? [Math.min(...selectedPositions), Math.max(...selectedPositions)]
    : [0, active.length > 1 ? 1 : 0];
  const selected: [number, number] = [
    active[selectedOrder[0]].i,
    active[selectedOrder[1]].i,
  ];
  const corr = correlationMatrix[selected[0]][selected[1]];
  const max = Math.max(...weights, ...metrics.risk.map((v) => v * 100)) * 1.12;
  return (
    <>
      <PageHeading
        title="Risk & exposure"
        description="Understand how your holdings behave together."
      >
        <button className="button subtle" onClick={onMethod}>
          <Info size={16} />
          How we measure risk
        </button>
        <button
          className="button dark"
          onClick={() => onAsk("Explain my risk concentration")}
        >
          <ChatBubbleLeftRight size={16} />
          Explain my risk
        </button>
      </PageHeading>
      <div className="risk-summary">
        <div className="risk-intro">
          <span className="label-chip">
            <Layers size={14} />
            PORTFOLIO RISK
          </span>
          <h2>
            {top.short} drives
            <br />
            <em>{pct(metrics.risk[metrics.topRisk], 0)}</em> of your risk.
          </h2>
          <p>
            Position size tells part of the story. Volatility and the way assets
            move together tell the rest.
          </p>
          <a href={`#/what-if?reduce=${top.symbol}`} className="text-link">
            Test a smaller position
            <ArrowUpRight size={17} />
          </a>
        </div>
        <section className="risk-bars-panel">
          <SectionTitle title="Capital vs. risk">
            <div className="chart-legend">
              <span>
                <i className="legend-square pale" />
                Capital
              </span>
              <span>
                <i className="legend-square" />
                Risk
              </span>
            </div>
          </SectionTitle>
          <div className="risk-bars">
            {active.map(({ a, i }) => (
              <a
                href={`#/research?symbol=${a.symbol}`}
                className="risk-bar-row"
                key={a.symbol}
              >
                <span className="risk-ticker">
                  <AssetMark asset={a} small />
                  <strong>{a.symbol}</strong>
                </span>
                <div className="risk-bar-pair">
                  <div>
                    <i
                      className="capital-bar"
                      style={{ width: `${(weights[i] / max) * 100}%` }}
                    />
                    <span>{weights[i]}%</span>
                  </div>
                  <div>
                    <i
                      className="risk-bar"
                      style={{
                        width: `${((Math.abs(metrics.risk[i]) * 100) / max) * 100}%`,
                      }}
                    />
                    <span>{pct(metrics.risk[i], 1)}</span>
                  </div>
                </div>
                <ArrowUpRight size={15} />
              </a>
            ))}
          </div>
          <p className="muted small-text">
            Risk contribution estimates how much each holding adds to or offsets
            portfolio risk over this sample year, accounting for how its daily
            returns move with the rest. Negative values reduced modeled risk.
          </p>
        </section>
      </div>
      <div className="two-columns risk-detail">
        <section>
          <SectionTitle
            eyebrow="HOW THINGS MOVE TOGETHER"
            title="Correlation, at a glance"
          >
            <button
              className="inline-icon"
              onClick={onMethod}
              aria-label="About correlation"
            >
              <Info size={17} />
            </button>
          </SectionTitle>
          <div className="matrix-scroll">
            <table className="correlation-table">
              <caption className="sr-only">
                {active.length > 1
                  ? "Correlation of daily returns over one year. Select a cell above the diagonal for a pair explanation. The lower half is blank to avoid repeating pairs. The diagonal shows each holding’s correlation with itself."
                  : "Correlation of daily returns over one year. Comparing correlation requires two holdings. Use the Long-term portfolio edit control above to add another holding."}
              </caption>
              <thead>
                <tr>
                  <th />
                  {active.map(({ a }) => (
                    <th key={a.symbol} scope="col">
                      {a.symbol}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {active.map(({ a, i }, rowIndex) => (
                  <tr key={a.symbol}>
                    <th scope="row">{a.symbol}</th>
                    {active.map(({ a: b, i: j }, columnIndex) => {
                      const value = correlationMatrix[i][j];
                      const intensity = Math.round(Math.abs(value) * 68);
                      const background =
                        i === j
                          ? "var(--panel-deep)"
                          : value < 0
                            ? `color-mix(in srgb, var(--negative) ${intensity}%, var(--surface))`
                            : `color-mix(in srgb, var(--bamboo) ${intensity}%, var(--surface))`;
                      const color = "var(--ink)";
                      const isDiagonal = rowIndex === columnIndex;
                      const isSelectable = rowIndex < columnIndex;

                      return (
                        <td
                          key={b.symbol}
                          className={
                            isDiagonal
                              ? "matrix-static matrix-diagonal"
                              : isSelectable
                                ? ""
                                : "matrix-empty"
                          }
                        >
                          {isSelectable ? (
                            <button
                              className={
                                selected[0] === i && selected[1] === j
                                  ? "selected"
                                  : ""
                              }
                              style={{ background, color }}
                              onClick={() => setPair([i, j])}
                              aria-label={`${a.symbol} and ${b.symbol}: ${value.toFixed(2)} correlation`}
                              aria-pressed={
                                selected[0] === i && selected[1] === j
                              }
                            >
                              {value.toFixed(2)}
                            </button>
                          ) : isDiagonal ? (
                            <span
                              style={{ background, color }}
                              aria-label={`${a.symbol} self-correlation: ${value.toFixed(2)}`}
                            >
                              {value.toFixed(2)}
                            </span>
                          ) : null}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="matrix-hint small-text">
            {active.length > 1
              ? "Select a cell above the diagonal to explore a pair. The lower half is blank to avoid repeating pairs. Diagonal cells show each holding’s self-correlation."
              : "Correlation needs two holdings. Use the Long-term portfolio edit control above to add another holding."}
          </p>
          <div className="matrix-key">
            <span>−1 · Opposite</span>
            <div />
            <span>+1 · Together</span>
          </div>
          <div className="correlation-insight">
            <strong>
              {active.length > 1
                ? `${assets[selected[0]].symbol} × ${assets[selected[1]].symbol}`
                : `${assets[selected[0]].symbol} · one holding`}
              {active.length > 1 && <span>{corr.toFixed(2)}</span>}
            </strong>
            <p>
              {active.length < 2
                ? "Correlation describes how two holdings move together. Add another holding with the Long-term portfolio edit control above to compare a pair."
                : selected[0] === selected[1]
                  ? "An asset is perfectly correlated with itself. Select two different holdings to explore their relationship."
                  : corr > 0.65
                    ? "These holdings often moved together in the sample. Owning both may offer less diversification than their separate names suggest."
                    : corr > 0.25
                      ? "These holdings had a moderate tendency to move together. Their returns still differ on many days."
                      : corr < -0.1
                        ? "These holdings tended to move in opposite directions in the sample. This relationship can change over time."
                        : "These holdings showed a weak relationship in the sample. Low historical correlation does not guarantee protection in a downturn."}
            </p>
          </div>
        </section>
        <section className="exposure-section">
          <SectionTitle
            eyebrow="WHERE YOUR CAPITAL SITS"
            title="Allocation breakdown"
          />
          <div
            className="segmented wide-segment"
            aria-label="Allocation grouping"
          >
            <button
              aria-pressed={view === "sectors"}
              onClick={() => setView("sectors")}
            >
              By category
            </button>
            <button
              aria-pressed={view === "holdings"}
              onClick={() => setView("holdings")}
            >
              By holding
            </button>
          </div>
          <div className="allocation-mosaic" aria-label="Portfolio allocation">
            {(view === "sectors"
              ? metrics.sectors.map(([label, v]) => ({
                  label,
                  value: v,
                  color: assets.find((a) => a.sector === label)!.color,
                }))
              : active.map(({ a, i }) => ({
                  label: a.symbol,
                  value: weights[i] / 100,
                  color: a.color,
                }))
            ).map(({ label, value, color }) => (
              <div
                key={label}
                style={{
                  flexGrow: value,
                  background: color,
                  backgroundColor: `color-mix(in srgb, ${color} 38%, var(--raised))`,
                }}
                title={`${label}: ${pct(value)}`}
              >
                {value > 0.12 && <span>{pct(value, 0)}</span>}
              </div>
            ))}
          </div>
          <div className="exposure-list">
            {(view === "sectors"
              ? metrics.sectors.map(([label, v]) => ({
                  label,
                  value: v,
                  color: assets.find((a) => a.sector === label)!.color,
                }))
              : active.map(({ a, i }) => ({
                  label: a.symbol,
                  value: weights[i] / 100,
                  color: a.color,
                }))
            ).map(({ label, value, color }) => (
              <div key={label}>
                <span>
                  <i style={{ background: color }} />
                  {label}
                </span>
                <strong>{pct(value, 0)}</strong>
              </div>
            ))}
          </div>
          <div className="note-panel">
            <Info size={18} />
            <p>
              <strong>Look beyond the label.</strong> Broad-market funds can
              include companies you hold directly. This view groups funds
              separately and does not look through their underlying holdings.
            </p>
          </div>
        </section>
      </div>
      <NextStep
        title="What would a different mix look like?"
        body="Adjust your allocations and compare the estimated risk side by side."
        to="#/what-if"
        label="Open the scenario lab"
      />
    </>
  );
}
