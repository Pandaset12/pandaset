"""Strict validation; no filling, sorting, dropping, or normalizing data."""
from collections.abc import Mapping
from numbers import Real, Integral

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype, is_complex_dtype

WEIGHT_TOLERANCE = 1e-10


def positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def annual_rate(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value) or value <= -1:
        raise ValueError(f"{name} must be finite and greater than -1")
    return float(value)


def validate_prices(prices):
    if not isinstance(prices, pd.DataFrame) or prices.shape[1] == 0 or len(prices) < 3:
        raise ValueError("prices must be a DataFrame with at least 3 rows and 1 asset")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("prices must have a DatetimeIndex")
    if prices.index.hasnans or not prices.index.is_unique or not prices.index.is_monotonic_increasing:
        raise ValueError("price dates must be nonmissing, unique, and increasing")
    if not prices.columns.is_unique or any(not isinstance(c, str) or not c for c in prices.columns):
        raise ValueError("asset labels must be unique nonempty strings")
    if any(not is_numeric_dtype(d) or is_bool_dtype(d) or is_complex_dtype(d) for d in prices.dtypes):
        raise ValueError("prices must contain real numeric values")
    values = prices.to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("prices must be finite, positive, and have no missing values")
    return prices.astype(float).copy()


def validate_weights(weights, assets):
    if not isinstance(weights, (Mapping, pd.Series)):
        raise ValueError("weights must be an asset-keyed mapping or Series")
    if isinstance(weights, pd.Series) and not weights.index.is_unique:
        raise ValueError("weight labels must be unique")
    if set(weights.keys()) != set(assets):
        raise ValueError("weight labels must exactly match price assets")
    raw = [weights[a] for a in assets]
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Real) for v in raw):
        raise ValueError("weights must be real numbers")
    result = pd.Series(raw, index=assets, dtype=float)
    if not np.isfinite(result).all() or (result < 0).any():
        raise ValueError("weights must be finite and nonnegative")
    if abs(float(result.sum()) - 1) > WEIGHT_TOLERANCE:
        raise ValueError("weights must sum to 1 within 1e-10; weights are never normalized")
    return result
