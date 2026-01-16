-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: doctor-claude-schema.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Database schema for Doctor Claude monitoring system
-- ============================================================================
--
-- USAGE:
--   psql $DATABASE_URL < doctor-claude-schema.sql
--
-- CREATES:
--   Tables:
--     - claude_activity_log: Audit trail of all Claude Code activities
--     - doctor_claude_rules: Configurable auto-fix rules
--
--   Views:
--     - v_trade_pipeline_status: Real-time pipeline status for watchdog
--     - v_claude_activity_summary: Daily activity summary
--     - v_recurring_issues: Issue frequency for learning
--     - v_recent_escalations: Issues needing human review
--     - v_failed_actions: Failed actions for investigation
--
-- ============================================================================

-- ============================================================================
-- TABLE: claude_activity_log
-- Stores all Claude Code (Doctor Claude) observations, decisions, and actions
-- ============================================================================

CREATE TABLE IF NOT EXISTS claude_activity_log (
    log_id              BIGSERIAL PRIMARY KEY,
    logged_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Session context
    session_id          VARCHAR(100),           -- Claude session identifier
    cycle_id            UUID,                   -- Trading cycle if applicable

    -- Observation (what was seen)
    observation_type    VARCHAR(50) NOT NULL,   -- watchdog_run, manual_check, startup, shutdown
    observation_summary JSONB,                  -- Full observation details as JSON
    issues_found        INTEGER DEFAULT 0,      -- Total issues detected
    critical_count      INTEGER DEFAULT 0,      -- Critical severity issues
    warning_count       INTEGER DEFAULT 0,      -- Warning severity issues

    -- Decision (what was decided)
    decision            VARCHAR(50),            -- auto_fix, escalate, monitor, no_action, defer
    decision_reasoning  TEXT,                   -- Why this decision was made

    -- Action (what was done)
    action_type         VARCHAR(50),            -- sql_update, api_call, alert_sent, none
    action_detail       TEXT,                   -- The actual command/query
    action_target       VARCHAR(100),           -- Table/service acted upon
    action_result       VARCHAR(50),            -- success, failed, partial, pending, skipped
    error_message       TEXT,                   -- Error details if failed

    -- Issue classification
    issue_type          VARCHAR(100),           -- Issue taxonomy (ORDER_STATUS_MISMATCH, etc.)
    issue_severity      VARCHAR(20),            -- CRITICAL, WARNING, INFO

    -- Timing
    fix_duration_ms     INTEGER,                -- How long the fix took
    watchdog_duration_ms INTEGER,               -- How long the diagnostic took

    -- Extensibility
    metadata            JSONB                   -- Additional context
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_claude_activity_logged_at
    ON claude_activity_log(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_activity_session
    ON claude_activity_log(session_id);
CREATE INDEX IF NOT EXISTS idx_claude_activity_decision
    ON claude_activity_log(decision);
CREATE INDEX IF NOT EXISTS idx_claude_activity_issue_type
    ON claude_activity_log(issue_type);
CREATE INDEX IF NOT EXISTS idx_claude_activity_action_result
    ON claude_activity_log(action_result);

-- ============================================================================
-- TABLE: doctor_claude_rules
-- Configurable rules for auto-fix behavior
-- ============================================================================

CREATE TABLE IF NOT EXISTS doctor_claude_rules (
    rule_id             SERIAL PRIMARY KEY,
    issue_type          VARCHAR(100) NOT NULL UNIQUE,

    -- Auto-fix settings
    auto_fix_enabled    BOOLEAN NOT NULL DEFAULT false,
    fix_sql_template    TEXT,                   -- SQL template for fix (use {placeholders})

    -- Rate limiting
    max_auto_fixes_per_hour INTEGER DEFAULT 10,
    cooldown_minutes    INTEGER DEFAULT 5,      -- Minutes between fixes for same issue

    -- Escalation
    escalation_priority VARCHAR(20) DEFAULT 'NORMAL', -- CRITICAL, HIGH, NORMAL, LOW
    escalation_email    BOOLEAN DEFAULT true,

    -- Metadata
    description         TEXT,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- DEFAULT RULES
-- ============================================================================

INSERT INTO doctor_claude_rules (issue_type, auto_fix_enabled, description, escalation_priority) VALUES
    ('ORDER_STATUS_MISMATCH', true, 'DB order status differs from Alpaca - safe to sync', 'NORMAL'),
    ('PHANTOM_POSITION', true, 'Position in DB not in Alpaca - mark as closed', 'NORMAL'),
    ('ORPHAN_POSITION', false, 'Position in Alpaca not in DB - REAL MONEY, needs human', 'CRITICAL'),
    ('QTY_MISMATCH', false, 'Quantity mismatch between DB and Alpaca', 'HIGH'),
    ('STUCK_ORDER', false, 'Order pending too long - may be market conditions', 'NORMAL'),
    ('CYCLE_STALE', false, 'No cycle activity - may be expected', 'LOW'),
    ('ORDER_NOT_FOUND', true, 'Order not found in Alpaca - mark as expired', 'NORMAL'),
    ('STALE_POSITION_DATA', false, 'P&L data not updated recently - informational', 'LOW'),
    ('ALPACA_CONNECTION_ERROR', false, 'Could not connect to Alpaca API', 'HIGH'),
    ('ALPACA_API_ERROR', false, 'Alpaca API error during operation', 'CRITICAL')
ON CONFLICT (issue_type) DO NOTHING;

-- ============================================================================
-- VIEW: v_trade_pipeline_status
-- Real-time snapshot of trading pipeline for watchdog
-- ============================================================================

CREATE OR REPLACE VIEW v_trade_pipeline_status AS
SELECT
    tc.cycle_id,
    tc.started_at::date AS date,
    tc.mode,
    tc.status AS cycle_state,
    tc.started_at,
    tc.stopped_at,

    -- Last activity timestamp
    GREATEST(
        tc.started_at,
        tc.stopped_at,
        (SELECT MAX(created_at) FROM positions WHERE cycle_id = tc.cycle_id)
    ) AS last_activity,

    -- Minutes since last activity
    EXTRACT(EPOCH FROM (NOW() - GREATEST(
        tc.started_at,
        tc.stopped_at,
        (SELECT MAX(created_at) FROM positions WHERE cycle_id = tc.cycle_id)
    ))) / 60 AS minutes_since_activity,

    -- Pipeline stage determination
    CASE
        WHEN tc.status = 'completed' THEN 'COMPLETED'
        WHEN tc.status = 'failed' THEN 'FAILED'
        WHEN EXISTS (SELECT 1 FROM positions WHERE cycle_id = tc.cycle_id AND status = 'open') THEN 'MONITORING'
        WHEN EXISTS (SELECT 1 FROM positions WHERE cycle_id = tc.cycle_id
                     AND alpaca_status IN ('submitted', 'pending_new', 'accepted', 'new')) THEN 'EXECUTING'
        WHEN EXISTS (SELECT 1 FROM scan_results WHERE cycle_id = tc.cycle_id) THEN 'EVALUATED'
        WHEN tc.started_at IS NOT NULL THEN 'SCANNING'
        ELSE 'IDLE'
    END AS pipeline_stage,

    -- Counts
    (SELECT COUNT(*) FROM scan_results WHERE cycle_id = tc.cycle_id) AS candidates_found,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id) AS positions_total,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'open') AS positions_open,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'closed') AS positions_closed,

    -- Order counts (using positions table with alpaca_status)
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND alpaca_order_id IS NOT NULL) AS orders_total,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id
     AND alpaca_status IN ('submitted', 'pending_new', 'accepted', 'new')) AS orders_pending,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND alpaca_status = 'filled') AS orders_filled,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND alpaca_status = 'cancelled') AS orders_cancelled,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND alpaca_status IN ('rejected', 'error')) AS orders_rejected,

    -- P&L
    COALESCE((SELECT SUM(realized_pnl) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'closed'), 0) AS realized_pnl,
    COALESCE((SELECT SUM(unrealized_pnl) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'open'), 0) AS unrealized_pnl,
    COALESCE((SELECT SUM(COALESCE(realized_pnl, 0) + COALESCE(unrealized_pnl, 0)) FROM positions WHERE cycle_id = tc.cycle_id), 0) AS daily_pnl,

    -- Trades
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'closed') AS trades_executed,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'closed' AND realized_pnl > 0) AS trades_won,
    (SELECT COUNT(*) FROM positions WHERE cycle_id = tc.cycle_id AND status = 'closed' AND realized_pnl < 0) AS trades_lost

