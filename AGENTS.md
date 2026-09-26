# Repository Guidelines

## Project Structure & Module Organization

PortfolioLens is a React, TypeScript, and Vite frontend. Application code lives in `frontend/src/`: `App.tsx` owns routing and shared portfolio state, `components/` holds reusable interface elements, and `pages/` contains the four workflows. Quantitative calculations and illustrative sample data live in `quant/`. Global styles are in `frontend/src/styles.css`. Quant tests are in `quant/tests/`; design and verification notes are in `docs/`; fonts and licenses are in `frontend/public/fonts/`.

Keep the asset order in `quant/data.ts` consistent with all portfolio weight and return arrays. Preserve visible labels that identify sample data and modeled results; the app is not connected to live market or brokerage services.

## Build, Test, and Development Commands

- `npm install` installs the locked dependencies.
- `npm run dev` starts Vite locally; use the URL it prints.
- `npm test` runs the Node test suite through `tsx`.
- `npm run build` type-checks with TypeScript and creates the production bundle in `frontend/dist/`.
- `npm run preview` serves the production build locally.

## Coding Style & Naming Conventions

Use TypeScript and React function components. Format with Prettier using two-space indentation, double quotes, and trailing commas; check with `npx prettier --check <files>`. Use PascalCase for component files and component names, camelCase for functions and values, and descriptive kebab-case CSS classes. Use shared components and CSS tokens where possible. Keep data calculations in `analytics.ts`, not presentation components.

## Testing Guidelines

Tests use Node’s built-in `node:test` and strict assertions. Name files `*.test.ts` and group cases by behavior or invariant. Cover calculation properties, input validation, and scenario behavior. Run `npm test` and `npm run build` before submitting changes. For UI changes, also inspect the affected route at desktop and mobile widths and verify keyboard and empty/error states where relevant.

## Commit & Pull Request Guidelines

Recent commits use concise subjects, often Conventional Commit prefixes, such as `feat: add PortfolioLens frontend` and `chore: add generic environment placeholders`. Prefer that format and describe the change directly. After finishing and verifying each requested change, commit only its files and push it to the current feature branch before starting unrelated work, unless the user asks otherwise. Pull requests should summarize user-visible changes, note relevant tests, link an issue when one exists, and include screenshots for significant visual changes. Keep generated output (`dist/`), dependencies (`node_modules/`), and local environment files out of commits.

## Security & Configuration

Keep credentials and local overrides in ignored `.env` files; never commit API keys. Portfolio values and returns are illustrative. Do not describe them as live financial data.
