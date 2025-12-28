#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: trade_watchdog.py
Version: 2.0.0
Last Updated: 2025-12-27
Purpose: Doctor Claude monitoring script - uses orders table (C1 fix)

REVISION HISTORY:
v2.0.0 (2025-12-27) - C1 Fix: Uses orders table instead of positions.alpaca_*
  - Queries orders table for order status
  - Detects stuck orders from orders table
  - Reconciles orders (not positions) with Alpaca
  - Updated v_trade_pipeline_status view usage

v1.1.0 (2025-12-20) - Added order monitoring from positions.alpaca_* columns
v1.0.0 (2025-12-15) - Initial Doctor Claude implementation

USAGE:
    python3 trade_watchdog.py           # Normal output (JSON)
    python3 trade_watchdog.py --pretty  # Pretty-printed output
    python3 trade_watchdog.py --verbose # Include all details

CRON:
    */5 9-16 * * 1-5 python3 /path/to/trade_watchdog.py >> /var/log/doctor_claude.log

ARCHITECTURE:
    This script follows ARCHITECTURE-RULES.md Rule 1: Orders ≠ Positions
    - Order status is tracked in the 'orders' table
    - Position status is tracked in the 'positions' table
    - Never query positions.alpaca_* columns (they should not exist)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('doctor_claude')

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# Thresholds
STUCK_ORDER_THRESHOLD_MINUTES = 5
MAX_PENDING_ORDERS = 10
DAILY_LOSS_WARNING_PCT = 1.5
DAILY_LOSS_HALT_PCT = 2.0

# ============================================================================
# DATABASE QUERIES - USING ORDERS TABLE (C1 FIX)
# ============================================================================

async def get_order_status_counts(conn: asyncpg.Connection) -> Dict[str, int]:
    """
    Get order counts by status from the ORDERS table.
    
    C1 FIX: Uses orders table, NOT positions.alpaca_* columns.
    """
    result = await conn.fetch("""
        SELECT 
            status,
            COUNT(*) as count
        FROM orders
        GROUP BY status
    """)
    
    counts = {row['status']: row['count'] for row in result}
    return {
        'total': sum(counts.values()),
        'created': counts.get('created', 0),
        'submitted': counts.get('submitted', 0),
        'accepted': counts.get('accepted', 0),
        'filled': counts.get('filled', 0),
        'partial_fill': counts.get('partial_fill', 0),
        'cancelled': counts.get('cancelled', 0) + counts.get('canceled', 0),
        'rejected': counts.get('rejected', 0),
        'expired': counts.get('expired', 0),
        'pending': (
            counts.get('created', 0) + 
            counts.get('submitted', 0) + 
            counts.get('accepted', 0) +
            counts.get('pending_new', 0) +
            counts.get('new', 0)
        )
    }


