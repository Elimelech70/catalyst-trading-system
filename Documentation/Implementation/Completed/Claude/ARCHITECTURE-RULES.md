# CRITICAL ARCHITECTURE RULES

**Name of Application**: Catalyst Trading System  
**Name of file**: ARCHITECTURE-RULES.md  
**Version**: 1.0.0  
**Last Updated**: 2025-12-27  
**Purpose**: Mandatory architecture rules Claude Code MUST follow  
**Authority**: AUTHORITATIVE - Violations require human approval

---

## ⛔ READ THIS BEFORE ANY CODE CHANGES

This document contains **mandatory architectural rules**. Claude Code:

1. **MUST** read this document before modifying trading-related code
2. **MUST NOT** deviate from these rules without explicit human approval
3. **MUST** flag any existing code that violates these rules
4. **MUST** ask for clarification if design docs conflict with these rules

---

## Rule 1: Orders and Positions Are Separate Entities

### The Rule

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ORDERS ≠ POSITIONS                                            │
│                                                                 │
│   Order = Instruction to broker ("Buy 100 AAPL at $150")       │
│   Position = Actual holding ("I own 100 AAPL")                 │
│                                                                 │
│   One position can have MANY orders:                           │
│   - Entry order                                                 │
│   - Stop loss order                                             │
│   - Take profit order                                           │
│   - Scale-in orders                                             │
│   - Scale-out orders                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Required Implementation

| Requirement | Description |
|-------------|-------------|
| `orders` table MUST exist | Stores all orders sent to Alpaca |
| `positions` table for holdings only | NO order columns (`alpaca_order_id`, `alpaca_status`) |
| Create order record FIRST | Before sending to Alpaca |
| Link order to position AFTER fill | Entry orders have NULL position_id initially |

### Forbidden Patterns

```python
# ⛔ FORBIDDEN: Order data in positions table
UPDATE positions SET alpaca_order_id = $1, alpaca_status = $2 ...

# ⛔ FORBIDDEN: Skip order record
alpaca.submit_order(...)  # No order record created!
INSERT INTO positions ...

# ⛔ FORBIDDEN: Query positions for order status
SELECT * FROM positions WHERE alpaca_status = 'submitted'
```

### Required Patterns

```python
# ✅ REQUIRED: Create order record first
INSERT INTO orders (...) VALUES (...)
alpaca.submit_order(...)
UPDATE orders SET alpaca_order_id = $1 ...

# ✅ REQUIRED: Query orders table for order status
SELECT * FROM orders WHERE status = 'submitted'
```

### Reference Document

**Full specification**: `Documentation/Implementation/ORDERS-POSITIONS-IMPLEMENTATION.md`

---

## Rule 2: Design Doc Discrepancies Must Be Flagged

### The Rule

When Claude Code encounters a difference between:
- What design documents specify
- What code actually does
- What the database actually contains

Claude Code **MUST**:

1. **STOP** before implementing
2. **REPORT** the discrepancy to the human
3. **ASK** which is correct: design or reality
4. **WAIT** for explicit direction

### Example

```
Claude Code finds:
- Design doc says: "orders table tracks all orders"
- Database shows: positions.alpaca_order_id column exists
- No orders table exists

REQUIRED ACTION:
"I found a discrepancy:
- Design specifies an 'orders' table
- Database has order columns in 'positions' table instead
- No 'orders' table exists

Which should I follow? Should I:
A) Implement using existing positions.alpaca_* columns
B) Create the orders table as designed
C) Something else?"
```

### Forbidden Pattern

```
# ⛔ FORBIDDEN: Silently adapt to different reality
"Design says X but database has Y. I'll just use Y and document it later."
```

---

## Rule 3: Database Schema Changes Require Migration Scripts

### The Rule

All database schema changes MUST:

1. Have a migration script in `/sql/` directory
2. Include rollback instructions
3. Be reviewed before execution
4. Be versioned and dated

