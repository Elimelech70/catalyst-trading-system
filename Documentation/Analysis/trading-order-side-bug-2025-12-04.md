# Implementation Analysis: Trading Order Side Bug

**Name of Application**: Catalyst Trading System
**Name of file**: trading-order-side-bug-2025-12-04.md
**Version**: 1.0.0
**Last Updated**: 2025-12-04
**Purpose**: Root cause analysis and fix implementation for order side mismatch bug

---

## Executive Summary

**Critical Bug Found**: The trading system is placing SELL (short) orders instead of BUY (long) orders.

- **Database**: Shows 68 "long" positions
- **Alpaca Reality**: Orders submitted as "sell" (short positions)
- **Financial Impact**: Positions are losing money due to wrong direction

---

## Bug Analysis

### Root Cause

The `alpaca_trader.py` module has a logic error in the side conversion:

**Location**: `services/trading/common/alpaca_trader.py:273`

```python
# CURRENT CODE (BUGGY)
order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
```

**The Problem**:
- Workflow sends `side="long"`
- `"long".lower() == "buy"` evaluates to `False`
- Falls through to `OrderSide.SELL`
- Result: Every "long" position becomes a short sell!

### Data Flow

```
Workflow Coordinator          Trading Service           Alpaca Trader              Alpaca API
      |                            |                         |                         |
      |-- POST /positions -------->|                         |                         |
      |   side: "long"             |                         |                         |
      |                            |-- submit_bracket_order->|                         |
      |                            |   side: "long"          |                         |
      |                            |                         |-- side == "buy"? NO --->|
      |                            |                         |   Use OrderSide.SELL    |
      |                            |                         |                         |
      |                            |                         |<-- Order accepted ------|
      |                            |                         |   (as SHORT position)   |
```

### Evidence from Alpaca API

Recent orders all show:
```json
{
  "side": "sell",
  "position_intent": "sell_to_open"
}
```

This confirms Alpaca received SELL orders when BUY was intended.

---

## Affected Code Locations

### 1. Primary Bug Location
**File**: `services/trading/common/alpaca_trader.py`
**Line**: 273
**Function**: `submit_bracket_order()`

```python
# Line 273 - BUGGY
order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
```

### 2. Same Bug in Other Functions
**File**: `services/trading/common/alpaca_trader.py`
**Lines**: 160, 212
**Functions**: `submit_market_order()`, `submit_limit_order()`

All three order functions have the same logic error.

### 3. Workflow Sends "long"
**File**: `services/workflow/workflow-coordinator.py`
**Lines**: 461, 512

```python
"side": "long",  # Trading service expects "long"/"short"
```

---

## Fix Implementation

### Option A: Fix alpaca_trader.py (Recommended)

Change the side conversion to handle both "buy"/"sell" AND "long"/"short":

```python
# FIXED CODE
def _normalize_side(side: str) -> OrderSide:
    """Convert side string to Alpaca OrderSide enum."""
    side_lower = side.lower()
    if side_lower in ("buy", "long"):
        return OrderSide.BUY
    elif side_lower in ("sell", "short"):
        return OrderSide.SELL
    else:
        raise ValueError(f"Invalid order side: {side}")
```

Then update all three functions:
```python
# Line 160 (submit_market_order)
order_side = _normalize_side(side)

# Line 212 (submit_limit_order)
order_side = _normalize_side(side)

# Line 273 (submit_bracket_order)
order_side = _normalize_side(side)
```

### Option B: Fix workflow-coordinator.py (Alternative)

Change workflow to send "buy" instead of "long":

```python
# Line 461, 512
"side": "buy",  # Changed from "long"
```

**Note**: Option A is preferred because it makes the alpaca_trader more robust and handles both conventions.

---

## Immediate Actions Required

### 1. Cancel Pending Orders
```bash
# Cancel all open orders that haven't filled
curl -X DELETE -H "APCA-API-KEY-ID: $KEY" -H "APCA-API-SECRET-KEY: $SECRET" \
  "https://paper-api.alpaca.markets/v2/orders"
```

### 2. Close Unwanted Short Positions
```bash
# Close AEO short position
curl -X DELETE -H "APCA-API-KEY-ID: $KEY" -H "APCA-API-SECRET-KEY: $SECRET" \
  "https://paper-api.alpaca.markets/v2/positions/AEO"

# Close QUBT short position
curl -X DELETE -H "APCA-API-KEY-ID: $KEY" -H "APCA-API-SECRET-KEY: $SECRET" \
  "https://paper-api.alpaca.markets/v2/positions/QUBT"
```

### 3. Apply Code Fix
Apply Option A fix to `services/trading/common/alpaca_trader.py`

### 4. Rebuild and Restart Trading Service
```bash
docker-compose build trading
docker-compose up -d --force-recreate trading
```

### 5. Clean Up Database
Mark all 68 "phantom" positions as cancelled/error since they never actually executed as intended.

---

## Database vs Reality Reconciliation

### Current State

| Source | Positions | Actual Effect |
|--------|-----------|---------------|
| Database | 68 "long" positions | Never executed correctly |
| Alpaca | 4 real positions | 2 longs (old), 2 shorts (bug) |

### Positions Needing Cleanup

**Alpaca Positions to Close**:
- AEO: -155 shares (short) - CLOSE
- QUBT: -200 shares (short) - CLOSE

**Database Positions to Mark as Error**:
- All 68 positions from Nov 29 - Dec 4 should be marked with status='error' or 'cancelled'

---

## Prevention Measures

### 1. Add Unit Tests
```python
def test_normalize_side():
    assert _normalize_side("buy") == OrderSide.BUY
    assert _normalize_side("BUY") == OrderSide.BUY
    assert _normalize_side("long") == OrderSide.BUY
    assert _normalize_side("LONG") == OrderSide.BUY
    assert _normalize_side("sell") == OrderSide.SELL
    assert _normalize_side("short") == OrderSide.SELL
```

