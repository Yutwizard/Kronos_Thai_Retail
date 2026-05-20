"""
Train per-market model fold N locally on GTX 1060 (6GB VRAM).
Usage: venv/bin/python scripts/train_per_market.py <model_name> [fold_number]
       model_name: thai_equity, us_equity, crypto
"""
import time
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kronos_repo"))

from kth.data.universe import UNIVERSE
from kth.data.loader import load_cached
from kth.models._kronos_bridge import KronosTokenizer, Kronos

MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "crypto"
FOLD = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CACHE_DIR = "./data/raw"
OUTPUT_DIR = f"./checkpoints/{MODEL_NAME}/fold{FOLD}"
LOOKBACK = 400
PRED_LEN = 20
FOLD_STEP_MONTHS = 21  # val/test need ≥420 rows; 21 mo × 21 bdays/mo = 441 ✅

MODEL_TICKERS = {
    "thai_equity": [t for t, _, _ in UNIVERSE["thai_equity"]],
    "us_equity":   [t for t, _, _ in UNIVERSE["us_equity"]],
    "crypto":      [t for t, _, _ in UNIVERSE["crypto"]],
}
TICKERS = MODEL_TICKERS[MODEL_NAME]


class TimeSeriesDataset(torch.utils.data.Dataset):
    def __init__(self, samples):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x_df, y_series = self.samples[idx]
        x = torch.tensor(x_df.values, dtype=torch.float32)
        y = torch.tensor(y_series.values, dtype=torch.float32)
        return x, y


def make_timestamps(batch_x, device):
    bs, seq_len = batch_x.shape[0], batch_x.shape[1]
    return torch.zeros(bs, seq_len, 5, dtype=torch.long, device=device)


def prepare_dataset():
    base_train_end = pd.Timestamp("2022-06-30")
    train_end = base_train_end + pd.DateOffset(months=FOLD * FOLD_STEP_MONTHS)
    val_start = train_end + pd.Timedelta(days=1)
    val_end = train_end + pd.DateOffset(months=FOLD_STEP_MONTHS)
    test_start = val_end + pd.Timedelta(days=1)
    test_end = test_start + pd.DateOffset(months=FOLD_STEP_MONTHS) - pd.Timedelta(days=1)

    print(f"Fold {FOLD}:")
    print(f"  Train:   ... -> {train_end.date()}")
    print(f"  Val:     {val_start.date()} -> {val_end.date()}")
    print(f"  Test:    {test_start.date()} -> {test_end.date()}")

    ohlcva_cols = ["open", "high", "low", "close", "volume", "amount"]

    def make_window(df, i):
        x = df.iloc[i:i + LOOKBACK][ohlcva_cols].copy()
        cw = df.iloc[i + LOOKBACK - 1:i + LOOKBACK + PRED_LEN]["close"]
        y = np.log(cw.values[1:] / cw.values[:-1])
        return x.reset_index(drop=True), pd.Series(y)

    train_samples, val_samples, test_samples = [], [], []
    skipped = 0

    for ticker in TICKERS:
        try:
            df = load_cached(ticker, CACHE_DIR)
        except FileNotFoundError:
            skipped += 1
            continue
        df = df.sort_values("timestamps").reset_index(drop=True)

        train_df = df[df["timestamps"] <= train_end]
        if len(train_df) < LOOKBACK + PRED_LEN:
            skipped += 1
            continue
        for i in range(len(train_df) - LOOKBACK - PRED_LEN + 1):
            train_samples.append(make_window(train_df, i))

        val_df = df[(df["timestamps"] >= val_start) & (df["timestamps"] <= val_end)]
        for i in range(0, len(val_df) - LOOKBACK - PRED_LEN + 1, PRED_LEN):
            val_samples.append(make_window(val_df, i))

        test_df = df[(df["timestamps"] >= test_start) & (df["timestamps"] <= test_end)]
        for i in range(0, len(test_df) - LOOKBACK - PRED_LEN + 1, PRED_LEN):
            test_samples.append(make_window(test_df, i))

    print(f"  Train: {len(train_samples)} Val: {len(val_samples)} Test: {len(test_samples)}")
    if skipped:
        print(f"  Skipped: {skipped} tickers")

    return (
        TimeSeriesDataset(train_samples),
        TimeSeriesDataset(val_samples) if val_samples else None,
        TimeSeriesDataset(test_samples),
    )


