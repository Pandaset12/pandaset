import pandas as pd
import pytest


@pytest.fixture
def prices():
    return pd.DataFrame({"A": [100., 110., 99.], "B": [100., 100., 110.]},
                        index=pd.date_range("2026-01-01", periods=3))
