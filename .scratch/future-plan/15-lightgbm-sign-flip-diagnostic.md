# Ticket 15: why did the LightGBM ranker flip sign? (TODO, optional)

STATUS: DONE 2026-09-23. Answer: mostly DATA DRIFT, not the model. The raw cache is not stable across days (see below) -- a bigger finding than the ticket's original scope. Depends on ticket 13. Feeds no adoption decision; nothing here is promoted.

## Question
In ticket 09 the frozen LightGBM top-10 ranker had pooled active return -12.6% (95% CI entirely below 0) in 2023-2026 and +9.0% (CI spanning 0) in 2020-2022, and both numbers moved by several points when one ticker's price scale changed (the rank-transformed dollar-volume feature). What explains the instability?

## Method (read-only analyses on the frozen model definition; no new candidate)
1. Rerun the frozen model through the clean loader and compare with the primary and the earlier cleaned-data run.
2. Feature importance by retrain month (gain) for both windows; which features flip.
3. Monthly rank IC of the model score vs the realised 20-day return in each window, with block-bootstrap CIs.
4. Sensitivity: drop each feature in turn, and drop the dollar-volume feature, to see whether the flip disappears (reported, not tuned).
5. Turnover and concentration (top-10 overlap month to month), and how many months the model held the same few names.

## Rules
- The ranker definition, hyperparameters and windows stay as frozen in ticket 09. Any variant is labelled a diagnostic and is never adopted or promoted to the paper track.
- No new correction family.

## Output
A short note appended to this ticket: the most likely cause (regime dependence, feature scale sensitivity, thin training history, or noise), with the supporting table.

## Result (run 2026-09-23, `scripts/diagnose_lgbm_sign_flip.py`, log `data/logs/lgbm_sign_flip_diagnostic.log`)

### Headline finding: ticket 09's own numbers are not reproducible today, because `data/raw/` changed underneath it
Before any of the planned diagnostics, item 1 ("rerun the frozen model ... and compare with the primary [ticket-09] run") failed to reproduce: on TODAY's cache the discovery-window pooled active return comes out **-5.4% [-16.9%, +6.5%]**, not ticket 09's recorded **-12.6% [-23.4%, -1.4%]**; holdout comes out **+6.5% [-8.1%, +20.6%]**, not **+9.0%**. This is not a bug in this diagnostic: a byte-for-byte reimplementation of `run_set_candidates.lgbm_scores` + `topn_weights` + `simulate_gross`, run against the SAME in-memory data as the real frozen script, gave a **max absolute difference of 0.0** against calling the real script's own functions directly -- proven, not assumed.

The cause, CONFIRMED 2026-09-23 by process inspection: `scripts/dashboard.py --generate` (PID 2948436) started at 20:52:27, two minutes before `data/raw/manifest.json`'s `written_at` of 20:54 -- this is the dashboard's documented "Run Pipeline" action (CLAUDE.md: "trigger them via the dashboard's 'Run Pipeline' button or `venv/bin/python scripts/dashboard.py --generate`"), spawned from a `scripts/dashboard.py --serve` process that has been running in a VS Code integrated terminal since 2026-09-18 -- i.e. the project owner's own dashboard, most likely triggered by the project owner in another terminal, independent of this session. Row counts drifted from what earlier tickets recorded (SCB.BK 1,074 -> 1,077 rows; PTT.BK 2,436 -> 2,435 rows, last date moving from 2026-09-18 to 2026-09-23), consistent with a fresh `download_universe()` run. A spot check of one historical price (TRUE.BK's 2023-03-03 close, 8.217 recorded earlier this session) is unchanged today, so no retroactive price revision was found on that name.

