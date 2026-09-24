# Ticket 19: are the live paper fills achievable, and how big is the dividend-adjustment bias?

STATUS: APPROVED 2026-09-24 (user "agree" to Q1-Q4 as recommended). Running first.

## Facts (read from code, 2026-09-23)
- Paper fills are typed in by hand in the dashboard (`/api/trades`, `fill_price`) and logged by `kth/trading/portfolio.py` `_log_trade` with `date.today()`: the log date is the day of entry, not necessarily the day the order would have filled.
- The ticket proposes buy limits at `close x (1 + exp_ret/2)` (`kth/trading/trade_gen.py`), above the close for a positive signal, so buy limits are usually easy to hit at the next open.
- Logged prices are nominal SET prices. `data/raw` is dividend-adjusted (`auto_adjust=True`). Example: CPF.BK bought at 19.0 on 2026-06-04; `data/raw` shows that day's range as about 18.64-18.74 (adjusted).
- `scripts/live_track_review.py` values the book as cash + shares x adjusted close, and the benchmark is adjusted throughout. So every holding bought before a later ex-dividend date starts with an artificial loss of about the dividends paid afterwards: a bias against the live book (ticket 11 addendum A4).

## Questions
1. **Fill realism:** was each logged fill price reachable in the session the order would have filled in?
2. **Bias size:** in THB and as a share of the book, how large is the nominal-versus-adjusted mismatch at each trade date?

## Why this is allowed
Ticket 11 allows data-input checks before the review. This ticket computes no live return, benchmark or IC; it looks only at each trade's price against that ticker's own price range and adjustment factor.

## Fixed design
- Trades: every row of `trade_log.csv` in the 2026-09-23 snapshot (46 rows then); later rows are audited at the review.
- Unadjusted prices: download daily OHLC with `yfinance` `auto_adjust=False` (gives raw Close and Adj Close) for the traded tickers, 2026-06-01 to the download date, into `data/audit/unadjusted/` (never `data/raw`). Needs network. The download date is recorded.
- Q1 classes per trade, using unadjusted high/low with a tolerance of one SET tick or 0.1%, whichever is larger:
  - A: price within the range of the first session after the forecast date (the session the ticket was written for);
  - B: not A, but within the range of the log-date session;
  - C: outside both;
  - D: no unadjusted data.
  Report counts and THB value by class and by thai_equity vs DR.
- Q2 per trade: adjustment factor F = Adj Close / Close on the trade date from the same download; bias per trade = shares x price x (1 - F). Report the total, the distribution, and the total as a share of 500,000 THB.
- Proposed fix (applied only if the user approves after seeing the bias SIZE, which is not a performance number): in `live_values`, value each lot as shares / F_trade x adjusted close (equivalent to total-return accounting with dividends reinvested, which matches the adjusted benchmark). Implemented with a self-test and before 2026-12-30, so it cannot be chosen after seeing a review result.

## Decision rule (fixed now)
- If class C is at least 10% of trades or of traded value: report it at the reviews as "fills partly not achievable". The ticket-11 decision rule is unchanged, and the result goes into every review's process log.
- If the total bias is at least 0.25% of initial capital: apply the proposed fix (after Q3 approval). Below that: record it and leave the implementation unchanged.

## Output
`scripts/audit_live_fills.py` (network for the download only), log `data/logs/live_fill_audit.log`, results appended here.

## Questions (recommended answers first)
- Q1: Download unadjusted prices into `data/audit/unadjusted/` (network, never `data/raw`)? **Recommended: yes.**
- Q2: Classes A-D with a tolerance of one tick or 0.1%? **Recommended: yes.**
- Q3: Pre-approve the total-return fix, applied only if the bias is at least 0.25% of capital? **Recommended: yes.**
- Q4: Do this ticket before ticket 18 (it is quicker and affects the 2026-12-30 review)? **Recommended: yes.**

