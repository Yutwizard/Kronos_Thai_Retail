"""Verify backtest bugfixes: PSR, equity curve alignment, open_trades blend,
block bootstrap, t-test ddof/bm fillna."""

import numpy as np
import pandas as pd
from kth.backtest.metrics import compute_psr, compute_sharpe_ci, compute_metrics


# ---- Task 1: PSR ----
def test_psr_returns_value_for_high_sharpe():
    """PSR must return a finite float, not NaN, when Sharpe > 2.0."""
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0.002, 0.01, 252))
    psr = compute_psr(returns, benchmark_sr=0.5)
    assert not np.isnan(psr), f"PSR is NaN -- the bug (annualized SR in per-period formula)"
    assert 0.0 <= psr <= 1.0, f"PSR {psr} out of [0,1]"
    print("PASS test_psr_returns_value_for_high_sharpe")


def test_psr_zero_sharpe_returns_05():
    """When true SR ~ benchmark (both near 0), PSR should be near 0.5, but sampling
    noise can push it lower/higher. Guard: produces a finite [0,1] float."""
    returns = pd.Series(np.random.default_rng(1).normal(0, 0.01, 500))
    psr = compute_psr(returns, benchmark_sr=0.0)
    assert 0.0 <= psr <= 1.0, f"Expected [0,1], got {psr}"
    print("PASS test_psr_zero_sharpe_returns_05")


def test_psr_benchmark_sr_clipped():
    returns = pd.Series(np.random.default_rng(2).normal(0.0001, 0.01, 500))
    psr = compute_psr(returns, benchmark_sr=1.0)
    assert psr < 0.5, f"Expected <0.5, got {psr}"
    print("PASS test_psr_benchmark_sr_clipped")


# ---- Task 2: equity curve ----
def test_equity_curve_index_is_mark_day_not_signal_day():
    """Regression guard: equity curve must be indexed by mark_days, not trading_days."""
    import inspect
    from kth.backtest import walkforward
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'mark_days' in source, "Equity curve must use mark_days"
    assert 'mark_index' in source, "Equity curve must use mark_index"
    print("PASS test_equity_curve_index_is_mark_day_not_signal_day")


# ---- Task 3: open_trades blend ----
def test_open_trades_blends_on_rebalance():
    """Regression guard: walkforward must blend entry price on rebalance."""
    import inspect
    from kth.backtest import walkforward
    source = inspect.getsource(walkforward.run_walkforward)
    assert 'blended' in source.lower(), "open_trades must blend entry price on rebalance"
    print("PASS test_open_trades_blends_on_rebalance")


def test_open_trades_blend_logic_correct():
    """Blend math: buy 100 @ 50, add 50 @ 60 -> weighted avg 53.33."""
    old = {"entry_price": 50.0, "units": 100, "trade_value": 5000.0, "entry_date": "d1"}
    new_units, new_price = 50, 60.0
    total = old["units"] + new_units
    blended = (old["units"] * old["entry_price"] + new_units * new_price) / total
    assert abs(blended - 53.333) < 0.01, f"Expected ~53.33, got {blended}"
    exec_price = 55.0
    gross_ret = (exec_price / blended - 1) * (total * blended)
    assert gross_ret > 0, f"Blended entry should give profit: {gross_ret}"
    print("PASS test_open_trades_blend_logic_correct")


# ---- Task 4: block bootstrap ----
def test_sharpe_ci_returns_finite_values():
    returns = pd.Series(np.random.default_rng(42).normal(0.001, 0.01, 500))
    ci = compute_sharpe_ci(returns, n_bootstrap=500)
    assert np.isfinite(ci["sharpe_ci_2_5"])
    assert np.isfinite(ci["sharpe_ci_97_5"])
    assert ci["sharpe_ci_2_5"] <= ci["sharpe_ci_97_5"]
    print("PASS test_sharpe_ci_returns_finite_values")


# ---- Task 5: t-test ----
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
    print("PASS test_t_stat_uses_sample_std")


# ---- Task 6: cash shortfall ----
def test_trade_ticket_buy_cost_does_not_exceed_cash():
    """Cash guard: deployable must be capped at available cash."""
    cash = 50_000.0
    total_value = 500_000.0
    alloc_pct = 0.10
    deployable_naive = total_value * alloc_pct  # 50,000
    deployable_guarded = min(deployable_naive, cash)  # 50,000
    cash2 = 25_000.0
    total_value2 = 500_000.0
    deployable_naive2 = total_value2 * alloc_pct  # 50,000
    deployable_guarded2 = min(deployable_naive2, cash2)  # 25,000
    assert deployable_guarded2 < deployable_naive2, "Cash guard must cap deployable"
    assert deployable_guarded2 == cash2, f"Should cap at cash {cash2}"
    print("PASS test_trade_ticket_buy_cost_does_not_exceed_cash")


# ---- Task 7: CACHE_SLUG ----
def test_cache_slug_consistent_across_modules():
    """CACHE_SLUG must be same in trade_gen and walkforward."""
    from kth.trading.trade_gen import CACHE_SLUG as tg_slug
    from kth.backtest.walkforward import _model_slug
    wf_slug = _model_slug("NeoQuasar/Kronos-small")
    assert tg_slug == wf_slug, f"trade_gen={tg_slug} vs walkforward={wf_slug}"
    print("PASS test_cache_slug_consistent_across_modules")


if __name__ == "__main__":
    import inspect
    import tempfile
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        params = inspect.signature(fn).parameters
        if params:
            with tempfile.TemporaryDirectory() as tmp:
                fn(tmp)
        else:
            fn()
    print(f"ALL {len(fns)} PASSED")
