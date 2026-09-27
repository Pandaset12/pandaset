import { getSupabase } from "../lib/supabase";
import type { Portfolio } from "./portfolio";

export class EventLabError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "EventLabError";
  }
}

export function validPercentAllocation(weights: readonly number[]): boolean {
  return (
    weights.length > 0 &&
    weights.length <= 25 &&
    weights.every(
      (value) =>
        Number.isFinite(value) &&
        value >= 0 &&
        value <= 100 &&
        Math.abs(value * 1_000_000 - Math.round(value * 1_000_000)) < 0.000001,
    ) &&
    weights.reduce((sum, value) => sum + Math.round(value * 1_000_000), 0) ===
      100_000_000
  );
}

export function editablePercentages(weights: readonly number[]): number[] {
  if (!weights.length) return [];
  const unitsPerPortfolio = 100_000_000;
  const unitsPerPercent = 1_000_000;
  const units = weights.map((weight) => Math.round(weight * unitsPerPortfolio));
  const difference =
    unitsPerPortfolio - units.reduce((sum, value) => sum + value, 0);
  // Put the display-rounding remainder on the largest holding so a valid
  // saved allocation remains valid when opened in the editor.
  const largest = units.reduce(
    (index, value, candidate) => (value > units[index] ? candidate : index),
    0,
  );
  units[largest] += difference;
  return units.map((value) => value / unitsPerPercent);
}

type RequestOptions = { signal?: AbortSignal; idempotencyKey?: string };

