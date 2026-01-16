# Trading Concepts: Bracket Orders & Time-In-Force

**Name of Application:** Catalyst Trading System  
**Name of file:** trading-concepts-bracket-orders.md  
**Version:** 1.0.0  
**Last Updated:** 2026-01-01  
**Purpose:** Educational reference for bracket order mechanics and GTC fix

---

## 1. What is a Bracket Order?

A **bracket order** bundles three orders together as a single trade package:

```
┌─────────────────────────────────────────────────────────────────┐
│                      BRACKET ORDER                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. ENTRY ORDER          "Buy AAPL at $150"                    │
│         │                                                        │
│         ▼ (when filled, creates position + activates legs)       │
│   ┌─────┴─────┐                                                  │
│   │           │                                                  │
│   ▼           ▼                                                  │
│   2. STOP-LOSS        3. TAKE-PROFIT                            │
│   "Sell at $145"      "Sell at $160"                            │
│   (protection)        (profit target)                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The Three Components

| Order | Purpose | Trigger | Example |
|-------|---------|---------|---------|
| **Entry** | Get into position | Immediate (limit or market) | Buy 200 AAPL @ $150 |
| **Stop-Loss** | Limit downside risk | Price falls to stop price | Sell @ $145 = -$1,000 loss |
| **Take-Profit** | Lock in gains | Price rises to target | Sell @ $160 = +$2,000 profit |

### Why Use Bracket Orders?

1. **Defined Risk** - You know your maximum loss before entering
2. **Automated Exits** - No manual monitoring required
3. **Emotional Discipline** - Removes temptation to "hold and hope"
4. **Autonomous Trading** - Essential for AI-driven systems

---

## 2. OCO: One-Cancels-Other

The stop-loss and take-profit legs are linked as **OCO** (One-Cancels-Other):

```
Scenario A: Price rises to $160 (take-profit hit)
    │
    ├──▶ Take-Profit order FILLS → Position closed with profit
    │
    └──▶ Stop-Loss order AUTO-CANCELLED (no longer needed)


Scenario B: Price falls to $145 (stop-loss hit)
    │
    ├──▶ Stop-Loss order FILLS → Position closed with limited loss
    │
    └──▶ Take-Profit order AUTO-CANCELLED (no longer needed)
```

**Why OCO matters:** Without it, you could accidentally sell the same shares twice - once at stop-loss AND once at take-profit.

---

## 3. Time-In-Force Explained

**Time-In-Force (TIF)** tells the broker how long to keep an order active:

| Value | Name | Behavior |
|-------|------|----------|
| `DAY` | Day Order | Expires at 4:00 PM ET market close |
| `GTC` | Good Till Canceled | Stays active until filled or manually canceled |
| `IOC` | Immediate or Cancel | Fill immediately or cancel (partial fills OK) |
| `FOK` | Fill or Kill | Fill entirely immediately or cancel completely |

### DAY vs GTC for Bracket Orders

| Aspect | DAY | GTC |
|--------|-----|-----|
| **Duration** | Single trading day | Weeks/months |
| **After market close** | Canceled automatically | Persists |
| **Use case** | Day trading (close same day) | Swing trading, position trading |
| **Risk** | Position left unprotected overnight | None (protection persists) |

---

## 4. The Critical Bug (Catalyst v2.0.0)

### What Went Wrong

```python
# OLD CODE - v2.0.0
request = LimitOrderRequest(
    symbol=symbol,
    qty=quantity,
    side=order_side,
    time_in_force=TimeInForce.DAY,  # ❌ PROBLEM
    order_class=OrderClass.BRACKET,
    stop_loss=stop_loss_req,
    take_profit=take_profit_req
)
```

### Daily Timeline (Broken)

```
09:30 AM  → Buy 200 IREN @ $39.41 (entry fills)
09:30 AM  → Stop-loss @ $37.44 created (active)
09:30 AM  → Take-profit @ $41.38 created (active)
    ...
04:00 PM  → Market closes
04:00 PM  → Stop-loss EXPIRES ❌ (canceled by Alpaca)
04:00 PM  → Take-profit EXPIRES ❌ (canceled by Alpaca)

Next day:
09:30 AM  → You still own 200 IREN
           → But NO protection orders exist!
           → Stock could drop to $0 and nothing would sell
