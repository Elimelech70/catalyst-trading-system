# Catalyst Trading System - Database Schema

**Name of Application**: Catalyst Trading System  
**Name of file**: database-schema.md  
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
- ⚠️ **BREAKING**: ML features moved to separate research schema (future)

**v5.0.0 (2025-10-06)** - Full 3NF Normalization (superseded)

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
❌ ML experiments table  
❌ ML models table  
❌ ML predictions table  
❌ Agent research logs  
❌ Pattern discovery table  
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
    vwap DECIMAL(12, 4),
    trade_count INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_security_time UNIQUE(security_id, time_id),
    CONSTRAINT chk_ohlc CHECK (high >= low AND high >= open AND high >= close AND low <= open AND low <= close)
);

CREATE INDEX idx_trading_history_security ON trading_history(security_id);
CREATE INDEX idx_trading_history_time ON trading_history(time_id);
CREATE INDEX idx_trading_history_security_time ON trading_history(security_id, time_id DESC);

COMMENT ON TABLE trading_history IS 'OHLCV bars - uses security_id FK (NOT symbol)';
```

### 3.2 News Sentiment

```sql
CREATE TABLE news_sentiment (
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
    catalyst_strength DECIMAL(5, 4), -- 0.0 to 1.0
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_news_security ON news_sentiment(security_id);
CREATE INDEX idx_news_time ON news_sentiment(time_id);
CREATE INDEX idx_news_catalyst ON news_sentiment(catalyst_type);

COMMENT ON TABLE news_sentiment IS 'News events with sentiment - uses security_id FK';
```

### 3.3 Technical Indicators

```sql
CREATE TABLE technical_indicators (
    indicator_id BIGSERIAL PRIMARY KEY,
    
    -- Foreign Keys
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    time_id BIGINT NOT NULL REFERENCES time_dimension(time_id),
    
    -- Timeframe
    timeframe VARCHAR(10) NOT NULL,  -- '1m', '5m', '15m', '1h', '1d'
    
    -- Momentum Indicators
    rsi_14 DECIMAL(8, 4),
    macd DECIMAL(12, 4),
    macd_signal DECIMAL(12, 4),
    macd_histogram DECIMAL(12, 4),
    
    -- Trend Indicators
    sma_9 DECIMAL(12, 4),
    sma_20 DECIMAL(12, 4),
    sma_50 DECIMAL(12, 4),
    sma_200 DECIMAL(12, 4),
    ema_9 DECIMAL(12, 4),
    ema_21 DECIMAL(12, 4),
    
    -- Volatility Indicators
    atr_14 DECIMAL(12, 4),
    bb_upper DECIMAL(12, 4),
    bb_middle DECIMAL(12, 4),
    bb_lower DECIMAL(12, 4),
    
    -- Volume Indicators
    vwap DECIMAL(12, 4),
    relative_volume DECIMAL(8, 4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_security_time_tf UNIQUE(security_id, time_id, timeframe)
);

CREATE INDEX idx_technical_security ON technical_indicators(security_id);
CREATE INDEX idx_technical_time ON technical_indicators(time_id);
CREATE INDEX idx_technical_timeframe ON technical_indicators(timeframe);

COMMENT ON TABLE technical_indicators IS 'Technical analysis - uses security_id FK';
```

---

## 4. Trading Operations Tables

### 4.1 Trading Cycles

```sql
CREATE TABLE trading_cycles (
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Cycle Info
    date DATE NOT NULL UNIQUE,
    cycle_state VARCHAR(50) NOT NULL,  -- 'scanning', 'evaluating', 'trading', 'monitoring', 'closed'
    phase VARCHAR(50),  -- 'pre-market', 'opening-range', 'morning', 'midday', 'power-hour', 'closed'
    
    -- Session Configuration
    mode VARCHAR(20) NOT NULL DEFAULT 'supervised',  -- 'autonomous', 'supervised', 'normal', 'aggressive', 'conservative'
    configuration JSONB,  -- Additional configuration as JSON
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    stopped_at TIMESTAMP WITH TIME ZONE,
    
    -- Performance Summary
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

### 4.2 Positions

```sql
CREATE TABLE positions (
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
    pattern VARCHAR(50),   -- 'bull_flag', 'cup_and_handle', etc.
    catalyst VARCHAR(255), -- News catalyst that drove the trade
    
    -- Timing
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE,
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_quantity CHECK (quantity > 0),
    CONSTRAINT chk_side CHECK (side IN ('long', 'short'))
);

CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);

COMMENT ON TABLE positions IS 'Trading positions - uses security_id FK (NOT symbol)';
```

### 4.3 Orders

```sql
CREATE TABLE orders (
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
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
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
    
    -- Market Data (at time of scan)
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
    
    -- Selection
    selected_for_trading BOOLEAN DEFAULT false,
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scan_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_security ON scan_results(security_id);
CREATE INDEX idx_scan_rank ON scan_results(cycle_id, rank);
CREATE INDEX idx_scan_timestamp ON scan_results(scan_timestamp DESC);

COMMENT ON TABLE scan_results IS 'Market scan candidates - uses security_id FK';
```

### 4.5 Risk Events

```sql
CREATE TABLE risk_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event Classification
    event_type VARCHAR(50) NOT NULL,  -- 'daily_loss_limit', 'position_limit', 'emergency_stop', etc.
    severity VARCHAR(20) NOT NULL,     -- 'info', 'warning', 'critical'
    
    -- Context
    cycle_id UUID REFERENCES trading_cycles(cycle_id),
    position_id UUID REFERENCES positions(position_id),
    
    -- Event Details
    message TEXT NOT NULL,
    threshold_value DECIMAL(12, 4),
    actual_value DECIMAL(12, 4),
    
    -- Action Taken
    action_taken VARCHAR(100),  -- 'rejected_trade', 'closed_position', 'emergency_stop', etc.
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_risk_events_type ON risk_events(event_type);
CREATE INDEX idx_risk_events_severity ON risk_events(severity);
CREATE INDEX idx_risk_events_cycle ON risk_events(cycle_id);
CREATE INDEX idx_risk_events_created ON risk_events(created_at DESC);

COMMENT ON TABLE risk_events IS 'Risk management event log';
```

---

## 5. Views & Materialized Views

### 5.1 Latest Securities View (Materialized)

```sql
CREATE MATERIALIZED VIEW v_securities_latest AS
SELECT 
    s.security_id,
    s.symbol,
    s.company_name,
    sec.sector_name,
    th.close AS last_price,
    th.volume AS last_volume,
    td.timestamp AS last_update
FROM securities s
LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
LEFT JOIN LATERAL (
    SELECT th2.close, th2.volume, th2.time_id
    FROM trading_history th2
    WHERE th2.security_id = s.security_id
    ORDER BY th2.time_id DESC
    LIMIT 1
) th ON true
LEFT JOIN time_dimension td ON td.time_id = th.time_id
WHERE s.is_active = true;

CREATE UNIQUE INDEX idx_v_securities_latest ON v_securities_latest(security_id);
CREATE INDEX idx_v_securities_symbol ON v_securities_latest(symbol);

COMMENT ON MATERIALIZED VIEW v_securities_latest IS 'Cached latest price for active securities';
```

### 5.2 Latest Scan View (Materialized)

```sql
CREATE MATERIALIZED VIEW v_scan_latest AS
SELECT 
    sr.scan_id,
    sr.cycle_id,
    s.symbol,
    s.company_name,
    sr.rank,
    sr.final_score,
    sr.price,
    sr.volume,
    sr.pattern,
    sr.catalyst_type,
    sr.selected_for_trading,
    sr.scan_timestamp
FROM scan_results sr
JOIN securities s ON s.security_id = sr.security_id
WHERE sr.cycle_id = (
    SELECT cycle_id FROM trading_cycles ORDER BY date DESC LIMIT 1
);

CREATE INDEX idx_v_scan_latest_rank ON v_scan_latest(rank);

COMMENT ON MATERIALIZED VIEW v_scan_latest IS 'Latest scan results with symbols';
```

---

## 6. Helper Functions

### 6.1 Get or Create Security

```sql
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR(10))
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    -- Try to find existing security
    SELECT security_id INTO v_security_id
    FROM securities
    WHERE symbol = UPPER(p_symbol);
    
    -- If not found, create it
    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange)
        VALUES (UPPER(p_symbol), 'UNKNOWN')
        RETURNING security_id INTO v_security_id;
    END IF;
    
    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_or_create_security IS 'Get security_id for symbol, creating if needed';
```

### 6.2 Get or Create Time

```sql
CREATE OR REPLACE FUNCTION get_or_create_time(p_timestamp TIMESTAMP WITH TIME ZONE)
RETURNS BIGINT AS $$
DECLARE
    v_time_id BIGINT;
    v_date DATE;
    v_hour INTEGER;
    v_is_market_hours BOOLEAN;
    v_market_session VARCHAR(20);
BEGIN
    -- Try to find existing time entry
    SELECT time_id INTO v_time_id
    FROM time_dimension
    WHERE timestamp = p_timestamp;
    
    -- If not found, create it
    IF v_time_id IS NULL THEN
        v_date := p_timestamp::DATE;
        v_hour := EXTRACT(HOUR FROM p_timestamp AT TIME ZONE 'America/New_York');
        
        -- Determine market hours (9:30 AM - 4:00 PM ET)
        v_is_market_hours := (
            v_hour >= 9 AND v_hour < 16 AND
            EXTRACT(DOW FROM v_date) BETWEEN 1 AND 5
        );
        
        -- Determine market session
        v_market_session := CASE
            WHEN v_hour < 9 THEN 'pre-market'
            WHEN v_hour >= 9 AND v_hour < 10 THEN 'open'
            WHEN v_hour >= 15 AND v_hour < 16 THEN 'close'
            WHEN v_hour >= 16 THEN 'after-hours'
            ELSE 'regular'
        END;
        
        INSERT INTO time_dimension (
            timestamp, date, year, month, day, day_of_week,
            hour, minute, is_market_hours, is_trading_day, market_session
        ) VALUES (
            p_timestamp,
            v_date,
            EXTRACT(YEAR FROM v_date),
            EXTRACT(MONTH FROM v_date),
            EXTRACT(DAY FROM v_date),
            EXTRACT(DOW FROM v_date),
            v_hour,
            EXTRACT(MINUTE FROM p_timestamp),
            v_is_market_hours,
            EXTRACT(DOW FROM v_date) BETWEEN 1 AND 5,
            v_market_session
        )
        RETURNING time_id INTO v_time_id;
    END IF;
    
    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_or_create_time IS 'Get time_id for timestamp, creating if needed';
```

### 6.3 Update Position P&L

```sql
CREATE OR REPLACE FUNCTION update_position_pnl(
    p_position_id UUID,
    p_current_price DECIMAL(12, 4)
)
RETURNS VOID AS $$
DECLARE
    v_entry_price DECIMAL(12, 4);
    v_quantity INTEGER;
    v_side VARCHAR(10);
    v_unrealized_pnl DECIMAL(12, 2);
    v_unrealized_pnl_pct DECIMAL(8, 4);
BEGIN
    -- Get position details
    SELECT entry_price, quantity, side
    INTO v_entry_price, v_quantity, v_side
    FROM positions
    WHERE position_id = p_position_id;
    
    -- Calculate P&L based on side
    IF v_side = 'long' THEN
        v_unrealized_pnl := (p_current_price - v_entry_price) * v_quantity;
    ELSE
        v_unrealized_pnl := (v_entry_price - p_current_price) * v_quantity;
    END IF;
    
    v_unrealized_pnl_pct := (v_unrealized_pnl / (v_entry_price * v_quantity)) * 100;
    
    -- Update position
    UPDATE positions
    SET current_price = p_current_price,
        unrealized_pnl = v_unrealized_pnl,
        unrealized_pnl_pct = v_unrealized_pnl_pct,
        updated_at = NOW()
    WHERE position_id = p_position_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_position_pnl IS 'Update position with current price and P&L';
```

---

## 7. Indexes & Performance

### 7.1 Performance Tips

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
    SET close = EXCLUDED.close, volume = EXCLUDED.volume
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
```

### 8.3 Opening a Position

```python
# Get security_id first
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
-- ✅ No orphaned records (should return 0)
SELECT COUNT(*) FROM news_sentiment ns
LEFT JOIN securities s ON s.security_id = ns.security_id
WHERE s.security_id IS NULL;

SELECT COUNT(*) FROM positions p
LEFT JOIN securities s ON s.security_id = p.security_id
WHERE s.security_id IS NULL;
```

---

## 10. Maintenance

### 10.1 Daily Tasks

```sql
-- Refresh materialized views
REFRESH MATERIALIZED VIEW CONCURRENTLY v_securities_latest;
REFRESH MATERIALIZED VIEW CONCURRENTLY v_scan_latest;
```

### 10.2 Weekly Tasks

```sql
ANALYZE trading_history;
ANALYZE news_sentiment;
ANALYZE positions;
ANALYZE orders;
```

### 10.3 Monthly Tasks

```sql
VACUUM ANALYZE;
REINDEX DATABASE catalyst_trading_production;
```

---

## Related Documents

- **architecture.md** - System architecture overview
- **functional-specification.md** - Service APIs and workflows
- **deployment-guide.md** - Database deployment steps

---

## Appendix: Table Summary

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

**Total Tables**: 11 | **Views**: 2 | **Materialized Views**: 2 | **Helper Functions**: 3

---

**END OF DATABASE SCHEMA DOCUMENT**

*Production schema ONLY. Clean, normalized, ready for trading.* 🎩
