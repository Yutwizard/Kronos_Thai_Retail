# Ticket 08: arXiv 2020-2026 strategy literature, shortlist of 20 (+5 reserves) for SET

Run 2026-09-21, second pass same day after the user's "focus on global markets, then test on Thai stocks" direction. Nothing here is backtested. Companion: `09-set-candidate-preregistration.md` (DRAFT, not approved, nothing run).

NOTE 2026-09-21: full-text pass changed ranks 2, 8, 9, 10, 12 and 18; see 'Addendum 2' at the end. The tables above are left as first written.

## Settled design (grilling rounds 1-5)
- Purpose: find a REPLACEMENT strategy family (Kronos has no valid edge, ticket 00). Ranking = global rigor + how easily the rule re-runs on SET data. "Thai fit" is no longer a scoring criterion (no paper tests SET).
- Families: classical price factors, technical rules, ML/DL (supervised, RL, foundation models). Foundation models capped at ~3 of 20. Soft floor of 2 per family.
- Reference-only, not in the 20: news/sentiment/LLM-text, intraday, Markowitz optimisation (ADR-0003), execution, anything needing fundamentals.
- Hard filters: long-only, daily OHLCV. RELAXED: long-short admitted as a research-only exception, tagged with short-leg feasibility, ranked below long-only. Product scope unchanged (TFEX still excluded in PROJECT_STRUCTURE.md, README.md:34, kth/data/universe.py:18). Backtests are long-only only; the short leg is not tested.
- Up to ~5 of the 20 are "evidence, not a candidate".
- Rubric: point-in-time rigor first, code release a bonus, no peer-review requirement. No cost model or no OOS split = "weak evidence", never outranks rigorous.
- Rebalance frequency and turnover tagged, scored neutrally. CONTEXT.md untouched.
- Only up to 3 candidates go to a SET backtest, as one Correction Family (p < 0.05/3 = 0.0167). Adoption needs a second untouched window. "Real use" = live paper track (about 6 months vs equal-weight), a real-money decision is separate and outside this project.
- Verification: every paper below was opened on arxiv.org. "abs" = abstract page only (costs/protocol often "not stated"); "html" = full text. Search-engine summaries were treated as leads only: one was wrong (2107.13148 was summarised as Chinese A-share, the page says US 2011-2019).

## Short-leg feasibility (facts, 2026-09-21)
- TFEX single-stock futures: 124 underlyings, cash-settled, 1,000 shares/contract. 48 of our 51 thai_equity tickers covered; not covered: DOHOME, JMART, CPNREIT. Source is a broker page mirroring the TFEX list, NOT the TFEX PDF; confirm before relying.
- SET50 index futures and sector index futures exist (index hedge only).
- SET cash short selling: SET100 only, zero-plus-tick rule; temporary ban April 2025 (news reports, not checked against SET rules).
- Cost caveat: our FRICTION is 0.268% one-way. Papers assume 2-20 bps, so reported net numbers are optimistic by roughly 1.3x-13x on costs before borrow, margin or roll.

## Ranked shortlist (20)
Region US unless stated; no paper tests Thai stocks. SSF = short leg via TFEX single-stock futures. Cache = computable from data/raw daily OHLCV.

