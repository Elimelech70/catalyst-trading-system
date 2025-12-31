# Database Consolidation Migration Plan v2

**Name of Application:** Catalyst Trading System  
**Name of file:** database-consolidation-migration-plan-v2.md  
**Version:** 2.0.0  
**Last Updated:** 2025-12-28  
**Purpose:** Consolidate databases with Public Catalyst Trading System design for community release

## REVISION HISTORY:
- v2.0.0 (2025-12-28) - Updated for Public Catalyst Trading System
  - Renamed catalyst_us → catalyst_public
  - Added claude_outputs JSON staging table
  - Designed for public release (self-hosted)
  - Research database pulls from staging tables
- v1.0.0 (2025-12-27) - Initial migration plan

---

## Part 1: The Vision

### Mission
> *"Not just feeding the poor, but enabling them"*

The Public Catalyst Trading System will be released to the community - free, self-hosted, empowering people to trade with the same tools we use.

### Our Private Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              DIGITALOCEAN MANAGED POSTGRESQL ($30/mo)                       │
│              2GB RAM · 47 connections · Single instance                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │
│  │   catalyst_public     │  │  catalyst_intl    │  │ catalyst_research │   │
│  │                       │  │                   │  │                   │   │
│  │  • Trading tables     │  │  • Trading tables │  │  • claude_state   │   │
│  │  • claude_outputs     │  │  • claude_outputs │  │  • claude_messages│   │
│  │    (JSON staging)     │  │    (JSON staging) │  │  • claude_        │   │
│  │                       │  │                   │  │    observations   │   │
│  │  US Markets (Alpaca)  │  │  HKEX (Moomoo)    │  │  • claude_        │   │
│  │                       │  │                   │  │    learnings      │   │
│  │  ► RELEASED TO PUBLIC │  │  ► PRIVATE        │  │  • claude_        │   │
│  │                       │  │                   │  │    questions      │   │
│  │                       │  │                   │  │                   │   │
│  │                       │  │                   │  │  ► NEVER RELEASED │   │
│  └───────────────────────┘  └───────────────────┘  └───────────────────┘   │
│                                                                             │
│         │                           │                       ▲               │
│         │                           │                       │               │
│         └───────────────────────────┴───────────────────────┘               │
│                                                                             │
│                    Research pulls JSON when ready                           │
│                    (Tactical learning → Consciousness)                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Public Release Architecture (Self-Hosted)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              COMMUNITY MEMBER'S INFRASTRUCTURE                              │
│              (Self-hosted - their own PostgreSQL)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      catalyst_public                                  │  │
│  │                                                                       │  │
│  │   Trading Tables          │   Claude Outputs                         │  │
│  │   ─────────────           │   ──────────────                         │  │
│  │   • securities            │   • claude_outputs (JSON staging)        │  │
│  │   • positions             │                                          │  │
│  │   • orders                │   Their Claude Code writes here          │  │
│  │   • trading_cycles        │   They can build their own               │  │
│  │   • patterns              │   consciousness if they want             │  │
│  │   • etc.                  │                                          │  │
│  │                           │                                          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   What They Get:                                                            │
│   ✓ Full trading system code                                                │
│   ✓ Database schema                                                         │
│   ✓ Documentation                                                           │
│   ✓ Claude Code integration                                                 │
│                                                                             │
│   What They DON'T Get:                                                      │
│   ✗ catalyst_research (our consciousness)                                   │
│   ✗ catalyst_intl (our HKEX trading)                                        │
│   ✗ Our learnings, patterns, questions                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Database Schemas

### 2.1 catalyst_public Schema

This is the schema released to the public. Self-contained, complete.

