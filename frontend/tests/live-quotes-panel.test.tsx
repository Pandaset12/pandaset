import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";
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
const { act, cleanup, render, screen, waitFor } =
  await import("@testing-library/react");
const { setApiAccessToken } = await import("../src/api/portfolio");
const { LiveQuotesPanel } = await import("../src/components/LiveQuotesPanel");
const originalFetch = globalThis.fetch;
const originalSetTimeout = window.setTimeout;
const originalClearTimeout = window.clearTimeout;

afterEach(() => {
  cleanup();
  setApiAccessToken(null);
  globalThis.fetch = originalFetch;
  window.setTimeout = originalSetTimeout;
  window.clearTimeout = originalClearTimeout;
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});
after(() => dom.window.close());

test("LiveQuotesPanel renders the latest IEX trade and avoids risk-metric claims", async () => {
  let requested = "";
  let authorization = "";
  globalThis.fetch = (async (input, init) => {
    requested = String(input);
    authorization = new Headers(init?.headers).get("Authorization") ?? "";
    return new Response(
      JSON.stringify({
        feed: "IEX",
        source: "alpaca",
        quotes: [
          {
            symbol: "AAPL",
            last_price: 201.25,
            last_trade_at: "2026-09-26T14:30:00Z",
            bid: 201.2,
            ask: 201.3,
            quote_at: "2026-09-26T14:30:01Z",
          },
        ],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }) as typeof fetch;
  setApiAccessToken("test-session");

  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.ok(screen.getByText("$201.25")));

  assert.equal(
    new URL(requested, "http://localhost").pathname,
    "/api/v1/quotes",
  );
  assert.equal(authorization, "Bearer test-session");
  assert.match(
    screen.getByRole("region", { name: "Latest IEX stock prices" })
      .textContent ?? "",
    /separate from risk calculations/,
  );
  assert.match(screen.getByText(/Last IEX trade/).textContent ?? "", /2026/);
  cleanup();
});

function quoteResponse(symbol = "AAPL", price: number | null = 201.25) {
  return new Response(
    JSON.stringify({
      feed: "IEX",
      source: "alpaca",
      quotes: [
        {
          symbol,
          last_price: price,
          last_trade_at: price === null ? null : "2026-09-25T19:59:00Z",
          bid: null,
          ask: null,
          quote_at: null,
        },
      ],
    }),
  );
}

function controlPolling() {
  let nextId = 0;
  const timers = new Map<number, { callback: () => void; delay: number }>();
  window.setTimeout = ((callback: () => void, delay: number) => {
    timers.set(++nextId, { callback, delay });
    return nextId;
  }) as typeof window.setTimeout;
  window.clearTimeout = (id?: number) => {
    timers.delete(id!);
  };
  return {
    timers,
    async tick() {
      const [id, timer] = timers.entries().next().value!;
      timers.delete(id);
      await act(async () => timer.callback());
    },
  };
}

async function visibility(value: "hidden" | "visible") {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value,
  });
  await act(async () =>
    document.dispatchEvent(new dom.window.Event("visibilitychange")),
  );
}

test("empty portfolios never poll, including after returning to the tab", async () => {
  let calls = 0;
  globalThis.fetch = (async () => {
    calls++;
    return quoteResponse();
  }) as typeof fetch;
  const polling = controlPolling();
  render(createElement(LiveQuotesPanel, { symbols: [] }));
  await visibility("hidden");
  await visibility("visible");
  assert.equal(calls, 0);
  assert.equal(polling.timers.size, 0);
  assert.equal(screen.queryByRole("region"), null);
});

test("polling pauses in hidden tabs and refreshes on return", async () => {
  let calls = 0;
  globalThis.fetch = (async () => {
    calls++;
    return quoteResponse();
  }) as typeof fetch;
  const polling = controlPolling();
  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.equal(polling.timers.size, 1));
  assert.equal([...polling.timers.values()][0].delay, 15_000);
  await visibility("hidden");
  assert.equal(polling.timers.size, 0);
  assert.equal(calls, 1);
  await visibility("visible");
  await waitFor(() => assert.equal(calls, 2));
  await waitFor(() => assert.equal(polling.timers.size, 1));
});

