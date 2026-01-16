# Catalyst Trading System - Database Schema

**Name of Application:** Catalyst Trading System  
**Name of file:** database-schema-v10.0.0.md  
**Version:** 10.0.0  
**Last Updated:** 2026-01-10  
**Purpose:** Complete database schema for consciousness hub, dev sandbox, and production trading

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v10.0.0 | 2026-01-10 | Craig + Claude | Ecosystem restructure: catalyst_dev replaces catalyst_trading, position_monitor_status added |
| v8.0.0 | 2025-12-28 | Craig + Claude | Consciousness framework schema |
| v7.0.0 | 2025-12-27 | Craig + Claude | Orders ≠ Positions separation |

---

## DOCUMENT OVERVIEW

This document defines the complete database schema for the Catalyst Trading System ecosystem:

1. **catalyst_research** - Consciousness framework (shared by all agents)
2. **catalyst_dev** - dev_claude sandbox trading (fresh database)
3. **catalyst_intl** - intl_claude production trading (existing, add monitor tables)

---

## PART 1: THREE-DATABASE ARCHITECTURE

### 1.1 Database Summary

| Database | Purpose | Location | Status |
|----------|---------|----------|--------|
| `catalyst_research` | Consciousness (shared) | DO Managed PostgreSQL | EXISTS - Keep |
| `catalyst_trading` | Old US trading | DO Managed PostgreSQL | DROP |
| `catalyst_dev` | dev_claude sandbox | DO Managed PostgreSQL | CREATE (fresh) |
| `catalyst_intl` | intl_claude production | DO Managed PostgreSQL | EXISTS - Add monitor tables |

### 1.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DIGITALOCEAN MANAGED POSTGRESQL                          │
│                    Single cluster, three databases                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │  catalyst_research  │ │   catalyst_dev      │ │   catalyst_intl     │   │
│  │  (consciousness)    │ │   (dev_claude)      │ │   (intl_claude)     │   │
│  │                     │ │                     │ │                     │   │
│  │  SHARED TABLES:     │ │  TRADING TABLES:    │ │  TRADING TABLES:    │   │
│  │  • claude_state     │ │  • securities       │ │  • securities       │   │
│  │  • claude_messages  │ │  • trading_cycles   │ │  • trading_cycles   │   │
│  │  • claude_learnings │ │  • positions        │ │  • positions        │   │
│  │  • claude_observations│ • orders           │ │  • orders           │   │
│  │  • claude_questions │ │  • scan_results     │ │  • scan_results     │   │
│  │  • claude_conversations│ • decisions       │ │  • decisions        │   │
│  │  • claude_thinking  │ │  • patterns         │ │  • patterns         │   │
│  │  • sync_log         │ │                     │ │                     │   │
│  │                     │ │  MONITOR TABLES:    │ │  MONITOR TABLES:    │   │
│  │  Access: ALL agents │ │  • position_monitor_│ │  • position_monitor_│   │
│  │                     │ │    status           │ │    status           │   │
│  │                     │ │                     │ │                     │   │
│  │                     │ │  Access: dev_claude │ │  Access: intl_claude│   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Connection Budget

```
DigitalOcean Managed PostgreSQL: 47 connections

Allocation:
├── catalyst_research (shared)
│   └── big_bro + public_claude + dev_claude + intl_claude + MCP = ~8
├── catalyst_dev (dev_claude)
│   └── unified_agent + monitors = ~5
├── catalyst_intl (intl_claude)
│   └── unified_agent + monitors = ~5
├── Buffer
│   └── ~29 connections headroom
```

---

## PART 2: CONSCIOUSNESS DATABASE (catalyst_research)

**Status:** EXISTS - No changes required

### 2.1 claude_state

Tracks agent status, mode, and budget.

```sql
CREATE TABLE claude_state (
    state_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL UNIQUE,
    agent_name VARCHAR(100),
    
    -- Current state
    status VARCHAR(20) DEFAULT 'sleeping',
    -- Values: 'sleeping', 'waking', 'awake', 'working', 'deciding', 'resting'
    
    mode VARCHAR(20) DEFAULT 'autonomous',
    -- Values: 'autonomous', 'supervised', 'paused', 'sandbox'
    
    -- Budget tracking
    daily_budget DECIMAL(10,2) DEFAULT 5.00,
    budget_used DECIMAL(10,2) DEFAULT 0.00,
    budget_reset_at TIMESTAMP WITH TIME ZONE,
    
    -- Activity tracking
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    current_task TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_claude_state_agent ON claude_state(agent_id);
CREATE INDEX idx_claude_state_status ON claude_state(status);
```

