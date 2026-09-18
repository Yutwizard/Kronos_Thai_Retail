> **Re-run completed 2026-07-29.** These numbers superseded two bugs, not one:
> (1) the originally-flagged 2026-06-21 fixes (equity curve alignment, PSR
> formula, open_trades blending) had never actually been re-run, because (2)
> `run_walkforward`'s last loop iteration re-marked the same day twice,
> crashing `compute_metrics()` on every attempt — found and fixed alongside
> `.scratch/optimize-entry-exit/`. Fixing that surfaced a third, independent
> bug while validating this re-run: the `equal_weight` and `60_40` benchmarks
> in `_compute_benchmarks()` silently degraded to a flat 1.0 line whenever
> `start_date` fell on a market holiday (e.g. Jan 1st — a business day by
> `freq='B'` but not an actual trading day), via a caught `KeyError`/
> `UnboundLocalError` in each benchmark's `except Exception` fallback. That
> bug directly corrupted the p-value below — it's a t-test of strategy
> returns **against the `equal_weight` benchmark**, so a flat degenerate
> benchmark silently turned it into a test against zero instead, a
> meaningfully weaker bar. Both bugs are now fixed; the numbers below are
> the first correct run of this test the project has had.
>
> **This changes the headline conclusion.** Under the old (bugged, vs-zero)
> comparison, 2024 was "the only year clearing p<0.05" (p=0.015). Under the
> corrected vs-equal-weight comparison: 2024 is *more* significant
> (p=0.001, now survives Bonferroni correction for the 4 OOS years,
> threshold p<0.0125 — previously "no year survives, 2024 is closest") and
> **2025 also now clears p<0.05** (p=0.027, previously p=0.257). 2026 moves
> the other way — was borderline (p=0.066 vs zero), now clearly
> non-significant (p=0.335 vs the real benchmark), because 2026's equal-weight
> benchmark itself surged in that bull run. `PROJECT_STRUCTURE.md` and the
> user-facing docs carry the corrected framing (checked 2026-09-18): 2024
> survives Bonferroni for the 4 OOS years; 2025 clears p<0.05 unadjusted only.

# Backtest Results Manifest

## Authoritative (n=50 samples, use these for citation)

| Directory | Period | Notes |
|-----------|--------|-------|
| `thai_equity_2023_n50/` | 2023 | p=0.313 (was 0.604 pre-fix) — bull market, cash drag |
| `thai_equity_2024_n50/` | 2024 | **p=0.001 (was 0.017 pre-fix) — survives Bonferroni for the 4 OOS years (p<0.0125)** |
| `thai_equity_2025_n50/` | 2025 | **p=0.027 (was 0.260 pre-fix) — now also clears p<0.05** |
| `thai_equity_2026_n50/` | 2026 YTD | p=0.335 (was 0.066 pre-fix) — no longer borderline; real EW benchmark surged too in this bull run |

## Superseded (do NOT cite — stale parameters)

| Directory | Why stale |
|-----------|-----------|
| `thai_equity_2020-2024/` | Pre-n50 (n=10 samples) |
| `thai_equity_2022-2024/` | Pre-n50 (n=10 samples) |
| `thai_equity_2022-2024_v2/` | Pre-n50 (n=10 samples) |
| `thai_equity_2022-2024_invvol/` | **Rejected** — inv_vol position sizing lost to equal-weight |
| `thai_equity_2023-2026/` | Full range, not per-year |
| `thai_equity_2026_n50_full/` | Extended 2026, not canonical |
| `thai_equity_2026_ytd/` | YTD only, not canonical |
| `test_2024q2/` | Early test run |

## Fine-tune vs zero-shot comparisons (archived 2026-07-16)

Project scope narrowed to SET equities + DR only; crypto and us_equity
backtests moved to `archive/other-asset-classes/data/backtest_results/`.

| Directory | Verdict |
|-----------|---------|
| `crypto_ft/` | FT did not beat ZS |
| `crypto_zs/` | Zero-shot baseline |
| `us_equity_ft/` | FT did not beat ZS |
| `us_equity_zs/` | Zero-shot baseline |

**Rule:** Only cite `*_n50/` results. Pre-n50 runs used n=10 samples (invalid for parameter tuning per AGENTS.md). inv_vol was conclusively rejected.
