# Map: Regime-conditional alpha — revise or reconfirm?

## Destination

A locked **research decision** — revising or reconfirming CLAUDE.md's
"Alpha is regime-conditional... In bull regimes, reduce to BEAR allocation"
bullet — backed by a rigorous daily-level, regime-split significance test.
Ends in edits to CLAUDE.md and the downstream operator-guidance docs
(`operations-manual.md`, `user-manual.md`, `backtest-methodology.md`,
`PROJECT_STRUCTURE.md`). **No code changes** — confirmed by exploring the
repo that this guidance was never implemented as automated production logic
(see Notes).

## Notes

- **Confirmed fact:** no code detects "SET bull/bear regime" at all.
  `kth/trading/portfolio.py`'s `allocation_band` (BULL/NEUTRAL/BEAR/EXIT) is
  driven purely by the strategy's own trailing-60-day Sharpe on **live
  performance** — unrelated to SET direction. `_compute_market_state()`
  (Normal/Elevated/Turmoil) is a forecast-band-width volatility proxy — also
  unrelated. The "reduce to BEAR allocation in SET bull regimes" instruction
  exists only as **manual operator guidance** in the docs (e.g.
  `operations-manual.md`: *"In a strong SET bull market, use BEAR allocation
  (5%)..."*). This is why the destination is doc edits, not a code-change
  follow-up map — there's no trigger to touch.
- **Origin of this question:** `.scratch/optimize-entry-exit/` (closed map)
  fixed two backtest bugs — a duplicate-mark-day crash and a degenerate
  `equal_weight`/`60_40` benchmark — and re-ran the authoritative
  `thai_equity_<year>_n50` results (2023-2026). The corrected numbers show
  **positive alpha vs equal-weight in all four tested years**, including 2026
  (a genuine bull year, EW +60.8%, strategy +60.5pp ahead). The original
  claim was built on 2023 as the bull-market counter-example, but 2023 was
  actually a **down** year for EW (−5.7%) — that premise was factually
  wrong. Full numbers in `PROJECT_STRUCTURE.md`'s "4-Year OOS Results" and
  `data/backtest_results/MANIFEST.md`.
- Those four docs already carry "⚠️ premise under re-verification" callouts
  pointing at exactly this question — this map is what resolves them.
- **Locked test methodology:** regime signal = SET index (not the 51-ticker
  equal-weight universe — matches CLAUDE.md's own wording, "SET regimes"),
  trailing 60-trading-day return (bull if >0, bear if ≤0 — reuses the
  60-day/12-week trailing window convention `portfolio.py` already uses for
  its own Sharpe band). Test = paired stationary block bootstrap (same
  method as `scripts/analyze_cap60_significance.py`, which mirrors
  `compute_sharpe_ci`'s block-length heuristic in `kth/backtest/metrics.py`)
  on daily active return (strategy − equal-weight), split by regime, across
  all ~920 trading days from the 4-year re-run. No new backtesting needed —
  reuses `daily_returns.parquet`/`benchmark_equal_weight.parquet`/
  `benchmark_SET.parquet` already saved in
  `data/backtest_results/thai_equity_<year>_n50/`, plus raw SET history
  (`load_cached("^SET.BK")`) for pre-2023-01-01 lookback on the trailing
  window.
- **Locked decision rule:** confirm the claim only if the block-bootstrap CI
  on (bull-day active return − bear-day active return) is significantly
  negative — i.e. bull-days must show a *significantly lower* active return
  than bear-days, not just a lower point estimate. Otherwise reject.
- Skills to consult: `/grilling` for the decision ticket.

## Decisions so far

- [01 - Build and run the daily regime-split significance analysis](issues/01-build-and-run-regime-split-analysis.md) — Pooled across all 922 trading days (2023-2026), active return is significantly positive in both bull-days (+34.78% ann.) and bear-days (+33.36% ann.), essentially identical in magnitude. The bull-minus-bear difference (+1.42% ann., 95% CI [-34.31%, +37.53%]) is nowhere near significantly negative — under the locked decision rule, this is a clean rejection of the regime-conditional-alpha claim.
- [02 - Lock the regime-conditional-alpha decision](issues/02-lock-regime-conditional-decision.md) — **Rejected.** CLAUDE.md's bullet replaced with the retraction record; operations-manual.md's and morning-paper-trading-guide.md's live operator instructions (manually force BEAR allocation in a perceived SET bull market) removed and replaced with corrected guidance; PROJECT_STRUCTURE.md/user-manual.md/backtest-methodology.md's disproven narrative deleted outright (user's call — cleaner over preserved-as-history). Also fixed the same stale claim in README.md and AGENTS.md, found while closing out. `reports/master_backtest_report.html` (generated, hardcoded) left untouched, flagged separately. AGENTS.md's unrelated stale "min_holding_days experiments are invalid" line also spotted but explicitly not fixed — out of scope for this ticket.

**Destination reached** — both tickets resolved, no open tickets remain. This map is complete.

## Not yet specified

- If the claim is rejected, what (if anything) replaces it in CLAUDE.md —
  drop the regime-conditional framing and its BEAR-allocation guidance
  entirely, or keep a softer/different version? Depends on the analysis
  result; not sharp enough to ticket yet.
- Whether `_compute_market_state()`'s volatility bands or `portfolio.py`'s
  trailing-Sharpe allocation band should also be reconsidered given this
  investigation — out of scope unless the analysis specifically implicates
  them.
- Extending the analysis beyond 2023-2026 — risky given Kronos's ~Dec 2022
  pre-training cutoff (earlier years may be partially in-sample per
  CLAUDE.md); not pursued now.

## Out of scope

_(none identified yet)_
