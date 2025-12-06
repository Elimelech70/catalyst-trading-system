# Implementation Plan: Order Side Bug Improvements

**Name of Application**: Catalyst Trading System
**Name of file**: order-side-bug-improvements-plan.md
**Version**: 1.0.0
**Last Updated**: 2025-12-06
**Purpose**: Implementation plan for hardening the order side fix and preventing future occurrences

---

## Executive Summary

The v1.2.0 fix for the order side bug is deployed and working. This plan outlines additional improvements to:
1. Add comprehensive unit tests
2. Add pre-submission validation
3. Standardize side conventions
4. Clean up affected database records
5. Add integration testing

---

## Current State

| Item | Status |
|------|--------|
| Bug Fix (v1.2.0) | ✅ Deployed |
| Unit Tests | ❌ Not implemented |
| Pre-submission Validation | ❌ Not implemented |
| Side Convention Standardized | ❌ Mixed ("long"/"short" and "buy"/"sell") |
| Database Cleanup | ⚠️ Partial (positions marked but not reconciled) |
| Integration Tests | ❌ Not implemented |

---

## Implementation Tasks

### Task 1: Add Unit Tests for `_normalize_side()`

**Priority**: HIGH
**Risk**: LOW
**Files**: `services/trading/tests/test_alpaca_trader.py` (new)

#### 1.1 Create Test File Structure

```
services/trading/
├── common/
│   └── alpaca_trader.py
├── tests/
│   ├── __init__.py
│   ├── test_alpaca_trader.py
│   └── conftest.py
└── trading-service.py
```

#### 1.2 Test Cases for `_normalize_side()`

| Test Case | Input | Expected Output | Description |
|-----------|-------|-----------------|-------------|
| test_normalize_buy_lowercase | "buy" | OrderSide.BUY | Standard buy |
| test_normalize_buy_uppercase | "BUY" | OrderSide.BUY | Case insensitive |
| test_normalize_buy_mixed | "Buy" | OrderSide.BUY | Mixed case |
| test_normalize_long_lowercase | "long" | OrderSide.BUY | Long maps to buy |
| test_normalize_long_uppercase | "LONG" | OrderSide.BUY | Case insensitive |
| test_normalize_sell_lowercase | "sell" | OrderSide.SELL | Standard sell |
| test_normalize_sell_uppercase | "SELL" | OrderSide.SELL | Case insensitive |
| test_normalize_short_lowercase | "short" | OrderSide.SELL | Short maps to sell |
| test_normalize_short_uppercase | "SHORT" | OrderSide.SELL | Case insensitive |
| test_normalize_invalid | "invalid" | ValueError | Invalid input rejected |
| test_normalize_empty | "" | ValueError | Empty string rejected |
| test_normalize_whitespace | " buy " | ValueError | Whitespace not trimmed |

#### 1.3 Test Cases for `_round_price()`

