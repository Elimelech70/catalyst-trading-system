-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: position_monitor_service_schema.sql
-- Version: 1.0.0
-- Last Updated: 2026-01-16
-- Purpose: Database schema updates for Position Monitor Service
--
-- Run on: catalyst_intl database
-- ============================================================================

-- ============================================================================
-- SERVICE HEALTH TABLE
-- ============================================================================
-- Tracks service health status for monitoring and alerting

CREATE TABLE IF NOT EXISTS service_health (
    service_id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'unknown',
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    last_check_count INTEGER DEFAULT 0,
    positions_monitored INTEGER DEFAULT 0,
    exits_executed INTEGER DEFAULT 0,
    haiku_calls INTEGER DEFAULT 0,
    errors_today INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_service_health_name 
ON service_health(service_name);

-- Initial record for position monitor service
INSERT INTO service_health (service_name, status, started_at)
VALUES ('position_monitor', 'stopped', NOW())
ON CONFLICT (service_name) DO NOTHING;

-- ============================================================================
-- POSITION MONITOR STATUS TABLE (if not exists)
-- ============================================================================
-- Tracks individual position monitoring status

CREATE TABLE IF NOT EXISTS position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    position_id INTEGER UNIQUE REFERENCES positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_check_at TIMESTAMP WITH TIME ZONE,
    checks_completed INTEGER DEFAULT 0,
    haiku_calls INTEGER DEFAULT 0,
    high_watermark NUMERIC(15,4),
    recommendation VARCHAR(20),
    recommendation_reason TEXT,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    pid INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_position_monitor_status_position 
ON position_monitor_status(position_id);

CREATE INDEX IF NOT EXISTS idx_position_monitor_status_symbol 
ON position_monitor_status(symbol);

CREATE INDEX IF NOT EXISTS idx_position_monitor_status_status 
ON position_monitor_status(status);

-- ============================================================================
-- MONITOR HEALTH VIEW
-- ============================================================================
-- Combined view of positions and their monitoring status

CREATE OR REPLACE VIEW v_monitor_health AS
SELECT 
    p.position_id,
    p.symbol,
    p.status AS position_status,
    p.side,
    p.quantity,
    p.entry_price,
    p.stop_loss,
    p.take_profit,
    p.created_at AS position_opened,
    EXTRACT(EPOCH FROM (NOW() - p.created_at))/3600 AS hours_held,
    m.status AS monitor_status,
    m.last_check_at,
    m.checks_completed,
    m.haiku_calls AS monitor_haiku_calls,
    m.error_count AS monitor_errors,
    EXTRACT(EPOCH FROM (NOW() - m.last_check_at))/60 AS minutes_since_check,
    CASE 
        WHEN m.last_check_at IS NULL THEN 'NO_MONITOR'
        WHEN EXTRACT(EPOCH FROM (NOW() - m.last_check_at)) > 600 THEN 'STALE'
        WHEN m.status = 'error' THEN 'ERROR'
        ELSE 'HEALTHY'
    END AS health_status
FROM positions p
LEFT JOIN position_monitor_status m ON p.position_id = m.position_id
WHERE p.status = 'open'
ORDER BY p.created_at;

-- ============================================================================
-- SERVICE HEALTH VIEW
-- ============================================================================
-- Quick view of all service statuses

CREATE OR REPLACE VIEW v_service_status AS
SELECT 
    service_name,
    status,
    last_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 AS minutes_since_heartbeat,
    last_check_count,
    positions_monitored,
    exits_executed,
    haiku_calls,
    errors_today,
    started_at,
    CASE 
        WHEN last_heartbeat IS NULL THEN 'NEVER_STARTED'
        WHEN EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) > 900 THEN 'DEAD'
        WHEN EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) > 600 THEN 'STALE'
        WHEN status = 'running' THEN 'HEALTHY'
        ELSE status
    END AS health_status
FROM service_health;

-- ============================================================================
-- HELPER FUNCTION: Update timestamp trigger
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to service_health
DROP TRIGGER IF EXISTS trg_service_health_updated ON service_health;
CREATE TRIGGER trg_service_health_updated
    BEFORE UPDATE ON service_health
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to position_monitor_status
DROP TRIGGER IF EXISTS trg_position_monitor_updated ON position_monitor_status;
CREATE TRIGGER trg_position_monitor_updated
    BEFORE UPDATE ON position_monitor_status
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check service_health table exists
SELECT 'service_health table' AS check_item, 
       COUNT(*) AS record_count 
FROM service_health;

-- Check position_monitor_status table exists  
SELECT 'position_monitor_status table' AS check_item, 
       COUNT(*) AS record_count 
FROM position_monitor_status;

-- Check views exist
SELECT 'v_monitor_health view' AS check_item,
       COUNT(*) AS open_positions
FROM v_monitor_health;

SELECT 'v_service_status view' AS check_item,
       COUNT(*) AS services
FROM v_service_status;

-- ============================================================================
-- USEFUL QUERIES FOR OPERATIONS
-- ============================================================================

-- Find positions without recent monitoring
-- SELECT * FROM v_monitor_health WHERE health_status IN ('NO_MONITOR', 'STALE');

-- Check service status
-- SELECT * FROM v_service_status WHERE service_name = 'position_monitor';

-- Get monitoring summary
-- SELECT 
--     COUNT(*) FILTER (WHERE health_status = 'HEALTHY') AS healthy,
--     COUNT(*) FILTER (WHERE health_status = 'STALE') AS stale,
--     COUNT(*) FILTER (WHERE health_status = 'NO_MONITOR') AS no_monitor,
--     COUNT(*) FILTER (WHERE health_status = 'ERROR') AS error
-- FROM v_monitor_health;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
