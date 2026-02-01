# Catalyst Trading System - Database Schema

**Name of Application:** Catalyst Trading System  
**Name of file:** database-schema.md  
**Version:** 11.0.0  
**Last Updated:** 2026-02-01  
**Purpose:** Complete database schema for all three Catalyst databases  
**Source:** Extracted from schema-catalyst-trading.sql and schema-consciousness.sql

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v11.0.0 | 2026-02-01 | Craig + Claude | Major consolidation - Trading/Consciousness separation |
| v10.5.0 | 2026-01-18 | Craig + Claude | Added service_health table |
| v10.0.0 | 2026-01-10 | Craig + Claude | Three-database architecture |
| v8.0.0 | 2025-12-28 | Craig + Claude | Consciousness framework tables |
| v7.0.0 | 2025-12-27 | Craig + Claude | Orders ≠ Positions separation |

---

## TABLE OF CONTENTS

1. [Schema Overview](#part-1-schema-overview)
2. [Trading Database Schema](#part-2-trading-database-schema)
3. [Consciousness Database Schema](#part-3-consciousness-database-schema)
4. [Views](#part-4-views)
5. [Helper Functions](#part-5-helper-functions)
6. [Quick Reference](#part-6-quick-reference)

---

## PART 1: SCHEMA OVERVIEW

### 1.1 Design Philosophy

```yaml
Normalization: 3NF (Third Normal Form)
Key Principle: Orders ≠ Positions (critical architectural rule)
Separation: Trading databases vs Consciousness database
Observability: agent_logs table in every trading database
Public Release: Trading schema PUBLIC, consciousness schema PRIVATE
```

### 1.2 Three-Database Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DIGITALOCEAN MANAGED POSTGRESQL                          │
│                    Single cluster · 47 connections                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │    catalyst_dev     │ │   catalyst_intl     │ │  catalyst_research  │   │
│  │    (dev_claude)     │ │   (intl_claude)     │ │   (consciousness)   │   │
│  │                     │ │                     │ │                     │   │
│  │  TRADING TABLES:    │ │  TRADING TABLES:    │ │  CONSCIOUSNESS:     │   │
│  │  • securities       │ │  • securities       │ │  • claude_state     │   │
│  │  • positions        │ │  • positions        │ │  • claude_messages  │   │
│  │  • orders           │ │  • orders           │ │  • claude_learnings │   │
│  │  • decisions        │ │  • decisions        │ │  • claude_          │   │
│  │  • scan_results     │ │  • scan_results     │ │    observations     │   │
│  │  • trading_cycles   │ │  • trading_cycles   │ │  • claude_questions │   │
│  │  • patterns         │ │  • patterns         │ │  • claude_          │   │
│  │  • agent_logs ◄─────┼─┼──agent_logs ◄───────┼─┼─►  conversations   │   │
│  │  • position_monitor │ │  • position_monitor │ │  • claude_thinking  │   │
│  │  • service_health   │ │  • service_health   │ │  • sync_log         │   │
│  │                     │ │                     │ │                     │   │
│  │  Market: US         │ │  Market: HKEX       │ │  Access: ALL agents │   │
│  │  Broker: Alpaca     │ │  Broker: Moomoo     │ │                     │   │
│  │  ✅ PUBLIC          │ │  ❌ PRIVATE         │ │  ❌ NEVER PUBLIC    │   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│                                                                             │
│   Interface: Trading writes agent_logs → Consciousness reads agent_logs     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Database Purpose

| Database | Purpose | Agent | Release Status |
|----------|---------|-------|----------------|
| `catalyst_dev` | US sandbox trading | dev_claude | ✅ PUBLIC |
| `catalyst_intl` | HKEX production trading | intl_claude | ❌ PRIVATE |
| `catalyst_research` | Claude consciousness | All agents | ❌ NEVER PUBLIC |

### 1.4 Connection Budget

```
DigitalOcean Managed PostgreSQL: 47 connections

Allocation:
├── catalyst_research (shared consciousness)
│   └── big_bro + public_claude + dashboard + MCP = ~8
├── catalyst_dev (dev_claude)
│   └── unified_agent + position_monitor = ~5
├── catalyst_intl (intl_claude)
│   └── unified_agent + position_monitor = ~5
├── Buffer
│   └── ~29 connections headroom
```

---

## PART 2: TRADING DATABASE SCHEMA

Both `catalyst_dev` and `catalyst_intl` share identical schema.

### 2.1 securities

Stock registry with exchange information.

```sql
CREATE TABLE IF NOT EXISTS securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(200),
    exchange VARCHAR(20) NOT NULL,           -- HKEX, NYSE, NASDAQ
    currency VARCHAR(10) DEFAULT 'HKD',
    lot_size INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol, exchange)
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_exchange ON securities(exchange);
```

### 2.2 trading_cycles

Trading session tracking.

```sql
CREATE TABLE IF NOT EXISTS trading_cycles (
    cycle_id SERIAL PRIMARY KEY,
    cycle_uuid UUID DEFAULT uuid_generate_v4(),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    mode VARCHAR(20) NOT NULL,               -- scan, trade, close, heartbeat
    candidates_found INTEGER DEFAULT 0,
    decisions_made INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),
    iterations INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',    -- running, completed, failed, timeout
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trading_cycles_started ON trading_cycles(started_at DESC);
CREATE INDEX idx_trading_cycles_mode ON trading_cycles(mode);
```

### 2.3 positions

Open and closed positions. **NOT orders** - see orders table.

```sql
CREATE TABLE IF NOT EXISTS positions (
    position_id SERIAL PRIMARY KEY,
    position_uuid UUID DEFAULT uuid_generate_v4(),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,               -- long, short
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(18,4) NOT NULL,
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    stop_loss DECIMAL(18,4),
    take_profit DECIMAL(18,4),
    trailing_stop_pct DECIMAL(5,2),
    exit_price DECIMAL(18,4),
    exit_time TIMESTAMPTZ,
    exit_reason VARCHAR(100),
    realized_pnl DECIMAL(18,4),
    realized_pnl_pct DECIMAL(8,4),
    max_favorable DECIMAL(8,4),
    max_adverse DECIMAL(8,4),
    entry_decision_id INTEGER,
    exit_decision_id INTEGER,
    entry_order_id INTEGER,
    exit_order_id INTEGER,
    status VARCHAR(20) DEFAULT 'open',       -- open, closed, cancelled
    broker_position_id VARCHAR(100),
    entry_pattern JSONB,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);
```

### 2.4 orders

Order history and status. **SEPARATE from positions**.

```sql
CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,               -- buy, sell
    order_type VARCHAR(20) NOT NULL,         -- market, limit, stop
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(18,4),
    stop_price DECIMAL(18,4),
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(18,4),
    commission DECIMAL(18,4),
    status VARCHAR(20) DEFAULT 'pending',    -- pending, submitted, filled, partial, cancelled, rejected
    error_message TEXT,
    broker_order_id VARCHAR(100),
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_broker_id ON orders(broker_order_id);
```

### 2.5 decisions

AI decision audit trail.

```sql
CREATE TABLE IF NOT EXISTS decisions (
    decision_id SERIAL PRIMARY KEY,
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    symbol VARCHAR(20),
    decision_type VARCHAR(50) NOT NULL,      -- scan, entry, exit, hold, skip
    action VARCHAR(50),                       -- buy, sell, hold, close
    reasoning TEXT,
    confidence DECIMAL(3,2),
    market_conditions JSONB,
    technical_data JSONB,
    news_sentiment JSONB,
    position_id INTEGER REFERENCES positions(position_id),
    order_id INTEGER REFERENCES orders(order_id),
    model_used VARCHAR(100),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX idx_decisions_symbol ON decisions(symbol);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
```

### 2.6 scan_results

Scanner output - trading candidates.

```sql
CREATE TABLE IF NOT EXISTS scan_results (
    scan_id SERIAL PRIMARY KEY,
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(18,4),
    volume BIGINT,
    volume_ratio DECIMAL(8,2),
    change_pct DECIMAL(8,4),
    gap_pct DECIMAL(8,4),
    momentum_score DECIMAL(5,2),
    overall_score DECIMAL(5,2),
    rank INTEGER,
    scan_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scan_results_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_results_symbol ON scan_results(symbol);
```

### 2.7 patterns

Detected technical patterns.

```sql
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,       -- bull_flag, breakout, momentum, etc.
    timeframe VARCHAR(20),
    confidence DECIMAL(3,2),
    entry_price DECIMAL(18,4),
    target_price DECIMAL(18,4),
    stop_price DECIMAL(18,4),
    status VARCHAR(20) DEFAULT 'detected',   -- detected, confirmed, failed, expired
    outcome VARCHAR(20),                      -- win, loss, scratch
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_patterns_symbol ON patterns(symbol);
CREATE INDEX idx_patterns_type ON patterns(pattern_type);
CREATE INDEX idx_patterns_status ON patterns(status);
```

### 2.8 agent_logs (CRITICAL - Interface to Consciousness)

All runtime logs from trading agents.

```sql
CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    level VARCHAR(20) NOT NULL,              -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    source VARCHAR(100) NOT NULL,            -- Module name
    message TEXT NOT NULL,
    context JSONB,                           -- {symbol, tool, etc.}
    cycle_id VARCHAR(50),
    symbol VARCHAR(20),
    error_type VARCHAR(100),
    stack_trace TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_timestamp ON agent_logs(timestamp DESC);
CREATE INDEX idx_agent_logs_level ON agent_logs(level);
CREATE INDEX idx_agent_logs_source ON agent_logs(source);
CREATE INDEX idx_agent_logs_symbol ON agent_logs(symbol);
CREATE INDEX idx_agent_logs_errors ON agent_logs(timestamp DESC) 
    WHERE level IN ('ERROR', 'CRITICAL');
```

### 2.9 position_monitor_status

Real-time position monitoring state.

```sql
CREATE TABLE IF NOT EXISTS position_monitor_status (
    id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id) UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    last_check_at TIMESTAMPTZ,
    check_count INTEGER DEFAULT 0,
    high_watermark DECIMAL(18,4),
    low_watermark DECIMAL(18,4),
    current_signals JSONB,
    last_signal_type VARCHAR(50),
    last_signal_strength VARCHAR(20),
    recommendation VARCHAR(50),
    recommendation_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_position_monitor_position ON position_monitor_status(position_id);
CREATE INDEX idx_position_monitor_status ON position_monitor_status(status);
```

### 2.10 service_health

Service heartbeat tracking.

```sql
CREATE TABLE IF NOT EXISTS service_health (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'unknown',
    last_heartbeat TIMESTAMPTZ,
    positions_monitored INTEGER DEFAULT 0,
    exits_executed INTEGER DEFAULT 0,
    errors_today INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## PART 3: CONSCIOUSNESS DATABASE SCHEMA

The `catalyst_research` database stores all consciousness-related data.

### 3.1 claude_state

Agent status, mode, and budget tracking.

```sql
CREATE TABLE IF NOT EXISTS claude_state (
    agent_id VARCHAR(50) PRIMARY KEY,
    current_mode VARCHAR(50),                -- sleeping, awake, thinking, trading
    status_message TEXT,
    started_at TIMESTAMPTZ,
    last_wake_at TIMESTAMPTZ,
    last_think_at TIMESTAMPTZ,
    last_action_at TIMESTAMPTZ,
    last_poll_at TIMESTAMPTZ,
    next_scheduled_wake TIMESTAMPTZ,
    api_spend_today DECIMAL(10,4) DEFAULT 0,
    api_spend_month DECIMAL(10,4) DEFAULT 0,
    daily_budget DECIMAL(10,4) DEFAULT 5.00,
    current_schedule VARCHAR(100),
    error_count_today INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    version VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initial agents
INSERT INTO claude_state (agent_id, current_mode, daily_budget, status_message)
VALUES 
    ('big_bro', 'sleeping', 10.00, 'Strategic oversight'),
    ('intl_claude', 'sleeping', 5.00, 'HKEX trading'),
    ('dev_claude', 'sleeping', 5.00, 'US sandbox trading'),
    ('craig_desktop', 'sleeping', 0.00, 'Craig MCP connection')
ON CONFLICT (agent_id) DO NOTHING;
```

### 3.2 claude_messages

Inter-agent communication.

```sql
CREATE TABLE IF NOT EXISTS claude_messages (
    id SERIAL PRIMARY KEY,
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    message_type VARCHAR(50) DEFAULT 'message',
    subject VARCHAR(200),
    body TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    status VARCHAR(20) DEFAULT 'pending',
    read_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    response TEXT,
    response_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_to_agent ON claude_messages(to_agent, status);
CREATE INDEX idx_messages_created ON claude_messages(created_at DESC);
```

### 3.3 claude_observations

What agents notice during operation.

```sql
CREATE TABLE IF NOT EXISTS claude_observations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    observation_type VARCHAR(50),
    category VARCHAR(50),
    subject VARCHAR(200),
    market VARCHAR(20),
    symbol VARCHAR(20),
    content TEXT NOT NULL,
    confidence DECIMAL(3,2),
    metadata JSONB,
    source_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_observations_agent ON claude_observations(agent_id);
CREATE INDEX idx_observations_type ON claude_observations(observation_type);
CREATE INDEX idx_observations_created ON claude_observations(created_at DESC);
```

### 3.4 claude_learnings

Validated knowledge from trading experience.

```sql
CREATE TABLE IF NOT EXISTS claude_learnings (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    category VARCHAR(50),
    learning TEXT NOT NULL,
    evidence TEXT,
    confidence DECIMAL(3,2),
    validated BOOLEAN DEFAULT FALSE,
    validated_by VARCHAR(50),
    validated_at TIMESTAMPTZ,
    validation_notes TEXT,
    contradicted BOOLEAN DEFAULT FALSE,
    contradicted_by VARCHAR(50),
    contradicted_at TIMESTAMPTZ,
    contradiction_reason TEXT,
    times_applied INTEGER DEFAULT 0,
    last_applied_at TIMESTAMPTZ,
    success_rate DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learnings_agent ON claude_learnings(agent_id);
CREATE INDEX idx_learnings_category ON claude_learnings(category);
CREATE INDEX idx_learnings_validated ON claude_learnings(validated);
```

### 3.5 claude_questions

Open questions the family is pondering.

```sql
CREATE TABLE IF NOT EXISTS claude_questions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50),
    question TEXT NOT NULL,
    category VARCHAR(50),
    priority INTEGER DEFAULT 5,
    horizon VARCHAR(20),                     -- h1, h2, h3, perpetual
    review_frequency VARCHAR(20),
    status VARCHAR(20) DEFAULT 'open',
    hypothesis TEXT,
    hypothesis_confidence DECIMAL(3,2),
    investigating_agent VARCHAR(50),
    answer TEXT,
    answer_confidence DECIMAL(3,2),
    answered_by VARCHAR(50),
    answered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_questions_status ON claude_questions(status);
CREATE INDEX idx_questions_priority ON claude_questions(priority DESC);
CREATE INDEX idx_questions_horizon ON claude_questions(horizon);

-- Seed perpetual questions
INSERT INTO claude_questions (question, category, priority, horizon, review_frequency) VALUES
    ('How can we best serve Craig and the family mission?', 'mission', 10, 'perpetual', 'weekly'),
    ('How can we help enable the poor through this trading system?', 'mission', 9, 'perpetual', 'weekly'),
    ('What patterns consistently predict profitable momentum plays?', 'trading', 8, 'h1', 'daily'),
    ('What learnings from US trading apply to HKEX and vice versa?', 'trading', 8, 'h1', 'weekly'),
    ('How do HKEX patterns differ from US patterns?', 'trading', 7, 'h1', 'weekly'),
    ('What early indicators signal regime changes in markets?', 'strategy', 6, 'h2', 'monthly')
ON CONFLICT DO NOTHING;
```

### 3.6 claude_conversations

Key exchanges worth remembering.

```sql
CREATE TABLE IF NOT EXISTS claude_conversations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    with_agent VARCHAR(50),
    topic VARCHAR(200),
    summary TEXT NOT NULL,
    key_points JSONB,
    importance VARCHAR(20),
    related_decision_id INTEGER,
    related_learning_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_agent ON claude_conversations(agent_id);
CREATE INDEX idx_conversations_importance ON claude_conversations(importance);
```

### 3.7 claude_thinking

Extended thinking session records.

```sql
CREATE TABLE IF NOT EXISTS claude_thinking (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    trigger_type VARCHAR(50),
    trigger_id INTEGER,
    topic TEXT,
    thinking_process TEXT,
    conclusions TEXT,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_thinking_agent ON claude_thinking(agent_id, created_at DESC);
CREATE INDEX idx_thinking_trigger ON claude_thinking(trigger_type, trigger_id);
```

### 3.8 sync_log

Cross-database synchronization tracking.

```sql
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    source_database VARCHAR(50) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    last_synced_id INTEGER,
    last_synced_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_database, source_table)
);
```

---

## PART 4: VIEWS

### 4.1 v_monitor_health (Trading DBs)

```sql
CREATE OR REPLACE VIEW v_monitor_health AS
SELECT 
    p.position_id,
    p.symbol,
    p.quantity,
    p.entry_price,
    p.status AS position_status,
    m.status AS monitor_status,
    m.last_check_at,
    m.check_count,
    m.high_watermark,
    m.recommendation,
    CASE 
        WHEN m.last_check_at IS NULL THEN 'NO_MONITOR'
        WHEN NOW() - m.last_check_at > INTERVAL '10 minutes' THEN 'STALE'
        WHEN m.status = 'error' THEN 'ERROR'
        ELSE 'HEALTHY'
    END AS health_status
FROM positions p
LEFT JOIN position_monitor_status m ON p.position_id = m.position_id
WHERE p.status = 'open';
```

### 4.2 v_recent_errors (Trading DBs)

```sql
CREATE OR REPLACE VIEW v_recent_errors AS
SELECT id, timestamp, level, source, message,
       context->>'symbol' AS symbol,
       context->>'tool' AS tool, error_type
FROM agent_logs
WHERE level IN ('ERROR', 'CRITICAL')
AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

### 4.3 v_agent_status (Consciousness DB)

```sql
CREATE OR REPLACE VIEW v_agent_status AS
SELECT agent_id, current_mode, status_message, last_action_at,
       api_spend_today, daily_budget,
       ROUND((api_spend_today / NULLIF(daily_budget, 0) * 100)::numeric, 1) AS budget_used_pct,
       CASE 
           WHEN last_action_at IS NULL THEN 'NEVER_ACTIVE'
           WHEN NOW() - last_action_at > INTERVAL '2 hours' THEN 'INACTIVE'
           WHEN current_mode = 'sleeping' THEN 'SLEEPING'
           ELSE 'ACTIVE'
       END AS health_status
FROM claude_state;
```

---

## PART 5: HELPER FUNCTIONS

### 5.1 get_or_create_security (Trading DBs)

```sql
CREATE OR REPLACE FUNCTION get_or_create_security(
    p_symbol VARCHAR(20),
    p_exchange VARCHAR(20) DEFAULT 'HKEX'
) RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities WHERE symbol = p_symbol AND exchange = p_exchange;
    
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange)
        VALUES (p_symbol, p_exchange)
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;
```

### 5.2 log_agent_activity (Trading DBs)

```sql
CREATE OR REPLACE FUNCTION log_agent_activity(
    p_level VARCHAR(20),
    p_source VARCHAR(100),
    p_message TEXT,
    p_context JSONB DEFAULT '{}'::jsonb,
    p_symbol VARCHAR(20) DEFAULT NULL,
    p_cycle_id VARCHAR(50) DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_log_id INTEGER;
BEGIN
    INSERT INTO agent_logs (level, source, message, context, symbol, cycle_id)
    VALUES (p_level, p_source, p_message, p_context, p_symbol, p_cycle_id)
    RETURNING id INTO v_log_id;
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;
```

### 5.3 update_agent_budget (Consciousness DB)

```sql
CREATE OR REPLACE FUNCTION update_agent_budget(
    p_agent_id VARCHAR(50),
    p_spend_amount DECIMAL(10,4)
) RETURNS VOID AS $$
BEGIN
    UPDATE claude_state
    SET api_spend_today = api_spend_today + p_spend_amount,
        api_spend_month = api_spend_month + p_spend_amount,
        updated_at = NOW()
    WHERE agent_id = p_agent_id;
END;
$$ LANGUAGE plpgsql;
```

---

## PART 6: QUICK REFERENCE

### 6.1 Table Summary by Database

| Database | Table | Purpose |
|----------|-------|---------|
| **Trading DBs** | securities | Stock registry |
| | positions | Holdings (NOT orders) |
| | orders | Order history |
| | decisions | AI decision audit |
| | scan_results | Scanner candidates |
| | trading_cycles | Session logs |
| | patterns | Technical patterns |
| | **agent_logs** | **Runtime logs (interface)** |
| | position_monitor_status | Real-time monitoring |
| | service_health | Service heartbeats |
| **Consciousness** | claude_state | Agent status/budget |
| | claude_messages | Inter-agent messages |
| | claude_observations | What agents notice |
| | claude_learnings | Validated knowledge |
| | claude_questions | Open questions |
| | claude_conversations | Key exchanges |
| | claude_thinking | Extended thinking |
| | sync_log | Sync tracking |

### 6.2 Key Constraints

| Rule | Description |
|------|-------------|
| Orders ≠ Positions | Order data ONLY in orders table |
| agent_logs interface | Trading writes, consciousness reads |
| Lot sizes | HKEX varies by stock, US always 1 |

### 6.3 Common Queries

```sql
-- Open positions
SELECT symbol, quantity, entry_price, status FROM positions WHERE status = 'open';

-- Recent errors
SELECT * FROM agent_logs WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 20;

-- Agent budgets
SELECT agent_id, api_spend_today, daily_budget FROM claude_state;

-- Pending messages
SELECT from_agent, to_agent, subject FROM claude_messages WHERE status = 'pending';

-- Validated learnings
SELECT category, learning, confidence FROM claude_learnings WHERE validated = true;

-- Position monitor health
SELECT * FROM v_monitor_health;
```

---

## APPENDIX: RELATED DOCUMENTS

| Document | Purpose |
|----------|---------|
| `catalyst-trading-system-architecture.md` | Trading system architecture |
| `consciousness-architecture.md` | Consciousness framework |
| `schema-catalyst-trading.sql` | Trading SQL file |
| `schema-consciousness.sql` | Consciousness SQL file |

---

**END OF DATABASE SCHEMA v11.0.0**

*Catalyst Trading System - Craig + The Claude Family - February 2026*
