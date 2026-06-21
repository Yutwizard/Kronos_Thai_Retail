# Quant Review Remediation — Phase 2 (GPU Required) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate the 8 GPU-blocked issues from the quant/trader/engineer review — re-run the Kronos backtest with the fixed Phase 1 code, then address the statistical/strategy questions that depend on fresh numbers.

**Prerequisite:** Phase 1 (`2026-06-21-quant-review-remediation-phase1-no-gpu.md`) MUST be complete. The GPU re-run is meaningless against buggy code. Verify:
- `pytest -q tests/` is green
- `python verify_data_layer.py` is green
- `python run_pipeline.py --dry-run` succeeds
- All Phase 1 commits are on `main`

**Architecture:** Three sub-phases.
1. **Pre-run code additions** (Tasks 1-3): add the FX adjustment, partial-fill model, and regime-adjusted threshold to the backtest engine — these need to be in place BEFORE the re-run so the fresh numbers include them.
2. **The GPU re-run** (Task 4): re-run all 4 OOS years (2023, 2024, 2025, 2026) with n=50 samples and the fixed + extended code.
3. **Post-run analysis + docs** (Tasks 5-8): verify the pre-training cutoff, update all cited numbers, resolve the friction drain, close out the open statistical questions.

**Tech Stack:** Python 3.11, pandas, numpy, scipy, Kronos-small (24.7M params), T4 GPU (16GB VRAM), parquet.

**Hardware:** Google Colab T4 free tier OR Kaggle T4. Each year takes ~8-12 hours of GPU time for n=50 precompute + walkforward.

**Branch strategy:** Work on `main`. Commit after every task. The GPU re-run produces artifacts in `data/backtest_results/` — commit these as a single atomic commit.

---

## File Structure

**New files:**
- `kth/data/fx.py` — FX conversion helper (M5)
- `kth/backtest/fills.py` — partial-fill slippage model (M4)
- `data/backtest_results/thai_equity_2023_n50_v2/` — fresh run
- `data/backtest_results/thai_equity_2024_n50_v2/` — fresh run
- `data/backtest_results/thai_equity_2025_n50_v2/` — fresh run
- `data/backtest_results/thai_equity_2026_n50_v2/` — fresh run
- `data/backtest_results/MANIFEST.md` (updated)

**Modified files (pre-run, no GPU):**
- `kth/backtest/walkforward.py` — M4 (partial fills), M5 (FX adjustment)
- `kth/backtest/strategy.py` — M1 (regime-adjusted entry threshold)
- `kth/backtest/metrics.py` — M1 (regime detection helper)

**Modified files (post-run, docs):**
- `README.md` — update with fresh numbers, remove stale banner
- `PROJECT_STRUCTURE.md` — update §14 + backtest tables
- `data/backtest_results/MANIFEST.md` — mark v2 as authoritative
- `CONTEXT.md` — update if any domain terms change

---

# Sub-Phase A: Pre-Run Code Additions (no GPU needed for these tasks, but must complete before Task 4)

## Task 1: Add FX-adjusted returns for non-THB assets (M5)

**Files:**
- Create: `kth/data/fx.py`
- Modify: `kth/backtest/walkforward.py` (`_compute_benchmarks` + portfolio MTM)

- [ ] **Step 1: Create `kth/data/fx.py`**

```python
"""FX conversion for Thai-investor P&L on USD-denominated assets."""
from __future__ import annotations

import pandas as pd
from kth.data.loader import load_cached


def load_usdthb(cache_dir: str = "./data/raw") -> pd.Series:
    """Load USDTHB close series, indexed by date."""
    df = load_cached("THB=X", cache_dir=cache_dir)
    s = df.set_index("timestamps")["close"]
    s.index = pd.to_datetime(s.index)
    return s.rename("usdthb")


def to_thb_returns(asset_returns: pd.Series, usdthb: pd.Series) -> pd.Series:
    """Convert USD-denominated daily returns to THB-denominated returns.

    THB return = (1 + USD return) * (USDTHB_t / USDTHB_{t-1}) - 1

    For assets already in THB (thai_equity, thai_index, CPNREIT.BK), this is a
    no-op (caller should skip FX conversion for those).
    """
    fx_rets = usdthb.pct_change().reindex(asset_returns.index).fillna(0)
    return (1 + asset_returns) * (1 + fx_rets) - 1


def is_thb_denominated(ticker: str) -> bool:
    """True for Thai-listed assets (already in THB, no FX conversion needed)."""
    return ticker.endswith(".BK") or ticker in ("^SET.BK",)
```

