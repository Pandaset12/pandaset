# Methodology

## Contract and assumptions

The engine analyzes historical, long-only, fully invested portfolios. All asset
prices must be positive finite real numbers on the same observation calendar.
The caller supplies adjusted prices; results are total returns only if the price
data include distributions. At least three prices (two returns) are required
because sample covariance uses one degree-of-freedom correction.

Dates must be a unique, increasing, nonmissing pandas DatetimeIndex; asset labels
must be unique nonempty strings. Missing prices are rejected, including prices
for zero-weight holdings. No forward filling, dropping, price adjustment, or date
sorting occurs. Asset columns are internally ordered alphabetically for identical
floating-point reduction order under column permutations. Caller inputs are copied.
The engine does not infer missing exchange sessions or validate calendar spacing;
the caller must supply a common sampling calendar matching periods_per_year.

Weights exactly match the asset labels, are finite and nonnegative, and sum to
one within absolute tolerance 1e-10. Accepted weights are never normalized.
Thus identities involving unit total weight hold to that tolerance.
Acceptance of the weight sum alone does not guarantee valid compounding: if the
weighted return is nonfinite or <= -1 on any observation, analysis raises
ValueError. This includes near-total losses combined with a tolerated weight sum
above one. Weights and returns are neither normalized nor clipped.
Weights remain constant: holdings are rebalanced each observation without costs,
taxes, or cash flows. This is not a buy-and-hold simulation.

Let P[t,i] denote prices; r[t,i] simple asset returns; w[i] weights; T the number
of return observations; A the positive integer periods per year (default 252).
All returns, rates, volatility, drawdown, weights, and risk percentages are decimal
fractions. Risk percentages sum to 1, not 100. Annual rates must be finite and
greater than -1. Top-k is a positive integer; k above asset count includes all
holdings. HHI, effective holdings, ratios, and correlations are dimensionless.

## Returns

- Asset simple return: r[t,i] = P[t,i] / P[t-1,i] - 1.
- Rebalanced portfolio return: r_p[t] = sum_i w[i] r[t,i].
- Cumulative return through t: C[t] = product_(u=1..t)(1+r[u]) - 1.
- Geometric annualized return: (product_t(1+r[t]))^(A/T) - 1.
  Implementation uses expm1(A * mean(log1p(r))) for numerical stability.
- Annualized arithmetic mean return: A * mean(r).

The report includes asset and portfolio return paths and cumulative paths, final
cumulative returns, and both annualized return definitions. Geometric return is
a compounded historical growth rate, while arithmetic annualization scales the
periodic average. Annualization uses observation count, not elapsed calendar days.
Neither quantity predicts future returns.

## Covariance, correlation, and volatility

Sample covariance S[i,j] = sum_t((r[t,i]-mean_i)(r[t,j]-mean_j))/(T-1).
Annual covariance Sigma = A*S. Annual asset volatility sigma_i = sqrt(Sigma[i,i]).
Correlation rho[i,j] = S[i,j]/sqrt(S[i,i]*S[j,j]); it is undefined if either
variance is zero, including a zero-variance asset's diagonal correlation.

Annual portfolio volatility sigma_p = sqrt(w^T Sigma w). This must agree with
sqrt(A) times the sample standard deviation of the portfolio return series.

Annual covariance and square-root volatility scaling assume sufficiently stable
returns and negligible serial correlation. Estimates may be singular; no inversion
or regularization is needed. Data are not modified to make a matrix invertible.
Covariance is calculated by explicit centered matrix multiplication. Translating
returns by their first observation before centering is algebraically equivalent
and ensures identical constant returns have exactly zero computed variance.
Nonfinite sample or annual covariance is rejected with ValueError, including
overflow from otherwise finite prices; it must never imply zero volatility.
When the quadratic form is within sqrt(machine epsilon) times the largest absolute covariance
entry of zero, analysis evaluates the equivalent norm of centered, weighted
return observations instead. Exact binary-rational weighted accumulation preserves
small hedge residuals before taking this norm. Contributions use the same return
factor, avoiding information already lost by rounding the covariance matrix.
The matrix-only portfolio_risk helper uses exact binary-rational accumulation in
this range; without observations it cannot recover information lost in the matrix.
For a positive exact quadratic form, the square root is taken before conversion
to binary floating point, preserving representable volatility even if variance
would underflow. A positive volatility below representable range is rejected.

## Risk attribution

- Marginal contribution MRC[i] = (Sigma*w)[i]/sigma_p.
- Component contribution CRC[i] = w[i]*MRC[i].
- Percentage contribution PRC[i] = CRC[i]/sigma_p.

