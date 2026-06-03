# Phase 3 — P2 Professional Metrics

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Complete Phase 2 before starting this phase.

**Goal:** Five additions that bring the system to quant-fund-manager standard — IR + batting average metrics, P5/P95 calibration check, T+2 settlement warning, model version audit trail, and LINE Notify on cron failure.

**Decisions locked (grilling session 2026-06-03):**
- T+2: warning-only (add `t2_warning` field to trade ticket JSON). No cash split or settlement job.
- Calibration: rolling window = 20 trading days (matches pred_len). Computed from forecast cache + raw parquet. Displayed in Signal Health row.
- Information Ratio: `IR = annualised_cagr_alpha / tracking_error_vs_equal_weight`. Batting Average: `% of calendar months where strategy beat equal-weight`.
- Model version: add `model_version` (e.g., `"Kronos-small-zero-shot"`) and `forecast_date` columns to `trade_log.csv`.
- Line Notify token: read from `$LINE_NOTIFY_TOKEN` environment variable. If unset, skip notification and log a warning — never error.

**Estimated time:** ~4 hours total.

---

### File Structure

| Action | Path | Change |
|--------|------|--------|
| Modify | `kth/backtest/metrics.py` | Add `compute_information_ratio()`, `compute_batting_average()`, `compute_calibration()` |
| Modify | `kth/trading/trade_gen.py` | Add `t2_warning` field to ticket output |
| Modify | `kth/trading/portfolio.py` | Add `model_version` + `forecast_date` to trade log writer |
| Modify | `scripts/cron_pipeline.sh` | Add LINE Notify on failure |
| Modify | `scripts/dashboard.py` | Wire calibration + new metrics into `/api/risk` response |

---

### Task 1 — Information Ratio and Batting Average

**File:** `kth/backtest/metrics.py`

**Context:** The existing `compute_metrics()` function returns Sharpe, Sortino, MaxDD, CAGR. IR and batting average measure stock-selection skill specifically and are the right metrics when presenting to a quant PM.

- [ ] **Step 1: Add `compute_information_ratio()`** after the existing metric functions:

```python
def compute_information_ratio(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """IR = annualised active return / tracking error vs benchmark."""
    active = strategy_returns - benchmark_returns
    if active.std() == 0:
        return 0.0
    return float(active.mean() / active.std() * np.sqrt(periods_per_year))
```

- [ ] **Step 2: Add `compute_batting_average()`**:

```python
def compute_batting_average(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """% of calendar months where strategy daily return mean > benchmark daily return mean."""
    df = pd.DataFrame({"strat": strategy_returns, "bench": benchmark_returns})
    df.index = pd.to_datetime(df.index)
    monthly = df.resample("ME").mean()
    if len(monthly) == 0:
        return 0.0
    wins = (monthly["strat"] > monthly["bench"]).sum()
    return float(wins / len(monthly))
```

- [ ] **Step 3: Expose both** in the main `compute_metrics()` function by adding them to the returned dict when `benchmark_returns` is provided as an optional argument. Check the function signature and add `benchmark_returns: pd.Series | None = None` parameter. If provided, compute IR and batting average and include in return dict.

---

### Task 2 — P5/P95 Calibration Check

**File:** `kth/backtest/metrics.py`

**Context:** `confidence = "green"` when band_width ≤ 10%. But we don't know if the actual price truly falls within [P5, P95] ~90% of the time. Without calibration, the green flag is unverified.

**How it works:** For each forecast made N days ago (where N = pred_len = 20), compare actual close price to the [P5, P95] band of that forecast. Coverage should be ~90%.

- [ ] **Step 1: Add `compute_calibration()`**:

