# Catalyst Trading System - Functional Specification

**Name of Application:** Catalyst Trading System
**Name of file:** functional-specification.md
**Version:** 8.2.0
**Last Updated:** 2026-01-16
**Purpose:** Complete functional specifications for trading tools and patterns

---

## REVISION HISTORY

- **v8.2.0 (2026-01-16)** - Volume Ratio & Position Monitor Fixes
  - Fixed volume_ratio calculation in market.py get_quote() to match scan_market()
  - Fixed position monitor: now passes position_id instead of safety_validator
  - Fixed position monitor: runs in background thread to avoid event loop conflicts
  - Increased max_iterations from 20 to 35 in config/settings.yaml
  - Successful trades now execute consistently

- **v8.1.0 (2026-01-06)** - Pattern Detection & Tool Updates
  - Added patterns.py v1.1.0 new pattern types (near_breakout, momentum_continuation)
  - Documented tool_executor.py bug fixes
  - Updated moomoo.py portfolio response format
  - Added tiered entry criteria reference
  
- **v8.0.0 (2025-12-28)** - Consciousness Framework
  - Added consciousness tables
  - Database consolidation

---

## 1. Trading Tools

### 1.1 Tool Summary

| Tool | Purpose | Returns |
|------|---------|---------|
| `scan_market` | Find momentum candidates | List of candidates with volume/change |
| `get_quote` | Current price data | Bid/ask/last/volume |
| `get_technicals` | RSI, MACD, support/resistance | Technical indicators |
| `detect_patterns` | Chart pattern detection | Pattern with entry/stop/target |
| `get_news` | News and sentiment | Headlines with sentiment score |
| `check_risk` | Validate trade parameters | Approved/rejected with reason |
| `get_portfolio` | Current holdings | Cash, positions, P&L |
| `execute_trade` | Place order | Order result |
| `close_position` | Close specific position | Close result |
| `close_all` | Emergency close all | List of close results |
| `send_alert` | Send notification | Success/failure |
| `log_decision` | Record reasoning | Logged decision ID |

### 1.2 Tool Input/Output Specifications

#### scan_market
```python
Input:
  index: str = "ALL"          # HSI, HSCEI, ALL
  limit: int = 10             # Max candidates
  min_volume_ratio: float = 1.5

Output:
  candidates: List[{
    symbol: str,
    name: str,
    price: float,
    change_pct: float,
    volume_ratio: float,
    momentum_score: float
  }]
```

#### detect_patterns
```python
Input:
  symbol: str                 # Stock code

Output:
  patterns: List[{
    pattern_type: str,        # See Pattern Types below
    confidence: float,        # 0.0 - 1.0
    entry_price: float,
    stop_loss: float,
    target_price: float,
    risk_reward: float,
    description: str
  }]
```

#### execute_trade
```python
Input:
  symbol: str
  side: str                   # "buy" or "sell"
  quantity: int               # Must be multiple of 100 for HKEX
  order_type: str             # "market" or "limit"
  limit_price: float = None   # Required for limit orders
  stop_loss: float            # Agent-managed stop
  take_profit: float          # Agent-managed target
  reason: str                 # Audit trail

Output:
  status: str                 # "success", "failed", "error"
  order_id: str
  fill_price: float
  timestamp: str
```

---

## 2. Pattern Detection (v1.1.0)

### 2.1 Pattern Types

| Pattern | Detection Criteria | Confidence Range |
|---------|-------------------|------------------|
| `breakout` | Current > resistance, prev within 2% of resistance, volume >1.3x | 0.50 - 0.85 |
| `near_breakout` | Within 1% of resistance, volume >1.2x | 0.40 - 0.60 |
| `momentum_continuation` | >3% daily gain, volume >1.5x, 3-day trend >5% | 0.35 - 0.50 |
| `bull_flag` | Pole >5%, flag <50% of pole, retracement <50% | 0.50 - 0.90 |
| `bear_flag` | Inverse of bull_flag | 0.50 - 0.90 |
| `ascending_triangle` | Flat resistance (std <2%), 3+ higher lows | 0.60 - 0.90 |
| `descending_triangle` | Flat support (std <2%), 3+ lower highs | 0.60 - 0.90 |
| `cup_handle` | U-shape (12-35% depth), handle <50% of cup | 0.60 - 0.90 |
| `ABCD` | BC retracement 38-62% of AB, R:R >1.5 | 0.60 - 0.80 |
| `breakdown` | Current < support, prev within 2% of support, volume >1.3x | 0.50 - 0.85 |

### 2.2 Pattern Changes in v1.1.0

| Change | Old Behavior | New Behavior |
|--------|--------------|--------------|
| Breakout tolerance | `prev_close <= resistance` exact | `prev_close <= resistance * 1.02` (2% tolerance) |
| Volume requirement | 1.5x minimum | 1.3x minimum |
| New: near_breakout | N/A | Within 1% of resistance |
| New: momentum_continuation | N/A | >3% daily + high volume |

---

## 3. Entry Criteria (Tiered System)

