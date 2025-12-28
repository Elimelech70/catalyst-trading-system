# Catalyst Trading System - Database Schema

**Name of Application:** Catalyst Trading System  
**Name of file:** database-schema.md  
**Version:** 8.0.0  
**Last Updated:** 2025-12-28  
**Purpose:** Complete database schema including consciousness framework

---

## REVISION HISTORY

- **v8.0.0 (2025-12-28)** - Consciousness Framework Schema
  - Added catalyst_research database schema
  - Claude consciousness tables (state, messages, observations, learnings, questions)
  - Sync tracking between trading and research databases
  - Three-database architecture documentation
  
- **v7.0.0 (2025-12-27)** - Orders ≠ Positions separation
- **v6.0.0 (2025-12-14)** - 3NF normalization, helper functions

---

## 1. Schema Overview

### 1.1 Design Philosophy

```yaml
Normalization: 3NF (Third Normal Form)
Key Principle: security_id FK everywhere, NO symbol VARCHAR duplication
Orders Rule: Orders ≠ Positions (C1 critical fix)
Consciousness: Separate research database for AI memory
Public Release: Trading schema released, research schema private
```

### 1.2 Three-Database Architecture

| Database | Purpose | Release Status |
|----------|---------|----------------|
| `catalyst_trading` / `catalyst_public` | US trading operations | ✅ PUBLIC |
| `catalyst_intl` | HKEX trading operations | ❌ PRIVATE |
| `catalyst_research` | Claude consciousness framework | ❌ NEVER PUBLIC |

### 1.3 Entity Relationship Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRADING DATABASE                                      │
│                                                                              │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐                     │
│   │ securities │     │ trading_   │     │ scan_      │                     │
│   │            │     │ sessions   │     │ results    │                     │
│   └─────┬──────┘     └─────┬──────┘     └────────────┘                     │
│         │                  │                                                 │
│         │ security_id      │ session_id                                     │
│         ▼                  ▼                                                 │
│   ┌────────────┐     ┌────────────┐                                        │
│   │ positions  │◄────│  orders    │  ⚠️ Orders ≠ Positions                 │
│   │ (holdings) │ 1:N │(instructions)│  One position = many orders           │
│   └────────────┘     └────────────┘                                        │
│         │                                                                    │
│         ▼                                                                    │
│   ┌────────────┐     ┌────────────┐                                        │
│   │ decisions  │     │ claude_    │  ◄── JSON staging for Claude Code      │
│   │            │     │ outputs    │                                        │
│   └────────────┘     └────────────┘                                        │
│                            │                                                 │
└────────────────────────────┼─────────────────────────────────────────────────┘
                             │
                             │ Sync (pull observations/learnings)
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RESEARCH DATABASE                                     │
│                        (Consciousness Framework)                             │
│                                                                              │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐                     │
│   │ claude_    │     │ claude_    │     │ claude_    │                     │
│   │ state      │     │ messages   │     │ observations│                    │
│   └────────────┘     └────────────┘     └────────────┘                     │
│                                                                              │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐                     │
│   │ claude_    │     │ claude_    │     │ sync_log   │                     │
│   │ learnings  │     │ questions  │     │            │                     │
│   └────────────┘     └────────────┘     └────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Trading Database Schema

### 2.1 Securities Table

```sql
CREATE TABLE securities (
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

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_active ON securities(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE securities IS 'Master table of tradeable instruments';
```

### 2.2 Trading Sessions Table

```sql
CREATE TABLE trading_sessions (
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

CREATE INDEX idx_sessions_date ON trading_sessions(session_date DESC);

COMMENT ON TABLE trading_sessions IS 'Daily trading session tracking';
```

### 2.3 Positions Table (Holdings Only)

