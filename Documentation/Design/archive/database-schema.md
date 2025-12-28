# Catalyst Trading System - Database Schema

**Name of Application**: Catalyst Trading System  
**Name of file**: database-schema.md  
**Version**: 7.0.0  
**Last Updated**: 2025-12-27  
**Purpose**: Complete database schema for production trading + Doctor Claude monitoring

---

## REVISION HISTORY

**v7.0.0 (2025-12-27)** - DOCTOR CLAUDE MONITORING TABLES
- ✅ **NEW**: `claude_activity_log` table for audit trail
- ✅ **NEW**: `doctor_claude_rules` table for auto-fix configuration  
- ✅ **NEW**: `v_trade_pipeline_status` view for real-time monitoring
- ✅ **NEW**: `v_claude_activity_summary` view for daily summaries
- ✅ **NEW**: `v_recurring_issues` view for pattern learning
- ✅ **NEW**: `v_recent_escalations` view
- ✅ **NEW**: `v_failed_actions` view
- ✅ **NEW**: `get_autofix_rule()` function
- ✅ **NEW**: `can_auto_fix()` function

**v6.0.0 (2025-10-25)** - 3NF NORMALIZED SCHEMA
- 3NF normalization complete
- security_id FK everywhere
- Helper functions for lookups

---

## Table of Contents

