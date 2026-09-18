# Ticket 05: Backup policy for the local Forecast Cache

**Status:** Scoped, not filed. Type: decision, then a small script. No GPU.

## Problem

`data/forecast_cache/` (~1.5 GB, 2020-01-01 to 2026-07-25) is a single local
copy and is git-ignored. Regenerating it takes 8-12 T4 GPU-hours per year
(Phase 2 plan estimate). Ticket 03 depends on it. The BANPU.BK incident
(`CLAUDE.md`, 2026-07-25) already lost a history to "git-ignored, no backup".
`data/raw/*.parquet` has the same exposure, though it is cheap to re-download.

## Decide

1. Target: an external disk, cloud storage (Drive), or a private Kaggle
   dataset.
2. Cadence: after each significant cache extension, or on a schedule.
3. Integrity: `kth/data/versioning.py` already writes/verifies a SHA-256
   manifest for `data/raw`; consider the same for the cache.

Build only after the decision. Keep it a script, not a service.
