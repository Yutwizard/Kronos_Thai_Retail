"""
Build notebooks/05_decision_report.ipynb — Daily Decision Report (Layer 5).

5 code cells:
  0. Config + imports
  1. Load model (zero-shot or fine-tuned)
  2. Generate forecasts (batch all tickers, cache)
  3. Build report DataFrame (22+ columns)
  4. Display per REPORT_MODE + disclaimers
"""

import json
from pathlib import Path

NOTEBOOK_DIR = Path(__file__).resolve().parent.parent / "notebooks"

CELL_0 = """\
import pandas as pd
import numpy as np
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path("kronos_repo")))

from kth.data.universe import UNIVERSE, FRICTION, get_all_tickers, get_ticker_class, get_display_name
from kth.data.loader import load_cached
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts

REPORT_MODE = "morning"   # "morning" | "trader" | "quant"
MODEL_TYPE  = "zero-shot" # "zero-shot" | "fine-tuned"
REPORT_DATE = pd.Timestamp.now().strftime("%Y-%m-%d")

if MODEL_TYPE == "zero-shot":
    CACHE_SLUG = "NeoQuasar_Kronos-small"
else:
    CACHE_SLUG = "./checkpoints/us_equity/fold2/best".replace("/", "_")

BACKTEST_METRICS = {
    "thai_equity": {"sharpe": 1.40, "cagr": 0.3144, "max_dd": -0.1797},
    "crypto":      {"sharpe": 0.52, "cagr": 0.1645, "max_dd": -0.6858},
    "us_equity":   {"sharpe": 0.97, "cagr": 0.3034, "max_dd": -0.4377},
    "thai_index":  {"sharpe": -0.63,"cagr": -0.0529,"max_dd": -0.2564},
    "etf_global":  {"sharpe": 0.44, "cagr": 0.0833, "max_dd": -0.2450},
    "commodity":   {"sharpe": None, "cagr": None, "max_dd": None},
    "bond_proxy":  {"sharpe": None, "cagr": None, "max_dd": None},
    "reit":        {"sharpe": None, "cagr": None, "max_dd": None},
    "fx_macro":    {"sharpe": None, "cagr": None, "max_dd": None},
}"""

CELL_1 = """\
if MODEL_TYPE == "zero-shot":
    th = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
else:
    from kth.models.finetune import load_finetuned_checkpoint
    th = load_finetuned_checkpoint("./checkpoints/us_equity/fold2/best", device="cuda")
    FT_ONLY_CLASS = "us_equity"

print(f"Model: {MODEL_TYPE} | Device: cuda")"""

CELL_2 = """\
today_dir = Path(f"data/forecast_cache/{CACHE_SLUG}/{REPORT_DATE}")
if today_dir.exists():
    shutil.rmtree(today_dir)

tickers = get_all_tickers()
if MODEL_TYPE == "fine-tuned":
    tickers = [t for t in tickers if get_ticker_class(t) == FT_ONLY_CLASS]
    print(f"FT mode: restricted to {FT_ONLY_CLASS} ({len(tickers)} tickers)")

precompute_forecasts(th, tickers,
    start_date=REPORT_DATE, end_date=REPORT_DATE,
    pred_len=20, n_samples=10, lookback=400)
print(f"Done. Cache: data/forecast_cache/{CACHE_SLUG}/{REPORT_DATE}/")"""

CELL_3 = """\
cache_dir = Path(f"data/forecast_cache/{CACHE_SLUG}/{REPORT_DATE}")

rows = []
skipped = []
for ticker in tickers:
    safe = ticker.replace("^", "_").replace("=", "_")
    parquet_file = cache_dir / f"{safe}.parquet"
    if not parquet_file.exists():
        skipped.append(ticker)
        continue

    fc = pd.read_parquet(parquet_file)
    ticker_data = load_cached(ticker)
    current_close = float(ticker_data["close"].iloc[-1])
    hist_vol = float(ticker_data["close"].pct_change().tail(252).std())

    cls = get_ticker_class(ticker) or "unknown"
    bm = BACKTEST_METRICS.get(cls, {})
    frac = FRICTION.get(cls, {"commission_oneway": 0, "slippage_oneway": 0})
    friction_rt = frac["commission_oneway"] * 2 + frac["slippage_oneway"] * 2

    p50_close = float(fc["p50"].iloc[-1])
    p5_close  = float(fc["p5"].iloc[-1])
    p95_close = float(fc["p95"].iloc[-1])
    mean_close = float(fc["mean"].iloc[-1])

    exp_return = (p50_close - current_close) / current_close
    band_width = (p95_close - p5_close) / current_close

    if band_width <= 0.10:
        confidence = "green"
    elif band_width <= 0.30:
        confidence = "yellow"
    else:
        confidence = "red"

    rows.append({
        "ticker": ticker,
        "name": get_display_name(ticker),
        "class": cls,
        "current_close": current_close,
        "p5_close": p5_close,
        "p25_close": float(fc["p25"].iloc[-1]),
        "p50_close": p50_close,
        "p75_close": float(fc["p75"].iloc[-1]),
        "p95_close": p95_close,
        "mean_close": mean_close,
        "expected_return_p50": exp_return,
        "expected_return_mean": (mean_close - current_close) / current_close,
        "band_width": band_width,
        "confidence": confidence,
        "direction": "up" if exp_return > 0 else "down",
        "hist_vol_1y": hist_vol,
        "risk_adj_return": exp_return / (hist_vol + 1e-6),
        "rank_score": exp_return / max(band_width, 0.001),
        "market_sharpe": bm.get("sharpe"),
        "market_cagr": bm.get("cagr"),
        "market_max_dd": bm.get("max_dd"),
        "friction_rt": friction_rt,
        "net_return": exp_return - friction_rt,
        "report_date": REPORT_DATE,
        "model": MODEL_TYPE,
    })

df = pd.DataFrame(rows)
print(f"{len(df)}/{len(tickers)} tickers, {len(skipped)} skipped")
if skipped:
    print(f"  Skipped: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")"""

