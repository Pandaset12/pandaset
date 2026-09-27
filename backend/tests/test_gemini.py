import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types

from backend.config import Settings
from backend.gemini_service import (
    GeminiUnavailable,
    extract_evidence,
    generate_analysis_workflow,
    generate_research_summary,
    generate_scenario_workflow,
    metric_summary,
    render_grounded_scenario,
    resolve_citations,
)
from backend.providers import demo_metrics
from backend.schemas import GroundedAnswer


class FakeClient:
    def __init__(self, response=None, side_effect=None):
        self.aio = self
        self.closed = False
        self.models = SimpleNamespace(generate_content=AsyncMock(return_value=response, side_effect=side_effect))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


def response_with_text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(parts=[types.Part(text=text)]),
    )])


def settings(**overrides):
    return Settings(_env_file=None, analyst_mode="gemini", gemini_api_key="test-only", **overrides)


@pytest.mark.parametrize("raw", [
    "not JSON",
    '{"explanation":"  ","cited_fields":[]}',
    '{"explanation":"Invented metric","cited_fields":["unknown"]}',
    '{"explanation":"Missing return","cited_fields":["portfolio_return"]}',
])
def test_invalid_model_output_is_rejected(raw):
    client = FakeClient(response_with_text(raw))
    with pytest.raises(GeminiUnavailable):
        asyncio.run(generate_analysis_workflow(
            "risk_explanation", "Explain risk", demo_metrics(), "analysis-42",
            settings(), client_factory=lambda **_: client,
        ))
    assert client.closed


def test_entire_gemini_operation_times_out_and_closes_client():
    async def slow_response(**kwargs):
        await asyncio.sleep(1)

    client = FakeClient(side_effect=slow_response)
    with pytest.raises(GeminiUnavailable, match="time limit"):
        asyncio.run(generate_analysis_workflow(
            "risk_explanation", "Explain risk", demo_metrics(), "analysis-42",
            settings(gemini_timeout_seconds=0.02), client_factory=lambda **_: client,
        ))
    assert client.closed


def test_dotted_symbols_can_be_cited_without_path_splitting():
    metrics = demo_metrics()
    metrics.weights["BRK.B"] = metrics.weights.pop("NVDA")
    metrics.risk_contribution["BRK.B"] = metrics.risk_contribution.pop("NVDA")
    assert resolve_citations(["risk_contribution.BRK.B"], metrics)[0].value == 0.41


def test_out_of_range_source_indices_are_not_forwarded():
    response = types.GenerateContentResponse(candidates=[types.Candidate(
        grounding_metadata=types.GroundingMetadata(
            grounding_chunks=[types.GroundingChunk(web=types.GroundingChunkWeb(uri="https://www.sec.gov/"))],
            grounding_supports=[types.GroundingSupport(grounding_chunk_indices=[5])],
        ),
    )])
    evidence = extract_evidence(response)
    assert len(evidence["sources"]) == 1
    assert evidence["grounding_supports"] == []


@pytest.mark.parametrize("explanation", [
    "NVDA contributes 99% of risk.",
    "NVDA contributes ninety-nine percent of risk.",
    "NVDA contributes \u4e5d\u5341\u4e5d% of risk.",
    "NVDA contributes \u00bd of risk.",
])
def test_risk_workflow_rejects_model_authored_numbers(explanation):
    raw = json.dumps({"explanation": explanation, "cited_fields": ["risk_contribution.NVDA"]})
    client = FakeClient(response_with_text(raw))
    with pytest.raises(GeminiUnavailable, match="numerical prose"):
        asyncio.run(generate_analysis_workflow(
            "risk_explanation", "Explain risk", demo_metrics(), "analysis-42",
            settings(), client_factory=lambda **_: client,
        ))


def test_analysis_workflow_uses_its_prompt_and_no_web_tools():
    raw = json.dumps({
        "explanation": "The saved analysis shows a concentrated risk profile.",
        "cited_fields": ["risk_contribution.NVDA"],
    })
    client = FakeClient(response_with_text(raw))
    result = asyncio.run(generate_analysis_workflow(
        "risk_explanation", "Explain the largest risk driver.", demo_metrics(),
        "analysis-42", settings(), client_factory=lambda **_: client,
    ))
    call = client.models.generate_content.call_args.kwargs
    context = json.loads(call["contents"])
    assert "risk explanation writer" in call["config"].system_instruction.lower()
    assert call["config"].tools is None
    assert context["analysis_id"] == "analysis-42"
    assert context["available_metrics"]["risk_contribution.NVDA"] == 0.41
    assert "series" not in context["portfolio_snapshot"]
    assert result["citations"][0].value == 0.41
    assert "FICTIONAL DEMO DATA" in result["answer"]


