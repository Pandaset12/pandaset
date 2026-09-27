## ADDED Requirements

### Requirement: Stable local portfolio storage
The local backend SHALL resolve its default SQLite portfolio database to the same user-level path regardless of which Git worktree launches it. An explicit `STORAGE_PATH` SHALL take precedence. The backend SHALL report the resolved location in local startup diagnostics without exposing it through public HTTP responses.

#### Scenario: Restart from another worktree
- **WHEN** the same developer starts the backend from two worktrees without an explicit `STORAGE_PATH`
- **THEN** both instances resolve the same absolute portfolio database path

#### Scenario: Explicit storage override
- **WHEN** `STORAGE_PATH` names an existing portfolio database
- **THEN** the backend uses that file without moving, copying, or replacing it

### Requirement: Existing local data is preserved
The change SHALL NOT automatically overwrite or combine existing worktree databases. Local setup documentation SHALL provide a non-destructive way to continue using an existing database and a way to verify the chosen path before serving requests.

#### Scenario: Existing database in a previous worktree
- **WHEN** a developer has saved portfolios in a previous worktree's SQLite file
- **THEN** they can configure the new backend launch to read that file without deleting or replacing records

#### Scenario: Destination already contains portfolios
- **WHEN** a developer follows the documented move procedure and the target database already contains portfolio records
- **THEN** the procedure does not overwrite that target

### Requirement: Owner-scoped portfolio discovery
The API SHALL continue to return only portfolios owned by the authenticated user. A successful empty list SHALL mean that the active store returned no portfolios for that user, not that every store or account has none.

#### Scenario: Portfolio exists for signed-in owner
- **WHEN** the same owner signs in after a backend restart using the same storage path
- **THEN** the portfolio list includes their saved portfolio

#### Scenario: Different authenticated owner
- **WHEN** another owner has no portfolios in the active store
- **THEN** their list is empty without revealing the first owner's records

### Requirement: Truthful and recoverable empty state
The frontend SHALL distinguish loading, request failure, confirmed first-time empty, and an unexpected empty response for a user previously known to have a portfolio. It SHALL never display stale portfolio holdings as authoritative after an empty response.

#### Scenario: First successful empty list
- **WHEN** the API returns an empty list for a signed-in user with no previous known portfolio
- **THEN** the frontend shows first-time onboarding with a way to retry discovery

#### Scenario: Previously known portfolio is absent
- **WHEN** the API returns an empty list for the same user after a previous successful nonempty list or creation
- **THEN** the frontend shows a recovery message identifying the signed-in account context, offers Retry, and allows explicit creation without claiming the portfolio was deleted

#### Scenario: Portfolio list request fails
- **WHEN** portfolio discovery fails or returns a malformed successful payload
- **THEN** the frontend shows a load-error state with Retry rather than a no-portfolio message

#### Scenario: Recovery after retry
- **WHEN** Retry returns a nonempty list
- **THEN** the frontend opens a saved portfolio and removes the recovery message

#### Scenario: Intentional deletion of last portfolio
- **WHEN** the user successfully deletes their last saved portfolio
- **THEN** the frontend shows first-time onboarding rather than the unexpected-empty recovery message

### Requirement: Latest discovery result wins
An older portfolio-list request SHALL NOT replace a newer list, selected portfolio, or newly created portfolio.

#### Scenario: Out-of-order list responses
- **WHEN** two discovery requests complete out of order
- **THEN** only the most recently started request changes portfolio discovery state

#### Scenario: Creation during list request
- **WHEN** a portfolio is created while an earlier list request remains in flight
- **THEN** that earlier response does not send the user back to the empty state
