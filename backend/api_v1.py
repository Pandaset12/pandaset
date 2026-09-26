from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .observability import log_failure
from .gemini_service import GeminiNotConfigured, GeminiUnavailable, generate_answer, metric_summary
from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable, SymbolLimitExceeded
from .providers import IntegrationPending, QuantProvider, get_provider
from .schemas import (
    MAX_PORTFOLIO_SYMBOLS, AllocationInput, AnalysisResponse, AnalystRequest, AnalystResponse,
    AnalyticsSnapshot, AskRequest, MarketHistoryResponse, Portfolio, PortfolioInput, WhatIfRequest,
)
from .storage import PortfolioStore, SnapshotNotFound


router = APIRouter(prefix="/api/v1", tags=["PortfolioLens v1"])


def get_store(request: Request) -> PortfolioStore:
    return request.app.state.store


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def require_portfolio(store: PortfolioStore, portfolio_id: str) -> Portfolio:
    portfolio = store.get(portfolio_id)
    if portfolio is None:
        raise api_error(404, "PORTFOLIO_NOT_FOUND", "Portfolio not found.")
    return portfolio


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
def create_portfolio(request: PortfolioInput, store: PortfolioStore = Depends(get_store)):
    return store.create(request)


@router.get("/portfolios/{portfolio_id}", response_model=Portfolio)
def get_portfolio(portfolio_id: str, store: PortfolioStore = Depends(get_store)):
    return require_portfolio(store, portfolio_id)


@router.post("/portfolios/{portfolio_id}/analysis", response_model=AnalysisResponse)
def analyze(
    portfolio_id: str, store: PortfolioStore = Depends(get_store),
    provider: QuantProvider = Depends(get_provider),
):
    portfolio = require_portfolio(store, portfolio_id)
    try:
        result = provider.analyze(portfolio.model_copy(deep=True))
        payload = result.model_dump() if isinstance(result, AnalyticsSnapshot) else result
        metrics = AnalyticsSnapshot.model_validate(payload)
        if metrics.portfolio_id != portfolio_id or metrics.weights != portfolio.weights:
            raise ValueError("Provider returned metrics for a different portfolio/allocation.")
    except SymbolLimitExceeded as exc:
        raise api_error(422, "SYMBOL_LIMIT_EXCEEDED", str(exc)) from exc
    except MarketHistoryNotFound as exc:
        log_failure("MARKET_HISTORY_NOT_FOUND", exc)
        raise api_error(404, "MARKET_HISTORY_NOT_FOUND", "Market history is unavailable for one or more portfolio symbols.") from exc
    except (ValidationError, ValueError) as exc:
        log_failure("INVALID_PROVIDER_DATA", exc)
        raise api_error(502, "INVALID_PROVIDER_DATA", "Provider returned inconsistent analysis data.") from exc
    except Exception as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "Analysis is unavailable. For Twelve Data, set TWELVE_DATA_API_KEY in backend/.env; also check key validity, usage limits, supported symbols, and provider status.") from exc
    analysis_id, created_at = store.save_analysis(metrics)
    return analysis_response(metrics, analysis_id, created_at)


@router.get("/portfolios/{portfolio_id}/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(portfolio_id: str, analysis_id: str, store: PortfolioStore = Depends(get_store)):
    require_portfolio(store, portfolio_id)
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
    except MarketHistoryNotFound as exc:
        log_failure("MARKET_HISTORY_NOT_FOUND", exc)
        raise api_error(404, "MARKET_HISTORY_UNAVAILABLE", "Market history is unavailable for one or more requested symbols.") from exc
    except ProviderUnavailable as exc:
        log_failure("MARKET_HISTORY_UNAVAILABLE", exc)
        raise api_error(502, "MARKET_HISTORY_UNAVAILABLE", "Market data is unavailable. If Twelve Data is selected, set TWELVE_DATA_API_KEY in backend/.env; also check the key, quota, requested symbols, and provider status.") from exc


@router.post("/portfolios/{portfolio_id}/ask", response_model=AnalystResponse)
async def ask(
    portfolio_id: str, request: AskRequest, store: PortfolioStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
):
    await run_in_threadpool(require_portfolio, store, portfolio_id)
    try:
        metrics, _ = await run_in_threadpool(store.get_analysis, portfolio_id, request.analysis_id)
    except SnapshotNotFound as exc:
        raise api_error(404, "ANALYSIS_NOT_FOUND", "Analysis not found for this portfolio.") from exc
    warnings = list(metrics.notes)
    if metrics.freshness == "stale":
        warnings.append("This saved snapshot contains stale market data.")
    summary, citations = metric_summary(metrics)
    common = dict(
        analyst_mode=settings.analyst_mode, metrics=metrics,
        analysis_id=request.analysis_id, warnings=warnings,
    )
    if settings.analyst_mode == "demo":
        warnings.append("Offline demo response; Gemini and web tools were not called.")
        return AnalystResponse(
            **common, status="demo", citations=citations,
            answer="Offline snapshot summary; this does not answer arbitrary questions. " + summary,
        )
    question = AnalystRequest(
        portfolio_id=portfolio_id, **request.model_dump(exclude={"analysis_id"})
    )
    try:
        output = await generate_answer(question, metrics, settings)
    except (GeminiNotConfigured, GeminiUnavailable) as exc:
        log_failure("GEMINI_NOT_CONFIGURED" if isinstance(exc, GeminiNotConfigured) else "GEMINI_UNAVAILABLE", exc)
        warnings.append(str(exc))
        return AnalystResponse(
            **common, status="unavailable", citations=citations,
            error_code="GEMINI_NOT_CONFIGURED" if isinstance(exc, GeminiNotConfigured) else "GEMINI_UNAVAILABLE",
            answer="AI explanation is unavailable. The saved metrics remain accessible. " + summary,
        )
    return AnalystResponse(**common, status="complete", **output)


@router.post("/portfolios/{portfolio_id}/what-if")
def what_if(
    portfolio_id: str, request: AllocationInput,
    store: PortfolioStore = Depends(get_store), provider: QuantProvider = Depends(get_provider),
):
portfolio = require_portfolio(store, portfolio_id)
symbol_count = len(set(portfolio.weights) | set(request.weights))
if symbol_count > MAX_PORTFOLIO_SYMBOLS:
    raise api_error(
        422, "SYMBOL_LIMIT_EXCEEDED",
        f"Saved and proposed allocations may contain at most {MAX_PORTFOLIO_SYMBOLS} distinct symbols combined.",
    )
    try:
        return provider.simulate(
            WhatIfRequest(portfolio_id=portfolio_id, proposed_weights=request.weights)
        )
    except IntegrationPending as exc:
        raise api_error(501, "QUANT_INTEGRATION_PENDING", str(exc)) from exc
    except SymbolLimitExceeded as exc:
        raise api_error(422, "SYMBOL_LIMIT_EXCEEDED", str(exc)) from exc
    except MarketHistoryNotFound as exc:
        log_failure("MARKET_HISTORY_NOT_FOUND", exc)
        raise api_error(404, "MARKET_HISTORY_NOT_FOUND", "Market history is unavailable for one or more allocation symbols.") from exc
    except ProviderUnavailable as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "What-if analysis is unavailable. Check the selected market-data provider, API key, quota, and supported symbols.") from exc
    except Exception as exc:
        log_failure("PROVIDER_UNAVAILABLE", exc)
        raise api_error(502, "PROVIDER_UNAVAILABLE", "What-if analysis is unavailable. Check the selected market-data provider, API key, quota, and supported symbols.") from exc
