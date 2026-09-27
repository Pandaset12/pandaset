# Pandaset

Pandaset is a portfolio research application built with React, TypeScript, Vite, and a Python API. Sign in, save a portfolio, and explore its performance, risk, research, and hypothetical allocation scenarios. The standard workspace can use fictional sample prices or configured adjusted daily market history. An event-aware What-if Lab is available only when its separate backend services and access gate are configured.

Financial results are modeled research outputs, not brokerage data or investment advice. The default market-data provider uses fictional prices. An AI explanation does not make the underlying prices live.

## Run locally

Requires Node.js 22.22.2+ on the 22.x line, 24.15.0+ on the 24.x line, or 26+, plus npm and Python 3.11+. Run these commands from the repository root.

1. Install frontend dependencies and configure Supabase Auth for the browser:

   ```sh
   npm install
   cp .env.example .env.local
   ```

   Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` in `.env.local`. Enable email/password sign-in in the same Supabase project and configure its local site and confirmation redirect URLs. `VITE_` values are visible in the browser; use a publishable key, never a secret or service-role key.

2. Install and start the backend in another terminal:

   ```sh
   python3 -m venv backend/.venv
   backend/.venv/bin/python -m pip install -r backend/requirements.txt
   backend/.venv/bin/python -m pip install -e quant_engine
   cp backend/.env.example backend/.env
   backend/.venv/bin/python -m uvicorn backend.main:app --reload
   ```

   Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `backend/.env` for the **same project** as the frontend. The backend verifies bearer tokens and scopes portfolios, current metrics, and event records to the signed-in user. `SUPABASE_ANON_KEY` is supported for legacy configuration. The backend guide includes Windows commands and more configuration detail.

3. Start the frontend:

   ```sh
   npm run dev
   ```

   Open the URL Vite prints for the monochrome Pandaset landing page. Its **Explore the demo** links open the dashboard at `app.html`; previously shared root dashboard hash URLs redirect there as well. Its `/api` development proxy points to `http://127.0.0.1:8000` by default; set `API_PROXY_TARGET` in `.env.local` if your backend uses another address. The API exposes [health](http://127.0.0.1:8000/health) and [interactive docs](http://127.0.0.1:8000/docs). Keep both local environment files out of Git.

The standard workspace runs with the fictional sample provider and demo AI mode. It needs no market-data or Gemini key. To use adjusted daily prices, configure `MARKET_DATA_PROVIDER=alpaca`, server-side Alpaca credentials, and an explicit history feed; see the [Alpaca history guide](backend/docs/ALPACA_HISTORY.md). To enable AI explanations, see [Gemini setup](backend/README.md#enable-gemini). Neither option turns the application into a brokerage connection or a live intraday quote feed.

To show stock and fund logos automatically, set `VITE_LOGO_DEV_PUBLISHABLE_KEY` in `.env.local` to a Logo.dev publishable key (`pk_…`). The browser requests images by ticker; no company logo files or ticker-to-domain mappings are needed. Missing images and missing configuration show a local ticker mark. Before deploying, confirm the Logo.dev plan, allowed production origins, and [attribution terms](https://www.logo.dev/docs/platform/attribution) for the intended use. Only use a publishable key in `VITE_` configuration; keep secret keys out of the frontend.

## Workspace

After sign-in, create a named portfolio with supported tickers and weights totaling 100%. You can select and edit saved portfolios; the backend stores them for the authenticated account. All signed-in users see the same Overview, Risk, Research, Ask Panda, and What-if pages.

| What-if path | What it does | Data and access |
| --- | --- | --- |
| **Quick allocation comparison** | Compare and optionally apply a proposed allocation. | Uses owner-scoped SQLite portfolios and on-demand metrics from fictional sample prices or configured adjusted daily Alpaca history. |
| **Optional event research** | Research an event against that proposal, review evidence and shocks, then calculate and revisit a saved run. | Uses the same portfolio identity, adjusted Alpaca history, and owner-scoped MongoDB drafts/runs. It remains gated by event-service configuration and access rules. |

If event research is unavailable, quick comparisons and the other pages remain usable. Event runs use hypothetical shocks and deterministic calculations; conditional probability ranges stay hidden until calibration is approved. See the [backend event-lab guide](backend/README.md#authenticated-event-lab-apiv2) and [unified release gates](docs/unified-what-if-release.md) before enabling it.

The sample asset primers and synthetic return series live in `quant/data.ts`. Browser calculations live in `quant/analytics.ts`; backend metrics are calculated on demand with the Python quant engine. Keep asset order aligned with weight and return arrays. Research can open external issuer pages, and an on-demand AI summary can be requested when Gemini is configured. Event drafts and runs pin their inputs so later portfolio or price changes cannot rewrite saved outcomes.

## Commands and project map

| Command                                                                  | Purpose                                                                             |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `npm test`                                                               | Run quant and frontend tests.                                                       |
| `npm run build`                                                          | Type-check and build the frontend into `frontend/dist/`.                            |
| `npm run preview`                                                        | Serve the production frontend locally.                                              |
| `backend/.venv/bin/python -m pytest backend/tests quant_engine/tests -q` | Run backend and Python quant tests after installing `backend/requirements-dev.txt`. |

```text
frontend/src/        React app, authenticated workspaces, pages, and components
frontend/tests/      Frontend behavior and API contract tests
quant/               Standard workspace sample data and TypeScript calculations
quant_engine/        Python portfolio analytics and event model
backend/             Authenticated APIs, storage, market data, and AI services
docs/                Design, onboarding, verification, and release notes
```

Vite builds both `index.html` (landing) and `app.html` (dashboard). The dashboard uses hash routes, so a static host can serve `frontend/dist/` without route rewrites. See the [backend guide](backend/README.md), [Python quant guide](quant_engine/README.md), [design notes](docs/design-system.md), and [verification notes](docs/verification.md) for details. Font licenses are in `frontend/public/fonts/`.
