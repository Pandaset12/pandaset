import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types

from backend.config import Settings
from backend.gemini_service import GeminiUnavailable, extract_evidence, generate_answer, resolve_citations
from backend.providers import demo_metrics
from backend.schemas import AnalystRequest


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


def test_structured_answer_uses_backend_values_and_selected_tools():
    raw = json.dumps({"answer": "Demo NVDA contributes 41% of volatility.",
                      "cited_fields": ["risk_contribution.NVDA", "risk_contribution.NVDA"]})
    client = FakeClient(response_with_text(raw))
    constructor_options = {}

    def factory(**kwargs):
        constructor_options.update(kwargs)
        return client

    result = asyncio.run(generate_answer(
        AnalystRequest(question="Explain risk", web_search=False, source_urls=["https://www.sec.gov/"]),
        demo_metrics(), settings(), client_factory=factory,
    ))
    assert result["citations"][0].model_dump() == {"field": "risk_contribution.NVDA", "value": 0.41}
    assert len(result["citations"]) == 1
    assert result["grounding_text"] == raw
    assert result["sources"] == []
    call = client.models.generate_content.call_args.kwargs
    assert len(call["config"].tools) == 1
    assert call["config"].tools[0].url_context is not None
    assert call["config"].tools[0].google_search is None
    context = json.loads(call["contents"])
    assert context["available_metrics"]["risk_contribution.NVDA"] == 0.41
    assert constructor_options["http_options"].retry_options.attempts == 2
    assert client.closed


@pytest.mark.parametrize("raw", [
    "not JSON",
    '{"answer":"  ","cited_fields":[]}',
    '{"answer":"Invented metric","cited_fields":["unknown"]}',
    '{"answer":"Missing return","cited_fields":["portfolio_return"]}',
])
def test_invalid_model_output_is_rejected(raw):
    client = FakeClient(response_with_text(raw))
    with pytest.raises(GeminiUnavailable):
        asyncio.run(generate_answer(
            AnalystRequest(question="Explain risk"), demo_metrics(), settings(),
            client_factory=lambda **_: client,
        ))
    assert client.closed


def test_entire_gemini_operation_times_out_and_closes_client():
    async def slow_response(**kwargs):
        await asyncio.sleep(1)

    client = FakeClient(side_effect=slow_response)
    with pytest.raises(GeminiUnavailable, match="time limit"):
        asyncio.run(generate_answer(
            AnalystRequest(question="Explain risk"), demo_metrics(),
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