```

### The Impact

- **36 open positions** worth **$125,738** with no protection
- **Zero natural exits** in entire trading history
- All 141 closed positions were from manual cleanup scripts
- Every bracket order expired daily, leaving positions vulnerable

---

## 5. The Fix (Catalyst v2.1.0)

### Code Change

```python
# NEW CODE - v2.1.0
request = LimitOrderRequest(
    symbol=symbol,
    qty=quantity,
    side=order_side,
    time_in_force=TimeInForce.GTC,  # ✅ FIXED
    order_class=OrderClass.BRACKET,
    stop_loss=stop_loss_req,
    take_profit=take_profit_req
)
```

### Daily Timeline (Fixed)

```
09:30 AM  → Buy 200 IREN @ $39.41 (entry fills)
09:30 AM  → Stop-loss @ $37.44 created (GTC - persists)
09:30 AM  → Take-profit @ $41.38 created (GTC - persists)
    ...
04:00 PM  → Market closes
           → Stop-loss STILL ACTIVE ✅
           → Take-profit STILL ACTIVE ✅

Day 2, Day 3, Day 4...
           → Protection orders remain active
           → When price hits target → Auto-exit
           → Position manages itself
```

---

## 6. Visual Comparison

```
With DAY (broken):
═══════════════════════════════════════════════════════════════════
Day 1     │ Day 2     │ Day 3     │ Day 4
──────────┼───────────┼───────────┼───────────
Entry ✓   │           │           │
SL active │ SL gone!  │ SL gone!  │ SL gone!  ← UNPROTECTED
TP active │ TP gone!  │ TP gone!  │ TP gone!  ← NO EXIT
──────────┴───────────┴───────────┴───────────
                    Stock drops 50%... nothing happens


With GTC (fixed):
═══════════════════════════════════════════════════════════════════
Day 1     │ Day 2     │ Day 3     │ Day 4
──────────┼───────────┼───────────┼───────────
Entry ✓   │           │           │
SL active │ SL active │ SL active │ SL FILLS! ← Loss limited
TP active │ TP active │ TP active │ TP cancel ← OCO
──────────┴───────────┴───────────┴───────────
                    Stock drops → Stop-loss triggers → Saves capital
```

---

## 7. Complete Order Lifecycle

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
                       │ (GTC active) │    protection         │
                       └──────────────┘                       │
                                                              │
                       ┌──────────────┐                       │
                       │ Take Profit  │◀──────────────────────┘
                       │ (GTC active) │    protection
                       └──────────────┘
                              │
                              │ Price hits target
                              ▼
                       ┌──────────────┐                ┌──────────────┐
                       │ Take Profit  │───────────────▶│   Position   │
                       │ status:filled│    closes      │status: closed│
                       └──────────────┘                └──────────────┘
                              │
                              │ OCO cancels stop-loss
                              ▼
                       ┌──────────────┐
                       │  Stop Loss   │
                       │status:cancel │
                       └──────────────┘

FINAL STATE:
  Position: CLOSED with realized P&L
  Orders:
    - Entry order: FILLED
    - Stop-loss: CANCELLED (OCO)
    - Take-profit: FILLED
```

---

## 8. Ross Cameron Methodology Alignment

This implementation aligns with Ross Cameron's momentum trading principles:

| Principle | Implementation |
|-----------|----------------|
| **Defined Risk** | Stop-loss set before entry |
| **Predetermined Targets** | Take-profit calculated from R:R ratio |
| **Trade Management** | Bracket orders handle exits automatically |
| **No Emotional Decisions** | AI doesn't "hold and hope" |

### Risk-Reward Calculation

```
Entry:       $150.00
Stop-Loss:   $145.00  (risk = $5.00 per share)
Take-Profit: $160.00  (reward = $10.00 per share)

R:R Ratio = Reward / Risk = $10 / $5 = 2:1

With 200 shares:
  Max Loss:   200 × $5  = $1,000
  Max Profit: 200 × $10 = $2,000
```

---

## 9. Key Takeaways

1. **Bracket orders = Entry + Stop-Loss + Take-Profit** bundled together
2. **OCO** ensures only one exit leg fills (prevents double-selling)
3. **GTC is essential** for positions held overnight or longer
4. **DAY orders expire** at market close - dangerous for swing trades
5. **Autonomous trading requires GTC** - AI can't manually replace expired orders

---

## 10. Verification Query

After the fix, verify bracket orders persist with:

```sql
-- Check orders table for GTC bracket legs
SELECT 
    o.order_id,
    o.symbol,
    o.order_type,
    o.time_in_force,
    o.status,
    o.created_at
FROM orders o
WHERE o.order_type IN ('stop', 'limit')
  AND o.parent_order_id IS NOT NULL
ORDER BY o.created_at DESC
LIMIT 20;
```

Expected: `time_in_force = 'gtc'` for all stop-loss and take-profit orders.

---

*Document created: 2026-01-01*  
*Catalyst Trading System - Educational Reference*
