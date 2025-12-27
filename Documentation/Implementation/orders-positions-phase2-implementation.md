# Orders/Positions Phase 2 Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** orders-positions-phase2-implementation.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-27  
**Purpose:** Complete Phase 2 of orders/positions separation - drop legacy columns, fix queries, fix order side mapping

---

## REVISION HISTORY

**v1.0.0 (2025-12-27)** - Phase 2 Implementation
- Drop legacy columns from positions table
- Fix all diagnostic queries to use orders table exclusively
- Fix order side mapping for entry AND exit orders (long and short)
- Update trade_watchdog.py to v1.2.0
- Update v_trade_pipeline_status view

---

## Executive Summary

Phase 1 (completed December 27, 2025) created the `orders` table and migrated 83 orders. Phase 2 completes the separation by:

1. **Dropping legacy columns** from `positions` table (`alpaca_order_id`, `alpaca_status`)
2. **Fixing diagnostic queries** to use `orders` table exclusively
3. **Fixing order side mapping** to handle both entry AND exit orders correctly

**Pre-requisite:** System must have completed at least one successful trading day with the new orders table architecture (December 30, 2025 or later).

---

## Phase 2.1: Drop Legacy Columns

### SQL Script

```sql
-- ============================================================================
-- ORDERS/POSITIONS PHASE 2: Drop Legacy Columns
-- ============================================================================
-- Run this ONLY after verifying the orders table is working correctly
-- Pre-requisite: At least one successful trading day (Dec 30+)
-- ============================================================================

BEGIN;

-- Step 1: Verify orders table exists and has data
DO $$
DECLARE
    order_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO order_count FROM orders;
    IF order_count = 0 THEN
        RAISE EXCEPTION 'Orders table is empty! Do not proceed with column removal.';
    END IF;
    RAISE NOTICE 'Orders table has % records. Safe to proceed.', order_count;
END $$;

-- Step 2: Drop legacy columns from positions table
ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_order_id;
ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_status;

-- Step 3: Verify columns are gone
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' 
        AND column_name IN ('alpaca_order_id', 'alpaca_status')
    ) THEN
        RAISE EXCEPTION 'Legacy columns still exist! DROP failed.';
    ELSE
        RAISE NOTICE 'Legacy columns successfully removed from positions table.';
    END IF;
END $$;

COMMIT;

-- Step 4: Verify final state
SELECT 
    'positions' as table_name,
    COUNT(*) as column_count
FROM information_schema.columns 
WHERE table_name = 'positions'
UNION ALL
SELECT 
    'orders' as table_name,
    COUNT(*) as column_count
FROM information_schema.columns 
WHERE table_name = 'orders';
```

### Execution Command

```bash
cd /root/catalyst-trading-system
psql $DATABASE_URL -f sql/orders-positions-phase2-drop-columns.sql
```

---

## Phase 2.2: Fix Order Side Mapping

### Problem

The original migration only handled **entry orders**:

```sql
-- WRONG: Only handles entry orders
CASE WHEN p.side = 'long' THEN 'buy' ELSE 'sell' END
```

This is incorrect because:
- **Long entry** = BUY ✓
- **Long exit** = SELL ✗ (was mapping to BUY)
- **Short entry** = SELL ✓
- **Short exit** = BUY ✗ (was mapping to SELL)

### Correct Mapping

| Position Side | Order Purpose | Order Side |
|---------------|---------------|------------|
| long | entry | **buy** |
| long | exit | **sell** |
| short | entry | **sell** |
| short | exit | **buy** |

### SQL Script to Fix Existing Orders

