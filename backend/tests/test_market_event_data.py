import json
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.event_sources import (
    FredClient, UnapprovedNewsSource, official_source_evidence, record_approved_news,
)
from backend.event_templates import get_event_template, list_event_templates
from backend.instruments import SUPPORTED_INSTRUMENTS, UnsupportedInstrument, resolve_instrument
from backend.twelve_data import CoverageError, ProviderUnavailable, TwelveDataPriceProvider


def series(symbol, rows):
    return {"meta": {"symbol": symbol}, "values": [
        {"datetime": day, "close": str(close)} for day, close in rows
    ]}


def test_supported_universe_has_25_stocks_and_factor_products():
    assert sum(item.kind == "us_stock" for item in SUPPORTED_INSTRUMENTS.values()) == 25
    assert resolve_instrument("spy").kind == "equity_etf"
    assert resolve_instrument("TLT").kind == "treasury_etf"
    assert resolve_instrument("GLD").kind == "gold_etp"
    with pytest.raises(UnsupportedInstrument):
        resolve_instrument("UNKNOWN")


def test_adjusted_history_is_sorted_aligned_and_provenance_is_explicit(monkeypatch):
    payload = {
        "SPY": series("SPY", [("2026-09-25", 102), ("2026-09-24", 100)]),
        "TLT": series("TLT", [("2026-09-24", 200), ("2026-09-25", 198)]),
    }
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return Response()

    monkeypatch.setattr("backend.twelve_data.urlopen", fake_urlopen)
    frame = TwelveDataPriceProvider("test-key").prices(["spy", "TLT"], 1)
    query = parse_qs(urlsplit(captured["url"]).query)
    assert query["symbol"] == ["SPY,TLT"]
    assert query["adjust"] == ["all"]
    assert query["outputsize"] == ["2"]
    assert list(frame.index.strftime("%Y-%m-%d")) == ["2026-09-24", "2026-09-25"]
    assert frame["SPY"].tolist() == [100.0, 102.0]
    assert frame.attrs["provenance"]["data_source"] == "twelve_data_adjusted_daily"


def test_missing_coverage_and_vendor_failure_never_use_sample_data():
    provider = TwelveDataPriceProvider("test-key")
    provider._fetch = lambda *_: series("SPY", [("2026-09-25", 100)])
    with pytest.raises(CoverageError, match="only 0 return observations"):
        provider.prices(["SPY"], 1)
    provider._fetch = lambda *_: {"status": "error", "code": 429, "message": "quota"}
    with pytest.raises(ProviderUnavailable, match="quota"):
        provider.prices(["SPY"], 1)


def test_cache_requires_rights_and_reuses_complete_rows(tmp_path):
    with pytest.raises(ValueError, match="durable cache path"):
        TwelveDataPriceProvider("key", cache_allowed=True)
    provider = TwelveDataPriceProvider(
        "key", cache_allowed=True, cache_path=tmp_path / "history.sqlite3",
    )
    calls = []
    provider._fetch = lambda symbols, count: (
        calls.append((symbols, count)) or series("SPY", [
            ("2026-09-25", 102), ("2026-09-24", 100),
        ])
    )
    first = provider.prices(["SPY"], 1)
    second = provider.prices(["SPY"], 1)
    assert calls == [(["SPY"], 2)]
    assert first.equals(second)
    assert second.attrs["provenance"]["cache_symbols"] == ["SPY"]


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
