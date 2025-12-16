# Catalyst Trading System - Full Issue Analysis

**Name of Application**: Catalyst Trading System
**Name of file**: trading-system-issue-analysis-2025-12-16.md
**Version**: 1.0.0
**Last Updated**: 2025-12-16
**Purpose**: Comprehensive analysis of all trading system issues

---

## Executive Summary

The trading system has **5 critical issues** that have prevented successful trading:

| Issue | Severity | Impact | Status |
|-------|----------|--------|--------|
| 1. Timezone Misconfiguration | **CRITICAL** | 100% orders outside market hours | Active |
| 2. Order Side Bug | CRITICAL | 81 positions lost | Fixed (v1.3.0) |
| 3. Sub-penny Pricing Bug | HIGH | 54 orders rejected | Fixed (v8.1.0) |
| 4. Status Sync Not Running | HIGH | DB out of sync with Alpaca | Active |
| 5. Database vs Alpaca Mismatch | HIGH | 59 "ghost" positions | Active |

**Net Result**: -4.36% return ($4,364.67 loss) from $100,161 starting equity

---

## Issue 1: Timezone Misconfiguration (CRITICAL)

### Problem

Cron jobs are scheduled in **AWST (Perth time)** but US markets operate in **EST**. All trading happens **outside market hours**.

### Evidence

```
Cron Schedule (AWST)  →  US Eastern Time  →  Market Status
─────────────────────────────────────────────────────────
09:30 AWST            →  20:30 ET         →  CLOSED (8:30 PM)
11:00 AWST            →  22:00 ET         →  CLOSED (10:00 PM)
13:00 AWST            →  00:00 ET         →  CLOSED (midnight)
15:00 AWST            →  02:00 ET         →  CLOSED (2:00 AM)
```

**US Market Hours**: 9:30 AM - 4:00 PM ET

### Database Proof

```
Trading Hour (ET) | Positions | Filled | Status
──────────────────────────────────────────────
00:00 (midnight)  |    36     |    0   | All outside hours
02:00 (2 AM)      |    31     |    0   | All outside hours
20:00 (8 PM)      |    35     |    0   | All outside hours
22:00 (10 PM)     |    33     |    0   | All outside hours
```

**Zero orders placed during market hours (9:30 AM - 4:00 PM ET)**

### Root Cause

Current crontab:
```bash
30 9 * * 1-5 curl ... /workflow/start   # 9:30 AWST = 8:30 PM ET
0 11 * * 1-5 curl ... /workflow/start   # 11:00 AWST = 10:00 PM ET
0 13 * * 1-5 curl ... /workflow/start   # 1:00 PM AWST = midnight ET
0 15 * * 1-5 curl ... /workflow/start   # 3:00 PM AWST = 2:00 AM ET
```

### Fix Required

To trade during US market hours from Perth timezone:
```
US Market Open  9:30 AM ET = 22:30 AWST (same day)
US Market Close 4:00 PM ET = 05:00 AWST (next day)
```

Corrected cron should be:
```bash
30 22 * * 0-4 curl ... /workflow/start  # 22:30 AWST = 9:30 AM ET (market open)
0 0 * * 1-5 curl ... /workflow/start    # midnight AWST = 11:00 AM ET
0 2 * * 1-5 curl ... /workflow/start    # 2:00 AM AWST = 1:00 PM ET
0 4 * * 1-5 curl ... /workflow/start    # 4:00 AM AWST = 3:00 PM ET (before close)
```

---

## Issue 2: Order Side Bug (FIXED)

### Problem

Simple ternary logic caused ALL "long" positions to execute as SHORT sells:

```python
# BUGGY CODE (v1.2.0)
order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
# "long" != "buy" → evaluated to SELL!
```

### Impact

