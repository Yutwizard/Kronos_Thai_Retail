"""
The investable universe for a Thai retail investor (as of 2025-2026).

Scope: SET-listed Thai equities (thai_equity, thai_index) plus DR
(Depositary Receipts) of major foreign stocks — DR is a separate plugin
package (kth_dr/) that extends this file via register_asset_class(),
never touching UNIVERSE directly.

Notes:
- Thai stocks (.BK): full retail access via any Thai broker.
- Thai mutual funds: most popular retail vehicle BUT no clean free API.
  We exclude them from the model and instead use their underlying
  benchmarks as proxies where relevant.

Excluded by design:
- Thai mutual funds: NAV-only, no free API, daily-lagged data
- Bonds: thin retail secondary market, irregular prices
- TFEX derivatives: outside retail scope for forecasting tool

Other asset classes (US equity, global ETF, commodity, crypto, bond
proxy, FX macro) were explored and backtested but archived 2026-07-16
to refocus the project on SET + DR — see archive/other-asset-classes/
for the original code, cached data, and backtest results.
"""

# Asset class -> list of (yfinance_ticker, display_name, notes)
UNIVERSE = {
    "thai_equity": [
        ("PTT.BK",     "PTT",                "Energy major"),
        ("KBANK.BK",   "Kasikornbank",       "Top 3 bank"),
        ("SCB.BK",     "SCB X",              "Top 3 bank"),
        ("BBL.BK",     "Bangkok Bank",       "Top 3 bank"),
        ("CPALL.BK",   "CP All",             "7-Eleven Thailand"),
        ("DELTA.BK",   "Delta Electronics",  "Largest SET mkt cap"),
        ("ADVANC.BK",  "AIS",                "Telecom"),
        ("AOT.BK",     "Airports of TH",     "Tourism proxy"),
        ("BDMS.BK",    "Bangkok Dusit Med",  "Healthcare"),
        ("GULF.BK",    "Gulf Energy",        "Power"),
        ("PTTEP.BK",   "PTT Exploration",    "Oil/gas E&P"),
        ("CPN.BK",     "Central Pattana",    "Retail property"),
        ("MINT.BK",    "Minor International","Hospitality"),
        ("BH.BK",      "Bumrungrad",         "Medical tourism"),
        ("IVL.BK",     "Indorama Ventures",  "Petrochem global"),
        ("BGRIM.BK",   "B.Grimm Power",      "Energy"),
        ("GPSC.BK",    "Global Power Synergy","Energy"),
        ("TOP.BK",     "Thai Oil",           "Energy"),
        ("IRPC.BK",    "IRPC",               "Petrochemical"),
        ("BANPU.BK",   "Banpu",              "Coal/energy"),
        ("BCP.BK",     "Bangchak Corp",      "Energy"),
        ("RATCH.BK",   "Ratch Group",        "Energy"),
        ("KTB.BK",     "Krung Thai Bank",    "Banking"),
        ("TISCO.BK",   "TISCO Financial",    "Banking"),
        ("TCAP.BK",    "Thanachart Capital", "Banking"),
        ("KKP.BK",     "Kiatnakin Phatra",   "Banking"),
        ("MEGA.BK",    "Mega Lifesciences",  "Commerce"),
        ("LH.BK",      "Land & Houses",      "Property"),
        ("QH.BK",      "Quality Houses",     "Property"),
        ("AP.BK",      "AP Thailand",        "Property"),
        ("ORI.BK",     "Origin Property",    "Property"),
        ("SCC.BK",     "Siam Cement",        "Construction"),
        ("HMPRO.BK",   "Home Product Center","Retail"),
        ("SIRI.BK",    "Sansiri",            "Property"),
        ("PSH.BK",     "Prinsiri",           "Property"),
        ("CPF.BK",     "Charoen Pokphand Foods","Food"),
        ("OSP.BK",     "Osotspa",            "Beverage"),
        ("ICHI.BK",    "Ichitan Group",      "Beverage"),
        ("CRC.BK",     "Central Retail",     "Retail"),
        ("GLOBAL.BK",  "Siam Global House",  "Retail"),
        ("DOHOME.BK",  "Dohome",             "Retail"),
        ("CENTEL.BK",  "Central Plaza Hotel","Hospitality"),
        ("ERW.BK",     "Erawan Group",       "Hospitality"),
        ("BCH.BK",     "Bangkok Chain Hospital","Healthcare"),
        ("CHG.BK",     "Chularat Hospital",  "Healthcare"),
        ("BEM.BK",     "Bangkok Expressway", "Logistics"),
        ("BTS.BK",     "BTS Group",          "Logistics"),
        ("TRUE.BK",    "True Corp",          "Telecom"),
        ("JMART.BK",   "J Mart",             "Tech"),
        ("HANA.BK",    "Hana Microelectronic","Tech"),
        ("CPNREIT.BK", "CPN Retail Growth REIT","Property"),
    ],

    "thai_index": [
        ("^SET.BK",    "SET Index",          "Thailand benchmark"),
    ],
}


# Reverse-lookup: ticker -> asset class (built once at import, O(1) lookup)
_TICKER_CLASS_MAP: dict[str, str] = {}
for _cls, _items in UNIVERSE.items():
    for _ticker, _, _ in _items:
        _TICKER_CLASS_MAP[_ticker] = _cls

# Reverse-lookup: ticker -> display name (built once at import, O(1) lookup)
_DISPLAY_NAME_MAP: dict[str, str] = {}
for _items in UNIVERSE.values():
    for _ticker, _name, _ in _items:
        _DISPLAY_NAME_MAP[_ticker] = _name

_extra_ticker_class: dict[str, str] = {}
_extra_sector: dict[str, str] = {}
_extra_friction: dict[str, dict] = {}