```sql
-- ============================================================================
-- FIX ORDER SIDE MAPPING FOR EXIT ORDERS
-- ============================================================================
-- This script corrects the side field for exit orders that were incorrectly
-- mapped during initial migration.
-- ============================================================================

BEGIN;

-- Step 1: Identify exit orders (positions that are closed)
-- Exit orders are orders linked to closed positions where the order
-- closed the position (not the entry order)

-- First, let's see what we're dealing with
SELECT 
    'Current order side distribution' as check_type,
    o.side,
    COUNT(*) as count
FROM orders o
GROUP BY o.side;

-- Step 2: Add order_purpose column if not exists (to track entry vs exit)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_purpose VARCHAR(20);

-- Step 3: Mark entry orders (first order per position, or orders without position)
UPDATE orders o
SET order_purpose = 'entry'
WHERE order_purpose IS NULL
  AND (
    -- First order for each position (by created_at)
    o.order_id = (
        SELECT MIN(o2.order_id) 
        FROM orders o2 
        WHERE o2.position_id = o.position_id
    )
    -- Or standalone orders without position
    OR o.position_id IS NULL
  );

-- Step 4: Mark exit orders (subsequent orders for closed positions)
UPDATE orders o
SET order_purpose = 'exit'
WHERE order_purpose IS NULL
  AND o.position_id IS NOT NULL;

-- Step 5: Fix exit order sides based on position side
-- Long position exit = SELL
UPDATE orders o
SET side = 'sell'
FROM positions p
WHERE o.position_id = p.position_id
  AND o.order_purpose = 'exit'
  AND p.side = 'long'
  AND o.side != 'sell';

-- Short position exit = BUY  
UPDATE orders o
SET side = 'buy'
FROM positions p
WHERE o.position_id = p.position_id
  AND o.order_purpose = 'exit'
  AND p.side = 'short'
  AND o.side != 'buy';

-- Step 6: Verify the fix
SELECT 
    'After fix - order distribution' as check_type,
    o.order_purpose,
    o.side,
    COUNT(*) as count
FROM orders o
GROUP BY o.order_purpose, o.side
ORDER BY o.order_purpose, o.side;

COMMIT;
```

### Execution Command

```bash
cd /root/catalyst-trading-system
psql $DATABASE_URL -f sql/orders-fix-side-mapping.sql
```

---

## Phase 2.3: Update trade_watchdog.py to v1.2.0

### Changes Required

1. Remove any fallback queries to `positions.alpaca_*` columns
2. Ensure all order queries use `orders` table exclusively
3. Add `order_purpose` to query outputs

### Updated trade_watchdog.py (v1.2.0)

Create file: `scripts/trade_watchdog.py`

