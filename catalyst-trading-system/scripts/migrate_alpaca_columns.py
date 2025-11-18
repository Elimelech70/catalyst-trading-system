#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: migrate_alpaca_columns.py
Version: 1.0.0
Last Updated: 2025-11-18
Purpose: Database migration to add Alpaca integration columns

Description:
Adds alpaca_order_id, alpaca_status, and alpaca_error columns to
the positions table for Alpaca API integration.

Usage:
    python3 scripts/migrate_alpaca_columns.py
"""

import asyncpg
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def run_migration():
    """Run database migration to add Alpaca columns"""

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ DATABASE_URL not set in environment")
        print("   Set it with: export DATABASE_URL=postgresql://...")
        return False

    print("=" * 70)
    print("Catalyst Trading System - Alpaca Columns Migration")
    print("=" * 70)
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    print()

    try:
        # Connect to database
        print("Connecting to database...")
        conn = await asyncpg.connect(database_url)
        print("✅ Connected")
        print()

        # Check if positions table exists
        print("Checking if positions table exists...")
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'positions'
            )
        """)

        if not table_exists:
            print("❌ positions table does not exist!")
            print("   Run the main schema migration first.")
            await conn.close()
            return False

        print("✅ positions table exists")
        print()

        # Check which columns already exist
        print("Checking existing Alpaca columns...")
        existing_columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'positions'
            AND column_name IN ('alpaca_order_id', 'alpaca_status', 'alpaca_error')
        """)

        existing_column_names = {row['column_name'] for row in existing_columns}

        if existing_column_names:
            print(f"   Found existing columns: {', '.join(existing_column_names)}")
        else:
            print("   No Alpaca columns found (will create all)")
        print()

        # Add alpaca_order_id column
        print("Adding alpaca_order_id column...")
        if 'alpaca_order_id' in existing_column_names:
            print("   ⏭️  Column already exists, skipping")
        else:
            await conn.execute("""
                ALTER TABLE positions
                ADD COLUMN alpaca_order_id VARCHAR(50)
            """)
            print("   ✅ Column added")

        # Add alpaca_status column
        print("Adding alpaca_status column...")
        if 'alpaca_status' in existing_column_names:
            print("   ⏭️  Column already exists, skipping")
        else:
            await conn.execute("""
                ALTER TABLE positions
                ADD COLUMN alpaca_status VARCHAR(50)
            """)
            print("   ✅ Column added")

        # Add alpaca_error column
        print("Adding alpaca_error column...")
        if 'alpaca_error' in existing_column_names:
            print("   ⏭️  Column already exists, skipping")
        else:
            await conn.execute("""
                ALTER TABLE positions
                ADD COLUMN alpaca_error TEXT
            """)
            print("   ✅ Column added")
        print()

        # Create indexes
        print("Creating indexes...")

        # Index on alpaca_order_id
        print("  1. Creating index on alpaca_order_id...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_alpaca_order_id
            ON positions(alpaca_order_id)
            WHERE alpaca_order_id IS NOT NULL
        """)
        print("     ✅ Index created")

        # Index on alpaca_status
        print("  2. Creating index on alpaca_status...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_alpaca_status
            ON positions(alpaca_status)
            WHERE alpaca_status IS NOT NULL
        """)
        print("     ✅ Index created")
        print()

        # Verify all columns
        print("Verifying migration...")
        columns = await conn.fetch("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'positions'
            AND column_name IN ('alpaca_order_id', 'alpaca_status', 'alpaca_error')
            ORDER BY column_name
        """)

        print("   Columns in positions table:")
        for col in columns:
            max_len = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
            print(f"     - {col['column_name']:<20} {col['data_type']}{max_len}")
        print()

        # Verify indexes
        indexes = await conn.fetch("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'positions'
            AND indexname LIKE '%alpaca%'
            ORDER BY indexname
        """)

        print("   Indexes created:")
        for idx in indexes:
            print(f"     - {idx['indexname']}")
        print()

        # Close connection
        await conn.close()

        print("=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("The positions table now supports Alpaca integration:")
        print("  - alpaca_order_id: Stores Alpaca's unique order ID")
        print("  - alpaca_status: Tracks order status (new/filled/error/etc.)")
        print("  - alpaca_error: Stores error messages if submission fails")
        print()
        print("Indexes created for performance:")
        print("  - idx_positions_alpaca_order_id (order lookups)")
        print("  - idx_positions_alpaca_status (status filtering)")
        print()
        print("You can now use Alpaca integration in:")
        print("  - Trading Service v8.0.0 (submit orders)")
        print("  - Risk Manager v7.0.0 (emergency stop)")
        print()

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print()
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)
