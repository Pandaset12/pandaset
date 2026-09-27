# Local portfolio storage across worktrees

The backend now defaults to `~/.pandaset/portfolios.sqlite3` (the equivalent user-home path on Windows). That path is shared by your Git worktrees. `STORAGE_PATH` in the environment or ignored `backend/.env` overrides it. Portfolios remain scoped to the signed-in Supabase account.

Before starting the API, run a read-only preflight from the repository root:

```sh
backend/.venv/bin/python -m backend.storage_preflight
```

On Windows PowerShell, use `.\backend\.venv\Scripts\python.exe -m backend.storage_preflight`. The command prints the resolved path, whether it is the default or an override, and whether the file exists. The backend logs the same path when it starts. Neither command prints credentials or portfolio contents.

## Keep an existing portfolio database

An older checkout may have saved portfolios at `<that-checkout>/backend/data/portfoliolens.sqlite3`. **Stop every backend process using that file before moving it.** If several worktrees have a file, inspect and back up each one; this procedure does not merge them or choose one for you.

The simplest option is to keep using the existing file. Set an **absolute** path in the ignored `backend/.env` for every worktree that runs the API:

```dotenv
STORAGE_PATH=/absolute/path/to/previous-checkout/backend/data/portfoliolens.sqlite3
```

On Windows, use an absolute Windows path. Run the preflight again to confirm the override and file before launching the backend. Keep `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` aligned with the frontend's Supabase project; a different account or project has a different owner-scoped list even when the SQLite file is the same.

If you prefer the shared default, first back up the legacy file to a separate location. With the backend stopped and no `STORAGE_PATH` override, use the non-overwriting SQLite backup command:

```sh
backend/.venv/bin/python -m backend.storage_migrate /absolute/path/to/previous-checkout/backend/data/portfoliolens.sqlite3
```

Windows PowerShell: `.\backend\.venv\Scripts\python.exe -m backend.storage_migrate "C:\absolute\path\to\portfoliolens.sqlite3"`.

The command checks the copy's integrity and refuses to replace an existing destination. It leaves the source untouched. If the shared destination already exists, do not delete it to retry; choose the authoritative database and use an explicit `STORAGE_PATH`, or plan a separate owner-aware merge.

After either option, run preflight, start the API, sign in with the same account, and confirm the saved portfolio and its metrics load. To roll back, stop the API and restore the previous explicit `STORAGE_PATH`; there is no schema migration.

Production deployments must set `STORAGE_PATH` to a persistent disk path. A user-home default inside an ephemeral container does not preserve data across deployments.
