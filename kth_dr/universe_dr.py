"""DR mapping data — loaded from data/dr/mapping.json at import time."""
import json
import logging
from pathlib import Path

DR_MAP_PATH = Path("data/dr/mapping.json")
MIN_DR_HISTORY = 60
DR_PREMIUM_WARN_THRESHOLD = 0.05

DR_MAP: dict = {}

# Hand-curated global industry taxonomy for DR underlyings, independent of
# SET's 10 thai_equity sector buckets (which are built around the Thai economy
# and don't map cleanly onto foreign large-caps). Keyed by underlying ticker,
# not DR ticker, since the underlying identity is stable even if the primary
# DR alternative changes. See docs/adr/0004-separate-dr-sector-and-currency-group.md.
# A judgment call, not a verifiable fact like the rest of mapping.json — kept
# out of mapping.json's verified-data curation workflow deliberately.
DR_SECTOR: dict[str, str] = {
    # Tech / Internet / AI
    "0700.HK": "Tech", "9988.HK": "Tech", "9888.HK": "Tech", "9618.HK": "Tech",
    "3690.HK": "Tech", "9999.HK": "Tech", "1024.HK": "Tech", "3888.HK": "Tech",
    "0020.HK": "Tech", "9660.HK": "Tech", "9880.HK": "Tech", "9984.T": "Tech",
    # Semiconductors
    "ASML.AS": "Semiconductors", "1347.HK": "Semiconductors",
    "8035.T": "Semiconductors", "6861.T": "Semiconductors",
    # Auto
    "7203.T": "Auto", "1211.HK": "Auto", "0175.HK": "Auto", "RACE.MI": "Auto",
    # Consumer Electronics
    "1810.HK": "Consumer Electronics", "6758.T": "Consumer Electronics",
    # Materials
    "2899.HK": "Materials", "3750.HK": "Materials",
    # Financials
    "3968.HK": "Financials",
    # Energy
    "0857.HK": "Energy",
    # Consumer (retail / staples / food)
    "9992.HK": "Consumer", "9633.HK": "Consumer", "8136.T": "Consumer",
    "9983.T": "Consumer", "3563.T": "Consumer",
    # Luxury
    "RMS.PA": "Luxury", "OR.PA": "Luxury", "MC.PA": "Luxury",
    # Healthcare
    "NOVO-B.CO": "Healthcare", "SAN.PA": "Healthcare",
    # Telecom
    "Z74.SI": "Telecom",
}


