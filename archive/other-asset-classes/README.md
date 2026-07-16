# Archived: non-SET/DR asset classes

On 2026-07-16, Kronos-TH's scope was narrowed to **SET-listed Thai
equities + DR (Depositary Receipts)** only. Before that, the project
covered 9 asset classes (100 tickers): `thai_equity`, `thai_index`,
`us_equity`, `etf_global`, `commodity`, `crypto`, `bond_proxy`, `reit`,
`fx_macro`, defined in `kth/data/universe.py`'s `UNIVERSE` dict.

This folder holds the code, cached data, and backtest results for the 7
classes that were removed from active scope (`us_equity`, `etf_global`,
`commodity`, `crypto`, `bond_proxy`, `fx_macro`, and `reit` — except
`CPNREIT.BK`, which was SET-listed and got folded into `thai_equity`
instead of archived; only `VNQ` moved here with the rest of `reit`).

## What's here

- `data/backtest_results/{crypto,us_equity}_{ft,zs}/` — fine-tune vs
  zero-shot backtest results for crypto and US equity. Verdict for both:
  fine-tuning did not beat zero-shot (see the original repo's
  `data/backtest_results/MANIFEST.md` for the summary table).
- `data/raw/*.parquet` — cached OHLCV for the 48 archived tickers
  (17 us_equity, 9 etf_global, 4 commodity, 12 crypto, 3 bond_proxy,
  1 reit [`VNQ`], 2 fx_macro).
- `scripts/train_crypto_fold0.py` — crypto-specific fine-tuning script.

The dedicated crypto backtest design spec moved separately, to
`docs/superpowers/archive/specs/2026-05-21-crypto-backtest-design.md`
(the existing archive convention for completed/descoped specs, rather
than duplicating it here).

## Why archived, not deleted

The research was real and the numbers are still valid as of when they
were computed — this is a scope decision (focus the tool on what a Thai
retail investor can *and does* actually trade), not a verdict that the
other markets were uninteresting or wrong.

## Reactivating a class later

The surviving mechanism for adding a class back is
`kth.data.universe.register_asset_class()` — the same plugin hook
`kth_dr/` already uses to add DR tickers without touching `UNIVERSE`
directly. To bring back, say, crypto: register its tickers/friction via
that hook (in a new `kth_crypto/`-style package, mirroring `kth_dr/`'s
structure) rather than re-adding a hardcoded key to `UNIVERSE` itself.
The cached data and backtest results in this folder are still valid
starting points; `kth/backtest/walkforward.py`'s crypto-specific
calendar handling and `kth/models/kronos_wrapper.py`'s crypto
7-day-calendar auto-detect were both left in place (not removed) during
the 2026-07-16 cleanup specifically so this path stays open.
