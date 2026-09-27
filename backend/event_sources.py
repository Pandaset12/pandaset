"""Dated macro observations and explicitly curated event source evidence."""

import json
import math
from hashlib import sha256
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


EvidenceStatus = Literal["available", "missing", "unavailable"]
RetrievalStatus = Literal["retrieved", "not_attempted", "failed"]
PublicationStatus = Literal["known", "unknown"]


class UnsupportedEvidenceSource(ValueError):
    pass


class UnapprovedNewsSource(ValueError):
    pass


@dataclass(frozen=True)
class EventEvidence:
    evidence_id: str
    kind: Literal["fred_observation", "official_source", "approved_news"]
    title: str
    source_name: str
    source_url: str
    status: EvidenceStatus
    retrieval_status: RetrievalStatus
    publication_status: PublicationStatus
    observed_on: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    vintage_on: str | None = None
    value: float | None = None
    unit: str | None = None
    excerpt: str | None = None
    missing_reason: str | None = None


@dataclass(frozen=True)
class FredSeries:
    series_id: str
    title: str
    unit: str
    original_source: str


FRED_SERIES: dict[str, FredSeries] = {
    item.series_id: item for item in (
        FredSeries("FEDFUNDS", "Effective Federal Funds Rate", "percent", "Federal Reserve Bank of New York"),
        FredSeries("DGS2", "2-Year Treasury Constant Maturity Rate", "percent", "Board of Governors of the Federal Reserve System"),
        FredSeries("DGS10", "10-Year Treasury Constant Maturity Rate", "percent", "Board of Governors of the Federal Reserve System"),
        FredSeries("CPIAUCSL", "Consumer Price Index for All Urban Consumers", "index", "US Bureau of Labor Statistics"),
        FredSeries("UNRATE", "Civilian Unemployment Rate", "percent", "US Bureau of Labor Statistics"),
        FredSeries("GDPC1", "Real Gross Domestic Product", "billions of chained dollars", "US Bureau of Economic Analysis"),
        FredSeries("INDPRO", "Industrial Production Index", "index", "Board of Governors of the Federal Reserve System"),
    )
}


@dataclass(frozen=True)
class OfficialSource:
    source_id: str
    title: str
    publisher: str
    url: str


OFFICIAL_SOURCES: dict[str, OfficialSource] = {
    item.source_id: item for item in (
        OfficialSource("fomc_releases", "FOMC statements and press releases", "Federal Reserve", "https://www.federalreserve.gov/newsevents/pressreleases.htm"),
        OfficialSource("bls_cpi", "Consumer Price Index releases", "US Bureau of Labor Statistics", "https://www.bls.gov/cpi/"),
        OfficialSource("bea_gdp", "Gross Domestic Product releases", "US Bureau of Economic Analysis", "https://www.bea.gov/data/gdp/gross-domestic-product"),
        OfficialSource("eia_today", "Energy information and releases", "US Energy Information Administration", "https://www.eia.gov/todayinenergy/"),
        OfficialSource("sec_edgar", "SEC EDGAR company filings", "US Securities and Exchange Commission", "https://www.sec.gov/edgar/search/"),
    )
}


def official_source_evidence(source_id: str) -> EventEvidence:
    """Expose an approved link without pretending that its content was retrieved."""
    try:
        source = OFFICIAL_SOURCES[source_id]
    except KeyError as exc:
        raise UnsupportedEvidenceSource(source_id) from exc
    return EventEvidence(
        evidence_id=f"official:{source_id}", kind="official_source", title=source.title,
        source_name=source.publisher, source_url=source.url, status="missing",
        retrieval_status="not_attempted", publication_status="unknown",
        missing_reason="This source is an approved link; no dated release was retrieved.",
    )


def record_source_retrieval(
    source_id: str,
    *,
    source_url: str,
    title: str,
    excerpt: str | None,
    published_at: datetime | None,
    retrieved_at: datetime,
) -> EventEvidence:
    """Record validated official content obtained by a separate retrieval step."""
    source = OFFICIAL_SOURCES.get(source_id)
    if source is None:
        raise UnsupportedEvidenceSource(source_id)
    source_host = urlsplit(source.url).hostname
    parts = urlsplit(source_url)
    if parts.scheme != "https" or parts.hostname != source_host or parts.username or parts.password:
        raise UnsupportedEvidenceSource("The retrieved URL must stay on the curated official host.")
    if retrieved_at.tzinfo is None or published_at is not None and published_at.tzinfo is None:
        raise ValueError("Evidence timestamps must include a timezone.")
    if published_at is not None and published_at > retrieved_at:
        raise ValueError("Publication cannot be later than retrieval.")
    # Different releases on the same approved host may have unknown publication
    # dates. Include the validated URL so their citations stay distinct.
    url_fingerprint = sha256(source_url.encode("utf-8")).hexdigest()[:16]
    return EventEvidence(
        evidence_id=f"official:{source_id}:{published_at.isoformat() if published_at else 'undated'}:{url_fingerprint}",
        kind="official_source", title=title.strip() or source.title,
        source_name=source.publisher, source_url=source_url,
        status="available" if excerpt else "missing", retrieval_status="retrieved",
        publication_status="known" if published_at else "unknown",
        published_at=published_at.isoformat() if published_at else None,
        retrieved_at=retrieved_at.isoformat(), excerpt=excerpt.strip() if excerpt else None,
        missing_reason=None if excerpt else "No source text was returned.",
    )