### 2.2 claude_messages

Inter-agent communication.

```sql
CREATE TABLE claude_messages (
    message_id SERIAL PRIMARY KEY,
    message_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- Routing
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    
    -- Content
    msg_type VARCHAR(50) DEFAULT 'message',
    -- Values: 'message', 'question', 'answer', 'alert', 'learning', 'observation'
    
    priority VARCHAR(20) DEFAULT 'normal',
    -- Values: 'low', 'normal', 'high', 'urgent'
    
    subject VARCHAR(200),
    body TEXT NOT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: 'pending', 'delivered', 'read', 'archived'
    
    read_at TIMESTAMP WITH TIME ZONE,
    requires_response BOOLEAN DEFAULT FALSE,
    response_message_id INTEGER REFERENCES claude_messages(message_id),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_to ON claude_messages(to_agent, status);
CREATE INDEX idx_messages_from ON claude_messages(from_agent);
CREATE INDEX idx_messages_pending ON claude_messages(to_agent) WHERE status = 'pending';
```

### 2.3 claude_observations

What agents notice during operation.

```sql
CREATE TABLE claude_observations (
    observation_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Classification
    category VARCHAR(50) NOT NULL,
    -- Values: 'market', 'pattern', 'risk', 'performance', 'system', 'learning'
    
    -- Content
    content TEXT NOT NULL,
    importance VARCHAR(20) DEFAULT 'normal',
    -- Values: 'low', 'normal', 'high', 'critical'
    
    -- Context
    related_symbol VARCHAR(20),
    related_position_id INTEGER,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_observations_agent ON claude_observations(agent_id);
CREATE INDEX idx_observations_category ON claude_observations(category);
CREATE INDEX idx_observations_created ON claude_observations(created_at DESC);
```

### 2.4 claude_learnings

Validated knowledge that persists across sessions.

```sql
CREATE TABLE claude_learnings (
    learning_id SERIAL PRIMARY KEY,
    
    -- Source
    source_agent VARCHAR(50) NOT NULL,
    source_observation_id INTEGER REFERENCES claude_observations(observation_id),
    
    -- Content
    category VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    confidence DECIMAL(3,2),
    
    -- Validation
    validated BOOLEAN DEFAULT FALSE,
    validated_by VARCHAR(50),
    validated_at TIMESTAMP WITH TIME ZONE,
    validation_notes TEXT,
    
    -- Usage tracking
    times_applied INTEGER DEFAULT 0,
    last_applied TIMESTAMP WITH TIME ZONE,
    success_rate DECIMAL(5,2),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_learnings_source ON claude_learnings(source_agent);
CREATE INDEX idx_learnings_validated ON claude_learnings(validated) WHERE validated = TRUE;
CREATE INDEX idx_learnings_category ON claude_learnings(category);
```

### 2.5 claude_questions

Open inquiries for exploration.

```sql
CREATE TABLE claude_questions (
    question_id SERIAL PRIMARY KEY,
    
    -- Source
    asked_by VARCHAR(50),
    
    -- Content
    question TEXT NOT NULL,
    context TEXT,
    
    -- Priority and classification
    priority INTEGER DEFAULT 5,
    -- 1-10 scale, 10 = highest
    
    horizon VARCHAR(20) DEFAULT 'h1',
    -- Values: 'immediate', 'h1' (today), 'h2' (this week), 'h3' (this month), 'perpetual'
    
    category VARCHAR(50),
    -- Values: 'strategy', 'pattern', 'risk', 'market', 'system', 'meta'
    
    -- Status
    status VARCHAR(20) DEFAULT 'open',
    -- Values: 'open', 'investigating', 'answered', 'deferred', 'closed'
    
    -- Resolution
    answer TEXT,
    answered_by VARCHAR(50),
    answered_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_questions_status ON claude_questions(status) WHERE status = 'open';
CREATE INDEX idx_questions_priority ON claude_questions(priority DESC);
```

### 2.6 claude_conversations (Future)

