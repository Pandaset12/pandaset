import assert from "node:assert/strict";
import { after, test } from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  MutationObserver: dom.window.MutationObserver,
});
Object.defineProperty(document, "visibilityState", {
  configurable: true,
  value: "visible",
});

const { createElement } = await import("react");
const { cleanup, render, screen, waitFor } =
  await import("@testing-library/react");
const { setApiAccessToken } = await import("../src/api/portfolio");
const { LiveQuotesPanel } = await import("../src/components/LiveQuotesPanel");
const originalFetch = globalThis.fetch;

after(() => {
  cleanup();
  setApiAccessToken(null);
  globalThis.fetch = originalFetch;
  dom.window.close();
});

test("LiveQuotesPanel renders the latest IEX trade and avoids risk-metric claims", async () => {
  let requested = "";
  let authorization = "";
  globalThis.fetch = (async (input, init) => {
    requested = String(input);
    authorization = new Headers(init?.headers).get("Authorization") ?? "";
    return new Response(JSON.stringify({
      feed: "IEX",
      source: "alpaca",
      quotes: [{
        symbol: "AAPL",
        last_price: 201.25,
        last_trade_at: "2026-09-26T14:30:00Z",
        bid: 201.2,
        ask: 201.3,
        quote_at: "2026-09-26T14:30:01Z",
      }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  setApiAccessToken("test-session");

  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.ok(screen.getByText("$201.25")));

  assert.equal(new URL(requested, "http://localhost").pathname, "/api/v1/quotes");
  assert.equal(authorization, "Bearer test-session");
  assert.match(screen.getByRole("region", { name: "Latest IEX stock prices" }).textContent ?? "", /separate from risk calculations/);
  assert.match(screen.getByText(/Last IEX trade/).textContent ?? "", /2026/);
  cleanup();
});
