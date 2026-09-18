# Ticket 01: HTML doc renders are hand-maintained and have drifted from their Markdown

**Status:** Scoped, not filed. Type: docs/tooling. No GPU.
**Origin:** graphify audit + `user-manual.md` fix, 2026-09-17/18.

## Problem

`docs/user-manual.html` and `docs/operations-manual.html` are not renders of
their `.md` twins. Each is produced by a script that returns a hardcoded HTML
string (`scripts/build_usermanual_html.py`, `scripts/build_operations_html.py`),
so they drift silently. Two concrete symptoms:

1. **`user-manual.html`** only has the older "Backtest Results (2022-2024)"
   section (`s6`, ~line 490) fed from a hardcoded `BACKTEST_RESULTS` dict
   (~line 21). It has no 4-Year OOS (2023-2026) section, which
   `user-manual.md` §6 now leads with. Re-running the script cannot fix this.
2. **`operations-manual.html`** describes the legacy 100-ticker /
   all-asset-class notebook workflow and lacks the disclaimer that
   `operations-manual.md` carries at line 29 ("This describes the original
   notebook workflow... see Dashboard User Manual for the current one"). A
   reader of the HTML gets no hint that it is legacy.

## Changes

`scripts/build_usermanual_html.py`:
1. **Data**: add per-year OOS data (2023-2026). Prefer loading
   `data/backtest_results/thai_equity_{year}_n50/metrics.json` (has `cagr`,
   `sharpe`, `max_drawdown`, `alpha_vs_equal_weight`) over hardcoding, so it
   cannot silently go stale again. Note `p-value` and EW CAGR are not in
   `metrics.json`; take them from `docs/backtest-methodology.md`'s table or
   the run's other files.
2. **Charts**: `chart_cagr_comparison()`, `chart_sharpe_comparison()`,
   `chart_max_drawdown()` are single-period; generalize to a list of years or
   add year-over-year variants.
3. **Section**: add `<h2 id="s10">4-Year Out-of-Sample Summary (2023-2026)</h2>`
   in `build_html()` and the Contents list.
4. **Framing**: the `.md` leads with the OOS results and treats 2022-2024 as
   secondary; the HTML's only results section is titled "(2022-2024)". Match
   the `.md` ordering, don't just append.
5. **Open decision**: port the Correction Family / regime-retraction narrative
   into the HTML, or keep the HTML lighter and link to the `.md`.

`scripts/build_operations_html.py`:
6. Add the legacy-workflow banner and the pointer to the Dashboard User Manual
   (49 tickers). Small, independent of the rest; can ship first.

## Update 2026-09-18

- **Item 6 DONE**: legacy-workflow banner added to
  `scripts/build_operations_html.py` and `docs/operations-manual.html`
  regenerated (uncommitted at time of writing). While doing it, the committed
  HTML differed from the builder by one hand-edited row ("Forecasts looking
  stale", troubleshooting table); the builder was synced first so
  regenerating did not revert it. This is direct evidence the HTML is edited
  by hand independently of its builder.
- **New item 7**: `scripts/build_master_report.py` (feeds the git-ignored
  `reports/master_backtest_report.html`) still hardcodes pre-fix numbers and
  the retracted regime narrative: line 68 (2023 +2.6%, 2024 p=0.015), line 139
  ("Regime finding: SET bull 2023 (EW +12.8%)... Alpha is structural"), and
  lines 151/153 ("regime-dependent", "2023: +2.6%"). Only line 138 (the
  Bonferroni sentence) was fixed, under ticket 02. The table rows themselves
  come from `metrics.json` and are fine.

## Aside (not in scope)

Both builders share one root cause: nothing derives HTML from Markdown. A real
`.md` -> `.html` pipeline would remove this class of bug, but that is an
architecture change, not part of this ticket.

## Effort

Medium overall; item 6 is trivial, item 4 is the judgment call.
