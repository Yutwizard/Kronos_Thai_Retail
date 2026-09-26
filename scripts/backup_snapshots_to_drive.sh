#!/bin/bash
# Off-machine copy of the live-track evidence to Google Drive (ticket .scratch/future-plan/05).
#
# Uploads the newest snapshot from scripts/snapshot_live_data.py as one .tar.gz (about 18 MB). The newest snapshot
# holds every live forecast folder, the whole trade log and all shadow-book candidates, so one archive per week is
# enough; older archives are kept on Drive (nothing is ever deleted there by this script).
#
# One-time setup (needs a browser, so only the owner can do it):
#   sudo apt install rclone          # or: curl https://rclone.org/install.sh | sudo bash
#   rclone config                    # n (new) -> name: gdrive -> storage: drive -> defaults -> browser login
# Then:
#   scripts/backup_snapshots_to_drive.sh            # weekly, and on every review date after the snapshot
#   scripts/backup_snapshots_to_drive.sh --dry-run  # verify + build the archive, no upload
# Env: KRONOS_SNAPSHOT_DIR (default ~/backups/kronos-th-snapshots), KRONOS_DRIVE_REMOTE (default gdrive:Kronos-TH-snapshots)
set -euo pipefail

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SNAP_DIR="${KRONOS_SNAPSHOT_DIR:-$HOME/backups/kronos-th-snapshots}"
REMOTE="${KRONOS_DRIVE_REMOTE:-gdrive:Kronos-TH-snapshots}"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

latest="$(find "$SNAP_DIR" -mindepth 1 -maxdepth 1 -type d -name '2*' | sort | tail -1)"
[ -n "$latest" ] || { echo "no snapshot in $SNAP_DIR"; exit 1; }
name="$(basename "$latest")"

echo "verifying $name"
"$PROJ_DIR/venv/bin/python" "$PROJ_DIR/scripts/snapshot_live_data.py" --verify "$latest"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -C "$SNAP_DIR" -czf "$tmp/$name.tar.gz" "$name"
(cd "$tmp" && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")
echo "archive $(du -h "$tmp/$name.tar.gz" | cut -f1)  $(cut -d' ' -f1 "$tmp/$name.tar.gz.sha256")"

if [ "$DRY_RUN" -eq 1 ]; then
    tar -tzf "$tmp/$name.tar.gz" > "$tmp/listing"
    grep -qx "$name/MANIFEST.sha256" "$tmp/listing" || { echo "archive is missing MANIFEST.sha256"; exit 1; }
    echo "dry run OK ($(wc -l < "$tmp/listing") entries, manifest inside); nothing uploaded"
    exit 0
fi

command -v rclone >/dev/null || { echo "rclone is not installed; see the setup lines at the top of this script"; exit 1; }
if rclone lsf "$REMOTE/" --include "$name.tar.gz" 2>/dev/null | grep -q .; then
    echo "$name.tar.gz is already on $REMOTE; nothing to do"
    exit 0
fi
rclone copy "$tmp" "$REMOTE" --include "$name.tar.gz*"
rclone check "$tmp" "$REMOTE" --one-way --include "$name.tar.gz*"
echo "uploaded and checked: $REMOTE/$name.tar.gz"