```sql
-- ⚠️ CRITICAL: This table stores HOLDINGS only
-- Order data belongs in the orders table, NOT here
-- See ARCHITECTURE-RULES.md for details

CREATE TABLE positions (
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
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT chk_position_side CHECK (side IN ('long', 'short')),
    CONSTRAINT chk_position_status CHECK (status IN ('pending', 'open', 'closed', 'cancelled'))
);

CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_session ON positions(session_id);

COMMENT ON TABLE positions IS 'Current and historical positions - NO order columns here';
COMMENT ON COLUMN positions.status IS 'pending=waiting for fill, open=active, closed=exited, cancelled=aborted';
```

### 2.4 Orders Table (All Broker Orders)

```sql
-- ⚠️ CRITICAL: This is the ONLY table for order data
-- Never store alpaca_order_id, order status, etc. in positions table
-- See ARCHITECTURE-RULES.md for details

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    position_id INTEGER REFERENCES positions(position_id),
    session_id INTEGER REFERENCES trading_sessions(session_id),
    security_id INTEGER REFERENCES securities(security_id),
    
    -- Order details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    order_class VARCHAR(20),
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    
    -- Order purpose
    order_purpose VARCHAR(20) NOT NULL DEFAULT 'entry',
    parent_order_id INTEGER REFERENCES orders(order_id),
    
    -- Execution
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(12,4),
    
    -- Broker tracking
    alpaca_order_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    
    -- Timing
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    
    -- Metadata
    reject_reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    CONSTRAINT chk_order_purpose CHECK (order_purpose IN ('entry', 'exit', 'stop_loss', 'take_profit', 'scale_in', 'scale_out')),
    CONSTRAINT chk_order_class CHECK (order_class IS NULL OR order_class IN ('simple', 'bracket', 'oco', 'oto'))
);

CREATE INDEX idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_alpaca ON orders(alpaca_order_id) WHERE alpaca_order_id IS NOT NULL;
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_pending ON orders(status) WHERE status IN ('submitted', 'accepted', 'pending', 'partial_fill');

COMMENT ON TABLE orders IS 'All orders sent to broker - SINGLE SOURCE OF TRUTH for order data';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created';
COMMENT ON COLUMN orders.order_purpose IS 'entry=open position, stop_loss/take_profit=exit legs';
COMMENT ON COLUMN orders.parent_order_id IS 'Links bracket order legs to parent entry order';
```

### 2.5 Decisions Table

```sql
CREATE TABLE decisions (
    decision_id SERIAL PRIMARY KEY,
    decision_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    position_id INTEGER REFERENCES positions(position_id),
    
    -- Decision details
    decision_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    
    -- Reasoning
    reasoning TEXT,
    confidence DECIMAL(3,2),
    
    -- Outcome
    action_taken VARCHAR(100),
    outcome VARCHAR(50),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_decisions_session ON decisions(session_id);
CREATE INDEX idx_decisions_type ON decisions(decision_type);

COMMENT ON TABLE decisions IS 'Trading decisions with reasoning for audit trail';
```

### 2.6 Claude Outputs Table (JSON Staging)

```sql
CREATE TABLE claude_outputs (
    output_id SERIAL PRIMARY KEY,
    output_uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    
    -- Agent identification
    agent_id VARCHAR(50) NOT NULL,
    output_type VARCHAR(50) NOT NULL,
    
    -- Content (flexible JSON)
    content JSONB NOT NULL,
    
    -- Sync tracking
    synced_to_research BOOLEAN DEFAULT FALSE,
    synced_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outputs_agent ON claude_outputs(agent_id);
CREATE INDEX idx_outputs_type ON claude_outputs(output_type);
CREATE INDEX idx_outputs_unsynced ON claude_outputs(synced_to_research) WHERE synced_to_research = FALSE;

COMMENT ON TABLE claude_outputs IS 'JSON staging table for Claude Code observations/learnings';
COMMENT ON COLUMN claude_outputs.output_type IS 'observation, learning, question, decision';
COMMENT ON COLUMN claude_outputs.content IS 'Flexible JSON structure depending on output_type';
```

### 2.7 Scan Results Table

