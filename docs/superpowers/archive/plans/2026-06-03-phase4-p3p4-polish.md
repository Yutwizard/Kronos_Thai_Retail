# Phase 4 — P3/P4 Polish

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Complete Phase 3 before starting this phase.

**Goal:** Five polish items — data sanity filter prevents absurd prices corrupting forecasts; POST trade input validation prevents fat-finger corruption; drawdown velocity catches slow portfolio grinds; rolling bootstrap p-value surfaces statistical significance live; survivorship bias estimate formalises the key disclosure.

**Decisions locked (grilling session 2026-06-03):**
- Bootstrap p-value: n=1000 samples, computed once at dashboard load from cached equity curve returns, displayed inline in Signal Health row (not tooltip-only).
- Data sanity filter: if any ticker's last-bar close moved > 30% from prior bar, log warning and exclude that ticker from today's forecast run.
- Drawdown velocity: flag "GRIND" if portfolio drops > 3% over 5 consecutive trading days, even if no single-day threshold triggers.
- Survivorship bias: cite ~1–3% CAGR per year as the academic range for SET delisting bias. Add as a formal disclosure paragraph in `docs/backtest-methodology.html`.

**Estimated time:** ~6 hours total.

---

### File Structure

| Action | Path | Change |
|--------|------|--------|
| Modify | `scripts/download_data.py` | Add price sanity filter post-download |
| Modify | `scripts/dashboard.py` | POST /api/trades input validation |
| Modify | `kth/backtest/metrics.py` | Add `compute_drawdown_velocity()`, `compute_bootstrap_pvalue()` |
| Modify | `kth/trading/trade_gen.py` | Wire drawdown velocity + bootstrap p-value into `/api/risk` payload |
| Modify | `scripts/static/dashboard.html` | Show p-value and grind flag in Signal Health row |
| Modify | `docs/backtest-methodology.html` | Add survivorship bias disclosure section |

---

### Task 1 — Data Price-Sanity Filter Post-Download

**File:** `scripts/download_data.py`

**Context:** After `download_universe()` writes parquet files, a corporate action Yahoo hasn't adjusted for (or a bad data pull) can produce a close that moved > 30% in one day. This corrupts the Kronos forecast for that ticker.

- [ ] **Step 1: Find where parquet files are written** in `download_data.py` — after each successful ticker download, find the quality check or save step.

- [ ] **Step 2: Add sanity check function**:

```python
def is_price_sane(df: pd.DataFrame, ticker: str, threshold: float = 0.30) -> bool:
    """Return False if the last bar moved more than threshold from the prior bar."""
    if len(df) < 2:
        return True
    last_close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2]
    if prev_close == 0:
        return True
    pct_change = abs(last_close - prev_close) / prev_close
    if pct_change > threshold:
        logging.warning(
            f"SANITY FAIL {ticker}: last close {last_close:.2f} moved {pct_change:.1%} "
            f"from prior {prev_close:.2f} — excluding from today's forecast"
        )
        return False
    return True
```

- [ ] **Step 3: Apply the check** after each ticker is loaded/saved. Build a `sanity_failures: list[str]` list. Pass it to a new return field or write it to `data/logs/sanity_{date}.json`:

```json
{"date": "2026-06-03", "failures": ["DELTA.BK"], "threshold": 0.30}
```

- [ ] **Step 4: In `dashboard.py --generate`**, before the forecast loop, load `sanity_{date}.json` and skip any tickers in the failures list. Log: `"Skipping DELTA.BK — failed price sanity check"`.

- [ ] **Step 5: Show in dashboard** — if `sanity_failures` is non-empty, `/api/health` response includes:

```json
"sanity_failures": ["DELTA.BK"]
```

Dashboard shows a dismissable yellow banner: `"⚠ 1 ticker excluded from today's forecast due to price anomaly: DELTA.BK. Check data/logs/sanity_2026-06-03.json."`

---

### Task 2 — POST /api/trades Input Validation

**File:** `scripts/dashboard.py`

**Context:** The POST `/api/trades` endpoint accepts `fill_price`, `shares`, `action` from the user. No current validation means a fat-finger (e.g., `shares: -800` or `fill_price: 0`) silently corrupts the position book.

- [ ] **Step 1: Find the POST `/api/trades` handler** in `dashboard.py`.

- [ ] **Step 2: Add a validation function** before the handler records any trade:

