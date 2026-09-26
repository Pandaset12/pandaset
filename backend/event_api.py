"""Authenticated, owner-scoped API for the event-aware What-if Lab."""

from __future__ import annotations

from dataclasses import asdict
import math
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from quant_engine.analytics import analyze_portfolio
from quant_engine.event_model import MODEL_VERSION

from .auth import AuthenticatedUser, require_user
from .config import Settings, get_settings
from .event_agents import answer_run_question
from .event_jobs import FACTOR_SYMBOLS
from .event_schemas import ChatRequest, ConfirmRequest, DraftRequest, validate_shocks
from .event_templates import EventTemplateNotFound, get_event_template, list_event_templates
from .gemini_service import (GeminiRateLimited, GeminiUnavailable,
                             gemini_cooldown_remaining, generate_analysis_workflow)
from .instruments import SUPPORTED_INSTRUMENTS, resolve_instrument, search_instruments
from .mongo_store import (IdempotencyConflict, InvalidTransition, MongoPortfolioStore,
                          QuotaExceeded, RecordNotFound, ReservationInProgress)
from .providers import map_quant_report
from .schemas import AIWorkflowResponse, AnalysisWorkflowRequest, AnalyticsSnapshot, PortfolioInput
from .storage import SnapshotNotFound
from .twelve_data import CoverageError, ProviderUnavailable, RateLimitError, TwelveDataPriceProvider

router = APIRouter(prefix="/api/v2", tags=["event-lab"])


def _error(status: int, code: str, message: str, *, headers: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message}, headers=headers)


def _gemini_rate_limit_error(seconds: int) -> HTTPException:
    return _error(429, "GEMINI_RATE_LIMITED",
                  f"Gemini rate limit reached. Try again in about {seconds} seconds.",
                  headers={"Retry-After": str(seconds)})


def _not_found() -> HTTPException:
    return _error(404, "NOT_FOUND", "Record not found.")


def _store(request: Request, user: AuthenticatedUser = Depends(require_user),
           settings: Settings = Depends(get_settings)) -> tuple[MongoPortfolioStore, AuthenticatedUser, Settings]:
    if not settings.event_lab_ready or settings.event_lab_public_enabled and not settings.event_lab_public_ready:
        raise _error(503, "EVENT_LAB_UNAVAILABLE", "The event lab is unavailable.")
    if not settings.event_lab_public_enabled:
        invited = {item.strip() for item in settings.event_lab_allowed_user_ids.split(",") if item.strip()}
        if user.user_id not in invited:
            raise _error(403, "EVENT_LAB_NOT_INVITED", "The event lab is not available to this account.")
    store = getattr(request.app.state, "event_store", None)
    if store is None:
        raise _error(503, "EVENT_LAB_UNAVAILABLE", "The event lab is unavailable.")
    return store, user, settings


def _map_store_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (RecordNotFound, SnapshotNotFound)):
        return _not_found()
    if isinstance(exc, IdempotencyConflict):
        return _error(409, "IDEMPOTENCY_CONFLICT", "This key was used for a different request.")
    if isinstance(exc, InvalidTransition):
        return _error(409, "INVALID_TRANSITION", "This scenario changed state. Refresh it and try again.")
    if isinstance(exc, QuotaExceeded):
        return _error(429, "LIMIT_REACHED", str(exc))
    return _error(422, "INVALID_INPUT", str(exc))


def _check_snapshot_coverage(record: dict, symbols: set[str]) -> None:
    snapshot = record.get("price_snapshot") or {}
    dates = snapshot.get("dates") or []
    holdings = snapshot.get("holding_prices") or {}
    factors = snapshot.get("factor_prices") or {}
    if ((record.get("metrics") or {}).get("data_mode") != "live"
            or len(dates) < 127 or len(dates) != (record.get("metrics") or {}).get("observation_count", -1) + 1
            or len(set(dates)) != len(dates)
            or dates != sorted(dates) or set(holdings) != symbols
            or set(factors) != set(FACTOR_SYMBOLS.values())):
        raise ValueError("Saved adjusted history lacks complete aligned factor and holding coverage.")
    for values in [*holdings.values(), *factors.values()]:
        if (len(values) != len(dates) or any(isinstance(value, bool) or not isinstance(value, (int, float))
                                           or not math.isfinite(value) or value <= 0 for value in values)):
            raise ValueError("Saved adjusted history has missing or invalid prices.")