```python
#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trade_watchdog.py
Version: 1.2.0
Last Updated: 2025-12-27
Purpose: Real-time trade lifecycle monitoring for Doctor Claude

REVISION HISTORY:
v1.2.0 (2025-12-27) - Phase 2 Complete
- Removed all references to positions.alpaca_* columns
- Added order_purpose tracking (entry/exit)
- All order queries use orders table exclusively
- Fixed order side validation for entry vs exit

v1.1.0 (2025-12-27) - Updated to use orders table
- Queries orders table instead of positions.alpaca_* columns

v1.0.0 (2025-12-27) - Initial implementation

Usage:
    python3 trade_watchdog.py              # Run once, output JSON
    python3 trade_watchdog.py --pretty     # Pretty print output

Exit Codes:
    0 = OK (no issues)
    1 = WARNING (non-critical issues found)
    2 = CRITICAL (critical issues found)
    3 = ERROR (script failed to run)
"""

import asyncio
import asyncpg
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import OrderStatus, QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("WARNING: alpaca-py not installed. Position reconciliation will be skipped.", file=sys.stderr)

# ============================================================================
# CONFIGURATION
# ============================================================================

STUCK_ORDER_MINUTES = 5          # Orders pending longer than this are "stuck"
QTY_MISMATCH_THRESHOLD = 0.10    # 10% quantity difference is WARNING, more is CRITICAL
STALE_CYCLE_MINUTES = 30         # Cycle not updated in this time is stale

# ============================================================================
# DECIMAL ENCODER FOR JSON
# ============================================================================

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# ============================================================================
# TRADE WATCHDOG CLASS
# ============================================================================

class TradeWatchdog:
    """
    Diagnostic tool for monitoring the Catalyst Trading System.
    
    Performs the following checks:
    1. Pipeline status (from v_trade_pipeline_status view)
    2. Stuck orders (orders pending > 5 minutes)
    3. Position reconciliation (DB vs Alpaca)
    4. Order status sync (DB order status vs Alpaca)
    5. Stale cycle detection
    6. Position P&L sync
    """
    
    def __init__(self):
        self.db: Optional[asyncpg.Connection] = None
        self.alpaca: Optional[TradingClient] = None
        self.start_time = datetime.now()
        self.issues: List[Dict[str, Any]] = []
        
    async def connect(self):
        """Establish database and Alpaca connections"""
        # Database connection
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        self.db = await asyncpg.connect(db_url)
        
        # Alpaca connection (optional)
        if ALPACA_AVAILABLE:
            api_key = os.getenv('ALPACA_API_KEY')
            secret_key = os.getenv('ALPACA_SECRET_KEY')
            paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
            
            if api_key and secret_key:
                self.alpaca = TradingClient(api_key, secret_key, paper=paper)
            else:
                self.issues.append({
                    "type": "CONFIG_WARNING",
                    "severity": "INFO",
                    "message": "Alpaca credentials not configured. Position reconciliation disabled."
                })
    
    async def disconnect(self):
        """Close connections"""
        if self.db:
            await self.db.close()

    # ========================================================================
    # CHECK: Pipeline Status
    # ========================================================================
    
    async def check_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status from view"""
        row = await self.db.fetchrow("""
            SELECT * FROM v_trade_pipeline_status
            WHERE cycle_date = CURRENT_DATE
            ORDER BY cycle_start DESC
            LIMIT 1
        """)
        
        if not row:
            return {
                "status": "NO_CYCLE",
                "message": "No trading cycle found for today",
                "cycle_id": None
            }
        
        return {
            "status": row['cycle_status'],
            "cycle_id": row['cycle_id'],
            "cycle_start": row['cycle_start'].isoformat() if row['cycle_start'] else None,
            "orders": {
                "pending": row.get('orders_pending', 0),
                "filled": row.get('orders_filled', 0),
                "total": row.get('orders_total', 0)
            },
            "positions": {
                "total": row['positions_total'],
                "open": row['positions_open']
            },
            "pnl": {
                "daily": float(row['daily_pnl'] or 0)
            }
        }

    # ========================================================================
    # CHECK: Stuck Orders (ORDERS TABLE ONLY)
    # ========================================================================
    
    async def check_stuck_orders(self) -> List[Dict[str, Any]]:
        """Find orders that have been pending too long - queries ORDERS table only"""
        stuck = await self.db.fetch(f"""
            SELECT
                o.order_id,
                o.position_id,
                o.alpaca_order_id,
                s.symbol,
                o.status,
                o.side,
                o.order_type,
                o.order_purpose,
                o.quantity,
                o.submitted_at,
                EXTRACT(EPOCH FROM (NOW() - o.submitted_at))/60 as minutes_pending
            FROM orders o
            JOIN securities s ON o.security_id = s.security_id
            WHERE o.status IN ('submitted', 'pending_new', 'accepted', 'new', 'created')
              AND o.submitted_at < NOW() - INTERVAL '{STUCK_ORDER_MINUTES} minutes'
        """)

        issues = []
        for row in stuck:
            issues.append({
                "type": "STUCK_ORDER",
                "severity": "WARNING",
                "order_id": str(row['order_id']),
                "position_id": str(row['position_id']) if row['position_id'] else None,
                "alpaca_order_id": row['alpaca_order_id'],
                "symbol": row['symbol'],
                "side": row['side'],
                "order_type": row['order_type'],
                "order_purpose": row['order_purpose'],
                "quantity": row['quantity'],
                "minutes_pending": round(float(row['minutes_pending']), 1),
                "message": f"Order {row['symbol']} {row['side']} {row['order_purpose'] or 'unknown'} {row['quantity']} pending for {round(float(row['minutes_pending']))} minutes",
                "fix": f"UPDATE orders SET status = 'expired', updated_at = NOW() WHERE order_id = {row['order_id']}"
            })

        return issues

    # ========================================================================
    # CHECK: Position Reconciliation
    # ========================================================================
    
    async def reconcile_positions(self) -> List[Dict[str, Any]]:
        """Cross-check DB positions vs Alpaca positions"""
        if not self.alpaca:
            return [{
                "type": "RECONCILIATION_SKIPPED",
                "severity": "INFO",
                "message": "Alpaca not connected, skipping position reconciliation"
            }]
        
        # Get DB positions
        db_positions = await self.db.fetch("""
            SELECT 
                p.position_id,
                s.symbol,
                p.quantity,
                p.side,
                p.status
            FROM positions p
            JOIN securities s ON p.security_id = s.security_id
            WHERE p.status = 'open'
        """)
        
        # Get Alpaca positions
        try:
            alpaca_positions = self.alpaca.get_all_positions()
        except Exception as e:
            return [{
                "type": "ALPACA_ERROR",
                "severity": "WARNING",
                "message": f"Failed to fetch Alpaca positions: {str(e)}"
            }]
        
        # Build maps for comparison
        db_map = {row['symbol']: row for row in db_positions}
        alpaca_map = {p.symbol: p for p in alpaca_positions}
        
        issues = []
        
        # PHANTOM POSITION: In DB but NOT in Alpaca
        for symbol in set(db_map.keys()) - set(alpaca_map.keys()):
            issues.append({
                "type": "PHANTOM_POSITION",
                "severity": "CRITICAL",
                "symbol": symbol,
                "position_id": str(db_map[symbol]['position_id']),
                "db_qty": db_map[symbol]['quantity'],
                "alpaca_qty": 0,
                "message": f"Position {symbol} exists in DB but NOT in Alpaca (phantom)",
                "fix": f"UPDATE positions SET status = 'closed', close_reason = 'phantom_reconciliation', closed_at = NOW() WHERE position_id = {db_map[symbol]['position_id']}"
            })
        
        # ORPHAN POSITION: In Alpaca but NOT in DB
        for symbol in set(alpaca_map.keys()) - set(db_map.keys()):
            issues.append({
                "type": "ORPHAN_POSITION",
                "severity": "CRITICAL",
                "symbol": symbol,
                "position_id": None,
                "db_qty": 0,
                "alpaca_qty": abs(int(float(alpaca_map[symbol].qty))),
                "message": f"Position {symbol} exists in Alpaca but NOT in DB (orphan)",
                "fix": None  # Cannot auto-fix - real money involved
            })
        
        # QUANTITY MISMATCH: Both exist but quantities differ
        for symbol in set(db_map.keys()) & set(alpaca_map.keys()):
            db_qty = db_map[symbol]['quantity']
            alpaca_qty = abs(int(float(alpaca_map[symbol].qty)))
            
            if db_qty != alpaca_qty:
                diff_pct = abs(db_qty - alpaca_qty) / max(db_qty, alpaca_qty) if max(db_qty, alpaca_qty) > 0 else 0
                severity = "WARNING" if diff_pct < QTY_MISMATCH_THRESHOLD else "CRITICAL"
                
                issues.append({
                    "type": "QTY_MISMATCH",
                    "severity": severity,
                    "symbol": symbol,
                    "position_id": str(db_map[symbol]['position_id']),
                    "db_qty": db_qty,
                    "alpaca_qty": alpaca_qty,
                    "difference": alpaca_qty - db_qty,
                    "difference_pct": round(diff_pct * 100, 1),
                    "message": f"Position {symbol} qty mismatch: DB={db_qty}, Alpaca={alpaca_qty} ({round(diff_pct*100, 1)}% diff)",
                    "fix": f"UPDATE positions SET quantity = {alpaca_qty}, updated_at = NOW() WHERE position_id = {db_map[symbol]['position_id']}"
                })
        
        return issues

    # ========================================================================
    # CHECK: Order Status Sync (ORDERS TABLE ONLY)
    # ========================================================================
    
    async def check_order_sync(self) -> List[Dict[str, Any]]:
        """Verify DB order statuses match Alpaca - queries ORDERS table only"""
        if not self.alpaca:
            return []

        # Get recent non-terminal orders from orders table
        db_orders = await self.db.fetch("""
            SELECT
                o.order_id,
                o.position_id,
                o.alpaca_order_id,
                o.status as db_status,
                o.filled_avg_price as db_filled_price,
                o.filled_qty as db_filled_qty,
                o.order_purpose,
                s.symbol,
                o.side,
                o.quantity
            FROM orders o
            JOIN securities s ON o.security_id = s.security_id
            WHERE o.alpaca_order_id IS NOT NULL
              AND o.status NOT IN ('filled', 'cancelled', 'rejected', 'expired')
              AND o.submitted_at > NOW() - INTERVAL '24 hours'
        """)

        if not db_orders:
            return []

        issues = []

        for row in db_orders:
            try:
                alpaca_order = self.alpaca.get_order_by_id(row['alpaca_order_id'])
                alpaca_status = alpaca_order.status.value if hasattr(alpaca_order.status, 'value') else str(alpaca_order.status)
                
                # Check for status mismatch
                if row['db_status'] != alpaca_status:
                    # Build fix SQL
                    fix_parts = [f"status = '{alpaca_status}'"]
                    
                    if alpaca_status == 'filled':
                        if alpaca_order.filled_avg_price:
                            fix_parts.append(f"filled_avg_price = {alpaca_order.filled_avg_price}")
                        if alpaca_order.filled_qty:
                            fix_parts.append(f"filled_qty = {alpaca_order.filled_qty}")
                        fix_parts.append("filled_at = NOW()")
                    
                    fix_parts.append("updated_at = NOW()")
                    fix_sql = f"UPDATE orders SET {', '.join(fix_parts)} WHERE order_id = {row['order_id']}"
                    
                    issues.append({
                        "type": "ORDER_STATUS_MISMATCH",
                        "severity": "WARNING",
                        "order_id": str(row['order_id']),
                        "alpaca_order_id": row['alpaca_order_id'],
                        "symbol": row['symbol'],
                        "side": row['side'],
                        "order_purpose": row['order_purpose'],
                        "db_status": row['db_status'],
                        "alpaca_status": alpaca_status,
                        "message": f"Order {row['symbol']} {row['order_purpose'] or ''} status mismatch: DB={row['db_status']}, Alpaca={alpaca_status}",
                        "fix": fix_sql
                    })
                    
            except Exception as e:
                error_str = str(e)
                if 'not found' in error_str.lower() or '404' in error_str:
                    issues.append({
                        "type": "ORDER_NOT_FOUND",
                        "severity": "WARNING",
                        "order_id": str(row['order_id']),
                        "alpaca_order_id": row['alpaca_order_id'],
                        "symbol": row['symbol'],
                        "message": f"Order {row['alpaca_order_id']} not found in Alpaca",
                        "fix": f"UPDATE orders SET status = 'not_found', updated_at = NOW() WHERE order_id = {row['order_id']}"
                    })
                else:
                    issues.append({
                        "type": "ORDER_CHECK_ERROR",
                        "severity": "INFO",
                        "order_id": str(row['order_id']),
                        "alpaca_order_id": row['alpaca_order_id'],
                        "error": error_str,
                        "message": f"Error checking order {row['alpaca_order_id']}: {error_str}"
                    })

        return issues

    # ========================================================================
    # CHECK: Stale Cycle
    # ========================================================================
    
    async def check_stale_cycle(self, pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if the current cycle is stale (not updated recently)"""
        if not pipeline.get('cycle_id'):
            return []
        
        row = await self.db.fetchrow("""
            SELECT 
                cycle_id,
                status,
                updated_at,
                EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as minutes_since_update
            FROM trading_cycles
            WHERE cycle_id = $1
        """, pipeline['cycle_id'])
        
        if not row:
            return []
        
        minutes_stale = float(row['minutes_since_update'])
        
        if minutes_stale > STALE_CYCLE_MINUTES and row['status'] not in ('completed', 'failed'):
            return [{
                "type": "CYCLE_STALE",
                "severity": "WARNING",
                "cycle_id": row['cycle_id'],
                "status": row['status'],
                "minutes_since_update": round(minutes_stale, 1),
                "message": f"Cycle {row['cycle_id']} not updated for {round(minutes_stale)} minutes (status: {row['status']})",
                "fix": None  # May be expected during quiet periods
            }]
        
        return []

    # ========================================================================
    # CHECK: Position P&L Sync
    # ========================================================================
    
    async def check_position_pnl_sync(self) -> List[Dict[str, Any]]:
        """Check for positions with stale P&L data"""
        issues = []
        
        stale_positions = await self.db.fetch("""
            SELECT
                p.position_id,
                s.symbol,
                p.entry_price,
                p.unrealized_pnl,
                p.updated_at,
                EXTRACT(EPOCH FROM (NOW() - p.updated_at))/60 as minutes_since_update
            FROM positions p
            JOIN securities s ON p.security_id = s.security_id
            WHERE p.status = 'open'
              AND p.updated_at < NOW() - INTERVAL '10 minutes'
        """)
        
        for row in stale_positions:
            issues.append({
                "type": "STALE_POSITION_DATA",
                "severity": "INFO",
                "position_id": str(row['position_id']),
                "symbol": row['symbol'],
                "minutes_since_update": round(float(row['minutes_since_update']), 1),
                "message": f"Position {row['symbol']} P&L not updated for {round(float(row['minutes_since_update']))} minutes",
                "fix": None  # Informational - P&L sync should update this
            })
        
        return issues

    # ========================================================================
    # MAIN: Run All Checks
    # ========================================================================
    
    async def run_full_check(self) -> Dict[str, Any]:
        """Execute all diagnostic checks and return structured report"""
        await self.connect()
        
        try:
            # Get pipeline status first
            pipeline = await self.check_pipeline_status()
            
            # Run all checks
            issues = []
            issues.extend(await self.check_stuck_orders())
            issues.extend(await self.reconcile_positions())
            issues.extend(await self.check_order_sync())
            issues.extend(await self.check_stale_cycle(pipeline))
            issues.extend(await self.check_position_pnl_sync())
            issues.extend(self.issues)  # Any issues from initialization
            
            # Build report
            end_time = datetime.now()
            duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
            
            # Count by severity
            critical_count = len([i for i in issues if i.get("severity") == "CRITICAL"])
            warning_count = len([i for i in issues if i.get("severity") == "WARNING"])
            info_count = len([i for i in issues if i.get("severity") == "INFO"])
            
            # Determine overall status
            if critical_count > 0:
                overall_status = "CRITICAL"
            elif warning_count > 0:
                overall_status = "WARNING"
            else:
                overall_status = "OK"
            
            return {
                "timestamp": self.start_time.isoformat(),
                "duration_ms": duration_ms,
                "alpaca_connected": self.alpaca is not None,
                "alpaca_mode": "paper" if self.alpaca and os.getenv('ALPACA_PAPER', 'true').lower() == 'true' else "live",
                "pipeline": pipeline,
                "issues": issues,
                "summary": {
                    "total_issues": len(issues),
                    "critical": critical_count,
                    "warnings": warning_count,
                    "info": info_count,
                    "status": overall_status
                }
            }
            
        finally:
            await self.disconnect()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description='Trade Watchdog - Diagnostic tool for Catalyst Trading System')
    parser.add_argument('--pretty', action='store_true', help='Pretty print JSON output')
    args = parser.parse_args()
    
    watchdog = TradeWatchdog()
    
    try:
        report = await watchdog.run_full_check()
        
        if args.pretty:
            print(json.dumps(report, indent=2, cls=DecimalEncoder))
        else:
            print(json.dumps(report, cls=DecimalEncoder))
        
        # Set exit code based on status
        status = report.get("summary", {}).get("status", "OK")
        if status == "CRITICAL":
            sys.exit(2)
        elif status == "WARNING":
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        error_report = {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "status": "ERROR"
        }
        print(json.dumps(error_report, indent=2 if args.pretty else None))
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Phase 2.4: Update v_trade_pipeline_status View

### SQL Script

```sql
-- ============================================================================
-- UPDATE v_trade_pipeline_status VIEW
-- ============================================================================
-- Now uses orders table exclusively for order counts
-- ============================================================================

