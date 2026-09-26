# PortfolioLens — High-Level Design

**Status:** MVP design for ShellHacks 2026  
**Audience:** PortfolioLens team — shared implementation context  
**Last updated:** September 26, 2026

## 1. What We Are Building

PortfolioLens is a lightweight investment portfolio analysis terminal. It brings portfolio holdings, market data, quantitative risk metrics, and an AI explanation layer into one dashboard.

The user should be able to answer:

- How is my portfolio performing?
- Which holdings contribute the most risk, and why?
- What happens if I change my portfolio weights?

This is an educational/demo product. It does not place trades or provide guaranteed investment advice.

## 2. MVP Scope

### Must have

- Loading a sample portfolio or entering holdings manually
- Daily adjusted-close price data, with a seeded-data fallback
- Portfolio return and volatility
- Risk contribution by holding
- One useful Gemini-powered explanation based on calculated metrics
- A frontend dashboard that makes the results easy to understand

### Nice to have

- Correlation matrix
- Concentration/diversification metrics
- What-if portfolio analysis
- Persistent portfolio and analysis history
- Automatic data refresh

If a market data or AI provider is temporarily unavailable, the demo should still work with cached or seeded data. The team should finish the must-have path before adding nice-to-have features.

## 3. System Overview

```text
┌──────────────┐       HTTPS/JSON       ┌────────────────────┐
│ Web Frontend │ ─────────────────────> │ Application API   │
│ Meirzhan     │ <───────────────────── │ Yuan Haoran       │
└──────────────┘                        └─────────┬──────────┘
                                                  │
                 ┌────────────────────────────────┼────────────────┐
                 ▼                                ▼                ▼
          ┌──────────────┐                 ┌──────────────┐  ┌──────────────┐
          │ Quant Engine │                 │ Gemini       │  │ Portfolio DB │
          │ Nel A        │                 │ AI Analyst   │  │ MongoDB      │
          └──────┬───────┘                 └──────────────┘  └──────────────┘
                 ▲
                 │
          ┌──────┴───────┐       ┌──────────────────────┐
          │ Market Data  │──────>│ Time-Series Storage  │
          │ Provider     │       │ Tiger Data/Timescale │
          └──────────────┘       └──────────────────────┘
```

### Component ownership

| Component | Responsibility | Owner |
|---|---|---|
| Frontend | Dashboard, charts, what-if controls, AI chat | Meirzhan |
| Application API | REST endpoints, validation, orchestration, Gemini calls | Yuan Haoran |
| Data and infrastructure | Market data ingestion, cleaning, caching, databases, deployment | Vincent |
| Quant engine | Returns, volatility, covariance, correlations, risk contribution, what-if calculations | Nel A |

## 4. Data Flow

```text
Market API
  → Data adapter
  → Clean and validate price data
  → Tiger Data / Timescale
  → Quant engine
  → Application API
  → Frontend and Gemini
```

Portfolio definitions and analysis snapshots are stored in MongoDB when persistence is enabled. Historical price data is stored in Tiger Data/Timescale because it is queried by symbol and time range.

For the first demo, seeded data and a lightweight local store are acceptable if setting up both databases becomes a time bottleneck. The database choice should not block the main end-to-end flow.

For the hackathon, these should be modules in one deployed API rather than separate production microservices. The logical boundaries matter more than physically splitting the services.

The Quant Engine will be a Python module called by the Application API for the MVP. It does not need to run as a separate network service.

The market data provider must be hidden behind a small adapter interface so that we can switch providers without changing the rest of the system:

```python
get_daily_prices(
    symbols: list[str],
    start: date,
    end: date,
) -> list[PriceBar]
```

API keys must be stored in environment variables and never committed to Git.

## 5. Shared API Contract

JSON is the data format used between the frontend and backend. It is not a database or a separate service. We should agree on the response shapes first so that all four people can work independently using mock data.

The examples below are the initial contract. The implementation can use TypeScript types, Python dictionaries, or Pydantic models, but the field names and meanings should stay consistent.

### Create a portfolio

`POST /api/v1/portfolios`

```json
{
  "name": "Demo Portfolio",
  "holdings": [
    {"symbol": "NVDA", "weight": 0.30},
    {"symbol": "SPY", "weight": 0.70}
  ]
}
```

### Run an analysis

`POST /api/v1/portfolios/{portfolio_id}/analysis`

Returns:

```json
{
  "analysis_id": "analysis_123",
  "as_of": "2026-09-26",
  "lookback_days": 252,
  "portfolio_return": 0.083,
  "portfolio_volatility": 0.184,
  "asset_volatility": {"NVDA": 0.42, "SPY": 0.16},
  "correlation_matrix": {
    "NVDA": {"NVDA": 1.0, "SPY": 0.72}
  },
  "risk_contribution": {
    "NVDA": 0.41,
    "SPY": 0.59
  },
  "concentration": {
    "largest_position": "NVDA",
    "largest_weight": 0.30
  },
  "data_quality": {
    "source": "cache",
    "warnings": []
  }
}
```

