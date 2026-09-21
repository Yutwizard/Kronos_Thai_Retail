"""Stop-loss variants (baseline entry rules) on clean forecasts: 2024 (point-in-time cache) and the live window
2026-06-22..2026-09-18 (live-pipeline folders in data/forecast_cache). Ticket 07 (stops).

Usage: venv/bin/python scripts/run_stop_loss_sweep.py
"""
from dataclasses import dataclass

from kth.backtest.walkforward import BacktestConfig, run_walkforward
from kth.data.universe import UNIVERSE

TICKERS = [x for x, _, _ in UNIVERSE["thai_equity"]]
VARIANTS = {
    "baseline (no stop)": {},
    "S1 fixed stop -8%": dict(stop_loss=0.08),
    "S2 fixed stop -12%": dict(stop_loss=0.12),
    "S3 trailing stop -12%": dict(trailing_stop=0.12),
}
WINDOWS = {
    "2024 (PIT cache)": ("2024-01-01", "2024-12-31", "./data/forecast_cache_pit"),
    "live 2026-06-22..09-18": ("2026-06-22", "2026-09-18", "./data/forecast_cache"),
}


@dataclass
class _Stub:
    model_name: str = "NeoQuasar/Kronos-small"


for wname, (s, e, cache) in WINDOWS.items():
    print(f"\n=== {wname} ===")
    print(f"{'variant':34s} {'total':>8s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>7s} {'vs EW':>8s} {'turn':>6s} {'fric':>6s} {'p':>6s}")
    for vname, kw in VARIANTS.items():
        cfg = BacktestConfig(start_date=s, end_date=e, lookback=400, pred_len=20, n_samples=50,
                             position_sizing="equal", max_positions=5, min_ticker_history=20,
                             forecast_cache_dir=cache, **kw)
        m = run_walkforward(cfg, _Stub(), TICKERS).metrics
        print(f"{vname:34s} {m['total_return']:+8.1%} {m['cagr']:+8.1%} {m['sharpe']:7.2f} {m['max_drawdown']:7.1%} "
              f"{m['alpha_vs_equal_weight']:+8.1%} {m['annual_turnover']:6.1f} {m['total_friction_paid']:6.1%} {m['p_value']:6.3f}", flush=True)