### 2. Add Validation Logging
```python
logger.info(f"Order side conversion: input='{side}' -> output={order_side}")
```

### 3. Add Pre-Trade Verification
Before submitting to Alpaca, verify the order makes sense:
```python
if side.lower() in ("long", "buy") and order_side != OrderSide.BUY:
    raise RuntimeError("Order side mismatch detected!")
```

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 2025-11-29 07:20 | First buggy orders placed (positions 3-7) |
| 2025-12-01 01:30 | Bug continues, more positions "opened" |
| 2025-12-02 01:30 | Bug continues |
| 2025-12-02 14:31 | AEO short partially fills (155 shares) |
| 2025-12-03 14:41 | QUBT short fills (200 shares) |
| 2025-12-04 04:35 | Bug discovered during trading review |

---

## Files to Modify

1. `services/trading/common/alpaca_trader.py` - Fix side conversion
2. `services/workflow/common/alpaca_trader.py` - Same fix if separate copy
3. Database cleanup script - Mark phantom positions

---

## Approval Required

- [ ] Cancel pending Alpaca orders
- [ ] Close unwanted short positions (AEO, QUBT)
- [ ] Apply code fix
- [ ] Rebuild trading service
- [ ] Clean up database records

---

**Priority**: CRITICAL
**Estimated Fix Time**: 30 minutes
**Risk if Not Fixed**: Continued financial losses from inverted positions

---

## Implementation Plan

### Phase 1: Stop the Bleeding (Immediate - 5 mins)

| Step | Action | Command/Details |
|------|--------|-----------------|
| 1.1 | Cancel all pending orders | `DELETE /v2/orders` |
| 1.2 | Close AEO short position | `DELETE /v2/positions/AEO` |
| 1.3 | Close QUBT short position | `DELETE /v2/positions/QUBT` |
| 1.4 | Disable trading cron | `crontab -e` - comment out trading jobs |

### Phase 2: Fix the Code (15 mins)

| Step | Action | File |
|------|--------|------|
| 2.1 | Add `_normalize_side()` helper function | `services/trading/common/alpaca_trader.py` |
| 2.2 | Update `submit_market_order()` line 160 | `services/trading/common/alpaca_trader.py` |
| 2.3 | Update `submit_limit_order()` line 212 | `services/trading/common/alpaca_trader.py` |
| 2.4 | Update `submit_bracket_order()` line 273 | `services/trading/common/alpaca_trader.py` |
| 2.5 | Copy fix to workflow service | `services/workflow/common/alpaca_trader.py` |
| 2.6 | Update version header to v1.2.0 | Both alpaca_trader.py files |

**Code Change**:
```python
def _normalize_side(side: str) -> OrderSide:
    """
    Convert side string to Alpaca OrderSide enum.

    Accepts: "buy", "long", "sell", "short" (case-insensitive)
    """
    side_lower = side.lower()
    if side_lower in ("buy", "long"):
        return OrderSide.BUY
    elif side_lower in ("sell", "short"):
        return OrderSide.SELL
    else:
        raise ValueError(f"Invalid order side: {side}. Must be buy/long or sell/short")
```

### Phase 3: Rebuild and Deploy (5 mins)

| Step | Action | Command |
|------|--------|---------|
| 3.1 | Rebuild trading service | `docker-compose build trading` |
| 3.2 | Rebuild workflow service | `docker-compose build workflow` |
| 3.3 | Restart services | `docker-compose up -d --force-recreate trading workflow` |
| 3.4 | Verify health | `curl localhost:5005/health` |

### Phase 4: Database Cleanup (10 mins)

| Step | Action | SQL |
|------|--------|-----|
| 4.1 | Mark phantom positions as error | `UPDATE positions SET status='error', close_reason='order_side_bug' WHERE position_id >= 3 AND position_id <= 69 AND alpaca_status != 'filled';` |
| 4.2 | Update cycle metrics | `UPDATE trading_cycles SET current_positions = 0, used_risk_budget = 0 WHERE cycle_id LIKE '202512%';` |
| 4.3 | Add audit note | Insert record in system_events table documenting the bug |

### Phase 5: Verification (5 mins)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 5.1 | Check Alpaca positions | Only AAPL and MSFT remain |
| 5.2 | Check pending orders | 0 pending orders |
| 5.3 | Test order submission | Submit test order with side="long", verify BUY |
| 5.4 | Re-enable trading cron | Uncomment trading jobs |

### Phase 6: Post-Incident (After market hours)

| Step | Action |
|------|--------|
| 6.1 | Add unit tests for `_normalize_side()` |
| 6.2 | Add integration test for order flow |
| 6.3 | Update CLAUDE.md with lesson learned |
| 6.4 | Document in incident log |

---

## Rollback Plan

If the fix causes issues:

1. Stop trading services: `docker-compose stop trading workflow`
2. Disable cron jobs: `crontab -r`
3. Cancel all orders: `DELETE /v2/orders`
4. Revert code: `git checkout HEAD~1 -- services/trading/common/alpaca_trader.py`
5. Rebuild and restart

---

## Success Criteria

- [ ] No pending short orders in Alpaca
- [ ] No unintended short positions in Alpaca
- [ ] New test order with `side="long"` creates BUY order
- [ ] Trading service health check passes
- [ ] Database positions reconciled with Alpaca

---

## Lessons Learned

1. **Always test order side conversion** with all expected inputs
2. **Add validation logging** for critical order parameters before API submission
3. **String equality is brittle** - use explicit mapping or enums
4. **Database records don't equal reality** - always verify against broker
