# Ticket 09: SET pre-registration for 3 literature candidates

STATUS: RUN 2026-09-21 (Q28 approval). NO candidate adopted; see Results. Nothing below may be tuned after seeing any result. Source list: ticket 08. Template: ticket 06.

## Question
Do any of three literature-derived, long-only, daily-OHLCV rules beat the equal-weight monthly-rebalanced basket on SET after 0.268% one-way friction, in a discovery window and again in an untouched holdout window?

## Fixed design (shared)
- Universe: the 51 `thai_equity` tickers in `data/raw/`, adjusted closes; eligible = at least 252 days of history and a price at the signal date. Known bias: current constituents only (survivorship) flatters every arm; stated, not corrected.
- Benchmark: equal-weight of every eligible ticker, rebalanced monthly, same cost model (ticket 06).
- Timing: signal at close of day d-1, held from day d returns; cost 0.268% one-way x turnover (`FRICTION`) on rebalance day; weights drift between rebalances.
- Windows: discovery 2023-01-02 to 2026-07-25; holdout 2020-01-02 to 2022-12-30. Both used once per candidate. Caveat: ticket 06 already used both windows for its own three rules; the equal-weight benchmark has been seen there, these three candidates have not.
- Test: paired stationary block bootstrap on daily active return (`kth.backtest.metrics.evaluate_variant_vs_baseline` plus a one-sided bootstrap p), as in ticket 06.
- Correction Family: these 3 candidates, threshold p < 0.05/3 = 0.0167. Ticket 06's momentum result is not re-counted as a pass.
- Adoption bar (all required): pooled 95% CI lower bound > 0 in discovery; one-sided p < 0.0167; no year with a statistically clean loss; AND the same rule clears p < 0.05 with a positive point estimate on the holdout window. Passing means "enter the live paper track", not "has an edge".
- Stated limits: 3.6-year discovery window, survivorship bias, 3 shots, ~2-13x optimistic costs in the source papers (ours are the SET rate, so this arm is not optimistic).

