## ADDED Requirements

### Requirement: Overview analytics follow the selected user's portfolio
The system SHALL calculate Overview historical return, normalized performance, risk, and per-holding contributions from the selected user's saved symbols and exact allocation weights using the configured backend history provider. It SHALL NOT treat latest quotes as portfolio return or actual brokerage P&L.

#### Scenario: Alpaca-backed portfolio
- **WHEN** an authenticated user selects a saved portfolio and Alpaca history is configured
- **THEN** Overview displays an analysis for that portfolio's symbols and weights using Alpaca adjusted daily history with its own historical as-of date

#### Scenario: Portfolio allocation changes
- **WHEN** the user saves a changed holding or allocation
- **THEN** Overview displays a new analysis for the saved allocation and does not present the previous allocation's metrics as current

### Requirement: Historical and latest-price sources are distinguishable
The system SHALL label Overview's historical analysis according to its saved source and data mode, including the selected Alpaca feed in source details when available. It SHALL label latest IEX trades separately and SHALL NOT describe adjusted daily results as intraday or realized performance.

#### Scenario: Alpaca history and IEX quotes are both available
- **WHEN** Overview has a saved Alpaca analysis and an IEX snapshot response
- **THEN** the return, chart, and risk areas identify modeled adjusted daily history and its as-of session, while the separate price strip identifies latest Alpaca IEX trades and their timestamps

#### Scenario: Sample history remains selected
- **WHEN** the backend analysis uses fictional sample history
- **THEN** Overview visibly labels the historical metrics and chart as sample data even if optional Alpaca IEX quotes are available

### Requirement: Overview handles arbitrary supported holdings without invented metadata
The system SHALL derive quantitative allocation displays from the saved portfolio and analysis rather than a fixed ticker list. Unknown but supported tickers SHALL retain their entered symbol and SHALL NOT receive a fabricated price, sector classification, or sample-history claim.

#### Scenario: Holding outside the curated asset list
- **WHEN** a user adds a ticker supported by the selected history provider but absent from the local asset catalog
- **THEN** Overview shows its symbol, allocation, and backend-computed contributions with neutral identity metadata and no sample-only description

#### Scenario: Concentrated portfolio without the four prelisted technology tickers
- **WHEN** the selected portfolio contains other supported symbols
- **THEN** Overview's allocation summary reflects the saved holdings rather than counting only NVDA, MSFT, AAPL, and AMD

### Requirement: Optional content and benchmark do not imply unavailable data
The system SHALL render a VTI comparison only when the saved analysis contains aligned VTI history. Curated research notes SHALL remain identified as editorial material filtered by the user's holdings, not as Alpaca-supplied news.

#### Scenario: Portfolio has no VTI history
- **WHEN** the saved analysis contains a portfolio index but no VTI asset index
- **THEN** Overview shows the portfolio chart without a VTI comparison and makes no additional benchmark request

#### Scenario: Curated note matches a holding
- **WHEN** an editorial note mentions a symbol in the selected portfolio
- **THEN** Overview may show the note with an editorial label and shall not imply the note came from Alpaca market data

### Requirement: Vendor failures remain explicit
The system SHALL surface missing Alpaca configuration, entitlement, rate-limit, or historical-coverage failures without presenting fictional values as market-backed results. Vendor-backed release SHALL require a live history/feed check and confirmation of applicable display and retention rights.

#### Scenario: Alpaca history is unavailable for a user-entered ticker
- **WHEN** the selected provider cannot supply the required complete aligned history
- **THEN** Overview does not display a new analysis for that allocation and offers a clear recoverable error

#### Scenario: Deployment is not approved for vendor-backed use
- **WHEN** Alpaca credentials, feed access, or applicable data rights have not been verified
- **THEN** the deployment remains in visibly labeled sample mode or keeps the affected vendor-backed feature unavailable
