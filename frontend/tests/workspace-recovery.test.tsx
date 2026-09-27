import assert from "node:assert/strict";
import { after, test } from "node:test";
import { JSDOM } from "jsdom";

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
dom.window.scrollTo = () => {};
dom.window.HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
dom.window.HTMLDialogElement.prototype.close = function () {
  this.open = false;
};

const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen, waitFor } =
  await import("@testing-library/react");
const { Application } = await import("../src/App");
const { EditPortfolio } = await import("../src/components/EditPortfolio");
const { PortfolioOnboarding } =
  await import("../src/components/onboarding/PortfolioOnboarding");
const { TickerSearch } =
  await import("../src/components/onboarding/TickerSearch");
const { default: WhatIf } = await import("../src/pages/WhatIf");
const { workspaceAssets, portfolioPercentages } =
  await import("../src/workspace/holdings");
const originalFetch = globalThis.fetch;

after(() => {
  globalThis.fetch = originalFetch;
  cleanup();
  dom.window.close();
});

test("a saved ticker rejected by sample prices offers retry, switching, and replacement", async () => {
  const saved = {
    portfolio_id: "failed",
    name: "TSLA portfolio",
    created_at: "2026-09-26T00:00:00Z",
    holdings: [{ symbol: "TSLA", weight: 1 }],
  };
  const other = {
    portfolio_id: "other",
    name: "Other portfolio",
    created_at: saved.created_at,
    holdings: [{ symbol: "SPY", weight: 1 }],
  };
  globalThis.fetch = (async (url: RequestInfo | URL) => {
    if (String(url) === "/api/v1/portfolios")
      return { ok: true, json: async () => [saved, other] } as Response;
    return {
      ok: false,
      status: 502,
      json: async () => ({
        error: { message: "Sample price data is unavailable." },
      }),
    } as Response;
  }) as typeof fetch;
  render(createElement(Application, { onSignOut: async () => {} }));
  await screen.findByText("We couldn’t load the portfolio analysis.");
  assert.ok(screen.getByRole("button", { name: "Retry analysis" }));
  fireEvent.click(screen.getByRole("button", { name: /TSLA portfolio/ }));
  assert.ok(screen.getByRole("button", { name: "Other portfolio" }));
  fireEvent.click(screen.getByRole("button", { name: "Other portfolio" }));
  await screen.findByText("We couldn’t load the portfolio analysis.");
  assert.ok(screen.getByRole("button", { name: /Other portfolio/ }));
  fireEvent.click(
    screen.getByRole("button", { name: "Create another portfolio" }),
  );
  await waitFor(() =>
    assert.ok(screen.getByRole("button", { name: /Create another portfolio/ })),
  );
  assert.ok(screen.getByRole("button", { name: "Back to saved portfolios" }));
  cleanup();
});

test("SPY and fractional saved allocations remain usable in edit and What-if", () => {
  const saved = {
    portfolio_id: "fractional",
    name: "Fractional",
    created_at: "2026-09-26T00:00:00Z",
    holdings: [
      { symbol: "SPY", weight: 0.255 },
      { symbol: "TLT", weight: 0.745 },
    ],
  };
  const holdings = workspaceAssets(saved);
  const weights = portfolioPercentages(saved);
  render(
    createElement(EditPortfolio, {
      holdings,
      weights,
      busy: false,
      error: "",
      searchTickers: async () => [],
      onClose: () => {},
      onSave: async () => true,
    }),
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "SPY portfolio allocation",
      }) as HTMLInputElement
    ).value,
    "25.5",
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "TLT portfolio allocation",
      }) as HTMLInputElement
    ).value,
    "74.5",
  );
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save changes",
      }) as HTMLButtonElement
    ).disabled,
    false,
  );
  cleanup();
  render(
    createElement(WhatIf, {
      holdings,
      weights,
      analysis: {
        portfolio_id: saved.portfolio_id,
        risk_contribution: { SPY: 0.5, TLT: 0.5 },
        portfolio_volatility: 0.1,
        lookback_days: 6,
      } as never,
      onApply: async () => true,
      onExplainScenario: () => {},
      query: new URLSearchParams(),
    }),
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "SPY proposed allocation",
      }) as HTMLInputElement
    ).value,
    "25.5",
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "TLT proposed allocation",
      }) as HTMLInputElement
    ).value,
    "74.5",
  );
  assert.ok(screen.getByText("100%"));
  const proposedSpy = screen.getByRole("textbox", {
    name: "SPY proposed allocation",
  }) as HTMLInputElement;
  const proposedTlt = screen.getByRole("textbox", {
    name: "TLT proposed allocation",
  }) as HTMLInputElement;
  fireEvent.change(screen.getByRole("combobox", { name: "From" }), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "To" }), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Move 5 points" }));
  assert.equal(proposedSpy.value, "30.5");
  assert.equal(proposedTlt.value, "69.5");
  fireEvent.change(proposedSpy, { target: { value: "" } });
  assert.equal(proposedSpy.value, "");
  fireEvent.change(proposedSpy, { target: { value: "0" } });
  assert.equal(proposedSpy.value, "0");
  fireEvent.change(proposedSpy, { target: { value: "40" } });
  fireEvent.change(proposedTlt, { target: { value: "60" } });
  assert.equal(proposedSpy.value, "40");
  assert.equal(proposedTlt.value, "60");
  assert.ok(screen.getByText("100%"));
  cleanup();
});

