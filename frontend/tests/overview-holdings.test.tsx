import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";
import { JSDOM } from "jsdom";
import type { AnalysisResponse } from "../src/api/portfolio";
import { workspaceAsset } from "../src/workspace/holdings";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  location: dom.window.location,
  HTMLElement: dom.window.HTMLElement,
  MutationObserver: dom.window.MutationObserver,
  ResizeObserver: class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
});
Object.defineProperty(document, "visibilityState", {
  configurable: true,
  value: "visible",
});

const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen, waitFor } =
  await import("@testing-library/react");
const { setApiAccessToken } = await import("../src/api/portfolio");
const { default: Overview } = await import("../src/pages/Overview");
const originalFetch = globalThis.fetch;

afterEach(() => {
  cleanup();
  setApiAccessToken(null);
  globalThis.fetch = originalFetch;
});
after(() => {
  dom.window.close();
});

const analysis = {
  portfolio_id: "saved",
  as_of: "2026-09-25T00:00:00Z",
  data_mode: "demo",
  data_quality: {
    source: "synthetic_fixture",
    freshness: "unknown",
    warnings: [],
  },
  weights: { SPY: 0.6, AAPL: 0.3, JPM: 0.1 },
  return_contribution: { SPY: 0.01, AAPL: -0.02, JPM: 0.08 },
  risk_contribution: { SPY: 0.6, AAPL: 0.3, JPM: 0.1 },
  portfolio_return: 0.07,
  annualized_return: 0.07,
  portfolio_volatility: 0.1,
  max_drawdown: -0.03,
  lookback_days: 6,
  observation_count: 6,
  series: null,
} as AnalysisResponse;

function tableRows() {
  return Array.from(screen.getByRole("table").querySelectorAll("tbody tr"));
}

function rowSymbols() {
  return tableRows().map(
    (row) => row.querySelector(".holding-identity strong")?.textContent,
  );
}

test("Overview holdings sort by allocation or descending signed return contribution", () => {
  render(
    createElement(Overview, {
      portfolioName: "Long-term holdings",
      analysis,
      holdings: ["SPY", "AAPL", "JPM"].map(workspaceAsset),
      onEdit: () => {},
      onBrief: () => {},
      onMethod: () => {},
    }),
  );
  const sort = screen.getByRole("combobox", {
    name: "Sort holdings",
  }) as HTMLSelectElement;
  assert.equal(sort.value, "weight");
  assert.equal(sort.selectedOptions[0].textContent, "By allocation");
  assert.deepEqual(rowSymbols(), ["SPY", "AAPL", "JPM"]);

  fireEvent.change(sort, { target: { value: "return" } });
  assert.equal(sort.value, "return");
  assert.equal(sort.selectedOptions[0].textContent, "By return impact");
  assert.deepEqual(rowSymbols(), ["JPM", "SPY", "AAPL"]);

  fireEvent.change(sort, { target: { value: "weight" } });
  assert.equal(sort.selectedOptions[0].textContent, "By allocation");
  assert.deepEqual(rowSymbols(), ["SPY", "AAPL", "JPM"]);

  const [spy, apple, jpm] = tableRows();
  assert.equal(spy.querySelector(".holding-identity small"), null);
  assert.equal(
    apple.querySelector(".holding-identity small")?.textContent,
    "Apple Inc.",
  );
  assert.equal(
    jpm.querySelector(".holding-identity small")?.textContent,
    "JPMorgan Chase & Co.",
  );
  cleanup();
});

test("overview heading follows the selected portfolio name", () => {
  const props = {
    analysis,
    holdings: [workspaceAsset("SPY")],
    onEdit: () => {},
    onBrief: () => {},
    onMethod: () => {},
  };
  const view = render(
    createElement(Overview, { ...props, portfolioName: "Retirement" }),
  );
  assert.ok(screen.getByRole("heading", { level: 1, name: "Retirement" }));

  view.rerender(
    createElement(Overview, { ...props, portfolioName: "Travel fund" }),
  );
  assert.ok(screen.getByRole("heading", { level: 1, name: "Travel fund" }));
  assert.equal(screen.queryByText("Retirement"), null);
});

function renderOverview(snapshot: AnalysisResponse, symbols: string[]) {
  return render(
    createElement(Overview, {
      portfolioName: "Example portfolio",
      analysis: snapshot,
      holdings: symbols.map(workspaceAsset),
      onEdit: () => {},
      onBrief: () => {},
      onMethod: () => {},
    }),
  );
}

