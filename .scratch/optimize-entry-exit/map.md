# Map: Optimize entry and exit

## Destination

A locked **research decision** — added to CLAUDE.md's "Research decisions that
constrain code" section, in the same style as the existing equal-weight-sizing
and zero-shot entries — on whether to adopt a `max_holding_days` + cooldown
time-based exit cap on top of the existing hysteresis logic
(`kth/backtest/strategy.py::apply_hysteresis`). Backed by a per-year
2023-2026 backtest sweep. An implementation spec for whichever verdict is
reached (wiring the winning config into the production default path) is
deliberately **out of scope** for this map — a future map picks that up.

## Notes

- Domain: Kronos-TH walk-forward backtest strategy layer. Entry/exit signal
  logic lives in `kth/backtest/strategy.py` (`compute_signals`,
  `apply_hysteresis`); the simulation loop is `kth/backtest/walkforward.py`.
- Standing constraints from CLAUDE.md (do not relitigate without a fresh GPU
  re-run): equal-weight position sizing is locked, `thai_equity` stays
  zero-shot, alpha is regime-conditional (crushes flat/down SET, underperforms
  in bull markets — 2024 was the only year clearing p<0.05), and there's a
  bootstrap-p-value distinction (live dashboard `/api/risk` uses centered
  resampling; historical backtest p-values are t-test, stored in
  `data/backtest_results/`, never changed).
- **Technical fact confirmed by exploring this repo (2026-07-26):**
  `data/forecast_cache/NeoQuasar_Kronos-small/` already holds real cached
  Kronos forecasts spanning 2020-01-01 → 2026-07-25. A GPU is present on this
  machine (`nvidia-smi` works) but the bare `python3` has no `torch` — use the
  project venv / `requirements-ml.txt`. This means the sweep in this map is a
  pure strategy-layer backtest re-run over already-cached forecasts; **no new
  Kronos inference is needed** to resolve this map's destination.
- `data/backtest_results/MANIFEST.md` flags all currently-stored per-year
  results as stale pending a GPU re-run of the 2026-06-21 bug fixes (equity
  curve alignment, PSR formula, open_trades blending) — but those fixes are
  already merged into the current `kth/backtest/walkforward.py` /
  `kth/backtest/metrics.py`. Any fresh run through today's code (baseline
  included) is automatically non-stale; don't cite the old stored numbers as
  the baseline comparison point.
- Skills to consult: `/grilling` for the decision ticket. No special skill
  needed for the task ticket (plain implementation + backtest execution).

## Decisions so far

- [01 - Build and run the max-holding-days + cooldown sweep](issues/01-build-and-run-max-holding-sweep.md) — Implemented the experimental `max_holding_days`/`cooldown_days` params (disabled by default, production path unchanged) and ran 20 fresh backtests (baseline + 4 caps × 2023-2026). Also found and fixed a pre-existing bug (duplicate final mark-day) that was crashing *every* backtest run, likely the actual blocker behind the outstanding GPU re-run in `data/backtest_results/MANIFEST.md`. Results: friction is equal-or-higher for every capped config in every year; in 2024 (the flagship p<0.05 year) every cap weakens PSR/Sharpe/p-value vs baseline; cap60 clearly wins in 2023 but that's a documented weak-edge year. Full table + interpretation deferred to Ticket 02.
- [02 - Lock the max-holding-days research decision](issues/02-lock-max-holding-decision.md) — Initially **adopted** `max_holding_days=60`/`cooldown_days=5` off annual point-estimates (required relaxing the map's own locked decision rule to do so). **Revised to REJECT** after a follow-up paired block-bootstrap on daily active returns (`scripts/analyze_cap60_significance.py`) showed 2024's degradation is statistically clean (not noise) while 2023's apparent win is only marginal — pooled across 2023-2026 the effect is statistically indistinguishable from zero. CLAUDE.md's entry updated in place to reflect the rejection.

**Destination reached** — both tickets resolved, no open tickets remain. This map is complete. Final verdict: reject the max-holding-days mechanism as tested.

## Not yet specified

Both items below survive this map's closure and carry forward into the
future implementation-spec map (wiring `max_holding_days=60`/`cooldown_days=5`
into the production `BacktestConfig` defaults) rather than being resolved
here — this map's destination was the adopt/reject decision only:

- Interaction between forced cooldown-driven exits and the sector-concentration
  guard / `max_positions=5` slot limits — does freeing a slot via a forced
  exit meaningfully change which tickers get selected in the same period?
- Whether `cooldown_days=5` (fixed for this sweep, matching the existing
  `min_holding_days`) is actually optimal, or whether a finer cooldown sweep
  is warranted, now that `max_holding_days=60` itself is locked.

## Out of scope

- **Price-based stop-loss / take-profit** (ATR-based trailing stop, fixed %
  stop-loss, fixed % take-profit) — deliberately excluded from this map. The
  motivating problem this map addresses is the *unbounded* holding period
  (`min_holding_days` is only a floor, no ceiling exists), not the lack of a
  price-based exit. Revisit as a separate future map if ever pursued.
