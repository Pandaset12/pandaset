import { useEffect, useState, Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
import {
  ArrowPath as RotateCcw,
  ArrowUpRight,
  ChatBubbleLeftRight,
  Check,
  ChevronDown,
  InformationCircle as Info,
  XMark as X,
} from "./components/icons";
import { assets, initialWeights, asOf } from "../../quant/data";
import { validateWeights } from "../../quant/analytics";
import { Brand, Modal, AssetMark } from "./components/UI";
import { Analyst } from "./components/Analyst";
import Overview from "./pages/Overview";
import Risk from "./pages/Risk";
import Research from "./pages/Research";
import WhatIf from "./pages/WhatIf";
class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("PandaSet rendering error", error, info.componentStack);
  }
  render() {
    return this.state.error ? (
      <main className="error-page">
        <h1>Something didn’t load.</h1>
        <p>Your sample portfolio can be restored by reloading the page.</p>
        <button className="button dark" onClick={() => location.reload()}>
          Reload PandaSet
          <RotateCcw size={16} />
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
function EditPortfolio({
  weights,
  onClose,
  onSave,
}: {
  weights: number[];
  onClose: () => void;
  onSave: (w: number[]) => void;
}) {
  const [draft, setDraft] = useState([...weights]);
  const total = draft.reduce((a, b) => a + b, 0);
  const valid = validateWeights(draft);
  return (
    <Modal title="Edit your sample portfolio" onClose={onClose}>
      <p className="modal-description">
        Set the allocation for each asset. Your weights should add up to 100%.
      </p>
      <div className="edit-weights">
        {assets.map((a, i) => (
          <label key={a.symbol}>
            <span>
              <AssetMark asset={a} small />
              <strong>{a.symbol}</strong>
              <small>{a.short}</small>
            </span>
            <span className="edit-weight-input">
              <input
                aria-label={`${a.symbol} portfolio allocation`}
                type="number"
                min="0"
                max="100"
                step="1"
                value={draft[i]}
                onChange={(e) =>
                  setDraft(
                    draft.map((v, j) => (i === j ? Number(e.target.value) : v)),
                  )
                }
              />
              %
            </span>
          </label>
        ))}
      </div>
      <div className={`allocation-total ${valid ? "valid" : "invalid"}`}>
        <span>Total allocation</span>
        <strong>{Number(total.toFixed(2))}%</strong>
      </div>
      {!valid && (
        <p className="field-error" role="alert">
          Allocations must total 100%, with each value between 0% and 100%.
        </p>
      )}
      <div className="modal-actions">
        <button
          className="text-button"
          onClick={() => setDraft([...initialWeights])}
        >
          <RotateCcw size={15} />
          Restore example
        </button>
        <button
          className="button dark"
          disabled={!valid}
          onClick={() => onSave(draft)}
        >
          Update portfolio
          <Check size={16} />
        </button>
      </div>
      <p className="small-text muted">
        Changes stay in this session. Reloading restores the example portfolio.
      </p>
    </Modal>
  );
}
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
      {method && (
        <Modal
          title="The numbers behind the view"
          onClose={() => setMethod(false)}
        >
          <div className="method-intro">
            <Info size={20} />
            <p>
              PandaSet is an interactive interface demo. Prices, returns, and
              portfolio values are illustrative, not live market data.
            </p>
          </div>
          <dl className="method-list">
            <dt>Sample period</dt>
            <dd>
              252 synthetic daily returns ending September 25, 2026. Every page
              uses the same observations.
            </dd>
            <dt>Portfolio model</dt>
            <dd>
              Constant daily allocations, with no deposits, withdrawals, fees,
              or taxes. Displayed value is a sample balance of $128,450.
            </dd>
            <dt>Risk & correlation</dt>
            <dd>
              Volatility uses the sample covariance matrix, annualized by 252
              trading days. Risk contributions sum to 100%; they can be negative
              for diversifying positions.
            </dd>
            <dt>Returns & drawdown</dt>
            <dd>
              Returns compound daily. Return contribution uses each day’s
              allocation and preceding portfolio growth. Drawdown is the largest
              decline from an earlier peak in the sample.
            </dd>
            <dt>Research & explanations</dt>
            <dd>
              Research primers link to official sources. The analyst uses
              curated explanations and computed metrics; Gemini and news feeds
              are not connected.
            </dd>
          </dl>
        </Modal>
      )}
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
