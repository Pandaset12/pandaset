## ADDED Requirements

### Requirement: Main dashboard remains the workspace
The application SHALL render the existing main Overview, Risk & exposure, Research, and What-if pages with their current navigation and onboarding for every authenticated user. Event-lab availability SHALL change only access to event features within What-if; it SHALL NOT replace the application shell or hide other pages.

#### Scenario: Event access is enabled
- **WHEN** an authenticated user with event access opens the application
- **THEN** the main dashboard and its pages remain available and the event path is reachable from What-if

#### Scenario: Event dependency is unavailable
- **WHEN** the event service cannot be reached but the standard dashboard service is available
- **THEN** the main pages remain usable and the event path shows an actionable unavailable state

### Requirement: One owner-scoped selected portfolio
The application SHALL use one selected portfolio from the main owner-scoped portfolio repository for all dashboard pages and both What-if paths. An event request MUST verify the same owner and portfolio before creating or reading event data. The event path SHALL NOT require or offer a second portfolio-creation flow.

#### Scenario: Switching portfolios
- **WHEN** a user selects another owned portfolio
- **THEN** Overview, Risk, Research, quick What-if, and new event drafts use that portfolio's name and allocation

#### Scenario: Cross-owner request
- **WHEN** a user requests event data for a portfolio owned by another user
- **THEN** the request is denied without returning that portfolio or its event records

### Requirement: Existing event-only portfolios are reconciled
Before retiring the event portfolio collection, the migration SHALL import each valid event-only portfolio into the main owner-scoped repository idempotently, preserving its owner and identifier where possible. A conflicting identifier or allocation MUST be reported for explicit resolution and MUST NOT overwrite an existing main portfolio.

#### Scenario: Repeated migration
- **WHEN** migration is run again after an event-only portfolio was imported
- **THEN** no duplicate portfolio is created and the original owner and allocation remain intact

#### Scenario: Conflicting portfolio
- **WHEN** an event-only portfolio conflicts with an existing main portfolio
- **THEN** migration records the conflict and leaves both source records unchanged for resolution
