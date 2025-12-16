# Catalyst Trading System - Critical Fixes Implementation Guide

**Name of Application**: Catalyst Trading System
**Name of file**: us-system-critical-fixes-2025-12-16.md
**Version**: 1.0.0
**Last Updated**: 2025-12-16
**Purpose**: Step-by-step fix implementation with full testing for US production system

---

## EXECUTIVE SUMMARY

This guide addresses **5 critical issues** preventing successful trading:

| Priority | Issue | Fix Type | Estimated Time |
|----------|-------|----------|----------------|
| P1 | Timezone Misconfiguration | Crontab update | 5 min |
| P2 | Status Sync Not Running | Service restart/rebuild | 10 min |
| P3 | Database Ghost Positions | SQL cleanup | 5 min |
| P4 | Add Monitoring | New health checks | 15 min |
| P5 | Verification Suite | Full system test | 10 min |

**Total estimated time**: 45 minutes

---

## PRE-FLIGHT CHECKLIST

Before making ANY changes, run these diagnostics:

```bash
#!/bin/bash
# ===========================================================================
# PRE-FLIGHT DIAGNOSTIC SCRIPT
# Run this FIRST to capture current state
# ===========================================================================

echo "============================================="
echo "CATALYST TRADING SYSTEM - PRE-FLIGHT CHECK"
echo "Date: $(date)"
echo "============================================="

# 1. Current timezone
echo ""
echo ">>> TIMEZONE CHECK"
echo "System TZ: $(cat /etc/timezone 2>/dev/null || timedatectl | grep 'Time zone')"
echo "Current AWST: $(TZ=Australia/Perth date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Current ET:   $(TZ=America/New_York date '+%Y-%m-%d %H:%M:%S %Z')"

# 2. US Market status
ET_HOUR=$(TZ=America/New_York date +%H)
ET_DOW=$(TZ=America/New_York date +%u)
if [ "$ET_DOW" -ge 6 ]; then
    echo "Market Status: CLOSED (Weekend)"
elif [ "$ET_HOUR" -ge 9 ] && [ "$ET_HOUR" -lt 16 ]; then
    echo "Market Status: OPEN"
else
    echo "Market Status: CLOSED (After hours)"
fi

# 3. Current crontab
echo ""
echo ">>> CURRENT CRONTAB"
crontab -l 2>/dev/null || echo "No crontab configured"

# 4. Docker services status
echo ""
echo ">>> DOCKER SERVICES"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -E "catalyst|NAME"

# 5. Trading service version
echo ""
echo ">>> TRADING SERVICE VERSION"
docker logs catalyst-trading 2>&1 | grep -i "version\|v8\|starting" | head -5

# 6. Sync task status
echo ""
echo ">>> SYNC TASK STATUS"
docker logs catalyst-trading 2>&1 | grep -i "sync" | tail -10

# 7. Database position count
echo ""
echo ">>> DATABASE POSITION COUNT"
docker exec catalyst-trading python3 -c "
import asyncio
import asyncpg
import os

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Open positions in DB
    db_open = await conn.fetchval(\"\"\"
        SELECT COUNT(*) FROM positions WHERE status = 'open'
    \"\"\")
    
    # Positions by alpaca_status
    by_status = await conn.fetch(\"\"\"
        SELECT alpaca_status, COUNT(*) as cnt 
        FROM positions 
        WHERE status = 'open'
        GROUP BY alpaca_status
    \"\"\")
    
    print(f'DB Open Positions: {db_open}')
    print('By Alpaca Status:')
    for row in by_status:
        print(f'  {row[\"alpaca_status\"]}: {row[\"cnt\"]}')
    
    await conn.close()

asyncio.run(check())
" 2>/dev/null || echo "Could not query database"

# 8. Alpaca account status
echo ""
echo ">>> ALPACA ACCOUNT STATUS"
if [ -n "$ALPACA_API_KEY" ]; then
    curl -s https://paper-api.alpaca.markets/v2/account \
        -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
        -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Equity: \${float(d[\"equity\"]):,.2f}'); print(f'Buying Power: \${float(d[\"buying_power\"]):,.2f}'); print(f'Positions: Check /v2/positions')" 2>/dev/null || echo "Could not reach Alpaca API"
else
    echo "ALPACA_API_KEY not set"
fi

# 9. Alpaca positions
echo ""
echo ">>> ALPACA POSITIONS"
if [ -n "$ALPACA_API_KEY" ]; then
    POSITIONS=$(curl -s https://paper-api.alpaca.markets/v2/positions \
        -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
        -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" 2>/dev/null)
    COUNT=$(echo "$POSITIONS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "Alpaca Open Positions: $COUNT"
fi

echo ""
echo "============================================="
echo "PRE-FLIGHT CHECK COMPLETE"
echo "============================================="
```

