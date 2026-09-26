"""Historical performance; returns are periodic simple returns."""
import numpy as np
import math


def _compoundable(returns):
    values = np.asarray(returns, dtype=float)
    if not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError("returns must be finite and greater than -1")
    return values


def annualized_return(returns, periods_per_year=252):
    return float(np.expm1(np.log1p(_compoundable(returns)).mean() * periods_per_year))


def annualized_arithmetic_mean(returns, periods_per_year=252):
    return float(returns.mean() * periods_per_year)


def periodic_rate(annual_rate, periods_per_year):
    if periods_per_year == 1:
        return float(annual_rate)
    return float(np.expm1(np.log1p(annual_rate) / periods_per_year))


def sharpe_ratio(returns, periods_per_year=252, annual_risk_free_rate=0.0):
    rate = periodic_rate(annual_risk_free_rate, periods_per_year)
    values = np.asarray(returns, dtype=float)
    # A constant shift does not change variance. Subtracting a huge rate first
    # would erase the original return differences.
    shifted = values - values[0]
    centered = shifted - math.fsum(shifted / len(shifted))
    sd = math.hypot(*centered) / math.sqrt(len(values) - 1)
    mean = math.fsum(values / len(values)) - rate
    if sd == 0:
        return None
    ratio = (mean / sd) * math.sqrt(periods_per_year)
    if not math.isfinite(ratio):
        raise ValueError("Sharpe ratio exceeds floating-point range")
    return ratio


def sortino_ratio(returns, periods_per_year=252, annual_target_return=0.0):
    rate = periodic_rate(annual_target_return, periods_per_year)
    values = np.asarray(returns, dtype=float)
    # Preserve close return/target differences, then scale before squaring.
    # If subtraction itself overflows, scale the operands first instead.
    with np.errstate(over="ignore"):
        excess = values - rate
    if not np.isfinite(excess).all():
        scale = max(float(np.max(np.abs(values))), abs(rate))
        excess = values / scale - rate / scale
    has_downside = bool((excess < 0).any())
    scale = float(np.max(np.abs(excess)))
    if scale == 0:
        return None
    excess = excess / scale
    downside = math.hypot(*np.minimum(excess, 0)) / math.sqrt(len(values))
    if downside == 0:
        if has_downside:
            raise ValueError("Sortino ratio exceeds floating-point range")
        return None
    ratio = (math.fsum(excess / len(values)) / downside) * math.sqrt(periods_per_year)
    if not math.isfinite(ratio):
        raise ValueError("Sortino ratio exceeds floating-point range")
    return ratio


def maximum_drawdown(returns):
    """Positive loss magnitude, including initial wealth V[0]=1."""
    # Track log wealth relative to its running peak, never absolute wealth.
    relative = worst = 0.0
    for growth in np.log1p(_compoundable(returns)):
        relative = min(0.0, relative + float(growth))
        worst = min(worst, relative)
    return float(-np.expm1(worst))
