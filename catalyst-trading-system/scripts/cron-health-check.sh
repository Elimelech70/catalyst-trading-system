#!/bin/bash
#
# Catalyst Trading System - Health Check
# Monitors all services and restarts if needed
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp/catalyst-cron"
LOG_FILE="$LOG_DIR/health-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

# Services to check
SERVICES=(
    "5001:scanner"
    "5002:news"
    "5003:technical"
    "5004:risk-manager"
    "5005:trading"
    "5006:workflow"
)

ALL_HEALTHY=true

for SERVICE in "${SERVICES[@]}"; do
    PORT="${SERVICE%%:*}"
    NAME="${SERVICE##*:}"

    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/health)

    if [ "$RESPONSE" = "200" ]; then
        echo "[$(date +%H:%M:%S)] ✓ $NAME (port $PORT): healthy" >> "$LOG_FILE"
    else
        echo "[$(date +%H:%M:%S)] ✗ $NAME (port $PORT): DOWN (HTTP $RESPONSE)" >> "$LOG_FILE"
        ALL_HEALTHY=false
    fi
done

if [ "$ALL_HEALTHY" = true ]; then
    echo "[$(date +%H:%M:%S)] All services healthy" >> "$LOG_FILE"
else
    echo "[$(date +%H:%M:%S)] WARNING: Some services are down!" >> "$LOG_FILE"
fi

# Keep only last 7 days of logs
find "$LOG_DIR" -name "health-*.log" -mtime +7 -delete

exit 0
