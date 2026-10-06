# Ticket 11: pre-committed review rule for the live paper track (DRAFT)

STATUS: APPROVED 2026-09-21 (user: "agree" to the four recommendations). Nothing below may change after any live result is compared with the benchmark. Written blind to the benchmark comparison; I have seen the raw recorded equity values (500,000 at start, peak 516,529 on 2026-08-03, 483,691 on 2026-09-10) but computed no benchmark or active return.

## Why this rule exists
Every historical backtest was invalid (ticket 00) and three literature candidates plus stop/entry variants failed on clean windows (tickets 06, 09, 10). The live paper track (first trades 2026-06-04, 500,000 THB, `data/positions/`) is the only clean forward test. The README says to review it "after ~6 months against equal-weight"; this ticket fixes how, before results can bias it.

## Facts about the track (checked 2026-09-21)
- State: `data/positions/paper_portfolio.json` (mode paper, initial_capital 500,000, cash + positions incl. DR tickers such as HORIZON23.BK, HERMES80.BK), trades in `data/positions/trade_log.csv` (46 rows, columns include ticker, action, shares, price, friction_cost, forecast_date), daily tickets `trade_ticket_<date>.json`.
- The recorded `equity_curve` is NOT a usable daily series: 47 points over 23 distinct dates, 15 dates with 2-4 different values, long gaps (2026-08-03 to 08-18 to 09-02), and it ends 2026-09-10. So the review must rebuild daily value itself (below).
- Point-in-time boundary: forecast folders from 2026-06-29 have `lookback_end == folder date` (ticket 00). Trades from 2026-06-04 to 2026-06-26 used earlier folders.

## Fixed design
1. Evaluation window: starts at the 2026-06-26 close (last trading day before the first point-in-time folder) and runs to the review date. Both the live book and the benchmark start with the same value at that close.
2. Daily live value: rebuilt as cash + shares x close from `trade_log.csv` (all trades, fills at logged price, logged friction_cost deducted) and `data/raw` closes (thai_equity and DR tickers). The stored `equity_curve` is not used. Dates on which at least half of the tickers are flat zero-volume stubs (`scripts/check_data_sanity.py`) are dropped from both series.
3. Benchmark (approved): equal-weight, rebalanced on the first trading day of each month, same 0.268% one-way friction (DRs inherit it), over the live tradable universe = the 51 `thai_equity` tickers plus the 36 verified DR tickers, both lists frozen below. Eligibility at each rebalance: the ticker has a real, non-stub price at the prior close (volume > 0 and not a flat zero-volume stub row). No minimum history; the 252-day rule of tickets 06/09 is not used because it existed for signal lookbacks and 15 of the 36 DRs have fewer than 252 cached rows (two of them, HORIZON23.BK and KUAISH80.BK, are held in the live book). A ticker that is not eligible at a rebalance is simply left out of that month. Secondary reference only: `^SET.BK` (cache gap and stub, see ticket 09) and the equal-weight of the 51 `thai_equity` tickers alone.
4. Statistics: paired stationary block bootstrap on daily active return (live minus benchmark), same block rule and 10,000 resamples as ticket 06 (`evaluate_variant_vs_baseline` plus one-sided bootstrap p). Secondary signal-quality metric: mean daily cross-sectional rank IC between the logged expected return and the realised 20-trading-day return, for forecast dates whose 20 days have elapsed, with a block-bootstrap 95% CI.
5. Process log to be reported with the review, not used to adjust results: number of trading days with no ticket or a failed run, manual skips/overrides, trades not followed. Missing days are reported as missing, not filled.

## Decision rule
Six-month review (SET close 2026-12-30). Purpose: futility only.
- Power warning: about 125 daily observations. If tracking error is 15-25% a year, the standard error of annualised active return is about 21-35%, so a real edge of +10% a year cannot be detected. A positive six-month result therefore proves nothing.
- FUTILE: pooled active-return 95% CI entirely below 0 AND rank-IC 95% CI entirely below 0. Consequence recommended to the user: stop presenting BUY/SELL tiers as advice; keep forecasts as monitoring only. The decision itself stays with the user.
- Otherwise INCONCLUSIVE: continue to twelve months, no edge claim in any document.
- No edge is declared at six months whatever the sign.