| Test Case | Input | Expected Output | Description |
|-----------|-------|-----------------|-------------|
| test_round_price_none | None | None | None passthrough |
| test_round_price_integer | 10 | 10.0 | Integer handling |
| test_round_price_two_decimals | 10.55 | 10.55 | Already rounded |
| test_round_price_many_decimals | 9.050000190734863 | 9.05 | Float precision fix |
| test_round_price_rounds_down | 10.554 | 10.55 | Round down |
| test_round_price_rounds_up | 10.555 | 10.56 | Round up (banker's) |

---

### Task 2: Add Pre-Submission Validation

**Priority**: HIGH
**Risk**: LOW
**Files**: `services/trading/common/alpaca_trader.py`, `services/workflow/common/alpaca_trader.py`

#### 2.1 Add Validation Function

```python
def _validate_order_side_mapping(input_side: str, output_side: OrderSide) -> None:
    """
    Validate that order side mapping is correct before API submission.

    Raises RuntimeError if mapping appears incorrect (defense in depth).
    """
    input_lower = input_side.lower()

    if input_lower in ("long", "buy") and output_side != OrderSide.BUY:
        raise RuntimeError(
            f"CRITICAL: Order side mismatch! Input '{input_side}' should map to BUY, "
            f"but got {output_side.value}. Aborting order."
        )

    if input_lower in ("short", "sell") and output_side != OrderSide.SELL:
        raise RuntimeError(
            f"CRITICAL: Order side mismatch! Input '{input_side}' should map to SELL, "
            f"but got {output_side.value}. Aborting order."
        )
```

#### 2.2 Integration Points

Add validation call after `_normalize_side()` in:
- `submit_market_order()` - Line ~190
- `submit_limit_order()` - Line ~242
- `submit_bracket_order()` - Line ~303

```python
order_side = _normalize_side(side)
_validate_order_side_mapping(side, order_side)  # Defense in depth
```

---

### Task 3: Add Enhanced Logging

**Priority**: MEDIUM
**Risk**: LOW
**Files**: `services/trading/common/alpaca_trader.py`, `services/workflow/common/alpaca_trader.py`

#### 3.1 Pre-Order Logging

Add detailed logging before each order submission:

```python
logger.info(
    f"ORDER SUBMISSION: symbol={symbol}, input_side='{side}', "
    f"mapped_side={order_side.value}, qty={quantity}, "
    f"entry=${entry_price}, stop=${stop_loss}, target=${take_profit}"
)
```

#### 3.2 Post-Order Logging

Enhance existing logging to confirm Alpaca response:

```python
logger.info(
    f"ORDER CONFIRMED: order_id={order.id}, alpaca_side={order.side}, "
    f"status={order.status.value}, symbol={order.symbol}"
)
```

---

### Task 4: Standardize Side Convention

**Priority**: LOW
**Risk**: MEDIUM (requires coordination across services)
**Files**: Multiple workflow and trading files

#### 4.1 Decision Required

| Option | Convention | Pros | Cons |
|--------|------------|------|------|
| A | Use "buy"/"sell" everywhere | Matches Alpaca API | Less intuitive for trading logic |
| B | Use "long"/"short" everywhere | Trading-native terminology | Requires translation layer |
| C | Keep both with `_normalize_side()` | No changes needed | Inconsistent, relies on translation |

**Recommendation**: Option C (current state) - The `_normalize_side()` function handles translation robustly. Changing convention system-wide introduces risk for minimal benefit.

---

### Task 5: Database Cleanup

**Priority**: MEDIUM
**Risk**: LOW
**Files**: SQL scripts only

#### 5.1 Reconciliation Query

First, identify what actually happened in Alpaca for affected positions:

```sql
-- Find positions affected by the bug
SELECT
    p.position_id,
    s.symbol,
    p.side,
    p.quantity,
    p.entry_price,
    p.alpaca_order_id,
    p.alpaca_status,
    p.status,
    p.close_reason,
    p.opened_at
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.close_reason = 'order_side_bug_v1.2.0_fix'
ORDER BY p.opened_at;
```

#### 5.2 Cleanup Options

| Option | Action | When to Use |
|--------|--------|-------------|
| Mark as cancelled | `status='cancelled'` | Order never filled in Alpaca |
| Mark as error | `status='error'` | Order rejected by Alpaca |
| Reconcile with fills | Update exit_price, realized_pnl | Order filled (need Alpaca data) |

#### 5.3 Cleanup SQL

```sql
-- Option 1: Mark unfilled orders as cancelled
UPDATE positions
SET
    status = 'cancelled',
    close_reason = 'order_side_bug_v1.2.0_cancelled',
    updated_at = NOW()
WHERE close_reason = 'order_side_bug_v1.2.0_fix'
  AND (alpaca_status IS NULL OR alpaca_status NOT IN ('filled', 'partially_filled'));

-- Option 2: For any that did fill, we need to query Alpaca API
-- and reconcile the actual P&L (manual process)
```

---

### Task 6: Integration Test

**Priority**: HIGH
**Risk**: LOW
**Files**: `scripts/test_order_side.py` (new)

#### 6.1 Test Script

```python
#!/usr/bin/env python3
"""
Integration test for order side mapping.
Submits a test order and immediately cancels it.
"""

import os
import sys
import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

def test_order_side_mapping():
    """Test that 'long' correctly maps to BUY order."""

    # Setup
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("TRADING_MODE", "paper").lower() == "paper"

    if not paper:
        print("ERROR: This test must run in paper mode only!")
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=True)

    # Test 1: Submit order with side="long" through our service
    print("Testing order side mapping...")

    # Call the trading service endpoint
    import requests
    response = requests.post(
        "http://localhost:5005/api/v1/orders/test",
        json={
            "symbol": "AAPL",
            "quantity": 1,
            "side": "long",  # This is what workflow sends
            "dry_run": True  # Don't actually submit
        }
    )

    result = response.json()

    # Verify the mapping
    if result.get("mapped_side") == "buy":
        print("✅ PASS: 'long' correctly maps to 'buy'")
        return True
    else:
        print(f"❌ FAIL: 'long' mapped to '{result.get('mapped_side')}'")
        return False

if __name__ == "__main__":
    success = test_order_side_mapping()
    sys.exit(0 if success else 1)
```

#### 6.2 Add Dry-Run Endpoint

Add to trading service for safe testing:

```python
@app.post("/api/v1/orders/test")
async def test_order_mapping(request: OrderTestRequest):
    """Test order side mapping without submitting to Alpaca."""

    mapped_side = _normalize_side(request.side)

    return {
        "input_side": request.side,
        "mapped_side": mapped_side.value,
        "symbol": request.symbol,
        "quantity": request.quantity,
        "dry_run": True,
        "would_submit": not request.dry_run
    }
```

---

## Test Plan

### Unit Tests

| Test Suite | Test Count | Coverage |
|------------|------------|----------|
| test_normalize_side | 12 | `_normalize_side()` function |
| test_round_price | 6 | `_round_price()` function |
| test_validate_mapping | 4 | `_validate_order_side_mapping()` function |
| **Total** | **22** | Core order functions |

### Integration Tests

| Test | Description | Expected Result |
|------|-------------|-----------------|
| test_long_to_buy | Submit order with side="long" | Alpaca receives side="buy" |
| test_short_to_sell | Submit order with side="short" | Alpaca receives side="sell" |
| test_buy_passthrough | Submit order with side="buy" | Alpaca receives side="buy" |
| test_sell_passthrough | Submit order with side="sell" | Alpaca receives side="sell" |

### Manual Verification

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Check trading service logs | See "input_side='long', mapped_side=buy" |
| 2 | Query Alpaca API for recent orders | All orders show correct side |
| 3 | Compare DB positions to Alpaca positions | Sides match |

---

## Rollout Plan

### Phase 1: Unit Tests (No Production Impact)

| Step | Action | Verification |
|------|--------|--------------|
| 1.1 | Create test directory structure | Directory exists |
| 1.2 | Write unit tests | Tests pass locally |
| 1.3 | Add pytest to requirements.txt | Dependency installed |
| 1.4 | Run tests in CI/local | All 22 tests pass |

### Phase 2: Pre-Submission Validation (Low Risk)

| Step | Action | Verification |
|------|--------|--------------|
| 2.1 | Add `_validate_order_side_mapping()` | Function added |
| 2.2 | Integrate into order functions | Code review |
| 2.3 | Test locally | No false positives |
| 2.4 | Deploy to trading service | Health check passes |
| 2.5 | Monitor logs for 1 trading cycle | No validation errors |

### Phase 3: Enhanced Logging (Low Risk)

| Step | Action | Verification |
|------|--------|--------------|
| 3.1 | Add pre-order logging | Code added |
| 3.2 | Add post-order logging | Code added |
| 3.3 | Deploy | Logs visible in docker logs |

### Phase 4: Database Cleanup (Medium Risk)

| Step | Action | Verification |
|------|--------|--------------|
| 4.1 | Run reconciliation query | Review affected positions |
| 4.2 | Query Alpaca for actual fills | Document findings |
| 4.3 | Execute cleanup SQL | Verify position counts |
| 4.4 | Update cycle metrics | Metrics accurate |

### Phase 5: Integration Test (Low Risk)

| Step | Action | Verification |
|------|--------|--------------|
| 5.1 | Add dry-run test endpoint | Endpoint responds |
| 5.2 | Create test script | Script runs |
| 5.3 | Run integration test | All tests pass |
| 5.4 | Add to CI pipeline | Automated testing |

---

## Success Criteria

| Criteria | Measurement |
|----------|-------------|
| Unit test coverage | 22 tests passing |
| No false validation errors | 0 RuntimeError in production |
| Logging captures all orders | 100% of orders logged with side mapping |
| Database reconciled | 0 positions with unknown status |
| Integration tests pass | 4/4 tests passing |

---

## Rollback Plan

### If Validation Causes False Positives

```bash
# 1. Disable validation (comment out _validate_order_side_mapping calls)
# 2. Rebuild and deploy
docker-compose build trading workflow
docker-compose up -d --force-recreate trading workflow

# 3. Verify health
curl http://localhost:5005/health
curl http://localhost:5006/health
```

### If Logging Causes Performance Issues

```bash
# 1. Reduce log level
# Edit trading-service.py: logging.getLogger().setLevel(logging.WARNING)

# 2. Rebuild and deploy
docker-compose up -d --force-recreate trading
```

---

## Estimated Effort

| Task | Effort |
|------|--------|
| Task 1: Unit Tests | 2 hours |
| Task 2: Pre-Submission Validation | 1 hour |
| Task 3: Enhanced Logging | 30 mins |
| Task 4: Standardize Convention | Skipped (Option C) |
| Task 5: Database Cleanup | 1 hour |
| Task 6: Integration Test | 2 hours |
| **Total** | **6.5 hours** |

---

## Approval Checklist

- [ ] Review implementation plan
- [ ] Approve unit test approach
- [ ] Approve validation logic
- [ ] Approve database cleanup SQL
- [ ] Approve integration test design
- [ ] Schedule implementation window

---

## Questions for Review

1. **Database Cleanup**: Should we attempt to reconcile actual Alpaca fills, or just mark all affected positions as cancelled?

2. **Integration Test Frequency**: Should the integration test run:
   - Once before each trading session?
   - As part of CI on each deploy?
   - Manually when changes are made?

3. **Side Convention**: Are you satisfied with Option C (keep `_normalize_side()` translation layer), or would you prefer to standardize on one convention?

---

**Document Status**: DRAFT - Pending Review
**Author**: Claude Code
**Next Action**: User review and approval
