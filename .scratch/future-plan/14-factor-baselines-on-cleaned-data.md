# Ticket 14: ticket 06's factor baselines on cleaned data (TODO)

STATUS: DONE 2026-09-21. VERDICT: momentum lead WITHDRAWN on cleaned data. Depends on ticket 13. This was a robustness check of an existing family, NOT a new one.

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

## Results (run 2026-09-21, `scripts/run_factor_baselines_clean.py`, log `data/logs/factor_baselines_clean.log`)
The runner runs the original loader and the cleaned loader in one pass. The "original" numbers reproduce ticket 06 exactly (momentum p = 0.0144, low vol p = 0.1423, reversal p = 0.5528 in 2023-2026). Cleaning: 57 stub dates dropped, TRUE.BK 2023-03-03 break scaled (x1.686274); 868 discovery days become 814. The 2020-2022 holdout has no stub dates, so its numbers are identical.

### Discovery 2023-01-02 .. 2026-07-25 (bar: pooled CI lower bound > 0, one-sided p < 0.0167, no clean-loss year)
| rule | data | CAGR | Sharpe | max DD | pooled active (95% CI) | p | adopt |
|---|---|---|---|---|---|---|---|
| equal-weight | original / cleaned | +0.6% / +0.3% | 0.12 / 0.10 | -37.4% / -38.3% | | | |
| momentum 12-1 | original | +14.4% | 0.94 | -22.2% | +12.8% [+1.3%, +24.9%] | 0.0144 | yes (marginal) |
| momentum 12-1 | cleaned | +11.8% | 0.79 | -24.6% | +10.7% [-1.4%, +22.5%] | 0.0379 | NO |
| low vol 60d | original | +6.8% | 0.60 | -23.3% | +5.4% [-4.8%, +15.6%] | 0.1423 | no |
| low vol 60d | cleaned | +7.9% | 0.69 | -20.1% | +6.7% [-4.3%, +17.5%] | 0.1132 | no |
| reversal 1m | original | -1.3% | 0.06 | -44.3% | -0.7% [-12.5%, +10.9%] | 0.5528 | no |
| reversal 1m | cleaned | -1.3% | 0.06 | -46.1% | -0.2% [-12.6%, +12.1%] | 0.5101 | no |

Momentum active return by year, original -> cleaned: 2023 +12.4% -> +16.3%; 2024 +7.4% -> +2.8%; 2025 +28.3% -> +21.5%; 2026 -3.9% -> -7.0%.

### Holdout 2020-01-02 .. 2022-12-30
Identical on both loaders (no stub dates or breaks in the window): momentum +9.4% [-10.0%, +27.5%] p 0.1561; low vol -12.5% [-21.4%, -3.9%] p 0.9985 (clean loss in 2020); reversal -7.1% [-20.2%, +6.5%] p 0.8611.

### Verdict by the frozen rule
Momentum on cleaned discovery data does not pass the 0.0167 bar (p = 0.0379, CI lower bound -1.4%), so the momentum lead is WITHDRAWN. Nothing is adopted. Low volatility and reversal are unchanged (neither adopted).

### Reading
- The original pass was marginal (p = 0.0144 against 0.0167) and did not survive removing the stub dates and the TRUE break. The point estimate is still positive (+10.7% a year) and positive in 2023-2025, but the evidence is now below the pre-registered bar, and the 2020-2022 holdout already failed.
- Caveat: with 57 dates dropped, CAGR and annualised figures use days/252 over a shorter calendar, so their level shifts slightly; compare the verdicts and p-values, not the decimals.
- No new correction family was opened; the threshold stayed 0.05/3.