MRC is the unconstrained partial derivative of volatility with respect to weight,
not the derivative of a funded trade constrained to preserve sum(w)=1.
Euler identities: sum_i CRC[i] = sigma_p and sum_i PRC[i] = 1.
MRC and CRC have annual volatility units. PRC is dimensionless.
Hedging assets may have negative CRC/PRC even for nonnegative weights. These are
not clipped. At sigma_p=0 all contributions are undefined, not assigned zero.

## Concentration and diversification

- HHI H = sum_i w[i]^2.
- Effective number of holdings = 1/H.
- Largest position = max_i w[i].
- Top-k concentration = sum of the largest min(k,n) weights.
- Diversification ratio = sum_i(w[i]*sigma_i)/sigma_p.

These definitions assume long-only weights. Equal weights across n holdings give
H=1/n and effective holdings=n. Weight concentration does not measure dependence;
the diversification ratio includes covariance through portfolio volatility.
It is undefined at zero portfolio volatility.

## Sharpe and Sortino

Convert effective annual risk-free rate f_a to periodic f=(1+f_a)^(1/A)-1.
Sharpe = sqrt(A)*mean(r_p-f)/s(r_p-f), where s is sample standard deviation
with ddof=1. A constant risk-free rate is assumed. Standard deviation is calculated
from the original returns after translating by the first return, using invariance
to a constant risk-free shift. This avoids erasing variation when the rate is huge.
Euclidean norms avoid overflow or underflow from directly squaring deviations.
Zero standard deviation gives an undefined Sharpe, regardless of numerator.

Convert effective annual target m_a to periodic m=(1+m_a)^(1/A)-1.
Downside deviation d = sqrt(sum_t(min(r_p[t]-m,0)^2)/T).
Sortino = sqrt(A)*(mean(r_p)-m)/d. All T observations enter the denominator,
not just the below-target observations. Zero downside deviation gives an undefined
Sortino, including a positive numerator. Defaults are f_a=m_a=0.
Sortino scales excess returns before calculating the downside norm; this common
scale cancels from the ratio. If excess subtraction overflows, its operands are
scaled first. Annual-to-periodic conversion is the identity when A=1. Extreme
rates remain supported when the resulting ratio is representable; a nonfinite
Sharpe or Sortino raises ValueError rather than returning a corrupted ratio.
Annual ratio scaling assumes comparable periods and appropriate time scaling;
serial dependence can make this scaling misleading.

## Maximum drawdown

Start wealth at V[0]=1 and V[t]=product_(u=1..t)(1+r_p[u]).
Peak[t]=max_(0<=u<=t)V[u]; drawdown[t]=V[t]/Peak[t]-1.
Maximum drawdown=-min_t(drawdown[t]), a nonnegative loss magnitude.
Including initial wealth ensures a loss on the first return is counted.
Implementation tracks log wealth relative to the current peak, updating
L[t]=min(0, L[t-1]+log1p(r_p[t])) and returning -expm1(min_t L[t]).
Absolute wealth is never accumulated, so its overflow or underflow cannot corrupt
drawdown, and long growth histories do not erase subsequent small losses.

## What-if comparisons and numerical behavior

Baseline and proposed portfolios use exactly the same supplied prices and
parameters, under the same constant-weight assumption. Each receives a full
analysis. Scalar portfolio metric differences are proposed minus baseline;
configuration top_k is excluded. A difference is undefined when either source
metric is undefined, or subtraction exceeds floating-point range. Historical
stress-window analysis is deliberately deferred.

Invalid inputs raise ValueError. Undefined metrics are returned as JSON null
(Python None) with warnings. Any nonfinite calculated value is converted to null
with its report path recorded in warnings, preventing NaN/Infinity in strict JSON.
Price ratios that overflow or round to returns <= -1 are rejected explicitly.
Portfolio returns and inputs to geometric annualization and drawdown must also
be finite and greater than -1; invalid observations are not silently skipped.
No statistical near-zero cutoff is imposed: small positive volatilities remain
positive. For matrix-only risk calculations, negative portfolio variance within
1e-12 times the largest absolute
annual covariance entry is treated as cancellation roundoff and clamped to zero;
larger negative variance raises ValueError. This does not regularize covariance.

Tests use hand-computed examples and invariants, including covariance, Euler
contributions, direct portfolio-series volatility, ordering invariance, identical
assets, negative hedge contributions, zero variance, concentration, return and
drawdown examples, annual-rate conversion, validation, and strict JSON round trips.