DROP VIEW IF EXISTS v_trade_pipeline_status;

CREATE VIEW v_trade_pipeline_status AS
SELECT
    tc.cycle_id,
    tc.cycle_date,
    tc.status as cycle_status,
    tc.start_time as cycle_start,
    tc.end_time as cycle_end,
    tc.updated_at as cycle_updated,
    
    -- Order counts from orders table
    COALESCE(o_stats.orders_total, 0) as orders_total,
    COALESCE(o_stats.orders_pending, 0) as orders_pending,
    COALESCE(o_stats.orders_filled, 0) as orders_filled,
    COALESCE(o_stats.orders_cancelled, 0) as orders_cancelled,
    
    -- Position counts
    COALESCE(p_stats.positions_total, 0) as positions_total,
    COALESCE(p_stats.positions_open, 0) as positions_open,
    
    -- P&L
    COALESCE(p_stats.daily_pnl, 0) as daily_pnl,
    
    -- Last activity from orders table
    o_stats.last_order_at
    
FROM trading_cycles tc

LEFT JOIN (
    -- Order statistics from orders table
    SELECT
        cycle_id,
        COUNT(*) as orders_total,
        COUNT(*) FILTER (WHERE status IN ('submitted', 'pending_new', 'accepted', 'new', 'created')) as orders_pending,
        COUNT(*) FILTER (WHERE status = 'filled') as orders_filled,
        COUNT(*) FILTER (WHERE status IN ('cancelled', 'rejected', 'expired')) as orders_cancelled,
        MAX(submitted_at) as last_order_at
    FROM orders
    GROUP BY cycle_id
) o_stats ON tc.cycle_id = o_stats.cycle_id

