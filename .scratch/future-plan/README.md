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
| 05 | Forecast Cache backup policy | Partly done: PIT 2024 cache and live folders (2026-06-22 on) tarred to ~/backups. Old contaminated cache needs no backup. Decide a recurring copy of live folders + data/raw. |
| 06 | Factor baselines vs equal-weight (pre-registered) | Done: momentum passed 2023-2026 narrowly, did not confirm on 2020-2022. |
| 07 | Entry/exit variants and stop-loss on clean windows | Done: no variant rescues the strategy; stops made 2024 worse. |
| 08 | arXiv 2020-2026 strategy literature, ranked shortlist of 20 | Done 2026-09-21: no paper gives a cost-robust, out-of-sample, long-only stock edge. |
| 09 | Pre-registered SET test of 3 literature candidates | Run 2026-09-21: none adopted (LightGBM ranker, VP-MACD overlay, SMA200 filter all fail the discovery bar). |
| 10 | Trend filter (SMA200) drawdown check on untouched 2018-2019 window | Run 2026-09-21: neither the stock-level nor the index-level filter improved Sharpe; drawdown lower but return given up or unchanged. Closed. |
| 11 | Pre-committed review rule for the live paper track | APPROVED 2026-09-21; review script `scripts/live_track_review.py` written and self-tested on synthetic data only. First review due 2026-12-30 (futility), edge decision 2027-06-30. |

| 12 | Stub-row impact on Kronos input windows (2024 PIT, live) | TODO, read-only; step 1 of PLAN-next-research.md |
| 13 | Tested clean-data loader + `^SET.BK` repair retry | TODO, after 12 |
| 14 | Ticket 06 factor baselines on cleaned data | TODO, after 13; robustness of the existing family |
| 15 | LightGBM sign-flip diagnostic | TODO, optional, diagnostic only |
| 16 | Non-arXiv literature on SET / emerging-market strategies | TODO, optional |

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
