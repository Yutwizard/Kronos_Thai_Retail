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
    cache_dir: str = "./data/raw",
    fold: int = 0,
    n_folds: int = 3,
    fold_step_months: int = 6,
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

    tickers = get_all_tickers()
    skipped = 0

    train_raw: list[tuple] = []  # (x, y, asset_class)
    val_samples: list[tuple[pd.DataFrame, pd.Series]] = []
    test_samples: list[tuple[pd.DataFrame, pd.Series]] = []

    for ticker in tickers:
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
    """Fine-tune the Kronos VQ tokenizer. Returns output_dir path."""
    import torch
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    from kronos import KronosTokenizer

    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    train_data = dataset["train"]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    tokenizer.fit(
        train_data,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=lr,
        output_dir=str(output_path),
    )

    with open(output_path / "training_args.json", "w") as f:
        json.dump({"lr": lr, "epochs": epochs, "seed": seed,
                    "batch_size": batch_size, "timestamp": str(pd.Timestamp.now())}, f)

    print(f"Tokenizer fine-tuned. Saved to {output_path}")
    return str(output_path)


def finetune_predictor(
    dataset: dict[str, KronosDataset],
    tokenizer_path: str,
    output_dir: str,
    epochs: int = 5,
    batch_size: int = 8,
    grad_accum: int = 4,
    fp16: bool = True,
    lr: float = 5e-5,
    lr_scheduler: str = "cosine",
    weight_decay: float = 0.01,
    loss: str = "mae",
    early_stopping_patience: int = 2,
    save_every_n_steps: int = 200,
    seed: int = 42,
) -> str:
    """Fine-tune the Kronos predictor. Returns path to best checkpoint."""
    import torch
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    from kronos import KronosPredictor

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    train_data = dataset["train"]
    val_data = dataset.get("val")
    if val_data is not None and len(val_data) == 0:
        val_data = None

    predictor = KronosPredictor.from_pretrained(
        tokenizer_path, device="cuda"
    )

    predictor.fit(
        train_data,
        val_data=val_data,
        epochs=epochs,
        batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        fp16=fp16,
        learning_rate=lr,
        lr_scheduler=lr_scheduler,
        weight_decay=weight_decay,
        loss=loss,
        early_stopping_patience=early_stopping_patience,
        save_every_n_steps=save_every_n_steps,
        output_dir=str(output_path),
    )

    with open(output_path / "training_args.json", "w") as f:
        json.dump({"lr": lr, "epochs": epochs, "seed": seed, "loss": loss,
                    "lr_scheduler": lr_scheduler, "weight_decay": weight_decay,
                    "timestamp": str(pd.Timestamp.now())}, f)

    print(f"Predictor fine-tuned. Best checkpoint saved to {output_path}")
    return str(output_path)
