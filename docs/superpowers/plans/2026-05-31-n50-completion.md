# 2026 + 2023 n=50 Plan — Status
> ✅ 2026 complete | ⬜ 2023 pending

## Steps

### Task 1: 2026 n=50 (107 days) ✅
- Script: `scripts/run_2026_n50.py`
- Period: 2026-01-01 → 2026-05-30
- Result: **+45.28%, Sharpe 2.42, Max DD −18.26%, p=0.353**
- Saved: `data/backtest_results/thai_equity_2026_n50_full/`

### Task 2: 2023 n=50 (252 days) ⬜
- Script: `scripts/run_2023_n50.py`
- Period: 2023-01-01 → 2023-12-31
- ~252 days × 2.8 min/day = ~12 hrs background
- Run after reboot:
  ```bash
  nohup venv/bin/python scripts/run_2023_n50.py > data/logs/2023_n50.log 2>&1 &
  ```

### Task 3: Generate final n=50 comparison report (all 4 years) ⬜
- After 2023 completes, regenerate all reports
