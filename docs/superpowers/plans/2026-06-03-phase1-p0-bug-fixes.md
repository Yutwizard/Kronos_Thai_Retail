# Phase 1 — P0 Bug Fixes

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two correctness bugs in `trade_gen.py` that produce wrong friction costs and duplicate a capital constant that already lives in `portfolio.py`.

**Decisions locked (grilling session 2026-06-03):**
- Friction must be computed per-ticket from the `FRICTION` dict, not from a hardcoded approximate rate.
- `INITIAL_CAPITAL` must have a single source of truth in `portfolio.py`; `trade_gen.py` imports it.

**Estimated time:** 15 minutes total. No new files. No dashboard changes needed.

---

### File Structure

| Action | Path | Change |
|--------|------|--------|
| Modify | `kth/trading/trade_gen.py` | Replace hardcoded `0.00268`; import `INITIAL_CAPITAL` from portfolio |

---

### Task 1 — Replace hardcoded friction with FRICTION dict (lines 187–191)

**File:** `kth/trading/trade_gen.py`

**Root cause:** Lines 189–190 multiply gross proceeds by `0.00268` for all tickers regardless of asset class. This is the exact one-way rate for `thai_equity` (0.168% commission + 0.10% slippage), but will silently produce wrong values if any non-thai-equity ticker is ever added to the dashboard.

- [ ] **Step 1: Add a private helper function** immediately above `generate_trade_ticket`:

```python
def _one_way_friction(ticker: str) -> float:
    """One-way friction rate for a ticker (commission + slippage)."""
    cls = get_ticker_class(ticker)
    fric = FRICTION.get(cls, {"commission_oneway": 0.002, "slippage_oneway": 0.001})
    return fric["commission_oneway"] + fric["slippage_oneway"]
```

- [ ] **Step 2: Replace the aggregate friction block** (current lines 187–191):

Replace:
```python
gross_sells = sum(e["estimated_thb"] for e in exits) + sum(r["estimated_thb"] for r in reduces)
gross_buys = sum(b["estimated_thb"] for b in buys)
friction_sells = gross_sells * 0.00268
friction_buys = gross_buys * 0.00268
total_friction = round(friction_sells + friction_buys, 2)
```

With:
```python
gross_sells = sum(e["estimated_thb"] for e in exits) + sum(r["estimated_thb"] for r in reduces)
gross_buys = sum(b["estimated_thb"] for b in buys)
friction_sells = sum(e["estimated_thb"] * _one_way_friction(e["ticker"]) for e in exits) + \
                 sum(r["estimated_thb"] * _one_way_friction(r["ticker"]) for r in reduces)
friction_buys = sum(b["estimated_thb"] * _one_way_friction(b["ticker"]) for b in buys)
total_friction = round(friction_sells + friction_buys, 2)
```

- [ ] **Step 3: Verify** — for current Thai-equity-only dashboard, the computed value must equal the old value within ±1 THB. Spot-check: a 45,000 THB buy → `45000 × 0.00268 = 120.60 THB` (old) vs `45000 × (0.00168 + 0.001) = 120.60 THB` (new). Identical for thai_equity ✅.

---

### Task 2 — Remove duplicated INITIAL_CAPITAL constant

**File:** `kth/trading/trade_gen.py`

**Root cause:** `INITIAL_CAPITAL = 500000.0` is defined at line 108 of `trade_gen.py` AND at the top of `portfolio.py`. Two definitions = drift risk when the user changes capital.

- [ ] **Step 1: Add import** at the top of `trade_gen.py`, alongside the existing portfolio import:

```python
from kth.trading.portfolio import get_positions, compute_metrics, INITIAL_CAPITAL
```

- [ ] **Step 2: Remove** the local `INITIAL_CAPITAL = 500000.0` line from `trade_gen.py`.

- [ ] **Step 3: Verify** — `python -c "from kth.trading.trade_gen import generate_trade_ticket; print('ok')"` must not raise `ImportError` or `NameError`.

---

### Verification Checklist

- [ ] `python verify_data_layer.py` still passes all 5 tests (no regressions in data layer)
- [ ] `python -c "from kth.trading import trade_gen, portfolio; print('imports ok')"` succeeds
- [ ] Friction for a 50,000 THB thai_equity sell = `50000 × 0.00268 = 134 THB` (unchanged from before)
- [ ] No other file references `INITIAL_CAPITAL` outside `portfolio.py` and `trade_gen.py` imports
