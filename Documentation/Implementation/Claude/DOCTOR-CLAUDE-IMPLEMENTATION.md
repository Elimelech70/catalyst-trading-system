# Doctor Claude Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** DOCTOR-CLAUDE-IMPLEMENTATION.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-27  
**Purpose:** Step-by-step deployment guide for Doctor Claude

---

## Prerequisites

- DigitalOcean droplet with Catalyst Trading System deployed
- PostgreSQL database (managed or local)
- Python 3.10+ with pip
- Alpaca API credentials (paper or live)
- SSH access to droplet

---

## Step 1: Upload Files to Droplet

### Option A: Using SCP

```bash
# From your local machine where files are located

# Create directories on droplet
ssh root@<DROPLET_IP> "mkdir -p /root/catalyst-trading-mcp/scripts /root/catalyst-trading-mcp/sql /root/catalyst-trading-mcp/Documentation/Design"

# Upload SQL schema
scp doctor-claude-schema.sql root@<DROPLET_IP>:/root/catalyst-trading-mcp/sql/

# Upload Python scripts
scp trade_watchdog.py root@<DROPLET_IP>:/root/catalyst-trading-mcp/scripts/
scp log_activity.py root@<DROPLET_IP>:/root/catalyst-trading-mcp/scripts/

# Upload documentation
scp DOCTOR-CLAUDE-DESIGN.md root@<DROPLET_IP>:/root/catalyst-trading-mcp/Documentation/Design/
```

### Option B: Using Git

```bash
# If files are in GitHub repo, SSH to droplet and pull
ssh root@<DROPLET_IP>
cd /root/catalyst-trading-mcp
git pull origin main
```

---

## Step 2: Install Python Dependencies

```bash
# SSH to droplet
ssh root@<DROPLET_IP>

# Install required packages
pip install asyncpg alpaca-py

# Verify installation
python3 -c "import asyncpg; import alpaca; print('Dependencies OK')"
```

---

## Step 3: Apply Database Schema

```bash
# SSH to droplet
ssh root@<DROPLET_IP>

# Navigate to SQL directory
cd /root/catalyst-trading-mcp/sql

# Apply schema (replace with your DATABASE_URL)
psql $DATABASE_URL < doctor-claude-schema.sql

# Or with explicit connection
psql -h <DB_HOST> -p 25060 -U <DB_USER> -d <DB_NAME> < doctor-claude-schema.sql
```

### Verify Installation

```bash
# Check tables created
psql $DATABASE_URL -c "\dt *claude*"

# Expected output:
#              List of relations
#  Schema |         Name          | Type  | Owner
# --------+-----------------------+-------+-------
#  public | claude_activity_log   | table | ...
#  public | doctor_claude_rules   | table | ...

# Check views created
psql $DATABASE_URL -c "\dv v_*"

# Expected output should include:
#  v_trade_pipeline_status
#  v_claude_activity_summary
#  v_recurring_issues
#  v_recent_escalations
#  v_failed_actions

# Check default rules loaded
psql $DATABASE_URL -c "SELECT issue_type, auto_fix_enabled FROM doctor_claude_rules;"
```

---

## Step 4: Make Scripts Executable

```bash
chmod +x /root/catalyst-trading-mcp/scripts/trade_watchdog.py
chmod +x /root/catalyst-trading-mcp/scripts/log_activity.py
```

---

## Step 5: Set Environment Variables

```bash
# Add to ~/.bashrc or /etc/environment
export DATABASE_URL="postgresql://user:pass@host:port/dbname?sslmode=require"
export ALPACA_API_KEY="your-api-key"
export ALPACA_SECRET_KEY="your-secret-key"
export ALPACA_PAPER="true"

# Optional thresholds
export STUCK_ORDER_MINUTES="5"
export STALE_CYCLE_MINUTES="30"

# Reload
source ~/.bashrc
```

---

## Step 6: Test Watchdog Script

```bash
cd /root/catalyst-trading-mcp/scripts

# Run with pretty output
python3 trade_watchdog.py --pretty

# Expected output (example):
# {
#   "timestamp": "2025-12-27T10:30:00.123456",
#   "duration_ms": 450,
#   "alpaca_connected": true,
#   "pipeline": {
#     "status": "OK",
#     "cycle_id": "abc-123",
#     ...
#   },
#   "issues": [],
#   "summary": {
#     "total_issues": 0,
#     "critical": 0,
#     "warnings": 0,
#     "status": "OK"
#   }
# }

# Check exit code
echo $?  # Should be 0 for OK
```

---

## Step 7: Test Activity Logger

```bash
cd /root/catalyst-trading-mcp/scripts

# Log a test entry
python3 log_activity.py \
    --type manual_check \
    --decision no_action \
    --reasoning "Testing Doctor Claude installation"

# Verify in database
psql $DATABASE_URL -c "SELECT logged_at, observation_type, decision FROM claude_activity_log ORDER BY logged_at DESC LIMIT 1;"

# View recent activity
python3 log_activity.py --view --limit 5
```