Twelve-month review (SET close 2027-06-30). Purpose: the only edge decision.
- EDGE CANDIDATE only if all hold: pooled active-return 95% CI lower bound > 0; one-sided p < 0.05; active return positive in each six-month half; mean rank IC with 95% CI lower bound > 0.
- If met, the result is "worth a small real-capital discussion", never automatic. Paper fills are assumed at limit or market prices and are optimistic, so the discussion must first compare logged prices with achievable SET prices.
- If not met, the project stays a forecasting/monitoring tool, as CLAUDE.md already states.

## Not decided here
- Any real-money decision, or its size. Separate, explicit, and after the twelve-month review.
- Any change to the trading rules during the window. If the live rules change, the window restarts and the change is logged.

## Decisions (2026-09-21, all four recommendations accepted)
1. Window start: 2026-06-26 close (the point-in-time boundary). Trades on 2026-06-04 to 2026-06-26 are inside the live book's starting state, not part of the evaluated returns.
2. Benchmark universe: `thai_equity` + verified DRs, price-only eligibility (item 3 above).
3. Two-stage review: futility only at 2026-12-30, the only edge decision at 2027-06-30.
4. A FUTILE outcome is a recommendation to the user, never an automatic product change.

## Frozen ticker lists (as of 2026-09-21)
- thai_equity (51): ADVANC.BK, AOT.BK, AP.BK, BANPU.BK, BBL.BK, BCH.BK, BCP.BK, BDMS.BK, BEM.BK, BGRIM.BK, BH.BK, BTS.BK, CENTEL.BK, CHG.BK, CPALL.BK, CPF.BK, CPN.BK, CPNREIT.BK, CRC.BK, DELTA.BK, DOHOME.BK, ERW.BK, GLOBAL.BK, GPSC.BK, GULF.BK, HANA.BK, HMPRO.BK, ICHI.BK, IRPC.BK, IVL.BK, JMART.BK, KBANK.BK, KKP.BK, KTB.BK, LH.BK, MEGA.BK, MINT.BK, ORI.BK, OSP.BK, PSH.BK, PTT.BK, PTTEP.BK, QH.BK, RATCH.BK, SCB.BK, SCC.BK, SIRI.BK, TCAP.BK, TISCO.BK, TOP.BK, TRUE.BK
- verified DR (36): ASML01.BK, BABA80.BK, BIDU80.BK, BYDCOM80.BK, CATL80.BK, CMBANK23.BK, FERRARI80.BK, GEELY80.BK, HERMES80.BK, HORIZON23.BK, JD80.BK, KEYENCE23.BK, KINGSOFT23.BK, KUAISH80.BK, LOREAL80.BK, LVMH01.BK, MEITUAN80.BK, NETEASE80.BK, NONGFU80.BK, NOVOB80.BK, PETROCN80.BK, POPMART80.BK, SANOFI80.BK, SANRIO23.BK, SENSE23.BK, SINGTEL80.BK, SOFTBANK23.BK, SONY80.BK, SUSHI23.BK, TEL23.BK, TENCENT80.BK, TOYOTA80.BK, UBTECH23.BK, UNIQLO80.BK, XIAOMI80.BK, ZIJIN80.BK
- Any ticker added to or removed from the live pipeline later is NOT added to or removed from the benchmark; changes are logged in the process log.

