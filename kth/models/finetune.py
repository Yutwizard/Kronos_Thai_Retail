"""
Fine-tuning pipeline for Kronos on the Thai-retail universe.
Mirrors Kronos repo finetune/ structure but as importable functions for Colab.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import random
import json

import numpy as np
import pandas as pd
import torch
import torch.utils.data


_TOKENIZER_CACHE: dict[str, object] = {}


# Module-level Dataset class (NOT inside a function — required for DataLoader pickle).
# Must inherit torch.utils.data.Dataset so Kronos's fit() accepts it via isinstance check.
class KronosDataset(torch.utils.data.Dataset):
    """PyTorch Dataset wrapping (x_df, y_series) samples for Kronos fine-tuning."""
    def __init__(self, samples: list[tuple[pd.DataFrame, pd.Series]]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        x_df, y_series = self.samples[idx]
        x = torch.tensor(x_df.values, dtype=torch.float32)
        y = torch.tensor(y_series.values, dtype=torch.float32)
        return x, y


def _validate_not_empty(dataset: dict, fold: int) -> None:
    """Warn if validation set is empty for this fold."""
    for split in ["val", "test"]:
        if split in dataset and len(dataset[split]) == 0:
            print(f"WARNING: {split} set is empty for fold {fold}. "
                  f"Early stopping may be disabled.")


def prepare_dataset(
    tickers: list[str] | None = None,
    ticker_data: dict[str, pd.DataFrame] | None = None,
    cache_dir: str = "./data/raw",
    fold: int = 0,
    n_folds: int = 3,
    fold_step_months: int = 6,
    holdout_start_date: str | None = None,
    lookback: int = 400,
    pred_len: int = 20,
    class_weights: dict[str, float] | None = None,
    seed: int = 42,
    streaming: bool = True,
) -> dict[str, KronosDataset]:
    """
    Returns {"train": KronosDataset, "val": KronosDataset, "test": KronosDataset}.
    Each KronosDataset wraps (x_df, y_series) pairs:
      x_df:    shape (lookback, 6)
      y_series: shape (pred_len,) — log-returns
    """
    from kth.data.loader import load_cached
    from kth.data.universe import get_all_tickers, get_ticker_class

    np.random.seed(seed)
    random.seed(seed)

    base_train_end = pd.Timestamp("2022-06-30")
    train_end = base_train_end + pd.DateOffset(months=fold * fold_step_months)
    val_start = train_end + pd.Timedelta(days=1)
    val_end = train_end + pd.DateOffset(months=6)
    test_start = val_end + pd.Timedelta(days=1)
    test_end = test_start + pd.DateOffset(months=6) - pd.Timedelta(days=1)

    print(f"Fold {fold}:")
    print(f"  Train:   ... -> {train_end.date()}")
    print(f"  Val:     {val_start.date()} -> {val_end.date()}")
    print(f"  Test:    {test_start.date()} -> {test_end.date()}")

    ohlcva_cols = ["open", "high", "low", "close", "volume", "amount"]

    def _make_window(df, i, lookback, pred_len, ohlcva_cols):
        x = df.iloc[i:i + lookback][ohlcva_cols].copy()
        close_window = df.iloc[i + lookback - 1:i + lookback + pred_len]["close"]
        y = np.log(close_window.values[1:] / close_window.values[:-1])
        return x.reset_index(drop=True), pd.Series(y)

    target_tickers = tickers if tickers is not None else get_all_tickers()
    skipped = 0
    print(f"prepare_dataset: {len(target_tickers)} tickers, fold {fold}")

    # ── Holdout mode ──
    if holdout_start_date is not None:
        holdout_since = pd.Timestamp(holdout_start_date)
        samples = []
        for ticker in target_tickers:
            if ticker_data is not None and ticker in ticker_data:
                df = ticker_data[ticker]
            else:
                try:
                    df = load_cached(ticker, cache_dir)
                except FileNotFoundError:
                    skipped += 1
                    continue
            df = df.sort_values("timestamps").reset_index(drop=True)
            holdout = df[df["timestamps"] >= holdout_since]
            if len(holdout) < lookback + pred_len:
                skipped += 1
                continue
            for i in range(0, len(holdout) - lookback - pred_len + 1, pred_len):
                x, y = _make_window(holdout, i, lookback, pred_len, ohlcva_cols)
                samples.append((x, y))
        print(f"Holdout: {len(samples)} samples from {holdout_start_date}")
        if skipped:
            print(f"  Skipped {skipped} tickers (insufficient data or missing cache)")
        return {"test": KronosDataset(samples)}

    # ── Normal fold-based split ──

    train_raw: list[tuple] = []  # (x, y, asset_class)
    val_samples: list[tuple[pd.DataFrame, pd.Series]] = []
    test_samples: list[tuple[pd.DataFrame, pd.Series]] = []

    for ticker in target_tickers:
        if ticker_data is not None and ticker in ticker_data:
            df = ticker_data[ticker]
        else:
            try:
                df = load_cached(ticker, cache_dir)
            except FileNotFoundError:
                skipped += 1
                continue

        df = df.sort_values("timestamps").reset_index(drop=True)
        asset_cls = get_ticker_class(ticker) or "unknown"

        # Train: sliding window stride=1
        train_df = df[df["timestamps"] <= train_end]
        if len(train_df) < lookback + pred_len:
            skipped += 1
            continue

        for i in range(len(train_df) - lookback - pred_len + 1):
            x, y = _make_window(train_df, i, lookback, pred_len, ohlcva_cols)
            train_raw.append((x, y, asset_cls))

        # Val: stride=pred_len
        val_df = df[(df["timestamps"] >= val_start) & (df["timestamps"] <= val_end)]
        for i in range(0, len(val_df) - lookback - pred_len + 1, pred_len):
            x, y = _make_window(val_df, i, lookback, pred_len, ohlcva_cols)
            val_samples.append((x, y))

        # Test: stride=pred_len
        test_df = df[(df["timestamps"] >= test_start) & (df["timestamps"] <= test_end)]
        for i in range(0, len(test_df) - lookback - pred_len + 1, pred_len):
            x, y = _make_window(test_df, i, lookback, pred_len, ohlcva_cols)
            test_samples.append((x, y))

    # Apply class_weights to train split
    if class_weights:
        weighted = []
        cls_groups: dict[str, list] = {}
        for x, y, cls in train_raw:
            cls_groups.setdefault(cls, []).append((x, y))
        for cls, weight in class_weights.items():
            if cls in cls_groups and weight > 1.0:
                dup_count = int(len(cls_groups[cls]) * (weight - 1.0))
                for _ in range(dup_count):
                    idx = random.randint(0, len(cls_groups[cls]) - 1)
                    weighted.append(cls_groups[cls][idx])
        train_raw_clean = [(x, y) for x, y, _ in train_raw]
        train_raw_clean.extend(weighted)
        random.shuffle(train_raw_clean)
    else:
        train_raw_clean = [(x, y) for x, y, _ in train_raw]

    print(f"  Train samples: {len(train_raw_clean)}")
    print(f"  Val samples:   {len(val_samples)}")
    print(f"  Test samples:  {len(test_samples)}")
    if skipped:
        print(f"  Skipped {skipped} tickers (insufficient data)")

    result = {
        "train": KronosDataset(train_raw_clean),
        "val": KronosDataset(val_samples),
        "test": KronosDataset(test_samples),
    }
    _validate_not_empty({"val": val_samples, "test": test_samples}, fold)
    return result


def finetune_tokenizer(
    dataset: dict[str, KronosDataset],
    output_dir: str,
    epochs: int = 1,
    batch_size: int = 32,
    lr: float = 1e-4,
    seed: int = 42,
) -> str:
    """
    DEPRECATED: Kronos does not expose a fit() method. Use the pre-trained
    tokenizer directly via:

        from kth.models._kronos_bridge import KronosTokenizer
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")

    For full training with SGDR + early stopping, see:
        scripts/train_per_market.py
    """
    raise NotImplementedError(
        "Kronos Tokenizer has no fit() method. "
        "Use KronosTokenizer.from_pretrained() directly. "
        "See scripts/train_per_market.py for the working training pipeline."
    )


def finetune_predictor(
    dataset: dict[str, KronosDataset],
    tokenizer_path: str,
    output_dir: str,
    **hparams,
) -> str:
    """
    DEPRECATED: Kronos does not expose a fit() method. The actual training
    pipeline is in scripts/train_per_market.py which uses:
        tokenizer.encode() → model.forward() → model.head.compute_loss()
    with SGDR (CosineAnnealingWarmRestarts) and early stopping.
    """
    raise NotImplementedError(
        "Kronos Predictor has no fit() method. "
        "Use scripts/train_per_market.py for training. "
        "For inference on fine-tuned checkpoints, use load_finetuned_checkpoint()."
    )


def evaluate_model(
    checkpoint_path: str,
    test_dataset: KronosDataset,
    kronos_model_name: str = "NeoQuasar/Kronos-small",
    max_samples: int = 100,
) -> dict:
    """
    Compare fine-tuned vs zero-shot on the same test set.
    Compares forecast-horizon return direction (sign of pct change
    at pred_len) against actual horizon return direction.

    Returns dict with per-metric comparison:
      - hit_rate: direction accuracy
      - mae: mean absolute error of predicted return vs actual return
      - n_samples: number of test windows evaluated
    """
    from kth.models.kronos_wrapper import KronosTH

    device = "cuda" if __import__("torch").cuda.is_available() else "cpu"

    # Zero-shot baseline
    k_zs = KronosTH.from_pretrained(kronos_model_name, device=device)
    # Fine-tuned
    k_ft = KronosTH.from_checkpoint(checkpoint_path, device=device)

    n = min(max_samples, len(test_dataset))
    zs_hits = 0
    zs_total = 0
    zs_errors: list[float] = []
    ft_hits = 0
    ft_total = 0
    ft_errors: list[float] = []

    for idx in range(n):
        x_tensor, y_actual = test_dataset[idx]
        lookback = x_tensor.shape[0]
        pred_len = len(y_actual)

        # Actual horizon return (total log-return over pred_len steps)
        actual_return = float(y_actual.sum())

        # Build DataFrame from tensor for Kronos input
        x_df = pd.DataFrame(
            x_tensor.numpy(),
            columns=["open", "high", "low", "close", "volume", "amount"],
        )
        last_close = float(x_df["close"].iloc[-1])

        # Build timestamps
        x_stamp = pd.Series(
            pd.bdate_range(
                end=pd.Timestamp.now() - pd.Timedelta(days=1),
                periods=lookback, freq="B",
            )
        )
        y_stamp = pd.Series(
            pd.bdate_range(
                start=x_stamp.iloc[-1] + pd.Timedelta(days=1),
                periods=pred_len, freq="B",
            )
        )

        try:
            r_zs = k_zs.forecast(
                ticker_or_df=x_df, pred_lens=[pred_len],
                n_samples=10, lookback=lookback,
            )
            zs_pred_close = float(
                r_zs.horizons[pred_len].summary["p50"].iloc[-1]
            )
            zs_return = np.log(zs_pred_close / last_close)
            if np.sign(zs_return) == np.sign(actual_return):
                zs_hits += 1
            zs_errors.append(abs(zs_return - actual_return))
            zs_total += 1
        except Exception:
            pass

        try:
            r_ft = k_ft.forecast(
                ticker_or_df=x_df, pred_lens=[pred_len],
                n_samples=10, lookback=lookback,
            )
            ft_pred_close = float(
                r_ft.horizons[pred_len].summary["p50"].iloc[-1]
            )
            ft_return = np.log(ft_pred_close / last_close)
            if np.sign(ft_return) == np.sign(actual_return):
                ft_hits += 1
            ft_errors.append(abs(ft_return - actual_return))
            ft_total += 1
        except Exception:
            pass

    return {
        "n_samples": max(zs_total, ft_total, 1),
        "zero_shot_hit_rate": zs_hits / max(zs_total, 1),
        "fine_tuned_hit_rate": ft_hits / max(ft_total, 1),
        "zero_shot_mae": np.mean(zs_errors) if zs_errors else 0.0,
        "fine_tuned_mae": np.mean(ft_errors) if ft_errors else 0.0,
        "improvement_pp": (ft_hits / max(ft_total, 1)) - (zs_hits / max(zs_total, 1)),
    }
