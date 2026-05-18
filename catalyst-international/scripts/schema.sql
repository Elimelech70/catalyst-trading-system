-- Catalyst Trading System - International (HKEX)
-- Database Schema for PostgreSQL
-- Version: 1.0.0
-- Last Updated: 2025-12-09

-- Run this on your DigitalOcean Managed PostgreSQL database
-- psql $DATABASE_URL < schema.sql

-- ============================================================================
-- EXCHANGES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS exchanges (
    exchange_id SERIAL PRIMARY KEY,
    exchange_code VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'HKD',
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Hong_Kong',
    lot_size INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert HKEX exchange
INSERT INTO exchanges (exchange_code, name, currency, timezone, lot_size)
VALUES ('HKEX', 'Hong Kong Stock Exchange', 'HKD', 'Asia/Hong_Kong', 100)
ON CONFLICT (exchange_code) DO NOTHING;

-- ============================================================================
-- SECURITIES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(200),
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap DECIMAL(20, 2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(symbol)
);

CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);
CREATE INDEX IF NOT EXISTS idx_securities_exchange ON securities(exchange_id);

-- ============================================================================
-- AGENT CYCLES TABLE (for tracking AI agent runs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_cycles (
    cycle_id VARCHAR(100) PRIMARY KEY,
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10, 2),
    tools_called JSONB,
    trades_executed INTEGER DEFAULT 0,
    api_tokens_used INTEGER DEFAULT 0,
    api_cost_usd DECIMAL(10, 4),
    final_response TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_cycles_exchange ON agent_cycles(exchange_id);
CREATE INDEX IF NOT EXISTS idx_agent_cycles_started ON agent_cycles(started_at);

-- ============================================================================
-- AGENT DECISIONS TABLE (audit trail for all decisions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_decisions (
    decision_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(100) REFERENCES agent_cycles(cycle_id),
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    decision_type VARCHAR(50) NOT NULL,  -- trade, skip, close, emergency, observation
    symbol VARCHAR(20),
    reasoning TEXT NOT NULL,
    tools_called JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_cycle ON agent_decisions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_type ON agent_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON agent_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created ON agent_decisions(created_at);

-- ============================================================================
-- POSITIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    security_id INTEGER REFERENCES securities(security_id),
    side VARCHAR(10) NOT NULL,  -- buy, sell
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(15, 4) NOT NULL,
    exit_price DECIMAL(15, 4),
    stop_loss DECIMAL(15, 4),
    take_profit DECIMAL(15, 4),
    entry_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    realized_pnl DECIMAL(15, 2),
    broker_order_id VARCHAR(100),
    broker_code VARCHAR(20) NOT NULL DEFAULT 'IBKR',
    currency VARCHAR(3) NOT NULL DEFAULT 'HKD',
    status VARCHAR(20) NOT NULL DEFAULT 'open',  -- open, closed, cancelled
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_security ON positions(security_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_broker ON positions(broker_code);
CREATE INDEX IF NOT EXISTS idx_positions_entry ON positions(entry_time);

-- ============================================================================
-- TRADING CYCLES TABLE (shared with US system)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading_cycles (
    cycle_id SERIAL PRIMARY KEY,
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    currency VARCHAR(3) NOT NULL DEFAULT 'HKD',
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    mode VARCHAR(20) DEFAULT 'paper',  -- paper, live
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trading_cycles_exchange ON trading_cycles(exchange_id);
CREATE INDEX IF NOT EXISTS idx_trading_cycles_status ON trading_cycles(status);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Get or create security by symbol
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
    v_exchange_id INTEGER;
BEGIN
    -- Get HKEX exchange_id
    SELECT exchange_id INTO v_exchange_id
    FROM exchanges WHERE exchange_code = 'HKEX';

    -- Try to find existing security
    SELECT security_id INTO v_security_id
    FROM securities WHERE symbol = p_symbol;

    -- If not found, create it
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange_id)
        VALUES (p_symbol, v_exchange_id)
        RETURNING security_id INTO v_security_id;
    END IF;

    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Daily trading summary view
CREATE OR REPLACE VIEW v_daily_trading_summary AS
SELECT
    DATE(p.entry_time AT TIME ZONE 'Asia/Hong_Kong') as trading_date,
    COUNT(*) FILTER (WHERE p.status = 'closed') as trades_closed,
    COUNT(*) FILTER (WHERE p.status = 'open') as trades_open,
    COALESCE(SUM(p.realized_pnl) FILTER (WHERE p.status = 'closed'), 0) as realized_pnl,
    COALESCE(AVG(p.realized_pnl) FILTER (WHERE p.status = 'closed'), 0) as avg_pnl_per_trade,
    COUNT(*) FILTER (WHERE p.status = 'closed' AND p.realized_pnl > 0) as winning_trades,
    COUNT(*) FILTER (WHERE p.status = 'closed' AND p.realized_pnl <= 0) as losing_trades
FROM positions p
WHERE p.broker_code = 'IBKR'
GROUP BY DATE(p.entry_time AT TIME ZONE 'Asia/Hong_Kong')
ORDER BY trading_date DESC;

-- Agent performance view
CREATE OR REPLACE VIEW v_agent_performance AS
SELECT
    DATE(ac.started_at AT TIME ZONE 'Asia/Hong_Kong') as run_date,
    COUNT(*) as total_cycles,
    SUM(ac.trades_executed) as total_trades,
    AVG(ac.duration_seconds) as avg_cycle_duration,
    SUM(ac.api_tokens_used) as total_tokens,
    SUM(ac.api_cost_usd) as total_api_cost,
    COUNT(*) FILTER (WHERE ac.error IS NOT NULL) as cycles_with_errors
FROM agent_cycles ac
GROUP BY DATE(ac.started_at AT TIME ZONE 'Asia/Hong_Kong')
ORDER BY run_date DESC;

-- ============================================================================
-- GRANT PERMISSIONS (adjust username as needed)
-- ============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_db_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_db_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_db_user;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify schema created successfully
DO $$
BEGIN
    RAISE NOTICE 'Schema created successfully!';
    RAISE NOTICE 'Tables: exchanges, securities, agent_cycles, agent_decisions, positions, trading_cycles';
    RAISE NOTICE 'Functions: get_or_create_security()';
    RAISE NOTICE 'Views: v_daily_trading_summary, v_agent_performance';
END $$;