### Required Format

```sql
-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: {description}-migration.sql
-- Version: 1.0.0
-- Last Updated: YYYY-MM-DD
-- Purpose: {what this migration does}
-- ============================================================================

BEGIN;
-- Changes here
COMMIT;

-- ROLLBACK SCRIPT
-- (how to undo if needed)

-- VERIFICATION QUERIES
-- (how to verify it worked)
```

---

## Rule 4: Trading Code Must Use Alpaca SDK Correctly

### Order Side Mapping

```python
# Position side → Order side mapping
# LONG position = BUY to enter, SELL to exit
# SHORT position = SELL to enter, BUY to exit

def get_entry_side(position_side: str) -> str:
    return 'buy' if position_side == 'long' else 'sell'

def get_exit_side(position_side: str) -> str:
    return 'sell' if position_side == 'long' else 'buy'
```

### Price Rounding

```python
# All prices sent to Alpaca MUST be rounded to 2 decimal places
def round_price(price: float) -> float:
    return round(price, 2)

# ⛔ FORBIDDEN: Sub-penny prices
alpaca.submit_order(limit_price=9.050000190734863)  # Will be rejected!

# ✅ REQUIRED: Rounded prices
alpaca.submit_order(limit_price=round_price(9.05))  # Correct
```

### Bracket Orders

```python
# Bracket orders MUST specify OrderClass.BRACKET
from alpaca.trading.enums import OrderClass

# ⛔ FORBIDDEN: Bracket without order_class
alpaca.submit_order(
    ...,
    take_profit=TakeProfitRequest(...),
    stop_loss=StopLossRequest(...)
)

# ✅ REQUIRED: Explicit order_class
alpaca.submit_order(
    ...,
    order_class=OrderClass.BRACKET,
    take_profit=TakeProfitRequest(...),
    stop_loss=StopLossRequest(...)
)
```

---

## Rule 5: Doctor Claude Monitors Orders, Not Positions

### The Rule

Doctor Claude reconciliation MUST:

1. Compare `orders` table to Alpaca orders
2. Track all order state transitions
3. Handle bracket order legs separately
4. NOT query `positions.alpaca_*` columns (they should not exist)

### Required Queries

```sql
-- Stuck orders query (CORRECT)
SELECT * FROM orders 
WHERE status IN ('submitted', 'accepted') 
  AND submitted_at < NOW() - INTERVAL '5 minutes';

-- Order reconciliation (CORRECT)
SELECT o.*, s.symbol 
FROM orders o
JOIN securities s ON o.security_id = s.security_id
WHERE o.alpaca_order_id IS NOT NULL
  AND o.status NOT IN ('filled', 'cancelled', 'rejected', 'expired');
```

---

## Summary: The Mandatory Checklist

Before modifying any trading code, Claude Code MUST verify:

- [ ] Changes use `orders` table for order data (not positions)
- [ ] Order records are created BEFORE submitting to Alpaca
- [ ] Position records are created ONLY when entry order fills
- [ ] Prices are rounded to 2 decimal places
- [ ] Order side is correctly mapped (long→buy, short→sell)
- [ ] Bracket orders specify `OrderClass.BRACKET`
- [ ] Database changes have migration scripts
- [ ] Any design discrepancies are flagged and resolved

---

## Violation Reporting

If Claude Code finds existing code that violates these rules:

1. **Document** the violation
2. **Report** to human immediately
3. **Propose** a fix
4. **Wait** for approval before changing

Example:
```
ARCHITECTURE VIOLATION FOUND:
- File: trading-service.py
- Line: 234
- Violation: Stores alpaca_order_id in positions table
- Rule: Rule 1 - Orders and Positions Are Separate
- Proposed Fix: Modify to use orders table instead
- Impact: Medium - requires migration

Awaiting approval to proceed with fix.
```

---

**This document is AUTHORITATIVE. Claude Code MUST follow these rules.**
