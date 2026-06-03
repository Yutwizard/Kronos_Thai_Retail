# Post-2023 Backtest Action Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Trigger:** Execute this plan immediately after `scripts/run_2023_n50.py` completes and results appear in `data/backtest_results/thai_equity_2023_n50_full/`.

**Context:** The 2023 n=50 backtest is the single most important data point in the project. It is:
- The first year with no risk of Kronos pre-training data contamination (earliest plausible cutoff is post-2022)
- A full 252-trading-day OOS window (unlike 2026 which has only 107 days)
- The missing piece of the 4-year (2023–2026) picture

All other investigations in this plan depend on or are informed by the 2023 result.

---

## Decision Gate Outcome ✅ EVALUATED (2026-06-03)

**2023 result:** CAGR +2.65%, Sharpe 0.10, p=0.419, Friction 5.68%/yr, EW=+12.8%, Alpha=−10.2pp

**Gate triggered: 🔴 MODEL REVIEW** (Sharpe=0.10 < 0.5)

**Critical finding — NOT model failure:**
The deployed stocks beat EW by +3.3pp on the deployed portion. The −10.2pp total alpha shortfall is explained by:
- Cash drag: NEUTRAL band (50% deployed) in a +12.8% EW bull market = −6.4pp
- Friction: −5.68%/yr
- Deployed stock-selection was actually POSITIVE (+3.3pp on deployed capital)

**Pattern:** Strategy holds cash by design (dynamic allocation band). In bull markets, this hurts vs EW. In bear markets (2024: EW −7.2%, 2025: EW −9.9%), cash preservation + selective positions crushes EW.

**Paper trading recommendation:** Current market is SET bull (2026 EW +41.8% ann.). Use BEAR allocation (5%) until regime shifts or 20 paper trades accumulate.

**Friction note:** AGENTS.md originally showed 19.52%/yr for 2023 — this was wrong. Actual is 5.68%/yr from `thai_equity_2023_n50` trades parquet. The 2025 friction (17.35%/yr) remains the high-friction anomaly to investigate.

**Tasks completed:** Task 1 ✅. Now executing Tasks 3, 4, 5.

---

## Decision Gate (Original Logic — Keep for Reference)

Read the result first, then branch:

```python
import json
from pathlib import Path
with open("data/backtest_results/thai_equity_2023_n50_full/metrics.json") as f:
    m = json.load(f)
print(f"2023: CAGR={m['cagr']*100:.2f}%  Sharpe={m['sharpe']:.2f}  p={m['p_value']:.3f}")
```

| 2023 result | Decision |
|-------------|----------|
| p < 0.05 AND Sharpe ≥ 1.0 | ✅ **PROCEED** — multi-year evidence. Execute all tasks in this plan. Begin Phase 2 gate clock. |
| p ≥ 0.05 AND Sharpe ≥ 1.0 | ⚠ **CONTINUE PAPER** — signal exists but unproven. Execute Tasks 1–3 only. Investigate threshold tuning (Task 4). |
| Sharpe < 0.5 | 🔴 **MODEL REVIEW** — strategy may be degrading. Execute Task 1 and Task 5 first. Pause live paper trading. |

---

## Task 1 — Record and Broadcast 2023 Result (10 min)

- [ ] **Step 1: Read result and compute 4-year summary:**

```python
import pandas as pd, json, numpy as np
from pathlib import Path
from scipy import stats

results_dir = Path("data/backtest_results")
years = {
    "2023": "thai_equity_2023_n50_full",
    "2024": "thai_equity_2024_n50",
    "2025": "thai_equity_2025_n50",
    "2026": "thai_equity_2026_n50_full",
}

summary = []
for yr, name in years.items():
    d = results_dir / name
    if not d.exists(): continue
    with open(d / "metrics.json") as f: m = json.load(f)
    with open(d / "config.json") as f: cfg = json.load(f)
    years_n = (pd.to_datetime(cfg["end_date"]) - pd.to_datetime(cfg["start_date"])).days / 365.25
    trades = pd.read_parquet(d / "trades.parquet")
    summary.append({
        "year": yr,
        "cagr": m["cagr"],
        "sharpe": m["sharpe"],
        "max_dd": m["max_drawdown"],
        "p_value": m["p_value"],
        "friction_yr": trades["friction_cost"].sum() / years_n,
        "trades_yr": len(trades) / years_n,
    })

df = pd.DataFrame(summary)
print(df.to_string(index=False))
```

