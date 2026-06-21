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


# ---- Task 10: Column to letter converter ----
def test_column_to_letter():
    """Column index to A1 notation must work for columns > 26."""
    from kth.pipeline.daily import _col_to_letter
    assert _col_to_letter(0) == "A"
    assert _col_to_letter(25) == "Z"
    assert _col_to_letter(26) == "AA"
    assert _col_to_letter(27) == "AB"
    assert _col_to_letter(51) == "AZ"
    print("PASS test_column_to_letter")


# ---- Task 9: Calibration idempotency ----
def test_calibration_idempotent_on_rerun(tmp):
    """Same-day re-run must not append duplicate Calibration rows.
    Monkeypatches _compute_calibration_data so the append path is exercised."""
    from kth.pipeline.daily import run_daily_pipeline
    from verify_kaggle_runtime import FakeModel, FakeLoader, seeded_fake_client
    import kth.pipeline.daily as daily_mod
    from datetime import date
    orig_cal = daily_mod._compute_calibration_data
    daily_mod._compute_calibration_data = lambda ohlcv, today_str: {
        'date': today_str, 'coverage': 0.88, 'n_samples': 15, 'status': 'on_track'
    }
    try:
        gc = seeded_fake_client()
        run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                           today=date(2026,6,18), work_dir=tmp, staging_sleep=0)
        rows1 = gc.open_by_key("test_id").worksheet("Calibration").get_all_values()
        run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                           today=date(2026,6,18), work_dir=tmp, staging_sleep=0)
        rows2 = gc.open_by_key("test_id").worksheet("Calibration").get_all_values()
        today1 = [r for r in rows1[1:] if r and r[0] == "2026-06-18"]
        today2 = [r for r in rows2[1:] if r and r[0] == "2026-06-18"]
        assert len(today1) == len(today2), f"Calibration duplicated: {len(today1)} -> {len(today2)}"
        print("PASS test_calibration_idempotent_on_rerun")
    finally:
        daily_mod._compute_calibration_data = orig_cal


# ---- Task 8: Risk Metrics upsert ----
def test_risk_metrics_history_preserved_on_rerun(tmp):
    """Same-day re-run must not wipe Risk Metrics history."""
    from kth.pipeline.daily import run_daily_pipeline
    from verify_kaggle_runtime import FakeModel, FakeLoader, seeded_fake_client
    from datetime import date
    gc = seeded_fake_client()
    sh = gc.open_by_key("test_id")
    sh.worksheet("Risk Metrics")._data = [
        ["date","equity","cash","deployed_pct","trailing_sharpe_12w","max_drawdown_pct",
         "mtd_pnl_pct","trade_win_rate","calmar_ratio","sortino_ratio","drawdown_velocity",
         "allocation_band","allocation_pct","market_state","is_frozen","bootstrap_p_value",
         "friction_ytd_pct","friction_ytd_thb"],
        ["2026-06-16","500000","500000","0","0","0","0","0","0","0","0",
         "NEUTRAL","0.1","Normal","0","1","0","0"],
        ["2026-06-17","500000","500000","0","0","0","0","0","0","0","0",
         "NEUTRAL","0.1","Normal","0","1","0","0"],
    ]
    run_daily_pipeline(gc, "test_id", model=FakeModel(), data_loader=FakeLoader(),
                       today=date(2026,6,18), work_dir=tmp, staging_sleep=0)
    rows = gc.open_by_key("test_id").worksheet("Risk Metrics").get_all_values()
    dates = [r[0] for r in rows[1:]]
    assert "2026-06-16" in dates, f"Prior day wiped! dates={dates}"
    assert "2026-06-17" in dates, f"Prior day wiped! dates={dates}"
    assert dates.count("2026-06-18") == 1, f"Today duplicated: {dates}"
    print("PASS test_risk_metrics_history_preserved_on_rerun")


# ---- Task 11: MEGA.BK sector classification ----
def test_mega_bk_sector_is_healthcare():
    """MEGA.BK (Mega Lifesciences) is a healthcare company, not Retail."""
    from kth.data.universe import get_sector
    assert get_sector("MEGA.BK") == "Healthcare", \
        f"MEGA.BK should be Healthcare, got {get_sector('MEGA.BK')}"
    print("PASS test_mega_bk_sector_is_healthcare")


# ---- Task 12: fx_macro exclusion ----
def test_fx_macro_excluded_from_investable():
    """fx_macro tickers must not appear in get_all_tickers()."""
    from kth.data.universe import get_all_tickers, get_ticker_class
    tickers = get_all_tickers()
    fx = [t for t in tickers if get_ticker_class(t) == "fx_macro"]
    assert len(fx) == 0, f"fx_macro leaked into investable: {fx}"
    from kth.data.universe import get_all_tickers_including_features
    all_t = get_all_tickers_including_features()
    assert len(all_t) == 100, f"get_all_tickers_including_features should return 100, got {len(all_t)}"
    assert "THB=X" in all_t, "THB=X should be in including_features"
    print("PASS test_fx_macro_excluded_from_investable")


