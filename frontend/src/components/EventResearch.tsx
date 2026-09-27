import { useEffect, useMemo, useState } from "react";
import {
  confirmDraft,
  createDraft,
  getDraft,
  getRun,
  listDrafts,
  listRuns,
  listTemplates,
  sendMessage,
  type CaseGrid,
  type ConfirmedShock,
  type EventTemplate,
  type ScenarioDraft,
  type ScenarioRun,
} from "../api/eventLab";

const cases = ["mild", "central", "severe"] as const;
const horizons = ["1m", "3m"] as const;
const factors = ["equity", "rates", "gold"] as const;
const message = (cause: unknown) =>
  cause instanceof Error ? cause.message : "Event research is unavailable.";
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
export const eventResearchApi = {
  confirmDraft,
  createDraft,
  getDraft,
  getRun,
  listDrafts,
  listRuns,
  listTemplates,
  sendMessage,
};

export function proposedShocks(
  draft: ScenarioDraft,
): CaseGrid<ConfirmedShock> | null {
  const proposed = draft.proposal?.proposed_shocks;
  if (!proposed) return null;
  return Object.fromEntries(
    cases.map((kind) => [
      kind,
      Object.fromEntries(
        horizons.map((horizon) => [
          horizon,
          {
            factors: { ...proposed[kind][horizon].factors },
            issuers: { ...proposed[kind][horizon].issuers },
          },
        ]),
      ),
    ]),
  ) as CaseGrid<ConfirmedShock>;
}

export function sameWeights(
  left: Record<string, number> | null | undefined,
  right: Record<string, number>,
) {
  if (!left) return false;
  return [...new Set([...Object.keys(left), ...Object.keys(right)])].every(
    (symbol) => Math.abs((left[symbol] ?? 0) - (right[symbol] ?? 0)) < 1e-10,
  );
}

