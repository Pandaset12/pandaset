# Twelve Data market data

Twelve Data is an optional source for adjusted daily closing prices. This is end-of-day history, not a live intraday quote feed. The default remains the fictional sample provider so the app runs without credentials.

## Local setup

1. Copy the environment template to backend/.env (or update your existing file); never commit an API key.
2. Create a key in your Twelve Data account.
3. Set:

~~~dotenv
MARKET_DATA_PROVIDER=twelvedata
TWELVE_DATA_API_KEY=your_server_side_key
MARKET_DATA_TIMEOUT_SECONDS=15
~~~

Restart the backend. To return to sample prices, set MARKET_DATA_PROVIDER=sample and restart. If Twelve Data is selected but unavailable, analysis returns an error; it does not fall back to fictional data.

## Request and data behavior

The backend batches requested symbols into one /time_series request with interval=1day, adjust=all, UTC session-date labels, and one initial price plus the requested return window. The adapter sorts observations chronologically, rejects missing symbols, invalid closes, and mismatched trading dates, and never fills gaps. A typical four-asset analysis consumes four API credits; batches reduce HTTP overhead, not per-symbol credit usage.

The free Basic plan is listed with 8 API credits per minute and 800 per day, and each requested symbol consumes a credit. Re-running analysis spends more credits; no cache is currently implemented. Keep the ticker count and repeated refreshes low during the demo. Check current quotas before the event: [Twelve Data pricing](https://twelvedata.com/pricing) and [batch request rules](https://support.twelvedata.com/en/articles/5203360-batch-api-requests).

Snapshots identify the source as twelve_data_adjusted_daily, mark the data mode as live (vendor data, not synthetic), and leave freshness unknown rather than guessing based on a calendar. Responses include a note that the feed is daily EOD. Prices and the as-of date are only as current as the vendor's latest completed session.

Before showing this market data to judges or other users, verify that the Twelve Data plan permits external/display use. The free plan description currently says internal non-display usage; do not assume that a public dashboard is covered. The provider key must stay on the backend and must never be sent to the frontend.

## Tests

backend/tests/test_twelve_data.py uses mocked responses. It checks request parameters and timeout, batch/single-symbol parsing, chronological order, invalid values, and alignment. The test suite does not contact Twelve Data and does not validate a real key or account quota.
