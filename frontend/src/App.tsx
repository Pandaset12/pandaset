import { useCallback, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { Check, ChevronDown, XMark as X } from "./components/icons";
import {
  analyzeExistingPortfolio,
  createPortfolio,
  deletePortfolio,
  createRequestGuard,
  searchAssets,
  verifyPortfolioHistory,
  verifyPortfolioSymbol,
  listPortfolios,
  setApiAccessToken,
  updatePortfolio,
  type AnalysisResponse,
  type Portfolio,
} from "./api/portfolio";
import { Brand, Modal } from "./components/UI";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EditPortfolio } from "./components/EditPortfolio";
import { MethodologyModal } from "./components/MethodologyModal";
import { AuthScreen } from "./components/AuthScreen";
import { AuthBoundary } from "./components/AuthBoundary";
import { PortfolioOnboarding } from "./components/onboarding/PortfolioOnboarding";
import { EventApplication } from "./EventApplication";
import {
  EventLabError,
  listPortfolios as listEventPortfolios,
} from "./api/eventLab";
import {
  AIWorkflowModal,
  type AIWorkflowAction,
} from "./components/AIWorkflowModal";
import Overview from "./pages/Overview";
import Risk from "./pages/Risk";
import Research from "./pages/Research";
import WhatIf from "./pages/WhatIf";
import {
  portfolioFromPercentages,
  portfolioPercentages,
  workspaceAssets,
} from "./workspace/holdings";

type ActiveAnalysis = { portfolio: Portfolio; analysis: AnalysisResponse };