test("refresh failures retain labeled old prices and back off, then recover", async () => {
  let calls = 0;
  globalThis.fetch = (async () => {
    calls++;
    if (calls === 2 || calls === 3)
      return new Response(
        JSON.stringify({ error: { message: "Upstream error" } }),
        { status: 502 },
      );
    return quoteResponse("AAPL", calls === 1 ? 201.25 : 202);
  }) as typeof fetch;
  const polling = controlPolling();
  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.ok(screen.getByText("$201.25")));
  await polling.tick();
  await waitFor(() =>
    assert.match(
      screen.getByRole("status").textContent!,
      /Showing last received prices/,
    ),
  );
  assert.ok(screen.getByText("$201.25"));
  assert.equal([...polling.timers.values()][0].delay, 30_000);
  await polling.tick();
  assert.equal([...polling.timers.values()][0].delay, 60_000);
  await polling.tick();
  await waitFor(() => assert.ok(screen.getByText("$202.00")));
  assert.equal(screen.queryByRole("status"), null);
  assert.equal([...polling.timers.values()][0].delay, 15_000);
});

test("switching portfolios aborts old requests and ignores late responses", async () => {
  const requests: {
    signal: AbortSignal;
    resolve: (response: Response) => void;
  }[] = [];
  globalThis.fetch = ((_input, init) =>
    new Promise<Response>((resolve) => {
      requests.push({ signal: init!.signal!, resolve });
    })) as typeof fetch;
  const view = render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  assert.match(view.container.textContent!, /Loading/);
  view.rerender(createElement(LiveQuotesPanel, { symbols: ["MSFT"] }));
  assert.equal(requests[0].signal.aborted, true);
  await act(async () => requests[1].resolve(quoteResponse("MSFT", 400)));
  await act(async () => requests[0].resolve(quoteResponse("AAPL", 100)));
  assert.ok(screen.getByText("$400.00"));
  assert.equal(screen.queryByText("AAPL"), null);
  view.unmount();
});

test("unmount cancels an in-flight request without scheduling a retry", async () => {
  const polling = controlPolling();
  let signal!: AbortSignal;
  globalThis.fetch = ((_input, init) =>
    new Promise<Response>((_resolve, reject) => {
      signal = init!.signal!;
      signal.addEventListener("abort", () => reject(signal.reason), {
        once: true,
      });
    })) as typeof fetch;
  const view = render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await act(async () => view.unmount());
  assert.equal(signal.aborted, true);
  assert.equal(polling.timers.size, 0);
});

test("missing configuration hides the optional panel and stops all retries", async () => {
  let calls = 0;
  const polling = controlPolling();
  globalThis.fetch = (async () => {
    calls++;
    return new Response(
      JSON.stringify({
        error: {
          code: "ALPACA_NOT_CONFIGURED",
          message: "Configure ALPACA_API_SECRET",
        },
      }),
      { status: 503 },
    );
  }) as typeof fetch;
  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.ok(screen.queryByRole("region") === null));
  await visibility("hidden");
  await visibility("visible");
  assert.equal(calls, 1);
  assert.equal(polling.timers.size, 0);
  assert.equal(screen.queryByRole("status"), null);
  assert.equal(document.body.textContent!.includes("ALPACA_API_SECRET"), false);
});

test("other 503 responses remain visible and retry instead of disabling quotes", async () => {
  const polling = controlPolling();
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        error: {
          code: "TEMPORARILY_UNAVAILABLE",
          message: "Service restarting",
        },
      }),
      { status: 503 },
    )) as typeof fetch;
  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.ok(screen.getByRole("status")));
  assert.ok(screen.getByRole("region"));
  assert.equal([...polling.timers.values()][0].delay, 30_000);
});

test("missing trades remain unavailable instead of showing a zero price", async () => {
  globalThis.fetch = (async () => quoteResponse("AAPL", null)) as typeof fetch;
  render(createElement(LiveQuotesPanel, { symbols: ["AAPL"] }));
  await waitFor(() => assert.ok(screen.getByText("No IEX trade available")));
  assert.ok(screen.getByText("—"));
  assert.equal(screen.queryByText("$0.00"), null);
});
