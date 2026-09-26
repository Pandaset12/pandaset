import asyncio
import json
import logging
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Type

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from .config import Settings
from .schemas import (
    AnalystRequest,
    AnalyticsSnapshot,
    GroundedAnswer,
    MetricCitation,
    ResearchSummaryDraft,
)


logger = logging.getLogger("portfoliolens")


@lru_cache(maxsize=1)
def analyst_prompt() -> str:
    return (Path(__file__).parent / "prompts" / "analyst.txt").read_text("utf-8")


@lru_cache(maxsize=4)
def workflow_prompt(workflow: str) -> str:
    allowed = {
        "analysis_briefing",
        "risk_explanation",
        "scenario_explanation",
        "research_summary",
    }
    if workflow not in allowed:
        raise ValueError("Unknown AI workflow.")
    return (Path(__file__).parent / "prompts" / f"{workflow}.txt").read_text("utf-8")


class GeminiNotConfigured(Exception):
    pass


class GeminiUnavailable(Exception):
    def __init__(self, message: str, *, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


def metric_catalog(metrics: AnalyticsSnapshot) -> dict[str, float]:
    """Build exact evidence keys from a validated server-side snapshot."""
    values: dict[str, float] = {"portfolio_volatility": metrics.portfolio_volatility}
    for field in (
        "portfolio_return",
        "annualized_return",
        "max_drawdown",
    ):
        value = getattr(metrics, field)
        if value is not None:
            values[field] = value
    for field in ("weights", "risk_contribution", "asset_volatility", "return_contribution"):
        values.update(
            {
                f"{field}.{symbol}": value
                for symbol, value in (getattr(metrics, field) or {}).items()
                if value is not None
            }
        )
    for symbol, row in (metrics.correlation_matrix or {}).items():
        values.update(
            {
                f"correlation.{symbol}.{other}": value
                for other, value in row.items()
                if value is not None
            }
        )
    return values


def workflow_snapshot_context(metrics: AnalyticsSnapshot) -> dict[str, Any]:
    """Keep workflow prompts to saved metrics and provenance, excluding raw series."""
    snapshot = metrics.model_dump(mode="json")
    fields = (
        "portfolio_id",
        "data_mode",
        "data_as_of",
        "lookback_trading_days",
        "observation_count",
        "return_frequency",
        "volatility_unit",
        "portfolio_return",
        "annualized_return",
        "max_drawdown",
        "portfolio_volatility",
        "weights",
        "asset_volatility",
        "correlation_matrix",
        "risk_contribution",
        "return_contribution",
        "data_source",
        "freshness",
        "notes",
        "assumptions",
    )
    return {field: snapshot[field] for field in fields}


def analysis_workflow_evidence(
    workflow: Literal["analysis_briefing", "risk_explanation"],
    metrics: AnalyticsSnapshot,
) -> tuple[dict[str, Any], dict[str, float]]:
    """Give each workflow only the snapshot fields and metrics it can explain."""
    provenance = {
        "portfolio_id", "data_mode", "data_as_of", "lookback_trading_days",
        "observation_count", "return_frequency", "volatility_unit",
        "data_source", "freshness", "notes", "assumptions",
    }
    if workflow == "analysis_briefing":
        snapshot_fields = {
            "weights", "portfolio_return", "annualized_return", "max_drawdown",
            "portfolio_volatility", "return_contribution",
        }
        metric_fields = {
            "portfolio_return", "annualized_return", "max_drawdown",
            "portfolio_volatility",
        }
        metric_prefixes = ("weights.", "return_contribution.")
    else:
        snapshot_fields = {
            "weights", "portfolio_volatility", "risk_contribution",
            "asset_volatility", "correlation_matrix",
        }
        metric_fields = {"portfolio_volatility"}
        metric_prefixes = (
            "weights.", "risk_contribution.", "asset_volatility.", "correlation.",
        )
    snapshot = workflow_snapshot_context(metrics)
    catalog = metric_catalog(metrics)
    return (
        {key: value for key, value in snapshot.items() if key in provenance | snapshot_fields},
        {
            key: value for key, value in catalog.items()
            if key in metric_fields or key.startswith(metric_prefixes)
        },
    )


def scenario_metric_catalog(comparison: dict[str, Any]) -> tuple[dict[str, float], dict[str, str], bool]:
    catalog: dict[str, float] = {}
    labels: dict[str, str] = {}
    is_demo = False
    for side, title in (("current_analysis", "Current"), ("proposed_analysis", "Proposed")):
        metrics = AnalyticsSnapshot.model_validate(comparison[side])
        is_demo = is_demo or metrics.data_mode == "demo"
        source = metric_catalog(metrics)
        label_map = metric_labels(metrics)
        prefix = "baseline" if side == "current_analysis" else "proposed"
        for field, value in source.items():
            key = f"{prefix}.{field}"
            catalog[key] = value
            labels[key] = f"{title} {label_map[field]}"
    for field, value in comparison.get("delta", {}).items():
        if value is None:
            continue
        key = f"delta.{field}"
        catalog[key] = float(value)
        labels[key] = f"Change in {metric_labels(None).get(field, field.replace('_', ' '))}"
    return catalog, labels, is_demo


def metric_labels(metrics: AnalyticsSnapshot | None) -> dict[str, str]:
    labels = {
        "portfolio_volatility": "annualized portfolio volatility",
        "portfolio_return": "return over the available sample",
        "annualized_return": "annualized portfolio return",
        "max_drawdown": "maximum drawdown over the available sample",
    }
    if metrics is None:
        return labels
    for symbol in metrics.weights:
        labels[f"weights.{symbol}"] = f"{symbol} capital weight"
        labels[f"risk_contribution.{symbol}"] = f"{symbol} share of portfolio volatility"
        labels[f"asset_volatility.{symbol}"] = f"{symbol} annualized volatility"
        labels[f"return_contribution.{symbol}"] = f"{symbol} return contribution"
    for symbol, row in (metrics.correlation_matrix or {}).items():
        for other in row:
            labels[f"correlation.{symbol}.{other}"] = f"{symbol} and {other} return correlation"
    return labels


def resolve_citations(fields: list[str], metrics: AnalyticsSnapshot) -> list[MetricCitation]:
    catalog = metric_catalog(metrics)
    if any(field not in catalog for field in fields):
        raise GeminiUnavailable("Gemini cited a metric that is not present in this analysis.")
    return [MetricCitation(field=field, value=catalog[field]) for field in dict.fromkeys(fields)]


# Qualitative portfolio prose excludes numbers because all quantitative facts
# are rendered separately from backend-owned evidence catalogs.
NUMBER_WORDS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"trillion|half|quarter|twice|double|triple)\b",
    re.IGNORECASE,
)


