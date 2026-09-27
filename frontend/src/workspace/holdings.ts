import { assets, type Asset } from "../../../quant/data";
import type { Portfolio, PortfolioInput } from "../api/portfolio";
import {
  FULL_ALLOCATION,
  PERCENT_SCALE,
  parsePercentage,
} from "../components/onboarding/portfolioDraft";

export function workspaceAsset(symbol: string): Asset {
  const known = assets.find((asset) => asset.symbol === symbol);
  return (
    known ?? {
      symbol,
      name: symbol,
      short: symbol,
      sector: "Unclassified",
      color: "#64748b",
      price: 0,
      target: 0,
      vol: 0,
      beta: 0,
      description: "Company details are unavailable for this ticker.",
      thesis: "",
      watch: "",
      source: "",
    }
  );
}

export function workspaceAssets(portfolio: Portfolio): Asset[] {
  return portfolio.holdings.map(({ symbol }) => workspaceAsset(symbol));
}

export function portfolioPercentages(portfolio: Portfolio): number[] {
  const exact = portfolio.holdings.map(
    ({ weight }) => weight * FULL_ALLOCATION,
  );
  const units = exact.map(Math.floor);
  let remaining =
    FULL_ALLOCATION - units.reduce((sum, value) => sum + value, 0);
  const order = exact
    .map((_, index) => index)
    .sort((a, b) => exact[b] - units[b] - (exact[a] - units[a]) || a - b);
  for (let index = 0; index < remaining; index += 1) units[order[index]] += 1;
  return units.map((value) => value / PERCENT_SCALE);
}

export function parsePercentageDraft(values: string[]): number[] | null {
  const units = values.map((value) => parsePercentage(value, true));
  if (units.some((value) => value === null)) return null;
  if (
    units.reduce<number>((sum, value) => sum + (value ?? 0), 0) !==
    FULL_ALLOCATION
  )
    return null;
  return units.map((value) => value! / PERCENT_SCALE);
}

export function allocationPercent(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: 6,
  }).format(value);
}

export function validPercentages(
  weights: number[],
  symbols: string[],
): boolean {
  return (
    weights.length === symbols.length &&
    weights.length > 0 &&
    weights.every(
      (weight) => Number.isFinite(weight) && weight >= 0 && weight <= 100,
    ) &&
    Math.abs(weights.reduce((sum, weight) => sum + weight, 0) - 100) < 0.000001
  );
}

export function portfolioFromPercentages(
  name: string,
  symbols: string[],
  weights: number[],
): PortfolioInput {
  if (!validPercentages(weights, symbols))
    throw new Error("Allocations must total 100%.");
  return {
    name,
    holdings: symbols.flatMap((symbol, index) =>
      weights[index] > 0 ? [{ symbol, weight: weights[index] / 100 }] : [],
    ),
  };
}
