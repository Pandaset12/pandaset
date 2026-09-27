## Context

`Settings.storage_path` currently defaults to `backend/data/portfoliolens.sqlite3` beside the imported backend module. Each Git worktree therefore has its own default database. The API lists portfolios for the authenticated owner from that database, while `Application.loadPortfolios` shows first-time onboarding whenever a successful response is `[]`. The existing loading, API-error, and metrics-error screens are separate. A local browser can keep the same URL and Supabase session while a restarted API silently points at another worktree's database.

## Goals / Non-Goals

**Goals:**
- Use a single durable local portfolio store across worktrees unless `STORAGE_PATH` explicitly selects another file.
- Make an unexpected empty list recoverable and accurately describe which signed-in account was checked.
- Preserve owner scoping, existing portfolio records, and the distinct loading, list-error, and metrics-error states.
- Make the active storage location visible to developers without sending paths, credentials, or holdings to the browser.

**Non-Goals:**
- Move portfolios into Supabase, merge different users' portfolios, or change the API's portfolio schema.
- Automatically copy or combine SQLite databases from multiple worktrees.
- Treat a failed metrics calculation as an empty portfolio list.

## Decisions

### Stable development storage default

Resolve the default local SQLite file under a user-level Pandaset data directory outside the repository and all worktrees (for example `~/.pandaset/portfolios.sqlite3`). `STORAGE_PATH` remains the highest-priority explicit override, including for production's persistent disk and isolated tests. Log the resolved path and whether it came from an override at backend startup; do not expose the path in public HTTP responses. A documented preflight command will show the same resolution before launching the API.

This is preferable to a repository-relative default because worktrees are disposable. Requiring every developer to hand-edit a per-worktree `.env` would leave the current failure mode intact whenever that step is missed. The default-path change needs a deliberate migration step for existing local files.

### No silent data migration

Document a one-time, opt-in procedure to locate an existing SQLite database and set `STORAGE_PATH` to its absolute path, or back it up and copy it to the new default while the backend is stopped. Refuse to overwrite a nonempty target; do not merge rows automatically. This keeps the current user's portfolios accessible without guessing which of several worktree databases is authoritative.

### Recovery state for a surprising empty response

Track only a per-user, non-sensitive `hasSeenPortfolio` marker in browser storage after a successful nonempty portfolio list or creation. No portfolio names, holdings, access tokens, or metric values are cached. A successful empty list for a user with no marker opens first-time onboarding. A successful empty list for a user with the marker opens a distinct recovery screen: explain that no saved portfolios were returned for this signed-in account, offer Retry, and allow an explicit choice to create a new portfolio. Clear the marker when the user intentionally deletes their last portfolio. If browser storage is unavailable, continue with the regular empty state and a visible Retry path.

This marker is a signal for more careful messaging, not proof that a particular portfolio still exists. It must never bypass the owner-scoped API response or show stale portfolio data. Key it to the authenticated user ID and reset UI state on account changes.

### Guard asynchronous discovery

Give each portfolio-list attempt a monotonically increasing request generation. Only the latest attempt may replace the list and its state; an older response must not erase a portfolio just created or selected in the meantime. Reject malformed successful responses as a load error rather than treating them as empty. Keep metrics retrieval separate from portfolio discovery.

## Risks / Trade-offs

- **Changed default path can initially look empty** → Document the legacy path and provide a preflight warning plus explicit, non-destructive migration steps before switching existing local setups.
- **A marker can outlive a portfolio deleted elsewhere** → The recovery screen permits retry and an explicit path to create; it never claims the portfolio still exists.
- **Browser storage may be unavailable** → Fall back safely without caching portfolio data; keep Retry accessible.
- **Production storage may still be ephemeral if misconfigured** → Preserve and document the explicit persistent `STORAGE_PATH` requirement; do not rely on the developer default for deployment.

## Migration Plan

1. Before changing local startup, identify which existing worktree database contains the desired owner-scoped portfolios and back it up.
2. Configure `STORAGE_PATH` to that absolute file or copy the backup into the new user-level default while the API is stopped. Never overwrite a nonempty destination.
3. Start the API, check the logged resolved path, sign in with the same Supabase account, and verify the portfolio list and metrics.
4. Roll back by restoring the prior explicit `STORAGE_PATH`; no schema migration or deletion is required.

## Open Questions

None required for implementation. The exact user-level directory name is an implementation detail; it must be stable across worktrees and documented for macOS, Linux, and Windows.