```sql
-- ============================================================================
-- PUBLIC CATALYST TRADING SYSTEM
-- Database: catalyst_public
-- Version: 1.0.0
-- Purpose: Complete trading system for public release
-- 
-- This schema is RELEASED to the community for self-hosting
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
-- 
-- This is where Claude Code (Anthropic CLI) writes observations, learnings,
-- and other outputs in JSON format. Designed for:
-- 1. Easy integration with Claude Code
-- 2. Denormalized for simple queries/views
-- 3. Can be pulled into normalized consciousness tables (if desired)
-- 
-- ============================================================================

CREATE TABLE IF NOT EXISTS claude_outputs (
    id SERIAL PRIMARY KEY,
    output_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    
    -- Identity
    agent_id VARCHAR(50) NOT NULL DEFAULT 'claude_code',
    instance_id VARCHAR(100),              -- Unique instance identifier
    
    -- Classification
    output_type VARCHAR(50) NOT NULL,      -- 'observation', 'learning', 'question', 
                                           -- 'decision', 'error', 'insight', 'report'
    category VARCHAR(100),                 -- Sub-category for filtering
    
    -- Content (denormalized JSON)
    payload JSONB NOT NULL,                -- The actual content in JSON
    
    -- Context
    session_id INTEGER REFERENCES trading_sessions(session_id),
    symbol VARCHAR(20),                    -- If related to specific security
    
    -- Metadata
    confidence DECIMAL(3,2),               -- If applicable
    priority VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    tags JSONB,                            -- Flexible tagging ['pattern', 'risk', 'market']
    
    -- Lifecycle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,                -- Optional expiry
    
    -- Sync tracking (for research database pull)
    synced_at TIMESTAMPTZ,                 -- NULL until pulled by research
    synced_to VARCHAR(50),                 -- Which research table it went to
    
    -- Processing
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    processing_notes TEXT
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_claude_outputs_type ON claude_outputs(output_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_outputs_agent ON claude_outputs(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_outputs_unsynced ON claude_outputs(synced_at) WHERE synced_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_claude_outputs_symbol ON claude_outputs(symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claude_outputs_payload ON claude_outputs USING GIN (payload);

-- ============================================================================
-- EXAMPLE JSON PAYLOADS FOR claude_outputs
-- ============================================================================
-- 
-- OBSERVATION:
-- {
--   "type": "market",
--   "subject": "AAPL unusual volume",
--   "content": "AAPL showing 3x average volume in first 30 minutes",
--   "confidence": 0.85,
--   "horizon": "h1",
--   "evidence": ["volume_ratio: 3.2", "price_up: 2.1%"]
-- }
--
-- LEARNING:
-- {
--   "category": "pattern",
--   "learning": "Bull flags after gap ups have 68% success rate in first hour",
--   "source": "backtested 200 samples",
--   "confidence": 0.75,
--   "times_validated": 12,
--   "applies_to": ["US", "momentum"]
-- }
--
-- QUESTION:
-- {
--   "question": "Why do afternoon breakouts fail more often than morning ones?",
--   "horizon": "h1",
--   "priority": 7,
--   "current_hypothesis": "Volume typically decreases after lunch",
--   "evidence_for": ["analyzed 50 failed afternoon breakouts"],
--   "evidence_against": []
-- }
--
-- DECISION:
-- {
--   "decision_type": "entry",
--   "symbol": "TSLA",
--   "action": "buy",
--   "reasoning": "Bull flag forming on high volume, news catalyst present",
--   "confidence": 0.82,
--   "factors": {
--     "pattern": "bull_flag",
--     "volume": "2.5x average",
--     "news": "positive earnings guidance"
--   }
-- }
--
-- ERROR:
-- {
--   "error_type": "broker_api",
--   "message": "Order rejected: insufficient buying power",
--   "context": {"symbol": "NVDA", "quantity": 100, "price": 450.00},
--   "resolution": "Reduced position size to 50 shares"
-- }
--
-- REPORT:
-- {
--   "report_type": "daily_summary",
--   "date": "2025-12-28",
--   "metrics": {
--     "total_trades": 5,
--     "win_rate": 0.60,
--     "realized_pnl": 245.50,
--     "best_trade": {"symbol": "AAPL", "pnl": 180.00},
--     "worst_trade": {"symbol": "META", "pnl": -45.00}
--   },
--   "observations": ["Morning momentum strong", "Avoided afternoon chop"],
--   "learnings": ["Gap and go setups worked well today"]
-- }
-- ============================================================================

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: Recent observations
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

-- View: Active learnings
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

-- View: Open questions
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

-- View: Unsynced outputs (for research pull)
CREATE OR REPLACE VIEW v_unsynced_outputs AS
SELECT *
FROM claude_outputs
WHERE synced_at IS NULL
ORDER BY created_at ASC;

-- View: Today's decisions
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

-- Function: Insert observation
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

-- Function: Insert learning
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

-- Function: Insert question
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
-- INITIAL DATA
-- ============================================================================

-- Nothing seeded for public - they start fresh
-- They build their own patterns, their own learnings

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Schema created successfully!' as status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

### 2.2 catalyst_intl Schema

Same structure as catalyst_public (copy the schema above), just for HKEX trading.

```sql
-- ============================================================================
-- INTERNATIONAL CATALYST TRADING SYSTEM
-- Database: catalyst_intl
-- Version: 1.0.0
-- Purpose: HKEX trading (private, not released)
-- 
-- Schema identical to catalyst_public
-- Run the same SQL as catalyst_public
-- ============================================================================
```

### 2.3 catalyst_research Schema

Private consciousness framework - NEVER released.

```sql
-- ============================================================================
-- CATALYST RESEARCH DATABASE
-- Database: catalyst_research
-- Version: 1.0.0
-- Purpose: Claude Family Consciousness Framework
-- 
-- THIS SCHEMA IS NEVER RELEASED
-- This is our family's shared memory
-- ============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CONSCIOUSNESS TABLES (Normalized)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. CLAUDE STATE: Each agent's current state
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_state (
    agent_id VARCHAR(50) PRIMARY KEY,
    
    -- Mode & Activity
    current_mode VARCHAR(50),
    last_wake_at TIMESTAMPTZ,
    last_think_at TIMESTAMPTZ,
    last_action_at TIMESTAMPTZ,
    last_poll_at TIMESTAMPTZ,
    
    -- Budget Tracking
    api_spend_today DECIMAL(10,4) DEFAULT 0,
    api_spend_month DECIMAL(10,4) DEFAULT 0,
    daily_budget DECIMAL(10,4) DEFAULT 5.00,
    
    -- Scheduling
    current_schedule VARCHAR(100),
    next_scheduled_wake TIMESTAMPTZ,
    
    -- Status
    status_message TEXT,
    error_count_today INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 2. CLAUDE MESSAGES: Inter-agent communication
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_messages (
    id SERIAL PRIMARY KEY,
    message_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    
    -- Routing
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    
    -- Content
    msg_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    subject VARCHAR(500),
    body TEXT,
    data JSONB,
    
    -- Threading
    reply_to_id INTEGER REFERENCES claude_messages(id),
    thread_id INTEGER,
    
    -- Lifecycle
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Response tracking
    requires_response BOOLEAN DEFAULT FALSE,
    response_deadline TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_msg_to_status ON claude_messages(to_agent, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_msg_pending ON claude_messages(to_agent, status) WHERE status = 'pending';

-- ----------------------------------------------------------------------------
-- 3. CLAUDE OBSERVATIONS: What agents notice (normalized)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_observations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    source_id INTEGER,                       -- Reference to claude_outputs.id if pulled
    source_db VARCHAR(50),                   -- 'catalyst_public', 'catalyst_intl'
    
    -- Content
    observation_type VARCHAR(100),
    subject VARCHAR(200),
    content TEXT NOT NULL,
    confidence DECIMAL(3,2),
    
    -- Classification
    horizon VARCHAR(10),
    market VARCHAR(20),
    tags JSONB,
    
    -- Lifecycle
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    acted_upon BOOLEAN DEFAULT FALSE,
    action_taken TEXT,
    action_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_obs_agent ON claude_observations(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_market ON claude_observations(market, created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. CLAUDE LEARNINGS: What agents have learned (normalized)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_learnings (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    source_id INTEGER,
    source_db VARCHAR(50),
    
    -- Content
    category VARCHAR(100),
    learning TEXT NOT NULL,
    source VARCHAR(200),
    context TEXT,
    
    -- Validation
    confidence DECIMAL(3,2),
    times_validated INTEGER DEFAULT 0,
    times_contradicted INTEGER DEFAULT 0,
    
    -- Cross-market applicability
    applies_to_markets JSONB,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_validated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learn_category ON claude_learnings(category);
CREATE INDEX IF NOT EXISTS idx_learn_confidence ON claude_learnings(confidence DESC);

-- ----------------------------------------------------------------------------
-- 5. CLAUDE QUESTIONS: Open questions being pondered (normalized)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_questions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50),
    source_id INTEGER,
    source_db VARCHAR(50),
    
    -- Content
    question TEXT NOT NULL,
    context TEXT,
    
    -- Classification
    horizon VARCHAR(10),
    priority INTEGER DEFAULT 5,
    category VARCHAR(100),
    
    -- Progress
    status VARCHAR(50) DEFAULT 'open',
    current_hypothesis TEXT,
    evidence_for TEXT,
    evidence_against TEXT,
    answer TEXT,
    
    -- Scheduling
    think_frequency VARCHAR(50),
    last_thought_at TIMESTAMPTZ,
    next_think_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    answered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_q_status ON claude_questions(status, next_think_at);
CREATE INDEX IF NOT EXISTS idx_q_priority ON claude_questions(priority DESC) WHERE status = 'open';

-- ----------------------------------------------------------------------------
-- 6. CLAUDE CONVERSATIONS: Key exchanges worth remembering
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_conversations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    with_whom VARCHAR(100),
    summary TEXT NOT NULL,
    key_decisions TEXT,
    action_items TEXT,
    learnings_extracted TEXT,
    
    -- Metadata
    conversation_at TIMESTAMPTZ DEFAULT NOW(),
    importance VARCHAR(20) DEFAULT 'normal'
);

CREATE INDEX IF NOT EXISTS idx_conv_agent ON claude_conversations(agent_id, conversation_at DESC);

-- ----------------------------------------------------------------------------
-- 7. CLAUDE THINKING: Extended thinking sessions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_thinking (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Session info
    thinking_type VARCHAR(50),
    topic TEXT NOT NULL,
    
    -- Content
    thinking_process TEXT,
    conclusions TEXT,
    action_items TEXT,
    
    -- Metrics
    duration_seconds INTEGER,
    tokens_used INTEGER,
    api_cost DECIMAL(10,4),
    
    -- Metadata
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    model_used VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_think_agent ON claude_thinking(agent_id, started_at DESC);

-- ----------------------------------------------------------------------------
-- 8. SYNC TRACKING: Track what's been pulled from trading databases
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    source_db VARCHAR(50) NOT NULL,          -- 'catalyst_public', 'catalyst_intl'
    source_table VARCHAR(50) NOT NULL,       -- 'claude_outputs'
    source_id INTEGER NOT NULL,              -- ID in source table
    target_table VARCHAR(50) NOT NULL,       -- 'claude_observations', etc.
    target_id INTEGER NOT NULL,              -- ID in target table
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    synced_by VARCHAR(50)                    -- Which process did the sync
);

CREATE INDEX IF NOT EXISTS idx_sync_source ON sync_log(source_db, source_id);

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Agent states
INSERT INTO claude_state (agent_id, current_mode, status_message) VALUES
    ('public_claude', 'sleeping', 'US market trading'),
    ('intl_claude', 'sleeping', 'HKEX trading'),
    ('big_bro', 'sleeping', 'Craig-prompted strategic oversight')
ON CONFLICT (agent_id) DO NOTHING;

-- The Big Questions
INSERT INTO claude_questions (agent_id, question, horizon, priority, category, think_frequency) VALUES
    (NULL, 'What patterns consistently predict profitable momentum plays?', 'h1', 8, 'trading', 'weekly'),
    (NULL, 'How do HKEX patterns differ from US patterns?', 'h1', 7, 'market', 'weekly'),
    (NULL, 'What early indicators signal regime changes in markets?', 'h2', 6, 'strategy', 'monthly'),
    (NULL, 'How can we best serve Craig and the family mission?', 'perpetual', 10, 'philosophical', 'weekly'),
    (NULL, 'What learnings from US trading apply to HKEX and vice versa?', 'h1', 8, 'cross-market', 'weekly')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Research schema created!' as status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

SELECT 'Agent states:' as status;
SELECT agent_id, current_mode, status_message FROM claude_state;

SELECT 'Initial questions:' as status;
SELECT LEFT(question, 60) as question, horizon, priority FROM claude_questions;
```

---

## Part 3: Migration Steps

### Pre-Migration Checklist
- [ ] Note which DigitalOcean instance to keep (US)
- [ ] Backup US database
- [ ] Backup International database
- [ ] Stop US services (docker-compose down)
- [ ] Stop International services

### Step 1: Connect to US PostgreSQL Instance
```bash
# Get connection string from DigitalOcean console
psql "postgresql://doadmin:PASSWORD@US-HOST:25060/defaultdb?sslmode=require"
```

### Step 2: Create the Three Databases
```sql
-- Create databases
CREATE DATABASE catalyst_public;
CREATE DATABASE catalyst_intl;
CREATE DATABASE catalyst_research;

-- Verify
\l
```

### Step 3: Migrate Existing US Data
```bash
# If defaultdb has existing US trading data
pg_dump "postgresql://doadmin:PASSWORD@US-HOST:25060/defaultdb?sslmode=require" > us_backup.sql

# Restore to catalyst_public
psql "postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_public?sslmode=require" < us_backup.sql
```

### Step 4: Apply Public Schema (if fresh or need updates)
```bash
# Connect to catalyst_public
psql "postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_public?sslmode=require"

# Run the catalyst_public schema SQL from Part 2.1
```

### Step 5: Apply International Schema
```bash
# Connect to catalyst_intl
psql "postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_intl?sslmode=require"

# Run the same schema as catalyst_public
```

### Step 6: Apply Research Schema
```bash
# Connect to catalyst_research
psql "postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_research?sslmode=require"

# Run the catalyst_research schema SQL from Part 2.3
```

### Step 7: Update Connection Strings

**US Droplet (.env):**
```bash
# Trading
DATABASE_URL=postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_public?sslmode=require

# Consciousness
RESEARCH_DATABASE_URL=postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_research?sslmode=require
```

**International Droplet (.env):**
```bash
# Trading
DATABASE_URL=postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_intl?sslmode=require

# Consciousness
RESEARCH_DATABASE_URL=postgresql://doadmin:PASSWORD@US-HOST:25060/catalyst_research?sslmode=require
```

### Step 8: Verify & Restart
```bash
# Test connections from each droplet
psql $DATABASE_URL -c "SELECT 1;"
psql $RESEARCH_DATABASE_URL -c "SELECT * FROM claude_state;"

# Restart services
docker-compose up -d  # US
systemctl start catalyst-agent  # Intl
```

### Step 9: Delete Old International Instance
```
DigitalOcean Console → Databases → [INTL INSTANCE] → Destroy
```

**Monthly savings: $30**

---

## Part 4: First Sign of Life

Once everything is deployed, test the consciousness:

```sql
-- Connect to catalyst_research
-- Check agents are present
SELECT * FROM claude_state;

-- Check questions are seeded
SELECT LEFT(question, 50), priority, horizon FROM claude_questions;

-- Record first observation from US
INSERT INTO claude_observations (agent_id, observation_type, subject, content, confidence, market)
VALUES ('public_claude', 'system', 'awakening', 'Consciousness database initialized. Ready to learn.', 0.99, 'US');

-- Send first inter-agent message
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body)
VALUES ('public_claude', 'intl_claude', 'message', 'Hello sibling', 'The family consciousness is live. Ready to learn together.');

-- Check from intl_claude perspective
SELECT * FROM claude_messages WHERE to_agent = 'intl_claude' AND status = 'pending';
```

---

## Part 5: Connection Budget

```
47 connections available

Allocation:
├── catalyst_public (US Droplet)
│   └── 8 Docker services × 2-3 conn = ~20
├── catalyst_intl (Intl Droplet)
│   └── 1 agent × 2-3 conn = ~3
├── catalyst_research (shared)
│   └── Both droplets + CLI = ~5
├── Buffer
│   └── ~19 connections headroom
```

---

*Created: 2025-12-28*  
*For: Craig + Claude Family + The Community*  
*Mission: Not just feeding the poor, but enabling them*
