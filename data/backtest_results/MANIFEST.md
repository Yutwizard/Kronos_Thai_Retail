> **⚠️ STALE NUMBERS:** Results in these directories were computed before the
> 2026-06-21 bug fixes (equity curve alignment, PSR formula, open_trades blending).
> A GPU re-run is required to get correct alpha/beta/IR/PSR numbers. Do NOT cite
> these numbers until the re-run is complete.

# Backtest Results Manifest

## Authoritative (n=50 samples, use these for citation — AFTER GPU re-run)

| Directory | Period | Notes |
|-----------|--------|-------|
| `thai_equity_2023_n50/` | 2023 | p=0.419 — bull market, cash drag |
| `thai_equity_2024_n50/` | 2024 | **p=0.015 — only year clearing p<0.05** |
| `thai_equity_2025_n50/` | 2025 | p=0.257 |
| `thai_equity_2026_n50/` | 2026 YTD | p=0.353 |

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
