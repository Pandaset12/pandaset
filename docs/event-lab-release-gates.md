# Event-aware What-if Lab release gates

The feature is disabled by default. Internal checks may enable `EVENT_LAB_ENABLED` with credentials, but `EVENT_LAB_PUBLIC_ENABLED` must remain false until every gate below has a recorded owner, date, and evidence.

## Data rights and provenance

- Confirm the applicable Alpaca agreement permits public display of the selected IEX or SIP adjusted history, derived analytics, latest IEX snapshots, and the intended cache lifetime. Set Alpaca display and cache rights flags only after written approval.
- Confirm approved news domains permit retrieval, excerpting, storage, and public display of citations. Keep the allowlist explicit.
- Show source, adjusted-price basis, as-of date, and missing evidence for every run. Never replace a failed real-data request with demo fixtures.
- Confirm FRED API access and attribution requirements for the selected series.

## Security and operations

- Verify Supabase signing mode and JWT audience/issuer checks in the deployed project.
- Keep the internal user allowlist explicit while public enablement is off; an empty allowlist denies all users.
- Check all portfolio, analysis, draft, run, and message endpoints across two distinct user accounts, including guessed IDs and deletion.
- Configure Mongo backups and retention. Verify a cancelled/restarted job cannot expose or overwrite another owner's data.
- Load-test provider quotas, Gemini cost and latency, idempotent retries, per-user active-job limits, and backpressure.

## Model quality

- Document factor/issuer sensitivity estimation and minimum aligned adjusted-history coverage.
- Backtest one- and three-month conditional ranges on held-out windows. A quant owner must accept a dated calibration report before `EVENT_LAB_PROBABILITY_ENABLED` is set.
- If calibration or any holding coverage fails, suppress the entire portfolio probability result and show the specific reason. Deterministic cases may remain visible.
- Label all scenario outputs as hypothetical; conditional P(loss) describes outcomes given confirmed shocks, not the likelihood of the event itself.

## UI and staged release

- Review desktop/mobile layout, keyboard access, loading/error states, source links, and assumption confirmation with internal users.
- Invite a small user cohort only after data, security, and capacity checks pass.
- Record product approval before public enablement. Turning on the public flag alone does not establish the external rights or model validation above.
