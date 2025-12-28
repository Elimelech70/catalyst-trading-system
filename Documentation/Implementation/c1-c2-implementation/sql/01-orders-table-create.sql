-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: 01-orders-table-create.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Create orders table to properly separate order tracking from positions
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-27) - Initial creation
--   - Implements ARCHITECTURE-RULES.md Rule 1: Orders ≠ Positions
--   - Creates orders table with proper schema
--   - Creates indexes for performance
--   - Creates views for Doctor Claude monitoring
--
-- EXECUTION:
--   psql $DATABASE_URL -f 01-orders-table-create.sql
-- ============================================================================

\echo '=============================================='
\echo 'C1 FIX: Creating orders table'
\echo '=============================================='

BEGIN;

-- ============================================================================
-- STEP 1: Create orders table
-- ============================================================================
\echo 'Step 1: Creating orders table...'

CREATE TABLE IF NOT EXISTS orders (
    -- Primary Key (SERIAL to match positions.position_id style)
    order_id SERIAL PRIMARY KEY,

    -- Foreign Keys (types match actual deployed schema)
    position_id INTEGER REFERENCES positions(position_id),  -- NULL until position created
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    cycle_id VARCHAR(20) REFERENCES trading_cycles(cycle_id),

    -- Order Hierarchy (for bracket orders)
    parent_order_id INTEGER REFERENCES orders(order_id),
    order_class VARCHAR(20),  -- 'simple', 'bracket', 'oco', 'oto'

    -- Order Purpose (entry vs exit)
    order_purpose VARCHAR(20) DEFAULT 'entry',  -- 'entry', 'stop_loss', 'take_profit', 'exit'

    -- Order Specification
    side VARCHAR(10) NOT NULL,  -- 'buy', 'sell'
    order_type VARCHAR(20) NOT NULL,  -- 'market', 'limit', 'stop', 'stop_limit', 'trailing_stop'
    time_in_force VARCHAR(10) DEFAULT 'day',  -- 'day', 'gtc', 'ioc', 'fok'
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12, 4),  -- For limit and stop_limit orders
    stop_price DECIMAL(12, 4),  -- For stop and stop_limit orders
    trail_percent DECIMAL(5, 2),  -- For trailing stop orders
    trail_price DECIMAL(12, 4),  -- For trailing stop orders

    -- Alpaca Integration
    alpaca_order_id VARCHAR(100) UNIQUE,  -- Alpaca's order ID
    alpaca_client_order_id VARCHAR(100),  -- Our client order ID sent to Alpaca

    -- Order Status (matches Alpaca status values)
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    -- Lifecycle: created → submitted → accepted → [partial_fill] → filled
    --            created → submitted → accepted → canceled/expired/rejected

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

    -- Error tracking
    rejection_reason TEXT,
    cancel_reason TEXT,
    
    -- Metadata
    metadata JSONB,

    -- Constraints
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    CONSTRAINT chk_order_class CHECK (order_class IS NULL OR order_class IN ('simple', 'bracket', 'oco', 'oto')),
    CONSTRAINT chk_order_quantity CHECK (quantity > 0),
    CONSTRAINT chk_order_purpose CHECK (order_purpose IN ('entry', 'stop_loss', 'take_profit', 'exit'))
);

\echo 'Step 1 complete: orders table created'

-- ============================================================================
-- STEP 2: Create indexes for performance
-- ============================================================================
\echo 'Step 2: Creating indexes...'

-- Index on position_id (for finding orders by position)
CREATE INDEX IF NOT EXISTS idx_orders_position 
ON orders(position_id) WHERE position_id IS NOT NULL;

-- Index on security_id (for finding orders by stock)
CREATE INDEX IF NOT EXISTS idx_orders_security ON orders(security_id);

-- Index on cycle_id (for finding orders by trading day)
CREATE INDEX IF NOT EXISTS idx_orders_cycle ON orders(cycle_id);