def _format_fact(field: str, value: float, label: str) -> str:
    rendered = f"{value:.3f}" if field.startswith("correlation.") else f"{value:.1%}"
    return f"- {label}: {rendered}"


def _render_grounded_answer(
    draft: GroundedAnswer,
    catalog: dict[str, float],
    labels: dict[str, str],
    *,
    is_demo: bool,
    heading: str,
) -> tuple[str, list[MetricCitation]]:
    explanation = draft.explanation
    if any(char.isnumeric() for char in explanation) or NUMBER_WORDS.search(explanation):
        raise GeminiUnavailable("Gemini returned numerical prose instead of metric references.")
    if any(field not in catalog for field in draft.cited_fields):
        raise GeminiUnavailable("Gemini cited a metric that is not present in this analysis.")
    fields = list(dict.fromkeys(draft.cited_fields))
    citations = [MetricCitation(field=field, value=catalog[field]) for field in fields]
    facts = [_format_fact(field, catalog[field], labels[field]) for field in fields]
    answer = explanation + (f"\n\n{heading}:\n" + "\n".join(facts) if facts else "")
    if is_demo:
        answer = "FICTIONAL DEMO DATA. " + answer
    return answer, citations


def render_grounded_answer(
    draft: GroundedAnswer, metrics: AnalyticsSnapshot,
) -> tuple[str, list[MetricCitation]]:
    return _render_grounded_answer(
        draft,
        metric_catalog(metrics),
        metric_labels(metrics),
        is_demo=metrics.data_mode == "demo",
        heading="Snapshot metrics",
    )


