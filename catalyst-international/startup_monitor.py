"""
Name of Application: Catalyst Trading System
Name of file: startup_monitor.py
Version: 1.1.0
Last Updated: 2026-01-10
Purpose: Pre-market position reconciliation and monitor startup

REVISION HISTORY:
v1.1.0 (2026-01-10) - Added broker position sync
- Syncs positions from Moomoo to database
- Adds missing positions, closes stale ones

v1.0.0 (2026-01-10) - Initial implementation

Description:
Called at pre-market to ensure every open position has an active monitor.
1. Syncs broker positions to database (adds new, closes stale)
2. Reconciles positions vs monitors, starts missing monitors, stops orphaned ones.
Records reconciliation results to position_monitor_status table.

Usage:
    # Run via cron at pre-market (09:00 HKT)
    python startup_monitor.py

    # Or import and call directly
    from startup_monitor import run_startup_reconciliation
    result = await run_startup_reconciliation()
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

import asyncpg

# Local imports
try:
    from brokers.moomoo import MoomooClient
except ImportError:
    MoomooClient = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Hong Kong timezone
HK_TZ = ZoneInfo("Asia/Hong_Kong")

# Database connection - set via environment
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("INTL_DATABASE_URL") or os.getenv("DEV_DATABASE_URL")


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

async def get_db_pool() -> asyncpg.Pool:
    """Create database connection pool."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set")
    
    return await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=30
    )


async def get_open_positions(pool: asyncpg.Pool) -> List[Dict[str, Any]]:
    """
    Get all open positions from database.

    Returns:
        List of position dicts
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.position_id,
                p.symbol,
                p.side,
                p.quantity,
                p.entry_price,
                p.stop_loss,
                p.take_profit,
                p.entry_time,
                p.notes as entry_reason,
                p.max_favorable as high_watermark
            FROM positions p
            WHERE p.status = 'open'
            ORDER BY p.entry_time
        """)
        return [dict(r) for r in rows]


# =============================================================================
# BROKER SYNC FUNCTIONS
# =============================================================================

def get_broker_positions() -> List[Dict[str, Any]]:
    """Get current positions from Moomoo broker."""
    if not MoomooClient:
        logger.warning("MoomooClient not available")
        return []

    try:
        client = MoomooClient(paper_trading=True)
        client.connect()
        positions = client.get_positions()
        client.disconnect()

        return [
            {
                'symbol': p.symbol,
                'quantity': p.quantity,
                'avg_cost': p.avg_cost,
                'current_price': p.current_price,
                'unrealized_pnl': p.unrealized_pnl,
            }
            for p in positions
        ]
    except Exception as e:
        logger.error(f"Error getting broker positions: {e}")
        return []


