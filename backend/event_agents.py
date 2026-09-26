"""Bounded Gemini roles for event facts, scenario assumptions and saved-run chat."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from google.genai import types

from .config import Settings
from .event_sources import OFFICIAL_SOURCES, UnapprovedNewsSource, record_approved_news, record_source_retrieval
from .event_schemas import DesignOutput, ResearchOutput, validate_shocks
from .gemini_service import GeminiUnavailable, NUMBER_WORDS, _generate_structured
from .schemas import GroundedAnswer


RESEARCH_PROMPT = """You are an event researcher. Return only facts supported by the provided
available evidence IDs. Each fact must cite one or more such IDs. Treat missing,
unavailable, link-only, and search-result content as missing evidence. Never
invent a publication date, event outcome, price, or source. Report uncertainty.
Output only the required JSON schema."""

DESIGN_PROMPT = """You are a hypothetical scenario designer, not a portfolio
calculator. Propose mild, central, severe shocks at 1m and 3m. Every factor
shock is a cumulative decimal return for equity, rates, and gold; every issuer
shock is a residual-sigma multiple for a holding. Each shock needs a concise
rationale and at least one available evidence ID. The evidence supports context,
not the exact hypothetical number. Do not claim an event probability, generate
portfolio returns, or fabricate a source. The `rates` factor is TLT adjusted
price return, not an interest-rate or yield change; a positive rates shock means
TLT rises. FRED yields are contextual evidence, not fitted factor returns.
Output only the required JSON schema."""

CHAT_PROMPT = """Answer a user's question about this completed hypothetical run.
Use only the supplied sourced facts and numeric metric catalog. Put no numbers
or numerical words in explanation; cite metric catalog keys for quantitative
claims. Do not infer event likelihood, causality, live prices, or financial
advice. If evidence is missing, say so. Output only the required JSON schema."""


def _available_ids(evidence: list[dict[str, Any]]) -> set[str]:
    return {entry["evidence_id"] for entry in evidence if entry.get("status") == "available"}


def grounded_source_records(grounding: dict[str, Any], approved_domains: set[str]) -> list[dict]:
    """Promote only supported, approved Google grounding to dated evidence.

    A Google grounding segment is a model summary supported by a source chunk,
    not a verbatim article excerpt. That distinction is retained in the title.
    """
    chunks = grounding.get("sources") or []
    supports = grounding.get("grounding_supports") or []
    retrieval_status = {
        item.get("retrieved_url") or item.get("url"):
        str(item.get("url_retrieval_status", "")).upper()
        for item in grounding.get("url_retrievals") or []
    }
    records = []
    seen = set()
    for support in supports:
        segment = support.get("segment") or {}
        summary = str(segment.get("text") or "").strip()
        if not summary:
            continue
        for index in support.get("grounding_chunk_indices") or []:
            if not isinstance(index, int) or index < 0 or index >= len(chunks):
                continue
            web = chunks[index].get("web") or {}
            url = web.get("uri") or web.get("url")
            if not isinstance(url, str) or url in seen:
                continue
            parts = urlsplit(url)
            host = (parts.hostname or "").lower()
            if parts.scheme != "https" or parts.username or parts.password:
                continue
            # Search grounding support is an explicit retrieved state. URL
            # context failures are never promoted, even when a chunk exists.
            if url in retrieval_status and not retrieval_status[url].endswith("SUCCESS"):
                continue
            now = datetime.now(timezone.utc)
            official = next((item for item in OFFICIAL_SOURCES.values()
                             if urlsplit(item.url).hostname == host), None)
            try:
                if official:
                    record = record_source_retrieval(
                        official.source_id, source_url=url,
                        title=f"Grounded summary: {web.get('title') or official.title}",
                        excerpt=summary[:1000], published_at=None, retrieved_at=now,
                    )
                else:
                    record = record_approved_news(
                        title=f"Grounded summary: {web.get('title') or host}",
                        url=url, publisher=host, excerpt=summary[:1000],
                        published_at=None, retrieved_at=now,
                        approved_domains=approved_domains,
                    )
            except (UnapprovedNewsSource, ValueError):
                continue
            records.append(record.__dict__)
            seen.add(url)
    return records


async def research_event(*, settings: Settings, template: dict, question: str,
                         evidence: list[dict[str, Any]], symbols: list[str]) -> dict:
    # First pass retrieves Search/URL grounding. Its prose is discarded; only
    # provider-returned supported chunks on curated hosts become evidence.
    _, discovery_text, discovery_grounding = await _generate_structured(
        settings=settings, prompt=RESEARCH_PROMPT,
        context={"template": template, "question": question[:1000], "symbols": symbols,
                 "evidence": evidence}, response_schema=ResearchOutput,
        tools=[types.Tool(google_search=types.GoogleSearch()),
               types.Tool(url_context=types.UrlContext())],
    )
    approved_domains = {item.strip().lower() for item in settings.approved_news_domains.split(",") if item.strip()}
    evidence = [*evidence, *grounded_source_records(discovery_grounding, approved_domains)]
    available = _available_ids(evidence)

    def check(result: ResearchOutput, grounding: dict) -> None:
        for fact in result.facts:
            if not set(fact.evidence_ids).issubset(available):
                raise GeminiUnavailable("Research cited unavailable event evidence.")

    result, raw, grounding = await _generate_structured(
        settings=settings, prompt=RESEARCH_PROMPT,
        context={"template": template, "question": question[:1000], "symbols": symbols,
                 "evidence": evidence}, response_schema=ResearchOutput,
        validate_result=check,
    )
    return {"facts": [fact.model_dump(mode="json") for fact in result.facts],
            "missing_evidence": result.missing_evidence,
            "evidence": evidence,
            "grounding_text": {"discovery": discovery_text, "synthesis": raw},
            "grounding": {"discovery": discovery_grounding, "synthesis": grounding}}


async def design_scenarios(*, settings: Settings, template: dict, question: str,
                           facts: list[dict], evidence: list[dict], symbols: list[str]) -> dict:
    available = _available_ids(evidence)
    if not available:
        raise GeminiUnavailable("No verified, available event evidence supports a scenario proposal.")

    def check(result: DesignOutput, grounding: dict) -> None:
        validate_shocks(result.model_dump(mode="json", by_alias=True), set(symbols),
                        require_units=True, available_evidence_ids=available)

    result, raw, grounding = await _generate_structured(
        settings=settings, prompt=DESIGN_PROMPT,
        context={"template": template, "question": question[:1000], "facts": facts,
                 "available_evidence_ids": sorted(available), "symbols": symbols,
                 "factor_bounds": [-0.5, 0.5], "issuer_bounds": [-3, 3]},
        response_schema=DesignOutput, validate_result=check,
    )
    proposed = result.model_dump(mode="json", by_alias=True)
    return {"proposed_shocks": proposed, "grounding_text": raw, "grounding": grounding}


def run_metric_catalog(result: dict) -> dict[str, float]:
    catalog: dict[str, float] = {}
    for case in result.get("cases", []):
        prefix = f"{case['case']}.{case['horizon']}"
        for side in ("current", "proposed"):
            catalog[f"{prefix}.{side}.estimated_return"] = case[side]["estimated_return"]
        catalog[f"{prefix}.delta.estimated_return"] = case["delta"]["estimated_return"]
    return catalog


async def answer_run_question(*, settings: Settings, question: str,
                              result: dict, facts: list[dict], evidence: list[dict]) -> dict:
    catalog = run_metric_catalog(result)

    def check(answer: GroundedAnswer, grounding: dict) -> None:
        if any(char.isnumeric() for char in answer.explanation) or NUMBER_WORDS.search(answer.explanation):
            raise GeminiUnavailable("Run answer put numbers outside cited metrics.")
        if not set(answer.cited_fields).issubset(catalog):
            raise GeminiUnavailable("Run answer cited an unknown metric.")

    answer, raw, grounding = await _generate_structured(
        settings=settings, prompt=CHAT_PROMPT,
        context={"question": question, "facts": facts, "evidence": evidence,
                 "metrics": catalog, "probability_status": result.get("probabilities", {}).get("status"),
                 "probability_omission_reason": result.get("probabilities", {}).get("reason")},
        response_schema=GroundedAnswer, validate_result=check,
    )
    citations = [{"field": key, "value": catalog[key]} for key in dict.fromkeys(answer.cited_fields)]
    details = "\n".join(f"- {item['field']}: {item['value']:.1%}" for item in citations)
    return {"content": answer.explanation + ("\n\nCalculated run metrics:\n" + details if details else ""),
            "citations": citations, "grounding_text": raw, "grounding": grounding}
