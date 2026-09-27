import { useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  XMark as X,
  MagnifyingGlass as Search,
} from "../components/icons";
import { pct, signedPct } from "../../../quant/analytics";
import type { AnalysisResponse } from "../api/portfolio";
import type { PortfolioAsset } from "../types/portfolioAsset";
import { AssetMark, PageHeading, Empty } from "../components/UI";
import { LineChart } from "../components/LineChart";

function completePath(
  values: (number | null)[] | undefined,
  dates: string[] | undefined,
) {
  if (!values || !dates || values.length < 2 || values.length !== dates.length)
    return null;
  return values.every(
    (value): value is number => value !== null && Number.isFinite(value),
  )
    ? values
    : null;
}

function safeHttpsSource(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export default function Research({
  assets,
  analysis,
  weights,
  onSummarizeSource,
  query,
}: {
  assets: PortfolioAsset[];
  analysis: AnalysisResponse;
  weights: number[];
  onSummarizeSource: (symbol: string) => void;
  query: URLSearchParams;
}) {
  const [search, setSearch] = useState("");
  const [compare, setCompare] = useState("");
  const [tab, setTab] = useState<"overview" | "sources">("overview");
  const requestedSymbol = query.get("symbol");
  const selected = requestedSymbol
    ? (assets.find((asset) => asset.symbol === requestedSymbol) ?? null)
    : (assets[0] ?? null);
  const results = assets.filter((asset) =>
    `${asset.symbol} ${asset.name}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const peer = selected
    ? (assets.find(
        (asset) => asset.symbol === compare && asset.symbol !== selected.symbol,
      ) ?? null)
    : null;
  const history = analysis.series;
  const selectedPath = selected
    ? completePath(history?.asset_index[selected.symbol], history?.dates)
    : null;
  const peerPath = peer
    ? completePath(history?.asset_index[peer.symbol], history?.dates)
    : null;
  const selectedReturn = selectedPath
    ? selectedPath.at(-1)! / selectedPath[0] - 1
    : null;
  const peerReturn = peerPath ? peerPath.at(-1)! / peerPath[0] - 1 : null;
  const selectedIndex = selected
    ? assets.findIndex((asset) => asset.symbol === selected.symbol)
    : -1;
  const peerIndex = peer
    ? assets.findIndex((asset) => asset.symbol === peer.symbol)
    : -1;
  const allocation = selectedIndex >= 0 ? weights[selectedIndex] : null;
  const peerAllocation = peerIndex >= 0 ? weights[peerIndex] : null;
  const sourceUrl = selected ? safeHttpsSource(selected.source) : null;

  return (
    <>
      <PageHeading
        title="Research library"
        description="Review a saved holding, its analysis history, and available sources."
      />
      <div className="research-workspace">
        <aside className="research-index">
          <label className="search-field large">
            <Search size={18} />
            <input
              aria-label="Search your holdings"
              type="search"
              placeholder="Holding name or ticker"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="asset-index-list">
            {results.map((asset) => (
              <a
                className={`asset-index-item ${asset.symbol === selected?.symbol ? "active" : ""}`}
                href={`#/research?symbol=${encodeURIComponent(asset.symbol)}`}
                key={asset.symbol}
                aria-current={
                  asset.symbol === selected?.symbol ? "page" : undefined
                }
              >
                <AssetMark asset={asset} />
                <span>
                  <strong>{asset.symbol}</strong>
                  <small>{asset.short}</small>
                </span>
                <ArrowUpRight size={16} />
              </a>
            ))}
          </div>
          {results.length === 0 && (
            <Empty
              title={
                assets.length === 0 ? "No holdings yet" : "No matching holdings"
              }
            >
              {assets.length === 0
                ? "Select or create a portfolio to research its holdings."
                : "Try another holding name or ticker."}
            </Empty>
          )}
          <div className="library-note">
            <p>
              {assets.length} saved{" "}
              {assets.length === 1 ? "holding" : "holdings"}
            </p>
            <span>
              History and returns come from the selected saved analysis.
            </span>
          </div>
        </aside>
        <section className="company-detail">
          {selected ? (
            <>
              <div className="company-header">
                <div className="company-identity">
                  <AssetMark asset={selected} />
                  <div>
                    <div className="eyebrow">
                      {selected.symbol} <span> / </span>{" "}
                      {selected.sector ?? "Category unavailable"}
                    </div>
                    <h2>{selected.name}</h2>
                  </div>
                </div>
                <span className="ownership-tag">
                  {allocation === null
                    ? "Allocation unavailable"
                    : `${allocation}% of your portfolio`}
                </span>
              </div>
              <p className="company-description">
                {selected.description ??
                  "A sourced description is not available for this holding."}
              </p>
              <div className="company-tabs">
                <div
                  className="underlined-tabs"
                  role="group"
                  aria-label="Research sections"
                >
                  <button
                    aria-pressed={tab === "overview"}
                    onClick={() => setTab("overview")}
                  >
                    Overview
                  </button>
                  <button
                    aria-pressed={tab === "sources"}
                    onClick={() => setTab("sources")}
                  >
                    Sources
                  </button>
                </div>
                <label className="compare-select">
                  <span className="sr-only">
                    Compare against another holding
                  </span>
                  <select
                    value={compare === selected.symbol ? "" : compare}
                    onChange={(event) => setCompare(event.target.value)}
                  >
                    <option value="">Compare with…</option>
                    {assets
                      .filter((asset) => asset.symbol !== selected.symbol)
                      .map((asset) => (
                        <option key={asset.symbol} value={asset.symbol}>
                          {asset.symbol}
                        </option>
                      ))}
                  </select>
                  <ChevronDown size={14} />
                </label>
              </div>
              {tab === "overview" ? (
                <>
                  <div className="company-chart-head">
                    <div>
                      <span className="eyebrow">SAVED NORMALIZED HISTORY</span>
                      <div className="company-price">
                        {selectedReturn === null
                          ? "Unavailable"
                          : signedPct(selectedReturn)}
                        <span> over available history</span>
                      </div>
                    </div>
                    <span className="label-chip">
                      {analysis.observation_count === null
                        ? "Observation count unavailable"
                        : `${analysis.observation_count} return observations`}
                    </span>
                  </div>
                  {selectedPath && history ? (
                    <LineChart
                      dates={history.dates}
                      series={selectedPath}
                      secondary={peerPath ?? undefined}
                      label={selected.symbol}
                      secondaryLabel={peerPath ? peer?.symbol : undefined}
                      compact
                    />
                  ) : (
                    <p role="status" className="api-state">
                      Dated history for {selected.symbol} is unavailable in this
                      saved analysis.
                    </p>
                  )}
                  <div
                    className="backend-analysis"
                    aria-label="Analysis history provenance"
                  >
                    <strong>
                      {analysis.data_mode === "demo"
                        ? "SAMPLE DATA"
                        : "SAVED ANALYSIS"}
                    </strong>
                    <span>
                      {analysis.data_quality.source} ·{" "}
                      {analysis.data_quality.freshness}
                      {history?.dates.length
                        ? ` · ${history.dates[0]} to ${history.dates.at(-1)}`
                        : ""}
                    </span>
                    {analysis.data_quality.warnings.map((warning) => (
                      <small key={warning}>{warning}</small>
                    ))}
                  </div>
                  {peer && (
                    <div className="comparison-table-wrap">
                      <div className="comparison-title">
                        <strong>
                          {selected.symbol} vs. {peer.symbol}
                        </strong>
                        <button
                          className="icon-button"
                          onClick={() => setCompare("")}
                          aria-label="Remove comparison"
                        >
                          <X size={16} />
                        </button>
                      </div>
                      <table className="comparison-table">
                        <thead>
                          <tr>
                            <th>Saved analysis</th>
                            <th>{selected.symbol}</th>
                            <th>{peer.symbol}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <th>Available-history return</th>
                            <td>
                              {selectedReturn === null
                                ? "Unavailable"
                                : signedPct(selectedReturn)}
                            </td>
                            <td>
                              {peerReturn === null
                                ? "Unavailable"
                                : signedPct(peerReturn)}
                            </td>
                          </tr>
                          <tr>
                            <th>Portfolio allocation</th>
                            <td>
                              {allocation === null
                                ? "Unavailable"
                                : pct(allocation / 100, 0)}
                            </td>
                            <td>
                              {peerAllocation === null
                                ? "Unavailable"
                                : pct(peerAllocation / 100, 0)}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className="company-thesis">
                    <div>
                      <h3>What to understand</h3>
                      <p>
                        {selected.thesis ??
                          "No sourced investment thesis is available for this holding."}
                      </p>
                    </div>
                    <div>
                      <h3>What to watch</h3>
                      <p>
                        {selected.watch ??
                          "No sourced watch list is available for this holding."}
                      </p>
                    </div>
                  </div>
                  <div className="company-action">
                    <a
                      className="button dark"
                      href={`#/what-if?asset=${encodeURIComponent(selected.symbol)}`}
                    >
                      Test an allocation <ArrowUpRight size={15} />
                    </a>
                  </div>
                </>
              ) : (
                <div className="sources-view">
                  <BookOpen size={26} />
                  <h3>Available sources</h3>
                  {sourceUrl ? (
                    <>
                      <p>
                        Review this holding’s linked source before using its
                        information.
                      </p>
                      <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="source-card"
                      >
                        <div>
                          <strong>{selected.short} · source</strong>
                          <span>{new URL(sourceUrl).hostname}</span>
                        </div>
                        <ArrowUpRight size={20} />
                      </a>
                      <button
                        className="button dark source-summary-button"
                        onClick={() => onSummarizeSource(selected.symbol)}
                      >
                        Summarize this source <ArrowUpRight size={15} />
                      </button>
                    </>
                  ) : (
                    <p role="status" className="api-state">
                      No source has been attached for {selected.symbol}. A
                      source summary cannot be generated yet.
                    </p>
                  )}
                </div>
              )}
            </>
          ) : (
            <Empty
              title={
                requestedSymbol ? "Holding not found" : "No holding selected"
              }
            >
              {requestedSymbol
                ? `${requestedSymbol} is not in the selected portfolio. Choose a saved holding from the list.`
                : "Select or create a portfolio to research its holdings."}
            </Empty>
          )}
        </section>
      </div>
    </>
  );
}