```python
def compute_calibration(
    forecast_cache_dir: "Path",
    raw_data_dir: "Path",
    tickers: list[str],
    pred_len: int = 20,
    lookback_days: int = 60,
) -> dict:
    """
    Compute P5/P95 coverage over the past `lookback_days` forecast dates.
    Returns {'coverage': float, 'n_samples': int, 'status': str}
    coverage = fraction of (ticker, date) pairs where actual close was within [P5, P95].
    """
    from pathlib import Path
    import pandas as pd
    from datetime import date, timedelta
    from kth.data.loader import load_cached

    hits, total = 0, 0
    today = date.today()

    for ticker in tickers:
        safe = ticker.replace("^", "_").replace("=", "_")
        try:
            price_df = load_cached(ticker, cache_dir=raw_data_dir)
            price_df.index = pd.to_datetime(price_df.index)
        except Exception:
            continue

        for days_ago in range(pred_len + 1, lookback_days + pred_len + 1):
            forecast_date = today - timedelta(days=days_ago)
            actual_date = today - timedelta(days=days_ago - pred_len)
            day_dir = forecast_cache_dir / str(forecast_date)
            fc_path = day_dir / f"{safe}.parquet"
            if not fc_path.exists():
                continue
            try:
                fc = pd.read_parquet(fc_path)
                p5 = float(fc["p5"].iloc[-1])
                p95 = float(fc["p95"].iloc[-1])
                actual_rows = price_df[price_df.index.date == actual_date]
                if actual_rows.empty:
                    continue
                actual_close = float(actual_rows["close"].iloc[0])
                total += 1
                if p5 <= actual_close <= p95:
                    hits += 1
            except Exception:
                continue

    if total < 10:
        return {"coverage": None, "n_samples": total, "status": "insufficient_data"}
    return {
        "coverage": round(hits / total, 3),
        "n_samples": total,
        "status": "ok" if hits / total >= 0.80 else "underconfident" if hits / total > 0.95 else "ok",
    }
```

- [ ] **Step 2: Wire into `/api/risk`** in `scripts/dashboard.py`. Call `compute_calibration()` at dashboard startup (cache the result — recompute at most once per day). Add to the `/api/risk` response JSON:

```json
"calibration": {"coverage": 0.87, "n_samples": 43, "status": "ok"}
```

- [ ] **Step 3: Show in Signal Health row** (dashboard HTML): display as `Band coverage: 87% (n=43)` next to the trailing accuracy tile. Show ⚠ if coverage < 0.80 or > 0.95 (overconfident).

---

### Task 3 — T+2 Settlement Warning in Trade Ticket

**File:** `kth/trading/trade_gen.py`

**Context:** Thai equity settles T+2. If exits and buys appear on the same trade ticket for the same day, sell proceeds are not yet available for the buys. The fix is a warning field — no data structure change to portfolio.py.

- [ ] **Step 1: Add settlement date logic** near the end of `generate_trade_ticket()`, after the `exits` and `buys` lists are built:

```python
from datetime import date, timedelta

t2_warning = None
if exits and buys:
    settle_date = _next_business_day(_next_business_day(date.today()))
    t2_warning = (
        f"Exit proceeds settle {settle_date} (T+2). "
        f"Today's buys draw from existing cash only — not from today's exit proceeds."
    )
```

- [ ] **Step 2: Add `_next_business_day()` helper** at the top of the file:

```python
def _next_business_day(d: "date") -> "date":
    from datetime import timedelta
    d = d + timedelta(days=1)
    while d.weekday() >= 5:  # Saturday=5, Sunday=6
        d = d + timedelta(days=1)
    return d
```

- [ ] **Step 3: Add `t2_warning` to the returned ticket dict**:

```python
ticket = {
    ...
    "t2_warning": t2_warning,
    ...
}
```

- [ ] **Step 4: Display in dashboard** — in the Trade Ticket zone, if `t2_warning` is not null, show a yellow info banner above the buy list with the warning text.

---

### Task 4 — Model Version + Forecast Date in Trade Log

**File:** `kth/trading/portfolio.py`

