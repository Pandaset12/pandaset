import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  ArrowPath,
  Check,
  InformationCircle as Info,
} from "../components/icons";
import { AssetMark, Modal, PageHeading } from "../components/UI";
import {
  createRequestGuard,
  type Portfolio,
  type AnalysisResponse,
} from "../api/portfolio";
import type { PortfolioAsset } from "../types/portfolioAsset";
import {
  cancelDraft,
  cancelRun,
  confirmDraft,
  createDraft,
  getDraft,
  getSavedAnalysis,
  getRun,
  listDrafts,
  listMessages,
  listRuns,
  listTemplates,
  sendMessage,
  validPercentAllocation,
  type CaseGrid,
  type ConfirmedShock,
  type DraftProposal,
  type EventTemplate,
  type Evidence,
  type RunMessage,
  type ScenarioDraft,
  type ScenarioRun,
  type SavedAnalysis,
} from "../api/eventLab";

const cases = ["mild", "central", "severe"] as const;
const horizons = ["1m", "3m"] as const;
const factors = ["equity", "rates", "gold"] as const;
const MAX_POLL_FAILURES = 3;
const percentage = (value: number) => `${(value * 100).toFixed(1)}%`;
const signed = (value: number) => `${value > 0 ? "+" : ""}${percentage(value)}`;
const errorText = (cause: unknown) =>
  cause instanceof Error ? cause.message : "The event service is unavailable.";

function proposedToConfirmed(
  proposal: DraftProposal,
): CaseGrid<ConfirmedShock> {
  return Object.fromEntries(
    cases.map((kind) => [
      kind,
      Object.fromEntries(
        horizons.map((horizon) => {
          const item = proposal.proposed_shocks[kind][horizon];
          return [
            horizon,
            { factors: { ...item.factors }, issuers: { ...item.issuers } },
          ];
        }),
      ),
    ]),
  ) as CaseGrid<ConfirmedShock>;
}

export function revisionReviewState(revision: ScenarioDraft) {
  return {
    draft: revision,
    run: null,
    shocks:
      revision.status === "confirmed"
        ? (revision.confirmed_shocks ?? null)
        : revision.status === "ready" && revision.proposal?.proposed_shocks
          ? proposedToConfirmed(revision.proposal)
          : null,
  };
}

export function draftAllocationFromSnapshot(
  revision: ScenarioDraft,
  snapshot: SavedAnalysis,
) {
  if (
    !revision.request ||
    revision.request.analysis_id !== snapshot.analysis_id ||
    revision.request.portfolio_id !== snapshot.portfolio_id
  )
    return null;
  const baseline = snapshot.metrics.weights;
  const symbols = Object.keys(baseline);
  const proposed = revision.request.proposed_weights ?? baseline;
  if (
    !symbols.length ||
    Object.keys(proposed).length !== symbols.length ||
    !symbols.every(
      (symbol) =>
        Number.isFinite(baseline[symbol]) &&
        Number.isFinite(proposed[symbol]) &&
        symbol in proposed,
    )
  )
    return null;
  return {
    symbols,
    current: symbols.map((symbol) => baseline[symbol] * 100),
    proposed: symbols.map((symbol) => proposed[symbol] * 100),
  };
}

function shocksValid(
  shocks: CaseGrid<ConfirmedShock> | null,
  symbols: Set<string>,
) {
  if (!shocks) return false;
  return cases.every((kind) =>
    horizons.every((horizon) => {
      const shock = shocks[kind]?.[horizon];
      return (
        shock &&
        factors.every(
          (factor) =>
            Number.isFinite(shock.factors[factor]) &&
            Math.abs(shock.factors[factor]) <= 0.5,
        ) &&
        Object.keys(shock.factors).length === 3 &&
        Object.entries(shock.issuers).every(
          ([symbol, value]) =>
            symbols.has(symbol) &&
            Number.isFinite(value) &&
            Math.abs(value) <= 3,
        )
      );
    }),
  );
}

export function contributionSymbols(
  current: Record<string, number>,
  proposed: Record<string, number>,
): string[] {
  return [...new Set([...Object.keys(current), ...Object.keys(proposed)])];
}