- **81 positions affected** (Nov 29 - Dec 4, 2025)
- 54 rejected by Alpaca (can't short without margin)
- 27 cancelled as pending

### Status: FIXED in v1.3.0

```python
def _normalize_side(side: str) -> OrderSide:
    if side.lower() in ("buy", "long"):
        return OrderSide.BUY
    elif side.lower() in ("sell", "short"):
        return OrderSide.SELL
```

Current deployed version: **v1.4.0** (fix confirmed)

---

## Issue 3: Sub-penny Pricing Bug (FIXED)

### Problem

Floating-point precision caused invalid prices to be sent to Alpaca:

```
DB Stored: 9.05
Sent to Alpaca: 9.050000190734863  ← REJECTED
```

### Impact

- **54 orders rejected** with error: "sub-penny increment does not fulfill minimum pricing criteria"

### Status: FIXED in v8.1.0 (Dec 3, 2025)

```python
def _round_price(price: Optional[float]) -> Optional[float]:
    if price is None:
        return None
    return round(float(price), 2)
```

**No sub-penny errors after Dec 3, 2025**

---

## Issue 4: Status Sync Not Running

### Problem

The database shows orders as "accepted" but they're actually "filled" or "expired" in Alpaca.

### Evidence

Checked 20 orders marked "accepted" in database:

| Actual Alpaca Status | Count |
|---------------------|-------|
| filled              | 12    |
| expired             | 8     |

**60% of "accepted" orders were actually filled!**

### Root Cause

Background sync task exists in code (lines 386-443 of trading-service.py) but:
1. No "[OK] Background order status sync started" in startup logs
2. No sync activity in service logs
3. Sync runs every 60 seconds but appears non-functional

### Impact

- Database shows 59 "open" positions
- Alpaca shows 0 positions
- P&L never tracked (all show $0.00)
- System thinks positions exist that don't

---

## Issue 5: Database vs Alpaca Mismatch

### Current State

| System | Open Positions | Equity |
|--------|---------------|--------|
| Database | 59 | Unknown |
| Alpaca | 0 | $95,796.78 |

### What Happened

1. Orders were placed outside market hours
2. Some filled when market opened (as day limit orders)
3. Database never updated (sync broken)
4. Positions were sold on Dec 13-15 (visible in Alpaca history)
5. Database still shows them as "open"

### Alpaca Activity (Dec 13-15)

```
All recent activity = SELLS (liquidating positions)
TE, PATH, HAL, MRNA, EOSE, UEC, SOUN... all sold
```

---

## Complete Position Lifecycle Analysis

```
140 Total Positions Created (Since Nov 1)
│
├── 81 Order Side Bug (Nov 29 - Dec 4)
│   ├── 54 Alpaca rejected (can't short)
│   └── 27 Pending cancelled
│
├── 54 Sub-penny Errors (Nov 29 - Dec 3)
│   └── All rejected by Alpaca
│
└── 59 Remaining "Active" (Dec 4+)
    │
    ├── 79 Show "accepted" in DB
    │   ├── ~12 Actually filled in Alpaca
    │   └── ~8 Actually expired in Alpaca
    │
    └── Alpaca shows 0 positions now
        └── All were sold Dec 13-15
```

---

## Financial Impact

### Portfolio Performance (30 Days)

```
Starting Equity:  $100,161.45
Current Equity:   $95,796.78
─────────────────────────────
Net Loss:         -$4,364.67 (-4.36%)
```

### Daily Performance (Last Week)

| Date | P&L | Event |
|------|-----|-------|
| Dec 5 | -$1,029.90 | Normal trading losses |
| Dec 6 | +$248.70 | Minor recovery |
| Dec 9 | -$75.24 | Minimal activity |
| Dec 10 | +$446.80 | Recovery |
| Dec 11 | -$682.72 | Losses |
| Dec 12 | +$1,791.74 | Best day |
| Dec 13 | **-$4,407.32** | Mass liquidation |

**Dec 13 loss**: Positions liquidated (possibly due to price movement while "orphaned")

---

## Recommendations

### Immediate Actions (Priority Order)

#### 1. Fix Timezone Configuration (CRITICAL)

```bash
# Update crontab to trade during US market hours
30 22 * * 0-4 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":5,"execute_top_n":3}' >> /var/log/catalyst/trading.log 2>&1
0 0 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":5,"execute_top_n":2}' >> /var/log/catalyst/trading.log 2>&1
0 2 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":5,"execute_top_n":2}' >> /var/log/catalyst/trading.log 2>&1
0 4 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous","max_positions":3,"execute_top_n":1}' >> /var/log/catalyst/trading.log 2>&1
```

#### 2. Fix Status Sync Task

- Debug why sync_order_statuses() isn't logging
- Verify asyncio task is running
- Add health check for sync task

#### 3. Clean Up Database State

```sql
-- Mark orphaned positions as closed
UPDATE positions
SET status = 'closed',
    close_reason = 'orphaned_alpaca_sync_failure'
WHERE status = 'open'
  AND alpaca_status = 'accepted'
  AND opened_at < NOW() - INTERVAL '3 days';
```

#### 4. Add Monitoring

- Alert if orders placed outside 9:30 AM - 4:00 PM ET
- Alert if DB position count != Alpaca position count
- Alert if sync task hasn't run in 5 minutes

### Before Next Trading Session

```bash
# 1. Run order side test
python3 scripts/test_order_side.py

# 2. Verify current time mapping
echo "Current AWST: $(TZ=Australia/Perth date)"
echo "Current ET: $(TZ=America/New_York date)"
echo "Market open? $(TZ=America/New_York date +%H:%M) should be 09:30-16:00"

# 3. Verify Alpaca connection
curl -s https://paper-api.alpaca.markets/v2/account \
  -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
  -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" | python3 -m json.tool
```

---

## Summary

| Issue | Root Cause | Fix Status | Business Impact |
|-------|-----------|------------|-----------------|
| Timezone | Cron in AWST, market in ET | **Needs Fix** | 0% orders during market hours |
| Order Side | Ternary logic bug | Fixed v1.3.0 | 81 positions lost |
| Sub-penny | Float precision | Fixed v8.1.0 | 54 orders rejected |
| Status Sync | Background task silent | **Needs Debug** | DB out of sync |
| Data Mismatch | Sync + timezone combo | **Needs Cleanup** | Ghost positions |

**Primary Issue**: The timezone misconfiguration means **no orders can execute during market hours**, making all other fixes ineffective.

---

## Appendix: Key Queries for Monitoring

### Check Trading Hours Distribution

```sql
SELECT
    EXTRACT(HOUR FROM opened_at AT TIME ZONE 'America/New_York') as hour_et,
    COUNT(*) as positions
FROM positions
WHERE opened_at >= NOW() - INTERVAL '7 days'
GROUP BY hour_et
ORDER BY hour_et;
```

### Compare DB vs Alpaca Status

```sql
SELECT
    alpaca_status,
    COUNT(*) as count
FROM positions
WHERE opened_at >= NOW() - INTERVAL '30 days'
GROUP BY alpaca_status
ORDER BY count DESC;
```

### Check for Orphaned Positions

```sql
SELECT
    s.symbol, p.status, p.alpaca_status,
    p.opened_at AT TIME ZONE 'America/New_York' as opened_et
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'open'
  AND p.alpaca_status IN ('accepted', 'pending_new')
  AND p.opened_at < NOW() - INTERVAL '24 hours';
```

---

*Report generated: 2025-12-16 by Claude Code*
