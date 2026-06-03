# Daily Decision Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a daily report answering "what does the model expect and how much should I trust it?" — an inline Markdown table in Jupyter plus a standalone HTML report with calibration-based confidence flags.

**Architecture:** Two utility modules: `plot.py` (reusable matplotlib chart functions) and `report.py` (signal table builder, Markdown/HTML renderer, confidence flags derived from `BacktestResult.per_class_attribution`). The notebook orchestrates: load model → forecast batch → build table → display + save.

**Tech Stack:** Python 3.10+, `matplotlib`, `pandas`, `numpy`

**Depends on:** Spec A (`KronosTH`, `ForecastResult`), Spec B (`BacktestResult.per_class_attribution` for calibration).

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `kth/utils/__init__.py` | Package marker |
| Create | `kth/utils/plot.py` | `plot_forecast_band`, `plot_equity_curve`, `plot_attribution`, `plot_drawdown` |
| Create | `kth/utils/report.py` | `build_report_table`, `render_markdown`, `render_html` |
| Create | `notebooks/05_decision_report.ipynb` | Daily report notebook |
| Create | `reports/.gitkeep` | Output directory marker |
| Create | `.gitignore` | Add `reports/*.html` pattern |

---

### Task 1: `plot.py` — reusable chart functions

**Files:**
- Create: `kth/utils/__init__.py`
- Create: `kth/utils/plot.py`

- [ ] **Step 1: Write failing test scaffold for plot functions**

```python
# tests/utils/test_plot.py
import sys; sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for testing

from kth.utils.plot import plot_forecast_band, plot_equity_curve, plot_attribution, plot_drawdown

print("Import OK — all plot functions defined")
print("PASS")
```

Run: `python tests/utils/test_plot.py`
Expected: `FAIL` with `ModuleNotFoundError`

- [ ] **Step 2: Implement `plot.py`**

```python
# kth/utils/__init__.py
"""Kronos-TH utilities: plotting and reporting."""
```

```python
# kth/utils/plot.py
"""Reusable matplotlib chart functions for notebooks 02–05."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


def plot_forecast_band(
    ticker: str,
    historical: pd.DataFrame,
    result,  # ForecastResult
    pred_len: int = 20,
    n_history_days: int = 60,
):
    """
    Actual close (last n_history_days) + shaded P5/P95 band + P50 line for pred_len.
    Returns matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    # Historical
    hist = historical.tail(n_history_days).copy()
    hist_dates = pd.to_datetime(hist["timestamps"])
    ax.plot(hist_dates, hist["close"], color="black", linewidth=1.5, label="Historical close")

    # Forecast
    h = result.horizons[pred_len]
    fc_dates = pd.to_datetime(h.summary["timestamps"])

    # Extend x-axis: last historical date → forecast dates
    last_hist_date = hist_dates.iloc[-1]
    x_fc = [last_hist_date] + list(fc_dates)
    last_close = float(hist["close"].iloc[-1])

    # P50 line
    p50 = np.concatenate([[last_close], h.summary["p50"].values])
    ax.plot(x_fc, p50, color="#2196F3", linewidth=1.5, label=f"P50 ({pred_len}d)")

    # P5/P95 band
    p5 = np.concatenate([[last_close], h.summary["p5"].values])
    p95 = np.concatenate([[last_close], h.summary["p95"].values])
    ax.fill_between(x_fc, p5, p95, alpha=0.15, color="#2196F3", label="P5–P95 band")

    ax.set_title(f"{ticker} — {pred_len}-day Forecast Band")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)

    return fig


def plot_equity_curve(
    backtest_result,  # BacktestResult
    include_benchmarks: bool = True,
):
    """Net equity curve vs benchmarks. Gross curve as dashed line."""
    fig, ax = plt.subplots(figsize=(12, 5))

    equity = backtest_result.equity_curve
    ax.plot(equity.index, equity.values, color="#2196F3", linewidth=1.5, label="Strategy (net)")

    gross = backtest_result.gross_equity_curve
    ax.plot(gross.index, gross.values, color="#2196F3", linewidth=1.0, linestyle="--", alpha=0.6, label="Strategy (gross)")

    if include_benchmarks:
        colors = {"SET": "#FF9800", "SPY": "#4CAF50", "60_40": "#9C27B0", "equal_weight": "#607D8B"}
        for name, curve in backtest_result.benchmarks.items():
            color = colors.get(name, "gray")
            ax.plot(curve.index, curve.values, color=color, linewidth=1.0, alpha=0.7, label=name)

    ax.set_title("Portfolio Equity Curve")
    ax.set_ylabel("Portfolio Value (normalized)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)

    return fig


def plot_attribution(backtest_result):
    """Horizontal bar chart: per-class P&L contribution."""
    fig, ax = plt.subplots(figsize=(10, 6))

    attr = backtest_result.per_class_attribution
    if attr.empty:
        ax.text(0.5, 0.5, "No trades — no attribution", ha="center", va="center")
        return fig

    classes = attr["asset_class"].tolist()
    pnl = attr["pnl"].tolist()
    friction = attr["friction_paid"].tolist()

    y_pos = range(len(classes))
    ax.barh(y_pos, pnl, height=0.6, color="#4CAF50", alpha=0.7, label="Gross P&L")
    ax.barh(y_pos, [-f for f in friction], height=0.6, color="#F44336", alpha=0.7, label="Friction paid")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(classes)
    ax.set_xlabel("P&L Contribution")
    ax.set_title("Per-Class Attribution — Gross P&L vs Friction")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.axvline(0, color="black", linewidth=0.5)

    return fig


def plot_drawdown(backtest_result):
    """Drawdown series with shaded underwater periods."""
    fig, ax = plt.subplots(figsize=(12, 5))

    equity = backtest_result.equity_curve
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak

    ax.fill_between(drawdown.index, drawdown.values, 0,
                    where=(drawdown < 0), color="#F44336", alpha=0.3, label="Drawdown")
    ax.plot(drawdown.index, drawdown.values, color="#F44336", linewidth=0.8)

    ax.set_title("Drawdown Series")
    ax.set_ylabel("Drawdown (%)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.grid(True, alpha=0.3)

    return fig
```