def _load_dr_mapping() -> dict:
    """mapping.json is hand-edited (a human flips `verified`), so a typo here
    must degrade to "no DRs" — never crash the pipeline that imports us."""
    if not DR_MAP_PATH.exists():
        return {}
    try:
        with open(DR_MAP_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning(f"DR mapping unreadable ({DR_MAP_PATH}): {e} — continuing without DRs")
        return {}
    if not isinstance(data, dict):
        logging.warning(f"DR mapping malformed ({DR_MAP_PATH}): top level must be an object — continuing without DRs")
        return {}
    return data


def _ensure_loaded():
    if not DR_MAP:
        DR_MAP.update(_load_dr_mapping())


def get_dr_for_underlying(underlying_ticker: str) -> dict | None:
    _ensure_loaded()
    entry = DR_MAP.get(underlying_ticker)
    if not isinstance(entry, dict) or "excluded_reason" in entry:
        return None
    alternatives = entry.get("alternatives", [])
    if not alternatives:
        return None
    primary_ticker = entry.get("primary_dr")
    if primary_ticker:
        for alt in alternatives:
            if alt["dr_ticker"] == primary_ticker and alt.get("verified") and alt.get("history_rows", 0) >= MIN_DR_HISTORY:
                return alt
    valid = [a for a in alternatives if a.get("verified") and a.get("history_rows", 0) >= MIN_DR_HISTORY]
    if not valid:
        return None
    return max(valid, key=lambda a: a.get("avg_volume_30d", 0))


def get_underlying_for_dr(dr_ticker: str) -> str | None:
    _ensure_loaded()
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        for alt in entry.get("alternatives", []):
            if alt["dr_ticker"] == dr_ticker:
                return underlying
    return None


def get_verified_dr_tickers() -> list[str]:
    """Flat list of DR tickers themselves (e.g. 'SAMSUNG80.BK'). Used to make sure
    DR price data gets downloaded/cached and for the discovery script — NOT for
    trade_gen's forecast loop (see get_dr_underlying_tickers below)."""
    _ensure_loaded()
    result = []
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        dr = get_dr_for_underlying(underlying)
        if dr:
            result.append(dr["dr_ticker"])
    return result


def get_dr_underlying_tickers() -> list[str]:
    """Underlying tickers that have a verified DR (e.g. '005930.KS').

    This is the list trade_gen.py's forecast loop must use — NOT
    get_verified_dr_tickers(). Kronos forecasts are always cached under the
    underlying's own ticker (the model never runs on the DR itself), so looping
    over DR tickers there would look for a forecast cache file that can never
    exist and silently drop every DR candidate. See implementation-plan review
    2026-07-12 for the bug this fixes.
    """
    _ensure_loaded()
    result = []
    for underlying, entry in DR_MAP.items():
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        if get_dr_for_underlying(underlying):
            result.append(underlying)
    return result


def get_dr_info_for_display(dr_ticker: str) -> dict | None:
    """Return enriched display info: underlying, ratio, fx_ticker, display_name."""
    underlying = get_underlying_for_dr(dr_ticker)
    if underlying is None:
        return None
    _ensure_loaded()
    entry = DR_MAP.get(underlying, {})
    for alt in entry.get("alternatives", []):
        if alt["dr_ticker"] == dr_ticker:
            return {
                "underlying_ticker": underlying,
                "display_name": entry.get("display_name", underlying),
                "ratio": alt.get("ratio", 1),
                "fx_ticker": entry.get("fx_ticker", "THB=X"),
            }
    return None


def get_all_download_tickers(base_tickers: list[str]) -> list[str]:
    """base_tickers plus every DR/underlying/FX ticker that needs downloading —
    the combined list kth.pipeline.daily, scripts/dashboard.py, and
    scripts/download_data.py all need before calling download_universe()."""
    _ensure_loaded()
    dr_tickers = get_verified_dr_tickers()
    dr_underlyings = get_dr_underlying_tickers()
    dr_fx_tickers = list({DR_MAP[u].get("fx_ticker", "THB=X") for u in dr_underlyings if u in DR_MAP})
    return base_tickers + dr_tickers + dr_underlyings + dr_fx_tickers


def build_registration_dicts() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, dict]]:
    """Build the four dicts needed by register_asset_class() from verified DRs.

    Sector and currency group are independent concentration dimensions — see
    docs/adr/0004-separate-dr-sector-and-currency-group.md. Sector is real
    industry classification (DR_SECTOR); currency group is the underlying's
    currency (HKD/JPY/EUR/...), capturing FX exposure and, for EUR names,
    correlated late market-close timing (see CLAUDE.md) — a distinct risk from
    industry correlation. A literal per-exchange split for currency was
    considered and rejected — NL/DK/IT each have exactly one verified DR
    today, so an exchange-level cap could never bind for them.
    """
    _ensure_loaded()
    ticker_class = {}
    sector = {}
    currency_group = {}
    friction = {"dr": {"commission_oneway": 0.00168, "slippage_oneway": 0.0010}}
    for underlying, entry in DR_MAP.items():
        # _meta is a dict but _unresolved is a list — same guard as the getters above
        if not isinstance(entry, dict) or "excluded_reason" in entry:
            continue
        currency = entry.get("underlying_currency") or "Other"
        sec = DR_SECTOR.get(underlying, "Other")
        for alt in entry.get("alternatives", []):
            if alt.get("verified"):
                dr_ticker = alt["dr_ticker"]
                ticker_class[dr_ticker] = "dr"
                sector[dr_ticker] = sec
                currency_group[dr_ticker] = currency
    return ticker_class, sector, currency_group, friction
