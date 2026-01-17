# Catalyst Alignment - Implementation Summary

**Name of Application:** Catalyst Trading System
**Name of File:** catalyst-alignment-implementation-summary.md
**Version:** 1.0.0
**Last Updated:** 2026-01-17
**Purpose:** Summary of dev_claude alignment with intl_claude architecture

---

## Overview

The **Catalyst Alignment** package aligns the US market trading agent (dev_claude) with the HKEX trading agent (intl_claude) architecture. This ensures consistent patterns, interfaces, and behavior across both market implementations.

---

## Package Contents

| File | Version | Purpose |
|------|---------|---------|
| `DEPLOYMENT.md` | 1.0.0 | Deployment guide and verification checklist |
| `alpaca.py` | 1.0.0 | Alpaca broker client for US markets |
| `tools.py` | 1.0.0 | 12 trading tool definitions for Claude AI |
| `tool_executor.py` | 1.0.0 | Routes tool calls to implementations |
| `database.py` | 1.0.0 | Database connection manager (trading + consciousness) |

---

## Architecture Alignment Status

| Component | intl_claude (HKEX) | dev_claude (US) | Status |
|-----------|-------------------|-----------------|--------|
| unified_agent.py | v3.0.0 | v3.0.0 | Aligned |
| tool_executor.py | v2.6.0 | v1.0.0 | Aligned |
| tools.py | v1.0.0 | v1.0.0 | Aligned |
| signals.py | v2.0.0 | v2.0.0 | Aligned |
| brokers/ | moomoo.py | alpaca.py | Aligned |
| data/database.py | v1.0.0 | v1.0.0 | Aligned |

---

## Key Components

### 1. Alpaca Broker Client (`alpaca.py`)

A complete Alpaca Markets integration providing:

- **Module-level singleton pattern** - `get_alpaca_client()` / `init_alpaca_client()`
- **Market data** - Real-time quotes, batch quotes, historical OHLCV
- **Account management** - Portfolio summary, positions, buying power
- **Order execution** - Market/limit orders with native bracket support
- **Sub-penny price rounding** - Prevents Alpaca rejection errors
- **Paper trading by default** - Configurable via `ALPACA_PAPER` env var

**Key Classes:**
```python
class AlpacaClient:
    def connect() -> bool
    def get_quote(symbol: str) -> Dict
    def get_portfolio() -> Dict
    def execute_trade(symbol, side, quantity, ...) -> OrderResult
    def close_position(symbol, reason) -> OrderResult

@dataclass
class OrderResult:
    order_id: str
    status: str
    filled_price: Optional[float]
    filled_quantity: int
```

### 2. Trading Tools (`tools.py`)

12 tools available to Claude AI during trading cycles:

**Market Data Tools:**
- `scan_market` - Find momentum candidates
- `get_quote` - Real-time price data
- `get_portfolio` - Account and position status
- `get_technicals` - RSI, MACD, moving averages
- `detect_patterns` - Chart pattern recognition
- `get_news` - Headlines and sentiment

**Risk & Execution Tools:**
- `check_risk` - Validate trade against risk rules
- `execute_trade` - Submit orders with bracket support
- `close_position` - Close single position
- `close_all_positions` - Emergency liquidation

**Communication Tools:**
- `send_alert` - Notify big_bro or Craig
- `log_decision` - Document trading decisions

### 3. Tool Executor (`tool_executor.py`)

Routes Claude's tool calls to actual implementations:

- **Broker integration** - Connects tools to AlpacaClient
- **Database logging** - Records trades and decisions
- **Risk validation** - Pre-trade checks against limits
- **Position monitoring** - Handled by separate systemd service (not inline)

**Key Features:**
- Order vs Position separation
- Filled status tracking
- Trade counting
- Error handling with graceful degradation

### 4. Database Client (`database.py`)

Dual database connectivity:

**Trading Database:**
- `get_open_positions()` - Active positions
- `record_trade()` - Order logging
- `log_decision()` - Decision audit trail
- `start_cycle()` / `end_cycle()` - Cycle tracking

**Consciousness Database:**
- `get_agent_state()` - Agent mode and status
- `update_agent_state()` - Track API spend, mode
- `get_pending_messages()` - Inter-agent messages
- `send_message()` - Alert routing
- `log_observation()` - Learning and observations

---

## Market-Specific Differences

| Aspect | intl_claude (HKEX) | dev_claude (US) |
|--------|-------------------|-----------------|
| Broker | Moomoo (OpenD) | Alpaca API |
| Timezone | HKT (UTC+8) | ET (UTC-5/4) |
| Market Hours | 9:30-12:00, 13:00-16:00 | 9:30-16:00 |
| Lunch Break | Yes (12:00-13:00) | No |
| Tick Sizes | HKEX 11-tier table | 2 decimal places |
| Currency | HKD | USD |
| Bracket Orders | Via conditional orders | Native support |

---

## Deployment Requirements

### Environment Variables

```bash
# Required
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
DATABASE_URL=postgresql://...
ANTHROPIC_API_KEY=your_key

# Optional
RESEARCH_DATABASE_URL=postgresql://...
```

### Dependencies

```bash
pip install alpaca-py asyncpg pyyaml anthropic pytz
```

### Cron Schedule (UTC)

```cron
# Pre-market scan (08:00 ET = 13:00 UTC)
0 13 * * 1-5 python3 unified_agent.py --mode scan

# Trading cycles (hourly 09:30-15:00 ET)
30 14 * * 1-5 python3 unified_agent.py --mode trade
0 15,16,17,18,19,20 * * 1-5 python3 unified_agent.py --mode trade

# End-of-day close (16:00 ET = 21:00 UTC)
0 21 * * 1-5 python3 unified_agent.py --mode close

# Off-hours heartbeat
0 0,3,6,9,12 * * 1-5 python3 unified_agent.py --mode heartbeat
```

---

## Verification Checklist

- [ ] Files deployed to `/root/catalyst-dev/`
- [ ] Environment variables set in `.env`
- [ ] Python dependencies installed
- [ ] Broker connection test passed
- [ ] Database connection test passed
- [ ] Heartbeat mode test passed
- [ ] Cron jobs installed
- [ ] Position monitor service running

---

## Testing Commands

```bash
# Test broker connection
python3 -c "
from brokers.alpaca import AlpacaClient
client = AlpacaClient(paper=True)
client.connect()
print(client.get_portfolio())
client.disconnect()
"

# Test database connection
python3 -c "
import asyncio
from data.database import init_database
async def test():
    db = await init_database()
    print('Connected:', db.is_connected())
asyncio.run(test())
"

# Test agent modes
python3 unified_agent.py --mode heartbeat --force
python3 unified_agent.py --mode scan --force
```

---

## Files Not Included (Keep Existing)

These files should remain from existing deployment:

- `.env` - Environment configuration
- `logs/` - Log directory
- `startup_monitor.py` - Pre-market reconciliation
- `position_monitor_service.py` - Systemd daemon
- `position-monitor-us.service` - Systemd unit file
- `unified_agent.py` - Main agent (already deployed)
- `signals.py` - Exit signal detection

---

## Summary

This alignment package ensures dev_claude (US markets) follows the same architectural patterns as intl_claude (HKEX markets), enabling:

1. **Consistent interfaces** - Same tool definitions and executor patterns
2. **Shared consciousness framework** - Both agents use the same database schema
3. **Market-specific isolation** - Broker implementations differ while interfaces match
4. **Simplified maintenance** - Changes to core logic apply to both markets

---

**Created:** 2026-01-17
**Author:** Claude Code
**Status:** Ready for deployment