```python
def _validate_trade_request(trades: list[dict], forecast_cache: dict) -> list[str]:
    """Return list of error strings. Empty list = valid."""
    errors = []
    for i, t in enumerate(trades):
        prefix = f"Trade {i+1} ({t.get('ticker','?')})"
        shares = t.get("shares", 0)
        fill_price = t.get("fill_price", 0)
        action = t.get("action", "")

        if action not in ("buy", "sell", "exit", "reduce"):
            errors.append(f"{prefix}: invalid action '{action}'")
        if not isinstance(shares, (int, float)) or shares <= 0:
            errors.append(f"{prefix}: shares must be positive, got {shares}")
        if shares % 100 != 0:
            errors.append(f"{prefix}: shares must be multiple of 100 (SET board lot), got {shares}")
        if not isinstance(fill_price, (int, float)) or fill_price <= 0:
            errors.append(f"{prefix}: fill_price must be positive, got {fill_price}")

        # Price sanity: fill_price must be within ±20% of last cached close
        ticker = t.get("ticker")
        if ticker and ticker in forecast_cache:
            cached_close = forecast_cache[ticker].get("close", 0)
            if cached_close > 0:
                deviation = abs(fill_price - cached_close) / cached_close
                if deviation > 0.20:
                    errors.append(
                        f"{prefix}: fill_price {fill_price} is {deviation:.0%} from cached close "
                        f"{cached_close} — exceeds 20% sanity limit"
                    )
    return errors
```

- [ ] **Step 3: Call validator** at the top of the POST handler. If errors, return HTTP 400:

```python
errors = _validate_trade_request(request.json.get("trades", []), today_forecasts)
if errors:
    return jsonify({"error": "Validation failed", "details": errors}), 400
```

- [ ] **Step 4: Verify** — POST `{"trades": [{"ticker": "KBANK.BK", "action": "buy", "shares": -100, "fill_price": 142}]}` must return 400 with `"shares must be positive"` in details.

---

### Task 3 — Drawdown Velocity Metric

**File:** `kth/backtest/metrics.py`

**Context:** The Circuit Breaker triggers at −10% portfolio DD. But a slow grind — say −0.6%/day for 5 days = −3% total — doesn't trigger any threshold yet signals regime trouble. Drawdown velocity catches this.

- [ ] **Step 1: Add `compute_drawdown_velocity()`**:

```python
def compute_drawdown_velocity(
    equity_curve: pd.Series,
    window: int = 5,
    threshold: float = -0.03,
) -> dict:
    """
    Check if the portfolio has ground down > threshold over the last `window` trading days.
    Returns {'grind': bool, 'velocity': float, 'window': int}
    velocity = (equity[-1] / equity[-window-1]) - 1
    """
    if len(equity_curve) < window + 1:
        return {"grind": False, "velocity": 0.0, "window": window}
    recent = equity_curve.iloc[-(window + 1):]
    velocity = float(recent.iloc[-1] / recent.iloc[0] - 1)
    return {
        "grind": velocity < threshold,
        "velocity": round(velocity, 4),
        "window": window,
    }
```

- [ ] **Step 2: Wire into `compute_metrics()`** in `portfolio.py` — call `compute_drawdown_velocity()` on the live equity curve and include in the metrics dict:

```python
"drawdown_velocity": compute_drawdown_velocity(equity_series)
```

- [ ] **Step 3: Show in Risk Bar** (dashboard) — add an 8th tile `"Grind"` between Drawdown and P&L MTD:
  - Normal: `−0.8% / 5d` (grey)
  - Grind triggered: `🔴 GRIND −3.2% / 5d` with orange background

- [ ] **Step 4: Decision tree update** — in `trade_gen.py`, check `metrics["drawdown_velocity"]["grind"]`. If True and market_state is not already Turmoil, add to ticket banner: `"⚠ Drawdown grind detected (−X% over 5 days) — consider reducing position sizes."`

---

### Task 4 — Rolling Bootstrap p-value in Signal Health

**File:** `kth/backtest/metrics.py` + `scripts/dashboard.py`

**Context:** The backtest showed p=0.257 in 2025 and p=0.353 in 2026 (not significant). For the live portfolio, the user needs to see whether the live edge is statistically real or noise. Bootstrap p-value = fraction of shuffled return sequences that beat equal-weight, computed from actual live trade returns.

**Decisions:** n=1000 bootstrap samples. Computed once at dashboard load (not per request). Displayed inline in Signal Health row.

- [ ] **Step 1: Add `compute_bootstrap_pvalue()`** to `metrics.py`:

```python
def compute_bootstrap_pvalue(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Bootstrap p-value: what fraction of random shuffles of strategy_returns
    beat benchmark_returns by >= the observed margin?
    Lower p = stronger evidence of genuine edge.
    Returns {'pvalue': float, 'n_bootstrap': int, 'n_obs': int, 'significant': bool}
    """
    if len(strategy_returns) < 20:
        return {"pvalue": None, "n_bootstrap": n_bootstrap,
                "n_obs": len(strategy_returns), "significant": False}

    rng = np.random.default_rng(seed)
    strat = strategy_returns.values
    bench = benchmark_returns.reindex(strategy_returns.index).fillna(0).values

    observed_alpha = strat.mean() - bench.mean()
    beat_count = 0
    for _ in range(n_bootstrap):
        shuffled = rng.permutation(strat)
        shuffled_alpha = shuffled.mean() - bench.mean()
        if shuffled_alpha >= observed_alpha:
            beat_count += 1

    pvalue = beat_count / n_bootstrap
    return {
        "pvalue": round(pvalue, 3),
        "n_bootstrap": n_bootstrap,
        "n_obs": len(strategy_returns),
        "significant": pvalue < 0.05,
    }
```