async def _call(method, *args, **kwargs):
    try:
        return await run_in_threadpool(method, *args, **kwargs)
    except (RecordNotFound, SnapshotNotFound, IdempotencyConflict, InvalidTransition, QuotaExceeded, ValueError) as exc:
        raise _map_store_error(exc) from exc


async def _aligned_histories(provider: TwelveDataPriceProvider, settings: Settings,
                             symbols: list[str]):
    factors = list(FACTOR_SYMBOLS.values())
    union = sorted(set(symbols) | set(factors))
    if len(union) <= 25:
        combined = await run_in_threadpool(provider.prices, union, 252)
        prices, factor_prices = combined[symbols].copy(), combined[factors].copy()
        prices.attrs["provenance"] = combined.attrs.get("provenance", {})
        factor_prices.attrs["provenance"] = combined.attrs.get("provenance", {})
        return prices, factor_prices
    prices = await run_in_threadpool(provider.prices, symbols, 252)
    factor_prices = await run_in_threadpool(provider.prices, factors, 252)
    if not prices.index.equals(factor_prices.index):
        # A licensed cache can straddle a trading-session rollover. Bypass it
        # once on both sides so a fresh holding window is compared with fresh
        # factor proxies. An upstream failure remains a provider error.
        fresh = TwelveDataPriceProvider(settings.twelve_data_api_key.get_secret_value(),
                                        cache_allowed=False)
        prices = await run_in_threadpool(fresh.prices, symbols, 252)
        factor_prices = await run_in_threadpool(fresh.prices, factors, 252)
    if not prices.index.equals(factor_prices.index):
        raise CoverageError("Holding and factor histories have different trading dates.")
    return prices, factor_prices


@router.get("/portfolios")
async def portfolios(context=Depends(_store)):
    store, user, _ = context
    return {"portfolios": await _call(store.list_portfolios, user.user_id)}


@router.post("/portfolios", status_code=201)
async def create_portfolio(body: PortfolioInput, context=Depends(_store)):
    store, user, _ = context
    return await _call(store.create_portfolio, user.user_id, body)


@router.get("/portfolios/{portfolio_id}")
async def portfolio(portfolio_id: str, context=Depends(_store)):
    store, user, _ = context
    item = await _call(store.get_portfolio, user.user_id, portfolio_id)
    if item is None:
        raise _not_found()
    return item


@router.put("/portfolios/{portfolio_id}")
@router.patch("/portfolios/{portfolio_id}")
async def update_portfolio(portfolio_id: str, body: PortfolioInput, context=Depends(_store)):
    store, user, _ = context
    return await _call(store.update_portfolio, user.user_id, portfolio_id, body)


@router.delete("/portfolios/{portfolio_id}", status_code=204)
async def delete_portfolio(portfolio_id: str, context=Depends(_store)):
    store, user, _ = context
    if not await _call(store.delete_portfolio, user.user_id, portfolio_id):
        raise _not_found()


@router.post("/portfolios/{portfolio_id}/analysis", status_code=201)
async def create_analysis(portfolio_id: str, request: Request, context=Depends(_store)):
    store, user, settings = context
    portfolio = await _call(store.get_portfolio, user.user_id, portfolio_id)
    if portfolio is None:
        raise _not_found()
    provider: TwelveDataPriceProvider = request.app.state.event_price_provider
    symbols = sorted(portfolio.weights)
    try:
        prices, factor_prices = await _aligned_histories(provider, settings, symbols)
        report = await run_in_threadpool(analyze_portfolio, prices, portfolio.weights)
        metrics = map_quant_report(report, portfolio_id, prices.attrs.get("provenance"))
    except RateLimitError as exc:
        raise _error(429, "PROVIDER_RATE_LIMIT", str(exc)) from exc
    except CoverageError as exc:
        raise _error(422, "PRICE_COVERAGE", str(exc)) from exc
    except ProviderUnavailable as exc:
        raise _error(502, "PROVIDER_UNAVAILABLE", str(exc)) from exc
    except ValueError as exc:
        raise _error(422, "PRICE_COVERAGE", str(exc)) from exc
    snapshot = {
        "dates": [day.isoformat() for day in prices.index],
        "holding_prices": {symbol: prices[symbol].astype(float).tolist() for symbol in prices.columns},
        "factor_prices": {symbol: factor_prices[symbol].astype(float).tolist() for symbol in factor_prices.columns},
        "provenance": prices.attrs.get("provenance", {}),
        "factor_provenance": factor_prices.attrs.get("provenance", {}),
    }
    analysis_id, created_at = await _call(store.save_analysis, user.user_id, metrics,
                                          portfolio.model_dump(mode="json"), snapshot, MODEL_VERSION)
    return {"analysis_id": analysis_id, "portfolio_id": portfolio_id, "created_at": created_at,
            "metrics": metrics, "price_provenance": snapshot["provenance"]}