FROM trading_cycles tc
WHERE tc.started_at::date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY tc.started_at DESC;

-- ============================================================================
-- VIEW: v_claude_activity_summary
-- Daily summary of Claude Code activities
-- ============================================================================

CREATE OR REPLACE VIEW v_claude_activity_summary AS
SELECT
    DATE(logged_at) AS activity_date,
    COUNT(*) AS total_observations,
    COUNT(*) FILTER (WHERE observation_type = 'watchdog_run') AS watchdog_runs,

    -- Issue counts
    SUM(issues_found) AS total_issues_found,
    SUM(critical_count) AS total_critical,
    SUM(warning_count) AS total_warnings,

    -- Decision breakdown
    COUNT(*) FILTER (WHERE decision = 'auto_fix') AS auto_fix_decisions,
    COUNT(*) FILTER (WHERE decision = 'escalate') AS escalate_decisions,
    COUNT(*) FILTER (WHERE decision = 'no_action') AS no_action_decisions,

    -- Action results
    COUNT(*) FILTER (WHERE action_result = 'success') AS successful_actions,
    COUNT(*) FILTER (WHERE action_result = 'failed') AS failed_actions,

    -- Issue type breakdown
    COUNT(DISTINCT issue_type) AS unique_issue_types,

    -- Timing
    AVG(watchdog_duration_ms) AS avg_watchdog_ms,
    MAX(watchdog_duration_ms) AS max_watchdog_ms,

    -- Session info
    MIN(logged_at) AS first_activity,
    MAX(logged_at) AS last_activity