test("sample Overview keeps modeled metrics separate from Alpaca IEX prices", async () => {
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        source: "alpaca",
        feed: "IEX",
        quotes: [
          {
            symbol: "SPY",
            last_price: 420,
            last_trade_at: "2026-09-25T19:59:00Z",
            bid: null,
            ask: null,
            quote_at: null,
          },
        ],
      }),
    )) as typeof fetch;
  setApiAccessToken("test-session");
  const sample = {
    ...analysis,
    weights: { SPY: 1 },
    risk_contribution: { SPY: 1 },
    return_contribution: { SPY: 0.07 },
  };
  const view = renderOverview(sample, ["SPY"]);
  await waitFor(() => assert.ok(screen.getByText("$420.00")));
  assert.match(view.container.textContent ?? "", /Fictional sample history/);
  assert.match(view.container.textContent ?? "", /\+7\.00%/);
  assert.match(view.container.textContent ?? "", /Alpaca IEX/);
  assert.doesNotMatch(
    view.container.textContent ?? "",
    /Alpaca adjusted daily history/,
  );
});

test("Alpaca Overview uses the saved symbols, weights, session and available benchmark", () => {
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        error: { code: "ALPACA_NOT_CONFIGURED", message: "Quotes unavailable" },
      }),
      { status: 503 },
    )) as typeof fetch;
  const live = {
    ...analysis,
    data_mode: "live" as const,
    data_quality: {
      source: "alpaca_adjusted_daily",
      freshness: "fresh" as const,
      warnings: ["Alpaca IEX adjusted daily closes; not intraday quotes."],
    },
    weights: { TSLA: 0.75, SPY: 0.25 },
    risk_contribution: { TSLA: 0.75, SPY: 0.25 },
    return_contribution: { TSLA: 0.06, SPY: 0.01 },
    series: {
      dates: ["2026-09-23", "2026-09-24", "2026-09-25"],
      portfolio_index: [1, 1.03, 1.07],
      asset_index: { TSLA: [1, 1.04, 1.08], SPY: [1, 1.01, 1.02] },
      return_contribution: { TSLA: 0.06, SPY: 0.01 },
    },
  } as AnalysisResponse;
  const view = renderOverview(live, ["TSLA", "SPY"]);
  assert.match(
    view.container.textContent ?? "",
    /Alpaca adjusted daily history/,
  );
  assert.match(view.container.textContent ?? "", /Sep 25, 2026/);
  assert.match(
    view.container.textContent ?? "",
    /Alpaca IEX adjusted daily closes/,
  );
  assert.doesNotMatch(
    view.container.textContent ?? "",
    /short sample|available sample|sample dates/,
  );
  assert.match(
    view.container.querySelector(".metric-strip")?.textContent ?? "",
    /Largest allocation75%TSLA/,
  );
  assert.match(view.container.textContent ?? "", /TSLA/);
  assert.equal(screen.queryByText("VTI history"), null);
  assert.equal(screen.queryByText("On your radar"), null);
  assert.equal(screen.queryByText(/Return contribution comes from/), null);
  assert.doesNotMatch(
    view.container.textContent ?? "",
    /This holding uses the backend's sample/,
  );

  const withVti = {
    ...live,
    weights: { TSLA: 0.2, VTI: 0.8 },
    risk_contribution: { TSLA: 0.2, VTI: 0.8 },
    return_contribution: { TSLA: 0.02, VTI: 0.05 },
    series: {
      ...live.series!,
      asset_index: { TSLA: [1, 1.04, 1.08], VTI: [1, 1.02, 1.06] },
    },
  } as AnalysisResponse;
  view.rerender(
    createElement(Overview, {
      portfolioName: "Example portfolio",
      analysis: withVti,
      holdings: ["TSLA", "VTI"].map(workspaceAsset),
      onEdit: () => {},
      onBrief: () => {},
      onMethod: () => {},
    }),
  );
  assert.match(
    view.container.querySelector(".metric-strip")?.textContent ?? "",
    /Largest allocation80%VTI/,
  );
  assert.ok(screen.getByText("VTI history"));
});

test("missing historical metrics and missing IEX trades stay unavailable", async () => {
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        source: "alpaca",
        feed: "IEX",
        quotes: [
          {
            symbol: "SPY",
            last_price: null,
            last_trade_at: null,
            bid: null,
            ask: null,
            quote_at: null,
          },
        ],
      }),
    )) as typeof fetch;
  setApiAccessToken("test-session");
  const missing = {
    ...analysis,
    weights: { SPY: 1 },
    risk_contribution: { SPY: null },
    return_contribution: { SPY: null },
    portfolio_return: null,
    annualized_return: null,
    max_drawdown: null,
  } as AnalysisResponse;
  const view = renderOverview(missing, ["SPY"]);
  await waitFor(() => assert.ok(screen.getByText("No IEX trade available")));
  assert.match(
    view.container.textContent ?? "",
    /Dated portfolio history is unavailable/,
  );
  assert.match(view.container.textContent ?? "", /Unavailable/);
  assert.equal(screen.queryByText("$0.00"), null);
});
