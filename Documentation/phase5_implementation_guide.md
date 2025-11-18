# Catalyst Trading System - Phase 5: Schema Logic Fixes
**Implementation Guide for Claude Code**

## 🎯 Executive Summary
The Catalyst Trading System database has been upgraded to v6.0 with full 3NF normalization. All Python services are currently coded against older denormalized schemas and need systematic updates to use the new normalized structure. This document provides clear instructions for Claude Code to implement these fixes.

## 📊 Current State
- **Database**: v6.0 schema (normalized, 3NF) ✅ COMPLETE
- **Services**: Using old schema patterns ❌ NEEDS FIXING
- **Impact**: Services cannot communicate with database until fixed
- **Estimated Time**: 16 hours total (2-3 hours per service)

## 🔑 Core Pattern Changes

### CRITICAL RULE: No Symbol Duplication
- **Symbol VARCHAR** exists ONLY in `securities` table
- All other tables use `security_id INTEGER` foreign key
- Always JOIN to `securities` table to get symbol names

### Before & After Patterns

#### Pattern 1: Inserting Data
```python
# ❌ OLD (Denormalized) - WRONG
await conn.execute(
    "INSERT INTO scan_results (symbol, score) VALUES ($1, $2)",
    'AAPL', 95.5
)

# ✅ NEW (Normalized) - CORRECT
security_id = await conn.fetchval(
    "SELECT get_or_create_security($1, $2, $3)",
    'AAPL', 'Apple Inc.', 'NASDAQ'
)
await conn.execute(
    "INSERT INTO scan_results (security_id, cycle_id, score) VALUES ($1, $2, $3)",
    security_id, cycle_id, 95.5
)
```

#### Pattern 2: Querying Data
```python
# ❌ OLD (Denormalized) - WRONG
results = await conn.fetch(
    "SELECT symbol, score FROM scan_results WHERE score > 80"
)

# ✅ NEW (Normalized) - CORRECT
results = await conn.fetch("""
    SELECT s.symbol, sr.score 
    FROM scan_results sr
    JOIN securities s ON s.security_id = sr.security_id
    WHERE sr.score > 80
""")
```

#### Pattern 3: Using Time Dimension
```python
# ❌ OLD - WRONG
await conn.execute(
    "INSERT INTO trading_history (symbol, timestamp, close) VALUES ($1, $2, $3)",
    'AAPL', datetime.now(), 150.50
)

# ✅ NEW - CORRECT
security_id = await conn.fetchval("SELECT get_or_create_security($1)", 'AAPL')
time_id = await conn.fetchval("SELECT get_or_create_time($1)", datetime.now())
await conn.execute(
    "INSERT INTO trading_history (security_id, time_id, close) VALUES ($1, $2, $3)",
    security_id, time_id, 150.50
)
```

## 📁 Files to Modify

### Service Files Location
```
/workspaces/catalyst-trading-system/catalyst-trading-system/services/
├── scanner-service.py
├── news-service.py  
├── technical-service.py
├── risk-manager-service.py
├── trading-service.py
└── workflow-service.py
```

## 🔧 Service-by-Service Fixes

### 1. Scanner Service (`scanner-service.py`)
**Tables Used**: `scan_results`, `securities`
**Priority**: HIGHEST (feeds the pipeline)

#### Required Changes:
1. **Database Queries**:
   - Find all `INSERT INTO scan_results` statements
   - Replace `symbol` column with `security_id`
   - Add `get_or_create_security()` calls before inserts

2. **Query Updates**:
   ```python
   # Find patterns like:
   "SELECT symbol, * FROM scan_results"
   
   # Replace with:
   """SELECT s.symbol, sr.* 
      FROM scan_results sr
      JOIN securities s ON s.security_id = sr.security_id"""
   ```

3. **Scan Results Structure**:
   ```python
   # OLD structure
   scan_result = {
       "symbol": "AAPL",
       "score": 95.5
   }
   
   # NEW structure  
   scan_result = {
       "security_id": security_id,  # Get via helper function
       "cycle_id": current_cycle_id,
       "score": 95.5
   }
   ```

### 2. News Service (`news-service.py`)
**Tables Used**: `news_sentiment`, `securities`, `time_dimension`

#### Required Changes:
1. **News Sentiment Inserts**:
   ```python
   # Add at top of insert function
   security_id = await conn.fetchval(
       "SELECT get_or_create_security($1)", symbol
   )
   time_id = await conn.fetchval(
       "SELECT get_or_create_time($1)", published_at
   )
   
   # Update INSERT statement
   await conn.execute("""
       INSERT INTO news_sentiment 
       (security_id, time_id, headline, sentiment_score, is_catalyst)
       VALUES ($1, $2, $3, $4, $5)
   """, security_id, time_id, headline, score, is_catalyst)
   ```

