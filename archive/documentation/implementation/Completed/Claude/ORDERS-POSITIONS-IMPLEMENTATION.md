# MANDATORY: Orders and Positions Table Implementation

**Name of Application**: Catalyst Trading System  
**Name of file**: ORDERS-POSITIONS-IMPLEMENTATION.md  
**Version**: 1.0.0  
**Last Updated**: 2025-12-27  
**Purpose**: MANDATORY implementation requirements for order and position tracking  
**Authority**: This document is AUTHORITATIVE. Claude Code MUST follow these requirements.

---

## ⛔ CRITICAL: READ BEFORE ANY TRADING CODE CHANGES

### The Problem We're Fixing

The current system incorrectly stores order data in the `positions` table using `alpaca_order_id` and `alpaca_status` columns. **This is architecturally wrong** and causes:

1. **Lost audit trail** - Cannot track multiple orders per position
2. **Broken reconciliation** - Cannot match DB orders to Alpaca orders
3. **Missing bracket legs** - Stop loss and take profit orders have nowhere to go
4. **Impossible debugging** - "Why did this position close?" becomes unanswerable

### The Mandate

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ORDERS and POSITIONS are SEPARATE ENTITIES.                   │
│                                                                 │
│   • Orders = Instructions sent to broker                        │
│   • Positions = Actual holdings resulting from filled orders    │
│                                                                 │
│   A position can have MANY orders.                              │
│   An order belongs to AT MOST ONE position.                     │
│                                                                 │
│   NEVER store order data in the positions table.                │
│   NEVER skip creating order records.                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Conceptual Model

### 1.1 Entity Definitions

| Entity | Definition | Examples |
|--------|------------|----------|
| **Order** | A request sent to the broker to buy or sell | "Buy 100 AAPL at $150 limit" |
| **Position** | Shares actually held in the account | "Long 100 AAPL @ $149.95 avg" |

### 1.2 Relationship

```
One Position : Many Orders

Example: Long 100 AAPL position

  ORDER #1: BUY 100 AAPL @ $150 LIMIT     → Entry order (filled)
  ORDER #2: SELL 100 AAPL @ $147 STOP     → Stop loss (cancelled)
  ORDER #3: SELL 100 AAPL @ $155 LIMIT    → Take profit (filled)

All three orders belong to ONE position.
```

### 1.3 Lifecycle Diagram

```
SCAN RESULT                 ORDERS                         POSITION
    │                          │                               │
    │ "Buy AAPL"               │                               │
    ▼                          ▼                               │
┌─────────┐            ┌──────────────┐                        │
│Candidate│───────────▶│ Entry Order  │                        │
│ Found   │  create    │ status:submit│                        │
└─────────┘            └──────┬───────┘                        │
                              │                                │
                              │ Alpaca fills                   │
                              ▼                                ▼
                       ┌──────────────┐                ┌──────────────┐
                       │ Entry Order  │───────────────▶│   Position   │
                       │ status:filled│    creates     │ status: open │
                       └──────────────┘                └──────┬───────┘
                                                              │
                       ┌──────────────┐                       │
                       │  Stop Loss   │◀──────────────────────┤
                       │ Order created│    protection         │
                       └──────────────┘                       │
                                                              │
                       ┌──────────────┐                       │
                       │ Take Profit  │◀──────────────────────┘
                       │ Order created│    protection
                       └──────────────┘
                              │
                              │ Price hits TP
                              ▼
                       ┌──────────────┐                ┌──────────────┐
                       │ Take Profit  │───────────────▶│   Position   │
                       │ status:filled│    closes      │status: closed│
                       └──────────────┘                └──────────────┘
                              │
                              │ OCO cancels SL
                              ▼
                       ┌──────────────┐
                       │  Stop Loss   │
                       │status:cancel │
                       └──────────────┘
```

---

## 2. Database Schema

### 2.1 Orders Table (REQUIRED)

```sql
-- ============================================================================
-- ORDERS TABLE - MANDATORY
-- Every order sent to Alpaca MUST have a row in this table
-- ============================================================================

CREATE TABLE IF NOT EXISTS orders (
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
    
    -- Order Status
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

-- Comments
COMMENT ON TABLE orders IS 'All orders sent to Alpaca - NEVER store order data in positions table';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created, then updated';
COMMENT ON COLUMN orders.parent_order_id IS 'For bracket orders: links take_profit and stop_loss to entry order';
COMMENT ON COLUMN orders.order_class IS 'bracket = entry with legs, oco = one-cancels-other, oto = one-triggers-other';
```