- [ ] **Step 3: Verify import and shape**

Run: `python tests/utils/test_plot.py`
Expected: `Import OK — all plot functions defined` / `PASS`

- [ ] **Step 4: Commit**

```bash
git add kth/utils/__init__.py kth/utils/plot.py tests/utils/test_plot.py
git commit -m "feat: add plot.py with forecast_band, equity_curve, attribution, drawdown charts"
```

---

### Task 2: `report.py` — signal table builder + renderers

**Files:**
- Create: `kth/utils/report.py`

- [ ] **Step 1: Write failing test**

```python
# tests/utils/test_report.py
import sys; sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from kth.utils.report import build_report_table, render_markdown

# Mock ForecastResult
class MockHorizon:
    def __init__(self, summary_df):
        self.summary = summary_df
class MockResult:
    def __init__(self, ticker, p50_20d, p5, p95, pred_len=20):
        # summary: timestamps, p5, p25, p50, p75, p95, mean
        n = pred_len
        summary = pd.DataFrame({
            "timestamps": pd.bdate_range("2024-01-01", periods=n, freq="B"),
            "p5": [p5] * n, "p25": [p50 * 0.95] * n,
            "p50": [p50] * n, "p75": [p50 * 1.05] * n,
            "p95": [p95] * n, "mean": [p50] * n,
        })
        h5_summary = summary.head(5).copy()
        self.horizons = {
            5: MockHorizon(h5_summary),
            20: MockHorizon(summary),
        }

# Build mock forecasts
forecasts = {
    "AAPL": MockResult("AAPL", p50_20d=105.0, p5=95.0, p95=115.0),
    "PTT.BK": MockResult("PTT.BK", p50_20d=51.0, p5=48.0, p95=54.0),
    "SPY": MockResult("SPY", p50_20d=410.0, p5=390.0, p95=430.0),
}

# Test without backtest (fallback band-width confidence)
# CRITICAL: last_closes must be passed explicitly — NOT derived from forecast
adj_table, raw_table = build_report_table(forecasts, last_closes={"AAPL": 100.0, "PTT.BK": 50.0, "SPY": 400.0},
                                          backtest_result=None, long_threshold=0.01)
assert len(adj_table) == 3, f"expected 3 rows, got {len(adj_table)}"
assert "Signal" in adj_table.columns
assert "Confidence" in adj_table.columns
# Verify 1d p50 is NOT all zeros (the old bug)
assert not (adj_table["1d p50"] == 0).all(), "1d p50 should not be all zeros with actual last_close!"
print("PASS: build_report_table without backtest")

# Test markdown rendering
md = render_markdown(adj_table)
assert "### Kronos-TH Daily Report" in md
assert "AAPL" in md
print("PASS: render_markdown")

print("ALL REPORT TESTS PASSED")
```

