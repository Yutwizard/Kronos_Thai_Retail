# Spec D — Daily Decision Report

**Date:** 2026-05-16
**Subsystem:** `kth/utils/plot.py`, `kth/utils/report.py` + `notebooks/05_decision_report.ipynb`
**Depends on:** Spec A (`KronosTH`), Spec B (`BacktestResult` for calibration flags)
**Spec C dependency:** optional — report works with either zero-shot or fine-tuned model
**Status:** Approved

---

## Purpose

A single daily output answering: *"What does the model expect for each asset I can buy, and how much should I trust it?"*

Produces:
1. **Inline Markdown table** in the notebook (live, sortable by the user in Colab)
2. **Saved HTML report** at `./reports/YYYY-MM-DD.html` (standalone, archivable)

---

## Module Layout

```
kth/utils/
├── __init__.py
├── plot.py      # reusable chart functions
└── report.py   # signal table builder + HTML/Markdown renderer
```

---

## Confidence Flag (Calibration-based)

Confidence is derived from `BacktestResult.per_class_attribution["hit_rate"]` (Spec B output). This grounds the flag in actual model performance, not just forecast uncertainty.

**Per-ticker hit rate preferred** when available. `BacktestResult` stores per-class attribution, but within each class the model's accuracy varies by ticker. `build_report_table` accepts an optional `per_ticker_hit_rates: dict[str, float]` parameter. When provided, individual ticker hit rates override the class-level rate. When absent, the class-level rate from `per_class_attribution` is the fallback.

| Hit rate (per ticker or class, whichever is available) | Flag | `flag_weight` | Meaning |
|---|---|---|---|
| ≥ 60% | 🟢 Green | 1.0 | Reliable directional accuracy for this ticker/class |
| 50–59% | 🟡 Yellow | 0.5 | Near-random; treat as weak signal |
| < 50% | 🔴 Red | 0.1 | Historically wrong more often than right |

**Fallback:** If no `BacktestResult` is provided (first run, or zero-shot only), fall back to band-width-based flags. Band-width thresholds are **per-asset-class** (not global), because crypto and FX routinely show 30%+ bands while bonds show 5%:

| Threshold | Description |
|---|---|
| `BAND_GREEN[p95/p50] / max_loss / expected_loss` | Derived from per-class historical forecast distribution |
| Default per-class thresholds | `thai_equity/us_equity/etf_global`: 0.15/0.30, `commodity`: 0.20/0.35, `crypto`: 0.30/0.50, `bond_proxy/reit`: 0.10/0.20, `fx_macro`: 0.05/0.15 |

The fallback threshold values are module-level constants in `report.py`, keyed by asset class, easy to tune per class.

---

## Report Table

