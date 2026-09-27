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
import type { Asset } from "../../../quant/data";
import { pct, showAnnualizedReturn, signedPct } from "../../../quant/analytics";
import {
  AnalysisDetails,
  historySessionLabel,
  historySourceLabel,
  observationCount,
  SampleContext,
} from "../components/AnalysisContext";
import { AssetMark, PageHeading, SectionTitle, Empty } from "../components/UI";
import { LineChart } from "../components/LineChart";
import { LiveQuotesPanel } from "../components/LiveQuotesPanel";
import { allocationPercent } from "../workspace/holdings";
import type { AnalysisResponse } from "../api/portfolio";

export default function Overview({
  portfolioName,
  analysis,
  holdings: portfolioAssets,
  onEdit,
  onBrief,
  onMethod,
}: {
  portfolioName: string;
  analysis: AnalysisResponse;
  holdings: Asset[];
  onEdit: () => void;
  onBrief: () => void;
  onMethod: () => void;
}) {
  const [view, setView] = useState<"holdings" | "drivers">("holdings");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"weight" | "return">("weight");
  const symbols = Object.keys(analysis.weights).filter(
    (symbol) => analysis.weights[symbol] > 0,
  );
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
  const largestHolding = Object.entries(analysis.weights)
    .filter(([, weight]) => weight > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
  const chartValues = analysis.series?.portfolio_index;
  const chartDates = analysis.series?.dates ?? [];
  const portfolioSeries =
    chartValues?.length === chartDates.length &&
    chartValues?.every((value): value is number => value !== null)
      ? chartValues
      : null;
  const benchmark = analysis.series?.asset_index.VTI;
  const benchmarkSeries =
    benchmark?.length === chartDates.length &&
    benchmark?.every((value): value is number => value !== null)
      ? benchmark
      : undefined;
  const returnContributions = Object.values(analysis.return_contribution ?? {});
  const contributionRange = Math.max(
    0.0001,
    ...returnContributions
      .filter((value): value is number => value !== null)
      .map(Math.abs),
  );

  return (
    <>
      <PageHeading title={portfolioName}>
        <button className="button subtle" onClick={onEdit}>
          <SlidersHorizontal size={16} />
          Edit portfolio
        </button>
        <button className="button subtle" onClick={onBrief}>
          <ChatBubbleLeftRight size={16} />
          Brief this portfolio
        </button>
      </PageHeading>
      <LiveQuotesPanel symbols={symbols} />
      <div className="overview-top">
        <section
          className="performance-panel"
          aria-labelledby="performance-title"
        >
          <div className="performance-head">
            <div>
              <div className="eyebrow" id="performance-title">
                {analysis.data_mode === "demo"
                  ? "ILLUSTRATIVE PORTFOLIO RETURN"
                  : "MODELED PORTFOLIO RETURN"}{" "}
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
              {showAnnualizedReturn(observationCount(analysis)) &&
              analysis.annualized_return !== null ? (
                <div
                  className={`return-caption ${(analysis.portfolio_return ?? 0) >= 0 ? "positive" : "negative"}`}
                >
                  {(analysis.portfolio_return ?? 0) >= 0 ? (
                    <ArrowUpRight size={17} />
                  ) : (
                    <ArrowDownRight size={17} />
                  )}
                  {signedPct(analysis.annualized_return)} annualized
                  <span className="muted"> over the available history</span>
                </div>
              ) : (
                <p className="return-caption muted">
                  Annualized return withheld for this short history.
                </p>
              )}
              <SampleContext analysis={analysis} />
            </div>
          </div>
          {portfolioSeries && portfolioSeries.length > 1 ? (
            <LineChart
              dates={chartDates}
              series={portfolioSeries}
              secondary={benchmarkSeries}
              secondaryLabel="VTI history"
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
              Normalized portfolio index · {historySourceLabel(analysis)} ·
              through {historySessionLabel(analysis)}
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
                portfolio volatility over {observationCount(analysis)} daily
                return observations.
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
      <AnalysisDetails analysis={analysis} />
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
          <span>Largest allocation</span>
          <strong>
            {largestHolding
              ? allocationPercent(largestHolding[1])
              : "Unavailable"}
            <small>
              {largestHolding
                ? `${largestHolding[0]} · saved weight`
                : "No holding"}
            </small>
          </strong>
        </div>
        <div>
          <span>Holdings</span>
          <strong>
            {Object.keys(analysis.weights).length.toString().padStart(2, "0")}
            <small>In the saved portfolio</small>
          </strong>
        </div>
      </div>
      <div className="overview-bottom overview-bottom-single">
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
                          aria-label={`Research ${asset.symbol}, ${asset.name}`}
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
        </section>
      </div>
    </>
  );
}
