from datetime import datetime
from functools import lru_cache
import json
import math
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
    AnalysisResponse,
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
from .storage import PortfolioStore, SnapshotNotFound, StalePortfolio


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


def require_supported_symbol_union(saved_weights: dict[str, float], proposed_weights: dict[str, float]) -> None:
    symbol_count = len(set(saved_weights) | set(proposed_weights))
    if symbol_count > MAX_PORTFOLIO_SYMBOLS:
        raise api_error(
            422,
            "SYMBOL_LIMIT_EXCEEDED",
            f"Saved and proposed allocations may contain at most {MAX_PORTFOLIO_SYMBOLS} distinct symbols combined.",
        )


def scenario_matches_snapshot(
    metrics: AnalyticsSnapshot,
    comparison: dict,
    proposed_weights: dict[str, float],
) -> bool:
    """Reject scenario narratives whose recomputed baseline differs from the selected snapshot."""
    def same_number(expected, actual) -> bool:
        if expected is None or actual is None:
            return expected is actual
        return math.isclose(float(expected), float(actual), rel_tol=0, abs_tol=1e-9)

    def same_numeric_map(expected, actual) -> bool:
        if expected is None or actual is None:
            return expected is actual
        return all(
            symbol in actual and same_number(value, actual[symbol])
            for symbol, value in expected.items()
        )

    def same_correlation_matrix(expected, actual) -> bool:
        if expected is None or actual is None:
            return expected is actual
        return all(
            symbol in actual
            and all(
                other in actual[symbol] and same_number(value, actual[symbol][other])
                for other, value in row.items()
            )
            for symbol, row in expected.items()
        )

    def same_series(expected, actual) -> bool:
        if expected is None or actual is None:
            return expected is actual
        if (
            expected.dates != actual.dates
            or not same_numeric_map(
                {str(index): value for index, value in enumerate(expected.portfolio_index)},
                {str(index): value for index, value in enumerate(actual.portfolio_index)},
            )
        ):
            return False
        return all(
            symbol in actual.asset_index
            and len(values) == len(actual.asset_index[symbol])
            and all(same_number(value, actual.asset_index[symbol][index]) for index, value in enumerate(values))
            for symbol, values in expected.asset_index.items()
        ) and same_numeric_map(expected.return_contribution, actual.return_contribution)

    try:
        baseline = AnalyticsSnapshot.model_validate(comparison["current_analysis"])
        proposed = AnalyticsSnapshot.model_validate(comparison["proposed_analysis"])
        positive_weights = {
            symbol: weight for symbol, weight in baseline.weights.items() if weight > 0
        }
        if baseline.portfolio_id != metrics.portfolio_id or positive_weights != metrics.weights:
            return False
        if (
            baseline.data_mode != metrics.data_mode
            or baseline.data_as_of != metrics.data_as_of
            or baseline.lookback_trading_days != metrics.lookback_trading_days
            or baseline.observation_count != metrics.observation_count
            or baseline.return_frequency != metrics.return_frequency
            or baseline.volatility_unit != metrics.volatility_unit
            or baseline.data_source != metrics.data_source
            or baseline.freshness != metrics.freshness
            or baseline.notes != metrics.notes
            or baseline.assumptions != metrics.assumptions
            or {symbol: weight for symbol, weight in proposed.weights.items() if weight > 0}
            != {symbol: weight for symbol, weight in proposed_weights.items() if weight > 0}
        ):
            return False
        for field in ("portfolio_return", "annualized_return", "max_drawdown", "portfolio_volatility"):
            expected = getattr(metrics, field)
            actual = getattr(baseline, field)
            if not same_number(expected, actual):
                return False
        if (
            not same_numeric_map(metrics.risk_contribution, baseline.risk_contribution)
            or not same_numeric_map(metrics.asset_volatility, baseline.asset_volatility)
            or not same_numeric_map(metrics.return_contribution, baseline.return_contribution)
            or not same_correlation_matrix(metrics.correlation_matrix, baseline.correlation_matrix)
            or not same_series(metrics.series, baseline.series)
        ):
            return False
        return True
    except (KeyError, TypeError, ValidationError, ValueError):
        return False


