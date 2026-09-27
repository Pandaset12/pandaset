from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .alpaca_quotes import AlpacaQuotesUnavailable, fetch_alpaca_quotes
from .alpaca_assets import AssetLookupUnavailable, search_alpaca_assets, search_catalog
from .alpaca_history import RateLimitError
from .config import Settings, get_settings
from .auth import current_user_id
from .instruments import SUPPORTED_INSTRUMENTS
from .observability import log_failure
from .gemini_service import (
    GeminiNotConfigured,
    GeminiUnavailable,
    generate_analysis_workflow,
    generate_research_summary,
    generate_scenario_workflow,
    metric_summary,
    portfolio_briefing_summary,
)
from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable, SymbolLimitExceeded
from .providers import IntegrationPending, QuantProvider, get_provider
from .research_sources import curated_research_source
from .schemas import (
    MAX_PORTFOLIO_SYMBOLS,
    MAX_QUOTE_SYMBOLS,
    AIWorkflowResponse,
    AllocationInput,
    CurrentMetricsResponse,
    AnalyticsSnapshot,
    AnalysisWorkflowRequest,
    MarketHistoryResponse,
    LiveQuotesResponse,
    Portfolio,
    PortfolioInput,
    ResearchSummaryRequest,
    ScenarioExplanationRequest,
    WhatIfRequest,
)
from .storage import PortfolioStore


router = APIRouter(prefix="/api/v1", tags=["PortfolioLens v1"])


def get_store(request: Request) -> PortfolioStore:
    return request.app.state.store


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@lru_cache(maxsize=1)
def _sample_assets() -> list[dict[str, str]]:
    fixture = Path(__file__).parent / "drafts" / "data_pipeline" / "sample_prices.json"
    symbols = json.loads(fixture.read_text("utf-8"))["prices"]
    return [
        {"symbol": symbol, "name": SUPPORTED_INSTRUMENTS[symbol].name}
        for symbol in symbols if symbol in SUPPORTED_INSTRUMENTS
    ]


@router.get("/assets/search")
async def search_assets(
    q: str = Query(min_length=1, max_length=64),
    settings: Settings = Depends(get_settings),
    _user_id: str = Depends(current_user_id),
) -> dict[str, list[dict[str, str]]]:
    if settings.market_data_provider == "sample":
        return {"results": search_catalog(_sample_assets(), q)}
    if not settings.has_alpaca_keys:
        raise api_error(503, "ALPACA_NOT_CONFIGURED", "Stock search needs Alpaca credentials on the backend.")
    try:
        results = await run_in_threadpool(
            search_alpaca_assets,
            q,
            settings.alpaca_api_key.get_secret_value().strip(),
            settings.alpaca_api_secret.get_secret_value().strip(),
            settings.alpaca_assets_base_url,
            min(settings.market_data_timeout_seconds, 10),
        )
    except AssetLookupUnavailable as exc:
        log_failure("ALPACA_ASSET_SEARCH_UNAVAILABLE", exc)
        raise api_error(502, "ALPACA_ASSET_SEARCH_UNAVAILABLE", str(exc)) from exc
    return {"results": results}


