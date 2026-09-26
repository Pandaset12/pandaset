class ProviderUnavailable(Exception):
    """The requested market-data operation could not be completed."""


class MarketHistoryNotFound(Exception):
    """No history exists for one or more requested symbols."""


class SymbolLimitExceeded(Exception):
    """A request exceeds the supported number of distinct market symbols."""
