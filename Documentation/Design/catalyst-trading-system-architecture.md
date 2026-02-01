# Catalyst Trading System Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** catalyst-trading-system-architecture.md  
**Version:** 1.0.0  
**Last Updated:** 2026-02-01  
**Purpose:** Architecture specification for the pure trading system  
**Scope:** Trading execution only - no consciousness framework  
**Release Status:** PUBLIC - Community self-hosting enabled

---

## REVISION HISTORY

- v1.0.0 (2026-02-01) - Initial separation from unified architecture
  - Pure trading system documentation
  - Removed all consciousness references
  - Added agent_logs table for observability
  - Designed for community release

---

## Part 1: Overview

### 1.1 Mission

> *"Enable the poor through accessible algorithmic trading"*

The Catalyst Trading System is designed to be self-hosted by anyone, providing sophisticated algorithmic trading capabilities that are typically only available to wealthy institutions.

### 1.2 Design Principles

| Principle | Description |
|-----------|-------------|
| **Pure Trading** | No external dependencies beyond broker and database |
| **Single Process** | One Python agent, not microservices |
| **AI-Powered** | Claude API for dynamic decisions |
| **Observable** | All activity logged to database |
| **Configurable** | YAML-based configuration |
| **Broker Agnostic** | Abstraction layer for multiple brokers |

### 1.3 What This System Does

- Scans markets for trading opportunities
- Detects technical patterns
- Manages risk and position sizing
- Executes trades via broker API
- Monitors open positions
- Logs all decisions and activity

### 1.4 What This System Does NOT Do

- No consciousness/inter-agent communication
- No email alerts (use database logs)
- No learning persistence (stateless between runs)
- No cross-system messaging

---

## Part 2: System Architecture

### 2.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CATALYST TRADING SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        UNIFIED AGENT                                 │  │
│   │                      (unified_agent.py)                              │  │
│   │                                                                      │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│   │   │   CLAUDE    │  │    TOOL     │  │  DATABASE   │                │  │
│   │   │     API     │  │  EXECUTOR   │  │   LOGGER    │                │  │
│   │   │             │  │             │  │             │                │  │
│   │   │  Decisions  │  │  Routing    │  │  All logs   │                │  │
│   │   │  Analysis   │  │  Execution  │  │  to DB      │                │  │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │  │
│   │          │                │                │                        │  │
│   └──────────┼────────────────┼────────────────┼────────────────────────┘  │
│              │                │                │                            │
│              ▼                ▼                ▼                            │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         TOOL LAYER                                   │  │
│   │                                                                      │  │
│   │  scan_market │ get_quote │ get_technicals │ detect_patterns         │  │
│   │  get_news │ get_portfolio │ check_risk │ execute_trade              │  │
│   │  close_position │ close_all │ log_decision                          │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│              │                │                │                            │
│              ▼                ▼                ▼                            │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│   │  BROKER CLIENT   │  │   MARKET DATA    │  │    DATABASE      │        │
│   │                  │  │                  │  │                  │        │
│   │  • Moomoo        │  │  • Quotes        │  │  • Positions     │        │
│   │  • Alpaca        │  │  • Technicals    │  │  • Orders        │        │
│   │  • (Others)      │  │  • Patterns      │  │  • Decisions     │        │
│   │                  │  │  • News          │  │  • Logs          │        │
│   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        │
│            │                     │                     │                   │
└────────────┼─────────────────────┼─────────────────────┼───────────────────┘
             │                     │                     │
             ▼                     ▼                     ▼
      ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
      │   BROKER     │     │   MARKET     │     │  POSTGRESQL  │
      │   (Moomoo/   │     │   DATA       │     │              │
      │    Alpaca)   │     │   FEED       │     │ catalyst_intl│
      └──────────────┘     └──────────────┘     └──────────────┘
