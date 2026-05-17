"""
Download full 51-ticker universe data via yfinance.
Downloads all tickers (shared between Phase 1 and Phase 2).
Run once — subsequent runs skip already-cached tickers.
"""
from kth.data.loader import download_universe
from kth.data.universe import get_all_tickers

tickers = get_all_tickers()
print(f"Downloading {len(tickers)} tickers (10 years each)...")
report = download_universe(tickers, period="10y", cache_dir="./data/raw")
print("\nDownload complete.")
print(report[["ticker", "rows", "start", "end"]].to_string(index=False))
