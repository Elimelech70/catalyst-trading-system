# Risk Management Fix Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** risk-management-fix-implementation.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-13  
**Purpose:** Implementation guide for Claude Code to fix risk management failures  
**Priority:** CRITICAL - Trading halted until complete

---

## Executive Summary

Risk management failed because bracket orders (stop-loss/take-profit) were never submitted to Alpaca. Three root causes identified:

1. **Missing `order_class=OrderClass.BRACKET`** in trading-service (FIXED in v1.4.0)
2. **Duplicate `alpaca_trader.py`** in risk-manager service still has OLD broken code
3. **No fallback monitoring** - system blindly trusted Alpaca bracket orders

---

## Phase 1: Fix Risk Manager alpaca_trader.py (CRITICAL)

### Problem

There are TWO copies of `alpaca_trader.py`:

| File | Version | Status |
|------|---------|--------|
| `services/trading/common/alpaca_trader.py` | v1.4.0 | ✅ Fixed |
| `services/risk-manager/common/alpaca_trader.py` | OLD | ❌ **BROKEN** |

### Task 1.1: Update risk-manager alpaca_trader.py

**File:** `services/risk-manager/common/alpaca_trader.py`

**Action:** Add `order_class=OrderClass.BRACKET` to ALL order request types.

**Find this code (BROKEN):**
```python
# In submit_bracket_order() function - Market order
request = MarketOrderRequest(
    symbol=symbol,
    qty=quantity,
    side=order_side,
    time_in_force=TimeInForce.DAY,
    stop_loss=stop_loss_req,
    take_profit=take_profit_req
)
```

**Replace with (FIXED):**
```python
# In submit_bracket_order() function - Market order
request = MarketOrderRequest(
    symbol=symbol,
    qty=quantity,
    side=order_side,
    time_in_force=TimeInForce.DAY,
    order_class=OrderClass.BRACKET,  # CRITICAL: Required for stop/target
    stop_loss=stop_loss_req,
    take_profit=take_profit_req
)
```

**Find this code (BROKEN):**
```python
# In submit_bracket_order() function - Limit order
request = LimitOrderRequest(
    symbol=symbol,
    qty=quantity,
    side=order_side,
    time_in_force=TimeInForce.DAY,
    limit_price=entry_price,
    stop_loss=stop_loss_req,
    take_profit=take_profit_req
)
```

**Replace with (FIXED):**
```python
# In submit_bracket_order() function - Limit order
request = LimitOrderRequest(
    symbol=symbol,
    qty=quantity,
    side=order_side,
    time_in_force=TimeInForce.DAY,
    limit_price=entry_price,
    order_class=OrderClass.BRACKET,  # CRITICAL: Required for stop/target
    stop_loss=stop_loss_req,
    take_profit=take_profit_req
)
```

**Also ensure import exists:**
```python
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, QueryOrderStatus, OrderClass
```

### Task 1.2: Add _normalize_side() function if missing

Check if `_normalize_side()` helper exists in risk-manager version. If not, add:

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
        raise ValueError(f"Invalid order side: {side}")
```

### Task 1.3: Add _round_price() function if missing

```python
def _round_price(price: Optional[float]) -> Optional[float]:
    """
    Round price to 2 decimal places for Alpaca API compliance.
    """
    if price is None:
        return None
    return round(float(price), 2)
```

### Task 1.4: Update version header

```python
"""
Name of Application: Catalyst Trading System
Name of file: alpaca_trader.py
Version: 1.4.0
Last Updated: 2025-12-14
Purpose: Alpaca trading integration for risk manager service

REVISION HISTORY:
v1.4.0 (2025-12-14) - Sync with trading-service fixes
- Added OrderClass.BRACKET to all bracket order requests
- Added _normalize_side() for long/short handling
- Added _round_price() for sub-penny compliance
- Synced with services/trading/common/alpaca_trader.py v1.4.0
"""
```

---

## Phase 2: Consolidate to Single Shared Module

### Problem

Having two copies of `alpaca_trader.py` caused this bug. When trading-service was fixed, risk-manager was forgotten.

### Task 2.1: Create shared module location

**Create directory:** `services/shared/common/`

**Move file:** Copy `services/trading/common/alpaca_trader.py` (v1.4.0) to `services/shared/common/alpaca_trader.py`

### Task 2.2: Update trading-service imports

**File:** `services/trading/trading-service.py`

**Change:**
```python
from common.alpaca_trader import AlpacaTrader
```

**To:**
```python
import sys
sys.path.insert(0, '/app/shared')
from common.alpaca_trader import AlpacaTrader
```

### Task 2.3: Update risk-manager imports

**File:** `services/risk-manager/risk-manager.py`

**Change:**
```python
from common.alpaca_trader import AlpacaTrader
```

**To:**
```python
import sys
sys.path.insert(0, '/app/shared')
from common.alpaca_trader import AlpacaTrader
```

### Task 2.4: Update docker-compose.yml

Add shared volume mount to both services:

```yaml
services:
  trading:
    volumes:
      - ./services/shared:/app/shared:ro
      
  risk-manager:
    volumes:
      - ./services/shared:/app/shared:ro
