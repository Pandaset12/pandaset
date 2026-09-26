"""Durable leased workers. Mongo owns the queue; this process can restart safely."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from uuid import uuid4

import pandas as pd
from starlette.concurrency import run_in_threadpool

from quant_engine.event_model import MODEL_VERSION, run_event_scenarios

from .config import Settings
from .event_agents import design_scenarios, research_event
from .event_sources import FredClient, official_source_evidence
from .event_templates import get_event_template
from .gemini_service import GeminiRateLimited, GeminiUnavailable, gemini_cooldown_remaining
from .mongo_store import InvalidTransition, MongoPortfolioStore
from .twelve_data import ProviderUnavailable

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120
FACTOR_SYMBOLS = {"equity": "SPY", "rates": "TLT", "gold": "GLD"}


def _frame(snapshot: dict[str, object], key: str) -> pd.DataFrame:
    values = snapshot[key]
    if not isinstance(values, dict):
        raise ValueError("Saved price snapshot is malformed.")
    frame = pd.DataFrame(values, index=pd.to_datetime(snapshot["dates"], utc=True))
    frame.index.name = "date"
    return frame.astype(float)


async def _lease_heartbeat(store: MongoPortfolioStore, kind: str, owner: str,
                           record_id: str, worker_id: str) -> None:
    renew = store.renew_draft_lease if kind == "draft" else store.renew_run_lease
    while True:
        await asyncio.sleep(30)
        if not await run_in_threadpool(renew, owner, record_id, worker_id, LEASE_SECONDS):
            return


async def _with_heartbeat(store, kind, job, worker_id, work):
    heartbeat = asyncio.create_task(_lease_heartbeat(store, kind, job["owner_id"], job["id"], worker_id))
    try:
        return await work()
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass


async def process_draft(store: MongoPortfolioStore, settings: Settings, job: dict,
                        worker_id: str) -> dict:
    owner = job["owner_id"]
    request = job["request"]
    record = await run_in_threadpool(store.get_analysis_record, owner,
                                     job["portfolio_id"], request["analysis_id"])
    if record is None:
        raise ValueError("The saved analysis is unavailable.")
    template = get_event_template(request["template_id"], request.get("template_version"))
    allocation = record["allocation_snapshot"]
    symbols = sorted(allocation["holdings"][index]["symbol"]
                     for index in range(len(allocation["holdings"])))
    as_of = pd.Timestamp(record["price_snapshot"]["dates"][-1]).date()
    fred = FredClient(settings.fred_api_key.get_secret_value() if settings.fred_api_key else "")
    evidence = []
    for series_id in template.fred_series_ids:
        item = await run_in_threadpool(fred.observation, series_id, as_of)
        evidence.append(asdict(item))
    evidence.extend(asdict(official_source_evidence(source_id))
                    for source_id in template.official_source_ids)
    template_dict = asdict(template)
    research = await research_event(settings=settings, template=template_dict,
                                    question=request.get("question", ""), evidence=evidence,
                                    symbols=symbols)
    evidence = research["evidence"]
    design = await design_scenarios(settings=settings, template=template_dict,
                                    question=request.get("question", ""),
                                    facts=research["facts"], evidence=evidence, symbols=symbols)
    proposal = {
        "template": template_dict,
        "facts": research["facts"],
        "evidence": evidence,
        "missing_evidence": research["missing_evidence"],
        "proposed_shocks": design["proposed_shocks"],
        "units": {"factors": "cumulative_decimal_return", "issuers": "residual_sigma_multiple"},
        "factor_proxies": {"equity": "SPY adjusted return", "rates": "TLT adjusted return (not a yield change)",
                           "gold": "GLD adjusted return"},
        "grounding": {"research": research["grounding"], "designer": design["grounding"]},
        "grounding_text": {"research": research["grounding_text"], "designer": design["grounding_text"]},
        "price_provenance": record["price_snapshot"].get("provenance", {}),
    }
    return await run_in_threadpool(store.complete_draft, owner, job["id"], proposal,
                                   worker_id=worker_id)


async def process_run(store: MongoPortfolioStore, settings: Settings, job: dict,
                      worker_id: str) -> dict:
    prices = _frame(job["price_snapshot"], "holding_prices")
    factor_prices = _frame(job["price_snapshot"], "factor_prices")
    factor_returns = factor_prices.pct_change().iloc[1:]
    factor_returns = factor_returns.rename(columns={symbol: factor for factor, symbol in FACTOR_SYMBOLS.items()})
    allocation = job["allocation_snapshot"]
    current = {item["symbol"]: item["weight"] for item in allocation["holdings"]}
    proposed = job.get("proposed_weights") or current
    calculated = await run_in_threadpool(
        run_event_scenarios, prices, current, proposed, factor_returns,
        job["confirmed_shocks"], seed=0, calibration_events=None,
    )
    # Public probability display needs an accepted calibration record. No such
    # record is supplied by this workflow; explicit omission is preserved.
    if not settings.event_lab_probability_enabled:
        calculated["probabilities"] = {"status": "omitted", "reason": "calibration_gate_disabled", "central": {}}
    proposal = job.get("proposal_snapshot") or {}
    result = {
        **calculated,
        "model_version": MODEL_VERSION,
        "facts": proposal.get("facts", []),
        "evidence": proposal.get("evidence", []),
        "missing_evidence": proposal.get("missing_evidence", []),
        "confirmed_assumptions": job["confirmed_shocks"],
        "confirmed_shocks": job["confirmed_shocks"],
        "current_weights": current,
        "proposed_weights": proposed,
        "price_provenance": job["price_snapshot"].get("provenance", {}),
        "analysis_id": job["analysis_id"],
        "disclaimer": "Hypothetical event-conditioned estimates; not live quotes, forecasts, or financial advice.",
    }
    return await run_in_threadpool(store.complete_run, job["owner_id"], job["id"], result,
                                   worker_id=worker_id)


class EventWorker:
    def __init__(self, store: MongoPortfolioStore, settings: Settings):
        self.store = store
        self.settings = settings
        self.worker_id = "event-" + uuid4().hex
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await run_in_threadpool(self.store.expire_exhausted_jobs, MAX_ATTEMPTS)
                did_work = False
                for kind in ("draft", "run"):
                    if kind == "draft" and gemini_cooldown_remaining():
                        # Calculation runs do not use Gemini; keep processing them.
                        continue
                    claim = self.store.claim_next_draft if kind == "draft" else self.store.claim_next_run
                    job = await run_in_threadpool(claim, self.worker_id,
                                                  lease_seconds=LEASE_SECONDS,
                                                  max_attempts=MAX_ATTEMPTS)
                    if job is None:
                        continue
                    did_work = True
                    try:
                        work = (lambda: process_draft(self.store, self.settings, job, self.worker_id)) if kind == "draft" else (lambda: process_run(self.store, self.settings, job, self.worker_id))
                        await _with_heartbeat(self.store, kind, job, self.worker_id, work)
                    except asyncio.CancelledError:
                        raise
                    except InvalidTransition:
                        # Cancellation or deletion won the completion race.
                        pass
                    except Exception as exc:
                        fail = self.store.fail_draft if kind == "draft" else self.store.fail_run
                        retryable = (not isinstance(exc, GeminiRateLimited) and
                                     isinstance(exc, (GeminiUnavailable, ProviderUnavailable,
                                                      TimeoutError, OSError)))
                        try:
                            await run_in_threadpool(fail, job["owner_id"], job["id"],
                                                    str(exc), worker_id=self.worker_id,
                                                    retryable=retryable, max_attempts=MAX_ATTEMPTS)
                        except InvalidTransition:
                            pass
                if not did_work:
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A database outage must not end the worker permanently.
                await asyncio.sleep(5)
