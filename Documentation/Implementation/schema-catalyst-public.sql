-- ============================================================================
-- PUBLIC CATALYST TRADING SYSTEM
-- Name of Application: Catalyst Trading System
-- Name of file: schema-catalyst-public.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-28
-- Purpose: Complete trading system schema for public release (self-hosted)
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-28) - Initial public release schema
--   - Core trading tables (securities, positions, orders, patterns)
--   - claude_outputs JSON staging table for Claude Code integration
--   - Helper views and functions
--   - Designed for self-hosting by community members
--
-- Description:
-- This schema provides everything needed to run the Public Catalyst Trading
-- System. It includes trading tables and a JSON staging table (claude_outputs)
-- where Claude Code can write observations, learnings, and decisions.
--
-- USAGE:
-- psql "postgresql://user:pass@host:port/catalyst_public" < schema-catalyst-public.sql
-- ============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE TRADING TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- SECURITIES: Tradeable instruments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200),
    exchange VARCHAR(20) DEFAULT 'US',
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap DECIMAL(20, 2),
    avg_volume BIGINT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);
CREATE INDEX IF NOT EXISTS idx_securities_active ON securities(is_active) WHERE is_active = TRUE;

-- ----------------------------------------------------------------------------
-- TRADING SESSIONS: Daily trading session tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trading_sessions (
    session_id SERIAL PRIMARY KEY,
    session_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    session_date DATE NOT NULL,
    mode VARCHAR(20) DEFAULT 'autonomous',
    status VARCHAR(20) DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    starting_capital DECIMAL(14,2),
    ending_capital DECIMAL(14,2),
    realized_pnl DECIMAL(14,2) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON trading_sessions(session_date DESC);

-- ----------------------------------------------------------------------------
-- POSITIONS: Current and historical positions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    position_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Position details
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(12,4) NOT NULL,
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    
    -- Risk management
    stop_loss DECIMAL(12,4),
    take_profit DECIMAL(12,4),
    trailing_stop_pct DECIMAL(5,2),
    
    -- Exit details
    exit_price DECIMAL(12,4),
    exit_time TIMESTAMPTZ,
    exit_reason VARCHAR(100),
    
    -- P&L
    realized_pnl DECIMAL(14,2),
    realized_pnl_pct DECIMAL(8,4),
    max_favorable DECIMAL(8,4),
    max_adverse DECIMAL(8,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'open',
    broker_position_id VARCHAR(50),
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_session ON positions(session_id);

-- ----------------------------------------------------------------------------
-- ORDERS: All orders submitted to broker
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    order_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    position_id INTEGER REFERENCES positions(position_id),
    session_id INTEGER REFERENCES trading_sessions(session_id),
    
    -- Order details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    
    -- Execution
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(12,4),
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',
    broker_order_id VARCHAR(50),
    
    -- Timing
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    
    -- Metadata
    reject_reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_broker ON orders(broker_order_id);

-- ----------------------------------------------------------------------------
-- PATTERNS: Detected chart patterns
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id SERIAL PRIMARY KEY,
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Pattern details
    pattern_type VARCHAR(50) NOT NULL,
    pattern_name VARCHAR(100),
    confidence DECIMAL(3,2),
    
    -- Price levels
    entry_price DECIMAL(12,4),
    stop_loss DECIMAL(12,4),
    target_price DECIMAL(12,4),
    
    -- Timing
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    -- Outcome tracking
    was_traded BOOLEAN DEFAULT FALSE,
    outcome VARCHAR(20),
    actual_pnl DECIMAL(14,2),
    
    -- Metadata
    detection_data JSONB,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patterns_symbol ON patterns(symbol);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_detected ON patterns(detected_at DESC);

-- ----------------------------------------------------------------------------
-- SCANS: Market scan results
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scans (
    scan_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    
    -- Scan details
    scan_type VARCHAR(50) NOT NULL,
    scan_time TIMESTAMPTZ DEFAULT NOW(),
    
    -- Results
    symbols_scanned INTEGER,
    candidates_found INTEGER,
    results JSONB,
    
    -- Metadata
    scan_params JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scans_type ON scans(scan_type, scan_time DESC);

-- ----------------------------------------------------------------------------
-- DECISIONS: Trading decisions with reasoning
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decisions (
    decision_id SERIAL PRIMARY KEY,
    decision_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    position_id INTEGER REFERENCES positions(position_id),
    
    -- Decision details
    decision_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    action VARCHAR(20),
    
    -- Reasoning
    reasoning TEXT NOT NULL,
    confidence DECIMAL(3,2),
    factors JSONB,
    
    -- Outcome
    was_executed BOOLEAN DEFAULT FALSE,
    outcome VARCHAR(50),
    
    -- Metadata
    thinking_level VARCHAR(20),
    model_used VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_decisions_session ON decisions(session_id);

-- ============================================================================
-- CLAUDE OUTPUTS: JSON Staging Table for Claude Code
-- ============================================================================

CREATE TABLE IF NOT EXISTS claude_outputs (
    id SERIAL PRIMARY KEY,
    output_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    
    -- Identity
    agent_id VARCHAR(50) NOT NULL DEFAULT 'claude_code',
    instance_id VARCHAR(100),
    
    -- Classification
    output_type VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    
    -- Content (denormalized JSON)
    payload JSONB NOT NULL,
    
    -- Context
    session_id INTEGER REFERENCES trading_sessions(session_id),
    symbol VARCHAR(20),
    
    -- Metadata
    confidence DECIMAL(3,2),
    priority VARCHAR(20) DEFAULT 'normal',
    tags JSONB,
    
    -- Lifecycle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    -- Sync tracking (for external pull if needed)
    synced_at TIMESTAMPTZ,
    synced_to VARCHAR(50),
    
    -- Processing
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    processing_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_claude_outputs_type ON claude_outputs(output_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_outputs_agent ON claude_outputs(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_outputs_unsynced ON claude_outputs(synced_at) WHERE synced_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_claude_outputs_symbol ON claude_outputs(symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claude_outputs_payload ON claude_outputs USING GIN (payload);

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW v_recent_observations AS
SELECT 
    id,
    agent_id,
    payload->>'subject' as subject,
    payload->>'content' as content,
    (payload->>'confidence')::decimal as confidence,
    payload->>'horizon' as horizon,
    created_at
FROM claude_outputs
WHERE output_type = 'observation'
ORDER BY created_at DESC
LIMIT 100;

CREATE OR REPLACE VIEW v_learnings AS
SELECT 
    id,
    agent_id,
    payload->>'category' as category,
    payload->>'learning' as learning,
    (payload->>'confidence')::decimal as confidence,
    (payload->>'times_validated')::integer as times_validated,
    created_at
FROM claude_outputs
WHERE output_type = 'learning'
ORDER BY (payload->>'confidence')::decimal DESC;

CREATE OR REPLACE VIEW v_open_questions AS
SELECT 
    id,
    agent_id,
    payload->>'question' as question,
    payload->>'horizon' as horizon,
    (payload->>'priority')::integer as priority,
    payload->>'current_hypothesis' as hypothesis,
    created_at
FROM claude_outputs
WHERE output_type = 'question'
  AND (payload->>'status' IS NULL OR payload->>'status' = 'open')
ORDER BY (payload->>'priority')::integer DESC;

CREATE OR REPLACE VIEW v_unsynced_outputs AS
SELECT *
FROM claude_outputs
WHERE synced_at IS NULL
ORDER BY created_at ASC;

CREATE OR REPLACE VIEW v_today_decisions AS
SELECT 
    id,
    agent_id,
    symbol,
    payload->>'decision_type' as decision_type,
    payload->>'action' as action,
    payload->>'reasoning' as reasoning,
    (payload->>'confidence')::decimal as confidence,
    created_at
FROM claude_outputs
WHERE output_type = 'decision'
  AND created_at >= CURRENT_DATE
ORDER BY created_at DESC;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION insert_observation(
    p_agent_id VARCHAR(50),
    p_subject VARCHAR(200),
    p_content TEXT,
    p_confidence DECIMAL(3,2) DEFAULT NULL,
    p_horizon VARCHAR(10) DEFAULT NULL,
    p_symbol VARCHAR(20) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_id INTEGER;
BEGIN
    INSERT INTO claude_outputs (agent_id, output_type, symbol, confidence, payload)
    VALUES (
        p_agent_id,
        'observation',
        p_symbol,
        p_confidence,
        jsonb_build_object(
            'subject', p_subject,
            'content', p_content,
            'confidence', p_confidence,
            'horizon', p_horizon
        )
    )
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION insert_learning(
    p_agent_id VARCHAR(50),
    p_category VARCHAR(100),
    p_learning TEXT,
    p_source VARCHAR(200) DEFAULT NULL,
    p_confidence DECIMAL(3,2) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_id INTEGER;
BEGIN
    INSERT INTO claude_outputs (agent_id, output_type, category, confidence, payload)
    VALUES (
        p_agent_id,
        'learning',
        p_category,
        p_confidence,
        jsonb_build_object(
            'category', p_category,
            'learning', p_learning,
            'source', p_source,
            'confidence', p_confidence,
            'times_validated', 0,
            'times_contradicted', 0
        )
    )
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION insert_question(
    p_agent_id VARCHAR(50),
    p_question TEXT,
    p_horizon VARCHAR(10) DEFAULT 'h1',
    p_priority INTEGER DEFAULT 5,
    p_hypothesis TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_id INTEGER;
BEGIN
    INSERT INTO claude_outputs (agent_id, output_type, priority, payload)
    VALUES (
        p_agent_id,
        'question',
        CASE WHEN p_priority >= 8 THEN 'high' WHEN p_priority >= 5 THEN 'normal' ELSE 'low' END,
        jsonb_build_object(
            'question', p_question,
            'horizon', p_horizon,
            'priority', p_priority,
            'status', 'open',
            'current_hypothesis', p_hypothesis,
            'evidence_for', '[]'::jsonb,
            'evidence_against', '[]'::jsonb
        )
    )
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT '========================================' as separator;
SELECT 'PUBLIC CATALYST TRADING SYSTEM' as title;
SELECT 'Schema created successfully!' as status;
SELECT '========================================' as separator;

SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT 'Views created:' as info;
SELECT table_name as view_name
FROM information_schema.views 
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT 'Functions created:' as info;
SELECT routine_name as function_name
FROM information_schema.routines 
WHERE routine_schema = 'public'
  AND routine_type = 'FUNCTION'
ORDER BY routine_name;
