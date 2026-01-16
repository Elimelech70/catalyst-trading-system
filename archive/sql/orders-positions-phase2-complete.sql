-- ============================================================================
-- ORDERS/POSITIONS PHASE 2: COMPLETE IMPLEMENTATION
-- ============================================================================
-- Run this script to complete Phase 2 of orders/positions separation
--
-- What this script does:
-- 1. Adds order_purpose column to orders table
-- 2. Fixes order side mapping for exit orders
-- 3. Updates v_trade_pipeline_status view
-- 4. Drops legacy columns from positions table
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Add order_purpose column
-- ============================================================================

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

-- ============================================================================
-- STEP 2: Fix order side mapping for exit orders
-- ============================================================================

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

-- ============================================================================
-- STEP 3: Update v_trade_pipeline_status view
-- ============================================================================

DROP VIEW IF EXISTS v_trade_pipeline_status;

CREATE VIEW v_trade_pipeline_status AS
SELECT
    tc.cycle_id,
    tc.started_at::date as cycle_date,
    tc.status as cycle_status,
    tc.started_at as cycle_start,
    tc.stopped_at as cycle_end,
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
ORDER BY tc.started_at DESC;

-- ============================================================================
-- STEP 4: Drop legacy columns from positions table
-- ============================================================================

ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_order_id;
ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_status;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Order purpose distribution:' as info;
SELECT order_purpose, side, COUNT(*) as count
FROM orders
GROUP BY order_purpose, side
ORDER BY order_purpose, side;

SELECT 'Phase 2 Complete' as status;