export async function eventRequest<T>(
  path: string,
  method = "GET",
  body?: object,
  options: RequestOptions = {},
): Promise<T> {
  const { data, error } = await getSupabase().auth.getSession();
  if (error || !data.session?.access_token) {
    throw new EventLabError(
      "Your session expired. Sign in again to continue.",
      401,
      "AUTH_REQUIRED",
    );
  }
  const response = await fetch(`/api/v2${path}`, {
    method,
    signal: options.signal,
    headers: {
      Authorization: `Bearer ${data.session.access_token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(options.idempotencyKey
        ? { "Idempotency-Key": options.idempotencyKey }
        : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const errorBody =
      payload && typeof payload === "object" && "error" in payload
        ? payload.error
        : null;
    const parsed =
      errorBody && typeof errorBody === "object"
        ? (errorBody as { code?: unknown; message?: unknown })
        : null;
    throw new EventLabError(
      typeof parsed?.message === "string"
        ? parsed.message
        : `The event service is unavailable (${response.status}).`,
      response.status,
      typeof parsed?.code === "string" ? parsed.code : "REQUEST_FAILED",
    );
  }
  return payload as T;
}

export type EventTemplate = {
  template_id: string;
  version: string;
  category: "macro" | "sector" | "issuer" | "custom";
  title: string;
  description: string;
  factor_ids: string[];
  target_symbols?: string[];
  situations: Array<{
    situation_id: string;
    title: string;
    description: string;
  }>;
};
export type Evidence = {
  evidence_id: string;
  status: string;
  title?: string;
  source_url?: string;
  published_at?: string | null;
  retrieved_at?: string | null;
  excerpt?: string | null;
  value?: number | string | null;
};
export type SourcedFact = { claim: string; evidence_ids: string[] };
export type ProposedShock = {
  factors: Record<string, number>;
  issuers: Record<string, number>;
  factor_unit: "cumulative_decimal_return";
  issuer_unit: "residual_sigma_multiple";
  rationale: string;
  evidence_ids: string[];
};
export type ConfirmedShock = {
  factors: Record<string, number>;
  issuers: Record<string, number>;
};
export type CaseGrid<T> = Record<
  "mild" | "central" | "severe",
  Record<"1m" | "3m", T>
>;
export type DraftProposal = {
  scenario_brief?: string;
  facts: SourcedFact[];
  missing_evidence: string[];
  evidence: Evidence[];
  proposed_shocks: CaseGrid<ProposedShock>;
  price_provenance?: unknown;
};
export type ScenarioDraft = {
  draft_id: string;
  created_at?: string;
  portfolio_revision?: number | null;
  allocation_snapshot?: Portfolio | null;
  proposed_weights?: Record<string, number> | null;
  price_provenance?: Record<string, unknown> | null;
  price_window?: { start: string | null; end: string | null };
  request?: {
    portfolio_id: string;
    portfolio_revision?: number;
    template_id: string;
    situation_id?: string | null;
    target_symbol?: string | null;
    situation_snapshot?: {
      situation_id: string;
      title: string;
      description: string;
    };
    description?: string;
    question?: string;
    proposed_weights?: Record<string, number> | null;
    source_run_id?: string;
  };
  status:
    | "pending"
    | "queued"
    | "running"
    | "ready"
    | "confirmed"
    | "failed"
    | "cancelled";
  revision: number | null;
  last_error?: string | null;
  proposal?: DraftProposal | null;
  confirmed_shocks?: CaseGrid<ConfirmedShock> | null;
};
export type CaseResult = {
  estimated_return: number;
  holding_contributions: Record<string, number>;
};
export type ScenarioResult = {
  current_weights?: Record<string, number>;
  proposed_weights?: Record<string, number>;
  cases: Array<{
    case: "mild" | "central" | "severe";
    horizon: "1m" | "3m";
    current: CaseResult;
    proposed: CaseResult;
    delta: CaseResult;
  }>;
  probabilities: {
    status: "available" | "omitted";
    reason: string | null;
    central: Partial<
      Record<
        "1m" | "3m",
        { current: ConditionalRange; proposed: ConditionalRange }
      >
    >;
  };
  coverage?: Record<string, unknown>;
  model_version?: string;
  facts?: SourcedFact[];
  evidence?: Evidence[];
  missing_evidence?: string[];
  confirmed_assumptions?: CaseGrid<ConfirmedShock>;
  price_provenance?: unknown;
};
export type ConditionalRange = {
  p10: number;
  p50: number;
  p90: number;
  probability_of_loss: number;
};
export type ScenarioRun = {
  run_id: string;
  portfolio_revision?: number | null;
  allocation_snapshot?: Portfolio | null;
  proposed_weights?: Record<string, number> | null;
  price_provenance?: Record<string, unknown> | null;
  price_window?: { start: string | null; end: string | null };
  created_at?: string;
  status:
    "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";
  last_error?: string | null;
  result?: ScenarioResult | null;
  sourced_facts?: SourcedFact[];
  evidence?: Evidence[];
  confirmed_shocks?: CaseGrid<ConfirmedShock>;
  allocation?: unknown;
};
export type RunMessage = {
  id: string;
  message: {
    role: "user";
    content: string;
    answer:
      | string
      | { content: string; citations?: { field: string; value: number }[] };
    revision_draft_id?: string;
  };
  created_at: string;
};

export const listTemplates = async (
  portfolioId: string,
  proposedSymbols: string[] = [],
) =>
  (
    await eventRequest<{ templates: EventTemplate[] }>(
      `/events/templates?portfolio_id=${encodeURIComponent(portfolioId)}${proposedSymbols.map((symbol) => `&proposed_symbol=${encodeURIComponent(symbol)}`).join("")}`,
    )
  ).templates;
export const createDraft = (
  body: {
    portfolio_id: string;
    portfolio_revision?: number;
    template_id: string;
    situation_id?: string;
    target_symbol?: string;
    description?: string;
    question?: string;
    proposed_weights?: Record<string, number>;
  },
  key: string,
) =>
  eventRequest<ScenarioDraft>("/scenarios/drafts", "POST", body, {
    idempotencyKey: key,
  });
export const getDraft = (id: string) =>
  eventRequest<ScenarioDraft>(`/scenarios/drafts/${encodeURIComponent(id)}`);
export const listDrafts = async (portfolioId: string) =>
  (
    await eventRequest<{ drafts: ScenarioDraft[] }>(
      `/scenarios/drafts?portfolio_id=${encodeURIComponent(portfolioId)}`,
    )
  ).drafts;
export const confirmDraft = (
  id: string,
  revision: number,
  confirmed_shocks: CaseGrid<ConfirmedShock>,
) =>
  eventRequest<ScenarioRun>(
    `/scenarios/drafts/${encodeURIComponent(id)}/confirm`,
    "POST",
    { revision, confirmed_shocks },
  );
export const getRun = (id: string) =>
  eventRequest<ScenarioRun>(`/scenarios/runs/${encodeURIComponent(id)}`);
export const listRuns = async (portfolioId: string) =>
  (
    await eventRequest<{ runs: ScenarioRun[] }>(
      `/scenarios/runs?portfolio_id=${encodeURIComponent(portfolioId)}`,
    )
  ).runs;
export const cancelDraft = (id: string) =>
  eventRequest<ScenarioDraft>(
    `/scenarios/drafts/${encodeURIComponent(id)}/cancel`,
    "POST",
  );
export const cancelRun = (id: string) =>
  eventRequest<ScenarioRun>(
    `/scenarios/runs/${encodeURIComponent(id)}/cancel`,
    "POST",
  );
export const listMessages = async (id: string) =>
  (
    await eventRequest<{ messages: RunMessage[] }>(
      `/scenarios/runs/${encodeURIComponent(id)}/messages`,
    )
  ).messages;
export const sendMessage = (id: string, content: string) =>
  eventRequest<{ message: RunMessage; revision_draft_id?: string | null }>(
    `/scenarios/runs/${encodeURIComponent(id)}/messages`,
    "POST",
    { content },
  );
