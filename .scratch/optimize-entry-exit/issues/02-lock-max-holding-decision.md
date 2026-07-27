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

Status: resolved.
