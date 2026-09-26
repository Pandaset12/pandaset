# PandaSet

**A clearer view of what you own.** PandaSet is an interactive portfolio research demo built with React, TypeScript, and Vite. Explore performance, risk, company research, and allocation scenarios through one shared sample portfolio.

## Explore the app

| Workspace           | What you can do                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| **Overview**        | Review sample performance and request a briefing grounded in the saved analysis.                    |
| **Risk & exposure** | Compare capital and risk contributions, inspect correlations, and explain the saved risk snapshot.    |
| **Research**        | Search eight sample assets, compare companies, and summarize a selected official issuer page.        |
| **What-if lab**     | Compare modeled outcomes and request an explanation before optionally applying a scenario.           |

**Ask Panda** explains a saved analysis. Optional Gemini mode also adds a portfolio briefing, a focused risk explanation, a What-if comparison explanation, and summaries of selected official issuer pages. The default demo labels these actions and does not call Gemini.

## Quick start

Requires **Node.js 22.12+** and npm.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. Run all commands from the repository root.

| Command           | Purpose                                                       |
| ----------------- | ------------------------------------------------------------- |
| `npm test`        | Run the quant and frontend API contract tests.                |
| `npm run build`   | Type-check and create the production app in `frontend/dist/`. |
| `npm run preview` | Serve the production build locally.                           |

The app uses hash routes, so the built `frontend/dist/` directory can be served from a static host without route rewrites.

## Project map

```text
frontend/
  src/
    App.tsx         Routes and session portfolio state
    pages/          Overview, risk, research, and what-if views
    components/     Shared UI, charts, dialogs, and Ask Panda
    styles/         Feature styles and responsive rules
  public/           Favicon and self-hosted fonts
  tests/            Frontend API request contract tests
quant/
  analytics.ts      Portfolio and risk calculations
  data.ts           Illustrative assets and return series
  tests/            Calculation and scenario tests
quant_engine/       Python analytics engine used by the backend
backend/            Portfolio API, snapshots, and optional Gemini integration
  tests/            API, quant integration, and Gemini workflow tests
docs/               Design and verification notes
```

The root `package.json` provides the development, test, and build commands. The frontend imports the shared sample model from `quant/`. Overview can request a separate demo analysis from the backend API when the backend is running; its existing charts and tables still use the local TypeScript model. See the [backend guide](backend/README.md) to start the API.

## How the sample works

`quant/data.ts` defines eight assets, initial weights, research primers, and a deterministic series of 252 synthetic daily returns. Asset order must remain aligned with weight and return arrays. Portfolio edits live only in browser state; reloading restores the sample.

`quant/analytics.ts` calculates compounded returns, linked return contributions, annualized volatility, correlations, risk contributions, and drawdown. The model assumes constant daily weights and excludes fees, taxes, deposits, and withdrawals. The methodology dialog in the app explains these assumptions alongside the results.

Research links open external issuer and public-disclosure pages. A user can request an on-demand summary of the selected official issuer page when Gemini is configured; PandaSet does not crawl or ingest those pages in the background. The backend analyzes fictional sample prices. Ask Panda and the contextual explanations share one Gemini adapter, with workflow-specific prompts and tool access. API credentials must stay out of the browser bundle.

See the [backend guide](backend/README.md), [Python quant guide](quant_engine/README.md), [design notes](docs/design-system.md), and [verification notes](docs/verification.md) for more detail. Font licenses are in `frontend/public/fonts/`.