1. [Schema Overview](#1-schema-overview)
2. [Dimension Tables](#2-dimension-tables)
3. [Fact Tables](#3-fact-tables)
4. [Trading Operations Tables](#4-trading-operations-tables)
5. [Doctor Claude Tables](#5-doctor-claude-tables)
6. [Views](#6-views)
7. [Doctor Claude Views](#7-doctor-claude-views)
8. [Helper Functions](#8-helper-functions)
9. [Doctor Claude Functions](#9-doctor-claude-functions)
10. [Indexes](#10-indexes)

---

## 1. Schema Overview

### 1.1 Design Philosophy

```yaml
Normalization: 3NF (Third Normal Form)
Key Principle: security_id FK everywhere, NO symbol VARCHAR duplication
Query Strategy: Always JOIN to get human-readable data
Monitoring: Doctor Claude tables for trade lifecycle tracking
```

### 1.2 Table Categories

| Category | Tables | Purpose |
|----------|--------|---------|
| **Dimension** | securities, sectors, time_dimension | Master data |
| **Fact** | trading_history, news_sentiment, technical_indicators | Time-series data |
| **Operations** | trading_cycles, positions, orders, scan_results, risk_events | Trading workflow |
| **Monitoring** | claude_activity_log, doctor_claude_rules | Doctor Claude |

### 1.3 Entity Relationship Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DIMENSION TABLES                              │
│  ┌───────────┐    ┌───────────┐    ┌────────────────┐          │
│  │ securities│    │  sectors  │    │ time_dimension │          │
│  │ (master)  │◄───│ (GICS)    │    │ (time entity)  │          │
│  └─────┬─────┘    └───────────┘    └───────┬────────┘          │
│        │                                    │                    │
└────────┼────────────────────────────────────┼────────────────────┘
         │                                    │
         │  security_id FK                    │  time_id FK
         │                                    │
┌────────▼────────────────────────────────────▼────────────────────┐
│                      FACT TABLES                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │ trading_history │  │ news_sentiment  │  │technical_indicators│ │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
         │
         │  security_id FK
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                   OPERATIONS TABLES                               │
│                                                                   │
│  ┌───────────────┐                                               │
│  │trading_cycles │ (One per day)                                 │
│  └───────┬───────┘                                               │
│          │                                                        │
│          │ cycle_id FK                                           │
│          │                                                        │
│  ┌───────▼───────┐         ┌─────────────┐                      │
│  │   POSITIONS   │◀────────│   ORDERS    │                      │
│  │  (Holdings)   │   N:1   │(Instructions)│                     │
│  └───────────────┘         └─────────────┘                      │
│                                   │                              │
│  ⚠️ CRITICAL RELATIONSHIP:        │                              │
│  One Position = Many Orders       │ self-reference               │
│  (entry, SL, TP, scale orders)    │ for bracket legs            │
│                                   ▼                              │
│                            parent_order_id                       │
│                                                                   │
│  ┌───────────────┐                                               │
│  │ scan_results  │ (Candidates)                                  │
│  └───────────────┘                                               │
└──────────────────────────────────────────────────────────────────┘
         │
         │  Monitored by
         │
┌────────▼─────────────────────────────────────────────────────────┐
│                   DOCTOR CLAUDE TABLES                           │
│  ┌───────────────────┐  ┌─────────────────────┐                 │
│  │claude_activity_log│  │ doctor_claude_rules │                 │
│  │ (audit trail)     │  │ (auto-fix config)   │                 │
│  └───────────────────┘  └─────────────────────┘                 │
└──────────────────────────────────────────────────────────────────┘
```

### 1.4 Orders vs Positions (CRITICAL DISTINCTION)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ORDERS ≠ POSITIONS                                            │
│                                                                 │
│   Order = Request sent to broker    Position = What you own     │
│   ─────────────────────────────    ──────────────────────────  │
│   "Buy 100 AAPL at $150"           "Long 100 AAPL @ $149.95"   │
│                                                                 │
│   One position can have MANY orders:                           │
│                                                                 │
│   POSITION: Long 100 AAPL                                       │
│       │                                                         │
│       ├── ORDER #1: BUY 100 @ $150 (entry) ......... filled    │
│       ├── ORDER #2: SELL 100 @ $147 (stop loss) .... cancelled │
│       └── ORDER #3: SELL 100 @ $155 (take profit) .. filled    │
│                                                                 │
│   See operations.md for complete lifecycle diagrams.            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Dimension Tables

### 2.1 Securities

```sql
CREATE TABLE securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    sector_id INTEGER REFERENCES sectors(sector_id),
    exchange VARCHAR(20),
    asset_type VARCHAR(20) DEFAULT 'stock',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_sector ON securities(sector_id);

COMMENT ON TABLE securities IS 'Master security/stock reference - SINGLE SOURCE OF TRUTH for symbols';
```

### 2.2 Sectors

```sql
CREATE TABLE sectors (
    sector_id SERIAL PRIMARY KEY,
    sector_code VARCHAR(10) NOT NULL UNIQUE,
    sector_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE sectors IS 'GICS sector classification';
```

### 2.3 Time Dimension

```sql
CREATE TABLE time_dimension (
    time_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL UNIQUE,
    date DATE NOT NULL,
    time TIME NOT NULL,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_market_hours BOOLEAN DEFAULT false,
    market_phase VARCHAR(20)
);

CREATE INDEX idx_time_timestamp ON time_dimension(timestamp);
CREATE INDEX idx_time_date ON time_dimension(date);

COMMENT ON TABLE time_dimension IS 'Time as a dimension for fact tables';
```

---

## 3. Fact Tables

### 3.1 Trading History

```sql
CREATE TABLE trading_history (
    history_id BIGSERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id INTEGER NOT NULL REFERENCES time_dimension(time_id),
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    vwap DECIMAL(12, 4),
    trade_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(security_id, time_id)
);

CREATE INDEX idx_history_security_time ON trading_history(security_id, time_id DESC);

COMMENT ON TABLE trading_history IS 'OHLCV price bars - uses security_id FK';
```

### 3.2 News Sentiment

```sql
CREATE TABLE news_sentiment (
    sentiment_id BIGSERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id INTEGER NOT NULL REFERENCES time_dimension(time_id),
    headline TEXT NOT NULL,
    source VARCHAR(100),
    sentiment_score DECIMAL(5, 4),
    magnitude DECIMAL(5, 4),
    catalyst_type VARCHAR(50),
    catalyst_strength INTEGER,
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_news_security_time ON news_sentiment(security_id, time_id DESC);
CREATE INDEX idx_news_catalyst ON news_sentiment(catalyst_type, catalyst_strength);

COMMENT ON TABLE news_sentiment IS 'News events with sentiment - uses security_id FK';
```

### 3.3 Technical Indicators

```sql
CREATE TABLE technical_indicators (
    indicator_id BIGSERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id INTEGER NOT NULL REFERENCES time_dimension(time_id),
    indicator_type VARCHAR(50) NOT NULL,
    value DECIMAL(20, 8) NOT NULL,
    parameters JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(security_id, time_id, indicator_type)
);

CREATE INDEX idx_indicators_security_time ON technical_indicators(security_id, time_id DESC);

COMMENT ON TABLE technical_indicators IS 'Technical analysis indicators - uses security_id FK';
```

---

## 4. Trading Operations Tables

### 4.1 Trading Cycles

```sql
CREATE TABLE trading_cycles (
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL UNIQUE,
    cycle_state VARCHAR(50) NOT NULL,
    phase VARCHAR(50),
    mode VARCHAR(20) NOT NULL DEFAULT 'supervised',
    configuration JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    stopped_at TIMESTAMP WITH TIME ZONE,
    daily_pnl DECIMAL(12, 2) DEFAULT 0.0,
    daily_pnl_pct DECIMAL(8, 4) DEFAULT 0.0,
    trades_executed INTEGER DEFAULT 0,
    trades_won INTEGER DEFAULT 0,
    trades_lost INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cycles_date ON trading_cycles(date DESC);
CREATE INDEX idx_cycles_state ON trading_cycles(cycle_state);

COMMENT ON TABLE trading_cycles IS 'Daily trading workflow state tracking';
```

### 4.2 Orders (REQUIRED - All orders to Alpaca)

```sql
-- ============================================================================
-- ORDERS TABLE - MANDATORY
-- Every order sent to Alpaca MUST have a row in this table
-- ============================================================================

CREATE TABLE orders (
    -- Primary Key
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    position_id UUID REFERENCES positions(position_id),  -- NULL until position created
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    cycle_id UUID REFERENCES trading_cycles(cycle_id),
    
    -- Order Hierarchy (for bracket orders)
    parent_order_id UUID REFERENCES orders(order_id),    -- Links bracket legs to parent
    order_class VARCHAR(20),                             -- 'simple', 'bracket', 'oco', 'oto'
    
    -- Order Specification
    side VARCHAR(10) NOT NULL,                           -- 'buy', 'sell'
    order_type VARCHAR(20) NOT NULL,                     -- 'market', 'limit', 'stop', 'stop_limit'
    time_in_force VARCHAR(10) DEFAULT 'day',             -- 'day', 'gtc', 'ioc', 'fok'
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12, 4),                          -- For limit and stop_limit orders
    stop_price DECIMAL(12, 4),                           -- For stop and stop_limit orders
    trail_percent DECIMAL(5, 2),                         -- For trailing stop orders
    trail_price DECIMAL(12, 4),                          -- For trailing stop orders
    
    -- Alpaca Integration
    alpaca_order_id VARCHAR(100) UNIQUE,                 -- Alpaca's order ID
    alpaca_client_order_id VARCHAR(100),                 -- Our client order ID sent to Alpaca
    
    -- Order Status (see operations.md for state machine)
    status VARCHAR(50) NOT NULL DEFAULT 'created',
        -- Lifecycle: created → submitted → accepted → [partial_fill] → filled
        --                                           → cancelled
        --                                           → rejected
        --                                           → expired
    
    -- Fill Information
    filled_qty INTEGER DEFAULT 0,
    filled_avg_price DECIMAL(12, 4),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,               -- When sent to Alpaca
    accepted_at TIMESTAMP WITH TIME ZONE,                -- When Alpaca accepted
    filled_at TIMESTAMP WITH TIME ZONE,                  -- When fully filled
    cancelled_at TIMESTAMP WITH TIME ZONE,
    expired_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    rejection_reason TEXT,                               -- Why Alpaca rejected
    cancel_reason TEXT,                                  -- Why cancelled
    metadata JSONB,                                      -- Additional context
    
    -- Constraints
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit', 'trailing_stop')),
    CONSTRAINT chk_order_class CHECK (order_class IS NULL OR order_class IN ('simple', 'bracket', 'oco', 'oto')),
    CONSTRAINT chk_order_quantity CHECK (quantity > 0),
    CONSTRAINT chk_filled_qty CHECK (filled_qty >= 0 AND filled_qty <= quantity)
);

-- Essential Indexes
CREATE INDEX idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_security ON orders(security_id);
CREATE INDEX idx_orders_cycle ON orders(cycle_id);
CREATE INDEX idx_orders_alpaca_id ON orders(alpaca_order_id) WHERE alpaca_order_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_parent ON orders(parent_order_id) WHERE parent_order_id IS NOT NULL;
CREATE INDEX idx_orders_submitted ON orders(submitted_at DESC) WHERE submitted_at IS NOT NULL;
CREATE INDEX idx_orders_pending ON orders(status) WHERE status IN ('submitted', 'accepted', 'pending_new', 'partial_fill');

COMMENT ON TABLE orders IS 'All orders sent to Alpaca - NEVER store order data in positions table';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created, then updated';
COMMENT ON COLUMN orders.parent_order_id IS 'For bracket orders: links take_profit and stop_loss to entry order';
COMMENT ON COLUMN orders.order_class IS 'bracket = entry with legs, oco = one-cancels-other, oto = one-triggers-other';
```

### 4.3 Positions (Holdings only - NO order columns)

```sql
-- ============================================================================
-- POSITIONS TABLE - Holdings only
-- Order data belongs in the orders table, NOT here
-- ============================================================================

CREATE TABLE positions (
    -- Primary Key
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    cycle_id UUID NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    
    -- Position Specification
    side VARCHAR(10) NOT NULL,                           -- 'long', 'short'
    quantity INTEGER NOT NULL,                           -- Current quantity (can change)
    
    -- Entry Information
    entry_price DECIMAL(12, 4) NOT NULL,                 -- Average entry price
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Exit Information
    exit_price DECIMAL(12, 4),                           -- Average exit price
    exit_time TIMESTAMP WITH TIME ZONE,
    
    -- Current State
    current_price DECIMAL(12, 4),
    
    -- Risk Parameters
    stop_loss DECIMAL(12, 4),
    take_profit DECIMAL(12, 4),
    risk_amount DECIMAL(12, 2),
    
    -- P&L Tracking
    unrealized_pnl DECIMAL(12, 2),
    unrealized_pnl_pct DECIMAL(8, 4),
    realized_pnl DECIMAL(12, 2),
    realized_pnl_pct DECIMAL(8, 4),
    
    -- Status (see operations.md for state machine)
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
        -- Lifecycle: pending → open → closed
        --            pending → cancelled (if entry never fills)
    
    -- Analysis Context
    pattern VARCHAR(50),
    catalyst VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB,
    
    -- Constraints
    CONSTRAINT chk_position_side CHECK (side IN ('long', 'short')),
    CONSTRAINT chk_position_status CHECK (status IN ('pending', 'open', 'closed', 'cancelled')),
    CONSTRAINT chk_position_quantity CHECK (quantity >= 0)
);

-- ============================================================================
-- ⛔ FORBIDDEN COLUMNS - These must NOT exist in positions table:
--    alpaca_order_id   -- WRONG: Use orders table
--    alpaca_status     -- WRONG: Use orders table
-- ============================================================================

CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';

COMMENT ON TABLE positions IS 'Actual holdings only - order data is in the orders table';
```

### 4.4 Scan Results

```sql
CREATE TABLE scan_results (
    scan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id UUID NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    scan_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    rank_in_scan INTEGER NOT NULL,
    price_at_scan DECIMAL(12, 4) NOT NULL,
    volume_at_scan BIGINT,
    gap_percent DECIMAL(8, 4),
    relative_volume DECIMAL(8, 2),
    float_shares BIGINT,
    catalyst_score INTEGER,
    pattern_score INTEGER,
    technical_score INTEGER,
    composite_score DECIMAL(8, 4),
    status VARCHAR(20) DEFAULT 'candidate',
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scan_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_security ON scan_results(security_id);
CREATE INDEX idx_scan_timestamp ON scan_results(scan_timestamp DESC);

COMMENT ON TABLE scan_results IS 'Market scan candidates - uses security_id FK';
```

### 4.5 Risk Events

```sql
CREATE TABLE risk_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id UUID REFERENCES trading_cycles(cycle_id),
    position_id UUID REFERENCES positions(position_id),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_risk_cycle ON risk_events(cycle_id);
CREATE INDEX idx_risk_type ON risk_events(event_type);
CREATE INDEX idx_risk_unresolved ON risk_events(resolved) WHERE resolved = false;

COMMENT ON TABLE risk_events IS 'Risk management event log';
```

---

## 5. Doctor Claude Tables

### 5.1 Claude Activity Log

```sql
CREATE TABLE claude_activity_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    session_id VARCHAR(50),
    cycle_id UUID,
    
    -- Observation
    observation_type VARCHAR(50) NOT NULL,
    observation_summary JSONB,
    issues_found INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    
    -- Decision
    decision VARCHAR(50),
    decision_reasoning TEXT,
    
    -- Action
    action_type VARCHAR(50),
    action_detail TEXT,
    action_target VARCHAR(100),
    action_result VARCHAR(20),
    error_message TEXT,
    
    -- Issue Classification
    issue_type VARCHAR(50),
    issue_severity VARCHAR(20),
    
    -- Performance
    fix_duration_ms INTEGER,
    watchdog_duration_ms INTEGER,
    
    -- Metadata
    metadata JSONB
);

CREATE INDEX idx_cal_logged_at ON claude_activity_log(logged_at DESC);
CREATE INDEX idx_cal_session ON claude_activity_log(session_id);
CREATE INDEX idx_cal_cycle ON claude_activity_log(cycle_id) WHERE cycle_id IS NOT NULL;
CREATE INDEX idx_cal_decision ON claude_activity_log(decision);
CREATE INDEX idx_cal_issue_type ON claude_activity_log(issue_type) WHERE issue_type IS NOT NULL;
CREATE INDEX idx_cal_action_result ON claude_activity_log(action_result) WHERE action_result = 'failed';

COMMENT ON TABLE claude_activity_log IS 'Audit trail of Doctor Claude monitoring activities';
COMMENT ON COLUMN claude_activity_log.observation_type IS 'watchdog_run, manual_check, startup, shutdown';
COMMENT ON COLUMN claude_activity_log.decision IS 'auto_fix, escalate, monitor, no_action, defer';
```

### 5.2 Doctor Claude Rules

```sql
CREATE TABLE doctor_claude_rules (
    rule_id SERIAL PRIMARY KEY,
    issue_type VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    auto_fix_enabled BOOLEAN DEFAULT false,
    escalate_threshold INTEGER DEFAULT 1,
    fix_template TEXT,
    fix_requires_confirmation BOOLEAN DEFAULT false,
    escalation_channel VARCHAR(50) DEFAULT 'email',
    escalation_priority VARCHAR(20) DEFAULT 'normal',
    max_auto_fixes_per_hour INTEGER DEFAULT 10,
    cooldown_minutes INTEGER DEFAULT 5,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE doctor_claude_rules IS 'Configurable rules for Doctor Claude auto-fix decisions';

-- Default rules
INSERT INTO doctor_claude_rules (issue_type, description, auto_fix_enabled, escalation_priority) VALUES
('ORDER_STATUS_MISMATCH', 'DB order status differs from Alpaca', true, 'normal'),
('PHANTOM_POSITION', 'Position in DB but not in Alpaca', true, 'high'),
('ORPHAN_POSITION', 'Position in Alpaca but not in DB', false, 'critical'),
('QTY_MISMATCH', 'Position quantity differs', false, 'high'),
('STUCK_ORDER', 'Order pending too long', false, 'normal'),
('CYCLE_STALE', 'No activity for extended period', false, 'normal'),
('SERVICE_UNHEALTHY', 'Service not responding', false, 'critical'),
('DAILY_LOSS_WARNING', 'Approaching loss limit', false, 'critical')
ON CONFLICT (issue_type) DO NOTHING;
```

---

## 6. Views

### 6.1 Latest Securities View

```sql
CREATE MATERIALIZED VIEW v_securities_latest AS
SELECT 
    s.security_id,
    s.symbol,
    s.name,
    sec.sector_name,
    th.close as latest_price,
    th.volume as latest_volume,
    td.timestamp as price_timestamp
FROM securities s
LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
LEFT JOIN LATERAL (
    SELECT th.close, th.volume, th.time_id
    FROM trading_history th
    WHERE th.security_id = s.security_id
    ORDER BY th.time_id DESC
    LIMIT 1
) th ON true
LEFT JOIN time_dimension td ON th.time_id = td.time_id
WHERE s.is_active = true;

CREATE UNIQUE INDEX idx_v_securities_latest ON v_securities_latest(security_id);
```

### 6.2 Latest Scan View

```sql
CREATE MATERIALIZED VIEW v_scan_latest AS
SELECT 
    sr.*,
    s.symbol,
    s.name
FROM scan_results sr
JOIN securities s ON sr.security_id = s.security_id
WHERE sr.scan_timestamp = (
    SELECT MAX(scan_timestamp) FROM scan_results
);
```

---

## 7. Doctor Claude Views

### 7.1 Trade Pipeline Status

```sql
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
    
    -- Counts
    COALESCE(scan.candidates, 0) as candidates_found,
    COALESCE(pos.total, 0) as positions_total,
    COALESCE(pos.open_count, 0) as positions_open,
    COALESCE(pos.closed_count, 0) as positions_closed,
    COALESCE(ord.total, 0) as orders_total,
    COALESCE(ord.submitted, 0) as orders_pending,
    COALESCE(ord.filled, 0) as orders_filled,
    COALESCE(ord.cancelled, 0) as orders_cancelled,
    COALESCE(ord.rejected, 0) as orders_rejected,
    
    -- P&L
    COALESCE(pos.realized_pnl, 0) as realized_pnl,
    COALESCE(pos.unrealized_pnl, 0) as unrealized_pnl,
    
    -- Health
    EXTRACT(EPOCH FROM (NOW() - tc.updated_at))/60 as minutes_since_activity,
    CASE 
        WHEN tc.cycle_state = 'closed' THEN 'COMPLETE'
        WHEN COALESCE(pos.open_count, 0) > 0 AND COALESCE(ord.submitted, 0) = 0 THEN 'MONITORING'
        WHEN COALESCE(ord.submitted, 0) > 0 THEN 'ORDERS_PENDING'
        WHEN COALESCE(scan.candidates, 0) > 0 AND COALESCE(pos.total, 0) = 0 THEN 'AWAITING_ENTRY'
        ELSE 'SCANNING'
    END as pipeline_stage

FROM trading_cycles tc
LEFT JOIN LATERAL (
    SELECT COUNT(*) as candidates FROM scan_results sr WHERE sr.cycle_id = tc.cycle_id
) scan ON true
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE p.status = 'open') as open_count,
        COUNT(*) FILTER (WHERE p.status = 'closed') as closed_count,
        COALESCE(SUM(p.realized_pnl) FILTER (WHERE p.status = 'closed'), 0) as realized_pnl,
        COALESCE(SUM(p.unrealized_pnl) FILTER (WHERE p.status = 'open'), 0) as unrealized_pnl
    FROM positions p WHERE p.cycle_id = tc.cycle_id
) pos ON true
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE o.status IN ('submitted', 'pending_new', 'accepted')) as submitted,
        COUNT(*) FILTER (WHERE o.status = 'filled') as filled,
        COUNT(*) FILTER (WHERE o.status = 'cancelled') as cancelled,
        COUNT(*) FILTER (WHERE o.status = 'rejected') as rejected
    FROM orders o JOIN positions p ON o.position_id = p.position_id WHERE p.cycle_id = tc.cycle_id
) ord ON true
WHERE tc.date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY tc.date DESC, tc.started_at DESC;

COMMENT ON VIEW v_trade_pipeline_status IS 'Real-time trade pipeline status for Doctor Claude';
```

### 7.2 Claude Activity Summary

```sql
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
    COUNT(*) FILTER (WHERE action_result = 'success') as successful_actions,
    COUNT(*) FILTER (WHERE action_result = 'failed') as failed_actions,
    MIN(logged_at) as session_start,
    MAX(logged_at) as session_end,
    ROUND(EXTRACT(EPOCH FROM (MAX(logged_at) - MIN(logged_at)))/3600, 2) as session_hours
FROM claude_activity_log
GROUP BY DATE(logged_at), session_id
ORDER BY activity_date DESC;

COMMENT ON VIEW v_claude_activity_summary IS 'Daily summary of Doctor Claude activities';
```

### 7.3 Recurring Issues

```sql
CREATE OR REPLACE VIEW v_recurring_issues AS
SELECT 
    issue_type,
    COUNT(*) as occurrences,
    COUNT(*) FILTER (WHERE action_result = 'success') as times_fixed,
    COUNT(*) FILTER (WHERE action_result = 'failed') as times_failed,
    COUNT(*) FILTER (WHERE decision = 'escalate') as times_escalated,
    ROUND(AVG(fix_duration_ms)) as avg_fix_ms,
    MAX(logged_at) as last_occurrence,
    MIN(logged_at) as first_occurrence
FROM claude_activity_log
WHERE issue_type IS NOT NULL
  AND logged_at > NOW() - INTERVAL '30 days'
GROUP BY issue_type
ORDER BY occurrences DESC;

COMMENT ON VIEW v_recurring_issues IS 'Issue frequency for Doctor Claude learning';
```

### 7.4 Recent Escalations

```sql
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

COMMENT ON VIEW v_recent_escalations IS 'Issues escalated to human review';
```

### 7.5 Failed Actions

```sql
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
```

---

## 8. Helper Functions

### 8.1 Get or Create Security

```sql
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities WHERE symbol = UPPER(p_symbol);
    
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol) 
        VALUES (UPPER(p_symbol))
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;
```

### 8.2 Get or Create Time

```sql
CREATE OR REPLACE FUNCTION get_or_create_time(p_timestamp TIMESTAMP WITH TIME ZONE)
RETURNS INTEGER AS $$
DECLARE
    v_time_id INTEGER;
BEGIN
    SELECT time_id INTO v_time_id
    FROM time_dimension WHERE timestamp = p_timestamp;
    
    IF v_time_id IS NULL THEN
        INSERT INTO time_dimension (timestamp, date, time, hour, minute, day_of_week)
        VALUES (
            p_timestamp,
            p_timestamp::DATE,
            p_timestamp::TIME,
            EXTRACT(HOUR FROM p_timestamp),
            EXTRACT(MINUTE FROM p_timestamp),
            EXTRACT(DOW FROM p_timestamp)
        )
        RETURNING time_id INTO v_time_id;
    END IF;
    
    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;
```

---

## 9. Doctor Claude Functions

### 9.1 Get Auto-Fix Rule

```sql
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

COMMENT ON FUNCTION get_autofix_rule IS 'Get auto-fix configuration for issue type';
```

### 9.2 Can Auto-Fix (Rate Limiting)

```sql
CREATE OR REPLACE FUNCTION can_auto_fix(p_issue_type VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    v_rule RECORD;
    v_recent_fixes INTEGER;
    v_last_fix TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT * INTO v_rule
    FROM doctor_claude_rules
    WHERE issue_type = p_issue_type AND is_active = true;
    
    IF NOT FOUND OR NOT v_rule.auto_fix_enabled THEN
        RETURN false;
    END IF;
    
    SELECT COUNT(*), MAX(logged_at) 
    INTO v_recent_fixes, v_last_fix
    FROM claude_activity_log
    WHERE issue_type = p_issue_type
      AND decision = 'auto_fix'
      AND logged_at > NOW() - INTERVAL '1 hour';
    
    IF v_recent_fixes >= v_rule.max_auto_fixes_per_hour THEN
        RETURN false;
    END IF;
    
    IF v_last_fix IS NOT NULL AND 
       v_last_fix > NOW() - (v_rule.cooldown_minutes || ' minutes')::INTERVAL THEN
        RETURN false;
    END IF;
    
    RETURN true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION can_auto_fix IS 'Check rate limits before auto-fixing';
```

---

## 10. Indexes

### 10.1 Performance Indexes Summary

| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| securities | idx_securities_symbol | symbol | Fast symbol lookup |
| trading_history | idx_history_security_time | security_id, time_id | Time-series queries |
| positions | idx_positions_status | status | Open position queries |
| orders | idx_orders_alpaca | alpaca_order_id | Broker reconciliation |
| claude_activity_log | idx_cal_logged_at | logged_at | Recent activity |
| claude_activity_log | idx_cal_issue_type | issue_type | Issue analysis |

---

## Related Documents

- **architecture.md** - System architecture including Doctor Claude
- **functional-specification.md** - Service APIs and operations
- **operations.md** - Core patterns, state machines, data flows
- **ORDERS-POSITIONS-IMPLEMENTATION.md** - Orders vs positions implementation guide
- **ARCHITECTURE-RULES.md** - Mandatory rules for Claude Code
- **DOCTOR-CLAUDE-DESIGN.md** - Doctor Claude detailed design

---

**END OF DATABASE SCHEMA DOCUMENT v7.0.0**
