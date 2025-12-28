-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: 02-migrate-data.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Migrate existing order data from positions table to orders table
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-27) - Initial creation
--   - Migrates alpaca_order_id, alpaca_status from positions to orders
--   - Preserves all historical data
--   - Creates proper order-position relationships
--
-- PREREQUISITES:
--   - 01-orders-table-create.sql must be run first
--   - positions table must have alpaca_order_id column
--
-- EXECUTION:
--   psql $DATABASE_URL -f 02-migrate-data.sql
-- ============================================================================

\echo '=============================================='
\echo 'C1 FIX: Migrating order data from positions'
\echo '=============================================='

BEGIN;

-- ============================================================================
-- STEP 1: Check prerequisites
-- ============================================================================
\echo 'Step 1: Checking prerequisites...'

DO $$
DECLARE
    orders_exists BOOLEAN;
    alpaca_col_exists BOOLEAN;
BEGIN
    -- Check orders table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'orders'
    ) INTO orders_exists;
    
    IF NOT orders_exists THEN
        RAISE EXCEPTION 'Orders table does not exist. Run 01-orders-table-create.sql first.';
    END IF;
    
    -- Check positions has alpaca_order_id column
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'alpaca_order_id'
    ) INTO alpaca_col_exists;
    
    IF NOT alpaca_col_exists THEN
        RAISE NOTICE 'No alpaca_order_id column in positions - nothing to migrate.';
    ELSE
        RAISE NOTICE 'Prerequisites met. Proceeding with migration.';
    END IF;
END $$;

\echo 'Step 1 complete: prerequisites verified'

-- ============================================================================
-- STEP 2: Count existing data
-- ============================================================================
\echo 'Step 2: Counting existing order data...'

SELECT 
    'Positions with alpaca_order_id' as metric,
    COUNT(*) as count
FROM positions
WHERE alpaca_order_id IS NOT NULL
UNION ALL
SELECT 
    'Existing orders in orders table' as metric,
    COUNT(*) as count
FROM orders;

-- ============================================================================
-- STEP 3: Migrate entry orders from positions to orders
-- ============================================================================
\echo 'Step 3: Migrating entry orders...'

INSERT INTO orders (
    position_id,
    security_id,
    cycle_id,
    side,
    order_type,
    order_purpose,
    quantity,
    limit_price,
    alpaca_order_id,
    status,
    filled_qty,
    filled_avg_price,
    submitted_at,
    filled_at,
    created_at,
    updated_at,
    metadata
)
SELECT 
    p.position_id,
    p.security_id,
    p.cycle_id,
    -- Map position side to order side
    CASE 
        WHEN p.side = 'long' THEN 'buy'
        WHEN p.side = 'short' THEN 'sell'
        ELSE p.side
    END as side,
    'market' as order_type,  -- Historical orders were market orders
    'entry' as order_purpose,
    p.quantity,
    p.entry_price as limit_price,  -- Store entry price
    p.alpaca_order_id,
    -- Map position/alpaca status to order status
    CASE 
        WHEN p.status IN ('open', 'closed') THEN 'filled'
        WHEN p.alpaca_status IS NOT NULL THEN p.alpaca_status
        ELSE 'filled'  -- Assume filled if position exists
    END as status,
    p.quantity as filled_qty,  -- Assume fully filled
    p.entry_price as filled_avg_price,
    COALESCE(p.opened_at, p.entry_time, p.created_at) as submitted_at,
    COALESCE(p.opened_at, p.entry_time, p.created_at) as filled_at,
    p.created_at,
    p.updated_at,
    jsonb_build_object(
        'migrated_from', 'positions',
        'migration_date', NOW(),
        'original_position_status', p.status,
        'original_alpaca_status', p.alpaca_status,
        'migration_version', '1.0.0'
    ) as metadata
FROM positions p
WHERE p.alpaca_order_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM orders o WHERE o.alpaca_order_id = p.alpaca_order_id
  );

\echo 'Step 3 complete: entry orders migrated'

-- ============================================================================
-- STEP 4: Create exit orders for closed positions (stop_loss/take_profit)
-- ============================================================================
\echo 'Step 4: Creating exit order records for closed positions...'

-- For positions that are closed, we know an exit order must have been filled
-- We create a synthetic exit order record for proper tracking
INSERT INTO orders (
    position_id,
    security_id,
    cycle_id,
    side,
    order_type,
    order_purpose,
    quantity,
    limit_price,
    status,
    filled_qty,
    filled_avg_price,
    filled_at,
    created_at,
    updated_at,
    metadata
)
SELECT 
    p.position_id,
    p.security_id,
    p.cycle_id,
    -- Exit is opposite of entry
    CASE 
        WHEN p.side = 'long' THEN 'sell'
        WHEN p.side = 'short' THEN 'buy'
        ELSE 'sell'
    END as side,
    -- Determine if stop_loss or take_profit based on exit price
    CASE 
        WHEN p.exit_price <= p.stop_loss THEN 'stop'
        WHEN p.exit_price >= p.take_profit THEN 'limit'
        ELSE 'market'
    END as order_type,
    -- Determine purpose based on exit price
    CASE 
        WHEN p.exit_price <= p.stop_loss THEN 'stop_loss'
        WHEN p.exit_price >= p.take_profit THEN 'take_profit'
        ELSE 'exit'
    END as order_purpose,
    p.quantity,
    p.exit_price as limit_price,
    'filled' as status,
    p.quantity as filled_qty,
    p.exit_price as filled_avg_price,
    p.closed_at as filled_at,
    p.closed_at as created_at,
    p.updated_at,
    jsonb_build_object(
        'migrated_from', 'positions',
        'migration_date', NOW(),
        'synthetic_exit_order', true,
        'migration_version', '1.0.0',
        'close_reason', p.close_reason
    ) as metadata
