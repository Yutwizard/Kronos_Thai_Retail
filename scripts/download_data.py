"""
Download full universe data via yfinance and run post-download price sanity check.
Sanity check: if any ticker's last close moved >30% from prior close, flag it
and write to data/logs/sanity_{date}.json so the forecast pipeline can skip it.
"""
import json
import logging
from datetime import date
from pathlib import Path

from kth.data.loader import download_universe, load_cached
from kth.data.universe import get_all_tickers_including_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

SANITY_THRESHOLD = 0.30
LOG_DIR = Path("data/logs")
CACHE_DIR = Path("data/raw")


def _check_price_sanity(tickers: list[str]) -> list[str]:
    """Return list of tickers whose last close moved > SANITY_THRESHOLD from prior close."""
    failures = []
    for ticker in tickers:
        try:
            df = load_cached(ticker, cache_dir=str(CACHE_DIR))
            if len(df) < 2:
                continue
            last = float(df["close"].iloc[-1])
            prev = float(df["close"].iloc[-2])
            if prev == 0:
                continue
            pct = abs(last - prev) / prev
            if pct > SANITY_THRESHOLD:
                logging.warning(
                    f"SANITY FAIL {ticker}: close {last:.2f} moved {pct:.1%} from prior {prev:.2f}"
                )
                failures.append(ticker)
        except Exception as e:
            logging.debug(f"Sanity skip {ticker}: {e}")
    return failures


tickers = get_all_tickers_including_features()
try:
    from kth_dr.universe_dr import get_verified_dr_tickers, get_dr_underlying_tickers, DR_MAP, _ensure_loaded
    _ensure_loaded()
    dr_tickers = get_verified_dr_tickers()
    dr_underlyings = get_dr_underlying_tickers()
    dr_fx_tickers = list({DR_MAP[u].get("fx_ticker", "THB=X") for u in dr_underlyings if u in DR_MAP})
    tickers = tickers + dr_tickers + dr_underlyings + dr_fx_tickers
except ImportError:
    pass
except Exception as e:
    print(f"WARN: DR ticker wiring skipped: {e}")

print(f"Downloading {len(tickers)} tickers (10 years each)...")
report = download_universe(tickers, period="10y", cache_dir=str(CACHE_DIR))
print("\nDownload complete.")
print(report[["ticker", "rows", "start", "end"]].to_string(index=False))

# Post-download sanity check
print(f"\nRunning price sanity check (>{SANITY_THRESHOLD:.0%} move threshold)...")
failures = _check_price_sanity(tickers)

LOG_DIR.mkdir(parents=True, exist_ok=True)
sanity_log = LOG_DIR / f"sanity_{date.today()}.json"
with open(sanity_log, "w") as f:
    json.dump({"date": str(date.today()), "failures": failures, "threshold": SANITY_THRESHOLD}, f)

if failures:
    print(f"⚠  {len(failures)} ticker(s) flagged: {failures}")
    print(f"   These will be excluded from today's forecast run.")
    print(f"   Details: {sanity_log}")
else:
    print(f"✅ All tickers passed sanity check.")
