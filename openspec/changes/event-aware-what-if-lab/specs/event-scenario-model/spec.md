## ADDED Requirements

### Requirement: Confirmed shock cases
The system SHALL validate factor names, units, bounds, evidence, and user confirmation before computing mild, central, and severe cases at one and three months with the same shocks for current and proposed allocations.

#### Scenario: Unconfirmed AI proposal
- **WHEN** an agent proposes shocks without user confirmation
- **THEN** the system saves a draft but does not create a computed run

### Requirement: Deterministic calculations
The quant engine SHALL produce holding contributions, data coverage, assumptions, and model version from a pinned snapshot; Gemini SHALL NOT supply final portfolio figures.

#### Scenario: Repeated run
- **WHEN** the same snapshot, confirmed shocks, and model version are recalculated
- **THEN** the deterministic case values match

### Requirement: Conditional outcomes
For a validated central case, the system SHALL return seeded 10th, 50th, and 90th percentile returns and probability of loss at one and three months only when every holding has adequate validated history and calibration is approved.

#### Scenario: Incomplete holding history
- **WHEN** one holding lacks sufficient aligned adjusted-price history
- **THEN** the whole-portfolio probability result is unavailable with a specific reason

#### Scenario: Interpretation
- **WHEN** conditional ranges are displayed
- **THEN** they are labeled as outcomes given the confirmed shocks rather than odds that the event occurs
