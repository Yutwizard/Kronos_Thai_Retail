#!/bin/bash
# Kronos-TH daily pipeline — retry wrapper for cron
# Recommended: run LATE EVENING at 23:45 BKK, not right after SET's 16:30
# close. The universe now includes DR (Depositary Receipt) underlyings on
# European exchanges (Hermès, L'Oréal, LVMH, Sanofi, Ferrari, Novo Nordisk —
# Euronext Paris/Amsterdam/Milan, Nasdaq Copenhagen), which close ~22:30 BKK
# (CEST, summer) to ~23:30 BKK (CET, winter) — LATER than Asian exchanges
# (SET/HKEX/TSE/SGX all close by ~16:30 BKK). A run at 17:30 BKK (the old
# recommendation) would silently forecast those 6 DRs off YESTERDAY's
# European close, breaking the "tomorrow's forecast uses today's close"
# guarantee just for them. 23:45 BKK clears Europe's close with margin in
# both DST seasons while staying on the SAME calendar day — run_pipeline.py
# derives `today` from Asia/Bangkok wall-clock date, so crossing midnight
# would roll the pipeline onto the wrong trading day. Do NOT push this past
# 23:59 BKK for that reason.
# Alternative: run at 06:30 BKK (morning, before SET opens) if same-day
# European DR freshness doesn't matter for your use case.
# Crontab examples:
#   45 23 * * 1-5  → late evening (recommended — clears Europe's close)
#   30  6 * * 1-5  → morning (alternative)
set -e

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="data/logs/cron_$(date +%Y-%m-%d).log"
RETRIES=3
BACKOFF=120

cd "$PROJ_DIR"
mkdir -p data/logs data/positions

log() { echo "[$(date +%H:%M:%S)] $1" | tee -a "$LOG"; }

notify_line() {
    if [ -z "$LINE_NOTIFY_TOKEN" ]; then
        log "WARN: LINE_NOTIFY_TOKEN not set — skipping notification"
        return
    fi
    curl -s -X POST https://notify-api.line.me/api/notify \
        -H "Authorization: Bearer $LINE_NOTIFY_TOKEN" \
        -F "message=$1" >> "$LOG" 2>&1
}

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
        notify_line "🚨 Kronos-TH STEP1 FAILED (download) on $(date +%Y-%m-%d). Check $LOG"
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
        notify_line "🚨 Kronos-TH STEP2 FAILED (forecast) on $(date +%Y-%m-%d). Check $LOG"
        exit 1
    fi
    log "STEP2 retry in ${BACKOFF}s..."
    sleep "$BACKOFF"
done

log "PIPELINE_OK — $(date)"
echo "PIPELINE_OK" >> "$LOG"