export function Application({ onSignOut }: { onSignOut: () => Promise<void> }) {
  const [hash, setHash] = useState(location.hash || "#/");
  const [weights, setWeights] = useState<number[]>([]);
  const [edit, setEdit] = useState(false);
  const [method, setMethod] = useState(false);
  const [aiWorkflow, setAiWorkflow] = useState<AIWorkflowAction | null>(null);
  const [toast, setToast] = useState("");
  const [active, setActive] = useState<ActiveAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [portfolioState, setPortfolioState] = useState<
    "loading" | "empty" | "error" | "ready"
  >("loading");
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(
    null,
  );
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [portfolioMenuOpen, setPortfolioMenuOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [portfolioToDelete, setPortfolioToDelete] = useState<Portfolio | null>(
    null,
  );
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const analysisRequest = useRef(createRequestGuard());

  useEffect(() => {
    const fn = () => {
      setHash(location.hash || "#/");
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(id);
  }, [toast]);

  async function loadAnalysis(portfolio: Portfolio) {
    const request = analysisRequest.current.begin();
    setAnalysisLoading(true);
    setAnalysisError("");
    try {
      const result = await analyzeExistingPortfolio(portfolio);
      if (!analysisRequest.current.isCurrent(request)) return false;
      setActive(result);
      setWeights(portfolioPercentages(portfolio));
      return true;
    } catch (error) {
      if (analysisRequest.current.isCurrent(request)) {
        setAnalysisError(
          error instanceof Error
            ? error.message
            : "The analysis service is unavailable.",
        );
      }
      return false;
    } finally {
      if (analysisRequest.current.isCurrent(request)) setAnalysisLoading(false);
    }
  }

  async function loadPortfolios() {
    setPortfolioState("loading");
    try {
      const portfolios = await listPortfolios();
      setPortfolios(portfolios);
      if (!portfolios.length) setPortfolioState("empty");
      else {
        setSelectedPortfolio(portfolios[0]);
        setPortfolioState("ready");
        void loadAnalysis(portfolios[0]);
      }
    } catch {
      setPortfolioState("error");
    }
  }

  function selectPortfolio(portfolio: Portfolio) {
    setPortfolioMenuOpen(false);
    if (portfolio.portfolio_id === selectedPortfolio?.portfolio_id) return;
    setSelectedPortfolio(portfolio);
    setActive(null);
    setAnalysisError("");
    setEdit(false);
    setAiWorkflow(null);
    setShowOnboarding(false);
    void loadAnalysis(portfolio);
  }

  async function confirmDeletePortfolio() {
    if (!portfolioToDelete || deleteBusy) return;
    setDeleteBusy(true);
    setDeleteError("");
    try {
      await deletePortfolio(portfolioToDelete.portfolio_id);
      const remaining = portfolios.filter(
        (portfolio) =>
          portfolio.portfolio_id !== portfolioToDelete.portfolio_id,
      );
      setPortfolios(remaining);
      setPortfolioToDelete(null);
      setPortfolioMenuOpen(false);
      if (selectedPortfolio?.portfolio_id === portfolioToDelete.portfolio_id) {
        analysisRequest.current.invalidate();
        setActive(null);
        setAnalysisLoading(false);
        setAnalysisError("");
        setEdit(false);
        setAiWorkflow(null);
        const next = remaining[0] ?? null;
        setSelectedPortfolio(next);
        if (next) void loadAnalysis(next);
        else setPortfolioState("empty");
      }
      setToast(`Deleted ${portfolioToDelete.name}.`);
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Could not delete portfolio.",
      );
    } finally {
      setDeleteBusy(false);
    }
  }

  useEffect(() => {
    void loadPortfolios();
    return () => {
      analysisRequest.current.invalidate();
    };
  }, []);

  async function apply(
    nextWeights: number[],
    source: "edit" | "scenario" = "edit",
    symbols = selectedPortfolio?.holdings.map(({ symbol }) => symbol) ?? [],
  ) {
    try {
      if (!selectedPortfolio) return false;
      const input = portfolioFromPercentages(
        source === "edit"
          ? selectedPortfolio.name
          : `${selectedPortfolio.name} scenario`,
        symbols,
        nextWeights,
      );
      await verifyPortfolioHistory(input.holdings);
      if (source === "edit") {
        const updated = await updatePortfolio(
          selectedPortfolio.portfolio_id,
          input,
        );
        setSelectedPortfolio(updated);
        setPortfolios((current) =>
          current.map((portfolio) =>
            portfolio.portfolio_id === updated.portfolio_id
              ? updated
              : portfolio,
          ),
        );
        setActive(null);
        setWeights(portfolioPercentages(updated));
        setEdit(false);
        setAiWorkflow(null);
        if (!(await loadAnalysis(updated))) return false;
      } else {
        const created = await createPortfolio(input);
        setPortfolios((current) => [created, ...current]);
        if (!(await loadAnalysis(created))) return false;
        setSelectedPortfolio(created);
      }
    } catch (error) {
      setAnalysisError(
        error instanceof Error ? error.message : "Could not save portfolio.",
      );
      return false;
    }
    setEdit(false);
    setToast(
      source === "scenario"
        ? "Scenario saved as the active portfolio."
        : "Portfolio updated.",
    );
    return true;
  }

  const [path, search = ""] = hash.replace(/^#/, "").split("?");
  const route = ["/", "/risk", "/research", "/what-if"].includes(path)
    ? path
    : "/";
  const query = new URLSearchParams(search);
  useEffect(() => {
    document.title = `${route === "/" ? "Overview" : route === "/risk" ? "Risk & exposure" : route === "/research" ? "Research" : "Scenario lab"} — Pandaset`;
  }, [route]);

  const nav = [
    ["/", "Overview"],
    ["/risk", "Risk & exposure"],
    ["/research", "Research"],
    ["/what-if", "What-if lab"],
  ];
  const workspaceHoldings = selectedPortfolio
    ? workspaceAssets(selectedPortfolio)
    : [];
  const searchTickers = useCallback(
    async (query: string, { signal }: { signal: AbortSignal }) =>
      (await searchAssets(query, signal)).results,
    [],
  );

  if (portfolioState !== "ready" || showOnboarding)
    return (
      <div className="onboarding-page">
        <header className="auth-header onboarding-header">
          <Brand />
          <span>Your investor workspace</span>
          <div className="onboarding-header-actions">
            {showOnboarding && portfolios.length > 0 && (
              <button
                className="text-button onboarding-header-back"
                onClick={() => setShowOnboarding(false)}
              >
                Back to saved portfolios
              </button>
            )}
            <button
              className="text-button sign-out-button"
              onClick={() => void onSignOut()}
            >
              Sign out
            </button>
          </div>
        </header>
        <main className="onboarding-main" id="main-content">
          <PortfolioOnboarding
            loadState={
              showOnboarding || portfolioState === "ready"
                ? "empty"
                : portfolioState
            }
            hasExistingPortfolios={portfolios.length > 0}
            onRetryLoad={() => void loadPortfolios()}
            searchTickers={searchTickers}
            verifyTicker={verifyPortfolioSymbol}
            onCancel={
              showOnboarding && portfolios.length > 0
                ? () => setShowOnboarding(false)
                : undefined
            }
            createPortfolio={async (input, options) => {
              await verifyPortfolioHistory(input.holdings, options.signal);
              return createPortfolio(input, options.signal);
            }}
            onOpenPortfolio={(portfolio) => {
              setSelectedPortfolio(portfolio);
              setPortfolios((current) => [portfolio, ...current]);
              setPortfolioState("ready");
              setShowOnboarding(false);
              void loadAnalysis(portfolio);
            }}
          />
        </main>
      </div>
    );
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
        <div>
          <div
            className="portfolio-picker"
            onKeyDown={(event) => {
              if (event.key === "Escape") setPortfolioMenuOpen(false);
            }}
          >
            <button
              className="portfolio-selector"
              aria-expanded={portfolioMenuOpen}
              aria-controls="saved-portfolios"
              onClick={() => setPortfolioMenuOpen((open) => !open)}
            >
              <span className="portfolio-initial">
                {selectedPortfolio?.name.slice(0, 1).toUpperCase() ?? "P"}
              </span>
              <span
                className="portfolio-selector-name"
                title={selectedPortfolio?.name}
              >
                {selectedPortfolio?.name ?? "Choose portfolio"}
              </span>
              <ChevronDown size={14} />
            </button>
            {portfolioMenuOpen && (
              <div
                id="saved-portfolios"
                className="portfolio-menu"
                aria-label="Saved portfolios"
              >
                {portfolios.map((portfolio) => (
                  <div
                    className="portfolio-menu-row"
                    key={portfolio.portfolio_id}
                  >
                    <button
                      type="button"
                      className="portfolio-menu-choice"
                      aria-current={
                        portfolio.portfolio_id ===
                        selectedPortfolio?.portfolio_id
                          ? "true"
                          : undefined
                      }
                      title={portfolio.name}
                      onClick={() => selectPortfolio(portfolio)}
                    >
                      {portfolio.name}
                    </button>
                    <button
                      type="button"
                      className="portfolio-menu-delete"
                      aria-label={`Delete ${portfolio.name}`}
                      title={`Delete ${portfolio.name}`}
                      onClick={() => {
                        setPortfolioMenuOpen(false);
                        setDeleteError("");
                        setPortfolioToDelete(portfolio);
                      }}
                    >
                      Delete
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="portfolio-menu-new"
                  onClick={() => {
                    setPortfolioMenuOpen(false);
                    setShowOnboarding(true);
                  }}
                >
                  + New portfolio
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      <main id="main-content" className="main-content" tabIndex={-1}>
        {analysisLoading && !active ? (
          <section className="api-state" role="status">
            <strong>Loading portfolio analysis…</strong>
            <p>Connecting to the backend and calculating this portfolio.</p>
          </section>
        ) : analysisError && !active ? (
          <section className="api-state api-state-featured" role="alert">
            <span className="api-state-kicker">PORTFOLIO ANALYSIS</span>
            <h1>We couldn’t load the portfolio analysis.</h1>
            <p>
              Your saved portfolio is still available. Try again, choose another
              portfolio above, or create a replacement with supported prices.
            </p>
            <button
              className="button dark"
              onClick={() =>
                selectedPortfolio && void loadAnalysis(selectedPortfolio)
              }
              disabled={analysisLoading}
            >
              Retry analysis
            </button>
            <button
              className="button subtle"
              onClick={() => setShowOnboarding(true)}
            >
              Create another portfolio
            </button>
            <button className="text-button" onClick={() => setMethod(true)}>
              Data & methodology
            </button>
            <details>
              <summary>Technical details</summary>
              <p>{analysisError}</p>
            </details>
          </section>
        ) : active ? (
          <ErrorBoundary>
            {route === "/" ? (
              <Overview
                holdings={workspaceHoldings}
                analysis={active.analysis}
                onEdit={() => setEdit(true)}
                onBrief={() => setAiWorkflow({ workflow: "analysis_briefing" })}
                onMethod={() => setMethod(true)}
              />
            ) : route === "/risk" ? (
              <Risk
                holdings={workspaceHoldings}
                analysis={active.analysis}
                onExplain={() =>
                  setAiWorkflow({
                    workflow: "risk_explanation",
                    question:
                      "Explain the main risk contributions and concentrations in this saved analysis.",
                  })
                }
                onMethod={() => setMethod(true)}
              />
            ) : route === "/research" ? (
              <Research
                key={hash}
                holdings={workspaceHoldings}
                weights={weights}
                onSummarizeSource={(symbol) =>
                  setAiWorkflow({ workflow: "research_summary", symbol })
                }
                query={query}
              />
            ) : (
              <WhatIf
                key={`${hash}:${active.analysis.analysis_id}`}
                holdings={workspaceHoldings}
                analysis={active.analysis}
                weights={weights}
                onApply={(w, symbols) => apply(w, "scenario", symbols)}
                onExplainScenario={(proposedWeights, symbols) =>
                  setAiWorkflow({
                    workflow: "scenario_explanation",
                    proposedWeights,
                    symbols,
                  })
                }
                query={query}
              />
            )}
            {analysisLoading && (
              <p className="analysis-saving" role="status">
                Saving the new allocation and calculating its analysis…
              </p>
            )}
            {analysisError && (
              <div className="analysis-saving error" role="alert">
                The analysis couldn’t be updated. Your active portfolio is
                unchanged.{" "}
                <button
                  className="text-button"
                  onClick={() =>
                    selectedPortfolio && void loadAnalysis(selectedPortfolio)
                  }
                >
                  Retry
                </button>
                <details>
                  <summary>Technical details</summary>
                  {analysisError}
                </details>
              </div>
            )}
          </ErrorBoundary>
        ) : null}
      </main>
      <footer className="site-footer">
        <span>
          Pandaset<span className="footer-slash">/</span>A clearer view of what
          you own.
        </span>
      </footer>
      {edit && active && (
        <EditPortfolio
          holdings={workspaceHoldings}
          weights={weights}
          searchTickers={searchTickers}
          verifyTicker={verifyPortfolioSymbol}
          busy={analysisLoading}
          error={analysisError}
          onClose={() => setEdit(false)}
          onSave={(w, symbols) => apply(w, "edit", symbols)}
        />
      )}
      {method && (
        <MethodologyModal
          analysis={active?.analysis ?? null}
          onClose={() => setMethod(false)}
        />
      )}
      {portfolioToDelete && (
        <Modal
          title="Delete portfolio?"
          onClose={
            deleteBusy ? () => undefined : () => setPortfolioToDelete(null)
          }
        >
          <p>
            Delete <strong>{portfolioToDelete.name}</strong> and its saved
            analyses? This cannot be undone.
          </p>
          {deleteError && (
            <p className="field-error" role="alert">
              {deleteError}
            </p>
          )}
          <div className="modal-actions">
            <button
              className="button subtle"
              disabled={deleteBusy}
              onClick={() => setPortfolioToDelete(null)}
            >
              Cancel
            </button>
            <button
              className="button dark"
              disabled={deleteBusy}
              onClick={() => void confirmDeletePortfolio()}
            >
              {deleteBusy ? "Deleting…" : "Delete portfolio"}
            </button>
          </div>
        </Modal>
      )}
      {aiWorkflow && active && (
        <AIWorkflowModal
          action={aiWorkflow}
          portfolioId={active.portfolio.portfolio_id}
          analysisId={active.analysis.analysis_id}
          onClose={() => setAiWorkflow(null)}
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
        renderDashboard={(currentSession, signOut) => (
          <AuthenticatedApplication
            session={currentSession}
            onSignOut={signOut}
          />
        )}
        renderSignedOut={(client) => {
          setApiAccessToken(null);
          return <AuthScreen client={client} />;
        }}
      />
    </ErrorBoundary>
  );
}

function AuthenticatedApplication({
  session,
  onSignOut,
}: {
  session: Session;
  onSignOut: () => Promise<void>;
}) {
  setApiAccessToken(session.access_token);
  const [mode, setMode] = useState<"loading" | "standard" | "event" | "error">(
    "loading",
  );
  const [modeError, setModeError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setMode("loading");
    setModeError("");
    const selectMode = async () => {
      try {
        try {
          await listEventPortfolios();
          if (active) setMode("event");
        } catch (cause) {
          if (
            cause instanceof EventLabError &&
            ([
              "EVENT_LAB_NOT_INVITED",
              "EVENT_LAB_UNAVAILABLE",
              "AUTH_UNAVAILABLE",
            ].includes(cause.code) ||
              cause.status >= 500)
          ) {
            if (active) setMode("standard");
          } else {
            throw cause;
          }
        }
      } catch (cause) {
        if (!active) return;
        setModeError(
          cause instanceof Error
            ? cause.message
            : "The portfolio service is unavailable.",
        );
        setMode("error");
      }
    };
    void selectMode();
    return () => {
      active = false;
    };
  }, [session.user.id, retry]);

  if (mode === "loading")
    return (
      <main className="auth-loading" role="status">
        Opening your workspace…
      </main>
    );
  if (mode === "error")
    return (
      <main className="auth-loading" role="alert">
        <p>{modeError}</p>
        <button
          className="button dark"
          onClick={() => setRetry((value) => value + 1)}
        >
          Retry
        </button>
      </main>
    );
  return mode === "event" ? (
    <EventApplication key={session.user.id} onSignOut={onSignOut} />
  ) : (
    <Application key={session.user.id} onSignOut={onSignOut} />
  );
}