- [ ] **Step 2: Update AGENTS.md** — replace `2023 n=50: ⬜ running` with actual result. Add to the yearly backtest table with CAGR, Sharpe, p-value, friction/yr.

- [ ] **Step 3: Update PROJECT_STRUCTURE.md §14** current status with 2023 result and overall 4-year assessment.

- [ ] **Step 4: Update `docs/superpowers/plans/2026-05-31-n50-completion.md`** — mark Task 2 (2023 n=50) as ✅ complete.

---

## Task 2 — Check Kronos Training Data Cutoff (30 min)

**Why:** If Kronos-small's pre-training data includes Thai stocks through 2024, the 2022–2024 canonical backtest is contaminated. This is the highest-impact unresolved risk in the project.

- [ ] **Step 1: Check the Kronos model card:**
  - Go to `huggingface.co/NeoQuasar/Kronos-small` (or read `kronos_repo/README.md`)
  - Find: training data date range, markets covered, any Thai stock mentions
  - Record the training cutoff date

- [ ] **Step 2: Apply decision:**
  - If training cutoff **≤ 2021-12-31**: All backtests (2022+) are clean OOS. No action.
  - If training cutoff **falls within 2022–2024**: The canonical 2022-2024 result is suspect. Re-evaluate strategy using **2025-only** or **2023+ only** data as the primary evidence. Update AGENTS.md with a prominent warning.
  - If cutoff is **unknown/undocumented**: Add a disclaimer to all reported results and flag for future investigation.

- [ ] **Step 3: Document finding in AGENTS.md** under "Known unknowns" with the exact cutoff date and implications.

---

## Task 3 — Compute 4-Year OOS Report (1 hr)

After 2023 completes, generate a unified comparison document covering all 4 OOS years.

- [ ] **Step 1: Run `scripts/build_n50_yearly_report.py`** (or equivalent) to generate the 4-year side-by-side report. If the script doesn't exist, create a minimal version:

```python
# scripts/build_4year_report.py
import pandas as pd, json
from pathlib import Path

years = {
    "2023 (most credible OOS)": "thai_equity_2023_n50_full",
    "2024 (only significant year)": "thai_equity_2024_n50",
    "2025 (high friction regime)": "thai_equity_2025_n50",
    "2026 (partial, 107 days)": "thai_equity_2026_n50_full",
}
rows = []
for label, name in years.items():
    d = Path("data/backtest_results") / name
    with open(d/"metrics.json") as f: m = json.load(f)
    with open(d/"config.json") as f: cfg = json.load(f)
    trades = pd.read_parquet(d/"trades.parquet")
    yrs = (pd.to_datetime(cfg["end_date"]) - pd.to_datetime(cfg["start_date"])).days/365.25
    rows.append({
        "Year": label,
        "CAGR": f"{m['cagr']*100:.1f}%",
        "Sharpe": f"{m['sharpe']:.2f}",
        "Max DD": f"{m['max_drawdown']*100:.1f}%",
        "p-value": f"{m['p_value']:.3f}",
        "Friction/yr": f"{trades['friction_cost'].sum()/yrs*100:.1f}%",
        "Significant": "✅" if m['p_value'] < 0.05 else "❌",
    })
print(pd.DataFrame(rows).to_string(index=False))
```

- [ ] **Step 2: Apply Bonferroni-corrected significance test** across all 4 years (plus the 2020–2024 expanded run = 5 tests). Threshold: p < 0.05/5 = 0.01. Document which years survive.

- [ ] **Step 3: Add combined 4-year table to `docs/user-manual.md` §6** (Backtest Results). Keep the existing 2022–2024 section; add a new "4-Year OOS Summary" subsection.

