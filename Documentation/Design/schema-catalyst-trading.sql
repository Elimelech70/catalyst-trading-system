-- ============================================================================
-- CATALYST TRADING SYSTEM - DATABASE SCHEMA
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: schema-catalyst-trading.sql
-- Version: 1.0.0
-- Last Updated: 2026-02-01
-- Purpose: Complete schema for trading database (catalyst_intl / catalyst_dev)
-- Release Status: PUBLIC - Community self-hosting
--
-- REVISION HISTORY:
-- v1.0.0 (2026-02-01) - Initial release version
--   - Core trading tables
--   - Added agent_logs table for observability
--   - Removed all consciousness references
--   - Designed for self-hosting
-- ============================================================================

-- ============================================================================
-- 1. EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 2. SECURITIES - Stock Registry
-- ============================================================================
CREATE TABLE IF NOT EXISTS securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(200),
    exchange VARCHAR(20) NOT NULL,           -- HKEX, NYSE, NASDAQ
    currency VARCHAR(10) DEFAULT 'HKD',
    lot_size INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);
CREATE INDEX IF NOT EXISTS idx_securities_exchange ON securities(exchange);

COMMENT ON TABLE securities IS 'Registry of tradeable securities';

-- ============================================================================
-- 3. POSITIONS - Open and Closed Positions
-- ============================================================================
CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Position Details
    side VARCHAR(10) NOT NULL,               -- long, short
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(18,4),
    entry_value DECIMAL(18,4),
    
    -- Current State
    current_price DECIMAL(18,4),
    current_value DECIMAL(18,4),
    unrealized_pnl DECIMAL(18,4),
    unrealized_pnl_pct DECIMAL(8,4),
    
    -- Risk Management
    stop_loss DECIMAL(18,4),
    take_profit DECIMAL(18,4),
    high_watermark DECIMAL(18,4),            -- For trailing stops
    
    -- Status
    status VARCHAR(20) DEFAULT 'open',       -- open, closed, error
    close_reason VARCHAR(100),
    exit_price DECIMAL(18,4),
    exit_value DECIMAL(18,4),
    realized_pnl DECIMAL(18,4),
    realized_pnl_pct DECIMAL(8,4),
    
    -- Broker Reference
    broker_order_id VARCHAR(100),
    broker_position_id VARCHAR(100),
    
    -- Timestamps
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_opened ON positions(opened_at DESC);

COMMENT ON TABLE positions IS 'Trading positions - open and closed';

-- ============================================================================
-- 4. ORDERS - Order History
-- ============================================================================
CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Order Details
    side VARCHAR(10) NOT NULL,               -- buy, sell
    order_type VARCHAR(20) NOT NULL,         -- market, limit, stop
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(18,4),
    stop_price DECIMAL(18,4),
    
    -- Execution
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(18,4),
    commission DECIMAL(18,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',    -- pending, submitted, filled, partial, cancelled, rejected, error
    error_message TEXT,
    
    -- Broker Reference
    broker_order_id VARCHAR(100),
    
    -- Timestamps
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_broker_id ON orders(broker_order_id);

COMMENT ON TABLE orders IS 'Order history and execution details';

-- ============================================================================
-- 5. DECISIONS - AI Decision Audit Trail
-- ============================================================================
CREATE TABLE IF NOT EXISTS decisions (
    decision_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50),
    symbol VARCHAR(20),
    
    -- Decision
    decision_type VARCHAR(50) NOT NULL,      -- scan, entry, exit, hold, skip
    action VARCHAR(50),                       -- buy, sell, hold, close
    reasoning TEXT,
    confidence DECIMAL(3,2),
    
    -- Context
    market_conditions JSONB,
    technical_data JSONB,
    news_sentiment JSONB,
    
    -- Outcome
    position_id INTEGER REFERENCES positions(position_id),
    order_id INTEGER REFERENCES orders(order_id),
    
    -- Metadata
    model_used VARCHAR(100),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol ON decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);

COMMENT ON TABLE decisions IS 'AI decision audit trail with reasoning';

