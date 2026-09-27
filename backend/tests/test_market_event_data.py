import json
from datetime import date, datetime, timezone

import pytest

from backend.event_sources import (
    FredClient, UnapprovedNewsSource, official_source_evidence, record_approved_news,
)
from backend.event_templates import get_event_template, list_event_templates
from backend.instruments import SUPPORTED_INSTRUMENTS, UnsupportedInstrument, resolve_instrument


def test_supported_universe_has_26_stocks_and_factor_products():
    assert sum(item.kind == "us_stock" for item in SUPPORTED_INSTRUMENTS.values()) == 26
    assert resolve_instrument("spy").kind == "equity_etf"
    assert resolve_instrument("TLT").kind == "treasury_etf"
    assert resolve_instrument("GLD").kind == "gold_etp"
    with pytest.raises(UnsupportedInstrument):
        resolve_instrument("UNKNOWN")


def test_template_versions_and_evidence_statuses(monkeypatch):
    template = get_event_template("fed_policy", "1.0.0")
    assert template.fred_series_ids == ("FEDFUNDS", "DGS2", "DGS10")
    assert any(item.template_id == "issuer_earnings" for item in list_event_templates())
    link = official_source_evidence("fomc_releases")
    assert (link.status, link.retrieval_status, link.publication_status) == (
        "missing", "not_attempted", "unknown",
    )
    missing_key = FredClient("").observation("DGS10")
    assert missing_key.status == "unavailable"

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"observations": [
                {"date": "2026-09-25", "value": "."},
                {"date": "2026-09-24", "value": "4.25"},
            ]}).encode()

    monkeypatch.setattr("backend.event_sources.urlopen", lambda *args, **kwargs: Response())
    observation = FredClient("test-key").observation("DGS10", date(2026, 9, 25))
    assert observation.status == "available"
    assert observation.observed_on == "2026-09-24"
    assert observation.vintage_on == "2026-09-25"
    assert observation.publication_status == "unknown"


def test_news_evidence_requires_explicit_approved_domain():
    retrieved = datetime(2026, 9, 26, tzinfo=timezone.utc)
    args = dict(title="Release", url="https://news.example.com/story", publisher="Example News",
                excerpt="Verified article text", published_at=retrieved, retrieved_at=retrieved)
    with pytest.raises(UnapprovedNewsSource):
        record_approved_news(**args, approved_domains=set())
    item = record_approved_news(**args, approved_domains={"example.com"})
    assert (item.status, item.publication_status, item.retrieval_status) == (
        "available", "known", "retrieved",
    )
