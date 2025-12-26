# US Catalyst Trading System - Troubleshooting & Implementation Plan

**Name of Application:** Catalyst Trading System  
**Name of file:** us-system-troubleshooting-plan-2025-12-25.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-25  
**Purpose:** Step-by-step guide for Claude Code to diagnose and fix the US trading system  

---

## REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-25 | Initial troubleshooting plan based on Dec 23 report |

---

## Executive Summary

The US Catalyst Trading System has been offline since December 16, 2025. Analysis of the December 23rd report reveals:

| Issue | Severity | Impact |
|-------|----------|--------|
| 40.7% Order Error Rate | 🔴 Critical | 57 of 140 orders failed |
| 26.4% Fill Rate | 🔴 Critical | Only 37 orders executed |
| P&L Not Recording | 🔴 Critical | No exit prices captured |
| 13.6% Expired Orders | 🟠 Medium | 19 orders timed out |
| Services Offline | 🟡 Expected | Intentional halt Dec 13 |

**Goal:** Get the system to a clean, working state with proper order execution and P&L tracking.

---

## Phase 1: Diagnosis (Do This First)

### 1.1 Check Current System State

```bash
# SSH to droplet
ssh root@<catalyst-droplet-ip>

# Check Docker container status
docker ps -a

# Check disk space
df -h

# Check system resources
free -m
top -bn1 | head -20
```

### 1.2 Examine Order Errors

```sql
-- Connect to database
psql $DATABASE_URL

-- Get breakdown of error types
SELECT 
    alpaca_status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
FROM positions
WHERE created_at >= '2025-11-29'
GROUP BY alpaca_status
ORDER BY count DESC;

-- Get actual error messages
SELECT 
    position_id,
    symbol,
    entry_price,
    alpaca_status,
    alpaca_order_id,
    error_message,
    created_at
FROM positions
WHERE alpaca_status = 'error'
ORDER BY created_at DESC
LIMIT 20;
```

### 1.3 Identify Error Patterns

Look for these known issues in the error messages:

| Error Pattern | Root Cause | Fix Reference |
|---------------|------------|---------------|
| "sub-penny" or "tick size" | Floating point precision | alpaca_trader.py v1.1.0 |
| "invalid side" or "side" | Order side mapping | alpaca_trader.py v1.3.0 |
| "rejected" with bracket | Missing OrderClass.BRACKET | alpaca_trader.py v1.4.0 |
| Order stuck in "accepted" | No status sync | trading-service.py v8.3.0 |

```sql
-- Categorize errors by type
SELECT 
    CASE 
        WHEN error_message ILIKE '%sub-penny%' OR error_message ILIKE '%tick%' THEN 'SUB_PENNY'
        WHEN error_message ILIKE '%side%' THEN 'ORDER_SIDE'
        WHEN error_message ILIKE '%bracket%' THEN 'BRACKET_ORDER'
        WHEN error_message ILIKE '%rejected%' THEN 'REJECTED'
        ELSE 'OTHER'
    END as error_type,
    COUNT(*) as count
FROM positions
WHERE alpaca_status = 'error'
AND created_at >= '2025-11-29'
GROUP BY error_type
ORDER BY count DESC;
```

---

## Phase 2: Verify Fixes Are Deployed

### 2.1 Check Service Versions

```bash
cd /root/catalyst-trading-system

# Check alpaca_trader.py version
head -20 services/trading/alpaca_trader.py | grep -i version

# Check trading-service.py version
head -20 services/trading/trading-service.py | grep -i version

# Expected versions:
# alpaca_trader.py: v1.4.0 or higher
# trading-service.py: v8.3.0 or higher
```

### 2.2 Verify Critical Fixes Present

#### Fix 1: Sub-Penny Pricing (v1.1.0)

```bash
# Check for _round_price function
grep -n "_round_price" services/trading/alpaca_trader.py
```

**Expected:** Function exists that rounds prices to 2 decimal places

```python
# Should contain something like:
def _round_price(self, price: float) -> float:
    if price is None:
        return None
    return round(float(price), 2)
```

#### Fix 2: Order Side Mapping (v1.3.0)

```bash
# Check order side mapping
grep -n "side" services/trading/alpaca_trader.py | grep -i "buy\|sell"
```

