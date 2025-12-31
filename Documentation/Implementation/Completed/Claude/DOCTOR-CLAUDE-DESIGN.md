# Doctor Claude - Trade Lifecycle Monitoring System

**Name of Application:** Catalyst Trading System  
**Component:** Doctor Claude  
**Version:** 1.0.0  
**Last Updated:** 2025-12-27  
**Author:** Craig & Claude

---

## 1. Overview

### 1.1 Purpose

Doctor Claude is an active monitoring system where Claude Code watches the trade pipeline during market hours, diagnoses issues, applies safe fixes, and logs all activities for audit and learning.

### 1.2 Core Capabilities

| Capability | Description |
|------------|-------------|
| **Observe** | Check trade pipeline status via database queries and Alpaca API |
| **Diagnose** | Identify issues by comparing DB state vs broker state |
| **Decide** | Determine if issue can be auto-fixed or needs human escalation |
| **Act** | Execute safe fixes (DB sync only) and log all activities |
| **Learn** | Build pattern recognition from recurring issues |

### 1.3 Key Principles

1. **Read from Alpaca, Write to DB** - Never modify broker state automatically
2. **Safe by Default** - Only auto-fix issues that cannot cause financial harm
3. **Full Audit Trail** - Every observation, decision, and action is logged
4. **Graceful Degradation** - System works even if Alpaca connection fails

---

## 2. Architecture

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CLAUDE CODE                             │
│                   (Doctor Claude)                           │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │                 OBSERVE-DECIDE-ACT LOOP             │  │
│   │                                                     │  │
│   │   ┌──────────┐    ┌──────────┐    ┌──────────┐    │  │
│   │   │   RUN    │───▶│   READ   │───▶│  DECIDE  │    │  │
│   │   │ WATCHDOG │    │  OUTPUT  │    │          │    │  │
│   │   └──────────┘    └──────────┘    └────┬─────┘    │  │
│   │        ▲                               │          │  │
│   │        │                               ▼          │  │
│   │   ┌────┴─────┐    ┌──────────┐    ┌──────────┐   │  │
│   │   │   LOG    │◀───│   LOG    │◀───│   ACT    │   │  │
│   │   │  RESULT  │    │ DECISION │    │          │   │  │
│   │   └──────────┘    └──────────┘    └──────────┘   │  │
│   │        │                                          │  │
│   │        └──────────── WAIT 5 MIN ─────────────────┘  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  PostgreSQL  │ │    Alpaca    │ │    Email     │
    │   Database   │ │   Broker     │ │   Alerts     │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### 2.2 Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   trade_watchdog.py                                               │
│         │                                                         │
│         ├──► PostgreSQL ──► v_trade_pipeline_status view         │
│         │         │                                               │
│         │         ├──► trading_cycles                            │
│         │         ├──► positions                                 │
│         │         ├──► orders                                    │
│         │         └──► scan_results                              │
│         │                                                         │
│         ├──► Alpaca API ──► get_all_positions()                  │
│         │              ──► get_order_by_id()                     │
│         │                                                         │
│         └──► JSON Output ──► Claude Code (parses)                │
│                                   │                               │
│                                   ▼                               │
│                           Decision Engine                         │
│                                   │                               │
│                    ┌──────────────┼──────────────┐               │
│                    │              │              │                │
│                    ▼              ▼              ▼                │
│               Auto-Fix      Escalate       No Action             │
│                    │              │              │                │
│                    ▼              ▼              ▼                │
│               psql -c        Email Craig    log_activity.py      │
│                    │                             │                │
│                    └─────────────────────────────┘                │
│                                   │                               │
│                                   ▼                               │
│                           claude_activity_log                     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 Trade Watchdog (`trade_watchdog.py`)

**Purpose:** Diagnostic script that checks system health and outputs structured JSON.

**Checks Performed:**

| Check | Description | Severity | Auto-Fixable |
|-------|-------------|----------|--------------|
| Pipeline Status | Query `v_trade_pipeline_status` view | INFO | N/A |
| Stuck Orders | Orders pending > 5 minutes | WARNING | No |
| Phantom Positions | DB position not in Alpaca | CRITICAL | Yes |
| Orphan Positions | Alpaca position not in DB | CRITICAL | No |
| Qty Mismatch | DB qty ≠ Alpaca qty | WARNING/CRITICAL | Maybe |
| Order Status Mismatch | DB status ≠ Alpaca status | WARNING | Yes |
| Stale Cycle | No activity > 30 minutes | WARNING | No |
| Stale Position Data | P&L not updated > 10 minutes | INFO | No |

