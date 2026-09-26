import assert from "node:assert/strict";
import { test } from "node:test";
import {
  FULL_ALLOCATION,
  MAX_HOLDINGS,
  formatPercentage,
  isValidSymbol,
  normalizeTickerResults,
  parsePercentage,
  validatePortfolioDraft,
} from "../src/components/onboarding/portfolioDraft";
import type { HoldingDraft } from "../src/components/onboarding/portfolioDraft";

test("manual portfolio payload trims names, normalizes symbols and converts percentages once", () => {
  const rows = [
    { symbol: " nvda ", percentage: "25", name: "NVIDIA" },
    { symbol: "SPY", percentage: "75" },
  ];
  const before = structuredClone(rows);
  const result = validatePortfolioDraft("  My portfolio  ", rows);
  assert.deepEqual(result.payload, {
    name: "My portfolio",
    holdings: [
      { symbol: "NVDA", weight: 0.25 },
      { symbol: "SPY", weight: 0.75 },
    ],
  });
  assert.equal(result.totalUnits, FULL_ALLOCATION);
  assert.deepEqual(rows, before);
});

test("decimal allocations reconcile exactly without silent normalization or display rounding", () => {
  const rows = [
    { symbol: "NVDA", percentage: "33.333333" },
    { symbol: "JPM", percentage: "33.333333" },
    { symbol: "TLT", percentage: "33.333334" },
  ];
  const result = validatePortfolioDraft("Decimals", rows);
  assert.ok(result.payload);
  assert.ok(
    Math.abs(
      result.payload.holdings.reduce((sum, row) => sum + row.weight, 0) - 1,
    ) < 1e-10,
  );
  rows[2].percentage = "33.333333";
  const short = validatePortfolioDraft("Decimals", rows);
  assert.equal(short.payload, null);
  assert.equal(formatPercentage(short.totalUnits), "99.999999");
  assert.equal(short.errors.total, "Allocate the remaining 0.000001%.");
});

test("under- and over-allocation are rejected rather than adjusted", () => {
  for (const [percentage, message] of [
    ["90", "remaining 10%"],
    ["60", "by 10%"],
  ]) {
    const rows =
      percentage === "90"
        ? [{ symbol: "NVDA", percentage }]
        : [
            { symbol: "NVDA", percentage },
            { symbol: "SPY", percentage: "50" },
          ];
    const result = validatePortfolioDraft("Portfolio", rows);
    assert.equal(result.payload, null);
    assert.ok(result.errors.total?.includes(message));
    assert.equal(rows[0].percentage, percentage);
  }
});

test("blank, zero, negative, non-finite and malformed percentages never produce an API payload", () => {
  for (const value of [
    "",
    " ",
    "0",
    "-1",
    "101",
    "NaN",
    "Infinity",
    "1e2",
    "50%",
    "12,5",
    "0.0000001",
    "1.1234567",
    ".",
  ]) {
    assert.equal(parsePercentage(value), null, value);
    const result = validatePortfolioDraft("Portfolio", [
      { symbol: "NVDA", percentage: value },
    ]);
    assert.equal(result.payload, null, value);
    assert.ok(result.errors.rows.NVDA, value);
  }
  assert.equal(parsePercentage(".5"), 500_000);
  assert.equal(parsePercentage("25."), 25_000_000);
});

test("duplicates are rejected after case and whitespace normalization", () => {
  const result = validatePortfolioDraft("Portfolio", [
    { symbol: "AAPL", percentage: "50" },
    { symbol: " aapl ", percentage: "50" },
  ]);
  assert.equal(result.payload, null);
  assert.match(result.errors.rows.AAPL, /already/);
});

test("names, ticker syntax, empty holdings and holding count enforce the current API contract", () => {
  const one = [{ symbol: "AAPL", percentage: "100" }];
  assert.ok(validatePortfolioDraft("", one).errors.name);
  assert.ok(validatePortfolioDraft(" ".repeat(3), one).errors.name);
  assert.ok(validatePortfolioDraft("A".repeat(101), one).errors.name);
  assert.ok(validatePortfolioDraft("A".repeat(100), one).payload);
  assert.ok(validatePortfolioDraft("Empty", []).errors.holdings);
  for (const symbol of ["", "A APL", "<script>", "A".repeat(21)]) {
    assert.equal(isValidSymbol(symbol), false);
    assert.equal(
      validatePortfolioDraft("Invalid", [{ symbol, percentage: "100" }])
        .payload,
      null,
    );
  }
  for (const symbol of ["BRK.B", "ETH-USD", "^GSPC", "AAPL"])
    assert.equal(isValidSymbol(symbol), true);
  const rows: HoldingDraft[] = Array.from(
    { length: MAX_HOLDINGS },
    (_, index) => ({
      symbol: "T" + index,
      percentage: String(100 / MAX_HOLDINGS),
    }),
  );
  assert.ok(validatePortfolioDraft("Full", rows).payload);
  rows.push({ symbol: "EXTRA", percentage: "1" });
  assert.ok(validatePortfolioDraft("Too many", rows).errors.holdings);
  assert.equal(validatePortfolioDraft("Too many", rows).payload, null);
});

test("search results are normalized, deduplicated and bounded before display", () => {
  const options = normalizeTickerResults([
    { symbol: " aapl ", name: " Apple " },
    { symbol: "AAPL", name: "Duplicate" },
    { symbol: "<invalid>", name: "Invalid" },
    { symbol: "MSFT" },
    ...Array.from({ length: 10 }, (_, i) => ({ symbol: "T" + i })),
  ]);
  assert.deepEqual(options[0], { symbol: "AAPL", name: "Apple" });
  assert.equal(options.length, 8);
  assert.equal(options.filter((option) => option.symbol === "AAPL").length, 1);
});
