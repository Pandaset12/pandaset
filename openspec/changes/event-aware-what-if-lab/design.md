## Context

The React app has Supabase sign-in and standalone onboarding, but the API still trusts opaque IDs, stores local SQLite records, and starts from fixed sample holdings. Twelve Data integration exists only on a conflicting branch. Current AI workflow explains completed calculations; it does not research events, confirm shocks, or persist scenario chat.

## Goals / Non-Goals

**Goals:** Owner-scoped real portfolios; reproducible immutable snapshots; sourced event research; user-confirmed shocks; deterministic one- and three-month results; gated conditional distributions; saved run chat; useful failure states.

**Non-Goals:** Brokerage connectivity, live trading, event-occurrence probabilities, causal attribution, AI-generated portfolio math, or public activation before data rights and calibration approval.

## Decisions

1. Keep Supabase as identity provider and MongoDB as application store. Verify every bearer JWT server-side against the project's configured signing mode, derive owner ID from verified subject, and scope every read/write by owner. Alternative of trusting client IDs is unsafe.
2. Use immutable allocation and adjusted-price snapshots for runs. New prices create a new analysis; existing runs remain reproducible. Alternative of reading latest prices on each result view would alter a saved baseline.
3. Reconcile Twelve Data provider changes manually. Support a bounded approved universe and explicit unsupported/coverage states. Cache only within licensed terms and quota budgets; no demo fallback on provider failures.
4. Version curated templates; preserve every evidence source URL, publication/retrieval time, and availability status. Gemini researcher/designer have bounded input/output schemas. Client review and confirmation are required before the quant engine runs.
5. The quant engine owns all portfolio returns, contributions, and conditional distributions. It estimates sensitivities from aligned adjusted history. The central-case path generator uses a fixed seed and historical residuals. Missing history for any holding removes whole-portfolio probabilities.
6. Persist asynchronous draft/run jobs with owner, status, idempotency key, retries, and cancellation. Store run chat beside immutable run results; requests that change assumptions create a new draft.
7. Gate public feature availability and probability output separately. Public release requires display/cache rights, security isolation, approved source use, capacity, and calibration approval.

## Risks / Trade-offs

- [Vendor rights and quotas] → Feature flag and explicit provider errors until contracts/capacity are confirmed.
- [Supabase signing-mode mismatch] → Select JWKS or Auth-server verification from configuration and reject unverified tokens.
- [Thin adjusted history] → Show deterministic cases with coverage disclosure; suppress whole-portfolio conditional ranges.
- [Unreliable grounding] → Preserve missing-evidence states; reject unsupported or uncited proposed shocks.
- [Long-running work] → Durable job records, bounded retries, idempotency, and cancellation.

## Migration Plan

Deploy storage and auth behind flags; migrate existing demo data only as explicitly labeled fixtures; add authenticated portfolio and event APIs; activate invited users after ownership and data checks; activate probabilities after documented held-out calibration; enable public access only after commercial rights and operations gates. Roll back by disabling feature flags while retaining stored user data.

## Open Questions

Exact Twelve Data license for public display/caching and approved news-domain list are deployment decisions; absence must fail closed.
