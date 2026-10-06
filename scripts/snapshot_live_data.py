"""Append-only snapshot of the live paper-track evidence (ticket .scratch/future-plan/05, 2026-09-23).

Why: the live track is the only clean forward test (ticket 11), but its inputs are git-ignored and
`data/raw/` is rewritten by every "Run Pipeline" (CLAUDE.md, 2026-09-23 finding). Each run of this script
freezes what exists now into a new timestamped folder that is never modified afterwards:

    <dest>/<YYYY-MM-DDTHHMMSS>/
        raw/*.parquet, raw/manifest.json            every cached price file
        positions/*                                 trade log, portfolio state, trade tickets
        forecast_cache/NeoQuasar_Kronos-small/<date>/   live forecast folders from LIVE_START on
        forecast_cache_superseded/...                   earlier same-day runs, archived by the pipeline
        MANIFEST.sha256                             `sha256sum -c` compatible
        snapshot.json                               created_at, git commit, counts, changed files

The layout matches `scripts/live_track_review.py --root`, so a review reads a frozen snapshot with
    python scripts/live_track_review.py --review six-month --root <dest>/<snapshot>
Files identical to the previous snapshot are hard-linked (no extra disk); every file is made read-only.
A forecast file that differs from the previous snapshot is reported as a WARNING: live forecast folders
are supposed to be immutable once written.

    python scripts/snapshot_live_data.py                 # snapshot data/ into the default dest
    python scripts/snapshot_live_data.py --verify DIR    # re-check a snapshot against its MANIFEST
    python scripts/snapshot_live_data.py --selftest      # temp dirs only, never touches real data
Default dest: $KRONOS_SNAPSHOT_DIR, else ~/backups/kronos-th-snapshots (outside the repo, same disk).
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

MODEL_DIR = "NeoQuasar_Kronos-small"
LIVE_START = "2026-06-01"  # first live folders; earlier folders are the look-ahead-contaminated backtest cache
DEFAULT_DEST = Path(os.environ.get("KRONOS_SNAPSHOT_DIR", Path.home() / "backups" / "kronos-th-snapshots"))
MANIFEST = "MANIFEST.sha256"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(data_root: Path) -> dict[str, Path]:
    """Map snapshot-relative path -> source file."""
    files = {}
    for p in sorted((data_root / "raw").glob("*.parquet")):
        files[f"raw/{p.name}"] = p
    if (data_root / "raw" / "manifest.json").exists():
        files["raw/manifest.json"] = data_root / "raw" / "manifest.json"
    for p in sorted((data_root / "positions").glob("*")):
        if p.is_file():
            files[f"positions/{p.name}"] = p
    fc_root = data_root / "forecast_cache" / MODEL_DIR
    if fc_root.exists():
        for folder in sorted(d for d in fc_root.iterdir() if d.is_dir() and d.name >= LIVE_START):
            for p in sorted(folder.iterdir()):
                if p.is_file():
                    files[f"forecast_cache/{MODEL_DIR}/{folder.name}/{p.name}"] = p
    sup_root = data_root / "forecast_cache_superseded" / MODEL_DIR  # same-day reruns archive, never delete
    if sup_root.exists():
        for folder in sorted(d for d in sup_root.iterdir() if d.is_dir()):
            for p in sorted(folder.iterdir()):
                if p.is_file():
                    files[f"forecast_cache_superseded/{MODEL_DIR}/{folder.name}/{p.name}"] = p
    return files


def read_manifest(snap: Path) -> dict[str, str]:
    out = {}
    for line in (snap / MANIFEST).read_text().splitlines():
        digest, rel = line.split("  ", 1)
        out[rel] = digest
    return out


def latest_snapshot(dest: Path) -> Path | None:
    snaps = sorted(d for d in dest.iterdir() if d.is_dir() and (d / MANIFEST).exists()) if dest.exists() else []
    return snaps[-1] if snaps else None


def git_commit(repo: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def snapshot(data_root: Path, dest: Path, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    files = collect(data_root)
    if not files:
        raise SystemExit(f"nothing to snapshot under {data_root}")
    prev = latest_snapshot(dest)
    prev_hashes = read_manifest(prev) if prev else {}
    snap = dest / now.strftime("%Y-%m-%dT%H%M%S")
    tmp = dest / f".{snap.name}.partial"
    if snap.exists():
        raise SystemExit(f"snapshot already exists: {snap}")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    lines, linked, changed_fc, new = [], 0, [], 0
    for rel, src in files.items():
        digest = sha256(src)
        out = tmp / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if prev_hashes.get(rel) == digest:
            os.link(prev / rel, out)
            linked += 1
        else:
            shutil.copy2(src, out)
            os.chmod(out, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            if rel in prev_hashes and rel.startswith("forecast_cache/"):
                changed_fc.append(rel)
            new += 1
        lines.append(f"{digest}  {rel}")

    (tmp / MANIFEST).write_text("\n".join(lines) + "\n")
    meta = {
        "created_at": now.isoformat(timespec="seconds"),
        "source": str(data_root.resolve()),
        "git_commit": git_commit(data_root.resolve().parent),
        "previous_snapshot": prev.name if prev else None,
        "files": len(files), "new_or_changed": new, "hardlinked_unchanged": linked,
        "forecast_folders": len({r.split("/")[2] for r in files if r.startswith("forecast_cache/")}),
        "forecast_files_changed_since_previous": changed_fc,
    }
    (tmp / "snapshot.json").write_text(json.dumps(meta, indent=2) + "\n")
    tmp.rename(snap)  # the folder only appears under its final name once complete

    print(f"snapshot {snap}: {len(files)} files, {new} new/changed, {linked} hard-linked, "
          f"{meta['forecast_folders']} forecast folders")
    if changed_fc:
        print(f"WARNING: {len(changed_fc)} live forecast file(s) changed since {prev.name}; "
              f"first: {changed_fc[:3]} (listed in snapshot.json)")
    return snap


def verify(snap: Path) -> list[str]:
    bad = []
    for rel, digest in read_manifest(snap).items():
        p = snap / rel
        if not p.exists():
            bad.append(f"missing {rel}")
        elif sha256(p) != digest:
            bad.append(f"hash mismatch {rel}")
    return bad


def selftest() -> None:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        data, dest = d / "data", d / "snaps"
        fc = data / "forecast_cache" / MODEL_DIR
        for folder in ("2026-05-15", "2026-06-29"):
            (fc / folder).mkdir(parents=True)
            (fc / folder / "A.BK.parquet").write_bytes(folder.encode())
        (data / "raw").mkdir(); (data / "raw" / "A.BK.parquet").write_bytes(b"v1")
        (data / "positions").mkdir(); (data / "positions" / "trade_log.csv").write_text("date\n")

        sup = data / "forecast_cache_superseded" / MODEL_DIR / "2026-06-29_073500"
        sup.mkdir(parents=True); (sup / "A.BK.parquet").write_bytes(b"morning")
        s1 = snapshot(data, dest, datetime(2026, 9, 23, 23, 50))
        assert (s1 / "forecast_cache_superseded" / MODEL_DIR / "2026-06-29_073500" / "A.BK.parquet").read_bytes() == b"morning"
        assert not (s1 / "forecast_cache" / MODEL_DIR / "2026-05-15").exists(), "pre-live folder copied"
        assert (s1 / "raw" / "A.BK.parquet").read_bytes() == b"v1" and verify(s1) == []
        assert not os.access(s1 / "raw" / "A.BK.parquet", os.W_OK) or os.geteuid() == 0, "file left writable"

        (data / "raw" / "A.BK.parquet").write_bytes(b"v2")  # raw drifts, as after a Run Pipeline
        (fc / "2026-06-29" / "A.BK.parquet").write_bytes(b"rewritten")  # a live forecast is rewritten
        s2 = snapshot(data, dest, datetime(2026, 9, 24, 23, 50))
        assert (s1 / "raw" / "A.BK.parquet").read_bytes() == b"v1", "older snapshot modified"
        assert (s2 / "raw" / "A.BK.parquet").read_bytes() == b"v2"
        assert os.stat(s2 / "positions" / "trade_log.csv").st_ino == os.stat(s1 / "positions" / "trade_log.csv").st_ino
        meta = json.loads((s2 / "snapshot.json").read_text())
        assert meta["forecast_files_changed_since_previous"] == [f"forecast_cache/{MODEL_DIR}/2026-06-29/A.BK.parquet"]
        assert meta["previous_snapshot"] == s1.name and verify(s2) == []

        target = s2 / "raw" / "A.BK.parquet"
        os.chmod(target, stat.S_IWUSR | stat.S_IRUSR); target.write_bytes(b"tampered")
        assert verify(s2) == ["hash mismatch raw/A.BK.parquet"]
        try:
            snapshot(data, dest, datetime(2026, 9, 24, 23, 50)); raise AssertionError("overwrote a snapshot")
        except SystemExit:
            pass
    print("selftest passed (live-only folders, append-only, hard links, read-only, changed-forecast warning, verify)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data", help="source data root (default: data)")
    ap.add_argument("--dest", default=str(DEFAULT_DEST))
    ap.add_argument("--verify", metavar="SNAPSHOT_DIR")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.verify:
        bad = verify(Path(a.verify))
        print("OK" if not bad else "\n".join(bad))
        sys.exit(1 if bad else 0)
    snapshot(Path(a.data), Path(a.dest))


if __name__ == "__main__":
    main()
