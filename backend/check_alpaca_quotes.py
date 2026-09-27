"""Opt-in, read-only smoke check. Run with python -m backend.check_alpaca_quotes."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from .alpaca_quotes import AlpacaQuotesUnavailable, fetch_alpaca_quotes
from .config import Settings
from .schemas import LiveQuotesResponse


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Alpaca IEX credentials without placing orders.")
    parser.add_argument("--env-file", type=Path, default=Path(__file__).parent / ".env")
    args = parser.parse_args()
    try:
        settings = Settings(_env_file=args.env_file)
        if not settings.has_alpaca_keys:
            print("Missing ALPACA_API_KEY or ALPACA_API_SECRET in the backend environment.")
            return 1
        result = LiveQuotesResponse.model_validate(fetch_alpaca_quotes(
            ["AAPL", "MSFT"],
            settings.alpaca_api_key.get_secret_value().strip(),
            settings.alpaca_api_secret.get_secret_value().strip(),
            min(settings.market_data_timeout_seconds, 10),
        ))
    except (AlpacaQuotesUnavailable, ValidationError, OSError):
        # Never print raw errors: configuration validation can include secret inputs.
        print("Quote check failed. Check credentials, IEX access, network, and account quota.")
        return 1
    print(json.dumps({
        "feed": result.feed,
        "quotes": [{
            "symbol": quote.symbol,
            "last_price": quote.last_price,
            "last_trade_at": quote.last_trade_at.isoformat() if quote.last_trade_at else None,
        } for quote in result.quotes],
    }, indent=2))
    if any(quote.last_price is None for quote in result.quotes):
        print("Response validated, but a requested symbol had no available IEX trade.")
        return 1
    print("Live vendor request passed. This does not verify app sign-in or display licensing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
