## ADDED Requirements

### Requirement: Approved instrument history
The system SHALL classify supported US stocks, conventional equity and Treasury ETFs, and gold products and SHALL obtain adjusted historical prices with provenance, coverage, and explicit failure states.

#### Scenario: Provider failure
- **WHEN** real historical prices cannot be retrieved
- **THEN** the system reports unavailable data and does not substitute fictional fixtures

### Requirement: Event templates and evidence
The system SHALL expose versioned macro, sector, and issuer templates and preserve source, publication date, retrieval date, and missing-evidence status for FRED and approved current context.

#### Scenario: Missing source
- **WHEN** a source has no validated observation for the requested event
- **THEN** the evidence record remains explicitly missing and cannot be presented as a sourced fact
