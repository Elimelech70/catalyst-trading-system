# Alpaca Integration - Implementation Complete

**Date**: 2025-11-18
**Status**: ✅ **FULLY INTEGRATED**
**Version**: Trading Service v8.0.0, Risk Manager v7.0.0

---

## 🎉 Summary

**Alpaca API integration is NOW complete in both Trading Service and Risk Manager.**

The system will:
- ✅ Submit **real bracket orders** to Alpaca when positions are created
- ✅ Close **real positions** via Alpaca during emergency stop
- ✅ Track Alpaca order IDs and status in database
- ✅ Handle errors gracefully (doesn't fail if Alpaca unavailable)
- ✅ Support both **paper trading** and **live trading**

---

## 📦 Updated Services

### 1. **Trading Service** (`services/trading/trading-service.py`)
**Version**: 8.0.0 (was 6.0.0)
**Changes**: +70 lines

#### **Integration Point**: `create_position` endpoint

**What It Does**:
```python
@app.post("/api/v1/positions")
async def create_position(cycle_id: str, request: PositionRequest):
    # ... risk validation ...

    # Create position in database
    position_id = await create_db_position(...)

    # ✅ NEW: Submit order to Alpaca
    if alpaca_trader.is_enabled():
        alpaca_order = await alpaca_trader.submit_bracket_order(
            symbol=request.symbol,
            quantity=request.quantity,
            side=request.side,
            entry_price=request.entry_price,    # None = market order
            stop_loss=request.stop_loss,        # Stop loss price
            take_profit=request.take_profit     # Take profit price
        )

        # Store Alpaca order_id in database
        await update_position_alpaca_info(
            position_id=position_id,
            alpaca_order_id=alpaca_order['order_id'],
            alpaca_status=alpaca_order['status']
        )

    return {
        "position_id": position_id,
        "alpaca_order_id": alpaca_order_id,     # NEW
        "alpaca_status": alpaca_status,          # NEW
        "alpaca_enabled": True                   # NEW
    }
```

#### **Bracket Order**:
```
Entry Order (Limit or Market)
    ├─> Stop Loss Order (at stop_loss price)
    └─> Take Profit Order (at take_profit price)
```

When entry fills:
- Stop loss becomes active
- Take profit becomes active
- When either triggers, the other is automatically cancelled

#### **Error Handling**:
- If Alpaca submission **fails**: Logs error, stores in DB, but **doesn't fail position creation**
- If Alpaca **not configured**: Creates DB position, logs warning
- All errors tracked in `alpaca_status` and `alpaca_error` database columns

#### **Database Columns Added**:
The code assumes these columns exist in `positions` table:
- `alpaca_order_id` (VARCHAR) - Alpaca's order ID
- `alpaca_status` (VARCHAR) - Order status (new/filled/error/etc.)
- `alpaca_error` (TEXT) - Error message if submission failed

**Note**: You may need to add these columns to your database schema:
```sql
ALTER TABLE positions
ADD COLUMN alpaca_order_id VARCHAR(50),
ADD COLUMN alpaca_status VARCHAR(50),
ADD COLUMN alpaca_error TEXT;
```

---

### 2. **Risk Manager** (`services/risk-manager/risk-manager-service.py`)
**Version**: 7.0.0 (no version change from monitoring update)
**Changes**: +60 lines in `execute_emergency_stop`

#### **Integration Point**: `execute_emergency_stop` function

**What It Does**:
```python
async def execute_emergency_stop(cycle_id: str, reason: str):
    # Get all open positions
    open_positions = await get_open_positions(cycle_id)

    # ✅ NEW: Close real positions via Alpaca FIRST
    if alpaca_trader.is_enabled():
        # Method 1: Close all at once (fastest)
        alpaca_results = await alpaca_trader.close_all_positions()

        # If that fails, fallback to individual closes
        for position in open_positions:
            await alpaca_trader.close_position(position['symbol'])

    # Mark positions as closed in database
    for position in open_positions:
        await close_position_in_db(position['position_id'])

    # Send emergency stop alert
    await alert_manager.alert_emergency_stop(
        reason=reason,
        positions_closed=db_closed,
        alpaca_positions_closed=alpaca_closed
    )
```

#### **Emergency Stop Flow**:
```
Daily P&L hits -$2,000
    ↓
monitor_positions_continuously() detects limit
    ↓
execute_emergency_stop() triggered
    ↓
1. Close ALL positions via Alpaca
   - Calls alpaca_trader.close_all_positions()
   - Submits market orders to exit all positions
    ↓
2. Mark positions as closed in database
   - Updates status = 'closed'
   - Sets alpaca_status = 'closed_by_emergency_stop'
    ↓
3. Stop the trading cycle
   - Updates cycle status = 'stopped'
    ↓
4. Send critical email alert
   - Subject: "🛑 EMERGENCY STOP - Trading Halted"
   - Body: "Closed X DB positions, Y Alpaca positions"
```

#### **Error Handling**:
- If `close_all_positions()` fails → Falls back to individual `close_position()` calls
- If individual close fails → Logs error, continues with others
- Even if Alpaca closes fail → Still closes DB positions and sends alert
- All errors stored in `result["errors"]` array

---

## 🔧 Configuration Required

### **Environment Variables** (`.env`)

```bash
# Alpaca API Credentials
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here

# Trading Mode
TRADING_MODE=paper              # Options: "paper" or "live"
# paper = Uses Alpaca paper trading endpoint (recommended for testing)
# live = Uses Alpaca live trading endpoint (REAL MONEY!)
```

### **Get Alpaca Credentials**:

1. **Paper Trading** (Recommended for testing):
   - Sign up at https://alpaca.markets
   - Generate API keys from paper trading account
   - Free, unlimited, no real money

2. **Live Trading** (Real money):
   - Complete Alpaca account verification
   - Fund account
   - Generate live API keys
   - Set `TRADING_MODE=live`

---

## 🧪 Testing Alpaca Integration

### **Test Alpaca Connectivity**:
```bash
# Test Alpaca trader utility
cd services/common
python3 alpaca_trader.py

# Expected output:
# ✅ Account: XXXXXXXX
# ✅ Cash: $100,000.00
# ✅ Portfolio: $100,000.00
# ✅ AAPL price: $150.25
```

### **Test Trading Service Integration**:
```bash
# Start trading service
docker-compose up -d trading

# Create a test position
curl -X POST http://localhost:5005/api/v1/positions?cycle_id=test_cycle \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 1,
    "entry_price": 150.00,
    "stop_loss": 145.00,
    "take_profit": 160.00
  }'

# Expected response:
# {
#   "success": true,
#   "position_id": 123,
#   "alpaca_order_id": "a1b2c3d4-...",
#   "alpaca_status": "new",
#   "alpaca_enabled": true
# }

# Check Alpaca dashboard to see the bracket order
```

### **Test Risk Manager Emergency Stop**:
```bash
# Manually trigger emergency stop (testing only)
curl -X POST http://localhost:5004/api/v1/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{
    "cycle_id": "test_cycle",
    "reason": "Manual test"
  }'

# Expected:
# - All open positions closed via Alpaca
# - Email alert sent
# - Cycle marked as stopped
```

---

## 📊 Database Schema Updates

### **Required Columns** (if not already present):

```sql
-- Add to positions table
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS alpaca_order_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS alpaca_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS alpaca_error TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_positions_alpaca_order_id
ON positions(alpaca_order_id);
```

### **Column Usage**:
- **`alpaca_order_id`**: Alpaca's unique order ID (e.g., "a1b2c3d4-e5f6-...")
- **`alpaca_status`**: Current order status:
  - `new` - Order submitted to Alpaca
  - `filled` - Order executed
  - `partially_filled` - Partial execution
  - `canceled` - Order cancelled
  - `error` - Submission failed
  - `alpaca_disabled` - Alpaca not configured
  - `closed_by_emergency_stop` - Closed during emergency stop
- **`alpaca_error`**: Error message if submission failed

---

## 🚀 Deployment Checklist

### **Before Deploying**:
- [ ] Alpaca API keys configured in `.env`
- [ ] `TRADING_MODE=paper` set (for testing)
- [ ] Database schema updated (added alpaca columns)
- [ ] Test Alpaca connectivity (`python3 alpaca_trader.py`)
- [ ] Test single position creation
- [ ] Verify order appears in Alpaca dashboard

### **Testing Phase** (Paper Trading):
- [ ] Create test positions
- [ ] Verify bracket orders in Alpaca
- [ ] Test emergency stop
- [ ] Verify positions close in Alpaca
- [ ] Monitor for 1-2 days

### **Go Live** (Real Money):
- [ ] Complete Alpaca account verification
- [ ] Fund Alpaca account
- [ ] Update `.env`: `TRADING_MODE=live`
- [ ] Start with small position sizes
- [ ] Monitor closely for first week

---

## 🔍 Monitoring & Troubleshooting

### **Check Alpaca Integration Status**:
```bash
# View trading service logs
docker-compose logs -f trading | grep -i alpaca

# Expected logs:
# "Alpaca trader initialized (PAPER mode)"
# "Submitting bracket order to Alpaca: AAPL"
# "Alpaca order submitted successfully: a1b2c3d4..."

# View risk manager logs
docker-compose logs -f risk-manager | grep -i alpaca

# Expected logs:
# "Closing all positions via Alpaca..."
# "Alpaca closed 5 positions successfully"
```

### **Common Issues**:

#### **1. "Alpaca not enabled"**
```
Cause: ALPACA_API_KEY or ALPACA_SECRET_KEY not set
Fix: Check .env file, ensure credentials are set
```

#### **2. "Forbidden" error from Alpaca**
```
Cause: Invalid API keys or wrong mode (paper vs live)
Fix: Regenerate API keys, check TRADING_MODE setting
```

#### **3. "Insufficient buying power"**
```
Cause: Not enough cash in Alpaca account
Fix: Fund paper account or reduce position sizes
```

#### **4. "Symbol not found"**
```
Cause: Invalid ticker symbol
Fix: Verify symbol is valid and tradeable on Alpaca
```

#### **5. Orders not appearing in Alpaca dashboard**
```
Cause: Using wrong API keys (live vs paper)
Fix: Ensure API keys match TRADING_MODE setting
```

---

## 📋 Integration Summary

### **What Works Now**:
✅ Submit bracket orders to Alpaca when creating positions
✅ Store Alpaca order IDs in database
✅ Track order status (new/filled/error)
✅ Close all positions via Alpaca during emergency stop
✅ Fallback to individual closes if close_all fails
✅ Error logging and tracking
✅ Paper trading and live trading support
✅ Graceful degradation (works without Alpaca)

### **What's Still Manual**:
🟡 Database schema migration (add alpaca columns)
🟡 Monitoring order fills and updating P&L
🟡 Handling partial fills
🟡 Cancelling pending orders during emergency stop

### **Future Enhancements** (Optional):
- Order fill tracking (webhook or polling)
- Real-time P&L updates from Alpaca
- Position sync (Alpaca → Database)
- Advanced order types (stop-limit, trailing stop)
- Multi-leg strategies

---

## 🎯 Integration Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ USER / CRON                                                 │
│ POST /api/v1/workflow/start                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ WORKFLOW COORDINATOR                                        │
│ - Scans market                                              │
│ - Filters candidates                                        │
│ - Validates with Risk Manager                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ TRADING SERVICE v8.0.0                                      │
├─────────────────────────────────────────────────────────────┤
│ create_position(symbol="AAPL", qty=10, ...)                │
│   1. Create position in database ✅                         │
│   2. Submit bracket order to Alpaca ✅ NEW                  │
│      - Entry: Limit @ $150                                  │
│      - Stop: $145                                           │
│      - Target: $160                                         │
│   3. Store alpaca_order_id in DB ✅ NEW                     │
│   4. Return position details                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                  ┌─────────┐
                  │ ALPACA  │
                  │   API   │
                  └─────────┘
                       │
                       ▼
                Order executed when price hits limit
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ RISK MANAGER v7.0.0 (Background Monitoring)                │
├─────────────────────────────────────────────────────────────┤
│ Every 60 seconds:                                           │
│   - Check daily P&L                                         │
│   - If P&L <= -$2,000:                                     │
│       execute_emergency_stop()                              │
│         1. Close ALL positions via Alpaca ✅ NEW           │
│            - alpaca_trader.close_all_positions()            │
│         2. Mark closed in database ✅                       │
│         3. Stop trading cycle ✅                            │
│         4. Send critical email alert ✅                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
                  ┌─────────┐
                  │ ALPACA  │
                  │   API   │
                  └─────────┘
                       │
                       ▼
                All positions closed with market orders
```

---

## ✅ Verification Steps

1. **Check Alpaca trader initialized**:
   ```bash
   docker-compose logs trading | grep "Alpaca trader initialized"
   ```

2. **Create test position**:
   ```bash
   curl -X POST http://localhost:5005/api/v1/positions?cycle_id=test \
     -d '{"symbol":"AAPL","side":"buy","quantity":1,...}'
   ```

3. **Verify in Alpaca dashboard**:
   - Log in to https://app.alpaca.markets
   - Check "Orders" tab
   - Should see bracket order with entry + stop + target

4. **Test emergency stop**:
   ```bash
   # Trigger manual stop
   curl -X POST http://localhost:5004/api/v1/emergency-stop \
     -d '{"cycle_id":"test","reason":"Manual test"}'
   ```

5. **Verify positions closed in Alpaca**:
   - Check Alpaca dashboard
   - All positions should be closed
   - Market orders should appear in history

---

## 📚 Code References

### **Trading Service Integration**:
- File: `services/trading/trading-service.py`
- Lines: 759-822 (Alpaca integration in create_position)
- Function: `create_position()`

### **Risk Manager Integration**:
- File: `services/risk-manager/risk-manager-service.py`
- Lines: 166-203 (Alpaca integration in emergency stop)
- Function: `execute_emergency_stop()`

### **Alpaca Trader Utility**:
- File: `services/common/alpaca_trader.py`
- Functions:
  - `submit_bracket_order()` - Submit entry + stop + target
  - `close_position()` - Close single position
  - `close_all_positions()` - Close all positions (emergency stop)
  - `get_account_info()` - Account details
  - `get_current_price()` - Real-time price

---

## 🎉 Summary

**Alpaca integration is COMPLETE and ready for testing!**

The system will now:
1. Submit **real bracket orders** to Alpaca when positions are created
2. Store Alpaca order IDs and status in database
3. Close **real positions** via Alpaca during emergency stop
4. Handle errors gracefully without failing operations
5. Support both paper and live trading modes

**Next Steps**:
1. Add alpaca columns to database (SQL above)
2. Configure Alpaca API keys in `.env`
3. Set `TRADING_MODE=paper`
4. Test with paper trading
5. Monitor for 1-2 days
6. Go live when ready (update `TRADING_MODE=live`)

---

**Implementation Complete**: 2025-11-18
**Trading Service**: v8.0.0
**Risk Manager**: v7.0.0
**Status**: ✅ FULLY INTEGRATED
