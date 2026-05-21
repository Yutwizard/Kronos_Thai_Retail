"""
Phase 2 — Generate daily decision report with calibration-based confidence flags.

Requires: scripts/run_backtest.py completed (BacktestResult saved to disk).
          scripts/download_data.py run recently (data not stale).
"""
import pandas as pd
from datetime import date
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.data.loader import load_cached
from kth.data.universe import get_all_tickers
from kth.backtest.walkforward import BacktestResult
from kth.utils.report import build_report_table, render_html


OUTPUT_DIR = Path("./data/backtest_results/2022-2024")


def main():
    # 1. Load model (auto-detect GPU/CPU)
    print("Loading Kronos-small (auto device)...")
    k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="auto")
    print(f"  Model: {k.model_name}")

    # 2. Run forecasts on all 51 tickers (today's prices)
    tickers = get_all_tickers()
    print(f"\nForecasting {len(tickers)} tickers (n_samples=50)...")
    forecasts = k.forecast_batch(tickers, pred_lens=[5, 20], n_samples=50)
    print(f"  Done. {len(forecasts)} tickers returned.")

    # 3. Build last_closes from latest cached data
    last_closes = {}
    for t in tickers:
        try:
            df = load_cached(t)
            last_closes[t] = float(df["close"].iloc[-1])
        except FileNotFoundError:
            print(f"  WARNING: {t} not cached — skipping")

    # 4. Load backtest result for calibration-based confidence
    br = None
    if (OUTPUT_DIR / "metrics.json").exists():
        print(f"\nLoading backtest results from {OUTPUT_DIR}...")
        br = BacktestResult.load(str(OUTPUT_DIR))
        print(f"  Sharpe: {br.metrics.get('sharpe', 'N/A')}")
        print(f"  Trade win rate: {br.metrics.get('trade_win_rate', 'N/A')}")
    else:
        print("\nNo backtest results — using band-width confidence fallback.")

    # 5. Build report tables
    adj_table, raw_table = build_report_table(
        forecasts, last_closes, backtest_result=br, long_threshold=0.01
    )

    # 6. Print top 10 by score
    print(f"\n=== TOP 10 BY CONFIDENCE-ADJUSTED SCORE ===")
    print(adj_table.head(10)[["Ticker", "Class", "20d p50", "Signal", "Confidence", "Score"]].to_string(index=False))

    # 7. Save HTML
    today = date.today().isoformat()
    html_path = render_html(
        (adj_table, raw_table),
        f"./reports/{today}.html",
        k.model_name,
        pd.Timestamp.now(),
    )
    print(f"\nHTML report saved to: {html_path}")

    print("\n=== DAILY REPORT COMPLETE ===")


if __name__ == "__main__":
    main()
