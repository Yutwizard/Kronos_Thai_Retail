# ADR 0001: Equal-Weight Position Sizing

**Date:** 2026-06-21  **Status:** Accepted

## Context
The backtest engine supports three sizing modes: `equal`, `signal` (rank-based), and `inv_vol` (inverse volatility).

## Decision
Use `equal` weighting only.

## Rationale
`inv_vol` was backtested in `thai_equity_2022-2024_invvol/`: CAGR 13.29%, Sharpe 0.84, p=0.732. Equal-weight conclusively beat it. inv_vol over-allocates to low-vol stocks where the Kronos signal is weakest. `signal` mode is untested.

## Consequences
- All deployed strategies use equal weight.
- Do not switch to `inv_vol` without a GPU re-run that beats equal-weight.