### A. Strategy candidates (12)
| # | arXiv | Family | Shape / freq | Costs, OOS | Region | Verified | Cache | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 2603.13252 When Alpha Breaks | ML (LightGBM ranker + gate) | L/S top10/bottom10, monthly, SSF | 10 bps/rebal; 109-fold expanding walk-forward, 90-day embargo, 2024 holdout | ~84 US AI stocks | html | partial | Best rigor. Ungated Sharpe 2.73 falls to 1.91 in 2024, RankIC 0.072 to 0.010; gate recovers little. Benchmark QQQ; long leg not reported alone. Features are OHLCV (1/3/12m momentum, 20/60d vol, volume). |
| 2 | 2512.12924 Hypothesis-driven walk-forward | Technical/RL | daily | costs modelled; 34 rolling windows | 100 US stocks 2015-24 | abs | yes | Honest null: 0.55% ann., Sharpe 0.33, p=0.34. Open code. Long-only not stated. |
| 3 | 2604.26063 Volume-price-adjusted MACD | Technical | long-only, daily, index | 8 bps round trip; train 2018-22 / test 2023-26 | SPY/QQQ/DIA | html | yes | Index timing (usable on ^SET.BK). Single split, tuned sensitivity parameter, benchmark is plain MACD not buy-and-hold. |
| 4 | 2603.14453 E-TRENDS | Technical/ML (SMA + LSTM) | position capped at +/-1, daily | 2 bps round trip; chronological 70/15/15, test 2019-25 | top-30 S&P 500, 2005-25 | html | yes | Daily OHLCV; SMA baseline P&L -2.15 vs +0.28 with LSTM, Sharpe 0.85 to 1.10, 70% of tickers improved. Costs very low, single split. Colab notebook released. |
| 5 | 2510.14156 Loss functions for stock ranking | ML (Transformer) | long-only top-5 equal-weight, daily | NO costs; single 70/15/15 split | 110 S&P stocks 2015-24 | html | partial | Same shape as our harness. Best Sharpe 0.75, 16.2% ann. Weak evidence. |
| 6 | 2302.10175 Spatio-temporal momentum | Momentum/ML | L/S [-1,1], daily, SSF | 0-10 bps; expanding window | 46 US financials + 12 index futures | html | partial | Sharpe 2.61 but costs only to 10 bps. Code not stated. |
| 7 | 2606.09420 Benchmarking deep TS models | ML (15 models) | L/S decile, daily, SSF | 10/20/50 bps; walk-forward, block bootstrap | US CRSP | html | partial | Rigorous and negative: all constrained net Sharpes negative at 20 bps; deep does not beat ridge. Also evidence. |
| 8 | 2409.00416 Betting against (bad) beta | Low-vol/beta | L/S factor | says costs critical; OOS not stated | not stated | abs | partial | Only low-vol-family paper. Betas vs ^SET.BK computable. Weak. |
| 9 | 2302.13245 Physical momentum, India | Momentum/reversal | portfolios by time scale | costs, OOS not stated | India NSE 500 2014-21 (EM) | abs | unknown | Only EM momentum paper; headline 16x is implausible without costs. PDF did not parse. Weak. |
| 10 | 2112.04755 High-dim portfolio DRL | RL | 48 setups, 10-500 stocks | costs varied; OOS across setups | US | abs | partial | Large claimed outperformance; long-only, code not stated. |
| 11 | 2605.27848 HMM + RL regime allocation | Regime/RL | 3 ETFs, daily | costs not stated; 30% OOS, 1-day lag | US ETFs | abs | partial | Asset allocation, not stock selection. Weak. |
| 12 | 2411.13555 DL in long-short allocation | ML | L/S daily, SSF | costs not stated; 2-year test | S&P 500/NASDAQ | abs | partial | Weak. |

### B. Evidence, not candidates (5)
| # | arXiv | What it shows | Verified |
|---|---|---|---|
| 13 | 2607.20093 Retail Trader's Ruin | Long-only, 10 bps, hierarchical BY-FDR. Golden/death cross, RSI/MACD/Bollinger, candlesticks, OBV, Sell-in-May: 0 supported, 4 refuted; trend and 12-1 momentum inconclusive. Code promised. | html |
| 14 | 2607.06502 What Useful Alphas? | ~200 published long-short anomalies: 48 bp/month pre-2006 to 7 bp/month post-2005 non-micro; modest costs remove it. | abs |
| 15 | 2105.01380 Why and how systematic strategies decay | Newly published factors lose ~5 ppt more Sharpe per year; publication year explains 30% of decay variance. | abs |
| 16 | 2609.12227 Seasonal trading in commodity futures | Only seasonality paper with costs (8.6 bps one-way), 10-year rolling estimation, 2016-24 OOS, equal-weight benchmark: none of 18 paired MEB Sharpe tests rejects after Holm. Commodities, not equities. Code public. | html |
| 17 | 2607.01550 Is trend still your friend? | ~100 futures 1995-2025: short-term trend (5-50d) Sharpe collapsed from ~0.8 to ~0 post-2008 on small-tick contracts, held at 1.0-1.2 on large-tick; driver is volatility-normalised tick size. Futures, long/short. Relevant because SET tick sizes are coarse for low-priced stocks. | html |

### C. Foundation-model evidence (3)
| # | arXiv | What it shows | Verified |
|---|---|---|---|
| 18 | 2511.18578 Re(Visiting) TSFMs in Finance | Zero-shot and fine-tuned generic TSFMs underperform strong baselines on daily excess returns; from-scratch finance pre-training helps. Full text not read. | abs |
| 19 | 2606.27100 Pretrained TSFMs for return forecasting | 5 US stocks; gains over random walk "small and sparse", significant in 2 cases. Forecast accuracy only. | abs |
| 20 | 2508.02739 Kronos | Pre-trained on 12B K-lines, 45 exchanges; SET not named. RankIC +93% vs best TSFM. No backtest with costs stated. | abs |

