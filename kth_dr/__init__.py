"""kth_dr — DR (Depositary Receipt) integration for Kronos-TH.

On import, registers all verified DR tickers with kth.data.universe
via the register_asset_class() plugin hook.
"""
from kth.data.universe import register_asset_class
from kth_dr.universe_dr import build_registration_dicts

ticker_class, sector, friction = build_registration_dicts()
register_asset_class(ticker_class, sector=sector, friction=friction)