LEFT JOIN (
    -- Position statistics
    SELECT
        cycle_id,
        COUNT(*) as positions_total,
        COUNT(*) FILTER (WHERE status = 'open') as positions_open,
        SUM(COALESCE(realized_pnl, 0) + COALESCE(unrealized_pnl, 0)) as daily_pnl
    FROM positions
    GROUP BY cycle_id
) p_stats ON tc.cycle_id = p_stats.cycle_id

ORDER BY tc.cycle_date DESC, tc.start_time DESC;

-- Grant permissions
GRANT SELECT ON v_trade_pipeline_status TO PUBLIC;
```

---

## Phase 2.5: Complete Execution Script

### All-in-One Script

Create file: `sql/orders-positions-phase2-complete.sql`

```sql
-- ============================================================================
-- ORDERS/POSITIONS PHASE 2: COMPLETE IMPLEMENTATION
-- ============================================================================
-- Run this script to complete Phase 2 of orders/positions separation
-- 
-- Prerequisites:
-- 1. Orders table created and populated (Phase 1 complete)
-- 2. At least one successful trading day with orders table
-- 3. Backup taken before running
--
-- What this script does:
-- 1. Adds order_purpose column to orders table
-- 2. Fixes order side mapping for exit orders
-- 3. Updates v_trade_pipeline_status view
-- 4. Drops legacy columns from positions table
-- ============================================================================

