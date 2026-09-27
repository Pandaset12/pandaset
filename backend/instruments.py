"""Small, explicit universe supported by the event-aware portfolio workflow.

The list is a product allowlist, not a claim that a vendor currently covers every
symbol. Historical coverage is checked separately when prices are requested.
"""

from dataclasses import dataclass
from typing import Literal


InstrumentKind = Literal["us_stock", "equity_etf", "treasury_etf", "gold_etp"]


class UnsupportedInstrument(ValueError):
    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"{symbol} is outside the supported US instrument universe.")


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    kind: InstrumentKind
    sector: str


_STOCKS = (
    ("NVDA", "NVIDIA", "Technology"),
    ("MSFT", "Microsoft", "Technology"),
    ("AAPL", "Apple", "Technology"),
    ("AMZN", "Amazon", "Consumer discretionary"),
    ("NFLX", "Netflix", "Communication services"),
    ("GOOGL", "Alphabet Class A", "Communication services"),
    ("META", "Meta Platforms", "Communication services"),
    ("TSLA", "Tesla", "Consumer discretionary"),
    ("AMD", "Advanced Micro Devices", "Technology"),
    ("AVGO", "Broadcom", "Technology"),
    ("ORCL", "Oracle", "Technology"),
    ("CRM", "Salesforce", "Technology"),
    ("JPM", "JPMorgan Chase", "Financials"),
    ("BAC", "Bank of America", "Financials"),
    ("GS", "Goldman Sachs", "Financials"),
    ("V", "Visa", "Financials"),
    ("MA", "Mastercard", "Financials"),
    ("UNH", "UnitedHealth Group", "Health care"),
    ("JNJ", "Johnson & Johnson", "Health care"),
    ("LLY", "Eli Lilly", "Health care"),
    ("XOM", "Exxon Mobil", "Energy"),
    ("CVX", "Chevron", "Energy"),
    ("PG", "Procter & Gamble", "Consumer staples"),
    ("COST", "Costco", "Consumer staples"),
    ("WMT", "Walmart", "Consumer staples"),
    ("KO", "Coca-Cola", "Consumer staples"),
)

_EQUITY_ETFS = (
    ("VTI", "Vanguard Total Stock Market ETF", "Broad US equity"),
    ("SPY", "SPDR S&P 500 ETF Trust", "Large-cap US equity"),
    ("IVV", "iShares Core S&P 500 ETF", "Large-cap US equity"),
    ("VOO", "Vanguard S&P 500 ETF", "Large-cap US equity"),
    ("QQQ", "Invesco QQQ Trust", "Nasdaq-100 equity"),
    ("IWM", "iShares Russell 2000 ETF", "Small-cap US equity"),
    ("VEA", "Vanguard FTSE Developed Markets ETF", "Developed-market equity"),
    ("VWO", "Vanguard FTSE Emerging Markets ETF", "Emerging-market equity"),
    ("XLK", "Technology Select Sector SPDR Fund", "Technology"),
    ("XLF", "Financial Select Sector SPDR Fund", "Financials"),
    ("XLE", "Energy Select Sector SPDR Fund", "Energy"),
    ("XLV", "Health Care Select Sector SPDR Fund", "Health care"),
    ("XLI", "Industrial Select Sector SPDR Fund", "Industrials"),
    ("XLY", "Consumer Discretionary Select Sector SPDR Fund", "Consumer discretionary"),
    ("XLP", "Consumer Staples Select Sector SPDR Fund", "Consumer staples"),
    ("XLU", "Utilities Select Sector SPDR Fund", "Utilities"),
)

_TREASURY_ETFS = (
    ("TLT", "iShares 20+ Year Treasury Bond ETF", "Long-term Treasury"),
    ("IEF", "iShares 7-10 Year Treasury Bond ETF", "Intermediate Treasury"),
    ("SHY", "iShares 1-3 Year Treasury Bond ETF", "Short-term Treasury"),
    ("SGOV", "iShares 0-3 Month US Treasury Bond ETF", "Treasury bills"),
    ("BIL", "SPDR Bloomberg 1-3 Month T-Bill ETF", "Treasury bills"),
)

_GOLD_ETPS = (
    ("GLD", "SPDR Gold Shares", "Physical gold"),
    ("IAU", "iShares Gold Trust", "Physical gold"),
)

SUPPORTED_INSTRUMENTS: dict[str, Instrument] = {
    item.symbol: item
    for item in (
        *(Instrument(symbol, name, "us_stock", sector) for symbol, name, sector in _STOCKS),
        *(Instrument(symbol, name, "equity_etf", sector) for symbol, name, sector in _EQUITY_ETFS),
        *(Instrument(symbol, name, "treasury_etf", sector) for symbol, name, sector in _TREASURY_ETFS),
        *(Instrument(symbol, name, "gold_etp", sector) for symbol, name, sector in _GOLD_ETPS),
    )
}


def resolve_instrument(symbol: str) -> Instrument:
    normalized = symbol.strip().upper()
    try:
        return SUPPORTED_INSTRUMENTS[normalized]
    except KeyError as exc:
        raise UnsupportedInstrument(normalized or symbol) from exc


def search_instruments(query: str, limit: int = 8) -> list[Instrument]:
    term = query.strip().casefold()
    if not term or not 1 <= limit <= 25:
        return []
    matches = [item for item in SUPPORTED_INSTRUMENTS.values()
               if term in item.symbol.casefold() or term in item.name.casefold()]
    matches.sort(key=lambda item: (not item.symbol.casefold().startswith(term), item.symbol))
    return matches[:limit]