**Expected:** Explicit mapping from "long"→"buy", "short"→"sell"

#### Fix 3: Bracket Orders (v1.4.0)

```bash
# Check for OrderClass.BRACKET
grep -n "OrderClass" services/trading/alpaca_trader.py
grep -n "order_class" services/trading/alpaca_trader.py
```

**Expected:** `order_class=OrderClass.BRACKET` in bracket order submission

#### Fix 4: Order Status Sync (v8.3.0)

```bash
# Check for background sync task
grep -n "sync" services/trading/trading-service.py
grep -n "60" services/trading/trading-service.py  # 60-second interval
```

**Expected:** Background task that syncs order status every 60 seconds

---

## Phase 3: Fix Missing Components

### 3.1 If Sub-Penny Fix Missing

Add to `services/trading/alpaca_trader.py`:

```python
def _round_price(self, price: float) -> float:
    """Round price to 2 decimal places to avoid sub-penny errors."""
    if price is None:
        return None
    return round(float(price), 2)
```

Apply to all order submissions:
- `submit_limit_order()` → `limit_price = self._round_price(limit_price)`
- `submit_bracket_order()` → Round entry_price, stop_loss, take_profit

### 3.2 If Order Side Fix Missing

```python
# In submit_limit_order() and submit_bracket_order()
def _map_side(self, side: str) -> OrderSide:
    """Map position side to Alpaca order side."""
    side_map = {
        'long': OrderSide.BUY,
        'buy': OrderSide.BUY,
        'short': OrderSide.SELL,
        'sell': OrderSide.SELL
    }
    mapped = side_map.get(side.lower())
    if not mapped:
        raise ValueError(f"Invalid side: {side}")
    return mapped
```

### 3.3 If Bracket Order Fix Missing

```python
# In submit_bracket_order()
order = self.client.submit_order(
    symbol=symbol,
    qty=quantity,
    side=self._map_side(side),
    type=OrderType.LIMIT,
    time_in_force=TimeInForce.DAY,
    limit_price=str(self._round_price(entry_price)),
    order_class=OrderClass.BRACKET,  # THIS IS CRITICAL
    stop_loss={"stop_price": str(self._round_price(stop_loss))},
    take_profit={"limit_price": str(self._round_price(take_profit))}
)
```

### 3.4 If P&L Tracking Missing

The report shows $0.00 realized P&L for all positions. Check exit price recording:

```sql
-- Check if exit prices are being recorded
SELECT 
    position_id,
    symbol,
    entry_price,
    exit_price,
    realized_pnl,
    status,
    alpaca_status
FROM positions
WHERE alpaca_status = 'filled'
AND status = 'closed'
ORDER BY closed_at DESC
LIMIT 10;
```

If exit_price is NULL for closed positions, the close order handler needs fixing:

```python
# In trading-service.py - when closing positions
async def close_position(self, position_id: int, exit_price: float):
    realized_pnl = (exit_price - entry_price) * quantity
    if side == 'short':
        realized_pnl = -realized_pnl
    
    await conn.execute("""
        UPDATE positions SET
            exit_price = $1,
            realized_pnl = $2,
            status = 'closed',
            closed_at = NOW()
        WHERE position_id = $3
    """, exit_price, realized_pnl, position_id)
```

---

## Phase 4: Database Cleanup

### 4.1 Reset Error Positions (Optional)

If you want to clear the slate:

```sql
-- Archive old error positions (DO NOT DELETE - preserve audit trail)
UPDATE positions
SET status = 'archived',
    notes = 'Archived during Dec 25 cleanup - original status: ' || alpaca_status
WHERE alpaca_status = 'error'
AND created_at < '2025-12-16';

-- Verify cleanup
SELECT status, COUNT(*) FROM positions GROUP BY status;
```

### 4.2 Reconcile with Alpaca

```bash
# Run reconciliation script
cd /root/catalyst-trading-system
python3 scripts/reconcile_positions.py
```

Or manually:

```sql
-- Find positions in DB that don't match Alpaca
-- (Run after checking Alpaca dashboard for actual open positions)

-- If Alpaca shows 0 open positions, mark all as closed
UPDATE positions
SET status = 'closed'
WHERE status = 'open';
```

---

## Phase 5: Restart Services

### 5.1 Pre-Start Checklist

