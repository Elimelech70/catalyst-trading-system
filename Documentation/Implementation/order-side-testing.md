# Order Side Bug Testing Guide

**Name of Application**: Catalyst Trading System
**Name of file**: order-side-testing.md
**Version**: 1.0.0
**Last Updated**: 2025-12-06
**Purpose**: Testing guide for order side bug fix (v1.2.0/v1.3.0)

---

## Background

The v1.2.0 bug caused all "long" positions to be placed as SHORT sells due to simple ternary logic:

```python
# BUGGY CODE - DO NOT USE
order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
```

The workflow sends `side="long"`, but `"long" != "buy"`, so it fell through to SELL.

**Impact**: 81 positions affected (Nov 29 - Dec 4, 2025)

---

## Solution (v1.3.0)

### Core Fix: `_normalize_side()`

```python
def _normalize_side(side: str) -> OrderSide:
    side_lower = side.lower()
    if side_lower in ("buy", "long"):
        return OrderSide.BUY
    elif side_lower in ("sell", "short"):
        return OrderSide.SELL
    else:
        raise ValueError(f"Invalid order side: {side}")
```

### Defense-in-Depth: `_validate_order_side_mapping()`

```python
def _validate_order_side_mapping(input_side: str, output_side: OrderSide) -> None:
    input_lower = input_side.lower()
    if input_lower in ("long", "buy") and output_side != OrderSide.BUY:
        raise RuntimeError(f"CRITICAL: Order side mismatch!")
    if input_lower in ("short", "sell") and output_side != OrderSide.SELL:
        raise RuntimeError(f"CRITICAL: Order side mismatch!")
```

---

## Files with Fix

| File | Version | Location |
|------|---------|----------|
| `alpaca_trader.py` | v1.3.0 | `services/trading/common/` |
| `alpaca_trader.py` | v1.3.0 | `services/workflow/common/` |
| `trading-service.py` | v8.2.0 | `services/trading/` |

---

## Testing

### Integration Test

Run before each trading session:

```bash
python3 scripts/test_order_side.py
```

Expected output:
```
RESULT: ALL TESTS PASSED
The order side bug (v1.2.0) fix is working correctly.
'long' correctly maps to 'buy' (not 'sell').
```

### Unit Tests

28 tests in `services/trading/tests/test_alpaca_trader.py`:

```bash
cd /root/catalyst-trading-system/services/trading
python3 -m pytest tests/ -v
```

| Test Suite | Count | Coverage |
|------------|-------|----------|
| TestNormalizeSide | 13 | Side string normalization |
| TestRoundPrice | 6 | Price rounding |
| TestValidateOrderSideMapping | 6 | Validation function |
| TestOrderSideBugRegression | 2 | Critical regression tests |

### Dry-Run API Endpoint

Test side mapping without submitting to Alpaca:

```bash
curl -X POST http://localhost:5005/api/v1/orders/test \
  -H "Content-Type: application/json" \
  -d '{"symbol":"TEST","quantity":1,"side":"long","dry_run":true}'
```

Expected response:
```json
{
  "input_side": "long",
  "mapped_side": "buy",
  "validation": "passed"
}
```

---

## Log Verification

After orders are placed, verify in logs:

```bash
docker logs catalyst-trading --tail 50 | grep "ORDER SUBMISSION"
```

Should show:
```
ORDER SUBMISSION [BRACKET]: symbol=AAPL, input_side='long', mapped_side=buy, qty=100
ORDER CONFIRMED [BRACKET]: order_id=xxx, alpaca_side=OrderSide.BUY
```

**Red flag**: If you see `input_side='long', mapped_side=sell` - STOP TRADING IMMEDIATELY.

---

## Pre-Trading Checklist

```bash
# 1. Run integration test
python3 scripts/test_order_side.py

# 2. Verify alpaca_trader version (must be 1.3.0+)
docker exec catalyst-trading head -10 /app/common/alpaca_trader.py | grep Version
docker exec catalyst-workflow head -10 /app/common/alpaca_trader.py | grep Version

# 3. Check services healthy
curl -s http://localhost:5005/health | python3 -m json.tool
curl -s http://localhost:5006/health | python3 -m json.tool
```

---

## Database Cleanup (Already Done)

Affected positions were marked in database:
- 54 positions: `order_side_bug_v1.2.0_alpaca_rejected`
- 27 positions: `order_side_bug_v1.2.0_pending_cancelled`

Query to check:
```sql
SELECT close_reason, COUNT(*)
FROM positions
WHERE close_reason LIKE '%order_side_bug%'
GROUP BY close_reason;
```
