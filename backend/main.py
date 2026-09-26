from contextlib import asynccontextmanager
import sqlite3
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .gemini_service import GeminiNotConfigured, GeminiUnavailable, generate_answer, metric_summary
from .api_v1 import router as v1_router
from .observability import log_failure, request_id_context
from .storage import PortfolioStore
from .providers import (
    IntegrationPending,
    PortfolioNotFound,
    QuantProvider,
    get_provider,
    demo_metrics,
)
from .market_data_errors import ProviderUnavailable
from .schemas import (
    AnalystRequest,
    AnalystResponse,
    AnalyticsSnapshot,
    WhatIfRequest,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = await run_in_threadpool(PortfolioStore, settings.storage_path)
        await run_in_threadpool(store.seed_demo, demo_metrics())
        app.state.store = store
        yield

    application = FastAPI(
        title="PortfolioLens API",
        version="0.2.0",
        description="Backend #2 starter. Default mode uses fictional demo data.",
        lifespan=lifespan,
    )
    application.dependency_overrides[get_settings] = lambda: settings
    application.include_router(v1_router)

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
                    {"error" if request.url.path.startswith("/api/v1/") else "detail": error},
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
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/v1/"):
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
        if request.url.path.startswith("/api/v1/"):
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
            {"error" if request.url.path.startswith("/api/v1/") else "detail": error}, status_code=503
        )

    @application.get("/health")
    def health(settings: Settings = Depends(get_settings)):
        live_data = settings.market_data_provider == "twelvedata"
        market_data_ready = not live_data or settings.has_twelve_data_key
        return {
            "status": "ok",
            "analyst_mode": settings.analyst_mode,
            "gemini_configured": settings.has_gemini_key,
            "quant_integration": (
                "quant_engine_twelvedata"
                if settings.market_data_provider == "twelvedata"
                else "quant_engine_sample_prices"
            ),
            "market_data_provider": settings.market_data_provider,
            "market_data_ready": market_data_ready,
            "data_mode": "live" if live_data else "demo",
            "storage_backend": "sqlite",
            "authentication_enabled": False,
        }

    def read_metrics(portfolio_id: str, provider: QuantProvider) -> AnalyticsSnapshot:
        try:
            return provider.get_analytics(portfolio_id)
        except ProviderUnavailable as exc:
            raise HTTPException(status_code=502, detail={
                "code": "provider_unavailable", "message": "Sample price data is unavailable."
            }) from exc
        except PortfolioNotFound:
            raise HTTPException(
                status_code=404,
                detail={"code": "portfolio_not_found", "message": "Portfolio not found."},
            )

    @application.get(
        "/api/portfolios/{portfolio_id}/analytics", response_model=AnalyticsSnapshot, deprecated=True
    )
    def analytics(portfolio_id: str, provider: QuantProvider = Depends(get_provider)):
        return read_metrics(portfolio_id, provider)

    @application.post("/api/analyst", response_model=AnalystResponse, deprecated=True)
    async def analyst(
        request: AnalystRequest,
        settings: Settings = Depends(get_settings),
        provider: QuantProvider = Depends(get_provider),
    ):
        metrics = await run_in_threadpool(read_metrics, request.portfolio_id, provider)
        warnings = list(metrics.notes)
        if settings.analyst_mode == "demo":
            warnings.append("Offline demo response; Gemini and web tools were not called.")
            summary, citations = metric_summary(metrics)
            answer = "Offline snapshot summary; this does not answer arbitrary questions. " + summary
            return AnalystResponse(
                analyst_mode="demo", status="demo", answer=answer, metrics=metrics,
                warnings=warnings, citations=citations,
            )
        try:
            output = await generate_answer(request, metrics, settings)
        except GeminiNotConfigured as exc:
            log_failure("GEMINI_NOT_CONFIGURED", exc)
            raise HTTPException(
                status_code=503,
                detail={"code": "gemini_not_configured", "message": str(exc)},
            )
        except GeminiUnavailable as exc:
            log_failure("GEMINI_UNAVAILABLE", exc)
            raise HTTPException(
                status_code=502,
                detail={"code": "gemini_unavailable", "message": str(exc)},
            )
        return AnalystResponse(
            analyst_mode="gemini", metrics=metrics, warnings=warnings, **output
        )

    @application.post("/api/what-if", deprecated=True)
    def what_if(request: WhatIfRequest, provider: QuantProvider = Depends(get_provider)):
        read_metrics(request.portfolio_id, provider)
        try:
            return provider.simulate(request)
        except ProviderUnavailable as exc:
            raise HTTPException(status_code=502, detail={
                "code": "provider_unavailable", "message": "Sample price data is unavailable."
            }) from exc
        except IntegrationPending as exc:
            raise HTTPException(
                status_code=501,
                detail={"code": "quant_integration_pending", "message": str(exc)},
            )

    return application


app = create_app()