async def get_stuck_orders(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Find orders that are stuck (pending for too long).
    
    C1 FIX: Queries orders table directly.
    """
    threshold = datetime.utcnow() - timedelta(minutes=STUCK_ORDER_THRESHOLD_MINUTES)
    
    result = await conn.fetch("""
        SELECT 
            o.order_id,
            o.alpaca_order_id,
            s.symbol,
            o.side,
            o.order_type,
            o.order_purpose,
            o.quantity,
            o.status,
            o.submitted_at,
            EXTRACT(EPOCH FROM (NOW() - o.submitted_at))/60 as minutes_pending
        FROM orders o
        JOIN securities s ON o.security_id = s.security_id
        WHERE o.status IN ('created', 'submitted', 'accepted', 'pending_new', 'new')
          AND o.submitted_at IS NOT NULL
          AND o.submitted_at < $1
        ORDER BY o.submitted_at ASC
    """, threshold)
    
    return [dict(row) for row in result]


async def get_unlinked_orders(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Find filled entry orders without linked positions.
    
    These are orders that filled but position creation failed.
    """
    result = await conn.fetch("""
        SELECT 
            o.order_id,
            o.alpaca_order_id,
            s.symbol,
            o.side,
            o.quantity,
            o.filled_qty,
            o.filled_avg_price,
            o.filled_at
        FROM orders o
        JOIN securities s ON o.security_id = s.security_id
        WHERE o.status = 'filled'
          AND o.order_purpose = 'entry'
          AND o.position_id IS NULL
        ORDER BY o.filled_at DESC
    """)
    
    return [dict(row) for row in result]


async def get_position_counts(conn: asyncpg.Connection) -> Dict[str, int]:
    """Get position counts by status."""
    result = await conn.fetch("""
        SELECT 
            status,
            COUNT(*) as count
        FROM positions
        GROUP BY status
    """)
    
    counts = {row['status']: row['count'] for row in result}
    return {
        'total': sum(counts.values()),
        'open': counts.get('open', 0),
        'closed': counts.get('closed', 0),
        'cancelled': counts.get('cancelled', 0),
        'failed': counts.get('failed', 0)
    }


async def get_daily_pnl(conn: asyncpg.Connection) -> Dict[str, float]:
    """Get today's P&L summary."""
    result = await conn.fetchrow("""
        SELECT 
            COALESCE(SUM(realized_pnl), 0) as realized_pnl,
            COALESCE(SUM(unrealized_pnl), 0) as unrealized_pnl
        FROM positions
        WHERE DATE(created_at) = CURRENT_DATE
    """)
    
    realized = float(result['realized_pnl']) if result else 0.0
    unrealized = float(result['unrealized_pnl']) if result else 0.0
    
    return {
        'realized_pnl': realized,
        'unrealized_pnl': unrealized,
        'total_pnl': realized + unrealized
    }


async def get_pipeline_status(conn: asyncpg.Connection) -> Dict[str, Any]:
    """
    Get trade pipeline status from the updated view.
    
    C1 FIX: This view now uses orders table for order counts.
    """
    result = await conn.fetchrow("""
        SELECT *
        FROM v_trade_pipeline_status
        ORDER BY cycle_date DESC
        LIMIT 1
    """)
    
    if result:
        return dict(result)
    return {}


# ============================================================================
# ALPACA RECONCILIATION
# ============================================================================

async def get_alpaca_orders() -> List[Dict[str, Any]]:
    """Fetch open orders from Alpaca API."""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        logger.warning("Alpaca credentials not configured")
        return []
    
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=(TRADING_MODE == "paper")
        )
        
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = client.get_orders(request)
        
        return [
            {
                'alpaca_order_id': str(order.id),
                'symbol': order.symbol,
                'side': order.side.value,
                'quantity': int(order.qty),
                'filled_qty': int(order.filled_qty or 0),
                'status': order.status.value,
                'submitted_at': order.submitted_at.isoformat() if order.submitted_at else None
            }
            for order in orders
        ]
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca orders: {e}")
        return []


async def get_alpaca_positions() -> List[Dict[str, Any]]:
    """Fetch positions from Alpaca API."""
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        logger.warning("Alpaca credentials not configured")
        return []
    
    try:
        from alpaca.trading.client import TradingClient
        
        client = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=(TRADING_MODE == "paper")
        )
        
        positions = client.get_all_positions()
        
        return [
            {
                'symbol': pos.symbol,
                'quantity': int(pos.qty),
                'side': 'long' if float(pos.qty) > 0 else 'short',
                'entry_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'unrealized_pnl': float(pos.unrealized_pl)
            }
            for pos in positions
        ]
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca positions: {e}")
        return []


