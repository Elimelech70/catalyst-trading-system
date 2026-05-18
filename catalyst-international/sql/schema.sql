-- =============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: schema.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-09
-- Purpose: PostgreSQL schema for autonomous trading agent with learning capability
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-09) - Initial implementation
-- - Core tables for decisions, positions, patterns, insights
-- - Strategy versioning for evolution tracking
-- - Meta-cognition for self-assessment
-- - Helper functions for common operations
--
-- Description:
-- This schema supports an autonomous trading agent that:
-- 1. Logs every decision with full reasoning (audit trail + ML training)
-- 2. Tracks positions with outcomes (win/loss analysis)
-- 3. Stores learned patterns and insights
-- 4. Manages strategy evolution over time
-- 5. Enables meta-cognition (thinking about thinking)
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- REFERENCE TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS exchanges (
    exchange_id SERIAL PRIMARY KEY,
    exchange_code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'HKD',
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Hong_Kong',
    morning_open TIME,
    morning_close TIME,
    afternoon_open TIME,
    afternoon_close TIME,
    lot_size INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO exchanges (exchange_code, name, currency, timezone, morning_open, morning_close, afternoon_open, afternoon_close, lot_size)
VALUES ('HKEX', 'Hong Kong Stock Exchange', 'HKD', 'Asia/Hong_Kong', '09:30', '12:00', '13:00', '16:00', 100)
ON CONFLICT (exchange_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    name VARCHAR(200),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, exchange_id)
);

CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);

-- =============================================================================
-- TIME DIMENSION
-- =============================================================================