@router.get("/portfolios/{portfolio_id}/analyses/{analysis_id}")
async def get_analysis(portfolio_id: str, analysis_id: str, context=Depends(_store)):
    store, user, _ = context
    record = await _call(store.get_analysis_record, user.user_id, portfolio_id, analysis_id)
    if record is None:
        raise _not_found()
    return {"analysis_id": analysis_id, "portfolio_id": portfolio_id,
            "created_at": record["created_at"], "metrics": record["metrics"],
            "price_provenance": record["price_snapshot"].get("provenance", {})}


@router.get("/portfolios/{portfolio_id}/analyses")
async def list_analyses(portfolio_id: str, limit: int = Query(default=10, ge=1, le=50),
                        context=Depends(_store)):
    store, user, _ = context
    if await _call(store.get_portfolio, user.user_id, portfolio_id) is None:
        raise _not_found()
    records = await _call(store.list_analyses, user.user_id, portfolio_id, limit)
    return {"analyses": [
        {"analysis_id": item["id"], "portfolio_id": portfolio_id,
         "created_at": item["created_at"], "metrics": item["metrics"],
         "price_provenance": item.get("price_snapshot", {}).get("provenance", {})}
        for item in records
    ]}


async def _saved_analysis_workflow(workflow: str, portfolio_id: str,
                                   body: AnalysisWorkflowRequest, context) -> AIWorkflowResponse:
    store, user, settings = context
    record = await _call(store.get_analysis_record, user.user_id, portfolio_id, body.analysis_id)
    if record is None:
        raise _not_found()
    metrics = AnalyticsSnapshot.model_validate(record["metrics"])
    try:
        output = await generate_analysis_workflow(
            workflow, body.question, metrics, body.analysis_id, settings,
        )
    except GeminiRateLimited as exc:
        raise _gemini_rate_limit_error(exc.retry_after_seconds) from exc
    except GeminiUnavailable as exc:
        raise _error(502, "GEMINI_UNAVAILABLE", str(exc)) from exc
    return AIWorkflowResponse(
        workflow=workflow, analyst_mode="gemini", status="complete",
        analysis_id=body.analysis_id, **output,
    )


@router.post("/portfolios/{portfolio_id}/briefing", response_model=AIWorkflowResponse)
async def saved_briefing(portfolio_id: str, body: AnalysisWorkflowRequest,
                         context=Depends(_store)):
    return await _saved_analysis_workflow("analysis_briefing", portfolio_id, body, context)


@router.post("/portfolios/{portfolio_id}/risk/explanation", response_model=AIWorkflowResponse)
async def saved_risk_explanation(portfolio_id: str, body: AnalysisWorkflowRequest,
                                 context=Depends(_store)):
    return await _saved_analysis_workflow("risk_explanation", portfolio_id, body, context)


@router.get("/instruments")
async def instruments(q: str = Query(default="", max_length=80), context=Depends(_store)):
    return {"instruments": [asdict(item) for item in search_instruments(q)]}


@router.get("/events/templates")
async def templates(portfolio_id: str | None = None, context=Depends(_store)):
    store, user, _ = context
    instruments_for_portfolio = None
    if portfolio_id:
        portfolio = await _call(store.get_portfolio, user.user_id, portfolio_id)
        if portfolio is None:
            raise _not_found()
        instruments_for_portfolio = [resolve_instrument(symbol) for symbol in portfolio.weights]
    return {"templates": [asdict(item) for item in list_event_templates(instruments_for_portfolio)]}