def test_briefing_and_risk_use_distinct_saved_evidence():
    metrics = demo_metrics()
    metrics.portfolio_return = 0.08
    briefing = FakeClient(response_with_text(json.dumps({
        "explanation": "The saved sample shows portfolio growth.",
        "cited_fields": ["portfolio_return", "weights.NVDA"],
    })))
    risk = FakeClient(response_with_text(json.dumps({
        "explanation": "NVDA is the main contributor to estimated volatility.",
        "cited_fields": ["risk_contribution.NVDA", "weights.NVDA"],
    })))

    briefing_result = asyncio.run(generate_analysis_workflow(
        "analysis_briefing", "Brief this portfolio.", metrics, "analysis-42",
        settings(), client_factory=lambda **_: briefing,
    ))
    risk_result = asyncio.run(generate_analysis_workflow(
        "risk_explanation", "Explain my risk.", metrics, "analysis-42",
        settings(), client_factory=lambda **_: risk,
    ))

    briefing_context = json.loads(briefing.models.generate_content.call_args.kwargs["contents"])
    risk_context = json.loads(risk.models.generate_content.call_args.kwargs["contents"])
    assert "portfolio_return" in briefing_context["available_metrics"]
    assert "risk_contribution.NVDA" not in briefing_context["available_metrics"]
    assert "risk_contribution" not in briefing_context["portfolio_snapshot"]
    assert "risk_contribution.NVDA" in risk_context["available_metrics"]
    assert "portfolio_return" not in risk_context["available_metrics"]
    assert "portfolio_return" not in risk_context["portfolio_snapshot"]
    assert [citation.field for citation in briefing_result["citations"]] == [
        "portfolio_return", "weights.NVDA",
    ]
    assert [citation.field for citation in risk_result["citations"]] == [
        "risk_contribution.NVDA", "weights.NVDA",
    ]

    wrong_field = FakeClient(response_with_text(json.dumps({
        "explanation": "The portfolio has a recorded sample return.",
        "cited_fields": ["portfolio_return"],
    })))
    with pytest.raises(GeminiUnavailable, match="not present"):
        asyncio.run(generate_analysis_workflow(
            "risk_explanation", "Explain my risk.", metrics, "analysis-42",
            settings(), client_factory=lambda **_: wrong_field,
        ))


def test_risk_fallback_skips_undefined_contributions():
    metrics = demo_metrics()
    metrics.risk_contribution = {symbol: None for symbol in metrics.weights}
    answer, citations = metric_summary(metrics)
    assert "No relative volatility risk ranking" in answer
    assert citations == []


def test_scenario_citations_are_resolved_from_the_quant_comparison():
    metrics = demo_metrics().model_dump(mode="json")
    comparison = {
        "current_analysis": metrics,
        "proposed_analysis": metrics,
        "delta": {"portfolio_volatility": 0.012},
        "difference_convention": "proposed minus current",
    }
    raw = json.dumps({
        "explanation": "The proposed mix changes estimated portfolio risk.",
        "cited_fields": ["baseline.portfolio_volatility", "delta.portfolio_volatility"],
    })
    client = FakeClient(response_with_text(raw))
    generated = asyncio.run(generate_scenario_workflow(
        "Explain the trade-offs.", comparison, settings(), analysis_id="analysis-42",
        client_factory=lambda **_: client,
    ))
    context = json.loads(client.models.generate_content.call_args.kwargs["contents"])
    assert context["analysis_id"] == "analysis-42"
    assert context["available_metrics"]["delta.portfolio_volatility"] == 0.012
    assert "series" not in context["baseline"]
    assert "series" not in context["proposed"]
    assert [citation.value for citation in generated["citations"]] == [0.184, 0.012]

    answer, citations = render_grounded_scenario(
        GroundedAnswer(
            explanation="The scenario changes the estimated portfolio risk.",
            cited_fields=["baseline.portfolio_volatility", "delta.portfolio_volatility"],
        ),
        comparison,
    )
    assert [citation.value for citation in citations] == [0.184, 0.012]
    assert "18.4%" in answer
    assert "1.2%" in answer
    with pytest.raises(GeminiUnavailable, match="not present"):
        render_grounded_scenario(
            GroundedAnswer(explanation="The result is informative.", cited_fields=["delta.unknown"]),
            comparison,
        )


def test_research_summary_uses_only_url_context_and_preserves_retrieval_metadata():
    raw = json.dumps({
        "summary": "The issuer page describes its latest reporting and investor materials.",
        "key_points": ["The page links to company disclosures."],
    })
    retrieval = SimpleNamespace(model_dump=lambda **_: {
        "retrieved_url": "https://investor.nvidia.com/financial-info/financial-reports-and-sec-filings/default.aspx",
        "url_retrieval_status": "URL_RETRIEVAL_STATUS_SUCCESS",
    })
    response = SimpleNamespace(
        text=raw,
        candidates=[SimpleNamespace(
            grounding_metadata=None,
            url_context_metadata=SimpleNamespace(url_metadata=[retrieval]),
        )],
    )
    client = FakeClient(response)
    result = asyncio.run(generate_research_summary(
        "NVDA", "https://investor.nvidia.com/financial-info/financial-reports-and-sec-filings/default.aspx",
        settings(), client_factory=lambda **_: client,
    ))
    tools = client.models.generate_content.call_args.kwargs["config"].tools
    assert len(tools) == 1
    assert tools[0].url_context is not None
    assert tools[0].google_search is None
    assert result["url_retrievals"][0]["url_retrieval_status"].endswith("SUCCESS")
    assert "Key points:" in result["answer"]


def test_research_summary_fails_closed_without_successful_retrieval():
    raw = json.dumps({"summary": "A generic page summary.", "key_points": []})
    retrieval = SimpleNamespace(model_dump=lambda **_: {
        "retrieved_url": "https://example.com/",
        "url_retrieval_status": "URL_RETRIEVAL_STATUS_UNAVAILABLE",
    })
    client = FakeClient(SimpleNamespace(
        text=raw,
        candidates=[SimpleNamespace(
            grounding_metadata=None,
            url_context_metadata=SimpleNamespace(url_metadata=[retrieval]),
        )],
    ))
    with pytest.raises(GeminiUnavailable, match="could not be retrieved") as error:
        asyncio.run(generate_research_summary(
            "NVDA", "https://example.com/", settings(),
            client_factory=lambda **_: client,
        ))
    assert error.value.evidence["url_retrievals"][0]["url_retrieval_status"].endswith("UNAVAILABLE")