## Reserves (5, all verified)
1. 2603.20319 Implementation risk in backtesting: same strategy diverges up to 3.71% across five engines under costs; relevant if re-implementing.
2. 2407.13685 Beyond trend following: risk-on/risk-off ML on S&P/NASDAQ/bonds; costs not stated.
3. 2002.06975 Cross-sectional DL, Japan: inputs, costs, OOS not stated; may need fundamentals.
4. 2506.06356 DL multi-day turnover, China A-share: needs open-signal, liquidity, market-cap inputs; no costs or benchmark.
5. 2003.08302 Low-vol anomaly / adaptive multi-factor model: theory, no tradable rule.
Unverified leads (not opened, do not cite): 2412.12516, 2306.13661, 2605.17307, 2606.08930, 2603.15848 (PDF did not parse).

## Excluded (verified, reference only)
- 2408.07497 quantile NN, 23 developed markets: 194 features incl. 153 fundamental anomalies, long-short only, costs not stated.
- 2608.26106 SPY directional benchmark: uses day-t open, so not implementable at prior close; backtest is "execution-illustrative".
- 2107.13148 ML classifiers: US 2011-2019, portfolio, costs, OOS split not stated.
- 2603.07692 long-only minimum variance: theory only.
- 2609.13125, 2602.10785, 2507.07107 (Markowitz, ADR-0003), 2512.16251 (analyst data), 2106.08420 (futures), 2606.08791 (theory), 2512.11913 (withdrawn), 2101.01006 (theory), 1706.02985 (2017), LLM-text/sentiment papers.

## Gaps against the agreed rules
- No paper tests SET or any Thai stock. EM evidence: India (weak), China (reserve, weak).
- Family floors: seasonality 1 (evidence only, commodities), reversal 0 dedicated, low-vol 1 (weak), momentum 2 (moderate/weak).
- Long-only + costs + OOS + multi-year: only #3 (index timing, single split). #5 is long-only with no costs; #4 has costs of 2 bps.
- 6 of 12 strategy papers are abstract-only. Reading their full text is the next step if any of them is picked.

