import { useState } from "react";
import {
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
  AdjustmentsHorizontal as SlidersHorizontal,
  ChatBubbleLeftRight,
  Eye,
  Plus,
  MagnifyingGlass as Search,
  ChevronDown,
  InformationCircle as Info,
} from "../components/icons";
import { assets, portfolioValue, researchNotes } from "../data";
import { analyze, assetPath, money, pct, signedPct } from "../analytics";
import {
  AssetMark,
  PageHeading,
  SectionTitle,
  TextLink,
  Empty,
} from "../components/UI";
import { LineChart } from "../components/LineChart";
export default function Overview({
  weights,
  onEdit,
  onAsk,
  onMethod,
}: {
  weights: number[];
  onEdit: () => void;
  onAsk: (q?: string) => void;
  onMethod: () => void;
}) {
  const [period, setPeriod] = useState(252);
  const [view, setView] = useState<"holdings" | "drivers">("holdings");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"weight" | "return">("weight");
  const metrics = analyze(weights, period);
  const annual = analyze(weights);
  const top = assets[annual.topRisk];
  const maxGain = Math.max(0, ...metrics.contributions);
  const maxLoss = Math.max(0, ...metrics.contributions.map((v) => -v));
  const contributionRange = maxGain + maxLoss || 1;
  const zeroPosition = 5 + (maxLoss / contributionRange) * 90;
  const holdings = assets
    .map((asset, i) => ({ asset, i }))
    .filter(
      ({ asset, i }) =>
        weights[i] > 0 &&
        `${asset.symbol} ${asset.name}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "weight"
        ? weights[b.i] - weights[a.i]
        : metrics.contributions[b.i] - metrics.contributions[a.i],
    );
  const periodLabel =
    period === 21
      ? "past month"
      : period === 63
        ? "past 3 months"
        : period === 126
          ? "past 6 months"
          : "past year";
  return (
    <>
      <PageHeading title="Portfolio overview">
        <button className="button subtle" onClick={onEdit}>
          <SlidersHorizontal size={16} />
          Edit portfolio
        </button>
        <button
          className="button dark"
          onClick={() => {
            location.hash = "#/what-if";
          }}
        >
          Explore a what-if
          <ArrowUpRight size={17} />
        </button>
      </PageHeading>
      <div className="overview-top">
        <section
          className="performance-panel"
          aria-labelledby="performance-title"
        >
          <div className="performance-head">
            <div>
              <div className="eyebrow" id="performance-title">
                PORTFOLIO VALUE{" "}
                <button
                  className="inline-icon"
                  aria-label="About sample portfolio data"
                  onClick={onMethod}
                >
                  <Info size={13} />
                </button>
              </div>
              <div className="large-value">
                {money(portfolioValue)}
                <span>.00</span>
              </div>
              <div
                className={`return-caption ${metrics.return >= 0 ? "positive" : "negative"}`}
              >
                {metrics.return >= 0 ? (
                  <ArrowUpRight size={17} />
                ) : (
                  <ArrowDownRight size={17} />
                )}{" "}
                {signedPct(metrics.return)}{" "}
                <span>
                  (
                  {money(
                    portfolioValue - portfolioValue / (1 + metrics.return),
                  )}
                  ) <span className="muted">{periodLabel}</span>
                </span>
              </div>
            </div>
            <div className="segmented" aria-label="Performance period">
              {[
                [21, "1M"],
                [63, "3M"],
                [126, "6M"],
                [252, "1Y"],
              ].map(([days, label]) => (
                <button
                  key={days}
                  aria-pressed={period === days}
                  onClick={() => setPeriod(Number(days))}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <LineChart
            series={metrics.path}
            secondary={assetPath(4, period)}
            secondaryLabel="U.S. market proxy (VTI)"
            currency
            endValue={portfolioValue}
          />
          <div className="performance-bottom">
            <span>
              Both lines model growth from the same start · Dollar axis shows
              modeled value
            </span>
            <button className="text-button" onClick={onMethod}>
              Data & methodology
              <ArrowUpRight size={13} />
            </button>
          </div>
        </section>
        <aside className="focus-panel">
          <div className="focus-label">
            <Eye size={16} />
            <span>IN FOCUS</span>
            <span className="edition">01 / RISK</span>
          </div>
          <h2>
            {annual.risk[annual.topRisk] > weights[annual.topRisk] / 100 ? (
              <>
                A larger share
                <br />
                of the risk.
              </>
            ) : (
              <>
                Your leading
                <br />
                risk contributor.
              </>
            )}
          </h2>
          <p>
            {top.short} is {pct(weights[annual.topRisk] / 100, 0)} of your
            portfolio, but contributes {pct(annual.risk[annual.topRisk], 0)} of
            its estimated volatility.
          </p>
          <div className="focus-bars">
            <div>
              <span>Capital allocated</span>
              <strong>{pct(weights[annual.topRisk] / 100, 0)}</strong>
            </div>
            <div className="focus-track">
              <i style={{ width: `${weights[annual.topRisk]}%` }} />
            </div>
            <div>
              <span>Share of portfolio risk</span>
              <strong>{pct(annual.risk[annual.topRisk], 0)}</strong>
            </div>
            <div className="focus-track bright">
              <i
                style={{
                  width: `${Math.max(0, annual.risk[annual.topRisk] * 100)}%`,
                }}
              />
            </div>
          </div>
          <a href="#/risk" className="focus-link">
            See the full risk picture
            <ArrowRight size={18} />
          </a>
        </aside>
      </div>
      <div className="metric-strip">
        <div>
          <span>
            Annualized volatility{" "}
            <button
              className="inline-icon"
              onClick={onMethod}
              aria-label="Explain annualized volatility"
            >
              <Info size={13} />
            </button>
          </span>
          <strong>
            {pct(annual.volatility)}
            <small>Estimated from 1 year</small>
          </strong>
        </div>
        <div>
          <span>Largest drawdown</span>
          <strong>
            {pct(annual.maxDrawdown)}
            <small>Peak-to-trough fall · 1 year</small>
          </strong>
        </div>
        <div>
          <span>Direct technology allocation</span>
          <strong>
            {pct(annual.sectors.find(([s]) => s === "Technology")?.[1] || 0, 0)}
            <small>Excludes stocks held in funds</small>
          </strong>
        </div>
        <div>
          <span>Holdings</span>
          <strong>
            {weights
              .filter((w) => w > 0)
              .length.toString()
              .padStart(2, "0")}
            <small>Across {annual.sectors.length} categories</small>
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
                  Positions
                </button>
                <button
                  aria-pressed={view === "drivers"}
                  onClick={() => setView("drivers")}
                >
                  Return drivers
                </button>
              </div>
              <button
                className="icon-button bordered"
                onClick={onEdit}
                aria-label="Add or edit holdings"
              >
                <Plus size={18} />
              </button>
            </div>
          </SectionTitle>
          <div className="table-tools">
            <label className="search-field">
              <Search size={16} />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Find a holding"
                aria-label="Find a holding"
              />
            </label>
            {view === "holdings" ? (
              <button
                className="text-button"
                onClick={() => setSort(sort === "weight" ? "return" : "weight")}
              >
                By {sort === "weight" ? "allocation" : "contribution"}
                <ChevronDown size={14} />
              </button>
            ) : (
              <span className="small-text muted">By contribution</span>
            )}
          </div>
          {view === "holdings" ? (
            <div className="table-scroll">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th scope="col">Asset</th>
                    <th scope="col" className="align-right">
                      Allocation
                    </th>
                    <th scope="col" className="align-right">
                      Value
                    </th>
                    <th scope="col" className="align-right">
                      Return impact{" "}
                      <span className="sub-label">
                        {period === 252
                          ? "1 year"
                          : period === 126
                            ? "6 months"
                            : period === 63
                              ? "3 months"
                              : "1 month"}
                      </span>
                    </th>
                    <th scope="col">
                      <span className="sr-only">Research</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map(({ asset, i }) => (
                    <tr key={asset.symbol}>
                      <td>
                        <a
                          className="asset-cell"
                          href={`#/research?symbol=${asset.symbol}`}
                        >
                          <AssetMark asset={asset} />
                          <span>
                            <strong>{asset.symbol}</strong>
                            <small>{asset.short}</small>
                          </span>
                        </a>
                      </td>
                      <td className="align-right">
                        <div className="allocation-cell">
                          <span>{weights[i]}%</span>
                          <div>
                            <i
                              style={{
                                width: `${weights[i] * 2}%`,
                                background: asset.color,
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="align-right numeric">
                        {money((portfolioValue * weights[i]) / 100)}
                      </td>
                      <td
                        className={`align-right numeric ${metrics.contributions[i] >= 0 ? "positive" : "negative"}`}
                      >
                        {metrics.contributions[i] >= 0 ? "+" : ""}
                        {(metrics.contributions[i] * 100).toFixed(2)} pp
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
              aria-label="Ranked return contributions"
            >
              {[...holdings]
                .sort(
                  (a, b) =>
                    metrics.contributions[b.i] - metrics.contributions[a.i],
                )
                .map(({ asset, i }) => (
                  <a
                    href={`#/research?symbol=${asset.symbol}`}
                    className="driver-row"
                    key={asset.symbol}
                  >
                    <span>{asset.symbol}</span>
                    <div
                      className="driver-track"
                      style={
                        { "--zero": `${zeroPosition}%` } as React.CSSProperties
                      }
                    >
                      <i
                        className={metrics.contributions[i] < 0 ? "loss" : ""}
                        style={{
                          width: `${(Math.abs(metrics.contributions[i]) / contributionRange) * 90}%`,
                          left: `${zeroPosition + (Math.min(0, metrics.contributions[i]) / contributionRange) * 90}%`,
                        }}
                      />
                    </div>
                    <strong
                      className={
                        metrics.contributions[i] >= 0 ? "positive" : "negative"
                      }
                    >
                      {metrics.contributions[i] >= 0 ? "+" : ""}
                      {(metrics.contributions[i] * 100).toFixed(2)} pp
                    </strong>
                  </a>
                ))}
            </div>
          )}
          {holdings.length === 0 && (
            <Empty title="No matching holdings">
              Try a company name or ticker.
              <button className="text-button" onClick={() => setSearch("")}>
                Clear search
              </button>
            </Empty>
          )}
          <p className="table-footnote">
            Return impact is each holding’s contribution to the portfolio’s
            return.
          </p>
        </section>
        <section className="briefing">
          <SectionTitle eyebrow="CONNECT THE DOTS" title="On your radar">
            <TextLink to="#/research">Research</TextLink>
          </SectionTitle>
          {researchNotes
            .filter((n) =>
              n.symbols.some(
                (s) => weights[assets.findIndex((a) => a.symbol === s)] > 0,
              ),
            )
            .slice(0, 3)
            .map((note, i) => (
              <a
                className="briefing-item"
                key={note.id}
                href={`#/research?note=${note.id}`}
              >
                <span className="note-index">0{i + 1}</span>
                <div>
                  <div className="eyebrow">{note.category}</div>
                  <h3>{note.title}</h3>
                  <div className="briefing-meta">
                    {note.symbols.slice(0, 3).map((s) => (
                      <span key={s}>{s}</span>
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
