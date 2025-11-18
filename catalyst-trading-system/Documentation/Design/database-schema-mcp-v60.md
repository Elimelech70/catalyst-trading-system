# Catalyst Trading System - Database Schema v6.0

**Name of Application**: Catalyst Trading System  
**Name of file**: database-schema-mcp-v60.md  
**Version**: 6.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: Normalized database schema for Production trading system
**Scope**: PRODUCTION SCHEMA ONLY

---

## REVISION HISTORY

**v6.0.0 (2025-10-25)** - PRODUCTION SCHEMA CLEAN SEPARATION
- ✅ **MAJOR CHANGE**: ML tables removed entirely
- ✅ Production tables ONLY (trading operations)
- ✅ Full 3NF normalization maintained
- ✅ US markets focus (single timezone, USD currency)
- ✅ No research tables, no ML experiments, no multi-agent logs
- ⚠️ **BREAKING**: ML features moved to research-database-schema-v10.md (future)

**v5.0.0 (2025-10-06)** - Full 3NF Normalization (superseded)
- Mixed Production + ML tables (caused confusion)

---

## ⚠️ CRITICAL: SCOPE DEFINITION

### **IN SCOPE (Production Schema)**
✅ Securities master data (US stocks)  
✅ Trading operations (positions, orders, cycles)  
✅ Market data (OHLCV, technical indicators)  
✅ News intelligence (catalysts, sentiment)  
✅ Risk management (events, limits)  
✅ Performance tracking (daily/weekly metrics)  
✅ Scan results (candidate filtering)  

### **OUT OF SCOPE (Future Research Schema)**
❌ ML experiments table (research-database-schema-v10.md)  
❌ ML models table (research-database-schema-v10.md)  
❌ ML predictions table (research-database-schema-v10.md)  
❌ Agent research logs (research-database-schema-v10.md)  
❌ Pattern discovery table (research-database-schema-v10.md)  
❌ Multi-market correlations (Phase 2+)  
❌ Chinese/Japanese market tables (Phase 2+)  

**REASON**: Clean Production schema for immediate trading, Research schema built later.

---

## Table of Contents

