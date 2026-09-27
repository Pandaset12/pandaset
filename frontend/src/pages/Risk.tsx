import { useState } from "react";
import {
  ArrowUpRight,
  ChatBubbleLeftRight,
  InformationCircle as Info,
  RectangleStack as Layers,
} from "../components/icons";
import { assets } from "../../../quant/data";
import { pct } from "../../../quant/analytics";
import {
  AssetMark,
  PageHeading,
  SectionTitle,
  NextStep,
} from "../components/UI";
import type { AnalysisResponse } from "../api/portfolio";
import { AnalysisDetails, SampleContext } from "../components/AnalysisContext";

export default function Risk({
  analysis,
  onExplain,
  onMethod,
}: {
  analysis: AnalysisResponse;
  onExplain: () => void;
  onMethod: () => void;
}) {
  const [pair, setPair] = useState<[string, string] | null>(null);
  const [view, setView] = useState<"sectors" | "holdings">("sectors");
  const active = assets
    .map((asset) => ({
      asset,
      weight: analysis.weights[asset.symbol] ?? 0,
      risk: analysis.risk_contribution[asset.symbol] ?? null,
    }))
    .filter((item) => item.weight > 0)
    .sort((a, b) => (b.risk ?? -Infinity) - (a.risk ?? -Infinity));
  const bestDefined = active.find((item) => item.risk !== null);
  const top = bestDefined?.asset ?? active[0]?.asset;
  const selected: [string, string] =
    pair &&
    active.some((item) => item.asset.symbol === pair[0]) &&
    active.some((item) => item.asset.symbol === pair[1])
      ? pair
      : [
          active[0]?.asset.symbol ?? "",
          active[1]?.asset.symbol ?? active[0]?.asset.symbol ?? "",
        ];
  const correlation =
    analysis.correlation_matrix?.[selected[0]]?.[selected[1]] ?? null;
  const max =
    Math.max(
      1,
      ...active.map((item) => item.weight * 100),
      ...active.map((item) => Math.abs(item.risk ?? 0) * 100),
    ) * 1.12;
  const categories = Object.entries(
    active.reduce<Record<string, number>>((grouped, { asset, weight }) => {
      grouped[asset.sector] = (grouped[asset.sector] ?? 0) + weight;
      return grouped;
    }, {}),
  ).sort((a, b) => b[1] - a[1]);
  const exposure =
    view === "sectors"
      ? categories.map(([label, value]) => ({
          label,
          value,
          color:
            assets.find((asset) => asset.sector === label)?.color ?? "#888",
        }))
      : active.map(({ asset, weight }) => ({
          label: asset.symbol,
          value: weight,
          color: asset.color,
        }));

  return (
    <>
      <PageHeading
        title="Risk & exposure"
        description="Understand how the holdings in your saved analysis behave together."
      >
        <button className="button subtle" onClick={onMethod}>
          <Info size={16} />
          How we measure risk
        </button>
        <button className="button dark" onClick={onExplain}>
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
          {top && bestDefined && bestDefined.risk !== null ? (
            <>
              <h2>
                {top.short} contributes
                <br />
                <em>{pct(bestDefined.risk, 0)}</em> of estimated risk.
              </h2>
              <p>
                Risk contribution and volatility below come from the saved
                analysis.
              </p>
              <SampleContext analysis={analysis} />
              <a href={`#/what-if?reduce=${top.symbol}`} className="text-link">
                Test a smaller position
                <ArrowUpRight size={17} />
              </a>
            </>
          ) : (
            <>
              <h2>Risk contribution unavailable.</h2>
              <p>
                The backend did not return a defined risk contribution for the
                active analysis.
              </p>
            </>
          )}
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
            {active.map(({ asset, weight, risk }) => (
              <a
                href={`#/research?symbol=${asset.symbol}`}
                className="risk-bar-row"
                key={asset.symbol}
              >
                <span className="risk-ticker">
                  <AssetMark asset={asset} small />
                  <strong>{asset.symbol}</strong>
                </span>
                <div className="risk-bar-pair">
                  <div>
                    <i
                      className="capital-bar"
                      style={{ width: `${((weight * 100) / max) * 100}%` }}
                    />
                    <span>{pct(weight, 0)}</span>
                  </div>
                  <div>
                    <i
                      className={`risk-bar ${risk !== null && risk < 0 ? "negative" : ""}`}
                      style={{
                        width: `${((Math.abs(risk ?? 0) * 100) / max) * 100}%`,
                      }}
                    />
                    <span>{risk === null ? "Unavailable" : pct(risk, 1)}</span>
                  </div>
                </div>
                <ArrowUpRight size={15} />
              </a>
            ))}
          </div>
          <p className="muted small-text">
            Risk contribution is an estimate based on the available daily return
            sample. Red bars mark negative contributions. Undefined values
            remain unavailable.
          </p>
        </section>
      </div>
      <AnalysisDetails analysis={analysis} />
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
          {!analysis.correlation_matrix ? (
            <p className="api-state" role="status">
              Correlation matrix unavailable for this analysis.
            </p>
          ) : (
            <>
              <div className="matrix-scroll">
                <table className="correlation-table">
                  <caption className="sr-only">
                    Pairwise correlations of daily returns for the active
                    analysis. Undefined correlations are labeled unavailable.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Holding</th>
                      {active.map(({ asset }) => (
                        <th key={asset.symbol} scope="col">
                          {asset.symbol}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {active.map(({ asset: row }, rowIndex) => (
                      <tr key={row.symbol}>
                        <th scope="row">{row.symbol}</th>
                        {active.map(({ asset: column }, columnIndex) => {
                          const value =
                            analysis.correlation_matrix?.[row.symbol]?.[
                              column.symbol
                            ] ?? null;
                          const diagonal = rowIndex === columnIndex;
                          const selectable =
                            rowIndex < columnIndex && value !== null;
                          const intensity = Math.round(
                            Math.abs(value ?? 0) * 68,
                          );
                          const background =
                            value === null || diagonal
                              ? "var(--panel-deep)"
                              : value < 0
                                ? `color-mix(in srgb, var(--negative) ${intensity}%, var(--surface))`
                                : `color-mix(in srgb, var(--bamboo) ${intensity}%, var(--surface))`;
                          return (
                            <td
                              key={column.symbol}
                              className={
                                diagonal
                                  ? "matrix-static matrix-diagonal"
                                  : selectable
                                    ? ""
                                    : "matrix-empty"
                              }
                            >
                              {selectable ? (
                                <button
                                  className={
                                    selected[0] === row.symbol &&
                                    selected[1] === column.symbol
                                      ? "selected"
                                      : ""
                                  }
                                  style={{
                                    background,
                                    color: "var(--ink)",
                                  }}
                                  onClick={() =>
                                    setPair([row.symbol, column.symbol])
                                  }
                                  aria-label={`${row.symbol} and ${column.symbol}: ${value.toFixed(2)} correlation`}
                                  aria-pressed={
                                    selected[0] === row.symbol &&
                                    selected[1] === column.symbol
                                  }
                                >
                                  {value.toFixed(2)}
                                </button>
                              ) : diagonal ? (
                                <span
                                  style={{ background }}
                                  aria-label={`${row.symbol} self-correlation: ${value === null ? "unavailable" : value.toFixed(2)}`}
                                >
                                  {value === null ? "—" : value.toFixed(2)}
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
                Select a cell above the diagonal to explore a pair. The lower
                half is blank to avoid repeating pairs.
              </p>
              <div className="matrix-key">
                <span>−1 · Opposite</span>
                <div />
                <span>+1 · Together</span>
              </div>
              <div className="correlation-insight">
                <strong>
                  {selected[0] && selected[1]
                    ? `${selected[0]} × ${selected[1]}`
                    : "Correlation unavailable"}
                  <span>
                    {correlation === null
                      ? "Unavailable"
                      : correlation.toFixed(2)}
                  </span>
                </strong>
                <p>
                  {active.length < 2
                    ? "Correlation describes how two holdings move together. Add another holding to compare a pair."
                    : selected[0] === selected[1]
                      ? "An asset is perfectly correlated with itself. Select two different holdings to explore their relationship."
                      : correlation === null
                        ? "Correlation is unavailable for this pair in the available sample."
                        : correlation > 0.65
                          ? "These holdings often moved together in the sample. Owning both may offer less diversification than their separate names suggest."
                          : correlation > 0.25
                            ? "These holdings had a moderate tendency to move together. Their returns still differ on many days."
                            : correlation < -0.1
                              ? "These holdings tended to move in opposite directions in the sample. This relationship can change over time."
                              : "These holdings showed a weak relationship in the sample. Low historical correlation does not guarantee protection in a downturn."}
                </p>
              </div>
            </>
          )}
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
            {exposure.map(({ label, value, color }) => (
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
            {exposure.map(({ label, value, color }) => (
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
              <strong>Look beyond the label.</strong> Funds are grouped as their
              own category; this view does not look through underlying holdings.
            </p>
          </div>
        </section>
      </div>
      <NextStep
        title="What would a different mix look like?"
        body="Adjust your allocations and compare backend estimates side by side."
        to="#/what-if"
        label="Open the scenario lab"
      />
    </>
  );
}