def analysis_response(metrics: AnalyticsSnapshot, analysis_id: str, created_at: datetime) -> AnalysisResponse:
    largest = max(metrics.weights, key=metrics.weights.get)
    return AnalysisResponse(
        analysis_id=analysis_id, portfolio_id=metrics.portfolio_id, created_at=created_at,
        as_of=metrics.data_as_of, lookback_days=metrics.lookback_trading_days,
        portfolio_return=metrics.portfolio_return,
        annualized_return=metrics.annualized_return,
        max_drawdown=metrics.max_drawdown,
        portfolio_volatility=metrics.portfolio_volatility,
        asset_volatility=metrics.asset_volatility, correlation_matrix=metrics.correlation_matrix,
        risk_contribution=metrics.risk_contribution,
        concentration={"largest_position": largest, "largest_weight": metrics.weights[largest]},
        data_quality={"source": metrics.data_source, "freshness": metrics.freshness, "warnings": metrics.notes},
        weights=metrics.weights, data_mode=metrics.data_mode,
        observation_count=metrics.observation_count, return_frequency=metrics.return_frequency,
        volatility_unit=metrics.volatility_unit, assumptions=metrics.assumptions,
        return_contribution=metrics.return_contribution, series=metrics.series,
    )


@router.post("/portfolios", response_model=Portfolio, status_code=201)
def create_portfolio(request: PortfolioInput, store: PortfolioStore = Depends(get_store), owner_id: str = Depends(current_user_id)):
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
    store: PortfolioStore = Depends(get_store), owner_id: str = Depends(current_user_id),
):
    require_portfolio(store, portfolio_id, owner_id)
    updated = store.update(portfolio_id, owner_id, request)
    if updated is None:
        raise api_error(404, "PORTFOLIO_NOT_FOUND", "Portfolio not found.")
    return updated


@router.post("/portfolios/{portfolio_id}/analysis", response_model=AnalysisResponse)
def analyze(
    portfolio_id: str, store: PortfolioStore = Depends(get_store),
    provider: QuantProvider = Depends(get_provider),
    owner_id: str = Depends(current_user_id),
):
    portfolio = require_portfolio(store, portfolio_id, owner_id)
    try:
        result = provider.analyze(portfolio.model_copy(deep=True))
        payload = result.model_dump() if isinstance(result, AnalyticsSnapshot) else result
        metrics = AnalyticsSnapshot.model_validate(payload)
        if metrics.portfolio_id != portfolio_id or metrics.weights != portfolio.weights:
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
    try:
        analysis_id, created_at = store.save_analysis(metrics, owner_id)
    except StalePortfolio as exc:
        raise api_error(409, "PORTFOLIO_CHANGED", "Portfolio changed during analysis. Retry analysis.") from exc
    return analysis_response(metrics, analysis_id, created_at)