2. **Query Pattern**:
   ```python
   # Get news with symbols
   news_items = await conn.fetch("""
       SELECT 
           s.symbol,
           ns.headline,
           ns.sentiment_score,
           td.full_timestamp as published_at
       FROM news_sentiment ns
       JOIN securities s ON s.security_id = ns.security_id
       JOIN time_dimension td ON td.time_id = ns.time_id
       WHERE ns.is_catalyst = true
       ORDER BY td.full_timestamp DESC
   """)
   ```

### 3. Technical Service (`technical-service.py`)
**Tables Used**: `technical_indicators`, `trading_history`, `securities`, `time_dimension`

#### Required Changes:
1. **Technical Indicator Inserts**:
   ```python
   async def save_indicators(symbol: str, indicators: dict):
       # Get IDs
       security_id = await conn.fetchval(
           "SELECT get_or_create_security($1)", symbol
       )
       time_id = await conn.fetchval(
           "SELECT get_or_create_time($1)", datetime.now()
       )
       
       # Insert with FKs
       await conn.execute("""
           INSERT INTO technical_indicators
           (security_id, time_id, rsi_14, macd_value, sma_20, sma_50)
           VALUES ($1, $2, $3, $4, $5, $6)
       """, security_id, time_id, 
            indicators['rsi'], indicators['macd'],
            indicators['sma_20'], indicators['sma_50'])
   ```

2. **Reading Historical Data**:
   ```python
   # Get OHLCV data
   history = await conn.fetch("""
       SELECT 
           s.symbol,
           td.full_timestamp,
           th.open, th.high, th.low, th.close, th.volume
       FROM trading_history th
       JOIN securities s ON s.security_id = th.security_id
       JOIN time_dimension td ON td.time_id = th.time_id
       WHERE s.symbol = $1
       AND td.full_timestamp >= $2
       ORDER BY td.full_timestamp
   """, symbol, start_date)
   ```

### 4. Risk Manager Service (`risk-manager-service.py`)
**Tables Used**: `positions`, `risk_events`, `securities`

#### Required Changes:
1. **Position Management**:
   ```python
   async def open_position(symbol: str, quantity: int, entry_price: float):
       # Get security_id
       security_id = await conn.fetchval(
           "SELECT get_or_create_security($1)", symbol
       )
       
       # Insert position
       position_id = await conn.fetchval("""
           INSERT INTO positions 
           (security_id, cycle_id, quantity, side, entry_price, status)
           VALUES ($1, $2, $3, $4, $5, 'open')
           RETURNING position_id
       """, security_id, cycle_id, quantity, 'long', entry_price)
       
       return position_id
   ```

2. **Position Queries**:
   ```python
   # Get all open positions with symbols
   positions = await conn.fetch("""
       SELECT 
           p.position_id,
           s.symbol,
           p.quantity,
           p.entry_price,
           p.current_price,
           p.unrealized_pnl
       FROM positions p
       JOIN securities s ON s.security_id = p.security_id
       WHERE p.status = 'open'
   """)
   ```

3. **Risk Events**:
   ```python
   # Log risk event
   await conn.execute("""
       INSERT INTO risk_events
       (event_type, severity, position_id, description, triggered_at)
       VALUES ($1, $2, $3, $4, NOW())
   """, 'stop_loss_triggered', 'warning', position_id, description)
   ```

### 5. Trading Service (`trading-service.py`)
**Tables Used**: `orders`, `positions`, `securities`

#### Required Changes:
1. **Order Placement**:
   ```python
   async def place_order(symbol: str, order_type: str, quantity: int):
       # Get security_id
       security_id = await conn.fetchval(
           "SELECT get_or_create_security($1)", symbol
       )
       
       # Insert order
       order_id = await conn.fetchval("""
           INSERT INTO orders
           (security_id, position_id, order_type, side, quantity, status)
           VALUES ($1, $2, $3, $4, $5, 'pending')
           RETURNING order_id
       """, security_id, position_id, order_type, 'buy', quantity)
       
       return order_id
   ```

2. **Order Status Queries**:
   ```python
   # Get pending orders
   orders = await conn.fetch("""
       SELECT 
           o.order_id,
           s.symbol,
           o.order_type,
           o.quantity,
           o.status
       FROM orders o
       JOIN securities s ON s.security_id = o.security_id
       WHERE o.status IN ('pending', 'submitted')
   """)
   ```

### 6. Workflow Service (`workflow-service.py`)
**Tables Used**: `trading_cycles`, `scan_results`

