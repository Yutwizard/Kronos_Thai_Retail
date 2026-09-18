# Ticket 02: One Correction Family for backtest significance wording

**Status:** Scoped, not filed. Type: docs. No GPU.
**Decision (2026-09-18):** the 4-year OOS family (p<0.0125) is the canonical
headline. See "Correction Family" in `CONTEXT.md`.

## Problem

Two Bonferroni families are cited with no explanation:
- 4 OOS years, p<0.0125: `docs/backtest-methodology.md:504`,
  `PROJECT_STRUCTURE.md:586`, `docs/user-manual.md` (~401, ~496, ~522).
- "9 tests", p<0.0056: `PROJECT_STRUCTURE.md:595`,
  `data/backtest_results/MANIFEST.md` lines 21 and 39.

The 9-test figure was introduced in commit 778f03e (2026-06-03, QFM data
review), before the four n50 runs existed, and the nine tests are never
listed. It cannot be labelled truthfully. 2024 (p=0.001) survives either
family and 2025 (p=0.027) fails both, so the verdict is unchanged.

Also stale: `MANIFEST.md` lines ~26-30 say the "only 2024 is significant"
framing in `PROJECT_STRUCTURE.md` "has not yet been updated". It has been.

## Changes

1. Remove the 9-test line at `PROJECT_STRUCTURE.md:595` and the two 9-test
   mentions in `MANIFEST.md` (lines 21, 39); fold any surviving sentence into
   the 4-test wording. (If the owner prefers to keep it, label it "legacy,
   members not recorded".)
2. Retire the stale "not yet updated" note in `MANIFEST.md`.
3. Grep once for any other "Bonferroni" wording so all docs say the same
   thing: 2024 survives; 2025 clears p<0.05 unadjusted only.

## Optional extra

A pooled paired block-bootstrap across all four years (strategy vs
Equal-Weight Benchmark daily returns), as a single headline test in place of
four per-year tests. CPU-only. Model on `scripts/analyze_cap60_significance.py`
(same stationary block bootstrap as `compute_sharpe_ci`). If done, decide
whether it replaces or sits beside the per-year table.

## Ordering

Do this before the wording updates in ticket 03 so the same paragraphs are not
edited twice. `MANIFEST.md` is tracked in git despite `data/backtest_results/`
being in `.gitignore`.
