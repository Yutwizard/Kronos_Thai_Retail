#!/bin/bash
# Did last night's scheduled pipeline run work? Read-only; run any morning:
#   scripts/check_last_run.sh
cd "$(dirname "$0")/.." || exit 1

log=$(ls -t data/logs/cron_20*.log 2>/dev/null | head -1)
fc=$(ls -d data/forecast_cache/NeoQuasar_Kronos-small/20* 2>/dev/null | sort | tail -1)
ticket=$(ls data/positions/trade_ticket_20*.json 2>/dev/null | sort | tail -1)
snap=$(ls -d "$HOME"/backups/kronos-th-snapshots/20* 2>/dev/null | sort | tail -1)

echo "Latest pipeline log : ${log:-none}"
if [ -n "$log" ]; then
    if grep -q "PIPELINE_OK" "$log"; then echo "  result            : OK (PIPELINE_OK)"
    elif grep -q "SCHEDULED: skipped" "$log"; then echo "  result            : skipped ($(grep -o 'skipped -- .*' "$log" | tail -1))"
    else echo "  result            : NOT FINISHED or FAILED -- last lines:"; tail -5 "$log" | sed 's/^/      /'
    fi
    grep -E "FAILED|WARN" "$log" | sed 's/^/  warning           : /' | head -5
fi
echo "Latest forecasts    : ${fc##*/} ($(ls "$fc"/*.parquet 2>/dev/null | wc -l) tickers)"
if [ -n "$ticket" ]; then
    venv/bin/python - "$ticket" <<'EOF'
import json, sys
t = json.load(open(sys.argv[1]))
n = lambda k: len(t.get(k) or [])
print(f"Latest trade ticket : {t.get('date')}  exits {n('exits')}  reduces {n('reduces')}  buys {n('buys')}  "
      f"band {t.get('allocation_band')}  market {t.get('market_state')}")
EOF
fi
echo "Latest snapshot     : ${snap##*/}"
echo "Last scheduled entry: $(tail -1 data/logs/cron_scheduled.log 2>/dev/null)"
