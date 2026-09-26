"""Versioned scenario starting points. Templates contain no event claims or forecasts."""

from dataclasses import dataclass
from typing import Literal

from .instruments import Instrument


EventCategory = Literal["macro", "sector", "issuer"]


class EventTemplateNotFound(KeyError):
    pass


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


TEMPLATE_VERSION = "1.0.0"
EVENT_TEMPLATES: dict[str, EventTemplate] = {
    item.template_id: item for item in (
        EventTemplate(
            "fed_policy", TEMPLATE_VERSION, "macro", "Federal Reserve policy decision",
            "Explore a hypothetical change in policy rates and its effect on equity, Treasury, and gold factors.",
            ("equity", "rates", "gold"), ("FEDFUNDS", "DGS2", "DGS10"), ("fomc_releases",),
        ),
        EventTemplate(
            "inflation_release", TEMPLATE_VERSION, "macro", "Inflation release",
            "Explore a hypothetical inflation surprise; the scenario requires confirmed factor shocks.",
            ("equity", "rates", "gold"), ("CPIAUCSL", "DGS10"), ("bls_cpi",),
        ),
        EventTemplate(
            "growth_release", TEMPLATE_VERSION, "macro", "US growth release",
            "Explore a hypothetical change in growth expectations.",
            ("equity", "rates", "gold"), ("GDPC1", "UNRATE", "INDPRO"), ("bea_gdp",),
        ),
        EventTemplate(
            "technology_sector", TEMPLATE_VERSION, "sector", "Technology sector development",
            "Explore a hypothetical sector event affecting technology holdings.",
            ("equity", "rates", "gold"), ("INDPRO",), ("sec_edgar",), ("Technology",),
        ),
        EventTemplate(
            "financial_sector", TEMPLATE_VERSION, "sector", "Financial sector development",
            "Explore a hypothetical sector event affecting financial holdings.",
            ("equity", "rates", "gold"), ("FEDFUNDS", "DGS10"), ("sec_edgar",), ("Financials",),
        ),
        EventTemplate(
            "energy_sector", TEMPLATE_VERSION, "sector", "Energy sector development",
            "Explore a hypothetical sector event affecting energy holdings.",
            ("equity", "rates", "gold"), ("INDPRO",), ("eia_today",), ("Energy",),
        ),
        EventTemplate(
            "healthcare_sector", TEMPLATE_VERSION, "sector", "Health care sector development",
            "Explore a hypothetical sector event affecting health care holdings.",
            ("equity", "rates", "gold"), (), ("sec_edgar",), ("Health care",),
        ),
        EventTemplate(
            "issuer_earnings", TEMPLATE_VERSION, "issuer", "Issuer earnings or guidance",
            "Explore a hypothetical issuer announcement for a selected US stock.",
            ("equity", "rates", "gold"), (), ("sec_edgar",),
        ),
    )
}


def list_event_templates(instruments: list[Instrument] | None = None) -> list[EventTemplate]:
    if instruments is None:
        return list(EVENT_TEMPLATES.values())
    sectors = {instrument.sector for instrument in instruments}
    has_stock = any(instrument.kind == "us_stock" for instrument in instruments)
    return [item for item in EVENT_TEMPLATES.values()
            if item.category == "macro"
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
