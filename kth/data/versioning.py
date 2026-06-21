"""Data cache versioning — write + verify a manifest of per-ticker hashes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, date
from pathlib import Path


def _hash_parquet(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def write_manifest(cache_dir: Path, tickers: list[str]) -> dict:
    """Write manifest.json with per-ticker row count + SHA256 + date.
    Called by loader.download_universe after a fresh download."""
    import pandas as pd
    cache_dir = Path(cache_dir)
    manifest = {
        "written_at": datetime.now().isoformat(),
        "download_date": str(date.today()),
        "tickers": {},
    }
    for ticker in tickers:
        safe = ticker.replace("^", "_").replace("=", "_")
        p = cache_dir / f"{safe}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        manifest["tickers"][ticker] = {
            "rows": len(df),
            "sha256_short": _hash_parquet(p),
            "last_date": str(df["timestamps"].iloc[-1]) if "timestamps" in df.columns else None,
        }
    out = cache_dir / "manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def verify_manifest(cache_dir: Path, strict: bool = False) -> dict:
    """Verify cached parquets match manifest.json.
    Returns {'ok': bool, 'mismatches': list[str], 'missing': list[str]}.
    If strict=True, raise on mismatch. Otherwise warn."""
    cache_dir = Path(cache_dir)
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "mismatches": [], "missing": [],
                "error": "No manifest.json — run download_universe first"}
    with open(manifest_path) as f:
        manifest = json.load(f)
    mismatches, missing = [], []
    for ticker, meta in manifest["tickers"].items():
        safe = ticker.replace("^", "_").replace("=", "_")
        p = cache_dir / f"{safe}.parquet"
        if not p.exists():
            missing.append(ticker)
            continue
        actual_hash = _hash_parquet(p)
        if actual_hash != meta["sha256_short"]:
            mismatches.append(f"{ticker}: hash {actual_hash} != manifest {meta['sha256_short']}")
    result = {"ok": not (mismatches or missing), "mismatches": mismatches, "missing": missing}
    if strict and (mismatches or missing):
        raise RuntimeError(f"Data cache mismatch: {result}")
    return result