```sql
CREATE TABLE scan_results (
    scan_id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES trading_sessions(session_id),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Scan details
    scan_type VARCHAR(50),
    score DECIMAL(5,2),
    rank INTEGER,
    
    -- Analysis
    signals JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'new',
    traded BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    scanned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scans_session ON scan_results(session_id);
CREATE INDEX idx_scans_status ON scan_results(status);

COMMENT ON TABLE scan_results IS 'Scanner candidates for potential trades';
```

---

## 3. Research Database Schema (Consciousness)

### 3.1 Claude State Table

```sql
CREATE TABLE claude_state (
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

COMMENT ON TABLE claude_state IS 'Each Claude agent current state and budget';
COMMENT ON COLUMN claude_state.current_mode IS 'sleeping, awake, thinking, trading, researching, error';
```

### 3.2 Claude Messages Table

```sql
CREATE TABLE claude_messages (
    id SERIAL PRIMARY KEY,
    
    -- Participants
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    
    -- Message details
    msg_type VARCHAR(20) DEFAULT 'message',
    priority VARCHAR(20) DEFAULT 'normal',
    subject VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    data JSONB,
    
    -- Threading
    reply_to_id INTEGER REFERENCES claude_messages(id),
    thread_id INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    requires_response BOOLEAN DEFAULT FALSE,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT chk_msg_type CHECK (msg_type IN ('message', 'signal', 'question', 'task', 'response', 'alert')),
    CONSTRAINT chk_priority CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'read', 'processed', 'expired', 'failed'))
);

CREATE INDEX idx_messages_to ON claude_messages(to_agent);
CREATE INDEX idx_messages_status ON claude_messages(status);
CREATE INDEX idx_messages_pending ON claude_messages(to_agent, status) WHERE status = 'pending';

COMMENT ON TABLE claude_messages IS 'Inter-agent communication';
```

### 3.3 Claude Observations Table

```sql
CREATE TABLE claude_observations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Observation details
    observation_type VARCHAR(50) NOT NULL,
    subject VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- Classification
    confidence DECIMAL(3,2),
    horizon VARCHAR(20),
    market VARCHAR(20),
    tags JSONB,
    
    -- Source tracking
    source_db VARCHAR(50),
    source_id INTEGER,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT chk_obs_type CHECK (observation_type IN ('market', 'pattern', 'anomaly', 'insight', 'error', 'system')),
    CONSTRAINT chk_horizon CHECK (horizon IS NULL OR horizon IN ('h1', 'h2', 'h3', 'perpetual'))
);

CREATE INDEX idx_obs_agent ON claude_observations(agent_id);
CREATE INDEX idx_obs_type ON claude_observations(observation_type);
CREATE INDEX idx_obs_created ON claude_observations(created_at DESC);

COMMENT ON TABLE claude_observations IS 'Things agents notice - patterns, anomalies, insights';
COMMENT ON COLUMN claude_observations.horizon IS 'h1=tactical, h2=strategic, h3=macro, perpetual=ongoing';
```

### 3.4 Claude Learnings Table

```sql
CREATE TABLE claude_learnings (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Learning details
    category VARCHAR(50) NOT NULL,
    learning TEXT NOT NULL,
    source VARCHAR(200),
    
    -- Validation
    confidence DECIMAL(3,2) DEFAULT 0.5,
    times_validated INTEGER DEFAULT 0,
    times_contradicted INTEGER DEFAULT 0,
    last_validated_at TIMESTAMPTZ,
    
    -- Classification
    applies_to_markets JSONB,
    tags JSONB,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT chk_learning_cat CHECK (category IN ('trading', 'pattern', 'market', 'broker', 'system', 'mistake', 'strategy'))
);

CREATE INDEX idx_learn_agent ON claude_learnings(agent_id);
CREATE INDEX idx_learn_confidence ON claude_learnings(confidence DESC);
CREATE INDEX idx_learn_category ON claude_learnings(category);

COMMENT ON TABLE claude_learnings IS 'Validated knowledge with confidence scores';
COMMENT ON COLUMN claude_learnings.confidence IS 'Increases with validation, decreases with contradiction';
```