**Save output before proceeding!**

```bash
# Save pre-flight results
./pre-flight.sh > /var/log/catalyst/pre-flight-$(date +%Y%m%d-%H%M%S).log 2>&1
cat /var/log/catalyst/pre-flight-*.log | tail -100
```

---

## FIX 1: TIMEZONE CONFIGURATION (CRITICAL)

### Problem
Cron jobs run at AWST daytime = US nighttime. Zero orders execute during market hours.

### Current State (WRONG)
```
09:30 AWST = 20:30 ET (8:30 PM) = MARKET CLOSED
11:00 AWST = 22:00 ET (10 PM)   = MARKET CLOSED
13:00 AWST = 00:00 ET (midnight)= MARKET CLOSED
15:00 AWST = 02:00 ET (2 AM)    = MARKET CLOSED
```

### Required State (CORRECT)
```
US Market: 9:30 AM - 4:00 PM ET
= 22:30 AWST (same day) to 05:00 AWST (next day)
```

### Implementation

#### Step 1.1: Backup Current Crontab
```bash
crontab -l > /root/crontab-backup-$(date +%Y%m%d-%H%M%S).txt
echo "Backup saved to /root/crontab-backup-*.txt"
```

#### Step 1.2: Create New Crontab
```bash
cat > /tmp/new-crontab.txt << 'EOF'
# ===========================================================================
# CATALYST TRADING SYSTEM - US MARKET HOURS (from Perth/AWST timezone)
# ===========================================================================
# US Market: 9:30 AM - 4:00 PM ET
# Perth equivalent: 22:30 (same day) to 05:00 (next day)
#
# IMPORTANT: Droplet timezone is Australia/Perth (AWST = UTC+8)
# US Eastern is UTC-5 (EST) or UTC-4 (EDT)
# Difference: 13 hours (AWST is 13 hours ahead of ET)
# ===========================================================================

# Market Open (9:30 AM ET = 22:30 AWST same day)
# Runs Sun-Thu night to catch Mon-Fri US market open
30 22 * * 0-4 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":5,"execute_top_n":3}' >> /var/log/catalyst/trading.log 2>&1

# Mid-Morning (11:00 AM ET = 00:00 AWST next day)
# Runs Mon-Fri midnight AWST
0 0 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":5,"execute_top_n":2}' >> /var/log/catalyst/trading.log 2>&1

# Early Afternoon (1:00 PM ET = 02:00 AWST)
0 2 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":5,"execute_top_n":2}' >> /var/log/catalyst/trading.log 2>&1

# Late Afternoon (3:00 PM ET = 04:00 AWST) - Before close, reduce positions
0 4 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":3,"execute_top_n":1}' >> /var/log/catalyst/trading.log 2>&1

# ===========================================================================
# HEALTH CHECKS (Run during Perth business hours for visibility)
# ===========================================================================

# Morning health check (8 AM AWST = 7 PM ET previous day)
0 8 * * 1-5 /root/catalyst-trading-mcp/scripts/health-check.sh >> /var/log/catalyst/health.log 2>&1

# Evening health check (6 PM AWST = 5 AM ET same day)  
0 18 * * 1-5 /root/catalyst-trading-mcp/scripts/health-check.sh >> /var/log/catalyst/health.log 2>&1

# ===========================================================================
# LOG ROTATION (Daily at 6 AM AWST)
# ===========================================================================
0 6 * * * find /var/log/catalyst -name "*.log" -mtime +7 -delete

EOF
```

#### Step 1.3: Install New Crontab
```bash
crontab /tmp/new-crontab.txt
echo "New crontab installed"
```

