"""Shared fixtures for the Kronos-TH test suite."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def synthetic_returns():
    rng = np.random.default_rng(42)
    return pd.Series(rng.normal(0.002, 0.012, 252))


@pytest.fixture
def synthetic_equity_curve(synthetic_returns):
    cum = (1 + synthetic_returns).cumprod()
    return pd.Series(cum.values, index=pd.date_range("2024-01-01", periods=len(cum), freq="B"))


@pytest.fixture
def synthetic_trades():
    return pd.DataFrame({
        "gross_return": [0.05, 0.03, -0.02, 0.08, 0.01, -0.04, 0.06, -0.01, 0.02, -0.03],
        "friction_cost": [0.001] * 10,
        "size_pct": [1000.0] * 10,
        "ticker": ["AAPL"] * 10,
    })


@pytest.fixture
def tmp_cache(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    return d
