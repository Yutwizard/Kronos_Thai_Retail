# Flask Dashboard Target Prices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show execution-scale P50 and P95 forecast prices beside expected return in the Flask dashboard's Morning Brief and Full Ranking tables.

**Architecture:** Add display fields while loading forecast rows, scaling DR forecast prices from the underlying price scale into the execution ticker's price scale. Keep the existing raw model fields, ranking, trade generation, and trade-ticket tables unchanged. Render the new fields through the shared Morning Brief and Full Ranking table builders.

**Tech Stack:** Python, pandas, Flask JSON API, vanilla JavaScript/HTML, repository verification scripts.

---

### Task 1: Add Target-Price Transformation Tests

**Files:**
- Create: `tests/test_trade_gen_display_prices.py`
- Modify: `kth/trading/trade_gen.py`

- [ ] **Step 1: Write the failing tests**

Add a focused pure-function test contract:

```python
from kth.trading.trade_gen import _execution_forecast_price


def test_execution_forecast_price_keeps_native_price_scale():
    assert _execution_forecast_price(100.0, 110.0, 100.0) == 110.0


def test_execution_forecast_price_scales_underlying_forecast_to_dr_price():
    assert _execution_forecast_price(100.0, 110.0, 25.0) == 27.5


def test_execution_forecast_price_falls_back_when_underlying_close_is_invalid():
    assert _execution_forecast_price(0.0, 110.0, 25.0) == 110.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/test_trade_gen_display_prices.py -q
```

Expected: FAIL because `_execution_forecast_price` does not exist yet.

- [ ] **Step 3: Implement the minimal transformation helper**

In `kth/trading/trade_gen.py`, add this helper before `load_forecasts`:

```python
def _execution_forecast_price(underlying_close: float, forecast_price: float,
                              execution_close: float) -> float:
    """Convert an underlying forecast price into execution-ticker units."""
    if underlying_close <= 0 or execution_close <= 0:
        return forecast_price
    return execution_close * forecast_price / underlying_close
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/test_trade_gen_display_prices.py -q
```

Expected: 3 passed.

### Task 2: Include Display Prices in Forecast API Rows

**Files:**
- Modify: `kth/trading/trade_gen.py:94-147`
- Modify: `tests/test_trade_gen_display_prices.py`

- [ ] **Step 1: Add row-level assertions to the test fixture**

Extend the test file with a representative row calculation assertion:

```python

def test_display_prices_are_execution_scale_values():
    underlying_close = 100.0
    execution_close = 25.0
    assert _execution_forecast_price(underlying_close, 110.0, execution_close) == 27.5
    assert _execution_forecast_price(underlying_close, 120.0, execution_close) == 30.0
```

- [ ] **Step 2: Run the focused tests before the production change**

Run:

```bash
pytest tests/test_trade_gen_display_prices.py -q
```

Expected: PASS, confirming the conversion contract before wiring it into rows.

- [ ] **Step 3: Add target fields to `load_forecasts`**

After resolving `exec_close`, calculate:

```python
target_price = _execution_forecast_price(current_close, p50, exec_close)
p95_price = _execution_forecast_price(current_close, p95, exec_close)
```

Add these rounded fields to each appended row:

```python
"target_price": round(target_price, 2),
"p95_price": round(p95_price, 2),
```

Do not replace `p50_close` or `p95_close`; those remain the raw model outputs.

- [ ] **Step 4: Run focused and existing trade-generation tests**

Run:

```bash
pytest tests/test_trade_gen_display_prices.py tests/test_pipeline_smoke.py -q
```

Expected: PASS.

### Task 3: Render Target and P95 Beside Expected Return

**Files:**
- Modify: `scripts/static/dashboard.html:493-589`

- [ ] **Step 1: Add column definitions and legend text**

Extend `COL` with:

```javascript
target: "Target: model's median (P50) forecast price in the tradable ticker's price scale.",
p95: "P95: upper forecast price in the tradable ticker's price scale. It is an uncertainty boundary, not a guaranteed price.",
```

Update the Morning Brief legend to mention `Target (P50)` and `P95`.

- [ ] **Step 2: Add columns to `_buildBullBearTable`**

Place `Target` and `P95` immediately after `Exp Ret` in the header. After the expected-return cell, add:

```javascript
+ '<td class="num">' + ((f.target_price ?? f.p50_close)?.toFixed(2) || "—") + '</td>'
+ '<td class="num">' + ((f.p95_price ?? f.p95_close)?.toFixed(2) || "—") + '</td>'
```

The fallback keeps historical or older API rows renderable.

- [ ] **Step 3: Add columns to `_buildRankingTable`**

Apply the same header and cell changes to the Full Ranking table immediately after `Exp Ret`.

- [ ] **Step 4: Verify the source contains both table integrations**

Run:

```bash
grep -n "Target\|P95\|target_price\|p95_price" scripts/static/dashboard.html
```

Expected: matches in `COL`, both table headers, both table row builders, and the legend.

### Task 4: Verify End-to-End Dashboard Compatibility

**Files:**
- Modify: none

- [ ] **Step 1: Run the relevant Python verification suite**

Run:

```bash
pytest tests/test_trade_gen_display_prices.py tests/test_pipeline_smoke.py tests/test_portfolio.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Check Python syntax**

Run:

```bash
python -m py_compile kth/trading/trade_gen.py scripts/dashboard.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Check dashboard HTML JavaScript syntax**

Run:

```bash
node --check <(python -c 'from pathlib import Path; import re; s=Path("scripts/static/dashboard.html").read_text(); print(re.search(r"<script>(.*?)</script>", s, re.S).group(1))')
```

Expected: no syntax errors.

- [ ] **Step 4: Inspect the final diff**

Run:

```bash
git diff --check
git diff -- kth/trading/trade_gen.py scripts/static/dashboard.html tests/test_trade_gen_display_prices.py
```

Expected: no whitespace errors, and only the target-price fields, rendering, tests, and required documentation changes are present.