def record_approved_news(
    *,
    title: str,
    url: str,
    publisher: str,
    excerpt: str | None,
    published_at: datetime | None,
    retrieved_at: datetime,
    approved_domains: set[str],
) -> EventEvidence:
    """Accept news only from domains approved by the deployment's data policy."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    domains = {domain.lower().rstrip(".") for domain in approved_domains}
    if (parts.scheme != "https" or parts.username or parts.password
            or not any(host == domain or host.endswith("." + domain) for domain in domains)):
        raise UnapprovedNewsSource("News URL is outside the approved HTTPS source list.")
    if retrieved_at.tzinfo is None or published_at is not None and published_at.tzinfo is None:
        raise ValueError("Evidence timestamps must include a timezone.")
    if published_at is not None and published_at > retrieved_at:
        raise ValueError("Publication cannot be later than retrieval.")
    if not title.strip() or not publisher.strip():
        raise ValueError("News title and publisher are required.")
    return EventEvidence(
        evidence_id=f"news:{url}", kind="approved_news", title=title.strip(),
        source_name=publisher.strip(), source_url=url,
        status="available" if excerpt else "missing", retrieval_status="retrieved",
        publication_status="known" if published_at else "unknown",
        published_at=published_at.isoformat() if published_at else None,
        retrieved_at=retrieved_at.isoformat(), excerpt=excerpt.strip() if excerpt else None,
        missing_reason=None if excerpt else "No source text was returned.",
    )


class FredClient:
    """Read FRED observations with an explicit real-time vintage for as-of queries."""

    def __init__(self, api_key: str, timeout_seconds: float = 12):
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive.")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def observation(self, series_id: str, as_of: date | None = None) -> EventEvidence:
        series = FRED_SERIES.get(series_id)
        if series is None:
            raise UnsupportedEvidenceSource(series_id)
        on = as_of or datetime.now(timezone.utc).date()
        base = dict(
            evidence_id=f"fred:{series_id}:{on.isoformat()}", kind="fred_observation",
            title=series.title, source_name=f"FRED / {series.original_source}",
            source_url=f"https://fred.stlouisfed.org/series/{series_id}",
            publication_status="unknown", unit=series.unit,
        )
        if not self._api_key:
            return EventEvidence(**base, status="unavailable", retrieval_status="not_attempted",
                                 missing_reason="FRED_API_KEY is not configured.")
        params = urlencode({
            "series_id": series_id, "api_key": self._api_key, "file_type": "json",
            "observation_end": on.isoformat(), "realtime_start": on.isoformat(),
            "realtime_end": on.isoformat(), "sort_order": "desc", "limit": 30,
        })
        request = Request(
            f"https://api.stlouisfed.org/fred/series/observations?{params}",
            headers={"Accept": "application/json", "User-Agent": "PortfolioLens/1.0"},
        )
        retrieved_at = datetime.now(timezone.utc).isoformat()
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return EventEvidence(**base, status="unavailable", retrieval_status="failed",
                                 retrieved_at=retrieved_at, missing_reason="FRED could not be retrieved.")
        rows = payload.get("observations") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return EventEvidence(**base, status="unavailable", retrieval_status="failed",
                                 retrieved_at=retrieved_at, missing_reason="FRED returned an invalid response.")
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                observed = date.fromisoformat(row["date"])
                value = float(row["value"])
            except (KeyError, TypeError, ValueError):
                continue  # FRED uses "." for missing observations.
            if observed > on or not math.isfinite(value):
                continue
            return EventEvidence(**base, status="available", retrieval_status="retrieved",
                                 observed_on=observed.isoformat(), vintage_on=on.isoformat(),
                                 retrieved_at=retrieved_at, value=value)
        return EventEvidence(**base, status="missing", retrieval_status="retrieved",
                             retrieved_at=retrieved_at,
                             missing_reason="No valid observation exists on or before the requested date.")