One row per ticker. Two sort options presented side-by-side in notebook (Issue #7):

- **Sort A — Raw forecast:** descending by `p50_return_20d`. Shows what the model predicts regardless of historical reliability.
- **Sort B — Confidence-adjusted:** descending by `score = p50_return_20d × flag_weight`, **but red-flagged assets are forced to `FLAT` signal regardless of forecast return.** A 🔴 Red asset with a 30% forecast will show the forecast for transparency but signal FLAT — the model has historically been wrong >50% of the time on this class and acting on it destroys capital.

The HTML report renders Sort B by default. Sort A is shown as a secondary table with a clear header: *"Raw model forecasts — not filtered by historical accuracy."*

**Markdown table header:**
```
| Ticker | Name | Class | 1d p50 | 5d p50 | 20d p50 | P5-P95 band | Signal | Confidence |
|---|---|---|---|---|---|---|---|---|
```
Use 9 plain `---` separators without alignment specifiers (or `:---:` for center) — the mixed `|---:|---:` syntax breaks in some parsers.

| Column | Definition |
|---|---|
| Ticker | yfinance ticker symbol |
| Name | Display name from `get_display_name()` |
| Class | Asset class from `get_ticker_class()` |
| 1d p50 | `(horizons[5].summary["p50"].iloc[0] / last_close - 1) × 100` — expected % return on day 1 |
| 5d p50 | `(horizons[5].summary["p50"].iloc[-1] / last_close - 1) × 100` — cumulative % return by day 5 |
| 20d p50 | `(horizons[20].summary["p50"].iloc[-1] / last_close - 1) × 100` — cumulative % return by day 20 |
| P5–P95 band | `(p95 - p5) / last_close × 100` — uncertainty width as % of price |
| Signal | LONG / FLAT. Red-flagged assets are always FLAT regardless of forecast. |
| Confidence | 🟢 / 🟡 / 🔴 with class hit-rate shown in parentheses, e.g. "🟢 (63%)" |

`long_threshold` defaults to `0.01` (same as `BacktestConfig`), configurable as a param.

---

## `kth/utils/report.py` — Public API

```python
def build_report_table(
    forecasts: dict[str, ForecastResult],    # from KronosTH.forecast_batch()
    last_closes: dict[str, float],           # actual last close price per ticker
    backtest_result: BacktestResult | None = None,
    per_ticker_hit_rates: dict[str, float] | None = None,  # optional per-ticker override
    long_threshold: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (confidence_adjusted_table, raw_forecast_table).
    confidence_adjusted_table: sorted by score, red assets forced to FLAT.
    raw_forecast_table: sorted by p50_return_20d only, no signal suppression.

    last_closes: REQUIRED. Actual close price for each ticker at the forecast date.
      Must not be derived from forecast output — using p50.iloc[0] as a proxy
      would make 1d p50 always 0%. The caller loads actual close prices via
      load_cached() and passes them here.
    """


def render_markdown(table: pd.DataFrame) -> str:
    """
    Returns a Markdown-formatted string for Jupyter display.
    Accepts a single DataFrame (either confidence_adjusted_table or raw_forecast_table).
    The caller is responsible for calling this twice if both tables are needed.

    Header and footer are included in the output:
      - Header: "### Kronos-TH Daily Report" + generation timestamp
      - Table: 9 plain --- separators (no alignment specifiers)
      - Footer: research disclaimer
    """


def render_html(
    tables: tuple[pd.DataFrame, pd.DataFrame],
    path: str,
    model_name: str,
    generated_at: pd.Timestamp,
) -> str:
    """
    Writes a standalone HTML report to `path`.
    Accepts the full (confidence_adjusted_table, raw_forecast_table) tuple.
    HTML structure:
      <h1>Kronos-TH Daily Report — YYYY-MM-DD</h1>
      <p>Model: {model_name} | Generated: {generated_at}</p>
      <h2>Signal Table (Confidence-Adjusted)</h2>
      <table>...colour-coded confidence flags...</table>
      <h2>Raw Model Forecasts — not filtered by historical accuracy</h2>
      <table>...raw forecast table...</table>
      <h2>Disclaimer</h2>
      <p>This is research output from a forecasting model, not financial advice...</p>
    Returns `path` (for use in notebook: `print(f"Saved to {render_html(...)}")`).
    """
```

HTML report structure:
```html
<h1>Kronos-TH Daily Report — YYYY-MM-DD</h1>
<p>Model: {model_name} | Generated: {generated_at}</p>
<table>...sorted signal table with colour-coded confidence...</table>
<h2>Disclaimer</h2>
<p>This is research output from a forecasting model, not financial advice...</p>
```

---

## `kth/utils/plot.py` — Chart Functions

Reusable across notebooks 02–05. All functions return a `matplotlib.figure.Figure`.

```python
def plot_forecast_band(
    ticker: str,
    historical: pd.DataFrame,        # Kronos-format, last N rows to show
    result: ForecastResult,
    pred_len: int = 20,
    n_history_days: int = 60,
) -> Figure:
    """Actual close (last 60d) + shaded P5/P95 band + P50 line for pred_len days."""


def plot_equity_curve(
    backtest_result: BacktestResult,
    include_benchmarks: bool = True,
) -> Figure:
    """Net equity curve vs all 4 benchmarks. Gross curve shown as dashed."""


def plot_attribution(
    backtest_result: BacktestResult,
) -> Figure:
    """Horizontal bar chart: per-class P&L contribution (gross and net)."""


def plot_drawdown(
    backtest_result: BacktestResult,
) -> Figure:
    """Drawdown series with shaded underwater periods."""
```

---

## Notebook 05 — Daily Decision Report

Cells:
1. Load model: `k = KronosTH.from_checkpoint(...)` or `KronosTH.from_pretrained(...)`
2. Load latest cached data (run `download_universe` if stale > 1 day)
3. `forecasts = k.forecast_batch(get_all_tickers(), pred_lens=[5, 20], n_samples=50)`
4. Load `backtest_result` from a saved parquet+JSON directory (output of notebook 03), or `None`: `br = BacktestResult.load("./data/backtest_results/") if Path("./data/backtest_results/metrics.json").exists() else None`
5. Build `last_closes` dict from cached data, then `adj_table, raw_table = build_report_table(forecasts, last_closes=last_closes, backtest_result=br, long_threshold=0.01)`
6. `display(Markdown(render_markdown(adj_table)))` — confidence-adjusted table; `display(Markdown("### Raw Model Forecasts (not filtered by historical accuracy)")); display(Markdown(render_markdown(raw_table)))`
7. `render_html((adj_table, raw_table), f"./reports/{date.today()}.html", k.model_name, pd.Timestamp.now())` — save file
8. For top 5 tickers by score: `plot_forecast_band(ticker, historical, result)` — one chart each
9. Disclaimers cell (required, not optional)

---

## Output Files

| Path | Contents |
|---|---|
| `./reports/YYYY-MM-DD.html` | Standalone daily report |
| `./reports/.gitkeep` | Directory tracked in git; HTML files gitignored |

Add `reports/*.html` to `.gitignore`. Create `.gitignore` at project root if it doesn't exist.

---

## Files to Create

| File | Purpose |
|---|---|
| `kth/utils/plot.py` | `plot_forecast_band`, `plot_equity_curve`, `plot_attribution`, `plot_drawdown` |
| `kth/utils/report.py` | `build_report_table`, `render_markdown`, `render_html` |
| `notebooks/05_decision_report.ipynb` | Daily report notebook |
| `reports/.gitkeep` | Output directory |
