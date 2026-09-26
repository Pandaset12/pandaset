import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from .schemas import AnalyticsSnapshot, Portfolio, WhatIfRequest


class PortfolioNotFound(Exception):
    pass


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
    """Replace DemoQuantProvider when the data/quant interfaces are ready."""

    def get_analytics(self, portfolio_id: str) -> AnalyticsSnapshot: ...

    def analyze(self, portfolio: Portfolio) -> AnalyticsSnapshot: ...

    def simulate(self, request: WhatIfRequest) -> dict: ...


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


_provider = DemoQuantProvider()


def get_provider() -> QuantProvider:
    # Backend #1 and the quant teammate supply the implementation here.
    return _provider
