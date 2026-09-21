# Ticket 11: pre-committed review rule for the live paper track (DRAFT)

STATUS: DRAFT 2026-09-21, NOT approved. Nothing below may change after any live result is compared with the benchmark. Written blind to the benchmark comparison; I have seen the raw recorded equity values (500,000 at start, peak 516,529 on 2026-08-03, 483,691 on 2026-09-10) but computed no benchmark or active return.

## Why this rule exists
Every historical backtest was invalid (ticket 00) and three literature candidates plus stop/entry variants failed on clean windows (tickets 06, 09, 10). The live paper track (first trades 2026-06-04, 500,000 THB, `data/positions/`) is the only clean forward test. The README says to review it "after ~6 months against equal-weight"; this ticket fixes how, before results can bias it.

## Facts about the track (checked 2026-09-21)
- State: `data/positions/paper_portfolio.json` (mode paper, initial_capital 500,000, cash + positions incl. DR tickers such as HORIZON23.BK, HERMES80.BK), trades in `data/positions/trade_log.csv` (46 rows, columns include ticker, action, shares, price, friction_cost, forecast_date), daily tickets `trade_ticket_<date>.json`.
- The recorded `equity_curve` is NOT a usable daily series: 47 points over 23 distinct dates, 15 dates with 2-4 different values, long gaps (2026-08-03 to 08-18 to 09-02), and it ends 2026-09-10. So the review must rebuild daily value itself (below).
- Point-in-time boundary: forecast folders from 2026-06-29 have `lookback_end == folder date` (ticket 00). Trades from 2026-06-04 to 2026-06-26 used earlier folders.

## Fixed design
1. Evaluation window: starts at the 2026-06-26 close (last trading day before the first point-in-time folder) and runs to the review date. Both the live book and the benchmark start with the same value at that close.
2. Daily live value: rebuilt as cash + shares x close from `trade_log.csv` (all trades, fills at logged price, logged friction_cost deducted) and `data/raw` closes (thai_equity and DR tickers). The stored `equity_curve` is not used. Dates on which at least half of the tickers are flat zero-volume stubs (`scripts/check_data_sanity.py`) are dropped from both series.
3. Benchmark: equal-weight, monthly rebalanced, same 0.268% one-way friction, over the live tradable universe = the thai_equity tickers plus the verified DR tickers, list fixed at approval (open, see below). Secondary reference only: `^SET.BK` (its cache has a gap and stub, see ticket 09), and the equal-weight of the 51 thai_equity tickers alone.
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

## Open before approval
1. Start of the window: 2026-06-26 close (recommended, the point-in-time boundary) or the first trade on 2026-06-04 (longer sample but earlier folders are not certified point-in-time).
2. Benchmark universe: thai_equity + verified DR list (recommended, matches what the pipeline can buy) or thai_equity only. Fix the DR list at approval.
3. Two-stage review (six-month futility only, twelve-month edge decision), as drafted, or a single review at six months.
4. Whether a FUTILE outcome should trigger any product change automatically. Drafted as a recommendation only.
