# 02 - Lock the max-holding-days research decision

Type: grilling
Status: resolved

Blocked by: 01

## Question

Given the per-year 2023-2026 PSR/Sharpe/friction/drawdown results from Ticket
01's sweep (baseline vs `max_holding_days ∈ {20, 40, 60, 90}`, `cooldown_days=5`),
decide:

1. Adopt a `max_holding_days` + cooldown cap, or reject the mechanism
   entirely?
2. If adopted — which `max_holding_days` value, and does the fixed
   `cooldown_days=5` hold or need its own follow-up sweep (see map's "Not yet
   specified")?
3. Does the adopted (or rejected) config preserve the regime-conditional edge
   documented in CLAUDE.md — i.e. does it still crush flat/down years like
   2024 (the only year that cleared p<0.05), or does capping holding period
   dilute that edge by force-exiting winners early in a grinding uptrend?

Decision rule (locked when this map was charted): adopt only if net
PSR/Sharpe — net of friction — improves across the sweep **without** eroding
that regime-conditional edge. Otherwise reject.

Record the locked verdict as a new bullet in CLAUDE.md's "Research decisions
that constrain code" section, matching the style of the existing
"Position sizing: equal-weight only" / "Fine-tuning: thai_equity stays
zero-shot" entries — the rule itself, then why (the sweep evidence), then
what it constrains going forward.

## Answer

**Verdict: ADOPT** `max_holding_days=60`, `cooldown_days=5`.

Walked the sweep table with the user. The straightforward reading of the
locked decision rule ("adopt only if... without eroding the 2024 edge")
argues for rejection — every capped config weakens 2024's PSR/Sharpe/p-value
versus baseline, and friction is equal-or-higher everywhere, every year.
Surfaced that tension explicitly before finalizing: cap60's 2024 numbers
(Sharpe 2.23→1.94, p=0.017→0.036) are objectively worse than baseline, and
choosing cap60 requires **relaxing** the original rule, not satisfying it.

User's call, made with that tension explicit rather than glossed over:
relax the rule to a holistic judgment across the whole sweep. cap60 clears
p<0.05 in 2024 (still passes, just less confidently), ties baseline exactly
in 2026 (cap never bound in that short window — no downside), wins clearly
across every metric in 2023, and is close (not badly worse) in 2025. That
profile — never a clean loser, one clean winner, one near-tie, one modest
give-up in the flagship year — was judged worth the trade versus rejecting
outright over a single weakened (but still significant) p-value.

Recorded as a new bullet in CLAUDE.md's "Research decisions that constrain
code" section, immediately after the equal-weight-sizing entry, with the
rule-relaxation made explicit in the text (not hidden) and an explicit note
that implementation into the live `BacktestConfig` defaults is a **separate,
not-yet-done** follow-up effort — this ticket's destination was the decision
only.

## Revision (2026-07-29): verdict reversed to REJECT

The original ADOPT call above was made off **annual point-estimates**
(CAGR/Sharpe/PSR/t-test p-value from `compute_metrics()`), comparing cap60's
full-year numbers against baseline's. Prompted by a user question about
whether cap60's edge could just be noise from the single Kronos Monte Carlo
forecast draw the sweep used, ran a follow-up check — cheaper than a
multi-draw re-run, and it changed the picture: a **paired stationary block
bootstrap** (same block-length method as `compute_sharpe_ci` in
`kth/backtest/metrics.py`) on the **daily active-return series**
(`cap60_returns − baseline_returns`), per year and pooled, via
`scripts/analyze_cap60_significance.py` (reads the already-saved
`daily_returns.parquet` from Ticket 01's sweep — no new inference):

```
[2023] active_mean(ann)= +6.69%  95% CI=[ -0.55%, +15.94%]  P(active≤0)=0.038
[2024] active_mean(ann)= -4.50%  95% CI=[ -8.96%,  -0.79%]  P(active≤0)=0.991
[2025] active_mean(ann)= -8.51%  95% CI=[-23.54%,  +0.94%]  P(active≤0)=0.944
[2026] active_mean(ann)=  0.00%  95% CI=[  0.00%,   0.00%]  P(active≤0)=1.000  (cap never bound — no difference, not a loss)
[pooled 2023-2026] active_mean(ann)= -1.78%  95% CI=[ -6.98%,  +2.47%]  P(active≤0)=0.766
```

This is materially different from the annual-table picture the original
ADOPT call rested on:

- **2024's degradation is not a modest point-estimate dip — it's the one
  statistically clean result in the whole sweep, and it's negative.** The CI
  doesn't cross zero. The original relaxation argument ("still passes
  p<0.05, just less confidently") understated how solid this loss is at the
  daily paired level.
- **2023's win — the main thing that justified relaxing the rule — is only
  marginal** (CI lower bound -0.55%, barely below zero), not the clean win
  the annual table suggested.
- **2025 leans negative, not "close."**
- **Pooled across all four years the effect is statistically indistinguishable
  from zero**, if anything leaning slightly negative.

The "ties-or-beats baseline in 3 of 4 years" framing that justified relaxing
the original decision rule does not hold up under this test: it's one
marginal win, one clean loss, one leaning-loss, and one true tie (2026, cap
never bound). **Verdict reversed: REJECT `max_holding_days`/`cooldown_days`
as tested.** CLAUDE.md's entry updated accordingly (see below) —
edited in place rather than left as a stale adopted decision, since nothing
was ever wired into production off it.

Caveat carried forward, not fully resolved by this check: this is still a
single Kronos forecast draw. The block bootstrap addresses path-dependent
return noise *given* that draw, not whether an independent forecast draw
would shift the ranking. Given the pooled result already leans negative
with a wide CI rather than showing a noisy-but-positive effect, there's no
positive finding here left to confirm via the more expensive multi-draw
test — it would mostly be re-confirming "no clear edge," so it's not deemed
necessary to reach this verdict. Left as a future option if someone wants
to rule out a real effect more conclusively rather than just failing to
find one.

Status: resolved (revised).
