# ADR 0002: Zero-Shot Only (No Fine-Tuning in Production)

**Date:** 2026-06-21  **Status:** Accepted

## Context
9 fine-tuned checkpoints were trained (3 markets × 3 folds) via SGDR.

## Decision
Deploy zero-shot Kronos-small only. Fine-tuned checkpoints are saved but not deployed.

## Rationale
Fine-tuning did not beat zero-shot in any of the 3 markets (thai_equity, us_equity, crypto). Direction-accuracy gains from FT did not translate to backtest alpha.

## Consequences
- All production forecasts use `NeoQuasar/Kronos-small` zero-shot.
- FT checkpoints remain at `checkpoints/{model}/fold{f}/best/` for reference.
- Re-evaluating FT requires a full re-run; do not relitigate without GPU time.