async def reconcile_orders(conn: asyncpg.Connection, alpaca_orders: List[Dict]) -> List[Dict[str, Any]]:
    """
    Reconcile database orders with Alpaca orders.
    
    C1 FIX: Compares orders table with Alpaca, not positions.alpaca_* columns.
    """
    issues = []
    
    # Get database orders that should be open
    db_orders = await conn.fetch("""
        SELECT 
            o.order_id,
            o.alpaca_order_id,
            s.symbol,
            o.status as db_status
        FROM orders o
        JOIN securities s ON o.security_id = s.security_id
        WHERE o.status IN ('submitted', 'accepted', 'pending_new', 'new', 'partial_fill')
          AND o.alpaca_order_id IS NOT NULL
    """)
    
    alpaca_ids = {o['alpaca_order_id'] for o in alpaca_orders}
    db_ids = {row['alpaca_order_id'] for row in db_orders}
    
    # Orders in DB but not in Alpaca (may have been filled/cancelled)
    for row in db_orders:
        if row['alpaca_order_id'] not in alpaca_ids:
            issues.append({
                'type': 'ORDER_NOT_IN_ALPACA',
                'severity': 'WARNING',
                'order_id': row['order_id'],
                'alpaca_order_id': row['alpaca_order_id'],
                'symbol': row['symbol'],
                'db_status': row['db_status'],
                'message': f"Order {row['alpaca_order_id']} is {row['db_status']} in DB but not found in Alpaca open orders"
            })
    
    # Orders in Alpaca but not in DB (should not happen)
    for order in alpaca_orders:
        if order['alpaca_order_id'] not in db_ids:
            issues.append({
                'type': 'ORDER_NOT_IN_DB',
                'severity': 'CRITICAL',
                'alpaca_order_id': order['alpaca_order_id'],
                'symbol': order['symbol'],
                'status': order['status'],
                'message': f"Alpaca order {order['alpaca_order_id']} not found in database"
            })
    
    return issues


async def reconcile_positions(conn: asyncpg.Connection, alpaca_positions: List[Dict]) -> List[Dict[str, Any]]:
    """Reconcile database positions with Alpaca positions."""
    issues = []
    
    # Get open positions from database
    db_positions = await conn.fetch("""
        SELECT 
            p.position_id,
            s.symbol,
            p.quantity as db_qty,
            p.side as db_side
        FROM positions p
        JOIN securities s ON p.security_id = s.security_id
        WHERE p.status = 'open'
    """)
    
    db_symbols = {row['symbol']: row for row in db_positions}
    alpaca_symbols = {p['symbol']: p for p in alpaca_positions}
    
    # Positions in DB but not in Alpaca
    for symbol, db_pos in db_symbols.items():
        if symbol not in alpaca_symbols:
            issues.append({
                'type': 'POSITION_NOT_IN_ALPACA',
                'severity': 'WARNING',
                'symbol': symbol,
                'position_id': db_pos['position_id'],
                'db_qty': db_pos['db_qty'],
                'message': f"Position {symbol} is open in DB but not found in Alpaca"
            })
    
    # Positions in Alpaca but not in DB
    for symbol, alpaca_pos in alpaca_symbols.items():
        if symbol not in db_symbols:
            issues.append({
                'type': 'POSITION_NOT_IN_DB',
                'severity': 'CRITICAL',
                'symbol': symbol,
                'alpaca_qty': alpaca_pos['quantity'],
                'message': f"Alpaca position {symbol} not found in database"
            })
    
    # Quantity mismatches
    for symbol in set(db_symbols.keys()) & set(alpaca_symbols.keys()):
        db_qty = db_symbols[symbol]['db_qty']
        alpaca_qty = alpaca_symbols[symbol]['quantity']
        
        if db_qty != alpaca_qty:
            issues.append({
                'type': 'QUANTITY_MISMATCH',
                'severity': 'WARNING',
                'symbol': symbol,
                'db_qty': db_qty,
                'alpaca_qty': alpaca_qty,
                'message': f"Position {symbol} quantity mismatch: DB={db_qty}, Alpaca={alpaca_qty}"
            })
    
    return issues


