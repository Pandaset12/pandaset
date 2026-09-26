import { test } from "node:test";
import assert from "node:assert/strict";
import {
  analyze,
  assetPath,
  correlationMatrix,
  covarianceMatrix,
  validateWeights,
} from "../analytics.ts";
import { assets, initialWeights, returns, dates } from "../data.ts";
const close = (actual: number, expected: number, tolerance = 1e-10) =>
  assert.ok(
    Math.abs(actual - expected) < tolerance,
    `${actual} != ${expected}`,
  );
test("return attribution reconciles to portfolio return for each supported time window", () => {
  for (const days of [21, 63, 126, 252]) {
    const m = analyze(initialWeights, days);
    close(
      m.contributions.reduce((a, b) => a + b, 0),
      m.return,
    );
    assert.equal(m.path.length, days + 1);
    assert.ok(m.maxDrawdown <= 0);
    assert.ok(m.path.every(Number.isFinite));
  }
});
test("risk contributions sum to 100% and absent holdings contribute zero", () => {
  const m = analyze(initialWeights);
  close(
    m.risk.reduce((a, b) => a + b, 0),
    1,
  );
  close(m.risk[6], 0);
  close(m.risk[7], 0);
  assert.ok(m.volatility > 0);
});
test("single-asset portfolios match the asset path and volatility", () => {
  assets.forEach((_, i) => {
    const weights = assets.map((_, j) => (i === j ? 100 : 0)),
      m = analyze(weights);
    close(m.return, assetPath(i).at(-1)! - 1);
    close(m.volatility, Math.sqrt(covarianceMatrix[i][i] * 252));
    close(m.risk[i], 1);
  });
});
test("weights reject non-finite, negative, out-of-bounds, and wrong totals", () => {
  assert.equal(validateWeights(initialWeights), true);
  for (const weights of [
    [],
    [100],
    [-1, 21, 16, 12, 32, 20, 0, 0],
    [NaN, 20, 16, 12, 18, 10, 0, 0],
    [101, 0, 0, 0, 0, 0, 0, 0],
    [20, 20, 16, 12, 18, 10, 0, 0],
  ]) {
    assert.equal(validateWeights(weights), false);
    assert.throws(() => analyze(weights));
  }
});
test("correlations are symmetric, bounded, and have unit diagonal", () => {
  correlationMatrix.forEach((row, i) =>
    row.forEach((value, j) => {
      close(value, correlationMatrix[j][i]);
      assert.ok(value >= -1.0000001 && value <= 1.0000001);
      if (i === j) close(value, 1);
    }),
  );
});
test("sample return series matches disclosed fixtures and aligned trading dates", () => {
  assert.equal(dates.length, 253);
  assert.equal(dates.at(-1), "2026-09-25");
  assets.forEach((a, i) => {
    assert.equal(returns[i].length, 252);
    close(assetPath(i).at(-1)! - 1, a.target);
  });
});
test("a scenario produces new metrics without mutating the original", () => {
  const before = [...initialWeights];
  const scenario = [...before];
  scenario[0] -= 10;
  scenario[3] += 10;
  assert.notEqual(analyze(scenario).volatility, analyze(before).volatility);
  assert.deepEqual(initialWeights, before);
});
