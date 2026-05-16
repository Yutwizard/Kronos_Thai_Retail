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
        instance._load_or_cache_model(key=model_name, is_checkpoint=False)
        slug = model_name.replace("/", "_").replace("\\", "_")
        hash_file = Path("./checkpoints") / slug / "commit_hash.txt"
        if hash_file.exists():
            commit_hash = hash_file.read_text().strip()
            instance.model_name = f"{model_name}@{commit_hash[:7]}"
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

        from kronos import KronosPredictor

        if is_checkpoint:
            self._predictor = KronosPredictor.from_pretrained(key, device=self.device)
        else:
            local_path = self._resolve_local_checkpoint(key)
            self._predictor = KronosPredictor.from_pretrained(str(local_path), device=self.device)

        _MODEL_CACHE[key] = self._predictor

    @staticmethod
    def _resolve_local_checkpoint(model_name: str) -> Path:
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
    ) -> ForecastResult:
        if pred_lens is None:
            pred_lens = [5, 20]

        max_pred_len = max(pred_lens)

        if isinstance(ticker_or_df, str):
            from kth.data.loader import load_cached
            df = load_cached(ticker_or_df, self.cache_dir)
            ticker = ticker_or_df
        else:
            df = ticker_or_df.copy()
            self._validate_columns(df)
            ticker = "<dataframe>"

        if len(df) < lookback:
            raise ValueError(
                f"lookback={lookback} exceeds available rows ({len(df)}). "
                "Reduce lookback or extend data history."
            )
        x_df = df.tail(lookback)
        x_timestamps = x_df["timestamps"].reset_index(drop=True)
        x_ohlcva = x_df[["open", "high", "low", "close", "volume", "amount"]]

        y_timestamps = pd.Series(range(1, max_pred_len + 1))

        raw_samples = self._predictor.predict_batch(
            x_df=x_ohlcva,
            x_timestamp=x_timestamps,
            y_timestamp=y_timestamps,
            n_samples=n_samples,
        )

        horizons = {}
        for pl in pred_lens:
            samples_for_len = raw_samples[:, :pl]
            horizons[pl] = self._build_horizon(y_timestamps.iloc[:pl], samples_for_len)

        return ForecastResult(
            ticker=ticker,
            model_name=self.model_name,
            generated_at=pd.Timestamp.now(),
            lookback_end=x_timestamps.iloc[-1],
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
    def _build_horizon(y_ts: pd.Series, samples: np.ndarray) -> HorizonForecast:
        n_samples, pred_len = samples.shape
        pcts = [5, 25, 50, 75, 95]
        summary_data = {"timestamps": y_ts.values}
        for p in pcts:
            summary_data[f"p{p}"] = np.percentile(samples, p, axis=0)
        summary_data["mean"] = np.mean(samples, axis=0)
        summary = pd.DataFrame(summary_data)

        sample_data = {"timestamps": y_ts.values}
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
    ) -> dict[str, ForecastResult]:
        if pred_lens is None:
            pred_lens = [5, 20]

        results: dict[str, ForecastResult] = {}
        for i, item in enumerate(tickers_or_dfs):
            if isinstance(item, str):
                key = item
                input_val = item
            else:
                key = f"df_{i}"
                input_val = item
            results[key] = self.forecast(input_val, pred_lens=pred_lens, n_samples=n_samples, lookback=lookback)
        return results
