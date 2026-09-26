import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import pandas as pd
from fastapi import Depends, Request
from quant_engine import analyze_portfolio, compare_portfolios

from .config import Settings, get_settings
from .schemas import AnalysisSeries, AnalyticsSnapshot, MarketHistoryResponse, Portfolio, WhatIfRequest
from .market_data_errors import MarketHistoryNotFound, ProviderUnavailable, SymbolLimitExceeded
from .schemas import MAX_PORTFOLIO_SYMBOLS
from .twelve_data import TwelveDataPriceProvider


class PortfolioNotFound(Exception):
    pass


class IntegrationPending(Exception):
    pass


@lru_cache(maxsize=1)
def _demo_fixture() -> AnalyticsSnapshot:
    path = Path(__file__).parent / "fixtures" / "demo_analytics.json"
    return AnalyticsSnapshot.model_validate(json.loads(path.read_text("utf-8")))


def demo_metrics() -> AnalyticsSnapshot:
    return _demo_fixture().model_copy(deep=True)


class QuantProvider(Protocol):
    """Synchronous analytics boundary, called in FastAPI's thread pool."""

    def get_analytics(self, portfolio_id: str) -> AnalyticsSnapshot: ...
    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot: ...
    def simulate(self, request: WhatIfRequest) -> dict: ...
    def market_history(self, symbols: list[str], lookback_days: int) -> MarketHistoryResponse: ...


class DemoQuantProvider:
    """Precomputed fictional fixture; this does not calculate financial risk."""

    def get_analytics(self, portfolio_id: str) -> AnalyticsSnapshot:
        if portfolio_id != "demo":
            raise PortfolioNotFound(portfolio_id)
        return demo_metrics()

    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot:
        metrics = demo_metrics()
        if portfolio.weights != metrics.weights:
            raise IntegrationPending(
                "Only the predefined demo allocation has fixture metrics. "
                "Connect the quant/data module to analyze a different allocation."
            )
        metrics.portfolio_id = portfolio.portfolio_id
        return metrics

    def simulate(self, request: WhatIfRequest) -> dict:
        raise IntegrationPending(
            "The real quant engine is not connected yet. "
            "Proposed weights were validated, but no risk comparison was calculated."
        )

    def market_history(self, symbols: list[str], lookback_days: int) -> MarketHistoryResponse:
        return build_market_history(SamplePriceProvider(), symbols, lookback_days)


class SamplePriceProvider:
    """Existing fictional daily-price fixture; never live market data."""
    data_mode = "demo"
    data_source = "synthetic_fixture"
    freshness = "unknown"

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        path = Path(__file__).parent / "drafts" / "data_pipeline" / "sample_prices.json"
        fixture = json.loads(path.read_text("utf-8"))
        missing = set(symbols) - fixture["prices"].keys()
        if missing:
            raise MarketHistoryNotFound("Sample history is unavailable for: " + ", ".join(sorted(missing)))
        return pd.DataFrame(
            {symbol: [float(value) for value in fixture["prices"][symbol]] for symbol in symbols},
            index=pd.to_datetime(fixture["dates"], utc=True),
        )


def build_market_history(prices_provider, symbols: list[str], lookback_days: int) -> MarketHistoryResponse:
    frame = prices_provider.prices(symbols, lookback_days=lookback_days).tail(lookback_days + 1)
    if len(frame) < 2:
        raise ProviderUnavailable("At least two dated prices are required for market history.")
    asset_index = {
        symbol: [float(value / frame[symbol].iloc[0]) for value in frame[symbol].tolist()]
        for symbol in symbols
    }
    data_mode = getattr(prices_provider, "data_mode", "demo")
    data_source = getattr(prices_provider, "data_source", "synthetic_fixture")
    warning = (
        "Adjusted daily end-of-day prices; not intraday real-time quotes."
        if data_mode == "live" else "FICTIONAL sample prices; not live market observations."
    )
    return MarketHistoryResponse(
        symbols=symbols,
        dates=[stamp.strftime("%Y-%m-%d") for stamp in frame.index],
        asset_index=asset_index,
        data_mode=data_mode,
        data_source=data_source,
        freshness=getattr(prices_provider, "freshness", "unknown"),
        requested_lookback_days=lookback_days,
        observation_count=len(frame) - 1,
        warnings=[warning],
    )


