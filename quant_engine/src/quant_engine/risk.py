"""Sample covariance and Euler decomposition of annual volatility."""
import numpy as np
import pandas as pd
import math
from fractions import Fraction
from decimal import Decimal, localcontext


def covariance(returns, periods_per_year=252):
    # Translation before centering avoids spurious variance for constants.
    shifted = returns - returns.iloc[0]
    centered = shifted - shifted.mean()
    sample = centered.T.dot(centered) / (len(returns) - 1)
    annual = sample * periods_per_year
    if not np.isfinite(sample.to_numpy()).all() or not np.isfinite(annual.to_numpy()).all():
        raise ValueError("covariance exceeds floating-point range")
    return sample, annual


def correlation(sample_covariance):
    sd = np.sqrt(np.diag(sample_covariance))
    denominator = np.outer(sd, sd)
    values = np.full_like(denominator, np.nan)
    np.divide(sample_covariance.to_numpy(), denominator, out=values, where=denominator > 0)
    return pd.DataFrame(values, index=sample_covariance.index, columns=sample_covariance.columns)


def asset_volatility(annual_covariance):
    return pd.Series(np.sqrt(np.diag(annual_covariance)), index=annual_covariance.index)


def portfolio_risk(annual_covariance, weights, *, returns=None, periods_per_year=252):
    """sigma=sqrt(w' Sigma w); MRC=Sigma w/sigma; CRC=w*MRC."""
    w = weights.reindex(annual_covariance.index)
    if not np.isfinite(annual_covariance.to_numpy()).all():
        raise ValueError("covariance must be finite")
    exposure = annual_covariance.dot(w)
    variance = float(w.dot(exposure))
    scale = float(np.abs(annual_covariance.to_numpy()).max())
    if not np.isfinite(variance) or not np.isfinite(exposure).all():
        raise ValueError("portfolio risk exceeds floating-point range")
    if abs(variance) <= math.sqrt(np.finfo(float).eps) * scale:
        # A rounded Gram matrix may have lost the small residual entirely.
        # When observations are available, retain their factored representation.
        if returns is not None:
            rows = [[Fraction(float(x)) for x in row]
                    for row in returns.reindex(columns=w.index).to_numpy()]
            exact_w = [Fraction(float(v)) for v in w]
            projected = [sum((x * wi for x, wi in zip(row, exact_w)), Fraction())
                         for row in rows]
            mean = sum(projected, Fraction()) / len(projected)
            centered = [x - mean for x in projected]
            norm = math.hypot(*(float(x) for x in centered))
            factor = math.sqrt(periods_per_year / (len(rows) - 1))
            volatility = norm * factor
            undefined = pd.Series(np.nan, index=w.index)
            if norm == 0:
                if any(centered):
                    raise ValueError("portfolio volatility is below floating-point range")
                return 0.0, undefined, undefined.copy(), undefined.copy()
            marginal = pd.Series([
                float(sum((row[i] * c for row, c in zip(rows, centered)), Fraction())
                      / Fraction(norm)) * factor for i in range(len(w))], index=w.index)
            component = w * marginal
            return volatility, marginal, component, component / volatility
        # Exact binary-rational accumulation avoids cancellation in w' Sigma w.
        exact_w = [Fraction(float(v)) for v in w]
        exact_exposure = [sum((Fraction(float(x)) * wi for x, wi in zip(row, exact_w)), Fraction())
                          for row in annual_covariance.to_numpy()]
        exact_variance = sum((wi * e for wi, e in zip(exact_w, exact_exposure)), Fraction())
        variance = float(exact_variance)
        exposure = pd.Series([float(e) for e in exact_exposure], index=w.index)
        if exact_variance > 0:
            # Take the root before conversion: variance can underflow even when
            # its square root and risk contributions are representable.
            with localcontext() as context:
                context.prec = 40
                volatility = float((Decimal(exact_variance.numerator)
                                    / Decimal(exact_variance.denominator)).sqrt())
            if volatility == 0:
                raise ValueError("portfolio volatility is below floating-point range")
            marginal = pd.Series([float(e / Fraction(volatility)) for e in exact_exposure], index=w.index)
            component = w * marginal
            return volatility, marginal, component, component / volatility
    # Permit only cancellation-sized negative roundoff from a rounded PSD matrix.
    if variance < -1e-12 * scale:
        raise ValueError("negative portfolio variance")
    volatility = float(np.sqrt(max(0.0, variance)))
    undefined = pd.Series(np.nan, index=w.index)
    marginal = exposure / volatility if volatility > 0 else undefined
    component = w * marginal
    percentage = component / volatility if volatility > 0 else undefined.copy()
    return volatility, marginal, component, percentage