test("a single-holding SPY scenario can add a second ticker", () => {
  const saved = {
    portfolio_id: "spy",
    name: "SPY",
    created_at: "2026-09-26T00:00:00Z",
    holdings: [{ symbol: "SPY", weight: 1 }],
  };
  render(
    createElement(WhatIf, {
      holdings: workspaceAssets(saved),
      weights: portfolioPercentages(saved),
      analysis: {
        portfolio_id: saved.portfolio_id,
        risk_contribution: { SPY: 1 },
        portfolio_volatility: 0.1,
        lookback_days: 6,
      } as never,
      onApply: async () => true,
      onExplainScenario: () => {},
      query: new URLSearchParams(),
    }),
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "SPY proposed allocation",
      }) as HTMLInputElement
    ).value,
    "100",
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Ticker to add" }), {
    target: { value: "TLT" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Add holding" }));
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "TLT proposed allocation",
      }) as HTMLInputElement
    ).value,
    "0",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Less single-stock risk" }),
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "SPY proposed allocation",
      }) as HTMLInputElement
    ).value,
    "90",
  );
  assert.equal(
    (
      screen.getByRole("textbox", {
        name: "TLT proposed allocation",
      }) as HTMLInputElement
    ).value,
    "10",
  );
  cleanup();
});

test("What-if editor groups holdings, allocations, and add controls", () => {
  const saved = {
    portfolio_id: "layout",
    name: "Layout",
    created_at: "2026-09-26T00:00:00Z",
    holdings: [
      { symbol: "SPY", weight: 0.255 },
      { symbol: "TLT", weight: 0.745 },
    ],
  };
  const { container } = render(
    createElement(WhatIf, {
      holdings: workspaceAssets(saved),
      weights: portfolioPercentages(saved),
      analysis: {
        portfolio_id: saved.portfolio_id,
        risk_contribution: { SPY: 0.5, TLT: 0.5 },
        portfolio_volatility: 0.1,
        lookback_days: 6,
      } as never,
      onApply: async () => true,
      onExplainScenario: () => {},
      query: new URLSearchParams(),
    }),
  );
  assert.deepEqual(
    [...container.querySelectorAll(".editor-table-head span")].map((node) =>
      node.textContent?.trim(),
    ),
    ["Holding", "Current", "Proposed"],
  );
  const rows = [
    ...container.querySelectorAll(".allocation-editor .editor-row"),
  ];
  assert.equal(rows.length, 2);
  assert.equal(
    rows[0].querySelector(".editor-asset strong")?.textContent,
    "SPY",
  );
  assert.equal(rows[0].querySelector(".current-weight")?.textContent, "25.5%");
  assert.equal(
    (rows[0].querySelector(".weight-input input") as HTMLInputElement).value,
    "25.5",
  );
  assert.equal(
    container.querySelector(".scenario-add-holding label")?.textContent?.trim(),
    "Add a ticker to this scenario",
  );
  assert.ok(container.querySelector(".scenario-add-holding .button"));
  assert.equal(
    container.querySelector(".allocation-total strong")?.textContent,
    "100%",
  );
  cleanup();
});

test("What-if limits the saved and proposed symbol union to eight", () => {
  const symbols = ["SPY", "TLT", "AAPL", "JPM", "NVDA", "VTI", "GLD", "MSFT"];
  const saved = {
    portfolio_id: "eight",
    name: "Eight",
    created_at: "2026-09-26T00:00:00Z",
    holdings: symbols.map((symbol) => ({ symbol, weight: 0.125 })),
  };
  render(
    createElement(WhatIf, {
      holdings: workspaceAssets(saved),
      weights: portfolioPercentages(saved),
      analysis: {
        portfolio_id: saved.portfolio_id,
        risk_contribution: {},
        portfolio_volatility: 0.1,
      } as never,
      onApply: async () => true,
      onExplainScenario: () => {},
      query: new URLSearchParams(),
    }),
  );
  const add = screen.getByRole("button", {
    name: "Add holding",
  }) as HTMLButtonElement;
  assert.equal(add.disabled, true);
  assert.match(
    screen.getByRole("status").textContent ?? "",
    /eight distinct symbols across the saved portfolio and proposed allocation/,
  );
  fireEvent.change(
    screen.getByRole("textbox", { name: "SPY proposed allocation" }),
    { target: { value: "0" } },
  );
  assert.equal(add.disabled, true);
  fireEvent.change(screen.getByRole("textbox", { name: "Ticker to add" }), {
    target: { value: "TSLA" },
  });
  fireEvent.submit(add.closest("form")!);
  assert.equal(
    screen.queryByRole("textbox", { name: "TSLA proposed allocation" }),
    null,
  );
  cleanup();
});