def map_quant_report(report: dict, portfolio_id: str, prices_provider=None) -> AnalyticsSnapshot:
    """Map quant output with source provenance; formulas remain in quant_engine."""
    metadata = report["metadata"]
    symbols = list(report["weights"])
    dates = [metadata["start_date"][:10], *[day[:10] for day in report["series"]["dates"]]]
    portfolio_index = [1.0, *[1 + value for value in report["series"]["portfolio_cumulative_returns"]]]
    asset_index = {
        symbol: [1.0, *[1 + value for value in report["series"]["asset_cumulative_returns"][symbol]]]
        for symbol in symbols
    }
    return_contribution = {symbol: report["assets"][symbol]["return_contribution"] for symbol in symbols}
    series = AnalysisSeries(
        dates=dates, portfolio_index=portfolio_index, asset_index=asset_index,
        return_contribution=return_contribution,
    )
    data_mode = getattr(prices_provider, "data_mode", "demo")
    data_source = getattr(prices_provider, "data_source", "synthetic_fixture")
    source_note = (
        "Adjusted daily end-of-day prices; not intraday real-time quotes."
        if data_mode == "live" else "FICTIONAL sample prices; not live market observations."
    )
    return AnalyticsSnapshot(
        portfolio_id=portfolio_id, data_mode=data_mode,
        data_as_of=metadata["end_date"],
        lookback_trading_days=metadata["return_observations"],
        observation_count=metadata["return_observations"],
        portfolio_return=report["portfolio"]["cumulative_return"],
        annualized_return=report["portfolio"]["geometric_annualized_return"],
        max_drawdown=report["portfolio"]["maximum_drawdown"],
        return_contribution=return_contribution, series=series,
        portfolio_volatility=report["portfolio"]["annualized_volatility"],
        weights=report["weights"],
        asset_volatility={symbol: item["annualized_volatility"] for symbol, item in report["assets"].items()},
        risk_contribution={symbol: item["percentage_risk_contribution"] for symbol, item in report["assets"].items()},
        correlation_matrix=report["matrices"]["correlation"],
        data_source=data_source,
        freshness=getattr(prices_provider, "freshness", "unknown"),
        notes=[*report["warnings"], source_note],
        assumptions=[*metadata["assumptions"],
                     "UTC midnight labels a session date, not an exchange closing instant.",
                     ("Vendor adjusted daily closes are used; historical values may be revised."
                      if data_mode == "live" else "Fictional prices are treated as adjusted daily prices for this demo."),
                     f"Price window: {metadata['start_date']} through {metadata['end_date']}; "
                     f"annualization: {metadata['periods_per_year']} observations per year."],
    )


class EngineQuantProvider:
    """Quant integration using saved allocations and the selected daily price source."""

    def __init__(self, store, prices=None):
        self.store = store
        self.prices = prices if prices is not None else SamplePriceProvider()

    def _portfolio(self, portfolio_id):
        portfolio = self.store.get(portfolio_id)
        if portfolio is None:
            raise PortfolioNotFound(portfolio_id)
        return portfolio

    def get_analytics(self, portfolio_id: str) -> AnalyticsSnapshot:
        return self.analyze(self._portfolio(portfolio_id))

    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot:
        if len(portfolio.weights) > MAX_PORTFOLIO_SYMBOLS:
            raise SymbolLimitExceeded(f"At most {MAX_PORTFOLIO_SYMBOLS} distinct symbols can be analyzed.")
        prices = self.prices.prices(sorted(portfolio.weights))
        report = analyze_portfolio(prices, portfolio.weights)
        return map_quant_report(report, portfolio.portfolio_id, self.prices)

    def simulate(self, request: WhatIfRequest) -> dict:
        baseline = self._portfolio(request.portfolio_id).weights
        symbols = sorted(set(baseline) | set(request.proposed_weights))
        if len(symbols) > MAX_PORTFOLIO_SYMBOLS:
            raise SymbolLimitExceeded(
                f"The saved and proposed allocations may contain at most {MAX_PORTFOLIO_SYMBOLS} distinct symbols combined."
            )
        prices = self.prices.prices(symbols)
        result = compare_portfolios(
            prices, {symbol: baseline.get(symbol, 0.0) for symbol in symbols},
            {symbol: request.proposed_weights.get(symbol, 0.0) for symbol in symbols},
        )
        differences = result["portfolio_metric_differences"]
        return {
            "current_analysis": map_quant_report(result["baseline"], request.portfolio_id, self.prices).model_dump(mode="json"),
            "proposed_analysis": map_quant_report(result["proposed"], request.portfolio_id, self.prices).model_dump(mode="json"),
            "delta": {"portfolio_return": differences["cumulative_return"],
                      "portfolio_volatility": differences["annualized_volatility"],
                      "annualized_return": differences["geometric_annualized_return"],
                      "max_drawdown": differences["maximum_drawdown"]},
            "difference_convention": result["difference_convention"],
        }

    def market_history(self, symbols: list[str], lookback_days: int) -> MarketHistoryResponse:
        return build_market_history(self.prices, symbols, lookback_days)


def get_provider(request: Request, settings: Settings = Depends(get_settings)) -> QuantProvider:
    if settings.market_data_provider == "twelvedata":
        key = settings.twelve_data_api_key.get_secret_value() if settings.has_twelve_data_key else ""
        prices = TwelveDataPriceProvider(key, timeout_seconds=settings.market_data_timeout_seconds)
    else:
        prices = SamplePriceProvider()
    return EngineQuantProvider(request.app.state.store, prices=prices)