```

### Task 2.5: Delete duplicate files

After verification, remove:
- `services/trading/common/alpaca_trader.py`
- `services/risk-manager/common/alpaca_trader.py`

---

## Phase 3: Add Fallback Position Monitoring

### Problem

System relied 100% on Alpaca bracket orders. When they silently failed, there was no backup.

### Task 3.1: Create position monitor background task

**File:** `services/risk-manager/risk-manager.py`

**Add new background task:**

```python
import asyncio
from datetime import datetime, timedelta

class PositionMonitor:
    """
    Fallback position monitoring that checks positions against stops.
    Runs every 30 seconds during market hours.
    """
    
    def __init__(self, db_pool, alpaca_trader):
        self.db_pool = db_pool
        self.alpaca_trader = alpaca_trader
        self.running = False
        
    async def start(self):
        """Start the position monitoring loop"""
        self.running = True
        logger.info("Position monitor started")
        
        while self.running:
            try:
                await self._check_positions()
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def stop(self):
        """Stop the position monitoring loop"""
        self.running = False
        logger.info("Position monitor stopped")
    
    async def _check_positions(self):
        """Check all open positions against their stop prices"""
        
        async with self.db_pool.acquire() as conn:
            # Get all open positions with stop prices
            positions = await conn.fetch("""
                SELECT 
                    p.position_id,
                    p.alpaca_order_id,
                    s.symbol,
                    p.quantity,
                    p.entry_price,
                    p.stop_loss,
                    p.take_profit,
                    p.side
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                WHERE p.status = 'open'
                AND p.stop_loss IS NOT NULL
            """)
            
            if not positions:
                return
            
            # Get current prices from Alpaca
            symbols = [p['symbol'] for p in positions]
            
            try:
                current_prices = await self.alpaca_trader.get_current_prices(symbols)
            except Exception as e:
                logger.error(f"Failed to get current prices: {e}")
                return
            
            # Check each position
            for pos in positions:
                symbol = pos['symbol']
                current_price = current_prices.get(symbol)
                
                if current_price is None:
                    continue
                
                stop_loss = float(pos['stop_loss'])
                take_profit = float(pos['take_profit']) if pos['take_profit'] else None
                side = pos['side']
                
                should_close = False
                close_reason = None
                
                # Check stop loss (for long positions, close if price <= stop)
                if side == 'long' and current_price <= stop_loss:
                    should_close = True
                    close_reason = f"STOP_LOSS_HIT: {symbol} @ ${current_price:.2f} <= ${stop_loss:.2f}"
                
                # Check take profit (for long positions, close if price >= target)
                if take_profit and side == 'long' and current_price >= take_profit:
                    should_close = True
                    close_reason = f"TAKE_PROFIT_HIT: {symbol} @ ${current_price:.2f} >= ${take_profit:.2f}"
                
                if should_close:
                    logger.warning(f"FALLBACK CLOSE TRIGGERED: {close_reason}")
                    await self._close_position(pos, current_price, close_reason)
    
    async def _close_position(self, position: dict, current_price: float, reason: str):
        """Close a position via market order"""
        
        symbol = position['symbol']
        quantity = position['quantity']
        
        try:
            # Submit market sell order to Alpaca
            result = await self.alpaca_trader.submit_market_order(
                symbol=symbol,
                quantity=quantity,
                side='sell'
            )
            
            logger.info(f"Fallback close order submitted: {symbol} {quantity} shares, reason: {reason}")
            
            # Update database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE positions
                    SET 
                        status = 'closed',
                        exit_price = $1,
                        closed_at = NOW(),
                        close_reason = $2
                    WHERE position_id = $3
                """, current_price, reason, position['position_id'])
            
        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
```

### Task 3.2: Add get_current_prices to AlpacaTrader

**File:** `services/shared/common/alpaca_trader.py`

**Add method:**

```python
async def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
    """
    Get current prices for multiple symbols.
    
    Args:
        symbols: List of stock symbols
        
    Returns:
        Dictionary mapping symbol to current price
    """
    if not self.enabled:
        raise RuntimeError("Alpaca trading not enabled")
    
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        
        data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        
        request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
        quotes = data_client.get_stock_latest_quote(request)
        
        prices = {}
        for symbol, quote in quotes.items():
            # Use mid-point of bid/ask
            if quote.bid_price and quote.ask_price:
                prices[symbol] = (quote.bid_price + quote.ask_price) / 2
            elif quote.ask_price:
                prices[symbol] = quote.ask_price
            elif quote.bid_price:
                prices[symbol] = quote.bid_price
        
        return prices
        
    except Exception as e:
        logger.error(f"Failed to get current prices: {e}")
        raise
```

### Task 3.3: Integrate monitor into risk-manager startup

**File:** `services/risk-manager/risk-manager.py`

**In lifespan/startup:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_pool, position_monitor
    
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    logger.info("Database pool created")
    
    # Start position monitor
    position_monitor = PositionMonitor(db_pool, alpaca_trader)
    asyncio.create_task(position_monitor.start())
    logger.info("Position monitor started")
    
    yield
    
    # Shutdown
    position_monitor.stop()
    await db_pool.close()
    logger.info("Shutdown complete")
```

---

## Phase 4: Add close_reason Column to Database

### Task 4.1: Run migration

```sql
-- Add close_reason column to positions table
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS close_reason VARCHAR(255);

-- Add index for querying closed positions by reason
CREATE INDEX IF NOT EXISTS idx_positions_close_reason 
ON positions(close_reason) 
WHERE close_reason IS NOT NULL;

COMMENT ON COLUMN positions.close_reason IS 
'Reason for position closure: STOP_LOSS_HIT, TAKE_PROFIT_HIT, MANUAL, EMERGENCY_STOP, MARKET_CLOSE';
```

---

## Phase 5: Testing Requirements

### Task 5.1: Unit test for bracket order

**File:** `tests/test_alpaca_trader.py`

```python
import pytest
from unittest.mock import Mock, patch
from services.shared.common.alpaca_trader import AlpacaTrader

def test_bracket_order_includes_order_class():
    """Verify bracket orders include OrderClass.BRACKET"""
    
    with patch('alpaca.trading.client.TradingClient') as mock_client:
        trader = AlpacaTrader()
        trader.enabled = True
        trader.trading_client = mock_client.return_value
        
        # Mock order submission
        mock_order = Mock()
        mock_order.id = "test-order-id"
        mock_order.status.value = "accepted"
        mock_order.submitted_at = None
        mock_client.return_value.submit_order.return_value = mock_order
        
        # Submit bracket order
        import asyncio
        asyncio.run(trader.submit_bracket_order(
            symbol="AAPL",
            quantity=100,
            side="long",
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00
        ))
        
        # Verify order_class was set
        call_args = mock_client.return_value.submit_order.call_args
        request = call_args[0][0]
        
        assert hasattr(request, 'order_class'), "order_class not set!"
        assert request.order_class == OrderClass.BRACKET, "order_class not BRACKET!"
```

### Task 5.2: Integration test before enabling trading

```bash
# 1. Submit test bracket order
curl -X POST http://localhost:5005/api/v1/orders/test \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "quantity": 1,
    "side": "buy",
    "entry_price": 150.00,
    "stop_loss": 145.00,
    "take_profit": 160.00
  }'

# 2. Check Alpaca dashboard for 3-legged order
# Should see: Parent order + Stop order + Take profit order

# 3. Verify in logs
docker logs trading-service | grep "ORDER CONFIRMED \[BRACKET\]"
```

---

## Phase 6: Deployment Checklist

### Pre-deployment

- [ ] risk-manager alpaca_trader.py updated to v1.4.0
- [ ] OrderClass.BRACKET added to ALL order types
- [ ] _normalize_side() function present
- [ ] _round_price() function present
- [ ] Import includes OrderClass
- [ ] Unit tests pass
- [ ] Shared module created (optional, can be Phase 2)

### Deployment

```bash
# 1. Stop trading cron
crontab -e  # Comment out trading jobs

# 2. Deploy updated services
docker-compose build risk-manager trading
docker-compose up -d risk-manager trading

# 3. Verify services started
docker-compose ps

# 4. Check logs for errors
docker-compose logs --tail=50 risk-manager
docker-compose logs --tail=50 trading
```

### Post-deployment verification

```bash
# 1. Test bracket order submission
curl -X POST http://localhost:5005/api/v1/orders/test \
  -d '{"symbol":"AAPL","quantity":1,"side":"buy","entry_price":150,"stop_loss":145,"take_profit":160}'

# 2. Check Alpaca for 3-legged order
# Login to https://app.alpaca.markets
# Navigate to Orders tab
# Verify: Parent + Stop + Target orders created

# 3. Re-enable trading cron (only after verification)
crontab -e  # Uncomment trading jobs
```

---

## Summary of Changes

| File | Change | Priority |
|------|--------|----------|
| `services/risk-manager/common/alpaca_trader.py` | Add `order_class=OrderClass.BRACKET` | CRITICAL |
| `services/risk-manager/common/alpaca_trader.py` | Add `_normalize_side()` | CRITICAL |
| `services/risk-manager/common/alpaca_trader.py` | Add `_round_price()` | CRITICAL |
| `services/risk-manager/common/alpaca_trader.py` | Update version to 1.4.0 | HIGH |
| `services/risk-manager/risk-manager.py` | Add PositionMonitor class | HIGH |
| `services/shared/common/alpaca_trader.py` | Create shared module | MEDIUM |
| `docker-compose.yml` | Add shared volume mounts | MEDIUM |
| Database | Add close_reason column | LOW |

---

## Do NOT Re-enable Trading Until

1. ✅ risk-manager alpaca_trader.py fixed
2. ✅ Test bracket order shows 3 legs in Alpaca
3. ✅ Position monitor running (check logs)
4. ✅ All 34 positions closed from previous week

---

*Implementation guide created by Claude Opus 4.5 for Claude Code execution*