#### Step 1.4: Verify Installation
```bash
echo ">>> NEW CRONTAB:"
crontab -l

echo ""
echo ">>> VERIFICATION:"
echo "Next market open cron (22:30 AWST):"
echo "  - Will fire at: $(TZ=Australia/Perth date -d 'today 22:30' '+%Y-%m-%d %H:%M %Z') AWST"
echo "  - US Eastern:   $(TZ=America/New_York date -d "$(TZ=Australia/Perth date -d 'today 22:30' '+%Y-%m-%d %H:%M')" '+%Y-%m-%d %H:%M %Z') ET"
```

### Test 1: Timezone Mapping Verification
```bash
#!/bin/bash
# ===========================================================================
# TEST 1: Verify timezone mapping is correct
# ===========================================================================

echo "=== TIMEZONE MAPPING TEST ==="

# Test each cron time
declare -A CRON_TIMES=(
    ["22:30"]="Market Open"
    ["00:00"]="Mid-Morning"
    ["02:00"]="Early Afternoon"
    ["04:00"]="Late Afternoon"
)

echo ""
echo "Cron Time (AWST) | US Eastern Time | Expected Market Status"
echo "-----------------|-----------------|------------------------"

for AWST_TIME in "22:30" "00:00" "02:00" "04:00"; do
    # Convert AWST to ET
    ET_TIME=$(TZ=America/New_York date -d "$(TZ=Australia/Perth date -d "today $AWST_TIME" '+%Y-%m-%d %H:%M')" '+%H:%M')
    ET_HOUR=${ET_TIME:0:2}
    
    # Check if within market hours (09:30 - 16:00)
    if [ "$ET_HOUR" -ge 9 ] && [ "$ET_HOUR" -lt 16 ]; then
        STATUS="✓ OPEN"
    else
        STATUS="✗ CLOSED"
    fi
    
    printf "%-16s | %-15s | %s\n" "$AWST_TIME AWST" "$ET_TIME ET" "$STATUS"
done

echo ""
echo "Expected: All times should show '✓ OPEN'"
```

**Expected Output:**
```
Cron Time (AWST) | US Eastern Time | Expected Market Status
-----------------|-----------------|------------------------
22:30 AWST       | 09:30 ET        | ✓ OPEN
00:00 AWST       | 11:00 ET        | ✓ OPEN
02:00 AWST       | 13:00 ET        | ✓ OPEN
04:00 AWST       | 15:00 ET        | ✓ OPEN
```

---

## FIX 2: STATUS SYNC TASK

### Problem
Background sync task exists in code but isn't running. Database out of sync with Alpaca.

### Diagnosis

#### Step 2.1: Check Current Service Logs
```bash
echo "=== SYNC TASK DIAGNOSTIC ==="

# Check for sync startup message
echo ""
echo ">>> Looking for sync startup message:"
docker logs catalyst-trading 2>&1 | grep -i "sync" | head -20

# Check for any errors during startup
echo ""
echo ">>> Looking for startup errors:"
docker logs catalyst-trading 2>&1 | grep -iE "error|exception|failed|traceback" | head -20

# Check service version
echo ""
echo ">>> Service version:"
docker logs catalyst-trading 2>&1 | grep -iE "version|v8|starting" | head -5
```

#### Step 2.2: Check If Code Has Sync Task
```bash
# Verify sync function exists in deployed code
docker exec catalyst-trading grep -n "sync_order_statuses" /app/trading-service.py 2>/dev/null || \
docker exec catalyst-trading grep -n "sync_order_statuses" /app/services/trading/trading-service.py 2>/dev/null || \
echo "WARNING: sync_order_statuses function not found in container!"
```

### Implementation

#### Step 2.3: Rebuild and Restart Trading Service
```bash
echo "=== REBUILDING TRADING SERVICE ==="

cd /root/catalyst-trading-mcp

# Pull latest code (if using git)
git pull origin main 2>/dev/null || echo "Not a git repo or no remote"

# Rebuild the trading service
echo ">>> Building trading service..."
docker-compose build --no-cache trading

# Restart with fresh image
echo ">>> Restarting trading service..."
docker-compose up -d trading

# Wait for startup
echo ">>> Waiting for startup (10 seconds)..."
sleep 10

# Check logs
echo ">>> Checking startup logs:"
docker logs catalyst-trading --tail 50 2>&1 | grep -iE "sync|started|version|error"
```