## Candidate 1: monthly LightGBM long-leg ranker (from arXiv 2603.13252)
- Features (OHLCV only): 1m, 3m, 12m momentum; 20d and 60d realised volatility; 20d average daily volume proxy; cross-sectional rank of each on the date.
- Label: 20-trading-day forward return minus the universe equal-weight forward return (paper: excess vs QQQ, 20/60/90-day horizons; we use only 20d).
- Training: expanding window, retrained monthly, 90-trading-day embargo between label maturity and prediction (paper's protocol).
- Hyperparameters FROZEN 2026-09-21: the paper does NOT state the base ranker's objective, n_estimators or other settings, or its cross-sectional normalisation (it gives only a secondary error-predictor: n_estimators=50, max_depth=3, num_leaves=8, min_child_samples=50, learning_rate=0.05, 80% row/column subsampling). Its repository link is truncated in the paper and the repo could not be found. So, as a stand-in decision by us and not the paper's: `lightgbm.LGBMRegressor` with exactly the paper's secondary-model settings above, random_state=0, no tuning, no early stopping; features cross-sectionally rank-transformed per date to [0,1]. This is a documented deviation from the source; the result tests our version, not the paper's.
- Portfolio: long-only, top 10 by predicted score, equal weight, monthly rebalance on first trading day.
- Note: the paper's result is long-short and degraded in its 2024 holdout; we test only the long leg.

## Candidate 2: index-timing overlay (from arXiv 2604.26063)
- FROZEN 2026-09-21 by user decision (b): VP-MACD with OUR chosen windows and lambda, fixed before any run. This is NOT the paper's exact method: the paper (arXiv 2604.26063) does not state the summation or STD window lengths, chose lambda in-sample per index (SPY 0.88, QQQ 0.98, DIA 0.86, no fixed rule) and has no code. Result tests our version.
- Definition (daily bars of `^SET.BK` from `data/raw/_SET.BK.parquet`):
  - sigma_t = rolling 20-day STD of (High - Low), divided by Close_t.
  - r_t = |Close_t - Open_t| / (High_t - Low_t); if High_t == Low_t, r_t = 0.
  - P*_t = sum over the trailing 20 days of (Close_i x Volume_i x sigma_i x r_i) / sum over the same 20 days of Volume_i.
  - VP-MACD_t = EMA_12(P*) - EMA_26(P*); Signal_t = EMA_9(VP-MACD). Standard (12, 26, 9) spans, standard EMA (adjust=False).
  - Buy when VP-MACD_{t-1} <= lambda x Signal_{t-1} and VP-MACD_t > lambda x Signal_t; sell when VP-MACD_{t-1} >= Signal_{t-1} and VP-MACD_t < Signal_t (as published; sell has no lambda). State is long from a buy until a sell, flat otherwise.
  - lambda = 0.90 fixed (mean of the paper's three tuned values 0.907, rounded to the paper's 0.02 grid). No tuning. Descriptive-only sensitivity over the paper's grid [0.80, 1.00] may be reported after the main test; it is NOT used for the adoption decision.
- Execution: signal at close of day t, position from day t+1 returns (trade at t close), same convention as ticket 06. Deviation: the paper trades at the next open; the equal-weight basket is close-to-close.
- Data rules: rows with Volume == 0 are dropped from the index series (this removes the final 2026-09-15 stub row, which follows a two-month gap after 2026-07-17); the index window therefore ends 2026-07-17, so discovery window end for this candidate is 2026-07-17 (candidates 1 and 3 keep the stock-data end from ticket 06 unless it is earlier). Sum of Volume over a window cannot be 0 after dropping zero-volume rows.
- Portfolio: hold the equal-weight monthly-rebalanced basket when long, 0% cash when flat; switching cost = 0.268% one-way on the whole book at each state change.
- Comparator: the equal-weight basket itself (buy-and-hold). Answers a timing question, not selection; not comparable to candidates 1 and 3.
- Previously proposed (not chosen): plain MACD(12, 26, 9).

## Candidate 3: stock-level SMA trend filter (baseline from arXiv 2603.14453; cf. 2607.20093, 2607.01550)
- Signal: hold a ticker only when its close is above its 200-day simple moving average; equal weight among holders, remainder in cash; monthly rebalance.
- Only one parameter (200d), fixed here; no other length is tested.
- Comparator: equal-weight basket.

## Outputs (to be produced only after approval)
- `scripts/run_set_candidates.py`, log `data/logs/set_candidates_*.log`, results section appended below in this file, with the per-year table exactly as in ticket 06.

## Status (2026-09-21)
1. Three candidates and the window split: approved by the user.
2. Full-text details frozen: candidate 1 (stand-in hyperparameters, deviation noted) and candidate 2 (our own windows and lambda, deviation noted). Candidate 3 has no open parameters.
3. Not yet done: a final go-ahead to write `scripts/run_set_candidates.py`. Nothing has been coded or run.

## Implementation notes frozen BEFORE the first run (2026-09-21, after Q28 approval)
Details the design left implicit, fixed now so none can be chosen after seeing a result.
- Runner: `scripts/run_set_candidates.py [START END]`; reuses `simulate`/`stats`/`one_sided_p` from `scripts/run_factor_baselines.py` (same friction 0.268%, same block bootstrap, same seed 42, N_BOOT 10000, family threshold 0.05/3). Run once per window: discovery `2023-01-02 2026-07-25`, holdout `2020-01-02 2022-12-30`.
- Candidate 1 features (all from close/volume, per ticker): mom_1m = close/close.shift(21)-1; mom_3m = shift(63); mom_12m = shift(252); vol_20d and vol_60d = rolling std of daily returns; adv_20d = log of the 20-day mean of (close x volume). Each feature is rank-transformed to [0,1] across eligible tickers on each date (6 features; "rank of each" in the design). Label = close[t+20]/close[t]-1 minus the eligible-universe mean of the same quantity at t. Training rows: dates s with s+20 <= (signal date - 90) in trading-day positions; eligible tickers with no missing feature/label; minimum 250 training dates or the month is skipped (equal-weight basket held). Retrain on the first trading day of each month using the previous close as signal date; score = model prediction; top 10, equal weight.
- Candidate 1 LightGBM: `LGBMRegressor(n_estimators=50, max_depth=3, num_leaves=8, min_child_samples=50, learning_rate=0.05, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=0, verbosity=-1)`. subsample_freq=1 added because LightGBM ignores `subsample` without it (paper says "80% of rows and columns").
- Candidate 2 overlay arithmetic: state from the VP-MACD series (index rows with Volume==0 dropped, forward-filled onto the stock calendar), state at close t applies to day t+1. Day return = state x (basket gross return - basket rebalance cost) - 0.268% x |state change|; flat = 0% cash. Initial state carries no entry cost. Candidate 2 is evaluated on days <= 2026-07-17 only in the discovery window, against the benchmark on the same days.
- Candidate 3 reading of "equal weight among holders, remainder in cash": each eligible ticker whose prior close is above its 200-day SMA gets weight 1/N_eligible, the rest of the book is cash (i.e. the equal-weight basket with non-trending names replaced by cash). 200-day SMA needs no extra history beyond the 252-day eligibility rule. Monthly rebalance on the first trading day, cost on turnover.
- Reporting: for each candidate and window, the same table as ticket 06 (CAGR, Sharpe, maxDD, turnover/yr, pooled active with 95% CI, one-sided p, per-year active with CI, clean-loss years). The two-window adoption rule from "Adoption bar" is applied by hand after both runs.

## Results (run 2026-09-21, `scripts/run_set_candidates.py`, logs `data/logs/set_candidates_discovery.log` and `set_candidates_holdout.log`)
One run per window, parameters exactly as frozen above; no re-runs, no tuning.

### Discovery 2023-01-02 .. 2026-07-25 (868 days; candidate 2: 863 days to 2026-07-17)
Equal-weight basket: CAGR +0.6%, Sharpe 0.12, maxDD -37.4%, 1.0x/yr turnover.

| candidate | CAGR | Sharpe | maxDD | turnover/yr | pooled active (95% CI) | one-sided p (need < 0.0167) | clean-loss years | adopt |
|---|---|---|---|---|---|---|---|---|
| C1 LightGBM top-10 monthly | -12.2% | -0.49 | -59.2% | 11.3x | -12.6% [-23.4%, -1.4%] | 0.987 | none | NO |
| C2 VP-MACD overlay | +4.8% | 0.41 | -26.7% | switches 34, 60% exposure | +3.5% [-4.9%, +12.8%] | 0.211 | 2026 | NO |
| C3 SMA200 filter | +2.3% | 0.33 | -11.6% | 2.4x | +0.7% [-12.4%, +13.1%] | 0.449 | 2026 | NO |

Per-year active return: C1 -11.4% / -9.6% / -15.5% / -14.7% (2023-26); C2 -6.0% / +16.3% / +7.9% / -10.2%; C3 +2.3% / +5.5% / +7.0% / -21.5%.

### Holdout 2020-01-02 .. 2022-12-30 (725 days, descriptive only: discovery already failed)
Equal-weight basket: CAGR +13.8%, Sharpe 0.71, maxDD -39.0%, 1.1x/yr turnover.

| candidate | CAGR | Sharpe | maxDD | pooled active (95% CI) | one-sided p (need < 0.05) | clean-loss years |
|---|---|---|---|---|---|---|
| C1 | +23.8% | 0.99 | -38.5% | +9.0% [-5.6%, +24.3%] | 0.117 | none |
| C2 | -0.6% | 0.06 | -39.0% | -14.1% [-27.3%, -2.6%] | 0.993 | 2022 |
| C3 | +7.7% | 0.88 | -9.1% | -7.5% [-30.5%, +16.1%] | 0.753 | 2021 |

### Verdict against the pre-registered rule
No candidate meets the discovery bar (pooled CI lower bound > 0 and p < 0.0167 and no clean-loss year), so none reaches the second-window confirmation and none enters the live paper track.
- C1: the sign flips between windows (-12.6% pooled active in discovery with a 95% CI entirely below zero, +9.0% in the holdout with a CI spanning zero). That is noise or regime dependence, not an edge. The frozen stand-in for the paper's model may also differ from the paper's real ranker.
- C2: +3.5% in discovery is not significant and turns to -14.1% (clean-loss 2022) in the holdout.
- C3: active return is about zero in discovery and negative in the holdout, so it adds no return. Descriptive observation, not a pre-registered claim: it cut max drawdown a lot in both windows (-11.6% and -9.1% vs -37.4% and -39.0%) because it sits in cash when most names are below their 200-day average. That is a risk-reduction pattern to consider separately, not a strategy edge, and it was not tested as one.

### Caveats
- Survivorship bias, 3.6-year discovery window, 3 shots, as stated up front.
- C1 and C2 test our versions of the papers' ideas (see deviations above), not the papers' exact methods.
- lightgbm was installed into `venv/` for this run and is not in requirements-ml.txt.
- The index cache ends with a zero-volume stub row on 2026-09-15 after a gap since 2026-07-17; it was dropped by rule (see Data rules).

## Data-quality audit and robustness check (2026-09-21, user Q32 "a and b")
The primary results above are unchanged. This section records what the audit found and how much it matters.

### Findings
- 76 stock-days have |return| > 15%. Most are genuine: market-wide crash days (2020-03-09, 2020-03-12), the 2020-11-10 vaccine rally, and DELTA's very volatile Dec-2020 rally.
- CONFIRMED corporate-action breaks: TRUE.BK 2023-03-03 (+68.6%, price frozen at 4.873 with zero volume 2023-02-20..03-02 during the DTAC merger, then resumed as the new TRUE at ~8.2 with 785M volume; new TRUE first traded 2023-03-03 per news) and SCB.BK 2022-04-27 (SCB X share swap; the series has only 1,074 rows, starts 2022-04-20, and is not eligible until 2023, so it did not touch any window). TRUE's break is inside the 2023-2026 discovery window.
- Halt resumptions after flat zero-volume stubs: IVL 2024-09-05, BANPU 2026-08-05 (after the discovery window), BTS 2024-06-04 (-22.7%, 84x volume, possibly ex-rights, unverified), JMART 2024-08-05.
- SYSTEMIC: on 57 calendar dates (49 in 2024 from 2024-03-12, 1 in 2025, 7 in 2026) at least 25 of the 51 stocks carry a flat zero-volume stub row. 50 of those 57 dates exist in the `^SET.BK` file, so they are real trading days with no usable prices for those stocks; the stale price is carried into the next real day. Total returns are unaffected but daily returns are lumped, daily variance is distorted, and the volume feature of candidate 1 is corrupted on those days. `scripts/check_data_sanity.py` does not detect this pattern.
- SIRI 2021-05-17/18 has zero volume with moving prices (a volume gap, not a price break).

### Robustness re-run (NOT the pre-registered result; log `data/logs/set_candidates_robustness_cleaned.log`)
Cleaned data: the 57 stub calendar dates dropped, TRUE.BK earlier prices rescaled so the 2023-03-03 return is 0. Annualised figures shift slightly because the day count changes; compare verdicts, not decimals.
| candidate | window | pooled active, primary | pooled active, cleaned (95% CI) | one-sided p, cleaned | adopt |
|---|---|---|---|---|---|
| C1 LightGBM | discovery | -12.6% (CI below 0) | -4.2% [-15.5%, +7.2%] | 0.767 | NO |
| C1 LightGBM | holdout | +9.0% (p 0.117) | +12.3% [-2.0%, +27.3%] | 0.049 | n/a (discovery fails) |
| C2 VP-MACD | discovery | +3.5% | +3.8% [-5.4%, +13.6%] | 0.213 | NO |
| C2 VP-MACD | holdout | -14.1% | -14.1% | 0.993 | NO |
| C3 SMA200 | discovery | +0.7% | +0.9% [-13.2%, +14.4%] | 0.439 | NO |
| C3 SMA200 | holdout | -7.5% | -7.5% | 0.753 | NO |
Conclusion: no candidate is adopted under either data version. The one change that matters is C1: its discovery loss was partly a data artifact (the CI no longer excludes zero), and its holdout number moved by 3.3 points from rescaling a single ticker's history (the rank-transformed dollar-volume feature responds to the price scale). That shows C1's results are fragile and neither the -12.6% nor the +9.0% should be read as evidence. The 2018-2019 check (ticket 10) is unaffected: no TRUE break and almost no stub dates fall in that window.

### `^SET.BK` gap repair (attempted, not completed)
- A fresh yfinance request for `^SET.BK` (10y, 1y, max, start/end, via both `yf.download` and `Ticker.history`) returned a single row dated 2026-09-21 with zero volume, the same thin-stub behaviour as the BANPU incident. The downloader's row-count guard would refuse to overwrite the cache with it and the cache was not touched.
- The scratch download was written only to the session scratchpad. An alternative source (stooq) is behind a JavaScript bot check and was not bypassed.
- The cache keeps its last real row at 2026-07-17 and a zero-volume stub at 2026-09-15. Options: wait for Yahoo to recover and re-run `download_universe` for that ticker, or load the index history from SET's own data files by hand. Until then any index-based rule (candidate 2) can only be evaluated to 2026-07-17.