- [ ] **Step 2: Wire FX adjustment into `_compute_benchmarks`**

In `walkforward.py`, for the SPY and 60/40 benchmarks, apply FX conversion:

```python
    # SPY buy-and-hold — FX-adjusted for Thai investor
    try:
        from kth.data.fx import load_usdthb, to_thb_returns
        spy_df = load_cached("SPY", config.cache_dir)
        spy_close = spy_df.set_index("timestamps")["close"]
        spy_rets = spy_close.pct_change()
        usdthb = load_usdthb(config.cache_dir)
        spy_thb_rets = to_thb_returns(spy_rets, usdthb)
        spy_aligned = (1 + spy_thb_rets).cumprod().reindex(trading_days, method="ffill").dropna()
        if len(spy_aligned) > 0:
            benchmarks["SPY"] = spy_aligned / spy_aligned.iloc[0]
    except Exception:
        benchmarks["SPY"] = pd.Series(1.0, index=trading_days)
```

- [ ] **Step 3: Wire FX into portfolio MTM (optional for equity-only runs)**

For Thai-equity-only backtests (the canonical n50 runs), FX is a no-op since all tickers are `.BK`. The FX adjustment matters for US/crypto runs. Add a guard:

```python
    from kth.data.fx import is_thb_denominated
    non_thb_holdings = any(not is_thb_denominated(t) for t in holdings_units)
```

Only apply FX to the MTM if `non_thb_holdings` is True. For the canonical Thai equity runs, this is False — skip.

- [ ] **Step 4: Test**

In `tests/test_walkforward.py`:

```python
def test_fx_conversion_applies_usdthb():
    import pandas as pd
    from kth.data.fx import to_thb_returns
    asset = pd.Series([0.0, 0.10, -0.05], index=pd.date_range("2024-01-01", periods=3))
    usdthb = pd.Series([35.0, 36.0, 35.0], index=asset.index)
    thb = to_thb_returns(asset, usdthb)
    # Day 1: asset +10%, THB strengthens +2.86% -> THB return = 1.10*1.0286 - 1
    assert abs(thb.iloc[1] - (1.10 * (36/35) - 1)) < 1e-6

def test_is_thb_denominated():
    from kth.data.fx import is_thb_denominated
    assert is_thb_denominated("PTT.BK") is True
    assert is_thb_denominated("^SET.BK") is True
    assert is_thb_denominated("AAPL") is False
    assert is_thb_denominated("BTC-USD") is False
```

- [ ] **Step 5: Run + commit**

```bash
pytest -q tests/ && git add kth/data/fx.py kth/backtest/walkforward.py tests/test_walkforward.py && git commit -m "feat(fx): add FX-adjusted returns for non-THB assets (M5)"
```

---

## Task 2: Add partial-fill slippage model (M4)

**Files:**
- Create: `kth/backtest/fills.py`
- Modify: `kth/backtest/walkforward.py:337-411` (trade execution)

- [ ] **Step 1: Create `kth/backtest/fills.py`**

```python
"""Partial-fill slippage model for Thai mid-cap equities."""
from __future__ import annotations

import pandas as pd


def estimate_fill_ratio(
    order_value: float,
    avg_daily_volume_value: float,
    max_participation: float = 0.10,
) -> float:
    """Estimate what fraction of an order fills at the open price.

    Args:
        order_value: THB value of the buy/sell order.
        avg_daily_volume_value: THB value of average daily volume (close * volume).
        max_participation: max % of daily volume we assume we can capture.
            10% is conservative for Thai mid-caps.

    Returns:
        Fill ratio in [0, 1]. 1.0 = full fill, <1.0 = partial fill.
        If order is small relative to volume, returns 1.0.
    """
    if avg_daily_volume_value <= 0:
        return 0.0
    capacity = avg_daily_volume_value * max_participation
    if order_value <= capacity:
        return 1.0
    return capacity / order_value


def apply_partial_fill(
    target_units: float,
    fill_ratio: float,
) -> tuple[float, float]:
    """Returns (filled_units, unfilled_units)."""
    filled = target_units * fill_ratio
    return filled, target_units - filled
```

