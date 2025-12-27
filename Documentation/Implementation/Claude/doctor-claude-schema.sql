-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: doctor-claude-schema.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Database schema for Doctor Claude trade lifecycle monitoring
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-27) - Initial implementation
--   - claude_activity_log table for audit trail
--   - doctor_claude_rules table for auto-fix configuration
--   - v_trade_pipeline_status view for real-time monitoring
--   - v_claude_activity_summary view for daily summaries
--   - v_recurring_issues view for pattern learning
--
-- INSTALLATION:
--   psql $DATABASE_URL < doctor-claude-schema.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- TABLE 1: claude_activity_log
-- Purpose: Audit trail of everything Claude Code observes, decides, and does
-- ============================================================================

CREATE TABLE IF NOT EXISTS claude_activity_log (
    -- Primary Key
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Timing
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Session Context
    session_id VARCHAR(50),           -- Claude Code session identifier (date-based)
    cycle_id UUID,                    -- References trading_cycles if applicable
    
    -- What Claude Code Observed
    observation_type VARCHAR(50) NOT NULL,  
        -- 'watchdog_run'      : Regular monitoring check
        -- 'manual_check'      : Ad-hoc diagnostic
        -- 'alert_triggered'   : Responding to alert
        -- 'startup'           : Session start
        -- 'shutdown'          : Session end
    
    observation_summary JSONB,        -- Full watchdog output or relevant data
    issues_found INTEGER DEFAULT 0,   -- Count of issues detected
    critical_count INTEGER DEFAULT 0, -- Count of critical issues
    warning_count INTEGER DEFAULT 0,  -- Count of warnings
    
    -- What Claude Code Decided
    decision VARCHAR(50),
        -- 'auto_fix'          : Safe to fix automatically
        -- 'escalate'          : Needs human intervention
        -- 'monitor'           : Watch but don't act yet
        -- 'no_action'         : Everything OK
        -- 'defer'             : Will address later
    
    decision_reasoning TEXT,          -- Why this decision was made
    
    -- What Claude Code Did
    action_type VARCHAR(50),
        -- 'sql_update'        : Database modification
        -- 'sql_insert'        : Database insert
        -- 'api_call'          : External API call (Alpaca)
        -- 'alert_sent'        : Notification to Craig
        -- 'service_restart'   : Restarted a service
        -- 'none'              : No action taken
    
    action_detail TEXT,               -- The actual command/query executed
    action_target VARCHAR(100),       -- What was acted upon (table, service, etc.)
    
    -- Result
    action_result VARCHAR(20),
        -- 'success'           : Action completed successfully
        -- 'failed'            : Action failed
        -- 'partial'           : Partially successful
        -- 'pending'           : Awaiting confirmation
        -- 'skipped'           : Action skipped
    
    error_message TEXT,               -- Error details if failed
    
    -- Issue Classification (for learning)
    issue_type VARCHAR(50),           -- Taxonomy: ORDER_STATUS_MISMATCH, PHANTOM_POSITION, etc.
    issue_severity VARCHAR(20),       -- CRITICAL, WARNING, INFO
    
    -- Performance Metrics
    fix_duration_ms INTEGER,          -- How long the fix took
    watchdog_duration_ms INTEGER,     -- How long the diagnostic took
    
    -- Metadata
    metadata JSONB                    -- Additional context
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_cal_logged_at ON claude_activity_log(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_cal_session ON claude_activity_log(session_id);
CREATE INDEX IF NOT EXISTS idx_cal_cycle ON claude_activity_log(cycle_id) WHERE cycle_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cal_decision ON claude_activity_log(decision);
CREATE INDEX IF NOT EXISTS idx_cal_issue_type ON claude_activity_log(issue_type) WHERE issue_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cal_action_result ON claude_activity_log(action_result) WHERE action_result = 'failed';

COMMENT ON TABLE claude_activity_log IS 'Audit trail of Claude Code (Doctor Claude) monitoring activities';
COMMENT ON COLUMN claude_activity_log.session_id IS 'Date-based session ID, e.g., claude-20251227';
COMMENT ON COLUMN claude_activity_log.observation_type IS 'Type of observation: watchdog_run, manual_check, startup, shutdown';
COMMENT ON COLUMN claude_activity_log.decision IS 'Decision made: auto_fix, escalate, monitor, no_action, defer';
COMMENT ON COLUMN claude_activity_log.issue_type IS 'Issue taxonomy for learning: ORDER_STATUS_MISMATCH, PHANTOM_POSITION, etc.';


-- ============================================================================
-- TABLE 2: doctor_claude_rules
-- Purpose: Configurable rules for auto-fix vs escalate decisions
-- ============================================================================

CREATE TABLE IF NOT EXISTS doctor_claude_rules (
    rule_id SERIAL PRIMARY KEY,
    
    -- Rule Identity
    issue_type VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    
    -- Decision Configuration
    auto_fix_enabled BOOLEAN DEFAULT false,
    escalate_threshold INTEGER DEFAULT 1,     -- Escalate after N occurrences in 1 hour
    
    -- Fix Template
    fix_template TEXT,                        -- SQL or command template with placeholders
    fix_requires_confirmation BOOLEAN DEFAULT false,
    
    -- Escalation Configuration
    escalation_channel VARCHAR(50) DEFAULT 'email',  -- 'email', 'github', 'slack'
    escalation_priority VARCHAR(20) DEFAULT 'normal', -- 'critical', 'high', 'normal', 'low'
    
    -- Safety Limits
    max_auto_fixes_per_hour INTEGER DEFAULT 10,
    cooldown_minutes INTEGER DEFAULT 5,       -- Wait between auto-fixes of same type
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE doctor_claude_rules IS 'Configurable rules for Doctor Claude auto-fix decisions';
COMMENT ON COLUMN doctor_claude_rules.fix_template IS 'SQL template with placeholders like {order_id}, {alpaca_status}';
COMMENT ON COLUMN doctor_claude_rules.escalate_threshold IS 'Number of occurrences before escalating even if auto-fix enabled';

-- Insert default rules
INSERT INTO doctor_claude_rules (issue_type, description, auto_fix_enabled, fix_template, escalation_priority) VALUES
('ORDER_STATUS_MISMATCH', 'DB order status differs from Alpaca - safe to sync', true, 
 'UPDATE orders SET status = ''{alpaca_status}'', updated_at = NOW() WHERE order_id = ''{order_id}''', 
 'normal'),

('PHANTOM_POSITION', 'Position exists in DB but not in Alpaca - mark as closed', true,
 'UPDATE positions SET status = ''closed'', exit_time = NOW(), updated_at = NOW() WHERE position_id = ''{position_id}''',
 'high'),

('ORPHAN_POSITION', 'Position exists in Alpaca but not tracked in DB - requires human review', false,
 NULL,
 'critical'),

('QTY_MISMATCH', 'Position quantity differs between DB and Alpaca', false,
 'UPDATE positions SET quantity = {alpaca_qty}, updated_at = NOW() WHERE position_id = ''{position_id}''',
 'high'),

('STUCK_ORDER', 'Order has been pending longer than expected - may be market conditions', false,
 NULL,
 'normal'),

('CYCLE_STALE', 'Trading cycle has no activity for extended period', false,
 NULL,
 'normal'),

('SERVICE_UNHEALTHY', 'A trading service is not responding to health checks', false,
 NULL,
 'critical'),

('DAILY_LOSS_WARNING', 'Approaching or exceeded daily loss limit', false,
 NULL,
 'critical'),

('ALPACA_CONNECTION_ERROR', 'Cannot connect to Alpaca API', false,
 NULL,
 'critical'),

('DATABASE_CONNECTION_ERROR', 'Cannot connect to PostgreSQL database', false,
 NULL,
 'critical')
ON CONFLICT (issue_type) DO NOTHING;


-- ============================================================================
-- VIEW: v_trade_pipeline_status
-- Purpose: Single view of current trade pipeline state for Doctor Claude
-- ============================================================================

CREATE OR REPLACE VIEW v_trade_pipeline_status AS
SELECT 
    tc.cycle_id,
    tc.date,
    tc.cycle_state,
    tc.phase,
    tc.mode,
    tc.started_at,
    tc.daily_pnl,
    tc.trades_executed,
    tc.trades_won,
    tc.trades_lost,
    tc.updated_at as last_activity,
    
    -- Pipeline Stage Counts
    COALESCE(scan.candidates, 0) as candidates_found,
    COALESCE(pos.total, 0) as positions_total,
    COALESCE(pos.open_count, 0) as positions_open,
    COALESCE(pos.closed_count, 0) as positions_closed,
    COALESCE(ord.total, 0) as orders_total,
    COALESCE(ord.submitted, 0) as orders_pending,
    COALESCE(ord.filled, 0) as orders_filled,
    COALESCE(ord.cancelled, 0) as orders_cancelled,
    COALESCE(ord.rejected, 0) as orders_rejected,
    
    -- P&L Summary
    COALESCE(pos.realized_pnl, 0) as realized_pnl,
    COALESCE(pos.unrealized_pnl, 0) as unrealized_pnl,
    
    -- Health Indicators
    EXTRACT(EPOCH FROM (NOW() - tc.updated_at))/60 as minutes_since_activity,
    CASE 
        WHEN tc.cycle_state = 'closed' THEN 'COMPLETE'
        WHEN COALESCE(pos.open_count, 0) > 0 AND COALESCE(ord.submitted, 0) = 0 THEN 'MONITORING'
        WHEN COALESCE(ord.submitted, 0) > 0 THEN 'ORDERS_PENDING'
        WHEN COALESCE(scan.candidates, 0) > 0 AND COALESCE(pos.total, 0) = 0 THEN 'AWAITING_ENTRY'
        WHEN COALESCE(scan.candidates, 0) = 0 THEN 'SCANNING'
        ELSE 'ACTIVE'
    END as pipeline_stage

FROM trading_cycles tc

-- Scan results aggregation
LEFT JOIN LATERAL (
    SELECT COUNT(*) as candidates
    FROM scan_results sr
    WHERE sr.cycle_id = tc.cycle_id
) scan ON true

-- Positions aggregation
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE p.status = 'open') as open_count,
        COUNT(*) FILTER (WHERE p.status = 'closed') as closed_count,
        COALESCE(SUM(p.realized_pnl) FILTER (WHERE p.status = 'closed'), 0) as realized_pnl,
        COALESCE(SUM(p.unrealized_pnl) FILTER (WHERE p.status = 'open'), 0) as unrealized_pnl
    FROM positions p
    WHERE p.cycle_id = tc.cycle_id
) pos ON true

-- Orders aggregation
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE o.status IN ('submitted', 'pending_new', 'accepted')) as submitted,
        COUNT(*) FILTER (WHERE o.status = 'filled') as filled,
        COUNT(*) FILTER (WHERE o.status = 'cancelled') as cancelled,
        COUNT(*) FILTER (WHERE o.status = 'rejected') as rejected
    FROM orders o
    JOIN positions p ON o.position_id = p.position_id
    WHERE p.cycle_id = tc.cycle_id
) ord ON true

