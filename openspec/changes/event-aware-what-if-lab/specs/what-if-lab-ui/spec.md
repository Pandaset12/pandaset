## ADDED Requirements

### Requirement: Event workflow
The What-if Lab SHALL let an authenticated user choose a saved portfolio and curated event, discuss context, inspect sourced facts and proposed numbers, confirm assumptions, and view separated calculated results.

#### Scenario: Proposed assumptions
- **WHEN** a draft is ready
- **THEN** every proposed shock and its units are visible before the user confirms

### Requirement: Honest labels and states
The interface SHALL distinguish sourced facts, confirmed assumptions, calculated cases, and conditional ranges, preserve explicit allocation-apply action, and show loading, empty, and error states at desktop and mobile sizes.

#### Scenario: Probability unavailable
- **WHEN** the quant engine withholds conditional ranges
- **THEN** the interface explains why while still showing valid deterministic cases