```

### 2.2 File Structure

```
catalyst-trading-system/
├── unified_agent.py              # Main agent entry point
├── tool_executor.py              # Routes tool calls to implementations
├── tools.py                      # Tool schema definitions
├── safety.py                     # Risk validation
├── signals.py                    # Exit signal detection
├── db_logger.py                  # Database logging handler (NEW)
│
├── position_monitor.py           # Trade-triggered position monitoring
├── position_monitor_service.py   # Systemd daemon for monitoring
├── startup_monitor.py            # Pre-market reconciliation
│
├── brokers/
│   ├── __init__.py
│   ├── base.py                   # Broker interface (abstract)
│   ├── moomoo.py                 # Moomoo/HKEX implementation
│   └── alpaca.py                 # Alpaca/US implementation
│
├── data/
│   ├── __init__.py
│   ├── market.py                 # Market data fetching
│   ├── patterns.py               # Pattern detection
│   └── news.py                   # News/sentiment data
│
├── config/
│   ├── trading_config.yaml       # Trading parameters
│   └── .env.example              # Environment template
│
├── sql/
│   └── schema-catalyst-trading.sql  # Database schema
│
├── logs/                         # Local log files (backup)
└── venv/                         # Python virtual environment
```

---

## Part 3: Database Schema

### 3.1 Overview

All trading data lives in a single PostgreSQL database (e.g., `catalyst_intl` or `catalyst_dev`).

### 3.2 Core Tables

| Table | Purpose |
|-------|---------|
| `securities` | Stock registry with exchange info |
| `positions` | Open and closed positions |
| `orders` | Order history and status |
| `decisions` | AI decision audit trail |
| `scan_results` | Scanner output |
| `trading_cycles` | Cycle execution logs |
| `patterns` | Detected technical patterns |
| `agent_logs` | **All runtime logs (NEW)** |
| `service_health` | Service heartbeat status |
| `position_monitor_status` | Real-time position tracking |

### 3.3 Key Design Principles

1. **Orders ≠ Positions** - Separate tables, clear relationship
2. **Audit Everything** - Every decision logged with reasoning
3. **Observability** - `agent_logs` captures all runtime activity
4. **Idempotency** - Safe to re-run operations

---

## Part 4: Component Specifications

### 4.1 Unified Agent (`unified_agent.py`)

The main entry point that orchestrates trading cycles.

**Modes:**
| Mode | Purpose |
|------|---------|
| `scan` | Pre-market candidate search |
| `trade` | Active trading during market hours |
| `close` | End-of-day position review |
| `heartbeat` | Off-hours health check |

**Responsibilities:**
- Load configuration
- Initialize broker connection
- Initialize database connection
- Set up logging (file + database)
- Run Claude API trading loop
- Execute tool calls
- Handle errors gracefully

### 4.2 Tool Executor (`tool_executor.py`)

Routes Claude's tool calls to actual implementations.

**Tools Available:**
| Tool | Purpose |
|------|---------|
| `scan_market` | Find trading candidates |
| `get_quote` | Current price/volume |
| `get_technicals` | RSI, MACD, VWAP, etc. |
| `detect_patterns` | Chart pattern recognition |
| `get_news` | News and sentiment |
| `get_portfolio` | Current positions |
| `check_risk` | Validate trade against limits |
| `execute_trade` | Place order with broker |
| `close_position` | Exit a position |
| `close_all` | Emergency close all |
| `log_decision` | Record decision to DB |

### 4.3 Database Logger (`db_logger.py`)

Custom Python logging handler that writes to `agent_logs` table.

**Features:**
- Non-blocking async writes
- Structured context (symbol, tool, cycle_id)
- Graceful failure (won't break trading)
- All log levels captured

### 4.4 Position Monitor Service (`position_monitor_service.py`)

Systemd daemon that monitors open positions.

**Features:**
- Runs continuously during market hours
- Detects exit signals (stop loss, take profit, pattern failure)
- Uses rules-based logic (free) + Haiku for uncertainty (~$0.05)
- Updates `position_monitor_status` table
- Writes to `agent_logs`

### 4.5 Broker Clients (`brokers/`)

Abstraction layer for broker-specific implementations.

**Interface:**
```python
class BrokerClient(ABC):
    async def connect(self)
    async def disconnect(self)
    async def get_quote(self, symbol: str) -> Quote
    async def get_positions(self) -> List[Position]
    async def place_order(self, order: Order) -> OrderResult
    async def cancel_order(self, order_id: str) -> bool
```

---

## Part 5: Configuration

### 5.1 Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:port/catalyst_intl?sslmode=require
ANTHROPIC_API_KEY=sk-ant-xxx

# Broker (Moomoo example)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111

# Broker (Alpaca example)
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Agent
AGENT_ID=intl_claude
LOG_LEVEL=INFO
```

### 5.2 Trading Configuration (`trading_config.yaml`)

```yaml
# Agent Identity
agent:
  id: intl_claude
  name: "HKEX Trading Agent"

# Market Configuration
market:
  exchange: HKEX
  timezone: Asia/Hong_Kong
  currency: HKD
  sessions:
    morning:
      open: "09:30"
      close: "12:00"
    afternoon:
      open: "13:00"
      close: "16:00"
  default_lot_size: 100

# Trading Parameters
trading:
  max_positions: 15
  max_position_value: 10000
  min_position_value: 2000
  daily_loss_limit: 16000
  position_stop_loss_pct: 0.03
  trailing_stop_pct: 0.03
  default_order_type: limit

# AI Configuration
ai:
  model: claude-sonnet-4-20250514
  daily_budget_usd: 5.00

# Signal Thresholds
signals:
  stop_loss_strong: -0.03
  stop_loss_moderate: -0.02
  take_profit_strong: 0.08
  take_profit_moderate: 0.05
  rsi_overbought: 75
  rsi_oversold: 30
```