### 2.2 Positions Table (CORRECTED)

```sql
-- ============================================================================
-- POSITIONS TABLE - CORRECTED
-- Represents actual holdings - NO order columns
-- ============================================================================

CREATE TABLE IF NOT EXISTS positions (
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
    current_price DECIMAL(12, 4),                        -- Last known price
    current_value DECIMAL(12, 2),                        -- quantity * current_price
    
    -- Risk Parameters
    stop_loss DECIMAL(12, 4),                            -- Current stop loss level
    take_profit DECIMAL(12, 4),                          -- Current take profit level
    risk_amount DECIMAL(12, 2),                          -- Dollar risk on position
    
    -- P&L Tracking
    unrealized_pnl DECIMAL(12, 2),
    unrealized_pnl_pct DECIMAL(8, 4),
    realized_pnl DECIMAL(12, 2),
    realized_pnl_pct DECIMAL(8, 4),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
        -- Lifecycle: pending → open → closed
        --            pending → cancelled (if entry never fills)
    
    -- Analysis Context
    pattern VARCHAR(50),                                 -- Pattern that triggered entry
    catalyst VARCHAR(255),                               -- News catalyst
    entry_score DECIMAL(5, 2),                           -- Conviction score at entry
    
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
-- ⛔ REMOVED COLUMNS - These should NOT exist in positions table:
--    alpaca_order_id   -- WRONG: Orders have their own table
--    alpaca_status     -- WRONG: Order status belongs in orders table
-- ============================================================================

-- Indexes
CREATE INDEX idx_positions_cycle ON positions(cycle_id);
CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';

COMMENT ON TABLE positions IS 'Actual holdings - order data is in the orders table';
```

### 2.3 Migration Script

```sql
-- ============================================================================
-- MIGRATION: Add orders table, clean positions table
-- Run this to fix the current schema
-- ============================================================================

BEGIN;

-- Step 1: Create orders table if not exists
-- (Use the CREATE TABLE from section 2.1 above)

-- Step 2: Migrate existing order data from positions to orders
INSERT INTO orders (
    position_id,
    security_id,
    cycle_id,
    side,
    order_type,
    quantity,
    alpaca_order_id,
    status,
    filled_qty,
    filled_avg_price,
    submitted_at,
    filled_at,
    created_at,
    updated_at
)
SELECT 
    p.position_id,
    p.security_id,
    p.cycle_id,
    CASE WHEN p.side = 'long' THEN 'buy' ELSE 'sell' END,  -- Convert side
    'market',                                                -- Assume market orders
    p.quantity,
    p.alpaca_order_id,
    COALESCE(p.alpaca_status, 'filled'),                    -- Assume filled if no status
    p.quantity,                                              -- Assume fully filled
    p.entry_price,
    p.entry_time,
    CASE WHEN p.status = 'closed' THEN p.exit_time ELSE NULL END,
    p.created_at,
    p.updated_at
FROM positions p
WHERE p.alpaca_order_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM orders o WHERE o.alpaca_order_id = p.alpaca_order_id
  );

-- Step 3: Drop order columns from positions (AFTER verifying migration)
-- ⚠️ Only run after confirming orders table has the data
-- ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_order_id;
-- ALTER TABLE positions DROP COLUMN IF EXISTS alpaca_status;

COMMIT;
```

---

## 3. Code Patterns

### 3.1 CORRECT: Creating an Entry Order

