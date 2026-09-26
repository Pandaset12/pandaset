import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ChatBubbleLeftRight,
  Check,
  ChevronDown,
  InformationCircle as Info,
  XMark as X,
} from "./components/icons";
import { assets, initialWeights } from "../../quant/data";
import {
  analyzePortfolio,
  createRequestGuard,
  type AnalysisResponse,
  type Portfolio,
} from "./api/portfolio";
import { Brand } from "./components/UI";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EditPortfolio } from "./components/EditPortfolio";
import { MethodologyModal } from "./components/MethodologyModal";
import { Analyst } from "./components/Analyst";
import Overview from "./pages/Overview";
import Risk from "./pages/Risk";
import Research from "./pages/Research";
import WhatIf from "./pages/WhatIf";

type ActiveAnalysis = { portfolio: Portfolio; analysis: AnalysisResponse };

function weightsFromAnalysis(analysis: AnalysisResponse) {
  return assets.map((asset) =>
    Math.round((analysis.weights[asset.symbol] ?? 0) * 100),
  );
}

function Application() {
  const [hash, setHash] = useState(location.hash || "#/");
  const [weights, setWeights] = useState([...initialWeights]);
  const [edit, setEdit] = useState(false);
  const [method, setMethod] = useState(false);
  const [analyst, setAnalyst] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [active, setActive] = useState<ActiveAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [analysisError, setAnalysisError] = useState("");
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

  async function loadAnalysis(nextWeights: number[]) {
    const request = analysisRequest.current.begin();
    setAnalysisLoading(true);
    setAnalysisError("");
    try {
      const result = await analyzePortfolio(nextWeights);
      if (!analysisRequest.current.isCurrent(request)) return false;
      setActive(result);
      setWeights(weightsFromAnalysis(result.analysis));
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

  useEffect(() => {
    void loadAnalysis(initialWeights);
    return () => {
      analysisRequest.current.invalidate();
    };
  }, []);

  async function apply(
    nextWeights: number[],
    source: "edit" | "scenario" = "edit",
  ) {
    if (!(await loadAnalysis(nextWeights))) return false;
    setEdit(false);
    setToast(
      source === "scenario"
        ? "Scenario saved as the active sample portfolio."
        : "Sample portfolio updated.",
    );
    return true;
  }

  const [path, search = ""] = hash.replace(/^#/, "").split("?");
  const route = ["/", "/risk", "/research", "/what-if"].includes(path)
    ? path
    : "/";
  const query = new URLSearchParams(search);
  useEffect(() => {
    document.title = `${route === "/" ? "Overview" : route === "/risk" ? "Risk & exposure" : route === "/research" ? "Research" : "Scenario lab"} — PandaSet`;
  }, [route]);

  const nav = [
    ["/", "Overview"],
    ["/risk", "Risk & exposure"],
    ["/research", "Research"],
    ["/what-if", "What-if lab"],
  ];
  const asOf = active?.analysis.as_of
    ? new Date(active.analysis.as_of).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      })
    : "Unavailable";

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
            className="analyst-button"
            onClick={() => setAnalyst("")}
            disabled={!active}
          >
            <ChatBubbleLeftRight size={17} />
            <span>Ask Panda</span>
            <span className="key-hint">↗</span>
          </button>
        </div>
      </header>
      <div className="workspace-bar">
        <div>
          <button
            className="portfolio-selector"
            onClick={() => setEdit(true)}
            disabled={!active || analysisLoading}
          >
            <span className="portfolio-initial">L</span>
            {active?.portfolio.name ?? "Long-term portfolio"}
            <ChevronDown size={14} />
          </button>
          <button className="demo-badge" onClick={() => setMethod(true)}>
            {active?.analysis.data_mode === "live"
              ? "LIVE DATA"
              : "SAMPLE DATA"}
            <Info size={12} />
          </button>
        </div>
        <span className="as-of">
          As of {asOf}
          <span className="separator">/</span>USD
        </span>
      </div>
      <main id="main-content" className="main-content" tabIndex={-1}>
        {analysisLoading && !active ? (
          <section className="api-state" role="status">
            <strong>Loading portfolio analysis…</strong>
            <p>
              Connecting to the backend and calculating the sample portfolio.
            </p>
          </section>
        ) : analysisError && !active ? (
          <section className="api-state" role="alert">
            <strong>Portfolio analysis is unavailable.</strong>
            <p>{analysisError}</p>
            <button
              className="button dark"
              onClick={() => void loadAnalysis(initialWeights)}
              disabled={analysisLoading}
            >
              Retry analysis
            </button>
          </section>
        ) : active ? (
          <ErrorBoundary>
            {route === "/" ? (
              <Overview
                analysis={active.analysis}
                onEdit={() => setEdit(true)}
                onAsk={(q) => setAnalyst(q || "")}
                onMethod={() => setMethod(true)}
              />
            ) : route === "/risk" ? (
              <Risk
                analysis={active.analysis}
                onAsk={(q) => setAnalyst(q || "")}
                onMethod={() => setMethod(true)}
              />
            ) : route === "/research" ? (
              <Research
                key={hash}
                weights={weights}
                onAsk={(q) => setAnalyst(q || "")}
                query={query}
              />
            ) : (
              <WhatIf
                key={hash}
                analysis={active.analysis}
                weights={weights}
                onApply={(w) => apply(w, "scenario")}
                onAsk={(q) => setAnalyst(q || "")}
                query={query}
              />
            )}
            {analysisLoading && (
              <p className="analysis-saving" role="status">
                Saving the new allocation and calculating its analysis…
              </p>
            )}
            {analysisError && (
              <p className="analysis-saving error" role="alert">
                The active analysis is unchanged. {analysisError}{" "}
                <button
                  className="text-button"
                  onClick={() => void loadAnalysis(weights)}
                >
                  Retry
                </button>
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
        <button className="text-button" onClick={() => setMethod(true)}>
          Sample data & methodology
          <ArrowUpRight size={13} />
        </button>
      </footer>
      {edit && active && (
        <EditPortfolio
          weights={weights}
          busy={analysisLoading}
          error={analysisError}
          onClose={() => setEdit(false)}
          onSave={(w) => apply(w)}
        />
      )}
      {method && <MethodologyModal onClose={() => setMethod(false)} />}
      {analyst !== null && active && (
        <Analyst
          portfolioId={active.portfolio.portfolio_id}
          analysis={active.analysis}
          question={analyst}
          onClose={() => setAnalyst(null)}
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
      <Application />
    </ErrorBoundary>
  );
}
