# PandaSet

A responsive investment research interface built with React, TypeScript, and Vite. Four connected workspaces share a portfolio model and a forest-green visual system:

- **Overview** — portfolio performance, period controls, holdings, return attribution, and relevant research connections.
- **Risk & exposure** — capital versus risk contributions, an interactive correlation matrix, and allocation breakdowns.
- **Research** — eight searchable assets, comparisons, company context, and links to official sources.
- **What-if lab** — editable allocations, validation, presets, recalculated comparisons, and applying a scenario to the sample portfolio.

The contextual analyst provides curated explanations grounded in the current calculations. It is clearly labeled as a guided demo.

## Run locally

Requires Node.js 22.12 or newer.

```sh
npm install
npm run dev
```

Use the local address printed by Vite. If the default port is occupied, Vite chooses the next available port.

```sh
npm test         # Financial invariants and scenario validation
npm run build   # TypeScript check and optimized static build
npm run preview # Serve the production build
```

All navigation uses hash routes, so `frontend/dist/` can be served by a static host without route rewrites. This project has no Sites dependency or hosting configuration.

## Data and integration boundaries

This is a complete frontend implementation using **illustrative data**. It is not connected to market data, brokerage accounts, a news feed, or Gemini. Research links point to external issuer and public-disclosure sources; their contents are not ingested. The UI discloses these boundaries in the sample-data badge, methodology dialog, research labels, and analyst.

`quant/data.ts` defines assets, initial allocations, research primers, and a deterministic 252-day sample. It generates correlated daily observations calibrated to the disclosed sample annual returns. The portfolio uses constant daily weights, excluding fees, taxes, deposits, and withdrawals. Editing a portfolio updates application state for the current session; reloading restores the sample.

`quant/analytics.ts` contains the portfolio calculations. Return contributions are geometrically linked to reconcile to the total compounded return. Risk contributions use the sample covariance matrix and sum to one, including possible negative contributions. Volatility is annualized using 252 trading days. Drawdown is computed from the modeled portfolio path.

To integrate a backend, replace the fixture data adapter while keeping aligned return arrays and the asset ordering contract. Replace the analyst response function with the desired service and preserve visible loading, error, and source-attribution states. Do not put API keys in the browser bundle.

## Structure

- `frontend/` — Vite application and public assets.
- `quant/` — illustrative data, portfolio calculations, and tests.
- `backend/` — reserved for a future service; no backend is implemented yet.
- `frontend/src/App.tsx` — navigation, portfolio state, editing, and methodology.
- `frontend/src/pages/` — four workflow-specific pages.
- `frontend/src/components/` — shared UI, responsive chart, and contextual analyst.
- `frontend/src/styles.css` — stylesheet entry point; feature styles live in `frontend/src/styles/`.
- `quant/tests/analytics.test.ts` — seven financial consistency checks.
- `docs/design-system.md` — visual direction and component conventions.
- `docs/verification.md` — verification evidence and limitations.

Fonts are self-hosted. Their licenses are included in `frontend/public/fonts/`.
