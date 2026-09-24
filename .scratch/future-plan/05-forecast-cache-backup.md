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

## Decision and build (2026-09-23, user "agree" to the 2026-09-23 review, item 1)
- Scope changed: what needs protecting is the **live-track evidence**, not the old look-ahead cache. Protected set: every `data/raw` file, `data/positions/*`, and live forecast folders from 2026-06-01 on.
- Built `scripts/snapshot_live_data.py`: each run writes a new read-only folder `<dest>/<YYYY-MM-DDTHHMMSS>/` (layout = `live_track_review.py --root`), a `sha256sum`-compatible `MANIFEST.sha256` and `snapshot.json`. Files unchanged since the last snapshot are hard-linked, so a daily snapshot costs only what changed. A live forecast file that differs from the previous snapshot is reported as a WARNING (those folders should never change). `--verify DIR` rechecks hashes; `--selftest` uses temp dirs only.
- Cadence: automatic, as STEP4 of `scripts/dashboard.py --generate` ("Run Pipeline"). A snapshot failure is logged (`STEP4_FAILED`) but never fails the pipeline. Not a trading-rule change, so the ticket-11 window is unaffected.
- Target: `~/backups/kronos-th-snapshots` (override with `KRONOS_SNAPSHOT_DIR`). First snapshot 2026-09-23T222128: 15,393 files, 79 forecast folders, 106 MB, hash check OK.
- **Still open (user):** this is the same physical disk as the repo, so it protects against deletion and against `data/raw` drift but not against disk loss. Add an off-machine copy (Drive, external disk or a private Kaggle dataset) of `~/backups/kronos-th-snapshots`, at least before each review date.
