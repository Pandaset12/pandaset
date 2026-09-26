"""Curated Research sources eligible for URL Context summaries."""

RESEARCH_SOURCES: dict[str, dict[str, dict[str, str]]] = {
    "NVDA": {"issuer": {"label": "NVIDIA investor information", "url": "https://investor.nvidia.com/financial-info/financial-reports-and-sec-filings/default.aspx"}},
    "MSFT": {"issuer": {"label": "Microsoft investor information", "url": "https://www.microsoft.com/en-us/Investor/earnings/FY-2025-Q4/press-release-webcast"}},
    "AAPL": {"issuer": {"label": "Apple SEC filings", "url": "https://investor.apple.com/sec-filings/default.aspx"}},
    "JPM": {"issuer": {"label": "JPMorgan Chase annual reports", "url": "https://www.jpmorganchase.com/ir/annual-report"}},
    "VTI": {"issuer": {"label": "Vanguard ETF profile", "url": "https://investor.vanguard.com/investment-products/etfs/profile/vti"}},
    "TLT": {"issuer": {"label": "iShares ETF profile", "url": "https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf"}},
    "AMD": {"issuer": {"label": "AMD SEC filings", "url": "https://ir.amd.com/financial-information/sec-filings"}},
    "GLD": {"issuer": {"label": "SPDR Gold Shares information", "url": "https://www.spdrgoldshares.com/usa/"}},
}


def curated_research_source(symbol: str, source_id: str) -> dict[str, str] | None:
    return RESEARCH_SOURCES.get(symbol.upper(), {}).get(source_id)