\echo '=============================================='
\echo 'PHASE 2: Orders/Positions Separation Complete'
\echo '=============================================='

BEGIN;

-- ============================================================================
-- STEP 1: Add order_purpose column
-- ============================================================================
\echo 'Step 1: Adding order_purpose column...'

ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_purpose VARCHAR(20);

-- Mark entry orders (first order per position)
UPDATE orders o
SET order_purpose = 'entry'
WHERE order_purpose IS NULL
  AND (
    o.order_id = (
        SELECT MIN(o2.order_id) 
        FROM orders o2 
        WHERE o2.position_id = o.position_id
    )
    OR o.position_id IS NULL
  );

-- Mark exit orders (subsequent orders)
UPDATE orders o
SET order_purpose = 'exit'
WHERE order_purpose IS NULL
  AND o.position_id IS NOT NULL;

-- Mark bracket legs
UPDATE orders o
SET order_purpose = CASE
    WHEN o.order_type = 'stop' OR o.order_type = 'stop_limit' THEN 'stop_loss'
    WHEN o.order_type = 'limit' AND o.parent_order_id IS NOT NULL THEN 'take_profit'
    ELSE o.order_purpose
END
WHERE o.parent_order_id IS NOT NULL;

\echo 'Step 1 complete: order_purpose column populated'

