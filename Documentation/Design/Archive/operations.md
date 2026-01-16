# Catalyst Trading System - Operations Guide

**Name of Application**: Catalyst Trading System  
**Name of file**: operations.md  
**Version**: 1.0.0  
**Last Updated**: 2025-12-27  
**Purpose**: Core operational patterns, state machines, and workflows

---

## REVISION HISTORY

**v1.0.0 (2025-12-27)** - Initial creation
- Core trading workflow patterns
- Order state machine
- Position state machine
- Cycle state machine
- Data flow diagrams
- Reconciliation patterns

---

## Table of Contents

1. [Core Trading Pattern](#1-core-trading-pattern)
2. [Order State Machine](#2-order-state-machine)
3. [Position State Machine](#3-position-state-machine)
4. [Trading Cycle State Machine](#4-trading-cycle-state-machine)
5. [Entity Relationships](#5-entity-relationships)
6. [Data Flow Patterns](#6-data-flow-patterns)
7. [Reconciliation Patterns](#7-reconciliation-patterns)
8. [Error Handling Patterns](#8-error-handling-patterns)

---

## 1. Core Trading Pattern

### 1.1 The Golden Rule

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ORDER FIRST, POSITION AFTER                                   │
│                                                                 │
│   1. Create order record in database                            │
│   2. Submit order to Alpaca                                     │
│   3. Update order with Alpaca response                          │
│   4. Wait for fill                                              │
│   5. Create position when entry fills                           │
│   6. Create protection orders (SL/TP)                           │
│   7. Update position when exit fills                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Complete Trade Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      TRADE LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PHASE 1: DISCOVERY                                             │
│  ─────────────────                                              │
│                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│  │ Scanner  │────▶│ Analyze  │────▶│ Candidate│               │
│  │  Runs    │     │ Patterns │     │  Ready   │               │
│  └──────────┘     └──────────┘     └────┬─────┘               │
│                                         │                       │
│                                         ▼                       │
│  PHASE 2: ENTRY                    ┌──────────┐                │
│  ──────────────                    │   Risk   │                │
│                                    │ Approved │                │
│                                    └────┬─────┘                │
│                                         │                       │
│      ┌──────────────────────────────────┘                      │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│  │ Create   │────▶│ Submit   │────▶│  Order   │               │
│  │ ORDER #1 │     │ to Alpaca│     │ Accepted │               │
│  │ (entry)  │     │          │     │          │               │
│  └──────────┘     └──────────┘     └────┬─────┘               │
│                                         │                       │
│                                         │ Fill received         │
│                                         ▼                       │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│  │ ORDER #1 │────▶│ Create   │────▶│ POSITION │               │
│  │  Filled  │     │ POSITION │     │   Open   │               │
│  └──────────┘     └──────────┘     └────┬─────┘               │
│                                         │                       │
│                                         │                       │
│  PHASE 3: PROTECTION                    │                       │
│  ───────────────────                    │                       │
│                                         │                       │
│      ┌──────────────────────────────────┤                      │
│      │                                  │                       │
│      ▼                                  ▼                       │
│  ┌──────────┐                      ┌──────────┐               │
│  │ Create   │                      │ Create   │               │
│  │ ORDER #2 │                      │ ORDER #3 │               │
│  │(stop loss)│                     │(take prof)│              │
│  └────┬─────┘                      └────┬─────┘               │
│       │                                 │                       │
│       │ Both submitted to Alpaca        │                       │
│       │ as OCO (one-cancels-other)      │                       │
│       └─────────────┬───────────────────┘                      │
│                     │                                           │
│                     ▼                                           │
│  PHASE 4: MONITORING                                            │
│  ───────────────────                                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    POSITION OPEN                          │  │
│  │                                                           │  │
│  │   ORDER #2 (SL): status = accepted, watching...          │  │
│  │   ORDER #3 (TP): status = accepted, watching...          │  │
│  │                                                           │  │
│  │   Doctor Claude monitors every 5 minutes                 │  │
│  │   - Reconcile order status with Alpaca                   │  │
│  │   - Update unrealized P&L                                │  │
│  │   - Check for stuck orders                               │  │
│  │                                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                     │                                           │
│                     │ Price hits take profit                    │
│                     ▼                                           │
│  PHASE 5: EXIT                                                  │
│  ─────────────                                                  │
│                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│  │ ORDER #3 │────▶│ ORDER #2 │────▶│ POSITION │               │
│  │  Filled  │     │ Cancelled│     │  Closed  │               │
│  │  (TP)    │     │  (OCO)   │     │          │               │
│  └──────────┘     └──────────┘     └──────────┘               │
│                                                                 │
│  Final State:                                                   │
│  - ORDER #1: filled (entry)                                    │
│  - ORDER #2: cancelled (stop loss - OCO)                       │
│  - ORDER #3: filled (take profit)                              │
│  - POSITION: closed, realized_pnl calculated                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Step-by-Step Code Flow

```
Step 1: CANDIDATE IDENTIFIED
─────────────────────────────
Scanner finds AAPL with:
  - Gap up 5%
  - News catalyst: Earnings beat
  - Volume 3x average
  - Pattern: Bull flag

↓

Step 2: CREATE ORDER RECORD (Before Alpaca!)
────────────────────────────────────────────
INSERT INTO orders (
    security_id,           -- AAPL's security_id
    cycle_id,              -- Today's cycle
    side,                  -- 'buy'
    order_type,            -- 'market' or 'limit'
    quantity,              -- 100
    limit_price,           -- $150.00 (if limit)
    status,                -- 'created'
    created_at             -- NOW()
) RETURNING order_id;

Result: order_id = 'ord-001'
        position_id = NULL  ← No position yet!

↓

Step 3: SUBMIT TO ALPACA
────────────────────────
alpaca_order = client.submit_order(
    symbol='AAPL',
    qty=100,
    side='buy',
    type='market',
    time_in_force='day'
)

Response: alpaca_order.id = 'alp-xyz-123'
          alpaca_order.status = 'accepted'

↓

Step 4: UPDATE ORDER WITH ALPACA RESPONSE
─────────────────────────────────────────
UPDATE orders SET
    alpaca_order_id = 'alp-xyz-123',
    status = 'submitted',
    submitted_at = NOW()
WHERE order_id = 'ord-001';

↓

Step 5: WAIT FOR FILL (via webhook or polling)
──────────────────────────────────────────────
Alpaca sends fill notification:
  - alpaca_order_id: 'alp-xyz-123'
  - status: 'filled'
  - filled_qty: 100
  - filled_avg_price: $149.95

↓

Step 6: UPDATE ORDER AS FILLED
──────────────────────────────
UPDATE orders SET
    status = 'filled',
    filled_qty = 100,
    filled_avg_price = 149.95,
    filled_at = NOW()
WHERE alpaca_order_id = 'alp-xyz-123';

↓

Step 7: CREATE POSITION (Only now!)
───────────────────────────────────
INSERT INTO positions (
    cycle_id,
    security_id,
    side,                  -- 'long'
    quantity,              -- 100
    entry_price,           -- 149.95
    entry_time,            -- NOW()
    stop_loss,             -- 147.00
    take_profit,           -- 155.00
    status                 -- 'open'
) RETURNING position_id;

Result: position_id = 'pos-001'

↓

Step 8: LINK ORDER TO POSITION
──────────────────────────────
UPDATE orders SET
    position_id = 'pos-001'
WHERE order_id = 'ord-001';

↓

Step 9: CREATE PROTECTION ORDERS
────────────────────────────────
-- Stop Loss Order
INSERT INTO orders (
    position_id,           -- 'pos-001' ← Linked immediately
    security_id,
    cycle_id,
    side,                  -- 'sell' (exit for long)
    order_type,            -- 'stop'
    quantity,              -- 100
    stop_price,            -- 147.00
    status                 -- 'created'
) RETURNING order_id;

Result: order_id = 'ord-002'

-- Take Profit Order
INSERT INTO orders (
    position_id,           -- 'pos-001'
    security_id,
    cycle_id,
    side,                  -- 'sell'
    order_type,            -- 'limit'
    quantity,              -- 100
    limit_price,           -- 155.00
    status                 -- 'created'
) RETURNING order_id;

Result: order_id = 'ord-003'

↓

Step 10: SUBMIT PROTECTION ORDERS TO ALPACA
───────────────────────────────────────────
Submit as OCO (one-cancels-other) or individually.
Update orders with alpaca_order_id.

↓

Step 11: MONITOR AND WAIT
─────────────────────────
Doctor Claude checks every 5 minutes:
- All 3 orders synced with Alpaca
- Position P&L updated
- No stuck orders

↓

Step 12: EXIT FILL RECEIVED
───────────────────────────
Take profit hit at $155.00:
- ORDER #3 filled
- ORDER #2 cancelled (OCO)

UPDATE orders SET status = 'filled', filled_avg_price = 155.00
WHERE order_id = 'ord-003';

UPDATE orders SET status = 'cancelled', cancel_reason = 'OCO'
WHERE order_id = 'ord-002';

↓

Step 13: CLOSE POSITION
───────────────────────
realized_pnl = (155.00 - 149.95) * 100 = $505.00

UPDATE positions SET
    status = 'closed',
    exit_price = 155.00,
    exit_time = NOW(),
    realized_pnl = 505.00,
    quantity = 0
WHERE position_id = 'pos-001';

↓

COMPLETE
────────
Final database state:

orders:
  ord-001: AAPL BUY  100 @ 149.95  status=filled     (entry)
  ord-002: AAPL SELL 100 @ 147.00  status=cancelled  (stop loss)
  ord-003: AAPL SELL 100 @ 155.00  status=filled     (take profit)

positions:
  pos-001: AAPL LONG 0 shares, closed, realized_pnl=$505.00
```

---

## 2. Order State Machine

### 2.1 State Diagram

```
                         ┌─────────────────────────────────────┐
                         │                                     │
                         ▼                                     │
                    ┌─────────┐                                │
        ┌──────────│ created │──────────────┐                 │
        │          └────┬────┘              │                 │
        │               │                   │                 │
        │               │ submit()          │ cancel_before   │
        │               ▼                   │ _submit()       │
        │          ┌─────────┐              │                 │
        │          │submitted│──────────────┤                 │
        │          └────┬────┘              │                 │
        │               │                   │                 │
        │               │ alpaca accepts    │                 │
        │               ▼                   │                 │
        │          ┌─────────┐              │                 │
        │   ┌──────│ accepted│──────┐       │                 │
        │   │      └────┬────┘      │       │                 │
        │   │           │           │       │                 │
        │   │ partial   │ full      │ cancel│                 │
        │   │ fill      │ fill      │       │                 │
        │   │           │           │       │                 │
        │   ▼           ▼           ▼       ▼                 │
        │ ┌────────┐ ┌──────┐ ┌─────────┐ ┌─────────┐        │
        │ │partial │ │filled│ │cancelled│ │cancelled│        │
        │ │ _fill  │ └──────┘ └─────────┘ └─────────┘        │
        │ └───┬────┘     ▲                     ▲              │
        │     │          │                     │              │
        │     │ remaining│                     │              │
        │     │ fills    │                     │              │
        │     └──────────┘                     │              │
        │                                      │              │
        │          ┌─────────┐                 │              │
        └─────────▶│rejected │                 │              │
                   └─────────┘                 │              │
                                               │              │
                   ┌─────────┐                 │              │
                   │ expired │◀────────────────┘              │
                   └─────────┘  (time_in_force                │
                                 expired)                     │
                                                              │
                   ┌─────────────────────────────────────────┘
                   │
                   │ replace() creates new order
                   ▼
              ┌─────────┐
              │ replaced│ (points to new order_id)
              └─────────┘
```

### 2.2 State Definitions

| State | Description | Terminal? | Next Actions |
|-------|-------------|-----------|--------------|
| `created` | Order record exists, not yet sent to Alpaca | No | submit, cancel |
| `submitted` | Sent to Alpaca, awaiting acceptance | No | wait for Alpaca |
| `accepted` | Alpaca accepted, waiting in order book | No | wait for fill, cancel |
| `partial_fill` | Some quantity filled, more pending | No | wait for remaining |
| `filled` | Fully executed | **Yes** | None |
| `cancelled` | Cancelled before full execution | **Yes** | None |
| `rejected` | Alpaca rejected the order | **Yes** | Review and retry |
| `expired` | Time in force expired | **Yes** | None |
| `replaced` | Order was replaced by a new order | **Yes** | Track new order |

### 2.3 State Transitions

```python
# Valid state transitions
ORDER_TRANSITIONS = {
    'created': ['submitted', 'cancelled', 'rejected'],
    'submitted': ['accepted', 'rejected', 'cancelled'],
    'accepted': ['partial_fill', 'filled', 'cancelled', 'expired', 'replaced'],
    'partial_fill': ['partial_fill', 'filled', 'cancelled'],
    'filled': [],      # Terminal
    'cancelled': [],   # Terminal
    'rejected': [],    # Terminal
    'expired': [],     # Terminal
    'replaced': [],    # Terminal
}

def can_transition(current_state: str, new_state: str) -> bool:
    return new_state in ORDER_TRANSITIONS.get(current_state, [])
```

### 2.4 Alpaca Status Mapping

| Alpaca Status | Our Status | Notes |
|---------------|------------|-------|
| `new` | `submitted` | Just received by Alpaca |
| `pending_new` | `submitted` | Being processed |
| `accepted` | `accepted` | In order book |
| `pending_cancel` | `accepted` | Cancel requested |
| `partially_filled` | `partial_fill` | Partial execution |
| `filled` | `filled` | Complete |
| `cancelled` | `cancelled` | Cancelled |
| `expired` | `expired` | TIF expired |
| `rejected` | `rejected` | Validation failed |
| `replaced` | `replaced` | Replaced by new order |

---

## 3. Position State Machine

### 3.1 State Diagram

```
              ┌─────────┐
              │ pending │ ← Entry order created but not filled
              └────┬────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        │ entry    │ entry    │ entry order
        │ fills    │ rejected │ cancelled
        │          │          │
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌─────────┐
   │  open  │ │ failed │ │cancelled│
   └───┬────┘ └────────┘ └─────────┘
       │          ▲           ▲
       │          │           │
       │ exit     │           │
       │ fills    │           │
       │          │           │
       ▼          │           │
   ┌────────┐     │           │
   │ closed │─────┴───────────┘
   └────────┘     (if position never had fills)
```

### 3.2 State Definitions

| State | Description | Entry Orders | Exit Orders | Qty |
|-------|-------------|--------------|-------------|-----|
| `pending` | Waiting for entry order to fill | submitted/accepted | None | 0 |
| `open` | Entry filled, holding shares | filled | accepted/pending | >0 |
| `closed` | All shares exited | filled | filled | 0 |
| `cancelled` | Entry never filled | cancelled/expired | None | 0 |
| `failed` | Entry rejected | rejected | None | 0 |

### 3.3 Position Quantity Rules

```python
# Position quantity changes ONLY when orders fill

def update_position_quantity(position, filled_order):
    if filled_order.side == 'buy':
        if position.side == 'long':
            # Adding to long position
            position.quantity += filled_order.filled_qty
        else:
            # Covering short position
            position.quantity -= filled_order.filled_qty
    
    elif filled_order.side == 'sell':
        if position.side == 'long':
            # Reducing long position
            position.quantity -= filled_order.filled_qty
        else:
            # Adding to short position
            position.quantity += filled_order.filled_qty
    
    # Check if closed
    if position.quantity <= 0:
        position.status = 'closed'
        position.quantity = 0
```

---

## 4. Trading Cycle State Machine

### 4.1 State Diagram

```
                    ┌────────────┐
    ┌──────────────▶│   idle     │◀──────────────┐
    │               └─────┬──────┘               │
    │                     │                      │
    │                     │ start_cycle()        │
    │                     ▼                      │
    │               ┌────────────┐               │
    │               │  scanning  │               │
    │               └─────┬──────┘               │
    │                     │                      │
    │                     │ candidates found     │
    │                     ▼                      │
    │               ┌────────────┐               │
    │               │ evaluating │               │
    │               └─────┬──────┘               │
    │                     │                      │
    │                     │ entries approved     │
    │                     ▼                      │
    │               ┌────────────┐               │
    │               │  trading   │               │
    │               └─────┬──────┘               │
    │                     │                      │
    │                     │ positions open       │
    │                     ▼                      │
    │               ┌────────────┐               │
    │               │ monitoring │               │
    │               └─────┬──────┘               │
    │                     │                      │
    │   emergency_stop()  │ all positions closed │
    │                     ▼                      │
    │               ┌────────────┐               │
    └───────────────│   closed   │───────────────┘
                    └────────────┘
                          │
                          │ end of day
                          ▼
                    ┌────────────┐
                    │ completed  │
                    └────────────┘
```

### 4.2 Phase Definitions

| Phase | Activities | Duration |
|-------|------------|----------|
| `idle` | Waiting for market open | Pre-market |
| `scanning` | Running market scans | 9:15-9:35 AM |
| `evaluating` | Analyzing candidates, risk approval | 9:30-10:00 AM |
| `trading` | Submitting entry orders | Active trading |
| `monitoring` | Watching positions, managing exits | Until close |
| `closed` | All positions closed | 4:00 PM |
| `completed` | P&L finalized, reports generated | End of day |

---

## 5. Entity Relationships

### 5.1 Complete Data Model

```
┌─────────────────────────────────────────────────────────────────┐
│                         TRADING CYCLE                           │
│                         (One per day)                           │
├─────────────────────────────────────────────────────────────────┤
│ cycle_id (PK)                                                   │
│ date                                                            │
│ cycle_state                                                     │
│ phase                                                           │
│ daily_pnl                                                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ 1:N
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  SCAN_RESULTS │      │   POSITIONS   │      │    ORDERS     │
│  (Candidates) │      │  (Holdings)   │      │ (Instructions)│
├───────────────┤      ├───────────────┤      ├───────────────┤
│ scan_id (PK)  │      │ position_id   │◀─────│ position_id   │
│ cycle_id (FK) │      │ (PK)          │  N:1 │ (FK, nullable)│
│ security_id   │      │ cycle_id (FK) │      │               │
│ rank_in_scan  │      │ security_id   │      │ order_id (PK) │
│ composite_    │      │ side          │      │ cycle_id (FK) │
│   score       │      │ quantity      │      │ security_id   │
│ status        │      │ entry_price   │      │ parent_order  │
│               │      │ exit_price    │      │   _id (FK)    │
│               │      │ status        │      │ side          │
│               │      │ realized_pnl  │      │ order_type    │
│               │      │               │      │ quantity      │
│               │      │               │      │ limit_price   │
│               │      │               │      │ stop_price    │
│               │      │               │      │ alpaca_order  │
│               │      │               │      │   _id         │
│               │      │               │      │ status        │
│               │      │               │      │ filled_qty    │
│               │      │               │      │ filled_avg    │
│               │      │               │      │   _price      │
└───────────────┘      └───────────────┘      └───────────────┘
        │                       │                       │
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                │ N:1
                                ▼
                       ┌───────────────┐
                       │  SECURITIES   │
                       │   (Stocks)    │
                       ├───────────────┤
                       │ security_id   │
                       │ (PK)          │
                       │ symbol        │
                       │ name          │
                       │ sector_id     │
                       └───────────────┘
```

### 5.2 Key Relationships

| Relationship | Cardinality | Description |
|--------------|-------------|-------------|
| Cycle → Positions | 1:N | One cycle has many positions |
| Cycle → Orders | 1:N | One cycle has many orders |
| Cycle → Scan Results | 1:N | One cycle has many candidates |
| Position → Orders | 1:N | One position has many orders |
| Order → Order (parent) | 1:N | Bracket legs link to parent |
| Security → All | 1:N | One security in many records |

### 5.3 Order-Position Linking Rules

```python
# Entry orders: position_id is NULL initially
entry_order = {
    'order_id': 'ord-001',
    'position_id': None,      # ← NULL until fill
    'side': 'buy',
    'status': 'submitted'
}

# When entry fills, create position and link
position = create_position(...)  # position_id = 'pos-001'
update_order(order_id='ord-001', position_id='pos-001')

# Protection orders: position_id set immediately
stop_loss_order = {
    'order_id': 'ord-002',
    'position_id': 'pos-001',  # ← Linked at creation
    'parent_order_id': 'ord-001',
    'side': 'sell',
    'order_type': 'stop'
}
```

---

## 6. Data Flow Patterns

### 6.1 Entry Order Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENTRY ORDER FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Trading      Orders         Alpaca         Orders     Positions│
│  Service      Table          API            Table      Table    │
│     │           │              │              │           │     │
│     │ INSERT    │              │              │           │     │
│     │ (created) │              │              │           │     │
│     │──────────▶│              │              │           │     │
│     │           │              │              │           │     │
│     │ submit_order()           │              │           │     │
│     │─────────────────────────▶│              │           │     │
│     │           │              │              │           │     │
│     │◀─────────────────────────│              │           │     │
│     │    alpaca_order_id       │              │           │     │
│     │           │              │              │           │     │
│     │ UPDATE    │              │              │           │     │
│     │ (submitted)              │              │           │     │
│     │──────────▶│              │              │           │     │
│     │           │              │              │           │     │
│     │           │   [fill event]              │           │     │
│     │           │◀─────────────│              │           │     │
│     │           │              │              │           │     │
│     │           │ UPDATE       │              │           │     │
│     │           │ (filled)     │              │           │     │
│     │           │──────────────────────────▶ │           │     │
│     │           │              │              │           │     │
│     │           │              │              │ INSERT    │     │
│     │           │              │              │ (open)    │     │
│     │           │              │              │──────────▶│     │
│     │           │              │              │           │     │
│     │           │ UPDATE       │              │           │     │
│     │           │ position_id  │              │           │     │
│     │           │◀─────────────────────────── │           │     │
│     │           │              │              │           │     │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Exit Order Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXIT ORDER FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Alpaca        Orders         Positions     Trading    Alpaca   │
│  (fill)        Table          Table         Service    (cancel) │
│     │            │               │             │          │     │
│     │ TP fills   │               │             │          │     │
│     │───────────▶│               │             │          │     │
│     │            │               │             │          │     │
│     │            │ UPDATE        │             │          │     │
│     │            │ (filled)      │             │          │     │
│     │            │──────────────▶│             │          │     │
│     │            │               │             │          │     │
│     │            │               │ UPDATE      │          │     │
│     │            │               │ (closed)    │          │     │
│     │            │               │────────────▶│          │     │
│     │            │               │             │          │     │
│     │            │               │             │ cancel SL│     │
│     │            │               │             │─────────▶│     │
│     │            │               │             │          │     │
│     │            │ UPDATE        │             │          │     │
│     │            │ (cancelled)   │             │          │     │
│     │            │◀─────────────────────────────────────── │     │
│     │            │               │             │          │     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Reconciliation Patterns

### 7.1 Order Reconciliation

```sql
-- Find orders needing reconciliation
SELECT 
    o.order_id,
    o.alpaca_order_id,
    o.status as db_status,
    o.filled_qty as db_filled,
    o.updated_at,
    s.symbol
FROM orders o
JOIN securities s ON o.security_id = s.security_id
WHERE o.alpaca_order_id IS NOT NULL
  AND o.status NOT IN ('filled', 'cancelled', 'rejected', 'expired')
  AND o.updated_at < NOW() - INTERVAL '1 minute'
ORDER BY o.submitted_at;
```

### 7.2 Position Reconciliation

```sql
-- Compare open positions to Alpaca
SELECT 
    p.position_id,
    s.symbol,
    p.quantity as db_qty,
    p.side,
    p.status
FROM positions p
JOIN securities s ON p.security_id = s.security_id
WHERE p.status = 'open'
  AND p.quantity > 0;

-- Then compare to Alpaca get_all_positions()
```

### 7.3 Doctor Claude Reconciliation Loop

```python
async def reconcile_with_alpaca():
    """
    Complete reconciliation flow:
    1. Sync order statuses
    2. Verify position quantities
    3. Identify orphans (Alpaca but not DB)
    4. Identify phantoms (DB but not Alpaca)
    """
    
    issues = []
    
    # Step 1: Order status sync
    pending_orders = await get_pending_orders()
    for order in pending_orders:
        try:
            alpaca_order = client.get_order_by_id(order.alpaca_order_id)
            if alpaca_order.status != order.status:
                issues.append({
                    'type': 'ORDER_STATUS_MISMATCH',
                    'order_id': order.order_id,
                    'db_status': order.status,
                    'alpaca_status': alpaca_order.status
                })
        except NotFoundError:
            issues.append({
                'type': 'ORDER_NOT_IN_ALPACA',
                'order_id': order.order_id
            })
    
    # Step 2: Position reconciliation
    db_positions = await get_open_positions()
    alpaca_positions = client.get_all_positions()
    
    db_symbols = {p.symbol for p in db_positions}
    alpaca_symbols = {p.symbol for p in alpaca_positions}
    
    # Orphans: In Alpaca but not in DB
    for symbol in alpaca_symbols - db_symbols:
        issues.append({
            'type': 'ORPHAN_POSITION',
            'symbol': symbol,
            'severity': 'CRITICAL'
        })
    
    # Phantoms: In DB but not in Alpaca
    for symbol in db_symbols - alpaca_symbols:
        issues.append({
            'type': 'PHANTOM_POSITION',
            'symbol': symbol,
            'severity': 'CRITICAL'
        })
    
    return issues
```

---

## 8. Error Handling Patterns

### 8.1 Order Submission Failures

```python
async def submit_order_with_retry(order_params, max_retries=3):
    """
    Submit order with proper error handling and DB tracking.
    """
    
    # Create order record first
    order_id = await create_order_record(order_params)
    
    for attempt in range(max_retries):
        try:
            alpaca_order = client.submit_order(**order_params)
            
            # Success - update order
            await update_order(
                order_id=order_id,
                alpaca_order_id=alpaca_order.id,
                status='submitted'
            )
            return order_id
            
        except APIError as e:
            if 'insufficient buying power' in str(e):
                # Permanent failure - mark rejected
                await update_order(
                    order_id=order_id,
                    status='rejected',
                    rejection_reason=str(e)
                )
                raise
                
            elif 'market is closed' in str(e):
                # Permanent failure
                await update_order(
                    order_id=order_id,
                    status='rejected',
                    rejection_reason='Market closed'
                )
                raise
                
            else:
                # Transient error - retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                else:
                    await update_order(
                        order_id=order_id,
                        status='rejected',
                        rejection_reason=f'Failed after {max_retries} attempts: {e}'
                    )
                    raise
```

### 8.2 Fill Processing Failures

```python
async def process_fill_safely(alpaca_order_id, fill_data):
    """
    Process fill with transaction safety.
    """
    
    async with db.transaction():
        # Find order
        order = await get_order_by_alpaca_id(alpaca_order_id)
        if not order:
            log.error(f"Fill for unknown order: {alpaca_order_id}")
            return
        
        # Update order
        await update_order(
            order_id=order.order_id,
            status='filled' if fill_data.filled_qty == order.quantity else 'partial_fill',
            filled_qty=fill_data.filled_qty,
            filled_avg_price=fill_data.filled_avg_price,
            filled_at=fill_data.filled_at
        )
        
        # Handle position changes
        if order.position_id is None:
            # Entry order - create position
            position_id = await create_position(
                cycle_id=order.cycle_id,
                security_id=order.security_id,
                side='long' if order.side == 'buy' else 'short',
                quantity=fill_data.filled_qty,
                entry_price=fill_data.filled_avg_price
            )
            await update_order(order_id=order.order_id, position_id=position_id)
        else:
            # Exit order - update position
            await update_position_from_exit(order.position_id, fill_data)
```

---

## Related Documents

- **architecture.md** - System architecture
- **database-schema.md** - Full schema including orders table
- **functional-specification.md** - Service specifications
- **ORDERS-POSITIONS-IMPLEMENTATION.md** - Detailed implementation guide
- **ARCHITECTURE-RULES.md** - Mandatory rules for Claude Code

---

**END OF OPERATIONS GUIDE v1.0.0**
