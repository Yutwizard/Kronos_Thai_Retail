# Ticket 20: forward shadow books for momentum and SMA200 (DRAFT, needs approval)

STATUS: DRAFT 2026-09-23 (from the 2026-09-23 review, item R3). Nothing built or run. Approve Q1-Q5 before implementation. Written blind: no forward result exists yet.

## Why
No unseen SET history is left (PLAN multiple-testing register). The only clean test for a new idea is forward data. Ticket 16 recommended exactly this for price-only momentum. Two rules already have fixed definitions and past (failed or marginal) evidence, so they can run forward next to the Kronos live book at almost no cost: computed books, no manual fills.

## Books (rules copied unchanged; no tuning)
- **S1 momentum 12-1:** ticket 06 strategy A: close[t-21]/close[t-252] - 1, top 10, equal weight, monthly rebalance on the first trading day, eligible = at least 252 days of history and a real (non-stub) price at the signal date.
- **S2 stock-level SMA200 filter:** ticket 09 candidate 3: each eligible ticker whose prior close is above its 200-day SMA gets weight 1/N_eligible, the rest is cash; monthly rebalance.
- Benchmark for both: equal-weight of all eligible names in the same universe, monthly rebalance (tickets 06/09).
- Universe: the 51 frozen `thai_equity` tickers (ticket 11 list). DRs are excluded because the rules were defined and tested on thai_equity only. A delisted or suspended name is sold at its last real close.
- Costs: 0.268% one-way x turnover on rebalance days. Signal at close d-1; returns from day d.

## Forward honesty
- On each rebalance day (the first "Run Pipeline" of the month) a script records the picks, weights and signal values to `data/positions/shadow_picks.csv`. That file is captured by the daily snapshot (ticket 05), so every pick is time-stamped before its returns exist.
- At review time, returns are rebuilt from a frozen snapshot and must match the recorded picks. A mismatch is reported in the process log, and the recorded picks are the ones used.

## Evaluation
- Window: from the first trading day of the month after approval (proposed 2026-11-02) to its own review dates: **twelve-month decision at the first trading day of 2027-11**, 24-month continuation as in ticket 11 addendum A2.
- Test: the same as ticket 11: paired stationary block bootstrap on daily active return (book minus benchmark), 10,000 resamples, seed 42.
- Multiple testing: the Kronos live book (its own frozen rule, 0.05) plus S1 and S2 are counted as one register entry of 3 forward tests. S1 and S2 each need **one-sided p < 0.05/3 = 0.0167** with the pooled CI lower bound > 0 and positive active return in each six-month half. Stated openly: including Kronos's unchanged 0.05, the combined false-positive rate is at most about 0.083.
- No six-month edge claim. At six months: futility only (active-return CI entirely below 0), with the same "recommendation, never automatic" wording as ticket 11.
- Power: the same warning as ticket 11 addendum A1 applies. Twelve months detects only very large edges.

## Build (after approval)
- `scripts/shadow_books.py`: `--record` (writes the month's picks once; refuses to rewrite a month that is already recorded), `--review` (date-guarded like `live_track_review.py`), `--selftest` (synthetic only). Hooked into `cmd_generate` after STEP3, non-fatal like STEP4.
- The ticket-06/09 helpers are reused, not copied, so the rule code matches what was tested.

## Questions (recommended answers first)
- Q1: S1 and S2 exactly as defined in tickets 06 and 09, thai_equity only? **Recommended: yes.**
- Q2: Start on the first trading day of 2026-11 (enough time to build and self-test)? **Recommended: yes.**
- Q3: Threshold 0.0167 for each shadow book, register entry of 3 with Kronos? **Recommended: yes.**
- Q4: Record picks in `shadow_picks.csv` at each rebalance, captured by the snapshot? **Recommended: yes.**
- Q5: Include low-volatility 60d (ticket 06 strategy B) as S3? **Recommended: no.** It lost significantly in 2020-2022, and a fourth book would lower every threshold to 0.0125.
