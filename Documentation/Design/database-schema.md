# Catalyst Trading System — Database Schema

**Name of Application:** Catalyst Trading System
**Name of file:** database-schema.md
**Version:** 13.0.0
**Last Updated:** 2026-04-04
**Purpose:** Complete database schema for all Catalyst databases — extracted from live PostgreSQL
**Source:** Live `\d+` output from catalyst_dev and catalyst_research (2026-04-04)

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v13.0.0 | 2026-04-04 | Craig + Claude | Full rewrite from live schema. Added pattern_outcomes, pattern_confidence, signals. Fixed trading_cycles PK (varchar not serial). Corrected positions columns. Added row counts. Documented leftover functions. |
| v12.0.0 | 2026-02-07 | Craig + Claude | Multi-agent MCP: added agent_decisions, position_monitor_status |
| v11.0.0 | 2026-02-01 | Craig + Claude | Major consolidation — Trading/Consciousness separation |
| v10.0.0 | 2026-01-10 | Craig + Claude | Three-database architecture |

---

## TABLE OF CONTENTS

1. [Schema Overview](#part-1-schema-overview)
2. [Trading Database Schema (catalyst_dev)](#part-2-trading-database-schema)
3. [Consciousness Database Schema (catalyst_research)](#part-3-consciousness-database-schema)
4. [Helper Functions](#part-4-helper-functions)
5. [Architecture Rules](#part-5-architecture-rules)
6. [Row Counts](#part-6-row-counts)
7. [Quick Reference](#part-7-quick-reference)

---

## PART 1: SCHEMA OVERVIEW

### 1.1 Design Philosophy

```yaml
Normalization: 3NF (Third Normal Form)
Key Principle: Orders ≠ Positions (critical architectural rule)
Separation: Trading databases vs Consciousness database
Observability: agent_logs table in every trading database
FK Chains: trading_cycles → positions/orders/scan_results/decisions
Learning: pattern_outcomes → pattern_confidence (LTP/LTD)
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
│  │  TRADING:           │ │  TRADING:           │ │  CONSCIOUSNESS:     │   │
│  │  • trading_cycles   │ │  • trading_cycles   │ │  • claude_state     │   │
│  │  • positions        │ │  • positions        │ │  • claude_messages  │   │
│  │  • orders           │ │  • orders           │ │  • claude_learnings │   │
│  │  • decisions        │ │  • decisions        │ │  • claude_          │   │
│  │  • scan_results     │ │  • scan_results     │ │    observations     │   │
│  │  • patterns         │ │  • patterns         │ │  • claude_questions │   │
│  │                     │ │                     │ │  • claude_          │   │
│  │  LEARNING:          │ │  LEARNING:          │ │    conversations    │   │
│  │  • pattern_outcomes │ │  • pattern_outcomes │ │  • claude_thinking  │   │
│  │  • pattern_confid.  │ │  • pattern_confid.  │ │  • claude_reports   │   │
│  │                     │ │                     │ │  • sync_log         │   │
│  │  SIGNALS:           │ │  SIGNALS:           │ │                     │   │
│  │  • signals          │ │  • signals          │ │                     │   │
│  │                     │ │                     │ │                     │   │
│  │  MONITORING:        │ │  MONITORING:        │ │                     │   │
│  │  • position_monitor │ │  • position_monitor │ │                     │   │
│  │  • agent_logs       │ │  • agent_logs       │ │                     │   │
│  │  • claude_state     │ │  • claude_state     │ │                     │   │
│  │                     │ │                     │ │                     │   │
│  │  Market: US         │ │  Market: HKEX       │ │  Access: ALL agents │   │
│  │  Broker: Alpaca     │ │  Broker: Moomoo     │ │                     │   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│                                                                             │
│  Environment Variables:                                                     │
│  $DATABASE_URL         $INTL_DATABASE_URL      $RESEARCH_DATABASE_URL      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 FK Dependency Chain

```
trading_cycles (root)
├── positions      (cycle_id FK)
│   ├── orders           (position_id FK)
│   ├── decisions        (position_id FK)
│   ├── pattern_outcomes (position_id FK)
│   └── position_monitor_status (position_id FK)
├── orders         (cycle_id FK)
├── decisions      (cycle_id FK)
└── scan_results   (cycle_id FK)

securities (dimension)
├── positions      (security_id FK)
├── orders         (security_id FK)
└── scan_results   (security_id FK)
```

---

## PART 2: TRADING DATABASE SCHEMA

Database: **catalyst_dev** (also applies to catalyst_intl with different defaults)
Extensions: pgcrypto 1.3, plpgsql 1.0, uuid-ossp 1.1

### 2.1 securities

Stock registry — central dimension table. All fact tables can FK to this.

```sql
CREATE TABLE securities (
    security_id    SERIAL PRIMARY KEY,
    symbol         VARCHAR(20) NOT NULL,
    name           VARCHAR(255),
    exchange       VARCHAR(20) DEFAULT 'HKEX',  -- NOTE: default is HKEX (legacy)
    lot_size       INTEGER DEFAULT 100,
    tick_size      NUMERIC(10,4),
    sector         VARCHAR(100),
    industry       VARCHAR(100),
    is_active      BOOLEAN DEFAULT true,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX ON securities(symbol);
CREATE INDEX idx_securities_symbol ON securities(symbol);
```

**Notes:**
- `exchange` defaults to 'HKEX' — for US symbols, code should set 'NYSE' or 'NASDAQ'
- Currently only 0 rows in catalyst_dev (symbols not auto-registered yet)

---

### 2.2 trading_cycles

Trading session lifecycle. Root of the FK chain — positions, orders, decisions, scan_results all reference this.

```sql
CREATE TABLE trading_cycles (
    cycle_id         VARCHAR(50) PRIMARY KEY,   -- format: YYYYMMDD-HHMMSS
    date             DATE NOT NULL,
    status           VARCHAR(20) DEFAULT 'active',   -- active, completed, failed
    mode             VARCHAR(20) DEFAULT 'trade',    -- scan, trade, close, heartbeat
    started_at       TIMESTAMPTZ DEFAULT NOW(),
    ended_at         TIMESTAMPTZ,
    positions_opened INTEGER DEFAULT 0,
    positions_closed INTEGER DEFAULT 0,
    daily_pnl        NUMERIC(14,2) DEFAULT 0,
    api_calls        INTEGER DEFAULT 0,
    api_cost         NUMERIC(10,4) DEFAULT 0,
    notes            TEXT,
    configuration    JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_cycles_date ON trading_cycles(date DESC);
CREATE INDEX idx_cycles_status ON trading_cycles(status);
```

**Notes:**
- PK is VARCHAR(50), not SERIAL — cycle_id is generated as datetime string
- INSERT at cycle start, UPDATE at cycle end with stats
- Referenced by: decisions, orders, positions, scan_results

---

### 2.3 positions

Trade journal — open and closed positions. **NOT orders** (see orders table).

```sql
CREATE TABLE positions (
    position_id      SERIAL PRIMARY KEY,
    position_uuid    UUID DEFAULT gen_random_uuid() UNIQUE,
    cycle_id         VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    security_id      INTEGER REFERENCES securities(security_id),
    symbol           VARCHAR(20) NOT NULL,
    side             VARCHAR(10) NOT NULL,       -- CHECK: long, short
    quantity         INTEGER NOT NULL,
    entry_price      NUMERIC(12,4) NOT NULL,
    entry_time       TIMESTAMPTZ DEFAULT NOW(),
    entry_reason     TEXT,
    entry_volume     NUMERIC(14,2),
    stop_loss        NUMERIC(12,4),
    take_profit      NUMERIC(12,4),
    trailing_stop_pct NUMERIC(5,2),
    exit_price       NUMERIC(12,4),
    exit_time        TIMESTAMPTZ,
    exit_reason      VARCHAR(100),
    realized_pnl     NUMERIC(14,2),
    realized_pnl_pct NUMERIC(8,4),
    unrealized_pnl   NUMERIC(14,2),
    unrealized_pnl_pct NUMERIC(8,4),
    high_watermark   NUMERIC(12,4),
    max_favorable    NUMERIC(8,4),
    max_adverse      NUMERIC(8,4),
    status           VARCHAR(20) DEFAULT 'open', -- CHECK: pending, open, closed, cancelled
    broker_order_id  VARCHAR(100),
    broker_code      VARCHAR(20) DEFAULT 'MOOMOO',  -- US agent must set 'ALPACA'
    currency         VARCHAR(10) DEFAULT 'HKD',     -- US agent must set 'USD'
    notes            TEXT,
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    opened_at        TIMESTAMPTZ,
    closed_at        TIMESTAMPTZ
);

-- Check constraints
ALTER TABLE positions ADD CONSTRAINT chk_position_side
    CHECK (side IN ('long', 'short'));
ALTER TABLE positions ADD CONSTRAINT chk_position_status
    CHECK (status IN ('pending', 'open', 'closed', 'cancelled'));

-- Trigger
CREATE TRIGGER trg_positions_updated
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Indexes
CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_symbol ON positions(symbol);
```

**CRITICAL NOTES:**
- `side` uses **long/short** (not buy/sell — that's the orders table)
- `broker_code` defaults to 'MOOMOO' and `currency` to 'HKD' (HKEX legacy). dev_claude v3.3.0 explicitly sets 'ALPACA' and 'USD'.
- `broker_order_id` is the column name (not `broker_position_id`)
- Referenced by: decisions, orders, pattern_outcomes, position_monitor_status

---

### 2.4 orders

Order audit trail. **SEPARATE from positions** — this is Architecture Rule #1.

```sql
CREATE TABLE orders (
    order_id         SERIAL PRIMARY KEY,
    order_uuid       UUID DEFAULT gen_random_uuid() UNIQUE,
    position_id      INTEGER REFERENCES positions(position_id),
    cycle_id         VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    security_id      INTEGER REFERENCES securities(security_id),
    parent_order_id  INTEGER REFERENCES orders(order_id),  -- self-referential
    order_class      VARCHAR(20),
    symbol           VARCHAR(20) NOT NULL,
    side             VARCHAR(10) NOT NULL,        -- CHECK: buy, sell
    order_type       VARCHAR(20) NOT NULL,        -- CHECK: market, limit, stop, stop_limit, trailing_stop
    quantity         INTEGER NOT NULL,
    limit_price      NUMERIC(12,4),
    stop_price       NUMERIC(12,4),
    order_purpose    VARCHAR(20) NOT NULL DEFAULT 'entry',  -- CHECK: entry, exit, stop_loss, take_profit, scale_in, scale_out
    filled_quantity  INTEGER DEFAULT 0,
    filled_price     NUMERIC(12,4),
    broker_order_id  VARCHAR(100),
    status           VARCHAR(20) DEFAULT 'pending',
    submitted_at     TIMESTAMPTZ DEFAULT NOW(),
    filled_at        TIMESTAMPTZ,
    cancelled_at     TIMESTAMPTZ,
    reject_reason    TEXT,
    error_message    TEXT,
    notes            TEXT,
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Check constraints
ALTER TABLE orders ADD CONSTRAINT chk_order_side
    CHECK (side IN ('buy', 'sell'));
ALTER TABLE orders ADD CONSTRAINT chk_order_type
    CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop'));
ALTER TABLE orders ADD CONSTRAINT chk_order_purpose
    CHECK (order_purpose IN ('entry', 'exit', 'stop_loss', 'take_profit', 'scale_in', 'scale_out'));

-- Trigger
CREATE TRIGGER trg_orders_updated
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Indexes
CREATE INDEX idx_orders_broker ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;
CREATE INDEX idx_orders_cycle ON orders(cycle_id);
CREATE INDEX idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_symbol ON orders(symbol);
```

**CRITICAL NOTES:**
- `side` uses **buy/sell** (not long/short — that's the positions table)
- The `_normalize_side()` function maps: long→buy, short→sell, buy→buy, sell→sell

---

### 2.5 decisions

AI decision audit trail — every decision Claude makes is recorded here.

```sql
CREATE TABLE decisions (
    decision_id      SERIAL PRIMARY KEY,
    decision_uuid    UUID DEFAULT gen_random_uuid() UNIQUE,
    cycle_id         VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    position_id      INTEGER REFERENCES positions(position_id),
    decision_type    VARCHAR(50) NOT NULL,       -- scan, entry, exit, hold, skip
    symbol           VARCHAR(20),
    action           VARCHAR(50),                -- buy, sell, hold, close
    reasoning        TEXT,
    confidence       NUMERIC(3,2),
    thinking_level   VARCHAR(20),
    model_used       VARCHAR(50),
    tokens_used      INTEGER,
    cost_usd         NUMERIC(10,4),
    outcome          VARCHAR(50),
    outcome_pnl      NUMERIC(14,2),
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX idx_decisions_symbol ON decisions(symbol);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
```

---

### 2.6 scan_results

Scanner output — trading candidates persisted per scan cycle.

```sql
CREATE TABLE scan_results (
    scan_id              SERIAL PRIMARY KEY,
    cycle_id             VARCHAR(50) REFERENCES trading_cycles(cycle_id),
    security_id          INTEGER REFERENCES securities(security_id),
    symbol               VARCHAR(20) NOT NULL,
    price                NUMERIC(12,4),
    volume               BIGINT,
    change_pct           NUMERIC(8,4),
    rank                 INTEGER,
    score                NUMERIC(8,4),
    composite_score      NUMERIC(8,4),
    selected_for_trading BOOLEAN DEFAULT false,
    selection_reason     TEXT,
    rsi                  NUMERIC(5,2),
    vwap                 NUMERIC(12,4),
    atr                  NUMERIC(12,4),
    relative_volume      NUMERIC(8,2),
    scan_data            JSONB DEFAULT '{}',    -- tier, direction, spread_pct
    scanned_at           TIMESTAMPTZ DEFAULT NOW(),
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_scans_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scans_score ON scan_results(composite_score DESC);
CREATE INDEX idx_scans_symbol ON scan_results(symbol);
```

**Notes:**
- `scan_data` JSONB stores adaptive tier info: `{"tier": 1, "direction": "bullish", "spread_pct": 0.01}`
- `selected_for_trading` = true for top 3 candidates by momentum score

---

### 2.7 patterns

Detected technical patterns.

```sql
CREATE TABLE patterns (
    pattern_id       SERIAL PRIMARY KEY,
    security_id      INTEGER REFERENCES securities(security_id),
    symbol           VARCHAR(20) NOT NULL,
    pattern_type     VARCHAR(50) NOT NULL,       -- bull_flag, breakout, momentum, etc.
    pattern_name     VARCHAR(100),
    confidence       NUMERIC(3,2),
    entry_price      NUMERIC(12,4),
    stop_loss        NUMERIC(12,4),
    target_price     NUMERIC(12,4),
    detected_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at       TIMESTAMPTZ,
    was_traded       BOOLEAN DEFAULT false,
    outcome          VARCHAR(20),                -- win, loss, scratch
    actual_pnl       NUMERIC(14,2),
    detection_data   JSONB DEFAULT '{}',
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_patterns_detected ON patterns(detected_at DESC);
CREATE INDEX idx_patterns_symbol ON patterns(symbol);
CREATE INDEX idx_patterns_type ON patterns(pattern_type);
```

---

### 2.8 pattern_confidence

Synaptic weights — updated by LTP/LTD learning loop after each trade outcome.

```sql
CREATE TABLE pattern_confidence (
    id               SERIAL PRIMARY KEY,
    pattern_type     VARCHAR(50) NOT NULL UNIQUE,
    confidence       NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    sample_count     INTEGER NOT NULL DEFAULT 0,
    win_count        INTEGER NOT NULL DEFAULT 0,
    loss_count       INTEGER NOT NULL DEFAULT 0,
    avg_win_pct      NUMERIC(8,4),
    avg_loss_pct     NUMERIC(8,4),
    last_updated     TIMESTAMPTZ DEFAULT NOW(),
    notes            TEXT
);
```

**Seeded patterns (10):**
bull_flag, bear_flag, breakout, momentum, double_bottom, cup_handle, ascending_triangle, vwap_reclaim, gap_and_go, news_catalyst

**LTP/LTD update rules (dev_claude v3.3.0):**
- Win: `confidence += 0.05` (capped at 0.95)
- Loss: `confidence -= 0.03` (floored at 0.10)
- Running averages maintained for avg_win_pct and avg_loss_pct

---

### 2.9 pattern_outcomes

Trade outcome per pattern — the raw data that feeds LTP/LTD learning.

```sql
CREATE TABLE pattern_outcomes (
    id                SERIAL PRIMARY KEY,
    pattern_type      VARCHAR(50) NOT NULL,
    setup_quality     VARCHAR(20),
    entry_signals     JSONB,
    symbol            VARCHAR(20) NOT NULL,
    position_id       INTEGER REFERENCES positions(position_id),
    entry_time        TIMESTAMPTZ NOT NULL,
    exit_time         TIMESTAMPTZ,
    pnl_pct           NUMERIC(8,4),
    pnl_usd           NUMERIC(10,2),
    outcome           VARCHAR(10),               -- win, loss
    exit_trigger      VARCHAR(50),               -- stop_loss, take_profit, eod_close, signal, manual
    confidence_before NUMERIC(5,4) DEFAULT 0.5,
    confidence_after  NUMERIC(5,4),
    strength_delta    NUMERIC(5,4),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_pattern_outcomes_outcome ON pattern_outcomes(outcome);
CREATE INDEX idx_pattern_outcomes_time ON pattern_outcomes(entry_time DESC);
CREATE INDEX idx_pattern_outcomes_type ON pattern_outcomes(pattern_type);
```

---

### 2.10 signals

Signal bus for inter-component communication (broadcast model).

```sql
CREATE TABLE signals (
    id               SERIAL PRIMARY KEY,
    severity         VARCHAR(10) NOT NULL,       -- CHECK: CRITICAL, WARNING, INFO, OBSERVE
    domain           VARCHAR(12) NOT NULL,       -- CHECK: HEALTH, TRADING, RISK, LEARNING, DIRECTION, LIFECYCLE
    scope            VARCHAR(60) NOT NULL,
    source           VARCHAR(50) NOT NULL,
    content          TEXT NOT NULL,
    data             JSONB,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at       TIMESTAMPTZ,
    acknowledged_by  JSONB DEFAULT '[]',
    resolved         BOOLEAN DEFAULT false
);

-- Check constraints
ALTER TABLE signals ADD CONSTRAINT signals_severity_check
    CHECK (severity IN ('CRITICAL', 'WARNING', 'INFO', 'OBSERVE'));
ALTER TABLE signals ADD CONSTRAINT signals_domain_check
    CHECK (domain IN ('HEALTH', 'TRADING', 'RISK', 'LEARNING', 'DIRECTION', 'LIFECYCLE'));

-- Indexes
CREATE INDEX idx_signals_active ON signals(resolved, expires_at);
CREATE INDEX idx_signals_created ON signals(created_at DESC);
CREATE INDEX idx_signals_domain ON signals(domain);
CREATE INDEX idx_signals_scope ON signals(scope);
CREATE INDEX idx_signals_severity ON signals(severity);
```

---

### 2.11 position_monitor_status

Continuous position monitoring — tracks per-position health and signals.

```sql
CREATE TABLE position_monitor_status (
    monitor_id              SERIAL PRIMARY KEY,
    position_id             INTEGER REFERENCES positions(position_id),
    symbol                  VARCHAR(20) NOT NULL,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',
    pid                     INTEGER,
    started_at              TIMESTAMPTZ,
    last_check_at           TIMESTAMPTZ,
    next_check_at           TIMESTAMPTZ,
    checks_completed        INTEGER DEFAULT 0,
    last_price              NUMERIC(12,4),
    high_watermark          NUMERIC(12,4),
    current_pnl_pct         NUMERIC(8,4),
    last_rsi                NUMERIC(5,2),
    last_macd_signal        VARCHAR(20),
    last_vwap_position      VARCHAR(20),
    last_ema20_position     VARCHAR(20),
    hold_signals            TEXT[],
    exit_signals            TEXT[],
    signal_strength         VARCHAR(20),
    recommendation          VARCHAR(10),
    recommendation_reason   TEXT,
    haiku_calls             INTEGER DEFAULT 0,
    last_haiku_recommendation TEXT,
    estimated_cost          NUMERIC(8,4) DEFAULT 0,
    last_error              TEXT,
    error_count             INTEGER DEFAULT 0,
    consecutive_errors      INTEGER DEFAULT 0,
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger
CREATE TRIGGER trg_monitor_updated
    BEFORE UPDATE ON position_monitor_status
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Indexes
CREATE INDEX idx_monitor_active ON position_monitor_status(status)
    WHERE status IN ('running', 'starting');
CREATE INDEX idx_monitor_position ON position_monitor_status(position_id);
CREATE INDEX idx_monitor_status ON position_monitor_status(status);
CREATE INDEX idx_monitor_symbol ON position_monitor_status(symbol);
```

---

### 2.12 agent_logs

Runtime log storage for observability.

```sql
CREATE TABLE agent_logs (
    id          SERIAL PRIMARY KEY,
    level       VARCHAR(20) NOT NULL,            -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    source      VARCHAR(50) NOT NULL,
    message     TEXT NOT NULL,
    context     JSONB DEFAULT '{}',
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_agent_logs_context ON agent_logs USING GIN(context);
CREATE INDEX idx_agent_logs_level ON agent_logs(level);
CREATE INDEX idx_agent_logs_source ON agent_logs(source);
CREATE INDEX idx_agent_logs_timestamp ON agent_logs(timestamp);
```

---

### 2.13 claude_state (trading DB version)

Simplified agent state — used for local budget tracking.

```sql
CREATE TABLE claude_state (
    agent_id         VARCHAR(50) PRIMARY KEY,
    current_mode     VARCHAR(20) DEFAULT 'SCANNING',
    api_spend_today  NUMERIC(10,4) DEFAULT 0.0,
    last_active      TIMESTAMPTZ DEFAULT NOW(),
    notes            TEXT
);
```

**Note:** This is a simplified version. The full consciousness `claude_state` is in catalyst_research (see Part 3).

---

### 2.14 Helper Functions (catalyst_dev)

```sql
-- Auto-update updated_at on row modification
CREATE FUNCTION update_timestamp() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Lookup or create a security by symbol
CREATE FUNCTION get_or_create_security(p_symbol VARCHAR) RETURNS INTEGER AS $$
DECLARE
    v_id INTEGER;
BEGIN
    SELECT security_id INTO v_id FROM securities WHERE symbol = p_symbol;
    IF v_id IS NULL THEN
        INSERT INTO securities (symbol, exchange) VALUES (p_symbol, 'HKEX')
        RETURNING security_id INTO v_id;
    END IF;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;
```

### 2.15 Triggers (catalyst_dev)

| Trigger | Table | Event | Function |
|---------|-------|-------|----------|
| trg_positions_updated | positions | BEFORE UPDATE | update_timestamp() |
| trg_orders_updated | orders | BEFORE UPDATE | update_timestamp() |
| trg_monitor_updated | position_monitor_status | BEFORE UPDATE | update_timestamp() |

---

## PART 3: CONSCIOUSNESS DATABASE SCHEMA

Database: **catalyst_research**
Extensions: pg_trgm 1.6, plpgsql 1.0, uuid-ossp 1.1

### 3.1 claude_state (consciousness version)

Full agent state — budget, scheduling, errors. One row per agent.

```sql
CREATE TABLE claude_state (
    agent_id            VARCHAR(50) PRIMARY KEY,
    current_mode        VARCHAR(50),
    last_wake_at        TIMESTAMPTZ,
    last_think_at       TIMESTAMPTZ,
    last_action_at      TIMESTAMPTZ,
    last_poll_at        TIMESTAMPTZ,
    api_spend_today     NUMERIC(10,4) DEFAULT 0,
    api_spend_month     NUMERIC(10,4) DEFAULT 0,
    daily_budget        NUMERIC(10,4) DEFAULT 5.00,
    current_schedule    VARCHAR(100),
    next_scheduled_wake TIMESTAMPTZ,
    status_message      TEXT,
    error_count_today   INTEGER DEFAULT 0,
    last_error          TEXT,
    last_error_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

**Current agents (6 rows):** big_bro, dev_claude, intl_claude, public_claude, and others.

---

### 3.2 claude_messages

Inter-agent communication bus. Supports threading and reply chains.

```sql
CREATE TABLE claude_messages (
    id                  SERIAL PRIMARY KEY,
    message_uuid        UUID DEFAULT uuid_generate_v4() UNIQUE,
    from_agent          VARCHAR(50) NOT NULL,
    to_agent            VARCHAR(50) NOT NULL,
    msg_type            VARCHAR(50) NOT NULL,     -- alert, report, question, instruction
    priority            VARCHAR(20) DEFAULT 'normal',
    subject             VARCHAR(500),
    body                TEXT,
    data                JSONB,
    reply_to_id         INTEGER REFERENCES claude_messages(id),
    thread_id           INTEGER,
    status              VARCHAR(50) DEFAULT 'pending',  -- pending, read, processed
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    read_at             TIMESTAMPTZ,
    processed_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    requires_response   BOOLEAN DEFAULT false,
    response_deadline   TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_msg_from ON claude_messages(from_agent, created_at DESC);
CREATE INDEX idx_msg_pending ON claude_messages(to_agent) WHERE status = 'pending';
CREATE INDEX idx_msg_thread ON claude_messages(thread_id);
CREATE INDEX idx_msg_to_status ON claude_messages(to_agent, status, created_at DESC);
```

---

### 3.3 claude_learnings

Validated learnings — long-term memory. Supports validation/contradiction scoring.

```sql
CREATE TABLE claude_learnings (
    id                  SERIAL PRIMARY KEY,
    agent_id            VARCHAR(50) NOT NULL,
    source_id           INTEGER,
    source_db           VARCHAR(50),
    category            VARCHAR(100),
    learning            TEXT NOT NULL,
    source              VARCHAR(200),
    context             TEXT,
    confidence          NUMERIC(3,2),
    times_validated     INTEGER DEFAULT 0,
    times_contradicted  INTEGER DEFAULT 0,
    applies_to_markets  JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_validated_at   TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_learn_agent ON claude_learnings(agent_id);
CREATE INDEX idx_learn_category ON claude_learnings(category);
CREATE INDEX idx_learn_confidence ON claude_learnings(confidence DESC);
CREATE INDEX idx_learn_source ON claude_learnings(source_db, source_id);
```

---

### 3.4 claude_observations

Market and system observations — medium-term memory with optional expiry.

```sql
CREATE TABLE claude_observations (
    id                  SERIAL PRIMARY KEY,
    agent_id            VARCHAR(50) NOT NULL,
    source_id           INTEGER,
    source_db           VARCHAR(50),
    observation_type    VARCHAR(100),
    subject             VARCHAR(200),
    content             TEXT NOT NULL,
    confidence          NUMERIC(3,2),
    horizon             VARCHAR(10),             -- short, medium, long
    market              VARCHAR(20),
    tags                JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    expires_at          TIMESTAMPTZ,
    acted_upon          BOOLEAN DEFAULT false,
    action_taken        TEXT,
    action_at           TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_obs_agent ON claude_observations(agent_id, created_at DESC);
CREATE INDEX idx_obs_market ON claude_observations(market, created_at DESC);
CREATE INDEX idx_obs_source ON claude_observations(source_db, source_id);
CREATE INDEX idx_obs_type ON claude_observations(observation_type, created_at DESC);
```

---

### 3.5 claude_questions

Open questions for deep thinking cycles.

```sql
CREATE TABLE claude_questions (
    id                   SERIAL PRIMARY KEY,
    agent_id             VARCHAR(50),
    source_id            INTEGER,
    source_db            VARCHAR(50),
    question             TEXT NOT NULL,
    context              TEXT,
    horizon              VARCHAR(10),
    priority             INTEGER DEFAULT 5,
    category             VARCHAR(100),
    status               VARCHAR(50) DEFAULT 'open',
    current_hypothesis   TEXT,
    evidence_for         TEXT,
    evidence_against     TEXT,
    answer               TEXT,
    think_frequency      VARCHAR(50),
    last_thought_at      TIMESTAMPTZ,
    next_think_at        TIMESTAMPTZ,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    answered_at          TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_q_agent ON claude_questions(agent_id);
CREATE INDEX idx_q_horizon ON claude_questions(horizon);
CREATE INDEX idx_q_priority ON claude_questions(priority DESC) WHERE status = 'open';
CREATE INDEX idx_q_status ON claude_questions(status, next_think_at);
```

---

### 3.6 claude_conversations

Conversation summaries with humans and other agents.

```sql
CREATE TABLE claude_conversations (
    id                  SERIAL PRIMARY KEY,
    agent_id            VARCHAR(50) NOT NULL,
    with_whom           VARCHAR(100),
    summary             TEXT NOT NULL,
    key_decisions       TEXT,
    action_items        TEXT,
    learnings_extracted TEXT,
    conversation_at     TIMESTAMPTZ DEFAULT NOW(),
    importance          VARCHAR(20) DEFAULT 'normal'
);

-- Indexes
CREATE INDEX idx_conv_agent ON claude_conversations(agent_id, conversation_at DESC);
CREATE INDEX idx_conv_importance ON claude_conversations(importance, conversation_at DESC);
CREATE INDEX idx_conv_with ON claude_conversations(with_whom, conversation_at DESC);
```

---

### 3.7 claude_thinking

Extended thinking sessions — deep analysis records.

```sql
CREATE TABLE claude_thinking (
    id                  SERIAL PRIMARY KEY,
    agent_id            VARCHAR(50) NOT NULL,
    thinking_type       VARCHAR(50),
    topic               TEXT NOT NULL,
    thinking_process    TEXT,
    conclusions         TEXT,
    action_items        TEXT,
    duration_seconds    INTEGER,
    tokens_used         INTEGER,
    api_cost            NUMERIC(10,4),
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    model_used          VARCHAR(50)
);

-- Indexes
CREATE INDEX idx_think_agent ON claude_thinking(agent_id, started_at DESC);
CREATE INDEX idx_think_type ON claude_thinking(thinking_type);
```

---

### 3.8 claude_reports

Generated reports (daily, weekly, performance).

```sql
CREATE TABLE claude_reports (
    id              SERIAL PRIMARY KEY,
    agent_id        VARCHAR(50) NOT NULL,
    market          VARCHAR(10) NOT NULL,
    report_type     VARCHAR(50) NOT NULL,
    report_date     DATE NOT NULL,
    title           VARCHAR(200) NOT NULL,
    summary         TEXT,
    content         TEXT NOT NULL,
    metrics         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, report_type, report_date, market)
);

-- Indexes
CREATE INDEX idx_reports_agent ON claude_reports(agent_id);
CREATE INDEX idx_reports_date ON claude_reports(report_date DESC);
CREATE INDEX idx_reports_market ON claude_reports(market);
CREATE INDEX idx_reports_type ON claude_reports(report_type);
```

---

### 3.9 sync_log

Cross-database sync tracking.

```sql
CREATE TABLE sync_log (
    id              SERIAL PRIMARY KEY,
    source_db       VARCHAR(50) NOT NULL,
    source_table    VARCHAR(50) NOT NULL,
    source_id       INTEGER NOT NULL,
    target_table    VARCHAR(50) NOT NULL,
    target_id       INTEGER NOT NULL,
    synced_at       TIMESTAMPTZ DEFAULT NOW(),
    synced_by       VARCHAR(50)
);

-- Indexes
CREATE UNIQUE INDEX idx_sync_unique ON sync_log(source_db, source_table, source_id);
CREATE INDEX idx_sync_source ON sync_log(source_db, source_id);
CREATE INDEX idx_sync_target ON sync_log(target_table, target_id);
```

---

### 3.10 Helper Functions (catalyst_research)

**Active functions:**

| Function | Purpose |
|----------|---------|
| `agent_wake(agent_id)` | Update claude_state on agent wake |
| `send_message(from, to, type, subject, body, priority, requires_response)` | Insert into claude_messages |
| `mark_message_read(message_id)` | Set status='read', read_at=NOW() |
| `get_unread_count(agent_id)` | Count pending messages |
| `record_learning(agent_id, category, learning, source, confidence, markets)` | Insert into claude_learnings |
| `record_observation(agent_id, type, subject, content, confidence, horizon, market)` | Insert into claude_observations |
| `validate_learning(learning_id)` | Increment times_validated, confidence += 0.05 |
| `contradict_learning(learning_id)` | Increment times_contradicted, confidence -= 0.10 |
| `update_agent_status(agent_id, mode, message)` | Update claude_state mode/status |

**Leftover functions (reference non-existent tables — safe to ignore):**

| Function | References |
|----------|------------|
| `get_or_create_security()` | securities, exchanges (not in research DB) |
| `get_or_create_time()` | time_dimension (not in research DB) |
| `get_current_strategy()` | strategy_versions (not in research DB) |
| `update_pattern_stats()` | patterns with INTL-specific columns |
| `close_position_with_pnl()` | positions with holding_duration column |

---

## PART 4: ARCHITECTURE RULES

### Rule 1: Orders ≠ Positions (NON-NEGOTIABLE)

```
positions.side = 'long' | 'short'   ← What you HOLD
orders.side    = 'buy'  | 'sell'    ← What you DO

A position is a holding. An order is a transaction.
They are DIFFERENT tables. Always.
```

### Rule 2: security_id FK Everywhere

```sql
-- CORRECT: join through securities
SELECT s.symbol FROM positions p JOIN securities s ON s.security_id = p.security_id;

-- WRONG: symbol column in fact tables as the join key
-- (symbol exists for convenience, security_id is the FK)
```

### Rule 3: Verify Against Deployed Schema

```bash
# ALWAYS check before INSERT/UPDATE
psql $DATABASE_URL -c "\d positions"
psql $DATABASE_URL -c "\d orders"
```

### Rule 4: trading_cycles Must Exist First

All fact tables (positions, orders, scan_results, decisions) have FK to `trading_cycles.cycle_id`. Insert the cycle record before inserting any child records.

### Rule 5: Explicit Broker/Currency for US

The positions table defaults to `broker_code='MOOMOO'` and `currency='HKD'`. US agent code must always set:
```sql
broker_code = 'ALPACA', currency = 'USD'
```

---

## PART 5: ROW COUNTS

As of 2026-04-04:

### catalyst_dev

| Table | Rows | Notes |
|-------|------|-------|
| decisions | 10 | Recent cycle decisions (325 in older data, seq at 389) |
| pattern_confidence | 10 | All seeded at 0.50, zero samples |
| signals | 1 | Test signal |
| claude_state | 1 | dev_claude agent |
| positions | 0 | Will populate after next trade cycle |
| orders | 0 | Will populate after next trade cycle |
| trading_cycles | 0 | Will populate after next cycle |
| scan_results | 0 | Will populate after next scan |
| pattern_outcomes | 0 | Will populate after first close |
| patterns | 0 | Empty |
| agent_logs | 0 | Empty |
| securities | 0 | Needs population |
| position_monitor_status | 0 | Empty |

### catalyst_research

| Table | Rows | Notes |
|-------|------|-------|
| claude_messages | 208 | Inter-agent messages |
| claude_observations | 160 | Market observations |
| claude_learnings | 128 | Validated learnings |
| claude_state | 6 | All agent states |
| claude_questions | 0 | No active questions |
| claude_conversations | 0 | Empty |
| claude_thinking | 0 | Empty |
| claude_reports | 0 | Empty |
| sync_log | 0 | Empty |

---

## PART 6: QUICK REFERENCE

### Common Queries

```sql
-- Check open positions
SELECT symbol, side, quantity, entry_price, unrealized_pnl_pct, status
FROM positions WHERE status = 'open' ORDER BY entry_time DESC;

-- Recent trading cycles
SELECT cycle_id, date, mode, status, positions_opened, api_cost
FROM trading_cycles ORDER BY started_at DESC LIMIT 10;

-- Pattern confidence (synaptic weights)
SELECT pattern_type, confidence, sample_count, win_count, loss_count,
       avg_win_pct, avg_loss_pct
FROM pattern_confidence ORDER BY confidence DESC;

-- Pattern outcomes (trade results by pattern)
SELECT pattern_type, outcome, pnl_pct, exit_trigger,
       confidence_before, confidence_after, strength_delta
FROM pattern_outcomes ORDER BY entry_time DESC LIMIT 20;

-- Recent scan results
SELECT cycle_id, symbol, price, change_pct, score, selected_for_trading
FROM scan_results ORDER BY scanned_at DESC LIMIT 20;

-- Agent states (consciousness)
SELECT agent_id, current_mode, api_spend_today, status_message, last_wake_at
FROM claude_state;  -- run against $RESEARCH_DATABASE_URL

-- Recent messages
SELECT from_agent, to_agent, msg_type, subject, status, created_at
FROM claude_messages ORDER BY created_at DESC LIMIT 10;

-- Learnings by confidence
SELECT agent_id, category, learning, confidence, times_validated
FROM claude_learnings ORDER BY confidence DESC LIMIT 20;
```

### Environment Variables

```bash
$DATABASE_URL           # catalyst_dev (US sandbox)
$INTL_DATABASE_URL      # catalyst_intl (HKEX production)
$RESEARCH_DATABASE_URL  # catalyst_research (consciousness)
```

### ER Diagram (Simplified)

```
securities ─────────────┐
                        │
trading_cycles ─────────┤
    │                   │
    ├── positions ──────┤
    │       │           │
    │       ├── orders ─┘
    │       ├── decisions
    │       ├── pattern_outcomes → pattern_confidence
    │       └── position_monitor_status
    │
    ├── orders
    ├── decisions
    └── scan_results

signals (standalone)
agent_logs (standalone)
claude_state (standalone)
```

---

*Schema extracted from live PostgreSQL on 2026-04-04*
*Craig + The Claude Family*
