# Future plan (from the 2026-09-17/18 graphify audit)

Not yet filed as GitHub issues: `gh` is not installed here. File each with
`gh issue create` once available (see `docs/agents/issue-tracker.md`, labels
per `docs/agents/triage-labels.md`), then delete this folder.

| # | Ticket | Type | GPU | Depends on |
|---|--------|------|-----|------------|
| 00 | **Historical forecast cache is not point-in-time (look-ahead)** — found 2026-09-18; code fix done 2026-09-19, quantify + re-run + re-evaluate still open, blocks 03 | bug + re-validation | yes, to re-validate | none |
| 01 | HTML doc renders drifted from Markdown (user + operations manual) | docs/tooling | no | none (item 6 done; item 7 added) |
| 02 | One Correction Family for significance wording | docs | no | none (done except optional pooled test) |
| 03 | Volatility-regime entry threshold experiment | research | no (optional top-up) | 02 for doc edits |
| 04 | Verify Kronos pre-training cutoff | research | no | none |
| 05 | Forecast Cache backup policy | decision | no | none |

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
