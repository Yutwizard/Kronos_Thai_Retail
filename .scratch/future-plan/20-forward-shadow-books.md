# Ticket 20: forward shadow books for momentum and SMA200

STATUS: APPROVED 2026-09-24 (user "agree" to Q1-Q5 as recommended). To build before the first trading day of 2026-11. Written blind: no forward result exists yet.

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

## Implementation notes frozen BEFORE any forward data exists (2026-09-24)
- **Prices:** `kth.data.clean.load_clean_closes` on the 51 frozen `thai_equity` tickers (stub dates dropped, known breaks scaled, `real` mask). At record time: the live `data/raw`. At review: the review snapshot's `raw/`.
- **Eligibility** (ticket 20 wording): at least 252 non-missing closes up to the signal date AND a real (non-stub) price on the signal date.
- **Rules**, reused unchanged from the tested scripts: S1 score `close.shift(21) / close.shift(252) - 1` (`run_factor_baselines.signals`) with `run_set_candidates.topn_weights`; S2 `run_set_candidates.sma_weights`; benchmark `ew_weights`; daily drift and rebalance cost via `run_set_candidates.simulate_gross` (0.268% one-way x turnover).
- **Why candidates are recorded:** the signal is the close of the last session before a month's first session, but on a given evening the pipeline cannot know whether today is the month's last session (SET holidays). So from the 20th of each month, every pipeline run appends a *candidate* set of picks for next month, with signal date = the latest clean session L, to `data/positions/shadow_candidates.csv` (append-only; a (target month, signal date) pair already present is never rewritten). Columns: `recorded_at, target_month, signal_date, book, ticker, weight, score`. The file is captured by the daily snapshot.
- **Effective picks for month M** (decided at review): d = first clean session of M; s = the clean session before d. The candidate with (M, s) is used if it exists and `recorded_at` is before d. Otherwise the picks are recomputed from the snapshot and counted as `late_or_missing` in the process log. A recorded candidate that differs from the snapshot recompute (data revision) is counted as `revised`, and the recorded picks are used (ticket 20).
- **Suspended or delisted holdings:** carried at the last close (return 0, as cash would earn), and sold with the normal cost at the next rebalance, where the name is not eligible. (Ticket wording "sold at its last real close": same value, with the cost deferred to the rebalance.)
- **Window:** 2026-11-02 (first session of November) to the review date. First candidates are recorded from 2026-10-20.
- **Reviews** (date-guarded): six-month futility on/after 2027-05-03; twelve-month decision on/after 2027-11-01; 24-month on/after 2028-11-01 with one-sided p < 0.0083 (the ticket-11 A2 halving applied to 0.0167).
- **Statistics:** daily active return (book minus benchmark); `evaluate_variant_vs_baseline` on six-month halves (H1 up to 2027-04-30, H2 after); `run_factor_baselines.one_sided_p`. EDGE CANDIDATE: pooled CI lower bound > 0, p < threshold, positive in every half. FUTILE (six months): pooled CI upper bound < 0.
- **Pipeline hook:** `dashboard.py --generate` STEP3b `shadow_books.py --record` after the trade ticket and before the snapshot. Non-fatal. It never changes the Kronos live book.

## Build (2026-09-24)
- `scripts/shadow_books.py` (`--record`, `--review`, `--selftest`), as frozen above. The self-test runs on synthetic data only and covers: the record window and first target month, idempotence, which candidate is effective, a recording after the month started not counting, late and revised logging, recorded picks driving returns including the first-day cost, the decision thresholds (0.0167 and 0.0083) and the date guard. No real forward data exists yet.
- Hooked in as STEP3b of `dashboard.py --generate`, after the trade ticket and before the STEP4 snapshot. Non-fatal.
- Real-data checks on 2026-09-24 only: `--record` answered "target month 2026-10 is before 2026-11" and wrote nothing; `--review six-month` was refused by the guard.
- First candidates will be written by the first Run Pipeline on or after 2026-10-20. Operator note: run the pipeline on the evening of the last SET session of October (and of every month), so the effective candidate is recorded before the next month's first session. A missed evening is recomputed at review and reported as `late_or_missing`.