export function EventResearch({
  portfolioId,
  portfolioRevision,
  proposedWeights,
  validAllocation,
  api = eventResearchApi,
}: {
  portfolioId: string;
  portfolioRevision: number;
  proposedWeights: Record<string, number>;
  validAllocation: boolean;
  api?: typeof eventResearchApi;
}) {
  const [templates, setTemplates] = useState<EventTemplate[]>([]);
  const [availability, setAvailability] = useState<
    "loading" | "ready" | "unavailable"
  >("loading");
  const [availabilityError, setAvailabilityError] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [situationId, setSituationId] = useState("");
  const [targetSymbol, setTargetSymbol] = useState("");
  const [description, setDescription] = useState("");
  const [drafts, setDrafts] = useState<ScenarioDraft[]>([]);
  const [runs, setRuns] = useState<ScenarioRun[]>([]);
  const [draft, setDraft] = useState<ScenarioDraft | null>(null);
  const [run, setRun] = useState<ScenarioRun | null>(null);
  const [shocks, setShocks] = useState<CaseGrid<ConfirmedShock> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [availabilityRetry, setAvailabilityRetry] = useState(0);
  const [draftPoll, setDraftPoll] = useState(0);
  const [runPoll, setRunPoll] = useState(0);

  const allocationKey = useMemo(
    () =>
      Object.entries(proposedWeights)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([symbol, weight]) => `${symbol}:${weight}`)
        .join("|"),
    [proposedWeights],
  );
  const symbolsKey = Object.keys(proposedWeights).sort().join("|");
  const selectedTemplate = templates.find(
    (item) => item.template_id === templateId,
  );
  const eligibleTargets = selectedTemplate?.target_symbols ?? [];
  const draftInputsChanged =
    !!draft &&
    ((draft.portfolio_revision != null &&
      draft.portfolio_revision !== portfolioRevision) ||
      !sameWeights(
        draft.proposed_weights ?? draft.request?.proposed_weights,
        proposedWeights,
      ));
  const historicalRevision = !!draft?.request?.source_run_id;
  const draftStale = draftInputsChanged && !historicalRevision;
  const canResearch =
    validAllocation &&
    !!selectedTemplate &&
    (!!situationId || !!description.trim()) &&
    (selectedTemplate.category !== "issuer" ||
      !!(targetSymbol || eligibleTargets[0]));

  useEffect(() => {
    let active = true;
    setAvailability("loading");
    void api
      .listTemplates(portfolioId, symbolsKey ? symbolsKey.split("|") : [])
      .then((items) => {
        if (!active) return;
        setTemplates(items);
        setTemplateId(items[0]?.template_id ?? "");
        setAvailability("ready");
        void Promise.all([
          api.listDrafts(portfolioId),
          api.listRuns(portfolioId),
        ])
          .then(([savedDrafts, savedRuns]) => {
            if (active) {
              setDrafts(savedDrafts);
              setRuns(savedRuns);
            }
          })
          .catch((cause) => {
            if (active) setError(message(cause));
          });
      })
      .catch((cause) => {
        if (!active) return;
        setAvailabilityError(message(cause));
        setAvailability("unavailable");
      });
    return () => {
      active = false;
    };
  }, [portfolioId, symbolsKey, availabilityRetry, api]);

  useEffect(() => {
    if (!draft || !["pending", "queued", "running"].includes(draft.status))
      return;
    let active = true;
    const timer = window.setTimeout(() => {
      void api
        .getDraft(draft.draft_id)
        .then((next) => {
          if (!active) return;
          setDraft(next);
          setDrafts((old) =>
            old.map((item) => (item.draft_id === next.draft_id ? next : item)),
          );
          if (next.status === "ready") setShocks(proposedShocks(next));
          setError("");
        })
        .catch((cause) => {
          if (active) setError(message(cause));
        })
        .finally(() => {
          if (active) setDraftPoll((old) => old + 1);
        });
    }, 1800);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [draft?.draft_id, draft?.status, draftPoll, api]);

  useEffect(() => {
    if (!run || !["pending", "queued", "running"].includes(run.status)) return;
    let active = true;
    const timer = window.setTimeout(() => {
      void api
        .getRun(run.run_id)
        .then((next) => {
          if (!active) return;
          setRun(next);
          setRuns((old) =>
            old.map((item) => (item.run_id === next.run_id ? next : item)),
          );
          setError("");
        })
        .catch((cause) => {
          if (active) setError(message(cause));
        })
        .finally(() => {
          if (active) setRunPoll((old) => old + 1);
        });
    }, 1800);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [run?.run_id, run?.status, runPoll, api]);

  async function startResearch() {
    if (!canResearch || busy) return;
    setBusy(true);
    setError("");
    setRun(null);
    setDraft(null);
    setShocks(null);
    try {
      const created = await api.createDraft(
        {
          portfolio_id: portfolioId,
          portfolio_revision: portfolioRevision,
          template_id: templateId,
          ...(situationId ? { situation_id: situationId } : {}),
          ...(selectedTemplate?.category === "issuer"
            ? { target_symbol: targetSymbol || eligibleTargets[0] }
            : {}),
          description,
          proposed_weights: proposedWeights,
        },
        crypto.randomUUID(),
      );
      const next = await api.getDraft(created.draft_id);
      setDraft(next);
      if (next.status === "ready") setShocks(proposedShocks(next));
      setDrafts((old) => [
        next,
        ...old.filter((item) => item.draft_id !== next.draft_id),
      ]);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!draft || !shocks || draft.revision == null || draftStale || busy)
      return;
    setBusy(true);
    setError("");
    try {
      const created = await api.confirmDraft(
        draft.draft_id,
        draft.revision,
        shocks,
      );
      const next = await api.getRun(created.run_id);
      setRun(next);
      setRuns((old) => [
        next,
        ...old.filter((item) => item.run_id !== next.run_id),
      ]);
      setDraft(await api.getDraft(draft.draft_id));
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  function openDraft(item: ScenarioDraft) {
    setDraft(item);
    setRun(null);
    setShocks(item.confirmed_shocks ?? proposedShocks(item));
    setError("");
  }

  function updateShock(
    kind: (typeof cases)[number],
    horizon: (typeof horizons)[number],
    group: "factors" | "issuers",
    name: string,
    text: string,
  ) {
    const value =
      text === "" ? NaN : Number(text) / (group === "factors" ? 100 : 1);
    setShocks(
      (old) =>
        old && {
          ...old,
          [kind]: {
            ...old[kind],
            [horizon]: {
              ...old[kind][horizon],
              [group]: { ...old[kind][horizon][group], [name]: value },
            },
          },
        },
    );
  }

  const validShocks =
    shocks &&
    cases.every((kind) =>
      horizons.every((horizon) => {
        const item = shocks[kind]?.[horizon];
        return (
          item &&
          factors.every(
            (factor) =>
              Number.isFinite(item.factors[factor]) &&
              Math.abs(item.factors[factor]) <= 0.5,
          ) &&
          Object.entries(item.issuers).every(
            ([symbol, value]) =>
              (draft?.proposed_weights ?? proposedWeights)[symbol] !==
                undefined &&
              Number.isFinite(value) &&
              Math.abs(value) <= 3,
          )
        );
      }),
    );

  return (
    <section
      className="event-research"
      id="event-research-panel"
      tabIndex={-1}
      aria-labelledby="event-research-title"
      data-allocation={allocationKey}
    >
      <div className="event-research-heading">
        <div>
          <h2 id="event-research-title">Research an event</h2>
          <p>
            Explore a possible event against the allocation shown above. Review
            the evidence and assumptions before calculating.
          </p>
        </div>
      </div>
      {availability === "loading" && (
        <p role="status">Checking event research availability…</p>
      )}
      {availability === "unavailable" && (
        <div className="event-research-unavailable" role="status">
          <strong>Event research is unavailable right now.</strong>
          <p>{availabilityError}</p>
          <p>You can still compare and apply allocations in the other view.</p>
          <button
            className="button subtle"
            type="button"
            onClick={() => setAvailabilityRetry((old) => old + 1)}
          >
            Try event research again
          </button>
        </div>
      )}
      {availability === "ready" && (
        <>
          {templates.length === 0 && (
            <p role="status">
              No researched events are available for these holdings.
            </p>
          )}
          <div className="event-research-controls">
            <label>
              Event
              <select
                value={templateId}
                onChange={(event) => {
                  setTemplateId(event.target.value);
                  setSituationId("");
                  setTargetSymbol("");
                }}
              >
                {templates.map((item) => (
                  <option key={item.template_id} value={item.template_id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
            {!!selectedTemplate?.situations.length && (
              <label>
                Situation
                <select
                  value={situationId}
                  onChange={(event) => setSituationId(event.target.value)}
                >
                  <option value="">Describe another situation</option>
                  {selectedTemplate.situations.map((item) => (
                    <option key={item.situation_id} value={item.situation_id}>
                      {item.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {selectedTemplate?.category === "issuer" && (
              <label>
                Target stock
                <select
                  value={targetSymbol || eligibleTargets[0] || ""}
                  onChange={(event) => setTargetSymbol(event.target.value)}
                >
                  {eligibleTargets.map((symbol) => (
                    <option key={symbol} value={symbol}>
                      {symbol}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="event-description">
              What would you like to examine?
              <textarea
                value={description}
                maxLength={700}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Describe the event or the question you want researched."
              />
            </label>
            <button
              className="button dark"
              type="button"
              disabled={!canResearch || busy}
              onClick={() => void startResearch()}
            >
              {busy ? "Starting research…" : "Research this event"}
            </button>
            {!validAllocation && (
              <p role="status">
                Complete the proposed allocation above to start research.
              </p>
            )}
          </div>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          {draft && (
            <div className="event-research-review">
              <div className="event-research-review-heading">
                <h3>{draft.proposal?.scenario_brief || "Event research"}</h3>
                <span>{draft.status}</span>
              </div>
              {draftStale && (
                <p className="event-stale" role="status">
                  The proposed allocation or portfolio changed after this draft
                  was created. Review it here, then start new research with the
                  current allocation.
                </p>
              )}
              {historicalRevision && draftInputsChanged && (
                <p className="event-stale" role="status">
                  This revision uses the saved run’s portfolio allocation and
                  price history. It does not use the current allocation above.
                  Review its assumptions before calculating.
                </p>
              )}
              {["pending", "queued", "running"].includes(draft.status) && (
                <p role="status">
                  Gathering evidence and modeling assumptions…
                </p>
              )}
              {draft.status === "failed" && (
                <p role="alert">
                  {draft.last_error ||
                    "Research could not finish. Start a new draft to retry."}
                </p>
              )}
              {draft.proposal && (
                <>
                  <p className="event-research-provenance">
                    Pinned to{" "}
                    {draft.allocation_snapshot?.name ?? "this portfolio"},
                    revision {draft.portfolio_revision ?? "unknown"}
                    {draft.price_window?.start && draft.price_window.end
                      ? ` · adjusted history ${draft.price_window.start}–${draft.price_window.end}`
                      : ""}
                    .
                  </p>
                  <div className="event-research-evidence">
                    <h4>Evidence to review</h4>
                    {draft.proposal.facts.length ? (
                      <ul>
                        {draft.proposal.facts.map((fact, index) => (
                          <li key={index}>
                            {fact.claim}{" "}
                            <small>{fact.evidence_ids.join(", ")}</small>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>No verified facts were available for this event.</p>
                    )}
                    {draft.proposal.evidence.length > 0 && (
                      <details>
                        <summary>Sources and retrieval status</summary>
                        <ul>
                          {draft.proposal.evidence.map((item) => (
                            <li key={item.evidence_id}>
                              {item.source_url?.startsWith("https://") ? (
                                <a
                                  href={item.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {item.title || item.evidence_id}
                                </a>
                              ) : (
                                item.title || item.evidence_id
                              )}{" "}
                              · {item.status}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                    {!!draft.proposal.missing_evidence.length && (
                      <p>
                        Missing evidence:{" "}
                        {draft.proposal.missing_evidence.join("; ")}
                      </p>
                    )}
                  </div>
                  {shocks && (
                    <div className="event-research-shocks">
                      <h4>Review the proposed shocks</h4>
                      <p>
                        Factor values are cumulative returns in percent. Issuer
                        values are residual standard-deviation multiples.
                      </p>
                      <div className="event-shock-grid">
                        {cases.flatMap((kind) =>
                          horizons.map((horizon) => (
                            <fieldset
                              key={`${kind}-${horizon}`}
                              disabled={
                                draft.status === "confirmed" || draftStale
                              }
                            >
                              <legend>
                                {kind} ·{" "}
                                {horizon === "1m"
                                  ? "one month"
                                  : "three months"}
                              </legend>
                              {factors.map((factor) => (
                                <label key={factor}>
                                  {factor} · %
                                  <input
                                    type="number"
                                    min={-50}
                                    max={50}
                                    step="0.1"
                                    value={
                                      Number.isFinite(
                                        shocks[kind][horizon].factors[factor],
                                      )
                                        ? shocks[kind][horizon].factors[
                                            factor
                                          ] * 100
                                        : ""
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
                                </label>
                              ))}
                              {Object.entries(
                                shocks[kind][horizon].issuers,
                              ).map(([symbol, value]) => (
                                <label key={symbol}>
                                  {symbol} · σ
                                  <input
                                    type="number"
                                    min={-3}
                                    max={3}
                                    step="0.1"
                                    value={Number.isFinite(value) ? value : ""}
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
                                </label>
                              ))}
                            </fieldset>
                          )),
                        )}
                      </div>
                      {draft.status === "ready" && (
                        <button
                          className="button dark"
                          disabled={!validShocks || draftStale || busy}
                          onClick={() => void confirm()}
                        >
                          Confirm assumptions and calculate
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
          {run && (
            <div className="event-research-results">
              <h3>Event-conditioned results</h3>
              {["pending", "queued", "running"].includes(run.status) && (
                <p role="status">Calculating one- and three-month outcomes…</p>
              )}
              {run.status === "failed" && (
                <p role="alert">
                  {run.last_error || "The calculation could not finish."}
                </p>
              )}
              {run.result && (
                <>
                  <p>
                    Hypothetical modeled estimates, not a forecast or live
                    quote.
                  </p>
                  <p className="event-research-provenance">
                    Saved allocation:{" "}
                    {run.allocation_snapshot?.name ?? "portfolio"}, revision{" "}
                    {run.portfolio_revision ?? "unknown"}
                    {run.price_window?.start && run.price_window.end
                      ? ` · adjusted history ${run.price_window.start}–${run.price_window.end}`
                      : ""}
                    . This run uses its saved inputs.
                  </p>
                  <div className="event-result-table-wrap">
                    <table>
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
                        {run.result.cases.map((item) => (
                          <tr key={`${item.case}-${item.horizon}`}>
                            <th>{item.case}</th>
                            <td>{item.horizon}</td>
                            <td>{percent(item.current.estimated_return)}</td>
                            <td>{percent(item.proposed.estimated_return)}</td>
                            <td>{percent(item.delta.estimated_return)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p>
                    Model: {run.result.model_version ?? "event model"}.{" "}
                    {run.result.probabilities.status === "omitted"
                      ? "Probability ranges are omitted because calibration is unavailable."
                      : "Probability ranges use the saved calibration."}
                  </p>
                  {(run.result.facts?.length ||
                    run.result.missing_evidence?.length) && (
                    <details className="event-result-evidence">
                      <summary>Evidence used for this run</summary>
                      {!!run.result.facts?.length && (
                        <ul>
                          {run.result.facts.map((fact, index) => (
                            <li key={index}>
                              {fact.claim}{" "}
                              <small>{fact.evidence_ids.join(", ")}</small>
                            </li>
                          ))}
                        </ul>
                      )}
                      {!!run.result.missing_evidence?.length && (
                        <p>
                          Missing evidence:{" "}
                          {run.result.missing_evidence.join("; ")}
                        </p>
                      )}
                    </details>
                  )}
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (!question.trim() || chatBusy) return;
                      setChatBusy(true);
                      setAnswer("");
                      void api
                        .sendMessage(run.run_id, question.trim())
                        .then(async (response) => {
                          const revisionId =
                            response.revision_draft_id ??
                            response.message.message.revision_draft_id;
                          if (revisionId) {
                            const next = await api.getDraft(revisionId);
                            openDraft(next);
                            setDrafts((old) => [
                              next,
                              ...old.filter(
                                (item) => item.draft_id !== next.draft_id,
                              ),
                            ]);
                            setQuestion("");
                            return;
                          }
                          const value = response.message.message.answer;
                          setAnswer(
                            typeof value === "string" ? value : value.content,
                          );
                        })
                        .catch((cause) => setError(message(cause)))
                        .finally(() => setChatBusy(false));
                    }}
                  >
                    <label>
                      Ask about this result
                      <input
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        maxLength={2000}
                      />
                    </label>
                    <button
                      className="button subtle"
                      disabled={!question.trim() || chatBusy}
                    >
                      Ask
                    </button>
                  </form>
                  {answer && <p className="event-chat-answer">{answer}</p>}
                </>
              )}
            </div>
          )}
          {(drafts.length > 0 || runs.length > 0) && (
            <details className="event-saved-work">
              <summary>Saved event research and runs</summary>
              {drafts.length > 0 && (
                <div>
                  <h4>Drafts</h4>
                  {drafts.map((item) => (
                    <button
                      type="button"
                      key={item.draft_id}
                      onClick={() => openDraft(item)}
                    >
                      {templates.find(
                        (template) =>
                          template.template_id === item.request?.template_id,
                      )?.title ?? "Event draft"}{" "}
                      · {item.status}
                    </button>
                  ))}
                </div>
              )}
              {runs.length > 0 && (
                <div>
                  <h4>Runs</h4>
                  {runs.map((item) => (
                    <button
                      type="button"
                      key={item.run_id}
                      onClick={() => {
                        setDraft(null);
                        setRun(item);
                        setError("");
                      }}
                    >
                      {item.created_at
                        ? new Date(item.created_at).toLocaleDateString()
                        : "Saved"}{" "}
                      · {item.status}
                    </button>
                  ))}
                </div>
              )}
            </details>
          )}
        </>
      )}
    </section>
  );
}
