# Ticket 14: ticket 06's factor baselines on cleaned data (TODO)

STATUS: TODO. Depends on ticket 13. This is a robustness check of an existing family, NOT a new one.

## Question
Ticket 06 found momentum 12-1 beat equal-weight in 2023-2026 with p = 0.0144 against a 0.0167 bar (marginal), and it did not confirm on 2020-2022. The cache it used carries stub rows and the TRUE break. Does the result survive cleaning?

## Fixed design (frozen before running)
- Same rules as ticket 06: momentum 12-1, low volatility 60d, 1-month reversal; top 10, equal weight, monthly, first trading day; benchmark equal-weight of eligible tickers; 0.268% one-way; eligibility of at least 252 days; discovery 2023-01-02 to 2026-07-25; holdout 2020-01-02 to 2022-12-30; same block bootstrap, seed and 10,000 resamples.
- Data: `load_clean_closes` from ticket 13; nothing else changes. Runner: a new `scripts/run_factor_baselines_clean.py` that imports the ticket-06 helpers; the original script and its stored results are not edited.
- Correction family: still the original 3 tests, threshold 0.05/3 = 0.0167. No new shots.

## Interpretation rule (fixed now)
- Momentum, discovery window on cleaned data: p < 0.0167 with pooled CI lower bound > 0 and no clean-loss year -> "still weak and unconfirmed" (the 2020-2022 holdout already failed). Otherwise -> "momentum lead withdrawn".
- Low volatility and reversal: report only; neither was adopted and neither can become adopted by this ticket.
- Whatever happens, no rule is adopted from this ticket. Momentum stays out of the product unless it passes both windows, which is not possible under this ticket.

## Outputs
Side-by-side table (original vs cleaned: CAGR, Sharpe, max drawdown, turnover, pooled active with CI, one-sided p, per-year), log `data/logs/factor_baselines_clean.log`, a short verdict appended below and one line added to ticket 06's Result section pointing here.

## Out of scope
New rules, other windows, other lookbacks, tuning the top-N.
