# Unified What-if release gates

This change keeps the existing SQLite portfolio store authoritative and moves event drafts and runs onto that portfolio identity. No production migration or destructive cleanup should run merely because the code is deployed.

## Before cutover

1. Confirm the deployment has exactly one writer for the SQLite portfolio database and that the database resides on a persistent volume shared with the API process. If the deployment has multiple API writers or ephemeral local disks, first move the owner-scoped portfolio repository to a shared transactional store; do not launch two editable copies.
2. Back up SQLite and MongoDB with a consistent timestamp. Verify that both backups can be restored in a test environment and record their encrypted storage location and access owner outside the repository.
3. Run `python -m backend.migrations.unified_inventory --sqlite PATH` with `MONGODB_URI` in the environment. Review import candidates, owner/ID conflicts, over-eight-holding portfolios, active drafts/runs, and missing analysis references. Resolve conflicts and missing input context before removal.
4. Run the event-portfolio import without `--apply`, compare counts, then run it with `--apply` against a restored copy. Repeat to confirm idempotence and owner isolation before production application.
5. Drain or explicitly cancel in-flight legacy drafts, backfill retained drafts/runs, and verify every completed run remains readable without its analysis record. The backfill reports incomplete adjusted-price coverage, invalid six-case results, unresolved references, and active jobs. It compares a completed result's fingerprint before and after each write and never rewrites the result.

## Analysis-backup retention

Retain an encrypted, recoverable copy of the legacy SQLite `analyses` table and MongoDB `analyses`/`analysis_counters` collections for **90 days after the verified cutover**. This is the proposed retention period for this release, subject to the data owner confirming it before production cleanup. No script in this change automatically deletes those backups. Record the cutover and scheduled deletion dates, then perform a separately reviewed purge after the period expires. If retention is not confirmed, keep the backups and leave the purge disabled.

## Rollback check

Keep the pre-cutover application/API version and both backups available during the migration window. Verify a restored copy can serve the old UI and analysis-ID reads. Do not rewrite or discard already saved event-run inputs during rollback. If the new path fails, disable its event entry point, restore the old API and stores together, and re-run the owner/count checks before reopening writes.

## Local rehearsal recorded for this change

`backend/tests/test_unified_release_rehearsal.py` exercises a representative owner-scoped SQLite/Mongo fixture. It verifies inventory and dry-run counts, imports a Mongo-only portfolio without replacing another owner's portfolio, backfills a ready draft and completed run, repeats both migrations without new writes, confirms the completed result is unchanged, and reads the saved draft/run after removing the test's legacy analysis record. It also checks that a running draft and an unresolved reference remain reported and that a pre-cutover SQLite copy restores the earlier portfolio state. This is a local test rehearsal; it does not establish the production store topology, backup recoverability, rights, or data-owner retention approval. Those checks remain required before production cutover.
