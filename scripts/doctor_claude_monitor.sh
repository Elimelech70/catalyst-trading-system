#!/bin/bash
# ============================================================================
# Name of Application: Catalyst Trading System
# Name of file: doctor_claude_monitor.sh
# Version: 1.0.0
# Last Updated: 2025-12-27
# Purpose: Doctor Claude monitoring loop - runs watchdog and handles issues
# ============================================================================
#
# Usage:
#   ./doctor_claude_monitor.sh           # Run in foreground
#   nohup ./doctor_claude_monitor.sh &   # Run in background
#
# Environment Variables Required:
#   DATABASE_URL        - PostgreSQL connection string
#   ALPACA_API_KEY      - Alpaca API key
#   ALPACA_SECRET_KEY   - Alpaca secret key
#
# ============================================================================

set -e

# Configuration
SCRIPTS_DIR="/root/catalyst-trading-system/scripts"
LOG_DIR="/var/log/catalyst"
INTERVAL_SECONDS=300  # 5 minutes between checks

# Create log directory if needed
mkdir -p "$LOG_DIR"

SESSION_DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/doctor-claude-$SESSION_DATE.log"

# Load environment variables
if [ -f "/root/catalyst-trading-system/.env" ]; then
    set -a
    source /root/catalyst-trading-system/.env
    set +a
fi

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check required environment variables
if [ -z "$DATABASE_URL" ]; then
    log "ERROR: DATABASE_URL not set"
    exit 1
fi

log "=== Doctor Claude Session Starting ==="
log "Log file: $LOG_FILE"
log "Check interval: $INTERVAL_SECONDS seconds"

# Log session start
python3 "$SCRIPTS_DIR/log_activity.py" \
    --type startup \
    --decision no_action \
    --reasoning "Beginning Doctor Claude monitoring session for $SESSION_DATE" \
    2>&1 | tee -a "$LOG_FILE"

# Trap for clean shutdown
cleanup() {
    log "=== Doctor Claude Session Ending ==="
    python3 "$SCRIPTS_DIR/log_activity.py" \
        --type shutdown \
        --decision no_action \
        --reasoning "Ending Doctor Claude monitoring session" \
        2>&1 | tee -a "$LOG_FILE"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Main monitoring loop
while true; do
    log "--- Running watchdog check ---"

    # Run watchdog and capture output
    OUTPUT=$(python3 "$SCRIPTS_DIR/trade_watchdog.py" 2>&1) || true
    EXIT_CODE=$?

    # Extract summary using jq (install: apt-get install jq)
    if command -v jq &> /dev/null; then
        STATUS=$(echo "$OUTPUT" | jq -r '.summary.status // "ERROR"')
        TOTAL=$(echo "$OUTPUT" | jq -r '.summary.total_issues // 0')
        CRITICAL=$(echo "$OUTPUT" | jq -r '.summary.critical // 0')
        WARNINGS=$(echo "$OUTPUT" | jq -r '.summary.warnings // 0')
        DURATION=$(echo "$OUTPUT" | jq -r '.duration_ms // 0')
    else
        # Fallback if jq not installed
        STATUS="UNKNOWN"
        TOTAL="?"
        CRITICAL="?"
        WARNINGS="?"
        DURATION="?"
    fi

    log "Status: $STATUS | Issues: $TOTAL (Critical: $CRITICAL, Warnings: $WARNINGS) | Duration: ${DURATION}ms"

    # Log the observation
    python3 "$SCRIPTS_DIR/log_activity.py" \
        --type watchdog_run \
        --issues "$TOTAL" \
        --critical "$CRITICAL" \
        --warnings "$WARNINGS" \
        --decision no_action \
        --watchdog-ms "$DURATION" \
        2>&1 | tee -a "$LOG_FILE"

    # Process issues if any (and jq available)
    if [ "$TOTAL" != "0" ] && [ "$TOTAL" != "?" ] && command -v jq &> /dev/null; then
        log "Processing $TOTAL issues..."
        ISSUE_COUNT=$(echo "$OUTPUT" | jq '.issues | length')

        for i in $(seq 0 $(($ISSUE_COUNT - 1))); do
            ISSUE_TYPE=$(echo "$OUTPUT" | jq -r ".issues[$i].type")
            SEVERITY=$(echo "$OUTPUT" | jq -r ".issues[$i].severity")
            FIX=$(echo "$OUTPUT" | jq -r ".issues[$i].fix")
            SYMBOL=$(echo "$OUTPUT" | jq -r ".issues[$i].symbol // \"N/A\"")

            log "  Issue $i: $ISSUE_TYPE ($SEVERITY) - $SYMBOL"

            # Check if auto-fixable
            if [ "$FIX" != "null" ] && [ -n "$FIX" ]; then
                # Check rules table for auto-fix permission
                CAN_FIX=$(PGPASSWORD=${PGPASSWORD:-} psql "$DATABASE_URL" -t -c \
                    "SELECT auto_fix_enabled FROM doctor_claude_rules WHERE issue_type = '$ISSUE_TYPE' AND is_active = true" 2>/dev/null | tr -d ' ')

                if [ "$CAN_FIX" = "t" ]; then
                    log "  Attempting auto-fix for $ISSUE_TYPE..."

                    # Execute fix
                    if PGPASSWORD=${PGPASSWORD:-} psql "$DATABASE_URL" -c "$FIX" 2>&1 | tee -a "$LOG_FILE"; then
                        RESULT="success"
                        log "  Fix applied successfully"
                    else
                        RESULT="failed"
                        log "  Fix failed"
                    fi

                    # Log the action
                    python3 "$SCRIPTS_DIR/log_activity.py" \
                        --type watchdog_run \
                        --decision auto_fix \
                        --reasoning "$ISSUE_TYPE is configured for auto-fix" \
                        --action-type sql_update \
                        --action "$FIX" \
                        --result "$RESULT" \
                        --issue-type "$ISSUE_TYPE" \
                        --severity "$SEVERITY" \
                        2>&1 | tee -a "$LOG_FILE"
                else
                    log "  Auto-fix not enabled for $ISSUE_TYPE - logging for review"
                    python3 "$SCRIPTS_DIR/log_activity.py" \
                        --type watchdog_run \
                        --decision escalate \
                        --reasoning "$ISSUE_TYPE requires human review" \
                        --issue-type "$ISSUE_TYPE" \
                        --severity "$SEVERITY" \
                        2>&1 | tee -a "$LOG_FILE"
                fi
            fi
        done
    fi

    log "Sleeping $INTERVAL_SECONDS seconds until next check..."
    sleep $INTERVAL_SECONDS
done
