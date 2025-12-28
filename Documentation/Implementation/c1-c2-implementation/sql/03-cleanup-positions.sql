-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: 03-cleanup-positions.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Remove legacy alpaca_* columns from positions table
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-27) - Initial creation
--   - Drops alpaca_order_id, alpaca_status, alpaca_error from positions
--   - ONLY run after verification in production
--
-- ⚠️ WARNING: RUN THIS ONLY AFTER:
--   1. 01-orders-table-create.sql has been run
--   2. 02-migrate-data.sql has been run
--   3. System has been verified working for at least 1 trading day
--   4. Doctor Claude diagnostic shows no issues
--
-- EXECUTION:
--   psql $DATABASE_URL -f 03-cleanup-positions.sql
-- ============================================================================

\echo '=============================================='
\echo '⚠️  CLEANUP: Removing legacy columns from positions'
\echo '=============================================='
\echo ''
\echo 'This script will DROP the following columns from positions:'
\echo '  - alpaca_order_id'
\echo '  - alpaca_status'
\echo '  - alpaca_error'
\echo ''
\echo 'Press Ctrl+C within 10 seconds to abort...'
\echo ''

-- Give operator time to abort
SELECT pg_sleep(10);

BEGIN;

-- ============================================================================
-- STEP 1: Verify orders table has data
-- ============================================================================
\echo 'Step 1: Verifying orders table has data...'

DO $$
DECLARE
    order_count INTEGER;
    position_with_alpaca INTEGER;
BEGIN
    -- Count orders
    SELECT COUNT(*) INTO order_count FROM orders;
    
    -- Count positions with alpaca_order_id (if column exists)
    BEGIN
        SELECT COUNT(*) INTO position_with_alpaca 
        FROM positions WHERE alpaca_order_id IS NOT NULL;
    EXCEPTION
        WHEN undefined_column THEN
            position_with_alpaca := 0;
    END;
    
    IF order_count = 0 AND position_with_alpaca > 0 THEN
        RAISE EXCEPTION 'Orders table is empty but positions has % orders. Run 02-migrate-data.sql first!', position_with_alpaca;
    END IF;
    
    RAISE NOTICE 'Orders table has % records. Safe to proceed.', order_count;
END $$;

\echo 'Step 1 complete: verification passed'

-- ============================================================================
-- STEP 2: Drop legacy columns
-- ============================================================================
\echo 'Step 2: Dropping legacy columns from positions table...'

ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_order_id;
ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_status;
ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_error;

\echo 'Step 2 complete: legacy columns dropped'

-- ============================================================================
-- STEP 3: Drop legacy indexes if they exist
-- ============================================================================
\echo 'Step 3: Dropping legacy indexes...'

DROP INDEX IF EXISTS idx_positions_alpaca_order_id;
DROP INDEX IF EXISTS idx_positions_alpaca_status;

\echo 'Step 3 complete: legacy indexes dropped'

-- ============================================================================
-- STEP 4: Update table comment
-- ============================================================================
\echo 'Step 4: Updating table comment...'

COMMENT ON TABLE positions IS 'Actual holdings - order data is in the orders table (migrated 2025-12-27, C1 fix applied)';

\echo 'Step 4 complete: comment updated'

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
\echo ''
\echo '=============================================='
\echo 'VERIFICATION'
\echo '=============================================='

\echo 'Positions table columns (should NOT have alpaca_* columns):'
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'positions'
ORDER BY ordinal_position;

\echo ''
\echo 'Orders table columns (should have all order fields):'
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'orders'
ORDER BY ordinal_position;

\echo ''
\echo '=============================================='
\echo 'CLEANUP COMPLETE'
\echo ''
\echo 'The positions table no longer has order-related columns.'
\echo 'All order tracking is now in the orders table.'
\echo ''
\echo 'ARCHITECTURE-RULES.md Rule 1 is now enforced:'
\echo '  Orders ≠ Positions'
\echo '=============================================='