- [ ] All fixes verified in code
- [ ] Database cleaned up
- [ ] Alpaca API keys valid
- [ ] Paper trading mode confirmed
- [ ] Sufficient disk space (>1GB)

### 5.2 Start Services

```bash
cd /root/catalyst-trading-system

# Pull latest code
git pull origin main

# Rebuild containers with fixes
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify all services healthy
docker ps
docker-compose logs --tail=50
```

### 5.3 Verify Health

```bash
# Health check all services
curl http://localhost:5001/health  # Scanner
curl http://localhost:5002/health  # Pattern
curl http://localhost:5003/health  # Technical
curl http://localhost:5004/health  # Risk Manager
curl http://localhost:5005/health  # Trading
curl http://localhost:5006/health  # Workflow
curl http://localhost:5008/health  # News
curl http://localhost:5009/health  # Reporting
```

---

## Phase 6: Test Before Live

### 6.1 Unit Test Order Submission

```bash
# Test order side mapping
python3 scripts/test_order_side.py

# Test price rounding
python3 -c "
from services.trading.alpaca_trader import AlpacaTrader
trader = AlpacaTrader()
print('Sub-penny test:', trader._round_price(9.050000190734863))  # Should be 9.05
print('Clean price:', trader._round_price(10.0))  # Should be 10.0
"
```

### 6.2 Submit Test Order

```bash
# Submit a single test order (paper trading)
curl -X POST http://localhost:5005/api/test-order \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "side": "long",
    "quantity": 1,
    "limit_price": 250.00
  }'
```

Check Alpaca dashboard to verify order appears correctly.

### 6.3 Run Single Workflow Cycle

```bash
# Trigger one workflow cycle manually
curl -X POST http://localhost:5006/api/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "max_positions": 1}'
```

Monitor logs:
```bash
docker-compose logs -f workflow trading
```

---

## Phase 7: Enable Cron Automation

Only after successful test cycle:

### 7.1 Review Crontab

```bash
crontab -l

# Expected schedule (Perth timezone = EST + 13 hours)
# 20:30 ET = 09:30 Perth (next day) - Market open
# 22:00 ET = 11:00 Perth
# 00:00 ET = 13:00 Perth
# 02:00 ET = 15:00 Perth
```

### 7.2 Enable Cron Jobs

```bash
# If cron disabled, re-enable
crontab /root/catalyst-trading-system/scripts/catalyst.crontab

# Verify
crontab -l
```

---

## Success Criteria

Before declaring the system "working":

| Criteria | How to Verify |
|----------|---------------|
| Services running | `docker ps` shows all 8 healthy |
| Orders submitting | Test order appears in Alpaca |
| No sub-penny errors | Check logs for price formatting |
| Correct order side | "long" maps to "buy" |
| Bracket orders work | Stop/take-profit legs created |
| P&L tracking | Exit price recorded on close |
| Status sync | DB matches Alpaca within 60s |

---

## Rollback Plan

If issues persist after fixes:

```bash
# Stop all services
docker-compose down

# Revert to last known good commit
git log --oneline -10
git checkout <last-good-commit>

# Rebuild
docker-compose build --no-cache
docker-compose up -d
```

---

## Reference: Known Bug Fixes

| Bug | Version Fixed | File | Key Change |
|-----|---------------|------|------------|
| Sub-penny pricing | v1.1.0 / v8.1.0 | alpaca_trader.py | `_round_price()` |
| Order side mapping | v1.3.0 | alpaca_trader.py | `_map_side()` |
| Bracket orders | v1.4.0 | alpaca_trader.py | `OrderClass.BRACKET` |
| Status sync | v8.3.0 | trading-service.py | 60s background task |
| Position dedup | v8.3.0 | trading-service.py | Check existing positions |
| Position limit | v8.3.0 | trading-service.py | Max 50 positions |

---

## Contact Points

- **GitHub Repo**: https://github.com/Elimelech70/catalyst-trading-system
- **Database**: DigitalOcean Managed PostgreSQL
- **Broker**: Alpaca (Paper Trading)
- **Droplet**: catalyst-droplet on DigitalOcean

---

*Document created by Claude Opus 4.5 for Claude Code implementation*
*Catalyst Trading System - December 25, 2025*
