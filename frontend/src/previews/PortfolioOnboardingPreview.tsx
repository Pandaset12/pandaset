import React, { useCallback, useState } from "react";
import ReactDOM from "react-dom/client";
import type { Portfolio, PortfolioInput } from "../api/portfolio";
import { Brand } from "../components/UI";
import { PortfolioOnboarding } from "../components/onboarding/PortfolioOnboarding";
import type { SearchTickers } from "../components/onboarding/TickerSearch";
import { assets } from "../../../quant/data";
import "../styles.css";
import "./onboarding-preview.css";

// Preview-only catalog and responses. Production supplies authenticated adapters.
const catalog = [
  ...assets.map(({ symbol, name }) => ({ symbol, name })),
  { symbol: "SPY", name: "SPDR S&P 500 ETF Trust" },
];

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    function abort() {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      reject(new DOMException("Aborted", "AbortError"));
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}

function Preview() {
  const [loadState, setLoadState] = useState<"empty" | "loading" | "error">(
    "empty",
  );
  const [saveMode, setSaveMode] = useState("success");
  const [searchFailure, setSearchFailure] = useState(false);
  const [version, setVersion] = useState(0);
  const [lastInput, setLastInput] = useState<PortfolioInput | null>(null);
  const [createCalls, setCreateCalls] = useState(0);
  const [selected, setSelected] = useState("");
  const searchTickers = useCallback<SearchTickers>(
    async (query, { signal }) => {
      await wait(180, signal);
      if (searchFailure) throw new Error("Preview search failure.");
      const normalized = query.toLowerCase().trim();
      return catalog.filter(
        (ticker) =>
          ticker.symbol.toLowerCase().includes(normalized) ||
          ticker.name.toLowerCase().includes(normalized),
      );
    },
    [searchFailure],
  );

  const createPortfolio = useCallback(
    async (
      input: PortfolioInput,
      { signal }: { signal: AbortSignal },
    ): Promise<Portfolio> => {
      setLastInput(structuredClone(input));
      setCreateCalls((count) => count + 1);
      await wait(saveMode === "slow" ? 2500 : 700, signal);
      if (saveMode === "fail") {
        setSaveMode("success");
        throw new Error("Preview save failure.");
      }
      return {
        ...input,
        portfolio_id: "preview-portfolio",
        created_at: new Date().toISOString(),
        revision: 1,
      };
    },
    [saveMode],
  );

  function reset() {
    setVersion((value) => value + 1);
    setLoadState("empty");
    setLastInput(null);
    setCreateCalls(0);
    setSelected("");
  }

  return (
    <div className="po-preview">
      <a className="skip-link" href="#onboarding-content">
        Skip to portfolio setup
      </a>
      <header className="po-preview-header">
        <Brand />
        <span>Investor workspace</span>
      </header>
      <div className="po-preview-banner">
        COMPONENT PREVIEW{" "}
        <span>Sample search results · Portfolios stay in this preview</span>
      </div>
      <main id="onboarding-content" tabIndex={-1}>
        <PortfolioOnboarding
          key={version}
          loadState={loadState}
          onRetryLoad={() => setLoadState("empty")}
          searchTickers={searchTickers}
          createPortfolio={createPortfolio}
          onOpenPortfolio={(portfolio) => setSelected(portfolio.name)}
        />
      </main>
      {selected && (
        <p className="po-preview-selection" role="status">
          Preview handoff complete: {selected} selected. Dashboard integration
          is handled by the parent app.
        </p>
      )}
      <details className="po-preview-controls">
        <summary>Preview controls & API handoff</summary>
        <div className="po-preview-control-row">
          <label>
            Portfolio loading state
            <select
              value={loadState}
              onChange={(event) =>
                setLoadState(event.target.value as typeof loadState)
              }
            >
              <option value="empty">No portfolios</option>
              <option value="loading">Loading</option>
              <option value="error">Loading error</option>
            </select>
          </label>
          <label>
            Next create request
            <select
              value={saveMode}
              onChange={(event) => setSaveMode(event.target.value)}
            >
              <option value="success">Success</option>
              <option value="fail">Fail once, then allow retry</option>
              <option value="slow">Slow success</option>
            </select>
          </label>
          <label className="po-preview-checkbox">
            <input
              type="checkbox"
              checked={searchFailure}
              onChange={(event) => setSearchFailure(event.target.checked)}
            />
            Simulate ticker search failure
          </label>
          <button className="button subtle" type="button" onClick={reset}>
            Reset preview
          </button>
        </div>
        <p>
          Create calls: {createCalls}. No real API request is made by this
          preview.
        </p>
        {lastInput && (
          <pre aria-label="Last portfolio API payload">
            {JSON.stringify(lastInput, null, 2)}
          </pre>
        )}
      </details>
      <footer className="po-preview-footer">
        Pandaset · A clearer view of what you own.
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Preview />
  </React.StrictMode>,
);
