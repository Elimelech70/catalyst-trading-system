-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: orders-table-migration.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Add proper orders table, migrate data from positions 
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-27) - Initial migration
--   - Creates orders table
--   - Migrates existing order data from positions.alpaca_* columns
--   - Adds indexes and constraints
--
-- INSTALLATION:
--   1. Review the migration carefully
--   2. Backup database first: pg_dump $DATABASE_URL > backup.sql
--   3. Run: psql $DATABASE_URL < orders-table-migration.sql
--   4. Verify: SELECT COUNT(*) FROM orders;
--   5. After verification, run Phase 2 to drop old columns
-- ============================================================================

-- ============================================================================
-- PHASE 1: Create orders table and migrate data
-- ============================================================================

BEGIN;

-- Step 1: Create orders table
CREATE TABLE IF NOT EXISTS orders (
    -- Primary Key
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    position_id UUID REFERENCES positions(position_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    cycle_id UUID REFERENCES trading_cycles(cycle_id),
    
    -- Order Hierarchy (for bracket orders)
    parent_order_id UUID REFERENCES orders(order_id),
    order_class VARCHAR(20),
    
    -- Order Specification
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    time_in_force VARCHAR(10) DEFAULT 'day',
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12, 4),
    stop_price DECIMAL(12, 4),
    trail_percent DECIMAL(5, 2),
    trail_price DECIMAL(12, 4),
    
    -- Alpaca Integration
    alpaca_order_id VARCHAR(100) UNIQUE,
    alpaca_client_order_id VARCHAR(100),
    
    -- Order Status
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    
    -- Fill Information
    filled_qty INTEGER DEFAULT 0,
    filled_avg_price DECIMAL(12, 4),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,
    accepted_at TIMESTAMP WITH TIME ZONE,
    filled_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    expired_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    rejection_reason TEXT,
    cancel_reason TEXT,
    metadata JSONB,
    
    -- Constraints
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    CONSTRAINT chk_order_class CHECK (order_class IS NULL OR order_class IN ('simple', 'bracket', 'oco', 'oto')),
    CONSTRAINT chk_order_quantity CHECK (quantity > 0),
    CONSTRAINT chk_filled_qty CHECK (filled_qty >= 0 AND filled_qty <= quantity)
);

-- Step 2: Create indexes
CREATE INDEX IF NOT EXISTS idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_security ON orders(security_id);
CREATE INDEX IF NOT EXISTS idx_orders_cycle ON orders(cycle_id);
CREATE INDEX IF NOT EXISTS idx_orders_alpaca_id ON orders(alpaca_order_id) WHERE alpaca_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_parent ON orders(parent_order_id) WHERE parent_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_submitted ON orders(submitted_at DESC) WHERE submitted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_pending ON orders(status) WHERE status IN ('submitted', 'accepted', 'pending_new', 'partial_fill');

-- Step 3: Add comments
COMMENT ON TABLE orders IS 'All orders sent to Alpaca - NEVER store order data in positions table';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created, then updated';
COMMENT ON COLUMN orders.parent_order_id IS 'For bracket orders: links take_profit and stop_loss to entry order';
COMMENT ON COLUMN orders.order_class IS 'bracket = entry with legs, oco = one-cancels-other, oto = one-triggers-other';

-- Step 4: Migrate existing order data from positions table
-- Only if positions has alpaca_order_id column
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'alpaca_order_id'
    ) THEN
        INSERT INTO orders (
            position_id,
            security_id,
            cycle_id,
            side,
            order_type,
            quantity,
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
            CASE 
                WHEN p.side = 'long' THEN 'buy' 
                WHEN p.side = 'short' THEN 'sell'
                ELSE p.side  -- In case it's already buy/sell
            END as side,
            'market' as order_type,  -- Assume market orders for historical data
            p.quantity,
            p.alpaca_order_id,
            CASE 
                WHEN p.status = 'closed' THEN 'filled'
                WHEN p.status = 'open' THEN 'filled'
                ELSE COALESCE(p.alpaca_status, 'filled')
            END as status,
            p.quantity as filled_qty,  -- Assume fully filled
            p.entry_price as filled_avg_price,
            p.entry_time as submitted_at,
            p.entry_time as filled_at,
            p.created_at,
            p.updated_at,
            jsonb_build_object(
                'migrated_from', 'positions',
                'migration_date', NOW(),
                'original_position_status', p.status,
                'original_alpaca_status', p.alpaca_status
            ) as metadata
        FROM positions p
        WHERE p.alpaca_order_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM orders o WHERE o.alpaca_order_id = p.alpaca_order_id
          );
        
        RAISE NOTICE 'Migrated % order records from positions table', 
            (SELECT COUNT(*) FROM orders WHERE metadata->>'migrated_from' = 'positions');
    ELSE
        RAISE NOTICE 'No alpaca_order_id column in positions - no migration needed';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES - Run these to verify migration
-- ============================================================================

-- Count orders created
SELECT 
    'Orders table' as check_item,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE metadata->>'migrated_from' = 'positions') as migrated_count
FROM orders;

-- Check order status distribution
SELECT 
    status,
    COUNT(*) as count
FROM orders
GROUP BY status
ORDER BY count DESC;

-- Verify positions with orders linked
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
LIMIT 20;


-- ============================================================================
-- PHASE 2: Drop old columns from positions (RUN AFTER VERIFICATION)
-- ⚠️ ONLY RUN THIS AFTER CONFIRMING MIGRATION WAS SUCCESSFUL
-- ============================================================================

-- Uncomment and run these ONLY after verifying Phase 1:

-- BEGIN;
-- 
-- -- Drop order-related columns from positions
-- ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_order_id;
-- ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_status;
-- 
-- -- Add comment to positions table
-- COMMENT ON TABLE positions IS 'Actual holdings - order data is in the orders table (migrated 2025-12-27)';
-- 
-- COMMIT;
-- 
-- -- Verify columns removed
-- SELECT column_name 
-- FROM information_schema.columns 
-- WHERE table_name = 'positions' 
-- ORDER BY ordinal_position;


-- ============================================================================
-- ROLLBACK SCRIPT (In case of emergency)
-- ============================================================================

-- If something goes wrong, you can rollback:
-- 
-- BEGIN;
-- 
-- -- Re-add columns to positions if needed
-- ALTER TABLE positions ADD COLUMN IF NOT EXISTS alpaca_order_id VARCHAR(100);
-- ALTER TABLE positions ADD COLUMN IF NOT EXISTS alpaca_status VARCHAR(50);
-- 
-- -- Restore data from orders back to positions
-- UPDATE positions p SET
--     alpaca_order_id = o.alpaca_order_id,
--     alpaca_status = o.status
-- FROM orders o
-- WHERE o.position_id = p.position_id
--   AND o.parent_order_id IS NULL;  -- Only entry orders
-- 
-- -- Drop orders table
-- DROP TABLE IF EXISTS orders;
-- 
-- COMMIT;
