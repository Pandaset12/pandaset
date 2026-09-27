import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";
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

const { createElement, StrictMode } = await import("react");
const { cleanup, fireEvent, render, screen, waitFor } =
  await import("@testing-library/react");
const { Application } = await import("../src/App");
const { createRequestGuard, listPortfolios, setApiAccessToken } =
  await import("../src/api/portfolio");
const { forgetPortfolio, hasKnownPortfolio, rememberPortfolio } =
  await import("../src/workspace/portfolioDiscovery");

const originalFetch = globalThis.fetch;
const saved = {
  portfolio_id: "saved",
  name: "Investment",
  created_at: "2026-09-26T00:00:00Z",
  revision: 1,
  holdings: [{ symbol: "SPY", weight: 1 }],
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status });

function show(userId = "owner-a") {
  return render(
    createElement(Application, {
      onSignOut: async () => {},
      userId,
      accountLabel: `${userId}@example.com`,
    }),
  );
}

afterEach(() => {
  cleanup();
  dom.window.localStorage.clear();
  dom.window.location.hash = "";
  globalThis.fetch = originalFetch;
  setApiAccessToken(null);
});

after(() => dom.window.close());

test("first-time empty offers creation and retry", async () => {
  let lists = 0;
  globalThis.fetch = (async () => {
    lists += 1;
    return json([]);
  }) as typeof fetch;
  show();
  await screen.findByText(/No portfolios yet/);
  assert.ok(
    screen.getByRole("button", { name: "Create your first portfolio" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: /Already have a portfolio/ }),
  );
  await waitFor(() => assert.equal(lists, 2));
});

test("previously known portfolio gets account-scoped recovery and retry", async () => {
  rememberPortfolio("owner-a");
  let lists = 0;
  globalThis.fetch = (async (url) => {
    if (String(url) === "/api/v1/portfolios") {
      lists += 1;
      return json(lists === 1 ? [] : [saved]);
    }
    return json({ error: { message: "Metrics unavailable" } }, 502);
  }) as typeof fetch;
  show();
  await screen.findByText("We couldn’t find your saved portfolios.");
  assert.match(document.body.textContent ?? "", /owner-a@example.com/);
  assert.ok(screen.getByRole("button", { name: "Create a new portfolio" }));
  fireEvent.click(screen.getByRole("button", { name: /Try again/ }));
  await screen.findByRole("button", { name: /Select portfolio: Investment/ });
  assert.equal(
    screen.queryByText("We couldn’t find your saved portfolios."),
    null,
  );
});

test("different signed-in account does not inherit another account's marker", async () => {
  rememberPortfolio("owner-a");
  globalThis.fetch = (async () => json([])) as typeof fetch;
  show("owner-b");
  await screen.findByText(/No portfolios yet/);
  assert.equal(hasKnownPortfolio("owner-b"), false);
});

test("malformed and failed list requests show a retryable error", async () => {
  for (const response of [
    json({ portfolios: [] }),
    json(null),
    json([{ name: "broken" }]),
    json({ error: { message: "Unavailable" } }, 503),
  ]) {
    globalThis.fetch = (async () => response.clone()) as typeof fetch;
    show();
    await screen.findByText("Your portfolios couldn’t load.");
    assert.ok(screen.getByRole("button", { name: /Try again/ }));
    assert.equal(screen.queryByText(/No portfolios yet/), null);
    cleanup();
  }
});

test("deleting the last portfolio clears the marker and shows first-time empty", async () => {
  globalThis.fetch = (async (url, init) => {
    if (String(url) === "/api/v1/portfolios") return json([saved]);
    if (String(url).endsWith("/metrics"))
      return json({ error: { message: "Metrics unavailable" } }, 502);
    if (init?.method === "DELETE") return json(null);
    throw new Error(`Unexpected request: ${String(url)}`);
  }) as typeof fetch;
  show();
  await screen.findByRole("button", { name: /Select portfolio: Investment/ });
  assert.equal(hasKnownPortfolio("owner-a"), true);
  fireEvent.click(
    screen.getByRole("button", { name: /Select portfolio: Investment/ }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Delete Investment" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete portfolio" }));
  await screen.findByText(/No portfolios yet/);
  assert.equal(hasKnownPortfolio("owner-a"), false);
});

test("newer request generation wins when list responses arrive out of order", async () => {
  let resolveOld: (value: Response) => void = () => {};
  let lists = 0;
  setApiAccessToken("first-token");
  globalThis.fetch = (async (url) => {
    if (String(url) === "/api/v1/portfolios") {
      lists += 1;
      if (lists === 1) {
        setApiAccessToken("second-token");
        return new Promise<Response>((resolve) => {
          resolveOld = resolve;
        });
      }
      return json([saved]);
    }
    return json({ error: { message: "Metrics unavailable" } }, 502);
  }) as typeof fetch;
  render(
    createElement(
      StrictMode,
      null,
      createElement(Application, {
        onSignOut: async () => {},
        userId: "owner-a",
      }),
    ),
  );
  await screen.findByRole("button", { name: /Select portfolio: Investment/ });
  resolveOld(json([]));
  await waitFor(() => assert.equal(lists, 2));
  assert.equal(screen.queryByText(/No portfolios yet/), null);
  assert.ok(
    screen.getByRole("button", { name: /Select portfolio: Investment/ }),
  );
});

test("creation invalidates any pending discovery result", () => {
  const guard = createRequestGuard();
  const first = guard.begin();
  guard.invalidate();
  assert.equal(guard.isCurrent(first), false);
});

test("invalid list payload never becomes an empty portfolio list", async () => {
  globalThis.fetch = (async () => json({ data: [] })) as typeof fetch;
  await assert.rejects(listPortfolios(), /invalid/);
  forgetPortfolio("owner-a");
});