**Context:** The trade log CSV has no record of which model generated the signal. When comparing paper performance across zero-shot vs fine-tuned checkpoints, there is no way to slice by model. This matters when the model changes.

- [ ] **Step 1: Find the trade log writer** — search for the CSV append logic:

```bash
grep -n "trade_log\|csv\|writerow\|DictWriter" kth/trading/portfolio.py
```

- [ ] **Step 2: Add columns** `model_version` and `forecast_date` to the CSV header. Check if the CSV already has a header row — if yes, the header must be updated for new files only (existing files are append-only, so new columns appear only in rows written after this change — acceptable).

- [ ] **Step 3: Populate values** when a trade is recorded. `model_version` defaults to `"Kronos-small-zero-shot"` (constant for now). `forecast_date` is `date.today()` at the time `record_trade()` is called.

```python
MODEL_VERSION = "Kronos-small-zero-shot"

# In the trade dict passed to the CSV writer, add:
"model_version": MODEL_VERSION,
"forecast_date": str(date.today()),
```

- [ ] **Step 4: Verify** — after recording a paper trade, open `data/positions/trade_log.csv` and confirm `model_version` and `forecast_date` columns are present.

---

### Task 5 — LINE Notify on Cron Failure

**File:** `scripts/cron_pipeline.sh`

**Context:** If the 06:30 cron fails, the user discovers it at 09:00 when they open a stale dashboard. LINE Notify sends an instant push to the user's phone.

- [ ] **Step 1: Add notify function** near the top of `cron_pipeline.sh`, after the `LOG=` line:

```bash
notify_line() {
  local msg="$1"
  if [ -z "$LINE_NOTIFY_TOKEN" ]; then
    echo "[WARN] LINE_NOTIFY_TOKEN not set — skipping notification" >> "$LOG"
    return
  fi
  curl -s -X POST https://notify-api.line.me/api/notify \
    -H "Authorization: Bearer $LINE_NOTIFY_TOKEN" \
    -F "message=$msg" >> "$LOG" 2>&1
}
```

- [ ] **Step 2: Call `notify_line` on step failure.** Replace the current failure exit with:

```bash
  done || {
    echo "STEP_FAILED: $step" >> "$LOG"
    notify_line "🚨 Kronos-TH cron FAILED at step: $step on $(date +%Y-%m-%d). Check $LOG"
    exit 1
  }
```

- [ ] **Step 3: Add success notification** (optional — comment it out by default to avoid noise):

```bash
# notify_line "✅ Kronos-TH pipeline OK — forecasts ready for $(date +%Y-%m-%d)"
```

- [ ] **Step 4: Document token setup** in `docs/operations-manual.md` under a new "Alerts" section:

```
# Set once in your shell profile:
export LINE_NOTIFY_TOKEN="your-token-from-notify.line.me/my"

# Or set directly in crontab:
30 6 * * 1-5 LINE_NOTIFY_TOKEN=xxx bash /path/to/cron_pipeline.sh
```

- [ ] **Step 5: Verify** — temporarily set an invalid token and trigger a failure. Confirm the log shows the curl response (invalid token error from LINE API), and the script still exits with code 1.

---

### Verification Checklist

- [ ] `python verify_data_layer.py` — all 5 tests pass
- [ ] `compute_information_ratio(strat, bench)` returns a float; `compute_batting_average()` returns 0.0–1.0
- [ ] Calibration with < 10 samples returns `status: "insufficient_data"` (not a crash)
- [ ] Trade ticket with exits + buys contains `t2_warning` string (not null)
- [ ] Trade ticket with exits only (no buys): `t2_warning` is null
- [ ] `trade_log.csv` new rows have `model_version` and `forecast_date` populated
- [ ] Cron failure with valid `LINE_NOTIFY_TOKEN` sends message to LINE app
- [ ] Cron failure with unset `LINE_NOTIFY_TOKEN` logs warning and exits 1 (no crash)