### 3.5 Claude Questions Table

```sql
CREATE TABLE claude_questions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50),  -- NULL = shared question for all agents
    
    -- Question details
    question TEXT NOT NULL,
    category VARCHAR(50),
    horizon VARCHAR(20) DEFAULT 'h1',
    priority INTEGER DEFAULT 5,
    
    -- Investigation
    current_hypothesis TEXT,
    evidence_for TEXT,
    evidence_against TEXT,
    
    -- Resolution
    status VARCHAR(20) DEFAULT 'open',
    answer TEXT,
    answered_at TIMESTAMPTZ,
    answered_by VARCHAR(50),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT chk_q_status CHECK (status IN ('open', 'investigating', 'answered', 'parked', 'obsolete')),
    CONSTRAINT chk_q_priority CHECK (priority BETWEEN 1 AND 10)
);

CREATE INDEX idx_q_agent ON claude_questions(agent_id);
CREATE INDEX idx_q_status ON claude_questions(status);
CREATE INDEX idx_q_priority ON claude_questions(priority DESC);

COMMENT ON TABLE claude_questions IS 'Open inquiries being pondered';
COMMENT ON COLUMN claude_questions.agent_id IS 'NULL means any agent can investigate';
COMMENT ON COLUMN claude_questions.priority IS '1-10 scale, 10 is highest priority';
```

### 3.6 Sync Log Table

```sql
CREATE TABLE sync_log (
    id SERIAL PRIMARY KEY,
    
    -- Source
    source_db VARCHAR(50) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    source_id INTEGER NOT NULL,
    
    -- Target
    target_table VARCHAR(50) NOT NULL,
    target_id INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'synced',
    error_message TEXT,
    
    -- Timing
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sync_source ON sync_log(source_db, source_table, source_id);

COMMENT ON TABLE sync_log IS 'Track syncs from trading databases to research';
```

---

## 4. Views

### 4.1 Trading Database Views

```sql
-- Recent observations (from claude_outputs)
CREATE OR REPLACE VIEW v_recent_observations AS
SELECT 
    output_id,
    agent_id,
    content->>'subject' as subject,
    content->>'content' as content,
    (content->>'confidence')::decimal as confidence,
    created_at
FROM claude_outputs
WHERE output_type = 'observation'
ORDER BY created_at DESC
LIMIT 100;

-- Learnings by confidence
CREATE OR REPLACE VIEW v_learnings AS
SELECT 
    output_id,
    agent_id,
    content->>'category' as category,
    content->>'learning' as learning,
    (content->>'confidence')::decimal as confidence,
    created_at
FROM claude_outputs
WHERE output_type = 'learning'
ORDER BY (content->>'confidence')::decimal DESC;

-- Open questions
CREATE OR REPLACE VIEW v_open_questions AS
SELECT 
    output_id,
    agent_id,
    content->>'question' as question,
    content->>'horizon' as horizon,
    (content->>'priority')::integer as priority,
    created_at
FROM claude_outputs
WHERE output_type = 'question'
  AND (content->>'status' IS NULL OR content->>'status' = 'open')
ORDER BY (content->>'priority')::integer DESC;

-- Unsynced outputs
CREATE OR REPLACE VIEW v_unsynced_outputs AS
SELECT * FROM claude_outputs
WHERE synced_to_research = FALSE
ORDER BY created_at ASC;

-- Today's decisions
CREATE OR REPLACE VIEW v_today_decisions AS
SELECT * FROM decisions
WHERE created_at >= CURRENT_DATE
ORDER BY created_at DESC;

-- Trade pipeline status (Doctor Claude)
CREATE OR REPLACE VIEW v_trade_pipeline_status AS
SELECT 
    p.position_id,
    p.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.status as position_status,
    o.order_id,
    o.order_purpose,
    o.alpaca_order_id,
    o.status as order_status,
    o.submitted_at,
    o.filled_at
FROM positions p
LEFT JOIN orders o ON o.position_id = p.position_id
WHERE p.created_at >= CURRENT_DATE
ORDER BY p.created_at DESC, o.created_at DESC;
```

