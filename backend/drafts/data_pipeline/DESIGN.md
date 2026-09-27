# Backend #1 design (incomplete draft)

Status: design target only. Only models.py, providers.py and the fictional price
fixture exist here. The storage, service and MongoDB files described below were
not implemented. These drafts are not connected to the running API.

## HLD

Market provider -> validated daily PriceBar records -> price store ->
aligned adjusted-price matrix for the quant teammate. MongoDB separately owns
users and holdings. Financial formulas and Gemini are separate responsibilities.

Default execution uses explicitly synthetic fixtures and a local SQLite cache.
The original vendor adapter was removed when the active API moved to Alpaca
history. Tiger Data/PostgreSQL and the draft MongoDB design here remain
unimplemented. No cloud service is contacted by this draft.

## LLD

- models.py: Decimal OHLC prices, UTC session-date labels, source/freshness
  metadata, validated deduplication and quant-input schemas.
- providers.py: fictional fixture reader only. The active Alpaca history
  provider is `backend/alpaca_history.py`.
- price_store.py: batch upserts on (symbol,time), range cache checkpoints and
  parameterized range queries. Repeating an ingestion never duplicates records.
- service.py: refresh only missing/expired ranges, validate a complete batch
  before storage, explicit stale-cache fallback, and strict date alignment.
- mongo_store.py: user/portfolio upserts and owner-scoped reads.
- __main__.py: reproducible demo and explicit database initialization commands.

Dates start/end are inclusive. time=00:00:00Z labels a trading-session date; it
does not claim the market closed at midnight. Raw OHLC is for valuation inputs;
adj_close is split/dividend-adjusted and is the only input supplied to risk
calculations. All instruments currently must use USD and US daily sessions.

Cache age and latest observed session are separate. After expiry/refresh, fetch
the whole requested window to update historical adjustments after corporate
actions. Do not silently mix vendors or fixture/live data in one quant input.

Quant input preparation does not fill missing values or drop dates silently.
All requested symbols must have identical observed dates; minimum return count
requires one extra price row. Cross-symbol alignment cannot detect a date absent
from every symbol: an exchange calendar/expected session list can be supplied
for that check. Without it, report that completeness is unverified.

Tests cover malformed OHLC, duplicate conflicts, alignment, missing history,
raw/adjusted separation, cache hits, stale fallback and idempotent ingestion.
Database adapter tests use fakes unless live database URLs are supplied; they do
not establish that a team's credentials or cloud deployment work.