CELL_4 = """\
def fmt_pct(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x*100:+.2f}%"

def fmt_ratio(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:.2f}"

def fmt_flag(confidence):
    return {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(confidence, "⚪")

median_band = df["band_width"].median()
all_red_day = median_band > 0.30

if all_red_day:
    print("⚠️  HIGH UNCERTAINTY DAY — sorting by return magnitude only.")
    df_view = df.assign(_abs_ret=df["expected_return_p50"].abs()).sort_values("_abs_ret", ascending=False)
else:
    df_view = df.copy()

if REPORT_MODE == "morning":
    cols = ["ticker", "name", "current_close", "expected_return_p50", "band_width", "confidence", "rank_score", "direction"]
    view = df_view[cols].copy()
    view["flag"] = view["confidence"].apply(fmt_flag)
    view["P50%"] = view["expected_return_p50"].apply(fmt_pct)
    view["Band"] = view["band_width"].apply(fmt_pct)
    view["Score"] = view["rank_score"].apply(fmt_ratio)
    if all_red_day:
        top = view.head(20)
    else:
        top = view.sort_values("rank_score", ascending=False).head(10)
        bottom = view.sort_values("rank_score", ascending=True).head(10)
        top = pd.concat([top, bottom], ignore_index=True)
    print("=== MORNING REPORT — TOP 10 BULLISH + BOTTOM 10 BEARISH ===")
    display_cols = ["flag", "ticker", "name", "current_close", "P50%", "Band", "Score", "direction"]
    display(top[display_cols])
elif REPORT_MODE == "trader":
    view = df_view[["ticker", "name", "class", "current_close", "expected_return_p50",
                     "p5_close", "p95_close", "market_sharpe", "friction_rt", "net_return", "confidence"]].copy()
    view["flag"] = view["confidence"].apply(fmt_flag)
    view["P50%"] = view["expected_return_p50"].apply(fmt_pct)
    view["Net%"] = view["net_return"].apply(fmt_pct)
    view = view.sort_values(["class", "net_return"], ascending=[True, False])
    print("=== TRADER REPORT — SORTED BY CLASS / NET RETURN ===")
    display_cols = ["flag", "ticker", "name", "class", "current_close", "P50%", "Net%",
                    "p5_close", "p95_close", "market_sharpe", "friction_rt"]
    display(view[display_cols])
elif REPORT_MODE == "quant":
    view = df_view[["ticker", "name", "class", "current_close", "expected_return_p50",
                     "expected_return_mean", "band_width", "risk_adj_return", "rank_score",
                     "market_cagr", "market_max_dd", "hist_vol_1y", "confidence"]].copy()
    view["flag"] = view["confidence"].apply(fmt_flag)
    view["P50%"] = view["expected_return_p50"].apply(fmt_pct)
    view["Mean%"] = view["expected_return_mean"].apply(fmt_pct)
    view["RAR"] = view["risk_adj_return"].apply(fmt_ratio)
    view["Score"] = view["rank_score"].apply(fmt_ratio)
    view = view.sort_values(["class", "risk_adj_return"], ascending=[True, False])
    print("=== QUANT REPORT — SORTED BY CLASS / RISK-ADJUSTED RETURN ===")
    display_cols = ["flag", "ticker", "name", "class", "current_close", "P50%", "Mean%", "RAR",
                    "Score", "market_cagr", "market_max_dd", "hist_vol_1y"]
    display(view[display_cols])
else:
    print(f"Unknown REPORT_MODE: {REPORT_MODE}. Choose: morning, trader, quant")

print()
print(f"Report generated at {pd.Timestamp.now()} for {REPORT_DATE}")
print(f"Tickers in report: {len(df)} | Model: {MODEL_TYPE}")
print()
print("DISCLAIMERS")
print("This is research output, not financial advice.")
print("Kronos is a forecasting model — past performance is not indicative of future results.")
print("All backtest metrics are from walk-forward evaluation on 2022-2024 data.")
print("Survivorship bias: the universe includes only currently-listed tickers.")
print(f"Forecasts generated at {REPORT_DATE} using {MODEL_TYPE} Kronos-small.")"""


def _split_lines(source: str) -> list[str]:
    return [line + "\n" for line in source.split("\n")]


def make_code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _split_lines(source),
    }


def build_notebook() -> dict:
    cells = [
        make_code_cell(CELL_0),
        make_code_cell(CELL_1),
        make_code_cell(CELL_2),
        make_code_cell(CELL_3),
        make_code_cell(CELL_4),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


def main() -> None:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTEBOOK_DIR / "05_decision_report.ipynb"
    nb = build_notebook()
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"Written: {path} ({len(nb['cells'])} cells, {len(nb['cells'][0]['source'])} lines in cell 0)")


if __name__ == "__main__":
    main()
