# Ticket 19: are the live paper fills achievable, and how big is the dividend-adjustment bias? (DRAFT, needs approval)

STATUS: DRAFT 2026-09-23 (from the 2026-09-23 review, item R4, plus a bias found while scoping it). Nothing run. Approve Q1-Q4 before any download or computation.

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