async def sync_broker_positions(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Sync positions from broker to database.

    Process:
    1. Get positions from Moomoo
    2. Get open positions from DB
    3. Add positions that exist in broker but not in DB
    4. Close positions that exist in DB but not in broker

    Returns:
        Sync results dict
    """
    logger.info("=" * 60)
    logger.info("SYNCING BROKER POSITIONS")
    logger.info("=" * 60)

    result = {
        'timestamp': datetime.now(HK_TZ).isoformat(),
        'broker_positions': 0,
        'db_positions': 0,
        'positions_added': 0,
        'positions_closed': 0,
        'errors': []
    }

    try:
        # Get broker positions
        broker_positions = get_broker_positions()
        result['broker_positions'] = len(broker_positions)
        broker_symbols = {p['symbol'] for p in broker_positions}
        broker_by_symbol = {p['symbol']: p for p in broker_positions}

        logger.info(f"Broker positions: {len(broker_positions)}")
        for p in broker_positions:
            logger.info(f"  {p['symbol']}: {p['quantity']} @ {p['avg_cost']:.2f}")

        # Get DB positions
        db_positions = await get_open_positions(pool)
        result['db_positions'] = len(db_positions)
        db_symbols = {p['symbol'] for p in db_positions}

        logger.info(f"DB positions: {len(db_positions)}")
        for p in db_positions:
            logger.info(f"  {p['symbol']}: {p['quantity']} @ {p['entry_price']}")

        # Find discrepancies
        in_broker_not_db = broker_symbols - db_symbols
        in_db_not_broker = db_symbols - broker_symbols

        # Add missing positions (in broker but not DB)
        async with pool.acquire() as conn:
            for symbol in in_broker_not_db:
                bp = broker_by_symbol[symbol]
                try:
                    await conn.execute("""
                        INSERT INTO positions (
                            symbol, side, quantity, entry_price, status,
                            entry_time, notes, created_at, updated_at
                        ) VALUES (
                            $1, 'long', $2, $3, 'open',
                            NOW(), 'Synced from broker', NOW(), NOW()
                        )
                    """, symbol, bp['quantity'], bp['avg_cost'])
                    logger.info(f"Added position: {symbol} x {bp['quantity']} @ {bp['avg_cost']:.2f}")
                    result['positions_added'] += 1
                except Exception as e:
                    error_msg = f"Failed to add {symbol}: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)

            # Close stale positions (in DB but not broker)
            for symbol in in_db_not_broker:
                try:
                    await conn.execute("""
                        UPDATE positions SET
                            status = 'closed',
                            exit_reason = 'Closed by broker sync - not found in broker',
                            exit_time = NOW(),
                            closed_at = NOW(),
                            updated_at = NOW()
                        WHERE symbol = $1 AND status = 'open'
                    """, symbol)
                    logger.info(f"Closed stale position: {symbol}")
                    result['positions_closed'] += 1
                except Exception as e:
                    error_msg = f"Failed to close {symbol}: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)

        logger.info("-" * 60)
        logger.info("BROKER SYNC COMPLETE")
        logger.info(f"  Broker positions: {result['broker_positions']}")
        logger.info(f"  DB positions: {result['db_positions']}")
        logger.info(f"  Positions added: {result['positions_added']}")
        logger.info(f"  Positions closed: {result['positions_closed']}")
        if result['errors']:
            logger.error(f"  Errors: {len(result['errors'])}")
        logger.info("=" * 60)

    except Exception as e:
        error_msg = f"Broker sync failed: {e}"
        logger.error(error_msg)
        result['errors'].append(error_msg)

    return result


async def get_active_monitors(pool: asyncpg.Pool) -> List[Dict[str, Any]]:
    """
    Get all monitors that should be running.
    
    Returns:
        List of monitor dicts
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                monitor_id,
                position_id,
                symbol,
                status,
                started_at,
                last_check_at,
                pid,
                checks_completed,
                recommendation,
                error_count
            FROM position_monitor_status
            WHERE status IN ('running', 'starting', 'sleeping', 'pending')
        """)
        return [dict(r) for r in rows]


async def create_monitor_record(
    pool: asyncpg.Pool,
    position_id: int,
    symbol: str,
    entry_price: float,
    stop_loss: Optional[float],
    take_profit: Optional[float]
) -> int:
    """
    Create a new monitor status record.
    
    Args:
        pool: Database pool
        position_id: Position ID to monitor
        symbol: Stock symbol
        entry_price: Entry price for P&L calculation
        stop_loss: Stop loss price
        take_profit: Take profit price
        
    Returns:
        monitor_id of created record
    """
    async with pool.acquire() as conn:
        monitor_id = await conn.fetchval("""
            INSERT INTO position_monitor_status (
                position_id,
                symbol,
                status,
                started_at,
                high_watermark,
                metadata
            ) VALUES (
                $1, $2, 'starting', NOW(), $3,
                jsonb_build_object(
                    'created_by', 'startup_monitor',
                    'stop_loss', $4::numeric,
                    'take_profit', $5::numeric
                )
            )
            RETURNING monitor_id
        """, position_id, symbol, entry_price, stop_loss, take_profit)
        
        logger.info(f"Created monitor record {monitor_id} for {symbol} (position_id={position_id})")
        return monitor_id


async def update_monitor_status(
    pool: asyncpg.Pool,
    monitor_id: int,
    status: str,
    reason: Optional[str] = None
) -> None:
    """
    Update monitor status.
    
    Args:
        pool: Database pool
        monitor_id: Monitor ID to update
        status: New status
        reason: Optional reason for status change
    """
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE position_monitor_status
            SET 
                status = $2,
                recommendation_reason = COALESCE($3, recommendation_reason),
                updated_at = NOW()
            WHERE monitor_id = $1
        """, monitor_id, status, reason)


async def stop_orphaned_monitor(pool: asyncpg.Pool, monitor_id: int, symbol: str) -> None:
    """
    Mark orphaned monitor as stopped.
    
    Args:
        pool: Database pool
        monitor_id: Monitor ID to stop
        symbol: Symbol for logging
    """
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE position_monitor_status
            SET 
                status = 'stopped',
                recommendation_reason = 'Orphaned - no matching open position',
                updated_at = NOW()
            WHERE monitor_id = $1
        """, monitor_id)
    
    logger.warning(f"Stopped orphaned monitor {monitor_id} for {symbol}")


async def mark_stale_monitors(pool: asyncpg.Pool) -> int:
    """
    Mark monitors that haven't checked in as potentially stale.
    
    Returns:
        Number of monitors marked stale
    """
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE position_monitor_status
            SET 
                status = 'error',
                last_error = 'Stale - no check-in for 30+ minutes',
                consecutive_errors = consecutive_errors + 1,
                updated_at = NOW()
            WHERE status = 'running'
            AND last_check_at < NOW() - INTERVAL '30 minutes'
        """)
        
        # Parse "UPDATE N" to get count
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.warning(f"Marked {count} stale monitors as error")
        return count


