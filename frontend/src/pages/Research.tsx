import { useState } from "react";
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
import {
  assetPath,
  covarianceMatrix,
  pct,
  signedPct,
  money,
} from "../../../quant/analytics";
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
  const note = researchNotes.find((n) => n.id === noteId);
  const [period, setPeriod] = useState(252);
  const results = assets.filter(
    (a, i) =>
      (filter === "all" || weights[i] > 0) &&
      `${a.symbol} ${a.name}`.toLowerCase().includes(search.toLowerCase()),
  );
  const peer = compare ? assetBySymbol(compare) : null;
  const selectedPath = assetPath(idx, period);
  const sampleReturn = selectedPath.at(-1)! - 1;
  const periodLabel =
    period === 63 ? "3-month" : period === 126 ? "6-month" : "1-year";
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
              onChange={(e) => setSearch(e.target.value)}
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
            {results.map((a) => (
              <a
                className={`asset-index-item ${a.symbol === selected.symbol ? "active" : ""}`}
                href={`#/research?symbol=${a.symbol}`}
                key={a.symbol}
                aria-current={a.symbol === selected.symbol ? "page" : undefined}
              >
                <AssetMark asset={a} />
                <span>
                  <strong>{a.symbol}</strong>
                  <small>{a.short}</small>
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
            <span>Illustrative prices & returns</span>
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
                onChange={(e) => setCompare(e.target.value)}
              >
                <option value="">Compare with…</option>
                {assets
                  .filter((a) => a.symbol !== selected.symbol)
                  .map((a) => (
                    <option key={a.symbol}>{a.symbol}</option>
                  ))}
              </select>
              <ChevronDown size={14} />
            </label>
          </div>
          {tab === "overview" ? (
            <>
              <div className="company-chart-head">
                <div>
                  <span className="eyebrow">ILLUSTRATIVE PRICE</span>
                  <div className="company-price">
                    {money(selected.price, 2)}
                    <span
                      className={sampleReturn >= 0 ? "positive" : "negative"}
                    >
                      {signedPct(sampleReturn)}
                    </span>
                  </div>
                </div>
                <div className="segmented" aria-label="Research chart period">
                  {[
                    [63, "3M"],
                    [126, "6M"],
                    [252, "1Y"],
                  ].map(([d, l]) => (
                    <button
                      key={d}
                      aria-pressed={period === d}
                      onClick={() => setPeriod(Number(d))}
                    >
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              <LineChart
                series={selectedPath}
                secondary={
                  peer && peer.symbol !== selected.symbol
                    ? assetPath(assets.indexOf(peer), period)
                    : undefined
                }
                label={selected.symbol}
                secondaryLabel={peer?.symbol}
                compact
              />
              {peer && peer.symbol !== selected.symbol && (
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
                        <th>{periodLabel} return · modeled sample</th>
                        <th>{selected.symbol}</th>
                        <th>{peer.symbol}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th>Return</th>
                        <td>{signedPct(sampleReturn)}</td>
                        <td>
                          {signedPct(
                            assetPath(assets.indexOf(peer), period).at(-1)! - 1,
                          )}
                        </td>
                      </tr>
                      <tr>
                        <th>Annualized volatility · one-year sample</th>
                        <td>
                          {pct(Math.sqrt(covarianceMatrix[idx][idx] * 252))}
                        </td>
                        <td>
                          {pct(
                            Math.sqrt(
                              covarianceMatrix[assets.indexOf(peer)][
                                assets.indexOf(peer)
                              ] * 252,
                            ),
                          )}
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
                  <span className="eyebrow">THE INVESTMENT CONTEXT</span>
                  <h3>What to understand</h3>
                  <p>{selected.thesis}</p>
                </div>
                <div>
                  <span className="eyebrow">THE OTHER SIDE</span>
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
                PandaSet prices and charts are illustrative fixtures. The links
                above take you to external sources; their live content is not
                ingested into this demo.
              </p>
            </div>
          )}
        </section>
      </div>
      <section className="research-reading">
        <SectionTitle
          eyebrow="THE WIDER PICTURE"
          title="Connections worth exploring"
        />
        <div className="reading-grid">
          {researchNotes.map((n, i) => (
            <button
              className="reading-note"
              onClick={() => setNoteId(n.id)}
              key={n.id}
            >
              <span className="reading-number">0{i + 1}</span>
              <span className="eyebrow">{n.category}</span>
              <h3>{n.title}</h3>
              <span className="reading-bottom">
                {n.read}
                <ArrowRight size={17} />
              </span>
            </button>
          ))}
        </div>
      </section>
      {note && (
        <Modal title={note.title} onClose={() => setNoteId(null)}>
          <span className="eyebrow">{note.category} · RESEARCH PRIMER</span>
          <p className="note-body">{note.body}</p>
          <div className="note-tickers">
            {note.symbols.map((s) => (
              <a
                href={`#/research?symbol=${s}`}
                onClick={() => setNoteId(null)}
                className="tag-link"
                key={s}
              >
                {s}
                <ArrowUpRight size={14} />
              </a>
            ))}
          </div>
          <p className="muted small-text">
            This is a general research connection, not a report of a current
            market event.
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