```python
async def submit_entry_order(
    security_id: int,
    cycle_id: UUID,
    side: str,           # 'buy' or 'sell'
    quantity: int,
    order_type: str,     # 'market', 'limit', etc.
    limit_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None
) -> UUID:
    """
    Submit an entry order to Alpaca and track in orders table.
    Position is created ONLY when order fills.
    """
    
    # Step 1: Create order record FIRST (before sending to Alpaca)
    order_id = await db.execute("""
        INSERT INTO orders (
            security_id, cycle_id, side, order_type, quantity,
            limit_price, status, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, 'created', NOW())
        RETURNING order_id
    """, security_id, cycle_id, side, order_type, quantity, limit_price)
    
    # Step 2: Submit to Alpaca
    try:
        if order_type == 'bracket':
            alpaca_order = alpaca_client.submit_order(
                symbol=symbol,
                qty=quantity,
                side=side,
                type='market',
                time_in_force='day',
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=take_profit),
                stop_loss=StopLossRequest(stop_price=stop_loss)
            )
        else:
            alpaca_order = alpaca_client.submit_order(
                symbol=symbol,
                qty=quantity,
                side=side,
                type=order_type,
                time_in_force='day',
                limit_price=limit_price
            )
        
        # Step 3: Update order with Alpaca response
        await db.execute("""
            UPDATE orders SET
                alpaca_order_id = $1,
                alpaca_client_order_id = $2,
                status = 'submitted',
                submitted_at = NOW(),
                updated_at = NOW()
            WHERE order_id = $3
        """, alpaca_order.id, alpaca_order.client_order_id, order_id)
        
        # Step 4: If bracket order, create leg order records
        if order_type == 'bracket' and alpaca_order.legs:
            for leg in alpaca_order.legs:
                await db.execute("""
                    INSERT INTO orders (
                        parent_order_id, security_id, cycle_id,
                        side, order_type, quantity,
                        limit_price, stop_price,
                        alpaca_order_id, status, order_class,
                        submitted_at, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'accepted', 'bracket', NOW(), NOW())
                """, 
                    order_id,  # parent_order_id
                    security_id,
                    cycle_id,
                    'sell',    # Exit orders are always opposite side
                    'limit' if leg.limit_price else 'stop',
                    quantity,
                    leg.limit_price,
                    leg.stop_price,
                    leg.id
                )
        
        return order_id
        
    except Exception as e:
        # Update order as rejected
        await db.execute("""
            UPDATE orders SET
                status = 'rejected',
                rejection_reason = $1,
                updated_at = NOW()
            WHERE order_id = $2
        """, str(e), order_id)
        raise
```

### 3.2 CORRECT: Processing a Fill

```python
async def process_order_fill(alpaca_order_id: str, fill_data: dict):
    """
    Process an order fill from Alpaca.
    Creates position if entry order, updates position if exit order.
    """
    
    # Step 1: Find the order
    order = await db.fetchrow("""
        SELECT o.*, s.symbol 
        FROM orders o
        JOIN securities s ON o.security_id = s.security_id
        WHERE o.alpaca_order_id = $1
    """, alpaca_order_id)
    
    if not order:
        raise ValueError(f"Order not found: {alpaca_order_id}")
    
    # Step 2: Update order with fill info
    await db.execute("""
        UPDATE orders SET
            status = $1,
            filled_qty = $2,
            filled_avg_price = $3,
            filled_at = $4,
            updated_at = NOW()
        WHERE order_id = $5
    """, 
        'filled' if fill_data['filled_qty'] == order['quantity'] else 'partial_fill',
        fill_data['filled_qty'],
        fill_data['filled_avg_price'],
        fill_data['filled_at'],
        order['order_id']
    )
    
    # Step 3: Handle based on order type
    if order['position_id'] is None:
        # This is an ENTRY order - create position
        position_id = await db.execute("""
            INSERT INTO positions (
                cycle_id, security_id, side, quantity,
                entry_price, entry_time, status,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, 'open', NOW(), NOW())
            RETURNING position_id
        """,
            order['cycle_id'],
            order['security_id'],
            'long' if order['side'] == 'buy' else 'short',
            fill_data['filled_qty'],
            fill_data['filled_avg_price'],
            fill_data['filled_at']
        )
        
        # Link order to position
        await db.execute("""
            UPDATE orders SET position_id = $1, updated_at = NOW()
            WHERE order_id = $2
        """, position_id, order['order_id'])
        
        # Link any bracket legs to position too
        await db.execute("""
            UPDATE orders SET position_id = $1, updated_at = NOW()
            WHERE parent_order_id = $2
        """, position_id, order['order_id'])
        
    else:
        # This is an EXIT order - update position
        position = await db.fetchrow("""
            SELECT * FROM positions WHERE position_id = $1
        """, order['position_id'])
        
        new_qty = position['quantity'] - fill_data['filled_qty']
        
        if new_qty <= 0:
            # Position fully closed
            realized_pnl = calculate_pnl(
                position['entry_price'],
                fill_data['filled_avg_price'],
                position['quantity'],
                position['side']
            )
            
            await db.execute("""
                UPDATE positions SET
                    quantity = 0,
                    exit_price = $1,
                    exit_time = $2,
                    realized_pnl = $3,
                    status = 'closed',
                    updated_at = NOW()
                WHERE position_id = $4
            """,
                fill_data['filled_avg_price'],
                fill_data['filled_at'],
                realized_pnl,
                order['position_id']
            )
            
            # Cancel any remaining open orders for this position
            await db.execute("""
                UPDATE orders SET
                    status = 'cancelled',
                    cancel_reason = 'Position closed',
                    cancelled_at = NOW(),
                    updated_at = NOW()
                WHERE position_id = $1
                  AND status IN ('submitted', 'accepted', 'pending_new')
            """, order['position_id'])
            
        else:
            # Partial exit
            await db.execute("""
                UPDATE positions SET
                    quantity = $1,
                    updated_at = NOW()
                WHERE position_id = $2
            """, new_qty, order['position_id'])
```

