import { test } from "node:test";
import assert from "node:assert/strict";
import {
  requestResearchSummary,
  requestScenarioExplanation,
} from "../src/api/portfolio.ts";

test("scenario explanation sends the selected analysis and exact positive draft weights", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ url: string; options: RequestInit }> = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), options: options || {} });
    return new Response(JSON.stringify({ status: "demo" }), { status: 200 });
  };
  const draft = [20, 20, 16, 16, 18, 10, 0, 0];
  try {
    await requestScenarioExplanation("portfolio id", "analysis-1", draft);
    assert.equal(
      calls[0].url,
      "/api/v1/portfolios/portfolio%20id/what-if/explanation",
    );
    const body = JSON.parse(String(calls[0].options.body));
    assert.equal(body.analysis_id, "analysis-1");
    assert.deepEqual(body.proposed_weights, {
      NVDA: 0.2,
      MSFT: 0.2,
      AAPL: 0.16,
      JPM: 0.16,
      VTI: 0.18,
      TLT: 0.1,
    });
    assert.deepEqual(draft, [20, 20, 16, 16, 18, 10, 0, 0]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Research summary request uses only the issuer source selector", async () => {
  const originalFetch = globalThis.fetch;
  let call: { url: string; options: RequestInit } | undefined;
  globalThis.fetch = async (url, options) => {
    call = { url: String(url), options: options || {} };
    return new Response(JSON.stringify({ status: "demo" }), { status: 200 });
  };
  try {
    await requestResearchSummary("nvda");
    assert.equal(call?.url, "/api/v1/research/NVDA/summary");
    assert.deepEqual(JSON.parse(String(call?.options.body)), {
      source_id: "issuer",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
