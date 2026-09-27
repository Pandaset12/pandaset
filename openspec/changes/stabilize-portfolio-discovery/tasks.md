## 1. Stable backend storage

- [x] 1.1 Resolve the default SQLite path in a user-level Pandaset data directory independent of the backend module or current worktree; preserve explicit `STORAGE_PATH` precedence.
- [x] 1.2 Add startup and preflight diagnostics for the resolved storage path and its override/default source, without returning the path in public API responses.
- [x] 1.3 Add backend tests proving two worktree launches share the default path, explicit overrides are honored, and portfolio reads remain owner-scoped.

## 2. Safe transition for existing portfolios

- [x] 2.1 Document how to identify and back up an existing worktree SQLite file, reuse it with an absolute `STORAGE_PATH`, or move it to the new default without overwriting a nonempty target.
- [x] 2.2 Update local and production startup guidance: local preflight path check, matching Supabase project, and explicit persistent `STORAGE_PATH` for deployment.

## 3. Truthful frontend discovery

- [x] 3.1 Pass authenticated user identity into portfolio discovery and persist only a per-user known-portfolio marker after a successful nonempty list or creation; clear it after intentional deletion of the last portfolio.
- [x] 3.2 Add a distinct unexpected-empty recovery state with account-scoped wording, Retry, and an explicit create option; keep Retry available on first-time empty and load-error states.
- [x] 3.3 Validate list response shape and guard list requests so an older response cannot overwrite a newer result or a newly created portfolio; keep metrics failures separate.
- [x] 3.4 Add frontend tests for first-time empty, previously known portfolio missing, malformed/error responses, retry recovery, different accounts, intentional last deletion, and out-of-order requests.

## 4. Verification

- [x] 4.1 Run backend tests, `npm test`, and `npm run build`; verify the local API sees the same owner-scoped portfolio from two worktrees using the chosen database path.
- [x] 4.2 Inspect the loading, recovery, first-time empty, and error screens at desktop and phone widths, including keyboard access to Retry and Create.
