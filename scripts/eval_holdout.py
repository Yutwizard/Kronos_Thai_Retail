"""
Holdout evaluation on 2025 data for the thai_equity fine-tuned model
(us_equity/crypto archived 2026-07-16, see archive/other-asset-classes/).
Usage: venv/bin/python scripts/eval_holdout.py [model_name]
"""
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kronos_repo"))
from kth.data.universe import UNIVERSE
from kth.data.loader import load_cached
from kth.models.kronos_wrapper import KronosTH
from kth.models.finetune import load_finetuned_checkpoint

LOOKBACK = 400; PRED_LEN = 20; CACHE_DIR = "./data/raw"
MODEL_TICKERS = {
    "thai_equity": [t for t,_,_ in UNIVERSE["thai_equity"]],
}


HOLDOUT_START = {"thai_equity": "2024-07-01"}


def evaluate(th, tickers, model_name):
    hits = 0; total = 0
    start_date = HOLDOUT_START.get(model_name, "2025-01-01")
    for ticker in tickers:
        try:
            df = load_cached(ticker, CACHE_DIR)
        except FileNotFoundError:
            continue
        df = df.sort_values("timestamps").reset_index(drop=True)
        holdout = df[df["timestamps"] >= start_date]
        if len(holdout) < LOOKBACK + PRED_LEN:
            continue
        for i in range(0, len(holdout) - LOOKBACK - PRED_LEN + 1, PRED_LEN):
            ctx = holdout.iloc[i:i + LOOKBACK].copy().reset_index(drop=True)
            gt = holdout.iloc[i + LOOKBACK:i + LOOKBACK + PRED_LEN]
            actual_return = float(np.log(gt["close"].values[-1] / gt["close"].values[0]))
            try:
                r = th.forecast(ticker_or_df=ctx, pred_lens=[PRED_LEN],
                                n_samples=10, lookback=LOOKBACK)
                pred_close = float(r.horizons[PRED_LEN].summary["p50"].iloc[-1])
                pred_return = np.log(pred_close / float(ctx["close"].iloc[-1]))
                if np.sign(pred_return) == np.sign(actual_return):
                    hits += 1
                total += 1
            except Exception:
                pass
    return hits, total


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "all"
    models = [model_name] if model_name != "all" else ["thai_equity"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}\n")

    print("Zero-shot...", end=" ", flush=True)
    zs = KronosTH.from_pretrained("NeoQuasar/Kronos-small", device=device)
    print("done")

    for m in models:
        print(f"\n{'='*60}\n{m} — Holdout 2025\n{'='*60}")
        tickers = MODEL_TICKERS[m]
        zs_h, zs_t = evaluate(zs, tickers, m)
        print(f"  ZS: {zs_h}/{zs_t} = {zs_h/max(zs_t,1):.1%}")

        folds = []
        for f in range(3):
            ckpt_dir = f"./checkpoints/{m}/fold{f}/best"
            if not (Path(ckpt_dir) / "model_config.json").exists():
                continue
            print(f"  Fold {f}...", end=" ", flush=True)
            ft = load_finetuned_checkpoint(ckpt_dir, device)
            ft_h, ft_t = evaluate(ft, tickers, m)
            rate = ft_h / max(ft_t, 1)
            folds.append({"f": f, "h": ft_h, "t": ft_t, "r": rate})
            print(f" {ft_h}/{ft_t} = {rate:.1%}")

        zr = zs_h / max(zs_t, 1)
        print(f"\n  {'Fold':<6}{'Hits':<8}{'Total':<8}{'Rate':<10}{'Δ':<10}")
        print(f"  {'ZS':<6}{zs_h:<8}{zs_t:<8}{zr:<10.1%}{'—':<10}")
        for fd in folds:
            d = fd["r"] - zr
            lbl = f"F{fd['f']}"
            print(f"  {lbl:<6}{fd['h']:<8}{fd['t']:<8}{fd['r']:<10.1%}{d:<+9.1%} ")

    print(f"\n{'='*60}\nDONE\n{'='*60}")

if __name__ == "__main__":
    main()