### Test 2: Verify Sync Task Running
```bash
#!/bin/bash
# ===========================================================================
# TEST 2: Verify sync task is running
# ===========================================================================

echo "=== SYNC TASK VERIFICATION TEST ==="

# Check for startup message
echo ""
echo ">>> Step 1: Check startup message"
SYNC_STARTED=$(docker logs catalyst-trading 2>&1 | grep -c "Background order status sync started")
if [ "$SYNC_STARTED" -gt 0 ]; then
    echo "✓ PASS: Sync task started message found"
else
    echo "✗ FAIL: Sync task started message NOT found"
fi

# Check for running message
echo ""
echo ">>> Step 2: Check running message"
SYNC_RUNNING=$(docker logs catalyst-trading 2>&1 | grep -c "Order status sync task running")
if [ "$SYNC_RUNNING" -gt 0 ]; then
    echo "✓ PASS: Sync task running message found"
else
    echo "✗ FAIL: Sync task running message NOT found"
fi

# Check for sync activity (wait 70 seconds for one cycle)
echo ""
echo ">>> Step 3: Check for sync activity (waiting 70 seconds for one cycle)..."
BEFORE_COUNT=$(docker logs catalyst-trading 2>&1 | grep -c "Syncing\|synced")
sleep 70
AFTER_COUNT=$(docker logs catalyst-trading 2>&1 | grep -c "Syncing\|synced")

if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
    echo "✓ PASS: Sync activity detected"
else
    echo "⚠ WARNING: No new sync activity (may be normal if no positions need sync)"
fi

# Check for errors
echo ""
echo ">>> Step 4: Check for sync errors"
SYNC_ERRORS=$(docker logs catalyst-trading 2>&1 | grep -iE "sync.*error|error.*sync" | wc -l)
if [ "$SYNC_ERRORS" -eq 0 ]; then
    echo "✓ PASS: No sync errors found"
else
    echo "⚠ WARNING: Found $SYNC_ERRORS sync-related errors"
    docker logs catalyst-trading 2>&1 | grep -iE "sync.*error|error.*sync" | tail -5
fi

echo ""
echo "=== SYNC TASK TEST COMPLETE ==="
```

---

## FIX 3: DATABASE CLEANUP

### Problem
59 "ghost" positions in database that don't exist in Alpaca.

### Implementation

#### Step 3.1: Analyze Ghost Positions
```bash
echo "=== GHOST POSITION ANALYSIS ==="

docker exec catalyst-trading python3 << 'EOF'
import asyncio
import asyncpg
import os

async def analyze():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Get ghost positions (open in DB but old)
    ghosts = await conn.fetch("""
        SELECT 
            p.position_id,
            s.symbol,
            p.status,
            p.alpaca_status,
            p.alpaca_order_id,
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et,
            p.entry_price,
            p.quantity
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.status = 'open'
          AND p.opened_at < NOW() - INTERVAL '3 days'
        ORDER BY p.opened_at DESC
    """)
    
    print(f"Found {len(ghosts)} potential ghost positions:")
    print("")
    print(f"{'Symbol':<8} {'Alpaca Status':<15} {'Opened (ET)':<20} {'Entry':<10} {'Qty':<6}")
    print("-" * 70)
    
    for g in ghosts[:20]:  # Show first 20
        print(f"{g['symbol']:<8} {str(g['alpaca_status']):<15} {str(g['opened_et'])[:19]:<20} ${g['entry_price']:<9.2f} {g['quantity']:<6}")
    
    if len(ghosts) > 20:
        print(f"... and {len(ghosts) - 20} more")
    
    # Summary by alpaca_status
    print("")
    print("Summary by Alpaca Status:")
    summary = await conn.fetch("""
        SELECT alpaca_status, COUNT(*) as cnt
        FROM positions
        WHERE status = 'open'
          AND opened_at < NOW() - INTERVAL '3 days'
        GROUP BY alpaca_status
        ORDER BY cnt DESC
    """)
    for s in summary:
        print(f"  {str(s['alpaca_status']):<15}: {s['cnt']}")
    
    await conn.close()

asyncio.run(analyze())
EOF
```