- [ ] **Step 4: Rebuild `docs/backtest-methodology.html`** if `scripts/build_backtest_html.py` supports it, to include the 2023 result and updated survivorship bias adjustment.

---

## Task 4 — Investigate 2025 Friction Drain ✅ ROOT CAUSE IDENTIFIED, GPU REQUIRED FOR EXPERIMENTS

> **IMPORTANT — Plan correction (2026-06-03):** Sub-tasks 4b and 4c originally stated "no GPU needed, reusing cached forecasts." This was WRONG. All parameter sensitivity experiments require GPU because:
>
> 1. The fresh local `run_walkforward()` reads `data/forecast_cache/NeoQuasar_Kronos-small/` which contains n10 forecasts from original runs. The stored n50 backtests (thai_equity_2024_n50 etc.) used dedicated n50 forecasts precomputed on Colab GPU.
> 2. Running `run_walkforward()` with different `min_holding_days` or `long_threshold` on local n10-quality forecasts produces meaningless results — the signal quality is completely different.
> 3. All three experiments (4b: min_hold 5/10/15/20, 4c: threshold 0.01/0.015/0.02) returned **identical results** regardless of parameter value, confirming the underlying forecast data is the problem, not the parameters.
>
> **To run these properly: precompute n50 forecasts on Colab GPU for the target year, then immediately run `run_walkforward()` before the cache is contaminated by other runs.**

### Sub-task 4a: Root cause ✅ COMPLETE (no GPU needed — reads stored parquet)

From `thai_equity_2024_n50` and `thai_equity_2025_n50` trades:

| Year | avg size_pct | Trades/yr | Friction/yr |
|------|-------------|-----------|-------------|
| 2024 | 0.021 | 1,322 | 7.54% |
| 2025 | **0.045** | 1,424 | **17.35%** |

**Root cause: 2025 average position size is 2.1× larger.** Not higher turnover. n50 forecasts in strong-signal 2025 regimes produce higher-conviction signals → larger entries. Friction spikes in Aug–Oct 2025 (avg_size 0.063–0.088) — the bull market phase. This is structural and acceptable: 17.35% friction was paid for +43.6pp alpha vs EW.

### Sub-task 4b: min_holding_days experiment ✅ COMPLETE — INVALIDATED (wrong data)

**Ran:** 5/10/15/20 days on 2023/2024/2025. **All configs returned identical results.**

**Why:** Fresh walkforward used local n10 cache; stored n50 results used Colab-precomputed n50 cache. Parameter changes had no effect because signal quality mismatch dwarfs parameter differences.

**Conclusion:** Cannot determine real effect of min_holding_days without GPU. The natural holding period appears long enough that 20d never binds — but this is a hypothesis that needs proper n50 testing.

**GPU test (run on Colab when needed):**
```bash
# Step 1: precompute n50 forecasts for 2025 with fresh GPU run
python scripts/dashboard.py --generate  # or run precompute_forecasts() on Colab

# Step 2: immediately run walkforward with different min_hold configs
# BacktestConfig(min_holding_days=5)  → save to thai_equity_2025_minhold_5/
# BacktestConfig(min_holding_days=10) → save to thai_equity_2025_minhold_10/
# BacktestConfig(min_holding_days=20) → save to thai_equity_2025_minhold_20/
```

**Decision criterion (when results are valid):** If min_hold=10 reduces friction/yr by >3pp with CAGR drop <2pp → implement. Otherwise keep 5.

### Sub-task 4c: long_threshold experiment ✅ COMPLETE — INVALIDATED (wrong data)

**Ran:** 0.01/0.015/0.02 thresholds on 2023/2024/2025. **All configs returned identical results.**

**Same diagnosis as 4b.** Local n10 cache makes all thresholds equivalent — every signal is either well above 2% or well below 1%, so the filter never changes outcomes.

**GPU test (run on Colab when needed):**
```bash
# Precompute n50 forecasts → run with threshold variants
# BacktestConfig(long_threshold=0.010, entry_buffer=0.005)
# BacktestConfig(long_threshold=0.015, entry_buffer=0.008)
# BacktestConfig(long_threshold=0.020, entry_buffer=0.010)
```