WHERE tc.date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY tc.date DESC, tc.started_at DESC;

COMMENT ON VIEW v_trade_pipeline_status IS 'Real-time trade pipeline status for Doctor Claude monitoring';


-- ============================================================================
-- VIEW: v_claude_activity_summary
-- Purpose: Summary of Claude Code activities for daily review
-- ============================================================================

CREATE OR REPLACE VIEW v_claude_activity_summary AS
SELECT 
    DATE(logged_at) as activity_date,
    session_id,
    COUNT(*) as total_observations,
    SUM(issues_found) as total_issues_found,
    SUM(critical_count) as total_critical,
    SUM(warning_count) as total_warnings,
    COUNT(*) FILTER (WHERE decision = 'auto_fix') as auto_fixes,
    COUNT(*) FILTER (WHERE decision = 'escalate') as escalations,
    COUNT(*) FILTER (WHERE decision = 'no_action') as no_action_count,
    COUNT(*) FILTER (WHERE action_result = 'success') as successful_actions,
    COUNT(*) FILTER (WHERE action_result = 'failed') as failed_actions,
    MIN(logged_at) as session_start,
    MAX(logged_at) as session_end,
    ROUND(EXTRACT(EPOCH FROM (MAX(logged_at) - MIN(logged_at)))/3600, 2) as session_hours
