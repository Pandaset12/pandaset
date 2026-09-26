"""Run after installation: python examples/basic_analysis.py."""
import json
import pandas as pd
from quant_engine import analyze_portfolio

prices = pd.DataFrame(
    {"A": [100.0, 110.0, 99.0], "B": [100.0, 100.0, 110.0]},
    index=pd.date_range("2026-01-01", periods=3),
)
if __name__ == "__main__":
    print(json.dumps(analyze_portfolio(prices, {"A": 0.5, "B": 0.5},
                                      periods_per_year=2, top_k=1), indent=2, allow_nan=False))
