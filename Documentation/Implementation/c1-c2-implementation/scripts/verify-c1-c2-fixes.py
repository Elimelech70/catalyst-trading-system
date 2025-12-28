#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: verify-c1-c2-fixes.py
Version: 1.0.0
Last Updated: 2025-12-27
Purpose: Verify C1 (orders table) and C2 (alpaca_trader consolidation) fixes

REVISION HISTORY:
v1.0.0 (2025-12-27) - Initial verification script

USAGE:
    python3 verify-c1-c2-fixes.py
    
    Exit codes:
      0 = All checks passed
      1 = Some checks failed
      2 = Critical error
"""

import asyncio
import os
import sys
from pathlib import Path

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")

# Expected paths for alpaca_trader.py
ALPACA_TRADER_AUTHORITATIVE = Path("/root/catalyst-trading-system/services/shared/common/alpaca_trader.py")
ALPACA_TRADER_SYMLINKS = [
    Path("/root/catalyst-trading-system/services/trading/common/alpaca_trader.py"),
    Path("/root/catalyst-trading-system/services/risk-manager/common/alpaca_trader.py"),
    Path("/root/catalyst-trading-system/services/workflow/common/alpaca_trader.py"),
]

# ============================================================================
# CHECK FUNCTIONS
# ============================================================================

def print_header(title: str):
    """Print a formatted section header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_check(name: str, passed: bool, details: str = ""):
    """Print a check result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {name}")
    if details:
        print(f"         {details}")


async def check_orders_table_exists() -> bool:
    """Check if orders table exists."""
    if not DATABASE_URL:
        print_check("Orders table exists", False, "DATABASE_URL not set")
        return False
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'orders'
            )
        """)
        await conn.close()
        
        print_check("Orders table exists", result)
        return result
    except Exception as e:
        print_check("Orders table exists", False, str(e))
        return False


async def check_orders_table_columns() -> bool:
    """Check if orders table has required columns."""
    if not DATABASE_URL:
        return False
    
    required_columns = [
        'order_id', 'position_id', 'security_id', 'cycle_id',
        'side', 'order_type', 'quantity', 'status',
        'alpaca_order_id', 'filled_qty', 'filled_avg_price',
        'order_purpose', 'parent_order_id'
    ]
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'orders'
        """)
        await conn.close()
        
        existing_columns = {row['column_name'] for row in result}
        missing = set(required_columns) - existing_columns
        
        passed = len(missing) == 0
        details = f"Missing: {missing}" if missing else f"{len(existing_columns)} columns found"
        
        print_check("Orders table has required columns", passed, details)
        return passed
    except Exception as e:
        print_check("Orders table has required columns", False, str(e))
        return False


async def check_orders_have_data() -> bool:
    """Check if orders table has data."""
    if not DATABASE_URL:
        return False
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        count = await conn.fetchval("SELECT COUNT(*) FROM orders")
        await conn.close()
        
        passed = count > 0
        print_check("Orders table has data", passed, f"{count} orders found")
        return passed
    except Exception as e:
        print_check("Orders table has data", False, str(e))
        return False


async def check_positions_no_alpaca_columns() -> bool:
    """Check that positions table does NOT have alpaca_* columns."""
    if not DATABASE_URL:
        return False
    
    forbidden_columns = ['alpaca_order_id', 'alpaca_status', 'alpaca_error']
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'positions'
              AND column_name IN ('alpaca_order_id', 'alpaca_status', 'alpaca_error')
        """)
        await conn.close()
        
        found_columns = [row['column_name'] for row in result]
        
        if len(found_columns) == 0:
            print_check("Positions table has NO alpaca_* columns", True, "Clean (C1 fix complete)")
            return True
        else:
            print_check("Positions table has NO alpaca_* columns", False, 
                       f"Found: {found_columns} (run 03-cleanup-positions.sql)")
            return False
    except Exception as e:
        print_check("Positions table has NO alpaca_* columns", False, str(e))
        return False


