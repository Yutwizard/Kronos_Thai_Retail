# Task: Extend docs/user-manual.html to cover the 4-Year OOS (2023–2026) results

**Status:** Scoped, not yet filed as a GitHub issue (`gh` CLI unavailable in the
scoping session — file this via `gh issue create` once available, per
`docs/agents/issue-tracker.md`, then delete this file).

**Origin:** Found while fixing stale pre-2026-07-29-bugfix backtest numbers in
`docs/user-manual.md` (graphify knowledge-graph audit, 2026-09-17). The `.md`
fix is done; this HTML gap is the deferred follow-up.

## Problem

`scripts/build_usermanual_html.py` only ever renders the older "Backtest
Results (2022–2024)" section (`s6`, line 490) from a hardcoded
`BACKTEST_RESULTS` dict (line 21) covering a single 3-year canonical run. It
has no section for the 4-year 2023–2026 OOS results that `user-manual.md` now
leads with in its §6. The HTML isn't just stale — it structurally can't
represent the current primary evidence no matter how many times it's
regenerated.

## What needs to change

All in `scripts/build_usermanual_html.py` (596 lines):

1. **Data**: add a per-year OOS dict (2023–2026) — either hardcode the
   corrected figures from `docs/backtest-methodology.md`'s table (matching
   the existing `BACKTEST_RESULTS` pattern), or load directly from
   `data/backtest_results/thai_equity_{year}_n50/metrics.json` (confirmed to
   hold `cagr`, `sharpe`, `max_drawdown`, `alpha_vs_equal_weight`, etc.) — the
   latter is more drift-resistant since it can't silently go stale the way
   the hardcoded dict did.
2. **Charts**: `chart_cagr_comparison()`, `chart_sharpe_comparison()`,
   `chart_max_drawdown()` (lines 52/89/123) are all built for a single-period
   strategy-vs-benchmark comparison — need either generalizing to accept a
   list of years, or a new set of year-over-year bar chart functions.
3. **New section**: add an `<h2 id="s10">4-Year Out-of-Sample Summary
   (2023–2026)</h2>` block in `build_html()` (section building starts line
   252), with the corrected table + new charts, wired into the Contents list
   (line 363 onward).
4. **Framing**: `user-manual.md` now leads with the 2023–2026 OOS results and
   treats 2022–2024 as a secondary "canonical backtest," but the HTML's only
   section is titled plainly "Backtest Results (2022–2024)" with no OOS
   mention — section ordering/titling needs to match the `.md`'s framing, not
   just gain a new section bolted on after.
5. **Open decision**: whether to also port the Bonferroni-correction and
   regime-retraction narrative (now correct in the `.md`) into the HTML, or
   keep the HTML lighter-weight and just link to the `.md` for that detail.

## Effort

Medium — mostly mechanical (new data + 1–2 new chart functions + 1 new
section), but item 4 (re-framing, not just appending) is the part that takes
judgment.
