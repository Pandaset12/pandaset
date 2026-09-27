# Event scenario calibration and release gate

## Model and input contract

`run_event_scenarios` accepts complete, daily adjusted holding-price histories,
daily factor changes, current and proposed long-only weights, and six confirmed
shock sets: mild, central, and severe at one and three months. Factor changes and
shocks share units. Issuer shocks are multiples of each holding's estimated
factor-adjusted residual volatility. The caller must label and verify the source,
date, and units of every factor and must obtain explicit user confirmation of all
shocks. This module does not fetch prices, infer news facts, or let an AI supply
returns.

The module calculates daily holding returns from adjusted prices and aligns them
with factor changes by date, without filling or extrapolation. It fits centered
ordinary least squares factor betas and the daily standard deviation of each
holding's residuals. At least 126 aligned returns, variable and linearly
independent factors, and a condition number at most 1e8 are required. Every
holding uses the same factor date set. The residual standard deviation times the
square root of 21 or 63 trading days is its issuer-specific sensitivity for the
respective horizon. This is a statistical proxy for security-specific event
effects; it is not a causal issuer estimate. A factor shock plus an issuer shock
times that sensitivity gives each holding's modeled return. Portfolio returns
are starting weights times holding impacts. Both portfolios receive the exact
same confirmed shocks and fitted sensitivities. Returns are additive estimates;
the model adds no baseline drift and excludes trading, fees, taxes, and cash flows.

The central conditional distribution samples aligned daily residual vectors with
a fixed seed. Sampling vectors preserves observed cross-holding residual
dependence. For each of 2,000 draws it sums 21 or 63 sampled daily residuals and
adds the fixed central shock impact. It reports the 10th, 50th, and 90th
percentiles and the fraction of draws below zero for each portfolio. These are
conditional model outputs, not unconditional forecasts or guarantees. Shocked
returns below -100%, or bootstrap draws below -100%, are rejected, not clipped.

## Held-out backtest

The calibration input is a curated event ledger. Each entry supplies a verified
source, an `as_of` date, and the central factor and issuer shocks for both
horizons. Realized outcomes come from the same adjusted-price history, never from
the ledger. Event origins must lie in the final 40% of observations, follow at
least 252 prior daily returns, have 63 future observations, and be at least 63
observations apart. At least 12 nonoverlapping events are required. At each
origin, sensitivities are re-fit using only prior history. The backtest then
calculates seeded central intervals and loss probabilities for current and
proposed weights at both horizons, comparing them with the subsequent adjusted
holding returns. This avoids fitting the event's actual outcome into its own
forecast.

The gate passes only if each of the four horizon/portfolio groups meets every
threshold:

| Metric | Pass range |
| --- | --- |
| Fraction of realized outcomes within the p10–p90 interval | 0.60–0.95 |
| Mean squared error of modeled loss probability (Brier score) | ≤ 0.30 |
| Median absolute error of p50 return | ≤ 0.20 decimal return |

The report records each metric, event count, held-out start date, model version,
thresholds, and a pass/fail reason. A passing report enables probability output
only if all holding histories are complete, all factor dates align, and at least
252 aligned residual observations exist. Missing event labels, sparse residuals,
incomplete factor alignment, a failed backtest, or invalid bootstrap outcomes
omit all conditional ranges and probabilities with a specific reason. The six
deterministic shock cases can still be calculated with partial factor-date
coverage when at least 126 aligned observations remain. No incomplete holding
price history is silently filled or dropped; invalid price data fail validation.

## Current calibration status

**Public gate: FAIL.** The repository has no licensed adjusted-price event ledger
or verified held-out event labels. Synthetic tests exercise the algorithm and
the pass/fail paths; they are not evidence of predictive calibration. Any run
without a verified ledger reports `no_held_out_event_labels` and omits p10,
p50, p90, and probability of loss. A real-data calibration report, reviewed
factor definitions, source rights, and vendor coverage are required before
public probability display is enabled.
