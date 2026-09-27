## ADDED Requirements

### Requirement: Explicit Alpaca history configuration
The system SHALL use Alpaca for vendor-backed daily history only when selected and SHALL require server-side Alpaca credentials and an explicit entitled history feed. The standard workspace SHALL continue to default to fictional sample history; the event lab SHALL require vendor-backed history.

#### Scenario: Standard workspace defaults to sample data
- **WHEN** no vendor history provider is selected
- **THEN** standard analysis and allocation What-if use labeled fictional sample prices

#### Scenario: Alpaca is selected without complete configuration
- **WHEN** Alpaca history is selected but credentials or the explicit history feed are missing
- **THEN** health reports the history provider as unready and calculation requests return a configuration error without using sample prices

### Requirement: Adjusted and complete daily price matrix
The system SHALL obtain Alpaca historical stock bars with one-day timeframe, all supported corporate-action adjustments, and the selected feed, and SHALL return the requested number of complete, date-aligned daily closes for every requested supported symbol.

#### Scenario: Paginated multi-symbol history
- **WHEN** the first Alpaca response contains only a subset of symbols or observations and supplies a next-page token
- **THEN** the provider follows pagination and verifies every requested symbol before returning a matrix

#### Scenario: Incomplete or inconsistent history
- **WHEN** a symbol lacks sufficient bars, a bar is invalid or duplicated, or symbol histories do not share the required session dates
- **THEN** the entire request fails with an explicit coverage or provider error and no fictional substitute

#### Scenario: Current trading session is incomplete
- **WHEN** historical data is requested during a New York trading session
- **THEN** the provider excludes that incomplete session from calculation history

### Requirement: Vendor provenance and feed separation
The system SHALL record the actual historical feed, adjustment mode, source, latest session date, retrieval time, and freshness in vendor-backed history and analysis outputs. The latest Alpaca IEX quote strip SHALL remain separate from historical calculations.

#### Scenario: Analysis uses Alpaca history
- **WHEN** a vendor-backed analysis or What-if comparison succeeds
- **THEN** its data-quality information identifies Alpaca adjusted daily history and the selected feed, while the quote strip remains labeled as latest IEX prices

### Requirement: Standard analytics use the selected history
The system SHALL use the selected price provider for v1 portfolio analysis, market-history responses, and allocation What-if comparisons over the union of current and proposed holdings.

#### Scenario: Standard What-if with an added holding
- **WHEN** a user compares a proposed allocation containing a supported symbol absent from the saved allocation
- **THEN** the backend obtains aligned history for the full symbol union and calculates both portfolios from that same history

### Requirement: Event scenarios use pinned Alpaca history
The event lab SHALL create new analysis snapshots from aligned adjusted Alpaca histories for holdings and factor proxies, and SHALL calculate later event runs from the immutable saved snapshot.

#### Scenario: New event analysis and run
- **WHEN** an eligible user creates an event analysis and later confirms a scenario
- **THEN** the run uses the saved Alpaca holding and factor histories without fetching live quotes or replacing the snapshot

#### Scenario: Existing Twelve Data analysis
- **WHEN** an existing saved analysis was created from Twelve Data before migration
- **THEN** it remains readable with its original source and completed runs remain unchanged; a new analysis is needed for an Alpaca-backed run

### Requirement: Errors and rights fail closed
The system SHALL distinguish missing entitlement or credentials, rate limits, malformed provider responses, and insufficient coverage. It SHALL NOT use fictional data after a selected vendor request fails, SHALL NOT cache Alpaca history without confirmed retention rights, and SHALL NOT enable public event-lab display without confirmed applicable display rights.

#### Scenario: Vendor or entitlement failure
- **WHEN** Alpaca rejects the feed or is unavailable during a vendor-backed calculation
- **THEN** the request returns a clear provider error and no new analysis is saved

#### Scenario: Cache or public display rights are unconfirmed
- **WHEN** Alpaca retention rights are unconfirmed or public display rights are unconfirmed
- **THEN** history caching is disabled or public event-lab display is blocked, respectively