1. [Normalization Principles](#1-normalization-principles)
2. [Dimension Tables (Master Data)](#2-dimension-tables-master-data)
3. [Fact Tables (Time-Series Events)](#3-fact-tables-time-series-events)
4. [Trading Operations Tables](#4-trading-operations-tables)
5. [Views & Materialized Views](#5-views--materialized-views)
6. [Helper Functions](#6-helper-functions)
7. [Indexes & Performance](#7-indexes--performance)
8. [Usage Patterns](#8-usage-patterns)
9. [Validation Queries](#9-validation-queries)

---

## 1. Normalization Principles

### 1.1 Core Rules (3NF - ALWAYS FOLLOW!)

**Rule #1: Master Data Lives in ONE Place**
```sql
-- ✅ CORRECT: Symbol stored ONCE in securities table
SELECT s.symbol, th.close, ns.headline
FROM trading_history th
JOIN securities s ON s.security_id = th.security_id
JOIN news_sentiment ns ON ns.security_id = th.security_id;

-- ❌ WRONG: Symbol duplicated everywhere (denormalized)
SELECT symbol, close FROM trading_history;  -- NO symbol column!
```

**Rule #2: All Relationships Use Foreign Keys**
```sql
-- Every table references securities via security_id FK
-- Every time-series table references time_dimension via time_id FK
-- NO VARCHAR(10) symbol columns anywhere except securities table!
```

**Rule #3: Query With JOINs**
```sql
-- Always JOIN to get human-readable data
-- Database stores IDs (integers), queries return symbols (JOINed)
```

### 1.2 Benefits of Normalization

**Data Integrity**:
- Symbol change? Update ONE row in securities table
- Sector change? Update ONE row in sectors table
- Referential integrity enforced by database

**Performance**:
- Integer FK joins faster than VARCHAR comparisons
- Smaller indexes (integers vs strings)
- Better query optimization

**ML Quality**:
- Consistent security_id across all tables
- No ambiguity (AAPL vs aapl vs Apple Inc.)
- Clean joins for feature engineering

---

## 2. Dimension Tables (Master Data)

### 2.1 Securities Table (Master Entity)

```sql
CREATE TABLE securities (
    -- Primary Key
    security_id SERIAL PRIMARY KEY,
    
    -- Symbol & Identity
    symbol VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255),
    
    -- Classification
    sector_id INTEGER REFERENCES sectors(sector_id),
    exchange VARCHAR(20) NOT NULL,  -- 'NYSE', 'NASDAQ'
    security_type VARCHAR(20) DEFAULT 'stock',  -- 'stock', 'etf'
    
    -- Market Data
    currency VARCHAR(3) DEFAULT 'USD',
    trading_hours_start TIME DEFAULT '09:30:00',  -- ET
    trading_hours_end TIME DEFAULT '16:00:00',    -- ET
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    listed_date DATE,
    delisted_date DATE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_sector ON securities(sector_id);
CREATE INDEX idx_securities_active ON securities(is_active) WHERE is_active = true;

COMMENT ON TABLE securities IS 'Master securities table - SINGLE SOURCE OF TRUTH for all symbols';
COMMENT ON COLUMN securities.security_id IS 'Primary key - used as FK in ALL other tables';
COMMENT ON COLUMN securities.symbol IS 'Stock ticker - ONLY place symbol is stored as VARCHAR';
```

### 2.2 Sectors Table

```sql
CREATE TABLE sectors (
    sector_id SERIAL PRIMARY KEY,
    sector_code VARCHAR(10) NOT NULL UNIQUE,  -- 'TECH', 'HLTH', etc.
    sector_name VARCHAR(100) NOT NULL,        -- 'Technology', 'Healthcare'
    industry_group VARCHAR(100),
    gics_code VARCHAR(8),  -- Global Industry Classification Standard
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed with 11 GICS sectors
INSERT INTO sectors (sector_code, sector_name, gics_code) VALUES
    ('TECH', 'Information Technology', '45'),
    ('HLTH', 'Health Care', '35'),
    ('FINL', 'Financials', '40'),
    ('DISC', 'Consumer Discretionary', '25'),
    ('STPL', 'Consumer Staples', '30'),
    ('ENRG', 'Energy', '10'),
    ('UTIL', 'Utilities', '55'),
    ('INDU', 'Industrials', '20'),
    ('MATL', 'Materials', '15'),
    ('RLST', 'Real Estate', '60'),
    ('COMM', 'Communication Services', '50');

COMMENT ON TABLE sectors IS 'GICS sector master data - normalized sector information';
```

### 2.3 Time Dimension Table

```sql
CREATE TABLE time_dimension (
    time_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL UNIQUE,
    
    -- Date Components
    date DATE NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,  -- 0=Monday, 6=Sunday
    
    -- Time Components
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    
    -- Market Context
    is_market_hours BOOLEAN NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    market_session VARCHAR(20),  -- 'pre-market', 'open', 'close', 'after-hours'
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_time_timestamp ON time_dimension(timestamp);
CREATE INDEX idx_time_date ON time_dimension(date);
CREATE INDEX idx_time_market_hours ON time_dimension(is_market_hours) WHERE is_market_hours = true;

COMMENT ON TABLE time_dimension IS 'Time as an entity - ALL time-series tables reference this';
COMMENT ON COLUMN time_dimension.time_id IS 'Primary key - used as FK in time-series tables';
```

---

## 3. Fact Tables (Time-Series Events)

### 3.1 Trading History (OHLCV Data)

```sql
CREATE TABLE trading_history (
    -- Primary Key
    history_id BIGSERIAL PRIMARY KEY,
    
    -- Foreign Keys (NO symbol column!)
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id BIGINT NOT NULL REFERENCES time_dimension(time_id),
    
    -- OHLCV Data
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Derived Metrics
    vwap DECIMAL(12, 4),  -- Volume-weighted average price
    trade_count INTEGER,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_security_time UNIQUE(security_id, time_id),
    CONSTRAINT chk_ohlc CHECK (high >= low AND high >= open AND high >= close AND low <= open AND low <= close)
);

-- Partition by month for performance
CREATE INDEX idx_trading_history_security ON trading_history(security_id);
CREATE INDEX idx_trading_history_time ON trading_history(time_id);
CREATE INDEX idx_trading_history_security_time ON trading_history(security_id, time_id DESC);

COMMENT ON TABLE trading_history IS 'OHLCV bars - uses security_id FK (NOT symbol)';
COMMENT ON CONSTRAINT unique_security_time ON trading_history IS 'One bar per security per timeframe';
```

### 3.2 News Sentiment

```sql
CREATE TABLE news_sentiment (
    -- Primary Key
    news_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id BIGINT NOT NULL REFERENCES time_dimension(time_id),
    
    -- News Content
    headline TEXT NOT NULL,
    summary TEXT,
    url TEXT,
    source VARCHAR(100) NOT NULL,  -- 'Benzinga', 'NewsAPI', etc.
    
    -- Sentiment Analysis
    sentiment_score DECIMAL(5, 4),  -- -1.0 to 1.0
    sentiment_label VARCHAR(20),    -- 'positive', 'negative', 'neutral'
    
    -- Catalyst Classification
    catalyst_type VARCHAR(50),      -- 'earnings', 'fda_approval', 'merger', etc.
    catalyst_strength DECIMAL(5, 4),  -- 0.0 to 1.0
    
    -- Source Quality
    source_reliability_score DECIMAL(5, 4) DEFAULT 0.5,
    
    -- Metadata
    metadata JSONB,  -- Flexible storage for additional fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_news_security ON news_sentiment(security_id);
CREATE INDEX idx_news_time ON news_sentiment(time_id);
CREATE INDEX idx_news_catalyst ON news_sentiment(catalyst_type) WHERE catalyst_type IS NOT NULL;
CREATE INDEX idx_news_source ON news_sentiment(source);

COMMENT ON TABLE news_sentiment IS 'News events with sentiment - uses security_id FK';
COMMENT ON COLUMN news_sentiment.catalyst_strength IS 'How strong the catalyst (0=weak, 1=very strong)';
```

### 3.3 Technical Indicators

```sql
CREATE TABLE technical_indicators (
    -- Primary Key
    indicator_id BIGSERIAL PRIMARY KEY,
    
    -- Foreign Keys
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id BIGINT NOT NULL REFERENCES time_dimension(time_id),
    
    -- Timeframe
    timeframe VARCHAR(20) NOT NULL,  -- '1min', '5min', '1hour', '1day'
    
    -- Moving Averages
    sma_20 DECIMAL(12, 4),
    sma_50 DECIMAL(12, 4),
    sma_200 DECIMAL(12, 4),
    ema_9 DECIMAL(12, 4),
    ema_21 DECIMAL(12, 4),
    
    -- Momentum
    rsi_14 DECIMAL(5, 2),           -- 0-100
    macd DECIMAL(12, 4),
    macd_signal DECIMAL(12, 4),
    macd_histogram DECIMAL(12, 4),
    
    -- Volatility
    atr_14 DECIMAL(12, 4),
    bollinger_upper DECIMAL(12, 4),
    bollinger_middle DECIMAL(12, 4),
    bollinger_lower DECIMAL(12, 4),
    
    -- Volume
    obv BIGINT,                     -- On-Balance Volume
    volume_ratio DECIMAL(8, 4),     -- Current vol / 20-day avg
    unusual_volume_flag BOOLEAN DEFAULT false,
    
    -- Support/Resistance
    support_level DECIMAL(12, 4),
    resistance_level DECIMAL(12, 4),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_security_time_timeframe UNIQUE(security_id, time_id, timeframe)
);

CREATE INDEX idx_technical_security ON technical_indicators(security_id);
CREATE INDEX idx_technical_time ON technical_indicators(time_id);
CREATE INDEX idx_technical_timeframe ON technical_indicators(timeframe);

COMMENT ON TABLE technical_indicators IS 'Technical analysis indicators - uses security_id FK';
```

---

## 4. Trading Operations Tables

### 4.1 Trading Cycles

```sql
CREATE TABLE trading_cycles (
    -- Primary Key
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Cycle Info
    date DATE NOT NULL UNIQUE,
    cycle_state VARCHAR(50) NOT NULL,  -- 'scanning', 'evaluating', 'trading', 'monitoring', 'closed'
    phase VARCHAR(50),  -- 'pre-market', 'opening-range', 'morning', 'midday', 'power-hour', 'closed'
    
    -- Session Configuration
    session_mode VARCHAR(20) NOT NULL DEFAULT 'supervised',  -- 'autonomous', 'supervised'
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Performance Summary
    daily_pnl DECIMAL(12, 2) DEFAULT 0.0,
    daily_pnl_pct DECIMAL(8, 4) DEFAULT 0.0,
    trades_executed INTEGER DEFAULT 0,
    trades_won INTEGER DEFAULT 0,
    trades_lost INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_cycles_date ON trading_cycles(date DESC);
CREATE INDEX idx_cycles_state ON trading_cycles(cycle_state);

COMMENT ON TABLE trading_cycles IS 'Daily trading workflow state tracking';
COMMENT ON COLUMN trading_cycles.session_mode IS 'autonomous = immediate action, supervised = 5-min warning';
```

### 4.2 Positions

```sql
CREATE TABLE positions (
    -- Primary Key
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    cycle_id UUID NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    
    -- Position Details
    side VARCHAR(10) NOT NULL,  -- 'long', 'short'
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(12, 4) NOT NULL,
    current_price DECIMAL(12, 4),
    
    -- Risk Management
    stop_loss DECIMAL(12, 4),
    take_profit DECIMAL(12, 4),
    risk_amount DECIMAL(12, 2) NOT NULL,
    
    -- P&L
    unrealized_pnl DECIMAL(12, 2),
    unrealized_pnl_pct DECIMAL(8, 4),
    realized_pnl DECIMAL(12, 2),
    realized_pnl_pct DECIMAL(8, 4),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'open',  -- 'open', 'closed', 'stopped_out'
    
    -- Trading Context
    pattern VARCHAR(50),  -- 'bull_flag', 'cup_and_handle', etc.
    catalyst VARCHAR(255),  -- News catalyst that drove the trade
    
    -- Timing
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_quantity CHECK (quantity > 0),
    CONSTRAINT chk_side CHECK (side IN ('long', 'short'))
);

CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);

COMMENT ON TABLE positions IS 'Trading positions - uses security_id FK (NOT symbol)';
COMMENT ON COLUMN positions.pattern IS 'Chart pattern that triggered entry';
```

### 4.3 Orders

```sql
CREATE TABLE orders (
    -- Primary Key
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    position_id UUID REFERENCES positions(position_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    
    -- Order Details
    side VARCHAR(10) NOT NULL,  -- 'buy', 'sell'
    order_type VARCHAR(20) NOT NULL,  -- 'market', 'limit', 'stop', 'stop_limit'
    quantity INTEGER NOT NULL,
    
    -- Pricing
    limit_price DECIMAL(12, 4),
    stop_price DECIMAL(12, 4),
    filled_avg_price DECIMAL(12, 4),
    
    -- Status
    status VARCHAR(50) NOT NULL,  -- 'submitted', 'filled', 'partially_filled', 'cancelled', 'rejected'
    filled_qty INTEGER DEFAULT 0,
    
    -- Alpaca Integration
    alpaca_order_id VARCHAR(100) UNIQUE,
    
    -- Timing
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    filled_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_order_quantity CHECK (quantity > 0),
    CONSTRAINT chk_order_side CHECK (side IN ('buy', 'sell'))
);

CREATE INDEX idx_orders_position ON orders(position_id);
CREATE INDEX idx_orders_security ON orders(security_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_alpaca ON orders(alpaca_order_id);
CREATE INDEX idx_orders_submitted ON orders(submitted_at DESC);

COMMENT ON TABLE orders IS 'Order execution history - uses security_id FK';
```

### 4.4 Scan Results

```sql
CREATE TABLE scan_results (
    -- Primary Key
    scan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    cycle_id UUID NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    
    -- Scan Metadata
    scan_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    rank INTEGER NOT NULL,  -- 1-5 (top 5 candidates)
    
    -- Scoring
    final_score DECIMAL(5, 4) NOT NULL,
    catalyst_score DECIMAL(5, 4),
    technical_score DECIMAL(5, 4),
    pattern_score DECIMAL(5, 4),
    
    -- Market Data
    price DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Analysis
    pattern VARCHAR(50),
    catalyst_type VARCHAR(50),
    news_headline TEXT,
    
    -- Entry/Exit Levels
    support_level DECIMAL(12, 4),
    resistance_level DECIMAL(12, 4),
    suggested_entry DECIMAL(12, 4),
    suggested_stop DECIMAL(12, 4),
    suggested_target DECIMAL(12, 4),
    
    -- Metadata
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_cycle_security UNIQUE(cycle_id, security_id),
    CONSTRAINT chk_rank CHECK (rank BETWEEN 1 AND 20)
);

CREATE INDEX idx_scan_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_security ON scan_results(security_id);
CREATE INDEX idx_scan_rank ON scan_results(rank);
CREATE INDEX idx_scan_timestamp ON scan_results(scan_timestamp DESC);

COMMENT ON TABLE scan_results IS 'Market scan candidates - uses security_id FK';
COMMENT ON COLUMN scan_results.rank IS '1=best candidate, 5=5th best';
```

### 4.5 Risk Events

```sql
CREATE TABLE risk_events (
    -- Primary Key
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    cycle_id UUID REFERENCES trading_cycles(cycle_id),
    
    -- Event Details
    event_type VARCHAR(50) NOT NULL,  -- 'daily_loss_limit', 'position_risk', 'emergency_stop'
    severity VARCHAR(20) NOT NULL,    -- 'critical', 'warning', 'info'
    
    -- Event Data
    message TEXT NOT NULL,
    details JSONB,
    
    -- Action Taken
    action_taken VARCHAR(255),
    positions_affected INTEGER DEFAULT 0,
    
    -- Timing
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_risk_cycle ON risk_events(cycle_id);
CREATE INDEX idx_risk_type ON risk_events(event_type);
CREATE INDEX idx_risk_severity ON risk_events(severity);
CREATE INDEX idx_risk_occurred ON risk_events(occurred_at DESC);

COMMENT ON TABLE risk_events IS 'Risk management event log - critical for analysis';
```

---

## 5. Views & Materialized Views

### 5.1 Current Positions View

```sql
CREATE VIEW v_positions_current AS
SELECT 
    p.position_id,
    s.symbol,
    s.company_name,
    p.side,
    p.quantity,
    p.entry_price,
    p.current_price,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    p.stop_loss,
    p.take_profit,
    p.pattern,
    p.catalyst,
    p.entry_time,
    (NOW() - p.entry_time) AS time_in_position,
    p.status
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'open'
ORDER BY p.entry_time DESC;

COMMENT ON VIEW v_positions_current IS 'Current open positions with symbol (JOINed from securities)';
```

### 5.2 Daily Performance View

```sql
CREATE VIEW v_performance_daily AS
SELECT 
    tc.date,
    tc.daily_pnl,
    tc.daily_pnl_pct,
    tc.trades_executed,
    tc.trades_won,
    tc.trades_lost,
    CASE 
        WHEN tc.trades_executed > 0 
        THEN ROUND(tc.trades_won::NUMERIC / tc.trades_executed, 3)
        ELSE 0 
    END AS win_rate,
    CASE 
        WHEN tc.trades_lost > 0
        THEN ROUND((tc.trades_won::NUMERIC * ABS(tc.daily_pnl / tc.trades_won)) / 
                   (tc.trades_lost * ABS(tc.daily_pnl / tc.trades_lost)), 2)
        ELSE NULL
    END AS profit_factor
FROM trading_cycles tc
WHERE tc.cycle_state = 'closed'
ORDER BY tc.date DESC;

COMMENT ON VIEW v_performance_daily IS 'Daily trading performance metrics';
```

### 5.3 Securities Latest Prices (Materialized)

```sql
CREATE MATERIALIZED VIEW v_securities_latest AS
SELECT DISTINCT ON (th.security_id)
    s.security_id,
    s.symbol,
    s.company_name,
    th.close AS last_price,
    th.volume AS last_volume,
    td.timestamp AS last_updated
FROM trading_history th
JOIN securities s ON s.security_id = th.security_id
JOIN time_dimension td ON td.time_id = th.time_id
ORDER BY th.security_id, td.timestamp DESC;

CREATE UNIQUE INDEX idx_securities_latest_id ON v_securities_latest(security_id);

COMMENT ON MATERIALIZED VIEW v_securities_latest IS 'Latest price for each security - refresh every 5 min';

-- Refresh schedule (via cron or application)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY v_securities_latest;
```

### 5.4 Scan Candidates Latest (Materialized)

```sql
CREATE MATERIALIZED VIEW v_scan_latest AS
SELECT 
    sr.scan_id,
    s.symbol,
    s.company_name,
    sr.rank,
    sr.final_score,
    sr.price,
    sr.volume,
    sr.pattern,
    sr.catalyst_type,
    sr.news_headline,
    sr.support_level,
    sr.resistance_level,
    sr.suggested_entry,
    sr.suggested_stop,
    sr.suggested_target,
    sr.scan_timestamp
FROM scan_results sr
JOIN securities s ON s.security_id = sr.security_id
WHERE sr.cycle_id = (
    SELECT cycle_id 
    FROM trading_cycles 
    ORDER BY date DESC 
    LIMIT 1
)
ORDER BY sr.rank;

COMMENT ON MATERIALIZED VIEW v_scan_latest IS 'Latest scan results with symbols - refresh after each scan';
```

---

## 6. Helper Functions

### 6.1 Get or Create Security

```sql
CREATE OR REPLACE FUNCTION get_or_create_security(
    p_symbol VARCHAR(10)
) RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    -- Try to find existing
    SELECT security_id INTO v_security_id
    FROM securities
    WHERE symbol = UPPER(p_symbol);
    
    -- If not found, create
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange, is_active)
        VALUES (UPPER(p_symbol), 'UNKNOWN', true)
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_or_create_security IS 'Get security_id or create new security if not exists';
```

### 6.2 Get or Create Time

```sql
CREATE OR REPLACE FUNCTION get_or_create_time(
    p_timestamp TIMESTAMP WITH TIME ZONE
) RETURNS BIGINT AS $$
DECLARE
    v_time_id BIGINT;
    v_date DATE;
    v_hour INTEGER;
    v_is_market_hours BOOLEAN;
BEGIN
    -- Try to find existing
    SELECT time_id INTO v_time_id
    FROM time_dimension
    WHERE timestamp = p_timestamp;
    
    -- If not found, create
    IF v_time_id IS NULL THEN
        v_date := DATE(p_timestamp);
        v_hour := EXTRACT(HOUR FROM p_timestamp);
        
        -- Market hours: 09:30-16:00 ET (14:30-21:00 UTC)
        v_is_market_hours := (
            EXTRACT(DOW FROM p_timestamp) BETWEEN 1 AND 5  -- Mon-Fri
            AND v_hour >= 14 AND v_hour < 21  -- UTC hours
        );
        
        INSERT INTO time_dimension (
            timestamp, date, year, month, day, day_of_week,
            hour, minute, is_market_hours, is_trading_day
        ) VALUES (
            p_timestamp,
            v_date,
            EXTRACT(YEAR FROM p_timestamp),
            EXTRACT(MONTH FROM p_timestamp),
            EXTRACT(DAY FROM p_timestamp),
            EXTRACT(DOW FROM p_timestamp),
            v_hour,
            EXTRACT(MINUTE FROM p_timestamp),
            v_is_market_hours,
            EXTRACT(DOW FROM p_timestamp) BETWEEN 1 AND 5
        )
        RETURNING time_id INTO v_time_id;
    END IF;
    
    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_or_create_time IS 'Get time_id or create new time entry if not exists';
```

### 6.3 Update Position P&L

```sql
CREATE OR REPLACE FUNCTION update_position_pnl(
    p_position_id UUID,
    p_current_price DECIMAL(12, 4)
) RETURNS VOID AS $$
BEGIN
    UPDATE positions
    SET 
        current_price = p_current_price,
        unrealized_pnl = (p_current_price - entry_price) * quantity * 
            CASE WHEN side = 'long' THEN 1 ELSE -1 END,
        unrealized_pnl_pct = ((p_current_price - entry_price) / entry_price) * 
            CASE WHEN side = 'long' THEN 1 ELSE -1 END,
        updated_at = NOW()
    WHERE position_id = p_position_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_position_pnl IS 'Update unrealized P&L for a position';
```

---

## 7. Indexes & Performance

### 7.1 Core Indexes (Already Created Above)

**Dimension Tables**:
- securities(symbol) - UNIQUE index for fast symbol lookups
- securities(sector_id) - For sector-based queries
- time_dimension(timestamp) - UNIQUE index for time lookups
- time_dimension(date) - For date-based queries

**Fact Tables**:
- trading_history(security_id, time_id DESC) - Composite for latest prices
- news_sentiment(security_id, time_id) - For news lookups
- technical_indicators(security_id, time_id, timeframe) - UNIQUE constraint

**Trading Tables**:
- positions(status) WHERE status='open' - Partial index for open positions
- orders(alpaca_order_id) - UNIQUE for Alpaca integration
- scan_results(cycle_id, rank) - For latest scan results

### 7.2 Performance Tips

**Query Pattern 1: Get Latest Price**
```sql
-- ✅ FAST: Uses v_securities_latest materialized view
SELECT symbol, last_price 
FROM v_securities_latest 
WHERE symbol = 'TSLA';

-- ❌ SLOW: Full table scan
SELECT s.symbol, th.close
FROM trading_history th
JOIN securities s ON s.security_id = th.security_id
WHERE s.symbol = 'TSLA'
ORDER BY th.time_id DESC
LIMIT 1;
```

**Query Pattern 2: Get News for Symbol**
```sql
-- ✅ FAST: Uses security_id FK join
SELECT ns.headline, ns.sentiment_score, td.timestamp
FROM news_sentiment ns
JOIN securities s ON s.security_id = ns.security_id
JOIN time_dimension td ON td.time_id = ns.time_id
WHERE s.symbol = 'TSLA'
  AND td.timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY td.timestamp DESC;
```

---

## 8. Usage Patterns

### 8.1 Inserting Market Data

```python
# Python example: Store OHLCV bar

# Step 1: Get security_id
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", symbol
)

# Step 2: Get time_id
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", bar_timestamp
)

# Step 3: Insert bar with FKs
await db.execute("""
    INSERT INTO trading_history (
        security_id, time_id, open, high, low, close, volume
    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (security_id, time_id) DO UPDATE
    SET open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume
""", security_id, time_id, open, high, low, close, volume)
```

### 8.2 Querying with JOINs

```python
# Python example: Get scan results with symbols

results = await db.fetch("""
    SELECT 
        s.symbol,
        sr.rank,
        sr.final_score,
        sr.price,
        sr.pattern,
        sr.catalyst_type
    FROM scan_results sr
    JOIN securities s ON s.security_id = sr.security_id
    WHERE sr.cycle_id = $1
    ORDER BY sr.rank
""", cycle_id)

# Results include symbol (from JOIN), not stored in scan_results!
```

### 8.3 Opening a Position

```python
# Python example: Create new position

# Get security_id
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", symbol
)

# Insert position
position_id = await db.fetchval("""
    INSERT INTO positions (
        cycle_id, security_id, side, quantity,
        entry_price, stop_loss, take_profit,
        risk_amount, pattern, catalyst, entry_time, status
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), 'open')
    RETURNING position_id
""", cycle_id, security_id, side, quantity,
     entry_price, stop_loss, take_profit,
     risk_amount, pattern, catalyst)
```

---

## 9. Validation Queries

### 9.1 Check Normalization

```sql
-- ✅ Should return 0 (no symbol columns in fact tables)
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_name IN ('trading_history', 'news_sentiment', 'technical_indicators', 
                     'positions', 'orders', 'scan_results')
  AND column_name = 'symbol';
-- Expected: 0 (only securities table has symbol)
```

### 9.2 Check Foreign Keys

```sql
-- ✅ All fact tables should have FK to securities
SELECT 
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS referenced_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu 
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_name = 'securities'
ORDER BY tc.table_name;
```

### 9.3 Check Data Integrity

```sql
-- ✅ No orphaned news (should return 0)
SELECT COUNT(*)
FROM news_sentiment ns
LEFT JOIN securities s ON s.security_id = ns.security_id
WHERE s.security_id IS NULL;

-- ✅ No orphaned positions (should return 0)
SELECT COUNT(*)
FROM positions p
LEFT JOIN securities s ON s.security_id = p.security_id
WHERE s.security_id IS NULL;
```

### 9.4 Performance Check

```sql
-- ✅ Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan AS times_used,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

---

## 10. Schema Deployment Checklist

### 10.1 Pre-Deployment

- [ ] PostgreSQL 15+ installed (DigitalOcean Managed)
- [ ] Database created: `catalyst_trading_production`
- [ ] Database user created with appropriate permissions
- [ ] Connection string secured in environment variables

### 10.2 Deployment Steps

```bash
# 1. Connect to database
psql $DATABASE_URL

# 2. Deploy schema (in order)
\i 01-dimension-tables.sql   # securities, sectors, time_dimension
\i 02-fact-tables.sql         # trading_history, news_sentiment, technical_indicators
\i 03-trading-tables.sql      # trading_cycles, positions, orders, scan_results, risk_events
\i 04-views.sql               # Views and materialized views
\i 05-functions.sql           # Helper functions
\i 06-indexes.sql             # Additional indexes (if not in table definitions)
\i 07-seed-data.sql           # Seed sectors

# 3. Validate
\i validate-schema-v60.sql
```

### 10.3 Post-Deployment Validation

```sql
-- Check all tables created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
-- Expected: 11 tables

-- Check all views created
SELECT table_name 
FROM information_schema.views 
WHERE table_schema = 'public'
ORDER BY table_name;
-- Expected: 2 views

-- Check materialized views
SELECT matviewname 
FROM pg_matviews 
WHERE schemaname = 'public';
-- Expected: 2 materialized views

-- Check helper functions
SELECT proname 
FROM pg_proc 
WHERE proname IN ('get_or_create_security', 'get_or_create_time', 'update_position_pnl');
-- Expected: 3 functions
```

---

## 11. Backup & Maintenance

### 11.1 Backup Strategy

**DigitalOcean Managed Database**:
- Automated daily backups (included)
- Point-in-time recovery (7 days)
- Manual snapshots before major changes

**Manual Backup**:
```bash
# Backup entire database
pg_dump $DATABASE_URL > catalyst_production_$(date +%Y%m%d).sql

# Backup schema only (no data)
pg_dump --schema-only $DATABASE_URL > schema_v60.sql
```

### 11.2 Maintenance Tasks

**Daily**:
```sql
-- Refresh materialized views
REFRESH MATERIALIZED VIEW CONCURRENTLY v_securities_latest;
REFRESH MATERIALIZED VIEW CONCURRENTLY v_scan_latest;
```

**Weekly**:
```sql
-- Analyze tables for query optimization
ANALYZE trading_history;
ANALYZE news_sentiment;
ANALYZE positions;
ANALYZE orders;
```

**Monthly**:
```sql
-- Vacuum to reclaim space
VACUUM ANALYZE;

-- Reindex for performance
REINDEX DATABASE catalyst_trading_production;
```

---

## 12. Migration from v5.0

### 12.1 Breaking Changes

**Removed Tables**:
- `ml_experiments` → Moved to research-database-schema-v10.md
- `ml_models` → Moved to research-database-schema-v10.md
- `ml_predictions` → Moved to research-database-schema-v10.md
- `agent_research_logs` → Moved to research-database-schema-v10.md
- `pattern_discovery` → Moved to research-database-schema-v10.md
- `multi_market_correlations` → Future (Phase 2+)

**No Changes to Core Tables**:
- Dimension tables (securities, sectors, time_dimension) unchanged
- Fact tables (trading_history, news_sentiment, technical_indicators) unchanged
- Trading tables (positions, orders, cycles, scan_results) unchanged

### 12.2 Migration Steps

**If upgrading from v5.0**:
```sql
-- No migration needed! ML tables are optional.
-- Simply don't create them in v6.0 (Production only)
-- ML tables will be in separate Research database later
```

---

## Appendix A: Table Summary

| Table | Type | Purpose | FK to securities | FK to time_dimension |
|-------|------|---------|------------------|----------------------|
| **securities** | Dimension | Master security data | - | - |
| **sectors** | Dimension | GICS sectors | - | - |
| **time_dimension** | Dimension | Time as entity | - | - |
| **trading_history** | Fact | OHLCV bars | ✅ | ✅ |
| **news_sentiment** | Fact | News events | ✅ | ✅ |
| **technical_indicators** | Fact | Technical analysis | ✅ | ✅ |
| **trading_cycles** | Operations | Daily workflows | - | - |
| **positions** | Operations | Trading positions | ✅ | - |
| **orders** | Operations | Order execution | ✅ | - |
| **scan_results** | Operations | Market scan candidates | ✅ | - |
| **risk_events** | Operations | Risk management log | - | - |

**Total Tables**: 11  
**Total Views**: 2  
**Total Materialized Views**: 2  
**Total Helper Functions**: 3  

---

## Appendix B: Glossary

**3NF**: Third Normal Form - database normalization level  
**FK**: Foreign Key - relationship between tables  
**OHLCV**: Open, High, Low, Close, Volume  
**Dimension Table**: Master data (securities, time)  
**Fact Table**: Time-series events (trading_history, news)  
**Materialized View**: Pre-computed view stored on disk  
**Helper Function**: PL/pgSQL function for common operations  

---

**END OF DATABASE SCHEMA v6.0**

*Production schema ONLY. Clean, normalized, ready for trading. No ML contamination.* 🎩