function sourceLink(evidence: Evidence) {
  try {
    const url = new URL(evidence.source_url ?? "");
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export default function WhatIf({
  portfolio,
  analysis,
  analysisBusy,
  analysisError,
  onRefreshAnalysis,
  assets,
  weights,
  onApply,
  query,
}: {
  portfolio: Portfolio;
  analysis: AnalysisResponse | null;
  analysisBusy: boolean;
  analysisError: string;
  onRefreshAnalysis: () => void;
  assets: PortfolioAsset[];
  weights: number[];
  onApply: (weights: number[]) => Promise<boolean>;
  query: URLSearchParams;
}) {
  const [allocation, setAllocation] = useState(() => {
    const next = [...weights];
    const reduced = assets.findIndex(
      (asset) => asset.symbol === query.get("reduce"),
    );
    if (reduced >= 0 && assets.length > 1) {
      const recipient = reduced === 0 ? 1 : 0;
      const amount = Math.min(10, next[reduced]);
      next[reduced] -= amount;
      next[recipient] += amount;
    }
    return next;
  });
  const [templates, setTemplates] = useState<EventTemplate[]>([]);
  const [templatesBusy, setTemplatesBusy] = useState(true);
  const [templateError, setTemplateError] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [question, setQuestion] = useState("");
  const [draft, setDraft] = useState<ScenarioDraft | null>(null);
  const [run, setRun] = useState<ScenarioRun | null>(null);
  const [shocks, setShocks] = useState<CaseGrid<ConfirmedShock> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applyConfirm, setApplyConfirm] = useState(false);
  const [applying, setApplying] = useState(false);
  const [messages, setMessages] = useState<RunMessage[]>([]);
  const [messageText, setMessageText] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const chatRequest = useRef(createRequestGuard());
  const selectionGeneration = useRef(0);
  const [draftAnalysis, setDraftAnalysis] = useState<SavedAnalysis | null>(
    null,
  );
  const [draftAnalysisBusy, setDraftAnalysisBusy] = useState(false);
  const [draftAnalysisError, setDraftAnalysisError] = useState("");
  const [draftAnalysisRetry, setDraftAnalysisRetry] = useState(0);
  const [draftPollFailures, setDraftPollFailures] = useState(0);
  const [runPollFailures, setRunPollFailures] = useState(0);
  const [savedRuns, setSavedRuns] = useState<ScenarioRun[]>([]);
  const [savedDrafts, setSavedDrafts] = useState<ScenarioDraft[]>([]);
  const [draftListBusy, setDraftListBusy] = useState(true);
  const [draftListError, setDraftListError] = useState("");
  const [runListBusy, setRunListBusy] = useState(true);
  const [runListError, setRunListError] = useState("");
  const pinnedAllocation =
    draft && draftAnalysis
      ? draftAllocationFromSnapshot(draft, draftAnalysis)
      : null;
  const editorAssets = draft
    ? (pinnedAllocation?.symbols.map(
        (symbol, index) =>
          assets.find((asset) => asset.symbol === symbol) ?? {
            symbol,
            name: symbol,
            short: symbol,
            sector: null,
            color: ["#39734f", "#38638a", "#a7473f"][index % 3],
            description: null,
            thesis: null,
            watch: null,
            source: null,
          },
      ) ?? [])
    : assets;
  const editorCurrent = draft ? (pinnedAllocation?.current ?? []) : weights;
  const editorProposed = draft
    ? (pinnedAllocation?.proposed ?? [])
    : allocation;
  const total = editorProposed.reduce((sum, weight) => sum + weight, 0);
  const validAllocation =
    allocation.length === assets.length && validPercentAllocation(allocation);
  const validDisplayedAllocation = draft
    ? Boolean(pinnedAllocation)
    : validAllocation;
  const changedAllocation = allocation.some(
    (weight, index) => Math.abs(weight - weights[index]) > 0.000001,
  );
  const selectedTemplate = templates.find(
    (item) => item.template_id === templateId,
  );
  const proposal =
    draft?.status === "ready" || draft?.status === "confirmed"
      ? draft.proposal
      : null;
  const validShocks = shocksValid(
    shocks,
    new Set(
      draft
        ? (pinnedAllocation?.symbols ?? [])
        : assets.map((asset) => asset.symbol),
    ),
  );

  useEffect(() => {
    const analysisId = draft?.request?.analysis_id;
    if (!analysisId) {
      setDraftAnalysis(null);
      setDraftAnalysisError("");
      setDraftAnalysisBusy(false);
      return;
    }
    let cancelled = false;
    setDraftAnalysis(null);
    setDraftAnalysisBusy(true);
    setDraftAnalysisError("");
    void getSavedAnalysis(portfolio.portfolio_id, analysisId)
      .then((saved) => {
        if (!cancelled) setDraftAnalysis(saved);
      })
      .catch((cause) => {
        if (!cancelled) setDraftAnalysisError(errorText(cause));
      })
      .finally(() => {
        if (!cancelled) setDraftAnalysisBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    portfolio.portfolio_id,
    draft?.draft_id,
    draft?.request?.analysis_id,
    draftAnalysisRetry,
  ]);

  useEffect(() => {
    let cancelled = false;
    setTemplatesBusy(true);
    setTemplateError("");
    void listTemplates(portfolio.portfolio_id)
      .then((found) => {
        if (cancelled) return;
        setTemplates(found);
        setTemplateId((old) =>
          found.some((item) => item.template_id === old)
            ? old
            : (found[0]?.template_id ?? ""),
        );
      })
      .catch((cause) => {
        if (!cancelled) setTemplateError(errorText(cause));
      })
      .finally(() => {
        if (!cancelled) setTemplatesBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [portfolio.portfolio_id]);

  useEffect(() => {
    let cancelled = false;
    setRunListBusy(true);
    setRunListError("");
    void listRuns(portfolio.portfolio_id)
      .then((found) => {
        if (!cancelled) setSavedRuns(found);
      })
      .catch((cause) => {
        if (!cancelled) setRunListError(errorText(cause));
      })
      .finally(() => {
        if (!cancelled) setRunListBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [portfolio.portfolio_id]);

  useEffect(() => {
    let cancelled = false;
    setDraftListBusy(true);
    setDraftListError("");
    void listDrafts(portfolio.portfolio_id)
      .then((found) => {
        if (!cancelled) setSavedDrafts(found);
      })
      .catch((cause) => {
        if (!cancelled) setDraftListError(errorText(cause));
      })
      .finally(() => {
        if (!cancelled) setDraftListBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [portfolio.portfolio_id]);

  useEffect(() => {
    if (
      !draft ||
      !["pending", "queued", "running"].includes(draft.status) ||
      draftPollFailures >= MAX_POLL_FAILURES
    )
      return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getDraft(draft.draft_id)
        .then((next) => {
          if (cancelled) return;
          setDraftPollFailures(0);
          setDraft(next);
          setSavedDrafts((old) =>
            old.map((item) => (item.draft_id === next.draft_id ? next : item)),
          );
          if (next.status === "ready" && next.proposal?.proposed_shocks)
            setShocks(proposedToConfirmed(next.proposal));
        })
        .catch((cause) => {
          if (!cancelled) {
            setError(errorText(cause));
            setDraftPollFailures((count) => count + 1);
          }
        });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [draft, draftPollFailures]);

  useEffect(() => {
    if (
      !run ||
      !["pending", "queued", "running"].includes(run.status) ||
      runPollFailures >= MAX_POLL_FAILURES
    )
      return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getRun(run.run_id)
        .then((next) => {
          if (!cancelled) {
            setRunPollFailures(0);
            setRun(next);
          }
        })
        .catch((cause) => {
          if (!cancelled) {
            setError(errorText(cause));
            setRunPollFailures((count) => count + 1);
          }
        });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [run, runPollFailures]);

  useEffect(() => {
    if (run?.status !== "completed") return;
    let cancelled = false;
    void listMessages(run.run_id)
      .then((found) => {
        if (!cancelled) setMessages(found);
      })
      .catch((cause) => {
        if (!cancelled) setError(errorText(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [run?.run_id, run?.status]);

  useEffect(() => {
    if (!run || !["completed", "failed", "cancelled"].includes(run.status))
      return;
    void listRuns(portfolio.portfolio_id)
      .then(setSavedRuns)
      .catch(() => undefined);
  }, [run?.run_id, run?.status, portfolio.portfolio_id]);

  function updateShock(
    kind: (typeof cases)[number],
    horizon: (typeof horizons)[number],
    group: "factors" | "issuers",
    key: string,
    text: string,
  ) {
    const value =
      text === "" ? Number.NaN : Number(text) / (group === "factors" ? 100 : 1);
    setShocks((previous) =>
      previous
        ? {
            ...previous,
            [kind]: {
              ...previous[kind],
              [horizon]: {
                ...previous[kind][horizon],
                [group]: { ...previous[kind][horizon][group], [key]: value },
              },
            },
          }
        : previous,
    );
  }

  function openDraft(item: ScenarioDraft) {
    if (busy) return;
    selectionGeneration.current += 1;
    chatRequest.current.invalidate();
    setChatBusy(false);
    setMessages([]);
    const review = revisionReviewState(item);
    setRun(review.run);
    setDraft(review.draft);
    setShocks(review.shocks);
    setDraftPollFailures(0);
    setTemplateId(item.request?.template_id ?? templateId);
    setQuestion(item.request?.question ?? "");
    setError("");
  }

  async function startDraft() {
    if (!analysis || !templateId || !validAllocation || busy) return;
    selectionGeneration.current += 1;
    setBusy(true);
    setError("");
    setRun(null);
    chatRequest.current.invalidate();
    setDraftPollFailures(0);
    setRunPollFailures(0);
    setDraft(null);
    setShocks(null);
    setMessages([]);
    try {
      const next = await createDraft(
        {
          portfolio_id: portfolio.portfolio_id,
          analysis_id: analysis.analysis_id,
          template_id: templateId,
          ...(question.trim() ? { question: question.trim() } : {}),
          ...(changedAllocation
            ? {
                proposed_weights: Object.fromEntries(
                  assets.map((asset, index) => [
                    asset.symbol,
                    allocation[index] / 100,
                  ]),
                ),
              }
            : {}),
        },
        crypto.randomUUID(),
      );
      setDraft(next);
      setSavedDrafts((old) => [
        next,
        ...old.filter((item) => item.draft_id !== next.draft_id),
      ]);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    const confirmed =
      draft?.status === "confirmed" ? draft.confirmed_shocks : shocks;
    if (!draft || draft.revision === null || !confirmed || !validShocks || busy)
      return;
    const targetDraftId = draft.draft_id;
    const generation = selectionGeneration.current;
    setBusy(true);
    setError("");
    try {
      const next = await confirmDraft(targetDraftId, draft.revision, confirmed);
      if (generation !== selectionGeneration.current) return;
      setRunPollFailures(0);
      setRun(next);
      setDraft((current) =>
        current?.draft_id === targetDraftId
          ? { ...current, status: "confirmed", confirmed_shocks: confirmed }
          : current,
      );
      setSavedDrafts((old) =>
        old.map((item) =>
          item.draft_id === targetDraftId
            ? { ...item, status: "confirmed", confirmed_shocks: confirmed }
            : item,
        ),
      );
    } catch (cause) {
      if (generation !== selectionGeneration.current) return;
      setError(errorText(cause));
      void getDraft(targetDraftId)
        .then((updated) => {
          if (generation !== selectionGeneration.current) return;
          setDraft(updated);
          setSavedDrafts((old) =>
            old.map((item) =>
              item.draft_id === updated.draft_id ? updated : item,
            ),
          );
          if (updated.status === "confirmed")
            setShocks(updated.confirmed_shocks ?? null);
        })
        .catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  async function stopJob() {
    setBusy(true);
    setError("");
    try {
      if (run && ["pending", "queued", "running"].includes(run.status))
        setRun(await cancelRun(run.run_id));
      else if (draft) setDraft(await cancelDraft(draft.draft_id));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!run || run.status !== "completed" || !messageText.trim() || chatBusy)
      return;
    const request = chatRequest.current.begin();
    const targetRun = run;
    setChatBusy(true);
    setError("");
    try {
      const sent = await sendMessage(targetRun.run_id, messageText.trim());
      if (!chatRequest.current.isCurrent(request)) return;
      setMessageText("");
      if (sent.revision_draft_id) {
        const revision = await getDraft(sent.revision_draft_id);
        if (!chatRequest.current.isCurrent(request)) return;
        setSavedRuns((old) =>
          old.some((item) => item.run_id === targetRun.run_id)
            ? old
            : [targetRun, ...old],
        );
        selectionGeneration.current += 1;
        const review = revisionReviewState(revision);
        setRun(review.run);
        setDraft(review.draft);
        setSavedDrafts((old) => [
          revision,
          ...old.filter((item) => item.draft_id !== revision.draft_id),
        ]);
        setShocks(review.shocks);
        setDraftPollFailures(0);
        setTemplateId(revision.request?.template_id ?? templateId);
        setQuestion(revision.request?.question ?? "");
        setMessages([]);
      } else {
        const latest = await listMessages(targetRun.run_id);
        if (chatRequest.current.isCurrent(request)) setMessages(latest);
      }
    } catch (cause) {
      if (chatRequest.current.isCurrent(request)) setError(errorText(cause));
    } finally {
      if (chatRequest.current.isCurrent(request)) setChatBusy(false);
    }
  }

  const displayFacts = proposal?.facts ?? run?.result?.facts ?? [];
  const evidence = proposal?.evidence ?? run?.result?.evidence ?? [];
  const results = run?.status === "completed" ? run.result : null;
  const appliedWeights =
    results?.proposed_weights &&
    Object.keys(results.proposed_weights).length === assets.length &&
    assets.every((asset) => asset.symbol in results.proposed_weights!)
      ? assets.map((asset) => results.proposed_weights![asset.symbol] * 100)
      : null;
  const canApply =
    appliedWeights &&
    appliedWeights.some(
      (weight, index) => Math.abs(weight - weights[index]) > 0.000001,
    );

  return (
    <>
      <PageHeading
        title="What-if lab"
        description="Explore a hypothetical event using your saved holdings and a dated analysis snapshot."
      >
        <span className="scenario-badge">
          <span />
          Hypothetical, not a forecast
        </span>
      </PageHeading>
      {!analysis && (
        <div className="api-state" role={analysisError ? "alert" : "status"}>
          <strong>
            {analysisBusy
              ? "Loading saved analysis…"
              : "Analysis unavailable for new scenarios."}
          </strong>
          <p>
            {analysisError ||
              "Saved runs and chat remain available below. Create an analysis to research a new event."}
          </p>
          <button
            className="button subtle"
            disabled={analysisBusy}
            onClick={onRefreshAnalysis}
          >
            Create analysis
          </button>
        </div>
      )}
      <div className="event-lab-grid">
        <section className="event-panel" aria-labelledby="allocation-title">
          <div className="eyebrow">01 / PORTFOLIO</div>
          <h2 id="allocation-title">Compare allocations</h2>
          <p>
            Adjust your saved holdings to compare the same event against a
            proposed allocation. Changes stay in this draft until you apply
            them.
          </p>
          <div className="event-allocation-head">
            <span>Holding</span>
            <span>Current</span>
            <span>Proposed</span>
          </div>
          {draft && !pinnedAllocation && (
            <div
              className="api-state"
              role={draftAnalysisError ? "alert" : "status"}
            >
              <p>
                {draftAnalysisError ||
                  (draftAnalysisBusy || !draft.request
                    ? "Loading the saved allocation for this draft…"
                    : "The saved allocation for this draft could not be reconciled.")}
              </p>
              {draftAnalysisError && (
                <button
                  className="button subtle"
                  onClick={() => setDraftAnalysisRetry((count) => count + 1)}
                >
                  Retry saved allocation
                </button>
              )}
            </div>
          )}
          {editorAssets.map((asset, index) => (
            <div className="event-allocation-row" key={asset.symbol}>
              <span className="event-holding">
                <AssetMark asset={asset} small />
                <strong>{asset.symbol}</strong>
              </span>
              <span>{editorCurrent[index].toFixed(2)}%</span>
              <label>
                <span className="sr-only">
                  {asset.symbol} proposed allocation
                </span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.000001"
                  value={editorProposed[index]}
                  disabled={Boolean(draft) || busy}
                  aria-invalid={
                    !Number.isFinite(editorProposed[index]) ||
                    editorProposed[index] < 0 ||
                    editorProposed[index] > 100
                  }
                  onChange={(event) =>
                    setAllocation((old) =>
                      old.map((value, i) =>
                        i === index ? Number(event.target.value) : value,
                      ),
                    )
                  }
                />
                <span>%</span>
              </label>
            </div>
          ))}
          {(!draft || pinnedAllocation) && (
            <div
              className={`allocation-total ${validDisplayedAllocation ? "valid" : "invalid"}`}
              aria-live="polite"
            >
              <span>Total allocation</span>
              <strong>{total.toFixed(2)}%</strong>
            </div>
          )}
          {!draft && !validAllocation && (
            <p className="field-error" role="alert">
              Allocations must total 100%, with each holding between 0% and
              100%.
            </p>
          )}
          <button
            className="text-button"
            disabled={Boolean(draft) || busy}
            onClick={() => setAllocation([...weights])}
          >
            Reset allocation
          </button>
          {draft && (
            <p className="event-note">
              This draft is pinned to the allocation shown above. Start a new
              draft to use other weights.
            </p>
          )}
        </section>

        <section className="event-panel" aria-labelledby="event-title">
          <div className="eyebrow">02 / EVENT</div>
          <h2 id="event-title">Choose an event</h2>
          {templatesBusy ? (
            <p role="status">Loading curated events…</p>
          ) : templateError ? (
            <div className="api-state" role="alert">
              <p>{templateError}</p>
              <button
                className="button subtle"
                onClick={() => {
                  setTemplatesBusy(true);
                  void listTemplates(portfolio.portfolio_id)
                    .then((found) => {
                      setTemplates(found);
                      setTemplateId(found[0]?.template_id ?? "");
                      setTemplateError("");
                    })
                    .catch((cause) => setTemplateError(errorText(cause)))
                    .finally(() => setTemplatesBusy(false));
                }}
              >
                Retry events
              </button>
            </div>
          ) : templates.length === 0 ? (
            <p>No curated events are available for these holdings.</p>
          ) : (
            <div
              className="event-template-list"
              role="radiogroup"
              aria-label="Curated events"
            >
              {templates.map((item) => (
                <label
                  key={item.template_id}
                  className={templateId === item.template_id ? "selected" : ""}
                >
                  <input
                    type="radio"
                    name="event-template"
                    value={item.template_id}
                    checked={templateId === item.template_id}
                    disabled={Boolean(draft) || busy}
                    onChange={() => setTemplateId(item.template_id)}
                  />
                  <span>
                    <small>
                      {item.category.toUpperCase()} · VERSION {item.version}
                    </small>
                    <strong>{item.title}</strong>
                    <em>{item.description}</em>
                  </span>
                </label>
              ))}
            </div>
          )}
          <label className="event-question">
            Context or question{" "}
            <textarea
              value={question}
              maxLength={1000}
              rows={3}
              disabled={Boolean(draft) || busy}
              placeholder="What would you like to explore?"
              onChange={(event) => setQuestion(event.target.value)}
            />
          </label>
          <button
            className="button dark full"
            disabled={
              !analysis ||
              !selectedTemplate ||
              !validAllocation ||
              busy ||
              Boolean(draft)
            }
            onClick={() => void startDraft()}
          >
            {busy ? "Starting…" : "Research this event"}
            <ArrowRight size={16} />
          </button>
        </section>
      </div>

      <section
        className="event-saved-runs"
        aria-labelledby="saved-drafts-title"
      >
        <div>
          <div className="eyebrow">SAVED WORK</div>
          <h2 id="saved-drafts-title">Drafts</h2>
        </div>
        {draftListBusy ? (
          <p role="status">Loading saved drafts…</p>
        ) : draftListError ? (
          <p role="alert">{draftListError}</p>
        ) : savedDrafts.length === 0 ? (
          <p>No saved drafts yet.</p>
        ) : (
          <div className="event-run-list">
            {savedDrafts
              .filter((item) =>
                [
                  "pending",
                  "queued",
                  "running",
                  "ready",
                  "failed",
                  "cancelled",
                  "confirmed",
                ].includes(item.status),
              )
              .map((item) => (
                <button
                  key={item.draft_id}
                  className={
                    draft?.draft_id === item.draft_id ? "selected" : ""
                  }
                  disabled={chatBusy || busy}
                  onClick={() => openDraft(item)}
                >
                  <strong>Draft {item.status}</strong>
                  <small>
                    {item.created_at
                      ? new Date(item.created_at).toLocaleString()
                      : item.draft_id}
                  </small>
                </button>
              ))}
          </div>
        )}
        {draft && (
          <button
            className="text-button"
            disabled={busy || chatBusy}
            onClick={() => {
              selectionGeneration.current += 1;
              setDraft(null);
              setShocks(null);
              setAllocation([...weights]);
            }}
          >
            Close draft view
          </button>
        )}
      </section>

      <section className="event-saved-runs" aria-labelledby="saved-runs-title">
        <div>
          <div className="eyebrow">SAVED SCENARIOS</div>
          <h2 id="saved-runs-title">Past runs</h2>
        </div>
        {runListBusy ? (
          <p role="status">Loading saved runs…</p>
        ) : runListError ? (
          <p role="alert">{runListError}</p>
        ) : savedRuns.length === 0 ? (
          <p>No saved runs yet.</p>
        ) : (
          <div className="event-run-list">
            {savedRuns.map((item) => (
              <button
                key={item.run_id}
                className={run?.run_id === item.run_id ? "selected" : ""}
                disabled={chatBusy || busy}
                onClick={() => {
                  if (busy) return;
                  selectionGeneration.current += 1;
                  chatRequest.current.invalidate();
                  setChatBusy(false);
                  setMessages([]);
                  setDraft(null);
                  setShocks(null);
                  setRunPollFailures(0);
                  setRun(item);
                  setError("");
                }}
              >
                <strong>
                  {item.status === "completed"
                    ? "Completed event run"
                    : `Run ${item.status}`}
                </strong>
                <small>
                  {item.created_at
                    ? new Date(item.created_at).toLocaleString()
                    : item.run_id}
                </small>
              </button>
            ))}
          </div>
        )}
      </section>

      {draft && (
        <section className="event-stage" aria-labelledby="draft-title">
          <div className="event-stage-heading">
            <div>
              <div className="eyebrow">03 / RESEARCH & REVIEW</div>
              <h2 id="draft-title">Review proposed assumptions</h2>
            </div>
            <span className="label-chip" role="status">
              Draft {draft.status}
            </span>
          </div>
          {["pending", "queued", "running"].includes(draft.status) && (
            <div className="api-state" role="status">
              <ArrowPath className="spin" size={18} />
              <p>
                Researching evidence and preparing six hypothetical cases. This
                may take a moment.
              </p>
              <button
                className="button subtle"
                disabled={busy}
                onClick={() => void stopJob()}
              >
                Cancel draft
              </button>
              {draftPollFailures >= MAX_POLL_FAILURES && (
                <button
                  className="button subtle"
                  onClick={() => {
                    setError("");
                    setDraftPollFailures(0);
                  }}
                >
                  Retry draft status
                </button>
              )}
            </div>
          )}
          {draft.status === "failed" && (
            <div className="api-state" role="alert">
              <p>{draft.last_error || "The draft could not be prepared."}</p>
              <button
                className="button subtle"
                onClick={() => {
                  setDraft(null);
                  setShocks(null);
                }}
              >
                Start another draft
              </button>
            </div>
          )}
          {draft.status === "cancelled" && (
            <div className="api-state">
              <p>Draft cancelled.</p>
              <button
                className="button subtle"
                onClick={() => {
                  setDraft(null);
                  setShocks(null);
                }}
              >
                Start another draft
              </button>
            </div>
          )}
          {proposal && (
            <>
              <EvidenceSection
                facts={displayFacts}
                evidence={evidence}
                missing={proposal.missing_evidence ?? []}
              />
              <div className="event-assumptions">
                <h3>
                  {draft.status === "confirmed"
                    ? "Confirmed shocks"
                    : "Proposed shocks"}
                </h3>
                <p>
                  These numbers are hypothetical assumptions. Factor changes are
                  cumulative returns; issuer changes are multiples of residual
                  volatility. Review every case and horizon before confirming.
                </p>
                {draft.status === "confirmed" && !run && (
                  <p role="status">
                    These assumptions were confirmed. Resume the saved
                    calculation to see its result.
                  </p>
                )}
                <div className="event-shock-grid">
                  {cases.map((kind) =>
                    horizons.map((horizon) => {
                      const proposed = proposal.proposed_shocks[kind][horizon];
                      const current = shocks?.[kind]?.[horizon];
                      return (
                        <fieldset
                          key={`${kind}-${horizon}`}
                          className="event-shock-cell"
                        >
                          <legend>
                            {kind[0].toUpperCase() + kind.slice(1)} ·{" "}
                            {horizon === "1m" ? "1 month" : "3 months"}
                          </legend>
                          <p>{proposed.rationale}</p>
                          <small>
                            Evidence: {proposed.evidence_ids.join(", ")}
                          </small>
                          <div className="event-shock-fields">
                            {factors.map((factor) => (
                              <label key={factor}>
                                {factor}{" "}
                                <span>
                                  <input
                                    type="number"
                                    step="0.1"
                                    min="-50"
                                    max="50"
                                    value={
                                      Number.isNaN(current?.factors[factor])
                                        ? ""
                                        : (current?.factors[factor] ?? 0) * 100
                                    }
                                    aria-label={`${kind} ${horizon} ${factor} factor shock, percent`}
                                    disabled={
                                      Boolean(run) ||
                                      busy ||
                                      draft.status === "confirmed"
                                    }
                                    onChange={(event) =>
                                      updateShock(
                                        kind,
                                        horizon,
                                        "factors",
                                        factor,
                                        event.target.value,
                                      )
                                    }
                                  />
                                  %
                                </span>
                              </label>
                            ))}
                            {Object.keys(proposed.issuers).map((symbol) => (
                              <label key={symbol}>
                                {symbol} issuer{" "}
                                <span>
                                  <input
                                    type="number"
                                    step="0.1"
                                    min="-3"
                                    max="3"
                                    value={
                                      Number.isNaN(current?.issuers[symbol])
                                        ? ""
                                        : (current?.issuers[symbol] ?? 0)
                                    }
                                    aria-label={`${kind} ${horizon} ${symbol} issuer shock, residual sigma multiples`}
                                    disabled={
                                      Boolean(run) ||
                                      busy ||
                                      draft.status === "confirmed"
                                    }
                                    onChange={(event) =>
                                      updateShock(
                                        kind,
                                        horizon,
                                        "issuers",
                                        symbol,
                                        event.target.value,
                                      )
                                    }
                                  />
                                  × σ
                                </span>
                              </label>
                            ))}
                          </div>
                        </fieldset>
                      );
                    }),
                  )}
                </div>
                {pinnedAllocation && !validShocks && (
                  <p className="field-error" role="alert">
                    Review all six cases. Factor shocks must be within ±50%, and
                    issuer shocks within ±3 residual standard deviations.
                  </p>
                )}
                {!run && (
                  <button
                    className="button dark"
                    disabled={!validShocks || busy}
                    onClick={() => void confirm()}
                  >
                    {busy
                      ? "Confirming…"
                      : draft.status === "confirmed"
                        ? "Resume confirmed run"
                        : "Confirm all assumptions and calculate"}
                    <Check size={16} />
                  </button>
                )}
              </div>
            </>
          )}
        </section>
      )}

      {run && (
        <section className="event-stage" aria-labelledby="run-title">
          <div className="event-stage-heading">
            <div>
              <div className="eyebrow">04 / RESULTS</div>
              <h2 id="run-title">Calculated cases</h2>
            </div>
            <span className="label-chip" role="status">
              Run {run.status}
            </span>
          </div>
          {["pending", "queued", "running"].includes(run.status) && (
            <div className="api-state" role="status">
              <ArrowPath className="spin" size={18} />
              <p>Calculating confirmed cases from the saved price snapshot.</p>
              <button
                className="button subtle"
                disabled={busy}
                onClick={() => void stopJob()}
              >
                Cancel run
              </button>
              {runPollFailures >= MAX_POLL_FAILURES && (
                <button
                  className="button subtle"
                  onClick={() => {
                    setError("");
                    setRunPollFailures(0);
                  }}
                >
                  Retry run status
                </button>
              )}
            </div>
          )}
          {run.status === "failed" && (
            <div className="api-state" role="alert">
              {run.last_error || "Calculation failed."}
            </div>
          )}
          {run.status === "cancelled" && (
            <div className="api-state">Run cancelled.</div>
          )}
          {results && (
            <>
              <EvidenceSection
                facts={results.facts ?? []}
                evidence={results.evidence ?? []}
                missing={results.missing_evidence ?? []}
              />
              <p>
                Hypothetical estimated returns, conditional on the confirmed
                shocks. Both allocations use the same event cases and saved
                price snapshot.
              </p>
              <div className="event-table-wrap">
                <table className="event-results-table">
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>Horizon</th>
                      <th>Current</th>
                      <th>Proposed</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.cases.map((item) => (
                      <tr key={`${item.case}-${item.horizon}`}>
                        <th>{item.case}</th>
                        <td>{item.horizon}</td>
                        <td>{signed(item.current.estimated_return)}</td>
                        <td>{signed(item.proposed.estimated_return)}</td>
                        <td>{signed(item.delta.estimated_return)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details className="event-details">
                <summary>Holding contributions</summary>
                {results.cases.map((item) => (
                  <div key={`${item.case}-${item.horizon}`}>
                    <strong>
                      {item.case} · {item.horizon}
                    </strong>
                    <ul>
                      {contributionSymbols(
                        item.current.holding_contributions,
                        item.proposed.holding_contributions,
                      ).map((symbol) => (
                        <li key={symbol}>
                          {symbol}: current{" "}
                          {item.current.holding_contributions[symbol] ===
                          undefined
                            ? "Unavailable"
                            : signed(
                                item.current.holding_contributions[symbol],
                              )}
                          , proposed{" "}
                          {item.proposed.holding_contributions[symbol] ===
                          undefined
                            ? "Unavailable"
                            : signed(
                                item.proposed.holding_contributions[symbol],
                              )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </details>
              <section className="event-result-block">
                <h3>Confirmed assumptions</h3>
                <p>
                  The following factor returns and issuer residual shocks were
                  confirmed before calculation.
                </p>
                <div className="event-confirmed-grid">
                  {cases.map((kind) =>
                    horizons.map((horizon) => {
                      const confirmed =
                        results.confirmed_assumptions?.[kind]?.[horizon] ??
                        shocks?.[kind]?.[horizon];
                      return (
                        <div key={`${kind}-${horizon}`}>
                          <strong>
                            {kind} · {horizon}
                          </strong>
                          <p>
                            {confirmed
                              ? factors
                                  .map(
                                    (factor) =>
                                      `${factor}: ${signed(confirmed.factors[factor])}`,
                                  )
                                  .join(" · ")
                              : "Unavailable"}
                          </p>
                          {confirmed &&
                            Object.keys(confirmed.issuers).length > 0 && (
                              <p>
                                Issuer shocks:{" "}
                                {Object.entries(confirmed.issuers)
                                  .map(
                                    ([symbol, value]) =>
                                      `${symbol}: ${value}× σ`,
                                  )
                                  .join(" · ")}
                              </p>
                            )}
                        </div>
                      );
                    }),
                  )}
                </div>
              </section>
              <section className="event-result-block">
                <h3>Conditional central-case ranges</h3>
                {results.probabilities?.status === "available" ? (
                  <>
                    <p>
                      Outcomes given the confirmed central shocks. These are not
                      odds that the event occurs.
                    </p>
                    <div className="event-table-wrap">
                      <table className="event-results-table">
                        <thead>
                          <tr>
                            <th>Horizon</th>
                            <th>Allocation</th>
                            <th>10th</th>
                            <th>Median</th>
                            <th>90th</th>
                            <th>Loss chance</th>
                          </tr>
                        </thead>
                        <tbody>
                          {horizons.flatMap((horizon) =>
                            (["current", "proposed"] as const).map(
                              (allocationType) => {
                                const range =
                                  results.probabilities.central[horizon]?.[
                                    allocationType
                                  ];
                                return range ? (
                                  <tr key={`${horizon}-${allocationType}`}>
                                    <th>{horizon}</th>
                                    <td>{allocationType}</td>
                                    <td>{signed(range.p10)}</td>
                                    <td>{signed(range.p50)}</td>
                                    <td>{signed(range.p90)}</td>
                                    <td>
                                      {percentage(range.probability_of_loss)}
                                    </td>
                                  </tr>
                                ) : null;
                              },
                            ),
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <p role="status">
                    Conditional ranges unavailable:{" "}
                    {results.probabilities?.reason?.replaceAll("_", " ") ||
                      "coverage or calibration requirements were not met"}
                    .
                  </p>
                )}
              </section>
              <section className="event-result-block">
                <h3>Coverage and provenance</h3>
                <dl className="event-provenance">
                  <div>
                    <dt>Model</dt>
                    <dd>{results.model_version ?? "Unavailable"}</dd>
                  </div>
                  <div>
                    <dt>Aligned observations</dt>
                    <dd>
                      {String(
                        results.coverage?.aligned_observations ?? "Unavailable",
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Analysis snapshot</dt>
                    <dd>
                      {run.analysis_id ?? results.analysis_id ?? "Unavailable"}
                    </dd>
                  </div>
                  <div>
                    <dt>Price provenance</dt>
                    <dd>
                      {results.price_provenance
                        ? `${Object.keys(results.price_provenance).length} saved provider records`
                        : "Unavailable"}
                    </dd>
                  </div>
                </dl>
                <p>
                  <Info size={15} /> Price and allocation snapshots are fixed
                  for this run. No trades are placed.
                </p>
              </section>
              {canApply && (
                <button
                  className="button dark"
                  onClick={() => setApplyConfirm(true)}
                >
                  Use proposed allocation
                  <ArrowRight size={16} />
                </button>
              )}
            </>
          )}
        </section>
      )}

      {run?.status === "completed" && (
        <section className="event-stage" aria-labelledby="chat-title">
          <div className="eyebrow">05 / DISCUSS</div>
          <h2 id="chat-title">Discuss this run</h2>
          <p>
            Questions are answered from saved evidence and calculations. A
            requested change creates a new draft for review.
          </p>
          <div className="event-chat-log" aria-live="polite">
            {messages.length === 0 ? (
              <p>No messages yet. Ask about a result or source.</p>
            ) : (
              messages.map((record) => (
                <div key={record.id}>
                  <article className="event-chat-message user">
                    <strong>You</strong>
                    <p>{record.message.content}</p>
                  </article>
                  <article className="event-chat-message assistant">
                    <strong>PandaSet</strong>
                    <p>
                      {typeof record.message.answer === "string"
                        ? record.message.answer
                        : record.message.answer.content}
                    </p>
                  </article>
                </div>
              ))
            )}
          </div>
          <form
            className="event-chat-form"
            onSubmit={(event) => void submitMessage(event)}
          >
            <label htmlFor="event-chat-input">Your question</label>
            <div>
              <input
                id="event-chat-input"
                value={messageText}
                maxLength={2000}
                disabled={chatBusy}
                onChange={(event) => setMessageText(event.target.value)}
                placeholder="What drives the central case?"
              />
              <button
                className="button dark"
                disabled={chatBusy || !messageText.trim()}
              >
                {chatBusy ? "Sending…" : "Send"}
              </button>
            </div>
          </form>
        </section>
      )}

      {error && (
        <div className="api-state" role="alert">
          <strong>Event request failed.</strong>
          <p>{error}</p>
          <button className="button subtle" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}
      {applyConfirm && appliedWeights && (
        <Modal
          title="Use the proposed allocation?"
          onClose={applying ? () => undefined : () => setApplyConfirm(false)}
        >
          <p>
            This updates your saved portfolio weights and creates a new analysis
            snapshot. Existing event runs keep their original allocation and
            prices.
          </p>
          <div className="modal-actions">
            <button
              className="button subtle"
              disabled={applying}
              onClick={() => setApplyConfirm(false)}
            >
              Keep exploring
            </button>
            <button
              className="button dark"
              disabled={applying}
              onClick={() => {
                setApplying(true);
                void onApply(appliedWeights)
                  .then((ok) => {
                    if (ok) setApplyConfirm(false);
                  })
                  .finally(() => setApplying(false));
              }}
            >
              {applying ? "Applying…" : "Apply allocation"}
              <Check size={16} />
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function EvidenceSection({
  facts,
  evidence,
  missing,
}: {
  facts: { claim: string; evidence_ids: string[] }[];
  evidence: Evidence[];
  missing: string[];
}) {
  const byId = new Map(evidence.map((item) => [item.evidence_id, item]));
  return (
    <div className="event-evidence">
      <h3>Sourced facts</h3>
      {facts.length ? (
        <ul>
          {facts.map((fact, index) => (
            <li key={`${fact.claim}-${index}`}>
              <p>{fact.claim}</p>
              <small>
                Sources:{" "}
                {fact.evidence_ids
                  .map((id) => byId.get(id)?.title ?? id)
                  .join(", ")}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <p>No sourced facts were available for this draft.</p>
      )}
      <details>
        <summary>Evidence and missing sources</summary>
        <ul>
          {evidence.map((item) => (
            <li key={item.evidence_id}>
              <strong>{item.title ?? item.evidence_id}</strong> · {item.status}
              {item.published_at ? ` · published ${item.published_at}` : ""}
              {item.retrieved_at ? ` · retrieved ${item.retrieved_at}` : ""}
              {sourceLink(item) && (
                <a href={sourceLink(item)!} target="_blank" rel="noreferrer">
                  Open source
                </a>
              )}
            </li>
          ))}
        </ul>
        {missing.length > 0 && <p>Missing evidence: {missing.join(", ")}</p>}
      </details>
    </div>
  );
}
