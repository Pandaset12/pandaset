"""Weight concentration and covariance-aware diversification."""


def concentration(weights, top_k=3):
    hhi = float((weights ** 2).sum())
    return {
        "hhi": hhi,
        "effective_number_of_holdings": 1 / hhi,
        "largest_position_weight": float(weights.max()),
        "top_k": top_k,
        "top_k_position_weight": float(weights.nlargest(top_k).sum()),
    }


def diversification_ratio(weights, asset_volatilities, portfolio_volatility):
    if portfolio_volatility == 0:
        return None
    return float(weights.dot(asset_volatilities.reindex(weights.index)) / portfolio_volatility)
