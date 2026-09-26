# Quant engine

Deterministic historical portfolio analytics using pandas and NumPy. No network,
frontend, AI, database, or authentication dependencies. Historical stress testing
is deferred; `scenarios.py` is the extension point.

From this directory, using Python 3.10 or newer:

```sh
python -m pip install -e ".[test]"
python -m pytest -q
python examples/basic_analysis.py
```

```python
from quant_engine import analyze_portfolio, compare_portfolios

report = analyze_portfolio(prices, {"AAPL": 0.6, "MSFT": 0.4})
comparison = compare_portfolios(
    prices,
    baseline_weights={"AAPL": 0.6, "MSFT": 0.4},
    proposed_weights={"AAPL": 0.5, "MSFT": 0.5},
)
```

`prices` is a positive, finite numeric DataFrame with unique increasing
DatetimeIndex and unique nonempty string asset labels. Supply at least three
price rows (two return observations). Weights must exactly match the assets,
be nonnegative, and sum to one within `1e-10`. Missing data are rejected.

Public keyword options: `periods_per_year=252`, `annual_risk_free_rate=0.0`,
`annual_target_return=0.0`, `top_k=3`. Annual rates are effective annual decimal
rates. Frequency and top-k must be positive integers. Sampling frequency is
caller-specified; the engine cannot infer an exchange calendar from dates.

Both public interfaces return strict JSON-compatible structures. Use
`json.dumps(report, allow_nan=False)`. Undefined metrics are `None` with report
warnings; input errors raise `ValueError`. The report contains metadata, weights,
dated return and cumulative-return series, asset metrics, labeled matrices,
portfolio metrics, and warnings. Matrix dictionaries use outer row labels and
inner column labels. Return-series dates correspond to the end of each interval.

Comparisons return full baseline and proposed reports plus portfolio metric
differences (proposed minus baseline). They use identical prices and settings;
undefined differences are null. `top_k` is configuration, so has no delta.

Only `analyze_portfolio` and `compare_portfolios` are the validated public
interfaces. Computational module helpers assume validated, aligned inputs.
See [methodology](docs/methodology.md) for formulas and limitations and
[example](examples/basic_analysis.py) for a self-contained demonstration.