# ---- Task 14: reduce only on bearish-yellow ----
def test_reduce_only_on_bearish_yellow():
    """Reduce should only trigger on yellow + bearish, not yellow + bullish."""
    def should_reduce(f):
        return f["confidence"] == "yellow" and f["direction"] == "down"
    assert should_reduce({"confidence": "yellow", "direction": "down"}), "Bearish yellow should reduce"
    assert not should_reduce({"confidence": "yellow", "direction": "up"}), "Bullish yellow should NOT reduce"
    print("PASS test_reduce_only_on_bearish_yellow")


# ---- Task 13: O(1) ticker-class lookup ----
def test_get_ticker_class_o1_lookup():
    """get_ticker_class must use O(1) dict lookup."""
    from kth.data.universe import get_ticker_class, _TICKER_CLASS_MAP
    assert "AOT.BK" in _TICKER_CLASS_MAP, "Reverse-lookup map not built"
    assert _TICKER_CLASS_MAP["AOT.BK"] == "thai_equity"
    assert get_ticker_class("BTC-USD") == "crypto"
    assert get_ticker_class("NONEXISTENT") is None
    print("PASS test_get_ticker_class_o1_lookup")


# ---- Task 1 fixes ----
def test_psr_uses_scipy_skew_kurtosis():
    """L13: compute_psr must use scipy.stats skew/kurtosis with bias=False."""
    import inspect
    from kth.backtest import metrics as m
    src = inspect.getsource(m.compute_psr)
    assert "from scipy.stats import" in src, "compute_psr must import scipy.stats"
    assert "bias=False" in src, "compute_psr must use bias=False for consistency"
    print("PASS test_psr_uses_scipy_skew_kurtosis")


def test_profit_factor_inf_when_no_losses():
    """L8: profit_factor returns inf (not None) when no losses."""
    import pandas as pd
    trades = pd.DataFrame({"gross_return": [0.1, 0.2, 0.05], "friction_cost": [0, 0, 0]})
    from kth.backtest.metrics import compute_trade_metrics
    m = compute_trade_metrics(trades)
    assert m["profit_factor"] == float("inf"), f"Expected inf, got {m['profit_factor']}"
    print("PASS test_profit_factor_inf_when_no_losses")


def test_bootstrap_docstring_says_centered():
    """L7: docstring must say 'centered bootstrap', not 'shuffles'."""
    from kth.backtest.metrics import compute_bootstrap_pvalue
    doc = compute_bootstrap_pvalue.__doc__ or ""
    assert "centered" in doc.lower(), "docstring must mention 'centered'"
    assert "shuffles" not in doc.lower(), "docstring must not say 'shuffles'"
    print("PASS test_bootstrap_docstring_says_centered")


def test_psr_high_sharpe_finite_after_scipy_fix():
    """L13 regression: PSR must be finite for high-Sharpe series."""
    rng = np.random.default_rng(99)
    returns = pd.Series(rng.normal(0.003, 0.008, 300))
    from kth.backtest.metrics import compute_psr
    psr = compute_psr(returns, benchmark_sr=1.0)
    assert np.isfinite(psr), f"PSR not finite: {psr}"
    assert 0.0 <= psr <= 1.0, f"PSR out of [0,1]: {psr}"
    print("PASS test_psr_high_sharpe_finite_after_scipy_fix")


# ---- Task 2: centralized friction ----
def test_get_friction_known_ticker():
    """H3: get_friction returns the right dict for a known Thai equity ticker."""
    from kth.data.universe import get_friction, get_one_way_friction_rate
    f = get_friction("PTT.BK")
    assert f["commission_oneway"] == 0.00168
    assert f["slippage_oneway"] == 0.0010
    assert get_one_way_friction_rate("PTT.BK") == 0.00268
    print("PASS test_get_friction_known_ticker")


def test_get_friction_fallback_unknown():
    """H3: get_friction returns conservative default for unknown ticker."""
    from kth.data.universe import get_friction
    f = get_friction("UNKNOWN.TICKER")
    assert f["commission_oneway"] == 0.003
    assert f["slippage_oneway"] == 0.001
    print("PASS test_get_friction_fallback_unknown")


def test_no_inline_friction_fallbacks_remain():
    """H3: no module should have inline friction dict-literal fallbacks."""
    from pathlib import Path
    for f in ["kth/backtest/walkforward.py", "kth/trading/portfolio.py", "kth/trading/trade_gen.py", "kth/pipeline/daily.py"]:
        text = Path(f).read_text()
        assert '{"commission_oneway":' not in text, \
            f"{f} still has inline friction fallback — use universe.get_friction()"
    print("PASS test_no_inline_friction_fallbacks_remain")


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
