#!/usr/bin/env python3
"""Generate kronos_kaggle_pipeline.ipynb — thin wiring only, no business logic."""
import hashlib
import json
import os

CELLS = []


def code(src):
    CELLS.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"id": hashlib.md5(src.encode()).hexdigest()[:12]},
        "outputs": [],
        "source": src.splitlines(keepends=True),
    })


def md(src):
    CELLS.append({
        "cell_type": "markdown",
        "metadata": {"id": hashlib.md5(src.encode()).hexdigest()[:12]},
        "source": src.splitlines(keepends=True),
    })


md("""# Kronos-TH Kaggle Pipeline

Scheduled daily run (evening BKK). GPU + Internet ON. Attach secrets:
`GCP_SA_JSON`, `SPREADSHEET_ID`, `HF_TOKEN` (optional), `GITHUB_PAT` (if private repo).

**No business logic** — all logic lives in `kth.pipeline.daily.run_daily_pipeline`.
""")

code(r"""import os, sys, subprocess, json
from pathlib import Path

# ── Pin the repo to a specific commit ──────────────────────────────────
# To bump: update PINNED_COMMIT and rebuild this notebook.
PINNED_COMMIT = "main"  # ← TODO: replace with actual commit hash after Phase 0
REPO_URL = "https://github.com/anomalyco/Kronos_Thai_Retail.git"
# If using a PAT for a private repo, uncomment the next line:
# REPO_URL = f"https://{os.environ.get('GITHUB_PAT')}@github.com/anomalyco/Kronos_Thai_Retail.git"

REPO_DIR = "/kaggle/working/Kronos_Thai_Retail"

if not Path(REPO_DIR).exists():
    subprocess.check_call(["git", "clone", "--depth", "1", "--branch", PINNED_COMMIT, REPO_URL, REPO_DIR], timeout=120)

os.chdir(REPO_DIR)

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                       "gspread", "google-auth", "pandas", "yfinance", "torch"])
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", REPO_DIR])
print("Dependencies installed.")
""")

code(r"""from kaggle_secrets import UserSecretsClient
from kth.io.kaggle_runtime import load_secrets, make_sheets_client

s = UserSecretsClient()
cfg = load_secrets(s.get_secret)
gc = make_sheets_client(cfg.sa_info)
print(f"Auth OK — spreadsheet: {cfg.spreadsheet_id[:12]}...")
""")

code(r"""import torch
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from kth.pipeline.daily import run_daily_pipeline

today = datetime.now(ZoneInfo("Asia/Bangkok")).date()

# ── Real model (GPU) ────────────────────────────────────────────────────
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import precompute_forecasts

print(f"CUDA available: {torch.cuda.is_available()}")
th = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda',
                              token=cfg.hf_token)

def model_forecast(tickers, today_str):
    CACHE_SLUG = "NeoQuasar_Kronos-small"
    pending = [t for t in tickers
               if t.startswith(tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))]
    pending = [t for t in tickers if not (
        Path(f'data/forecast_cache/{CACHE_SLUG}/{today_str}/'
             f'{t.replace("^","_").replace("=","_")}.parquet').exists()
    )]
    if pending:
        precompute_forecasts(th, pending,
                             start_date=today_str, end_date=today_str,
                             pred_len=20, n_samples=50, lookback=400)
        print(f"Forecasted {len(pending)} tickers")
    else:
        print("All tickers already forecasted for today — skipping")

model = type('ModelFacade', (), {'forecast': model_forecast})()

# ── Data loader ─────────────────────────────────────────────────────────
from kth.data.loader import download_universe, load_cached
from kth.data.universe import get_all_tickers

def data_ensure(tickers):
    download_universe(tickers)
    ohlcv = {}
    for t in tickers:
        try:
            df = load_cached(t)
            if df is not None and not df.empty:
                ohlcv[t] = df
        except Exception:
            pass
    return ohlcv

data_loader = type('DataLoader', (), {'ensure': data_ensure})()

# ── Notifier (print to stderr; extend with email/webhook later) ─────────
import sys
notifier = lambda lvl, msg: print(f"[Kronos] {lvl}: {msg[:200]}", file=sys.stderr)

# ── Run pipeline ────────────────────────────────────────────────────────
result = run_daily_pipeline(
    gc, cfg.spreadsheet_id,
    model=model,
    data_loader=data_loader,
    today=today,
    notifier=notifier,
)
print(f"Pipeline result: {result}")
""")

md("""## Troubleshooting

- **GPU not available:** Check Runtime → Change runtime type → GPU, Internet ON.
- **Secrets missing:** Add-ons → Secrets → add GCP_SA_JSON (paste SA key or base64),
  SPREADSHEET_ID (from sheet URL).
- **yfinance blocked:** Switch to Kaggle Dataset OHLCV fallback.
- **Auth fails:** Verify the SA email has Editor access to the spreadsheet.
- **Rebuild notebook:** Run `python kaggle/build_kaggle_notebook.py` to regenerate.
""")

nb = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "kaggle": {
            "accelerator": "GPU",
            "internet": True,
            "isGpuEnabled": True,
        },
        "kernelspec": {
            "display_name": "Python 3",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.10.0"},
    },
    "cells": CELLS,
}

path = os.path.join(os.path.dirname(__file__), "kronos_kaggle_pipeline.ipynb")
with open(path, "w") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"Generated {path} — {len(CELLS)} cells")
