import assert from "node:assert/strict";
import { after, test } from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/app.html#/",
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
});

const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen, waitFor } =
  await import("@testing-library/react");
const { WorkspaceNavigation } =
  await import("../src/components/WorkspaceNavigation");

after(() => dom.window.close());

test("responsive navigation opens, closes, and keeps the current route", async () => {
  const view = render(
    createElement(WorkspaceNavigation, {
      route: "/",
      onSignOut: async () => {},
    }),
  );

  const toggle = screen.getByRole("button", { name: "Open navigation" });
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  fireEvent.click(toggle);
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(
    screen.getByRole("link", { name: "Overview" }).getAttribute("aria-current"),
    "page",
  );

  fireEvent.keyDown(document, { key: "Escape" });
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.equal(document.activeElement, toggle);

  fireEvent.click(toggle);
  view.rerender(
    createElement(WorkspaceNavigation, {
      route: "/risk",
      onSignOut: async () => {},
    }),
  );
  await waitFor(() =>
    assert.equal(toggle.getAttribute("aria-expanded"), "false"),
  );
  assert.equal(
    screen
      .getByRole("link", { name: "Risk & exposure" })
      .getAttribute("aria-current"),
    "page",
  );
  cleanup();
});

test("sign out remains available in the collapsible navigation", async () => {
  let signedOut = false;
  render(
    createElement(WorkspaceNavigation, {
      route: "/",
      onSignOut: async () => {
        signedOut = true;
      },
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => assert.equal(signedOut, true));
  cleanup();
});
