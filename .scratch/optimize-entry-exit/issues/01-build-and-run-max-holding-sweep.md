# 01 - Build and run the max-holding-days + cooldown sweep

Type: task
Status: resolved

## Question

Build an experimental, research-only `max_holding_days` + `cooldown_days`
exit path and run the backtest sweep needed to inform the map's destination
decision.

**Implementation:**

- Add `max_holding_days` and `cooldown_days` as new optional parameters to
  `apply_hysteresis()` in `kth/backtest/strategy.py`, and thread them through
  `BacktestConfig` in `kth/backtest/walkforward.py`. Default both to `None` /
  disabled so the existing production default path (`long_threshold=0.01`,
  `entry_buffer=0.005`, `min_holding_days=5`, no cap) is completely unchanged
  when the new params aren't set — this is a research branch, not a production
  change.
- Mechanism: once `holding_days >= max_holding_days`, force-close the position
  regardless of signal. After a forced close, block re-entry into that ticker
  until `cooldown_days` have elapsed (no same-day or early re-entry even if
  the raw signal still clears the entry threshold).
- No new Kronos inference is required — `data/forecast_cache/NeoQuasar_Kronos-small/`
  already covers 2020-01-01 → 2026-07-25 (confirmed by exploring the repo; see
  map Notes). Use the project venv (`requirements-ml.txt` installed) rather
  than bare `python3`, which lacks `torch`.

**Sweep:**

- Grid: `max_holding_days ∈ {20, 40, 60, 90}` × `cooldown_days = 5` (fixed) ×
  years `{2023, 2024, 2025, 2026}` = 16 runs.
- Also re-run the **baseline** (no cap — current production default path) for
  all 4 years through today's code. Do NOT use the numbers already stored in
  `data/backtest_results/thai_equity_2023_n50` etc. as the comparison
  baseline — `MANIFEST.md` flags those as stale pending a re-run of the
  2026-06-21 fixes. Since those fixes are already merged into the current
  `walkforward.py`/`metrics.py`, a fresh baseline run through today's code is
  the valid comparison point, not the old stored one.
- Use n=50 samples per the MANIFEST's "authoritative" convention
  (`thai_equity_<year>_n50`-style), matching `long_threshold`/`entry_buffer`/
  `pred_len`/`lookback` etc. from the existing `BacktestConfig` defaults —
  only `max_holding_days`/`cooldown_days` vary across the grid.
- For each of the 20 runs (16 candidate + 4 baseline), capture: PSR, Sharpe,
  t-test p-value, friction % drag, max drawdown, and trade count/avg holding
  duration (from the trades ledger) — the same metrics `compute_metrics()`
  already produces.

## Answer

**Implementation** — added `max_holding_days: int | None = None` and
`cooldown_days: int | None = None` to `BacktestConfig`
(`kth/backtest/walkforward.py`), and to `apply_hysteresis()`
(`kth/backtest/strategy.py`): a held position force-closes once
`holding_days >= max_holding_days`, and a `cooldown_remaining` dict (owned/
decremented once per day by `run_walkforward`, read+written by
`apply_hysteresis`) blocks re-entry for `cooldown_days` after a forced exit.
Both default to `None`/disabled, so the production default path is provably
unchanged (verified with a standalone unit check: a position held 100 days
with `max_holding_days` unset still returns `signals[t] == 1`, and all 90
pre-existing tests in `verify_fixes.py` / `verify_data_layer.py` /
`verify_kaggle_runtime.py` / `verify_dr.py` still pass).