## Implementation notes frozen BEFORE the run (2026-09-24; nothing computed yet)
Facts found while wiring the script (read from metadata only, no prices compared):
- The pipeline ran at two times of day. Until late June it ran in the morning of D (`generated_at` 06:28-10:34, `lookback_end` = D-1), so the ticket was for session D. From July it ran in the evening of D (19:37-22:05, `lookback_end` = D), so the ticket was for session D+1. Trades are logged dated D in both cases (`date.today()` at entry).
- Rows 10-11 (2026-06-25, BANPU.BK and BTS.BK) have a log date one day BEFORE their `forecast_date` (2026-06-26). Reported as an anomaly; classified like any other row.

Clarified definitions (these replace the wording above where they differ):
- **Intended session** = the first session of that ticker strictly after the forecast's `lookback_end` (from `<forecast_date>/<ticker>_meta.json` in the 2026-09-23 snapshot; if missing, the first session after `forecast_date`). This covers both regimes: morning runs give D, evening runs give D+1.
- Class A = price within the intended session's unadjusted [low, high] +/- tolerance; B = not A but within the log-date session's range; C = neither; D = no unadjusted data for either session.
- Extra flag, reported per class: **logged before its intended session** (log date < intended session date). The price then could not have been observed in the session that fills it.
- Tolerance = max(one SET tick, 0.1% of price). SET tick table: < 2: 0.01; 2-5: 0.02; 5-10: 0.05; 10-25: 0.10; 25-100: 0.25; 100-200: 0.50; 200-400: 1.00; >= 400: 2.00 (DRs use the same table).
- Q2 factor F = Adj Close / Close on the **log date** (the date the review applies the trade). If the log date is not a session, use the last session on or before it.
- Bias: net = sum over buys of shares x price x (1 - F) minus the same sum over exits (economically: dividends the adjusted marks assume but the logged cash never received). Gross buy-side also reported. **The 0.25% rule uses |net|.**
- Cross-check: yfinance `dividends` for each traded ticker, 2026-06-01 to the download date, listed next to F. A ticker with F < 1 but no listed dividend, or the reverse, is reported.
- Not decided here (reported only): the review applies each trade on its log date, which from July is one session before it could fill. Any change to that is a separate user decision, before 2026-12-30.

## Result (run 2026-09-24, `scripts/audit_live_fills.py`, log `data/logs/live_fill_audit.log`)
Snapshot 2026-09-23T222128 (46 trades); unadjusted prices for the 17 traded tickers downloaded 2026-09-24 into `data/audit/unadjusted/` (git-ignored). The first run printed the full table and then crashed while printing the summary (tuple keys in JSON). It was rerun on the same files after fixing the summary formatting and narrowing the dividend cross-check to dividends after each ticker's first trade. No definition or threshold was changed.

### Q1 fill realism
| class | trades | value (THB) |
|---|---|---|
| A: within the intended session's range | 38 | 872,264 |
| B: only within the log-date session's range | 5 | 113,580 |
| C: within neither | 3 | 31,965 |
| D: no data | 0 | 0 |
- By kind: thai_equity 32 A / 2 B / 3 C; DR 6 A / 3 B / 0 C.
- Class C: rows 10 (BANPU.BK buy 5.25, 2026-06-25), 22 (IVL.BK exit 22.70, 2026-07-03), 24 (BANPU.BK exit 5.60, 2026-07-06).
- **17 of 46 trades were logged before their intended session**: every evening-run trade from 2026-07-02 on, plus the two 2026-06-25 rows logged a day before their forecast date. Their prices could not have been observed when they were entered. Most still fall inside the next session's range (class A), but that is luck or a limit price, not a recorded fill. The 5 class-B trades (TRUE.BK 07-02, HORIZON23.BK 07-16, KUAISH80.BK 07-21, SINGTEL80.BK 07-30, BTS.BK 06-04) match only the log-date session, i.e. a price from the session before the one that would have filled them.
- **Verdict by the frozen rule:** class C is 6.5% of trades and 3.1% of value, both under 10%, so fills are NOT flagged "partly not achievable". The logged-before-session count is reported in the process log from now on.