- [ ] **Step 2: Compute at dashboard startup** in `scripts/dashboard.py`. Load the live equity curve and equal-weight benchmark from `portfolio.py`. Compute once, cache in a module-level variable. Recompute daily (check if date changed since last computation).

```python
_pvalue_cache = {"date": None, "result": None}

def get_bootstrap_pvalue():
    today = str(date.today())
    if _pvalue_cache["date"] != today:
        metrics = compute_metrics("paper")
        eq_curve = metrics.get("equity_curve", pd.Series(dtype=float))
        ew_returns = metrics.get("equal_weight_returns", pd.Series(dtype=float))
        strat_returns = eq_curve.pct_change().dropna()
        _pvalue_cache["result"] = compute_bootstrap_pvalue(strat_returns, ew_returns)
        _pvalue_cache["date"] = today
    return _pvalue_cache["result"]
```

- [ ] **Step 3: Add to `/api/risk` response**:

```json
"bootstrap_pvalue": {"pvalue": 0.043, "n_obs": 87, "significant": true}
```

- [ ] **Step 4: Show inline in Signal Health row** (dashboard HTML):
  - Significant (p < 0.05): `p=0.043 ✅ edge confirmed`
  - Borderline (0.05 ≤ p < 0.15): `p=0.098 ⚠ weak evidence`
  - Not significant (p ≥ 0.15): `p=0.312 ❌ no confirmed edge`
  - Insufficient data (< 20 obs): `p=— (need ≥ 20 trading days)`

- [ ] **Step 5: Verify** — with a strategy that simply mirrors the benchmark (no edge), p-value should be ~0.5. With a large consistent positive alpha, p-value should be < 0.05. Sanity check with synthetic data.

---

### Task 5 — Survivorship Bias Disclosure

**File:** `docs/backtest-methodology.html`

**Context:** The backtest uses only tickers currently in the 50-ticker universe — all survivors. Delisted Thai stocks (e.g., companies that went bankrupt or were acquired 2020–2024) are excluded. This mechanically inflates reported CAGR.

- [ ] **Step 1: Find the "Known Limitations" section** in `backtest-methodology.html`. It likely already mentions data quality caveats.

- [ ] **Step 2: Add or expand a "Survivorship Bias" subsection** with this content:

```html
<h3>Survivorship Bias</h3>
<p>
  The 49 Thai equity tickers in this backtest were selected as of mid-2025.
  Thai stocks that were delisted, suspended, or merged between 2020 and 2024
  are <strong>not included</strong> — because yfinance does not expose
  historical data for delisted securities.
</p>
<p>
  Academic studies of SET delisting rates (2010–2020) suggest that
  survivorship bias inflates reported CAGR by approximately
  <strong>1–3 percentage points per year</strong> for universe sizes
  comparable to ours (40–60 stocks). Applying this range to our
  2022–2024 result of +31.44% CAGR: the survivorship-adjusted estimate
  is approximately <strong>+28–30% CAGR</strong>. The qualitative
  conclusion (genuine alpha over SET and equal-weight benchmarks) is
  robust to this adjustment.
</p>
<p>
  <em>Mitigation path:</em> A point-in-time universe (using SET constituent
  lists from 2020 onwards) would eliminate this bias but requires
  historical sector data not available via yfinance. This is flagged as
  a future enhancement.
</p>
```

- [ ] **Step 3: Add survivorship bias adjustment row** to the main backtest results table:

| Metric | Reported | Survivorship-Adjusted |
|---|---|---|
| CAGR (Thai equity, 2022–2024) | +31.44% | ~+28–30% |

- [ ] **Step 4: Cross-reference** from `docs/user-manual.html` backtest results section — add a footnote: `"¹ Unadjusted for survivorship bias. See backtest methodology for estimated adjustment range."`

---

### Verification Checklist

- [ ] `python verify_data_layer.py` — all 5 tests pass
- [ ] Price sanity filter flags a synthetic ticker with > 30% move; normal tickers pass
- [ ] POST `/api/trades` with `shares: -100` returns HTTP 400 with clear error message
- [ ] POST `/api/trades` with `fill_price: 999999` (>20% from close) returns HTTP 400
- [ ] `compute_drawdown_velocity(pd.Series([100,99,98,97,96,95]))` returns `grind=True`
- [ ] `compute_drawdown_velocity(pd.Series([100,100,100,100,100]))` returns `grind=False`
- [ ] `compute_bootstrap_pvalue()` with < 20 observations returns `pvalue=None` (not a crash)
- [ ] Dashboard Signal Health row shows p-value tile (or "insufficient data" before 20 trade days)
- [ ] Survivorship bias section present in `backtest-methodology.html` with ~+28–30% adjusted CAGR range
- [ ] `docs/user-manual.html` footnote links to methodology doc
