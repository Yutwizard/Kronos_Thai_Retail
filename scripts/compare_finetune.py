"""
Compare walk-forward backtest results: fine-tuned vs zero-shot for a given model.
Usage: venv/bin/python scripts/compare_finetune.py <model_name> <checkpoint_path>

Example: venv/bin/python scripts/compare_finetune.py thai_equity ./checkpoints/thai_equity/fold2
"""
import sys
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import (
    run_walkforward, precompute_forecasts, BacktestConfig,
)
from kth.data.universe import UNIVERSE


MODEL_TICKERS = {
    "thai_equity": [t for t,_,_ in UNIVERSE["thai_equity"]],
    "us_equity":   [t for t,_,_ in UNIVERSE["us_equity"]],
    "crypto":      [t for t,_,_ in UNIVERSE["crypto"]],
}


def compute_benchmark_metrics(r: "BacktestResult") -> dict:
    from kth.backtest.metrics import compute_sharpe, compute_max_drawdown
    bm_metrics = {}
    for name, eq in r.benchmarks.items():
        if len(eq) < 2:
            continue
        daily = eq.pct_change().dropna()
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (252 / len(eq)) - 1 if len(eq) > 0 else 0
        bm_metrics[name] = {
            "cagr": cagr,
            "sharpe": compute_sharpe(daily),
            "max_drawdown": compute_max_drawdown(eq),
        }
    return bm_metrics


def main():
    model_name = sys.argv[1]
    checkpoint_path = sys.argv[2]
    tickers = MODEL_TICKERS[model_name]

    config = BacktestConfig(
        start_date="2022-01-01", end_date="2024-12-31",
        lookback=400, pred_len=20, n_samples=10,
        position_sizing="equal",
    )

    # Zero-shot
    k_zs = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="auto")
    precompute_forecasts(
        k_zs, tickers,
        start_date=config.start_date, end_date=config.end_date,
        pred_len=config.pred_len, n_samples=config.n_samples,
        lookback=config.lookback,
    )
    r_zs = run_walkforward(config, k_zs, tickers)

    # Fine-tuned
    try:
        from kth.models.finetune import load_finetuned_checkpoint
        k_ft = load_finetuned_checkpoint(checkpoint_path, device="auto")
    except Exception as e:
        print(f"FAILED to load checkpoint: {e}")
        print(f"Path: {checkpoint_path}")
        print("Fine-tuned model not available — comparison skipped")
        return

    precompute_forecasts(
        k_ft, tickers,
        start_date=config.start_date, end_date=config.end_date,
        pred_len=config.pred_len, n_samples=config.n_samples,
        lookback=config.lookback,
    )
    r_ft = run_walkforward(config, k_ft, tickers)

    print(f"\n=== {model_name}: Fine-Tuned vs Zero-Shot ===")
    print(f"{'Metric':20s} {'Zero-Shot':>12s} {'Fine-Tuned':>12s} {'Δ':>8s}")
    print("-" * 54)
    for key in ["cagr", "sharpe", "sortino", "max_drawdown", "calmar", "trade_win_rate"]:
        zs_v = r_zs.metrics.get(key, 0) or 0
        ft_v = r_ft.metrics.get(key, 0) or 0
        delta = ft_v - zs_v
        print(f"{key:20s} {zs_v:>+10.2%} {ft_v:>+10.2%} {delta:>+7.2%}")

    # Statistical significance
    zs_t = r_zs.metrics.get("t_stat", 0) or 0
    zs_p = r_zs.metrics.get("p_value", 1) or 1
    ft_t = r_ft.metrics.get("t_stat", 0) or 0
    ft_p = r_ft.metrics.get("p_value", 1) or 1
    print(f"\nStatistical Significance (vs equal-weight benchmark):")
    print(f"  Zero-Shot:  t={zs_t:.2f} p={zs_p:.3f}")
    print(f"  Fine-Tuned: t={ft_t:.2f} p={ft_p:.3f}")

    bm = compute_benchmark_metrics(r_zs)
    print(f"\n  Benchmark Comparison (2022-2024):")
    print(f"  {'Benchmark':<15} {'CAGR':>10} {'Sharpe':>10} {'Max DD':>10}")
    print(f"  {'-'*45}")
    for name, m in bm.items():
        print(f"  {name:<15} {m['cagr']:>+9.2%} {m['sharpe']:>9.2f} {m['max_drawdown']:>9.2%}")
    print(f"  {'Strategy':<15} {r_zs.metrics.get('cagr',0):>+9.2%} {r_zs.metrics.get('sharpe',0):>9.2f} {r_zs.metrics.get('max_drawdown',0):>9.2%}")

    out_dir = Path(f"./data/backtest_results/{model_name}_ft")
    r_ft.save(str(out_dir))
    out_dir_zs = Path(f"./data/backtest_results/{model_name}_zs")
    r_zs.save(str(out_dir_zs))
    print(f"\nResults saved to {out_dir} and {out_dir_zs}")


if __name__ == "__main__":
    main()
