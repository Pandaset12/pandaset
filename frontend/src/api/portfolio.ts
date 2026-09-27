import { assets } from "../../../quant/data";
import { validateWeights } from "../../../quant/analytics";

export type Holding = { symbol: string; weight: number };
export type PortfolioInput = { name: string; holdings: Holding[] };
export type Portfolio = PortfolioInput & {
  portfolio_id: string;
  created_at: string;
};
export type Freshness = "fresh" | "stale" | "unknown";
export type AnalysisSeries = {
  dates: string[];
  portfolio_index: (number | null)[];
  asset_index: Record<string, (number | null)[]>;
  return_contribution: Record<string, number | null>;
};
export type MetricSnapshot = {
  portfolio_id: string;
  data_mode: "demo" | "live";
  data_as_of: string | null;
  lookback_trading_days: number;
  portfolio_volatility: number;
  weights: Record<string, number>;
  portfolio_return: number | null;
  annualized_return: number | null;
  max_drawdown: number | null;
  asset_volatility: Record<string, number> | null;
  correlation_matrix: Record<string, Record<string, number | null>> | null;
  risk_contribution: Record<string, number | null>;
  return_contribution: Record<string, number | null> | null;
  series: AnalysisSeries | null;
  data_source: string;
  freshness: Freshness;
  notes: string[];
  assumptions: string[];
};
export type AnalysisResponse = Omit<
  MetricSnapshot,
  "data_as_of" | "lookback_trading_days" | "data_source" | "freshness" | "notes"
> & {
  analysis_id: string;
  created_at: string;
  as_of: string | null;
  lookback_days: number;
  data_quality: { source: string; freshness: Freshness; warnings: string[] };
  concentration: { largest_position: string; largest_weight: number };
  observation_count: number | null;
  return_frequency: "daily";
  volatility_unit: "annualized_decimal";
};
export type MarketHistoryResponse = {
  symbols: string[];
  dates: string[];
  asset_index: Record<string, (number | null)[]>;
  data_mode: "demo" | "live";
  data_source: string;
  freshness: Freshness;
  requested_lookback_days: number;
  observation_count: number;
  warnings: string[];
};
export type AskResponse = {
  analyst_mode: "demo" | "gemini";
  status: "complete" | "demo" | "unavailable";
  answer: string;
  citations: { field: string; value: number }[];
  warnings: string[];
  disclaimer: string;
  analysis_id: string | null;
  error_code: string | null;
};
export type AIWorkflow =
  | "analysis_briefing"
  | "risk_explanation"
  | "scenario_explanation"
  | "research_summary";
export type AIWorkflowResponse = {
  workflow: AIWorkflow;
  analyst_mode: "demo" | "gemini";
  status: "complete" | "demo" | "unavailable";
  answer: string;
  analysis_id: string | null;
  symbol: string | null;
  source_url: string | null;
  citations: { field: string; value: number }[];
  sources: Record<string, unknown>[];
  grounding_supports: Record<string, unknown>[];
  url_retrievals: Record<string, unknown>[];
  warnings: string[];
  disclaimer: string;
  error_code: string | null;
};
export type WhatIfResponse = {
  current_analysis: MetricSnapshot;
  proposed_analysis: MetricSnapshot;
  delta: {
    portfolio_return: number | null;
    portfolio_volatility: number;
    annualized_return: number | null;
    max_drawdown: number | null;
  };
  difference_convention: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function createRequestGuard() {
  let current = 0;
  return {
    begin: () => ++current,
    isCurrent: (request: number) => request === current,
    invalidate: () => {
      current += 1;
    },
  };
}

export function portfolioInput(
  weights: number[],
  name = "Long-term portfolio",
): PortfolioInput {
  if (!validateWeights(weights)) {
    throw new Error(
      "Allocations must total 100%, with each value between 0% and 100%.",
    );
  }
  return {
    name,
    holdings: assets.flatMap((asset, index) =>
      weights[index] === 0
        ? []
        : [{ symbol: asset.symbol, weight: weights[index] / 100 }],
    ),
  };
}

function allocation(weights: number[]) {
  return portfolioInput(weights).holdings;
}

const requestsInFlight = new Map<string, Promise<unknown>>();

function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const key = `${init.method ?? "GET"} ${url} ${typeof init.body === "string" ? init.body : ""}`;
  const existing = requestsInFlight.get(key);
  if (existing) return existing as Promise<T>;
  const pending = (async () => {
    const response = await fetch(url, init);
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const error = payload?.error;
      throw new ApiError(
        typeof error?.message === "string"
          ? error.message
          : `Pandaset API request failed (${response.status}).`,
        response.status,
        typeof error?.request_id === "string" ? error.request_id : undefined,
      );
    }
    return payload as T;
  })();
  requestsInFlight.set(key, pending);
  void pending.then(
    () => {
      if (requestsInFlight.get(key) === pending) requestsInFlight.delete(key);
    },
    () => {
      if (requestsInFlight.get(key) === pending) requestsInFlight.delete(key);
    },
  );
  return pending;
}

const post = <T>(url: string, body?: object) =>
  request<T>(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

export async function analyzePortfolio(weights: number[]) {
  const portfolio = await post<Portfolio>(
    "/api/v1/portfolios",
    portfolioInput(weights),
  );
  const analysis = await post<AnalysisResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolio.portfolio_id)}/analysis`,
  );
  if (
    analysis.portfolio_id !== portfolio.portfolio_id ||
    assets.some(
      (asset, index) =>
        Math.abs((analysis.weights[asset.symbol] ?? 0) * 100 - weights[index]) >
        0.001,
    )
  ) {
    throw new Error(
      "Pandaset API returned an analysis for a different portfolio allocation.",
    );
  }
  return { portfolio, analysis };
}

export async function getAnalysis(portfolioId: string, analysisId: string) {
  return request<AnalysisResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/analyses/${encodeURIComponent(analysisId)}`,
  );
}

export function getMarketHistory(symbols: string[], lookbackDays = 252) {
  const query = new URLSearchParams({ lookback_days: String(lookbackDays) });
  symbols.forEach((symbol) => query.append("symbols", symbol));
  return request<MarketHistoryResponse>(`/api/v1/market-history?${query}`);
}

export function comparePortfolio(portfolioId: string, weights: number[]) {
  return post<WhatIfResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/what-if`,
    { holdings: allocation(weights) },
  );
}

export function askPortfolio(
  portfolioId: string,
  analysisId: string,
  question: string,
) {
  return post<AskResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/ask`,
    { analysis_id: analysisId, question },
  );
}

export function requestAnalysisBriefing(
  portfolioId: string,
  analysisId: string,
) {
  return post<AIWorkflowResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/briefing`,
    { analysis_id: analysisId },
  );
}

export function requestRiskExplanation(
  portfolioId: string,
  analysisId: string,
  question: string,
) {
  return post<AIWorkflowResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/risk/explanation`,
    { analysis_id: analysisId, question },
  );
}

export function requestScenarioExplanation(
  portfolioId: string,
  analysisId: string,
  weights: number[],
) {
  return post<AIWorkflowResponse>(
    `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/what-if/explanation`,
    {
      analysis_id: analysisId,
      proposed_weights: Object.fromEntries(
        allocation(weights).map(({ symbol, weight }) => [symbol, weight]),
      ),
      question:
        "Explain the trade-offs across the current, proposed, and change metrics.",
    },
  );
}

export function requestResearchSummary(symbol: string) {
  return post<AIWorkflowResponse>(
    `/api/v1/research/${encodeURIComponent(symbol.toUpperCase())}/summary`,
    { source_id: "issuer" },
  );
}