#### Required Changes:
1. **Cycle Management** (minimal changes):
   ```python
   # Trading cycles don't use symbol/security_id directly
   # But queries that JOIN to other tables need updates
   
   async def get_cycle_performance(cycle_id: int):
       return await conn.fetchrow("""
           SELECT 
               tc.*,
               COUNT(DISTINCT sr.security_id) as securities_scanned,
               COUNT(DISTINCT p.position_id) as positions_opened
           FROM trading_cycles tc
           LEFT JOIN scan_results sr ON sr.cycle_id = tc.cycle_id
           LEFT JOIN positions p ON p.cycle_id = tc.cycle_id
           WHERE tc.cycle_id = $1
           GROUP BY tc.cycle_id
       """, cycle_id)
   ```

## 🧪 Testing Each Service

### After Each Service Update:
1. **Test Database Connection**:
   ```python
   # Add test function to each service
   async def test_db_connection():
       try:
           result = await conn.fetchval("SELECT 1")
           print(f"✅ Database connected")
           
           # Test helper functions
           security_id = await conn.fetchval(
               "SELECT get_or_create_security($1)", "TEST"
           )
           print(f"✅ Helper functions work: security_id={security_id}")
           
           return True
       except Exception as e:
           print(f"❌ Database error: {e}")
           return False
   ```

2. **Test Core Operations**:
   - Scanner: Test inserting scan results
   - News: Test sentiment insert/query
   - Technical: Test indicator calculations
   - Risk: Test position management
   - Trading: Test order placement
   - Workflow: Test cycle creation

## 📝 Implementation Checklist

### For Each Service:
- [ ] Backup original service file
- [ ] Search for all `symbol` column references
- [ ] Replace with `security_id` + JOIN patterns
- [ ] Add helper function calls before inserts
- [ ] Update all SELECT queries to use JOINs
- [ ] Test database operations
- [ ] Verify service starts without errors
- [ ] Test with sample data

## ⚠️ Common Pitfalls to Avoid

1. **Don't Store Symbols in Variables**:
   ```python
   # ❌ WRONG
   data = {"symbol": "AAPL", "price": 150}
   
   # ✅ CORRECT
   data = {"security_id": security_id, "price": 150}
   ```

2. **Always Use Helper Functions**:
   ```python
   # ❌ WRONG - Manual insert
   await conn.execute(
       "INSERT INTO securities (symbol) VALUES ($1)", 
       symbol
   )
   
   # ✅ CORRECT - Use helper
   security_id = await conn.fetchval(
       "SELECT get_or_create_security($1)", 
       symbol
   )
   ```

3. **Don't Forget Time Dimension**:
   ```python
   # Tables that need time_id:
   # - trading_history
   # - news_sentiment
   # - technical_indicators
   
   time_id = await conn.fetchval(
       "SELECT get_or_create_time($1)", 
       timestamp
   )
   ```

## 🎓 Helper Function Reference

### get_or_create_security
```sql
-- Usage: Returns security_id, creates if doesn't exist
SELECT get_or_create_security(
    'AAPL',           -- symbol (required)
    'Apple Inc.',     -- company_name (optional)
    'NASDAQ'          -- exchange (optional)
);
```

### get_or_create_time
```sql
-- Usage: Returns time_id, creates time dimension entry
SELECT get_or_create_time(
    '2025-11-18 09:30:00-05:00'::timestamptz
);
```

### insert_trading_data
```sql
-- Usage: Example helper for inserting OHLCV data
SELECT insert_trading_data(
    'AAPL',           -- symbol
    NOW(),            -- timestamp
    150.00,           -- open
    151.50,           -- high
    149.50,           -- low
    151.00,           -- close
    1000000           -- volume
);
```

## 🚀 Expected Outcomes

After completing Phase 5:
1. All services use normalized schema (v6.0)
2. No symbol duplication across tables
3. Proper foreign key relationships
4. Services can read/write to database
5. Ready for Phase 6 integration testing

## 📊 Success Metrics

- [ ] All 6 services updated
- [ ] Zero "symbol" columns except in securities table
- [ ] All queries use JOINs for symbol retrieval
- [ ] Helper functions used for all inserts
- [ ] Services start without database errors
- [ ] Test queries return expected data

## 🆘 If You Get Stuck

1. Check the database schema: `/workspaces/catalyst-trading-system/SDLC/2. Design/database-schema-mcp-v60.md`
2. Review the architecture: `/workspaces/catalyst-trading-system/SDLC/2. Design/architecture-mcp-v60.md`
3. Test helper functions directly in psql
4. Verify foreign key relationships exist
5. Check service logs for specific error messages

---

**Remember**: The goal is to make services communicate with the normalized v6.0 database. Every `symbol` reference should be replaced with `security_id` + JOIN pattern. Use helper functions for all inserts. Test frequently!