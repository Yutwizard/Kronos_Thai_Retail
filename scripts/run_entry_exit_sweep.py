"""Entry/exit variants on clean forecasts: 2024 (point-in-time cache) and the live window
2026-06-22..2026-09-18 (live-pipeline folders in data/forecast_cache). Ticket 07.

Usage: venv/bin/python scripts/run_entry_exit_sweep.py
"""
from dataclasses import dataclass

from kth.backtest.walkforward import BacktestConfig, run_walkforward
from kth.data.universe import UNIVERSE

TICKERS = [x for x, _, _ in UNIVERSE["thai_equity"]]
VARIANTS = {
    "baseline (1%/0.5%, min hold 5)": {},
    "V1 entry 5% / buffer 2%": dict(long_threshold=0.05, entry_buffer=0.02),
    "V2 min hold 20d": dict(min_holding_days=20),
    "V3 entry 3%/1% + min hold 20d": dict(long_threshold=0.03, entry_buffer=0.01, min_holding_days=20),
    "V4 entry 8% / buffer 3%": dict(long_threshold=0.08, entry_buffer=0.03),
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