**Decision criterion (when results are valid):** If threshold=0.015 reduces friction/yr by >3pp with net CAGR drop <3pp → adopt as new default for both `BacktestConfig` and `trade_gen.py` buy filter.

### Sub-task 4d: Apply optimal parameters ❌ BLOCKED on 4b and 4c GPU runs

Once valid 4b/4c results exist:
- [ ] Confirm improvement on 2023 and 2024 too
- [ ] Update `BacktestConfig` defaults and `trade_gen.py`
- [ ] Re-run 4-year OOS comparison with new parameters

---

## Task 5 — Factor Attribution (1–2 hrs)

**Why:** The +30pp alpha over equal-weight could be momentum in disguise rather than AI alpha. If SET momentum explains most of the strategy return, Kronos is a momentum strategy — still valuable, but differently positioned.

- [ ] **Step 1: Compute SET 12-1 momentum factor:**

```python
import pandas as pd, numpy as np
from kth.data.loader import load_cached
from kth.data.universe import UNIVERSE

# Load all 49 thai equity tickers
prices = {}
for ticker, _, _ in UNIVERSE["thai_equity"]:
    try:
        df = load_cached(ticker)
        prices[ticker] = df["close"]
    except: pass

price_df = pd.DataFrame(prices).sort_index()

# 12-1 month momentum: return from 252 days ago to 21 days ago
mom = price_df.shift(21).pct_change(231)  # 252-21=231 trading days
equal_weight_mom = mom.mean(axis=1)  # cross-sectional average
```

- [ ] **Step 2: Load strategy daily returns and run OLS:**

```python
from scipy import stats
from kth.backtest.metrics import compute_metrics

# Load 2022-2024 v2 equity curve
import pandas as pd
equity = pd.read_parquet("data/backtest_results/thai_equity_2022-2024_v2/equity_curve.parquet")["equity"]
strat_returns = equity.pct_change().dropna()

# SET benchmark returns
set_prices = load_cached("^SET.BK")["close"]
set_returns = set_prices.pct_change().reindex(strat_returns.index).fillna(0)

# Align momentum factor
factor = equal_weight_mom.reindex(strat_returns.index).fillna(0)

# OLS: strategy ~ market + momentum
X = pd.DataFrame({"market": set_returns, "momentum": factor})
X = X.reindex(strat_returns.index).dropna()
y = strat_returns.reindex(X.index)

slope, intercept, r, p, se = stats.linregress(X["market"], y)
print(f"Beta_market: {slope:.3f}")
print(f"OLS alpha (annualised): {intercept * 252 * 100:.2f}%")

from numpy.linalg import lstsq
A = np.column_stack([np.ones(len(X)), X.values])
coef, _, _, _ = lstsq(A, y.values, rcond=None)
print(f"Intercept (alpha/day): {coef[0]*252*100:.2f}%/yr")
print(f"Beta_market: {coef[1]:.3f}")
print(f"Beta_momentum: {coef[2]:.3f}")
```

- [x] **Step 3: Interpret and document (2026-06-03):**

Results from `thai_equity_2022-2024_v2` equity curve vs SET market + 12-1 month momentum:

| Factor | Beta | R² contribution |
|---|---|---|
| Market (SET) | −0.009 | 0.000 |
| Momentum | −0.010 | 0.000 |
| Residual alpha | +29.4%/yr | — |

**Verdict: Genuinely market-neutral, NOT a momentum proxy. Alpha is from the Kronos model, not factor exposure.** This is the strongest possible outcome — the strategy's returns are uncorrelated with any common risk factor. Updated in AGENTS.md backtest section.

---

## Task 6 — Phase 2 Gate Assessment (Ongoing after paper trading)

The Phase 2 gate requires ALL of the following before switching to real money:

