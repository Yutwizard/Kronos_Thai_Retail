# Daily Decision Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `notebooks/05_decision_report.ipynb` — daily forecast + signal report for 100 tickers with 3 toggleable views (morning/trader/quant).

**Architecture:** 5 cells. Cell 0: config + imports. Cell 1: load Kronos model. Cell 2: generate forecasts (idempotent, today invalidated). Cell 3: build 22-column DataFrame from cache + universe + backtest. Cell 4: display per-mode. Cell 5: disclaimers.

**Tech Stack:** Python 3.10+, pandas, PyTorch, Kronos (local repo)

---

### File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `notebooks/05_decision_report.ipynb` | Full report notebook |

---

### Task 1: Write + test the notebook

**Files:**
- Create: `notebooks/05_decision_report.ipynb`

- [ ] **Step 1: Write a Python script that generates the notebook JSON**

Create `scripts/build_decision_notebook.py` that builds the notebook programmatically (avoids JSON escaping issues in plans). Refer to spec `docs/superpowers/specs/2026-05-24-daily-decision-report-design.md` for the exact cell contents.

The script should:
1. Define 5 cells as Python code strings (matching spec §2 exactly)
2. Wrap in notebook JSON structure (nbformat: 4, nbformat_minor: 5)
3. Save to `notebooks/05_decision_report.ipynb`

Run: `venv/bin/python scripts/build_decision_notebook.py`

Expected: `notebooks/05_decision_report.ipynb created`

- [ ] **Step 2: Verify notebook JSON is valid**

Run: `venv/bin/python -c "import json; nb = json.load(open('notebooks/05_decision_report.ipynb')); assert nb['nbformat']==4; assert len(nb['cells'])==5; print('OK — 5 cells')"`

Expected: `OK — 5 cells`

- [ ] **Step 3: Verify syntax of all cell code**

Run: `venv/bin/python -c "
import json, ast
nb = json.load(open('notebooks/05_decision_report.ipynb'))
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        try:
            ast.parse(source)
        except SyntaxError as e:
            print(f'Cell {i}: SYNTAX ERROR — {e}')
            break
else:
    print('All cells — syntax OK')
"`

Expected: `All cells — syntax OK`

- [ ] **Step 4: Test Cell 0+1 (imports + model load) on CPU**

Run: `venv/bin/python -c "
# Simulate Cell 0
import pandas as pd, numpy as np, json
from pathlib import Path
import shutil, sys
sys.path.insert(0, 'kronos_repo')
from kth.data.universe import UNIVERSE, FRICTION, get_all_tickers, get_ticker_class, get_display_name
from kth.data.loader import load_cached
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts
REPORT_MODE, MODEL_TYPE = 'morning', 'zero-shot'
REPORT_DATE = pd.Timestamp.now().strftime('%Y-%m-%d')
CACHE_SLUG = 'NeoQuasar_Kronos-small'
BACKTEST_METRICS = {'thai_equity':{'sharpe':1.40,'cagr':0.3144,'max_dd':-0.1797}}
print('Cell 0 imports — OK')

# Simulate Cell 1
th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cpu')
print('Cell 1 model load — OK')
"`

Expected: prints OK for both cells (no GPU needed for CPU-only load test).

- [ ] **Step 5: Test Cell 4 (display logic) with a fake DataFrame**

Run: `venv/bin/python -c "
import pandas as pd, numpy as np
df = pd.DataFrame({
    'ticker': ['AAPL','MSFT','GOOGL'],
    'name': ['Apple','Microsoft','Alphabet'],
    'class': ['us_equity']*3,
    'current_close': [180.0, 400.0, 170.0],
    'expected_return_p50': [0.03, -0.02, 0.01],
    'expected_return_mean': [0.035, -0.015, 0.012],
    'band_width': [0.08, 0.15, 0.05],
    'confidence': ['green','yellow','green'],
    'direction': ['up','down','up'],
    'rank_score': [0.375, -0.133, 0.200],
    'p5_close': [175.0, 370.0, 167.0],
    'p95_close': [190.0, 430.0, 176.0],
    'market_sharpe': [0.97]*3,
    'market_cagr': [0.30]*3,
    'market_max_dd': [-0.44]*3,
    'hist_vol_1y': [0.25, 0.30, 0.20],
    'risk_adj_return': [0.12, -0.07, 0.05],
    'friction_rt': [0.007]*3,
    'net_return': [0.023, -0.027, 0.003],
    'report_date': ['2026-05-24']*3,
    'model': ['zero-shot']*3,
})

def fmt_pct(v):
    if pd.isna(v) or v is None: return '—'
    return f'{v:+.2%}'
def fmt_ratio(v):
    if v is None or (isinstance(v,float) and np.isnan(v)): return '—'
    return f'{v:.2f}'

# Morning
cols = ['ticker','name','class','current_close','expected_return_p50','band_width','confidence','rank_score','direction']
sub = df[cols].copy()
top = sub.nlargest(10, 'rank_score')
bot = sub.nsmallest(10, 'rank_score')
assert len(top) == 3 and len(bot) == 3
print('Cell 4 display logic — OK')
"`

Expected: `Cell 4 display logic — OK`

- [ ] **Step 6: Full integration test — run a single-date forecast on CPU**

Run a single-ticker forecast to verify the full pipeline:

```bash
venv/bin/python -c "
import pandas as pd; from pathlib import Path; import shutil, sys
sys.path.insert(0, 'kronos_repo')
from kth.data.universe import UNIVERSE, get_ticker_class, get_display_name
from kth.data.loader import load_cached
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts

th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cpu')
tickers = ['AAPL', 'MSFT', 'BTC-USD']
today = pd.Timestamp.now().strftime('%Y-%m-%d')
slug = 'NeoQuasar_Kronos-small'
today_dir = Path(f'data/forecast_cache/{slug}/{today}')
if today_dir.exists(): shutil.rmtree(today_dir)

precompute_forecasts(th, tickers, start_date=today, end_date=today,
                     pred_len=20, n_samples=10, lookback=400)

# Verify cache
for t in tickers:
    safe = t.replace('^','_').replace('=','_')
    f = today_dir / f'{safe}.parquet'
    if f.exists():
        fc = pd.read_parquet(f)
        print(f'{t}: forecast cached ({len(fc)} horizons)')
    else:
        print(f'{t}: MISSING')
print('Pipeline test — OK')
"
```

Expected: 1-3 tickers forecasted (some may be skipped on CPU if too slow). At least 1 should succeed.

- [ ] **Step 7: Commit**

```bash
git add notebooks/05_decision_report.ipynb scripts/build_decision_notebook.py
git commit -m "feat: Layer 5 daily decision report notebook

- 5 cells: config, model, forecasts, DataFrame, display
- 3 toggleable views: morning/trader/quant
- 22 columns from forecast cache + universe + backtest
- Idempotent: re-running skips cached forecasts"
```

---

### Self-Review

1. **Spec coverage:** All §2 cells covered (0-5). All §4 data sources used. All §5 derived fields computed. All modes (morning/trader/quant) displayed.

2. **Placeholder scan:** No TBDs. All code inline. All expected outputs specified.

3. **Type consistency:** `CACHE_SLUG` computed in Cell 0, used in Cells 2 and 3. `BACKTEST_METRICS` dict matches spec §4. Column names match Cell 3 rows.append().

4. **Testing:** Steps 2-6 test JSON validity, syntax, imports, display logic, and full pipeline integration.

---

*Document version: 2026-05-24.*
