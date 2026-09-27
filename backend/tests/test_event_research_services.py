import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.config import Settings
from backend.event_research_services import (
    EventResearchUnavailable,
    _approved_source,
    _published_at,
    extract_event_facts,
    retrieve_event_evidence,
)


def test_only_curated_https_hosts_are_candidates():
    assert _approved_source("https://www.bls.gov/news.release/cpi.htm", ("bls_cpi",), set())
    assert _approved_source("https://fake-bls.gov/news", ("bls_cpi",), set()) is None
    assert _approved_source("http://www.bls.gov/news", ("bls_cpi",), set()) is None
    assert _approved_source("https://www.bls.gov:444/news", ("bls_cpi",), set()) is None
    assert _approved_source("https://www.bls.gov:bad/news", ("bls_cpi",), set()) is None
    assert _approved_source("https://sub.example.com/news", (), {"example.com"})


def test_publication_dates_are_not_invented_or_future_dated():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    assert _published_at("2025-09-01", now) == datetime(2025, 9, 1, tzinfo=timezone.utc)
    assert _published_at("2027-01-01T00:00:00Z", now) is None
    assert _published_at("Fri, 25 Sep 2026 12:00:00 GMT", now)


def test_only_extracted_pages_become_available_evidence(monkeypatch):
    search = {"results": [
        {"url": "https://www.bls.gov/news.release/cpi.htm", "title": "CPI release",
         "published_date": "Fri, 25 Sep 2026 12:00:00 GMT", "content": "Snippet only"},
        {"url": "https://www.bls.gov/unavailable", "title": "Other page",
         "published_date": "Fri, 25 Sep 2026 12:00:00 GMT"},
        {"url": "https://unapproved.example/claim", "title": "Unapproved"},
    ]}
    extract = {"results": [
        {"url": "https://www.bls.gov/news.release/cpi.htm", "raw_content": "Extracted CPI page."},
    ], "failed_results": [{"url": "https://www.bls.gov/unavailable"}]}
    post = AsyncMock(side_effect=[search, extract])
    monkeypatch.setattr("backend.event_research_services._post", post)
    records, metadata = asyncio.run(retrieve_event_evidence(
        settings=Settings(tavily_api_key="test"),
        template={"title": "Inflation release", "official_source_ids": ("bls_cpi",)},
        question="latest CPI", symbols=["SPY"],
    ))
    assert len(records) == 2
    assert records[0]["status"] == "available"
    assert records[0]["excerpt"] == "Extracted CPI page."
    assert records[1]["status"] == "unavailable"
    assert records[1]["retrieval_status"] == "failed"
    assert metadata["failed_urls"] == ["https://www.bls.gov/unavailable"]
    assert post.call_args_list[0].args[3]["filter_by_published_date"] is True


def test_deepseek_cannot_cite_an_unknown_evidence_id(monkeypatch):
    post = AsyncMock(return_value={"choices": [{"message": {"content":
        '{"facts":[{"claim":"Unsupported","evidence_ids":["unknown"]}],"missing_evidence":[]}'}}]})
    monkeypatch.setattr("backend.event_research_services._post", post)
    with pytest.raises(EventResearchUnavailable, match="unavailable event evidence"):
        asyncio.run(extract_event_facts(
            settings=Settings(deepseek_api_key="test"), template={"title": "Event"},
            question="What happened?", symbols=["SPY"],
            evidence=[{"evidence_id": "approved", "status": "available", "excerpt": "Source"}],
        ))
