# 02 - Lock the regime-conditional-alpha decision

Type: grilling
Status: resolved

Blocked by: 01

## Question

Given Ticket 01's bull-day vs bear-day active-return split (per year and
pooled 2023-2026), decide:

1. Confirm or reject the regime-conditional-alpha claim, per the locked
   decision rule: confirm only if the bootstrap CI on (bull-day active
   return − bear-day active return) is significantly negative. Otherwise
   reject.
2. If **rejected**: revise CLAUDE.md's "Alpha is regime-conditional... In
   bull regimes, reduce to BEAR allocation" bullet — remove or replace it —
   and resolve the "⚠️ premise under re-verification" callouts already
   sitting in `PROJECT_STRUCTURE.md`, `operations-manual.md`,
   `user-manual.md`, and `backtest-methodology.md` (the bull/cash-drag
   narrative those callouts flagged) to match.
3. If **confirmed**: replace the informal "EW sign per calendar year"
   heuristic in those same docs with the statistically-grounded trailing-SET
   window/threshold this analysis established.

## Answer

**Verdict: REJECT.** Confirmed with the user against the pooled evidence
(positive, near-identical active return in both regimes; bull-minus-bear CI
[-34.31%, +37.53%], nowhere near significantly negative) — a clean
rejection, no rule-relaxation needed this time.

Three decisions on how to record it:
1. **CLAUDE.md:** replaced the "Alpha is regime-conditional" bullet with the
   retraction record (what was claimed, why the premise was wrong, what the
   corrected test found) — same pattern as the max-holding-days rejection
   earlier this session, not deleted outright.
2. **operations-manual.md** (has live, actionable operator instructions, not
   just narrative): removed the "use BEAR allocation in a SET bull market"
   directive and the "verify the regime" override-justification step,
   replaced with a retraction note plus corrected guidance (trust the
   automated trailing-Sharpe band, don't manually override on perceived SET
   regime). This one got the strongest treatment since leaving it in place
   risked an operator actually following bad guidance.
3. **PROJECT_STRUCTURE.md, user-manual.md, backtest-methodology.md**
   (narrative/explanatory only): deleted the disproven "2023 bull market,
   cash drag" narrative outright rather than keeping it as labeled history —
   user's call, cleaner docs over a preserved trail (the git history and this
   ticket already preserve the reasoning for anyone who wants it later).

While closing out, found the same claim also lived in three more places not
originally scoped into this ticket — fixed for consistency since leaving
them stale would have defeated the point: `README.md` caveat #4,
`AGENTS.md`'s Research Decisions (a separate file from CLAUDE.md with
overlapping but not identical content — also has a stale
"min_holding_days/long_threshold experiments are invalid" line contradicted
by this session's earlier `.scratch/optimize-entry-exit/` work; **not**
fixed here, flagged as a separate follow-up, out of scope for this ticket),
`docs/morning-paper-trading-guide.md`'s "Today's decision rule" (also had
live actionable guidance, same treatment as operations-manual.md), and a
second `operations-manual.md` section ("Extended Cash Regime"). Left
untouched: `reports/master_backtest_report.html` and its generator
`scripts/build_master_report.py` — hardcoded stale figures, but it's
generated output, flagged rather than hand-edited (same call made for the
p-value fix earlier this session).

Status: resolved.
