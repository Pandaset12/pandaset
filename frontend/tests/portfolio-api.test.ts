import assert from "node:assert/strict";
import { after, test } from "node:test";
import { assets, initialWeights } from "../../quant/data";
import {
  ApiError,
  analyzeExistingPortfolio,
  comparePortfolio,
  createRequestGuard,
  getMarketHistory,
  getLiveQuotes,
  portfolioInput,
  listPortfolios,
  searchAssets,
  setApiAccessToken,
  verifyPortfolioHistory,
  verifyPortfolioSymbol,
  updatePortfolio,
} from "../src/api/portfolio";

const originalFetch = globalThis.fetch;
after(() => {
  globalThis.fetch = originalFetch;
  setApiAccessToken(null);
});

test("portfolio requests use the current access token", async () => {
  const seen: string[] = [];
  stubFetch((_url, init) => {
    seen.push(new Headers(init?.headers).get("Authorization") ?? "");
    return [];
  });
  setApiAccessToken("first-token");
  await listPortfolios();
  setApiAccessToken("refreshed-token");
  await listPortfolios();
  setApiAccessToken(null);
  assert.deepEqual(seen, ["Bearer first-token", "Bearer refreshed-token"]);
});

test("What-if accepts persisted symbols and fractional allocations outside the sample UI list", async () => {
  let payload: unknown;
  stubFetch((_url, init) => {
    payload = JSON.parse(String(init?.body));
    return {};
  });
  await comparePortfolio("saved", [25.5, 74.5], ["SPY", "TLT"]);
  assert.deepEqual(payload, {
    holdings: [
      { symbol: "SPY", weight: 0.255 },
      { symbol: "TLT", weight: 0.745 },
    ],
  });
});

test("history preflight reports the selected provider's safe error for a user ticker", async () => {
  stubFetch((url) => {
    assert.match(url, /symbols=TSLA/);
    return {
      ok: false,
      status: 502,
      json: async () => ({
        error: { message: "Alpaca history rate limit was reached." },
      }),
    } as Response;
  });
  await assert.rejects(
    verifyPortfolioHistory([{ symbol: "TSLA", weight: 1 }]),
    /TSLA\. Alpaca history rate limit was reached/,
  );
});

test("company lookup uses the authenticated backend and failed history suggests a real symbol", async () => {
  const calls: string[] = [];
  stubFetch((url, init) => {
    calls.push(url);
    if (url.startsWith("/api/v1/assets/search")) {
      assert.equal(
        new Headers(init?.headers).get("Authorization"),
        "Bearer owner-token",
      );
      return { results: [{ symbol: "AAPL", name: "Apple Inc." }] };
    }
    assert.match(url, /symbols=APPLE/);
    return {
      ok: false,
      status: 404,
      json: async () => ({
        error: {
          code: "MARKET_HISTORY_UNAVAILABLE",
          message:
            "Market history is unavailable for one or more requested symbols.",
        },
      }),
    } as Response;
  });
  setApiAccessToken("owner-token");
  assert.deepEqual((await searchAssets("Apple")).results[0].symbol, "AAPL");
  await assert.rejects(
    verifyPortfolioHistory([{ symbol: "APPLE", weight: 1 }]),
    /select AAPL \(Apple Inc\.\)/,
  );
  setApiAccessToken(null);
  assert.deepEqual(calls, [
    "/api/v1/assets/search?q=Apple",
    "/api/v1/market-history?lookback_days=2&symbols=APPLE",
    "/api/v1/assets/search?q=APPLE",
  ]);
});

test("missing tickers and rate limits have distinct verification errors", async () => {
  stubFetch(
    () =>
      ({
        ok: false,
        status: 404,
        json: async () => ({ error: { message: "Missing" } }),
      }) as Response,
  );
  await assert.rejects(
    verifyPortfolioSymbol("SPACE"),
    /couldn't find that ticker \(SPACE\)/,
  );
  stubFetch(
    () =>
      ({
        ok: false,
        status: 429,
        json: async () => ({ error: { message: "Rate limited" } }),
      }) as Response,
  );
  await assert.rejects(verifyPortfolioSymbol("SPY"), /rate limited/);
});

