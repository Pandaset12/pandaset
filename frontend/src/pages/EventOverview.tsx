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
import type { AnalysisResponse } from "../api/portfolio";
import type { PortfolioAsset } from "../types/portfolioAsset";

export default function Overview({
  analysis,
  assets,
  onEdit,
  onBrief,
  onMethod,
}: {
  analysis: AnalysisResponse;
  assets: PortfolioAsset[];
  onEdit: () => void;
  onBrief: () => void;
  onMethod: () => void;
}) {
  const [view, setView] = useState<"holdings" | "drivers">("holdings");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"weight" | "return">("weight");
  const holdings = assets
    .map((asset) => ({
      asset,
      weight: analysis.weights[asset.symbol] ?? 0,
      symbol: asset.symbol,
    }))
    .filter(
      ({ asset, weight }) =>
        weight > 0 &&
        `${asset.symbol} ${asset.name}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "weight"
        ? b.weight - a.weight
        : (analysis.return_contribution?.[b.symbol] ?? -Infinity) -
          (analysis.return_contribution?.[a.symbol] ?? -Infinity),
    );
  const topRisk = Object.entries(analysis.risk_contribution)
    .filter(([, value]) => value !== null)
    .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
  const topAsset = assets.find((asset) => asset.symbol === topRisk?.[0]);
  const chartValues = analysis.series?.portfolio_index;
  const chartDates = analysis.series?.dates ?? [];
  const portfolioSeries = chartValues?.every(
    (value): value is number => value !== null,
  )
    ? chartValues
    : null;
  const sectors = Object.entries(
    assets.reduce<Record<string, number>>((grouped, asset) => {
      const category = asset.sector ?? "Unclassified";
      grouped[category] =
        (grouped[category] ?? 0) + (analysis.weights[asset.symbol] ?? 0);
      return grouped;
    }, {}),
  ).filter(([, value]) => value > 0);
  const largestAllocation = assets
    .filter((asset) => (analysis.weights[asset.symbol] ?? 0) > 0)
    .sort(
      (left, right) =>
        (analysis.weights[right.symbol] ?? 0) -
        (analysis.weights[left.symbol] ?? 0),
    )[0];
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
        <button className="button subtle" onClick={onBrief}>
          <ChatBubbleLeftRight size={16} />
          Brief this portfolio
        </button>
      </PageHeading>
      <LiveQuotesPanel
        symbols={Object.keys(analysis.weights).filter(
          (symbol) => analysis.weights[symbol] > 0,
        )}
      />
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
                className={`return-caption ${analysis.portfolio_return === null ? "" : analysis.portfolio_return >= 0 ? "positive" : "negative"}`}
              >
                {analysis.portfolio_return ===
                null ? null : analysis.portfolio_return >= 0 ? (
                  <ArrowUpRight size={17} />
                ) : (
                  <ArrowDownRight size={17} />
                )}
                {analysis.annualized_return === null
                  ? "Annualized return unavailable"
                  : `${signedPct(analysis.annualized_return)} annualized`}
                <span className="muted"> over the saved analysis period</span>
              </div>
            </div>
            <span className="label-chip">
              {analysis.observation_count === null
                ? "Observation count unavailable"
                : `${analysis.observation_count} return observations`}
            </span>
          </div>
          {portfolioSeries && portfolioSeries.length > 1 ? (
            <LineChart
              dates={chartDates}
              series={portfolioSeries}
              label="Portfolio index"
              compact
            />
          ) : (
            <p className="api-state" role="status">
              Dated portfolio history is unavailable for this saved analysis.
            </p>
          )}
          <div className="performance-bottom">
            <span>Normalized portfolio value · saved analysis dates</span>
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
                {pct(analysis.weights[topAsset.symbol] ?? 0, 0)} of capital and
                accounts for {pct(topRisk[1] ?? 0, 0)} of estimated portfolio
                volatility.
              </p>
              <div className="focus-bars">
                <div>
                  <span>Capital allocated</span>
                  <strong>
                    {pct(analysis.weights[topAsset.symbol] ?? 0, 0)}
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
          <span>Largest allocation</span>
          <strong>
            {largestAllocation
              ? pct(analysis.weights[largestAllocation.symbol], 0)
              : "Unavailable"}
            <small>{largestAllocation?.symbol ?? "No saved holding"}</small>
          </strong>
        </div>
        <div>
          <span>Holdings</span>
          <strong>
            {assets
              .filter((asset) => (analysis.weights[asset.symbol] ?? 0) > 0)
              .length.toString()
              .padStart(2, "0")}
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
                          <span>
                            <strong>{asset.symbol}</strong>
                            <small>{asset.short}</small>
                          </span>
                        </a>
                      </th>
                      <td className="align-right">{pct(weight, 0)}</td>
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
          <SectionTitle title="Explore your holdings">
            <TextLink to="#/research">Research</TextLink>
          </SectionTitle>
          {assets
            .filter((asset) => (analysis.weights[asset.symbol] ?? 0) > 0)
            .sort(
              (left, right) =>
                (analysis.weights[right.symbol] ?? 0) -
                (analysis.weights[left.symbol] ?? 0),
            )
            .slice(0, 3)
            .map((asset, index) => (
              <a
                className="briefing-item"
                key={asset.symbol}
                href={`#/research?symbol=${asset.symbol}`}
              >
                <span className="note-index">0{index + 1}</span>
                <div>
                  <h3>{asset.name}</h3>
                  <div className="briefing-meta">
                    <span>{asset.symbol}</span>
                    <span>
                      {pct(analysis.weights[asset.symbol] ?? 0, 0)} allocated
                    </span>
                    <ArrowUpRight size={16} />
                  </div>
                </div>
              </a>
            ))}
          {assets.every(
            (asset) => (analysis.weights[asset.symbol] ?? 0) <= 0,
          ) && (
            <p className="api-state" role="status">
              No saved holdings are available for research.
            </p>
          )}
        </section>
      </div>
    </>
  );
}
