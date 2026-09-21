# Ticket 15: why did the LightGBM ranker flip sign? (TODO, optional)

STATUS: TODO, optional, diagnostic only. Depends on ticket 13. Feeds no adoption decision.

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