async def check_orders_view_exists() -> bool:
    """Check if v_orders_status view exists."""
    if not DATABASE_URL:
        return False
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_name = 'v_orders_status'
            )
        """)
        await conn.close()
        
        print_check("v_orders_status view exists", result)
        return result
    except Exception as e:
        print_check("v_orders_status view exists", False, str(e))
        return False


async def check_pipeline_view_uses_orders() -> bool:
    """Check if v_trade_pipeline_status uses orders table."""
    if not DATABASE_URL:
        return False
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        result = await conn.fetchval("""
            SELECT view_definition 
            FROM information_schema.views 
            WHERE table_name = 'v_trade_pipeline_status'
        """)
        await conn.close()
        
        if result:
            # Check if view references orders table
            uses_orders = 'orders' in result.lower() and 'positions.alpaca' not in result.lower()
            print_check("v_trade_pipeline_status uses orders table", uses_orders,
                       "View updated for C1 fix" if uses_orders else "View still uses positions.alpaca_*")
            return uses_orders
        else:
            print_check("v_trade_pipeline_status uses orders table", False, "View not found")
            return False
    except Exception as e:
        print_check("v_trade_pipeline_status uses orders table", False, str(e))
        return False


def check_alpaca_trader_authoritative() -> bool:
    """Check if authoritative alpaca_trader.py exists."""
    if ALPACA_TRADER_AUTHORITATIVE.exists():
        # Check version
        content = ALPACA_TRADER_AUTHORITATIVE.read_text()
        if 'Version: 2.0.0' in content or 'v2.0.0' in content:
            print_check("Authoritative alpaca_trader.py exists", True, "v2.0.0 found")
            return True
        else:
            print_check("Authoritative alpaca_trader.py exists", False, "Wrong version")
            return False
    else:
        print_check("Authoritative alpaca_trader.py exists", False, 
                   f"Not found at {ALPACA_TRADER_AUTHORITATIVE}")
        return False


def check_alpaca_trader_symlinks() -> bool:
    """Check if duplicate locations are symlinks to authoritative."""
    all_symlinks = True
    
    for symlink_path in ALPACA_TRADER_SYMLINKS:
        if symlink_path.exists():
            if symlink_path.is_symlink():
                target = symlink_path.resolve()
                if target == ALPACA_TRADER_AUTHORITATIVE.resolve():
                    print_check(f"Symlink: {symlink_path.name}", True, "→ shared/common/")
                else:
                    print_check(f"Symlink: {symlink_path.name}", False, f"Wrong target: {target}")
                    all_symlinks = False
            else:
                print_check(f"Symlink: {symlink_path.name}", False, "Is a file, not symlink")
                all_symlinks = False
        else:
            print_check(f"Symlink: {symlink_path.name}", True, "Not present (OK)")
    
    return all_symlinks


def check_trade_watchdog_version() -> bool:
    """Check if trade_watchdog.py is v2.0.0."""
    watchdog_path = Path("/root/catalyst-trading-system/scripts/trade_watchdog.py")
    
    if watchdog_path.exists():
        content = watchdog_path.read_text()
        if 'Version: 2.0.0' in content or 'v2.0.0' in content:
            print_check("trade_watchdog.py is v2.0.0", True, "C1 fix applied")
            return True
        else:
            print_check("trade_watchdog.py is v2.0.0", False, "Old version")
            return False
    else:
        print_check("trade_watchdog.py is v2.0.0", False, f"Not found at {watchdog_path}")
        return False


# ============================================================================
# MAIN
# ============================================================================

async def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     Catalyst Trading System - C1 & C2 Fix Verification   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    results = {
        'c1_checks': [],
        'c2_checks': [],
        'all_passed': True
    }
    
    # ========================================================================
    # C1 FIX: Orders Table
    # ========================================================================
    print_header("C1 FIX: Orders Table (Orders ≠ Positions)")
    
    if ASYNCPG_AVAILABLE:
        c1_checks = [
            await check_orders_table_exists(),
            await check_orders_table_columns(),
            await check_orders_have_data(),
            await check_positions_no_alpaca_columns(),
            await check_orders_view_exists(),
            await check_pipeline_view_uses_orders(),
        ]
        results['c1_checks'] = c1_checks
    else:
        print("  ⚠️  asyncpg not available, skipping database checks")
        results['c1_checks'] = [False]
    
    # ========================================================================
    # C2 FIX: alpaca_trader.py Consolidation
    # ========================================================================
    print_header("C2 FIX: alpaca_trader.py Consolidation")
    
    c2_checks = [
        check_alpaca_trader_authoritative(),
        check_alpaca_trader_symlinks(),
        check_trade_watchdog_version(),
    ]
    results['c2_checks'] = c2_checks
    
    # ========================================================================
    # Summary
    # ========================================================================
    print_header("SUMMARY")
    
    c1_passed = all(results['c1_checks'])
    c2_passed = all(results['c2_checks'])
    all_passed = c1_passed and c2_passed
    
    print(f"  C1 Fix (Orders Table):       {'✅ COMPLETE' if c1_passed else '❌ INCOMPLETE'}")
    print(f"  C2 Fix (alpaca_trader.py):   {'✅ COMPLETE' if c2_passed else '❌ INCOMPLETE'}")
    print()
    
    if all_passed:
        print("  🎉 All fixes verified successfully!")
        print()
        print("  Next steps:")
        print("    1. Run Doctor Claude: python3 scripts/trade_watchdog.py --pretty")
        print("    2. Monitor next trading session")
        print("    3. After verification, run 03-cleanup-positions.sql")
    else:
        print("  ⚠️  Some checks failed. Review the issues above.")
        print()
        print("  Troubleshooting:")
        if not c1_passed:
            print("    - C1: Run sql/01-orders-table-create.sql and sql/02-migrate-data.sql")
        if not c2_passed:
            print("    - C2: Deploy services/shared/common/alpaca_trader.py and create symlinks")
    
    print()
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
