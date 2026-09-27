## ADDED Requirements

### Requirement: Verified owner identity
The API SHALL verify Supabase bearer tokens with the configured signing mode and SHALL derive the owner from the verified subject for every portfolio, analysis, scenario, and chat operation.

#### Scenario: Another user's ID
- **WHEN** a valid user requests another owner's opaque ID
- **THEN** the API denies access without disclosing its contents

### Requirement: Manual supported portfolio
The API SHALL allow an authenticated user to list, create, select, and update a portfolio of at most 25 supported holdings.

#### Scenario: Unsupported holding
- **WHEN** a user submits an unsupported symbol or more than 25 holdings
- **THEN** the API returns a precise validation error

### Requirement: Immutable run baseline
The API SHALL pin allocation, adjusted prices, dates, provider provenance, and model version for each scenario run.

#### Scenario: Prices refresh
- **WHEN** provider prices update after a run is saved
- **THEN** viewing that run returns its original baseline and results
