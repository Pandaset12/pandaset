import assert from "node:assert/strict";
import { test } from "node:test";
import { landingRedirect } from "../src/lib/landingRedirect";

test("dashboard bookmarks preserve routes and search parameters", () => {
  for (const hash of ["#/", "#/risk", "#/research?symbol=NVDA", "#/what-if"]) {
    assert.equal(
      landingRedirect(`https://example.com/?source=bookmark${hash}`),
      `https://example.com/app.html?source=bookmark${hash}`,
    );
  }
});

test("auth callbacks reach the same-origin dashboard without losing credentials", () => {
  for (const callback of [
    "#access_token=example&refresh_token=example&type=signup",
    "#error=access_denied&error_description=Link+expired",
    "?code=example",
  ]) {
    assert.equal(
      landingRedirect(`https://example.com/${callback}`),
      `https://example.com/app.html${callback}`,
    );
  }
});

test("landing visits and section anchors stay on the landing page", () => {
  for (const suffix of ["", "#perspective", "#toolkit", "?source=campaign"]) {
    assert.equal(landingRedirect(`https://example.com/${suffix}`), null);
  }
});
