from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from pymongo import MongoClient
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .auth import SupabaseTokenVerifier
from .event_api import router as v2_router
from .event_jobs import EventWorker
from .instruments import SUPPORTED_INSTRUMENTS
from .mongo_store import MongoPortfolioStore
from .alpaca_history import AlpacaHistoryProvider
from .api_v1 import get_store, require_portfolio, router as v1_router
from .auth import current_user_id
from .observability import log_failure, request_id_context
from .storage import PortfolioStore
from .price_cache import RecentPriceCache
from .providers import (
    IntegrationPending,
    QuantProvider,
    get_provider,
    demo_metrics,
)
from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable, SymbolLimitExceeded
from .schemas import (
    AnalyticsSnapshot,
    Portfolio,
    WhatIfRequest,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = await run_in_threadpool(PortfolioStore, settings.storage_path)
        await run_in_threadpool(store.seed_demo, demo_metrics())
        app.state.store = store
        app.state.price_cache = RecentPriceCache()
        worker = None
        verifier = None
        mongo_client = None
        app.state.auth_verifier = None
        app.state.event_store = None
        app.state.event_price_provider = None
        app.state.event_worker = None
        try:
            if settings.event_lab_ready:
                try:
                    verifier = SupabaseTokenVerifier(
                        settings.supabase_url, settings.supabase_publishable_key,
                        signing_mode=settings.supabase_signing_mode,
                    )
                    mongo_client = await run_in_threadpool(
                        MongoClient, settings.mongo_uri.get_secret_value(),
                        serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                    )
                    event_store = await run_in_threadpool(
                        MongoPortfolioStore, "", settings.mongo_database,
                        database=mongo_client[settings.mongo_database],
                        supported_symbol=lambda symbol: symbol in SUPPORTED_INSTRUMENTS,
                        max_active_jobs_per_owner=settings.event_max_active_jobs_per_user,
                        max_messages_per_run=settings.event_max_messages_per_run,
                    )
                    event_price_provider = AlpacaHistoryProvider(
                        settings.alpaca_api_key.get_secret_value(),
                        settings.alpaca_api_secret.get_secret_value(),
                        settings.alpaca_history_feed,
                        timeout_seconds=settings.market_data_timeout_seconds,
                        cache_allowed=settings.alpaca_cache_rights_confirmed,
                        cache_path=(Path(__file__).parent / "data" / "alpaca_adjusted.sqlite3"
                                    if settings.alpaca_cache_rights_confirmed else None),
                    )
                    worker = EventWorker(event_store, settings)
                    worker.start()
                except Exception as exc:
                    log_failure("EVENT_LAB_STARTUP_UNAVAILABLE", exc)
                    if worker is not None:
                        try:
                            await worker.stop()
                        except Exception as cleanup_exc:
                            log_failure("EVENT_LAB_WORKER_CLEANUP_FAILED", cleanup_exc)
                        worker = None
                    if mongo_client is not None:
                        try:
                            mongo_client.close()
                        except Exception as cleanup_exc:
                            log_failure("EVENT_LAB_MONGO_CLEANUP_FAILED", cleanup_exc)
                        mongo_client = None
                    if verifier is not None:
                        try:
                            verifier.http_client.close()
                        except Exception as cleanup_exc:
                            log_failure("EVENT_LAB_AUTH_CLEANUP_FAILED", cleanup_exc)
                        verifier = None
                else:
                    app.state.auth_verifier = verifier
                    app.state.event_store = event_store
                    app.state.event_price_provider = event_price_provider
                    app.state.event_worker = worker
            yield
        finally:
            try:
                if worker is not None:
                    await worker.stop()
            finally:
                try:
                    if mongo_client is not None:
                        mongo_client.close()
                finally:
                    if verifier is not None:
                        verifier.http_client.close()

    application = FastAPI(
        title="PandaSet API",
        version="0.2.0",
        description="PandaSet quantitative portfolio analytics and research API.",
        lifespan=lifespan,
    )
    application.dependency_overrides[get_settings] = lambda: settings
    application.include_router(v1_router)
    application.include_router(v2_router)

    @application.middleware("http")
    async def correlate_request(request: Request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                log_failure("INTERNAL_ERROR", exc)
                error = {"code": "INTERNAL_ERROR", "message": "An internal error occurred.",
                         "request_id": request_id}
                response = JSONResponse(
                    {"error" if request.url.path.startswith(("/api/v1/", "/api/v2/")) else "detail": error},
                    status_code=500,
                )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_context.reset(token)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith(("/api/v1/", "/api/v2/")):
            error = exc.detail if isinstance(exc.detail, dict) else {
                "code": f"HTTP_{exc.status_code}", "message": str(exc.detail)
            }
            error = {**error, "request_id": request.state.request_id}
            return JSONResponse({"error": error}, status_code=exc.status_code, headers=exc.headers)
        return await http_exception_handler(request, exc)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo raw input: it may contain secrets or non-JSON values such as NaN.
        details = [{"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
                   for error in exc.errors()]
        if request.url.path.startswith(("/api/v1/", "/api/v2/")):
            return JSONResponse(
                {"error": {"code": "INVALID_INPUT", "message": "Request validation failed.",
                           "details": details, "request_id": request.state.request_id}},
                status_code=422,
            )
        return JSONResponse({"detail": details}, status_code=422)

    @application.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, exc: sqlite3.Error):
        log_failure("STORAGE_UNAVAILABLE", exc)
        error = {"code": "STORAGE_UNAVAILABLE", "message": "Local portfolio storage is unavailable.",
                 "request_id": request.state.request_id}
        return JSONResponse(
            {"error" if request.url.path.startswith(("/api/v1/", "/api/v2/")) else "detail": error}, status_code=503
        )

    @application.get("/health")
    def health(request: Request, settings: Settings = Depends(get_settings)):
        live_data = settings.market_data_provider == "alpaca"
        market_data_ready = not live_data or settings.has_alpaca_history
        event_store_ready = getattr(request.app.state, "event_store", None) is not None
        analyst_ready = settings.analyst_mode != "gemini" or settings.has_gemini_key
        configuration_issues = []
        if not settings.authentication_enabled:
            configuration_issues.append("AUTH_NOT_CONFIGURED")
        if not analyst_ready:
            configuration_issues.append("GEMINI_NOT_CONFIGURED")
        if not market_data_ready:
            configuration_issues.append("MARKET_DATA_NOT_CONFIGURED")
        if settings.event_lab_enabled and not settings.event_lab_ready:
            configuration_issues.append("EVENT_LAB_NOT_CONFIGURED")
        return {
            "status": "degraded" if configuration_issues or (
                settings.event_lab_enabled and not event_store_ready
            ) else "ok",
            "configuration_issues": configuration_issues,
            "analyst_mode": settings.analyst_mode,
            "analyst_ready": analyst_ready,
            "gemini_configured": settings.has_gemini_key,
            "legacy_quant_integration": "quant_engine_alpaca" if live_data else "quant_engine_sample_prices",
            "legacy_data_mode": "live" if live_data else "demo",
            "legacy_storage_backend": "sqlite",
            "quant_integration": "quant_engine_alpaca" if live_data else "quant_engine_sample_prices",
            "market_data_provider": settings.market_data_provider,
            "market_data_ready": market_data_ready,
            "data_mode": "live" if live_data else "demo",
            "storage_backend": "sqlite",
            "event_data_mode": "live" if event_store_ready else "unavailable" if settings.event_lab_enabled else "disabled",
            "event_storage_backend": "mongo" if event_store_ready else "unavailable" if settings.event_lab_enabled else "disabled",
            "authentication_enabled": settings.authentication_enabled,
            "event_authentication_enabled": getattr(request.app.state, "auth_verifier", None) is not None,
            "event_lab_enabled": settings.event_lab_enabled,
            "event_lab_ready": settings.event_lab_ready and event_store_ready,
            "event_lab_public_ready": settings.event_lab_public_ready and event_store_ready,
            "event_lab_probability_enabled": settings.event_lab_probability_enabled,
        }

    def read_metrics(portfolio: Portfolio, provider: QuantProvider) -> AnalyticsSnapshot:
        try:
            return provider.analyze(portfolio)
        except MarketHistoryNotFound as exc:
            raise HTTPException(status_code=404, detail={
                "code": "market_history_not_found", "message": "Market history is unavailable for one or more portfolio symbols."
            }) from exc
        except SymbolLimitExceeded as exc:
            raise HTTPException(status_code=422, detail={
                "code": "symbol_limit_exceeded", "message": str(exc)
            }) from exc
        except ProviderUnavailable as exc:
            raise HTTPException(status_code=502, detail={
                "code": "provider_unavailable", "message": "Market data is unavailable from the selected provider."
            }) from exc
        except IntegrationPending as exc:
            raise HTTPException(status_code=501, detail={
                "code": "quant_integration_pending", "message": str(exc)
            }) from exc

    @application.get(
        "/api/portfolios/{portfolio_id}/analytics", response_model=AnalyticsSnapshot, deprecated=True
    )
    def analytics(portfolio_id: str, provider: QuantProvider = Depends(get_provider),
                  store: PortfolioStore = Depends(get_store), owner_id: str = Depends(current_user_id)):
        return read_metrics(require_portfolio(store, portfolio_id, owner_id), provider)

    @application.post("/api/what-if", deprecated=True)
    def what_if(
        request: WhatIfRequest,
        provider: QuantProvider = Depends(get_provider),
        store: PortfolioStore = Depends(get_store),
        owner_id: str = Depends(current_user_id),
    ):
        portfolio = require_portfolio(store, request.portfolio_id, owner_id)
        try:
            return provider.simulate(request, portfolio)
        except MarketHistoryNotFound as exc:
            raise HTTPException(status_code=404, detail={
                "code": "market_history_not_found", "message": "Market history is unavailable for one or more allocation symbols."
            }) from exc
        except SymbolLimitExceeded as exc:
            raise HTTPException(status_code=422, detail={
                "code": "symbol_limit_exceeded", "message": str(exc)
            }) from exc
        except ProviderUnavailable as exc:
            raise HTTPException(status_code=502, detail={
                "code": "provider_unavailable", "message": "Market data is unavailable from the selected provider."
            }) from exc
        except IntegrationPending as exc:
            raise HTTPException(
                status_code=501,
                detail={"code": "quant_integration_pending", "message": str(exc)},
            )

    return application


app = create_app()
