"""Historical weight comparisons. Historical stress windows are deferred."""
import math
from .analytics import analyze_portfolio


def compare_portfolios(prices, baseline_weights, proposed_weights, **kwargs):
    """Same prices/settings; deltas are proposed minus baseline scalar metrics."""
    baseline = analyze_portfolio(prices, baseline_weights, **kwargs)
    proposed = analyze_portfolio(prices, proposed_weights, **kwargs)
    differences = {}
    for key, before in baseline["portfolio"].items():
        if key == "top_k":
            continue
        after = proposed["portfolio"][key]
        delta = None if before is None or after is None else after - before
        differences[key] = delta if delta is None or math.isfinite(delta) else None
    return {"baseline": baseline, "proposed": proposed,
            "portfolio_metric_differences": differences,
            "difference_convention": "proposed minus baseline; null if undefined or nonfinite"}
