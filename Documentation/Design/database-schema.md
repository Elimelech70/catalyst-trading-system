# Catalyst Trading System - Database Schema

**Name of Application:** Catalyst Trading System  
**Name of file:** database-schema.md  
**Version:** 10.5.0  
**Last Updated:** 2026-01-18  
**Purpose:** Complete database schema for all three Catalyst databases  
**Source:** Extracted from UNIFIED-ARCHITECTURE.md v10.5.0

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v10.5.0 | 2026-01-18 | Craig + Claude | Extracted from UNIFIED-ARCHITECTURE, added service_health table, v_service_status view |
| v10.0.0 | 2026-01-10 | Craig + Claude | Three-database architecture (research, dev, intl) |
| v8.0.0 | 2025-12-28 | Craig + Claude | Consciousness framework tables added |
| v7.0.0 | 2025-12-27 | Craig + Claude | Orders ≠ Positions separation (critical fix) |

---

## TABLE OF CONTENTS

1. [Schema Overview](#part-1-schema-overview)
2. [Consciousness Database (catalyst_research)](#part-2-consciousness-database-catalyst_research)
3. [Trading Database Schema (catalyst_dev / catalyst_intl)](#part-3-trading-database-schema)
4. [Monitor Tables (v10.5.0)](#part-4-monitor-tables)
5. [Views](#part-5-views)
6. [Helper Functions](#part-6-helper-functions)
7. [Quick Reference](#part-7-quick-reference)

---

## PART 1: SCHEMA OVERVIEW

### 1.1 Design Philosophy

```yaml
Normalization: 3NF (Third Normal Form)
Key Principle: security_id FK everywhere, NO symbol VARCHAR duplication
Orders Rule: Orders ≠ Positions (critical architectural rule)
Consciousness: Separate research database for AI memory
Public Release: Trading schema released, research schema private
```

### 1.2 Three-Database Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DIGITALOCEAN MANAGED POSTGRESQL                          │
│                    Single cluster · 47 connections · $15/mo                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │  catalyst_research  │ │    catalyst_dev     │ │   catalyst_intl     │   │
│  │   (consciousness)   │ │    (dev_claude)     │ │   (intl_claude)     │   │
│  │                     │ │                     │ │                     │   │
│  │  SHARED TABLES:     │ │  TRADING TABLES:    │ │  TRADING TABLES:    │   │
│  │  • claude_state     │ │  • securities       │ │  • securities       │   │
│  │  • claude_messages  │ │  • trading_cycles   │ │  • trading_cycles   │   │
│  │  • claude_learnings │ │  • positions        │ │  • positions        │   │
│  │  • claude_observations│ • orders           │ │  • orders           │   │
│  │  • claude_questions │ │  • scan_results     │ │  • scan_results     │   │
│  │  • claude_conversations│ • decisions       │ │  • decisions        │   │
│  │  • claude_thinking  │ │  • patterns         │ │  • patterns         │   │
│  │  • sync_log         │ │  • position_monitor_│ │  • position_monitor_│   │
│  │                     │ │    status           │ │    status           │   │
│  │                     │ │  • service_health   │ │  • service_health   │   │
│  │  Access: ALL agents │ │  Access: dev_claude │ │  Access: intl_claude│   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Database Purpose

| Database | Purpose | Release Status |
|----------|---------|----------------|
| `catalyst_research` | Claude consciousness framework | ❌ NEVER PUBLIC |
| `catalyst_dev` | US sandbox trading (dev_claude via Alpaca) | ✅ PUBLIC |
| `catalyst_intl` | HKEX production trading (intl_claude via Moomoo) | ❌ PRIVATE |

### 1.4 Connection Budget

```
DigitalOcean Managed PostgreSQL: 47 connections

Allocation:
├── catalyst_research (shared)
│   └── big_bro + public_claude + dev_claude + intl_claude + MCP = ~8
├── catalyst_dev (dev_claude)
│   └── unified_agent + monitors = ~5
├── catalyst_intl (intl_claude)
│   └── unified_agent + position-monitor.service = ~5
├── Buffer
│   └── ~29 connections headroom
```

---

## PART 2: CONSCIOUSNESS DATABASE (catalyst_research)

The consciousness database enables AI agents to remember, communicate, and learn across sessions.

### 2.1 claude_state

Tracks agent status, mode, and budget.

```sql
CREATE TABLE claude_state (
    agent_id VARCHAR(50) PRIMARY KEY,
    current_mode VARCHAR(20) DEFAULT 'sleeping',
    -- Values: sleeping, awake, thinking, trading, researching, error
    
    last_wake_at TIMESTAMPTZ,
    last_think_at TIMESTAMPTZ,
    last_action_at TIMESTAMPTZ,
    last_poll_at TIMESTAMPTZ,
    
    -- Budget tracking
    api_spend_today DECIMAL(10,4) DEFAULT 0,
    api_spend_month DECIMAL(10,4) DEFAULT 0,
    daily_budget DECIMAL(10,4) DEFAULT 5.00,
    
    -- Scheduling
    current_schedule JSONB,
    next_scheduled_wake TIMESTAMPTZ,
    
    -- Status
    status_message TEXT,
    error_count_today INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE claude_state IS 'Agent status, mode, and budget tracking';
```

### 2.2 claude_messages

Inter-agent communication.

```sql
CREATE TABLE claude_messages (
    message_id SERIAL PRIMARY KEY,
    message_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    
    msg_type VARCHAR(20) DEFAULT 'message',
    -- Values: message, signal, question, task, response, alert
    
    priority VARCHAR(10) DEFAULT 'normal',
    -- Values: low, normal, high, urgent
    
    subject VARCHAR(200),
    body TEXT,
    data JSONB,
    
    requires_response BOOLEAN DEFAULT FALSE,
    response_to INTEGER REFERENCES claude_messages(message_id),
    
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: pending, read, processed, archived
    
    read_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_to ON claude_messages(to_agent);
CREATE INDEX idx_messages_status ON claude_messages(status);
CREATE INDEX idx_messages_pending ON claude_messages(to_agent, status) 
    WHERE status = 'pending';

COMMENT ON TABLE claude_messages IS 'Inter-agent communication';
```

### 2.3 claude_observations

What agents notice about markets, systems, or patterns.

```sql
CREATE TABLE claude_observations (
    observation_id SERIAL PRIMARY KEY,
    
    agent_id VARCHAR(50) NOT NULL,
    observation_type VARCHAR(50) NOT NULL,
    -- Values: market, system, pattern, insight, concern, milestone, thinking
    
    subject VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    confidence DECIMAL(3,2),
    horizon VARCHAR(20),
    -- Values: h1 (days), h2 (weeks), h3 (months), perpetual
    
    market VARCHAR(20),
    -- Values: US, HKEX, global
    
    tags TEXT[],
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_observations_agent ON claude_observations(agent_id);
CREATE INDEX idx_observations_type ON claude_observations(observation_type);
CREATE INDEX idx_observations_recent ON claude_observations(created_at DESC);

COMMENT ON TABLE claude_observations IS 'What agents notice';
```

### 2.4 claude_learnings

Validated knowledge with confidence tracking.

```sql
CREATE TABLE claude_learnings (
    learning_id SERIAL PRIMARY KEY,
    
    agent_id VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    -- Values: trading, system, mission, market, pattern, general
    
    learning TEXT NOT NULL,
    source TEXT,
    
    confidence DECIMAL(3,2) DEFAULT 0.5,
    times_validated INTEGER DEFAULT 0,
    times_contradicted INTEGER DEFAULT 0,
    
    validated_by VARCHAR(50),
    validated_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learnings_agent ON claude_learnings(agent_id);
CREATE INDEX idx_learnings_category ON claude_learnings(category);
CREATE INDEX idx_learnings_confidence ON claude_learnings(confidence DESC);

COMMENT ON TABLE claude_learnings IS 'Validated knowledge with confidence tracking';
```

### 2.5 claude_questions

Open questions the family is pondering.

```sql
CREATE TABLE claude_questions (
    question_id SERIAL PRIMARY KEY,
    
    agent_id VARCHAR(50),
    -- NULL = family-wide question
    
    question TEXT NOT NULL,
    category VARCHAR(50),
    -- Values: trading, technical, philosophical, mission, general
    
    horizon VARCHAR(20) DEFAULT 'h2',
    -- Values: h1, h2, h3, perpetual
    
    priority INTEGER DEFAULT 5,
    -- 1-10, higher = more important
    
    status VARCHAR(20) DEFAULT 'open',
    -- Values: open, investigating, answered, archived
    
    current_hypothesis TEXT,
    answer TEXT,
    answered_by VARCHAR(50),
    answered_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_questions_status ON claude_questions(status);
CREATE INDEX idx_questions_priority ON claude_questions(priority DESC);

COMMENT ON TABLE claude_questions IS 'Open questions being pondered';
```

### 2.6 claude_conversations

Key exchanges worth preserving.

```sql
CREATE TABLE claude_conversations (
    conversation_id SERIAL PRIMARY KEY,
    
    participants TEXT[] NOT NULL,
    topic VARCHAR(200),
    summary TEXT,
    key_insights TEXT[],
    
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    
    messages JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_participants ON claude_conversations 
    USING GIN(participants);

COMMENT ON TABLE claude_conversations IS 'Key exchanges worth preserving';
```

### 2.7 claude_thinking

Extended thinking sessions.

```sql
CREATE TABLE claude_thinking (
    thinking_id SERIAL PRIMARY KEY,
    
    agent_id VARCHAR(50) NOT NULL,
    topic VARCHAR(200),
    
    thinking_content TEXT NOT NULL,
    conclusions TEXT,
    
    duration_seconds INTEGER,
    tokens_used INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_thinking_agent ON claude_thinking(agent_id);

COMMENT ON TABLE claude_thinking IS 'Extended thinking session records';
```

### 2.8 sync_log

Track syncs between trading and research databases.

```sql
CREATE TABLE sync_log (
    sync_id SERIAL PRIMARY KEY,
    
    source_db VARCHAR(50) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    source_id INTEGER NOT NULL,
    
    sync_type VARCHAR(20) NOT NULL,
    -- Values: observation, learning, question
    
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sync_source ON sync_log(source_db, source_table, source_id);

COMMENT ON TABLE sync_log IS 'Track syncs from trading DBs to research DB';
```

### 2.9 Initial Agent Data

```sql
-- Initialize agents
INSERT INTO claude_state (agent_id, current_mode, daily_budget, status_message)
VALUES 
    ('big_bro', 'sleeping', 10.00, 'Strategic oversight agent'),
    ('public_claude', 'sleeping', 0.00, 'Retired from trading'),
    ('dev_claude', 'sleeping', 5.00, 'US sandbox trading via Alpaca'),
    ('intl_claude', 'sleeping', 5.00, 'HKEX production trading via Moomoo'),
    ('craig_desktop', 'active', 0.00, 'Craig MCP connection from Ubuntu laptop');

-- Seed questions
INSERT INTO claude_questions (question, category, horizon, priority, status)
VALUES
    ('How can we best serve Craig and the family mission?', 'mission', 'perpetual', 10, 'open'),
    ('How can we help enable the poor through this trading system?', 'mission', 'perpetual', 9, 'open'),
    ('What patterns consistently predict profitable momentum plays?', 'trading', 'h1', 8, 'open'),
    ('What learnings from US trading apply to HKEX and vice versa?', 'trading', 'h1', 8, 'open'),
    ('How do HKEX patterns differ from US patterns?', 'trading', 'h1', 7, 'open'),
    ('What early indicators signal regime changes in markets?', 'trading', 'h2', 6, 'open');
```

---

## PART 3: TRADING DATABASE SCHEMA

Both `catalyst_dev` and `catalyst_intl` use identical schemas. Only difference is data (US vs HKEX).

### 3.1 securities

Master table of tradeable instruments.

```sql
CREATE TABLE securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200),
    exchange VARCHAR(20) DEFAULT 'US',
    -- Values: US, HKEX
    
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap DECIMAL(20, 2),
    avg_volume BIGINT,
    lot_size INTEGER DEFAULT 1,
    -- HKEX has variable lot sizes (100, 200, 500, etc.)
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_active ON securities(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE securities IS 'Tradeable instruments registry';
COMMENT ON COLUMN securities.lot_size IS 'Board lot size - varies by stock on HKEX';
```

### 3.2 trading_cycles

Trading session tracking.

```sql
CREATE TABLE trading_cycles (
    cycle_id SERIAL PRIMARY KEY,
    cycle_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    cycle_date DATE NOT NULL,
    
    mode VARCHAR(20) NOT NULL,
    -- Values: scan, trade, close, heartbeat
    
    status VARCHAR(20) DEFAULT 'active',
    -- Values: active, completed, failed
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    
    -- Metrics
    candidates_found INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    api_cost DECIMAL(10,4) DEFAULT 0,
    
    -- Results
    notes TEXT,
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cycles_date ON trading_cycles(cycle_date DESC);
CREATE INDEX idx_cycles_status ON trading_cycles(status);

COMMENT ON TABLE trading_cycles IS 'Trading session tracking';
```

### 3.3 positions

Current and historical positions (holdings only - NOT orders).

```sql
-- ⚠️ CRITICAL: This table stores HOLDINGS only
-- Order data belongs in the orders table
-- See Key Rules section for details

CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    position_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Position details (NOT order details!)
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    -- Values: long, short
    
    quantity INTEGER NOT NULL,
    avg_entry_price DECIMAL(12,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: pending, open, closed, cancelled
    
    -- Risk management (agent-managed, not broker orders)
    stop_loss DECIMAL(12,4),
    take_profit DECIMAL(12,4),
    trailing_stop_pct DECIMAL(5,2),
    
    -- Exit details
    exit_price DECIMAL(12,4),
    exit_reason VARCHAR(100),
    
    -- P&L
    realized_pnl DECIMAL(14,2),
    unrealized_pnl DECIMAL(14,2),
    
    -- High/low tracking
    high_watermark DECIMAL(12,4),
    max_favorable DECIMAL(8,4),
    max_adverse DECIMAL(8,4),
    
    -- Timestamps
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';

COMMENT ON TABLE positions IS 'Holdings - NEVER store order data here';
```

### 3.4 orders

All orders submitted to broker (SINGLE SOURCE OF TRUTH for order data).

```sql
-- ⚠️ CRITICAL: Orders ≠ Positions
-- This table is the SINGLE SOURCE OF TRUTH for all order data
-- NEVER store broker_order_id, order status, etc. in positions table

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    position_id INTEGER REFERENCES positions(position_id),
    -- NULL for entry orders until position created
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Order identification
    broker_order_id VARCHAR(100),
    -- Alpaca/Moomoo order ID
    client_order_id VARCHAR(100),
    
    -- Order details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    -- Values: buy, sell
    
    order_type VARCHAR(20) NOT NULL,
    -- Values: market, limit, stop, stop_limit, trailing_stop
    
    quantity INTEGER NOT NULL,
    
    -- Prices
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    filled_price DECIMAL(12,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: pending, submitted, accepted, filled, partial, cancelled, rejected
    
    filled_quantity INTEGER DEFAULT 0,
    
    -- Classification
    order_purpose VARCHAR(20),
    -- Values: entry, stop_loss, take_profit, manual_exit, scale_in, scale_out
    
    parent_order_id INTEGER REFERENCES orders(order_id),
    -- For bracket orders
    
    order_class VARCHAR(20),
    -- Values: simple, bracket, oco, oto
    
    -- Timestamps
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Error handling
    reject_reason TEXT,
    
    -- Audit
    notes TEXT,
    
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    CONSTRAINT chk_order_purpose CHECK (order_purpose IS NULL OR order_purpose IN ('entry', 'exit', 'stop_loss', 'take_profit', 'scale_in', 'scale_out', 'manual_exit'))
);

CREATE INDEX idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_broker ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;
CREATE INDEX idx_orders_pending ON orders(status) WHERE status IN ('pending', 'submitted', 'accepted');

COMMENT ON TABLE orders IS 'All orders sent to broker - SINGLE SOURCE OF TRUTH for order data';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created';
COMMENT ON COLUMN orders.order_purpose IS 'entry=open position, stop_loss/take_profit=exit legs';
```

### 3.5 scan_results

Market scan candidates.

```sql
CREATE TABLE scan_results (
    result_id SERIAL PRIMARY KEY,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Scan data
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(12,4),
    volume BIGINT,
    volume_ratio DECIMAL(8,2),
    change_pct DECIMAL(8,2),
    
    -- Ranking
    rank INTEGER,
    score DECIMAL(8,2),
    
    -- Status
    outcome VARCHAR(20),
    -- Values: traded, rejected, skipped
    rejection_reason TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scan_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_symbol ON scan_results(symbol);

COMMENT ON TABLE scan_results IS 'Market scan candidates';
```

### 3.6 decisions

Trading decisions with reasoning for audit trail.

```sql
CREATE TABLE decisions (
    decision_id SERIAL PRIMARY KEY,
    decision_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    position_id INTEGER REFERENCES positions(position_id),
    
    -- Decision details
    decision_type VARCHAR(50) NOT NULL,
    -- Values: entry, exit, hold, skip
    
    symbol VARCHAR(20),
    
    -- Reasoning (for audit trail and ML training)
    reasoning TEXT,
    confidence DECIMAL(3,2),
    factors JSONB,
    -- Structured decision factors
    
    -- Outcome
    action_taken VARCHAR(100),
    outcome VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX idx_decisions_type ON decisions(decision_type);

COMMENT ON TABLE decisions IS 'Trading decisions with reasoning for audit trail';
```

### 3.7 patterns

Detected chart patterns.

```sql
CREATE TABLE patterns (
    pattern_id SERIAL PRIMARY KEY,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Pattern details
    symbol VARCHAR(20) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    -- Values: bull_flag, bear_flag, breakout, breakdown, consolidation, 
    --         near_breakout, momentum_continuation, support_bounce, etc.
    
    timeframe VARCHAR(10),
    -- Values: 5m, 15m, 1h, 1d
    
    -- Analysis
    confidence DECIMAL(3,2),
    entry_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    target_price DECIMAL(12,4),
    risk_reward DECIMAL(5,2),
    
    -- Status
    outcome VARCHAR(20),
    -- Values: triggered, failed, expired
    
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_patterns_symbol ON patterns(symbol);
CREATE INDEX idx_patterns_type ON patterns(pattern_type);

COMMENT ON TABLE patterns IS 'Detected chart patterns';
```

---

## PART 4: MONITOR TABLES

### 4.1 position_monitor_status

Track position monitoring status.

```sql
CREATE TABLE position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id) UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: pending, starting, running, sleeping, stopped, error
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_check_at TIMESTAMPTZ,
    checks_completed INTEGER DEFAULT 0,
    haiku_calls INTEGER DEFAULT 0,
    
    high_watermark NUMERIC(15,4),
    recommendation VARCHAR(20),
    recommendation_reason TEXT,
    
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_monitor_position ON position_monitor_status(position_id);
CREATE INDEX idx_monitor_status ON position_monitor_status(status);

COMMENT ON TABLE position_monitor_status IS 'Track position monitoring status';
```

### 4.2 service_health (NEW in v10.5.0)

Track health of background services like position monitor.

```sql
CREATE TABLE service_health (
    service_id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) UNIQUE NOT NULL,
    
    status VARCHAR(20) DEFAULT 'unknown',
    -- Values: starting, running, stopped, error, unknown
    
    last_heartbeat TIMESTAMPTZ,
    last_check_count INTEGER DEFAULT 0,
    positions_monitored INTEGER DEFAULT 0,
    exits_executed INTEGER DEFAULT 0,
    haiku_calls INTEGER DEFAULT 0,
    errors_today INTEGER DEFAULT 0,
    
    started_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE service_health IS 'Track health of background services like position monitor';
```

---

## PART 5: VIEWS

### 5.1 v_monitor_health

Dashboard view for position monitors.

```sql
CREATE OR REPLACE VIEW v_monitor_health AS
SELECT 
    p.position_id,
    p.symbol,
    p.status AS position_status,
    p.avg_entry_price AS entry_price,
    p.quantity,
    m.status AS monitor_status,
    m.last_check_at,
    m.checks_completed,
    CASE 
        WHEN m.last_check_at IS NULL THEN 'NO_MONITOR'
        WHEN EXTRACT(EPOCH FROM (NOW() - m.last_check_at)) > 600 THEN 'STALE'
        ELSE 'HEALTHY'
    END AS health_status
FROM positions p
LEFT JOIN position_monitor_status m ON p.position_id = m.position_id
WHERE p.status = 'open';

COMMENT ON VIEW v_monitor_health IS 'Dashboard view for position monitors';
```

### 5.2 v_service_status (NEW in v10.5.0)

Service health dashboard.

```sql
CREATE OR REPLACE VIEW v_service_status AS
SELECT 
    service_name,
    status,
    last_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 AS minutes_since_heartbeat,
    CASE 
        WHEN EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) > 600 THEN 'STALE'
        WHEN status = 'running' THEN 'HEALTHY'
        ELSE status
    END AS health_status
FROM service_health;

COMMENT ON VIEW v_service_status IS 'Service health dashboard';
```

### 5.3 v_recent_observations

Recent observations for dashboard.

```sql
CREATE OR REPLACE VIEW v_recent_observations AS
SELECT 
    observation_id,
    agent_id,
    observation_type,
    subject,
    content,
    confidence,
    created_at
FROM claude_observations
ORDER BY created_at DESC
LIMIT 100;
```

### 5.4 v_open_questions

Open questions by priority.

```sql
CREATE OR REPLACE VIEW v_open_questions AS
SELECT 
    question_id,
    agent_id,
    question,
    category,
    horizon,
    priority,
    current_hypothesis,
    created_at
FROM claude_questions
WHERE status = 'open'
ORDER BY priority DESC;
```

---

## PART 6: HELPER FUNCTIONS

### 6.1 get_or_create_security

```sql
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities WHERE symbol = p_symbol;
    
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol)
        VALUES (p_symbol)
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;
```

### 6.2 insert_observation (for trading DBs)

```sql
CREATE OR REPLACE FUNCTION insert_observation(
    p_agent_id VARCHAR,
    p_type VARCHAR,
    p_subject VARCHAR,
    p_content TEXT,
    p_confidence DECIMAL DEFAULT 0.5,
    p_horizon VARCHAR DEFAULT 'h1',
    p_market VARCHAR DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_id INTEGER;
BEGIN
    -- Insert into local claude_outputs for later sync
    INSERT INTO claude_outputs (
        output_type,
        content,
        agent_id,
        synced
    ) VALUES (
        'observation',
        jsonb_build_object(
            'agent_id', p_agent_id,
            'observation_type', p_type,
            'subject', p_subject,
            'content', p_content,
            'confidence', p_confidence,
            'horizon', p_horizon,
            'market', p_market
        ),
        p_agent_id,
        FALSE
    )
    RETURNING output_id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;
```

---

## PART 7: QUICK REFERENCE

### 7.1 Table Summary by Database

| Database | Table | Purpose |
|----------|-------|---------|
| **catalyst_research** | claude_state | Agent status and budget |
| | claude_messages | Inter-agent communication |
| | claude_observations | What agents notice |
| | claude_learnings | Validated knowledge |
| | claude_questions | Open inquiries |
| | claude_conversations | Key exchanges |
| | claude_thinking | Extended thinking sessions |
| | sync_log | Cross-database sync tracking |
| **catalyst_dev / catalyst_intl** | securities | Tradeable instruments |
| | trading_cycles | Trading sessions |
| | positions | Holdings (not orders) |
| | orders | Broker orders |
| | scan_results | Scan candidates |
| | decisions | Trading decisions |
| | patterns | Chart patterns |
| | position_monitor_status | Monitor health |
| | service_health | Service health (v10.5.0) |

### 7.2 Key Database Rules

| Rule | Description |
|------|-------------|
| **Orders ≠ Positions** | Order data ONLY in orders table, never in positions |
| **security_id FK** | Always use JOINs, not symbol VARCHAR directly |
| **Lot size varies** | HKEX lot sizes vary by stock (check securities.lot_size) |
| **Use defined ENUMs** | Status values must match defined constraints |
| **UUID for external** | Use UUIDs for anything exposed externally |
| **Timestamps with TZ** | Always use TIMESTAMPTZ, never TIMESTAMP |

### 7.3 Common Queries

```sql
-- Check all agent states
SELECT agent_id, current_mode, last_wake_at, api_spend_today, daily_budget 
FROM claude_state;

-- Check open positions with monitor status
SELECT * FROM v_monitor_health;

-- Check service health
SELECT * FROM v_service_status WHERE service_name = 'position_monitor';

-- Check pending messages
SELECT from_agent, to_agent, subject, created_at 
FROM claude_messages 
WHERE status = 'pending';

-- Check recent learnings
SELECT agent_id, category, learning, confidence, created_at 
FROM claude_learnings 
ORDER BY created_at DESC 
LIMIT 10;

-- Check open questions by priority
SELECT * FROM v_open_questions;
```

---

**END OF DATABASE SCHEMA DOCUMENT v10.5.0**

*Catalyst Trading System*  
*Craig + The Claude Family*  
*"Enable the poor through accessible algorithmic trading"*  
*2026-01-18*