def train_predictor(train_loader, val_loader, tokenizer, model, device, output_dir, epochs=10, lr=5e-5):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    # SGDR: cosine annealing with warm restarts (2 cycles of 5 epochs each)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=len(train_loader) * 5, T_mult=1, eta_min=1e-6,
    )

    best_val_loss = float("inf")
    patience = 3
    patience_counter = 0

    for epoch in range(epochs):
        epoch_start = time.time()
        train_loss = 0.0
        n_batches = 0
        model.train()

        for batch_x, _ in train_loader:
            batch_x = batch_x.to(device, non_blocking=True)
            with torch.no_grad():
                t0, t1 = tokenizer.encode(batch_x, half=True)
            ti0, ti1 = t0[:, :-1], t1[:, :-1]
            to0, to1 = t0[:, 1:], t1[:, 1:]
            stamps = make_timestamps(ti0, device)

            logits = model(ti0, ti1, stamps)
            loss, _, _ = model.head.compute_loss(logits[0], logits[1], to0, to1)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
            optimizer.step()
            scheduler.step()

            train_loss += loss.item()
            n_batches += 1

        avg_train_loss = train_loss / max(n_batches, 1)

        avg_val_loss = avg_train_loss
        if val_loader is not None:
            model.eval()
            val_loss = 0.0
            val_batches = 0
            with torch.no_grad():
                for batch_x, _ in val_loader:
                    batch_x = batch_x.to(device, non_blocking=True)
                    t0, t1 = tokenizer.encode(batch_x, half=True)
                    ti0, ti1 = t0[:, :-1], t1[:, :-1]
                    to0, to1 = t0[:, 1:], t1[:, 1:]
                    stamps = make_timestamps(ti0, device)
                    logits = model(ti0, ti1, stamps)
                    v_loss, _, _ = model.head.compute_loss(logits[0], logits[1], to0, to1)
                    val_loss += v_loss.item()
                    val_batches += 1
            avg_val_loss = val_loss / max(val_batches, 1)

        elapsed = time.time() - epoch_start
        print(f"  Epoch {epoch+1}/{epochs} — Train: {avg_train_loss:.4f} Val: {avg_val_loss:.4f} ({elapsed:.0f}s)")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0
            ckpt_dir = output_path / "best"
            ckpt_dir.mkdir(exist_ok=True)
            model_config = {k: getattr(model, k) for k in
                ["s1_bits","s2_bits","n_layers","d_model","n_heads","ff_dim",
                 "ffn_dropout_p","attn_dropout_p","resid_dropout_p","token_dropout_p","learn_te"]}
            with open(ckpt_dir / "model_config.json", "w") as f:
                json.dump(model_config, f, indent=2)
            model.save_pretrained(str(ckpt_dir))
            print(f"    → Best saved (val: {best_val_loss:.4f})")
        elif val_loader is not None:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"    → Early stopping (val loss not improving for {patience} epochs)")
                break

    return str(output_path / "best")


def main():
    print("=" * 60)
    print(f"{MODEL_NAME} Fine-Tuning — Fold {FOLD} (GTX 1060)")
    print("=" * 60)
    print(f"Tickers: {len(TICKERS)}")
    print(f"Output:  {OUTPUT_DIR}")
    print()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print()

    t0 = time.time()
    print("── Step 1: Prepare dataset ──")
    train_ds, val_ds, test_ds = prepare_dataset()
    print(f"  Time: {time.time()-t0:.0f}s\n")

    if len(train_ds) == 0:
        print("ERROR: No training samples.")
        sys.exit(1)

    t0 = time.time()
    print("── Step 2: Load tokenizer ──")
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    tokenizer.eval().to(device)
    print(f"  Time: {time.time()-t0:.0f}s\n")

    t0 = time.time()
    print("── Step 3: Load predictor ──")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    model.to(device)
    print(f"  Time: {time.time()-t0:.0f}s\n")

    t0 = time.time()
    print("── Step 4: Create DataLoaders ──")
    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=4, shuffle=False) if val_ds and len(val_ds) > 0 else None
    print(f"  Train batches: {len(train_loader)}")
    print(f"  Val batches:   {len(val_loader) if val_loader else 0}")
    print(f"  Time: {time.time()-t0:.0f}s\n")

    t0 = time.time()
    print("── Step 5: Train predictor ──")
    ckpt_path = train_predictor(train_loader, val_loader, tokenizer, model, device, output_dir=OUTPUT_DIR)
    print(f"  Checkpoint: {ckpt_path}")
    print(f"  Total time: {time.time()-t0:.0f}s\n")

    print("=" * 60)
    print(f"DONE — {MODEL_NAME} fold {FOLD}")
    print(f"Checkpoint: {ckpt_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