## Implementation (2026-09-21): `scripts/live_track_review.py`
Written and tested on synthetic data only. It has NOT read the real live track, benchmark or forecast results; the only real-data invocations so far were guard refusals that exit before any file is opened.
- Guard: real-data mode needs `--review six-month|twelve-month` and refuses when the as-of date is before 2026-12-30 / 2027-06-30. `--selftest` (hand-computed cases: live value with friction, benchmark first-day cost, price-only eligibility, stub-date drop, decision rules, guard, rank IC of 1.0 for a perfect forecast and about 0 for noise) and `--synthetic` (end-to-end on generated data) never touch real data.
- Details the ticket left implicit, fixed before any real run:
  - Live value = cash + shares x close, rebuilt from `trade_log.csv`; buys deduct `shares x price + friction_cost`, exits add `shares x price - friction_cost`; trades dated on or before 2026-06-26 set the starting state from the 500,000 THB initial capital; later trades apply on their date (or the next calendar date); selling more than held is an error.
  - Benchmark: the first day after the window start counts as a rebalance (costs 0.268% x turnover), then the first trading day of each month.
  - Rank IC universe: the frozen thai_equity tickers only. DR forecasts are made on the foreign underlying, whose realised return is in another currency and calendar, so DRs are excluded from the IC (they stay in the return comparison). Expected return = p50 at horizon step 20 divided by the close at the forecast's `lookback_end`, minus 1; realised return = the close 20 trading days later divided by the same base, minus 1; per-date Spearman correlation with at least 10 names; only forecast dates whose 20 days have elapsed by the review date; block-bootstrap 95% CI of the mean IC (10,000 resamples, seed 42, not annualised).
  - Halves for the twelve-month rule: H1 = returns up to 2026-12-30, H2 = after; "positive in each half" uses the annualised mean active return of each half.
  - Stub calendar dates (at least half of the tickers flat with zero volume) are dropped from both the live and benchmark series; the process log reports how many.
  - Process log reported with every review: trading days in the window, dropped stub dates, trading days with no `trade_ticket_<date>.json`, number of trades in the log, forecast dates used for the IC. It is not used to adjust any result.
- Known limitation: paper fills are taken at the logged prices, which may be optimistic (see the twelve-month decision rule).
- Frozen ticker lists are hard-coded in the script and match the lists above.

## Addendum A (written 2026-09-23, BEFORE any live-vs-benchmark comparison) -- APPROVED 2026-09-24 (user "agree" to QA1-QA3 as recommended)
Nothing above is changed. This adds what the rule left open. Written blind: no benchmark, active return or live IC has been computed.

### A1. Honest power at twelve months (the original power warning covered six months only)
- Active return: about 250 daily observations. With tracking error 15-25% a year, the standard error of the annualised mean active return is about 15-25%, so the 95% CI half-width is about 30-50%. The EDGE CANDIDATE rule (CI lower bound > 0) is met only by a true edge of roughly +30% a year or more. A realistic +5-10% edge will almost always come out NO EDGE.
- Rank IC: forecasts overlap on a 20-day horizon, so 250 dates carry about 12 independent observations. With a per-date IC spread of 0.15-0.20 the standard error of the mean IC is about 0.04-0.06, so the IC CI excludes 0 only if the true IC is about 0.10 or more. Useful stock-selection ICs are usually 0.02-0.05.
- Therefore a NO EDGE verdict at twelve months means "not shown", not "shown absent". No document may describe it as evidence that no edge exists.

### A2. Continuation after the twelve-month review (new, pre-committed)
- If the twelve-month verdict is NO EDGE and the result is not clearly negative (clearly negative = both the pooled active-return CI and the rank-IC CI entirely below 0, the FUTILE definition), the track continues unchanged to a **24-month review at the SET close of 2028-06-30**, evaluated over the whole window from 2026-06-26.
- If the twelve-month verdict is EDGE CANDIDATE, the paper track also continues to 24 months (a real-money discussion may run in parallel, per the original rule).
- If clearly negative at twelve months: stop the edge question; the recommendation (user decides) is monitoring-only use, as in the six-month FUTILE rule.
- 24-month EDGE CANDIDATE: the same four conditions as twelve months, except one-sided p < 0.025 (a second look at the same question; the twelve-month look keeps its frozen 0.05, so the combined false-positive rate is at most about 0.075, stated openly), and "positive in each half" becomes "positive in each of the two twelve-month halves".
- Expected power at 24 months is still low (standard error about 11-18% a year; IC standard error about 0.03-0.04). There is no further extension after 24 months: the result then stands as final.
- Any change to the live trading rules still restarts the window (original rule).