**Blocking bug found and fixed** — `run_walkforward`'s loop computed
`next_day = trading_days[day_idx + 1] if ... else day`, so on the final
iteration `next_day` fell back to `day` itself, duplicating the previous
iteration's mark-day in `equity_curve`'s index. This crashed
`compute_metrics()` (`pandas.concat`: "cannot reindex on an axis with
duplicate labels") on **every** backtest run, baseline included — reproduced
independent of any of this ticket's new parameters. Fixed by breaking out of
the loop one iteration early (no next-day open exists to execute into on the
last day, so nothing valid can happen that day). This is very likely why the
GPU re-run flagged as outstanding in `data/backtest_results/MANIFEST.md` has
not happened yet — every fresh run through the 2026-06-21-fixed code path
would have hit this crash. Sanity check: the fresh baseline friction numbers
this ticket produced for 2024 (7.26%) and 2025 (17.29%) land almost exactly on
the previously-cited stale figures in CLAUDE.md (7.54% / 17.35%), so the fix
did not distort results, just removed the crash.

**Sweep results** (thai_equity, n=50, `max_positions=5`, `cooldown_days=5` for
all capped configs; full run log + `summary.json` in
`data/backtest_results/max_holding_sweep/`):

```
config   year      CAGR  Sharpe    MaxDD  PSR0.5  p-val  friction  turnover  avg_hold  trades
---------------------------------------------------------------------------------------------
baseline 2023    +9.13%    0.42  -15.80%   0.505  0.604     8.28%     26.20     25.3d    1338
baseline 2024   +41.28%    2.23   -6.92%   0.961  0.017     7.26%     22.85     10.2d    1315
baseline 2025   +34.55%    1.05  -23.51%   0.739  0.260    17.29%     54.67     16.1d    1413
baseline 2026  +121.27%    2.39  -18.26%   0.917  0.066    23.92%    109.31     16.1d     717
cap20    2023    +1.94%    0.10  -14.29%   0.375  0.846    13.57%     46.03     17.9d    1391
cap20    2024   +15.48%    0.93   -8.10%   0.711  0.279    14.29%     50.08      9.7d    1414
cap20    2025   +14.86%    0.54  -22.44%   0.542  0.542    22.68%     79.49     17.6d    1488
cap20    2026   +88.66%    1.93  -18.52%   0.859  0.134    27.48%    131.28     16.8d     733
cap40    2023   -10.08%   -0.67  -17.91%   0.144  0.578    10.84%     39.05     19.7d    1372
cap40    2024   +35.17%    1.82   -7.83%   0.929  0.049    11.60%     36.81     10.5d    1358
cap40    2025   +20.19%    0.68  -25.95%   0.601  0.448    17.94%     60.73     17.4d    1429
cap40    2026  +117.10%    2.54  -16.72%   0.943  0.051    24.26%    111.82     14.5d     716
cap60    2023   +16.72%    0.74  -10.86%   0.647  0.399    10.17%     31.53     21.3d    1357
cap60    2024   +35.08%    1.94   -6.90%   0.934  0.036     9.50%     30.39      9.8d    1334
cap60    2025   +23.50%    0.77  -27.73%   0.634  0.398    17.80%     60.29     16.2d    1434
cap60    2026  +121.27%    2.39  -18.26%   0.917  0.066    23.92%    109.31     16.1d     717
cap90    2023    +4.91%    0.23  -18.61%   0.428  0.741     9.41%     30.20     24.8d    1348
cap90    2024   +37.63%    2.09   -6.92%   0.948  0.025     9.19%     29.32     10.5d    1337
cap90    2025   +35.31%    1.07  -23.51%   0.746  0.250    17.79%     56.23     17.3d    1416
cap90    2026  +121.27%    2.39  -18.26%   0.917  0.066    23.92%    109.31     16.1d     717
```

Notable patterns for Ticket 02 to interpret: (a) friction is equal-or-higher
for every capped config in every year, never lower; (b) in 2024 — the only
year clearing p<0.05 in prior research — every capped config weakens PSR/
Sharpe/p-value relative to baseline; (c) 2026's cap60/cap90 rows are
byte-identical to baseline (avg holding never reached 60 days in this
dataset, confirming the cap only binds when it's actually short enough to
matter); (d) cap60 in 2023 is the one config that clearly beats baseline
across every metric, but 2023 is a documented weak-edge year for the strategy
overall (baseline PSR0.5 = 0.505, barely above coin-flip).

Status: resolved.
