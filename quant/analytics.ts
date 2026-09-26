import { assets, returns } from "./data";
export const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;
export function covariance(a: number[], b: number[]) {
  const ma = mean(a),
    mb = mean(b);
  return a.reduce((s, x, i) => s + (x - ma) * (b[i] - mb), 0) / (a.length - 1);
}
export const covarianceMatrix = returns.map((a) =>
  returns.map((b) => covariance(a, b)),
);
export const correlationMatrix = covarianceMatrix.map((row, i) =>
  row.map(
    (v, j) => v / Math.sqrt(covarianceMatrix[i][i] * covarianceMatrix[j][j]),
  ),
);
export function validateWeights(weights: number[]) {
  return (
    weights.length === assets.length &&
    weights.every((w) => Number.isFinite(w) && w >= 0 && w <= 100) &&
    Math.abs(weights.reduce((s, w) => s + w, 0) - 100) < 0.001
  );
}
export function analyze(weights: number[], days = 252) {
  if (!validateWeights(weights))
    throw new Error(
      "Allocations must total 100%, with each value between 0 and 100.",
    );
  const w = weights.map((v) => v / 100);
  const window = Math.max(1, Math.min(252, days));
  const daily = returns[0]
    .slice(-window)
    .map((_, day) =>
      w.reduce(
        (s, weight, i) => s + weight * returns[i][252 - window + day],
        0,
      ),
    );
  const path = [1];
  const contributions = assets.map(() => 0);
  daily.forEach((r, day) => {
    const prev = path.at(-1)!;
    w.forEach((weight, i) => {
      contributions[i] += prev * weight * returns[i][252 - window + day];
    });
    path.push(prev * (1 + r));
  });
  let peak = 1,
    maxDrawdown = 0;
  path.forEach((v) => {
    peak = Math.max(peak, v);
    maxDrawdown = Math.min(maxDrawdown, v / peak - 1);
  });
  const variance = w.reduce(
    (total, weight, i) =>
      total +
      weight * w.reduce((s, wj, j) => s + wj * covarianceMatrix[i][j], 0),
    0,
  );
  const risk = w.map((weight, i) =>
    variance > 0
      ? (weight * w.reduce((s, wj, j) => s + wj * covarianceMatrix[i][j], 0)) /
        variance
      : 0,
  );
  const annualReturn = path.at(-1)! ** (252 / window) - 1;
  const volatility = Math.sqrt(variance * 252);
  const sectors = Object.entries(
    w.reduce(
      (s, weight, i) => {
        s[assets[i].sector] = (s[assets[i].sector] || 0) + weight;
        return s;
      },
      {} as Record<string, number>,
    ),
  )
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
  const topRisk = risk.indexOf(Math.max(...risk));
  return {
    daily,
    path,
    return: path.at(-1)! - 1,
    volatility,
    risk,
    contributions,
    maxDrawdown,
    annualReturn,
    sectors,
    topRisk,
    sharpe: (annualReturn - 0.04) / volatility,
    concentration: Math.max(...w),
    beta: w.reduce((s, v, i) => s + v * assets[i].beta, 0),
  };
}
export function assetPath(index: number, days = 252) {
  return returns[index]
    .slice(-days)
    .reduce((path, r) => [...path, path.at(-1)! * (1 + r)], [1]);
}
export const pct = (v: number, digits = 1) =>
  new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v);
export const signedPct = (v: number, digits = 2) =>
  `${v > 0 ? "+" : ""}${pct(v, digits)}`;
export const money = (v: number, digits = 0) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(v);
export const pp = (v: number) =>
  `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)} pp`;
