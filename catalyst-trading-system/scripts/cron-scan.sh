#!/bin/bash
#
# Catalyst Trading System - Automated Market Scan
# Triggers scanner service to perform market analysis
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp/catalyst-cron"
LOG_FILE="$LOG_DIR/scan-$(date +%Y%m%d).log"

# Create log directory
mkdir -p "$LOG_DIR"

# Log start
echo "========================================" >> "$LOG_FILE"
echo "Scan started: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Trigger scan via API
RESPONSE=$(curl -s -X POST http://localhost:5001/api/v1/scan \
  -H "Content-Type: application/json" \
  -w "\nHTTP_CODE:%{http_code}" 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")

echo "HTTP Status: $HTTP_CODE" >> "$LOG_FILE"
echo "Response: $BODY" >> "$LOG_FILE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Scan completed successfully" >> "$LOG_FILE"

    # Parse and log results
    CYCLE_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('cycle_id', 'N/A'))" 2>/dev/null)
    CANDIDATES=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('candidates', 0))" 2>/dev/null)

    echo "Cycle ID: $CYCLE_ID" >> "$LOG_FILE"
    echo "Candidates found: $CANDIDATES" >> "$LOG_FILE"
else
    echo "✗ Scan failed with HTTP $HTTP_CODE" >> "$LOG_FILE"
fi

echo "Scan completed: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Keep only last 7 days of logs
find "$LOG_DIR" -name "scan-*.log" -mtime +7 -delete

exit 0