### 3.1 Tier Definitions

**Tier 1 - Strong Setup (Trade Full Size)**
```yaml
Requirements (ALL):
  - volume_ratio: "> 2.0x"
  - RSI: "30 - 70"
  - pattern: "Clear with defined entry"
  - catalyst: "Positive (sentiment > 0.2)"
  - risk_reward: ">= 2:1"
```

**Tier 2 - Good Setup (Trade Full Size)**
```yaml
Requirements:
  - volume_ratio: "> 1.5x"
  - RSI: "30 - 75"
  - pattern_or_catalyst: "Either one, not both required"
  - risk_reward: ">= 1.5:1"
  - breakout_tolerance: "Within 1% counts"
```

**Tier 3 - Learning Trade (Trade Half Size)**
```yaml
Requirements:
  - volume_ratio: "> 1.3x"
  - RSI: "25 - 80"
  - momentum: "> 3% daily gain"
  - any_signal: "pattern forming, news mention, or sector strength"
  - risk_reward: ">= 1.5:1"
  - logging: "Mark as 'learning trade'"
```

### 3.2 When to PASS

Only skip a trade if:
- RSI > 80 (severely overbought) or < 20 (oversold crash)
- Volume is BELOW average
- `check_risk` returns `approved=false`
- Already at max positions (5)
- No clear stop loss level identifiable

---

## 4. Moomoo Client Specifications

### 4.1 Portfolio Response Format (v1.2.1)

```python
{
    "cash": float,              # Available cash in HKD
    "total_assets": float,      # Total portfolio value
    "equity": float,            # Alias for total_assets (compatibility)
    "market_value": float,      # Value of positions
    "positions": [              # List of position dicts
        {
            "symbol": str,
            "quantity": int,
            "avg_cost": float,
            "current_price": float,
            "unrealized_pnl": float
        }
    ],
    "position_count": int,      # Number of positions
    "unrealized_pnl": float,    # Total unrealized P&L
    "daily_pnl": float,         # Today's P&L
    "daily_pnl_pct": float,     # Today's P&L percentage
    "currency": str             # "HKD"
}
```

### 4.2 Quote Response Format (v2.1.1)

```python
{
    "symbol": str,
    "last": float,              # Mapped from last_price
    "bid": float,               # Mapped from bid_price
    "ask": float,               # Mapped from ask_price
    "high": float,              # Mapped from high_price
    "low": float,               # Mapped from low_price
    "open": float,              # Mapped from open_price
    "prev_close": float,
    "volume": int,
    "turnover": float,
    "change": float,            # Calculated if not provided
    "change_pct": float         # Calculated if not provided
}
```

### 4.3 OrderResult Dataclass

```python
@dataclass
class OrderResult:
    order_id: str
    status: str                 # "SUBMITTED", "FILLED", "FAILED", etc.
    symbol: str
    side: str
    quantity: int
    order_type: str
    filled_price: Optional[float]
    filled_quantity: int
    message: str
```

**Important**: OrderResult is a dataclass, not a dict. Use `.status` not `["status"]`.

---

## 5. Bug Fixes Reference (2026-01-06)

### 5.1 tool_executor.py Fixes

| Bug | Error Message | Fix Applied |
|-----|---------------|-------------|
| OrderResult access | `TypeError: 'OrderResult' object is not subscriptable` | Convert to dict or use `.status` |
| has_position method | `AttributeError: 'MoomooClient' has no attribute 'has_position'` | Query `get_positions()` and check list |
| AlertSender callable | `TypeError: 'AlertSender' object is not callable` | Check for `.send()` method before calling |
| Portfolio KeyError | `KeyError: 'daily_pnl_pct'` | Use `.get()` with default values |

### 5.2 Code Pattern for Position Check

```python
# WRONG (has_position doesn't exist):
if self.broker.has_position(symbol):
    ...

# CORRECT:
positions = self.broker.get_positions()
has_pos = any(p.symbol == symbol for p in positions)
if has_pos:
    ...
```

### 5.3 Code Pattern for AlertSender

```python
# WRONG (AlertSender is object, not function):
self.alert_callback("info", "Subject", "Message")

# CORRECT:
if hasattr(self.alert_callback, 'send'):
    self.alert_callback.send("info", "Subject", "Message")
elif callable(self.alert_callback):
    self.alert_callback("info", "Subject", "Message")
```

---

## 6. Environment Variables

### 6.1 Required Variables

```bash
# Trading Database
DATABASE_URL=postgresql://user:pass@host:port/catalyst_intl?sslmode=require

# Research Database (Consciousness)
RESEARCH_DATABASE_URL=postgresql://user:pass@host:port/catalyst_research?sslmode=require

# Moomoo OpenD
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADE_PWD=your_trade_password

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx
```

---

## 7. Related Documents

| Document | Purpose |
|----------|---------|
| `architecture-international.md` | System architecture |
| `database-schema.md` | Database schema |
| `CLAUDE.md` | Operational guidelines |

---

**END OF FUNCTIONAL SPECIFICATION v8.1.0**
