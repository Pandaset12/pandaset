"""Simple returns and constant-weight, per-observation rebalancing."""
import numpy as np


def asset_returns(prices):
    """r[t,i] = P[t,i] / P[t-1,i] - 1; prices must be validated."""
    result = prices.pct_change(fill_method=None).iloc[1:]
    if not np.isfinite(result.to_numpy()).all() or (result <= -1).any().any():
        raise ValueError("price ratios exceed floating-point return range")
    return result


def portfolio_returns(returns, weights):
    """r_p[t] = sum_i w_i r[t,i], aligning weights by asset label."""
    result = returns.dot(weights.reindex(returns.columns)).rename("portfolio")
    if not np.isfinite(result.to_numpy()).all() or (result <= -1).any():
        raise ValueError("portfolio returns must be finite and greater than -1; check weight tolerance")
    return result


def cumulative_returns(returns):
    """Cumulative simple return path: product(1+r) - 1."""
    return (1 + returns).cumprod() - 1