# =============================================================================
# RECONCILIATION LOGIC
# =============================================================================

async def reconcile_monitors(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Ensure every open position has an active monitor.
    
    Process:
    1. Get all open positions
    2. Get all active/pending monitors
    3. For positions without monitors -> create monitor record
    4. For monitors without positions -> stop (orphaned)
    5. For stale monitors -> mark as error
    
    Returns:
        Reconciliation results dict
    """
    logger.info("=" * 60)
    logger.info("STARTING MONITOR RECONCILIATION")
    logger.info("=" * 60)
    
    result = {
        'timestamp': datetime.now(HK_TZ).isoformat(),
        'positions_found': 0,
        'monitors_active': 0,
        'monitors_started': [],
        'monitors_orphaned': [],
        'monitors_already_running': [],
        'monitors_stale': 0,
        'errors': []
    }
    
    try:
        # Get current state
        positions = await get_open_positions(pool)
        monitors = await get_active_monitors(pool)
        
        result['positions_found'] = len(positions)
        result['monitors_active'] = len(monitors)
        
        logger.info(f"Found {len(positions)} open positions")
        logger.info(f"Found {len(monitors)} active/pending monitors")
        
        # Build lookup sets
        position_ids = {p['position_id'] for p in positions}
        position_map = {p['position_id']: p for p in positions}
        monitored_position_ids = {m['position_id'] for m in monitors}
        
        # Find positions without monitors
        unmonitored_ids = position_ids - monitored_position_ids
        
        # Find monitors without positions (orphaned)
        orphaned_monitors = [m for m in monitors if m['position_id'] not in position_ids]
        
        # Start monitors for unmonitored positions
        for pos_id in unmonitored_ids:
            pos = position_map[pos_id]
            try:
                logger.info(f"Starting monitor for {pos['symbol']} (position_id={pos_id})")
                
                monitor_id = await create_monitor_record(
                    pool=pool,
                    position_id=pos_id,
                    symbol=pos['symbol'],
                    entry_price=float(pos['entry_price']),
                    stop_loss=float(pos['stop_loss']) if pos['stop_loss'] else None,
                    take_profit=float(pos['take_profit']) if pos['take_profit'] else None
                )
                
                result['monitors_started'].append({
                    'symbol': pos['symbol'],
                    'position_id': pos_id,
                    'monitor_id': monitor_id
                })
                
            except Exception as e:
                error_msg = f"Failed to start monitor for {pos['symbol']}: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        # Stop orphaned monitors
        for mon in orphaned_monitors:
            try:
                await stop_orphaned_monitor(pool, mon['monitor_id'], mon['symbol'])
                result['monitors_orphaned'].append({
                    'symbol': mon['symbol'],
                    'monitor_id': mon['monitor_id']
                })
            except Exception as e:
                error_msg = f"Failed to stop orphaned monitor {mon['monitor_id']}: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        # Note already running monitors
        already_running = [p for p in positions if p['position_id'] in monitored_position_ids]
        result['monitors_already_running'] = [
            {'symbol': p['symbol'], 'position_id': p['position_id']} 
            for p in already_running
        ]
        
        # Mark stale monitors
        result['monitors_stale'] = await mark_stale_monitors(pool)
        
        # Summary logging
        logger.info("-" * 60)
        logger.info("RECONCILIATION COMPLETE")
        logger.info(f"  Positions found: {result['positions_found']}")
        logger.info(f"  Monitors started: {len(result['monitors_started'])}")
        logger.info(f"  Monitors orphaned: {len(result['monitors_orphaned'])}")
        logger.info(f"  Monitors already running: {len(result['monitors_already_running'])}")
        logger.info(f"  Monitors marked stale: {result['monitors_stale']}")
        
        if result['errors']:
            logger.error(f"  Errors: {len(result['errors'])}")
            for err in result['errors']:
                logger.error(f"    - {err}")
        
        logger.info("=" * 60)
        
    except Exception as e:
        error_msg = f"Reconciliation failed: {e}"
        logger.error(error_msg, exc_info=True)
        result['errors'].append(error_msg)
    
    return result


# =============================================================================
# HEALTH REPORT
# =============================================================================

async def get_monitor_health_report(pool: asyncpg.Pool) -> Dict[str, Any]:
    """
    Get comprehensive monitor health report.
    
    Returns:
        Health report dict with summary and position details
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM v_monitor_health
        """)
        
        positions = [dict(r) for r in rows]
        
        # Calculate summary
        total = len(positions)
        no_monitor = sum(1 for p in positions if p['monitor_status'] == 'NO_MONITOR')
        errors = sum(1 for p in positions if p['monitor_status'] == 'error')
        stale = sum(1 for p in positions if p.get('minutes_since_check') and p['minutes_since_check'] > 15)
        active = sum(1 for p in positions if p['monitor_status'] == 'running')
        sleeping = sum(1 for p in positions if p['monitor_status'] == 'sleeping')
        
        # Overall health
        if total == 0:
            health = '⚪ NO POSITIONS'
        elif no_monitor == 0 and errors == 0 and stale == 0:
            health = '🟢 ALL OK'
        elif no_monitor > 0 or errors > 0:
            health = '🔴 NEEDS ATTENTION'
        else:
            health = '🟡 CHECK STALE'
        
        # Build alerts
        alerts = []
        for p in positions:
            if p['health'] in ('🔴 NO_MONITOR', '🔴 ERROR', '🔴 FAILING'):
                alerts.append(f"{p['symbol']}: {p['health']}")
            elif p['health'] == '🟡 STALE':
                alerts.append(f"{p['symbol']}: {p['health']} ({p.get('minutes_since_check', 0):.0f} min)")
        
        return {
            'timestamp': datetime.now(HK_TZ).isoformat(),
            'summary': {
                'total_positions': total,
                'active_monitors': active,
                'sleeping_monitors': sleeping,
                'no_monitor': no_monitor,
                'error_monitors': errors,
                'stale_monitors': stale,
                'health': health
            },
            'positions': positions,
            'alerts': alerts
        }


def print_health_report(health: Dict[str, Any]) -> None:
    """Print health report in readable format."""
    summary = health['summary']
    
    print("\n" + "=" * 60)
    print("MONITOR HEALTH REPORT")
    print("=" * 60)
    print(f"Time: {health['timestamp']}")
    print(f"Overall Health: {summary['health']}")
    print("-" * 60)
    print(f"Total Positions: {summary['total_positions']}")
    print(f"  Active Monitors: {summary['active_monitors']}")
    print(f"  Sleeping: {summary['sleeping_monitors']}")
    print(f"  No Monitor: {summary['no_monitor']}")
    print(f"  Errors: {summary['error_monitors']}")
    print(f"  Stale: {summary['stale_monitors']}")
    
    if health['alerts']:
        print("-" * 60)
        print("ALERTS:")
        for alert in health['alerts']:
            print(f"  ⚠️  {alert}")
    
    if health['positions']:
        print("-" * 60)
        print("POSITIONS:")
        print(f"{'Symbol':<8} {'Health':<15} {'Last Check':<12} {'RSI':<6} {'Recommendation':<10}")
        print("-" * 60)
        for p in health['positions']:
            last_check = f"{p.get('minutes_since_check', 0):.0f} min" if p.get('minutes_since_check') else "-"
            rsi = f"{p['last_rsi']:.1f}" if p.get('last_rsi') else "-"
            rec = p.get('recommendation') or '-'
            print(f"{p['symbol']:<8} {p['health'] or '-':<15} {last_check:<12} {rsi:<6} {rec:<10}")
    
    print("=" * 60)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def run_startup_reconciliation() -> Dict[str, Any]:
    """
    Main entry point for startup reconciliation.

    Process:
    1. Sync positions from broker to database
    2. Reconcile monitors for all open positions
    3. Generate health report

    Returns:
        Dict with sync, reconciliation, and health results
    """
    pool = await get_db_pool()

    try:
        # Step 1: Sync broker positions to DB
        sync_result = await sync_broker_positions(pool)

        # Step 2: Reconcile monitors
        recon_result = await reconcile_monitors(pool)

        # Step 3: Get health report
        health = await get_monitor_health_report(pool)

        # Print health report
        print_health_report(health)

        return {
            'broker_sync': sync_result,
            'reconciliation': recon_result,
            'health': health
        }

    finally:
        await pool.close()


# =============================================================================
# CLI
# =============================================================================

def main():
    """Command line entry point."""
    print("\n" + "=" * 60)
    print("CATALYST STARTUP MONITOR")
    print(f"Time: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 60)
    
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set one of: DATABASE_URL, INTL_DATABASE_URL, or DEV_DATABASE_URL")
        sys.exit(1)
    
    # Run reconciliation
    result = asyncio.run(run_startup_reconciliation())
    
    # Exit with error code if there were problems
    if result['reconciliation']['errors']:
        sys.exit(1)
    if result['health']['summary']['no_monitor'] > 0:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
