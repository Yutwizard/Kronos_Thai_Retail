# Ticket 17: rerun the 2024 point-in-time forecasts on cleaned inputs (DRAFT, needs approval)

STATUS: DRAFT 2026-09-21, NOT approved, NOTHING RUN. Opened by the MATERIAL verdict of ticket 12. Depends on ticket 13 (clean loader). Needs the user's approval and a compute choice (GPU, or slow CPU).

## Question
Ticket 00 re-ran the 2024 point-in-time backtest and found CAGR -26.2%, Sharpe -1.19, one-sided p 0.24 against equal-weight, rank IC -0.10. Ticket 12 showed the 2024 model inputs contained up to about 11% stub rows. Does that loss survive when the same forecasts are regenerated from cleaned inputs?

## Design (frozen before running)
- Cleaned input for forecast date D and ticker T: from `load_clean_closes` (ticket 13) drop stub calendar dates and T's own stub rows, then take the last 400 remaining rows up to the same `lookback_end` as before (rows are dropped, not filled). Fewer than 400 real rows -> the ticker is skipped that day, as the wrapper already does.
- Model, sampling settings, `pred_len`, `n_samples`, seed: exactly as in the original 2024 PIT run (`scripts/run_pit_backtest.py`, ticket 00). Only the input frames change.
- Output goes to a fresh cache directory (for example `data/forecast_cache_pit_clean/`); the existing PIT cache and its results are never overwritten. The point-in-time guard (`require_point_in_time_forecast`) must pass for every forecast.
- Backtest: same 2024 strategy config, same benchmark and friction, same paired block bootstrap as ticket 00. Signal quality: mean daily rank IC of the 20-day forecast vs the realised 20-day return, block-bootstrap 95% CI.

## Comparison rule (fixed now)
- Report original vs cleaned side by side: CAGR, Sharpe, max drawdown, pooled active return with CI and one-sided p, rank IC with CI.
- "Loss confirmed": the cleaned pooled active-return CI upper bound is below 0, or the cleaned rank IC CI upper bound is below 0.
- "Loss not confirmed, result inconclusive": both CIs include 0.
- "Signal appears positive on cleaned inputs": cleaned active-return CI lower bound above 0 and rank IC CI lower bound above 0. Even then nothing is adopted: it is one window, one shot, the other years would also need cleaned reruns, and no unseen historical window remains. The consequence would be a new pre-registration, not a change to the product.
- No parameter, strategy setting or window is changed after seeing the result.

## Cost and prerequisites (to confirm before approval)
- Number of forecasts: about 13,100 (262 dates x about 50 tickers). The compute time of the original run is not recorded in the repo; estimate it on a small batch first.
- Kronos-small needs the local model weights and torch (`requirements-ml.txt`); a GPU is strongly preferred (Kaggle or Colab are the project's GPU runtimes).

## Open before approval
1. Approve the rerun, or decide the 2024 result is left as "not re-checked" and only flagged.
2. Compute choice: Kaggle/Colab GPU (recommended), or local CPU.
3. Whether to also rerun 2023 and 2025-2026 windows later (ticket 00 deliberately did not re-run them); not part of this ticket.
