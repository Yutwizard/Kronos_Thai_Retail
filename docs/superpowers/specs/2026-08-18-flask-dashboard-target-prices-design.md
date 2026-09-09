# Flask Dashboard Target Prices Design

## Goal

Show both the model's median forecast price (P50) and its upper forecast price
(P95) beside expected return in the Flask dashboard's forecast tables.

## Scope

- Flask dashboard only.
- Update the Morning Brief tables and Full Ranking table.
- Leave trade-ticket tables unchanged.
- Preserve existing expected-return, ranking, confidence, and trade-selection
  behavior.

## Data Contract

Each forecast row will expose two display fields:

- `target_price`: P50 forecast price in the execution ticker's price scale.
- `p95_price`: P95 forecast price in the execution ticker's price scale.

For ordinary stocks, these are the existing `p50_close` and `p95_close`
values. For DR-backed forecasts, the underlying forecast prices will be scaled
by the current execution-price-to-underlying-close ratio. This keeps the values
actionable in THB while preserving the model's forecasted percentage move.

The existing `p50_close` and `p95_close` fields remain available for model and
history consumers. The new fields are display-oriented and do not affect
ranking or trade generation.

## UI Changes

In both forecast table builders, add columns adjacent to `Exp Ret`:

1. `Target` for the P50 execution-scale price.
2. `P95` for the upper forecast price.

Prices will use the same two-decimal formatting as Close. Existing color,
direction, delta, band, flag, and net-return presentation remains unchanged.
Column tooltips and the legend will explain that Target is P50 and P95 is the
upper model forecast, not a guaranteed price.

## Testing

- Add a focused test for ordinary-stock target prices.
- Add a focused test for DR target-price scaling.
- Verify the dashboard table markup contains both new columns and values.
- Run the repository's relevant verification tests and a syntax check for the
  dashboard JavaScript-bearing HTML.

## Error Handling

If execution-price conversion cannot be calculated, retain the underlying
forecast values rather than dropping the forecast row. Existing forecast-row
error handling remains unchanged.