### What-if analysis

`POST /api/v1/portfolios/{portfolio_id}/what-if`

The request contains proposed holdings. The response contains `current_analysis`, `proposed_analysis`, and a `delta` object for the most important metrics.

### Error responses

All API errors should use the same shape:

```json
{
  "error": {
    "code": "INVALID_PORTFOLIO",
    "message": "Weights must sum to 1.0"
  }
}
```

Expected error cases include invalid weights, missing ticker data, market API timeout, stale data, and Gemini timeout.

### Ask the AI analyst

`POST /api/v1/portfolios/{portfolio_id}/ask`

```json
{
  "question": "What is my biggest risk and why?",
  "analysis_id": "analysis_123"
}
```

```json
{
  "answer": "NVDA is the largest risk contributor...",
  "citations": [
    {"field": "risk_contribution.NVDA", "value": 0.41}
  ],
  "disclaimer": "For educational purposes only; not financial advice."
}
```

The AI layer must use the saved analysis result as context. Gemini should not invent portfolio metrics.

## 6. Data Model

### MongoDB: `portfolios`

```json
{
  "_id": "portfolio_123",
  "name": "Demo Portfolio",
  "holdings": [
    {"symbol": "NVDA", "weight": 0.30}
  ],
  "created_at": "2026-09-26T10:00:00Z",
  "updated_at": "2026-09-26T10:00:00Z"
}
```

### Tiger Data/Timescale: `daily_prices`

```text
time        TIMESTAMPTZ
symbol      TEXT
open        NUMERIC
high        NUMERIC
low         NUMERIC
close       NUMERIC
adj_close   NUMERIC
volume      BIGINT
source      TEXT
```

Use `(symbol, time)` as a unique key and index `(symbol, time DESC)`.

### Analysis snapshots

Store the portfolio ID, analysis date, lookback window, calculated metrics, data source, and warnings. Gemini should reference a specific snapshot instead of recalculating everything for every question.

## 7. Team Responsibilities

### Nel A — Quant Engine

Owns the financial calculations and the definition of the metrics shown in the product.

**Deliverables:**

- Portfolio return and annualized volatility
- Asset volatility and covariance/correlation matrix
- Portfolio volatility using the portfolio weights
- Risk contribution by holding
- Concentration and diversification metrics
- What-if analysis for proposed weights
- A clean function or service that accepts normalized prices and holdings and returns JSON
- Basic tests for the formulas and edge cases

**MVP assumptions:** long-only holdings, weights must sum to 1.0, daily adjusted-close prices, and 252 trading days for annualization. Short positions, leverage, options, and trading execution are out of scope.

**Should not own:** database access, market data fetching, Gemini prompts, or frontend logic.

### Vincent — Data and Infrastructure (Backend Person #1)

Owns the market data pipeline, storage, caching, and the shared local/deployment setup.

**Deliverables:**

1. Define the normalized `PriceBar` and portfolio data shapes.
2. Implement the market data adapter.
3. Clean data: uppercase symbols, sort dates, remove duplicates, detect missing values, and use adjusted close.
4. Write and query daily prices in Tiger Data.
5. Provide cached-data and seeded-demo-data fallbacks.
6. Expose clean price data to the quant engine.
7. Document local setup and environment variables.
8. Help connect the data layer to Yuan Haoran’s API service.

**Nice to have:** a data refresh command, provider/cache health endpoint, Docker Compose setup, structured logs, and request IDs.

**Should not own:** final quant formulas, Gemini behavior, or frontend layout.

### Backend Person #2 — Application API and Gemini (Yuan Haoran)

Owns the API layer that connects the frontend, data layer, quant engine, and Gemini.

**Deliverables:**

- Implement the portfolio, analysis, what-if, and AI question endpoints
- Validate request bodies and return consistent error responses
- Orchestrate data loading and quant calculations
- Save and retrieve analysis snapshots
- Build the Gemini prompt using the portfolio, metrics, warnings, and user question
- Make sure Gemini explains existing metrics instead of inventing numbers
- Return metric references and the educational-use disclaimer with AI answers
- Add loading/error fallbacks when Gemini or another service is unavailable
- Deploy the API and document the required environment variables

**Should not own:** the underlying quant formulas, market-data cleaning details, or dashboard visual design.

### Frontend — Meirzhan

Owns the user-facing PortfolioLens dashboard and the demo experience.

**Deliverables:**