-- ============================================================================
-- 6. SCAN_RESULTS - Scanner Output
-- ============================================================================
CREATE TABLE IF NOT EXISTS scan_results (
    scan_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50),
    symbol VARCHAR(20) NOT NULL,
    
    -- Scan Data
    tier INTEGER,                            -- 1, 2, 3 (filtering tier)
    score DECIMAL(5,2),
    
    -- Market Data
    last_price DECIMAL(18,4),
    volume BIGINT,
    change_pct DECIMAL(8,4),
    
    -- Technical Indicators
    rsi DECIMAL(5,2),
    macd_signal VARCHAR(20),
    vwap_position VARCHAR(20),
    
    -- Pattern Detection
    patterns JSONB,
    
    -- News
    news_sentiment DECIMAL(3,2),
    news_count INTEGER,
    
    -- Result
    passed BOOLEAN DEFAULT false,
    skip_reason VARCHAR(200),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scan_cycle ON scan_results(cycle_id);
CREATE INDEX IF NOT EXISTS idx_scan_symbol ON scan_results(symbol);
CREATE INDEX IF NOT EXISTS idx_scan_passed ON scan_results(passed);

COMMENT ON TABLE scan_results IS 'Market scanner output and filtering results';

-- ============================================================================
-- 7. TRADING_CYCLES - Cycle Execution Logs
-- ============================================================================
CREATE TABLE IF NOT EXISTS trading_cycles (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) UNIQUE NOT NULL,
    
    -- Cycle Info
    mode VARCHAR(20) NOT NULL,               -- scan, trade, close, heartbeat
    agent_id VARCHAR(50),
    
    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    -- Results
    status VARCHAR(20) DEFAULT 'running',    -- running, completed, failed, suspended
    candidates_found INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    positions_closed INTEGER DEFAULT 0,
    
    -- Cost
    api_calls INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    
    -- Error
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cycles_mode ON trading_cycles(mode);
CREATE INDEX IF NOT EXISTS idx_cycles_status ON trading_cycles(status);
CREATE INDEX IF NOT EXISTS idx_cycles_started ON trading_cycles(started_at DESC);

COMMENT ON TABLE trading_cycles IS 'Trading cycle execution logs';

