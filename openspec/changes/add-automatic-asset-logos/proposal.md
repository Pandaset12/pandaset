## Why

Portfolio holdings currently show ticker initials or simplified marks, even when a recognizable company logo exists. Users can add new tickers, so maintaining image files or a ticker-to-domain list by hand would leave gaps and create ongoing maintenance.

## What Changes

- Resolve holding logos automatically from ticker symbols through a logo provider, without adding per-company files or mappings.
- Show the same asset mark across onboarding, portfolio, risk, research, and scenario views.
- Retain a readable ticker mark when a logo is missing, fails to load, or the provider is not configured.
- Configure the provider through a publishable client token and meet its applicable display terms.

## Capabilities

### New Capabilities

- `automatic-asset-logos`: Automatically display stock and fund logos for supported and user-added tickers, with a reliable fallback.

### Modified Capabilities

None.

## Impact

- Frontend asset-mark presentation, onboarding holding rows, styling, and configuration.
- An external logo image service receives requested ticker symbols. This change does not alter market data, portfolio calculations, or backend credentials.