@router.get("/quotes")
async def live_quotes(
    symbols: list[str] = Query(min_length=1, max_length=MAX_QUOTE_SYMBOLS),
    settings: Settings = Depends(get_settings),
    _user_id: str = Depends(current_user_id),
) -> LiveQuotesResponse:
    normalized = [symbol.strip().upper() for symbol in symbols]
    if (
        any(len(symbol) > 20 or not re.fullmatch(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*", symbol, flags=re.ASCII) for symbol in normalized)
        or len(set(normalized)) != len(normalized)
    ):
        raise api_error(422, "INVALID_QUOTES_REQUEST", f"Provide one to {MAX_QUOTE_SYMBOLS} unique stock symbols, each at most 20 characters.")
    if not settings.has_alpaca_keys:
        raise api_error(503, "ALPACA_NOT_CONFIGURED", "Live quotes are unavailable. Configure ALPACA_API_KEY and ALPACA_API_SECRET on the backend.")
    try:
        payload = await run_in_threadpool(
            fetch_alpaca_quotes,
            normalized,
            settings.alpaca_api_key.get_secret_value().strip(),
            settings.alpaca_api_secret.get_secret_value().strip(),
            min(settings.market_data_timeout_seconds, 10),
        )
        return LiveQuotesResponse.model_validate(payload)
    except (AlpacaQuotesUnavailable, ValidationError) as exc:
        log_failure("ALPACA_QUOTES_UNAVAILABLE", exc)
        message = str(exc) if isinstance(exc, AlpacaQuotesUnavailable) else "Alpaca returned an invalid snapshot response."
        raise api_error(502, "ALPACA_QUOTES_UNAVAILABLE", message) from exc


def require_portfolio(store: PortfolioStore, portfolio_id: str, owner_id: str) -> Portfolio:
    portfolio = store.get(portfolio_id, owner_id)
    if portfolio is None:
        raise api_error(404, "PORTFOLIO_NOT_FOUND", "Portfolio not found.")
    return portfolio


def require_portfolio_history(request: PortfolioInput, provider: QuantProvider) -> None:
    try:
        provider.market_history(sorted(request.weights), 2)
    except RateLimitError as exc:
        raise api_error(429, "PROVIDER_RATE_LIMIT", "Price history validation is rate limited. Try again shortly.") from exc
    except MarketHistoryNotFound as exc:
        raise api_error(422, "UNSUPPORTED_PORTFOLIO_SYMBOL", "We couldn't find price history for one or more holdings. Check the ticker and try again.") from exc
    except ProviderUnavailable as exc:
        raise api_error(502, "MARKET_HISTORY_UNAVAILABLE", "Could not verify price history right now. Try again shortly.") from exc


def require_supported_symbol_union(saved_weights: dict[str, float], proposed_weights: dict[str, float]) -> None:
    symbol_count = len(set(saved_weights) | set(proposed_weights))
    if symbol_count > MAX_PORTFOLIO_SYMBOLS:
        raise api_error(
            422,
            "SYMBOL_LIMIT_EXCEEDED",
            f"Saved and proposed allocations may contain at most {MAX_PORTFOLIO_SYMBOLS} distinct symbols combined.",
        )


def metrics_payload(metrics: AnalyticsSnapshot) -> dict:
    largest = max(metrics.weights, key=metrics.weights.get)
    return {
        "portfolio_id": metrics.portfolio_id,
        "as_of": metrics.data_as_of, "lookback_days": metrics.lookback_trading_days,
        "portfolio_return": metrics.portfolio_return,
        "annualized_return": metrics.annualized_return,
        "max_drawdown": metrics.max_drawdown,
        "portfolio_volatility": metrics.portfolio_volatility,
        "asset_volatility": metrics.asset_volatility,
        "correlation_matrix": metrics.correlation_matrix,
        "risk_contribution": metrics.risk_contribution,
        "concentration": {"largest_position": largest, "largest_weight": metrics.weights[largest]},
        "data_quality": {"source": metrics.data_source, "freshness": metrics.freshness, "warnings": metrics.notes},
        "weights": metrics.weights, "data_mode": metrics.data_mode,
        "observation_count": metrics.observation_count, "return_frequency": metrics.return_frequency,
        "volatility_unit": metrics.volatility_unit, "assumptions": metrics.assumptions,
        "return_contribution": metrics.return_contribution, "series": metrics.series,
    }


@router.post("/portfolios", response_model=Portfolio, status_code=201)
def create_portfolio(request: PortfolioInput, store: PortfolioStore = Depends(get_store), provider: QuantProvider = Depends(get_provider), owner_id: str = Depends(current_user_id)):
    require_portfolio_history(request, provider)
    return store.create(request, owner_id)


@router.get("/portfolios", response_model=list[Portfolio])
def list_portfolios(store: PortfolioStore = Depends(get_store), owner_id: str = Depends(current_user_id)):
    return store.list_for_owner(owner_id)


@router.get("/portfolios/{portfolio_id}", response_model=Portfolio)
def get_portfolio(portfolio_id: str, store: PortfolioStore = Depends(get_store), owner_id: str = Depends(current_user_id)):
    return require_portfolio(store, portfolio_id, owner_id)


@router.put("/portfolios/{portfolio_id}", response_model=Portfolio)
def update_portfolio(
    portfolio_id: str, request: PortfolioInput,
    store: PortfolioStore = Depends(get_store), provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    require_portfolio(store, portfolio_id, owner_id)
    require_portfolio_history(request, provider)
    updated = store.update(portfolio_id, owner_id, request)
    if updated is None:
        raise api_error(404, "PORTFOLIO_NOT_FOUND", "Portfolio not found.")
    return updated


@router.delete("/portfolios/{portfolio_id}", status_code=204)
def delete_portfolio(
    portfolio_id: str, store: PortfolioStore = Depends(get_store),
    owner_id: str = Depends(current_user_id),
):
    if not store.delete(portfolio_id, owner_id):
        raise api_error(404, "PORTFOLIO_NOT_FOUND", "Portfolio not found.")


def calculate_metrics(portfolio: Portfolio, provider: QuantProvider) -> AnalyticsSnapshot:
    try:
        result = provider.analyze(portfolio.model_copy(deep=True))
        payload = result.model_dump() if isinstance(result, AnalyticsSnapshot) else result
        metrics = AnalyticsSnapshot.model_validate(payload)
        if metrics.portfolio_id != portfolio.portfolio_id or metrics.weights != portfolio.weights:
            raise ValueError("Provider returned metrics for a different portfolio/allocation.")
    except IntegrationPending as exc:
        raise api_error(501, "QUANT_INTEGRATION_PENDING", str(exc)) from exc
    except SymbolLimitExceeded as exc:
        raise api_error(422, "SYMBOL_LIMIT_EXCEEDED", str(exc)) from exc
    except RateLimitError as exc:
        raise api_error(429, "PROVIDER_RATE_LIMIT", str(exc)) from exc
    except MarketHistoryNotFound as exc:
        log_failure("MARKET_HISTORY_NOT_FOUND", exc)
        raise api_error(404, "MARKET_HISTORY_NOT_FOUND", "Market history is unavailable for one or more portfolio symbols.") from exc
    except (ValidationError, ValueError) as exc:
        log_failure("INVALID_PROVIDER_DATA", exc)
        raise api_error(502, "INVALID_PROVIDER_DATA", "Provider returned inconsistent analysis data.") from exc
    except ProviderUnavailable as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "Analysis is unavailable. Check Alpaca credentials, selected history feed, entitlement, and provider status.") from exc
    except Exception as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "Analysis is unavailable. Check the selected market-data provider.") from exc
    return metrics


@router.get("/portfolios/{portfolio_id}/metrics", response_model=CurrentMetricsResponse)
def current_metrics(
    portfolio_id: str, store: PortfolioStore = Depends(get_store),
    provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    portfolio = require_portfolio(store, portfolio_id, owner_id)
    metrics = calculate_metrics(portfolio, provider)
    latest = require_portfolio(store, portfolio_id, owner_id)
    if latest.revision != portfolio.revision:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed during calculation. Retry.")
    return CurrentMetricsResponse(
        **metrics_payload(metrics), portfolio_revision=portfolio.revision,
        calculated_at=datetime.now(timezone.utc),
    )


@router.get("/market-history", response_model=MarketHistoryResponse)
def market_history(
    symbols: list[str] = Query(min_length=1, max_length=MAX_PORTFOLIO_SYMBOLS),
    lookback_days: int = Query(default=252, ge=1, le=1000),
    provider: QuantProvider = Depends(get_provider),
):
    normalized = [symbol.strip().upper() for symbol in symbols]
    if any(not symbol or len(symbol) > 20 for symbol in normalized) or len(set(normalized)) != len(normalized):
        raise api_error(422, "INVALID_MARKET_HISTORY_REQUEST", f"Provide one to {MAX_PORTFOLIO_SYMBOLS} unique symbols.")
    try:
        return provider.market_history(normalized, lookback_days)
    except RateLimitError as exc:
        raise api_error(429, "PROVIDER_RATE_LIMIT", str(exc)) from exc
    except MarketHistoryNotFound as exc:
        log_failure("MARKET_HISTORY_NOT_FOUND", exc)
        raise api_error(404, "MARKET_HISTORY_UNAVAILABLE", "Market history is unavailable for one or more requested symbols.") from exc
    except ProviderUnavailable as exc:
        log_failure("MARKET_HISTORY_UNAVAILABLE", exc)
        raise api_error(502, "MARKET_HISTORY_UNAVAILABLE", "Market data is unavailable. Check Alpaca credentials, selected history feed, entitlement, and provider status.") from exc


async def current_workflow_response(
    workflow: str, portfolio_id: str, request: AnalysisWorkflowRequest,
    store: PortfolioStore, provider: QuantProvider, settings: Settings, owner_id: str,
) -> AIWorkflowResponse:
    portfolio = await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    if portfolio.revision != request.portfolio_revision:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed. Refresh its metrics before asking for an explanation.")
    metrics = await run_in_threadpool(calculate_metrics, portfolio, provider)
    context = CurrentMetricsResponse(
        **metrics_payload(metrics), portfolio_revision=portfolio.revision,
        calculated_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")
    fallback, citations = (
        portfolio_briefing_summary(metrics) if workflow == "analysis_briefing"
        else metric_summary(metrics)
    )
    title = "Portfolio briefing" if workflow == "analysis_briefing" else "Risk explanation"
    warnings = list(metrics.notes)
    if settings.analyst_mode == "demo":
        warnings.append("Offline demo response; Gemini was not called.")
        output = AIWorkflowResponse(
            workflow=workflow, analyst_mode="demo", status="demo",
            answer=f"{title} is disabled in demo mode. Current metrics: {fallback}",
            citations=citations, warnings=warnings,
            portfolio_revision=portfolio.revision, metrics=context,
        )
    else:
        try:
            generated = await generate_analysis_workflow(
                workflow, request.question, metrics, settings,
            )
        except (GeminiNotConfigured, GeminiUnavailable) as exc:
            code = "GEMINI_NOT_CONFIGURED" if isinstance(exc, GeminiNotConfigured) else "GEMINI_UNAVAILABLE"
            log_failure(code, exc)
            output = AIWorkflowResponse(
                workflow=workflow, analyst_mode="gemini", status="unavailable",
                answer=f"{title} is unavailable right now. Current metrics: {fallback}",
                citations=citations, warnings=[*warnings, str(exc)], error_code=code,
                portfolio_revision=portfolio.revision, metrics=context,
            )
        else:
            output = AIWorkflowResponse(
                workflow=workflow, analyst_mode="gemini", status="complete",
                warnings=warnings, portfolio_revision=portfolio.revision,
                metrics=context, **generated,
            )
    latest = await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    if latest.revision != portfolio.revision:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed while the explanation was prepared. Retry.")
    return output


@router.post(
    "/portfolios/{portfolio_id}/briefing",
    response_model=AIWorkflowResponse,
)
async def analysis_briefing(
    portfolio_id: str,
    request: AnalysisWorkflowRequest,
    store: PortfolioStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    return await current_workflow_response(
        "analysis_briefing", portfolio_id, request, store, provider, settings, owner_id,
    )


@router.post(
    "/portfolios/{portfolio_id}/risk/explanation",
    response_model=AIWorkflowResponse,
)
async def risk_explanation(
    portfolio_id: str,
    request: AnalysisWorkflowRequest,
    store: PortfolioStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    return await current_workflow_response(
        "risk_explanation", portfolio_id, request, store, provider, settings, owner_id,
    )


@router.post(
    "/portfolios/{portfolio_id}/what-if/explanation",
    response_model=AIWorkflowResponse,
)
async def scenario_explanation(
    portfolio_id: str,
    request: ScenarioExplanationRequest,
    store: PortfolioStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    portfolio = await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    require_supported_symbol_union(portfolio.weights, request.proposed_weights)
    if request.portfolio_revision is None:
        raise api_error(422, "MISSING_CONTEXT", "Select a portfolio revision for this explanation.")
    if request.portfolio_revision != portfolio.revision:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed. Recalculate this comparison.")
    comparison = await run_in_threadpool(
        what_if, portfolio_id,
        AllocationInput(holdings=[{"symbol": symbol, "weight": weight}
                                  for symbol, weight in request.proposed_weights.items()]),
        store, provider, owner_id,
    )
    baseline = AnalyticsSnapshot.model_validate(comparison["current_analysis"])
    warnings = list(baseline.notes)
    if settings.analyst_mode == "demo":
        warnings.append("Offline demo response; Gemini was not called.")
        output = AIWorkflowResponse(
            workflow="scenario_explanation", analyst_mode="demo", status="demo",
            answer="AI explanations are disabled in demo mode. The matched modeled comparison is available below.",
            portfolio_revision=portfolio.revision, comparison=comparison, warnings=warnings,
        )
    else:
        try:
            generated = await generate_scenario_workflow(request.question, comparison, settings)
        except (GeminiNotConfigured, GeminiUnavailable) as exc:
            code = "GEMINI_NOT_CONFIGURED" if isinstance(exc, GeminiNotConfigured) else "GEMINI_UNAVAILABLE"
            log_failure(code, exc)
            output = AIWorkflowResponse(
                workflow="scenario_explanation", analyst_mode="gemini", status="unavailable",
                answer="AI explanation is unavailable. The matched modeled comparison is available below.",
                portfolio_revision=portfolio.revision, comparison=comparison,
                warnings=[*warnings, str(exc)], error_code=code,
            )
        else:
            output = AIWorkflowResponse(
                workflow="scenario_explanation", analyst_mode="gemini", status="complete",
                portfolio_revision=portfolio.revision, comparison=comparison,
                warnings=warnings, **generated,
            )
    latest = await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    if latest.revision != portfolio.revision:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed while the explanation was prepared. Retry.")
    return output


@router.post(
    "/research/{symbol}/summary",
    response_model=AIWorkflowResponse,
)
async def research_summary(
    symbol: str,
    request: ResearchSummaryRequest,
    settings: Settings = Depends(get_settings),
):
    normalized_symbol = symbol.strip().upper()
    source = curated_research_source(normalized_symbol, request.source_id)
    if source is None:
        raise api_error(404, "RESEARCH_SOURCE_NOT_FOUND", "No curated source is available for this asset.")
    if settings.analyst_mode == "demo":
        return AIWorkflowResponse(
            workflow="research_summary",
            analyst_mode="demo",
            status="demo",
            symbol=normalized_symbol,
            source_url=source["url"],
            answer="AI source summaries are disabled in demo mode. Open the selected official source to review its content.",
            warnings=["Gemini and URL Context were not called."],
        )
    try:
        output = await generate_research_summary(
            normalized_symbol, source["url"], settings
        )
    except (GeminiNotConfigured, GeminiUnavailable) as exc:
        error_code = (
            "GEMINI_NOT_CONFIGURED"
            if isinstance(exc, GeminiNotConfigured)
            else "GEMINI_UNAVAILABLE"
        )
        log_failure(error_code, exc)
        evidence = exc.evidence if isinstance(exc, GeminiUnavailable) else {}
        return AIWorkflowResponse(
            workflow="research_summary",
            analyst_mode="gemini",
            status="unavailable",
            symbol=normalized_symbol,
            source_url=source["url"],
            answer="The selected source could not be summarized. Open the source to review its content.",
            warnings=[str(exc)],
            error_code=error_code,
            **evidence,
        )
    return AIWorkflowResponse(
        workflow="research_summary",
        analyst_mode="gemini",
        status="complete",
        symbol=normalized_symbol,
        source_url=source["url"],
        **output,
    )


@router.post("/portfolios/{portfolio_id}/what-if")
def what_if(
    portfolio_id: str, request: AllocationInput,
    store: PortfolioStore = Depends(get_store), provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    portfolio = require_portfolio(store, portfolio_id, owner_id)
    require_supported_symbol_union(portfolio.weights, request.weights)
    try:
        comparison = provider.simulate(
            WhatIfRequest(portfolio_id=portfolio_id, proposed_weights=request.weights), portfolio
        )
    except IntegrationPending as exc:
        raise api_error(501, "QUANT_INTEGRATION_PENDING", str(exc)) from exc
    except SymbolLimitExceeded as exc:
        raise api_error(422, "SYMBOL_LIMIT_EXCEEDED", str(exc)) from exc
    except RateLimitError as exc:
        raise api_error(429, "PROVIDER_RATE_LIMIT", str(exc)) from exc
    except MarketHistoryNotFound as exc:
        log_failure("MARKET_HISTORY_NOT_FOUND", exc)
        raise api_error(404, "MARKET_HISTORY_NOT_FOUND", "Market history is unavailable for one or more allocation symbols.") from exc
    except ProviderUnavailable as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "What-if analysis is unavailable. Check the selected market-data provider, API key, quota, and supported symbols.") from exc
    except Exception as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "What-if analysis is unavailable. Check the selected market-data provider, API key, quota, and supported symbols.") from exc
    latest = require_portfolio(store, portfolio_id, owner_id)
    if latest.revision != portfolio.revision:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed during comparison. Retry.")
    return {
        **comparison,
        "portfolio_revision": portfolio.revision,
        "calculated_at": datetime.now(timezone.utc),
        "modeled_result": True,
    }