-- ============================================================================
-- 8. PATTERNS - Detected Technical Patterns
-- ============================================================================
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    
    -- Pattern Info
    pattern_type VARCHAR(50) NOT NULL,       -- bull_flag, breakout, momentum, etc.
    timeframe VARCHAR(20),                    -- 1m, 5m, 15m, 1h, 1d
    confidence DECIMAL(3,2),
    
    -- Price Levels
    entry_price DECIMAL(18,4),
    target_price DECIMAL(18,4),
    stop_price DECIMAL(18,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'detected',   -- detected, confirmed, failed, expired
    outcome VARCHAR(20),                      -- win, loss, scratch
    
    -- Timestamps
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patterns_symbol ON patterns(symbol);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(status);

COMMENT ON TABLE patterns IS 'Detected technical patterns and their outcomes';

-- ============================================================================
-- 9. AGENT_LOGS - Runtime Logs (NEW - Critical for Observability)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    -- Log Info
    level VARCHAR(20) NOT NULL,              -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    source VARCHAR(100) NOT NULL,            -- unified_agent, tool_executor, position_monitor, etc.
    message TEXT NOT NULL,
    
    -- Context
    context JSONB,                           -- Structured data (symbol, tool, etc.)
    cycle_id VARCHAR(50),                    -- Link to trading cycle
    symbol VARCHAR(20),                      -- Stock symbol if relevant
    
    -- Error Details (for ERROR/CRITICAL)
    error_type VARCHAR(100),
    stack_trace TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_level ON agent_logs(level);
CREATE INDEX IF NOT EXISTS idx_agent_logs_source ON agent_logs(source);
CREATE INDEX IF NOT EXISTS idx_agent_logs_symbol ON agent_logs(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_logs_cycle ON agent_logs(cycle_id);

-- Partial index for quick error lookup
CREATE INDEX IF NOT EXISTS idx_agent_logs_errors ON agent_logs(timestamp DESC) 
    WHERE level IN ('ERROR', 'CRITICAL');

COMMENT ON TABLE agent_logs IS 'Runtime logs for observability and debugging';

-- ============================================================================
-- 10. SERVICE_HEALTH - Service Heartbeat Status
-- ============================================================================
CREATE TABLE IF NOT EXISTS service_health (
    service_name VARCHAR(100) PRIMARY KEY,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'unknown',  -- running, stopped, error
    last_heartbeat TIMESTAMPTZ,
    
    -- Metrics
    last_check_count INTEGER DEFAULT 0,
    positions_monitored INTEGER DEFAULT 0,
    exits_executed INTEGER DEFAULT 0,
    haiku_calls INTEGER DEFAULT 0,
    
    -- Timing
    started_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE service_health IS 'Service heartbeat and health status';

-- ============================================================================
-- 11. POSITION_MONITOR_STATUS - Real-time Position Tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',    -- pending, starting, running, sleeping, stopped, error
    
    -- Market State
    last_price DECIMAL(18,4),
    high_watermark DECIMAL(18,4),
    current_pnl_pct DECIMAL(8,4),
    
    -- Technical Analysis
    last_rsi DECIMAL(5,2),
    last_macd_signal VARCHAR(20),
    last_vwap_position VARCHAR(20),
    
    -- Signals
    hold_signals TEXT[],
    exit_signals TEXT[],
    recommendation VARCHAR(10),              -- HOLD, EXIT, REVIEW
    
    -- AI Tracking
    haiku_calls INTEGER DEFAULT 0,
    estimated_cost DECIMAL(8,4) DEFAULT 0,
    
    -- Timing
    last_check_at TIMESTAMPTZ,
    next_check_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monitor_position ON position_monitor_status(position_id);
CREATE INDEX IF NOT EXISTS idx_monitor_status ON position_monitor_status(status);
CREATE INDEX IF NOT EXISTS idx_monitor_symbol ON position_monitor_status(symbol);

COMMENT ON TABLE position_monitor_status IS 'Real-time position monitoring status';

-- ============================================================================
-- 12. HELPER VIEWS
-- ============================================================================

-- Open positions with current P&L
CREATE OR REPLACE VIEW v_open_positions AS
SELECT 
    p.position_id,
    p.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.current_price,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    p.stop_loss,
    p.take_profit,
    p.opened_at,
    m.status as monitor_status,
    m.recommendation,
    m.last_check_at
FROM positions p
LEFT JOIN position_monitor_status m ON p.position_id = m.position_id
WHERE p.status = 'open'
ORDER BY p.opened_at DESC;

-- Recent errors
CREATE OR REPLACE VIEW v_recent_errors AS
SELECT 
    id,
    timestamp,
    source,
    message,
    context->>'symbol' as symbol,
    cycle_id,
    error_type
FROM agent_logs
WHERE level IN ('ERROR', 'CRITICAL')
ORDER BY timestamp DESC
LIMIT 100;

-- Service health overview
CREATE OR REPLACE VIEW v_service_status AS
SELECT 
    service_name,
    status,
    last_heartbeat,
    positions_monitored,
    exits_executed,
    CASE 
        WHEN last_heartbeat > NOW() - INTERVAL '15 minutes' THEN 'HEALTHY'
        WHEN last_heartbeat > NOW() - INTERVAL '1 hour' THEN 'STALE'
        ELSE 'OFFLINE'
    END as health
FROM service_health;

-- Daily trading summary
CREATE OR REPLACE VIEW v_daily_summary AS
SELECT 
    DATE(opened_at) as trade_date,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE status = 'closed' AND realized_pnl > 0) as wins,
    COUNT(*) FILTER (WHERE status = 'closed' AND realized_pnl < 0) as losses,
    COUNT(*) FILTER (WHERE status = 'open') as still_open,
    SUM(realized_pnl) FILTER (WHERE status = 'closed') as realized_pnl,
    SUM(unrealized_pnl) FILTER (WHERE status = 'open') as unrealized_pnl
FROM positions
GROUP BY DATE(opened_at)
ORDER BY trade_date DESC;

-- ============================================================================
-- 13. HELPER FUNCTIONS
-- ============================================================================

-- Function to clean old logs (keep 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM agent_logs 
    WHERE timestamp < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get error rate for last N hours
CREATE OR REPLACE FUNCTION get_error_rate(hours INTEGER DEFAULT 24)
RETURNS TABLE(
    total_logs BIGINT,
    error_count BIGINT,
    error_rate DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_logs,
        COUNT(*) FILTER (WHERE level IN ('ERROR', 'CRITICAL'))::BIGINT as error_count,
        ROUND(
            (COUNT(*) FILTER (WHERE level IN ('ERROR', 'CRITICAL'))::DECIMAL / 
             NULLIF(COUNT(*), 0) * 100), 2
        ) as error_rate
    FROM agent_logs
    WHERE timestamp > NOW() - (hours || ' hours')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 14. LOG RETENTION POLICY (Optional - run via cron)
-- ============================================================================
-- Schedule: 0 0 * * 0 psql $DATABASE_URL -c "SELECT cleanup_old_logs();"

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================

COMMENT ON DATABASE current_database() IS 'Catalyst Trading System - Trading Database';