- Portfolio input or sample portfolio loading
- Portfolio overview with return and volatility
- Holdings table
- Risk contribution chart
- Correlation/diversification view
- What-if weight controls and before/after comparison
- AI chat or question panel
- Loading, empty, and error states
- Clear display of data freshness and the financial-education disclaimer
- A polished, responsive demo flow that can be shown during judging

**Should not own:** financial calculations, direct market API calls, or Gemini API keys. The frontend should use the shared Application API.

### Team-wide responsibilities

- Agree on the shared JSON schemas before implementing deep integrations.
- Keep demo data available so the project can run without external APIs.
- Use feature branches or clearly separated folders and merge changes frequently.
- Test the complete flow together after each integration milestone.
- Keep the README and setup instructions up to date.

The team should treat the API schemas in this document as the integration contract. If a field needs to change, update the contract and tell the other owners before changing implementation code.

## 8. Main Request Flows

### Portfolio analysis

1. Frontend calls the analysis endpoint. For the MVP, this is a synchronous request.
2. API validates the holdings and weight total.
3. Data layer loads the requested price window from Tiger Data.
4. If data is missing, the adapter fetches and stores it.
5. Quant engine calculates the metrics.
6. API saves an analysis snapshot in MongoDB.
7. API returns the result to the frontend.

### AI question

1. Frontend sends a question and analysis ID.
2. API loads the analysis snapshot.
3. API builds a prompt containing holdings, metrics, warnings, and the user question.
4. Gemini explains the result.
5. API returns the answer together with metric references and the disclaimer.

## 9. Reliability and Safety

- Validate symbols, dates, weights, and weight totals at the API boundary.
- Show whether data is fresh or cached.
- Return a readable fallback if Gemini fails.
- Do not expose API keys in the frontend or repository.
- Add tests for normal data, missing data, invalid weights, and a single-asset portfolio.
- Display “For educational purposes only; not financial advice.”
- Do not execute trades or connect to brokerage accounts.

## 10. Hackathon Delivery Plan

| Time | Goal |
|---|---|
| 0–3 hours | Agree on schemas, repo structure, demo portfolio, and environment variables |
| 3–10 hours | Build data adapter, basic quant metrics, API skeleton, and frontend shell |
| 10–18 hours | Connect databases, analysis endpoint, and dashboard charts |
| 18–26 hours | Add Gemini chat, what-if analysis, loading/error states, and fallbacks |
| 26–32 hours | Deploy, test the full flow, and fix integration issues |
| 32–36 hours | Prepare README, demo script, screenshots, and final submission |

### Integration milestones

- **M1:** All teams can use the same mock JSON schemas.
- **M2:** The analysis endpoint returns real quant results.
- **M3:** The dashboard and AI assistant use the same analysis snapshot.
- **M4:** The demo still works with cached data when external services fail.

## 11. Suggested Repository Layout

```text
portfolio-lens/
├─ apps/
│  ├─ web/                 # Frontend
│  └─ api/                 # Application API
├─ services/
│  ├─ data-ingestion/      # Market data and storage
│  └─ quant-engine/        # Portfolio analytics
├─ packages/
│  └─ schemas/             # Shared request/response schemas
├─ infra/
│  └─ docker-compose.yml
├─ scripts/
│  └─ seed_demo_data.*
├─ .env.example
└─ README.md
```

## 12. Demo Story

1. Load a portfolio containing NVDA, SPY, JPM, and TLT.
2. Show return, volatility, and risk contribution.
3. Explain why the largest position is not always the only source of risk.
4. Reduce NVDA from 30% to 15% using the what-if control.
5. Show the change in portfolio volatility and risk contribution.
6. Ask Gemini: “Why is my portfolio risk concentrated, and what changed in the what-if scenario?”

The demo should make one idea obvious: the quant engine calculates what is happening, while the AI layer explains it in plain English.

## 13. Open Questions / Team Decisions

This section is intentionally left for the team to edit during the first planning session.

- [ ] Which market data provider will we use, and do we already have an API key?
- [ ] Are Tiger Data and MongoDB required for the demo, or should we start with seeded/local data and add persistence only if time allows?
- [ ] Where will the API and frontend be deployed?
- [ ] Is authentication out of scope for the demo? The current assumption is yes.
- [ ] Is what-if analysis a must-have or a nice-to-have after the basic analysis flow works?
- [ ] How should the quant engine handle missing price observations: drop the asset, use the latest valid value, or return a warning?
- [ ] What exact lookback period should the default analysis use: 1 year, 2 years, or the maximum available data?
- [ ] Which Gemini model and SDK will Yuan Haoran use?
- [ ] Who will own the final integration branch and the demo deployment?
- [ ] What is the final two-minute demo script and judging narrative?
