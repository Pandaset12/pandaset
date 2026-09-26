import { assets } from "../../../quant/data";
import { validateWeights } from "../../../quant/analytics";

export type Holding = { symbol: string; weight: number };
export type PortfolioInput = { name: string; holdings: Holding[] };
export type Portfolio = PortfolioInput & {
  portfolio_id: string;
  created_at: string;
};
export type AnalysisResponse = {
  analysis_id: string;
  portfolio_id: string;
  created_at: string;
  as_of: string | null;
  lookback_days: number;
  portfolio_return: number | null;
  portfolio_volatility: number;
  asset_volatility: Record<string, number> | null;
  correlation_matrix: Record<string, Record<string, number | null>> | null;
  risk_contribution: Record<string, number | null>;
  concentration: { largest_position: string; largest_weight: number };
  data_quality: {
    source: string;
    freshness: "fresh" | "stale" | "unknown";
    warnings: string[];
  };
  weights: Record<string, number>;
  data_mode: "demo" | "live";
  observation_count: number | null;
  return_frequency: "daily";
  volatility_unit: "annualized_decimal";
  assumptions: string[];
};

export function portfolioInput(weights: number[]): PortfolioInput {
  if (!validateWeights(weights)) {
    throw new Error(
      "Allocations must total 100%, with each value between 0% and 100%.",
    );
  }
  return {
    name: "Long-term portfolio",
    holdings: assets.flatMap((asset, index) =>
      weights[index] === 0
        ? []
        : [{ symbol: asset.symbol, weight: weights[index] / 100 }],
    ),
  };
}

async function post<T>(url: string, body?: object): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.error?.message || `Demo API returned ${response.status}.`,
    );
  }
  return (await response.json()) as T;
}

export async function analyzePortfolio(weights: number[]) {
  const portfolio = await post<Portfolio>(
    "/api/v1/portfolios",
    portfolioInput(weights),
  );
  const analysis = await post<AnalysisResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolio.portfolio_id)}/analysis`,
  );
  if (analysis.portfolio_id !== portfolio.portfolio_id) {
    throw new Error("Demo API returned an analysis for a different portfolio.");
  }
  return { portfolio, analysis };
}
