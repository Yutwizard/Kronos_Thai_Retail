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

## Still to do (not blocking)
- Write `scripts/live_track_review.py` implementing items 2 and 4 (rebuild the daily live value from `trade_log.csv` and `data/raw`, the benchmark, the block bootstrap, the rank IC). It must not be run against the evaluation window before the review dates except to test on synthetic data.
