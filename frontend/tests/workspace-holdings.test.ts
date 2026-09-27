import assert from "node:assert/strict";
import { test } from "node:test";
import type { Portfolio } from "../src/api/portfolio";
import {
  portfolioFromPercentages,
  portfolioPercentages,
  validPercentages,
  workspaceAssets,
  parsePercentageDraft,
} from "../src/workspace/holdings";

function portfolio(holdings: Portfolio["holdings"]): Portfolio {
  return {
    portfolio_id: "saved",
    name: "Saved",
    created_at: "2026-09-26T00:00:00Z",
    holdings,
  };
}

test("backend portfolio symbols, including SPY, define the workspace holdings", () => {
  const saved = portfolio([{ symbol: "SPY", weight: 1 }]);
  assert.deepEqual(
    workspaceAssets(saved).map(({ symbol }) => symbol),
    ["SPY"],
  );
  assert.deepEqual(portfolioPercentages(saved), [100]);
  assert.deepEqual(
    portfolioFromPercentages("SPY copy", ["SPY"], [100]).holdings,
    [{ symbol: "SPY", weight: 1 }],
  );
});

test("unknown holding metadata does not invent a market-data source", () => {
  const [holding] = workspaceAssets(portfolio([{ symbol: "SPY", weight: 1 }]));
  assert.equal(
    holding.description,
    "Price history comes from the configured market-data provider. See the chart for source and freshness.",
  );
});

test("fractional backend weights stay exact and immediately valid", () => {
  const saved = portfolio([
    { symbol: "SPY", weight: 0.255 },
    { symbol: "TLT", weight: 0.745 },
  ]);
  const percentages = portfolioPercentages(saved);
  assert.deepEqual(percentages, [25.5, 74.5]);
  assert.equal(validPercentages(percentages, ["SPY", "TLT"]), true);
  assert.deepEqual(
    portfolioFromPercentages("copy", ["SPY", "TLT"], percentages).holdings,
    saved.holdings,
  );
});

test("thirds reconcile to editable six-decimal percentages totaling exactly 100", () => {
  const symbols = ["SPY", "TLT", "AAPL"];
  const saved = portfolio(symbols.map((symbol) => ({ symbol, weight: 1 / 3 })));
  const percentages = portfolioPercentages(saved);
  assert.equal(
    percentages.reduce((sum, value) => sum + value, 0),
    100,
  );
  assert.ok(percentages.every((value) => /^\d+\.\d{6}$/.test(String(value))));
  assert.deepEqual(parsePercentageDraft(percentages.map(String)), percentages);
  const updated = portfolioFromPercentages("thirds", symbols, percentages);
  assert.ok(
    Math.abs(
      updated.holdings.reduce((sum, holding) => sum + holding.weight, 0) - 1,
    ) < 1e-10,
  );
  assert.ok(
    updated.holdings.every(
      (holding) => Math.abs(holding.weight - 1 / 3) < 1e-8,
    ),
  );
});

test("unsupported saved tickers remain visible and can be replaced without local allowlisting", () => {
  const saved = portfolio([{ symbol: "TSLA", weight: 1 }]);
  assert.deepEqual(
    workspaceAssets(saved).map(({ symbol }) => symbol),
    ["TSLA"],
  );
  assert.deepEqual(
    portfolioFromPercentages("replacement", ["SPY"], [100]).holdings,
    [{ symbol: "SPY", weight: 1 }],
  );
});
