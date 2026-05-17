"""
Phase 1 end-to-end demo: forecast 5 tickers on CPU → build report → save HTML.

5 representative tickers across asset classes:
  AAPL    — US large-cap equity
  PTT.BK  — Thai blue-chip equity
  GLD     — commodity (gold ETF)
  BTC-USD — crypto
  ^SET.BK — Thai index benchmark
"""
import pandas as pd
from pathlib import Path

from kth.models.kronos_wrapper import KronosTH
from kth.data.loader import load_cached
from kth.utils.report import build_report_table, render_html

TICKERS = ["AAPL", "PTT.BK", "GLD", "BTC-USD", "^SET.BK"]

def main():
    # 1. Load model (CPU) — device="cpu" required: default is "auto" which uses CUDA if present
    print("Loading Kronos-small on CPU...")
    k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cpu")
    print(f"  Model: {k.model_name}")
    print(f"  Device: {k.device}")

    # 2. Forecast batch (n_samples=5 for CPU speed; increase to 50 on GPU)
    print(f"\nForecasting {len(TICKERS)} tickers (n_samples=5, CPU mode)...")
    forecasts = k.forecast_batch(TICKERS, pred_lens=[5, 20], n_samples=5)
    print(f"  Done. {len(forecasts)} tickers returned.")

    # 3. Build last_closes from cached data
    last_closes = {}
    for t in TICKERS:
        try:
            df = load_cached(t)
            last_closes[t] = float(df["close"].iloc[-1])
            print(f"  {t:10s} close: {last_closes[t]:.2f}")
        except FileNotFoundError:
            print(f"  {t:10s} WARNING: no cache — run scripts/download_data.py first")

    # 4. Build report tables
    adj_table, raw_table = build_report_table(
        forecasts, last_closes, long_threshold=0.01
    )

    print(f"\n=== Confidence-Adjusted Report ===")
    print(adj_table[["Ticker", "Class", "1d p50", "5d p50", "20d p50", "Signal", "Score"]].to_string(index=False))

    # 5. Save HTML report
    report_path = Path("./reports") / f"{pd.Timestamp.now().strftime('%Y-%m-%d')}_demo.html"
    html_path = render_html(
        (adj_table, raw_table),
        str(report_path),
        k.model_name,
        pd.Timestamp.now(),
    )
    print(f"\nHTML report saved to: {html_path}")

    # 6. Quick validation
    assert len(adj_table) == len(TICKERS), f"Expected {len(TICKERS)} rows"
    assert not (adj_table["1d p50"] == 0).all(), "1d p50 should not be all zero!"
    print("\n=== Demo PASSED ===")


if __name__ == "__main__":
    main()
