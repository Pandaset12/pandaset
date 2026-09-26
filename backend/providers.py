import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from fastapi import Request
import pandas as pd
from quant_engine import analyze_portfolio, compare_portfolios

from .schemas import AnalysisSeries, AnalyticsSnapshot, MarketHistoryResponse, Portfolio, WhatIfRequest
from .price_cache import CachedPriceProvider, RecentPriceCache


class IntegrationPending(Exception):
    pass


class ProviderUnavailable(Exception):
    """Data adapters should wrap network/database failures in this exception."""


@lru_cache(maxsize=1)
def _demo_fixture() -> AnalyticsSnapshot:
    path = Path(__file__).parent / "fixtures" / "demo_analytics.json"
    return AnalyticsSnapshot.model_validate(json.loads(path.read_text("utf-8")))


def demo_metrics() -> AnalyticsSnapshot:
    return _demo_fixture().model_copy(deep=True)


class QuantProvider(Protocol):
    """Synchronous analytics boundary, called in FastAPI's thread pool."""

    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot: ...

    def simulate(self, request: WhatIfRequest, portfolio: Portfolio) -> dict: ...

    def market_history(self, symbols: list[str], lookback_days: int) -> MarketHistoryResponse: ...


class DemoQuantProvider:
    """Precomputed fictional fixture; this does not calculate financial risk."""

    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot:
        metrics = demo_metrics()
        if portfolio.weights != metrics.weights:
            raise IntegrationPending(
                "Only the predefined demo allocation has fixture metrics. "
                "Connect the quant/data module to analyze a different allocation."
            )
        metrics.portfolio_id = portfolio.portfolio_id
        return metrics

    def simulate(self, request: WhatIfRequest, portfolio: Portfolio) -> dict:
        raise IntegrationPending(
            "The real quant engine is not connected yet. "
            "Proposed weights were validated, but no risk comparison was calculated."
        )

    def market_history(self, symbols: list[str], lookback_days: int) -> MarketHistoryResponse:
        return build_market_history(SamplePriceProvider(), symbols, lookback_days)


class SamplePriceProvider:
    """Existing fictional daily-price fixture; never live market data."""

    def prices(self, symbols: list[str], lookback_days: int = 252) -> pd.DataFrame:
        path = Path(__file__).parent / "drafts" / "data_pipeline" / "sample_prices.json"
        fixture = json.loads(path.read_text("utf-8"))
        missing = set(symbols) - fixture["prices"].keys()
        if missing:
            raise ProviderUnavailable("Sample history is unavailable for: " + ", ".join(sorted(missing)))
        return pd.DataFrame(
            {symbol: [float(value) for value in fixture["prices"][symbol]] for symbol in symbols},
            index=pd.to_datetime(fixture["dates"], utc=True),
        )


def build_market_history(prices_provider, symbols: list[str], lookback_days: int) -> MarketHistoryResponse:
    frame = prices_provider.prices(symbols, lookback_days=lookback_days).tail(lookback_days + 1)
    if len(frame) < 2:
        raise ProviderUnavailable("At least two dated prices are required for market history.")
    series = {
        symbol: [float(value / frame[symbol].iloc[0]) for value in frame[symbol].tolist()]
        for symbol in symbols
    }
    return MarketHistoryResponse(
        symbols=symbols,
        dates=[stamp.strftime("%Y-%m-%d") for stamp in frame.index],
        asset_index=series,
        data_mode="demo",
        data_source="synthetic_fixture",
        freshness="unknown",
        requested_lookback_days=lookback_days,
        observation_count=len(frame) - 1,
        warnings=["FICTIONAL sample prices; not live market observations."],
    )


def map_quant_report(report: dict, portfolio_id: str) -> AnalyticsSnapshot:
    """Map the sample-price report explicitly, without normalizing weights or metrics."""
    metadata = report["metadata"]
    symbols = list(report["weights"])
    dates = [metadata["start_date"][:10], *[date[:10] for date in report["series"]["dates"]]]
    portfolio_index = [1.0, *[1 + value for value in report["series"]["portfolio_cumulative_returns"]]]
    asset_index = {
        symbol: [1.0, *[1 + value for value in report["series"]["asset_cumulative_returns"][symbol]]]
        for symbol in symbols
    }
    return_contribution = {
        symbol: report["assets"][symbol]["return_contribution"] for symbol in symbols
    }
    series = AnalysisSeries(
        dates=dates, portfolio_index=portfolio_index, asset_index=asset_index,
        return_contribution=return_contribution,
    )
    return AnalyticsSnapshot(
        portfolio_id=portfolio_id, data_mode="demo",
        data_as_of=metadata["end_date"],
        lookback_trading_days=metadata["return_observations"],
        observation_count=metadata["return_observations"],
        portfolio_return=report["portfolio"]["cumulative_return"],
        annualized_return=report["portfolio"]["geometric_annualized_return"],
        max_drawdown=report["portfolio"]["maximum_drawdown"],
        return_contribution=return_contribution,
        series=series,
        portfolio_volatility=report["portfolio"]["annualized_volatility"],
        weights=report["weights"],
        asset_volatility={symbol: asset["annualized_volatility"]
                          for symbol, asset in report["assets"].items()},
        risk_contribution={symbol: asset["percentage_risk_contribution"]
                           for symbol, asset in report["assets"].items()},
        correlation_matrix=report["matrices"]["correlation"],
        data_source="synthetic_fixture", freshness="unknown",
        notes=[*report["warnings"], "FICTIONAL sample prices; not live market observations."],
        assumptions=[*metadata["assumptions"],
                     "UTC midnight labels a session date, not an exchange closing instant.",
                     "Fictional prices are treated as adjusted daily prices for this demo.",
                     f"Price window: {metadata['start_date']} through {metadata['end_date']}; "
                     f"annualization: {metadata['periods_per_year']} observations per year."],
    )


class EngineQuantProvider:
    """Quant integration using the saved allocation and demo price history."""

    def __init__(self, store, prices=None):
        self.store = store
        self.prices = prices if prices is not None else SamplePriceProvider()

    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot:
        prices = self.prices.prices(sorted(portfolio.weights))
        return map_quant_report(analyze_portfolio(prices, portfolio.weights), portfolio.portfolio_id)

    def simulate(self, request: WhatIfRequest, portfolio: Portfolio) -> dict:
        baseline = portfolio.weights
        symbols = sorted(set(baseline) | set(request.proposed_weights))
        prices = self.prices.prices(symbols)
        result = compare_portfolios(
            prices, {symbol: baseline.get(symbol, 0.0) for symbol in symbols},
            {symbol: request.proposed_weights.get(symbol, 0.0) for symbol in symbols},
        )
        differences = result["portfolio_metric_differences"]
        return {
            "current_analysis": map_quant_report(result["baseline"], request.portfolio_id).model_dump(mode="json"),
            "proposed_analysis": map_quant_report(result["proposed"], request.portfolio_id).model_dump(mode="json"),
            "delta": {"portfolio_return": differences["cumulative_return"],
                      "portfolio_volatility": differences["annualized_volatility"],
                      "annualized_return": differences["geometric_annualized_return"],
                      "max_drawdown": differences["maximum_drawdown"]},
            "difference_convention": result["difference_convention"],
        }

    def market_history(self, symbols: list[str], lookback_days: int) -> MarketHistoryResponse:
        return build_market_history(self.prices, symbols, lookback_days)


def get_provider(request: Request) -> QuantProvider:
    return EngineQuantProvider(
        request.app.state.store,
        prices=CachedPriceProvider(SamplePriceProvider(), request.app.state.price_cache),
    )