Run: `python tests/utils/test_report.py`
Expected: `FAIL`

- [ ] **Step 2: Implement `report.py`**

```python
# kth/utils/report.py
"""Daily decision report: signal table builder, Markdown/HTML renderer."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from kth.data.universe import get_ticker_class, get_display_name

# Fallback band-width thresholds — PER ASSET CLASS (not global)
# Crypto routinely shows 30%+ bands; bonds show 5%. Global thresholds misclassify both.
BAND_THRESHOLDS = {
    "thai_equity":   (0.15, 0.30),
    "thai_index":    (0.15, 0.30),
    "us_equity":     (0.15, 0.30),
    "etf_global":    (0.15, 0.30),
    "commodity":     (0.20, 0.35),
    "crypto":        (0.30, 0.50),
    "bond_proxy":    (0.10, 0.20),
    "reit":          (0.10, 0.20),
    "fx_macro":      (0.05, 0.15),
}
DEFAULT_THRESHOLD = (0.15, 0.30)  # green_max, yellow_max


def _compute_band_width(result) -> float:
    """Compute (p95 - p5) / abs(p50) for the 20d horizon. Returns inf if p50=0."""
    h = result.horizons[20]
    p5 = h.summary["p5"].iloc[-1]
    p95 = h.summary["p95"].iloc[-1]
    p50 = h.summary["p50"].iloc[-1]
    if abs(p50) < 1e-10:
        return float("inf")
    return float((p95 - p5) / abs(p50))


def _get_confidence(
    ticker: str,
    result,
    backtest_result=None,             # BacktestResult or None
    per_ticker_hit_rates: dict[str, float] | None = None,
) -> tuple[str, float]:
    """
    Returns (flag_emoji, flag_weight).
    Priority: per-ticker hit_rate > per-class hit_rate > band-width fallback.
    """
    # 1. Per-ticker calibration (highest priority)
    if per_ticker_hit_rates and ticker in per_ticker_hit_rates:
        hit_rate = per_ticker_hit_rates[ticker]
        if hit_rate >= 0.60:
            return f"\U0001F7E2 ({hit_rate:.0%})", 1.0
        elif hit_rate >= 0.50:
            return f"\U0001F7E1 ({hit_rate:.0%})", 0.5
        else:
            return f"\U0001F534 ({hit_rate:.0%})", 0.1

    # 2. Per-class calibration (from BacktestResult)
    if backtest_result is not None:
        attr = backtest_result.per_class_attribution
        cls = get_ticker_class(ticker) or "unknown"
        cls_row = attr[attr["asset_class"] == cls]
        if len(cls_row) > 0:
            hit_rate = float(cls_row["hit_rate"].iloc[0])
            if hit_rate >= 0.60:
                return f"\U0001F7E2 ({hit_rate:.0%})", 1.0
            elif hit_rate >= 0.50:
                return f"\U0001F7E1 ({hit_rate:.0%})", 0.5
            else:
                return f"\U0001F534 ({hit_rate:.0%})", 0.1

    # 3. Fallback: band-width based (PER CLASS thresholds)
    cls = get_ticker_class(ticker) or "unknown"
    green_max, yellow_max = BAND_THRESHOLDS.get(cls, DEFAULT_THRESHOLD)
    bw = _compute_band_width(result)
    if bw < green_max:
        return "\U0001F7E2 (band)", 1.0
    elif bw < yellow_max:
        return "\U0001F7E1 (band)", 0.5
    else:
        return "\U0001F534 (band)", 0.1


def build_report_table(
    forecasts: dict[str, object],  # dict[str, ForecastResult]
    last_closes: dict[str, float],  # REQUIRED: actual close per ticker
    backtest_result=None,  # BacktestResult | None
    per_ticker_hit_rates: dict[str, float] | None = None,
    long_threshold: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (confidence_adjusted_table, raw_forecast_table).

    last_closes: REQUIRED parameter. Actual close price for each ticker at the
      forecast date. Must not be derived from forecast output — using p50.iloc[0]
      as a proxy makes 1d p50 always 0%. Caller loads actual close from cached data.
    """
    rows = []
    for ticker, result in forecasts.items():
        cls = get_ticker_class(ticker) or "unknown"
        name = get_display_name(ticker)

        # CRITICAL: use actual last_close, NOT p50.iloc[0]
        if ticker not in last_closes:
            continue
        last_close = last_closes[ticker]

        h5 = result.horizons[5]
        h20 = result.horizons[20]

        p50_1d = float((h5.summary["p50"].iloc[0] / last_close - 1) * 100)
        p50_5d = float((h5.summary["p50"].iloc[-1] / last_close - 1) * 100)
        p50_20d = float((h20.summary["p50"].iloc[-1] / last_close - 1) * 100)

        band_20 = float(h20.summary["p95"].iloc[-1] - h20.summary["p5"].iloc[-1])
        p5_p95_band = float((band_20 / last_close) * 100)

        confidence, flag_weight = _get_confidence(ticker, result, backtest_result, per_ticker_hit_rates)
        score = p50_20d * flag_weight

        signal = "LONG" if p50_20d > long_threshold else "FLAT"
        is_red = confidence.startswith("\U0001F534")

        rows.append({
            "Ticker": ticker,
            "Name": name,
            "Class": cls,
            "1d p50": round(p50_1d, 2),
            "5d p50": round(p50_5d, 2),
            "20d p50": round(p50_20d, 2),
            "P5-P95 band": round(p5_p95_band, 2),
            "Signal": "FLAT" if is_red else signal,
            "Confidence": confidence,
            "Score": round(score, 2),
        })

    raw_table = pd.DataFrame(rows).sort_values("20d p50", ascending=False)
    adj_table = pd.DataFrame(rows).sort_values("Score", ascending=False)

    return adj_table, raw_table


def render_markdown(table: pd.DataFrame) -> str:
    """Returns a Markdown-formatted string for Jupyter display.
    Accepts a single DataFrame (pass adj_table or raw_table separately)."""
    lines = []
    lines.append("### Kronos-TH Daily Report")
    lines.append("")
    lines.append(f"*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    # 9 plain separators — no alignment specifiers that break parsers
    lines.append("| Ticker | Name | Class | 1d p50 | 5d p50 | 20d p50 | P5-P95 band | Signal | Confidence |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |")

    for _, row in table.iterrows():
        lines.append(
            f"| {row['Ticker']} | {row['Name']} | {row['Class']} | "
            f"{row['1d p50']:+.1f}% | {row['5d p50']:+.1f}% | {row['20d p50']:+.1f}% | "
            f"{row['P5-P95 band']:.1f}% | **{row['Signal']}** | {row['Confidence']} |"
        )

    lines.append("")
    lines.append("*This is research output, not financial advice.*")
    return "\n".join(lines)


def _table_to_html(table: pd.DataFrame) -> str:
    """Convert report DataFrame to an HTML table with colour-coded confidence cells."""
    rows = ["<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"]
    cols = ["Ticker", "Name", "Class", "1d p50", "5d p50", "20d p50", "P5-P95 band", "Signal", "Confidence"]
    rows.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>")
    rows.append("<tbody>")
    for _, row in table.iterrows():
        conf = str(row["Confidence"])
        if "\U0001F7E2" in conf:
            bg = "#e8f5e9"
        elif "\U0001F7E1" in conf:
            bg = "#fffde7"
        else:
            bg = "#ffebee"
        signal_style = "font-weight:bold;color:#1565C0" if row["Signal"] == "LONG" else "color:#999"
        cells = (
            f"<td>{row['Ticker']}</td>"
            f"<td>{row['Name']}</td>"
            f"<td>{row['Class']}</td>"
            f"<td align='right'>{row['1d p50']:+.1f}%</td>"
            f"<td align='right'>{row['5d p50']:+.1f}%</td>"
            f"<td align='right'>{row['20d p50']:+.1f}%</td>"
            f"<td align='right'>{row['P5-P95 band']:.1f}%</td>"
            f"<td style='{signal_style}'>{row['Signal']}</td>"
            f"<td style='background:{bg}'>{conf}</td>"
        )
        rows.append(f"<tr>{cells}</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_html(
    tables: tuple[pd.DataFrame, pd.DataFrame],
    path: str,
    model_name: str,
    generated_at: "pd.Timestamp",
) -> str:
    """
    Write a standalone HTML report to `path`.
    `tables` is the (confidence_adjusted_table, raw_forecast_table) tuple from build_report_table().
    Returns `path` for chaining: print(f"Saved to {render_html(tables, path, ...)}")
    """
    adj_table, raw_table = tables
    date_str = generated_at.strftime("%Y-%m-%d")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Kronos-TH Daily Report — {date_str}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #1565C0; }} h2 {{ color: #333; margin-top: 40px; }}
    p.meta {{ color: #666; font-size: 0.9em; }}
    .disclaimer {{ background: #f5f5f5; padding: 16px; border-left: 4px solid #ccc; margin-top: 40px; }}
  </style>
</head>
<body>
  <h1>Kronos-TH Daily Report — {date_str}</h1>
  <p class="meta">Model: {model_name} &nbsp;|&nbsp; Generated: {generated_at.strftime("%Y-%m-%d %H:%M")}</p>

  <h2>Signal Table (Confidence-Adjusted)</h2>
  <p>Sorted by score = 20d p50 × confidence weight. Red-flagged assets are forced to FLAT.</p>
  {_table_to_html(adj_table)}

  <h2>Raw Model Forecasts — not filtered by historical accuracy</h2>
  <p>Sorted by 20d p50 only. No signal suppression applied.</p>
  {_table_to_html(raw_table)}

  <div class="disclaimer">
    <h2>Disclaimer</h2>
    <p>This is research output from a forecasting model, not financial advice.
    Past model accuracy does not guarantee future performance. All investments carry risk.
    The confidence flags are derived from historical backtests and may not reflect
    future model behaviour, especially after regime changes or model updates.</p>
  </div>
</body>
</html>"""

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)
```

