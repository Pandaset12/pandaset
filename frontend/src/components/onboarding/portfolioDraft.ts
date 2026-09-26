import type { PortfolioInput } from "../../api/portfolio";

export const MAX_HOLDINGS = 8;
export const MAX_NAME_LENGTH = 100;
export const PERCENT_SCALE = 1_000_000;
export const FULL_ALLOCATION = 100 * PERCENT_SCALE;

export type TickerResult = { symbol: string; name?: string };
export type HoldingDraft = TickerResult & { percentage: string };
export type DraftErrors = {
  name?: string;
  holdings?: string;
  total?: string;
  rows: Record<string, string>;
};
export type DraftValidation = {
  errors: DraftErrors;
  totalUnits: number;
  payload: PortfolioInput | null;
};

export function normalizeSymbol(value: string) {
  return value.trim().toUpperCase();
}

export function isValidSymbol(value: string) {
  return /^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/.test(normalizeSymbol(value));
}

export function portfolioNameError(name: string): string | undefined {
  if (!name.trim()) return "Give your portfolio a name.";
  if (name.trim().length > MAX_NAME_LENGTH)
    return "Use a portfolio name of 100 characters or fewer.";
}

// Integer percentage units avoid rounding 99.999999% up to a valid allocation.
export function parsePercentage(
  value: string,
  allowZero = false,
): number | null {
  const trimmed = value.trim();
  if (!/^(?:\d+(?:\.\d{0,6})?|\.\d{1,6})$/.test(trimmed)) return null;
  const number = Number(trimmed);
  if (
    !Number.isFinite(number) ||
    number < 0 ||
    (!allowZero && number === 0) ||
    number > 100
  )
    return null;
  const [whole, fraction = ""] = trimmed.split(".");
  return Number(whole || 0) * PERCENT_SCALE + Number(fraction.padEnd(6, "0"));
}

export function formatPercentage(units: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 6,
  }).format(units / PERCENT_SCALE);
}

export function validatePortfolioDraft(
  name: string,
  holdings: readonly HoldingDraft[],
): DraftValidation {
  const errors: DraftErrors = { rows: {} };
  errors.name = portfolioNameError(name);
  if (!holdings.length)
    errors.holdings = "Add at least one holding to continue.";
  if (holdings.length > MAX_HOLDINGS)
    errors.holdings = `A portfolio can contain up to ${MAX_HOLDINGS} holdings.`;

  let totalUnits = 0;
  const symbols = new Set<string>();
  const payloadHoldings: PortfolioInput["holdings"] = [];
  for (const holding of holdings) {
    const symbol = normalizeSymbol(holding.symbol);
    if (!isValidSymbol(symbol))
      errors.rows[symbol] = "Enter a valid ticker of up to 20 characters.";
    else if (symbols.has(symbol))
      errors.rows[symbol] = "This ticker is already in your portfolio.";
    symbols.add(symbol);

    const units = parsePercentage(holding.percentage);
    if (units === null) {
      errors.rows[symbol] ??=
        "Enter a weight above 0% and up to 100%, with up to 6 decimal places.";
    } else {
      totalUnits += units;
      payloadHoldings.push({ symbol, weight: units / FULL_ALLOCATION });
    }
  }
  if (holdings.length && totalUnits !== FULL_ALLOCATION) {
    errors.total =
      totalUnits < FULL_ALLOCATION
        ? "Allocate the remaining " +
          formatPercentage(FULL_ALLOCATION - totalUnits) +
          "%."
        : "Reduce your allocation by " +
          formatPercentage(totalUnits - FULL_ALLOCATION) +
          "%.";
  }
  const valid =
    !errors.name &&
    !errors.holdings &&
    !errors.total &&
    Object.keys(errors.rows).length === 0;
  return {
    errors,
    totalUnits,
    payload: valid ? { name: name.trim(), holdings: payloadHoldings } : null,
  };
}

export function normalizeTickerResults(results: readonly TickerResult[]) {
  const seen = new Set<string>();
  return results
    .flatMap((result) => {
      if (!result || typeof result.symbol !== "string") return [];
      const symbol = normalizeSymbol(result.symbol);
      if (!isValidSymbol(symbol) || seen.has(symbol)) return [];
      seen.add(symbol);
      return [
        {
          symbol,
          name:
            typeof result.name === "string"
              ? result.name.trim().slice(0, 160)
              : undefined,
        },
      ];
    })
    .slice(0, 8);
}