@router.get("/scenarios/drafts")
async def drafts(portfolio_id: str, context=Depends(_store)):
    store, user, _ = context
    return {"drafts": [public_draft(item) for item in await _call(store.list_drafts, user.user_id, portfolio_id)]}


@router.post("/scenarios/drafts", status_code=202)
async def create_draft(body: DraftRequest, context=Depends(_store),
                       idempotency_key: str | None = Header(default=None, max_length=128)):
    store, user, _ = context
    try:
        template = get_event_template(body.template_id)
    except EventTemplateNotFound as exc:
        raise _error(422, "UNKNOWN_TEMPLATE", "Event template is unsupported.") from exc
    portfolio = await _call(store.get_portfolio, user.user_id, body.portfolio_id)
    if portfolio is None:
        raise _not_found()
    record = await _call(store.get_analysis_record, user.user_id, body.portfolio_id, body.analysis_id)
    if record is None:
        raise _not_found()
    eligible = {item.template_id for item in list_event_templates(
        [resolve_instrument(symbol) for symbol in portfolio.weights])}
    if template.template_id not in eligible:
        raise _error(422, "UNKNOWN_TEMPLATE", "This template does not apply to the saved portfolio.")
    if body.proposed_weights is not None and set(body.proposed_weights) != set(record["metrics"]["weights"]):
        raise _error(422, "INVALID_WEIGHTS", "Proposed weights must cover the saved holdings.")
    try:
        _check_snapshot_coverage(record, set(record["metrics"]["weights"]))
    except ValueError as exc:
        raise _error(422, "PRICE_COVERAGE", str(exc)) from exc
    payload = body.model_dump(mode="json", exclude_none=True)
    payload["template_version"] = template.version
    cooldown = gemini_cooldown_remaining()
    if cooldown:
        raise _gemini_rate_limit_error(cooldown)
    draft = await _call(store.create_draft, user.user_id, body.portfolio_id,
                        payload, idempotency_key)
    return {"draft_id": draft["id"], "status": draft["status"]}


def public_draft(item: dict) -> dict:
    return {"draft_id": item["id"], "portfolio_id": item["portfolio_id"],
            "status": item["status"], "revision": item.get("revision"),
            "request": item["request"], "proposal": item.get("proposal"),
            "confirmed_shocks": item.get("confirmed_shocks"),
            "attempt_count": item["attempt_count"], "last_error": item.get("last_error"),
            "created_at": item["created_at"], "updated_at": item["updated_at"]}


@router.get("/scenarios/drafts/{draft_id}")
async def draft(draft_id: str, context=Depends(_store)):
    store, user, _ = context
    item = await _call(store.get_draft, user.user_id, draft_id)
    if item is None:
        raise _not_found()
    return public_draft(item)


@router.post("/scenarios/drafts/{draft_id}/confirm", status_code=202)
async def confirm(draft_id: str, body: ConfirmRequest, context=Depends(_store)):
    store, user, _ = context
    item = await _call(store.get_draft, user.user_id, draft_id)
    if item is None:
        raise _not_found()
    if item["status"] not in {"ready", "confirmed"} or item.get("revision") != body.revision:
        raise _map_store_error(InvalidTransition(draft_id))
    record = await _call(store.get_analysis_record, user.user_id, item["portfolio_id"],
                         item["request"]["analysis_id"])
    if record is None:
        raise _not_found()
    symbols = set(record["metrics"]["weights"])
    try:
        _check_snapshot_coverage(record, symbols)
        shocks = validate_shocks(body.confirmed_shocks.as_engine_input(), symbols)
    except ValueError as exc:
        raise _error(422, "INVALID_SHOCKS", str(exc)) from exc
    if item["status"] == "confirmed":
        if item.get("confirmed_shocks") != shocks:
            raise _map_store_error(InvalidTransition(draft_id))
    else:
        try:
            await _call(store.confirm_draft, user.user_id, draft_id, shocks, revision=body.revision)
        except HTTPException as exc:
            # A concurrent identical confirmation may have won the transition.
            current = await _call(store.get_draft, user.user_id, draft_id)
            if (exc.status_code != 409 or current is None or current.get("status") != "confirmed"
                    or current.get("confirmed_shocks") != shocks):
                raise
    # A stable server key gives one run per confirmed draft. If run insertion or
    # quota checks fail after confirmation, the same request can be retried.
    run = await _call(store.create_run, user.user_id, draft_id, item["request"]["analysis_id"],
                      f"confirmed:{draft_id}")
    return {"run_id": run["id"], "status": run["status"]}


