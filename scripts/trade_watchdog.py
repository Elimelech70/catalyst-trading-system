#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trade_watchdog.py
Version: 1.0.0
Last Updated: 2025-12-27
Purpose: Real-time trade lifecycle monitoring for Doctor Claude

REVISION HISTORY:
v1.0.0 (2025-12-27) - Initial implementation
- Pipeline status check from v_trade_pipeline_status view
- Stuck order detection
- Position reconciliation with Alpaca
- Order status sync verification
- Structured JSON output for Claude Code parsing

Usage:
    python3 trade_watchdog.py              # Run once, output JSON
    python3 trade_watchdog.py --pretty     # Pretty print output
    python3 trade_watchdog.py --help       # Show help

Exit Codes:
    0 = OK (no issues)
    1 = WARNING (non-critical issues found)
    2 = CRITICAL (critical issues found)
    3 = ERROR (script failed to run)

Dependencies:
    pip install asyncpg alpaca-py

Environment Variables:
    DATABASE_URL        - PostgreSQL connection string
    ALPACA_API_KEY      - Alpaca API key
    ALPACA_SECRET_KEY   - Alpaca secret key
    ALPACA_PAPER        - 'true' for paper trading (default), 'false' for live
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

DATABASE_URL = os.environ.get('DATABASE_URL')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY')
ALPACA_PAPER = os.environ.get('ALPACA_PAPER', 'true').lower() == 'true'

# Thresholds (configurable)
STUCK_ORDER_MINUTES = int(os.environ.get('STUCK_ORDER_MINUTES', '5'))
STALE_CYCLE_MINUTES = int(os.environ.get('STALE_CYCLE_MINUTES', '30'))
QTY_MISMATCH_THRESHOLD = float(os.environ.get('QTY_MISMATCH_THRESHOLD', '0.1'))  # 10%


# ============================================================================
# JSON ENCODER FOR SPECIAL TYPES
# ============================================================================

