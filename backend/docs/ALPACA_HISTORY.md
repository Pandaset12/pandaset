# Alpaca adjusted daily history

The standard workspace uses fictional sample prices by default. To use Alpaca
for portfolio analysis, market history, and allocation What-if, put these values
in the ignored `backend/.env` and restart the API:

```dotenv
MARKET_DATA_PROVIDER=alpaca
ALPACA_API_KEY=your_server_side_key
ALPACA_API_SECRET=your_server_side_secret
ALPACA_HISTORY_FEED=iex
```

Choose `iex` only if its coverage meets the approved holdings and factor-ETF
universe. Choose `sip` only when the account is entitled to consolidated history.
The API requests Alpaca stock bars with `timeframe=1Day` and `adjustment=all`,
follows every response page, excludes the current New York session, and requires
the requested symbols to have complete aligned dates. IEX is a single-exchange
feed; it may have gaps or different closes from SIP. There is no automatic feed
switch or fallback to fictional prices when Alpaca is selected.

The event lab also requires these credentials and an explicit history feed. It
saves holding and SPY/TLT/GLD histories in each analysis. Scenario runs use that
saved snapshot. Analyses and runs created before migration retain their original
Twelve Data provenance; create a new analysis to use Alpaca history.

`ALPACA_CACHE_RIGHTS_CONFIRMED=false` disables the short-lived v1 history
cache and prevents event-lab startup, because event analyses retain price
snapshots. Set it to `true` only after confirming the applicable retention
rights; it also permits the durable v2 cache. Public event-lab readiness additionally
requires `ALPACA_DISPLAY_RIGHTS_CONFIRMED=true` and
the other release gates. Verify the terms for any public v1 history display and
the existing latest-price strip as well. Keep credentials on the backend.

The Overview latest-price strip uses a separate Alpaca IEX snapshot endpoint;
those prices do not enter risk or What-if calculations. Analysis provenance
identifies `alpaca_adjusted_daily`, the selected feed, adjustment, latest session,
and retrieval time. Missing entitlement, rate limits, invalid responses, and
incomplete symbol coverage produce errors instead of silently changing sources.

Before enabling vendor-backed release, run
`PYTHONPATH=quant_engine/src backend/.venv/bin/python -m backend.check_alpaca_history`
with an opted-in account. It checks AAPL, MSFT, SPY, TLT, and GLD for 252
aligned return observations and prints metadata without prices or credentials.
Inspect quota behavior and record display/cache rights. Mocked tests do not
establish account entitlement. To roll back, set `MARKET_DATA_PROVIDER=sample` and disable
the event lab; saved analyses remain readable. Remove old Twelve Data secrets
and caches only after verifying saved records can still be read.

See Alpaca's [historical bars reference](https://docs.alpaca.markets/us/reference/stockbars)
for parameters and pagination, its [market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)
for feed differences, and the [release gates](../../docs/event-lab-release-gates.md).
