## Context

`AssetMark` currently renders letters or hand-drawn marks from a symbol. Both the standard and event-aware applications use it for saved holdings, while onboarding has separate ticker initials. The standard workflow accepts user-entered US stock symbols, and the event-aware workflow has a fixed US stock and fund universe. Neither asset model carries a logo URL.

The provider must resolve symbols without a maintained ticker-to-domain table. Logo.dev's image endpoint accepts US ticker symbols directly and documents coverage for many ETFs. Its publishable token can be used in an image URL; an unrecognized ticker can return HTTP 404 when `fallback=404` is set. Alpaca's logo endpoint was considered because the backend already uses Alpaca, but logo access is separately authenticated, covers select symbols, and may require an additional product entitlement.

## Goals / Non-Goals

**Goals:**

- Show recognizable logos automatically wherever the interface displays an asset mark, including ticker selection and onboarding.
- Cover newly added symbols without new image files or manual ticker mappings.
- Keep the ticker and company/fund name legible when a logo is unavailable.
- Preserve existing portfolio and market-data behavior.

**Non-Goals:**

- Guarantee that every stock or ETF has a logo in the provider's catalog.
- Build a logo scraper, upload flow, or local catalog of company marks.
- Replace asset names, tickers, or sample-data disclosures with logos.

## Decisions

### Use a ticker-based image provider in the frontend

Create a small shared URL helper for `https://img.logo.dev/ticker/{symbol}` with a `VITE_LOGO_DEV_PUBLISHABLE_KEY`, a suitable small image size, and `fallback=404`. Only normalized, valid ticker symbols enter the URL. This is a publishable client key, not a secret. Keep the existing Alpaca keys on the backend. Direct image requests avoid a new backend endpoint and per-symbol metadata lookup. Document the key and origin restrictions in `.env.example` and setup notes.

Alternative: proxy Alpaca logos through the backend. That protects its credentials but adds an endpoint and depends on separate logo entitlement and select-symbol coverage. Alternative: bundle logos; this does not meet automatic coverage for new holdings.

### Centralize rendering and fallback

Extend `AssetMark` to accept a ticker and optional display color, so existing asset objects and onboarding search results can use it without changing their data models. Render an image inside the existing mark container. Keep its current symbol mark as the fallback while the image loads and when the token is absent or the image emits an error. On symbol change, reset image state so a previous failure cannot hide the next logo. Use `object-fit: contain` and the existing small/regular dimensions. The image is decorative because adjacent text identifies the holding; retain the accessible ticker/name text.

Replace onboarding's independent initial mark with the shared component and use the same component in ticker search and selected-holding summaries where a mark is shown. This keeps standard and event-aware views consistent without changing the portfolio data model.

Alternative: let the provider return its generated monogram on missing logos. This hides a catalog miss and looks inconsistent with the app's fallback, so request 404 instead.

### Handle provider terms in the interface

Include a visible Logo.dev attribution link on screens that display provider logos, including onboarding, so the free commercial-use requirement is met. Verify the applicable provider plan and terms before release; a paid plan can retain the link harmlessly. Avoid copying provider images into the repository.

## Risks / Trade-offs

- [Provider has no logo or returns an incorrect one] → Keep the ticker/name visible; use the fallback for missing images and document a process for reporting incorrect matches.
- [Third-party image requests expose requested tickers and depend on network access] → Request only ticker symbols, never portfolio weights or user identifiers; render fallback on failure.
- [Missing key, quota limit, or provider outage] → Render local ticker marks without blocking any portfolio workflow.
- [Logo contrast or shape varies] → Use contained images at fixed dimensions and inspect representative light/dark, stock, and ETF cases.
- [Provider terms or pricing change] → Keep provider URL construction isolated so the source can be replaced without changing page components.

## Migration Plan

Add the publishable token to frontend deployment configuration and include attribution. Deploy the UI with fallback enabled, so missing configuration does not interrupt portfolio use. Rollback consists of removing the token or reverting the mark component; no saved data migration is required.

## Open Questions

Before release, verify the project's Logo.dev plan, allowed production origins, and attribution terms against the deployment's intended use. Logo coverage should be spot-checked for the supported stock and ETF symbols; misses remain valid fallback cases rather than a release blocker.
