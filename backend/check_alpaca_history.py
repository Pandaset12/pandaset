"""Opt-in read-only check for the configured Alpaca historical feed."""

from .alpaca_history import AlpacaHistoryProvider, CoverageError, RateLimitError
from .config import Settings
from .market_data_errors import ProviderUnavailable


SYMBOLS = ["AAPL", "MSFT", "SPY", "TLT", "GLD"]


def main() -> int:
    settings = Settings()
    if not settings.has_alpaca_history:
        print("Configure ALPACA_API_KEY, ALPACA_API_SECRET, and ALPACA_HISTORY_FEED in backend/.env.")
        return 2
    provider = AlpacaHistoryProvider(
        settings.alpaca_api_key.get_secret_value(),
        settings.alpaca_api_secret.get_secret_value(),
        settings.alpaca_history_feed,
        timeout_seconds=settings.market_data_timeout_seconds,
    )
    try:
        frame = provider.prices(SYMBOLS, 252)
    except (CoverageError, RateLimitError, ProviderUnavailable, ValueError) as exc:
        print(f"Alpaca history check failed: {type(exc).__name__}: {exc}")
        return 1
    provenance = frame.attrs["provenance"]
    print(f"Alpaca history check passed: feed={provenance['feed']}, "
          f"adjustment={provenance['adjustment']}, "
          f"latest_session={provenance['session_date']}, "
          f"return_observations={len(frame) - 1}, symbols={','.join(SYMBOLS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
