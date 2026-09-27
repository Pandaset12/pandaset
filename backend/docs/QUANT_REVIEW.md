# Historical quant engine integration review

This records the pre-integration review of `500c77c`, not the current runtime.
The quant engine is now connected through `EngineQuantProvider`. Current status
and contracts are in [INTEGRATION.md](../INTEGRATION.md); the findings below
describe the older review baseline.

Reviewed `quant-engine` commit
[`500c77c`](https://github.com/Pandaset12/pandaset/commit/500c77c)
on 2026-09-26. At that time the module was inspected and tested in an isolated
copy before being wired into the API.

## Confirmed implementation

`analyze_portfolio(prices, weights, *, periods_per_year=252,
annual_risk_free_rate=0.0, annual_target_return=0.0, top_k=3)`
returns portfolio/asset performance, covariance/correlation, volatility,
risk contributions, Sharpe/Sortino, drawdown, concentration and diversification.

`compare_portfolios(prices, baseline_weights, proposed_weights, **kwargs)`
returns two complete reports and proposed-minus-baseline differences.

Prices must be a positive finite pandas DataFrame with a unique increasing
DatetimeIndex, at least three rows, no missing values, and columns matching all
weight keys. The caller supplies adjusted prices and a common observation
calendar. Weights are decimals, nonnegative, and must total one within 1e-10.
Historical stress-window testing is intentionally deferred.

The calculations assume constant weights rebalanced at every observation,
without costs or taxes. They are historical simulations, not the user's actual
brokerage performance or daily news attribution.

## API adapter changes required

| Quant result | Current API field / required treatment |
| --- | --- |
| `portfolio.cumulative_return` | `portfolio_return`; keep separate from annualized returns |
| `portfolio.annualized_volatility` | `portfolio_volatility` |
| `assets[symbol].annualized_volatility` | `asset_volatility[symbol]` |
| `assets[symbol].percentage_risk_contribution` | `risk_contribution[symbol]`; keep signed decimal shares |
| `matrices.correlation` | `correlation_matrix`; support undefined cells and numerical tolerance |
| `metadata.return_observations` | `observation_count` and the chosen analysis window |
| `metadata.end_date` | Coordinate timestamp/session-date meaning and timezone with the data adapter |
| `warnings`, `metadata.assumptions` | Preserve with the saved snapshot and Gemini context |
| `baseline`, `proposed`, `portfolio_metric_differences` | Map to the HLD's `current_analysis`, `proposed_analysis`, `delta` |

Other new metrics, including Sharpe/Sortino and drawdown, need explicit schema
and metric-citation fields if exposed to the frontend/Gemini. Do not send the
full price/return history to the model when summary metrics suffice.

### Reproduced compatibility issues

1. **Correlation roundoff:** the engine can return `1.0000000000000002`
   for a diagonal correlation. The current API's strict [-1, 1] check rejects
   this ordinary floating-point result. It occurred in 18 of 20 deterministic
   four-asset synthetic samples and in a small normal mapping example. Agree on
   a narrow roundoff tolerance; reject materially invalid correlations.
2. **Undefined values:** zero-variance assets produce null correlation cells;
   a zero-volatility portfolio produces null risk shares. Those are valid
   undefined results with warnings, but the API currently requires numeric
   dictionary values. Preserve nulls and omit them from numeric metric citations.
3. **Weight tolerance:** the API accepts a total of 1.0000005 (1e-6 tolerance),
   while the engine rejects it (1e-10). Align validation without silently
   renormalizing the user's allocation.
4. **Dates/provenance:** the engine accepts naive dates, while the API requires
   aware timestamps. The caller must provide timezone/session semantics, data
   source and freshness; the engine cannot invent them.
5. **Adding/removing assets in what-if:** both weight maps must cover the same
   union of assets as the price columns. Fill absent *weights* with zero after
   forming that union; obtain real aligned history for every symbol. Do not fill
   missing prices with zero.

The default API provider remains the fictional fixture, and what-if still
returns 501. These findings are integration work, not a claim that the quant
module is connected.

## Verification

- Isolated Windows/Python 3.12 environment, NumPy 2.5.3, pandas 3.0.6:
  **83 quant tests passed**.
- Representative analysis/comparison results serialize with
  `json.dumps(..., allow_nan=False)`.
- Both comparison reports used the same input prices; zero-filled weight keys
  allowed a newly allocated asset.
- Compatibility probes reproduced the issues above against the current
  `AnalyticsSnapshot` model.
- No market account, Gemini, MongoDB or Tiger Data service was contacted.
