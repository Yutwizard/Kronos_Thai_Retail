"""kth_dr — DR (Depositary Receipt) integration for Kronos-TH.

On import, registers all verified DR tickers with kth.data.universe
via the register_asset_class() plugin hook.
"""
import logging

try:
    from kth.data.universe import register_asset_class
    from kth_dr.universe_dr import build_registration_dicts

    ticker_class, sector, currency_group, friction = build_registration_dicts()
    register_asset_class(ticker_class, sector=sector, currency_group=currency_group, friction=friction)
except Exception as e:
    # Registration is best-effort: a broken mapping.json must degrade to
    # "no DRs registered", never make `import kth_dr` fail — trade_gen and
    # the daily pipeline import this package behind optional-import guards.
    logging.warning(f"kth_dr: DR registration skipped: {e}")
