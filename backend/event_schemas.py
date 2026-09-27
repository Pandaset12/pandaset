"""Bounded inputs and agent output for the authenticated event lab."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schemas import Holding, PortfolioInput, check_weights


class EventPortfolioInput(PortfolioInput):
    """Event-lab allocation with the same validation as v1 and a 25-holding cap."""

    holdings: list[Holding] = Field(min_length=1, max_length=25)


class EventPortfolio(EventPortfolioInput):
    portfolio_id: str
    created_at: datetime

FACTOR_IDS = ("equity", "rates", "gold")
FACTOR_BOUNDS = (-0.5, 0.5)  # cumulative decimal factor return
ISSUER_BOUNDS = (-3.0, 3.0)  # residual standard-deviation multiples


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    portfolio_id: str = Field(min_length=1, max_length=80)
    analysis_id: str = Field(min_length=1, max_length=80)
    template_id: str = Field(min_length=1, max_length=80)
    situation_id: str | None = Field(default=None, min_length=1, max_length=80)
    target_symbol: str | None = Field(default=None, min_length=1, max_length=12)
    description: str = Field(default="", max_length=700)
    question: str = Field(default="", max_length=1000)
    proposed_weights: dict[str, float] | None = None

    @field_validator("target_symbol")
    @classmethod
    def normalize_target_symbol(cls, symbol: str | None) -> str | None:
        return symbol.upper() if symbol else None

    @field_validator("proposed_weights")
    @classmethod
    def weights_valid(cls, weights: dict[str, float] | None) -> dict[str, float] | None:
        return check_weights(weights) if weights is not None else None


class Shock(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    factors: dict[str, float]
    issuers: dict[str, float] = Field(default_factory=dict)


class CaseShocks(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    one_month: Shock = Field(alias="1m")
    three_month: Shock = Field(alias="3m")


class ConfirmedShocks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mild: CaseShocks
    central: CaseShocks
    severe: CaseShocks

    def as_engine_input(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    confirmed_shocks: ConfirmedShocks


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=2000)
    revision: DraftRequest | None = None


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class ResearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[Fact] = Field(default_factory=list, max_length=8)
    missing_evidence: list[str] = Field(default_factory=list, max_length=8)


class ProposedShock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factors: dict[str, float]
    issuers: dict[str, float] = Field(default_factory=dict)
    factor_unit: Literal["cumulative_decimal_return"]
    issuer_unit: Literal["residual_sigma_multiple"]
    rationale: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class ProposedCase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    one_month: ProposedShock = Field(alias="1m")
    three_month: ProposedShock = Field(alias="3m")


class DesignOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mild: ProposedCase
    central: ProposedCase
    severe: ProposedCase


def validate_shocks(shocks: dict, symbols: set[str], *, require_units: bool = False,
                    available_evidence_ids: set[str] | None = None) -> dict:
    """Reject unsupported factors, issuer IDs, units and out-of-bound values."""
    if set(shocks) != {"mild", "central", "severe"}:
        raise ValueError("Every mild, central, and severe case is required.")
    clean = {}
    for case, horizons in shocks.items():
        if set(horizons) != {"1m", "3m"}:
            raise ValueError(f"{case} needs 1m and 3m shocks.")
        clean[case] = {}
        for horizon, item in horizons.items():
            expected = {"factors", "issuers", "factor_unit", "issuer_unit", "rationale", "evidence_ids"} if require_units else {"factors", "issuers"}
            if set(item) != expected:
                raise ValueError(f"Unexpected fields in {case}/{horizon} shock.")
            if set(item["factors"]) != set(FACTOR_IDS):
                raise ValueError("Shocks must cover exactly equity, rates, and gold factors.")
            if not set(item["issuers"]).issubset(symbols):
                raise ValueError("An issuer shock names a symbol outside the saved portfolio.")
            for name, value in item["factors"].items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not FACTOR_BOUNDS[0] <= value <= FACTOR_BOUNDS[1]:
                    raise ValueError(f"Factor shock {name} is outside allowed decimal-return bounds.")
            for name, value in item["issuers"].items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not ISSUER_BOUNDS[0] <= value <= ISSUER_BOUNDS[1]:
                    raise ValueError(f"Issuer shock {name} is outside allowed residual-sigma bounds.")
            if require_units:
                if item["factor_unit"] != "cumulative_decimal_return" or item["issuer_unit"] != "residual_sigma_multiple":
                    raise ValueError("Shock units are unsupported.")
                if not item["rationale"].strip() or not set(item["evidence_ids"]).issubset(available_evidence_ids or set()):
                    raise ValueError("Every proposed shock needs a rationale and available evidence citation.")
                if not item["evidence_ids"]:
                    raise ValueError("Every proposed shock needs available evidence citation.")
            clean[case][horizon] = {"factors": item["factors"], "issuers": item["issuers"]}
    return clean
