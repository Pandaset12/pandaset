import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";
import { JSDOM } from "jsdom";
import type { MarketHistoryResponse } from "../src/api/portfolio";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  MutationObserver: dom.window.MutationObserver,
  ResizeObserver: class {
    observe() {}
    disconnect() {}
  },
});
const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen, waitFor, act } =
  await import("@testing-library/react");
const { default: Research } = await import("../src/pages/Research");
const originalFetch = globalThis.fetch;
afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
});
after(() => dom.window.close());

function history(
  symbol = "NVDA",
  overrides: Partial<MarketHistoryResponse> = {},
): MarketHistoryResponse {
  return {
    symbols: [symbol],
    dates: ["2026-09-24", "2026-09-25"],
    asset_index: { [symbol]: [1, 1.05] },
    data_mode: "demo",
    data_source: "synthetic_fixture",
    freshness: "unknown",
    requested_lookback_days: 252,
    observation_count: 1,
    warnings: [],
    ...overrides,
  };
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });
function props(query = "", weights = [25, 25, 25, 25, 0, 0, 0, 0]) {
  return {
    weights,
    query: new URLSearchParams(query),
    onAsk: () => {},
    onSummarizeSource: (_symbol: string) => {},
  };
}

test("loading doesn't masquerade as missing data, and vendor history is labelled as daily market data", async () => {
  let resolve!: (value: Response) => void;
  globalThis.fetch = () =>
    new Promise((done) => {
      resolve = done;
    });
  render(createElement(Research, props()));
  assert.ok(screen.getByText("Loading NVDA history"));
  assert.equal(screen.queryByText("Unavailable"), null);
  assert.equal(screen.queryByText("0 daily returns"), null);
  await act(async () =>
    resolve(
      json(
        history("NVDA", {
          data_mode: "live",
          data_source: "twelve_data_adjusted_daily",
        }),
      ),
    ),
  );
  await screen.findByRole("img", { name: /NVDA:.*5/ });
  assert.ok(screen.getByText("MARKET DATA · DAILY"));
  assert.ok(
    screen.getByText(
      /Twelve Data · adjusted daily closes · Freshness not verified/,
    ),
  );
  assert.equal(screen.queryByText("SAMPLE DATA"), null);
  assert.equal(screen.queryByText(/currently demo fixture/), null);
});

test("an outage keeps issuer sources usable and retry recovers the chart", async () => {
  let calls = 0;
  globalThis.fetch = async () =>
    ++calls === 1
      ? json(
          { error: { message: "The market data provider is unavailable." } },
          502,
        )
      : json(history());
  const summarized: string[] = [];
  render(
    createElement(Research, {
      ...props(),
      onSummarizeSource: (symbol: string) => summarized.push(symbol),
    }),
  );
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("tab", { name: "Sources & filings" }));
  assert.ok(
    screen.getByRole("link", {
      name: /Selected issuer page.*opens in a new tab/,
    }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Summarize issuer source" }),
  );
  assert.deepEqual(summarized, ["NVDA"]);
  fireEvent.click(screen.getByRole("tab", { name: "Overview" }));
  fireEvent.click(screen.getByRole("button", { name: /Retry history/ }));
  await screen.findByRole("img", { name: /NVDA:/ });
  assert.equal(screen.queryByRole("alert"), null);
  assert.equal(calls, 2);
  assert.ok(screen.getByText("SAMPLE DATA"));
});

for (const series of [[], [1], [1, null], [1, 0]]) {
  test(`incomplete history ${JSON.stringify(series)} shows an empty state, not a broken chart`, async () => {
    globalThis.fetch = async () =>
      json(history("NVDA", { asset_index: { NVDA: series } }));
    render(createElement(Research, props()));
    await screen.findByText("No usable price history yet");
    assert.equal(screen.queryByRole("img", { name: /NVDA:/ }), null);
    assert.ok(screen.getByRole("button", { name: "Retry history" }));
  });
}

test("research sections support arrow keys, Home/End, and linked tab panels", async () => {
  globalThis.fetch = async () => json(history());
  render(createElement(Research, props()));
  await screen.findByRole("img", { name: /NVDA:/ });
  const overview = screen.getByRole("tab", { name: "Overview" });
  const sources = screen.getByRole("tab", { name: "Sources & filings" });
  overview.focus();
  fireEvent.keyDown(overview, { key: "ArrowRight" });
  assert.equal(document.activeElement, sources);
  assert.equal(sources.getAttribute("aria-selected"), "true");
  assert.equal(
    screen.getByRole("tabpanel").id,
    sources.getAttribute("aria-controls"),
  );
  fireEvent.keyDown(sources, { key: "Home" });
  assert.equal(document.activeElement, overview);
  fireEvent.keyDown(overview, { key: "End" });
  assert.equal(document.activeElement, sources);
  fireEvent.keyDown(sources, { key: "ArrowLeft" });
  assert.equal(document.activeElement, overview);
});

test("empty holdings and search results explain how to recover", async () => {
  globalThis.fetch = async () => json(history());
  render(createElement(Research, props("", Array(8).fill(0))));
  await screen.findByRole("img", { name: /NVDA:/ });
  fireEvent.click(screen.getByRole("button", { name: "Your holdings" }));
  assert.ok(screen.getByText("No holdings in this library"));
  fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "does-not-exist" },
  });
  assert.ok(screen.getByText("No matching assets"));
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "  nvidia  " },
  });
  const directory = screen.getByRole("navigation", { name: "Research assets" });
  assert.equal(directory.querySelectorAll("a").length, 1);
});

test("unknown research URLs don't silently show or fetch NVIDIA", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return json(history());
  };
  render(createElement(Research, props("symbol=UNKNOWN")));
  assert.ok(screen.getByText("This asset isn't in the research library"));
  assert.ok(screen.getByRole("link", { name: "Browse supported assets" }));
  assert.equal(calls, 0);
});

test("a late response for a previous ticker can't overwrite the current chart", async () => {
  const pending = new Map<string, (value: Response) => void>();
  globalThis.fetch = (url) =>
    new Promise((resolve) => {
      pending.set(
        new URL(String(url), "http://localhost").searchParams.get("symbols")!,
        resolve,
      );
    });
  const view = render(createElement(Research, props("symbol=NVDA")));
  view.rerender(createElement(Research, props("symbol=MSFT")));
  await act(async () => pending.get("MSFT")!(json(history("MSFT"))));
  await screen.findByRole("img", { name: /MSFT:/ });
  await act(async () => pending.get("NVDA")!(json(history("NVDA"))));
  await waitFor(() => assert.ok(screen.getByRole("img", { name: /MSFT:/ })));
  assert.equal(screen.queryByRole("img", { name: /NVDA:/ }), null);
});
