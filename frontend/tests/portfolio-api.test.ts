import assert from "node:assert/strict";
import { after, test } from "node:test";
import { assets, initialWeights } from "../../quant/data";
import {
  ApiError,
  analyzePortfolio,
  askPortfolio,
  comparePortfolio,
  createRequestGuard,
  getMarketHistory,
  getLiveQuotes,
  portfolioInput,
  listPortfolios,
  setApiAccessToken,
  verifyPortfolioHistory,
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

test("unsupported edited tickers fail sample-history verification before save", async () => {
  stubFetch((url) => {
    assert.match(url, /symbols=TSLA/);
    return {
      ok: false,
      status: 502,
      json: async () => ({ error: { message: "Unavailable" } }),
    } as Response;
  });
  await assert.rejects(
    verifyPortfolioHistory([{ symbol: "TSLA", weight: 1 }]),
    /TSLA/,
  );
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

test("analysis creation sends weights and rejects a mismatched backend allocation", async () => {
  const portfolio = {
    portfolio_id: "portfolio_test",
    name: "Long-term portfolio",
    created_at: "now",
    holdings: portfolioInput(initialWeights).holdings,
  };
  let call = 0;
  stubFetch(() => {
    call += 1;
    return call === 1
      ? portfolio
      : { portfolio_id: portfolio.portfolio_id, weights: { NVDA: 0.3 } };
  });
  await assert.rejects(
    analyzePortfolio(initialWeights),
    /different portfolio allocation/,
  );
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

test("what-if uses decimal weights and Ask Panda sends the active analysis ID", async () => {
  const calls: { url: string; body: unknown }[] = [];
  stubFetch((url, init) => {
    calls.push({
      url,
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    return url.includes("what-if")
      ? {
          current_analysis: {},
          proposed_analysis: {},
          delta: {},
          difference_convention: "proposed minus baseline",
        }
      : {
          status: "demo",
          answer: "Demo",
          citations: [],
          warnings: [],
          disclaimer: "Educational only",
          analysis_id: "analysis_saved",
          error_code: null,
          analyst_mode: "demo",
        };
  });
  await comparePortfolio("portfolio_saved", [0, 0, 0, 0, 0, 100, 0, 0]);
  await askPortfolio("portfolio_saved", "analysis_saved", "Explain risk");
  assert.deepEqual((calls[0].body as { holdings: unknown }).holdings, [
    { symbol: "TLT", weight: 1 },
  ]);
  assert.equal(calls[1].url, "/api/v1/portfolios/portfolio_saved/ask");
  assert.deepEqual(calls[1].body, {
    analysis_id: "analysis_saved",
    question: "Explain risk",
  });
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
