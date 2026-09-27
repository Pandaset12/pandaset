import { test } from "node:test";
import assert from "node:assert/strict";
import {
  analyzeExistingPortfolio,
  createPortfolio,
  portfolioInput,
} from "../../frontend/src/api/portfolio.ts";
import { initialWeights } from "../data.ts";

test("omits zero weights and converts positive percentages without normalization", () => {
  const input = portfolioInput(initialWeights);
  assert.deepEqual(input.holdings, [
    { symbol: "NVDA", weight: 0.24 },
    { symbol: "MSFT", weight: 0.2 },
    { symbol: "AAPL", weight: 0.16 },
    { symbol: "JPM", weight: 0.12 },
    { symbol: "VTI", weight: 0.18 },
    { symbol: "TLT", weight: 0.1 },
  ]);
  assert.throws(() => portfolioInput([25, ...initialWeights.slice(1)]));
});

test("creates a portfolio, then reads current metrics for its returned ID", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ url: string; options: RequestInit }> = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), options: options || {} });
    return new Response(
      JSON.stringify(
        calls.length === 1
          ? {
              ...portfolioInput(initialWeights),
              portfolio_id: "saved-id",
              created_at: "2026-01-01",
              revision: 1,
            }
          : {
              portfolio_id: "saved-id",
              portfolio_revision: 1,
              weights: Object.fromEntries(
                portfolioInput(initialWeights).holdings.map(
                  ({ symbol, weight }) => [symbol, weight],
                ),
              ),
            },
      ),
      { status: calls.length === 1 ? 201 : 200 },
    );
  };
  try {
    const portfolio = await createPortfolio(portfolioInput(initialWeights));
    const result = await analyzeExistingPortfolio(portfolio);
    assert.equal(result.portfolio.portfolio_id, "saved-id");
    assert.equal(result.analysis.portfolio_revision, 1);
    assert.equal(calls[0].url, "/api/v1/portfolios");
    assert.equal(calls[1].url, "/api/v1/portfolios/saved-id/metrics");
    assert.deepEqual(
      JSON.parse(String(calls[0].options.body)).holdings,
      portfolioInput(initialWeights).holdings,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("surfaces API failures", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: { message: "Unavailable" } }), {
      status: 503,
    });
  try {
    await assert.rejects(
      createPortfolio(portfolioInput(initialWeights)),
      /Unavailable/,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