#### Step 3.2: Create Cleanup Script
```bash
cat > /tmp/cleanup-ghost-positions.sql << 'EOF'
-- ===========================================================================
-- GHOST POSITION CLEANUP SCRIPT
-- ===========================================================================
-- This script marks orphaned positions as closed.
-- Run AFTER verifying sync task is working.
-- ===========================================================================

BEGIN;

-- Step 1: Count positions to be cleaned
SELECT 'Positions to clean:' as action, COUNT(*) as count
FROM positions
WHERE status = 'open'
  AND alpaca_status IN ('accepted', 'pending_new', NULL)
  AND opened_at < NOW() - INTERVAL '3 days';

-- Step 2: Mark as closed with reason
UPDATE positions
SET 
    status = 'closed',
    close_reason = 'orphaned_alpaca_sync_failure_cleanup_2025_12_16',
    closed_at = NOW(),
    notes = COALESCE(notes, '') || ' | Cleaned by ghost position script'
WHERE status = 'open'
  AND alpaca_status IN ('accepted', 'pending_new')
  AND opened_at < NOW() - INTERVAL '3 days';

-- Step 3: Report results
SELECT 'Positions cleaned:' as action, COUNT(*) as count
FROM positions
WHERE close_reason = 'orphaned_alpaca_sync_failure_cleanup_2025_12_16';

-- Step 4: Verify remaining open positions
SELECT 'Remaining open positions:' as action, COUNT(*) as count
FROM positions
WHERE status = 'open';

COMMIT;
EOF

echo "Cleanup script created at /tmp/cleanup-ghost-positions.sql"
echo "Review before running!"
```

#### Step 3.3: Execute Cleanup (After Review)
```bash
# DRY RUN - See what would be cleaned
echo "=== DRY RUN (No changes made) ==="
docker exec -i catalyst-postgres psql -U postgres -d catalyst_trading << 'EOF'
SELECT 
    s.symbol,
    p.alpaca_status,
    p.opened_at AT TIME ZONE 'America/New_York' as opened_et
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'open'
  AND p.alpaca_status IN ('accepted', 'pending_new')
  AND p.opened_at < NOW() - INTERVAL '3 days'
ORDER BY p.opened_at DESC
LIMIT 20;
EOF

# ACTUAL CLEANUP (Only run after reviewing dry run!)
echo ""
echo "To execute cleanup, run:"
echo "docker exec -i catalyst-postgres psql -U postgres -d catalyst_trading < /tmp/cleanup-ghost-positions.sql"
```

### Test 3: Verify Cleanup
```bash
#!/bin/bash
# ===========================================================================
# TEST 3: Verify database cleanup
# ===========================================================================

echo "=== DATABASE CLEANUP VERIFICATION ==="

docker exec catalyst-trading python3 << 'EOF'
import asyncio
import asyncpg
import os

async def verify():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Check remaining open positions
    open_count = await conn.fetchval("""
        SELECT COUNT(*) FROM positions WHERE status = 'open'
    """)
    
    # Check cleaned positions
    cleaned_count = await conn.fetchval("""
        SELECT COUNT(*) FROM positions 
        WHERE close_reason LIKE '%orphaned%cleanup%'
    """)
    
    # Check positions by status
    by_status = await conn.fetch("""
        SELECT status, COUNT(*) as cnt
        FROM positions
        WHERE opened_at >= NOW() - INTERVAL '30 days'
        GROUP BY status
        ORDER BY cnt DESC
    """)
    
    print("=== POST-CLEANUP STATUS ===")
    print(f"Open positions remaining: {open_count}")
    print(f"Positions cleaned: {cleaned_count}")
    print("")
    print("Positions by status (last 30 days):")
    for row in by_status:
        print(f"  {row['status']}: {row['cnt']}")
    
    # Verify no old ghost positions remain
    old_ghosts = await conn.fetchval("""
        SELECT COUNT(*) FROM positions
        WHERE status = 'open'
          AND alpaca_status IN ('accepted', 'pending_new')
          AND opened_at < NOW() - INTERVAL '3 days'
    """)
    
    print("")
    if old_ghosts == 0:
        print("✓ PASS: No ghost positions remaining")
    else:
        print(f"✗ FAIL: {old_ghosts} ghost positions still exist")
    
    await conn.close()

asyncio.run(verify())
EOF
```

---

## FIX 4: ADD MONITORING

