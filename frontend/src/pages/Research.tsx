import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  BookOpen,
  ChevronDown,
  XMark as X,
  ChatBubbleLeftRight,
  ArrowTopRightOnSquare as ExternalLink,
  MagnifyingGlass as Search,
} from "../components/icons";
import { assets, researchNotes, assetBySymbol } from "../../../quant/data";
import { signedPct } from "../../../quant/analytics";
import {
  createRequestGuard,
  getMarketHistory,
  type MarketHistoryResponse,
} from "../api/portfolio";
import {
  AssetMark,
  PageHeading,
  SectionTitle,
  Empty,
  Modal,
} from "../components/UI";
import { LineChart } from "../components/LineChart";

export default function Research({
  weights,
  onAsk,
  query,
}: {
  weights: number[];
  onAsk: (q?: string) => void;
  query: URLSearchParams;
}) {
  const symbol = query.get("symbol");
  const selected = assetBySymbol(symbol || "NVDA");
  const idx = assets.indexOf(selected);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "owned">("all");
  const [compare, setCompare] = useState("");
  const [tab, setTab] = useState<"overview" | "sources">("overview");
  const [noteId, setNoteId] = useState<string | null>(query.get("note"));
  const [history, setHistory] = useState<MarketHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestId = useRef(createRequestGuard());
  const note = researchNotes.find((item) => item.id === noteId);
  const results = assets.filter(
    (asset, index) =>
      (filter === "all" || weights[index] > 0) &&
      `${asset.symbol} ${asset.name}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const peer =
    compare && compare !== selected.symbol ? assetBySymbol(compare) : null;
  const symbols = peer ? [selected.symbol, peer.symbol] : [selected.symbol];

  async function loadHistory() {
    const id = requestId.current.begin();
    setLoading(true);
    setError("");
    setHistory(null);
    try {
      const result = await getMarketHistory(symbols, 252);
      if (requestId.current.isCurrent(id)) setHistory(result);
    } catch (reason) {
      if (requestId.current.isCurrent(id)) {
        setHistory(null);
        setError(
          reason instanceof Error
            ? reason.message
            : "Market history is unavailable.",
        );
      }
    } finally {
      if (requestId.current.isCurrent(id)) setLoading(false);
    }
  }
  useEffect(() => {
    void loadHistory();
    return () => {
      requestId.current.invalidate();
    };
  }, [selected.symbol, compare]);

  const selectedRaw = history?.asset_index[selected.symbol];
  const selectedPath = selectedRaw?.every(
    (value): value is number => value !== null,
  )
    ? selectedRaw
    : null;
  const peerRaw = peer ? history?.asset_index[peer.symbol] : undefined;
  const peerPath = peerRaw?.every((value): value is number => value !== null)
    ? peerRaw
    : undefined;
  const sampleReturn = selectedPath?.length
    ? selectedPath.at(-1)! - selectedPath[0]
    : null;
  const peerReturn = peerPath?.length ? peerPath.at(-1)! - peerPath[0] : null;

  return (
    <>
      <PageHeading
        title="Research library"
        description="Explore a holding. Understand its place in your portfolio."
      />
      <div className="research-workspace">
        <aside className="research-index">
          <label className="search-field large">
            <Search size={18} />
            <input
              aria-label="Search research library"
              type="search"
              placeholder="Company or ticker"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="index-filter">
            <button
              aria-pressed={filter === "all"}
              onClick={() => setFilter("all")}
            >
              All assets <span>08</span>
            </button>
            <button
              aria-pressed={filter === "owned"}
              onClick={() => setFilter("owned")}
            >
              Your holdings
            </button>
          </div>
          <div className="asset-index-list">
            {results.map((asset) => (
              <a
                className={`asset-index-item ${asset.symbol === selected.symbol ? "active" : ""}`}
                href={`#/research?symbol=${asset.symbol}`}
                key={asset.symbol}
                aria-current={
                  asset.symbol === selected.symbol ? "page" : undefined
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
          {!results.length && (
            <Empty title="Nothing here yet">
              Try another ticker or view all assets.
              <button
                className="text-button"
                onClick={() => {
                  setSearch("");
                  setFilter("all");
                }}
              >
                Reset filters
              </button>
            </Empty>
          )}
          <div className="library-note">
            <span className="eyebrow">A FOCUSED UNIVERSE</span>
            <p>Eight assets. A clearer view of how they fit together.</p>
            <span>
              Price charts use backend history · currently demo fixture data
            </span>
          </div>
        </aside>
        <section className="company-detail">
          <div className="company-header">
            <div className="company-identity">
              <AssetMark asset={selected} />
              <div>
                <div className="eyebrow">
                  {selected.symbol} <span> / </span> {selected.sector}
                </div>
                <h2>{selected.name}</h2>
              </div>
            </div>
            <span className="ownership-tag">
              {weights[idx] > 0
                ? `${weights[idx]}% of your portfolio`
                : "Not in your portfolio"}
            </span>
          </div>
          <p className="company-description">{selected.description}</p>
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
                Sources & filings
                <ExternalLink size={12} />
              </button>
            </div>
            <label className="compare-select">
              <span className="sr-only">Compare against another asset</span>
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
                  <span className="eyebrow">NORMALIZED PRICE HISTORY</span>
                  <div className="company-price">
                    {sampleReturn === null
                      ? "Unavailable"
                      : signedPct(sampleReturn)}
                    <span> over available history</span>
                  </div>
                </div>
                <span className="label-chip">
                  {history?.observation_count ?? 0} return observations
                </span>
              </div>
              {loading && (
                <p role="status" className="api-state">
                  Loading dated history…
                </p>
              )}
              {error && (
                <div className="api-state" role="alert">
                  <p>{error}</p>
                  <button
                    className="button subtle"
                    onClick={() => void loadHistory()}
                    disabled={loading}
                  >
                    Retry history
                  </button>
                </div>
              )}
              {!loading && !error && selectedPath && history && (
                <LineChart
                  dates={history.dates}
                  series={selectedPath}
                  secondary={peerPath}
                  label={selected.symbol}
                  secondaryLabel={peer?.symbol}
                  compact
                />
              )}
              {!loading && !error && !selectedPath && (
                <p role="status" className="api-state">
                  Dated price history is unavailable. No local series was
                  substituted.
                </p>
              )}
              {history && (
                <div
                  className="backend-analysis"
                  aria-label="Price history provenance"
                >
                  <strong>
                    {history.data_mode === "demo" ? "DEMO DATA" : "LIVE DATA"}
                  </strong>
                  <span>
                    {history.data_source} · {history.freshness} ·{" "}
                    {history.dates[0]} to {history.dates.at(-1)}
                  </span>
                  {history.warnings.map((warning) => (
                    <small key={warning}>{warning}</small>
                  ))}
                </div>
              )}
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
                        <th>Available-history return · backend</th>
                        <th>{selected.symbol}</th>
                        <th>{peer.symbol}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th>Return</th>
                        <td>
                          {sampleReturn === null
                            ? "Unavailable"
                            : signedPct(sampleReturn)}
                        </td>
                        <td>
                          {peerReturn === null
                            ? "Unavailable"
                            : signedPct(peerReturn)}
                        </td>
                      </tr>
                      <tr>
                        <th>Portfolio allocation</th>
                        <td>{weights[idx]}%</td>
                        <td>{weights[assets.indexOf(peer)]}%</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
              <div className="company-thesis">
                <div>
                  <span className="eyebrow">EDITORIAL CONTEXT</span>
                  <h3>What to understand</h3>
                  <p>{selected.thesis}</p>
                </div>
                <div>
                  <span className="eyebrow">EDITORIAL CONTEXT</span>
                  <h3>What to watch</h3>
                  <p>{selected.watch}</p>
                </div>
              </div>
              <div className="company-action">
                <button
                  className="text-button"
                  onClick={() =>
                    onAsk(`How does ${selected.symbol} affect my portfolio?`)
                  }
                >
                  <ChatBubbleLeftRight size={16} />
                  Explain its portfolio impact
                </button>
                <a
                  className="button dark"
                  href={`#/what-if?asset=${selected.symbol}`}
                >
                  Test an allocation
                  <ArrowUpRight size={15} />
                </a>
              </div>
            </>
          ) : (
            <div className="sources-view">
              <BookOpen size={26} />
              <h3>Start with the source.</h3>
              <p>
                Use company filings and fund disclosures to check financial
                results, business risks, and portfolio composition.
              </p>
              <a
                href={selected.source}
                target="_blank"
                rel="noreferrer"
                className="source-card"
              >
                <div>
                  <strong>{selected.short} · Investor information</strong>
                  <span>Official issuer website</span>
                </div>
                <ArrowUpRight size={20} />
              </a>
              <a
                href={`https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(selected.name)}`}
                target="_blank"
                rel="noreferrer"
                className="source-card"
              >
                <div>
                  <strong>SEC EDGAR filings</strong>
                  <span>Search public disclosures</span>
                </div>
                <ArrowUpRight size={20} />
              </a>
              <p className="small-text muted">
                These links open external sources. Their content is not ingested
                into the backend demo.
              </p>
            </div>
          )}
        </section>
      </div>
      <section className="research-reading">
        <SectionTitle
          eyebrow="EDITORIAL RESEARCH"
          title="Connections worth exploring"
        />
        <div className="reading-grid">
          {researchNotes.map((item, index) => (
            <button
              className="reading-note"
              onClick={() => setNoteId(item.id)}
              key={item.id}
            >
              <span className="reading-number">0{index + 1}</span>
              <span className="eyebrow">
                EDITORIAL PRIMER · {item.category}
              </span>
              <h3>{item.title}</h3>
              <span className="reading-bottom">
                {item.read}
                <ArrowRight size={17} />
              </span>
            </button>
          ))}
        </div>
      </section>
      {note && (
        <Modal title={note.title} onClose={() => setNoteId(null)}>
          <span className="eyebrow">
            {note.category} · EDITORIAL RESEARCH PRIMER
          </span>
          <p className="note-body">{note.body}</p>
          <div className="note-tickers">
            {note.symbols.map((ticker) => (
              <a
                href={`#/research?symbol=${ticker}`}
                onClick={() => setNoteId(null)}
                className="tag-link"
                key={ticker}
              >
                {ticker}
                <ArrowUpRight size={14} />
              </a>
            ))}
          </div>
          <p className="muted small-text">
            This is editorial research context, not a report of a current market
            event.
          </p>
          <a
            className="button dark"
            href={note.url}
            target="_blank"
            rel="noreferrer"
          >
            Read the source
            <ArrowUpRight size={16} />
          </a>
        </Modal>
      )}
    </>
  );
}