FROM claude_activity_log
GROUP BY DATE(logged_at)
ORDER BY activity_date DESC;

-- ============================================================================
-- VIEW: v_recurring_issues
-- Issues that keep happening - for learning and pattern detection
-- ============================================================================

CREATE OR REPLACE VIEW v_recurring_issues AS
SELECT
    issue_type,
    issue_severity,
    COUNT(*) AS occurrences,
    COUNT(*) FILTER (WHERE decision = 'auto_fix' AND action_result = 'success') AS auto_fixed,
    COUNT(*) FILTER (WHERE decision = 'escalate') AS escalated,
    COUNT(*) FILTER (WHERE action_result = 'failed') AS fix_failures,
    MIN(logged_at) AS first_seen,
    MAX(logged_at) AS last_seen,
    ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'auto_fix' AND action_result = 'success') /
          NULLIF(COUNT(*) FILTER (WHERE decision = 'auto_fix'), 0), 1) AS auto_fix_success_rate
FROM claude_activity_log
WHERE issue_type IS NOT NULL
  AND logged_at > NOW() - INTERVAL '30 days'
GROUP BY issue_type, issue_severity
ORDER BY occurrences DESC;

-- ============================================================================
-- VIEW: v_recent_escalations
-- Issues that were escalated and need human review
-- ============================================================================

CREATE OR REPLACE VIEW v_recent_escalations AS
SELECT
    log_id,
    logged_at,
    session_id,
    cycle_id,
    issue_type,
    issue_severity,
    decision_reasoning,
    observation_summary,
    metadata
FROM claude_activity_log
WHERE decision = 'escalate'
  AND logged_at > NOW() - INTERVAL '7 days'
ORDER BY logged_at DESC;

-- ============================================================================
-- VIEW: v_failed_actions
-- Actions that failed - for investigation
-- ============================================================================

CREATE OR REPLACE VIEW v_failed_actions AS
SELECT
    log_id,
    logged_at,
    session_id,
    cycle_id,
    issue_type,
    issue_severity,
    action_type,
    action_detail,
    action_target,
    error_message,
    observation_summary
FROM claude_activity_log
WHERE action_result = 'failed'
  AND logged_at > NOW() - INTERVAL '7 days'
ORDER BY logged_at DESC;

-- ============================================================================
-- FUNCTION: Check rate limit for auto-fix
-- ============================================================================

CREATE OR REPLACE FUNCTION check_auto_fix_rate_limit(p_issue_type VARCHAR(100))
RETURNS BOOLEAN AS $$
DECLARE
    v_max_per_hour INTEGER;
    v_cooldown INTEGER;
    v_recent_count INTEGER;
    v_last_fix TIMESTAMPTZ;
BEGIN
    -- Get rule settings
    SELECT max_auto_fixes_per_hour, cooldown_minutes
    INTO v_max_per_hour, v_cooldown
    FROM doctor_claude_rules
    WHERE issue_type = p_issue_type AND is_active = true;

    IF NOT FOUND THEN
        RETURN false;  -- No rule means not allowed
    END IF;

    -- Count recent fixes in last hour
    SELECT COUNT(*), MAX(logged_at)
    INTO v_recent_count, v_last_fix
    FROM claude_activity_log
    WHERE issue_type = p_issue_type
      AND decision = 'auto_fix'
      AND logged_at > NOW() - INTERVAL '1 hour';

    -- Check rate limit
    IF v_recent_count >= v_max_per_hour THEN
        RETURN false;
    END IF;

    -- Check cooldown
    IF v_last_fix IS NOT NULL AND v_last_fix > NOW() - (v_cooldown || ' minutes')::INTERVAL THEN
        RETURN false;
    END IF;

    RETURN true;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANT PERMISSIONS (if needed)
-- ============================================================================

-- These are only needed if running with a non-superuser
-- GRANT SELECT, INSERT ON claude_activity_log TO catalyst_user;
-- GRANT SELECT, UPDATE ON doctor_claude_rules TO catalyst_user;
-- GRANT USAGE, SELECT ON SEQUENCE claude_activity_log_log_id_seq TO catalyst_user;

-- ============================================================================
-- COMPLETE
-- ============================================================================

SELECT 'Doctor Claude schema installed successfully' AS status;