### Step 4.1: Create Health Check Script
```bash
cat > /root/catalyst-trading-mcp/scripts/health-check.sh << 'EOF'
#!/bin/bash
# ===========================================================================
# CATALYST TRADING SYSTEM - HEALTH CHECK
# ===========================================================================

LOG_FILE="/var/log/catalyst/health-$(date +%Y%m%d).log"
ALERT_EMAIL="${ALERT_EMAIL:-}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local subject="$1"
    local body="$2"
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$body" | mail -s "[CATALYST] $subject" "$ALERT_EMAIL" 2>/dev/null || true
    fi
    log "ALERT: $subject"
}

# ===========================================================================
# CHECK 1: Docker Services Running
# ===========================================================================
check_services() {
    log "Checking Docker services..."
    
    SERVICES="catalyst-trading catalyst-workflow catalyst-scanner catalyst-risk-manager"
    ALL_UP=true
    
    for SVC in $SERVICES; do
        if docker ps --format '{{.Names}}' | grep -q "^${SVC}$"; then
            log "  ✓ $SVC: running"
        else
            log "  ✗ $SVC: NOT RUNNING"
            ALL_UP=false
        fi
    done
    
    if [ "$ALL_UP" = false ]; then
        send_alert "Services Down" "One or more Catalyst services are not running"
        return 1
    fi
    return 0
}

# ===========================================================================
# CHECK 2: Sync Task Active
# ===========================================================================
check_sync() {
    log "Checking sync task..."
    
    # Look for sync activity in last 5 minutes
    RECENT_SYNC=$(docker logs catalyst-trading --since 5m 2>&1 | grep -c "sync" || echo "0")
    
    if [ "$RECENT_SYNC" -gt 0 ]; then
        log "  ✓ Sync task active ($RECENT_SYNC log entries)"
        return 0
    else
        log "  ⚠ No sync activity in last 5 minutes"
        return 1
    fi
}

# ===========================================================================
# CHECK 3: Database vs Alpaca Position Count
# ===========================================================================
check_position_sync() {
    log "Checking position sync..."
    
    # Get DB count
    DB_COUNT=$(docker exec catalyst-trading python3 -c "
import asyncio, asyncpg, os
async def get():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    cnt = await conn.fetchval(\"SELECT COUNT(*) FROM positions WHERE status = 'open'\")
    await conn.close()
    print(cnt)
asyncio.run(get())
" 2>/dev/null || echo "-1")
    
    # Get Alpaca count
    ALPACA_COUNT=$(curl -s https://paper-api.alpaca.markets/v2/positions \
        -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
        -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" 2>/dev/null | \
        python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "-1")
    
    log "  DB positions: $DB_COUNT"
    log "  Alpaca positions: $ALPACA_COUNT"
    
    if [ "$DB_COUNT" = "-1" ] || [ "$ALPACA_COUNT" = "-1" ]; then
        log "  ⚠ Could not retrieve position counts"
        return 1
    fi
    
    DIFF=$((DB_COUNT - ALPACA_COUNT))
    if [ "$DIFF" -lt 0 ]; then DIFF=$((DIFF * -1)); fi
    
    if [ "$DIFF" -gt 5 ]; then
        send_alert "Position Mismatch" "DB has $DB_COUNT positions, Alpaca has $ALPACA_COUNT (diff: $DIFF)"
        log "  ✗ Position count mismatch: $DIFF difference"
        return 1
    else
        log "  ✓ Position counts aligned (diff: $DIFF)"
        return 0
    fi
}

# ===========================================================================
# CHECK 4: Market Hours Validation
# ===========================================================================
check_market_hours() {
    log "Checking market hours..."
    
    ET_HOUR=$(TZ=America/New_York date +%H)
    ET_DOW=$(TZ=America/New_York date +%u)
    
    # Weekend
    if [ "$ET_DOW" -ge 6 ]; then
        log "  ℹ Weekend - market closed"
        return 0
    fi
    
    # Market hours: 9:30 AM - 4:00 PM ET
    if [ "$ET_HOUR" -ge 9 ] && [ "$ET_HOUR" -lt 16 ]; then
        log "  ✓ Within market hours ($(TZ=America/New_York date '+%H:%M ET'))"
        return 0
    else
        log "  ℹ Outside market hours ($(TZ=America/New_York date '+%H:%M ET'))"
        return 0
    fi
}

# ===========================================================================
# CHECK 5: Recent Errors
# ===========================================================================
check_errors() {
    log "Checking for recent errors..."
    
    ERROR_COUNT=$(docker logs catalyst-trading --since 1h 2>&1 | grep -ciE "error|exception|failed" || echo "0")
    
    if [ "$ERROR_COUNT" -gt 10 ]; then
        log "  ⚠ High error count: $ERROR_COUNT in last hour"
        send_alert "High Error Rate" "$ERROR_COUNT errors in the last hour"
        return 1
    else
        log "  ✓ Error count normal: $ERROR_COUNT"
        return 0
    fi
}

# ===========================================================================
# MAIN
# ===========================================================================
log "========================================="
log "CATALYST HEALTH CHECK START"
log "========================================="

FAILURES=0

check_services || FAILURES=$((FAILURES + 1))
check_sync || FAILURES=$((FAILURES + 1))
check_position_sync || FAILURES=$((FAILURES + 1))
check_market_hours
check_errors || FAILURES=$((FAILURES + 1))

log "========================================="
if [ "$FAILURES" -eq 0 ]; then
    log "HEALTH CHECK PASSED"
else
    log "HEALTH CHECK FAILED ($FAILURES issues)"
fi
log "========================================="

exit $FAILURES
EOF

chmod +x /root/catalyst-trading-mcp/scripts/health-check.sh
echo "Health check script created"
```

