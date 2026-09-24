# Future plan (from the 2026-09-17/18 graphify audit)

Not yet filed as GitHub issues: `gh` is not installed here. File each with
`gh issue create` once available (see `docs/agents/issue-tracker.md`, labels
per `docs/agents/triage-labels.md`), then delete this folder.

| # | Ticket | Status (2026-09-21) |
|---|--------|------|
| 00 | Historical forecast cache not point-in-time (look-ahead) | Fixed in code; 2024 re-run done: strategy loses (CAGR -26%, IC -0.10). 2023/2025/2026 deliberately NOT re-run. |
| 01 | HTML doc renders drifted from Markdown | Superseded for results: invalidation notice added to all HTML/MD docs via the builders. Remaining structure drift is low priority. |
| 02 | One Correction Family for significance wording | Done except optional pooled test (moot: the numbers are invalid). |
| 03 | Volatility-regime entry threshold experiment | CLOSED as moot: no valid baseline edge to improve; code kept, off by default. |
| 04 | Verify Kronos pre-training cutoff | CLOSED as low value: only mattered for interpreting backtests that now fail. |
| 05 | Forecast Cache backup policy | DONE 2026-09-23 for the live evidence: `scripts/snapshot_live_data.py`, automatic after every Run Pipeline, read-only hash-checked snapshots in `~/backups/kronos-th-snapshots`. Still open: an off-machine copy. |
| 06 | Factor baselines vs equal-weight (pre-registered) | Done: momentum passed 2023-2026 narrowly, did not confirm on 2020-2022. |
| 07 | Entry/exit variants and stop-loss on clean windows | Done: no variant rescues the strategy; stops made 2024 worse. |
| 08 | arXiv 2020-2026 strategy literature, ranked shortlist of 20 | Done 2026-09-21: no paper gives a cost-robust, out-of-sample, long-only stock edge. |
| 09 | Pre-registered SET test of 3 literature candidates | Run 2026-09-21: none adopted (LightGBM ranker, VP-MACD overlay, SMA200 filter all fail the discovery bar). |
| 10 | Trend filter (SMA200) drawdown check on untouched 2018-2019 window | Run 2026-09-21: neither the stock-level nor the index-level filter improved Sharpe; drawdown lower but return given up or unchanged. Closed. |
| 11 | Pre-committed review rule for the live paper track | APPROVED 2026-09-21; review script `scripts/live_track_review.py` written and self-tested on synthetic data only. First review due 2026-12-30 (futility), edge decision 2027-06-30. Addendum A (2026-09-23, DRAFT QA1-QA3): 12-month power, 24-month continuation, snapshot-only reviews, dividend-adjustment bias (ticket 19). |

| 12 | Stub-row impact on Kronos input windows (2024 PIT, live) | DONE 2026-09-21: MATERIAL (76.9% of 2024 windows affected, 48.6% heavy; live about 1.3% of input rows). Follow-up 17. 2026-09-23: pipeline unchanged; stub share added to the review process log. |
| 13 | Tested clean-data loader + `^SET.BK` repair retry | DONE 2026-09-21: `kth/data/clean.py` + `verify_clean_data.py`, reproduces the ticket-09 cleaned frame exactly; `^SET.BK` repair blocked (Yahoo returns one row). |
| 14 | Ticket 06 factor baselines on cleaned data | DONE 2026-09-21: momentum lead withdrawn on cleaned data (p 0.0379 vs bar 0.0167); nothing adopted. |
| 15 | LightGBM sign-flip diagnostic | DONE 2026-09-23: mostly explained by data drift (the raw cache is not stable across days -- a bigger finding than planned) plus a near-zero, noise-like signal (IC CI spans zero both windows) and adv_20d's scale sensitivity. Nothing adopted. |
| 17 | Rerun 2024 PIT forecasts on cleaned inputs | CLOSED 2026-09-22: Stage 1 (53-date sample) found no detectable IC change from cleaning (gate G3); user chose not to run Stage 2. 2024 result stands. |
| 16 | Non-arXiv literature on SET / emerging-market strategies | DONE 2026-09-22: 5 papers verified; Thai literature is mostly long-short/fundamentals-based, none fits the price-only rubric well except a technical-trading-rules paper and a price-only momentum factor. Nothing tested. |
| 18 | Kronos forecast quality vs naive baselines (2024 PIT) | DRAFT 2026-09-23, needs approval (Q1-Q4). Tests the "forecasting tool" claim; opens no correction family. |
| 19 | Live fill realism + dividend-adjustment bias in the review | DRAFT 2026-09-23, needs approval (Q1-Q4). Do before 2026-12-30. |
| 20 | Forward shadow books: momentum 12-1, SMA200 | DRAFT 2026-09-23, needs approval (Q1-Q5). After 05 (done) and ticket-11 addendum A. |

Sequence, gates and the multiple-testing register: `PLAN-next-research.md`.

Overall verdict: no valid evidence of an edge over equal-weight buy-and-hold. Live paper trading (since 2026-06) is the only clean forward test; review after ~6 months against equal-weight with a pre-committed rule.

Done already: BANPU.BK fix in `CLAUDE.md` (history restored to 2,381 rows;
still to watch: a 38-day data gap ending 2026-09-18, thin liquidity).

## Deferred

- **Partial-fill model** (Phase 2 Task 2). At 500K THB and 10 positions the
  largest order is 4.5% of median daily traded value and no ticker hits the
  10% cap. It first binds near 1.1M THB total capital (BANPU.BK), and on 3
  tickers by 5M THB. Revisit when capital passes ~1M THB.

## Dropped

- **FX-adjusted returns** (Phase 2 Task 1). Written for USD-denominated
  crypto/us_equity, archived in the 2026-07-16 scope narrowing. DR tickers
  trade in THB on the SET.

## Noted, not in the plan

- `GULF.BK` in `CLAUDE.md` says 281 rows and "~Oct 2026"; the manifest now
  shows 357 rows, so that estimate is stale.
- Nothing has been run on GPU for any of this.