**Output Format:**
```json
{
  "timestamp": "2025-12-27T10:30:00",
  "duration_ms": 450,
  "alpaca_connected": true,
  "pipeline": {
    "status": "OK",
    "cycle_id": "abc-123",
    "state": "trading",
    "pipeline_stage": "MONITORING",
    "counts": {...},
    "pnl": {...}
  },
  "issues": [
    {
      "type": "ORDER_STATUS_MISMATCH",
      "severity": "WARNING",
      "symbol": "AAPL",
      "message": "Order AAPL status: DB=submitted, Alpaca=filled",
      "fix": "UPDATE orders SET status = 'filled'..."
    }
  ],
  "summary": {
    "total_issues": 1,
    "critical": 0,
    "warnings": 1,
    "status": "WARNING"
  }
}
```

**Exit Codes:**
- `0` = OK (no issues)
- `1` = WARNING (non-critical issues)
- `2` = CRITICAL (critical issues)
- `3` = ERROR (script failure)

### 3.2 Activity Logger (`log_activity.py`)

**Purpose:** Record all Claude Code observations, decisions, and actions to database.

**Usage Examples:**
```bash
# Log watchdog run with no issues
python3 log_activity.py --type watchdog_run --decision no_action

# Log an auto-fix
python3 log_activity.py \
    --type watchdog_run \
    --decision auto_fix \
    --reasoning "ORDER_STATUS_MISMATCH is safe per rules" \
    --action-type sql_update \
    --action "UPDATE orders SET status = 'filled'..." \
    --result success \
    --issue-type ORDER_STATUS_MISMATCH

# Log session start/end
python3 log_activity.py --type startup --decision no_action
python3 log_activity.py --type shutdown --decision no_action

# View recent activity
python3 log_activity.py --view --limit 20
```

### 3.3 Database Tables

| Table/View | Purpose |
|------------|---------|
| `claude_activity_log` | Audit trail of all activities |
| `doctor_claude_rules` | Configurable auto-fix rules |
| `v_trade_pipeline_status` | Real-time pipeline view |
| `v_claude_activity_summary` | Daily activity summary |
| `v_recurring_issues` | Issue frequency for learning |
| `v_recent_escalations` | Issues needing human review |
| `v_failed_actions` | Failed actions for investigation |

---

## 4. Issue Taxonomy

### 4.1 Issue Types and Handling

| Issue Type | Severity | Auto-Fix | Reasoning |
|------------|----------|----------|-----------|
| `ORDER_STATUS_MISMATCH` | WARNING | ✅ Yes | DB sync only, no broker action |
| `PHANTOM_POSITION` | CRITICAL | ✅ Yes | Mark closed, already gone from broker |
| `ORPHAN_POSITION` | CRITICAL | ❌ No | Real money in Alpaca, needs human |
| `QTY_MISMATCH` | VARIES | ⚠️ Maybe | Small diff = auto, large = escalate |
| `STUCK_ORDER` | WARNING | ❌ No | May be market conditions |
| `CYCLE_STALE` | WARNING | ❌ No | Expected during quiet periods |
| `ORDER_NOT_FOUND` | WARNING | ✅ Yes | Mark as expired |
| `STALE_POSITION_DATA` | INFO | ❌ No | Informational only |
| `ALPACA_CONNECTION_ERROR` | WARNING | ❌ No | Retry or escalate |
| `ALPACA_API_ERROR` | CRITICAL | ❌ No | Needs investigation |

### 4.2 Auto-Fix Rules

Auto-fix rules are stored in `doctor_claude_rules` table and can be modified:

```sql
-- View current rules
SELECT issue_type, auto_fix_enabled, escalation_priority 
FROM doctor_claude_rules 
WHERE is_active = true;

-- Disable auto-fix for an issue type
UPDATE doctor_claude_rules 
SET auto_fix_enabled = false 
WHERE issue_type = 'ORDER_STATUS_MISMATCH';

-- Adjust rate limits
UPDATE doctor_claude_rules 
SET max_auto_fixes_per_hour = 5, cooldown_minutes = 10 
WHERE issue_type = 'PHANTOM_POSITION';
```

---

## 5. Decision Framework

### 5.1 Decision Tree

