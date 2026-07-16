"""
Train crypto model fold N locally on GTX 1060 (6GB VRAM).
Uses the actual Kronos training API (no fit() method).
Usage: venv/bin/python scripts/train_crypto_fold0.py [fold_number]
"""
import time
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

# Add Kronos repo to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kronos_repo"))

from kth.data.universe import UNIVERSE
from kth.data.loader import load_cached
from kth.models._kronos_bridge import KronosTokenizer, Kronos, KronosPredictor

CRYPTO_TICKERS = [t for t, _, _ in UNIVERSE["crypto"]]
FOLD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
CACHE_DIR = "./data/raw"
OUTPUT_DIR = f"./checkpoints/crypto/fold{FOLD}"
LOOKBACK = 400
PRED_LEN = 20
SEED = 42


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
    """Build temporal stamps [batch, seq_len, 5] = [minute, hour, weekday, day, month]."""
    bs, seq_len = batch_x.shape[0], batch_x.shape[1]
    return torch.zeros(bs, seq_len, 5, dtype=torch.long, device=device)


def prepare_crypto_dataset():
    """Build train/val/test splits for crypto fold 0."""
    base_train_end = pd.Timestamp("2022-06-30")
    train_end = base_train_end
    val_start = train_end + pd.Timedelta(days=1)
    val_end = train_end + pd.DateOffset(months=6)
    test_start = val_end + pd.Timedelta(days=1)
    test_end = test_start + pd.DateOffset(months=6) - pd.Timedelta(days=1)

    print(f"Fold {FOLD}:")
    print(f"  Train:   ... -> {train_end.date()}")
    print(f"  Val:     {val_start.date()} -> {val_end.date()}")
    print(f"  Test:    {test_start.date()} -> {test_end.date()}")

    ohlcva_cols = ["open", "high", "low", "close", "volume", "amount"]

    def make_window(df, i):
        x = df.iloc[i:i + LOOKBACK][ohlcva_cols].copy()
        close_window = df.iloc[i + LOOKBACK - 1:i + LOOKBACK + PRED_LEN]["close"]
        y = np.log(close_window.values[1:] / close_window.values[:-1])
        return x.reset_index(drop=True), pd.Series(y)

    train_samples = []
    val_samples = []
    test_samples = []
    skipped = 0

    for ticker in CRYPTO_TICKERS:
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
            x, y = make_window(train_df, i)
            train_samples.append((x, y))

        val_df = df[(df["timestamps"] >= val_start) & (df["timestamps"] <= val_end)]
        for i in range(0, len(val_df) - LOOKBACK - PRED_LEN + 1, PRED_LEN):
            x, y = make_window(val_df, i)
            val_samples.append((x, y))

        test_df = df[(df["timestamps"] >= test_start) & (df["timestamps"] <= test_end)]
        for i in range(0, len(test_df) - LOOKBACK - PRED_LEN + 1, PRED_LEN):
            x, y = make_window(test_df, i)
            test_samples.append((x, y))

    print(f"  Train: {len(train_samples)} samples")
    print(f"  Val:   {len(val_samples)} samples")
    print(f"  Test:  {len(test_samples)} samples")
    if skipped:
        print(f"  Skipped: {skipped} tickers")

    return (
        TimeSeriesDataset(train_samples),
        TimeSeriesDataset(val_samples) if val_samples else None,
        TimeSeriesDataset(test_samples),
    )