test("Edit sends an authenticated PUT for the existing portfolio ID", async () => {
  const calls: {
    url: string;
    method: string;
    body: unknown;
    token: string | null;
  }[] = [];
  stubFetch((url, init) => {
    calls.push({
      url,
      method: init?.method ?? "GET",
      body: JSON.parse(String(init?.body)),
      token: new Headers(init?.headers).get("Authorization"),
    });
    return {
      portfolio_id: "saved",
      name: "Updated",
      holdings: [{ symbol: "SPY", weight: 1 }],
      created_at: "2026-09-26T00:00:00Z",
    };
  });
  setApiAccessToken("owner-token");
  const updated = await updatePortfolio("saved", {
    name: "Updated",
    holdings: [{ symbol: "SPY", weight: 1 }],
  });
  setApiAccessToken(null);
  assert.equal(updated.portfolio_id, "saved");
  assert.deepEqual(calls, [
    {
      url: "/api/v1/portfolios/saved",
      method: "PUT",
      body: { name: "Updated", holdings: [{ symbol: "SPY", weight: 1 }] },
      token: "Bearer owner-token",
    },
  ]);
});

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const payload = handler(String(input), init);
    if (payload && typeof payload === "object" && "json" in payload)
      return payload as Response;
    return { ok: true, status: 200, json: async () => payload } as Response;
  }) as typeof fetch;
}

test("portfolio payload converts percentages to decimal holdings and omits zero weights", () => {
  const payload = portfolioInput(initialWeights);
  assert.equal(payload.name, "Long-term portfolio");
  assert.deepEqual(
    payload.holdings,
    assets.slice(0, 6).map((asset, index) => ({
      symbol: asset.symbol,
      weight: initialWeights[index] / 100,
    })),
  );
  assert.throws(() => portfolioInput([20, 20]), /total 100%/);
});

test("current metrics request uses the saved portfolio ID", async () => {
  const portfolio = {
    portfolio_id: "portfolio_test",
    name: "Long-term portfolio",
    created_at: "now",
    revision: 2,
    holdings: portfolioInput(initialWeights).holdings,
  };
  let path = "";
  stubFetch((url) => {
    path = url;
    return { portfolio_id: portfolio.portfolio_id, portfolio_revision: 2 };
  });
  const result = await analyzeExistingPortfolio(portfolio);
  assert.equal(path, "/api/v1/portfolios/portfolio_test/metrics");
  assert.equal(result.portfolio, portfolio);
  assert.equal(result.analysis.portfolio_revision, 2);
});

test("market history keeps repeated symbol query parameters", async () => {
  let requested = "";
  stubFetch((url) => {
    requested = url;
    return { symbols: ["NVDA", "VTI"] };
  });
  await getMarketHistory(["NVDA", "VTI"], 63);
  const query = new URL(requested, "http://localhost").searchParams;
  assert.deepEqual(query.getAll("symbols"), ["NVDA", "VTI"]);
  assert.equal(query.get("lookback_days"), "63");
});

test("live quote requests keep repeated symbols and request only the backend", async () => {
  let requested = "";
  let authorization = "";
  stubFetch((url, init) => {
    requested = url;
    authorization = new Headers(init?.headers).get("Authorization") ?? "";
    return { feed: "IEX", source: "alpaca", quotes: [] };
  });
  setApiAccessToken("test-user-token");
  await getLiveQuotes(["AAPL", "MSFT"]);
  setApiAccessToken(null);
  const parsed = new URL(requested, "http://localhost");
  assert.equal(parsed.pathname, "/api/v1/quotes");
  assert.deepEqual(parsed.searchParams.getAll("symbols"), ["AAPL", "MSFT"]);
  assert.equal(authorization, "Bearer test-user-token");
});