# ============================================================================
# MAIN DIAGNOSTIC
# ============================================================================

async def run_diagnostic(verbose: bool = False) -> Dict[str, Any]:
    """
    Run full Doctor Claude diagnostic.
    
    Returns structured JSON output for Claude Code parsing.
    """
    if not DATABASE_URL:
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'ERROR',
            'error': 'DATABASE_URL not configured',
            'issues': []
        }
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Gather all data
        order_counts = await get_order_status_counts(conn)
        stuck_orders = await get_stuck_orders(conn)
        unlinked_orders = await get_unlinked_orders(conn)
        position_counts = await get_position_counts(conn)
        daily_pnl = await get_daily_pnl(conn)
        pipeline_status = await get_pipeline_status(conn)
        
        # Alpaca reconciliation
        alpaca_orders = await get_alpaca_orders()
        alpaca_positions = await get_alpaca_positions()
        
        order_issues = await reconcile_orders(conn, alpaca_orders)
        position_issues = await reconcile_positions(conn, alpaca_positions)
        
        await conn.close()
        
        # Compile all issues
        issues = []
        
        # Check for stuck orders
        for order in stuck_orders:
            issues.append({
                'type': 'STUCK_ORDER',
                'severity': 'WARNING',
                'order_id': order['order_id'],
                'alpaca_order_id': order['alpaca_order_id'],
                'symbol': order['symbol'],
                'minutes_pending': float(order['minutes_pending']),
                'message': f"Order {order['symbol']} stuck in {order['status']} for {order['minutes_pending']:.1f} minutes"
            })
        
        # Check for unlinked orders
        for order in unlinked_orders:
            issues.append({
                'type': 'UNLINKED_ORDER',
                'severity': 'CRITICAL',
                'order_id': order['order_id'],
                'symbol': order['symbol'],
                'filled_qty': order['filled_qty'],
                'message': f"Filled order {order['symbol']} has no linked position"
            })
        
        # Add reconciliation issues
        issues.extend(order_issues)
        issues.extend(position_issues)
        
        # Determine overall status
        critical_count = sum(1 for i in issues if i['severity'] == 'CRITICAL')
        warning_count = sum(1 for i in issues if i['severity'] == 'WARNING')
        
        if critical_count > 0:
            status = 'CRITICAL'
        elif warning_count > 0:
            status = 'WARNING'
        else:
            status = 'HEALTHY'
        
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': status,
            'version': '2.0.0',  # C1 fix version
            'orders': order_counts,
            'positions': position_counts,
            'daily_pnl': daily_pnl,
            'stuck_orders': len(stuck_orders),
            'unlinked_orders': len(unlinked_orders),
            'alpaca': {
                'open_orders': len(alpaca_orders),
                'open_positions': len(alpaca_positions)
            },
            'issues': issues,
            'issue_summary': {
                'critical': critical_count,
                'warning': warning_count,
                'total': len(issues)
            }
        }
        
        if verbose:
            result['stuck_orders_detail'] = stuck_orders
            result['unlinked_orders_detail'] = unlinked_orders
            result['pipeline_status'] = pipeline_status
        
        return result
        
    except Exception as e:
        logger.error(f"Diagnostic failed: {e}")
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'ERROR',
            'error': str(e),
            'issues': []
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Doctor Claude Trade Watchdog v2.0.0 (C1 Fix)'
    )
    parser.add_argument('--pretty', action='store_true', help='Pretty-print output')
    parser.add_argument('--verbose', action='store_true', help='Include detailed info')
    
    args = parser.parse_args()
    
    result = asyncio.run(run_diagnostic(verbose=args.verbose))
    
    if args.pretty:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps(result, default=str))
    
    # Exit code based on status
    if result['status'] == 'CRITICAL':
        sys.exit(2)
    elif result['status'] == 'WARNING':
        sys.exit(1)
    elif result['status'] == 'ERROR':
        sys.exit(3)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
