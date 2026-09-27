## 1. Logo lookup and shared mark

- [ ] 1.1 Add a validated ticker-logo URL helper using the configured Logo.dev publishable key and `fallback=404`; document the `VITE_LOGO_DEV_PUBLISHABLE_KEY` setting in `.env.example`.
- [ ] 1.2 Update `AssetMark` to render a contained logo with a local ticker fallback during loading, on image error, and when the key is absent; reset image state when its ticker changes.
- [ ] 1.3 Update mark styles for regular and small sizes without shifting adjacent ticker/name text.

## 2. Complete interface coverage and attribution

- [ ] 2.1 Use the shared mark in onboarding search results, selected holding rows, and selected-holding summaries; confirm existing overview, risk, research, and scenario uses work in both application modes.
- [ ] 2.2 Add visible provider attribution wherever configured logos are displayed, including onboarding and both portfolio modes, and document the provider plan/origin check for deployment.

## 3. Verification

- [ ] 3.1 Add focused tests for URL normalization, no-key behavior, loading/error fallback, and recovery when the displayed ticker changes.
- [ ] 3.2 Run `npm test` and `npm run build`; inspect representative stock, ETF, unknown-symbol, and failed-image cases at desktop and mobile widths in onboarding and a portfolio route.
- [ ] 3.3 Confirm no manual logo files or ticker-to-domain mappings were added and no secret provider or Alpaca key reaches browser requests.