- [ ] **Step 3: Run tests** (update test to also cover render_html)

Add to `tests/utils/test_report.py`:
```python
# Test render_html
from kth.utils.report import render_html
import tempfile, os
with tempfile.TemporaryDirectory() as tmp:
    html_path = render_html((adj_table, raw_table), os.path.join(tmp, "test.html"),
                            model_name="NeoQuasar/Kronos-small@a3f1c2d",
                            generated_at=pd.Timestamp.now())
    assert os.path.exists(html_path), "HTML file not created"
    content = open(html_path).read()
    assert "Kronos-TH Daily Report" in content
    assert "AAPL" in content
    assert "Disclaimer" in content
    print("PASS: render_html")
```

Run: `python tests/utils/test_report.py`
Expected: `ALL REPORT TESTS PASSED`

- [ ] **Step 4: Update self-review note and commit**

Remove the incorrect self-review note that said `build_report_table` uses `p50.iloc[0]` as last_close proxy — the code correctly uses `last_closes[ticker]`.

```bash
git add kth/utils/report.py tests/utils/test_report.py
git commit -m "feat: add report.py with build_report_table, render_markdown, render_html"
```

---

### Task 3: `.gitignore` and `reports/.gitkeep`

**Files:**
- Create: `reports/.gitkeep`
- Create/Modify: `.gitignore`

