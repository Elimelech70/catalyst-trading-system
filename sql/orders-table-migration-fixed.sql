-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: orders-table-migration-fixed.sql
-- Version: 1.0.1
-- Last Updated: 2025-12-27
-- Purpose: Add proper orders table - FIXED for actual schema types
-- ============================================================================

BEGIN;

-- Step 1: Create orders table with CORRECT types matching existing schema
CREATE TABLE IF NOT EXISTS orders (
    -- Primary Key (SERIAL to match positions.position_id style)
    order_id SERIAL PRIMARY KEY,

    -- Foreign Keys (types match actual schema)
    position_id INTEGER REFERENCES positions(position_id),  -- INTEGER not UUID
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id),  -- VARCHAR not UUID

    -- Order Hierarchy (for bracket orders)
    parent_order_id INTEGER REFERENCES orders(order_id),
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
    CONSTRAINT chk_order_quantity CHECK (quantity > 0)
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

-- Step 4: Migrate existing order data from positions table
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
        ELSE p.side
    END as side,
    'market' as order_type,
    p.quantity,
    p.alpaca_order_id,
    CASE
        WHEN p.status = 'closed' THEN 'filled'
        WHEN p.status = 'open' THEN 'filled'
        ELSE COALESCE(p.alpaca_status, 'filled')
    END as status,
    p.quantity as filled_qty,
    p.entry_price as filled_avg_price,
    p.opened_at as submitted_at,
    p.opened_at as filled_at,
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

COMMIT;

-- Verification queries
SELECT 'Orders table created' as status, COUNT(*) as total_orders FROM orders;

SELECT
    status,
    COUNT(*) as count
FROM orders
GROUP BY status
ORDER BY count DESC;
