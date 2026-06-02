#!/bin/bash
# Kronos-TH morning pipeline — retry wrapper for cron
set -e

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="data/logs/cron_$(date +%Y-%m-%d).log"
RETRIES=3
BACKOFF=120

cd "$PROJ_DIR"
mkdir -p data/logs data/positions

log() { echo "[$(date +%H:%M:%S)] $1" | tee -a "$LOG"; }

log "Pipeline starting — $(date)"

# Step 1: Download data
for i in $(seq 1 $RETRIES); do
    log "STEP1 attempt $i/$RETRIES: download_data.py"
    if venv/bin/python scripts/download_data.py >> "$LOG" 2>&1; then
        log "STEP1_OK"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        log "STEP1_FAILED after $RETRIES attempts"
        exit 1
    fi
    log "STEP1 retry in ${BACKOFF}s..."
    sleep "$BACKOFF"
done

# Step 2: Generate forecasts + trade ticket
for i in $(seq 1 $RETRIES); do
    log "STEP2 attempt $i/$RETRIES: forecast generation"
    if venv/bin/python scripts/dashboard.py --generate >> "$LOG" 2>&1; then
        log "STEP2_OK"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        log "STEP2_FAILED after $RETRIES attempts"
        exit 1
    fi
    log "STEP2 retry in ${BACKOFF}s..."
    sleep "$BACKOFF"
done

log "PIPELINE_OK — $(date)"
echo "PIPELINE_OK" >> "$LOG"