### A3. Data the reviews must read (ticket 05)
- Every review runs on a frozen snapshot, taken after the review date's pipeline run: `python scripts/live_track_review.py --review <name> --root ~/backups/kronos-th-snapshots/<snapshot>`. The script checks the snapshot's hashes and refuses on a mismatch. The snapshot name is reported with the result.
- The process log now also reports the stub share of the live input windows (ticket 12, reporting only).

### A4. Known accounting bias to be settled before 2026-12-30 (ticket 19)
Fills are logged at nominal SET prices, but the review values holdings with dividend-adjusted closes (`auto_adjust=True`), while the benchmark is adjusted throughout. Each holding bought before a later ex-dividend date therefore starts with an artificial loss of about the dividends paid afterwards, which biases the comparison against the live book. Ticket 19 measures the size from data inputs only (no performance is computed) and proposes one fix, to be approved before the six-month review. Applying that fix is a correction to the implementation, not to the decision rule.

### Questions (recommended answers first)
- QA1: Approve A2's 24-month continuation with p < 0.025 at 24 months? **Recommended: yes.**
- QA2: Continue the paper track to 24 months even after an EDGE CANDIDATE at twelve months? **Recommended: yes.**
- QA3: Require every review to run on a hash-checked snapshot (A3)? **Recommended: yes.**

## Addendum B (2026-09-24, from ticket 19; written before any live-vs-benchmark comparison) -- APPROVED 2026-09-24 (user "agree" to ticket 19 Q5-Q7)
Implementation corrections only; the decision rule and the frozen lists are unchanged.
1. **Review procedure.** On the review date, after that day's pipeline run: (a) take a snapshot; (b) `python scripts/audit_live_fills.py --download` then `python scripts/audit_live_fills.py --snapshot <snapshot>`, which writes `data/audit/fill_factors_<snapshot>.json`; (c) `python scripts/live_track_review.py --review <name> --root <snapshot> --fill-factors data/audit/fill_factors_<snapshot>.json`. The review refuses a factor file made for a different snapshot.
2. **Dividend adjustment (Q5).** If that audit's |net bias| >= 0.25% of capital, the review values holdings in total-return terms (effective shares = shares / F at the trade date; exits add the dividends earned while held). Otherwise the valuation is unchanged. The audit reports only the bias size, never a performance number.
3. **Trade timing (Q6).** Each trade applies on the later of its intended session (first priced session after its source forecast's `lookback_end`, source ticket rule of ticket 19) and its log date: never before the order could fill, never before it was recorded. A recorded `fill_date` (from 2026-09-24) is used as is. On the 2026-09-23 snapshot this moves 2 of 46 trades one session later and none earlier (checked by share-count replay only, no prices valued). Disclosure: the approved wording was "apply on the intended session"; taking the later of the two was added the same day, before any review, because 14 trades from older tickets would otherwise have been applied before they were entered.
4. The process log reports `trades_applied_after_log_date` and whether the total-return factors were used.

## Process log entry (2026-10-06): runtime environment change, not a rule change
The system upgrade switched `/usr/bin/python3` from 3.12 to 3.14, which broke the venv. The venv was rebuilt on Python 3.14.4 with the same package versions, except torch 2.5.1+cu121 -> 2.14.1+cu126 (no 3.14 build of 2.5.1; the GTX 1060 runs via sm_60 compatibility). All verify suites and self-tests pass. A same-input forecast check (PTT.BK, KBANK.BK, CPALL.BK, data to 2026-09-25, n_samples 50) gave new-venv 20-day p50 inside the spread of two old-venv runs (forecasting is unseeded, so runs differ anyway): PTT -19.5% / -18.6% old vs -19.0% new; KBANK -24.8% / -24.5% vs -23.6%; CPALL -3.2% / -2.7% vs -2.8%. Model, weights, settings and trading rules are unchanged, so the review window does NOT restart. Forecast folders from 2026-10-07 on are produced with the new environment; the old venv is kept as `venv-py312/` for rollback.