FROM claude_activity_log
GROUP BY DATE(logged_at), session_id
ORDER BY activity_date DESC, session_start DESC;

COMMENT ON VIEW v_claude_activity_summary IS 'Daily summary of Doctor Claude monitoring activities';


-- ============================================================================
-- VIEW: v_recurring_issues
-- Purpose: Identify patterns in issues for learning and improvement
-- ============================================================================

CREATE OR REPLACE VIEW v_recurring_issues AS
SELECT 
    issue_type,
    COUNT(*) as occurrences,
    COUNT(*) FILTER (WHERE action_result = 'success') as times_fixed,
    COUNT(*) FILTER (WHERE action_result = 'failed') as times_failed,
    COUNT(*) FILTER (WHERE decision = 'escalate') as times_escalated,
    COUNT(*) FILTER (WHERE decision = 'auto_fix') as times_auto_fixed,
    ROUND(AVG(fix_duration_ms)) as avg_fix_ms,
    MAX(logged_at) as last_occurrence,
    MIN(logged_at) as first_occurrence,
    ROUND(COUNT(*)::numeric / GREATEST(1, EXTRACT(DAY FROM (MAX(logged_at) - MIN(logged_at)))), 2) as avg_per_day
FROM claude_activity_log
WHERE issue_type IS NOT NULL
  AND logged_at > NOW() - INTERVAL '30 days'