```
Issue Detected
      │
      ▼
┌─────────────────┐
│ Check Rule in   │
│ doctor_claude_  │
│ rules table     │
└────────┬────────┘
         │
         ├── auto_fix_enabled = false?
         │         │
         │    YES  │  
         │         ▼
         │   ┌──────────┐
         │   │ Escalate │──► Email Craig
         │   └──────────┘
         │
         ├── auto_fix_enabled = true?
         │         │
         │    YES  │
         │         ▼
         │   ┌──────────────┐
         │   │ Check Rate   │
         │   │ Limits       │
         │   └──────┬───────┘
         │          │
         │          ├── Within limits?
         │          │         │
         │          │    YES  │
         │          │         ▼
         │          │   ┌──────────┐
         │          │   │ Execute  │
         │          │   │ Fix SQL  │
         │          │   └────┬─────┘
         │          │        │
         │          │        ▼
         │          │   ┌──────────┐
         │          │   │ Verify   │
         │          │   │ Fixed    │
         │          │   └──────────┘
         │          │
         │          ├── Rate limited?
         │          │         │
         │          │    YES  │
         │          │         ▼
         │          │   ┌──────────┐
         │          │   │ Defer /  │
         │          │   │ Monitor  │
         │          │   └──────────┘
         │
         └──────────────────────────────┐
                                        │
                                        ▼
                                 ┌──────────┐
                                 │   Log    │
                                 │ Activity │
                                 └──────────┘
```

### 5.2 Safety Boundaries

**Doctor Claude will NEVER:**
- Close positions in Alpaca (broker) automatically
- Modify real money amounts
- Change risk parameters
- Override emergency stops
- Act on orphan positions (real money not tracked in DB)
- Execute more than `max_auto_fixes_per_hour` fixes

**Doctor Claude CAN:**
- Sync DB state to match Alpaca (read broker, write DB)
- Mark phantom positions as closed (already gone from broker)
- Update order statuses to match Alpaca
- Alert Craig to issues requiring human judgment

---

## 6. Claude Code Workflow

### 6.1 Session Start (Market Open)

```bash
# Log session start
python3 /root/catalyst-trading-mcp/scripts/log_activity.py \
    --type startup \
    --decision no_action \
    --reasoning "Beginning Doctor Claude monitoring session for $(date +%Y-%m-%d)"

echo "Doctor Claude session started at $(date)"
```

### 6.2 Monitoring Loop (Every 5 Minutes)

```bash
#!/bin/bash
# doctor_claude_loop.sh

SCRIPTS_DIR="/root/catalyst-trading-mcp/scripts"

while true; do
    echo "=== $(date) - Running watchdog ==="
    
    # Step 1: Run watchdog and capture output
    OUTPUT=$($SCRIPTS_DIR/trade_watchdog.py)
    EXIT_CODE=$?
    DURATION=$(echo "$OUTPUT" | jq -r '.duration_ms')
    
    # Step 2: Extract summary
    TOTAL_ISSUES=$(echo "$OUTPUT" | jq -r '.summary.total_issues')
    CRITICAL=$(echo "$OUTPUT" | jq -r '.summary.critical')
    WARNINGS=$(echo "$OUTPUT" | jq -r '.summary.warnings')
    STATUS=$(echo "$OUTPUT" | jq -r '.summary.status')
    
    echo "Status: $STATUS | Issues: $TOTAL_ISSUES (Critical: $CRITICAL, Warnings: $WARNINGS)"
    
    # Step 3: Log observation
    python3 $SCRIPTS_DIR/log_activity.py \
        --type watchdog_run \
        --summary "$OUTPUT" \
        --issues $TOTAL_ISSUES \
        --critical $CRITICAL \
        --warnings $WARNINGS \
        --decision no_action \
        --watchdog-ms $DURATION
    
    # Step 4: Process issues if any
    if [ "$TOTAL_ISSUES" -gt 0 ]; then
        # Claude Code would parse issues and handle each one
        echo "Issues found - Claude Code will analyze and act..."
    fi
    
    # Step 5: Wait before next check
    echo "Sleeping 5 minutes..."
    sleep 300
done
```

### 6.3 Issue Handling (Claude Code Logic)

For each issue, Claude Code:

1. **Reads the issue type** from JSON output
2. **Checks if auto-fixable** based on `doctor_claude_rules`
3. **If auto-fix enabled:**
   - Execute the `fix` SQL from the issue
   - Log the action with result
   - Re-run watchdog to verify
