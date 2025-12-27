# Catalyst Trading System - Functional Specification

**Name of Application**: Catalyst Trading System  
**Name of file**: functional-specification.md  
**Version**: 7.0.0  
**Last Updated**: 2025-12-27  
**Purpose**: Functional specifications for all services including Doctor Claude

---

## REVISION HISTORY

**v7.0.0 (2025-12-27)** - DOCTOR CLAUDE FUNCTIONAL SPECS
- ✅ **NEW**: Section 11 - Doctor Claude Operations
- ✅ **NEW**: Trade watchdog diagnostic specifications
- ✅ **NEW**: Activity logging specifications
- ✅ **NEW**: Auto-fix decision framework
- ✅ **NEW**: Escalation procedures

**v6.1.0 (2025-10-25)** - Monitoring and alerting additions

**v6.0.0 (2025-10-22)** - 9-service microservices architecture

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Service Matrix](#2-service-matrix)
3. [MCP Resource Hierarchy](#3-mcp-resource-hierarchy)
4. [Orchestration Service](#4-orchestration-service)
5. [Scanner Service](#5-scanner-service)
6. [Trading Service](#6-trading-service)
7. [Risk Manager Service](#7-risk-manager-service)
8. [Workflow Service](#8-workflow-service)
9. [Cron Schedule](#9-cron-schedule)
10. [Alert System](#10-alert-system)
11. [Doctor Claude Operations](#11-doctor-claude-operations)

---

## 1. System Overview

### 1.1 Operational Model

```
CRON → Workflow → Services → Database
                      ↑
              Doctor Claude
              (monitors and fixes)
```

**Key Points:**
- CRON triggers automated workflows during market hours
- Services execute trading logic and write to database
- Doctor Claude monitors trade lifecycle and fixes issues
- Claude Desktop provides human oversight via MCP

### 1.2 Trading Day Timeline

```
Pre-Market (4:00 AM - 9:30 AM ET):
  - Scanner runs at 9:15 AM
  - News service gathers catalysts
  - Candidates identified

Market Open (9:30 AM ET):
  - Workflow starts trading cycle
  - Doctor Claude begins monitoring
  - Position entries executed

Market Hours (9:30 AM - 4:00 PM ET):
  - Cron triggers every 30-60 minutes
  - Doctor Claude checks every 5 minutes
  - Positions monitored and managed

Market Close (4:00 PM ET):
  - All positions closed
  - Daily P&L calculated
  - Doctor Claude session ends
```

---

## 2. Service Matrix

### 2.1 Complete Service Inventory

| # | Service | Type | Port | Primary Function |
|---|---------|------|------|------------------|
| 1 | **Orchestration** | MCP | 5000 | Claude Desktop interface |
| 2 | **Workflow** | REST | 5006 | Trade coordination |
| 3 | **Scanner** | REST | 5001 | Market scanning |
| 4 | **Pattern** | REST | 5002 | Chart pattern recognition |
| 5 | **Technical** | REST | 5003 | Technical analysis |
| 6 | **Risk Manager** | REST | 5004 | Risk validation |
| 7 | **Trading** | REST | 5005 | Order execution |
| 8 | **News** | REST | 5008 | News catalyst detection |
| 9 | **Reporting** | REST | 5009 | Performance analytics |
| 10 | **Doctor Claude** | Script | N/A | Trade lifecycle monitoring |

### 2.2 Service Dependency Flow

```
AUTOMATED WORKFLOWS (Cron-initiated):
┌─────────────┐
│  Cron Job   │
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────┐
│  Workflow   │
└──────┬──────┘
       │
       ├──► Scanner ──► News ──► Pattern ──► Technical
       │
       ├──► Risk Manager
       │
       ├──► Trading ──► Alpaca Markets
       │
       └──► Reporting

MONITORING (Doctor Claude):
┌─────────────────┐
│  Doctor Claude  │ (Every 5 minutes)
└────────┬────────┘
         │
         ├──► PostgreSQL (read pipeline state)
         │
         ├──► Alpaca API (reconcile positions/orders)
         │
         └──► Fix issues or escalate
```

---

## 3. MCP Resource Hierarchy

### 3.1 Resource URIs

```
trading-cycle://
├── current                    # Active cycle state
├── {cycle_id}/
│   ├── status                 # Cycle status
│   └── positions              # Cycle positions

market-scan://
├── latest                     # Most recent scan
└── candidates/{symbol}        # Candidate details

positions://
├── current                    # Open positions
└── history                    # Closed positions

performance://
├── daily                      # Daily metrics
└── weekly                     # Weekly metrics

doctor-claude://               # NEW in v7.0
├── status                     # Current monitoring status
├── activity                   # Recent activity log
└── issues                     # Current issues
```

---

## 4. Orchestration Service

### 4.1 MCP Tools

| Tool | Purpose | Parameters |
|------|---------|------------|
| `execute_trade` | Submit trade order | symbol, side, quantity, order_type |
| `get_positions` | List open positions | - |
| `close_position` | Close specific position | position_id |
| `emergency_stop` | Close all positions | - |
| `get_scan_results` | Latest scan candidates | - |

### 4.2 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health check |
| `/mcp` | POST | MCP protocol handler |

---

## 5. Scanner Service

### 5.1 Scanning Pipeline

```
Universe (4000+ stocks)
         │
         ▼ Filter: Volume > 500K
Top 100 by Volume
         │
         ▼ Filter: Gap > 2%
Gap Candidates (~50)
         │
         ▼ News Service: Catalyst Check
Catalyst Candidates (~20)
         │
         ▼ Pattern + Technical Analysis
Final Candidates (5)
```

### 5.2 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/scan` | POST | Trigger market scan |
| `/api/v1/candidates` | GET | Get current candidates |
| `/health` | GET | Service health check |

---

## 6. Trading Service

### 6.1 Order Execution Flow

```
1. Receive order request
2. Validate with Risk Manager
3. Submit to Alpaca
4. Store in database
5. Return confirmation
```

### 6.2 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/orders` | POST | Submit new order |
| `/api/v1/orders/{id}` | GET | Get order status |
| `/api/v1/positions` | GET | List positions |
| `/api/v1/positions/{id}/close` | POST | Close position |
| `/api/v1/sync` | POST | Sync with Alpaca |
| `/health` | GET | Service health check |

### 6.3 Order Types

| Type | Use Case |
|------|----------|
| `market` | Immediate execution |
| `limit` | Price control |
| `stop` | Stop loss |
| `stop_limit` | Stop with limit |
| `bracket` | Entry + SL + TP |

---

## 7. Risk Manager Service

### 7.1 Risk Checks

| Check | Threshold | Action |
|-------|-----------|--------|
| Daily loss limit | $2,000 | Emergency stop |
| Position size | 2% of account | Reject order |
| Max positions | 5 concurrent | Queue new orders |
| Sector exposure | 40% max | Warn and limit |

### 7.2 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/validate` | POST | Validate proposed trade |
| `/api/v1/status` | GET | Current risk status |
| `/api/v1/emergency-stop` | POST | Trigger emergency stop |
| `/health` | GET | Service health check |

---

## 8. Workflow Service

### 8.1 Workflow States

```
CYCLE STATES:
  scanning → evaluating → trading → monitoring → closed

TRANSITIONS:
  scanning    : Running market scans
  evaluating  : Analyzing candidates
  trading     : Executing entries
  monitoring  : Watching positions
  closed      : Day complete
```

### 8.2 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/workflow/start` | POST | Start trading cycle |
| `/api/v1/workflow/stop` | POST | End trading cycle |
| `/api/v1/workflow/status` | GET | Current workflow state |
| `/health` | GET | Service health check |

---

## 9. Cron Schedule

### 9.1 Market Hours Schedule (US Eastern)

```bash
# Pre-market scan
15 9 * * 1-5    /scripts/trigger-workflow.sh

# Market open
30 9 * * 1-5    /scripts/trigger-workflow.sh

# Intraday scans (hourly)
30 10 * * 1-5   /scripts/trigger-workflow.sh
30 11 * * 1-5   /scripts/trigger-workflow.sh
0 13 * * 1-5    /scripts/trigger-workflow.sh
0 14 * * 1-5    /scripts/trigger-workflow.sh
0 15 * * 1-5    /scripts/trigger-workflow.sh

# Market close
0 16 * * 1-5    /scripts/close-positions.sh

# Health checks (every 15 minutes)
*/15 * * * *    /scripts/health-check.sh
```

### 9.2 Doctor Claude Schedule

```bash
# Doctor Claude runs as continuous loop during market hours
# OR can be scheduled via cron:

# Every 5 minutes during market hours
*/5 9-16 * * 1-5  python3 /scripts/trade_watchdog.py >> /var/log/catalyst/watchdog.log 2>&1
```

---

## 10. Alert System

### 10.1 Alert Channels

| Channel | Use Case | Recipients |
|---------|----------|------------|
| Email | Critical alerts | Craig |
| Log | All events | System |
| Redis | Real-time | Services |

### 10.2 Alert Types

| Type | Severity | Trigger |
|------|----------|---------|
| Emergency Stop | CRITICAL | Daily loss exceeded |
| Position Closed | INFO | Stop loss / take profit hit |
| Service Down | CRITICAL | Health check failed |
| Doctor Claude Issue | WARNING/CRITICAL | Reconciliation mismatch |

---

## 11. Doctor Claude Operations

### 11.1 Overview

Doctor Claude is an active monitoring system that runs during market hours to:
1. **Observe** - Check trade pipeline via database queries
2. **Diagnose** - Compare DB state vs Alpaca broker state
3. **Decide** - Determine auto-fix vs escalation
4. **Act** - Execute safe fixes or alert human
5. **Log** - Record all activities for audit trail

### 11.2 Components

| Component | File | Purpose |
|-----------|------|---------|
| Trade Watchdog | `trade_watchdog.py` | Run diagnostics, output JSON |
| Activity Logger | `log_activity.py` | Record to `claude_activity_log` |
| Monitor Script | `doctor_claude_monitor.sh` | Continuous monitoring loop |

### 11.3 Diagnostic Checks

| Check | Query Source | Comparison |
|-------|--------------|------------|
| Pipeline Status | `v_trade_pipeline_status` | N/A (status only) |
| Stuck Orders | `orders` table | submitted_at > 5 min |
| Position Reconciliation | `positions` table | vs Alpaca `get_all_positions()` |
| Order Status Sync | `orders` table | vs Alpaca `get_order_by_id()` |
| Stale Cycle | `trading_cycles` | updated_at > 30 min |

### 11.4 Issue Taxonomy

| Issue Type | Severity | Auto-Fix | Reasoning |
|------------|----------|----------|-----------|
| `ORDER_STATUS_MISMATCH` | WARNING | ✅ Yes | DB sync only |
| `PHANTOM_POSITION` | CRITICAL | ✅ Yes | Already gone from broker |
| `ORPHAN_POSITION` | CRITICAL | ❌ No | Real money, needs human |
| `QTY_MISMATCH` | WARNING | ⚠️ Maybe | Depends on size |
| `STUCK_ORDER` | WARNING | ❌ No | May be market conditions |
| `CYCLE_STALE` | WARNING | ❌ No | May be expected |

### 11.5 Decision Framework

```
Issue Detected
      │
      ▼
┌─────────────────┐
│ Check rules in  │
│ doctor_claude_  │
│ rules table     │
└────────┬────────┘
         │
    auto_fix_enabled?
         │
    ┌────┴────┐
   YES       NO
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│Execute│ │Escalate│
│Fix SQL│ │to Craig│
└───┬───┘ └───────┘
    │
    ▼
┌───────┐
│Verify │
│Fixed  │
└───┬───┘
    │
    ▼
┌───────┐
│ Log   │
│Activity│
└───────┘
```

### 11.6 Watchdog Output Format

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
    "counts": {
      "candidates": 5,
      "positions_open": 2,
      "orders_filled": 3
    },
    "pnl": {
      "daily": 150.00,
      "realized": 100.00,
      "unrealized": 50.00
    }
  },
  "issues": [
    {
      "type": "ORDER_STATUS_MISMATCH",
      "severity": "WARNING",
      "symbol": "AAPL",
      "message": "Order status: DB=submitted, Alpaca=filled",
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

### 11.7 Activity Logging

All Doctor Claude activities are logged to `claude_activity_log`:

```sql
-- Example log entry
INSERT INTO claude_activity_log (
    observation_type,
    issues_found, critical_count, warning_count,
    decision, decision_reasoning,
    action_type, action_detail, action_result,
    issue_type, issue_severity
) VALUES (
    'watchdog_run',
    1, 0, 1,
    'auto_fix', 'ORDER_STATUS_MISMATCH is safe per rules',
    'sql_update', 'UPDATE orders SET status = ''filled''...', 'success',
    'ORDER_STATUS_MISMATCH', 'WARNING'
);
```

### 11.8 Operational Commands

**Start Doctor Claude session:**
```bash
python3 log_activity.py --type startup --decision no_action
```

**Run single diagnostic:**
```bash
python3 trade_watchdog.py --pretty
```

**View recent activity:**
```bash
python3 log_activity.py --view --limit 20
```

**Query pipeline status:**
```sql
SELECT * FROM v_trade_pipeline_status WHERE date = CURRENT_DATE;
```

**Query today's activity:**
```sql
SELECT * FROM v_claude_activity_summary WHERE activity_date = CURRENT_DATE;
```

**Check recurring issues:**
```sql
SELECT * FROM v_recurring_issues;
```

### 11.9 Safety Boundaries

**Doctor Claude will NEVER:**
- Close positions in Alpaca automatically
- Modify real money amounts
- Change risk parameters
- Override emergency stops
- Act on orphan positions (real money not tracked)

**Doctor Claude CAN:**
- Sync DB state to match Alpaca
- Mark phantom positions as closed
- Update order statuses
- Alert Craig for human judgment

### 11.10 Escalation Procedures

| Priority | Channel | Response Time |
|----------|---------|---------------|
| CRITICAL | Email immediately | < 15 min |
| HIGH | Email | Same day |
| NORMAL | Daily summary | Next review |
| LOW | Log only | Weekly review |

**Escalation triggers:**
- 3+ failures of same issue type in 1 hour
- Any `ORPHAN_POSITION` (real money)
- Database or Alpaca connection failure
- Daily loss approaching limit

---

## Related Documents

- **architecture.md** - System architecture
- **database-schema.md** - Database schema
- **DOCTOR-CLAUDE-DESIGN.md** - Doctor Claude detailed design
- **DOCTOR-CLAUDE-IMPLEMENTATION.md** - Deployment guide

---

**END OF FUNCTIONAL SPECIFICATION v7.0.0**