def train_predictor(train_loader, val_loader, tokenizer, model, device, output_dir, epochs, lr):
    """Custom training loop for Kronos predictor."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=lr,
        steps_per_epoch=len(train_loader), epochs=epochs,
        pct_start=0.03, div_factor=10,
    )

    best_val_loss = float("inf")

    for epoch in range(epochs):
        epoch_start = time.time()
        train_loss = 0.0
        n_batches = 0

        model.train()
        for batch_x, _ in train_loader:
            batch_x = batch_x.to(device, non_blocking=True)

            with torch.no_grad():
                token_seq_0, token_seq_1 = tokenizer.encode(batch_x, half=True)

            token_in_0 = token_seq_0[:, :-1]
            token_in_1 = token_seq_1[:, :-1]
            token_out_0 = token_seq_0[:, 1:]
            token_out_1 = token_seq_1[:, 1:]

            timestamps = make_timestamps(token_in_0, device)
            logits = model(token_in_0, token_in_1, timestamps)
            loss, s1_loss, s2_loss = model.head.compute_loss(
                logits[0], logits[1], token_out_0, token_out_1
            )

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
            optimizer.step()
            scheduler.step()

            train_loss += loss.item()
            n_batches += 1

        avg_train_loss = train_loss / max(n_batches, 1)

        # Validation
        val_loss = 0.0
        val_batches = 0
        if val_loader is not None:
            model.eval()
            with torch.no_grad():
                for batch_x, _ in val_loader:
                    batch_x = batch_x.to(device, non_blocking=True)
                    token_seq_0, token_seq_1 = tokenizer.encode(batch_x, half=True)
                    token_in_0 = token_seq_0[:, :-1]
                    token_in_1 = token_seq_1[:, :-1]
                    token_out_0 = token_seq_0[:, 1:]
                    token_out_1 = token_seq_1[:, 1:]
                    timestamps = make_timestamps(token_in_0, device)
                    logits = model(token_in_0, token_in_1, timestamps)
                    v_loss, _, _ = model.head.compute_loss(
                        logits[0], logits[1], token_out_0, token_out_1
                    )
                    val_loss += v_loss.item()
                    val_batches += 1
            avg_val_loss = val_loss / max(val_batches, 1)
        else:
            avg_val_loss = avg_train_loss

        elapsed = time.time() - epoch_start
        print(f"  Epoch {epoch+1}/{epochs} — "
              f"Train loss: {avg_train_loss:.4f}, "
              f"Val loss: {avg_val_loss:.4f}, "
              f"Time: {elapsed:.0f}s")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            ckpt_dir = output_path / "best"
            ckpt_dir.mkdir(exist_ok=True)
            # Save Kronos model config
            model_config = {
                "s1_bits": model.s1_bits,
                "s2_bits": model.s2_bits,
                "n_layers": model.n_layers,
                "d_model": model.d_model,
                "n_heads": model.n_heads,
                "ff_dim": model.ff_dim,
                "ffn_dropout_p": model.ffn_dropout_p,
                "attn_dropout_p": model.attn_dropout_p,
                "resid_dropout_p": model.resid_dropout_p,
                "token_dropout_p": model.token_dropout_p,
                "learn_te": model.learn_te,
            }
            with open(ckpt_dir / "model_config.json", "w") as f:
                json.dump(model_config, f, indent=2)
            model.save_pretrained(str(ckpt_dir))
            print(f"    → Best checkpoint saved (val loss: {best_val_loss:.4f})")

    return str(output_path / "best")


def main():
    print("=" * 60)
    print("Crypto Fine-Tuning — Fold 0 (GTX 1060)")
    print("=" * 60)
    print(f"Tickers: {len(CRYPTO_TICKERS)}")
    print(f"Output:  {OUTPUT_DIR}")
    print()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print()

    # ── Step 1: Prepare dataset ──
    t0 = time.time()
    print("── Step 1: Prepare dataset ──")
    train_ds, val_ds, test_ds = prepare_crypto_dataset()
    print(f"  Time: {time.time() - t0:.0f}s")
    print()

    if len(train_ds) == 0:
        print("ERROR: No training samples.")
        sys.exit(1)

    # ── Step 2: Load pre-trained tokenizer ──
    t0 = time.time()
    print("── Step 2: Load tokenizer ──")
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    tokenizer.eval().to(device)
    print(f"  Time: {time.time() - t0:.0f}s")
    print()

    # ── Step 3: Load predictor model ──
    t0 = time.time()
    print("── Step 3: Load predictor ──")
    model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    model.to(device)
    print(f"  Time: {time.time() - t0:.0f}s")
    print()

    # ── Step 4: Create DataLoaders ──
    t0 = time.time()
    print("── Step 4: Create DataLoaders ──")
    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=4, shuffle=False) if val_ds and len(val_ds) > 0 else None
    print(f"  Train batches: {len(train_loader)}")
    print(f"  Val batches:   {len(val_loader) if val_loader else 0}")
    print(f"  Time: {time.time() - t0:.0f}s")
    print()

    # ── Step 5: Train ──
    t0 = time.time()
    print("── Step 5: Train predictor ──")
    ckpt_path = train_predictor(
        train_loader, val_loader, tokenizer, model, device,
        output_dir=OUTPUT_DIR,
        epochs=5,
        lr=5e-5,
    )
    print(f"  Checkpoint: {ckpt_path}")
    print(f"  Time: {time.time() - t0:.0f}s")
    print()

    # ── Step 6: Quick evaluation ──
    t0 = time.time()
    print("── Step 6: Quick evaluation ──")
    if len(test_ds) == 0:
        print("  No test samples — skipping evaluation")
    else:
        k_ft = KronosPredictor(ckpt_path, device=device)
        k_zs = KronosPredictor.from_pretrained("NeoQuasar/Kronos-small", device=device)

        hits_zs = 0
        hits_ft = 0
        total = 0
        n_eval = min(20, len(test_ds))

        for idx in range(n_eval):
            x_df, y_actual = test_ds.samples[idx]
            actual_return = float(y_actual.sum())

            try:
                r_zs = k_zs.forecast(x_df, pred_lens=[PRED_LEN], n_samples=10, lookback=LOOKBACK)
                zs_close = float(r_zs.horizons[PRED_LEN].summary["p50"].iloc[-1])
                zs_return = np.log(zs_close / float(x_df["close"].iloc[-1]))
                if np.sign(zs_return) == np.sign(actual_return):
                    hits_zs += 1
            except Exception:
                pass

            try:
                r_ft = k_ft.forecast(x_df, pred_lens=[PRED_LEN], n_samples=10, lookback=LOOKBACK)
                ft_close = float(r_ft.horizons[PRED_LEN].summary["p50"].iloc[-1])
                ft_return = np.log(ft_close / float(x_df["close"].iloc[-1]))
                if np.sign(ft_return) == np.sign(actual_return):
                    hits_ft += 1
            except Exception:
                pass
            total += 1

        print(f"  Samples: {total}")
        print(f"  Zero-shot hit-rate: {hits_zs}/{total} = {hits_zs/max(total,1):.1%}")
        print(f"  Fine-tuned hit-rate: {hits_ft}/{total} = {hits_ft/max(total,1):.1%}")
    print(f"  Time: {time.time() - t0:.0f}s")
    print()

    print("=" * 60)
    print("DONE")
    print(f"Checkpoint: {ckpt_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