### 3.3 CORRECT: Order Reconciliation (Doctor Claude)

```python
async def reconcile_orders_with_alpaca():
    """
    Compare orders table with Alpaca orders.
    This is the CORRECT way to do reconciliation.
    """
    
    issues = []
    
    # Get all non-terminal orders from DB
    db_orders = await db.fetch("""
        SELECT 
            o.order_id,
            o.alpaca_order_id,
            o.status as db_status,
            o.filled_qty as db_filled_qty,
            o.filled_avg_price as db_filled_price,
            s.symbol,
            o.side,
            o.quantity
        FROM orders o
        JOIN securities s ON o.security_id = s.security_id
        WHERE o.alpaca_order_id IS NOT NULL
          AND o.status NOT IN ('filled', 'cancelled', 'rejected', 'expired')
          AND o.submitted_at > NOW() - INTERVAL '7 days'
    """)
    
    for db_order in db_orders:
        try:
            # Fetch from Alpaca
            alpaca_order = alpaca_client.get_order_by_id(db_order['alpaca_order_id'])
            alpaca_status = alpaca_order.status.value.lower()
            
            # Compare status
            if alpaca_status != db_order['db_status']:
                issues.append({
                    "type": "ORDER_STATUS_MISMATCH",
                    "severity": "WARNING",
                    "order_id": str(db_order['order_id']),
                    "alpaca_order_id": db_order['alpaca_order_id'],
                    "symbol": db_order['symbol'],
                    "db_status": db_order['db_status'],
                    "alpaca_status": alpaca_status,
                    "fix": f"""
                        UPDATE orders SET 
                            status = '{alpaca_status}',
                            filled_qty = {alpaca_order.filled_qty or 0},
                            filled_avg_price = {alpaca_order.filled_avg_price or 'NULL'},
                            updated_at = NOW()
                        WHERE order_id = '{db_order['order_id']}'
                    """
                })
                
        except Exception as e:
            if 'not found' in str(e).lower():
                issues.append({
                    "type": "ORDER_NOT_FOUND_IN_ALPACA",
                    "severity": "WARNING",
                    "order_id": str(db_order['order_id']),
                    "alpaca_order_id": db_order['alpaca_order_id'],
                    "fix": f"""
                        UPDATE orders SET 
                            status = 'expired',
                            updated_at = NOW()
                        WHERE order_id = '{db_order['order_id']}'
                    """
                })
    
    return issues
```

---

## 4. Anti-Patterns (FORBIDDEN)

### 4.1 ⛔ NEVER: Store order ID in positions table

```python
# ⛔ WRONG - DO NOT DO THIS
await db.execute("""
    UPDATE positions SET
        alpaca_order_id = $1,
        alpaca_status = $2
    WHERE position_id = $3
""", alpaca_order.id, alpaca_order.status, position_id)
```

### 4.2 ⛔ NEVER: Skip creating order record

```python
# ⛔ WRONG - DO NOT DO THIS
alpaca_order = alpaca_client.submit_order(...)
# Missing: No order record created in database!
await db.execute("""
    INSERT INTO positions (...) VALUES (...)
""")
```

### 4.3 ⛔ NEVER: Query positions for order status

```python
# ⛔ WRONG - DO NOT DO THIS
stuck_orders = await db.fetch("""
    SELECT * FROM positions
    WHERE alpaca_status = 'submitted'
      AND entry_time < NOW() - INTERVAL '5 minutes'
""")
```

### 4.4 ✅ CORRECT: Query orders table for order status

```python
# ✅ CORRECT
stuck_orders = await db.fetch("""
    SELECT o.*, s.symbol, p.position_id
    FROM orders o
    JOIN securities s ON o.security_id = s.security_id
    LEFT JOIN positions p ON o.position_id = p.position_id
    WHERE o.status IN ('submitted', 'accepted', 'pending_new')
      AND o.submitted_at < NOW() - INTERVAL '5 minutes'
""")
```

---

## 5. Queries Reference

### 5.1 Get all orders for a position

