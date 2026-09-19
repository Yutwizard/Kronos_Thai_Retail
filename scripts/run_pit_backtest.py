"""Run the baseline backtest for one year on the point-in-time forecast cache and
compare it with the stored (look-ahead) authoritative result.

Ticket .scratch/future-plan/00. Reads data/forecast_cache_pit (see
scripts/regenerate_forecast_sample.py). Refuses to run if any business day in the
year is missing forecasts, since run_walkforward silently skips absent files.

Usage: venv/bin/python scripts/run_pit_backtest.py 2024
Output: data/backtest_results/pit/thai_equity_{year}_n50/
"""
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kth.backtest.walkforward import BacktestConfig, run_walkforward
from kth.data.universe import UNIVERSE

TICKERS = [x for x, _, _ in UNIVERSE["thai_equity"]]
YEARS = {
    "2023": ("2023-01-01", "2023-12-31"),
    "2024": ("2024-01-01", "2024-12-31"),
    "2025": ("2025-01-01", "2025-12-31"),
    "2026": ("2026-01-01", "2026-07-25"),
}
PIT_CACHE = "./data/forecast_cache_pit"
SLUG = "NeoQuasar_Kronos-small"
MIN_TICKERS_PER_DAY = 45
KEYS = ["cagr", "sharpe", "max_drawdown", "p_value", "alpha_vs_equal_weight",
        "annual_turnover", "total_friction_paid"]


@dataclass
class _StubModel:
    model_name: str = "NeoQuasar/Kronos-small"


def _assert_cache_complete(start: str, end: str) -> None:
    root = Path(PIT_CACHE) / SLUG
    short = []
    for day in pd.bdate_range(start, end):
        d = root / day.strftime("%Y-%m-%d")
        n = len(list(d.glob("*.parquet"))) if d.exists() else 0
        if n < MIN_TICKERS_PER_DAY:
            short.append((day.date(), n))
    if short:
        raise SystemExit(f"Point-in-time cache incomplete for {len(short)} business days, e.g. {short[:5]}")


def main(year: str) -> None:
    start, end = YEARS[year]
    _assert_cache_complete(start, end)
    config = BacktestConfig(
        start_date=start, end_date=end, lookback=400, pred_len=20, n_samples=50,
        position_sizing="equal", max_positions=5, min_ticker_history=20,
        forecast_cache_dir=PIT_CACHE,
    )
    result = run_walkforward(config, _StubModel(), TICKERS)
    out = Path(f"./data/backtest_results/pit/thai_equity_{year}_n50")
    result.save(str(out))

    stored = json.loads(Path(f"./data/backtest_results/thai_equity_{year}_n50/metrics.json").read_text())
    print(f"\n{year}: point-in-time baseline vs stored (look-ahead) authoritative run")
    print(f"{'metric':24s} {'point-in-time':>14s} {'stored':>14s}")
    for k in KEYS:
        new, old = result.metrics.get(k), stored.get(k)
        fmt = lambda v: "n/a" if v is None else f"{v:14.4f}"
        print(f"{k:24s} {fmt(new):>14s} {fmt(old):>14s}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2024")
