#!/usr/bin/env python3
"""
Thin entrypoint for the daily Kaggle pipeline.

Usage:
    python run_pipeline.py              # production (needs env vars + GPU)
    python run_pipeline.py --dry-run    # offline fakes, no network
"""
import os
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path


def _load_real_model(cfg):
    from kth.models.kronos_wrapper import KronosTH
    hf_model = cfg.hf_token or None
    model = KronosTH.from_pretrained(
        'NeoQuasar/Kronos-small',
        device='cuda',
        token=hf_model,
    )
    return model


def _make_real_model_facade(model):
    """Wrap KronosTH into the simple 'model.forecast(tickers, today_str)' interface."""
    from kth.backtest.walkforward import precompute_forecasts

    def forecast(tickers, today_str):
        pending = [t for t in tickers if not _forecast_exists(t, today_str)]
        if not pending:
            return
        precompute_forecasts(model, pending,
                             start_date=today_str, end_date=today_str,
                             pred_len=20, n_samples=50, lookback=400)

    return type('ModelFacade', (), {'forecast': forecast})()


def _forecast_exists(ticker: str, today_str: str) -> bool:
    safe = ticker.replace('^', '_').replace('=', '_')
    from kth.trading.trade_gen import CACHE_SLUG
    return (Path('data/forecast_cache') / CACHE_SLUG / today_str / f'{safe}.parquet').exists()


def _real_data_loader():
    from kth.data.loader import download_universe, load_cached
    from kth.data.universe import get_all_tickers_including_features

    def ensure(tickers):
        download_universe(tickers)
        ohlcv_dict = {}
        failed_tickers = set()
        for ticker in tickers:
            try:
                df = load_cached(ticker)
                if df is None or df.empty:
                    continue
                last_close = float(df['close'].iloc[-1])
                prev_close = float(df['close'].iloc[-2]) if len(df) > 1 else last_close
                if prev_close > 0 and abs(last_close - prev_close) / prev_close > 0.30:
                    failed_tickers.add(ticker)
                    continue
                ohlcv_dict[ticker] = df
            except Exception:
                continue
        return ohlcv_dict

    return type('DataLoader', (), {'ensure': ensure})()


def _make_notifier(cfg):
    """Build a simple notifier that prints to stderr (extend with email/webhook later)."""

    def notify(level, msg):
        msg_str = f"[Kronos] {level}: {msg[:200]}"
        print(msg_str, file=sys.stderr)
        if level == 'error':
            print(f"  Hint: check the dashboard Pipeline Status tab and logs.", file=sys.stderr)

    return notify


def main(dry_run: bool = False):
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()

    if dry_run:
        _dry_run(today)
        return

    from kth.io.kaggle_runtime import load_secrets, make_sheets_client
    from kth.pipeline.daily import run_daily_pipeline

    cfg = load_secrets(os.environ.get)
    gc = make_sheets_client(cfg.sa_info)
    model_facade = _make_real_model_facade(_load_real_model(cfg))
    data_loader = _real_data_loader()
    notifier = _make_notifier(cfg)

    result = run_daily_pipeline(
        gc, cfg.spreadsheet_id,
        model=model_facade,
        data_loader=data_loader,
        today=today,
        notifier=notifier,
    )
    print(f"Pipeline result: {result}")


def _dry_run(today):
    from kth.io.kaggle_runtime import load_secrets
    from kth.pipeline.daily import run_daily_pipeline
    from verify_kaggle_runtime import FakeModel, FakeLoader, seeded_fake_client

    with tempfile.TemporaryDirectory() as tmp:
        gc = seeded_fake_client()
        fake_model = FakeModel()
        fake_loader = FakeLoader()
        result = run_daily_pipeline(
            gc, 'test_id', model=fake_model, data_loader=fake_loader,
            today=today, work_dir=tmp,
        )
        print(f"Dry-run result: {result}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
