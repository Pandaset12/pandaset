## ADDED Requirements

### Requirement: Bounded roles
A shared Gemini gateway SHALL run a bounded event researcher and scenario designer, retain grounding citation statuses, and reject unsupported shocks or out-of-bounds outputs.

#### Scenario: Agent exceeds bounds
- **WHEN** an agent proposes an unsupported factor or invalid unit
- **THEN** the proposal is rejected before confirmation

### Requirement: Durable scenario lifecycle
Authenticated APIs SHALL support templates, instrument search, idempotent draft creation, progress, confirmation and run creation, run messages, cancellation, and deletion with bounded retries and per-user limits.

#### Scenario: Duplicate request
- **WHEN** a user repeats a draft request with the same idempotency key
- **THEN** the API returns the same draft rather than creating another job

### Requirement: Run-specific chat
The system SHALL save messages with their owner's scenario run until deletion and SHALL answer using stored calculations and cited evidence.

#### Scenario: Requested revision
- **WHEN** a chat message requests changed weights or assumptions
- **THEN** the system creates a new draft requiring confirmation and recalculation