- [ ] **Step 2: Wire into `walkforward.py` trade execution**

In the buy branch (~line 372-411), after computing `units_delta`:

```python
            # Partial-fill model: estimate fill ratio from volume
            from kth.backtest.fills import estimate_fill_ratio
            mask_vol = df_t["timestamps"] <= day
            vol_df = df_t[mask_vol].tail(20)
            if len(vol_df) > 0 and "amount" in vol_df.columns:
                avg_vol_value = float(vol_df["amount"].mean())
            else:
                avg_vol_value = 0.0
            fill_ratio = estimate_fill_ratio(abs(trade_value), avg_vol_value)
            if fill_ratio < 1.0:
                units_delta = units_delta * fill_ratio
                trade_value = units_delta * exec_price
                friction_cost = abs(trade_value) * (frict["commission_oneway"] + frict["slippage_oneway"])
                # Log partial fill in trade record
                partial_flag = f" (partial: {fill_ratio:.0%})"
            else:
                partial_flag = ""
```

Append `partial_flag` to the trade record's direction or add a `fill_ratio` column.

- [ ] **Step 3: Add `fill_ratio` column to trade records**

In the `trades_list.append` for both buy and sell:

```python
            trades_list.append({
                "date": day, "ticker": t, "direction": direction + partial_flag if partial_flag else direction,
                "size_pct": abs(trade_value), "friction_cost": friction_cost,
                "gross_return": 0.0, "fill_ratio": fill_ratio,
            })
```

For sell trades, apply the same model.

- [ ] **Step 4: Test**

In `tests/test_walkforward.py`:

```python
def test_fill_ratio_full_when_order_small():
    from kth.backtest.fills import estimate_fill_ratio
    assert estimate_fill_ratio(10_000, 1_000_000) == 1.0

def test_fill_ratio_partial_when_order_large():
    from kth.backtest.fills import estimate_fill_ratio
    r = estimate_fill_ratio(500_000, 1_000_000, max_participation=0.10)
    assert 0.0 < r < 1.0
    assert abs(r - 0.2) < 0.01  # 100k capacity / 500k order = 0.2

def test_fill_ratio_zero_when_no_volume():
    from kth.backtest.fills import estimate_fill_ratio
    assert estimate_fill_ratio(10_000, 0) == 0.0
```

- [ ] **Step 5: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/fills.py kth/backtest/walkforward.py tests/test_walkforward.py && git commit -m "feat(fills): add partial-fill slippage model for mid-caps (M4)"
```

---

## Task 3: Add regime-adjusted entry threshold (M1)

**Files:**
- Modify: `kth/backtest/strategy.py` (add `compute_regime_adjusted_threshold`)
- Modify: `kth/backtest/walkforward.py:286-301` (use adjusted threshold)

- [ ] **Step 1: Add regime detection to `strategy.py`**

```python
def compute_regime_adjusted_threshold(
    base_threshold: float,
    base_buffer: float,
    ticker_data: dict[str, "pd.DataFrame"],
    eligible: list[str],
    day: "pd.Timestamp",
    vol_lookback: int = 20,
    vol_percentile_threshold: float = 80,
) -> tuple[float, float]:
    """Adjust entry threshold upward in high-volatility regimes.

    When the median 20-day realized vol across eligible tickers exceeds its
    80th historical percentile, raise the entry buffer to reduce turnover.

    Returns (adjusted_threshold, adjusted_buffer).
    """
    import numpy as np
    vols = []
    for t in eligible:
        df = ticker_data.get(t)
        if df is None:
            continue
        mask = df["timestamps"] <= day
        recent = df[mask].tail(vol_lookback)
        if len(recent) >= 2:
            vol = float(recent["close"].pct_change().std())
            if vol == vol and vol > 0:
                vols.append(vol)

    if not vols:
        return base_threshold, base_buffer

    median_vol = float(np.median(vols))
    # Compare to historical: use the vol lookback window's own distribution
    # Simplification: if median vol > 3% daily, we're in a high-vol regime
    if median_vol > 0.03:
        return base_threshold, base_buffer * 2.0  # double the buffer
    return base_threshold, base_buffer