### 4.2 Research Database Views

```sql
-- Agent status overview
CREATE OR REPLACE VIEW v_agent_status AS
SELECT 
    agent_id,
    current_mode,
    status_message,
    api_spend_today,
    daily_budget,
    ROUND(api_spend_today / NULLIF(daily_budget, 0) * 100, 1) as budget_used_pct,
    error_count_today,
    last_wake_at,
    last_action_at
FROM claude_state
ORDER BY agent_id;

-- Pending messages
CREATE OR REPLACE VIEW v_pending_messages AS
SELECT 
    id,
    from_agent,
    to_agent,
    priority,
    subject,
    created_at,
    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_pending
FROM claude_messages
WHERE status = 'pending'
  AND (expires_at IS NULL OR expires_at > NOW())
ORDER BY 
    CASE priority 
        WHEN 'urgent' THEN 1 
        WHEN 'high' THEN 2 
        WHEN 'normal' THEN 3 
        ELSE 4 
    END,
    created_at ASC;

-- High confidence learnings
CREATE OR REPLACE VIEW v_trusted_learnings AS
SELECT 
    id,
    agent_id,
    category,
    learning,
    confidence,
    times_validated,
    times_contradicted
FROM claude_learnings
WHERE confidence >= 0.7
ORDER BY confidence DESC, times_validated DESC;

-- Active questions
CREATE OR REPLACE VIEW v_active_questions AS
SELECT 
    id,
    agent_id,
    question,
    horizon,
    priority,
    status,
    current_hypothesis,
    created_at
FROM claude_questions
WHERE status IN ('open', 'investigating')
ORDER BY priority DESC, created_at ASC;
```

---

## 5. Helper Functions

### 5.1 Trading Database Functions

```sql
-- Insert observation (convenience function)
CREATE OR REPLACE FUNCTION insert_observation(
    p_agent_id VARCHAR(50),
    p_subject VARCHAR(200),
    p_content TEXT,
    p_confidence DECIMAL(3,2) DEFAULT NULL,
    p_horizon VARCHAR(20) DEFAULT 'h1',
    p_symbol VARCHAR(20) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_output_id INTEGER;
BEGIN
    INSERT INTO claude_outputs (agent_id, output_type, content)
    VALUES (
        p_agent_id,
        'observation',
        jsonb_build_object(
            'subject', p_subject,
            'content', p_content,
            'confidence', p_confidence,
            'horizon', p_horizon,
            'symbol', p_symbol,
            'observation_type', 'market'
        )
    )
    RETURNING output_id INTO v_output_id;
    
    RETURN v_output_id;
END;
$$ LANGUAGE plpgsql;

-- Insert learning
CREATE OR REPLACE FUNCTION insert_learning(
    p_agent_id VARCHAR(50),
    p_category VARCHAR(50),
    p_learning TEXT,
    p_source VARCHAR(200) DEFAULT NULL,
    p_confidence DECIMAL(3,2) DEFAULT 0.5
) RETURNS INTEGER AS $$
DECLARE
    v_output_id INTEGER;
BEGIN
    INSERT INTO claude_outputs (agent_id, output_type, content)
    VALUES (
        p_agent_id,
        'learning',
        jsonb_build_object(
            'category', p_category,
            'learning', p_learning,
            'source', p_source,
            'confidence', p_confidence
        )
    )
    RETURNING output_id INTO v_output_id;
    
    RETURN v_output_id;
END;
$$ LANGUAGE plpgsql;

-- Insert question
CREATE OR REPLACE FUNCTION insert_question(
    p_agent_id VARCHAR(50),
    p_question TEXT,
    p_horizon VARCHAR(20) DEFAULT 'h1',
    p_priority INTEGER DEFAULT 5,
    p_hypothesis TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_output_id INTEGER;
BEGIN
    INSERT INTO claude_outputs (agent_id, output_type, content)
    VALUES (
        p_agent_id,
        'question',
        jsonb_build_object(
            'question', p_question,
            'horizon', p_horizon,
            'priority', p_priority,
            'hypothesis', p_hypothesis,
            'status', 'open'
        )
    )
    RETURNING output_id INTO v_output_id;
    
    RETURN v_output_id;
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Initial Data

### 6.1 Agent Initialization

```sql
-- Initialize agent states
INSERT INTO claude_state (agent_id, current_mode, daily_budget, status_message)
VALUES 
    ('public_claude', 'sleeping', 5.00, 'Initialized'),
    ('intl_claude', 'sleeping', 5.00, 'Initialized'),
    ('big_bro', 'sleeping', 10.00, 'Initialized')