@router.post("/scenarios/drafts/{draft_id}/cancel")
async def cancel_draft(draft_id: str, context=Depends(_store)):
    store, user, _ = context
    if await _call(store.get_draft, user.user_id, draft_id) is None:
        raise _not_found()
    await _call(store.cancel_draft, user.user_id, draft_id)
    return {"draft_id": draft_id, "status": (await _call(store.get_draft, user.user_id, draft_id))["status"]}


@router.delete("/scenarios/drafts/{draft_id}", status_code=204)
async def delete_draft(draft_id: str, context=Depends(_store)):
    store, user, _ = context
    if not await _call(store.delete_draft, user.user_id, draft_id):
        raise _not_found()


@router.get("/scenarios/runs")
async def runs(portfolio_id: str, context=Depends(_store)):
    store, user, _ = context
    return {"runs": [public_run(item) for item in await _call(store.list_runs, user.user_id, portfolio_id)]}


def public_run(item: dict) -> dict:
    return {"run_id": item["id"], "portfolio_id": item["portfolio_id"],
            "draft_id": item["draft_id"], "analysis_id": item["analysis_id"],
            "status": item["status"], "result": item.get("result"),
            "attempt_count": item["attempt_count"], "last_error": item.get("last_error"),
            "created_at": item["created_at"], "updated_at": item["updated_at"]}


@router.get("/scenarios/runs/{run_id}")
async def run(run_id: str, context=Depends(_store)):
    store, user, _ = context
    item = await _call(store.get_run, user.user_id, run_id)
    if item is None:
        raise _not_found()
    return public_run(item)


@router.post("/scenarios/runs/{run_id}/cancel")
async def cancel_run(run_id: str, context=Depends(_store)):
    store, user, _ = context
    if await _call(store.get_run, user.user_id, run_id) is None:
        raise _not_found()
    await _call(store.cancel_run, user.user_id, run_id)
    return {"run_id": run_id, "status": (await _call(store.get_run, user.user_id, run_id))["status"]}


@router.delete("/scenarios/runs/{run_id}", status_code=204)
async def delete_run(run_id: str, context=Depends(_store)):
    store, user, _ = context
    if not await _call(store.delete_run, user.user_id, run_id):
        raise _not_found()


@router.get("/scenarios/runs/{run_id}/messages")
async def messages(run_id: str, context=Depends(_store)):
    store, user, _ = context
    return {"messages": await _call(store.list_messages, user.user_id, run_id)}


REVISION_LANGUAGE = re.compile(r"\b(change|revise|adjust|edit|rebalance|increase|decrease|raise|lower)\b.*\b(weight|allocation|shock|assumption|position|holding)\b", re.I | re.S)


async def _existing_chat_response(store: MongoPortfolioStore, owner_id: str, run_id: str,
                                  key: str | None, body: ChatRequest,
                                  messages: list[dict] | None = None) -> dict | None:
    if key is None:
        return None
    request = body.model_dump(mode="json", exclude_none=True)
    for saved in (messages if messages is not None else await _call(store.list_messages, owner_id, run_id)):
        if saved.get("idempotency_key") != key:
            continue
        if saved.get("message", {}).get("request") != request:
            raise _error(409, "IDEMPOTENCY_CONFLICT", "This key was used for a different message.")
        return {"message": saved,
                "revision_draft_id": saved["message"].get("revision_draft_id")}
    return None


