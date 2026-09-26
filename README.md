# PandaSet

**A clearer view of what you own.** PandaSet is an interactive portfolio research demo built with React, TypeScript, and Vite. Explore performance, risk, company research, and allocation scenarios through one shared sample portfolio.

## Explore the app

| Workspace           | What you can do                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| **Overview**        | Review sample performance, holdings, return attribution, and related research.                       |
| **Risk & exposure** | Compare capital and risk contributions, inspect correlations, and see allocation breakdowns.         |
| **Research**        | Search eight sample assets, compare companies, and follow links to official sources.                 |
| **What-if lab**     | Change weights, try presets, compare modeled outcomes, and apply a scenario for the current session. |

**Ask Panda** offers curated explanations using the app’s calculations. It is a guided demo, not a connected AI assistant.

## Quick start

Requires **Node.js 22.12+** and npm.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. Run all commands from the repository root.

| Command           | Purpose                                                       |
| ----------------- | ------------------------------------------------------------- |
| `npm test`        | Run the quant calculation and scenario tests.                 |
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
quant/
  analytics.ts      Portfolio and risk calculations
  data.ts           Illustrative assets and return series
  tests/            Calculation and scenario tests
backend/            Placeholder for a future service
docs/               Design and verification notes
```

The root `package.json` provides the development, test, and build commands. The frontend imports the shared sample model from `quant/`. There is **no backend implementation** yet.

## How the sample works

`quant/data.ts` defines eight assets, initial weights, research primers, and a deterministic series of 252 synthetic daily returns. Asset order must remain aligned with weight and return arrays. Portfolio edits live only in browser state; reloading restores the sample.

`quant/analytics.ts` calculates compounded returns, linked return contributions, annualized volatility, correlations, risk contributions, and drawdown. The model assumes constant daily weights and excludes fees, taxes, deposits, and withdrawals. The methodology dialog in the app explains these assumptions alongside the results.

Research links open external issuer and public-disclosure pages. PandaSet does not ingest their contents. A future backend can replace the sample data and curated analyst responses; API credentials must stay out of the browser bundle.

See [design notes](docs/design-system.md) and [verification notes](docs/verification.md) for more detail. Font licenses are in `frontend/public/fonts/`.
