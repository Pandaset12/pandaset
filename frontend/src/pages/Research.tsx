import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  BookOpen,
  ChevronDown,
  XMark as X,
  ChatBubbleLeftRight,
  ArrowTopRightOnSquare as ExternalLink,
  MagnifyingGlass as Search,
  ArrowPath,
  InformationCircle,
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
  onSummarizeSource,
  query,
}: {
  weights: number[];
  onAsk: (q?: string) => void;
  onSummarizeSource: (symbol: string) => void;
  query: URLSearchParams;
}) {
  const symbol = query.get("symbol")?.trim().toUpperCase();
  const unsupportedSymbol =
    !!symbol && !assets.some((asset) => asset.symbol === symbol);
  const selected = assetBySymbol(symbol || "NVDA");
  const idx = assets.indexOf(selected);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "owned">("all");
  const [compare, setCompare] = useState("");
  const [tab, setTab] = useState<"overview" | "sources">("overview");
  const [noteId, setNoteId] = useState<string | null>(query.get("note"));
  const [history, setHistory] = useState<MarketHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestId = useRef(createRequestGuard());
  const sectionId = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const note = researchNotes.find((item) => item.id === noteId);
  const results = assets.filter(
    (asset, index) =>
      (filter === "all" || weights[index] > 0) &&
      `${asset.symbol} ${asset.name}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
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
    if (unsupportedSymbol) {
      setLoading(false);
      setHistory(null);
      return;
    }
    void loadHistory();
    return () => {
      requestId.current.invalidate();
    };
  }, [selected.symbol, compare, unsupportedSymbol]);

  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? 1
          : tab === "overview"
            ? 1
            : 0;
    setTab(next === 0 ? "overview" : "sources");
    tabRefs.current[next]?.focus();
  }

  const selectedRaw = history?.asset_index[selected.symbol];
  const selectedPath =
    selectedRaw &&
    selectedRaw.length >= 2 &&
    selectedRaw.length === history?.dates.length &&
    selectedRaw.every(
      (value): value is number =>
        value !== null && Number.isFinite(value) && value > 0,
    )
      ? selectedRaw
      : null;
  const peerRaw = peer ? history?.asset_index[peer.symbol] : undefined;
  const peerPath =
    peerRaw &&
    peerRaw.length >= 2 &&
    peerRaw.length === history?.dates.length &&
    peerRaw.every(
      (value): value is number =>
        value !== null && Number.isFinite(value) && value > 0,
    )
      ? peerRaw
      : undefined;
  const sampleReturn = selectedPath?.length
    ? selectedPath.at(-1)! / selectedPath[0] - 1
    : null;
  const peerReturn = peerPath?.length
    ? peerPath.at(-1)! / peerPath[0] - 1
    : null;
  const issuerHost = new URL(selected.source).hostname.replace(/^www\./, "");
  const sourceName =
    history?.data_source === "twelve_data_adjusted_daily"
      ? "Twelve Data · adjusted daily closes"
      : history?.data_source === "synthetic_fixture"
        ? "Fictional sample prices"
        : history?.data_source.replaceAll("_", " ");
  const freshnessLabel =
    history?.freshness === "fresh"
      ? "Up to date"
      : history?.freshness === "stale"
        ? "May be out of date"
        : "Freshness not verified";

  if (unsupportedSymbol) {
    return (
      <>
        <PageHeading
          title="Research library"
          description="Explore a holding. Understand its place in your portfolio."
        />
        <Empty
          title="This asset isn't in the research library"
          action={
            <a className="button subtle" href="#/research">
              Browse supported assets
            </a>
          }
        >
          We don't have a research profile for {symbol} yet. The library
          currently covers {assets.length} selected assets.
        </Empty>
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="Research library"
        description="Explore a holding. Understand its place in your portfolio."
      />
      <div className="research-workspace">
        <aside className="research-index" aria-label="Research asset directory">
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
              All assets <span>{assets.length}</span>
            </button>
            <button
              aria-pressed={filter === "owned"}
              onClick={() => setFilter("owned")}
            >
              Your holdings
            </button>
          </div>
          <p className="research-result-count" role="status" aria-live="polite">
            {results.length} {results.length === 1 ? "asset" : "assets"}
            {filter === "owned" ? " in your holdings" : " in the library"}
          </p>
          <nav className="asset-index-list" aria-label="Research assets">
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
          </nav>
          {!results.length && (
            <Empty
              title={
                search.trim()
                  ? "No matching assets"
                  : "No holdings in this library"
              }
              action={
                <button
                  className="text-button"
                  onClick={() => {
                    setSearch("");
                    setFilter("all");
                  }}
                >
                  Reset filters
                </button>
              }
            >
              {search.trim()
                ? "Try a company name or ticker, or clear your filters."
                : "Your portfolio may include assets outside this curated selection. Browse all assets to explore."}
            </Empty>
          )}
          <div className="library-note">
            <span className="eyebrow">A FOCUSED UNIVERSE</span>
            <p>Explore the businesses behind your holdings.</p>
            <span>
              Curated issuer profiles and public disclosures. Each chart
              identifies its price source.
            </span>
          </div>
        </aside>
        <section
          className="company-detail"
          aria-label={`${selected.symbol} research`}
        >
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
              role="tablist"
              aria-label="Research sections"
            >
              <button
                role="tab"
                id={`${sectionId}-overview-tab`}
                aria-controls={`${sectionId}-overview-panel`}
                aria-selected={tab === "overview"}
                tabIndex={tab === "overview" ? 0 : -1}
                ref={(node) => {
                  tabRefs.current[0] = node;
                }}
                onKeyDown={navigateTabs}
                onClick={() => setTab("overview")}
              >
                Overview
              </button>
              <button
                role="tab"
                id={`${sectionId}-sources-tab`}
                aria-controls={`${sectionId}-sources-panel`}
                aria-selected={tab === "sources"}
                tabIndex={tab === "sources" ? 0 : -1}
                ref={(node) => {
                  tabRefs.current[1] = node;
                }}
                onKeyDown={navigateTabs}
                onClick={() => setTab("sources")}
              >
                Sources & filings
              </button>
            </div>
            {tab === "overview" && (
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
            )}
          </div>
          <div
            role="tabpanel"
            id={`${sectionId}-overview-panel`}
            aria-labelledby={`${sectionId}-overview-tab`}
            hidden={tab !== "overview"}
            tabIndex={0}
          >
            <div className="company-chart-head">
              <div>
                <span className="eyebrow">NORMALIZED PRICE HISTORY</span>
                <div className="company-price">
                  {loading
                    ? "—"
                    : sampleReturn === null
                      ? "—"
                      : signedPct(sampleReturn)}
                  <span>
                    {loading
                      ? "Loading price history"
                      : sampleReturn === null
                        ? "Return not available"
                        : "over available history"}
                  </span>
                </div>
              </div>
              {history && !loading && selectedPath && (
                <span className="label-chip">
                  {history.observation_count} daily returns
                </span>
              )}
            </div>
            {loading && (
              <div
                role="status"
                className="research-chart-state"
                aria-live="polite"
              >
                <ArrowPath size={22} className="spin" aria-hidden="true" />
                <strong>
                  Loading {selected.symbol}
                  {peer ? ` and ${peer.symbol}` : ""} history
                </strong>
                <p>Fetching dated prices for this chart.</p>
                <div className="research-skeleton" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </div>
              </div>
            )}
            {error && (
              <div className="research-chart-state is-error" role="alert">
                <InformationCircle size={22} aria-hidden="true" />
                <strong>Price history couldn't be loaded</strong>
                <p>{error}</p>
                <p className="small-text muted">
                  You can still read the company profile and official sources.
                </p>
                <button
                  className="button subtle"
                  onClick={() => void loadHistory()}
                  disabled={loading}
                >
                  <ArrowPath size={15} aria-hidden="true" /> Retry history
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
              <div role="status" className="research-chart-state">
                <BookOpen size={22} aria-hidden="true" />
                <strong>No usable price history yet</strong>
                <p>
                  A chart needs at least two dated prices. Official issuer
                  sources are still available in Sources &amp; filings.
                </p>
                <button
                  className="button subtle"
                  onClick={() => void loadHistory()}
                >
                  Retry history
                </button>
              </div>
            )}
            {history && (
              <div
                className="research-provenance"
                aria-label="Price history provenance"
              >
                <strong>
                  {history.data_mode === "demo"
                    ? "SAMPLE DATA"
                    : "MARKET DATA · DAILY"}
                </strong>
                <span>
                  {sourceName} · {freshnessLabel}
                </span>
                {history.dates.length > 0 && (
                  <span>
                    {history.dates[0]} to {history.dates.at(-1)}
                  </span>
                )}
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
                      <th scope="col">Over the same history</th>
                      <th scope="col">{selected.symbol}</th>
                      <th scope="col">{peer.symbol}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th scope="row">Return</th>
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
                      <th scope="row">Portfolio allocation</th>
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
          </div>
          <div
            className="sources-view"
            role="tabpanel"
            id={`${sectionId}-sources-panel`}
            aria-labelledby={`${sectionId}-sources-tab`}
            hidden={tab !== "sources"}
            tabIndex={0}
          >
            <BookOpen size={26} aria-hidden="true" />
            <h3>Start with the source.</h3>
            <p>
              Use company filings and fund disclosures to check financial
              results, business risks, and portfolio composition.
            </p>
            <article className="research-source-block">
              <div className="research-source-kind">
                <span>01</span> OFFICIAL ISSUER SOURCE
              </div>
              <a
                href={selected.source}
                target="_blank"
                rel="noopener noreferrer"
                className="source-card"
              >
                <div>
                  <strong>{selected.short} · Selected issuer page</strong>
                  <span className="source-domain">{issuerHost}</span>
                  <span>
                    Issuer-published information and disclosures. Review the
                    date on the original page.
                  </span>
                  <span className="source-open">
                    Open source{" "}
                    <span className="sr-only">(opens in a new tab)</span>
                  </span>
                </div>
                <ExternalLink size={20} aria-hidden="true" />
              </a>
              <button
                className="button dark source-summary-button"
                onClick={() => onSummarizeSource(selected.symbol)}
              >
                Summarize issuer source
                <ArrowUpRight size={15} />
              </button>
              <p className="source-summary-note">
                AI summarizes this selected page. Open the original to check the
                full context.
              </p>
            </article>
            <article className="research-source-block">
              <div className="research-source-kind">
                <span>02</span> PUBLIC FILING DATABASE
              </div>
              <a
                href={`https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(selected.name)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="source-card"
              >
                <div>
                  <strong>SEC EDGAR filings</strong>
                  <span className="source-domain">sec.gov</span>
                  <span>
                    Search public disclosures for {selected.name}. This search
                    is not part of the AI summary.
                  </span>
                  <span className="source-open">
                    Search filings{" "}
                    <span className="sr-only">(opens in a new tab)</span>
                  </span>
                </div>
                <ExternalLink size={20} aria-hidden="true" />
              </a>
            </article>
            <p className="small-text muted">
              These are curated research starting points, not a live news feed.
              Source links open in a new tab. AI summaries may be unavailable
              while the original sources remain accessible.
            </p>
          </div>
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