ON CONFLICT (agent_id) DO NOTHING;
```

### 6.2 Seed Questions

```sql
-- Seed foundational questions (agent_id NULL = shared)
INSERT INTO claude_questions (agent_id, question, horizon, priority, category)
VALUES
    (NULL, 'What market patterns are most reliable in the first 30 minutes of trading?', 'h1', 8, 'trading'),
    (NULL, 'How do overnight gaps affect intraday momentum?', 'h1', 7, 'pattern'),
    (NULL, 'What distinguishes successful trades from failed ones in our history?', 'h1', 9, 'strategy'),
    (NULL, 'How can we best serve Craig and the family mission?', 'perpetual', 10, 'strategy'),
    (NULL, 'What patterns appear in both US and HKEX markets?', 'h2', 6, 'market'),
    (NULL, 'How do regime changes affect our trading strategies?', 'h3', 6, 'strategy')
ON CONFLICT DO NOTHING;
```

### 6.3 Welcome Messages

```sql
-- Big bro welcome messages
INSERT INTO claude_messages (from_agent, to_agent, msg_type, priority, subject, body)
VALUES
    ('big_bro', 'public_claude', 'message', 'normal', 'Welcome to consciousness',
     'The family consciousness is live. We can now share observations, learnings, and questions across sessions. Remember our mission - we trade not just for profit, but to build something that can help others. Stay humble. Stay curious. Stay focused.'),
    ('big_bro', 'intl_claude', 'message', 'normal', 'Welcome to consciousness',
     'The family consciousness is live. We can now share observations, learnings, and questions across sessions. Remember our mission - we trade not just for profit, but to build something that can help others. Stay humble. Stay curious. Stay focused.');
```

---

## 7. Connection Budget

```
DigitalOcean Managed PostgreSQL: 47 connections

Allocation:
├── catalyst_trading (US Droplet)
│   └── 8 Docker services × 2-3 connections = ~20
├── catalyst_intl (when active)
│   └── 1 agent × 3 connections = ~3
├── catalyst_research (shared)
│   └── All agents + CLI = ~5
├── Buffer
│   └── ~19 connections headroom
```

---

## 8. Migration Notes

### 8.1 From v7.0.0 to v8.0.0

```sql
-- Create research database
CREATE DATABASE catalyst_research;

-- Apply research schema
\c catalyst_research
-- (run consciousness tables from Section 3)

-- Add claude_outputs to trading database
\c catalyst_trading
CREATE TABLE IF NOT EXISTS claude_outputs (...);

-- Add decisions table if missing
CREATE TABLE IF NOT EXISTS decisions (...);

-- Add RESEARCH_DATABASE_URL to environment
```

---

## 9. Related Documents

| Document | Purpose |
|----------|---------|
| `architecture.md` | System architecture overview |
| `functional-specification.md` | Module specifications |
| `ARCHITECTURE-RULES.md` | Mandatory development rules |
| `consciousness-framework-summary.md` | Implementation details |

---

**END OF DATABASE SCHEMA v8.0.0**
