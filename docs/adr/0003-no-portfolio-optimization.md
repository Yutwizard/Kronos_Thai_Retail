# ADR 0003: No Portfolio Optimization (Markowitz / Risk Parity / Factor Models)

**Date:** 2026-06-21  **Status:** Accepted

## Context
The strategy selects top-5 stocks by Expected Return and sizes them equally.

## Decision
Do not add Markowitz, risk parity, or factor-model optimization.

## Rationale
Per `PROJECT_STRUCTURE.md §12`: adds complexity without changing the core question ("does the model pick well?"). Equal-weight is the cleanest test of stock-selection alpha. Optimization can be Notebook 06 later if useful.

## Consequences
- Position sizing stays equal-weight (see ADR 0001).
- Portfolio optimization is out of scope until explicitly requested.
