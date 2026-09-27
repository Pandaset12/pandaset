import type { Portfolio } from "../api/portfolio";

/** Display metadata for a saved holding. Financial values live in its analysis. */
export type PortfolioAsset = {
  symbol: string;
  name: string;
  short: string;
  sector: string | null;
  color: string;
  description: string | null;
  thesis: string | null;
  watch: string | null;
  source: string | null;
};

export type Instrument = {
  symbol: string;
  name: string;
  kind: "us_stock" | "equity_etf" | "treasury_etf" | "gold_etp";
  sector: string;
};

const colors = [
  "#39734f",
  "#38638a",
  "#a7473f",
  "#86580f",
  "#566735",
  "#765477",
  "#9a4d2a",
  "#547e79",
];

export function assetsForPortfolio(
  portfolio: Portfolio,
  instruments: readonly Instrument[],
): PortfolioAsset[] {
  const bySymbol = new Map(instruments.map((item) => [item.symbol, item]));
  return portfolio.holdings.map(({ symbol }, index) => {
    const instrument = bySymbol.get(symbol);
    return {
      symbol,
      name: instrument?.name ?? symbol,
      short: instrument?.name ?? symbol,
      sector: instrument?.sector ?? null,
      color: colors[index % colors.length],
      description: null,
      thesis: null,
      watch: null,
      source: null,
    };
  });
}