class CustomJSONEncoder(json.JSONEncoder):
    """Handle Decimal, datetime, UUID types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__str__'):
            return str(obj)
        return super().default(obj)


# ============================================================================
# WATCHDOG CLASS
# ============================================================================

class TradeWatchdog:
    """Trade lifecycle monitoring and diagnostics for Doctor Claude"""
    
    def __init__(self):
        self.db: Optional[asyncpg.Connection] = None
        self.alpaca: Optional[TradingClient] = None
        self.issues: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        
    async def connect(self):
        """Establish database and broker connections"""
        # Database connection
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
        
        try:
            self.db = await asyncpg.connect(DATABASE_URL)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {str(e)}")
        
        # Alpaca connection (optional - graceful degradation)
        if ALPACA_AVAILABLE and ALPACA_API_KEY and ALPACA_SECRET_KEY:
            try:
                self.alpaca = TradingClient(
                    ALPACA_API_KEY, 
                    ALPACA_SECRET_KEY, 
                    paper=ALPACA_PAPER
                )
                # Test connection
                self.alpaca.get_account()
            except Exception as e:
                self.alpaca = None
                self.issues.append({
                    "type": "ALPACA_CONNECTION_ERROR",
                    "severity": "WARNING",
                    "message": f"Could not connect to Alpaca: {str(e)}",
                    "fix": None
                })
        else:
            if not ALPACA_AVAILABLE:
                self.issues.append({
                    "type": "ALPACA_NOT_INSTALLED",
                    "severity": "INFO",
                    "message": "alpaca-py not installed - broker reconciliation disabled",
                    "fix": "pip install alpaca-py"
                })
    
    async def close(self):
        """Clean up connections"""
        if self.db:
            await self.db.close()

    # ========================================================================
    # CHECK: Pipeline Status
    # ========================================================================
    
    async def check_pipeline_status(self) -> Dict[str, Any]:
        """Get current trade pipeline status from view"""
        
        # First check if view exists
        view_exists = await self.db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_views WHERE viewname = 'v_trade_pipeline_status'
            )
        """)
        
        if not view_exists:
            # Fallback to direct query if view not created yet
            return await self._check_pipeline_status_fallback()
        
        row = await self.db.fetchrow("""
            SELECT * FROM v_trade_pipeline_status
            WHERE date = CURRENT_DATE
            ORDER BY started_at DESC
            LIMIT 1
        """)
        
        if not row:
            return {
                "status": "NO_CYCLE",
                "message": "No trading cycle found for today",
                "cycle_id": None
            }
        
        return {
            "status": "OK",
            "cycle_id": str(row['cycle_id']),
            "date": str(row['date']),
            "state": row['cycle_state'],
            "phase": row.get('phase'),
            "mode": row.get('mode'),
            "pipeline_stage": row.get('pipeline_stage', 'UNKNOWN'),
            "started_at": row['started_at'].isoformat() if row['started_at'] else None,
            "last_activity": row['last_activity'].isoformat() if row['last_activity'] else None,
            "minutes_since_activity": round(float(row['minutes_since_activity'] or 0), 1),
            "counts": {
                "candidates": row.get('candidates_found', 0),
                "positions_total": row.get('positions_total', 0),
                "positions_open": row.get('positions_open', 0),
                "positions_closed": row.get('positions_closed', 0),
                "orders_total": row.get('orders_total', 0),
                "orders_pending": row.get('orders_pending', 0),
                "orders_filled": row.get('orders_filled', 0),
                "orders_cancelled": row.get('orders_cancelled', 0),
                "orders_rejected": row.get('orders_rejected', 0)
            },
            "pnl": {
                "daily": float(row['daily_pnl'] or 0),
                "realized": float(row.get('realized_pnl') or 0),
                "unrealized": float(row.get('unrealized_pnl') or 0)
            },
            "trades": {
                "executed": row.get('trades_executed', 0),
                "won": row.get('trades_won', 0),
                "lost": row.get('trades_lost', 0)
            }
        }

    async def _check_pipeline_status_fallback(self) -> Dict[str, Any]:
        """Fallback pipeline check if view doesn't exist"""
        row = await self.db.fetchrow("""
            SELECT 
                tc.cycle_id,
                tc.date,
                tc.cycle_state,
                tc.started_at,
                tc.daily_pnl,
                tc.trades_executed,
                tc.trades_won,
                tc.trades_lost,
                tc.updated_at,
                (SELECT COUNT(*) FROM scan_results sr WHERE sr.cycle_id = tc.cycle_id) as candidates,
                (SELECT COUNT(*) FROM positions p WHERE p.cycle_id = tc.cycle_id) as positions_total,
                (SELECT COUNT(*) FROM positions p WHERE p.cycle_id = tc.cycle_id AND p.status = 'open') as positions_open
            FROM trading_cycles tc
            WHERE tc.date = CURRENT_DATE
            ORDER BY tc.started_at DESC
            LIMIT 1
        """)
        
        if not row:
            return {
                "status": "NO_CYCLE",
                "message": "No trading cycle found for today",
                "cycle_id": None
            }
        
        minutes_since = 0
        if row['updated_at']:
            minutes_since = (datetime.now(row['updated_at'].tzinfo) - row['updated_at']).total_seconds() / 60
        
        return {
            "status": "OK",
            "cycle_id": str(row['cycle_id']),
            "date": str(row['date']),
            "state": row['cycle_state'],
            "pipeline_stage": "FALLBACK_QUERY",
            "started_at": row['started_at'].isoformat() if row['started_at'] else None,
            "last_activity": row['updated_at'].isoformat() if row['updated_at'] else None,
            "minutes_since_activity": round(minutes_since, 1),
            "counts": {
                "candidates": row['candidates'],
                "positions_total": row['positions_total'],
                "positions_open": row['positions_open']
            },
            "pnl": {
                "daily": float(row['daily_pnl'] or 0)
            },
            "trades": {
                "executed": row.get('trades_executed', 0),
                "won": row.get('trades_won', 0),
                "lost": row.get('trades_lost', 0)
            }
        }

    # ========================================================================
    # CHECK: Stuck Orders
    # ========================================================================
    
    async def check_stuck_orders(self) -> List[Dict[str, Any]]:
        """Find orders that have been pending too long"""
        stuck = await self.db.fetch(f"""
            SELECT
                p.position_id,
                p.alpaca_order_id,
                s.symbol,
                p.alpaca_status as status,
                p.side,
                'limit' as order_type,
                p.quantity,
                p.opened_at as submitted_at,
                EXTRACT(EPOCH FROM (NOW() - p.opened_at))/60 as minutes_pending
            FROM positions p
            JOIN securities s ON p.security_id = s.security_id
            WHERE p.alpaca_status IN ('submitted', 'pending_new', 'accepted', 'new')
              AND p.opened_at < NOW() - INTERVAL '{STUCK_ORDER_MINUTES} minutes'
        """)

        issues = []
        for row in stuck:
            issues.append({
                "type": "STUCK_ORDER",
                "severity": "WARNING",
                "position_id": str(row['position_id']),
                "alpaca_order_id": row['alpaca_order_id'],
                "symbol": row['symbol'],
                "side": row['side'],
                "order_type": row['order_type'],
                "quantity": row['quantity'],
                "minutes_pending": round(float(row['minutes_pending']), 1),
                "message": f"Order {row['symbol']} {row['side']} {row['quantity']} pending for {round(float(row['minutes_pending']))} minutes",
                "fix": None  # Requires manual review - may be market conditions
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
                "message": "Alpaca not connected - position reconciliation skipped",
                "fix": None
            }]
        
        # Get DB open positions
        db_positions = await self.db.fetch("""
            SELECT 
                p.position_id,
                s.symbol,
                p.quantity,
                p.side,
                p.entry_price,
                p.status
            FROM positions p
            JOIN securities s ON p.security_id = s.security_id
            WHERE p.status = 'open'
        """)
        db_map = {row['symbol']: dict(row) for row in db_positions}
        
        # Get Alpaca positions
        try:
            alpaca_positions = self.alpaca.get_all_positions()
            alpaca_map = {p.symbol: p for p in alpaca_positions}
        except Exception as e:
            return [{
                "type": "ALPACA_API_ERROR",
                "severity": "CRITICAL",
                "message": f"Failed to fetch Alpaca positions: {str(e)}",
                "fix": None
            }]
        
        issues = []
        
        # PHANTOM: In DB but not in Alpaca
        for symbol, db_pos in db_map.items():
            if symbol not in alpaca_map:
                issues.append({
                    "type": "PHANTOM_POSITION",
                    "severity": "CRITICAL",
                    "symbol": symbol,
                    "position_id": str(db_pos['position_id']),
                    "db_qty": db_pos['quantity'],
                    "db_side": db_pos['side'],
                    "message": f"Position {symbol} exists in DB but not in Alpaca",
                    "fix": f"UPDATE positions SET status = 'closed', exit_time = NOW(), updated_at = NOW() WHERE position_id = '{db_pos['position_id']}'"
                })
        
        # ORPHAN: In Alpaca but not in DB
        for symbol, alpaca_pos in alpaca_map.items():
            if symbol not in db_map:
                issues.append({
                    "type": "ORPHAN_POSITION",
                    "severity": "CRITICAL",
                    "symbol": symbol,
                    "alpaca_qty": int(float(alpaca_pos.qty)),
                    "alpaca_side": alpaca_pos.side.value if hasattr(alpaca_pos.side, 'value') else str(alpaca_pos.side),
                    "alpaca_market_value": float(alpaca_pos.market_value),
                    "alpaca_unrealized_pl": float(alpaca_pos.unrealized_pl),
                    "message": f"Position {symbol} in Alpaca not tracked in DB - REAL MONEY",
                    "fix": None  # Requires manual review - real money involved
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
                    "fix": f"UPDATE positions SET quantity = {alpaca_qty}, updated_at = NOW() WHERE position_id = '{db_map[symbol]['position_id']}'"
                })
        
        return issues

    # ========================================================================
    # CHECK: Order Status Sync
    # ========================================================================
    
    async def check_order_sync(self) -> List[Dict[str, Any]]:
        """Verify DB order statuses match Alpaca"""
        if not self.alpaca:
            return []

        # Get recent non-terminal positions from DB (using positions table)
        db_positions = await self.db.fetch("""
            SELECT
                p.position_id,
                p.alpaca_order_id,
                p.alpaca_status as db_status,
                p.entry_price as db_filled_price,
                s.symbol,
                p.side,
                p.quantity
            FROM positions p
            JOIN securities s ON p.security_id = s.security_id
            WHERE p.alpaca_order_id IS NOT NULL
              AND p.alpaca_status NOT IN ('filled', 'cancelled', 'rejected', 'expired')
              AND p.opened_at > NOW() - INTERVAL '24 hours'
        """)

        if not db_positions:
            return []

        issues = []

        for row in db_positions:
            try:
                alpaca_order = self.alpaca.get_order_by_id(row['alpaca_order_id'])
                alpaca_status = alpaca_order.status.value.lower() if hasattr(alpaca_order.status, 'value') else str(alpaca_order.status).lower()
                alpaca_filled_qty = int(float(alpaca_order.filled_qty or 0))
                alpaca_filled_price = float(alpaca_order.filled_avg_price or 0) if alpaca_order.filled_avg_price else None

                # Status mismatch
                if alpaca_status != row['db_status']:
                    fix_parts = [f"UPDATE positions SET alpaca_status = '{alpaca_status}'"]

                    # If filled, also update fill details
                    if alpaca_status == 'filled' and alpaca_filled_price:
                        fix_parts.append(f"entry_price = {alpaca_filled_price}")

                    fix_parts.append("updated_at = NOW()")
                    fix_sql = ", ".join(fix_parts[1:])
                    fix_sql = f"UPDATE positions SET alpaca_status = '{alpaca_status}', {fix_sql} WHERE position_id = {row['position_id']}"

                    issues.append({
                        "type": "ORDER_STATUS_MISMATCH",
                        "severity": "WARNING",
                        "position_id": str(row['position_id']),
                        "alpaca_order_id": row['alpaca_order_id'],
                        "symbol": row['symbol'],
                        "side": row['side'],
                        "db_status": row['db_status'],
                        "alpaca_status": alpaca_status,
                        "alpaca_filled_qty": alpaca_filled_qty,
                        "alpaca_filled_price": alpaca_filled_price,
                        "message": f"Position {row['symbol']} status: DB={row['db_status']}, Alpaca={alpaca_status}",
                        "fix": fix_sql
                    })

            except Exception as e:
                error_str = str(e)
                # Order might not exist in Alpaca anymore
                if 'not found' in error_str.lower() or '404' in error_str:
                    issues.append({
                        "type": "ORDER_NOT_FOUND",
                        "severity": "WARNING",
                        "position_id": str(row['position_id']),
                        "alpaca_order_id": row['alpaca_order_id'],
                        "symbol": row['symbol'],
                        "db_status": row['db_status'],
                        "message": f"Order {row['alpaca_order_id']} not found in Alpaca - may be expired",
                        "fix": f"UPDATE positions SET alpaca_status = 'expired', updated_at = NOW() WHERE position_id = {row['position_id']}"
                    })
                else:
                    issues.append({
                        "type": "ORDER_FETCH_ERROR",
                        "severity": "WARNING",
                        "position_id": str(row['position_id']),
                        "alpaca_order_id": row['alpaca_order_id'],
                        "symbol": row['symbol'],
                        "message": f"Could not fetch Alpaca order: {error_str}",
                        "fix": None
                    })

        return issues

    # ========================================================================
    # CHECK: Stale Cycle
    # ========================================================================
    
    async def check_stale_cycle(self, pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if cycle has gone stale (no activity)"""
        issues = []
        
        if pipeline.get('status') != 'OK':
            return issues
        
        minutes_inactive = pipeline.get('minutes_since_activity', 0)
        state = pipeline.get('state')
        
        # Only alert if cycle is supposed to be active
        active_states = ('scanning', 'evaluating', 'trading', 'monitoring', 'active')
        if state and state.lower() in active_states:
            if minutes_inactive > STALE_CYCLE_MINUTES:
                issues.append({
                    "type": "CYCLE_STALE",
                    "severity": "WARNING",
                    "cycle_id": pipeline.get('cycle_id'),
                    "state": state,
                    "minutes_inactive": round(minutes_inactive, 1),
                    "threshold_minutes": STALE_CYCLE_MINUTES,
                    "message": f"Cycle in '{state}' state with no activity for {round(minutes_inactive)} minutes",
                    "fix": None  # May be expected during quiet periods
                })
        
        return issues

    # ========================================================================
    # CHECK: Pending Position Updates
    # ========================================================================
    
    async def check_position_pnl_sync(self) -> List[Dict[str, Any]]:
        """Check if open positions have stale P&L data"""
        if not self.alpaca:
            return []
        
        issues = []
        
        # Get positions that haven't been updated recently
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
            
            report = {
                "timestamp": end_time.isoformat(),
                "duration_ms": duration_ms,
                "alpaca_connected": self.alpaca is not None,
                "alpaca_mode": "paper" if ALPACA_PAPER else "live",
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
            
            return report
            
        finally:
            await self.close()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description='Trade Watchdog - Pipeline Monitoring for Doctor Claude',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0  OK       - No issues found
  1  WARNING  - Non-critical issues found
  2  CRITICAL - Critical issues found  
  3  ERROR    - Script failed to run

Examples:
  python3 trade_watchdog.py              # Standard JSON output
  python3 trade_watchdog.py --pretty     # Human-readable output
        """
    )
    parser.add_argument('--pretty', action='store_true', help='Pretty print JSON output')
    parser.add_argument('--version', action='version', version='trade_watchdog.py v1.0.0')
    args = parser.parse_args()
    
    try:
        watchdog = TradeWatchdog()
        report = await watchdog.run_full_check()
        
        # Output JSON
        if args.pretty:
            print(json.dumps(report, indent=2, cls=CustomJSONEncoder))
        else:
            print(json.dumps(report, cls=CustomJSONEncoder))
        
        # Exit code based on status
        status = report["summary"]["status"]
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
            "error_type": type(e).__name__,
            "summary": {"status": "ERROR", "total_issues": 0, "critical": 0, "warnings": 0}
        }
        print(json.dumps(error_report, cls=CustomJSONEncoder))
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())