4. **If not auto-fixable:**
   - Log as escalation
   - Send alert email to Craig
5. **Always logs the activity**

### 6.4 Session End (Market Close)

```bash
# Log session end
python3 /root/catalyst-trading-mcp/scripts/log_activity.py \
    --type shutdown \
    --decision no_action \
    --reasoning "Market closed - ending Doctor Claude session" \
    --metadata '{"session_date": "'$(date +%Y-%m-%d)'"}'

echo "Doctor Claude session ended at $(date)"
```

---

## 7. Queries for Review

### 7.1 Today's Activity

```sql
SELECT 
    to_char(logged_at, 'HH24:MI:SS') as time,
    observation_type,
    decision,
    action_type,
    action_result,
    issue_type
FROM claude_activity_log
WHERE DATE(logged_at) = CURRENT_DATE
ORDER BY logged_at DESC;
```

### 7.2 Session Summary

```sql
SELECT * FROM v_claude_activity_summary
WHERE activity_date = CURRENT_DATE;
```

### 7.3 Recurring Issues (Learning)

```sql
SELECT * FROM v_recurring_issues
ORDER BY occurrences DESC;
```

### 7.4 Failed Actions (Needs Review)

```sql
SELECT * FROM v_failed_actions;
```

### 7.5 Recent Escalations

```sql
SELECT * FROM v_recent_escalations;
```

### 7.6 Auto-Fix Success Rate

```sql
SELECT 
    issue_type,
    COUNT(*) as attempts,
    COUNT(*) FILTER (WHERE action_result = 'success') as successes,
    ROUND(100.0 * COUNT(*) FILTER (WHERE action_result = 'success') / COUNT(*), 1) as success_rate
FROM claude_activity_log
WHERE decision = 'auto_fix'
  AND logged_at > NOW() - INTERVAL '30 days'
GROUP BY issue_type
ORDER BY attempts DESC;
```

---

## 8. Escalation Channels

| Priority | Channel | Response Time | Trigger |
|----------|---------|---------------|---------|
| CRITICAL | Email + GitHub Issue | Immediate | Orphan positions, API failures |
| HIGH | Email | Same day | Repeated failures, large mismatches |
| NORMAL | Daily summary email | Next review | Auto-fixed issues |
| LOW | Log only | Weekly review | Informational items |

---

## 9. Files and Locations

| File | Location | Purpose |
|------|----------|---------|
| `trade_watchdog.py` | `/root/catalyst-trading-mcp/scripts/` | Diagnostic script |
| `log_activity.py` | `/root/catalyst-trading-mcp/scripts/` | Activity logger |
| `doctor-claude-schema.sql` | `/root/catalyst-trading-mcp/sql/` | DB schema |
| `DOCTOR-CLAUDE-DESIGN.md` | `/root/catalyst-trading-mcp/Documentation/Design/` | This document |

---

## 10. Configuration

### 10.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | Required | PostgreSQL connection string |
| `ALPACA_API_KEY` | Required | Alpaca API key |
| `ALPACA_SECRET_KEY` | Required | Alpaca secret key |
| `ALPACA_PAPER` | `true` | Paper trading mode |
| `STUCK_ORDER_MINUTES` | `5` | Threshold for stuck orders |
| `STALE_CYCLE_MINUTES` | `30` | Threshold for stale cycles |
| `QTY_MISMATCH_THRESHOLD` | `0.1` | 10% qty diff = critical |

### 10.2 Modifying Auto-Fix Rules

```sql
-- Disable auto-fix for all
UPDATE doctor_claude_rules SET auto_fix_enabled = false;

-- Enable only ORDER_STATUS_MISMATCH
UPDATE doctor_claude_rules 
SET auto_fix_enabled = true 
WHERE issue_type = 'ORDER_STATUS_MISMATCH';

-- Increase rate limit for busy periods
UPDATE doctor_claude_rules 
SET max_auto_fixes_per_hour = 20 
WHERE issue_type = 'ORDER_STATUS_MISMATCH';
```

---

## 11. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-27 | Initial implementation |

---

## 12. Future Enhancements

1. **Machine Learning** - Predict issues before they occur
2. **Slack Integration** - Real-time alerts to Slack channel
3. **Dashboard** - Web UI for monitoring status
4. **Pattern Detection** - Identify systemic issues from recurring patterns
5. **Self-Healing** - Expand auto-fix capabilities based on success rates