test("Edit adds unique holdings, keeps intermediate percentage text, validates 100%, and removes holdings", async () => {
  const saved = {
    portfolio_id: "spy",
    name: "SPY",
    created_at: "2026-09-26T00:00:00Z",
    holdings: [{ symbol: "SPY", weight: 1 }],
  };
  let submitted: { weights: number[]; symbols: string[] } | null = null;
  render(
    createElement(EditPortfolio, {
      holdings: workspaceAssets(saved),
      weights: [100],
      busy: false,
      error: "",
      searchTickers: async () => [],
      onClose: () => {},
      onSave: async (weights, symbols) => {
        submitted = { weights, symbols };
        return true;
      },
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "+ Add holding" }));
  fireEvent.change(screen.getByRole("combobox", { name: "Add a holding" }), {
    target: { value: "AAPL" },
  });
  fireEvent.click(
    await screen.findByRole("option", { name: /AAPL.*Add exact ticker/ }),
  );
  const spy = screen.getByRole("textbox", {
    name: "SPY portfolio allocation",
  }) as HTMLInputElement;
  const aapl = screen.getByRole("textbox", {
    name: "AAPL portfolio allocation",
  }) as HTMLInputElement;
  fireEvent.change(spy, { target: { value: "" } });
  assert.equal(spy.value, "");
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save changes",
      }) as HTMLButtonElement
    ).disabled,
    true,
  );
  fireEvent.change(spy, { target: { value: "100" } });
  fireEvent.change(aapl, { target: { value: "0" } });
  assert.equal(aapl.value, "0");
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save changes",
      }) as HTMLButtonElement
    ).disabled,
    true,
  );
  fireEvent.change(spy, { target: { value: "74.5" } });
  fireEvent.change(aapl, { target: { value: "25.5" } });
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save changes",
      }) as HTMLButtonElement
    ).disabled,
    false,
  );
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  assert.deepEqual(submitted, {
    weights: [74.5, 25.5],
    symbols: ["SPY", "AAPL"],
  });
  await waitFor(() =>
    assert.equal(
      (
        screen.getByRole("button", {
          name: "+ Add holding",
        }) as HTMLButtonElement
      ).disabled,
      false,
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "+ Add holding" }));
  fireEvent.change(screen.getByRole("combobox", { name: "Add a holding" }), {
    target: { value: "AAPL" },
  });
  await screen.findByText(/No matching stock found/);
  assert.equal(screen.queryByRole("option", { name: /AAPL/ }), null);
  assert.equal(
    screen.getAllByRole("textbox", { name: "AAPL portfolio allocation" })
      .length,
    1,
  );
  fireEvent.click(screen.getByRole("button", { name: "Remove AAPL" }));
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save changes",
      }) as HTMLButtonElement
    ).disabled,
    true,
  );
  fireEvent.change(spy, { target: { value: "100" } });
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Save changes",
      }) as HTMLButtonElement
    ).disabled,
    false,
  );
  cleanup();
});

