"""Wayfinder ticket .scratch/optimize-entry-exit/issues/01: max_holding_days +
cooldown sweep, thai_equity, n_samples=50, per-year 2023-2026.

Reads entirely from the already-populated data/forecast_cache/NeoQuasar_Kronos-small/
cache (spans 2020-01-01 to 2026-07-25) -- no new Kronos inference is run. A
lightweight stub stands in for the KronosTH instance since run_walkforward()
only reads kronos_th.model_name (to derive the cache directory slug).

Grid: max_holding_days in {None(baseline), 20, 40, 60, 90} x cooldown_days=5
(fixed, only applies when max_holding_days is set) x years {2023,2024,2025,2026}
= 20 runs total.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from kth.data.universe import UNIVERSE
from kth.backtest.walkforward import BacktestConfig, run_walkforward

TICKERS = [x for x, _, _ in UNIVERSE["thai_equity"]]

YEARS = {
    "2023": ("2023-01-01", "2023-12-31"),
    "2024": ("2024-01-01", "2024-12-31"),
    "2025": ("2025-01-01", "2025-12-31"),
    "2026": ("2026-01-01", "2026-07-25"),
}

GRID = [
    ("baseline", None),
    ("cap20", 20),
    ("cap40", 40),
    ("cap60", 60),
    ("cap90", 90),
]

OUT_ROOT = Path("./data/backtest_results/max_holding_sweep")


@dataclass
class _StubModel:
    model_name: str = "NeoQuasar/Kronos-small"


def main():
    stub = _StubModel()
    print(f"Universe: {len(TICKERS)} thai_equity tickers")
    print(f"Grid: {[name for name, _ in GRID]} x years {list(YEARS)} = {len(GRID) * len(YEARS)} runs\n")

    summary_rows = []
    t_start = time.time()

    for config_name, max_holding_days in GRID:
        cooldown_days = 5 if max_holding_days is not None else None
        for year, (start, end) in YEARS.items():
            t0 = time.time()
            config = BacktestConfig(
                start_date=start, end_date=end,
                lookback=400, pred_len=20, n_samples=50,
                position_sizing="equal", max_positions=5,
                min_ticker_history=20,
                max_holding_days=max_holding_days,
                cooldown_days=cooldown_days,
            )
            result = run_walkforward(config, stub, TICKERS)
            elapsed = time.time() - t0

            out_dir = OUT_ROOT / f"{config_name}_{year}"
            out_dir.mkdir(parents=True, exist_ok=True)
            result.save(str(out_dir))

            m = result.metrics
            row = {
                "config": config_name,
                "max_holding_days": max_holding_days,
                "cooldown_days": cooldown_days,
                "year": year,
                "cagr": m.get("cagr"),
                "total_return": m.get("total_return"),
                "sharpe": m.get("sharpe"),
                "sortino": m.get("sortino"),
                "max_drawdown": m.get("max_drawdown"),
                "calmar": m.get("calmar"),
                "psr_0_5": m.get("psr_0_5"),
                "psr_1_0": m.get("psr_1_0"),
                "t_stat": m.get("t_stat"),
                "p_value": m.get("p_value"),
                "annual_turnover": m.get("annual_turnover"),
                "total_friction_paid": m.get("total_friction_paid"),
                "avg_holding_period": m.get("avg_holding_period"),
                "trade_win_rate": m.get("trade_win_rate"),
                "n_trades": len(result.trades) if result.trades is not None else 0,
            }
            summary_rows.append(row)
            print(
                f"[{config_name:8s} {year}] elapsed={elapsed:5.1f}s  "
                f"CAGR={row['cagr']:+.2%}  Sharpe={row['sharpe']:.2f}  "
                f"MaxDD={row['max_drawdown']:.2%}  PSR0.5={row['psr_0_5']:.3f}  "
                f"p={row['p_value']:.3f}  friction={row['total_friction_paid']:.4f}  "
                f"turnover={row['annual_turnover']:.2f}  avg_hold={row['avg_holding_period']:.1f}d  "
                f"trades={row['n_trades']}",
                flush=True,
            )

    total_elapsed = time.time() - t_start
    print(f"\nTotal sweep time: {total_elapsed/60:.1f} min")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    with open(OUT_ROOT / "summary.json", "w") as f:
        json.dump(summary_rows, f, indent=2)
    print(f"Summary written to {OUT_ROOT / 'summary.json'}")


if __name__ == "__main__":
    main()
