import assert from "node:assert/strict";
import { after, test } from "node:test";
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
});

const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen } =
  await import("@testing-library/react");
const { default: Overview } = await import("../src/pages/Overview");

after(() => {
  cleanup();
  dom.window.close();
});

const analysis = {
  analysis_id: "analysis_fixture",
  portfolio_id: "saved",
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
      analysis,
      holdings: ["SPY", "AAPL", "JPM"].map(workspaceAsset),
      onEdit: () => {},
      onAsk: () => {},
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
