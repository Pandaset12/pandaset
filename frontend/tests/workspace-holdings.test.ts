import assert from "node:assert/strict";
import { test } from "node:test";
import type { Portfolio } from "../src/api/portfolio";
import {
  portfolioFromPercentages,
  portfolioPercentages,
  validPercentages,
  workspaceAssets,
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
