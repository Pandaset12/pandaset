import { chromium } from "playwright-core";
import assert from "node:assert/strict";
import fs from "node:fs";
const url = process.env.LANDING_URL || "http://127.0.0.1:45273";
const out = new URL("./lab/functional/", import.meta.url);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const report = [];
for (const [name, width, height, reducedMotion] of [
  ["desktop", 1440, 900, "no-preference"],
  ["mobile", 390, 844, "no-preference"],
  ["compact", 360, 640, "no-preference"],
  ["reduced", 1440, 900, "reduce"],
]) {
  const context = await browser.newContext({
    viewport: { width, height },
    reducedMotion,
  });
  await context.addInitScript(() => {
    Element.prototype.requestPointerLock = () =>
      Promise.reject(new Error("Disabled"));
    Element.prototype.setPointerCapture = () => {};
    Element.prototype.releasePointerCapture = () => {};
    Document.prototype.exitPointerLock = () => {};
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(url);
  await page.waitForSelector("html.sc-ready");
  await page.evaluate(() => document.fonts.ready);
  assert.match(await page.title(), /Pandaset/);
  assert.equal(
    await page.locator("h1").innerText(),
    "Less noise.\nMore insight.",
  );
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
    "no horizontal overflow",
  );
  await page.screenshot({ path: new URL(`${name}-hero.png`, out).pathname });
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(":focus").innerText(), "Skip to content");
  await page.keyboard.press("Enter");
  assert.equal(await page.locator(":focus").getAttribute("id"), "main");
  if (width < 761) {
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    assert.equal(await page.locator("#landing-nav").isVisible(), true);
    await page.getByRole("link", { name: "The toolkit", exact: true }).focus();
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#landing-nav").isVisible(), false);
    assert.equal(await page.locator(":focus").innerText(), "Menu");
  }
  const peak = page.locator("#perspective");
  await peak.scrollIntoViewIfNeeded();
  await page.getByRole("button", { name: "Risk", exact: true }).click();
  assert.equal(
    await page
      .getByRole("button", { name: "Risk", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  await page
    .getByRole("heading", { name: "Where the risk comes from" })
    .waitFor();
  assert.match(
    await page.locator(".lp-chart-takeaway").innerText(),
    /NVIDIA contributes/,
  );
  await page.waitForTimeout(650);
  const hedgeScale = await page
    .locator(".lp-bar-row")
    .filter({ hasText: "TLT" })
    .locator(".lp-bar")
    .evaluate((el) => new DOMMatrix(getComputedStyle(el).transform).a);
  assert.ok(hedgeScale < 0, "negative modeled risk extends left of zero");
  await page.screenshot({ path: new URL(`${name}-risk.png`, out).pathname });
  await page.getByRole("button", { name: "Capital", exact: true }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("heading", { name: "Where the money sits" }).waitFor();
  assert.match(await page.locator(".lp-chart-takeaway").innerText(), /24%/);
  const links = await page
    .locator(".lp-tool-list a")
    .evaluateAll((els) => els.map((e) => e.getAttribute("href")));
  assert.deepEqual(links, [
    "./app.html#/",
    "./app.html#/risk",
    "./app.html#/research",
    "./app.html#/what-if",
  ]);
  await page.locator(".lp-close").scrollIntoViewIfNeeded();
  await page.screenshot({ path: new URL(`${name}-close.png`, out).pathname });
  await page.getByRole("link", { name: "Back to top" }).click();
  await page.waitForTimeout(reducedMotion === "reduce" ? 50 : 700);
  assert.equal(await page.locator(":focus").getAttribute("id"), "main");
  assert.equal(errors.length, 0, errors.join("\n"));
  report.push({
    name,
    width,
    height,
    reducedMotion,
    checks:
      "overflow, keyboard skip, menu and Escape, both chart controls, sample values, workflow links, closing action, console",
    errors,
  });
  await context.close();
}
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
});
await context.addInitScript(() => {
  Element.prototype.requestPointerLock = () =>
    Promise.reject(new Error("Disabled"));
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
});
const page = await context.newPage();
await page.goto(url);
await page.waitForSelector("html.sc-ready");
const peak = await page.locator("#perspective").evaluate((el) => ({
  top: el.offsetTop,
  height: el.offsetHeight,
}));
assert.equal(await page.locator(".sc-act--pinned").count(), 0);
let previous;
for (const y of [
  peak.top - 150,
  peak.top,
  peak.top + 160,
  peak.top + 320,
  peak.top + peak.height - 100,
]) {
  await page.evaluate((y) => scrollTo({ top: y, behavior: "instant" }), y);
  await page.waitForTimeout(40);
  const position = await page
    .locator(".lp-perspective-stage")
    .evaluate((el) => ({
      top: el.getBoundingClientRect().top,
      scroll: scrollY,
    }));
  if (previous) {
    assert.ok(
      Math.abs(
        position.top - previous.top + (position.scroll - previous.scroll),
      ) < 1,
      "black section moves with the document without sticking",
    );
  }
  previous = position;
}
await page.getByRole("heading", { name: "Where the money sits" }).waitFor();
await page.getByRole("button", { name: "Risk", exact: true }).click();
await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
await page.locator("#perspective").scrollIntoViewIfNeeded();
await page
  .getByRole("heading", { name: "Where the risk comes from" })
  .waitFor();
report.push({
  nativeComparisonScroll:
    "no pinning across entry, middle, or exit; manual chart choice persists",
});
// The merged dashboard requires authentication before loading portfolio data.
await page.locator(".lp-nav-cta").click();
await page.waitForURL("**/app.html#/");
await page
  .getByRole("heading", {
    name: /Welcome back|authentication is not configured/,
  })
  .waitFor();
report.push({
  dashboardNavigation: "passed (authentication boundary reached)",
});
for (const hash of ["#/", "#/risk", "#/research?symbol=NVDA", "#/what-if"]) {
  await page.goto(`${url}/${hash}`);
  await page.waitForURL(`**/app.html${hash}`);
  assert.equal(new URL(page.url()).hash, hash);
}
report.push({ legacyHashLinks: "all four dashboard routes preserved" });
fs.writeFileSync(new URL("report.json", out), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