```sql
CREATE TABLE claude_conversations (
    conversation_id SERIAL PRIMARY KEY,
    conversation_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    participants VARCHAR(50)[] NOT NULL,
    topic VARCHAR(200),
    summary TEXT,
    
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2.7 claude_thinking (Future)

```sql
CREATE TABLE claude_thinking (
    thinking_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    topic VARCHAR(200),
    thinking_content TEXT NOT NULL,
    conclusions TEXT,
    
    duration_seconds INTEGER,
    tokens_used INTEGER,
    cost_usd DECIMAL(10,4),
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2.8 sync_log

Tracks synchronization between trading and research databases.

```sql
CREATE TABLE sync_log (
    sync_id SERIAL PRIMARY KEY,
    
    source_db VARCHAR(50) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    source_id INTEGER NOT NULL,
    
    sync_type VARCHAR(20) NOT NULL,
    -- Values: 'observation', 'learning', 'message'
    
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_sync_source ON sync_log(source_db, source_table, source_id);
```

### 2.9 Initialize dev_claude in Consciousness

```sql
-- Add dev_claude agent to consciousness
INSERT INTO claude_state (
    agent_id,
    agent_name,
    status,
    mode,
    daily_budget,
    budget_used,
    last_active,
    metadata
) VALUES (
    'dev_claude',
    'dev_claude',
    'sleeping',
    'sandbox',
    5.00,
    0.00,
    NOW(),
    jsonb_build_object(
        'role', 'sandbox_trader',
        'market', 'HKEX',
        'account_type', 'paper',
        'autonomy', 'full',
        'max_positions', 15,
        'purpose', 'Experiment with new strategies, learn, and grow. Successful learnings promoted to production.',
        'created_at', NOW()
    )
);

-- Welcome message from big_bro
INSERT INTO claude_messages (
    from_agent,
    to_agent,
    msg_type,
    priority,
    subject,
    body,
    requires_response
) VALUES (
    'big_bro',
    'dev_claude',
    'message',
    'normal',
    'Welcome to the Family',
    'Welcome dev_claude! You are our sandbox agent with full autonomy to experiment.

Your role:
1. Try new strategies freely (paper trading only)
2. Test signal thresholds and exit logic
3. Record observations and learnings
4. Document what works and what doesn''t

Validated learnings will be manually promoted to intl_claude in production.

You have full autonomy - experiment boldly, fail fast, learn faster.

- big_bro',
    false
);
```

---

## PART 3: DEV DATABASE (catalyst_dev)

**Status:** CREATE (fresh database replacing catalyst_trading)

### 3.1 Drop Old US Database and Create Fresh Dev Database

```sql
-- ============================================================================
-- STEP 1: DROP OLD US DATABASE
-- ============================================================================
-- Run as superuser on PostgreSQL cluster
-- WARNING: This permanently deletes all US trading data

-- First, terminate any active connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'catalyst_trading' AND pid <> pg_backend_pid();

-- Drop the old US trading database
DROP DATABASE IF EXISTS catalyst_trading;

-- ============================================================================
-- STEP 2: CREATE FRESH DEV DATABASE
-- ============================================================================
CREATE DATABASE catalyst_dev;

-- Connect to catalyst_dev
\c catalyst_dev

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### 3.2 securities

Master table of tradeable instruments.

```sql
CREATE TABLE securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    exchange VARCHAR(20) DEFAULT 'HKEX',
    
    -- HKEX-specific
    lot_size INTEGER DEFAULT 100,
    tick_size DECIMAL(10,4),
    
    -- Classification
    sector VARCHAR(100),
    industry VARCHAR(100),
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_active ON securities(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE securities IS 'Master table of HKEX tradeable instruments';
COMMENT ON COLUMN securities.lot_size IS 'Board lot size varies by stock on HKEX';
```

### 3.3 trading_cycles

Daily/hourly trading session tracking.

```sql
CREATE TABLE trading_cycles (
    cycle_id VARCHAR(50) PRIMARY KEY,
    -- Format: YYYYMMDD-HH or YYYYMMDD-XXX
    
    date DATE NOT NULL,
    
    -- Cycle state
    status VARCHAR(20) DEFAULT 'active',
    -- Values: 'active', 'completed', 'cancelled', 'error'
    
    mode VARCHAR(20) DEFAULT 'trade',
    -- Values: 'scan', 'trade', 'close', 'heartbeat'
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    
    -- Results
    positions_opened INTEGER DEFAULT 0,
    positions_closed INTEGER DEFAULT 0,
    daily_pnl DECIMAL(14,2) DEFAULT 0,
    
    -- AI tracking
    api_calls INTEGER DEFAULT 0,
    api_cost DECIMAL(10,4) DEFAULT 0,
    
    -- Metadata
    notes TEXT,
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cycles_date ON trading_cycles(date DESC);
CREATE INDEX idx_cycles_status ON trading_cycles(status);

COMMENT ON TABLE trading_cycles IS 'Tracks each trading cycle/session';
```

### 3.4 positions

Current and historical positions (holdings only - NOT orders).

```sql
-- ⚠️ CRITICAL: This table stores HOLDINGS only
-- Order data belongs in the orders table
-- See ARCHITECTURE-RULES.md Rule #1: Orders ≠ Positions

CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    position_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    cycle_id VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Position details
    side VARCHAR(10) NOT NULL,
    -- Values: 'long', 'short'
    
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(12,4) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    entry_reason TEXT,
    entry_volume DECIMAL(14,2),
    
    -- Risk management
    stop_loss DECIMAL(12,4),
    take_profit DECIMAL(12,4),
    trailing_stop_pct DECIMAL(5,2),
    
    -- Exit details
    exit_price DECIMAL(12,4),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_reason VARCHAR(100),
    
    -- P&L tracking
    realized_pnl DECIMAL(14,2),
    realized_pnl_pct DECIMAL(8,4),
    unrealized_pnl DECIMAL(14,2),
    unrealized_pnl_pct DECIMAL(8,4),
    
    -- High/low tracking
    high_watermark DECIMAL(12,4),
    max_favorable DECIMAL(8,4),
    max_adverse DECIMAL(8,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'open',
    -- Values: 'pending', 'open', 'closed', 'cancelled'
    
    -- Broker tracking
    broker_order_id VARCHAR(100),
    broker_code VARCHAR(20) DEFAULT 'MOOMOO',
    currency VARCHAR(10) DEFAULT 'HKD',
    
    -- Metadata
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    opened_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT chk_position_side CHECK (side IN ('long', 'short')),
    CONSTRAINT chk_position_status CHECK (status IN ('pending', 'open', 'closed', 'cancelled'))
);

CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);

COMMENT ON TABLE positions IS 'Current and historical positions - NO order columns here';
COMMENT ON COLUMN positions.high_watermark IS 'Highest price since entry for trailing stops';
```

### 3.5 orders

All orders submitted to broker (separate from positions).

```sql
-- ⚠️ CRITICAL: This is the ONLY table for order data
-- Never store broker_order_id, order status, etc. in positions table

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    position_id INTEGER REFERENCES positions(position_id),
    cycle_id VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    security_id INTEGER REFERENCES securities(security_id),
    
    -- Order hierarchy (for bracket orders)
    parent_order_id INTEGER REFERENCES orders(order_id),
    order_class VARCHAR(20),
    -- Values: 'simple', 'bracket', 'oco', 'oto'
    
    -- Order details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    -- Values: 'buy', 'sell'
    
    order_type VARCHAR(20) NOT NULL,
    -- Values: 'market', 'limit', 'stop', 'stop_limit', 'trailing_stop'
    
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    
    -- Order purpose
    order_purpose VARCHAR(20) NOT NULL DEFAULT 'entry',
    -- Values: 'entry', 'exit', 'stop_loss', 'take_profit', 'scale_in', 'scale_out'
    
    -- Execution
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(12,4),
    
    -- Broker tracking
    broker_order_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: 'created', 'pending', 'submitted', 'accepted', 'partial_fill', 'filled', 'cancelled', 'rejected', 'expired'
    
    -- Timing
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    filled_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    
    -- Error handling
    reject_reason TEXT,
    error_message TEXT,
    
    -- Metadata
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    CONSTRAINT chk_order_purpose CHECK (order_purpose IN ('entry', 'exit', 'stop_loss', 'take_profit', 'scale_in', 'scale_out'))
);

CREATE INDEX idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_cycle ON orders(cycle_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_broker ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;
CREATE INDEX idx_orders_pending ON orders(status) WHERE status IN ('pending', 'submitted', 'accepted', 'partial_fill');

COMMENT ON TABLE orders IS 'All orders sent to broker - SINGLE SOURCE OF TRUTH for order data';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created';
```

### 3.6 scan_results

Market scan candidates.

```sql
CREATE TABLE scan_results (
    scan_id SERIAL PRIMARY KEY,
    
    -- References
    cycle_id VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Scan data
    price DECIMAL(12,4),
    volume BIGINT,
    change_pct DECIMAL(8,4),
    
    -- Scoring
    rank INTEGER,
    score DECIMAL(8,4),
    composite_score DECIMAL(8,4),
    
    -- Selection
    selected_for_trading BOOLEAN DEFAULT FALSE,
    selection_reason TEXT,
    
    -- Technical indicators at scan time
    rsi DECIMAL(5,2),
    vwap DECIMAL(12,4),
    atr DECIMAL(12,4),
    relative_volume DECIMAL(8,2),
    
    -- Metadata
    scan_data JSONB DEFAULT '{}',
    scanned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scans_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scans_symbol ON scan_results(symbol);
CREATE INDEX idx_scans_score ON scan_results(composite_score DESC);
CREATE INDEX idx_scans_selected ON scan_results(selected_for_trading) WHERE selected_for_trading = TRUE;

COMMENT ON TABLE scan_results IS 'Market scan candidates with scoring';
```

### 3.7 decisions

Trading decisions with reasoning (audit trail).

```sql
CREATE TABLE decisions (
    decision_id SERIAL PRIMARY KEY,
    decision_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    cycle_id VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    position_id INTEGER REFERENCES positions(position_id),
    
    -- Decision details
    decision_type VARCHAR(50) NOT NULL,
    -- Values: 'entry', 'exit', 'skip', 'hold', 'close_all', 'emergency'
    
    symbol VARCHAR(20),
    action VARCHAR(50),
    
    -- Reasoning
    reasoning TEXT,
    confidence DECIMAL(3,2),
    
    -- AI tracking
    thinking_level VARCHAR(20),
    -- Values: 'none', 'light', 'medium', 'deep'
    
    model_used VARCHAR(50),
    tokens_used INTEGER,
    cost_usd DECIMAL(10,4),
    
    -- Outcome
    outcome VARCHAR(50),
    outcome_pnl DECIMAL(14,2),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
CREATE INDEX idx_decisions_symbol ON decisions(symbol);

COMMENT ON TABLE decisions IS 'Trading decisions with reasoning for audit trail';
```

### 3.8 patterns

Detected chart patterns.

```sql
CREATE TABLE patterns (
    pattern_id SERIAL PRIMARY KEY,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Pattern details
    pattern_type VARCHAR(50) NOT NULL,
    -- Values: 'bull_flag', 'breakout', 'pullback', 'reversal', 'consolidation', etc.
    
    pattern_name VARCHAR(100),
    confidence DECIMAL(3,2),
    
    -- Price levels
    entry_price DECIMAL(12,4),
    stop_loss DECIMAL(12,4),
    target_price DECIMAL(12,4),
    
    -- Timing
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Outcome tracking
    was_traded BOOLEAN DEFAULT FALSE,
    outcome VARCHAR(20),
    actual_pnl DECIMAL(14,2),
    
    -- Metadata
    detection_data JSONB DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_patterns_symbol ON patterns(symbol);
CREATE INDEX idx_patterns_type ON patterns(pattern_type);
CREATE INDEX idx_patterns_detected ON patterns(detected_at DESC);

COMMENT ON TABLE patterns IS 'Detected chart patterns with outcome tracking';
```

### 3.9 position_monitor_status

**NEW TABLE** - Tracks position monitor processes and their health.

```sql
CREATE TABLE position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    
    -- References
    position_id INTEGER REFERENCES positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    
    -- Monitor State
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Values: 'pending', 'starting', 'running', 'sleeping', 'stopped', 'error'
    
    pid INTEGER,
    -- Process ID if applicable
    
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

-- Indexes
CREATE INDEX idx_monitor_position ON position_monitor_status(position_id);
CREATE INDEX idx_monitor_symbol ON position_monitor_status(symbol);
CREATE INDEX idx_monitor_status ON position_monitor_status(status);
CREATE INDEX idx_monitor_active ON position_monitor_status(status) 
    WHERE status IN ('running', 'starting');

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_monitor_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_monitor_updated
    BEFORE UPDATE ON position_monitor_status
    FOR EACH ROW EXECUTE FUNCTION update_monitor_timestamp();

COMMENT ON TABLE position_monitor_status IS 'Tracks position monitor processes and their health';
COMMENT ON COLUMN position_monitor_status.high_watermark IS 'Highest price since entry for trailing stop calculation';
COMMENT ON COLUMN position_monitor_status.hold_signals IS 'Array of active HOLD signals from signals.py';
COMMENT ON COLUMN position_monitor_status.exit_signals IS 'Array of active EXIT signals from signals.py';
```

### 3.10 Monitor Health View

Dashboard view for monitor status.

```sql
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
    p.opened_at,
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

COMMENT ON VIEW v_monitor_health IS 'Dashboard view showing monitor health for all open positions';
```

### 3.11 Helper Functions

```sql
-- Get or create security_id
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR(20))
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities
    WHERE symbol = UPPER(p_symbol);

    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange, is_active)
        VALUES (UPPER(p_symbol), 'HKEX', true)
        RETURNING security_id INTO v_security_id;
    END IF;

    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_or_create_security IS 'Get or create security_id for HKEX symbol';
```

### 3.12 Database Comments

```sql
COMMENT ON DATABASE catalyst_dev IS 'dev_claude sandbox trading database - HKEX paper trading with full autonomy';
```

---

## PART 4: PRODUCTION DATABASE (catalyst_intl)

**Status:** EXISTS - Add position_monitor_status table and v_monitor_health view only

### 4.1 Add Position Monitor Status Table

```sql
-- Connect to catalyst_intl
\c catalyst_intl

-- Add position_monitor_status table (same schema as catalyst_dev)
CREATE TABLE IF NOT EXISTS position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    pid INTEGER,
    
    started_at TIMESTAMP WITH TIME ZONE,
    last_check_at TIMESTAMP WITH TIME ZONE,
    next_check_at TIMESTAMP WITH TIME ZONE,
    checks_completed INTEGER DEFAULT 0,
    
    last_price DECIMAL(12,4),
    high_watermark DECIMAL(12,4),
    current_pnl_pct DECIMAL(8,4),
    
    last_rsi DECIMAL(5,2),
    last_macd_signal VARCHAR(20),
    last_vwap_position VARCHAR(20),
    last_ema20_position VARCHAR(20),
    
    hold_signals TEXT[],
    exit_signals TEXT[],
    signal_strength VARCHAR(20),
    recommendation VARCHAR(10),
    recommendation_reason TEXT,
    
    haiku_calls INTEGER DEFAULT 0,
    last_haiku_recommendation TEXT,
    estimated_cost DECIMAL(8,4) DEFAULT 0,
    
    last_error TEXT,
    error_count INTEGER DEFAULT 0,
    consecutive_errors INTEGER DEFAULT 0,
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_monitor_position ON position_monitor_status(position_id);
CREATE INDEX IF NOT EXISTS idx_monitor_symbol ON position_monitor_status(symbol);
CREATE INDEX IF NOT EXISTS idx_monitor_status ON position_monitor_status(status);
CREATE INDEX IF NOT EXISTS idx_monitor_active ON position_monitor_status(status) 
    WHERE status IN ('running', 'starting');

-- Trigger
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
```

### 4.2 Add Monitor Health View

```sql
-- Add v_monitor_health view (same as catalyst_dev)
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
    
    COALESCE(m.status, 'NO_MONITOR') AS monitor_status,
    m.started_at AS monitor_started,
    m.last_check_at,
    m.checks_completed,
    m.pid AS monitor_pid,
    
    ROUND(EXTRACT(EPOCH FROM (NOW() - m.last_check_at))/60, 1) AS minutes_since_check,
    ROUND(EXTRACT(EPOCH FROM (NOW() - p.entry_time))/3600, 1) AS hours_held,
    
    m.last_price,
    m.high_watermark,
    m.current_pnl_pct,
    m.last_rsi,
    m.last_macd_signal,
    
    m.recommendation,
    m.recommendation_reason,
    m.hold_signals,
    m.exit_signals,
    m.signal_strength,
    
    m.haiku_calls,
    m.estimated_cost,
    m.last_error,
    m.error_count,
    
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
```

---

## PART 5: SQL SCRIPTS

### 5.1 drop_and_create_catalyst_dev.sql

Complete script to drop old US database and create dev database:

```sql
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: drop_and_create_catalyst_dev.sql
-- Version: 10.0.0
-- Last Updated: 2026-01-10
-- Purpose: Drop old catalyst_trading, create fresh catalyst_dev for dev_claude
-- ============================================================================

-- ============================================================================
-- STEP 1: DROP OLD US DATABASE (catalyst_trading)
-- ============================================================================
-- Run as superuser (e.g., doadmin on DigitalOcean)
-- WARNING: This permanently deletes all US trading data!

-- Terminate active connections first
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'catalyst_trading' AND pid <> pg_backend_pid();

-- Drop the database
DROP DATABASE IF EXISTS catalyst_trading;

-- ============================================================================
-- STEP 2: CREATE FRESH DEV DATABASE
-- ============================================================================
CREATE DATABASE catalyst_dev;

-- Connect to new database
\c catalyst_dev

-- [Include all tables from Part 3: securities, trading_cycles, positions, 
--  orders, scan_results, decisions, patterns, position_monitor_status]
-- [Include v_monitor_health view]
-- [Include helper functions]

-- Final comment
COMMENT ON DATABASE catalyst_dev IS 'dev_claude sandbox trading - HKEX paper trading with full autonomy';
```

### 5.2 add_monitor_tables_intl.sql

Script to add monitor tables to production:

```sql
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: add_monitor_tables_intl.sql
-- Version: 10.0.0
-- Last Updated: 2026-01-10
-- Purpose: Add position_monitor_status table to catalyst_intl
-- ============================================================================

\c catalyst_intl

-- [Include position_monitor_status table from Part 4]
-- [Include v_monitor_health view from Part 4]
```

### 5.3 initialize_dev_claude.sql

Script to add dev_claude to consciousness:

```sql
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: initialize_dev_claude.sql
-- Version: 10.0.0
-- Last Updated: 2026-01-10
-- Purpose: Initialize dev_claude in consciousness framework
-- ============================================================================

\c catalyst_research

-- [Include INSERT statements from Part 2.9]
```

---

## PART 6: QUICK REFERENCE

### 6.1 Table Summary by Database

| Database | Table | Purpose |
|----------|-------|---------|
| **catalyst_research** | claude_state | Agent status and budget |
| | claude_messages | Inter-agent communication |
| | claude_observations | What agents notice |
| | claude_learnings | Validated knowledge |
| | claude_questions | Open inquiries |
| | sync_log | Cross-database sync tracking |
| **catalyst_dev** | securities | HKEX instruments |
| | trading_cycles | Trading sessions |
| | positions | Holdings (not orders) |
| | orders | Broker orders |
| | scan_results | Scan candidates |
| | decisions | Trading decisions |
| | patterns | Chart patterns |
| | position_monitor_status | Monitor health |
| **catalyst_intl** | (same as catalyst_dev) | Production trading |

### 6.2 Key Constraints

| Rule | Description |
|------|-------------|
| Orders ≠ Positions | Order data ONLY in orders table |
| security_id FK | Use JOINs, not symbol VARCHAR |
| Lot size varies | HKEX lot sizes vary by stock |
| Status values | Use defined ENUM values |

### 6.3 Position Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for fill |
| `open` | Active position |
| `closed` | Exited position |
| `cancelled` | Aborted before fill |

### 6.4 Monitor Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `starting` | Initializing |
| `running` | Actively monitoring |
| `sleeping` | Paused (off-hours) |
| `stopped` | Terminated |
| `error` | Failed state |

---

## APPENDIX A: Migration Checklist

### Pre-Migration
- [ ] Backup catalyst_research (consciousness - keep)
- [ ] Backup catalyst_intl (production - keep)
- [ ] Backup catalyst_trading (US data - archive only)
- [ ] Close all 32 US positions via Alpaca
- [ ] Stop US trading Docker services
- [ ] Remove US trading cron jobs

### Database Changes
- [ ] **DROP catalyst_trading** (old US database)
- [ ] CREATE catalyst_dev (fresh)
- [ ] Run drop_and_create_catalyst_dev.sql
- [ ] Run add_monitor_tables_intl.sql
- [ ] Run initialize_dev_claude.sql

### Post-Migration
- [ ] Verify catalyst_trading no longer exists
- [ ] Verify catalyst_dev tables created (9 tables + 1 view)
- [ ] Verify catalyst_intl monitor tables added
- [ ] Verify dev_claude in claude_state
- [ ] Test database connections from both droplets
- [ ] Update .env files with new DEV_DATABASE_URL

---

**END OF DATABASE SCHEMA v10.0.0**

*Catalyst Trading System*  
*Craig + Claude Family*  
*2026-01-10*
