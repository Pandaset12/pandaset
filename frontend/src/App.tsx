import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Check, XMark as X } from "./components/icons";
import { Brand } from "./components/UI";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EditPortfolio } from "./components/EditPortfolio";
import { AuthScreen } from "./components/AuthScreen";
import { AuthBoundary } from "./components/AuthBoundary";
import { PortfolioOnboarding } from "./components/onboarding/PortfolioOnboarding";
import {
  asAnalysisResponse,
  analysisMatchesPortfolio,
  createAnalysis,
  createPortfolio,
  listAnalyses,
  listPortfolios,
  searchInstruments,
  updatePortfolio,
  validPercentAllocation,
  type SavedAnalysis,
} from "./api/eventLab";
import { createRequestGuard, type Portfolio } from "./api/portfolio";
import { assetsForPortfolio, type Instrument } from "./types/portfolioAsset";
import Overview from "./pages/Overview";
import Risk from "./pages/Risk";
import Research from "./pages/Research";
import WhatIf from "./pages/WhatIf";

function Application({ onSignOut }: { onSignOut: () => Promise<void> }) {
  const [hash, setHash] = useState(location.hash || "#/");
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [listState, setListState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [listError, setListError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [savedAnalysis, setSavedAnalysis] = useState<SavedAnalysis | null>(
    null,
  );
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [onboarding, setOnboarding] = useState(false);
  const [edit, setEdit] = useState(false);
  const [toast, setToast] = useState("");
  const listGuard = useRef(createRequestGuard());
  const analysisGuard = useRef(createRequestGuard());

  useEffect(() => {
    const update = () => {
      setHash(location.hash || "#/");
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  const loadPortfolios = useCallback(async () => {
    const request = listGuard.current.begin();
    setListState("loading");
    setListError("");
    try {
      const result = await listPortfolios();
      if (!listGuard.current.isCurrent(request)) return;
      setPortfolios(result);
      setSelectedId((old) =>
        result.some((p) => p.portfolio_id === old)
          ? old
          : (result[0]?.portfolio_id ?? ""),
      );
      setListState("ready");
    } catch (cause) {
      if (!listGuard.current.isCurrent(request)) return;
      setListError(
        cause instanceof Error
          ? cause.message
          : "Your portfolios are unavailable.",
      );
      setListState("error");
    }
  }, []);
  useEffect(() => {
    void loadPortfolios();
    return () => {
      listGuard.current.invalidate();
      analysisGuard.current.invalidate();
    };
  }, [loadPortfolios]);

  const selected =
    portfolios.find((p) => p.portfolio_id === selectedId) ?? null;
  const loadAnalysis = useCallback(
    async (portfolioId: string, refresh = false) => {
      const request = analysisGuard.current.begin();
      setSavedAnalysis((old) =>
        refresh && old?.portfolio_id === portfolioId ? old : null,
      );
      setAnalysisBusy(true);
      setAnalysisError("");
      try {
        const result = refresh
          ? await createAnalysis(portfolioId)
          : ((await listAnalyses(portfolioId))[0] ??
            (await createAnalysis(portfolioId)));
        if (analysisGuard.current.isCurrent(request)) setSavedAnalysis(result);
        return analysisGuard.current.isCurrent(request);
      } catch (cause) {
        if (analysisGuard.current.isCurrent(request))
          setAnalysisError(
            cause instanceof Error
              ? cause.message
              : "The analysis is unavailable.",
          );
        return false;
      } finally {
        if (analysisGuard.current.isCurrent(request)) setAnalysisBusy(false);
      }
    },
    [],
  );
  useEffect(() => {
    if (selectedId && listState === "ready") void loadAnalysis(selectedId);
    return () => analysisGuard.current.invalidate();
  }, [selectedId, listState, loadAnalysis]);

  useEffect(() => {
    if (!selected) {
      setInstruments([]);
      return;
    }
    let cancelled = false;
    void Promise.all(
      selected.holdings.map(({ symbol }) =>
        searchInstruments(symbol)
          .then((items) => items.find((item) => item.symbol === symbol))
          .catch(() => undefined),
      ),
    ).then((items) => {
      if (!cancelled)
        setInstruments(
          items.filter((item): item is Instrument => Boolean(item)),
        );
    });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  async function apply(weights: number[]) {
    if (
      !selected ||
      weights.length !== selected.holdings.length ||
      !validPercentAllocation(weights)
    )
      return false;
    setAnalysisBusy(true);
    setAnalysisError("");
    try {
      const updated = await updatePortfolio(selected.portfolio_id, {
        name: selected.name,
        holdings: selected.holdings
          .map((holding, index) => ({
            symbol: holding.symbol,
            weight: weights[index] / 100,
          }))
          .filter((holding) => holding.weight > 0),
      });
      setSavedAnalysis(null);
      setPortfolios((old) =>
        old.map((p) => (p.portfolio_id === updated.portfolio_id ? updated : p)),
      );
      const created = await createAnalysis(updated.portfolio_id);
      setSavedAnalysis(created);
      setEdit(false);
      setToast("Allocation applied. A new analysis snapshot was saved.");
      return true;
    } catch (cause) {
      setAnalysisError(
        cause instanceof Error
          ? cause.message
          : "The allocation could not be saved.",
      );
      return false;
    } finally {
      setAnalysisBusy(false);
    }
  }

  function openPortfolio(portfolio: Portfolio) {
    setPortfolios((old) => [
      portfolio,
      ...old.filter((p) => p.portfolio_id !== portfolio.portfolio_id),
    ]);
    setSelectedId(portfolio.portfolio_id);
    setOnboarding(false);
  }

  const [path, search = ""] = hash.replace(/^#/, "").split("?");
  const route = ["/", "/risk", "/research", "/what-if"].includes(path)
    ? path
    : "/";
  const query = new URLSearchParams(search);
  useEffect(() => {
    document.title = `${route === "/" ? "Overview" : route === "/risk" ? "Risk & exposure" : route === "/research" ? "Research" : "What-if lab"} — PandaSet`;
  }, [route]);
  const analysisMismatch = Boolean(
    savedAnalysis &&
    selected &&
    !analysisMatchesPortfolio(savedAnalysis, selected),
  );
  const visibleAnalysisError =
    analysisError ||
    (analysisMismatch
      ? "The saved analysis uses a different allocation. Refresh it before starting a new scenario."
      : "");
  const analysis =
    savedAnalysis &&
    selected &&
    !analysisMismatch &&
    savedAnalysis.portfolio_id === selected.portfolio_id
      ? asAnalysisResponse(savedAnalysis)
      : null;
  const weights =
    selected?.holdings.map((holding) =>
      Number(
        ((analysis?.weights[holding.symbol] ?? holding.weight) * 100).toFixed(
          6,
        ),
      ),
    ) ?? [];
  const assets = selected ? assetsForPortfolio(selected, instruments) : [];
  const asOf = analysis?.as_of
    ? new Date(analysis.as_of).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      })
    : "Unavailable";
  const nav = [
    ["/", "Overview"],
    ["/risk", "Risk & exposure"],
    ["/research", "Research"],
    ["/what-if", "What-if lab"],
  ];

  return (
    <>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Brand />
          <nav aria-label="Main navigation">
            {nav.map(([to, label]) => (
              <a
                key={to}
                href={`#${to}`}
                className={route === to ? "active" : ""}
                aria-current={route === to ? "page" : undefined}
              >
                {label}
              </a>
            ))}
          </nav>
          <button
            className="text-button sign-out-button"
            onClick={() => void onSignOut()}
          >
            Sign out
          </button>
        </div>
      </header>
      <div className="workspace-bar">
        <div className="workspace-portfolio-controls">
          {portfolios.length > 0 && (
            <label className="portfolio-select-label">
              Portfolio{" "}
              <select
                aria-label="Select portfolio"
                value={selectedId}
                onChange={(e) => {
                  setSelectedId(e.target.value);
                  setOnboarding(false);
                }}
                disabled={listState !== "ready" || analysisBusy}
              >
                {portfolios.map((p) => (
                  <option key={p.portfolio_id} value={p.portfolio_id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {listState === "ready" && portfolios.length > 0 && (
            <button className="text-button" onClick={() => setOnboarding(true)}>
              New portfolio
            </button>
          )}
          {selected && (
            <button
              className="text-button"
              disabled={analysisBusy}
              onClick={() => void loadAnalysis(selected.portfolio_id, true)}
            >
              {analysisBusy
                ? "Loading analysis…"
                : analysis
                  ? "Refresh analysis"
                  : "Create analysis"}
            </button>
          )}
          {analysis && <span className="demo-badge">LIVE DATA</span>}
        </div>
        <span className="as-of">
          As of {asOf}
          <span className="separator">/</span>USD
        </span>
      </div>
      <main id="main-content" className="main-content" tabIndex={-1}>
        {listState === "loading" ? (
          <section className="api-state" role="status">
            <strong>Loading your portfolios…</strong>
          </section>
        ) : listState === "error" ? (
          <section className="api-state" role="alert">
            <strong>Portfolios are unavailable.</strong>
            <p>{listError}</p>
            <button
              className="button dark"
              onClick={() => void loadPortfolios()}
            >
              Retry
            </button>
          </section>
        ) : onboarding || portfolios.length === 0 ? (
          <PortfolioOnboarding
            key={onboarding ? "new" : "first"}
            searchTickers={(q, options) => searchInstruments(q, options.signal)}
            createPortfolio={(input, options) =>
              createPortfolio(input, options.signal)
            }
            onOpenPortfolio={openPortfolio}
            onCancel={
              portfolios.length ? () => setOnboarding(false) : undefined
            }
          />
        ) : route === "/what-if" && selected ? (
          <ErrorBoundary>
            <WhatIf
              key={selected.portfolio_id}
              portfolio={selected}
              analysis={analysis}
              analysisBusy={analysisBusy}
              analysisError={visibleAnalysisError}
              onRefreshAnalysis={() =>
                void loadAnalysis(selected.portfolio_id, true)
              }
              assets={assets}
              weights={weights}
              onApply={apply}
              query={query}
            />
          </ErrorBoundary>
        ) : analysisBusy && !analysis ? (
          <section className="api-state" role="status">
            <strong>Analyzing {selected?.name}…</strong>
            <p>Retrieving adjusted price history for the saved allocation.</p>
          </section>
        ) : visibleAnalysisError && !analysis ? (
          <section className="api-state" role="alert">
            <strong>Analysis is unavailable.</strong>
            <p>{visibleAnalysisError}</p>
            <button
              className="button dark"
              onClick={() => selectedId && void loadAnalysis(selectedId, true)}
            >
              Retry analysis
            </button>
          </section>
        ) : analysis && selected ? (
          <ErrorBoundary>
            {route === "/" ? (
              <Overview
                analysis={analysis}
                assets={assets}
                onEdit={() => setEdit(true)}
                onAsk={() =>
                  setToast(
                    "Portfolio chat is available in a completed event run.",
                  )
                }
                onBrief={() =>
                  setToast("Briefing is unavailable for this saved analysis.")
                }
                onMethod={() =>
                  setToast(
                    "This analysis uses saved adjusted-price history and the displayed data source.",
                  )
                }
              />
            ) : route === "/risk" ? (
              <Risk
                analysis={analysis}
                assets={assets}
                onExplain={() =>
                  setToast(
                    "Risk explanation is unavailable for this saved analysis.",
                  )
                }
                onMethod={() =>
                  setToast(
                    "Risk estimates use the saved adjusted-price history.",
                  )
                }
              />
            ) : route === "/research" ? (
              <Research
                key={hash}
                analysis={analysis}
                assets={assets}
                weights={weights}
                onAsk={() =>
                  setToast(
                    "Portfolio chat is available in a completed event run.",
                  )
                }
                onSummarizeSource={() =>
                  setToast(
                    "Issuer source summaries are unavailable for this saved analysis.",
                  )
                }
                query={query}
              />
            ) : null}
            {analysisError && (
              <p className="analysis-saving error" role="alert">
                {analysisError}
              </p>
            )}
          </ErrorBoundary>
        ) : null}
      </main>
      <footer className="site-footer">
        <span>
          PandaSet<span className="footer-slash">/</span>A clearer view of what
          you own.
        </span>
        <span>
          Hypothetical analysis. No brokerage connection or trades.
          <ArrowUpRight size={13} />
        </span>
      </footer>
      {edit && selected && (
        <EditPortfolio
          assets={assets}
          weights={weights}
          busy={analysisBusy}
          error={analysisError}
          onClose={() => setEdit(false)}
          onSave={apply}
        />
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={18} />
          {toast}
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
    </>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthBoundary
        renderDashboard={(signOut) => <Application onSignOut={signOut} />}
        renderSignedOut={(client) => <AuthScreen client={client} />}
      />
    </ErrorBoundary>
  );
}