### Test 4: Run Health Check
```bash
/root/catalyst-trading-mcp/scripts/health-check.sh
```

---

## FIX 5: FULL SYSTEM VERIFICATION

### Final Verification Suite
```bash
#!/bin/bash
# ===========================================================================
# FULL SYSTEM VERIFICATION SUITE
# Run this after all fixes are applied
# ===========================================================================

echo "============================================="
echo "CATALYST TRADING SYSTEM - FULL VERIFICATION"
echo "Date: $(date)"
echo "============================================="

PASS=0
FAIL=0

test_result() {
    if [ "$1" = "PASS" ]; then
        echo "  ✓ $2"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $2"
        FAIL=$((FAIL + 1))
    fi
}

# ===========================================================================
# TEST 1: Timezone Configuration
# ===========================================================================
echo ""
echo ">>> TEST 1: Timezone Configuration"

# Check cron has correct times
CRON_22=$(crontab -l 2>/dev/null | grep -c "^30 22")
CRON_00=$(crontab -l 2>/dev/null | grep -c "^0 0")
CRON_02=$(crontab -l 2>/dev/null | grep -c "^0 2")
CRON_04=$(crontab -l 2>/dev/null | grep -c "^0 4")

if [ "$CRON_22" -gt 0 ] && [ "$CRON_00" -gt 0 ] && [ "$CRON_02" -gt 0 ] && [ "$CRON_04" -gt 0 ]; then
    test_result "PASS" "Crontab has correct US market hour entries"
else
    test_result "FAIL" "Crontab missing US market hour entries"
fi

# ===========================================================================
# TEST 2: Docker Services
# ===========================================================================
echo ""
echo ">>> TEST 2: Docker Services"

for SVC in catalyst-trading catalyst-workflow catalyst-scanner catalyst-risk-manager; do
    if docker ps --format '{{.Names}}' | grep -q "^${SVC}$"; then
        test_result "PASS" "$SVC is running"
    else
        test_result "FAIL" "$SVC is NOT running"
    fi
done

# ===========================================================================
# TEST 3: Sync Task
# ===========================================================================
echo ""
echo ">>> TEST 3: Sync Task"

SYNC_MSG=$(docker logs catalyst-trading 2>&1 | grep -c "Background order status sync started")
if [ "$SYNC_MSG" -gt 0 ]; then
    test_result "PASS" "Sync task startup message found"
else
    test_result "FAIL" "Sync task startup message NOT found"
fi

# ===========================================================================
# TEST 4: Database State
# ===========================================================================
echo ""
echo ">>> TEST 4: Database State"

# Check for ghost positions
GHOST_COUNT=$(docker exec catalyst-trading python3 -c "
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    cnt = await conn.fetchval('''
        SELECT COUNT(*) FROM positions
        WHERE status = 'open'
          AND alpaca_status IN ('accepted', 'pending_new')
          AND opened_at < NOW() - INTERVAL '3 days'
    ''')
    await conn.close()
    print(cnt)
asyncio.run(check())
" 2>/dev/null || echo "-1")

if [ "$GHOST_COUNT" = "0" ]; then
    test_result "PASS" "No ghost positions found"
elif [ "$GHOST_COUNT" = "-1" ]; then
    test_result "FAIL" "Could not query database"
else
    test_result "FAIL" "$GHOST_COUNT ghost positions still exist"
fi

# ===========================================================================
# TEST 5: Alpaca Connection
# ===========================================================================
echo ""
echo ">>> TEST 5: Alpaca Connection"

ALPACA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    https://paper-api.alpaca.markets/v2/account \
    -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
    -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" 2>/dev/null)

if [ "$ALPACA_STATUS" = "200" ]; then
    test_result "PASS" "Alpaca API connection successful"
else
    test_result "FAIL" "Alpaca API returned status $ALPACA_STATUS"
fi

# ===========================================================================
# TEST 6: Order Side Fix Verification
# ===========================================================================
echo ""
echo ">>> TEST 6: Order Side Fix"

# Check trading service version includes fix
VERSION=$(docker logs catalyst-trading 2>&1 | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" | head -1)
if [[ "$VERSION" =~ v8\.[3-9]\. ]] || [[ "$VERSION" =~ v[9-9]\. ]]; then
    test_result "PASS" "Trading service version $VERSION includes order side fix"
else
    test_result "FAIL" "Trading service version $VERSION may not include fix (need v8.3.0+)"
fi

# ===========================================================================
# TEST 7: Health Check Script
# ===========================================================================
echo ""
echo ">>> TEST 7: Health Check Script"

if [ -x "/root/catalyst-trading-mcp/scripts/health-check.sh" ]; then
    test_result "PASS" "Health check script exists and is executable"
else
    test_result "FAIL" "Health check script missing or not executable"
fi

# ===========================================================================
# SUMMARY
# ===========================================================================
echo ""
echo "============================================="
echo "VERIFICATION SUMMARY"
echo "============================================="
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED - System ready for trading"
    exit 0
else
    echo "⚠️  $FAIL TESTS FAILED - Review issues above"
    exit 1
fi
```