GROUP BY issue_type
ORDER BY occurrences DESC;

COMMENT ON VIEW v_recurring_issues IS 'Issue frequency analysis for Doctor Claude learning and pattern recognition';


-- ============================================================================
-- VIEW: v_recent_escalations
-- Purpose: Quick view of issues that needed human intervention
-- ============================================================================

CREATE OR REPLACE VIEW v_recent_escalations AS
SELECT 
    logged_at,
    session_id,
    issue_type,
    issue_severity,
    decision_reasoning,
    observation_summary->>'message' as issue_message,
    cycle_id
FROM claude_activity_log
WHERE decision = 'escalate'
  AND logged_at > NOW() - INTERVAL '7 days'
ORDER BY logged_at DESC;

COMMENT ON VIEW v_recent_escalations IS 'Recent issues escalated to human review';


-- ============================================================================
-- VIEW: v_failed_actions
-- Purpose: Actions that failed and may need investigation
-- ============================================================================

CREATE OR REPLACE VIEW v_failed_actions AS
SELECT 
    logged_at,
    session_id,
    issue_type,
    action_type,
    action_detail,
    action_target,
    error_message,
    cycle_id
FROM claude_activity_log
WHERE action_result = 'failed'
  AND logged_at > NOW() - INTERVAL '7 days'
ORDER BY logged_at DESC;

COMMENT ON VIEW v_failed_actions IS 'Failed actions requiring investigation';


-- ============================================================================
-- FUNCTION: Get auto-fix rule for issue type
-- ============================================================================

CREATE OR REPLACE FUNCTION get_autofix_rule(p_issue_type VARCHAR)
RETURNS TABLE (
    auto_fix_enabled BOOLEAN,
    fix_template TEXT,
    max_auto_fixes_per_hour INTEGER,
    cooldown_minutes INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.auto_fix_enabled,
        r.fix_template,
        r.max_auto_fixes_per_hour,
        r.cooldown_minutes
    FROM doctor_claude_rules r
    WHERE r.issue_type = p_issue_type
      AND r.is_active = true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_autofix_rule IS 'Get auto-fix configuration for a specific issue type';


-- ============================================================================
-- FUNCTION: Check if auto-fix is allowed (rate limiting)
-- ============================================================================

CREATE OR REPLACE FUNCTION can_auto_fix(p_issue_type VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    v_rule RECORD;
    v_recent_fixes INTEGER;
    v_last_fix TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Get rule
    SELECT * INTO v_rule
    FROM doctor_claude_rules
    WHERE issue_type = p_issue_type AND is_active = true;
    
    IF NOT FOUND OR NOT v_rule.auto_fix_enabled THEN
        RETURN false;
    END IF;
    
    -- Check rate limit
    SELECT COUNT(*), MAX(logged_at) 
    INTO v_recent_fixes, v_last_fix
    FROM claude_activity_log
    WHERE issue_type = p_issue_type
      AND decision = 'auto_fix'
      AND logged_at > NOW() - INTERVAL '1 hour';
    
    IF v_recent_fixes >= v_rule.max_auto_fixes_per_hour THEN
        RETURN false;
    END IF;
    
    -- Check cooldown
    IF v_last_fix IS NOT NULL AND 
       v_last_fix > NOW() - (v_rule.cooldown_minutes || ' minutes')::INTERVAL THEN
        RETURN false;
    END IF;
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION can_auto_fix IS 'Check if auto-fix is allowed considering rate limits and cooldown';


COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after installation)
-- ============================================================================

-- Uncomment to verify installation:
-- SELECT 'claude_activity_log' as table_name, COUNT(*) as row_count FROM claude_activity_log
-- UNION ALL
-- SELECT 'doctor_claude_rules', COUNT(*) FROM doctor_claude_rules;

-- SELECT viewname FROM pg_views WHERE viewname LIKE 'v_%claude%' OR viewname LIKE 'v_trade_%';

-- SELECT * FROM doctor_claude_rules;