-- ============================================================================
-- STEP 2: Fix order side mapping for exit orders
-- ============================================================================
\echo 'Step 2: Fixing order side mapping...'

-- Long position exit = SELL
UPDATE orders o
SET side = 'sell'
FROM positions p
WHERE o.position_id = p.position_id
  AND o.order_purpose = 'exit'
  AND p.side = 'long'
  AND o.side = 'buy';

-- Short position exit = BUY  
UPDATE orders o
SET side = 'buy'
FROM positions p
WHERE o.position_id = p.position_id
  AND o.order_purpose = 'exit'
  AND p.side = 'short'
  AND o.side = 'sell';

\echo 'Step 2 complete: Order sides fixed'

-- ============================================================================
-- STEP 3: Update v_trade_pipeline_status view
-- ============================================================================
\echo 'Step 3: Updating v_trade_pipeline_status view...'

DROP VIEW IF EXISTS v_trade_pipeline_status;

CREATE VIEW v_trade_pipeline_status AS
SELECT
    tc.cycle_id,
    tc.cycle_date,
    tc.status as cycle_status,
    tc.start_time as cycle_start,
    tc.end_time as cycle_end,
    tc.updated_at as cycle_updated,
    COALESCE(o_stats.orders_total, 0) as orders_total,
    COALESCE(o_stats.orders_pending, 0) as orders_pending,
    COALESCE(o_stats.orders_filled, 0) as orders_filled,
    COALESCE(o_stats.orders_cancelled, 0) as orders_cancelled,
    COALESCE(p_stats.positions_total, 0) as positions_total,
    COALESCE(p_stats.positions_open, 0) as positions_open,
    COALESCE(p_stats.daily_pnl, 0) as daily_pnl,
    o_stats.last_order_at