async def _save_chat_message(store: MongoPortfolioStore, owner_id: str, run_id: str,
                             payload: dict, key: str | None, body: ChatRequest,
                             reservation_id: str) -> dict:
    try:
        saved = await _call(store.save_message, owner_id, run_id, payload, key,
                            reservation_id=reservation_id)
        return {"message": saved, "revision_draft_id": payload.get("revision_draft_id")}
    except HTTPException as exc:
        # Another identical request can finish while this one generates an
        # answer. Read its saved response after Mongo's unique-key conflict.
        if (key is not None and exc.status_code == 409 and isinstance(exc.detail, dict)
                and exc.detail.get("code") == "IDEMPOTENCY_CONFLICT"):
            existing = await _existing_chat_response(store, owner_id, run_id, key, body)
            if existing is not None:
                return existing
        raise


@router.post("/scenarios/runs/{run_id}/messages", status_code=201)
async def post_message(run_id: str, body: ChatRequest, context=Depends(_store),
                       idempotency_key: str | None = Header(default=None, max_length=128)):
    store, user, settings = context
    item = await _call(store.get_run, user.user_id, run_id)
    if item is None:
        raise _not_found()
    if item["status"] != "completed":
        raise _map_store_error(InvalidTransition(run_id))
    saved_messages = await _call(store.list_messages, user.user_id, run_id)
    existing = await _existing_chat_response(store, user.user_id, run_id, idempotency_key,
                                             body, saved_messages)
    if existing is not None:
        return existing
    try:
        reservation_id = await run_in_threadpool(store.reserve_message_slot,
                                                 user.user_id, run_id, idempotency_key)
    except ReservationInProgress as exc:
        existing = await _existing_chat_response(store, user.user_id, run_id, idempotency_key, body)
        if existing is not None:
            return existing
        raise _error(409, "MESSAGE_IN_PROGRESS", "This message is already being answered.") from exc
    except IdempotencyConflict as exc:
        existing = await _existing_chat_response(store, user.user_id, run_id, idempotency_key, body)
        if existing is not None:
            return existing
        raise _map_store_error(exc) from exc
    except (QuotaExceeded, RecordNotFound, InvalidTransition, ValueError) as exc:
        raise _map_store_error(exc) from exc
    request_payload = body.model_dump(mode="json", exclude_none=True)
    try:
        is_revision = body.revision is not None or REVISION_LANGUAGE.search(body.content) is not None
        if is_revision:
            prior = item.get("proposal_snapshot") or {}
            template_id = (prior.get("template") or {}).get("template_id")
            if not template_id:
                raise _error(409, "REVISION_UNAVAILABLE", "The original template is unavailable.")
            revision = body.revision or DraftRequest(
                portfolio_id=item["portfolio_id"], analysis_id=item["analysis_id"],
                template_id=template_id, question=body.content,
                proposed_weights=item.get("proposed_weights"),
            )
            if revision.portfolio_id != item["portfolio_id"] or revision.analysis_id != item["analysis_id"]:
                raise _error(422, "INVALID_REVISION", "A run revision must use its saved portfolio and analysis.")
            template = get_event_template(revision.template_id)
            payload = revision.model_dump(mode="json", exclude_none=True)
            payload["template_version"] = template.version
            cooldown = gemini_cooldown_remaining()
            if cooldown:
                raise _gemini_rate_limit_error(cooldown)
            new_draft = await _call(store.create_draft, user.user_id, item["portfolio_id"],
                                    payload, idempotency_key)
            return await _save_chat_message(
                store, user.user_id, run_id,
                {"role": "user", "content": body.content, "request": request_payload,
                 "answer": "A new draft is ready for review before recalculation.",
                 "revision_draft_id": new_draft["id"]}, idempotency_key, body, reservation_id)
        try:
            answer = await answer_run_question(settings=settings, question=body.content,
                                               result=item["result"],
                                               facts=item["result"].get("facts", []),
                                               evidence=item["result"].get("evidence", []))
        except GeminiRateLimited as exc:
            raise _gemini_rate_limit_error(exc.retry_after_seconds) from exc
        except Exception as exc:
            raise _error(502, "ANSWER_UNAVAILABLE", "The grounded answer is unavailable.") from exc
        return await _save_chat_message(
            store, user.user_id, run_id,
            {"role": "user", "content": body.content, "request": request_payload,
             "answer": answer}, idempotency_key, body, reservation_id)
    finally:
        await run_in_threadpool(store.release_message_slot, user.user_id, run_id, reservation_id)