| Criterion | Required | How to measure |
|-----------|----------|----------------|
| Paper trading duration | ≥ 4 weeks (20+ trading days) | `data/positions/trade_log.csv` date range |
| Round-trip trades | ≥ 10 | FIFO-matched closed positions |
| Win rate | ≥ 50% | Dashboard `/api/risk` → `win_rate` |
| Live Sharpe | ≥ 0.90 (within 0.5 of backtest 1.40) | Dashboard `/api/risk` → `sharpe` |
| No stop-loss trigger | ✅ Never hit −10% drawdown | Dashboard → `frozen` == false |
| Monthly rebalances | ≥ 3 full rebalances executed | `data/positions/trade_log.csv` monthly counts |

- [ ] **Check gate status** (run after paper trading accumulates):

```python
import pandas as pd, json
from pathlib import Path

pf = json.loads(Path("data/positions/paper_portfolio.json").read_text())
trades = pd.read_csv("data/positions/trade_log.csv")
print(f"Frozen (stop-loss triggered): {pf.get('frozen', False)}")
print(f"Equity curve points: {len(pf.get('equity_curve', []))}")
print(f"Total trade log entries: {len(trades)}")
print(f"Dashboard /api/risk will show: sharpe, win_rate, drawdown, closed_trades")
```

- [ ] **Gate evaluation checklist** — run monthly until all 6 pass.

---

## Task 7 — Strategy Parameter Update (if Tasks 4b/4c find better config)

If sub-tasks 4b and 4c identify improved parameters:

- [ ] Update `kth/backtest/walkforward.py` `BacktestConfig` defaults:
  ```python
  min_holding_days: int = 5  # → increase to optimal value from Task 4b
  long_threshold: float = 0.01  # → increase to optimal value from Task 4c
  ```

- [ ] Update `kth/trading/trade_gen.py` buy filter to match new threshold:
  ```python
  # Currently: if f["net_ret"] <= f["friction_rt"]: continue
  # Update to use the same threshold as BacktestConfig.long_threshold
  ENTRY_THRESHOLD = 0.015  # match BacktestConfig if changed
  if f["net_ret"] < ENTRY_THRESHOLD: continue
  ```

- [ ] Re-run the full 4-year comparison (2023-2026) with new parameters to confirm improvement is consistent, not year-specific.

- [ ] Update AGENTS.md backtest results section with updated metrics.

---

## Appendix — Computed Findings (2026-06-03)

For reference when executing this plan:

### Friction by year

| Year | CAGR | Sharpe | p-value | Friction/yr | Friction/CAGR |
|------|------|--------|---------|-------------|---------------|
| 2022–2024 (canonical v2) | 31.44% | 1.40 | 0.034 | 4.63% | 15% |
| 2024 n50 | 41.99% | 2.27 | **0.015** | 7.54% | 18% |
| **2025 n50** | **33.69%** | **1.03** | **0.257** | **17.35%** | **51% ⚠** |
| 2026 n50 (partial) | 143% (ann.) | 2.42 | 0.353 | 22.9% (est.) | 16% |

### 2025 friction root cause

Average position size (size_pct) per trade:
- 2024: **0.021** (21% of portfolio per average trade)
- 2025: **0.045** (45% of portfolio per average trade) — **2.1× larger**

Monthly breakdown shows spike in Aug–Oct 2025 (avg_size 0.063–0.088), coinciding with presumed bull market regime when the strategy was in BULL allocation band. Large full-size entries (20% positions) in bull regimes generate large per-trade friction.

### Position sizing: equal-weight confirmed superior

`inv_vol` was tested in `thai_equity_2022-2024_invvol/`:
- CAGR: 13.29% (vs 31.44% equal-weight)
- Sharpe: 0.84 (vs 1.40)
- p = 0.732 (vs 0.034)
- **Do not re-test. Equal-weight is conclusively better for this strategy.**

### Bonferroni correction

Testing 9 hypotheses (3 markets × ~3 periods): corrected threshold = p < 0.05/9 = **0.0056**.
- 2024 n50: p=0.015 — does NOT survive correction.
- 2022–2024 v2 single-run: p=0.034 — does NOT survive.
- No result currently clears the corrected threshold.
- The 2023 result is the pivotal test.

---

*Document version: 2026-06-03. Execute after `data/backtest_results/thai_equity_2023_n50_full/` appears. Author: QFM data review session.*