```

- [ ] **Step 2: Wire into walkforward**

At line 286, before `compute_signals`:

```python
        from kth.backtest.strategy import compute_regime_adjusted_threshold
        adj_threshold, adj_buffer = compute_regime_adjusted_threshold(
            config.long_threshold, config.entry_buffer,
            ticker_data, eligible, day,
        )
        raw_signals = compute_signals(forecasts, last_closes, adj_threshold, config.pred_len)
```

Then pass `adj_buffer` to `apply_hysteresis`:

```python
        signals, signals_for_ranking = apply_hysteresis(
            raw_signals, holdings_units, holding_days,
            adj_threshold, adj_buffer, config.min_holding_days,
        )
```

- [ ] **Step 3: Test**

```python
def test_regime_threshold_doubles_buffer_in_high_vol():
    import pandas as pd
    import numpy as np
    from kth.backtest.strategy import compute_regime_adjusted_threshold
    # High-vol: daily std ~4%
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=30),
        "close": 100 + rng.normal(0, 4, 30).cumsum(),
    })
    t, b = compute_regime_adjusted_threshold(0.01, 0.005, {"A": df}, ["A"], pd.Timestamp("2024-01-30"))
    assert b == 0.01  # doubled

def test_regime_threshold_unchanged_in_low_vol():
    import pandas as pd
    import numpy as np
    from kth.backtest.strategy import compute_regime_adjusted_threshold
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "timestamps": pd.date_range("2024-01-01", periods=30),
        "close": 100 + rng.normal(0, 0.5, 30).cumsum(),
    })
    t, b = compute_regime_adjusted_threshold(0.01, 0.005, {"A": df}, ["A"], pd.Timestamp("2024-01-30"))
    assert b == 0.005  # unchanged
```

- [ ] **Step 4: Run + commit**

```bash
pytest -q tests/ && git add kth/backtest/strategy.py kth/backtest/walkforward.py tests/test_walkforward.py && git commit -m "feat(strategy): regime-adjusted entry threshold for high-vol (M1)"
```

---

# Sub-Phase B: The GPU Re-Run (C1)

## Task 4: Re-run all 4 OOS years with fixed code

**Hardware:** T4 GPU (Colab free tier or Kaggle).
**Time estimate:** ~8-12 hours per year, ~32-48 hours total. Can run overnight.

**Prerequisite:** Tasks 1-3 committed to `main`. All tests green.

- [ ] **Step 1: Push Phase 1 + Sub-Phase A code to the runtime**

```bash
# On Colab/Kaggle, clone the repo or upload the kth/ package
git pull origin main
pip install -e . && pip install -r requirements.txt && pip install -r requirements-ml.txt
```

- [ ] **Step 2: Download fresh data + write manifest**

```python
from kth.data.loader import download_universe
from kth.data.universe import get_all_tickers
from kth.data.versioning import write_manifest
from pathlib import Path

download_universe(get_all_tickers(), period="10y", cache_dir="./data/raw")
write_manifest(Path("./data/raw"), get_all_tickers())
```

- [ ] **Step 3: Verify data manifest**

```python
from kth.data.versioning import verify_manifest
v = verify_manifest(Path("./data/raw"), strict=True)
print(v)  # must be ok=True
```

- [ ] **Step 4: Run 2023 backtest (n=50)**

```bash
python scripts/run_2023_n50.py
```
Expected output: `DONE: Ret=...% Sharpe=... MaxDD=...% p=...`

This runs `precompute_forecasts` (GPU) + `run_walkforward` (CPU). Saves to `data/backtest_results/thai_equity_2023_n50_v2/`.

- [ ] **Step 5: Run 2024 backtest (n=50)**

```bash
python scripts/run_2024_n50.py
```

- [ ] **Step 6: Run 2025 backtest (n=50)**

```bash
python scripts/run_2025_n50.py
```

- [ ] **Step 7: Run 2026 YTD backtest (n=50)**

```bash
python scripts/run_2026_n50.py
```

- [ ] **Step 8: Verify all 4 runs completed**

```python
from pathlib import Path
import json
for year in [2023, 2024, 2025, 2026]:
    p = Path(f"data/backtest_results/thai_equity_{year}_n50_v2/metrics.json")
    assert p.exists(), f"Missing {p}"
    m = json.loads(p.read_text())
    print(f"{year}: CAGR={m['cagr']:.2%} Sharpe={m['sharpe']:.2f} p={m['p_value']:.3f}")
