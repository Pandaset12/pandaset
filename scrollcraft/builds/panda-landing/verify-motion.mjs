import { chromium } from "playwright-core";
import assert from "node:assert/strict";
import fs from "node:fs";
const url = process.env.LANDING_URL || "http://127.0.0.1:45274/";
const out = new URL("./lab/motion-interactions/", import.meta.url);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
});
const safePointer = () => {
  Element.prototype.requestPointerLock = () =>
    Promise.reject(new Error("Disabled during verification"));
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Document.prototype.exitPointerLock = () => {};
};
await context.addInitScript(safePointer);
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.goto(url);
await page.waitForSelector(".lp-hero-awake");
await page.evaluate(() => document.fonts.ready);
await page.evaluate(() => {
  for (const animation of document.getAnimations()) {
    if (
      animation instanceof CSSAnimation &&
      [
        "lp-heading-arrive",
        "lp-panda-arrive",
        "lp-chart-draw",
        "lp-tip-arrive",
      ].includes(animation.animationName)
    ) {
      animation.pause();
      animation.currentTime = 450;
    }
  }
});
await page.screenshot({ path: new URL("hero-arriving.png", out).pathname });
const initialClip = await page
  .locator(".lp-chart-ink")
  .evaluate((el) => getComputedStyle(el).clipPath);
await page.evaluate(() =>
  document.getAnimations().forEach((animation) => animation.finish()),
);
const settledClip = await page
  .locator(".lp-chart-ink")
  .evaluate((el) => getComputedStyle(el).clipPath);
assert.notEqual(
  initialClip,
  settledClip,
  "the chart visibly reveals across its arrival",
);
const scene = page.locator(".lp-scene");
const box = await scene.boundingBox();
await page.mouse.move(box.x + 25, box.y + 160);
await page.waitForTimeout(400);
const left = await scene.screenshot({
  path: new URL("panda-look-left.png", out).pathname,
});
const leftTransform = await page
  .locator(".lp-panda-gaze")
  .evaluate((el) => getComputedStyle(el).transform);
await page.mouse.move(box.x + box.width - 25, box.y + 200);
await page.waitForTimeout(400);
const right = await scene.screenshot({
  path: new URL("panda-look-right.png", out).pathname,
});
const rightTransform = await page
  .locator(".lp-panda-gaze")
  .evaluate((el) => getComputedStyle(el).transform);
assert.notEqual(leftTransform, rightTransform);
assert.equal(
  left.equals(right),
  false,
  "pointer movement changes actual scene pixels",
);
await page.mouse.move(0, 0);
await page.waitForTimeout(300);
assert.equal(
  await scene.evaluate((el) => el.style.getPropertyValue("--lp-look-x")),
  "0px",
);
const sentenceTop = await page
  .locator("#recognition-heading")
  .evaluate((el) => el.getBoundingClientRect().top + scrollY);
await page.evaluate(
  (y) => scrollTo({ top: y, behavior: "instant" }),
  sentenceTop - 760,
);
await page.waitForTimeout(100);
const before = await page
  .locator(".lp-recognition-word")
  .last()
  .evaluate((el) => Number(getComputedStyle(el).opacity));
await page.evaluate(
  (y) => scrollTo({ top: y, behavior: "instant" }),
  sentenceTop - 350,
);
await page.waitForTimeout(100);
const after = await page
  .locator(".lp-recognition-word")
  .last()
  .evaluate((el) => Number(getComputedStyle(el).opacity));
assert.ok(after > before && after === 1, "scroll resolves word emphasis");
const toolkit = page.locator(".lp-tool-list a").last();
await toolkit.focus();
assert.equal(
  await toolkit.evaluate((el) => el.classList.contains("lp-arrived")),
  true,
);
await page.waitForTimeout(850);
assert.equal(
  await toolkit.evaluate((el) => Number(getComputedStyle(el).opacity)),
  1,
);
assert.equal(
  await page
    .locator(".lp-tool-list")
    .evaluate((el) => getComputedStyle(el).clipPath),
  "none",
);
await page.emulateMedia({ reducedMotion: "reduce" });
await page.waitForTimeout(100);
assert.equal(
  await page
    .locator(".panda-landing")
    .evaluate((el) => el.classList.contains("lp-motion-ready")),
  false,
);
assert.equal(
  await page
    .locator(".lp-panda-gaze")
    .evaluate((el) => getComputedStyle(el).transform),
  "none",
);
assert.equal(
  await page
    .locator(".lp-tool-list a")
    .evaluateAll((els) =>
      els.every((el) => getComputedStyle(el).opacity === "1"),
    ),
  true,
);
assert.equal(
  await page.evaluate(
    () =>
      document.getAnimations().filter((a) => a.playState === "running").length,
  ),
  0,
);
await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
await page.screenshot({
  path: new URL("reduced-after-toggle.png", out).pathname,
});
await page.emulateMedia({ reducedMotion: "no-preference" });
await page.waitForSelector(".lp-motion-ready");
await page.waitForTimeout(1900);
assert.equal(
  await page.evaluate(
    () =>
      document.getAnimations().filter((a) => a.playState === "running").length,
  ),
  0,
  "no indefinite ambient animation",
);
assert.deepEqual(errors, []);
await context.close();
const touch = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});
await touch.addInitScript(safePointer);
const phone = await touch.newPage();
await phone.goto(url);
await phone.waitForSelector(".lp-hero-awake");
await phone.waitForTimeout(1900);
assert.equal(
  await phone.evaluate(
    () => matchMedia("(hover: hover) and (pointer: fine)").matches,
  ),
  false,
);
await phone.locator(".lp-scene").tap();
assert.equal(
  await phone
    .locator(".lp-panda-gaze")
    .evaluate((el) => getComputedStyle(el).transform),
  "none",
);
await phone.screenshot({ path: new URL("touch-hero.png", out).pathname });
await touch.close();
await browser.close();
const report = {
  chartArrival: true,
  pointerPixelChange: true,
  pointerReset: true,
  scrollWordEmphasis: true,
  keyboardReveal: true,
  liveReducedMotion: true,
  noInfiniteAnimation: true,
  touchFallback: true,
  consoleErrors: errors,
};
fs.writeFileSync(new URL("report.json", out), JSON.stringify(report, null, 2));
console.log(report);