---

## POST-FIX MONITORING

### First Trading Session Checklist

After fixes are applied, monitor the first US market session:

```bash
# 1. Watch logs during market open (22:30 AWST)
docker logs -f catalyst-trading &
docker logs -f catalyst-workflow &

# 2. Check if workflow starts
# Should see at 22:30 AWST:
#   "Autonomous workflow started"
#   "Scanning..."
#   "Executing trade..." (if opportunities found)

# 3. Verify orders are placed during market hours
# In a new terminal:
watch -n 60 'TZ=America/New_York date; curl -s https://paper-api.alpaca.markets/v2/orders -H "APCA-API-KEY-ID: $ALPACA_API_KEY" -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" | python3 -m json.tool | head -30'

# 4. Check position sync is working
watch -n 60 'docker logs catalyst-trading --tail 10 2>&1 | grep -i sync'
```

---

## ROLLBACK PROCEDURES

If issues occur, rollback each fix:

### Rollback Timezone
```bash
# Restore original crontab
crontab /root/crontab-backup-*.txt
crontab -l
```

### Rollback Trading Service
```bash
# Restart with previous image (if tagged)
docker-compose down trading
docker-compose up -d trading
```

### Rollback Database Cleanup
```bash
# Re-open cleaned positions (if needed)
docker exec -i catalyst-postgres psql -U postgres -d catalyst_trading << 'EOF'
UPDATE positions
SET 
    status = 'open',
    close_reason = NULL,
    closed_at = NULL
WHERE close_reason = 'orphaned_alpaca_sync_failure_cleanup_2025_12_16';
EOF
```

---

## COMPLETION CHECKLIST

| Step | Action | Verified |
|------|--------|----------|
| 1 | Run pre-flight diagnostic | ☐ |
| 2 | Backup current crontab | ☐ |
| 3 | Install new crontab | ☐ |
| 4 | Test timezone mapping | ☐ |
| 5 | Rebuild trading service | ☐ |
| 6 | Verify sync task running | ☐ |
| 7 | Review ghost positions | ☐ |
| 8 | Execute database cleanup | ☐ |
| 9 | Verify cleanup | ☐ |
| 10 | Install health check script | ☐ |
| 11 | Run full verification suite | ☐ |
| 12 | Monitor first trading session | ☐ |

---

**Document Version**: 1.0.0
**Created**: 2025-12-16
**Author**: Big Bro Claude (for Claude Code execution)
**Target System**: US Production Droplet (catalyst-trading-system)
