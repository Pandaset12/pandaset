import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  ChatBubbleLeftRight,
  Check,
  ChevronDown,
  InformationCircle as Info,
  XMark as X,
} from "./components/icons";
import { initialWeights, asOf } from "../../quant/data";
import { validateWeights } from "../../quant/analytics";
import { Brand } from "./components/UI";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EditPortfolio } from "./components/EditPortfolio";
import { MethodologyModal } from "./components/MethodologyModal";
import { Analyst } from "./components/Analyst";
import Overview from "./pages/Overview";
import Risk from "./pages/Risk";
import Research from "./pages/Research";
import WhatIf from "./pages/WhatIf";
function Application() {
  const [hash, setHash] = useState(location.hash || "#/");
  const [weights, setWeights] = useState([...initialWeights]);
  const [edit, setEdit] = useState(false);
  const [method, setMethod] = useState(false);
  const [analyst, setAnalyst] = useState<string | null>(null);
  const [toast, setToast] = useState("");
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
  const [path, search = ""] = hash.replace(/^#/, "").split("?");
  const route = ["/", "/risk", "/research", "/what-if"].includes(path)
    ? path
    : "/";
  const query = new URLSearchParams(search);
  useEffect(() => {
    document.title = `${route === "/" ? "Overview" : route === "/risk" ? "Risk & exposure" : route === "/research" ? "Research" : "Scenario lab"} — PandaSet`;
  }, [route]);
  function apply(w: number[], source: "edit" | "scenario" = "edit") {
    if (!validateWeights(w)) return;
    setWeights([...w]);
    setEdit(false);
    setToast(
      source === "scenario"
        ? "Scenario applied for this browser session. Reloading restores the example portfolio."
        : "Sample portfolio updated for this browser session. Reloading restores the example portfolio.",
    );
  }
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
          <button className="analyst-button" onClick={() => setAnalyst("")}>
            <ChatBubbleLeftRight size={17} />
            <span>Ask Panda</span>
            <span className="key-hint">↗</span>
          </button>
        </div>
      </header>
      <div className="workspace-bar">
        <div>
          <button className="portfolio-selector" onClick={() => setEdit(true)}>
            <span className="portfolio-initial">L</span>Long-term portfolio
            <ChevronDown size={14} />
          </button>
          <button className="demo-badge" onClick={() => setMethod(true)}>
            SAMPLE DATA
            <Info size={12} />
          </button>
        </div>
        <span className="as-of">
          As of {asOf}
          <span className="separator">/</span>USD
        </span>
      </div>
      <main id="main-content" className="main-content" tabIndex={-1}>
        <ErrorBoundary>
          {route === "/" ? (
            <Overview
              weights={weights}
              onEdit={() => setEdit(true)}
              onAsk={(q) => setAnalyst(q || "")}
              onMethod={() => setMethod(true)}
            />
          ) : route === "/risk" ? (
            <Risk
              weights={weights}
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
              weights={weights}
              onApply={(w) => {
                apply(w, "scenario");
                location.hash = "#/";
              }}
              onAsk={(q) => setAnalyst(q || "")}
              query={query}
            />
          )}
        </ErrorBoundary>
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
      {edit && (
        <EditPortfolio
          weights={weights}
          onClose={() => setEdit(false)}
          onSave={apply}
        />
      )}
      {method && <MethodologyModal onClose={() => setMethod(false)} />}
      {analyst !== null && (
        <Analyst
          key={analyst}
          weights={weights}
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