---

## Step 8: Create Monitoring Script

Create `/root/catalyst-trading-mcp/scripts/doctor_claude_monitor.sh`:

```bash
#!/bin/bash
# Doctor Claude Monitoring Script
# Run during market hours to watch trade lifecycle

SCRIPTS_DIR="/root/catalyst-trading-mcp/scripts"
LOG_DIR="/var/log/catalyst"
mkdir -p $LOG_DIR

SESSION_DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/doctor-claude-$SESSION_DATE.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# Log session start
log "=== Doctor Claude Session Starting ==="
python3 $SCRIPTS_DIR/log_activity.py \
    --type startup \
    --decision no_action \
    --reasoning "Beginning Doctor Claude monitoring session"

# Main monitoring loop
while true; do
    log "Running watchdog check..."
    
    # Run watchdog and capture output
    OUTPUT=$(python3 $SCRIPTS_DIR/trade_watchdog.py 2>&1)
    EXIT_CODE=$?
    
    # Extract summary
    STATUS=$(echo "$OUTPUT" | jq -r '.summary.status // "ERROR"')
    TOTAL=$(echo "$OUTPUT" | jq -r '.summary.total_issues // 0')
    CRITICAL=$(echo "$OUTPUT" | jq -r '.summary.critical // 0')
    WARNINGS=$(echo "$OUTPUT" | jq -r '.summary.warnings // 0')
    DURATION=$(echo "$OUTPUT" | jq -r '.duration_ms // 0')
    
    log "Status: $STATUS | Issues: $TOTAL (Critical: $CRITICAL, Warnings: $WARNINGS) | Duration: ${DURATION}ms"
    
    # Log observation
    python3 $SCRIPTS_DIR/log_activity.py \
        --type watchdog_run \
        --issues $TOTAL \
        --critical $CRITICAL \
        --warnings $WARNINGS \
        --decision no_action \
        --watchdog-ms $DURATION
    
    # Handle issues (placeholder for Claude Code logic)
    if [ "$TOTAL" -gt 0 ]; then
        log "Issues found - details in watchdog output"
        echo "$OUTPUT" | jq '.issues' >> $LOG_FILE
        
        # Process each issue
        ISSUE_COUNT=$(echo "$OUTPUT" | jq '.issues | length')
        for i in $(seq 0 $(($ISSUE_COUNT - 1))); do
            ISSUE_TYPE=$(echo "$OUTPUT" | jq -r ".issues[$i].type")
            SEVERITY=$(echo "$OUTPUT" | jq -r ".issues[$i].severity")
            FIX=$(echo "$OUTPUT" | jq -r ".issues[$i].fix")
            
            log "  Issue $i: $ISSUE_TYPE ($SEVERITY)"
            
            # Check if auto-fixable
            if [ "$FIX" != "null" ]; then
                # Check rules table for auto-fix permission
                CAN_FIX=$(psql $DATABASE_URL -t -c "SELECT auto_fix_enabled FROM doctor_claude_rules WHERE issue_type = '$ISSUE_TYPE' AND is_active = true")
                
                if [ "$(echo $CAN_FIX | tr -d ' ')" = "t" ]; then
                    log "  Auto-fixing: $ISSUE_TYPE"
                    # Execute fix
                    psql $DATABASE_URL -c "$FIX" 2>&1 | tee -a $LOG_FILE
                    FIX_RESULT=$?
                    
                    if [ $FIX_RESULT -eq 0 ]; then
                        RESULT="success"
                    else
                        RESULT="failed"
                    fi
                    
                    # Log the action
                    python3 $SCRIPTS_DIR/log_activity.py \
                        --type watchdog_run \
                        --decision auto_fix \
                        --reasoning "$ISSUE_TYPE is configured for auto-fix" \
                        --action-type sql_update \
                        --action "$FIX" \
                        --result $RESULT \
                        --issue-type $ISSUE_TYPE \
                        --severity $SEVERITY
                    
                    log "  Fix result: $RESULT"
                else
                    log "  Auto-fix not enabled for $ISSUE_TYPE - logging for review"
                    python3 $SCRIPTS_DIR/log_activity.py \
                        --type watchdog_run \
                        --decision escalate \
                        --reasoning "$ISSUE_TYPE requires human review" \
                        --issue-type $ISSUE_TYPE \
                        --severity $SEVERITY
                fi
            fi
        done
    fi
    
    log "Sleeping 5 minutes..."
    sleep 300
done
```

Make it executable:
```bash
chmod +x /root/catalyst-trading-mcp/scripts/doctor_claude_monitor.sh
```

---

## Step 9: Create Systemd Service (Optional)

Create `/etc/systemd/system/doctor-claude.service`:

```ini
[Unit]
Description=Doctor Claude Trade Monitor
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/catalyst-trading-mcp/scripts
ExecStart=/root/catalyst-trading-mcp/scripts/doctor_claude_monitor.sh
Restart=always
RestartSec=10
Environment="DATABASE_URL=postgresql://..."
Environment="ALPACA_API_KEY=..."
Environment="ALPACA_SECRET_KEY=..."
Environment="ALPACA_PAPER=true"

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable doctor-claude
systemctl start doctor-claude
systemctl status doctor-claude
```

---

## Step 10: Verification Checklist

Run these checks to verify everything is working:

```bash
# 1. Watchdog runs without errors
python3 /root/catalyst-trading-mcp/scripts/trade_watchdog.py --pretty
echo "Exit code: $?"

# 2. Activity logger works
python3 /root/catalyst-trading-mcp/scripts/log_activity.py --view

# 3. Database tables exist
psql $DATABASE_URL -c "SELECT COUNT(*) FROM claude_activity_log;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM doctor_claude_rules;"

# 4. Views work
psql $DATABASE_URL -c "SELECT * FROM v_trade_pipeline_status LIMIT 1;"

# 5. Rules are loaded
psql $DATABASE_URL -c "SELECT issue_type, auto_fix_enabled FROM doctor_claude_rules;"

# 6. If running as service, check logs
journalctl -u doctor-claude -f
```

---

## Troubleshooting

### Issue: "DATABASE_URL not set"
```bash
# Check environment variable
echo $DATABASE_URL

# If empty, set it
export DATABASE_URL="postgresql://..."
```

### Issue: "alpaca-py not installed"
```bash
pip install alpaca-py
```

### Issue: "Table does not exist"
```bash
# Re-run schema
psql $DATABASE_URL < /root/catalyst-trading-mcp/sql/doctor-claude-schema.sql
```

### Issue: "Connection refused to Alpaca"
```bash
# Check API keys
echo $ALPACA_API_KEY | head -c 10  # Should show start of key

# Test connection
python3 -c "
from alpaca.trading.client import TradingClient
import os
client = TradingClient(os.environ['ALPACA_API_KEY'], os.environ['ALPACA_SECRET_KEY'], paper=True)
print(client.get_account())
"
```

### Issue: Watchdog returns ERROR status
```bash
# Run with full output to see error
python3 /root/catalyst-trading-mcp/scripts/trade_watchdog.py --pretty 2>&1

# Check the error field in output
python3 /root/catalyst-trading-mcp/scripts/trade_watchdog.py | jq '.error'
```

---

## Daily Operations

### Start of Day (Before Market Open)
```bash
# Check system health
python3 /root/catalyst-trading-mcp/scripts/trade_watchdog.py --pretty

# View yesterday's activity
psql $DATABASE_URL -c "SELECT * FROM v_claude_activity_summary WHERE activity_date = CURRENT_DATE - 1;"

# Start monitoring (if not running as service)
nohup /root/catalyst-trading-mcp/scripts/doctor_claude_monitor.sh &
```

### End of Day (After Market Close)
```bash
# View today's summary
psql $DATABASE_URL -c "SELECT * FROM v_claude_activity_summary WHERE activity_date = CURRENT_DATE;"

# Check for any escalations
psql $DATABASE_URL -c "SELECT * FROM v_recent_escalations;"

# Check for failed actions
psql $DATABASE_URL -c "SELECT * FROM v_failed_actions;"
```

### Weekly Review
```bash
# Recurring issues
psql $DATABASE_URL -c "SELECT * FROM v_recurring_issues;"

# Auto-fix success rate
psql $DATABASE_URL -c "
SELECT 
    issue_type,
    COUNT(*) as attempts,
    COUNT(*) FILTER (WHERE action_result = 'success') as successes,
    ROUND(100.0 * COUNT(*) FILTER (WHERE action_result = 'success') / COUNT(*), 1) as success_rate
FROM claude_activity_log
WHERE decision = 'auto_fix'
  AND logged_at > NOW() - INTERVAL '7 days'
GROUP BY issue_type
ORDER BY attempts DESC;
"
```

---

## Summary

| Component | Location | Status |
|-----------|----------|--------|
| Schema | `/root/catalyst-trading-mcp/sql/doctor-claude-schema.sql` | ⬜ Deploy |
| Watchdog | `/root/catalyst-trading-mcp/scripts/trade_watchdog.py` | ⬜ Deploy |
| Logger | `/root/catalyst-trading-mcp/scripts/log_activity.py` | ⬜ Deploy |
| Monitor | `/root/catalyst-trading-mcp/scripts/doctor_claude_monitor.sh` | ⬜ Create |
| Service | `/etc/systemd/system/doctor-claude.service` | ⬜ Optional |
| Design Doc | `/root/catalyst-trading-mcp/Documentation/Design/DOCTOR-CLAUDE-DESIGN.md` | ⬜ Deploy |

---

**Implementation Complete When:**
- [ ] Schema applied to database
- [ ] Scripts deployed and executable
- [ ] Environment variables configured
- [ ] Watchdog runs without errors
- [ ] Activity logger records entries
- [ ] Monitoring script tested
- [ ] Documentation in place
