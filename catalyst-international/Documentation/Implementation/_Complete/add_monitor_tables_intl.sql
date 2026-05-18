-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: add_monitor_tables_intl.sql
-- Version: 10.0.0
-- Last Updated: 2026-01-10
-- Purpose: Add position_monitor_status table to catalyst_intl production
-- ============================================================================
--
-- REVISION HISTORY:
-- v10.0.0 (2026-01-10) - Initial creation for ecosystem restructure
--   - Adds position_monitor_status table for pattern-based monitoring
--   - Adds v_monitor_health view for dashboard
--
-- USAGE:
--   psql -h <host> -U doadmin -d catalyst_intl -f add_monitor_tables_intl.sql
--
-- NOTE: This script is safe to run multiple times (uses IF NOT EXISTS)
-- ============================================================================

-- ============================================================================
-- STEP 1: POSITION_MONITOR_STATUS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    
    -- References
    position_id INTEGER REFERENCES positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Monitor State
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Values: 'pending', 'starting', 'running', 'sleeping', 'stopped', 'error'
    pid INTEGER,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    last_check_at TIMESTAMP WITH TIME ZONE,
    next_check_at TIMESTAMP WITH TIME ZONE,
    checks_completed INTEGER DEFAULT 0,
    
    -- Current Market State
    last_price DECIMAL(12,4),
    high_watermark DECIMAL(12,4),
    current_pnl_pct DECIMAL(8,4),
    
    -- Technical Analysis
    last_rsi DECIMAL(5,2),
    last_macd_signal VARCHAR(20),
    -- Values: 'bullish', 'bearish', 'neutral'
    last_vwap_position VARCHAR(20),
    -- Values: 'above', 'below', 'at'
    last_ema20_position VARCHAR(20),
    -- Values: 'above', 'below', 'at'
    
    -- Signal State
    hold_signals TEXT[],
    exit_signals TEXT[],
    signal_strength VARCHAR(20),
    -- Values: 'strong_hold', 'hold', 'review', 'exit', 'strong_exit'
    recommendation VARCHAR(10),
    -- Values: 'HOLD', 'EXIT', 'REVIEW'
    recommendation_reason TEXT,
    
    -- AI Consultation Tracking
    haiku_calls INTEGER DEFAULT 0,
    last_haiku_recommendation TEXT,
    estimated_cost DECIMAL(8,4) DEFAULT 0,
    
    -- Error Tracking
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    consecutive_errors INTEGER DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- STEP 2: INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_monitor_position ON position_monitor_status(position_id);
CREATE INDEX IF NOT EXISTS idx_monitor_symbol ON position_monitor_status(symbol);
CREATE INDEX IF NOT EXISTS idx_monitor_status ON position_monitor_status(status);
CREATE INDEX IF NOT EXISTS idx_monitor_active ON position_monitor_status(status) 
    WHERE status IN ('running', 'starting');

-- ============================================================================
-- STEP 3: TRIGGER FOR UPDATED_AT
-- ============================================================================
CREATE OR REPLACE FUNCTION update_monitor_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_monitor_updated ON position_monitor_status;
CREATE TRIGGER trg_monitor_updated
    BEFORE UPDATE ON position_monitor_status
    FOR EACH ROW EXECUTE FUNCTION update_monitor_timestamp();

-- ============================================================================
-- STEP 4: MONITOR HEALTH VIEW
-- ============================================================================
CREATE OR REPLACE VIEW v_monitor_health AS
SELECT 
    p.position_id,
    p.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.stop_loss,
    p.take_profit,
    p.status AS position_status,
    p.entry_time,
    p.unrealized_pnl,
    
    -- Monitor Status
    COALESCE(m.status, 'NO_MONITOR') AS monitor_status,
    m.started_at AS monitor_started,
    m.last_check_at,
    m.next_check_at,
    m.checks_completed,
    m.pid AS monitor_pid,
    
    -- Time Calculations
    ROUND(EXTRACT(EPOCH FROM (NOW() - m.last_check_at))/60, 1) AS minutes_since_check,
    ROUND(EXTRACT(EPOCH FROM (NOW() - p.entry_time))/3600, 1) AS hours_held,
    
    -- Technical State
    m.last_price,
    m.high_watermark,
    m.current_pnl_pct,
    m.last_rsi,
    m.last_macd_signal,
    m.last_vwap_position,
    
    -- Signals
    m.recommendation,
    m.recommendation_reason,
    m.hold_signals,
    m.exit_signals,
    m.signal_strength,
    
    -- Cost Tracking
    m.haiku_calls,
    m.estimated_cost,
    
    -- Errors
    m.last_error,
    m.error_count,
    m.consecutive_errors,
    
    -- Health Indicator
    CASE 
        WHEN m.status IS NULL THEN '🔴 NO_MONITOR'
        WHEN m.status = 'error' THEN '🔴 ERROR'
        WHEN m.consecutive_errors >= 3 THEN '🔴 FAILING'
        WHEN m.last_check_at < NOW() - INTERVAL '15 minutes' THEN '🟡 STALE'
        WHEN m.status = 'running' THEN '🟢 ACTIVE'
        WHEN m.status = 'sleeping' THEN '🔵 SLEEPING'
        WHEN m.status = 'starting' THEN '🟡 STARTING'
        ELSE '⚪ UNKNOWN'
    END AS health,
    
    -- Priority for sorting (issues first)
    CASE 
        WHEN m.status IS NULL THEN 0
        WHEN m.status = 'error' THEN 1
        WHEN m.consecutive_errors >= 3 THEN 2
        WHEN m.last_check_at < NOW() - INTERVAL '15 minutes' THEN 3
        ELSE 10
    END AS priority
    
FROM positions p
LEFT JOIN position_monitor_status m ON m.position_id = p.position_id
WHERE p.status = 'open'
ORDER BY priority, p.entry_time;

-- ============================================================================
-- STEP 5: TABLE COMMENTS
-- ============================================================================
COMMENT ON TABLE position_monitor_status IS 'Tracks position monitor processes and their health';
COMMENT ON COLUMN position_monitor_status.high_watermark IS 'Highest price since entry for trailing stop calculation';
COMMENT ON COLUMN position_monitor_status.hold_signals IS 'Array of active HOLD signals from signals.py';
COMMENT ON COLUMN position_monitor_status.exit_signals IS 'Array of active EXIT signals from signals.py';
COMMENT ON VIEW v_monitor_health IS 'Dashboard view showing monitor health for all open positions';

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'Monitor tables added to catalyst_intl successfully!' AS status;

-- Show current open positions and their monitor status
SELECT 
    p.symbol,
    p.status AS position_status,
    COALESCE(m.status, 'NO_MONITOR') AS monitor_status
FROM positions p
LEFT JOIN position_monitor_status m ON m.position_id = p.position_id
WHERE p.status = 'open';