test("onboarding percentage input keeps empty, zero, replacement, and fractional text", async () => {
  render(
    createElement(PortfolioOnboarding, {
      searchTickers: async () => [],
      createPortfolio: async () => {
        throw new Error("Not submitted");
      },
      onOpenPortfolio: () => {},
    }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: /Create your first portfolio/ }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Portfolio name" }), {
    target: { value: "Fractional" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.change(screen.getByRole("combobox", { name: "Add a holding" }), {
    target: { value: "SPY" },
  });
  fireEvent.click(
    await screen.findByRole("option", { name: /SPY.*Add exact ticker/ }),
  );
  const spy = screen.getByRole("textbox", {
    name: "SPY weight (%)",
  }) as HTMLInputElement;
  fireEvent.change(spy, { target: { value: "50" } });
  fireEvent.change(spy, { target: { value: "" } });
  assert.equal(spy.value, "");
  fireEvent.change(spy, { target: { value: "0" } });
  assert.equal(spy.value, "0");
  fireEvent.change(spy, { target: { value: "25.5" } });
  assert.equal(spy.value, "25.5");
  fireEvent.change(screen.getByRole("combobox", { name: "Add a holding" }), {
    target: { value: "TLT" },
  });
  fireEvent.click(
    await screen.findByRole("option", { name: /TLT.*Add exact ticker/ }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "TLT weight (%)" }), {
    target: { value: "74.5" },
  });
  assert.equal(
    (
      screen.getByRole("button", {
        name: "Review portfolio",
      }) as HTMLButtonElement
    ).disabled,
    false,
  );
  cleanup();
});

test("company search selects the returned symbol without offering the company name as a ticker", async () => {
  const selected: string[] = [];
  render(
    createElement(TickerSearch, {
      inputId: "company-search",
      selectedSymbols: [],
      searchTickers: async () => [{ symbol: "AAPL", name: "Apple Inc." }],
      onSelect: (ticker) => selected.push(ticker.symbol),
    }),
  );
  fireEvent.change(screen.getByRole("combobox", { name: "Add a holding" }), {
    target: { value: "APPLE" },
  });
  const match = await screen.findByRole("option", { name: /AAPL.*Apple Inc/ });
  assert.equal(
    screen.queryByRole("option", { name: /APPLE.*Add exact ticker/ }),
    null,
  );
  fireEvent.click(match);
  assert.deepEqual(selected, ["AAPL"]);
  cleanup();
});

test("repeated workspace edits PUT one selected portfolio and refresh its analysis", async () => {
  let saved = {
    portfolio_id: "saved",
    name: "Portfolio",
    created_at: "2026-09-26T00:00:00Z",
    holdings: [{ symbol: "SPY", weight: 1 }],
  };
  let updates = 0;
  let creates = 0;
  let analyses = 0;
  const response = (payload: unknown) =>
    ({ ok: true, status: 200, json: async () => payload }) as Response;
  globalThis.fetch = (async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url);
    if (path === "/api/v1/portfolios" && !init?.method)
      return response([saved]);
    if (path === "/api/v1/portfolios" && init?.method === "POST") {
      creates += 1;
      throw new Error("Edit must not create");
    }
    if (path.startsWith("/api/v1/market-history"))
      return response({ symbols: [], dates: [] });
    if (path === "/api/v1/portfolios/saved" && init?.method === "PUT") {
      updates += 1;
      saved = { ...saved, ...JSON.parse(String(init.body)) };
      return response(saved);
    }
    if (
      path === "/api/v1/portfolios/saved/analysis" &&
      init?.method === "POST"
    ) {
      analyses += 1;
      const weights = Object.fromEntries(
        saved.holdings.map(({ symbol, weight }) => [symbol, weight]),
      );
      return response({
        analysis_id: `analysis_${analyses}`,
        portfolio_id: saved.portfolio_id,
        weights,
        risk_contribution: Object.fromEntries(
          saved.holdings.map(({ symbol, weight }) => [symbol, weight]),
        ),
        return_contribution: null,
        series: null,
        data_mode: "demo",
        data_quality: { source: "sample", freshness: "unknown", warnings: [] },
        portfolio_return: 0,
        annualized_return: 0,
        max_drawdown: 0,
        portfolio_volatility: 0.1,
        observation_count: 6,
        lookback_days: 6,
        as_of: null,
        concentration: {
          largest_position: saved.holdings[0].symbol,
          largest_weight: saved.holdings[0].weight,
        },
      });
    }
    throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${path}`);
  }) as typeof fetch;
  render(createElement(Application, { onSignOut: async () => {} }));
  await screen.findByText("analysis_1");
  assert.equal(screen.queryByRole("button", { name: "Ask Panda" }), null);
  assert.equal(screen.queryByRole("link", { name: "Explore a what-if" }), null);
  assert.equal(document.querySelector(".demo-badge"), null);
  assert.equal(document.querySelector(".as-of"), null);
  for (const [index, [first, second]] of [
    ["75", "25"],
    ["50", "50"],
  ].entries()) {
    fireEvent.click(screen.getByRole("button", { name: "Edit portfolio" }));
    if (updates === 0) {
      fireEvent.click(screen.getByRole("button", { name: "+ Add holding" }));
      fireEvent.change(
        screen.getByRole("combobox", { name: "Add a holding" }),
        { target: { value: "AAPL" } },
      );
      fireEvent.click(await screen.findByRole("option", { name: /AAPL/ }));
    }
    fireEvent.change(
      screen.getByRole("textbox", { name: "SPY portfolio allocation" }),
      { target: { value: first } },
    );
    fireEvent.change(
      screen.getByRole("textbox", { name: "AAPL portfolio allocation" }),
      { target: { value: second } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByText(`analysis_${index + 2}`);
  }
  assert.equal(updates, 2);
  assert.equal(creates, 0);
  assert.equal(analyses, 3);
  assert.equal(saved.portfolio_id, "saved");
  assert.equal(saved.holdings.length, 2);
  fireEvent.click(screen.getByRole("button", { name: /Portfolio/ }));
  assert.equal(screen.getAllByRole("button", { name: "Portfolio" }).length, 1);
  cleanup();
});