-- Index on alpaca_order_id (for looking up by Alpaca ID)
CREATE INDEX IF NOT EXISTS idx_orders_alpaca_id 
ON orders(alpaca_order_id) WHERE alpaca_order_id IS NOT NULL;

-- Index on status (for finding active orders)
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- Index on parent_order_id (for bracket order legs)
CREATE INDEX IF NOT EXISTS idx_orders_parent 
ON orders(parent_order_id) WHERE parent_order_id IS NOT NULL;

-- Index for finding stuck/pending orders (Doctor Claude uses this)
CREATE INDEX IF NOT EXISTS idx_orders_pending 
ON orders(status, submitted_at) 
WHERE status IN ('created', 'submitted', 'accepted', 'pending_new', 'new', 'partial_fill');

-- Index on order_purpose (for separating entry vs exit orders)
CREATE INDEX IF NOT EXISTS idx_orders_purpose ON orders(order_purpose);

\echo 'Step 2 complete: indexes created'

-- ============================================================================
-- STEP 3: Add comments
-- ============================================================================
\echo 'Step 3: Adding table/column comments...'

COMMENT ON TABLE orders IS 'All orders sent to Alpaca - ARCHITECTURE RULE: Orders ≠ Positions';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created, then linked';
COMMENT ON COLUMN orders.parent_order_id IS 'For bracket orders: links stop_loss and take_profit to entry order';
COMMENT ON COLUMN orders.order_class IS 'bracket = entry with legs, oco = one-cancels-other, oto = one-triggers-other';
COMMENT ON COLUMN orders.order_purpose IS 'entry = opening position, stop_loss/take_profit/exit = closing position';
COMMENT ON COLUMN orders.status IS 'Tracks order lifecycle: created → submitted → accepted → filled (or cancelled/expired/rejected)';

\echo 'Step 3 complete: comments added'

-- ============================================================================
-- STEP 4: Create view for Doctor Claude monitoring
-- ============================================================================
\echo 'Step 4: Creating Doctor Claude monitoring view...'

CREATE OR REPLACE VIEW v_orders_status AS
SELECT 
    o.order_id,
    o.position_id,
    s.symbol,
    o.side,
    o.order_type,
    o.order_purpose,
    o.quantity,
    o.filled_qty,
    o.status,
    o.alpaca_order_id,
    o.submitted_at,
    o.filled_at,
    EXTRACT(EPOCH FROM (NOW() - o.submitted_at))/60 as minutes_pending,
    CASE 
        WHEN o.status IN ('created', 'submitted', 'accepted', 'pending_new', 'new')
             AND o.submitted_at < NOW() - INTERVAL '5 minutes'
        THEN true
        ELSE false
    END as is_stuck,
    o.rejection_reason,
    o.metadata
FROM orders o
JOIN securities s ON o.security_id = s.security_id
ORDER BY o.created_at DESC;

COMMENT ON VIEW v_orders_status IS 'Doctor Claude uses this view to monitor order status and detect stuck orders';

\echo 'Step 4 complete: monitoring view created'

-- ============================================================================
-- STEP 5: Create trigger for updated_at
-- ============================================================================
\echo 'Step 5: Creating updated_at trigger...'

CREATE OR REPLACE FUNCTION update_orders_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_orders_updated_at ON orders;
CREATE TRIGGER trigger_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_orders_updated_at();

\echo 'Step 5 complete: trigger created'

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
\echo ''
\echo '=============================================='
\echo 'VERIFICATION'
\echo '=============================================='

\echo 'Orders table columns:'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'orders'
ORDER BY ordinal_position;

\echo ''
\echo 'Orders table indexes:'
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'orders';

\echo ''
\echo '=============================================='
\echo 'PHASE 1 COMPLETE: Orders table created'
\echo 'Next: Run 02-migrate-data.sql'
\echo '=============================================='
