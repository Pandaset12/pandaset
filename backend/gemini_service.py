import asyncio
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from .config import Settings
from .schemas import AnalystRequest, AnalyticsSnapshot, GroundedAnswer, MetricCitation


@lru_cache(maxsize=1)
def analyst_prompt() -> str:
    return (Path(__file__).parent / "prompts" / "analyst.txt").read_text("utf-8")


class GeminiNotConfigured(Exception):
    pass


class GeminiUnavailable(Exception):
    pass


def metric_catalog(metrics: AnalyticsSnapshot) -> dict[str, float]:
    """Exact keys also work for dotted symbols such as BRK.B."""
    values = {"portfolio_volatility": metrics.portfolio_volatility}
    if metrics.portfolio_return is not None:
        values["portfolio_return"] = metrics.portfolio_return
    for field in ("weights", "risk_contribution", "asset_volatility"):
        values.update(
            {f"{field}.{symbol}": value for symbol, value in (getattr(metrics, field) or {}).items()
             if value is not None}
        )
    return values


def resolve_citations(fields: list[str], metrics: AnalyticsSnapshot) -> list[MetricCitation]:
    catalog = metric_catalog(metrics)
    if any(field not in catalog for field in fields):
        raise GeminiUnavailable("Gemini cited a metric that is not present in this analysis.")
    return [MetricCitation(field=field, value=catalog[field]) for field in dict.fromkeys(fields)]


# Qualitative prose is separate from the server-rendered numerical facts.
# This catches numeric literals and common English number words, not every
# possible misleading quantitative claim in natural language.
NUMBER_WORDS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"trillion|half|quarter|twice|double|triple)\b", re.IGNORECASE
)


def render_grounded_answer(
    draft: GroundedAnswer, metrics: AnalyticsSnapshot,
) -> tuple[str, list[MetricCitation]]:
    explanation = draft.explanation
    if any(char.isnumeric() for char in explanation) or NUMBER_WORDS.search(explanation):
        raise GeminiUnavailable("Gemini returned numerical prose instead of metric references.")
    citations = resolve_citations(draft.cited_fields, metrics)
    labels = {
        "portfolio_volatility": "Annualized portfolio volatility",
        "portfolio_return": "Portfolio return over the analysis window",
    }
    for symbol in metrics.weights:
        labels[f"weights.{symbol}"] = f"{symbol} capital weight"
        labels[f"risk_contribution.{symbol}"] = f"{symbol} share of portfolio volatility"
        labels[f"asset_volatility.{symbol}"] = f"{symbol} annualized volatility"
    facts = [f"- {labels[item.field]}: {item.value:.1%}" for item in citations]
    answer = explanation + ("\n\nSnapshot metrics:\n" + "\n".join(facts) if facts else "")
    if metrics.data_mode == "demo":
        answer = "FICTIONAL DEMO DATA. " + answer
    return answer, citations


def metric_summary(metrics: AnalyticsSnapshot) -> tuple[str, list[MetricCitation]]:
    prefix = "FICTIONAL DEMO DATA. " if metrics.data_mode == "demo" else ""
    if metrics.portfolio_volatility == 0 or not metrics.risk_contribution:
        return prefix + "No relative volatility risk ranking is available for this snapshot.", []
    symbol = max(metrics.risk_contribution, key=metrics.risk_contribution.get)
    answer = (
        prefix + f"{symbol} contributes {metrics.risk_contribution[symbol]:.1%} of "
        f"estimated portfolio volatility, with {metrics.weights[symbol]:.1%} of capital. "
        "These are snapshot metrics, not a prediction or a computed rebalance."
    )
    return answer, resolve_citations([f"risk_contribution.{symbol}", f"weights.{symbol}"], metrics)


def extract_evidence(response: Any) -> dict[str, Any]:
    """Keep original grounding indices so the frontend can render citations."""
    result: dict[str, Any] = {
        "sources": [],
        "grounding_supports": [],
        "search_suggestions_html": None,
        "web_search_queries": [],
        "url_retrievals": [],
    }
    candidates = response.candidates or []
    if not candidates:
        return result
    candidate = candidates[0]
    metadata = candidate.grounding_metadata
    if metadata:
        result["web_search_queries"] = list(metadata.web_search_queries or [])
        # Preserve one entry for every chunk, including chunks without a web URL,
        # so grounding_supports indices still refer to the correct sources.
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


async def generate_answer(
    request: AnalystRequest, metrics: AnalyticsSnapshot, settings: Settings,
    *, client_factory=None,
) -> dict[str, Any]:
    if not settings.has_gemini_key:
        raise GeminiNotConfigured("Set GEMINI_API_KEY in backend/.env first.")

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
    config = types.GenerateContentConfig(
        system_instruction=analyst_prompt(),
        tools=tools or None,
        max_output_tokens=2048,
        response_mime_type="application/json",
        response_json_schema=GroundedAnswer.model_json_schema(),
    )
    try:
        factory = client_factory or genai.Client
        # Bound the entire operation, including retry delays, not only each HTTP call.
        async with asyncio.timeout(settings.gemini_timeout_seconds):
            async with factory(
                api_key=settings.gemini_api_key.get_secret_value(),
                http_options=types.HttpOptions(
                    timeout=int(settings.gemini_timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(
                        attempts=2, initial_delay=0.5, max_delay=1,
                        http_status_codes=[408, 429, 500, 502, 503, 504],
                    ),
                ),
            ).aio as client:
                response = await client.models.generate_content(
                    model=settings.gemini_model,
                    contents=json.dumps(context, ensure_ascii=False),
                    config=config,
                )
        raw_text = response.text or ""
        draft = GroundedAnswer.model_validate_json(raw_text)
        answer, citations = render_grounded_answer(draft, metrics)
        evidence = extract_evidence(response)
    except TimeoutError as exc:
        raise GeminiUnavailable("Gemini exceeded the request time limit.") from exc
    except GeminiUnavailable:
        raise
    except Exception as exc:
        # Return a stable error without exposing credentials or upstream payloads.
        raise GeminiUnavailable(
            "Gemini request failed. Check the model, API key, quota, and connectivity."
        ) from exc
    return {
        "answer": answer,
        "citations": citations,
        "grounding_text": raw_text,
        **evidence,
    }
