"""Thin wrapper around KronosPredictor with caching, batch, and structured output."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class HorizonForecast:
    pred_len: int
    summary: pd.DataFrame    # timestamps, p5, p25, p50, p75, p95, mean
    samples: pd.DataFrame    # timestamps, s0, s1, ..., s_{n_samples-1}


@dataclass
class ForecastResult:
    ticker: str
    model_name: str
    generated_at: pd.Timestamp
    lookback_end: pd.Timestamp
    horizons: dict[int, HorizonForecast]


# Module-level cache
_MODEL_CACHE: dict[str, object] = {}


class KronosTH:
    """Kronos forecasting wrapper for the Thai-retail universe."""

    def __init__(
        self,
        model_name: str = "NeoQuasar/Kronos-small",
        device: str = "auto",
        cache_dir: str = "./data/raw",
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir

        if device == "auto":
            self.device = "cuda" if self._cuda_available() else "cpu"
        else:
            self.device = device

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    @classmethod
    def from_pretrained(cls, model_name: str = "NeoQuasar/Kronos-small", **kwargs) -> "KronosTH":
        instance = cls(model_name=model_name, **kwargs)
        instance._load_or_cache_model(key=model_name)
        return instance

    @classmethod
    def from_checkpoint(cls, checkpoint_path: str, **kwargs) -> "KronosTH":
        instance = cls(model_name=checkpoint_path, **kwargs)
        instance._load_or_cache_model(key=checkpoint_path, is_checkpoint=True)
        return instance

    def _load_or_cache_model(self, key: str, is_checkpoint: bool = False) -> None:
        if key in _MODEL_CACHE:
            self._predictor = _MODEL_CACHE[key]
            return

        from kth.models._kronos_bridge import KronosPredictor, KronosTokenizer, Kronos

        # Auto-derive tokenizer name: Kronos-small -> Kronos-Tokenizer-base
        if not is_checkpoint:
            tokenizer_name = "NeoQuasar/Kronos-Tokenizer-base"
            print(f"Loading tokenizer: {tokenizer_name} ...")
            tokenizer = KronosTokenizer.from_pretrained(tokenizer_name)
            print(f"Loading model: {key} ...")
            model = Kronos.from_pretrained(key)
        else:
            # Checkpoint: both tokenizer and model in same directory
            ckpt = Path(key)
            tokenizer = KronosTokenizer.from_pretrained(key)
            model = Kronos.from_pretrained(key)

        tokenizer.eval()
        model.eval()
        self._predictor = KronosPredictor(model=model, tokenizer=tokenizer, device=self.device)
        _MODEL_CACHE[key] = self._predictor

    @staticmethod
    def _resolve_hf_checkpoint(model_name: str) -> Path:
        import shutil
        from huggingface_hub import snapshot_download, repo_info

        slug = model_name.replace("/", "_").replace("\\", "_")
        local_dir = Path("./checkpoints") / slug
        hash_file = local_dir / "commit_hash.txt"

        if local_dir.exists() and hash_file.exists() and hash_file.read_text().strip():
            return local_dir

        info = repo_info(model_name, repo_type="model")
        commit_hash = info.sha

        hf_cached = snapshot_download(repo_id=model_name, revision=commit_hash)
        if local_dir.exists():
            shutil.rmtree(local_dir)
        shutil.copytree(hf_cached, local_dir)

        hash_file.write_text(commit_hash)
        return local_dir

    def forecast(
        self,
        ticker_or_df: str | pd.DataFrame,
        pred_lens: list[int] | None = None,
        n_samples: int = 50,
        lookback: int = 400,
        calendar_freq: str = "B",
    ) -> ForecastResult:
        if pred_lens is None:
            pred_lens = [5, 20]

        max_pred_len = max(pred_lens)

        # 1. Input resolution + calendar detection
        if isinstance(ticker_or_df, str):
            from kth.data.loader import load_cached
            df = load_cached(ticker_or_df, self.cache_dir)
            ticker = ticker_or_df
            if calendar_freq == "B":
                from kth.data.universe import get_ticker_class
                if get_ticker_class(ticker) == "crypto":
                    calendar_freq = "D"
        else:
            df = ticker_or_df.copy()
            self._validate_columns(df)
            ticker = "<dataframe>"

        # 2. Context window
        if len(df) < lookback:
            raise ValueError(
                f"lookback={lookback} exceeds available rows ({len(df)}). "
                "Reduce lookback or extend data history."
            )
        x_df = df.tail(lookback).reset_index(drop=True)
        x_timestamps = x_df["timestamps"]
        x_ohlcva = x_df[["open", "high", "low", "close", "volume", "amount"]]
        last_ts = x_timestamps.iloc[-1]

        # 3. Future timestamps (asset-class-aware calendar)
        y_timestamps = pd.Series(
            pd.date_range(start=last_ts + pd.Timedelta(days=1), periods=max_pred_len, freq=calendar_freq)
        )

        # 4. Multi-sample forward pass (Kronos predict() is single-sample; loop n_samples times)
        raw_close_samples = np.zeros((n_samples, max_pred_len))
        for s in range(n_samples):
            pred_df = self._predictor.predict(
                df=x_ohlcva,
                x_timestamp=x_timestamps,
                y_timestamp=y_timestamps,
                pred_len=max_pred_len,
                sample_count=1,
                verbose=False,
            )
            raw_close_samples[s, :] = pred_df["close"].values

        # 5. Build HorizonForecast per pred_len
        horizons = {}
        for pl in pred_lens:
            samples_for_len = raw_close_samples[:, :pl]
            horizons[pl] = self._build_horizon(pl, samples_for_len)

        return ForecastResult(
            ticker=ticker,
            model_name=self.model_name,
            generated_at=pd.Timestamp.now(),
            lookback_end=last_ts,
            horizons=horizons,
        )

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        required = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing columns: {missing}. Expected: {', '.join(required)}."
            )

    @staticmethod
    def _build_horizon(pred_len: int, samples: np.ndarray) -> HorizonForecast:
        n_samples = samples.shape[0]
        pcts = [5, 25, 50, 75, 95]
        summary_data = {"timestamps": range(1, pred_len + 1)}
        for p in pcts:
            summary_data[f"p{p}"] = np.percentile(samples, p, axis=0)
        summary_data["mean"] = np.mean(samples, axis=0)
        summary = pd.DataFrame(summary_data)

        sample_data = {"timestamps": range(1, pred_len + 1)}
        for i in range(n_samples):
            sample_data[f"s{i}"] = samples[i, :]
        samples_df = pd.DataFrame(sample_data)

        return HorizonForecast(pred_len=pred_len, summary=summary, samples=samples_df)

    def forecast_batch(
        self,
        tickers_or_dfs: list[str | pd.DataFrame],
        pred_lens: list[int] | None = None,
        n_samples: int = 50,
        lookback: int = 400,
        calendar_freq: str = "B",
    ) -> dict[str, ForecastResult]:
        if pred_lens is None:
            pred_lens = [5, 20]

        max_pred_len = max(pred_lens)

        # Auto-detect calendar: if any ticker is crypto, use 7-day freq
        if calendar_freq == "B":
            from kth.data.universe import get_ticker_class
            for item in tickers_or_dfs:
                if isinstance(item, str) and get_ticker_class(item) == "crypto":
                    calendar_freq = "D"
                    break

        # 1. Resolve all inputs and prepare data
        keys: list[str] = []
        df_list: list[pd.DataFrame] = []
        x_stamp_list: list[pd.Series] = []
        y_stamp_list: list[pd.Series] = []
        last_ts_list: list[pd.Timestamp] = []

        for i, item in enumerate(tickers_or_dfs):
            if isinstance(item, str):
                from kth.data.loader import load_cached
                try:
                    df = load_cached(item, self.cache_dir)
                except FileNotFoundError:
                    continue
                key = item
            else:
                df = item.copy()
                self._validate_columns(df)
                key = f"df_{i}"

            if len(df) < lookback:
                continue

            x_df = df.tail(lookback).reset_index(drop=True)
            x_stamp = x_df["timestamps"]
            x_ohlcva = x_df[["open", "high", "low", "close", "volume", "amount"]]
            last_ts = x_stamp.iloc[-1]

            y_stamp = pd.Series(
                pd.date_range(start=last_ts + pd.Timedelta(days=1), periods=max_pred_len, freq=calendar_freq)
            )

            keys.append(key)
            df_list.append(x_ohlcva)
            x_stamp_list.append(x_stamp)
            y_stamp_list.append(y_stamp)
            last_ts_list.append(last_ts)

        if not keys:
            return {}

        # 2. Batched multi-sample forward pass
        n_tickers = len(keys)
        all_samples = np.zeros((n_tickers, n_samples, max_pred_len))
        for s in range(n_samples):
            pred_dfs = self._predictor.predict_batch(
                df_list, x_stamp_list, y_stamp_list,
                pred_len=max_pred_len, sample_count=1, verbose=False,
            )
            for t_idx in range(n_tickers):
                all_samples[t_idx, s, :] = pred_dfs[t_idx]["close"].values

        # 3. Build ForecastResults
        results: dict[str, ForecastResult] = {}
        for t_idx, key in enumerate(keys):
            horizons = {}
            for pl in pred_lens:
                samples_for_len = all_samples[t_idx, :, :pl]
                horizons[pl] = self._build_horizon(pl, samples_for_len)

            results[key] = ForecastResult(
                ticker=key,
                model_name=self.model_name,
                generated_at=pd.Timestamp.now(),
                lookback_end=last_ts_list[t_idx],
                horizons=horizons,
            )

        return results
