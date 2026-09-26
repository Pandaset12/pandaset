"""Versioned scenario starting points. Templates contain no event claims or forecasts."""

from dataclasses import dataclass
from typing import Literal

from .instruments import Instrument


EventCategory = Literal["macro", "sector", "issuer", "custom"]


class EventTemplateNotFound(KeyError):
    pass


@dataclass(frozen=True)
class EventSituation:
    situation_id: str
    title: str
    description: str


@dataclass(frozen=True)
class EventTemplate:
    template_id: str
    version: str
    category: EventCategory
    title: str
    description: str
    factor_ids: tuple[str, ...]
    fred_series_ids: tuple[str, ...] = ()
    official_source_ids: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    situations: tuple[EventSituation, ...] = ()


TEMPLATE_VERSION = "1.0.0"
EVENT_TEMPLATES: dict[str, EventTemplate] = {
    item.template_id: item for item in (
        EventTemplate(
            "fed_policy", TEMPLATE_VERSION, "macro", "Federal Reserve policy decision",
            "Explore a hypothetical change in policy rates and its effect on equity, Treasury, and gold factors.",
            ("equity", "rates", "gold"), ("FEDFUNDS", "DGS2", "DGS10"), ("fomc_releases",),
            situations=(
                EventSituation("faster_cuts", "Rates fall sooner", "Suppose the Fed cuts policy rates sooner or faster than markets expect."),
                EventSituation("higher_for_longer", "Rates stay higher", "Suppose the Fed keeps policy rates elevated longer than markets expect."),
                EventSituation("surprise_hike", "Rates rise unexpectedly", "Suppose the Fed raises policy rates unexpectedly."),
            ),
        ),
        EventTemplate(
            "inflation_release", TEMPLATE_VERSION, "macro", "Inflation release",
            "Explore a hypothetical inflation surprise; the scenario requires confirmed factor shocks.",
            ("equity", "rates", "gold"), ("CPIAUCSL", "DGS10"), ("bls_cpi",),
            situations=(
                EventSituation("hotter_inflation", "Inflation runs hotter", "Suppose a future inflation release comes in above expectations."),
                EventSituation("cooler_inflation", "Inflation cools faster", "Suppose a future inflation release comes in below expectations."),
            ),
        ),
        EventTemplate(
            "growth_release", TEMPLATE_VERSION, "macro", "US growth release",
            "Explore a hypothetical change in growth expectations.",
            ("equity", "rates", "gold"), ("GDPC1", "UNRATE", "INDPRO"), ("bea_gdp",),
            situations=(
                EventSituation("growth_slows", "Growth slows", "Suppose a future GDP release signals weaker growth than expected."),
                EventSituation("growth_accelerates", "Growth accelerates", "Suppose a future GDP release signals stronger growth than expected."),
            ),
        ),
        EventTemplate(
            "technology_sector", TEMPLATE_VERSION, "sector", "Technology sector development",
            "Explore a hypothetical sector event affecting technology holdings.",
            ("equity", "rates", "gold"), ("INDPRO",), ("sec_edgar",), ("Technology",),
            situations=(
                EventSituation("tech_demand_weakens", "Tech demand weakens", "Suppose major technology issuers report weaker demand or guidance."),
                EventSituation("tech_demand_strengthens", "Tech demand strengthens", "Suppose major technology issuers report stronger demand or guidance."),
            ),
        ),
        EventTemplate(
            "financial_sector", TEMPLATE_VERSION, "sector", "Financial sector development",
            "Explore a hypothetical sector event affecting financial holdings.",
            ("equity", "rates", "gold"), ("FEDFUNDS", "DGS10"), ("sec_edgar",), ("Financials",),
            situations=(
                EventSituation("credit_stress", "Credit conditions tighten", "Suppose lenders report rising credit losses or tighter lending conditions."),
                EventSituation("bank_outlook_improves", "Bank outlook improves", "Suppose major banks report stronger earnings and healthier credit conditions."),
            ),
        ),
        EventTemplate(
            "energy_sector", TEMPLATE_VERSION, "sector", "Energy sector development",
            "Explore a hypothetical sector event affecting energy holdings.",
            ("equity", "rates", "gold"), ("INDPRO",), ("eia_today",), ("Energy",),
            situations=(
                EventSituation("oil_supply_disruption", "Oil supply tightens", "Suppose a supply disruption raises oil-price expectations."),
                EventSituation("oil_demand_weakens", "Oil demand weakens", "Suppose slower demand lowers oil-price expectations."),
            ),
        ),
        EventTemplate(
            "healthcare_sector", TEMPLATE_VERSION, "sector", "Health care sector development",
            "Explore a hypothetical sector event affecting health care holdings.",
            ("equity", "rates", "gold"), (), ("sec_edgar",), ("Health care",),
            situations=(
                EventSituation("healthcare_guidance_weakens", "Guidance weakens", "Suppose major health care issuers reduce their outlook."),
                EventSituation("healthcare_guidance_improves", "Guidance improves", "Suppose major health care issuers raise their outlook."),
            ),
        ),
        EventTemplate(
            "issuer_earnings", TEMPLATE_VERSION, "issuer", "Issuer earnings or guidance",
            "Explore a hypothetical issuer announcement for a selected US stock.",
            ("equity", "rates", "gold"), (), ("sec_edgar",),
            situations=(
                EventSituation("issuer_beats", "Earnings beat expectations", "Suppose an issuer reports stronger earnings or guidance than expected."),
                EventSituation("issuer_misses", "Earnings miss expectations", "Suppose an issuer reports weaker earnings or guidance than expected."),
            ),
        ),
        EventTemplate(
            "custom_event", TEMPLATE_VERSION, "custom", "Something else",
            "Describe your own hypothetical situation. Research depends on available approved sources.",
            ("equity", "rates", "gold"), (),
            ("fomc_releases", "bls_cpi", "bea_gdp", "eia_today", "sec_edgar"),
        ),
    )
}


def list_event_templates(instruments: list[Instrument] | None = None) -> list[EventTemplate]:
    if instruments is None:
        return list(EVENT_TEMPLATES.values())
    sectors = {instrument.sector for instrument in instruments}
    has_stock = any(instrument.kind == "us_stock" for instrument in instruments)
    return [item for item in EVENT_TEMPLATES.values()
            if item.category in {"macro", "custom"}
            or item.category == "sector" and bool(sectors.intersection(item.sectors))
            or item.category == "issuer" and has_stock]


def get_event_template(template_id: str, version: str | None = None) -> EventTemplate:
    try:
        item = EVENT_TEMPLATES[template_id]
    except KeyError as exc:
        raise EventTemplateNotFound(template_id) from exc
    if version is not None and version != item.version:
        raise EventTemplateNotFound(f"{template_id}@{version}")
    return item