---

## Part 6: Cron Schedule

### 6.1 HKEX Schedule (Example)

```cron
# Pre-market scan
0 1 * * 1-5 cd /root/catalyst && ./run.sh scan

# Trading cycles (every 30 min during market hours)
30 1 * * 1-5 cd /root/catalyst && ./run.sh trade
0,30 2-3 * * 1-5 cd /root/catalyst && ./run.sh trade
0,30 5-7 * * 1-5 cd /root/catalyst && ./run.sh trade

# Market close
0 8 * * 1-5 cd /root/catalyst && ./run.sh close

# Off-hours heartbeat
0 12,18 * * 1-5 cd /root/catalyst && ./run.sh heartbeat
```

### 6.2 Position Monitor Service

```bash
# Runs as systemd service, not cron
systemctl enable position-monitor
systemctl start position-monitor
```

---

## Part 7: Logging & Observability

### 7.1 Log Destinations

| Destination | Purpose | Retention |
|-------------|---------|-----------|
| `agent_logs` table | Primary - queryable | 30 days |
| `/logs/*.log` files | Backup - local debug | 7 days |

### 7.2 Log Levels

| Level | When Used | Example |
|-------|-----------|---------|
| ERROR | Failures requiring attention | Order rejected, API error |
| WARNING | Unusual but handled | Rate limit hit, data mismatch |
| INFO | Normal operations | Trade executed, cycle started |
| DEBUG | Detailed tracing | Tool calls, API responses |

### 7.3 Useful Queries

```sql
-- Recent errors
SELECT * FROM agent_logs 
WHERE level = 'ERROR' 
ORDER BY timestamp DESC LIMIT 20;

-- Activity for specific symbol
SELECT * FROM agent_logs 
WHERE context->>'symbol' = '0700' 
ORDER BY timestamp DESC;

-- Error rate by hour
SELECT 
    date_trunc('hour', timestamp) as hour,
    COUNT(*) as error_count
FROM agent_logs 
WHERE level = 'ERROR' 
GROUP BY hour 
ORDER BY hour DESC;
```

---

## Part 8: Deployment

### 8.1 Requirements

| Component | Specification |
|-----------|---------------|
| Droplet | 1-2GB RAM, 1 vCPU |
| Python | 3.10+ |
| PostgreSQL | 13+ |
| Broker Gateway | Moomoo OpenD / Alpaca API |

### 8.2 Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/your-repo/catalyst-trading-system.git
cd catalyst-trading-system

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp config/.env.example .env
# Edit .env with your credentials

# 5. Initialize database
psql $DATABASE_URL -f sql/schema-catalyst-trading.sql

# 6. Test connection
python3 unified_agent.py --mode heartbeat

# 7. Install cron schedule
cp config/cron.d /etc/cron.d/catalyst

# 8. Install position monitor service
cp config/position-monitor.service /etc/systemd/system/
systemctl enable position-monitor
systemctl start position-monitor
```

---

## Part 9: Security

### 9.1 Credentials

| Credential | Storage |
|------------|---------|
| Database URL | `.env` file (chmod 600) |
| API Keys | `.env` file (chmod 600) |
| Broker credentials | `.env` file (chmod 600) |

### 9.2 Network

| Connection | Security |
|------------|----------|
| PostgreSQL | SSL required |
| Broker API | TLS encrypted |
| Claude API | HTTPS |

---

## Part 10: Troubleshooting

### 10.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "MoomooClient not initialized" | OpenD not running | `systemctl start opend` |
| "Rate limit exceeded" | Too many API calls | Use batch APIs, add delays |
| "Order rejected" | Price/quantity issue | Check sub-penny rounding |
| Position sync mismatch | DB out of sync with broker | Run startup_monitor.py |

### 10.2 Health Checks

```bash
# Check agent can connect
python3 unified_agent.py --mode heartbeat

# Check database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM positions;"

# Check position monitor
systemctl status position-monitor

# Check recent logs
psql $DATABASE_URL -c "SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT 10;"
```

---

**END OF CATALYST TRADING SYSTEM ARCHITECTURE**

*Version 1.0.0 - February 2026*
*Designed for community self-hosting*
*"Enable the poor through accessible algorithmic trading"*
