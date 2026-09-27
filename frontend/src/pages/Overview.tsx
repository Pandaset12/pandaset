import { useState } from "react";
import {
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
  AdjustmentsHorizontal as SlidersHorizontal,
  ChatBubbleLeftRight,
  MagnifyingGlass as Search,
  InformationCircle as Info,
} from "../components/icons";
import { researchNotes, type Asset } from "../../../quant/data";
import { pct, signedPct } from "../../../quant/analytics";
import {
  AssetMark,
  PageHeading,
  SectionTitle,
  TextLink,
  Empty,
} from "../components/UI";
import { LineChart } from "../components/LineChart";
import { LiveQuotesPanel } from "../components/LiveQuotesPanel";
import { allocationPercent } from "../workspace/holdings";
import type { AnalysisResponse } from "../api/portfolio";

export default function Overview({
  analysis,
  holdings: portfolioAssets,
  onEdit,
  onAsk,
  onBrief,
  onMethod,
}: {
  analysis: AnalysisResponse;
  holdings: Asset[];
  onEdit: () => void;
  onAsk: (q?: string) => void;
  onBrief: () => void;
  onMethod: () => void;
}) {
  const [view, setView] = useState<"holdings" | "drivers">("holdings");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"weight" | "return">("weight");
  const symbols = Object.keys(analysis.weights).filter((symbol) => analysis.weights[symbol] > 0);
  const holdings = portfolioAssets
    .map((asset) => ({
      asset,
      weight: analysis.weights[asset.symbol] ?? 0,
      symbol: asset.symbol,
      returnImpact: analysis.return_contribution?.[asset.symbol] ?? null,
    }))
    .filter(
      ({ asset, weight }) =>
        weight > 0 &&
        `${asset.symbol} ${asset.name}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) => {
      if (sort === "weight")
        return b.weight - a.weight || a.symbol.localeCompare(b.symbol);
      if (a.returnImpact === null)
        return b.returnImpact === null ? a.symbol.localeCompare(b.symbol) : 1;
      if (b.returnImpact === null) return -1;
      return (
        b.returnImpact - a.returnImpact || a.symbol.localeCompare(b.symbol)
      );
    });
  const topRisk = Object.entries(analysis.risk_contribution)
    .filter(([, value]) => value !== null)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
  const topAsset = portfolioAssets.find(
    (asset) => asset.symbol === topRisk?.[0],
  );
  const chartValues = analysis.series?.portfolio_index;
  const chartDates = analysis.series?.dates ?? [];
  const portfolioSeries = chartValues?.every(
    (value): value is number => value !== null,
  )
    ? chartValues
    : null;
  const benchmark = analysis.series?.asset_index.VTI;
  const benchmarkSeries = benchmark?.every(
    (value): value is number => value !== null,
  )
    ? benchmark
    : undefined;
  const sectors = Object.entries(
    portfolioAssets.reduce<Record<string, number>>((grouped, asset) => {
      grouped[asset.sector] =
        (grouped[asset.sector] ?? 0) + (analysis.weights[asset.symbol] ?? 0);
      return grouped;
    }, {}),
  ).filter(([, value]) => value > 0);
  const returnContributions = Object.values(analysis.return_contribution ?? {});
  const contributionRange = Math.max(
    0.0001,
    ...returnContributions
      .filter((value): value is number => value !== null)
      .map(Math.abs),
  );

  return (
    <>
      <PageHeading title="Portfolio overview">
        <button className="button subtle" onClick={onEdit}>
          <SlidersHorizontal size={16} />
          Edit portfolio
        </button>
        <a className="button dark" href="#/what-if">
          Explore a what-if
          <ArrowUpRight size={17} />
        </a>
        <button className="button subtle" onClick={onBrief}>
          <ChatBubbleLeftRight size={16} />
          Brief this portfolio
        </button>
      </PageHeading>
      <LiveQuotesPanel symbols={symbols} />
      <section className="backend-analysis" aria-label="Saved backend analysis">
        <div>
          <strong>
            {analysis.data_mode === "demo"
              ? "Backend demo analysis"
              : "Backend analysis"}
          </strong>
          <p>
            Analysis {analysis.analysis_id} · portfolio {analysis.portfolio_id}{" "}
            · {analysis.observation_count ?? "—"} daily return observations
          </p>
        </div>
        <span>
          {analysis.data_quality.source} · {analysis.data_quality.freshness}
        </span>
        {analysis.data_quality.warnings.length > 0 && (
          <small>{analysis.data_quality.warnings[0]}</small>
        )}
      </section>
      <div className="overview-top">
        <section
          className="performance-panel"
          aria-labelledby="performance-title"
        >
          <div className="performance-head">
            <div>
              <div className="eyebrow" id="performance-title">
                PORTFOLIO RETURN{" "}
                <button
                  className="inline-icon"
                  aria-label="About portfolio data"
                  onClick={onMethod}
                >
                  <Info size={13} />
                </button>
              </div>
              <div className="large-value">
                {analysis.portfolio_return === null
                  ? "Unavailable"
                  : signedPct(analysis.portfolio_return)}
              </div>
              <div
                className={`return-caption ${(analysis.portfolio_return ?? 0) >= 0 ? "positive" : "negative"}`}
              >
                {(analysis.portfolio_return ?? 0) >= 0 ? (
                  <ArrowUpRight size={17} />
                ) : (
                  <ArrowDownRight size={17} />
                )}
                {analysis.annualized_return === null
                  ? "Annualized return unavailable"
                  : `${signedPct(analysis.annualized_return)} annualized`}
                <span className="muted"> over the available sample</span>
              </div>
            </div>
            <span className="label-chip">
              {analysis.lookback_days} return observations
            </span>
          </div>
          {portfolioSeries && portfolioSeries.length > 1 ? (
            <LineChart
              dates={chartDates}
              series={portfolioSeries}
              secondary={benchmarkSeries}
              secondaryLabel="VTI sample history"
              label="Portfolio index"
              compact
            />
          ) : (
            <p className="api-state" role="status">
              Dated portfolio history is unavailable for this saved analysis.
            </p>
          )}
          <div className="performance-bottom">
            <span>
              Normalized portfolio value · based on the backend’s available
              dates
            </span>
            <button className="text-button" onClick={onMethod}>
              Data & methodology
              <ArrowUpRight size={13} />
            </button>
          </div>
        </section>
        <aside className="focus-panel">
          <div className="focus-label">
            <span>IN FOCUS</span>
            <span className="edition">01 / RISK</span>
          </div>
          {topAsset && topRisk?.[1] !== null ? (
            <>
              <h2>{topAsset.short} leads estimated risk contribution.</h2>
              <p>
                {topAsset.symbol} is{" "}
                {allocationPercent(analysis.weights[topAsset.symbol] ?? 0)} of
                capital and accounts for {pct(topRisk[1] ?? 0, 0)} of estimated
                portfolio volatility.
              </p>
              <div className="focus-bars">
                <div>
                  <span>Capital allocated</span>
                  <strong>
                    {allocationPercent(analysis.weights[topAsset.symbol] ?? 0)}
                  </strong>
                </div>
                <div className="focus-track">
                  <i
                    style={{
                      width: `${(analysis.weights[topAsset.symbol] ?? 0) * 100}%`,
                    }}
                  />
                </div>
                <div>
                  <span>Share of portfolio risk</span>
                  <strong>{pct(topRisk[1] ?? 0, 0)}</strong>
                </div>
                <div className="focus-track bright">
                  <i
                    style={{
                      width: `${Math.max(0, (topRisk[1] ?? 0) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </>
          ) : (
            <>
              <h2>Risk contribution unavailable.</h2>
              <p>
                The backend did not return a defined risk estimate for this
                analysis.
              </p>
            </>
          )}
          <a href="#/risk" className="focus-link">
            See the full risk picture
            <ArrowRight size={18} />
          </a>
        </aside>
      </div>
      <div className="metric-strip">
        <div>
          <span>Annualized volatility</span>
          <strong>
            {pct(analysis.portfolio_volatility)}
            <small>Backend estimate</small>
          </strong>
        </div>
        <div>
          <span>Largest drawdown</span>
          <strong>
            {analysis.max_drawdown === null
              ? "Unavailable"
              : pct(analysis.max_drawdown)}
            <small>Peak-to-trough · available history</small>
          </strong>
        </div>
        <div>
          <span>Direct technology allocation</span>
          <strong>
            {pct(
              (analysis.weights.NVDA ?? 0) +
                (analysis.weights.MSFT ?? 0) +
                (analysis.weights.AAPL ?? 0) +
                (analysis.weights.AMD ?? 0),
              0,
            )}
            <small>Direct holdings only</small>
          </strong>
        </div>
        <div>
          <span>Holdings</span>
          <strong>
            {Object.keys(analysis.weights).length.toString().padStart(2, "0")}
            <small>Across {sectors.length} categories</small>
          </strong>
        </div>
      </div>
      <div className="overview-bottom">
        <section className="holdings-section">
          <SectionTitle eyebrow="THE BUILDING BLOCKS" title="Your holdings">
            <div className="holdings-actions">
              <div className="segmented" aria-label="Holdings view">
                <button
                  aria-pressed={view === "holdings"}
                  onClick={() => setView("holdings")}
                >
                  Holdings
                </button>
                <button
                  aria-pressed={view === "drivers"}
                  onClick={() => setView("drivers")}
                >
                  Return drivers
                </button>
              </div>
              <label className="search-field">
                <Search size={15} />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  aria-label="Search holdings"
                  placeholder="Search"
                />
              </label>
              <select
                aria-label="Sort holdings"
                value={sort}
                onChange={(event) =>
                  setSort(event.target.value as "weight" | "return")
                }
              >
                <option value="weight">By allocation</option>
                <option value="return">By return impact</option>
              </select>
            </div>
          </SectionTitle>
          {view === "holdings" ? (
            <div className="table-scroll">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Holding</th>
                    <th className="align-right">Allocation</th>
                    <th className="align-right">Return contribution</th>
                    <th>Risk contribution</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {holdings.map(({ asset, weight }) => (
                    <tr key={asset.symbol}>
                      <th>
                        <a
                          href={`#/research?symbol=${asset.symbol}`}
                          className="table-asset"
                        >
                          <AssetMark asset={asset} />
                          <span className="holding-identity">
                            <strong>{asset.symbol}</strong>
                            {asset.name !== asset.symbol && (
                              <small>{asset.name}</small>
                            )}
                          </span>
                        </a>
                      </th>
                      <td className="align-right">
                        {allocationPercent(weight)}
                      </td>
                      <td className="align-right numeric">
                        {analysis.return_contribution?.[asset.symbol] == null
                          ? "Unavailable"
                          : signedPct(
                              analysis.return_contribution[asset.symbol]!,
                            )}
                      </td>
                      <td>
                        {analysis.risk_contribution[asset.symbol] == null
                          ? "Unavailable"
                          : pct(analysis.risk_contribution[asset.symbol]!)}
                      </td>
                      <td>
                        <a
                          href={`#/research?symbol=${asset.symbol}`}
                          className="icon-button"
                          aria-label={`Research ${asset.symbol}`}
                        >
                          <ArrowUpRight size={17} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div
              className="return-drivers"
              aria-label="Ranked backend return contributions"
            >
              {holdings
                .slice()
                .sort(
                  (a, b) =>
                    (analysis.return_contribution?.[b.asset.symbol] ??
                      -Infinity) -
                    (analysis.return_contribution?.[a.asset.symbol] ??
                      -Infinity),
                )
                .map(({ asset }) => {
                  const contribution =
                    analysis.return_contribution?.[asset.symbol];
                  return (
                    <div className="driver-row" key={asset.symbol}>
                      <span>{asset.symbol}</span>
                      <div className="driver-track">
                        <i
                          className={
                            contribution !== null &&
                            contribution !== undefined &&
                            contribution < 0
                              ? "loss"
                              : ""
                          }
                          style={{
                            width: `${Math.min(100, (Math.abs(contribution ?? 0) / contributionRange) * 100)}%`,
                          }}
                        />
                      </div>
                      <strong>
                        {contribution == null
                          ? "Unavailable"
                          : signedPct(contribution)}
                      </strong>
                    </div>
                  );
                })}
            </div>
          )}
          {holdings.length === 0 && (
            <Empty title="No matching holdings">
              Try another company name or ticker.
            </Empty>
          )}
          <p className="table-footnote">
            Return contribution comes from the saved backend analysis. Undefined
            values stay unavailable.
          </p>
        </section>
        <section className="briefing">
          <SectionTitle eyebrow="CONNECT THE DOTS" title="On your radar">
            <TextLink to="#/research">Research</TextLink>
          </SectionTitle>
          {researchNotes
            .filter((note) =>
              note.symbols.some(
                (symbol) => (analysis.weights[symbol] ?? 0) > 0,
              ),
            )
            .slice(0, 3)
            .map((note, index) => (
              <a
                className="briefing-item"
                key={note.id}
                href={`#/research?note=${note.id}`}
              >
                <span className="note-index">0{index + 1}</span>
                <div>
                  <div className="eyebrow">EDITORIAL PRIMER</div>
                  <h3>{note.title}</h3>
                  <div className="briefing-meta">
                    {note.symbols.slice(0, 3).map((symbol) => (
                      <span key={symbol}>{symbol}</span>
                    ))}
                    <ArrowUpRight size={16} />
                  </div>
                </div>
              </a>
            ))}
          <div className="analyst-callout">
            <ChatBubbleLeftRight size={20} />
            <div>
              <strong>Make sense of the numbers.</strong>
              <button
                className="text-button"
                onClick={() => onAsk("What is my biggest risk?")}
              >
                Ask about your portfolio
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
