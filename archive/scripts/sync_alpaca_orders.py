#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: sync_alpaca_orders.py
Version: 1.1.0
Last Updated: 2025-12-20
Purpose: One-time sync of Alpaca order statuses to database

REVISION HISTORY:
v1.1.0 (2025-12-20) - Added all Alpaca terminal states
- Terminal states: filled, canceled, expired, rejected, done_for_day, replaced
- Auto-close positions when order is in terminal state and not in Alpaca

v1.0.0 (2025-12-20) - Initial version
- Sync order statuses from Alpaca to database
- Close ghost positions

Description:
This script syncs all open positions in the database with their actual
status in Alpaca. It's designed to be run manually to fix sync issues.

Usage:
    python3 scripts/sync_alpaca_orders.py [--dry-run]
"""

import asyncio
import asyncpg
import os
import sys
import argparse
from datetime import datetime

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
except ImportError:
    print("ERROR: alpaca-py not installed. Run: pip install alpaca-py")
    sys.exit(1)


async def sync_orders(dry_run: bool = False):
    """Sync all open position order statuses from Alpaca."""

    print("=" * 70)
    print("CATALYST TRADING SYSTEM - ALPACA ORDER SYNC")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will update DB)'}")
    print("=" * 70)

    # Get credentials
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    database_url = os.getenv("DATABASE_URL")

    if not api_key or not secret_key:
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        sys.exit(1)

    if not database_url:
        print("ERROR: DATABASE_URL must be set")
        sys.exit(1)

    # Initialize Alpaca client
    print("\n>>> Connecting to Alpaca (paper mode)...")
    client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)

    # Test connection
    try:
        account = client.get_account()
        print(f"    Account: {account.account_number}")
        print(f"    Equity: ${float(account.equity):,.2f}")
        print(f"    Cash: ${float(account.cash):,.2f}")
    except Exception as e:
        print(f"ERROR: Failed to connect to Alpaca: {e}")
        sys.exit(1)

    # Get Alpaca positions
    print("\n>>> Fetching Alpaca positions...")
    try:
        alpaca_positions = client.get_all_positions()
        print(f"    Alpaca has {len(alpaca_positions)} open positions")
        for pos in alpaca_positions:
            print(f"      - {pos.symbol}: {pos.qty} shares @ ${float(pos.current_price):.2f}")
    except Exception as e:
        print(f"ERROR: Failed to get positions: {e}")
        alpaca_positions = []

    # Connect to database
    print("\n>>> Connecting to database...")
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        sys.exit(1)

    # Get positions that need syncing
    print("\n>>> Finding positions to sync...")
    positions = await conn.fetch("""
        SELECT
            p.position_id,
            s.symbol,
            p.alpaca_order_id,
            p.alpaca_status,
            p.status,
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.alpaca_order_id IS NOT NULL
        AND p.status = 'open'
        ORDER BY p.opened_at DESC
    """)

    print(f"    Found {len(positions)} open positions with Alpaca order IDs")

    # Track results
    synced = 0
    errors = 0
    unchanged = 0
    closed = 0

    print("\n>>> Syncing order statuses...")
    print("-" * 70)

    for pos in positions:
        order_id = pos['alpaca_order_id']
        current_status = pos['alpaca_status']
        symbol = pos['symbol']

        try:
            # Get order status from Alpaca
            order = client.get_order_by_id(order_id)
            new_status = order.status.value
            filled_qty = int(order.filled_qty) if order.filled_qty else 0
            filled_price = float(order.filled_avg_price) if order.filled_avg_price else None

            # Determine if we need to update
            status_changed = new_status != current_status

            # Check if order is terminal (all Alpaca terminal states)
            is_terminal = new_status in ('filled', 'expired', 'canceled', 'rejected', 'done_for_day', 'replaced')

            # Check if symbol still has position in Alpaca
            has_alpaca_position = any(p.symbol == symbol for p in alpaca_positions)

            if status_changed or is_terminal:
                print(f"  {symbol}: {current_status} -> {new_status}", end="")

                if new_status == 'filled':
                    print(f" (filled {filled_qty} @ ${filled_price:.2f})")
                elif new_status == 'expired':
                    print(" (order expired - never filled)")
                else:
                    print()

                if not dry_run:
                    # Update the status (only columns that exist in schema)
                    await conn.execute("""
                        UPDATE positions
                        SET alpaca_status = $1,
                            updated_at = NOW()
                        WHERE position_id = $2
                    """,
                        new_status,
                        pos['position_id']
                    )

                    # If order is terminal and no position in Alpaca, close it
                    if is_terminal and not has_alpaca_position:
                        close_reason = f"alpaca_{new_status}"
                        await conn.execute("""
                            UPDATE positions
                            SET status = 'closed',
                                close_reason = $1,
                                closed_at = NOW()
                            WHERE position_id = $2
                        """, close_reason, pos['position_id'])
                        closed += 1
                        print(f"    -> Closed position (reason: {close_reason})")

                synced += 1
            else:
                unchanged += 1

        except Exception as e:
            print(f"  {symbol}: ERROR - {e}")
            errors += 1

    print("-" * 70)

    # Summary
    print("\n>>> SYNC SUMMARY")
    print(f"    Synced:    {synced}")
    print(f"    Unchanged: {unchanged}")
    print(f"    Closed:    {closed}")
    print(f"    Errors:    {errors}")

    if dry_run:
        print("\n    [DRY RUN - No changes made to database]")
    else:
        print("\n    [Changes applied to database]")

    # Also check for ghost positions (in DB but not in Alpaca)
    print("\n>>> Checking for ghost positions...")
    ghost_positions = await conn.fetch("""
        SELECT
            p.position_id,
            s.symbol,
            p.alpaca_status,
            p.opened_at AT TIME ZONE 'America/New_York' as opened_et
        FROM positions p
        JOIN securities s ON s.security_id = p.security_id
        WHERE p.status = 'open'
        AND p.opened_at < NOW() - INTERVAL '3 days'
    """)

    alpaca_symbols = {p.symbol for p in alpaca_positions}
    ghosts = [p for p in ghost_positions if p['symbol'] not in alpaca_symbols]

    if ghosts:
        print(f"    Found {len(ghosts)} ghost positions (in DB but not in Alpaca):")
        for g in ghosts[:10]:
            print(f"      - {g['symbol']}: status={g['alpaca_status']}, opened={g['opened_et']}")
        if len(ghosts) > 10:
            print(f"      ... and {len(ghosts) - 10} more")

        if not dry_run:
            print("\n    To clean these up, run with --cleanup flag")
    else:
        print("    No ghost positions found")

    await conn.close()

    print("\n" + "=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Sync Alpaca order statuses to database")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just show what would be done")
    args = parser.parse_args()

    asyncio.run(sync_orders(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