@router.get("/portfolios/{portfolio_id}/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(portfolio_id: str, analysis_id: str, store: PortfolioStore = Depends(get_store), owner_id: str = Depends(current_user_id)):
    require_portfolio(store, portfolio_id, owner_id)
    try:
        metrics, created_at = store.get_analysis(portfolio_id, analysis_id)
    except SnapshotNotFound as exc:
        raise api_error(404, "ANALYSIS_NOT_FOUND", "Analysis not found for this portfolio.") from exc
    return analysis_response(metrics, analysis_id, created_at)


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


async def analysis_workflow_response(
    workflow: str,
    portfolio_id: str,
    request: AnalysisWorkflowRequest,
    store: PortfolioStore,
    settings: Settings,
) -> AIWorkflowResponse:
    title = "Portfolio briefing" if workflow == "analysis_briefing" else "Risk explanation"
    try:
        metrics, _ = await run_in_threadpool(
            store.get_analysis, portfolio_id, request.analysis_id
        )
    except SnapshotNotFound as exc:
        raise api_error(404, "ANALYSIS_NOT_FOUND", "Analysis not found for this portfolio.") from exc
    warnings = list(metrics.notes)
    if metrics.freshness == "stale":
        warnings.append("This saved snapshot contains stale market data.")
    fallback, citations = (
        portfolio_briefing_summary(metrics)
        if workflow == "analysis_briefing"
        else metric_summary(metrics)
    )
    if settings.analyst_mode == "demo":
        warnings.append("Offline demo response; Gemini was not called.")
        return AIWorkflowResponse(
            workflow=workflow,
            analyst_mode="demo",
            status="demo",
            analysis_id=request.analysis_id,
            answer=f"{title} is disabled in demo mode. Saved metrics: {fallback}",
            citations=citations,
            warnings=warnings,
        )
    try:
        output = await generate_analysis_workflow(
            workflow, request.question, metrics, request.analysis_id, settings
        )
    except (GeminiNotConfigured, GeminiUnavailable) as exc:
        error_code = (
            "GEMINI_NOT_CONFIGURED"
            if isinstance(exc, GeminiNotConfigured)
            else "GEMINI_UNAVAILABLE"
        )
        log_failure(error_code, exc)
        warnings.append(str(exc))
        return AIWorkflowResponse(
            workflow=workflow,
            analyst_mode="gemini",
            status="unavailable",
            analysis_id=request.analysis_id,
            answer=f"{title} is unavailable right now. Saved metrics: {fallback}",
            citations=citations,
            warnings=warnings,
            error_code=error_code,
        )
    return AIWorkflowResponse(
        workflow=workflow,
        analyst_mode="gemini",
        status="complete",
        analysis_id=request.analysis_id,
        warnings=warnings,
        **output,
    )


@router.post(
    "/portfolios/{portfolio_id}/briefing",
    response_model=AIWorkflowResponse,
)
async def analysis_briefing(
    portfolio_id: str,
    request: AnalysisWorkflowRequest,
    store: PortfolioStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    owner_id: str = Depends(current_user_id),
):
    await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    return await analysis_workflow_response(
        "analysis_briefing", portfolio_id, request, store, settings
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
    owner_id: str = Depends(current_user_id),
):
    await run_in_threadpool(require_portfolio, store, portfolio_id, owner_id)
    return await analysis_workflow_response(
        "risk_explanation", portfolio_id, request, store, settings
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
    try:
        metrics, _ = await run_in_threadpool(
            store.get_analysis, portfolio_id, request.analysis_id
        )
    except SnapshotNotFound as exc:
        raise api_error(404, "ANALYSIS_NOT_FOUND", "Analysis not found for this portfolio.") from exc
    if metrics.weights != portfolio.weights:
        raise api_error(
            409,
            "ANALYSIS_ALLOCATION_MISMATCH",
            "The selected analysis no longer matches the saved portfolio allocation.",
        )
    try:
        comparison = await run_in_threadpool(
            provider.simulate,
            WhatIfRequest(
                portfolio_id=portfolio_id,
                proposed_weights=request.proposed_weights,
            ),
            portfolio,
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
        raise api_error(502, "PROVIDER_UNAVAILABLE", "Market data is unavailable for the requested scenario.") from exc
    except (ValidationError, ValueError) as exc:
        log_failure("INVALID_SCENARIO_COMPARISON", exc)
        raise api_error(502, "INVALID_SCENARIO_COMPARISON", "The quant provider returned an invalid comparison.") from exc
    except Exception as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "What-if provider is currently unavailable.") from exc
    if not scenario_matches_snapshot(metrics, comparison, request.proposed_weights):
        raise api_error(
            409,
            "ANALYSIS_STALE",
            "The comparison baseline differs from the selected analysis. Recalculate the active analysis before explaining this scenario.",
        )
    warnings = list(metrics.notes)
    if metrics.freshness == "stale":
        warnings.append("This saved snapshot contains stale market data.")
    if settings.analyst_mode == "demo":
        warnings.append("Offline demo response; Gemini was not called.")
        return AIWorkflowResponse(
            workflow="scenario_explanation",
            analyst_mode="demo",
            status="demo",
            analysis_id=request.analysis_id,
            answer="AI explanations are disabled in demo mode. The server-calculated comparison remains available in the What-if workspace.",
            warnings=warnings,
        )
    try:
        output = await generate_scenario_workflow(
            request.question,
            comparison,
            settings,
            analysis_id=request.analysis_id,
        )
    except (GeminiNotConfigured, GeminiUnavailable) as exc:
        error_code = (
            "GEMINI_NOT_CONFIGURED"
            if isinstance(exc, GeminiNotConfigured)
            else "GEMINI_UNAVAILABLE"
        )
        log_failure(error_code, exc)
        warnings.append(str(exc))
        return AIWorkflowResponse(
            workflow="scenario_explanation",
            analyst_mode="gemini",
            status="unavailable",
            analysis_id=request.analysis_id,
            answer="AI explanation is unavailable. The server-calculated comparison remains available in the What-if workspace.",
            warnings=warnings,
            error_code=error_code,
        )
    return AIWorkflowResponse(
        workflow="scenario_explanation",
        analyst_mode="gemini",
        status="complete",
        analysis_id=request.analysis_id,
        warnings=warnings,
        **output,
    )


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
        return provider.simulate(
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