test("identical requests in flight share one backend call", async () => {
  let calls = 0;
  let finish!: (response: Response) => void;
  globalThis.fetch = (() => {
    calls += 1;
    return new Promise<Response>((resolve) => {
      finish = resolve;
    });
  }) as typeof fetch;
  const first = getMarketHistory(["NVDA"]);
  const second = getMarketHistory(["NVDA"]);
  assert.equal(calls, 1);
  finish(new Response(JSON.stringify({ symbols: ["NVDA"] })));
  await Promise.all([first, second]);
});

test("stalled quotes time out and release the request for a later retry", async (context) => {
  context.mock.timers.enable({ apis: ["setTimeout"] });
  let signal!: AbortSignal;
  globalThis.fetch = ((_input, init) =>
    new Promise<Response>((_resolve, reject) => {
      signal = init!.signal!;
      signal.addEventListener("abort", () => reject(signal.reason), {
        once: true,
      });
    })) as typeof fetch;
  const pending = getLiveQuotes(["AAPL"]);
  const rejected = assert.rejects(
    pending,
    (error: unknown) => error instanceof ApiError && error.status === 408,
  );
  context.mock.timers.tick(20_000);
  await rejected;
  assert.equal(signal.aborted, true);
  stubFetch(() => ({ feed: "IEX", source: "alpaca", quotes: [] }));
  assert.equal((await getLiveQuotes(["AAPL"])).feed, "IEX");
});

test("cancelling one quote consumer does not cancel another", async () => {
  const requests: {
    signal: AbortSignal;
    resolve: (response: Response) => void;
  }[] = [];
  globalThis.fetch = ((_input, init) =>
    new Promise<Response>((resolve, reject) => {
      const signal = init!.signal!;
      signal.addEventListener("abort", () => reject(signal.reason), {
        once: true,
      });
      requests.push({ signal, resolve });
    })) as typeof fetch;
  const controller = new AbortController();
  const first = getLiveQuotes(["AAPL"], controller.signal);
  const second = getLiveQuotes(["AAPL"]);
  const rejected = assert.rejects(first, { name: "AbortError" });
  controller.abort();
  await rejected;
  assert.equal(requests[1].signal.aborted, false);
  requests[1].resolve(
    new Response(JSON.stringify({ feed: "IEX", source: "alpaca", quotes: [] })),
  );
  assert.equal((await second).feed, "IEX");
});

test("what-if sends decimal weights", async () => {
  const calls: { url: string; body: unknown }[] = [];
  stubFetch((url, init) => {
    calls.push({
      url,
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    assert.match(url, /what-if$/);
    return {
      current_analysis: {},
      proposed_analysis: {},
      delta: {},
      difference_convention: "proposed minus baseline",
    };
  });
  await comparePortfolio("portfolio_saved", [0, 0, 0, 0, 0, 100, 0, 0]);
  assert.equal(calls.length, 1);
  assert.deepEqual((calls[0].body as { holdings: unknown }).holdings, [
    { symbol: "TLT", weight: 1 },
  ]);
});

test("API errors expose only the safe message and request ID", async () => {
  stubFetch(() => ({
    ok: false,
    status: 503,
    json: async () => ({
      error: {
        message: "Local storage unavailable.",
        request_id: "req-123",
        secret: "hidden",
      },
    }),
  }));
  await assert.rejects(getMarketHistory(["NVDA"]), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 503);
    assert.equal(error.requestId, "req-123");
    assert.equal(error.message, "Local storage unavailable.");
    assert.equal(error.message.includes("hidden"), false);
    return true;
  });
});

test("request guard prevents an older response from replacing the latest request", () => {
  const guard = createRequestGuard();
  const oldRequest = guard.begin();
  const latestRequest = guard.begin();
  assert.equal(guard.isCurrent(oldRequest), false);
  assert.equal(guard.isCurrent(latestRequest), true);
  guard.invalidate();
  assert.equal(guard.isCurrent(latestRequest), false);
});