def render_grounded_scenario(
    draft: GroundedAnswer, comparison: dict[str, Any],
) -> tuple[str, list[MetricCitation]]:
    catalog, labels, is_demo = scenario_metric_catalog(comparison)
    return _render_grounded_answer(
        draft,
        catalog,
        labels,
        is_demo=is_demo,
        heading="Quant-engine comparison metrics",
    )


def metric_summary(metrics: AnalyticsSnapshot) -> tuple[str, list[MetricCitation]]:
    prefix = "FICTIONAL DEMO DATA. " if metrics.data_mode == "demo" else ""
    ranked = {
        symbol: value for symbol, value in metrics.risk_contribution.items()
        if value is not None
    }
    if metrics.portfolio_volatility == 0 or not ranked:
        return prefix + "No relative volatility risk ranking is available for this snapshot.", []
    symbol = max(ranked, key=ranked.get)
    answer = (
        prefix + f"{symbol} contributes {ranked[symbol]:.1%} of "
        f"estimated portfolio volatility, with {metrics.weights[symbol]:.1%} of capital. "
        "These are snapshot metrics, not a prediction or a computed rebalance."
    )
    return answer, resolve_citations([f"risk_contribution.{symbol}", f"weights.{symbol}"], metrics)


def portfolio_briefing_summary(metrics: AnalyticsSnapshot) -> tuple[str, list[MetricCitation]]:
    """Render a brief saved-metric summary when AI is disabled or unavailable."""
    symbol = max(metrics.weights, key=metrics.weights.get)
    facts = [f"{symbol} is the largest holding at {metrics.weights[symbol]:.1%} of capital."]
    fields = [f"weights.{symbol}"]
    if metrics.portfolio_return is not None:
        facts.append(f"Return over the available sample is {metrics.portfolio_return:.1%}.")
        fields.append("portfolio_return")
    facts.append(f"Estimated annualized portfolio volatility is {metrics.portfolio_volatility:.1%}.")
    fields.append("portfolio_volatility")
    prefix = "FICTIONAL DEMO DATA. " if metrics.data_mode == "demo" else ""
    return prefix + " ".join(facts), resolve_citations(fields, metrics)


def extract_evidence(response: Any) -> dict[str, Any]:
    """Keep original grounding indices so the frontend can render citations."""
    result: dict[str, Any] = {
        "sources": [],
        "grounding_supports": [],
        "search_suggestions_html": None,
        "url_retrievals": [],
    }
    candidates = response.candidates or []
    if not candidates:
        return result
    candidate = candidates[0]
    metadata = candidate.grounding_metadata
    if metadata:
        for chunk in metadata.grounding_chunks or []:
            result["sources"].append(chunk.model_dump(mode="json", exclude_none=True))
        for support in metadata.grounding_supports or []:
            indices = support.grounding_chunk_indices or []
            if indices and all(0 <= index < len(result["sources"]) for index in indices):
                result["grounding_supports"].append(
                    support.model_dump(mode="json", exclude_none=True)
                )
        if metadata.search_entry_point:
            result["search_suggestions_html"] = metadata.search_entry_point.rendered_content
    if candidate.url_context_metadata:
        result["url_retrievals"] = [
            item.model_dump(mode="json", exclude_none=True)
            for item in candidate.url_context_metadata.url_metadata or []
        ]
    return result