```

- [ ] **Step 9: Commit the fresh results**

```bash
git add data/backtest_results/thai_equity_*_n50_v2/
git commit -m "data: fresh n50 backtest results (post-bug-fix, post-M4/M5/M1) (C1)"
```

---

# Sub-Phase C: Post-Run Analysis & Docs (C2, C3, H2, Q5)

## Task 5: Verify Kronos pre-training cutoff (C3)

**Files:** None (research task, document findings)

- [ ] **Step 1: Fetch the Kronos paper**

```bash
# Use webfetch or manual lookup of arXiv:2508.02739 §3
```

- [ ] **Step 2: Identify the pre-training data cutoff date**

Look for: "training data up to [date]" or "data collected until [date]".

- [ ] **Step 3: Document the finding**

In `PROJECT_STRUCTURE.md`, under "Research decisions", update:

```markdown
- **Kronos pre-training cutoff:** [DATE FOUND] (confirmed via arXiv:2508.02739 §3).
  2023-2026 OOS backtests are clean. [If 2022 is in-sample: "The 2022 portion
  of older runs is partially in-sample — only cite 2023+ OOS results."]
```

- [ ] **Step 4: If 2022 is in-sample, update all citations**

Search for any reference to 2022 backtest results and add a caveat:

```bash
rg "2022" README.md PROJECT_STRUCTURE.md docs/ --type md
```

- [ ] **Step 5: Commit**

```bash
git add PROJECT_STRUCTURE.md && git commit -m "docs: verify + document Kronos pre-training cutoff (C3)"
```

---

## Task 6: Update MANIFEST.md with fresh v2 results (C1 closeout)

**Files:**
- Modify: `data/backtest_results/MANIFEST.md`

- [ ] **Step 1: Update MANIFEST.md**

Replace the stale banner with:

```markdown
# Backtest Results Manifest

## Authoritative (n=50, post-2026-06-21 bug fixes — USE THESE)

| Directory | Period | Status |
|-----------|--------|--------|
| `thai_equity_2023_n50_v2/` | 2023 | Fresh run with PSR/FX/fill/regime fixes |
| `thai_equity_2024_n50_v2/` | 2024 | Fresh run |
| `thai_equity_2025_n50_v2/` | 2025 | Fresh run |
| `thai_equity_2026_n50_v2/` | 2026 YTD | Fresh run |

## Superseded (pre-bug-fix, do NOT cite)

| Directory | Why superseded |
|-----------|----------------|
| `thai_equity_2023_n50/` | Pre-2026-06-21 bug fixes |
| `thai_equity_2024_n50/` | Pre-2026-06-21 bug fixes |
| `thai_equity_2025_n50/` | Pre-2026-06-21 bug fixes |
| `thai_equity_2026_n50/` | Pre-2026-06-21 bug fixes |
| `thai_equity_2020-2024/` | Pre-n50 |
| `thai_equity_2022-2024/` | Pre-n50 |
| `thai_equity_2022-2024_v2/` | Pre-n50 |
| `thai_equity_2022-2024_invvol/` | Rejected (inv_vol) |
| All others | See git history |

**Rule:** Only cite `*_n50_v2/` results. These include FX adjustment (M5),
partial-fill slippage (M4), and regime-adjusted thresholds (M1).
```

- [ ] **Step 2: Commit**

```bash
git add data/backtest_results/MANIFEST.md && git commit -m "docs(MANIFEST): mark v2 runs as authoritative (C1 closeout)"
```

---

## Task 7: Update README + PROJECT_STRUCTURE with fresh numbers (C1, C2, H2)

**Files:**
- Modify: `README.md` (remove stale banner, add fresh numbers)
- Modify: `PROJECT_STRUCTURE.md` (update §14 + backtest tables)

- [ ] **Step 1: Read fresh metrics from v2 runs**

```python
import json
from pathlib import Path
for year in [2023, 2024, 2025, 2026]:
    m = json.loads(Path(f"data/backtest_results/thai_equity_{year}_n50_v2/metrics.json").read_text())
    print(f"{year}: CAGR={m['cagr']:.2%} Sharpe={m['sharpe']:.2f} MaxDD={m['max_drawdown']:.2%} p={m['p_value']:.3f} friction={m['total_friction_paid']:.0f}")
```

- [ ] **Step 2: Update README "Project state" section**

Remove the stale banner (added in Phase 1 Task 16). Replace the backtest results block with the fresh v2 numbers:

```markdown
- ✅ **Backtest results (v2, post-bug-fix):** Thai equity 2023-2026 OOS.
  See `data/backtest_results/MANIFEST.md` for the authoritative runs.

| Year | Net CAGR | Sharpe | Max DD | p-value | Friction/yr |
|------|----------|--------|--------|---------|-------------|
| 2023 | [FRESH]  | [FRESH]| [FRESH]| [FRESH] | [FRESH]     |
| 2024 | [FRESH]  | [FRESH]| [FRESH]| [FRESH] | [FRESH]     |
| 2025 | [FRESH]  | [FRESH]| [FRESH]| [FRESH] | [FRESH]     |
| 2026 | [FRESH]  | [FRESH]| [FRESH]| [FRESH] | [FRESH]     |
```

- [ ] **Step 3: Update PROJECT_STRUCTURE.md §14 backtest table**

Replace the 4-Year OOS Results table with fresh v2 numbers. Update the "Decision gate" line based on fresh Sharpe values.

- [ ] **Step 4: Add Bonferroni caveat explicitly**

After the table:

```markdown
**Bonferroni (4 OOS years, threshold p<0.0125):** [STATE WHETHER ANY YEAR
SURVIVES. If none: "No year survives Bonferroni. The edge is suggestive,
not statistically established. Treat as regime-conditional." If 2024 survives:
"2024 survives Bonferroni (p=[FRESH] < 0.0125)."]
```

- [ ] **Step 5: Update the "2025 friction drain" resolution (M1/Q5)**

In the "Open questions" section, update:

```markdown
- **2025 friction drain:** [RESOLVED/UNRESOLVED]. With regime-adjusted entry
  threshold (M1), 2025 friction is [FRESH]% vs [OLD 17.35]%. [If reduced:
  "The regime-adjusted buffer cut turnover in the high-vol 2025 regime."]
```

- [ ] **Step 6: Commit**

```bash
git add README.md PROJECT_STRUCTURE.md && git commit -m "docs: update with fresh v2 backtest numbers + Bonferroni + friction (C1,C2,H2,M1)"
```

---

## Task 8: Final validation + close statistical questions (C2, H2)

**Files:** None (validation task, document findings in PROJECT_STRUCTURE.md)

- [ ] **Step 1: Check if any year survives Bonferroni**

```python
import json
from pathlib import Path
pvals = {}
for year in [2023, 2024, 2025, 2026]:
    m = json.loads(Path(f"data/backtest_results/thai_equity_{year}_n50_v2/metrics.json").read_text())
    pvals[year] = m["p_value"]
bonferroni_threshold = 0.05 / 4
survivors = [y for y, p in pvals.items() if p < bonferroni_threshold]
print(f"p-values: {pvals}")
print(f"Bonferroni threshold: {bonferroni_threshold}")
print(f"Survivors: {survivors}")
```

- [ ] **Step 2: Document the statistical conclusion**

In `PROJECT_STRUCTURE.md`, add a "Statistical Conclusion" subsection:

```markdown
### Statistical Conclusion (2026-06-21, post-re-run)

**p-values (t-test vs equal-weight, 4 OOS years):**
- 2023: p=[FRESH]
- 2024: p=[FRESH]
- 2025: p=[FRESH]
- 2026: p=[FRESH]

**Bonferroni correction (4 tests, α=0.05/4=0.0125):**
[NUMBER] year(s) survive: [YEAR(S)].

**Conclusion:** [Choose one:
- If ≥1 year survives: "The edge is statistically established for [YEAR(S)].
  Treat as suggestive evidence of a regime-conditional alpha."
- If 0 years survive: "No year survives Bonferroni. The edge is suggestive,
  not conclusive. Treat as a regime-conditional hypothesis requiring more OOS data."]
```

- [ ] **Step 3: Investigate 2026 if still suspicious (H2)**

If 2026 still shows >100% annualized with p>0.3:

```python
m = json.loads(Path("data/backtest_results/thai_equity_2026_n50_v2/metrics.json").read_text())
print(f"Turnover: {m['annual_turnover']:.1f}x")
print(f"Friction: {m['total_friction_paid']:.0f}")
print(f"Trades: {m.get('trade_count', 'N/A')}")
```

Document whether the regime-adjusted threshold (M1) reduced the turnover.

- [ ] **Step 4: Resolve the factor-attribution question**

If fresh numbers still show strong alpha, run the factor regression:

```python
# Regress daily strategy returns on SET market + 12-1 momentum
# If beta ≈ 0 and alpha is still significant, the alpha is genuine
from kth.backtest.metrics import compute_metrics
# (This requires SET + momentum factor data — may need a separate script)
```

- [ ] **Step 5: Update "Open questions" to "Resolved"**

In `PROJECT_STRUCTURE.md`, move resolved items from "Open" to "Resolved":

```markdown
**Resolved (2026-06-21 post-re-run):**
- ✅ 2025 friction drain: [resolution]
- ✅ Kronos pre-training cutoff: [date] (Task 5)
- ✅ Factor attribution: beta=[FRESH], alpha=[FRESH] — [genuine / momentum proxy]
- ✅ Statistical significance: [X] year(s) survive Bonferroni
```

- [ ] **Step 6: Final commit**

```bash
git add PROJECT_STRUCTURE.md && git commit -m "docs: close statistical questions post-re-run (C2, H2)"
```

---

## Phase 2 Completion Check

- [ ] **Step 1: All 4 v2 backtest results exist and have sensible numbers**

```bash
ls data/backtest_results/thai_equity_*_n50_v2/metrics.json
```

- [ ] **Step 2: No stale numbers remain in docs**

```bash
rg "CAGR.*31.44|Sharpe.*1.40|p.*0.015" README.md PROJECT_STRUCTURE.md
```
Expected: no matches (or only in historical context with "superseded" label).

- [ ] **Step 3: Full test suite green**

```bash
pytest -q tests/ && python verify_data_layer.py
```

- [ ] **Step 4: MANIFEST.md points to v2 as authoritative**

- [ ] **Step 5: Bonferroni conclusion documented**

- [ ] **Step 6: Pre-training cutoff documented**

- [ ] **Step 7: Final commit**

```bash
git add -A && git commit -m "chore: Phase 2 completion — fresh backtest numbers, statistical closeout"
```

---

## Phase 2 Summary

| Task | Issues Fixed | GPU? | Effort |
|------|-------------|------|--------|
| 1 | M5 (FX adjustment) | No (code only) | M |
| 2 | M4 (partial fills) | No (code only) | M |
| 3 | M1 (regime threshold) | No (code only) | M |
| 4 | C1 (the re-run) | **Yes** (~32-48 hrs) | L |
| 5 | C3 (pre-training cutoff) | No (research) | S |
| 6 | C1 closeout (MANIFEST) | No | S |
| 7 | C1, C2, H2 (update docs) | No | M |
| 8 | C2, H2 (statistical close) | No | M |

**Total: 8 issues fixed. GPU time: ~32-48 hours. Human time: ~1-2 days (plus GPU wait).**

---

## Full Remediation Summary (Phase 1 + Phase 2)

| Severity | Total | Phase 1 (no GPU) | Phase 2 (GPU) |
|----------|-------|------------------|---------------|
| Critical | 6 | 2 (C5, C6) | 4 (C1, C2, C3, C4=live track) |
| High | 4 | 2 (H3, H1) | 2 (H2, +C1 closeout) |
| Medium | 8 | 5 (M6, M7, M8, +2) | 3 (M1, M4, M5) |
| Low | 14 | 14 | 0 |
| Process/Docs | 5 | 5 | 0 |
| **Total** | **37** | **29** | **8** |

**Phase 4 (C4 — live paper track record):** Not in this plan. Requires 6 months of calendar time, not engineering effort. Track via the existing dashboard; the bootstrap p-value accumulates automatically.