## Bottom line
No paper shows a positive, cost-robust, out-of-sample, long-only stock strategy strong enough to replace Kronos on SET. The most rigorous ones report failure or decay (#1, #7, #13, #14, #16). Use the list as a source of pre-registered candidates, not as evidence of an edge. Proposed three for SET (see ticket 09 draft): (1) #1's OHLCV features as a monthly LightGBM long-leg ranker, (2) #3's rule as an index-timing overlay on ^SET.BK, (3) stock-level SMA trend filter (#4's baseline, cf. #13, #17).

## Addendum 2026-09-21: drawdown-control / volatility-management search (user Q30 "c")
Prompted by the SMA200-filter observation in ticket 09 (SMA200 filter cut max drawdown, no return gain). Opened on arxiv.org; NOT added to the ranked 20 (different question: risk reduction, not return).
| arXiv | What it shows | Verified | Fit |
|---|---|---|---|
| 2603.15848 Algorithmic trading strategy development and optimisation | S&P 500 2000-2024, long-only, weekly. MA200 regime filter: dev-period drawdown -57.4% to -23.1%, Sharpe 1.19 to 1.69. Baseline is "50-day MA + FinBERT", NOT buy-and-hold; costs not stated; ATR stop effect not isolated; validation/test 2018-24 numbers not read. Student-team paper, no code stated. | html | Weak, but the direction matches our own SMA200 observation. |
| 2212.07288 Smoothed stochastic volatility-managed portfolios (v2 Aug 2026) | 158 equity-factor portfolios; vol-managed is modest and uneven; smoothed volatility targeting is positive net of costs where a plain realised-volatility rule is not. Abstract only; specific figures not read. | abs | Factor portfolios, not long-only stock baskets; no clean transfer. |
| 2603.01298 Single-asset adaptive leveraged volatility control | IVV + 44 ETFs, tuned 2000-09, tested 2010-24, 5 bps. Sharpe 0.42 vs 0.33 open-loop, max DD 37.1% vs 38.6% (tiny drawdown effect); leverage cap 1.5; turnover 800-1800%/yr. | html | Not implementable at SET's 26.8 bps friction. |
| 2303.02613 Drawdown control with restart | ETFs and crypto, costs considered, OOS period and benchmark not stated. | abs | Weak. |
Reading: the literature offers only weak, cost-light support for MA200-style regime filters and modest, uneven support for volatility management. Nothing here beats a plain buy-and-hold on a cost-robust, out-of-sample, long-only basis. The search-engine claim "vol-managed beat unmanaged in only 6% of 158 strategies" was not confirmed on the page and is not cited.

## Addendum 2 2026-09-21: full-text pass on abstract-only papers (user Q32 "c")
Opened on arxiv.org (html) unless noted. Supersedes the table rows for these papers.
| Rank | arXiv | Full-text facts | Change |
|---|---|---|---|
| 2 | 2512.12924 | Confirmed long-only. Five volume/price patterns, 30-day cap, stop-loss; 5 bps slippage + $1 commission; walk-forward 252-day train / 63-day test / 63-day step, 34 folds 2015-24; benchmark SPY. Net Sharpe 0.33, +0.55%/yr, p=0.34, power about 12%; low-vol regime 2015-19 Sharpe -0.21, high-vol 2020-24 +1.01. Code: github.com/akashdeepo/Interpretable-Hypothesis-Driven-Trading. | Upgraded to full text; still an honest null. |
| 8 | 2409.00416 Betting against (bad) beta | US CRSP monthly 1963-2021, 3x3 beta / cash-flow-beta double sort, monthly, costs from effective-spread estimates, but needs CAPE and book-to-market state variables (fundamentals); market-neutral long-short; net Sharpe 1.09 vs 1.01; no OOS protocol. | REMOVED from the 20 (fundamentals input, long-short factor). Low-vol family now has no compliant paper. |
| 9 | 2302.13245 Physical momentum, India | NSE 500 2014-21, long-short dollar-neutral (top and bottom of 50 groups), momentum = sum of (mass x log-return) with turnover/volatility as mass, daily to yearly lookbacks; "commissions are not considered"; IN-SAMPLE (same period for construction and test); benchmark NIFTY 50; the 16-fold profit is the daily-reversal variant. | Kept only as a low-ranked EM reference; evidence value nil (in-sample, no costs). |
| 10 | 2112.04755 High-dim DRL | 500 US stocks 2010-2021, long-only, daily reallocation; costs 1/5/10 bps; train 2010-18, validation 2019, test 2020-01 to 2021-06 (1.5 years); mean test return 144.7% / 95.8% / 75.7% at 1/5/10 bps vs buy-and-hold 66.6%; beats benchmarks in 36 of 48 setups. | Upgraded: long-only, costs, OOS. But the test is 1.5 years including the 2020 crash and rebound, costs stop at 10 bps against SET's 26.8, code not stated. |
| 11 | 2605.27848 HMM+RL | html returned 404; not read. | Unchanged (abstract only). |
| 12 | 2411.13555 DL long-short | 20 randomly selected US stocks, 2-year test 2022-2024, daily long-short on next-day prediction, "transaction costs are negligible", no benchmark; Sharpe 0.8-2.3. | REMOVED from the 20 (costs ignored, tiny universe, no benchmark). |
| 18 | 2511.18578 Re(Visiting) TSFMs in Finance | 94 countries, ~10,000 US securities, daily excess returns 1990-2023, OOS 2001-2023, long-short top/bottom decile daily; main results ignore transaction costs. US Sharpe (gross, 512-day window): CatBoost 6.79, Chronos zero-shot ~2.9, TimesFM zero-shot ~0.2, scratch-trained Chronos 5.42 and TimesFM 3.66; R2OOS is negative for all. Long leg beats short leg. Finance-pre-trained models on Hugging Face (FinText). | Upgraded: zero-shot generic TSFMs are far below gradient-boosting baselines; gross Sharpes of that size cannot survive daily costs and are not usable as evidence of edge. |

### Revised composition of the 20
- Out: 2409.00416, 2411.13555.
- In (from reserves and the drawdown addendum, both already verified): 2603.15848 (MA200 regime filter, S&P 500, long-only, weekly, costs not stated) and 2407.13685 (ML risk-on/risk-off, costs not stated). Both are weak evidence.
- Family floors now: momentum 2 (one in-sample), low-vol 0 compliant, reversal 0, seasonality 1 (evidence only). Nothing changes the bottom line: no paper shows a cost-robust, out-of-sample, long-only stock edge.
