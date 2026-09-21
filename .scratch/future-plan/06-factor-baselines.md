# Ticket 06: Do simple price factors beat equal-weight buy-and-hold? (pre-registered)

Written 2026-09-21 BEFORE any result was computed. Motivation: the Kronos strategy has no
valid evidence of beating buy-and-hold (ticket 00). CPU-only, price data only.

## Fixed design (no tuning after seeing results)
- Universe: the 51 `thai_equity` tickers in `data/raw/`, adjusted closes. Known bias: current
  constituents only (survivorship), which flatters every arm.
- Benchmark: equal-weight of every eligible ticker, rebalanced monthly (same cost model).
- Strategies (3, each top 10 of eligible, equal weight, monthly rebalance, first trading day):
  A momentum 12-1 (close[t-21]/close[t-252]-1, high = buy);
  B low volatility (60-day daily-return std, low = buy);
  C 1-month reversal (close[t]/close[t-21]-1, low = buy).
- Eligible: has >= 252 days history and a price at the signal date.
- Timing: signal at close of day d-1, weights held from day d returns onward (trade at d-1 close);
  cost = 0.268% one-way (`FRICTION`) x turnover, paid on the rebalance day. Weights drift between rebalances.
- Period: 2023-01-02 .. 2026-07-25, one continuous series, reported by year.
- Test: paired stationary block bootstrap on daily active return (strategy - benchmark),
  `kth.backtest.metrics.evaluate_variant_vs_baseline` plus a one-sided bootstrap p.
- Correction family: 3 tests, so a strategy is "adopted" only if pooled 95% CI lower bound > 0,
  one-sided p < 0.05/3 = 0.0167, and no year has a statistically clean loss.
- Stated limits: 3.6 years, survivorship bias, 3 shots. A pass is a lead to confirm, not proof.

## Result
Run 2026-09-21 (`scripts/run_factor_baselines.py`, log `data/logs/factor_baselines.log`), 868 days, 51 tickers:

| | CAGR | Sharpe | maxDD | turnover/yr | pooled active (95% CI) | one-sided p | adopt |
|---|---|---|---|---|---|---|---|
| equal-weight | +0.6% | 0.12 | -37.4% | 1x | | | |
| momentum 12-1 | +14.4% | 0.94 | -22.2% | 5.9x | +12.8% [+1.3%, +24.9%] | 0.0144 | YES (marginal, needs < 0.0167) |
| low vol 60d | +6.8% | 0.60 | -23.3% | 6.1x | +5.4% [-4.8%, +15.6%] | 0.142 | no |
| reversal 1m | -1.3% | 0.06 | -44.3% | 19.4x | -0.7% [-12.5%, +10.9%] | 0.553 | no |

Momentum passes the pre-registered rule narrowly. Active return is positive in 3 of 4 years but
no single year is significant (2026 slightly negative). Survivorship bias, 3.6 years and 3 shots
mean this is a lead to confirm out of sample (e.g. the live paper track or 2020-2022), not proof.

## Holdout confirmation 2020-01-02 .. 2022-12-30 (same fixed rule, run 2026-09-21)

`run_factor_baselines.py 2020-01-02 2022-12-30`, log `data/logs/factor_baselines_2020_2022.log`,
725 days, 47-49 eligible tickers. Equal-weight +13.8% CAGR.

| | CAGR | pooled active (95% CI) | one-sided p | adopt |
|---|---|---|---|---|
| momentum 12-1 | +24.2% | +9.4% [-10.0%, +27.5%] | 0.156 | no |
| low vol 60d | +1.1% | -12.5% [-21.4%, -3.9%] | 0.9985 | no (clean loss 2020) |
| reversal 1m | +4.9% | -7.1% [-20.2%, +6.5%] | 0.861 | no |

Momentum does not confirm at the pre-registered bar: same sign and similar size (+9.4% vs +12.8%),
positive in 2020 and 2021, negative in 2022, but the CI comfortably includes zero. Low vol was
significantly worse than equal-weight in this window. Conclusion: no factor is a validated
edge over equal-weight; momentum stays a weak, unconfirmed lead.