def register_asset_class(
    ticker_class: dict[str, str],
    sector: dict[str, str] | None = None,
    friction: dict[str, dict] | None = None,
):
    _extra_ticker_class.update(ticker_class)
    if sector:
        _extra_sector.update(sector)
    if friction:
        _extra_friction.update(friction)


def get_all_tickers():
    """Flat list of every INVESTABLE ticker in the universe.

    The `cls != "fx_macro"` filter is now permanently a no-op (fx_macro was
    archived 2026-07-16, see archive/other-asset-classes/) but is left in
    place rather than removed — harmless, and matches the same
    leave-dead-code-in-place call made for other now-unreachable
    asset-class branches (e.g. crypto handling in kth/backtest/walkforward.py).
    """
    return [t for cls, items in UNIVERSE.items()
            for (t, _, _) in items
            if cls != "fx_macro"]


def get_all_tickers_including_features():
    """All tickers, including any future features-only class. Use for data download only."""
    return [t for cls, items in UNIVERSE.items()
            for (t, _, _) in items]


def get_ticker_class(ticker):
    result = _TICKER_CLASS_MAP.get(ticker)
    if result is not None:
        return result
    return _extra_ticker_class.get(ticker)


def get_display_name(ticker):
    """Reverse lookup: display name for a ticker. O(1) dict lookup."""
    return _DISPLAY_NAME_MAP.get(ticker, ticker)


# Trading frictions per asset class (used by backtester)
# These are typical Thai-retail effective costs, round-trip.
FRICTION = {
    # Thai equity: ~0.157% commission online + 7% VAT on commission + 0.001% SET fee
    #             = ~0.168% one-way, ~0.336% round-trip. Plus 0.1% slippage assumed.
    # CPNREIT.BK (folded in from the archived standalone "reit" class 2026-07-16)
    # uses this rate too; the old reit-specific slippage of 0.0015 (vs 0.0010 here)
    # was intentionally dropped — see archive/other-asset-classes/.
    "thai_equity":  {"commission_oneway": 0.00168, "slippage_oneway": 0.0010},
    "thai_index":   {"commission_oneway": 0.00168, "slippage_oneway": 0.0010},
}


# SET sector classification for thai_equity tickers.
# Used by the sector concentration guard (max 2 positions per sector).
SECTOR: dict[str, str] = {
    # Banking (7)
    "KBANK.BK": "Banking", "SCB.BK":  "Banking", "BBL.BK":   "Banking",
    "KTB.BK":   "Banking", "TISCO.BK":"Banking",  "TCAP.BK":  "Banking", "KKP.BK": "Banking",
    # Energy (10)
    "PTT.BK":   "Energy",  "PTTEP.BK":"Energy",   "BGRIM.BK": "Energy",  "GPSC.BK": "Energy",
    "TOP.BK":   "Energy",  "IRPC.BK": "Energy",   "BANPU.BK": "Energy",  "BCP.BK":  "Energy",
    "RATCH.BK": "Energy",  "GULF.BK": "Energy",
    # Property (8)
    "LH.BK":    "Property","QH.BK":   "Property", "AP.BK":    "Property","ORI.BK":  "Property",
    "SIRI.BK":  "Property","PSH.BK":  "Property", "CPN.BK":   "Property","CPNREIT.BK":"Property",
    # Healthcare (5)
    "BDMS.BK":  "Healthcare","BH.BK": "Healthcare","BCH.BK":  "Healthcare",
    "CHG.BK":   "Healthcare","MEGA.BK":"Healthcare",
    # Retail (5)
    "CPALL.BK": "Retail",  "HMPRO.BK":"Retail",   "CRC.BK":   "Retail",
    "GLOBAL.BK":"Retail",  "DOHOME.BK":"Retail",
    # Hospitality & Tourism (4)
    "MINT.BK":  "Hospitality","CENTEL.BK":"Hospitality","ERW.BK":"Hospitality","AOT.BK":"Hospitality",
    # Telecom (2)
    "ADVANC.BK":"Telecom", "TRUE.BK": "Telecom",
    # Food & Beverage (3)
    "CPF.BK":   "Food",    "OSP.BK":  "Food",     "ICHI.BK":  "Food",
    # Tech & Electronics (3)
    "JMART.BK": "Tech",    "HANA.BK": "Tech",     "DELTA.BK": "Tech",
    # Logistics & Infrastructure (2)
    "BEM.BK":   "Logistics","BTS.BK": "Logistics",
    # Other / Diversified (2)
    "IVL.BK":   "Other",   "SCC.BK":  "Other",
}


def get_sector(ticker: str) -> str:
    result = SECTOR.get(ticker)
    if result is not None:
        return result
    return _extra_sector.get(ticker, "Other")


_DEFAULT_FRICTION = {"commission_oneway": 0.003, "slippage_oneway": 0.001}


def get_friction(ticker: str) -> dict[str, float]:
    cls = get_ticker_class(ticker)
    if cls is None:
        return dict(_DEFAULT_FRICTION)
    base = FRICTION.get(cls)
    if base is not None:
        return dict(base)
    extra = _extra_friction.get(cls)
    if extra is not None:
        return dict(extra)
    return dict(_DEFAULT_FRICTION)


def get_one_way_friction_rate(ticker: str) -> float:
    """One-way friction rate (commission + slippage) for a ticker."""
    f = get_friction(ticker)
    return f["commission_oneway"] + f["slippage_oneway"]


if __name__ == "__main__":
    print(f"Total asset classes: {len(UNIVERSE)}")
    print(f"Total tickers (investable):     {len(get_all_tickers())}")
    print(f"Total tickers (incl features):  {len(get_all_tickers_including_features())}")
    for cls, items in UNIVERSE.items():
        print(f"  {cls:14s} {len(items):3d} tickers")