FROM trading_cycles tc
LEFT JOIN (
    SELECT
        cycle_id,
        COUNT(*) as orders_total,
        COUNT(*) FILTER (WHERE status IN ('submitted', 'pending_new', 'accepted', 'new', 'created')) as orders_pending,
        COUNT(*) FILTER (WHERE status = 'filled') as orders_filled,
        COUNT(*) FILTER (WHERE status IN ('cancelled', 'rejected', 'expired')) as orders_cancelled,
        MAX(submitted_at) as last_order_at
    FROM orders
    GROUP BY cycle_id
) o_stats ON tc.cycle_id = o_stats.cycle_id
LEFT JOIN (
    SELECT
        cycle_id,
        COUNT(*) as positions_total,
        COUNT(*) FILTER (WHERE status = 'open') as positions_open,
        SUM(COALESCE(realized_pnl, 0) + COALESCE(unrealized_pnl, 0)) as daily_pnl
    FROM positions
    GROUP BY cycle_id
) p_stats ON tc.cycle_id = p_stats.cycle_id
ORDER BY tc.cycle_date DESC, tc.start_time DESC;

GRANT SELECT ON v_trade_pipeline_status TO PUBLIC;

\echo 'Step 3 complete: View updated'

-- ============================================================================
-- STEP 4: Drop legacy columns from positions table
-- ============================================================================
\echo 'Step 4: Dropping legacy columns from positions table...'

ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_order_id;
ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_status;

\echo 'Step 4 complete: Legacy columns dropped'

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
\echo ''
\echo '=============================================='
\echo 'VERIFICATION'
\echo '=============================================='

\echo 'Order purpose distribution:'
SELECT order_purpose, side, COUNT(*) as count
FROM orders
GROUP BY order_purpose, side
ORDER BY order_purpose, side;

\echo ''
\echo 'Positions table columns (should NOT have alpaca_order_id or alpaca_status):'
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'positions'
ORDER BY ordinal_position;

\echo ''
\echo 'Orders table columns (should have order_purpose):'
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'orders'
ORDER BY ordinal_position;

\echo ''
\echo '=============================================='
\echo 'PHASE 2 COMPLETE'
\echo '=============================================='
```

---

## Execution Commands

### Step-by-Step Execution

```bash
cd /root/catalyst-trading-system

# 1. Create the SQL file
cat > sql/orders-positions-phase2-complete.sql << 'EOF'
# [paste the complete SQL script above]
EOF

# 2. Take a backup first
pg_dump $DATABASE_URL > /backups/catalyst/pre-phase2-$(date +%Y%m%d_%H%M%S).sql

# 3. Execute Phase 2
psql $DATABASE_URL -f sql/orders-positions-phase2-complete.sql

# 4. Update trade_watchdog.py
cp scripts/trade_watchdog.py scripts/trade_watchdog.py.backup
# [update with v1.2.0 code]

# 5. Test the watchdog
python3 scripts/trade_watchdog.py --pretty

# 6. Commit changes
git add -A
git commit -m "feat(orders): Complete Phase 2 - drop legacy columns, fix order sides

Phase 2 of orders/positions separation:
- Added order_purpose column (entry/exit/stop_loss/take_profit)
- Fixed order side mapping for exit orders
- Updated v_trade_pipeline_status view to use orders table only
- Dropped legacy columns from positions table (alpaca_order_id, alpaca_status)
- Updated trade_watchdog.py to v1.2.0"

git push origin main
```

---

## Rollback Script (Emergency)

If anything goes wrong:

```sql
-- ============================================================================
-- ROLLBACK: Restore legacy columns (EMERGENCY ONLY)
-- ============================================================================

BEGIN;

-- Re-add columns
ALTER TABLE positions ADD COLUMN IF NOT EXISTS alpaca_order_id VARCHAR(100);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS alpaca_status VARCHAR(50);

-- Restore data from orders table
UPDATE positions p
SET 
    alpaca_order_id = o.alpaca_order_id,
    alpaca_status = o.status
FROM orders o
WHERE o.position_id = p.position_id
  AND o.order_purpose = 'entry';

COMMIT;

\echo 'Rollback complete - legacy columns restored'
```

---

## Verification Checklist

After running Phase 2, verify:

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Legacy columns gone | `\d positions` | No `alpaca_order_id` or `alpaca_status` |
| order_purpose populated | `SELECT DISTINCT order_purpose FROM orders;` | entry, exit, stop_loss, take_profit |
| View works | `SELECT * FROM v_trade_pipeline_status LIMIT 1;` | No errors |
| Watchdog runs | `python3 scripts/trade_watchdog.py --pretty` | JSON output, no errors |
| No hardcoded position queries | `grep -r "positions.*alpaca" scripts/` | No matches |

---

**END OF IMPLEMENTATION GUIDE**

*Generated by Claude Desktop*  
*Catalyst Trading System*  
*December 27, 2025*
