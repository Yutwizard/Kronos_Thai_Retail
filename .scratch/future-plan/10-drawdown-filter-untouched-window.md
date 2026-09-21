# Ticket 10: does a trend filter reduce drawdown on an untouched SET window? (DRAFT)

STATUS: RUN 2026-09-21 (Q31 approval). NEITHER variant passed; stopped per the pre-registered rule. Nothing below may be tuned after seeing a result. Origin: ticket 09 (SMA200 filter had -11.6% / -9.1% max drawdown vs -37.4% / -39.0% for equal-weight in 2023-26 / 2020-22, with no return gain) and ticket 08 addendum.

## Question
Does holding the equal-weight basket only in names above their 200-day average (V1), or only while `^SET.BK` is above its own 200-day average (V2), give a better risk-adjusted result than the equal-weight monthly basket, after 0.268% one-way friction, on data none of the earlier tests touched?

## Why an untouched window
The drawdown pattern was seen in 2020-2026, so re-testing there would be circular. Data starts 2016-09, so the only unused period is 2018-01-02 .. 2019-12-30 (489 trading days; 45-47 eligible names; eligibility needs 252 days, first reached 2017-09-27). Disclosure: before writing this design I looked at the SET index's max drawdown in that window (-15.8%) for context only; I did not compute any filter or basket result on it.

## Fixed design
- Universe, benchmark, timing, friction, eligibility, block bootstrap: exactly as ticket 09 / ticket 06 (equal-weight basket rebalanced monthly; signal at prior close; 0.268% one-way x turnover; 51 `thai_equity` tickers; `scripts/run_factor_baselines.py` helpers).
- V1: ticket 09's C3 unchanged (weight 1/N_eligible for each name whose prior close is above its 200-day SMA, rest cash, monthly rebalance).
- V2: hold the whole equal-weight basket when the prior `^SET.BK` close is above its 200-day SMA, else cash; state changes cost 0.268% x the whole book; state evaluated daily (dropping zero-volume index rows as before), position from next day's returns.
- No parameters other than 200 days; no other length is tested; no restart or stop rules.
- Primary metric (chosen because return already failed): paired stationary block bootstrap on the difference in Sharpe ratio, filter minus equal-weight (same block rule as ticket 06, 10,000 resamples, seed 42). One-sided p for difference > 0.
- Correction Family: V1 and V2, threshold p < 0.05/2 = 0.025 on the Sharpe difference.
- Secondary (reported, not a gate): max drawdown, CAGR, active return CI, per-year table.
- Pass rule for "trend filter improves risk-adjusted return on SET": Sharpe difference p < 0.025 AND max drawdown lower than equal-weight AND CAGR not more than 3 percentage points below equal-weight. A pass means "worth a live paper overlay track", not an edge, since 2018-2019 contains one mild drawdown (index -15.8%) and the test has low power.
- A fail or a mixed result is reported as is; no other window or filter length is then tried.
- Stated limits: 489 days, survivorship bias, one mild drawdown episode, 2 shots, the idea was inspired by earlier windows.

## Outputs after approval
- Extend `scripts/run_set_candidates.py` with a `--filters` mode (or add `scripts/run_trend_filter_check.py`), run once on `2018-01-02 2019-12-30`, log `data/logs/trend_filter_2018_2019.log`, append results here.

## Open before approval
1. Approve V1 + V2 as the family of 2, the untouched window, and the Sharpe-difference primary test.
2. Approve the pass rule (Sharpe p < 0.025, lower max drawdown, CAGR no more than 3 pp below).

## Results (run 2026-09-21, `scripts/run_trend_filter_check.py`, log `data/logs/trend_filter_2018_2019.log`)
Window 2018-01-02 .. 2019-12-30, 489 days, 45 eligible names at start and 47 at end. One run, parameters exactly as frozen.

| | CAGR | Sharpe | maxDD | Sharpe diff vs EW (95% CI) | one-sided p (need < 0.025) | maxDD lower | CAGR gap (limit -3.0 pp) | pass |
|---|---|---|---|---|---|---|---|---|
| equal-weight basket | -1.5% | -0.07 | -15.4% | | | | | |
| V1 stock SMA200 | -1.6% | -0.22 | -9.3% | -0.15 [-0.98, +0.67] | 0.634 | yes | -0.1 pp | NO |
| V2 index SMA200 | -5.1% | -0.81 | -13.1% | -0.74 [-2.21, +0.69] | 0.853 | yes | -3.5 pp | NO |

Secondary (active return vs equal-weight): V1 pooled -0.6% [-11.9%, +10.5%] (2018 +5.7%, 2019 -6.9%); V2 pooled -4.1% [-18.6%, +10.3%] (2018 +7.6%, 2019 -15.9%). V2 was invested 38% of the time with 15 state switches.

### Reading
- Both filters lowered maximum drawdown a little (V1 -9.3% vs -15.4%; V2 -13.1% vs -15.4%), the same direction as in 2020-2026, but the Sharpe ratio was not better for either and the Sharpe difference is far from significant (CIs span zero widely).
- V1 keeps its return (CAGR gap -0.1 pp) but its Sharpe is lower than equal-weight, so the smaller drawdown did not come with better risk-adjusted return here.
- V2 gave up 3.5 pp of CAGR and 0.74 Sharpe, missing the 2019 recovery while out of the market.
- The drawdown reduction is therefore consistent in sign across three windows (2018-19, 2020-22, 2023-26) but the improvement in risk-adjusted return is not supported. Any drawdown benefit is real only as an exposure reduction (holding less), not as evidence of skill; it costs return when markets recover.
- Per the pre-registered rule: no other window, filter length or variant is tried. Ticket closed.
- Limits as stated: 489 days, one mild drawdown episode (index -15.8%), survivorship bias, low power.