**Consequence for every earlier ticket in this project that reads `data/raw/` directly (06, 09, 10, 14, 17):** their code and parameters are frozen as designed, but their sole data input is not frozen across calendar days. A rerun of any of them today would not reproduce the exact numbers on record, even with zero changes to the script. This is a more fundamental and more general explanation for "the numbers moved by several points" than the ticket's original hypothesis (feature-scale sensitivity to one ticker) -- though that mechanism is real too (ticket 09 already showed the TRUE.BK price-scale change shifted results by several points within a single day's data). **Not investigated further here**: whether the drift is from genuinely new trading days, a corporate-action re-adjustment, or a cache-integrity fix; that would need its own ticket if the user wants it pinned down. **Correction (investigated and retracted, 2026-09-23):** this section originally flagged `git log` commits (`f898ca4`, `d017a8f`, `0d253e0`, `ee6e0e1`) as unexplained. On checking dates and ancestry, they are ordinary pre-existing project history dated 2026-09-10 to 2026-09-17 -- BEFORE this diagnostic session and before every other ticket in this plan -- all authored by the project owner (Yut) doing routine manifest updates from earlier data downloads. `git merge-base --is-ancestor` confirms they are simply older commits on the same branch, not concurrent activity. There is nothing unexplained: withdrawn.

### Planned diagnostics (run on today's snapshot; self-consistent, not compared to old headline numbers)
Both loaders (original and ticket-13 clean) give the same qualitative picture; only the clean-loader numbers are summarised here since ticket 14 already established cleaning matters more for the factor rules than for this model.

**2. Feature importance by retrain month (gain-based share):**
| window | mean share (highest to lowest) |
|---|---|
| discovery | adv_20d 21.8%, mom_12m 20.4%, vol_60d 20.0%, mom_3m 18.4%, vol_20d 11.6%, mom_1m 7.8% |
| holdout | vol_60d 22.7%, adv_20d 21.9%, mom_3m 20.9%, mom_12m 16.7%, vol_20d 8.9%, mom_1m 8.8% |

No single feature dominates in either window (max ~23% of total gain), and the ranking of the top 3 features differs between windows (adv_20d/mom_12m/vol_60d in discovery vs vol_60d/adv_20d/mom_3m in holdout) -- some regime dependence in which feature the model leans on, but nothing categorical.

**3. Monthly rank IC (score vs realised 20-day return), block-bootstrap 95% CI:**
| window | mean IC | 95% CI |
|---|---|---|
| discovery | -0.004 | [-0.058, +0.046] |
| holdout | +0.012 | [-0.038, +0.060] |

Both intervals span zero comfortably. The model's monthly signal quality is statistically indistinguishable from noise in both windows -- this alone is close to sufficient to explain sign instability: a signal with no real predictive power will vary in sign across periods essentially at random.

**4. Sensitivity (drop-one-feature, simple annualised pooled active, not bootstrapped; clean loader):**
| dropped feature | discovery | holdout |
|---|---|---|
| mom_1m | -1.8% | +15.7% |
| mom_3m | +2.9% | +6.6% |
| mom_12m | -1.8% | +10.2% |
| vol_20d | -10.9% | +7.2% |
| vol_60d | -9.3% | +6.1% |
| adv_20d | +1.7% | -0.1% |
| (full model) | -1.4% | +6.1% |

No feature removal flips the discovery-window sign to positive or the holdout sign to negative; both signs are stable to which feature is dropped, given today's data. Dropping `adv_20d` (the dollar-volume feature ticket 09 flagged as scale-sensitive) has the largest effect on holdout (+6.1% to -0.1%, i.e. it removes most of the holdout's apparent edge) and only a small effect on discovery -- consistent with ticket 09's finding that this feature's scale sensitivity mattered more for the holdout number.

**5. Turnover and concentration:**
| window | month-to-month top-10 overlap | names held >=50% of scored months |
|---|---|---|
| discovery | 56.0% | 5 of 43 ever picked |
| holdout | 57.4% | 5 of 45 ever picked |

Moderate persistence (about half the top-10 carries over month to month) with a small core of frequently-held names in both windows; not itself a sign of instability.

## Conclusion
Most likely cause, in order: (1) **the underlying data changes day to day** (headline finding above) -- this alone means "the same frozen model" is not actually being fed the same inputs on different calendar days, and is the most concrete, evidenced explanation for why numbers "moved by several points"; (2) **the signal is not distinguishable from noise** (IC CIs span zero in both windows) -- a model with no real edge will naturally flip sign as the sample changes; (3) **feature-scale sensitivity of `adv_20d`**, confirmed again here (drop-adv_20d changes the holdout result the most), consistent with ticket 09's original observation. Regime dependence in feature importance (item 2) is present but secondary -- no feature categorically explains the flip on its own (item 4). This is diagnostic only; nothing here is adopted, and the candidate remains rejected per ticket 09.