- [ ] **Step 1: Create files**

Check if `.gitignore` exists; if not, create:

```
# .gitignore
__pycache__/
*.pyc
.ipynb_checkpoints/
data/raw/*.parquet
data/forecast_cache/
reports/*.html
checkpoints/
*.egg-info/
```

```bash
New-Item -ItemType File -Path "reports/.gitkeep" -Force
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore reports/.gitkeep
git commit -m "chore: add .gitignore and reports/.gitkeep"
```

---

### Task 4: Notebook 05 — Daily Decision Report

**Files:**
- Create: `notebooks/05_decision_report.ipynb`

**Cells:**
1. **Mount Drive + import deps**
   ```python
   from google.colab import drive; drive.mount('/content/drive')
   import sys; sys.path.append('/content/drive/MyDrive/kronos-th')
   from kth.models.kronos_wrapper import KronosTH
   from kth.data.universe import get_all_tickers
   from kth.data.loader import load_cached
   ```

2. **Load model** (zero-shot or fine-tuned)
   ```python
   k = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device="cuda")
   # Or: k = KronosTH.from_checkpoint("./checkpoints/pred_fold0")
   ```

3. **Refresh data if stale**
   ```python
   from kth.data.loader import download_universe
   # download_universe(get_all_tickers(), period="5y")  # uncomment if stale
   ```