FROM positions p
WHERE p.status = 'closed'
  AND p.exit_price IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM orders o 
      WHERE o.position_id = p.position_id 
        AND o.order_purpose IN ('stop_loss', 'take_profit', 'exit')
  );

\echo 'Step 4 complete: exit orders created'

-- ============================================================================
-- STEP 5: Update v_trade_pipeline_status view to use orders table
-- ============================================================================
\echo 'Step 5: Updating v_trade_pipeline_status view...'

CREATE OR REPLACE VIEW v_trade_pipeline_status AS
SELECT 
    tc.cycle_id,
    tc.cycle_date,
    tc.status as cycle_status,
    tc.current_positions,
    tc.max_positions,
    -- Order counts from orders table (not positions!)
    COALESCE(o_stats.total_orders, 0) as total_orders,
    COALESCE(o_stats.orders_pending, 0) as orders_pending,
    COALESCE(o_stats.orders_filled, 0) as orders_filled,
    COALESCE(o_stats.orders_rejected, 0) as orders_rejected,
    COALESCE(o_stats.orders_cancelled, 0) as orders_cancelled,
    COALESCE(o_stats.stuck_orders, 0) as stuck_orders,
    -- Position counts
    COALESCE(p_stats.positions_open, 0) as positions_open,
    COALESCE(p_stats.positions_closed, 0) as positions_closed,
    COALESCE(p_stats.daily_pnl, 0) as daily_pnl
FROM trading_cycles tc
LEFT JOIN (
    SELECT 
        cycle_id,
        COUNT(*) as total_orders,
        COUNT(*) FILTER (WHERE status IN ('created', 'submitted', 'accepted', 'pending_new', 'new')) as orders_pending,
        COUNT(*) FILTER (WHERE status = 'filled') as orders_filled,
        COUNT(*) FILTER (WHERE status = 'rejected') as orders_rejected,
        COUNT(*) FILTER (WHERE status IN ('cancelled', 'canceled', 'expired')) as orders_cancelled,
        COUNT(*) FILTER (
            WHERE status IN ('created', 'submitted', 'accepted', 'pending_new', 'new')
            AND submitted_at < NOW() - INTERVAL '5 minutes'
        ) as stuck_orders
    FROM orders
    GROUP BY cycle_id
) o_stats ON tc.cycle_id = o_stats.cycle_id
LEFT JOIN (
    SELECT 
        cycle_id,
        COUNT(*) FILTER (WHERE status = 'open') as positions_open,
        COUNT(*) FILTER (WHERE status = 'closed') as positions_closed,
        SUM(COALESCE(realized_pnl, 0) + COALESCE(unrealized_pnl, 0)) as daily_pnl
    FROM positions
    GROUP BY cycle_id
) p_stats ON tc.cycle_id = p_stats.cycle_id
ORDER BY tc.cycle_date DESC, tc.start_time DESC;

COMMENT ON VIEW v_trade_pipeline_status IS 'Trade pipeline status - uses orders table for order tracking (C1 fix applied)';

\echo 'Step 5 complete: view updated'

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
\echo ''
\echo '=============================================='
\echo 'VERIFICATION'
\echo '=============================================='

\echo 'Order counts by status:'
SELECT 
    status,
    COUNT(*) as count
FROM orders
GROUP BY status
ORDER BY count DESC;

\echo ''
\echo 'Order counts by purpose:'
SELECT 
    order_purpose,
    side,
    COUNT(*) as count
FROM orders
GROUP BY order_purpose, side
ORDER BY order_purpose, side;

\echo ''
\echo 'Positions with linked orders:'
SELECT 
    p.position_id,
    s.symbol,
    p.status as position_status,
    COUNT(o.order_id) as order_count
FROM positions p
JOIN securities s ON p.security_id = s.security_id
LEFT JOIN orders o ON o.position_id = p.position_id
GROUP BY p.position_id, s.symbol, p.status
ORDER BY order_count DESC
LIMIT 10;

\echo ''
\echo '=============================================='
\echo 'PHASE 2 COMPLETE: Data migrated'
\echo ''
\echo 'DO NOT run 03-cleanup-positions.sql yet!'
\echo 'Wait for verification in production first.'
\echo '=============================================='
