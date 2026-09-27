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

const { createElement } = await import("react");
const { cleanup, fireEvent, render } = await import("@testing-library/react");
const { assetLogoUrl } = await import("../src/components/assetLogo");
const { AssetMark } = await import("../src/components/UI");

afterEach(cleanup);
after(() => dom.window.close());

test("logo lookup normalizes tickers and uses only a publishable key", () => {
  const url = new URL(assetLogoUrl(" brk.b ", " pk_test ")!);
  assert.equal(url.origin, "https://img.logo.dev");
  assert.equal(url.pathname, "/ticker/BRK.B");
  assert.equal(url.searchParams.get("token"), "pk_test");
  assert.equal(url.searchParams.get("fallback"), "404");
  assert.equal(assetLogoUrl("AAPL", ""), null);
  assert.equal(assetLogoUrl("AAPL", "sk_private"), null);
  assert.equal(assetLogoUrl("AAPL/../../x", "pk_test"), null);
  assert.equal(assetLogoUrl("^GSPC", "pk_test"), null);
});

test("asset mark keeps its ticker fallback until the logo loads", () => {
  const { container } = render(
    createElement(AssetMark, { asset: { symbol: "NVDA" }, logoKey: "pk_test" }),
  );
  assert.equal(
    container.querySelector(".asset-mark-fallback")?.textContent,
    "N",
  );
  const image = container.querySelector(".asset-mark img")!;
  assert.match(image.getAttribute("src") ?? "", /\/ticker\/NVDA\?/);
  assert.equal(image.classList.contains("loaded"), false);

  fireEvent.load(image);
  assert.equal(container.querySelector(".asset-mark-fallback"), null);
  assert.equal(container.querySelector(".asset-mark img.loaded"), image);
});

test("missing logos fall back and a new ticker gets a fresh image request", () => {
  const view = render(
    createElement(AssetMark, { asset: { symbol: "NVDA" }, logoKey: "pk_test" }),
  );
  fireEvent.error(view.container.querySelector(".asset-mark img")!);
  assert.equal(view.container.querySelector(".asset-mark img"), null);
  assert.equal(
    view.container.querySelector(".asset-mark-fallback")?.textContent,
    "N",
  );

  view.rerender(
    createElement(AssetMark, { asset: { symbol: "VTI" }, logoKey: "pk_test" }),
  );
  assert.match(
    view.container.querySelector(".asset-mark img")?.getAttribute("src") ?? "",
    /\/ticker\/VTI\?/,
  );
  assert.equal(
    view.container.querySelector(".asset-mark-fallback")?.textContent,
    "V",
  );
});

test("no provider key renders only the local mark", () => {
  const { container } = render(
    createElement(AssetMark, { asset: { symbol: "MSFT" }, logoKey: "" }),
  );
  assert.equal(container.querySelector("img"), null);
  assert.ok(container.querySelector(".ms-grid"));
});
