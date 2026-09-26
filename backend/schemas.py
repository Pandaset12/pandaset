import ipaddress
import math
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


DISCLAIMER = "For educational purposes only; not financial advice."


def check_weights(weights: dict[str, float]) -> dict[str, float]:
    normalized = {}
    for symbol, weight in weights.items():
        symbol = symbol.strip().upper()
        if not symbol or symbol in normalized:
            raise ValueError("Symbols must be nonempty and unique after normalization.")
        if not math.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("This MVP uses finite long-only weights between 0 and 1.")
        normalized[symbol] = weight
    if not math.isclose(math.fsum(normalized.values()), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Weights must sum to 1.0; they are never silently renormalized.")
    return normalized


class AnalyticsSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    portfolio_id: str
    data_mode: Literal["demo", "live"]
    data_as_of: AwareDatetime | None = None
    lookback_trading_days: int = Field(gt=0)
    volatility_unit: Literal["annualized_decimal"] = "annualized_decimal"
    portfolio_volatility: float = Field(ge=0)
    weights: dict[str, float] = Field(min_length=1, max_length=100)
    risk_contribution: dict[str, float]
    notes: list[str] = Field(default_factory=list)
    portfolio_return: float | None = None
    asset_volatility: dict[str, float] | None = None
    correlation_matrix: dict[str, dict[str, float]] | None = None
    observation_count: int | None = Field(default=None, ge=2)
    return_frequency: Literal["daily"] = "daily"
    data_source: str = "unspecified"
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_allocation(self):
        normalized = check_weights(self.weights)
        if normalized != self.weights:
            raise ValueError("Provider symbols must already be normalized.")
        symbols = set(self.weights)
        if self.data_mode == "live" and (
            self.data_as_of is None or self.observation_count is None
            or self.data_source == "unspecified" or not self.data_source.strip()
        ):
            raise ValueError("Live metrics need a valuation timestamp, source and observation count.")
        if self.asset_volatility is not None:
            if set(self.asset_volatility) != symbols or any(v < 0 for v in self.asset_volatility.values()):
                raise ValueError("Asset volatilities must be nonnegative and cover all holdings.")
        if self.correlation_matrix is not None:
            matrix = self.correlation_matrix
            if set(matrix) != symbols or any(set(row) != symbols for row in matrix.values()):
                raise ValueError("The correlation matrix must cover all holdings.")
            for symbol, row in matrix.items():
                if not math.isclose(row[symbol], 1.0, abs_tol=1e-6):
                    raise ValueError("Correlation diagonals must equal one.")
                for other, value in row.items():
                    if not -1 <= value <= 1 or not math.isclose(value, matrix[other][symbol], abs_tol=1e-6):
                        raise ValueError("Correlations must be symmetric and between -1 and 1.")
        if self.portfolio_volatility == 0 and not self.risk_contribution:
            return self
        if set(self.risk_contribution) != set(self.weights):
            raise ValueError("Risk contributions must cover exactly the portfolio symbols.")
        total = math.fsum(self.risk_contribution.values())
        if self.portfolio_volatility > 0:
            if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-6):
                raise ValueError("Relative volatility risk contributions must sum to 1.")
        elif any(self.risk_contribution.values()):
            raise ValueError("Relative risk shares are undefined at zero variance.")
        return self


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    web_search: bool = False
    source_urls: list[AnyHttpUrl] = Field(default_factory=list, max_length=5)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank.")
        return value

    @field_validator("source_urls")
    @classmethod
    def public_https_urls(cls, urls: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        for url in urls:
            host = (url.host or "").lower()
            if url.scheme != "https" or url.username or url.password:
                raise ValueError("Use public HTTPS URLs without credentials.")
            if "." not in host or host.endswith((".localhost", ".local", ".internal")):
                raise ValueError("Use a public website domain.")
            try:
                ipaddress.ip_address(host.strip("[]"))
            except ValueError:
                continue
            raise ValueError("Use a website domain, not an IP address.")
        return urls


class AnalystRequest(QuestionInput):
    portfolio_id: str = Field(default="demo", min_length=1, max_length=64)


class AskRequest(QuestionInput):
    analysis_id: str = Field(min_length=1, max_length=80)


class MetricCitation(BaseModel):
    field: str
    value: float


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    explanation: str = Field(min_length=1, max_length=16000)
    cited_fields: list[str] = Field(max_length=200)


class AnalystResponse(BaseModel):
    analyst_mode: Literal["demo", "gemini"]
    answer: str
    metrics: AnalyticsSnapshot
    sources: list[dict[str, Any]] = Field(default_factory=list)
    grounding_supports: list[dict[str, Any]] = Field(default_factory=list)
    search_suggestions_html: str | None = None
    url_retrievals: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: Literal["complete", "demo", "unavailable"] = "complete"
    citations: list[MetricCitation] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
    analysis_id: str | None = None
    # Grounding offsets refer to this original model text, not parsed answer text.
    grounding_text: str | None = None
    error_code: str | None = None


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    portfolio_id: str = Field(default="demo", min_length=1, max_length=64)
    proposed_weights: dict[str, float] = Field(min_length=1, max_length=100)

    @field_validator("proposed_weights")
    @classmethod
    def valid_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        return check_weights(weights)


class Holding(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9^][A-Za-z0-9.^=-]*$")
    weight: float = Field(ge=0, le=1, strict=True)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class AllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    holdings: list[Holding] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_allocation(self):
        symbols = [holding.symbol for holding in self.holdings]
        if len(set(symbols)) != len(symbols):
            raise ValueError("Duplicate symbols are not allowed.")
        check_weights(self.weights)
        return self

    @property
    def weights(self) -> dict[str, float]:
        return {holding.symbol: holding.weight for holding in self.holdings}


class PortfolioInput(AllocationInput):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, name: str) -> str:
        if not name.strip():
            raise ValueError("Portfolio name cannot be blank.")
        return name.strip()


class Portfolio(PortfolioInput):
    portfolio_id: str
    created_at: datetime


class DataQuality(BaseModel):
    source: str
    freshness: Literal["fresh", "stale", "unknown"]
    warnings: list[str]


class Concentration(BaseModel):
    largest_position: str
    largest_weight: float


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    analysis_id: str
    portfolio_id: str
    created_at: datetime
    as_of: datetime | None
    lookback_days: int
    portfolio_return: float | None
    portfolio_volatility: float
    asset_volatility: dict[str, float] | None
    correlation_matrix: dict[str, dict[str, float]] | None
    risk_contribution: dict[str, float]
    concentration: Concentration
    data_quality: DataQuality
    weights: dict[str, float]
    data_mode: Literal["demo", "live"]
    observation_count: int | None
    return_frequency: Literal["daily"]
    volatility_unit: Literal["annualized_decimal"]
    assumptions: list[str]