### Q2 dividend-adjustment bias
- Net bias +632 THB = **0.126% of capital** (gross on buys only: 3,481 THB = 0.70%; most of it reverses on exit because most positions were closed).
- **Verdict by the frozen rule:** |net| < 0.25%, so the total-return fix is NOT applied; the review implementation is unchanged.
- Cross-check: Yahoo lists dividends after the first trade for 12 of 17 tickers, consistent with F < 1. One mismatch: BANPU.BK lists a 0.40 dividend on 2026-09-11 but F = 1.0 on its trade dates (Yahoo did not adjust; BANPU has a data gap 2026-08-11..09-18). BANPU was bought and sold before 2026-09-11, so it does not affect the net figure.

### Limits
- F is measured against the 2026-09-24 download. Dividends paid after that date on positions still held, or on later trades, add to the bias, so the measured figure is a lower bound for the review date.
- Tolerance and tick table as frozen; no sensitivity analysis was run.

## Open, for the user (recommended answers first)
- Q5: Rerun this audit on the review snapshot before each ticket-11 review, and apply the approved total-return fix then if |net| has reached 0.25%? The bias size is not a performance number, so this cannot be tuned on a result. **Recommended: yes.**
- Q6: Make the review apply each trade on its intended session (first session after `lookback_end`) instead of the log date? From July, the log date is one session early. Decide before 2026-12-30. **Recommended: yes.**
- Q7 (process, from today): enter fills after the session they filled in, at the real price, so the logged date is the fill date. Optionally, the dashboard could record a `fill_date` separate from the entry date. **Recommended: yes to the routine; the `fill_date` field as a small separate change.**

## CORRECTION (2026-09-24, same day): the "17 logged before their session" figure is withdrawn
While scoping Q7 I found that `kth/trading/portfolio.py` `_log_trade` writes `forecast_date = date.today()`, so the log's `forecast_date` is the entry date, not the forecast a trade came from. The first run used it to find `lookback_end`. A trade entered on the morning of D from the D-1 evening ticket was therefore wrongly anchored to the D forecast and flagged as "logged before its session".

Corrected source rule (fixed before the rerun, self-tested): the source is trade ticket D if `trade_ticket_<D>.json` lists the ticker under the matching action (buy -> `buys`; exit -> `exits`/`reduces`). A ticket regenerated after the trade cannot list a trade that is already done, so a match means ticket D came first. Otherwise the source is the latest earlier ticket that lists it that way. No match = off-ticket trade: the log-date session is taken as intended, and "logged before" is unknown. Thresholds, tolerance and the bias definition are unchanged. Log: `data/logs/live_fill_audit_corrected.log`.

| | first run | corrected |
|---|---|---|
| class A / B / C / D | 38 / 5 / 3 / 0 | 39 / 4 / 3 / 0 |
| class C share of trades / value | 6.5% / 3.1% | 6.5% / 3.1% (same three rows) |
| logged before intended session | 17 | **2** (BTS.BK exit 2026-07-14, IVL.BK exit 2026-09-02) |
| off-ticket trades | not measured | 11 (the four 2026-06-04 buys, PSH.BK 06-30, PTTEP.BK 07-02, both HORIZON23.BK buys, SINGTEL80.BK 07-20, 07-30 and 08-18) |
| net dividend bias | 0.126% of capital | unchanged |

- Weak source matches, reported and not reclassified: BTS.BK buys 2026-07-01 matched to the 2026-06-24 ticket, KUAISH80.BK 2026-08-03 to 2026-07-20, TRUE.BK 2026-09-10 to 2026-09-02. These are more than three sessions apart and may really be off-ticket.
- Verdicts by the frozen rule are unchanged: fills NOT flagged; total-return fix NOT applied.
- Most trades were entered during or after the session they filled in, not before it. The real process gaps are: `forecast_date` in the log is wrong, 11 trades have no source ticket, and 2 were entered before their session.

## User decisions (2026-09-24, "agree" to Q5-Q7)
- Q5: this audit is rerun on the review snapshot before each ticket-11 review; the approved total-return fix is applied if |net| >= 0.25% of capital at that time.
- Q6: the review applies each trade on its intended session (first session after the source forecast's `lookback_end`; off-ticket trades on the log date), using the source rule above.
- Q7: fills are entered after the session they filled in, at the real price. The dashboard records a separate `fill_date` and the real source `forecast_date`.
