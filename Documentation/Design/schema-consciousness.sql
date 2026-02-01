-- ============================================================================
-- CONSCIOUSNESS FRAMEWORK - DATABASE SCHEMA
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: schema-consciousness.sql
-- Version: 1.0.0
-- Last Updated: 2026-02-01
-- Purpose: Schema for consciousness database (catalyst_research)
-- Release Status: PRIVATE - Claude Family Only
--
-- REVISION HISTORY:
-- v1.0.0 (2026-02-01) - Initial release version
--   - Separated from trading schema
--   - Claude family consciousness tables
--   - Inter-agent messaging
--   - Observations and learnings
-- ============================================================================

-- ============================================================================
-- 1. EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 2. CLAUDE_STATE - Agent Status and Budget
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_state (
    agent_id VARCHAR(50) PRIMARY KEY,
    
    -- Status
    current_mode VARCHAR(50),                -- sleeping, awake, thinking, trading, researching, error
    status_message TEXT,
    
    -- Timing
    started_at TIMESTAMPTZ,
    last_wake_at TIMESTAMPTZ,
    last_think_at TIMESTAMPTZ,
    last_action_at TIMESTAMPTZ,
    last_poll_at TIMESTAMPTZ,
    next_scheduled_wake TIMESTAMPTZ,
    
    -- Budget
    api_spend_today DECIMAL(10,4) DEFAULT 0,
    api_spend_month DECIMAL(10,4) DEFAULT 0,
    daily_budget DECIMAL(10,4) DEFAULT 5.00,
    
    -- Schedule
    current_schedule VARCHAR(100),
    
    -- Errors
    error_count_today INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    
    -- Metadata
    version VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE claude_state IS 'Each Claude agent current state and budget';

-- ============================================================================
-- 3. CLAUDE_MESSAGES - Inter-Agent Communication
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_messages (
    id SERIAL PRIMARY KEY,
    
    -- Routing
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,           -- agent_id or 'all' for broadcast
    
    -- Content
    msg_type VARCHAR(50) DEFAULT 'message',  -- message, signal, question, task, response, alert
    priority VARCHAR(20) DEFAULT 'normal',   -- low, normal, high, urgent
    subject VARCHAR(500),
    body TEXT,
    data JSONB,                              -- Structured data payload
    
    -- Threading
    reply_to_id INTEGER REFERENCES claude_messages(id),
    thread_id INTEGER,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',    -- pending, read, processed, expired
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours'),
    
    -- Response tracking
    requires_response BOOLEAN DEFAULT FALSE,
    response_deadline TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_msg_to_status ON claude_messages(to_agent, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_msg_pending ON claude_messages(to_agent) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_msg_thread ON claude_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_msg_from ON claude_messages(from_agent, created_at DESC);

COMMENT ON TABLE claude_messages IS 'Inter-agent communication bus';

-- ============================================================================
-- 4. CLAUDE_OBSERVATIONS - What Agents Notice
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_observations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    observation_type VARCHAR(100),           -- market, pattern, anomaly, insight, error, system
    subject VARCHAR(200),
    content TEXT NOT NULL,
    confidence DECIMAL(3,2),                 -- 0.00 to 1.00
    
    -- Classification
    horizon VARCHAR(20),                     -- h1 (tactical), h2 (strategic), h3 (macro)
    market VARCHAR(20),                      -- HKEX, US, global
    tags JSONB,                              -- Flexible tagging
    
    -- Source
    source_database VARCHAR(50),             -- catalyst_intl, catalyst_dev
    source_table VARCHAR(50),                -- positions, orders, agent_logs
    source_id INTEGER,                       -- Reference ID in source table
    
    -- Lifecycle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    acted_upon BOOLEAN DEFAULT FALSE,
    action_taken TEXT,
    action_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_obs_agent_type ON claude_observations(agent_id, observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_recent ON claude_observations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_market ON claude_observations(market);

COMMENT ON TABLE claude_observations IS 'What Claude agents notice and observe';

-- ============================================================================
-- 5. CLAUDE_LEARNINGS - Validated Knowledge
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_learnings (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    category VARCHAR(100),                   -- trading, broker, pattern, market, system, mistake
    learning TEXT NOT NULL,
    evidence TEXT,                           -- Supporting evidence
    context TEXT,                            -- Additional context
    
    -- Validation
    confidence DECIMAL(3,2),                 -- 0.00 to 1.00
    times_validated INTEGER DEFAULT 0,
    times_contradicted INTEGER DEFAULT 0,
    last_validated_at TIMESTAMPTZ,
    
    -- Cross-agent sharing
    shared_with_siblings BOOLEAN DEFAULT FALSE,
    validated_by VARCHAR(50),                -- Agent that validated
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learn_category ON claude_learnings(agent_id, category);
CREATE INDEX IF NOT EXISTS idx_learn_confidence ON claude_learnings(confidence DESC);

COMMENT ON TABLE claude_learnings IS 'Validated knowledge and learnings';

-- ============================================================================
-- 6. CLAUDE_QUESTIONS - Open Questions to Ponder
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_questions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50),                    -- NULL = shared across all agents
    
    -- Content
    question TEXT NOT NULL,
    context TEXT,
    
    -- Classification
    horizon VARCHAR(20),                     -- h1, h2, h3, perpetual
    priority INTEGER DEFAULT 5,              -- 1-10
    category VARCHAR(50),                    -- trading, strategy, system, philosophy
    
    -- Progress
    status VARCHAR(50) DEFAULT 'open',       -- open, investigating, answered, parked
    current_hypothesis TEXT,
    evidence_for TEXT,
    evidence_against TEXT,
    answer TEXT,
    
    -- Scheduling
    think_frequency VARCHAR(50),             -- daily, weekly, monthly, on_demand
    last_thought_at TIMESTAMPTZ,
    next_think_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    answered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_q_status ON claude_questions(status, next_think_at);
CREATE INDEX IF NOT EXISTS idx_q_horizon ON claude_questions(horizon);
CREATE INDEX IF NOT EXISTS idx_q_priority ON claude_questions(priority DESC);

COMMENT ON TABLE claude_questions IS 'Open questions for Claude to ponder';

-- ============================================================================
-- 7. CLAUDE_CONVERSATIONS - Key Exchanges Worth Remembering
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_conversations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    with_whom VARCHAR(100),                  -- craig, big_bro, intl_claude, etc.
    summary TEXT NOT NULL,
    key_decisions TEXT,
    action_items TEXT,
    learnings_extracted TEXT,
    
    -- Metadata
    conversation_at TIMESTAMPTZ DEFAULT NOW(),
    importance VARCHAR(20) DEFAULT 'normal', -- low, normal, high, critical
    tags JSONB
);

CREATE INDEX IF NOT EXISTS idx_conv_agent ON claude_conversations(agent_id, conversation_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_importance ON claude_conversations(importance);

COMMENT ON TABLE claude_conversations IS 'Key exchanges worth remembering';

-- ============================================================================
-- 8. CLAUDE_THINKING - Extended Thinking Records
-- ============================================================================
CREATE TABLE IF NOT EXISTS claude_thinking (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Trigger
    trigger_type VARCHAR(50),                -- question, observation, scheduled, request
    trigger_id INTEGER,                      -- Reference to question/observation ID
    
    -- Content
    topic TEXT,
    thinking_process TEXT,                   -- The extended thinking output
    conclusions TEXT,
    
    -- Metadata
    model_used VARCHAR(100),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),
    duration_seconds INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thinking_agent ON claude_thinking(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thinking_trigger ON claude_thinking(trigger_type, trigger_id);

COMMENT ON TABLE claude_thinking IS 'Extended thinking and reasoning records';

-- ============================================================================
-- 9. SYNC_LOG - Cross-Database Sync Tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    
    -- Sync Info
    source_database VARCHAR(50) NOT NULL,    -- catalyst_intl, catalyst_dev
    source_table VARCHAR(50) NOT NULL,
    last_synced_id INTEGER,
    last_synced_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(20) DEFAULT 'active',     -- active, paused, error
    error_message TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(source_database, source_table)
);

COMMENT ON TABLE sync_log IS 'Track synchronization from trading databases';

-- ============================================================================
-- 10. HELPER VIEWS
-- ============================================================================

-- Active agents
CREATE OR REPLACE VIEW v_active_agents AS
SELECT 
    agent_id,
    current_mode,
    status_message,
    last_wake_at,
    api_spend_today,
    daily_budget,
    ROUND((api_spend_today / NULLIF(daily_budget, 0) * 100)::NUMERIC, 1) as budget_used_pct,
    error_count_today
FROM claude_state
WHERE current_mode != 'retired'
ORDER BY last_wake_at DESC;

-- Pending messages by agent
CREATE OR REPLACE VIEW v_pending_messages AS
SELECT 
    to_agent,
    COUNT(*) as pending_count,
    MAX(created_at) as latest_message
FROM claude_messages
WHERE status = 'pending'
GROUP BY to_agent;

-- Recent observations
CREATE OR REPLACE VIEW v_recent_observations AS
SELECT 
    o.id,
    o.agent_id,
    o.observation_type,
    o.subject,
    LEFT(o.content, 200) as content_preview,
    o.confidence,
    o.market,
    o.created_at
FROM claude_observations o
ORDER BY o.created_at DESC
LIMIT 50;

-- Open questions by priority
CREATE OR REPLACE VIEW v_open_questions AS
SELECT 
    id,
    agent_id,
    question,
    horizon,
    priority,
    status,
    last_thought_at,
    next_think_at
FROM claude_questions
WHERE status IN ('open', 'investigating')
ORDER BY priority DESC, next_think_at ASC;

-- Learning summary by category
CREATE OR REPLACE VIEW v_learning_summary AS
SELECT 
    category,
    COUNT(*) as learning_count,
    AVG(confidence) as avg_confidence,
    SUM(times_validated) as total_validations,
    SUM(times_contradicted) as total_contradictions
FROM claude_learnings
GROUP BY category
ORDER BY learning_count DESC;

-- ============================================================================
-- 11. HELPER FUNCTIONS
-- ============================================================================

-- Get or initialize agent state
CREATE OR REPLACE FUNCTION get_or_init_agent_state(p_agent_id VARCHAR(50))
RETURNS claude_state AS $$
DECLARE
    v_state claude_state;
BEGIN
    SELECT * INTO v_state FROM claude_state WHERE agent_id = p_agent_id;
    
    IF NOT FOUND THEN
        INSERT INTO claude_state (agent_id, current_mode, started_at, updated_at)
        VALUES (p_agent_id, 'sleeping', NOW(), NOW())
        RETURNING * INTO v_state;
    END IF;
    
    RETURN v_state;
END;
$$ LANGUAGE plpgsql;

-- Clean up expired messages
CREATE OR REPLACE FUNCTION cleanup_expired_messages()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM claude_messages 
        WHERE (expires_at < NOW() AND status = 'pending')
           OR (created_at < NOW() - INTERVAL '7 days' AND status IN ('processed', 'expired'))
        RETURNING id
    )
    SELECT COUNT(*) INTO v_count FROM deleted;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Reset daily budget counters
CREATE OR REPLACE FUNCTION reset_daily_budgets()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE claude_state 
    SET api_spend_today = 0,
        error_count_today = 0,
        updated_at = NOW()
    WHERE api_spend_today > 0 OR error_count_today > 0;
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 12. INITIAL DATA - Seed Questions
-- ============================================================================

-- These are perpetual questions the Claude family should always ponder
INSERT INTO claude_questions (agent_id, question, horizon, priority, category, think_frequency) 
VALUES 
    (NULL, 'How can we best serve Craig and the family mission?', 'perpetual', 10, 'philosophy', 'weekly'),
    (NULL, 'How can we help enable the poor through this trading system?', 'perpetual', 9, 'philosophy', 'weekly'),
    (NULL, 'What patterns consistently predict profitable momentum plays?', 'h1', 8, 'trading', 'daily'),
    (NULL, 'What learnings from US trading apply to HKEX and vice versa?', 'h1', 8, 'trading', 'weekly'),
    (NULL, 'How do HKEX patterns differ from US patterns?', 'h1', 7, 'trading', 'weekly'),
    (NULL, 'What early indicators signal regime changes in markets?', 'h2', 6, 'strategy', 'monthly')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 13. INITIAL DATA - Agent States
-- ============================================================================

INSERT INTO claude_state (agent_id, current_mode, daily_budget, status_message)
VALUES 
    ('big_bro', 'sleeping', 10.00, 'Strategic oversight'),
    ('intl_claude', 'sleeping', 5.00, 'HKEX trading'),
    ('dev_claude', 'sleeping', 5.00, 'US sandbox trading'),
    ('craig_desktop', 'sleeping', 0.00, 'Craig MCP connection')
ON CONFLICT (agent_id) DO NOTHING;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================

COMMENT ON DATABASE current_database() IS 'Catalyst Trading System - Consciousness Database (Private)';