```sql
SELECT 
    o.order_id,
    o.side,
    o.order_type,
    o.quantity,
    o.limit_price,
    o.stop_price,
    o.status,
    o.filled_qty,
    o.filled_avg_price,
    o.submitted_at,
    o.filled_at,
    CASE 
        WHEN o.parent_order_id IS NULL THEN 'entry'
        WHEN o.order_type = 'limit' THEN 'take_profit'
        WHEN o.order_type = 'stop' THEN 'stop_loss'
        ELSE 'unknown'
    END as order_purpose
FROM orders o
WHERE o.position_id = $1
ORDER BY o.created_at;
```

### 5.2 Get pending orders

```sql
SELECT 
    o.*,
    s.symbol,
    p.status as position_status
FROM orders o
JOIN securities s ON o.security_id = s.security_id
LEFT JOIN positions p ON o.position_id = p.position_id
WHERE o.status IN ('submitted', 'accepted', 'pending_new', 'partial_fill')
ORDER BY o.submitted_at;
```

### 5.3 Get order fill history for a position

```sql
SELECT 
    o.filled_at,
    o.side,
    o.filled_qty,
    o.filled_avg_price,
    o.filled_qty * o.filled_avg_price as fill_value
FROM orders o
WHERE o.position_id = $1
  AND o.status IN ('filled', 'partial_fill')
ORDER BY o.filled_at;
```

### 5.4 Calculate position P&L from orders

```sql
SELECT 
    p.position_id,
    s.symbol,
    -- Entry orders (buys for long, sells for short)
    SUM(CASE WHEN o.side = 'buy' THEN o.filled_qty * o.filled_avg_price ELSE 0 END) as total_bought,
    SUM(CASE WHEN o.side = 'buy' THEN o.filled_qty ELSE 0 END) as qty_bought,
    -- Exit orders (sells for long, buys for short)
    SUM(CASE WHEN o.side = 'sell' THEN o.filled_qty * o.filled_avg_price ELSE 0 END) as total_sold,
    SUM(CASE WHEN o.side = 'sell' THEN o.filled_qty ELSE 0 END) as qty_sold,
    -- P&L
    SUM(CASE WHEN o.side = 'sell' THEN o.filled_qty * o.filled_avg_price ELSE 0 END) -
    SUM(CASE WHEN o.side = 'buy' THEN o.filled_qty * o.filled_avg_price ELSE 0 END) as realized_pnl
FROM positions p
JOIN securities s ON p.security_id = s.security_id
LEFT JOIN orders o ON o.position_id = p.position_id AND o.status = 'filled'
WHERE p.position_id = $1
GROUP BY p.position_id, s.symbol;
```

---

## 6. Doctor Claude Updates Required

Doctor Claude's `trade_watchdog.py` must be updated to:

1. Query `orders` table instead of `positions.alpaca_*` columns
2. Reconcile orders (not positions) with Alpaca
3. Track order status mismatches properly
4. Handle bracket order legs

See updated `trade_watchdog.py` implementation in the deployment package.

---

## 7. Implementation Checklist

### Phase 1: Schema Migration
- [ ] Create `orders` table with all columns
- [ ] Add indexes for performance
- [ ] Migrate existing order data from positions
- [ ] Verify migration successful

### Phase 2: Code Updates
- [ ] Update `trading-service.py` to use orders table
- [ ] Update `alpaca_trader.py` order submission
- [ ] Update `alpaca_trader.py` fill processing
- [ ] Update Doctor Claude `trade_watchdog.py`
- [ ] Update any other services that touch orders

### Phase 3: Cleanup
- [ ] Remove `alpaca_order_id` from positions table
- [ ] Remove `alpaca_status` from positions table
- [ ] Update all queries to use orders table
- [ ] Verify no code references old columns

### Phase 4: Verification
- [ ] Test order submission flow
- [ ] Test fill processing flow
- [ ] Test bracket order handling
- [ ] Test Doctor Claude reconciliation
- [ ] Run full trading cycle in paper mode

---

## 8. Summary

| Rule | Description |
|------|-------------|
| **Orders table is mandatory** | Every order sent to Alpaca MUST have a row |
| **Positions don't store order data** | No `alpaca_order_id` or `alpaca_status` in positions |
| **One position, many orders** | Entry, stop loss, take profit = 3+ orders per position |
| **Order first, position after** | Create order record BEFORE sending to Alpaca |
| **Position on fill only** | Position created when entry order fills, not before |
| **Reconcile orders** | Doctor Claude compares orders table to Alpaca orders |

---

**This document is AUTHORITATIVE. Claude Code MUST follow these requirements.**

**Violations of these patterns will cause data integrity issues and make the system impossible to debug.**

---

*Document created: 2025-12-27*
*Authority: Craig (System Owner)*
