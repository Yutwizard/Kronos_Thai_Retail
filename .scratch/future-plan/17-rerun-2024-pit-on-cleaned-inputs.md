# Ticket 17: rerun the 2024 point-in-time forecasts on cleaned inputs (DRAFT, needs approval)

STATUS: CLOSED 2026-09-22 (user decision: do not run Stage 2). VERDICT: G3, inconclusive on a 53-date sample; stub-row contamination does not look like the explanation for the 2024 result. Stage 2 (~33h) NOT run. Opened by the MATERIAL verdict of ticket 12. Depends on ticket 13 (clean loader). Needs the user's approval and a compute choice (GPU, or slow CPU).

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

## Cost and prerequisites (superseded by 'Measured facts' below)
- Number of forecasts: about 13,100 (262 dates x about 50 tickers). The compute time of the original run is not recorded in the repo; estimate it on a small batch first.
- Kronos-small needs the local model weights and torch (`requirements-ml.txt`); a GPU is strongly preferred (Kaggle or Colab are the project's GPU runtimes).

## Open before approval
1. Approve the rerun, or decide the 2024 result is left as "not re-checked" and only flagged.
2. Compute choice: Kaggle/Colab GPU (recommended), or local CPU.
3. Whether to also rerun 2023 and 2025-2026 windows later (ticket 00 deliberately did not re-run them); not part of this ticket.

## Measured facts (2026-09-21, no result peeking)
- Compute: this machine has a CUDA GPU (GTX 1060, 6 GB), torch 2.5.1+cu121, and the Kronos-small weights in the local HF cache. Timing of `forecast_batch` with the original settings (lookback 400, pred_len 20, n_samples 50): 9 frames 100 s, 49 frames 545 s, about 11 s per forecast, about 9 minutes per date of about 50 tickers, peak GPU memory only 765 MiB (compute-bound). Ticket 00 records about 9.5 minutes per date on the same GPU, so the original 2024 run took about 40 hours here. Forecasts from the timing run were discarded and never evaluated.
- Full rerun: 262 dates x about 9 min = about 40 hours. Generation is idempotent per date (`precompute_forecasts` skips cached dates), so it can run unattended in chunks and be resumed. A Kaggle/Colab T4 was not measured.
- Prerequisite gap: `kth/data/clean.py` cleans closes only. Kronos needs full OHLCV(+amount) windows, so the loader must first gain a frame-level function (drop stub dates and the ticker's own stub rows across all columns, scale open/high/low/close and amount for the TRUE.BK break) with a self-test.
- Original signal quality, existing 2024 PIT cache (`scripts/pit_signal_quality.py`): mean rank IC -0.104, 95% CI [-0.214, +0.024] (262 days, block bootstrap, overlapping 20-day windows). The interval includes 0, so the "-0.10" quoted elsewhere is not statistically distinguishable from zero.
- Exploratory split of that IC by period (descriptive only, overlapping windows, small n, NOT a test): Jan-Feb (windows nearly clean, mean 0.2 stub rows) -0.102 [-0.182, -0.010]; Mar-May -0.003 [-0.117, +0.114]; Jun-Aug -0.037 [-0.289, +0.263]; Sep-Dec (heaviest contamination, about 45 stub rows) -0.231 [-0.308, -0.142]. No monotonic dose-response: the nearly clean months already show a negative IC, and the mid-year months are near zero. So contamination is not an obvious sole cause of the negative result, and the raw data cannot settle it.

## Options (need the user's choice)
- A. Full rerun on the local GPU: about 40 h, resumable, answers both the IC and the -26% backtest question.
- B. Staged (recommended): Stage 1 = cleaned forecasts on every 5th business day of 2024 (53 dates, about 8.5 h), IC comparison only; Stage 2 = the other 209 dates (about 33 h) and the full backtest only if the gate below says so.
- C. Kaggle/Colab T4: unmeasured, needs upload/setup; only worth it if the machine cannot be tied up for days.
- D. Do nothing: leave the 2024 result flagged "not re-checked".

## Staged design (option B, frozen before running if approved)
- Stage 1 dates: `pd.bdate_range("2024-01-01", "2024-12-31")[::5]` (53 dates), every frozen thai_equity ticker with 400 real rows after cleaning. Cleaned input as defined above; same model, n_samples, seed and point-in-time guard as the original run; output to `data/forecast_cache_pit_clean/`.
- Metric: mean daily rank IC of the 20-day forecast vs the realised 20-day return, computed with `scripts/pit_signal_quality.py` logic (parameterised on the cache directory) for the cleaned and the original cache on the SAME 53 dates, plus the paired per-date difference (cleaned minus original); block-bootstrap 95% CIs.
- Gate, fixed now:
  - G1: cleaned IC CI lower bound above 0, or paired-difference CI lower bound above 0 -> run Stage 2 and the full backtest comparison of this ticket.
  - G2: paired-difference CI includes 0 AND cleaned IC CI upper bound below 0 -> STOP: cleaning does not change the signal; the 2024 loss is not a contamination artifact; the -26% stands as originally measured.
  - G3: anything else (both CIs include 0) -> inconclusive; stop and ask the user whether the further 33 h is worth it.
- Power warning: 53 dates with overlapping 20-day windows give low power, so G2 will rarely trigger and G3 is the most likely outcome. Say so in any write-up.
- No parameter, ticker list, date or window changes after seeing Stage 1.

## Open before approval
1. Option A, B (recommended), C or D.
2. Compute: local GPU unattended (recommended for B, 8.5 h for Stage 1) or Kaggle/Colab.
3. Approve the gate rules G1-G3 and the prerequisite loader extension (frame-level cleaning with a self-test), which I would write first.

## Stage 1 results (run 2026-09-21/22, GPU: local GTX 1060)
- Generation: `scripts/run_pit_stage1_clean.py`, log `data/logs/pit_stage1_clean.log`. All 53 dates completed, 50 of 51 tickers forecast per date (1 ticker -- the same one skipped by the original run for insufficient history -- lacks a full 400-row window even after cleaning), 0 errors, 0 point-in-time violations (`lookback_end` never after its own date). Cleaning removed 57 stub dates and applied the TRUE.BK break; 49 of 51 tickers had at least one of their own stub rows removed from their input history. Wall time: about 6h30m for 53 dates (~7.4 min/date), a bit faster than the ~9 min/date estimate.
- Comparison: `scripts/compare_pit_stage1_ic.py`, log `data/logs/pit_stage1_ic_comparison.log`. Same 53 dates, same realised-return series (unclean, since it is a fact about what happened, not a model input) for both sides, so the comparison isolates the effect of cleaning the model's input only.

| | mean rank IC | 95% CI | n |
|---|---|---|---|
| original cache, same 53 dates | -0.1088 | [-0.2117, +0.0027] | 53 |
| cleaned Stage-1 rerun | -0.1139 | [-0.2202, +0.0028] | 53 |
| paired difference (cleaned - original) | -0.0051 | [-0.0243, +0.0141] | 53 |

Cleaned IC was higher than original on 24 of 53 dates (close to a coin flip).

### Gate outcome
G3: inconclusive. The paired-difference CI includes 0 (rules out G1) and the cleaned IC's CI also includes 0 (rules out G2, which needed the cleaned CI entirely below 0). Per the frozen rule, the run stops here and the remaining ~33 hours (Stage 2 + the full backtest) is not spent without asking the user.

## Reading
- Cleaning the model's inputs did not detectably change the 2024 signal quality in either direction, on this sample. The point estimate moved from -0.109 to -0.114 (slightly worse, not better), and the paired difference is centered at essentially zero with a tight-ish CI that still straddles it.
- This is consistent with the ticket-12 exploratory split, which already showed no dose-response between stub density and IC (the least-contaminated months were already negative). Stub contamination in the model's 400-row input window does not look like the explanation for the 2024 signal's weakness.
- It does NOT prove the signal has no value or that cleaning would never matter over a longer sample; 53 dates with overlapping 20-day windows is low power, as flagged before running.
- No change to the standing conclusion: 2024 point-in-time still shows a weak-to-negative signal (IC not distinguishable from zero even before cleaning), and this Stage-1 check gives no evidence that the raw stub-row problem was hiding a better signal.

## Decision needed from the user
Per Option B's design: G3 means STOP and ask, not automatically proceed. Continuing to Stage 2 (the other 209 dates, about 33h, then the full backtest comparison) would only confirm this null result more precisely; it would not plausibly reverse it, since the mean shifted in the wrong direction. Recommended: do NOT run Stage 2; record the 2024 result as "checked for stub-row contamination on a 53-date sample, no detectable effect found" and close this ticket. Leave the option to run Stage 2 open if the user wants full-year confirmation regardless.

## Closure (2026-09-22)
User decision: close without running Stage 2. Recorded conclusion: the 2024 point-in-time result (CAGR -26.2%, rank IC -0.104, ticket 00) was checked for stub-row contamination on a 53-date sample (every 5th business day of 2024) and no detectable effect was found (IC -0.1088 original vs -0.1139 cleaned, paired-difference 95% CI [-0.0243, +0.0141]). The 2024 finding stands as originally measured; it is not attributable to the data-quality problems found in the 2026-09-21 audit. Full-year confirmation (Stage 2) remains an option if ever wanted, but is not planned.