CREATE TABLE IF NOT EXISTS time_dimension (
    time_id SERIAL PRIMARY KEY,
    full_timestamp TIMESTAMPTZ UNIQUE NOT NULL,
    date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    week INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    is_market_hours BOOLEAN DEFAULT FALSE,
    session VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_time_date ON time_dimension(date);
CREATE INDEX IF NOT EXISTS idx_time_market_hours ON time_dimension(is_market_hours);

-- =============================================================================
-- STRATEGY MANAGEMENT
-- =============================================================================

CREATE TABLE IF NOT EXISTS strategy_versions (
    strategy_id SERIAL PRIMARY KEY,
    version_number INTEGER NOT NULL DEFAULT 1,
    parameters JSONB NOT NULL,
    rationale TEXT,
    changed_by VARCHAR(50) DEFAULT 'SYSTEM',
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    performance_metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO strategy_versions (version_number, parameters, rationale, changed_by)
SELECT 1, '{
    "risk_appetite": "conservative",
    "max_position_size_pct": 5,
    "max_daily_loss_pct": 2,
    "max_open_positions": 3,
    "volume_threshold": 1.5,
    "price_threshold": 2.0,
    "min_risk_reward": 2.0,
    "rsi_min": 40,
    "rsi_max": 70,
    "stop_loss_atr_multiple": 1.5,
    "take_profit_atr_multiple": 2.5
}'::jsonb, 'Initial conservative strategy for system validation', 'SYSTEM'
WHERE NOT EXISTS (SELECT 1 FROM strategy_versions);

-- =============================================================================
-- DECISION TRACKING
-- =============================================================================

CREATE TABLE IF NOT EXISTS decisions (
    decision_id SERIAL PRIMARY KEY,
    decision_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    market VARCHAR(10) DEFAULT 'HKEX',
    symbol VARCHAR(20),
    stimulus_type VARCHAR(50) NOT NULL,
    stimulus_data JSONB,
    context_provided JSONB,
    observation TEXT,
    assessment TEXT,
    reasoning TEXT NOT NULL,
    confidence DECIMAL(5,2),
    confidence_reasoning TEXT,
    action VARCHAR(20) NOT NULL,
    entry_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    target_price DECIMAL(12,4),
    position_size DECIMAL(5,2),
    executed BOOLEAN DEFAULT FALSE,
    execution_price DECIMAL(12,4),
    execution_time TIMESTAMPTZ,
    position_id INTEGER,
    uncertainties TEXT[],
    additional_info_wanted TEXT[],
    thinking_level VARCHAR(20) DEFAULT 'TACTICAL',
    strategy_version_id INTEGER REFERENCES strategy_versions(strategy_id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol ON decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_decisions_action ON decisions(action);
CREATE INDEX IF NOT EXISTS idx_decisions_confidence ON decisions(confidence);
CREATE INDEX IF NOT EXISTS idx_decisions_thinking_level ON decisions(thinking_level);

-- =============================================================================
-- POSITIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    position_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20),
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(12,4) NOT NULL,
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    entry_decision_id INTEGER REFERENCES decisions(decision_id),
    stop_loss DECIMAL(12,4),
    take_profit DECIMAL(12,4),
    trailing_stop_pct DECIMAL(5,2),
    exit_price DECIMAL(12,4),
    exit_time TIMESTAMPTZ,
    exit_decision_id INTEGER REFERENCES decisions(decision_id),
    exit_reason VARCHAR(100),
    realized_pnl DECIMAL(14,2),
    realized_pnl_pct DECIMAL(8,4),
    max_favorable DECIMAL(8,4),
    max_adverse DECIMAL(8,4),
    holding_duration INTERVAL,
    status VARCHAR(20) DEFAULT 'open',
    broker_order_id VARCHAR(50),
    broker_code VARCHAR(20) DEFAULT 'IBKR',
    currency VARCHAR(10) DEFAULT 'HKD',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time DESC);

-- Prevent duplicate open positions for the same symbol (database-level safety net)
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_unique_open_symbol
  ON positions(symbol) WHERE status = 'open';

-- =============================================================================
-- PATTERNS
-- =============================================================================

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    pattern_type VARCHAR(50),
    description TEXT,
    identification_rules JSONB,
    conditions_favorable JSONB,
    conditions_unfavorable JSONB,
    times_traded INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    total_pnl DECIMAL(14,2) DEFAULT 0,
    avg_pnl DECIMAL(14,2),
    win_rate DECIMAL(5,2),
    avg_confidence_when_win DECIMAL(5,2),
    avg_confidence_when_loss DECIMAL(5,2),
    active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    last_traded_at TIMESTAMPTZ,
    source VARCHAR(50) DEFAULT 'ANALYTICAL',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patterns_active ON patterns(active);
CREATE INDEX IF NOT EXISTS idx_patterns_win_rate ON patterns(win_rate DESC);

-- =============================================================================
-- INSIGHTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS insights (
    insight_id SERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    thinking_level VARCHAR(20) NOT NULL,
    insight_type VARCHAR(50) NOT NULL,
    insight_text TEXT NOT NULL,
    supporting_evidence JSONB,
    action_taken TEXT,
    validation_status VARCHAR(20) DEFAULT 'pending',
    validated_at TIMESTAMPTZ,
    validation_notes TEXT,
    importance VARCHAR(20) DEFAULT 'normal',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_insights_generated_at ON insights(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_insights_thinking_level ON insights(thinking_level);

-- =============================================================================
-- META-COGNITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS meta_cognition (
    meta_id SERIAL PRIMARY KEY,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    period_type VARCHAR(20) NOT NULL,
    total_decisions INTEGER,
    decisions_acted_on INTEGER,
    decisions_held INTEGER,
    correct_actions INTEGER,
    incorrect_actions INTEGER,
    accuracy_rate DECIMAL(5,2),
    avg_confidence DECIMAL(5,2),
    avg_confidence_when_correct DECIMAL(5,2),
    avg_confidence_when_incorrect DECIMAL(5,2),
    overconfidence_score DECIMAL(5,2),
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    total_pnl DECIMAL(14,2),
    win_rate DECIMAL(5,2),
    avg_win DECIMAL(14,2),
    avg_loss DECIMAL(14,2),
    profit_factor DECIMAL(8,2),
    best_pattern VARCHAR(100),
    worst_pattern VARCHAR(100),
    patterns_discovered INTEGER,
    what_worked TEXT,
    what_didnt_work TEXT,
    improvements TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_period ON meta_cognition(period_start DESC);
CREATE INDEX IF NOT EXISTS idx_meta_type ON meta_cognition(period_type);

-- =============================================================================
-- AGENT CYCLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_cycles (
    cycle_id VARCHAR(100) PRIMARY KEY,
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds DECIMAL(10,2),
    tools_called JSONB,
    trades_executed INTEGER DEFAULT 0,
    decisions_made INTEGER DEFAULT 0,
    api_tokens_used INTEGER,
    api_cost_usd DECIMAL(10,4),
    final_response TEXT,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cycles_started ON agent_cycles(started_at DESC);

-- =============================================================================
-- AGENT DECISIONS (for compatibility with existing code)
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_decisions (
    decision_id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(100) REFERENCES agent_cycles(cycle_id),
    exchange_id INTEGER REFERENCES exchanges(exchange_id),
    decision_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    reasoning TEXT NOT NULL,
    tools_called JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_cycle ON agent_decisions(cycle_id);

-- =============================================================================
-- MARKET SNAPSHOTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    security_id INTEGER REFERENCES securities(security_id),
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    rsi_14 DECIMAL(6,2),
    macd DECIMAL(12,4),
    macd_signal DECIMAL(12,4),
    sma_20 DECIMAL(12,4),
    sma_50 DECIMAL(12,4),
    atr_14 DECIMAL(12,4),
    volume_ratio DECIMAL(8,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(security_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_time ON market_snapshots(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_security ON market_snapshots(security_id);

-- =============================================================================
-- SIGNALS (Nervous System - v2.0.0)
-- =============================================================================

CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('CRITICAL','WARNING','INFO','OBSERVE')),
    domain VARCHAR(12) NOT NULL CHECK (domain IN ('HEALTH','TRADING','RISK','LEARNING','DIRECTION','LIFECYCLE')),
    scope VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    acknowledged_by JSONB DEFAULT '[]'::jsonb,
    response_required BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_signals_active ON signals(resolved, expires_at);
CREATE INDEX IF NOT EXISTS idx_signals_severity ON signals(severity);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities
    WHERE symbol = UPPER(p_symbol);

    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange_id)
        SELECT UPPER(p_symbol), exchange_id
        FROM exchanges
        WHERE exchange_code = 'HKEX'
        RETURNING security_id INTO v_security_id;
    END IF;

    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_or_create_time(p_timestamp TIMESTAMPTZ)
RETURNS INTEGER AS $$
DECLARE
    v_time_id INTEGER;
    v_is_market_hours BOOLEAN;
    v_session VARCHAR(20);
    v_hour INTEGER;
    v_minute INTEGER;
BEGIN
    SELECT time_id INTO v_time_id
    FROM time_dimension
    WHERE full_timestamp = p_timestamp;

    IF v_time_id IS NULL THEN
        v_hour := EXTRACT(HOUR FROM p_timestamp AT TIME ZONE 'Asia/Hong_Kong');
        v_minute := EXTRACT(MINUTE FROM p_timestamp AT TIME ZONE 'Asia/Hong_Kong');

        IF v_hour >= 9 AND (v_hour < 12 OR (v_hour = 9 AND v_minute >= 30)) THEN
            v_session := 'morning';
            v_is_market_hours := TRUE;
        ELSIF v_hour = 12 THEN
            v_session := 'lunch';
            v_is_market_hours := FALSE;
        ELSIF v_hour >= 13 AND v_hour < 16 THEN
            v_session := 'afternoon';
            v_is_market_hours := TRUE;
        ELSE
            v_session := 'closed';
            v_is_market_hours := FALSE;
        END IF;

        INSERT INTO time_dimension (
            full_timestamp, date, year, quarter, month, week,
            day_of_month, day_of_week, hour, minute,
            is_market_hours, session
        )
        VALUES (
            p_timestamp,
            DATE(p_timestamp AT TIME ZONE 'Asia/Hong_Kong'),
            EXTRACT(YEAR FROM p_timestamp),
            EXTRACT(QUARTER FROM p_timestamp),
            EXTRACT(MONTH FROM p_timestamp),
            EXTRACT(WEEK FROM p_timestamp),
            EXTRACT(DAY FROM p_timestamp),
            EXTRACT(DOW FROM p_timestamp),
            v_hour,
            v_minute,
            v_is_market_hours,
            v_session
        )
        RETURNING time_id INTO v_time_id;
    END IF;

    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_current_strategy()
RETURNS JSONB AS $$
DECLARE
    v_strategy JSONB;
BEGIN
    SELECT parameters INTO v_strategy
    FROM strategy_versions
    WHERE effective_until IS NULL
    ORDER BY effective_from DESC
    LIMIT 1;

    RETURN COALESCE(v_strategy, '{}'::JSONB);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_pattern_stats(
    p_pattern_id INTEGER,
    p_pnl DECIMAL,
    p_confidence DECIMAL
)
RETURNS VOID AS $$
BEGIN
    UPDATE patterns
    SET
        times_traded = times_traded + 1,
        win_count = win_count + CASE WHEN p_pnl > 0 THEN 1 ELSE 0 END,
        loss_count = loss_count + CASE WHEN p_pnl <= 0 THEN 1 ELSE 0 END,
        total_pnl = total_pnl + p_pnl,
        avg_pnl = (total_pnl + p_pnl) / (times_traded + 1),
        win_rate = CASE
            WHEN (times_traded + 1) > 0
            THEN (win_count + CASE WHEN p_pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / (times_traded + 1) * 100
            ELSE 0
        END,
        avg_confidence_when_win = CASE
            WHEN p_pnl > 0
            THEN COALESCE((avg_confidence_when_win * win_count + p_confidence) / (win_count + 1), p_confidence)
            ELSE avg_confidence_when_win
        END,
        avg_confidence_when_loss = CASE
            WHEN p_pnl <= 0
            THEN COALESCE((avg_confidence_when_loss * loss_count + p_confidence) / (loss_count + 1), p_confidence)
            ELSE avg_confidence_when_loss
        END,
        last_traded_at = NOW(),
        updated_at = NOW()
    WHERE pattern_id = p_pattern_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION close_position_with_pnl()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'closed' AND OLD.status = 'open' AND NEW.exit_price IS NOT NULL THEN
        IF NEW.side = 'buy' THEN
            NEW.realized_pnl := (NEW.exit_price - NEW.entry_price) * NEW.quantity;
        ELSE
            NEW.realized_pnl := (NEW.entry_price - NEW.exit_price) * NEW.quantity;
        END IF;

        NEW.realized_pnl_pct := (NEW.realized_pnl / (NEW.entry_price * NEW.quantity)) * 100;
        NEW.holding_duration := NEW.exit_time - NEW.entry_time;
        NEW.updated_at := NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_position_pnl ON positions;
CREATE TRIGGER trg_position_pnl
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION close_position_with_pnl();

-- =============================================================================
-- VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW recent_decisions_with_outcomes AS
SELECT
    d.decision_id,
    d.timestamp,
    d.symbol,
    d.stimulus_type,
    d.action,
    d.confidence,
    d.reasoning,
    d.executed,
    p.realized_pnl,
    p.realized_pnl_pct,
    p.status as position_status,
    p.exit_reason,
    CASE
        WHEN p.realized_pnl > 0 THEN 'WIN'
        WHEN p.realized_pnl < 0 THEN 'LOSS'
        WHEN p.status = 'open' THEN 'OPEN'
        ELSE 'N/A'
    END as outcome
FROM decisions d
LEFT JOIN positions p ON d.position_id = p.position_id
ORDER BY d.timestamp DESC;

CREATE OR REPLACE VIEW pattern_performance AS
SELECT
    pattern_id,
    name,
    pattern_type,
    times_traded,
    win_count,
    loss_count,
    ROUND(win_rate, 1) as win_rate_pct,
    ROUND(total_pnl, 2) as total_pnl,
    ROUND(avg_pnl, 2) as avg_pnl,
    ROUND(avg_confidence_when_win, 1) as avg_conf_win,
    ROUND(avg_confidence_when_loss, 1) as avg_conf_loss,
    active,
    last_traded_at
FROM patterns
WHERE times_traded > 0
ORDER BY win_rate DESC, total_pnl DESC;

CREATE OR REPLACE VIEW daily_performance AS
SELECT
    DATE(entry_time AT TIME ZONE 'Asia/Hong_Kong') as trade_date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
    ROUND(SUM(realized_pnl)::DECIMAL, 2) as total_pnl,
    ROUND(AVG(realized_pnl)::DECIMAL, 2) as avg_pnl,
    ROUND(AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END)::DECIMAL, 2) as avg_win,
    ROUND(AVG(CASE WHEN realized_pnl < 0 THEN realized_pnl END)::DECIMAL, 2) as avg_loss
FROM positions
WHERE status = 'closed'
GROUP BY DATE(entry_time AT TIME ZONE 'Asia/Hong_Kong')
ORDER BY trade_date DESC;

CREATE OR REPLACE VIEW strategy_history AS
SELECT
    strategy_id,
    version_number,
    parameters,
    rationale,
    changed_by,
    effective_from,
    effective_until,
    CASE
        WHEN effective_until IS NULL THEN 'ACTIVE'
        ELSE 'EXPIRED'
    END as status,
    performance_metrics
FROM strategy_versions
ORDER BY effective_from DESC;
