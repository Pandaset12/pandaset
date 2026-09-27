## Why

A saved portfolio can appear to disappear when the local API is restarted from another Git worktree: its default SQLite path is inside that worktree, so the same signed-in account may receive a different portfolio list. The first-time onboarding screen then treats any successful empty list as proof that no portfolio exists, without explaining the account or data source it checked.

## What Changes

- Give local development one explicit, stable portfolio database path across worktrees, with a documented way to point it at an existing database without overwriting data.
- Make backend startup expose and verify which storage configuration is active, without exposing portfolio contents or credentials.
- Make portfolio discovery distinguish a confirmed empty list for the current account from a request failure, loading state, and a previously known portfolio that is temporarily absent. Provide a retry path before presenting first-time creation in the latter case.
- Add focused tests for worktree restarts, owner-scoped empty results, transient list responses, and recovery.

## Capabilities

### New Capabilities

- `portfolio-discovery-reliability`: Stable local portfolio storage and truthful, recoverable discovery states for signed-in users.

### Modified Capabilities

None; there are no existing main OpenSpec capability specs for this behavior.

## Impact

Backend storage configuration and development startup documentation; the portfolio-list API's observable state handling in `frontend/src/App.tsx` and onboarding; frontend and backend tests. Existing portfolio records remain owner-scoped and are not migrated or deleted automatically. Production must continue using an explicitly configured persistent `STORAGE_PATH`.