4. **Run forecast batch**
   ```python
   forecasts = k.forecast_batch(get_all_tickers(), pred_lens=[5, 20], n_samples=50)
   ```

5. **Load backtest result (optional)**
   ```python
   from kth.backtest.walkforward import BacktestResult
   try:
       br = BacktestResult.load("/content/drive/MyDrive/kronos-th/results/backtest_latest")
   except:
       br = None
       print("No backtest result found — using band-width confidence fallback")
   ```

6. **Build and display report table** (with actual last_close prices)
   ```python
   from kth.utils.report import build_report_table, render_markdown
   from IPython.display import display, Markdown

   # Build last_closes dict from cached data
   last_closes = {}
   for t in get_all_tickers():
       try:
           df = load_cached(t)
           last_closes[t] = float(df["close"].iloc[-1])
       except: pass

   adj_table, raw_table = build_report_table(forecasts, last_closes=last_closes, backtest_result=br)
   display(Markdown(render_markdown(adj_table)))
   # Raw forecasts table
   display(Markdown("### Raw Model Forecasts (not filtered by historical accuracy)"))
   display(Markdown(render_markdown(raw_table)))
   ```

7. **Save HTML report**
   ```python
   from kth.utils.report import render_html
   from datetime import date

   html_path = render_html(adj_table, f"/content/drive/MyDrive/kronos-th/reports/{date.today()}.html",
                           model_name=k.model_name, generated_at=pd.Timestamp.now())
   print(f"Report saved to {html_path}")
   ```

8. **Plot top 5 tickers by score**
   ```python
   from kth.utils.plot import plot_forecast_band

   top5 = adj_table.head(5)["Ticker"].tolist()
   for t in top5:
       result = forecasts[t]
       historical = load_cached(t).tail(60)
       fig = plot_forecast_band(t, historical, result, pred_len=20)
       plt.show()
   ```

9. **Disclaimers**
   ```markdown
   ## Disclaimer
   This is research output from a forecasting model, not financial advice...
   ```

- [ ] **Step 1: Create notebook on Colab and verify end-to-end**

- [ ] **Step 2: Save notebook to repo**

---

### Self-Review

- [x] Spec coverage: All sections — plot functions (forecast_band, equity_curve, attribution, drawdown), report functions (build_report_table with dual sort, confidence flags via calibration + fallback, render_markdown, render_html), notebook cells, .gitignore
- [x] Placeholder scan: No TBDs. Last_close derivation from p50 day-0 is a known approximation; the notebook will have actual `last_close` from `load_cached()`.
- [x] Type consistency: `Confidence` column uses same format across markdown and HTML. `Signal=LONG/FLAT` consistent. `Score = p50_return_20d * flag_weight` used for Sort B sorting.
- [x] last_close handling: `build_report_table` requires `last_closes` dict from the caller (loaded via `load_cached()`). The function does NOT derive last_close from `p50.iloc[0]` — doing so would make the 1d p50 column always 0%.
