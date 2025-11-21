#!/bin/bash
#
# Catalyst Trading System - Automated Autonomous Trading Workflow
# Triggers the full autonomous trading workflow (scan + analysis + risk + execution)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp/catalyst-cron"
LOG_FILE="$LOG_DIR/workflow-$(date +%Y%m%d).log"

# Create log directory
mkdir -p "$LOG_DIR"

# Log start
echo "========================================" >> "$LOG_FILE"
echo "Autonomous workflow started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Trigger autonomous workflow via Workflow Coordinator API
RESPONSE=$(curl -s -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "autonomous", "max_candidates": 5}' \
  -w "\nHTTP_CODE:%{http_code}" 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")

echo "HTTP Status: $HTTP_CODE" >> "$LOG_FILE"
echo "Response: $BODY" >> "$LOG_FILE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Autonomous workflow triggered successfully" >> "$LOG_FILE"

    # Parse and log results
    CYCLE_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cycle_id', 'N/A'))" 2>/dev/null)
    MODE=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('mode', 'N/A'))" 2>/dev/null)
    MAX_POS=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('max_positions', 0))" 2>/dev/null)

    echo "Cycle ID: $CYCLE_ID" >> "$LOG_FILE"
    echo "Mode: $MODE" >> "$LOG_FILE"
    echo "Max positions: $MAX_POS" >> "$LOG_FILE"
    echo "🤖 Autonomous trading workflow executing..." >> "$LOG_FILE"
    echo "   → Scanner will find candidates" >> "$LOG_FILE"
    echo "   → Risk manager will validate trades" >> "$LOG_FILE"
    echo "   → Trading service will execute via Alpaca" >> "$LOG_FILE"
else
    echo "✗ Workflow failed with HTTP $HTTP_CODE" >> "$LOG_FILE"
fi

echo "Workflow trigger completed: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Keep only last 7 days of logs
find "$LOG_DIR" -name "workflow-*.log" -mtime +7 -delete

exit 0