async def _generate_structured_once(
    *,
    settings: Settings,
    model: str,
    prompt: str,
    context: dict[str, Any],
    response_schema: Type[BaseModel],
    tools: list[types.Tool] | None = None,
    client_factory=None,
) -> tuple[BaseModel, str, dict[str, Any]]:
    config = types.GenerateContentConfig(
        system_instruction=prompt,
        tools=tools or None,
        max_output_tokens=2048,
        response_mime_type="application/json",
        response_json_schema=response_schema.model_json_schema(),
    )
    try:
        factory = client_factory or genai.Client
        async with asyncio.timeout(settings.gemini_timeout_seconds):
            async with factory(
                api_key=settings.gemini_api_key.get_secret_value(),
                http_options=types.HttpOptions(
                    timeout=int(settings.gemini_timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(
                        attempts=2,
                        initial_delay=0.5,
                        max_delay=1,
                        http_status_codes=[408, 429, 500, 502, 503, 504],
                    ),
                ),
            ).aio as client:
                response = await client.models.generate_content(
                    model=model,
                    contents=json.dumps(context, ensure_ascii=False),
                    config=config,
                )
        raw_text = response.text or ""
        draft = response_schema.model_validate_json(raw_text)
        return draft, raw_text, extract_evidence(response)
    except TimeoutError as exc:
        raise GeminiUnavailable("Gemini exceeded the request time limit.") from exc
    except errors.ServerError as exc:
        if getattr(exc, "code", None) == 503:
            raise GeminiUnavailable("Gemini is busy right now. Retry this request in a moment.") from exc
        raise GeminiUnavailable("Gemini request failed. Please retry this request.") from exc
    except GeminiUnavailable:
        raise
    except Exception as exc:
        raise GeminiUnavailable(
            "Gemini request failed. Check the model, API key, quota, and connectivity."
        ) from exc


async def _generate_structured(
    *,
    settings: Settings,
    prompt: str,
    context: dict[str, Any],
    response_schema: Type[BaseModel],
    tools: list[types.Tool] | None = None,
    client_factory=None,
    validate_result: Callable[[BaseModel, dict[str, Any]], None] | None = None,
) -> tuple[BaseModel, str, dict[str, Any]]:
    if not settings.has_gemini_key:
        raise GeminiNotConfigured("Set GEMINI_API_KEY in backend/.env first.")
    models = [settings.gemini_model]
    fallback = settings.gemini_fallback_model.strip()
    if fallback and fallback != settings.gemini_model:
        models.append(fallback)
    for index, model in enumerate(models):
        try:
            draft, raw_text, evidence = await _generate_structured_once(
                settings=settings,
                model=model,
                prompt=prompt,
                context=context,
                response_schema=response_schema,
                tools=tools,
                client_factory=client_factory,
            )
            if validate_result is not None:
                validate_result(draft, evidence)
            return draft, raw_text, evidence
        except GeminiUnavailable as exc:
            if index == len(models) - 1:
                raise
            cause = type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__
            logger.warning(
                "Gemini model %s failed (%s); trying fallback model %s",
                model,
                cause,
                models[index + 1],
            )
    raise AssertionError("Gemini model list cannot be empty.")


async def generate_answer(
    request: AnalystRequest,
    metrics: AnalyticsSnapshot,
    settings: Settings,
    *,
    client_factory=None,
) -> dict[str, Any]:
    tools: list[types.Tool] = []
    if request.web_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    if request.web_search or request.source_urls:
        tools.append(types.Tool(url_context=types.UrlContext()))
    context = {
        "question": request.question,
        "portfolio_metrics": metrics.model_dump(mode="json"),
        "available_metrics": metric_catalog(metrics),
        "source_urls": [str(url) for url in request.source_urls],
    }

    def validate_result(draft, evidence):
        render_grounded_answer(draft, metrics)

    draft, raw_text, evidence = await _generate_structured(
        settings=settings,
        prompt=analyst_prompt(),
        context=context,
        response_schema=GroundedAnswer,
        tools=tools,
        client_factory=client_factory,
        validate_result=validate_result,
    )
    answer, citations = render_grounded_answer(draft, metrics)
    return {
        "answer": answer,
        "citations": citations,
        "grounding_text": raw_text,
        **evidence,
    }


async def generate_analysis_workflow(
    workflow: Literal["analysis_briefing", "risk_explanation"],
    question: str,
    metrics: AnalyticsSnapshot,
    analysis_id: str,
    settings: Settings,
    *,
    client_factory=None,
) -> dict[str, Any]:
    snapshot, available_metrics = analysis_workflow_evidence(workflow, metrics)
    labels = metric_labels(metrics)
    heading = "Briefing metrics" if workflow == "analysis_briefing" else "Risk metrics"

    def validate_result(draft, evidence):
        _render_grounded_answer(
            draft,
            available_metrics,
            labels,
            is_demo=metrics.data_mode == "demo",
            heading=heading,
        )

    draft, raw_text, evidence = await _generate_structured(
        settings=settings,
        prompt=workflow_prompt(workflow),
        context={
            "question": question,
            "analysis_id": analysis_id,
            "portfolio_snapshot": snapshot,
            "available_metrics": available_metrics,
        },
        response_schema=GroundedAnswer,
        client_factory=client_factory,
        validate_result=validate_result,
    )
    answer, citations = _render_grounded_answer(
        draft,
        available_metrics,
        labels,
        is_demo=metrics.data_mode == "demo",
        heading=heading,
    )
    return {"answer": answer, "citations": citations, "grounding_text": raw_text, **evidence}


async def generate_scenario_workflow(
    question: str,
    comparison: dict[str, Any],
    settings: Settings,
    *,
    analysis_id: str | None = None,
    client_factory=None,
) -> dict[str, Any]:
    catalog, _, _ = scenario_metric_catalog(comparison)
    baseline = AnalyticsSnapshot.model_validate(comparison["current_analysis"])
    proposed = AnalyticsSnapshot.model_validate(comparison["proposed_analysis"])

    def validate_result(draft, evidence):
        render_grounded_scenario(draft, comparison)

    draft, raw_text, evidence = await _generate_structured(
        settings=settings,
        prompt=workflow_prompt("scenario_explanation"),
        context={
            "question": question,
            "analysis_id": analysis_id,
            "baseline": workflow_snapshot_context(baseline),
            "proposed": workflow_snapshot_context(proposed),
            "delta": comparison.get("delta", {}),
            "available_metrics": catalog,
            "difference_convention": comparison.get("difference_convention"),
        },
        response_schema=GroundedAnswer,
        client_factory=client_factory,
        validate_result=validate_result,
    )
    answer, citations = render_grounded_scenario(draft, comparison)
    return {"answer": answer, "citations": citations, "grounding_text": raw_text, **evidence}


def _retrieval_succeeded(url_retrievals: list[dict[str, Any]]) -> bool:
    for retrieval in url_retrievals:
        status = str(retrieval.get("url_retrieval_status", "")).upper()
        if status.endswith("SUCCESS"):
            return True
    return False


async def generate_research_summary(
    symbol: str,
    source_url: str,
    settings: Settings,
    *,
    client_factory=None,
) -> dict[str, Any]:
    def validate_result(draft, evidence):
        if not _retrieval_succeeded(evidence["url_retrievals"]):
            raise GeminiUnavailable(
                "The selected source could not be retrieved with usable evidence.",
                evidence=evidence,
            )

    draft, raw_text, evidence = await _generate_structured(
        settings=settings,
        prompt=workflow_prompt("research_summary"),
        context={"symbol": symbol, "source_url": source_url},
        response_schema=ResearchSummaryDraft,
        tools=[types.Tool(url_context=types.UrlContext())],
        client_factory=client_factory,
        validate_result=validate_result,
    )
    retrievals = evidence["url_retrievals"]
    if not _retrieval_succeeded(retrievals):
        raise GeminiUnavailable(
            "The selected source could not be retrieved with usable evidence.",
            evidence=evidence,
        )
    summary = draft.summary
    if draft.key_points:
        summary += "\n\nKey points:\n" + "\n".join(f"- {point}" for point in draft.key_points)
    return {
        "answer": summary,
        "citations": [],
        "grounding_text": raw_text,
        **evidence,
    }
