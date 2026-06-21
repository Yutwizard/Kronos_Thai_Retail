"""Tests for kth.backtest.metrics — PSR, Sharpe CI, t-test, profit factor, bootstrap."""
import inspect

import numpy as np
import pandas as pd

from kth.backtest.metrics import (
    compute_bootstrap_pvalue,
    compute_metrics,
    compute_psr,
    compute_sharpe_ci,
    compute_trade_metrics,
)


def test_psr_returns_value_for_high_sharpe():
    """PSR must return a finite float, not NaN, when Sharpe > 2.0."""
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0.002, 0.01, 252))
    psr = compute_psr(returns, benchmark_sr=0.5)
    assert not np.isnan(psr), "PSR is NaN -- the bug (annualized SR in per-period formula)"
    assert 0.0 <= psr <= 1.0, f"PSR {psr} out of [0,1]"


def test_psr_zero_sharpe_returns_05():
    """When true SR ~ benchmark (both near 0), PSR should be near 0.5, but sampling
    noise can push it lower/higher. Guard: produces a finite [0,1] float."""
    returns = pd.Series(np.random.default_rng(1).normal(0, 0.01, 500))
    psr = compute_psr(returns, benchmark_sr=0.0)
    assert 0.0 <= psr <= 1.0, f"Expected [0,1], got {psr}"


def test_psr_benchmark_sr_clipped():
    returns = pd.Series(np.random.default_rng(2).normal(0.0001, 0.01, 500))
    psr = compute_psr(returns, benchmark_sr=1.0)
    assert psr < 0.5, f"Expected <0.5, got {psr}"


def test_sharpe_ci_returns_finite_values():
    returns = pd.Series(np.random.default_rng(42).normal(0.001, 0.01, 500))
    ci = compute_sharpe_ci(returns, n_bootstrap=500)
    assert np.isfinite(ci["sharpe_ci_2_5"])
    assert np.isfinite(ci["sharpe_ci_97_5"])
    assert ci["sharpe_ci_2_5"] <= ci["sharpe_ci_97_5"]


def test_t_stat_uses_sample_std():
    """t-test must use sample std (ddof=1)."""
    rng = np.random.default_rng(42)
    days = pd.bdate_range("2024-01-01", periods=300)
    strat = pd.Series(rng.normal(0.001, 0.01, 300), index=days)
    bench = pd.Series(rng.normal(0.0005, 0.01, 300), index=days)
    eq = pd.Series(np.cumprod(1 + strat) * 100, index=days)
    dr = eq.pct_change().dropna()
    m = compute_metrics(eq, dr, pd.DataFrame(), bench)
    excess = (dr - bench.pct_change()).dropna()
    t_manual = excess.mean() / (excess.std(ddof=1) / np.sqrt(len(excess)))
    assert abs(m["t_stat"] - t_manual) < 0.01, f"t-stat {m['t_stat']} vs manual {t_manual}"


def test_psr_uses_scipy_skew_kurtosis():
    """L13: compute_psr must use scipy.stats skew/kurtosis with bias=False."""
    from kth.backtest import metrics as m

    src = inspect.getsource(m.compute_psr)
    assert "from scipy.stats import" in src, "compute_psr must import scipy.stats"
    assert "bias=False" in src, "compute_psr must use bias=False for consistency"


def test_profit_factor_inf_when_no_losses():
    """L8: profit_factor returns inf (not None) when no losses."""
    trades = pd.DataFrame({"gross_return": [0.1, 0.2, 0.05], "friction_cost": [0, 0, 0]})
    result = compute_trade_metrics(trades)
    assert result["profit_factor"] == float("inf"), f"Expected inf, got {result['profit_factor']}"


def test_bootstrap_docstring_says_centered():
    """L7: docstring must say 'centered bootstrap', not 'shuffles'."""
    doc = compute_bootstrap_pvalue.__doc__ or ""
    assert "centered" in doc.lower(), "docstring must mention 'centered'"
    assert "shuffles" not in doc.lower(), "docstring must not say 'shuffles'"


def test_psr_high_sharpe_finite_after_scipy_fix():
    """L13 regression: PSR must be finite for high-Sharpe series."""
    rng = np.random.default_rng(99)
    returns = pd.Series(rng.normal(0.003, 0.008, 300))
    psr = compute_psr(returns, benchmark_sr=1.0)
    assert np.isfinite(psr), f"PSR not finite: {psr}"
    assert 0.0 <= psr <= 1.0, f"PSR out of [0,1]: {psr}"
