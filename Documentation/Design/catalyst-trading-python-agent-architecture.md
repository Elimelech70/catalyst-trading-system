# Catalyst Trading System - Python Agent Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** catalyst-trading-python-agent-architecture.md  
**Version:** 2.0.0  
**Last Updated:** 2026-02-01  
**Purpose:** Architecture specification for the Python-based trading agent  
**Scope:** Production trading system using Python + Claude API  
**Deployment:** International Droplet (intl_claude - HKEX)  
**Release Status:** PUBLIC - Community self-hosting enabled

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v2.0.0 | 2026-02-01 | Craig + Claude | Separated from unified architecture |
| | | | - Distinct from Claude Code agent approach |
| | | | - Production-proven architecture |
| | | | - ~1,200 lines Python codebase |
| v1.0.0 | 2026-02-01 | Craig + Claude | Initial separation |

---

## TABLE OF CONTENTS

1. [Overview](#part-1-overview)
2. [Architecture Comparison](#part-2-architecture-comparison)
3. [System Architecture](#part-3-system-architecture)
4. [Component Specifications](#part-4-component-specifications)
5. [Tool Layer](#part-5-tool-layer)
6. [Configuration](#part-6-configuration)
7. [Cron Schedule](#part-7-cron-schedule)
8. [Deployment](#part-8-deployment)
9. [Troubleshooting](#part-9-troubleshooting)

---

## PART 1: OVERVIEW

### 1.1 What is the Python Agent?

The Python Agent is Catalyst's **production-proven** trading architecture:

- ~1,200 lines of Python code
- Claude API for AI decision-making
- Full programmatic control
- Runs autonomously via cron
- Currently trading HKEX via Moomoo

### 1.2 Mission

> *"Enable the poor through accessible algorithmic trading"*

### 1.3 Design Principles

| Principle | Description |
|-----------|-------------|
| **Python Control** | Full programmatic control over execution |
| **API-First** | Claude API for decisions, Python for actions |
| **Single Process** | One unified agent, not microservices |
| **Observable** | All activity logged to `agent_logs` table |
| **Production-Proven** | Running live on HKEX market |
| **Self-Hostable** | ~$50/month infrastructure |

### 1.4 Current Deployment

| Aspect | Value |
|--------|-------|
| Agent | intl_claude |
| Market | HKEX (Hong Kong) |
| Broker | Moomoo/OpenD |
| Droplet | International (137.184.244.45) |
| Database | catalyst_intl |
| Status | ✅ Production |

---

## PART 2: ARCHITECTURE COMPARISON

### 2.1 Python Agent vs Claude Code Agent

| Aspect | Python Agent (This Doc) | Claude Code Agent |
|--------|------------------------|-------------------|
| **Status** | ✅ Production | 🧪 Experimental |
| **Deployment** | intl_claude (HKEX) | dev_claude (US) |
| **Execution** | Python + Claude API | Claude Code + Bash |
| **Control** | Full programmatic | AI autonomous |
| **Codebase** | ~1,200 lines Python | ~50 lines CLAUDE.md |
| **Tool Calls** | Python functions | Bash scripts |
| **Error Handling** | Try/except in code | AI self-correction |
| **Complexity** | Higher (more control) | Lower (more trust) |
| **Proven** | Yes (live trading) | Not yet |

### 2.2 When to Use Which

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE SELECTION GUIDE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   USE PYTHON AGENT WHEN:              USE CLAUDE CODE AGENT WHEN:           │
│   ─────────────────────               ──────────────────────────            │
│   • Production trading                • Experimental/sandbox                │
│   • Need full control                 • Rapid prototyping                   │
│   • Complex error handling            • Trust AI judgment                   │
│   • Regulatory compliance             • Learning new patterns               │
│   • Real money at stake               • Testing new strategies              │
│   • Proven reliability needed         • Paper trading                       │
│                                                                             │
│   CURRENT DEPLOYMENT:                                                       │
│   ─────────────────────                                                     │
│   Python Agent → intl_claude (HKEX) → Real Money                           │
│   Claude Code  → dev_claude (US)    → Paper Trading                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 3: SYSTEM ARCHITECTURE

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PYTHON AGENT ARCHITECTURE                                │
│                    (Production - intl_claude)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        UNIFIED AGENT                                 │  │
│   │                      (unified_agent.py)                              │  │
│   │                        ~500 lines                                    │  │
│   │                                                                      │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│   │   │   CLAUDE    │  │    TOOL     │  │  DATABASE   │                │  │
│   │   │     API     │  │  EXECUTOR   │  │   CLIENT    │                │  │
│   │   │             │  │             │  │             │                │  │
│   │   │  Sonnet 4   │  │  Routes     │  │  asyncpg    │                │  │
│   │   │  Decisions  │  │  tool calls │  │  postgres   │                │  │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │  │
│   │          │                │                │                        │  │
│   └──────────┼────────────────┼────────────────┼────────────────────────┘  │
│              │                │                │                            │
│              ▼                ▼                ▼                            │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         TOOL LAYER                                   │  │
│   │                    (tool_executor.py ~450 lines)                     │  │
│   │                                                                      │  │
│   │  scan_market │ get_quote │ get_technicals │ detect_patterns         │  │
│   │  get_news │ get_portfolio │ check_risk │ execute_trade              │  │
│   │  close_position │ close_all │ log_decision                          │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│              │                │                │                            │
│              ▼                ▼                ▼                            │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│   │  BROKER CLIENT   │  │   DATA MODULES   │  │    DATABASE      │        │
│   │  (brokers/)      │  │   (data/)        │  │                  │        │
│   │                  │  │                  │  │                  │        │
│   │  moomoo.py       │  │  market.py       │  │  positions       │        │
│   │  ~300 lines      │  │  patterns.py     │  │  orders          │        │
│   │                  │  │  news.py         │  │  decisions       │        │
│   │                  │  │  database.py     │  │  agent_logs      │        │
│   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        │
│            │                     │                     │                   │
└────────────┼─────────────────────┼─────────────────────┼───────────────────┘
             │                     │                     │
             ▼                     ▼                     ▼
      ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
      │   MOOMOO     │     │   MARKET     │     │  POSTGRESQL  │
      │   OpenD      │     │   DATA       │     │              │
      │   Gateway    │     │   (via API)  │     │ catalyst_intl│
      └──────────────┘     └──────────────┘     └──────────────┘
```

### 3.2 File Structure

```
/root/catalyst-international/
├── unified_agent.py              # Main entry point (~500 lines)
├── tool_executor.py              # Tool routing (~450 lines)
├── tools.py                      # Tool schemas (~200 lines)
├── safety.py                     # Risk validation (~150 lines)
├── signals.py                    # Exit signal detection (~100 lines)
│
├── position_monitor.py           # Trade-triggered monitoring
├── position_monitor_service.py   # Systemd daemon
├── startup_monitor.py            # Pre-market reconciliation
│
├── brokers/
│   ├── __init__.py
│   ├── base.py                   # Broker interface
│   └── moomoo.py                 # Moomoo implementation (~300 lines)
│
├── data/
│   ├── __init__.py
│   ├── database.py               # Database operations (~200 lines)
│   ├── market.py                 # Market data fetching (~250 lines)
│   ├── patterns.py               # Pattern detection (~200 lines)
│   └── news.py                   # News/sentiment (~150 lines)
│
├── config/
│   ├── settings.yaml             # Trading parameters
│   ├── news_context.yaml         # News sentiment config
│   ├── exit_context.yaml         # Exit signal thresholds
│   └── .env                      # Credentials
│
├── sql/
│   └── schema-catalyst-trading.sql
│
├── logs/                         # Local log files
└── venv/                         # Python environment

TOTAL: ~1,200 lines of Python
```

### 3.3 Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PYTHON AGENT EXECUTION FLOW                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. CRON TRIGGERS                                                          │
│      └── python3 unified_agent.py --mode trade                             │
│                                                                             │
│   2. INITIALIZATION                                                         │
│      ├── Load config/settings.yaml                                         │
│      ├── Connect to PostgreSQL (catalyst_intl)                             │
│      ├── Connect to Moomoo OpenD                                           │
│      └── Initialize logging (file + database)                              │
│                                                                             │
│   3. CLAUDE API LOOP                                                        │
│      ┌────────────────────────────────────────────────────────────┐        │
│      │  while iterations < max_iterations:                         │        │
│      │      response = claude.messages.create(                     │        │
│      │          model="claude-sonnet-4-20250514",                  │        │
│      │          tools=TOOL_DEFINITIONS,                            │        │
│      │          messages=conversation                              │        │
│      │      )                                                      │        │
│      │                                                             │        │
│      │      for tool_call in response.tool_calls:                  │        │
│      │          result = tool_executor.execute(tool_call)          │        │
│      │          conversation.append(result)                        │        │
│      │                                                             │        │
│      │      if response.stop_reason == "end_turn":                 │        │
│      │          break                                              │        │
│      └────────────────────────────────────────────────────────────┘        │
│                                                                             │
│   4. TOOL EXECUTION                                                         │
│      ├── tool_executor routes to Python functions                          │
│      ├── Functions call broker/database directly                           │
│      └── Results returned to Claude for next decision                      │
│                                                                             │
│   5. CLEANUP                                                                │
│      ├── Log cycle summary to agent_logs                                   │
│      ├── Update trading_cycles table                                       │
│      └── Close connections                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 4: COMPONENT SPECIFICATIONS

### 4.1 Unified Agent (`unified_agent.py`)

The main entry point orchestrating trading cycles.

**Modes:**

| Mode | Purpose | When |
|------|---------|------|
| `scan` | Pre-market candidate search | Before market open |
| `trade` | Active trading | Market hours |
| `close` | EOD position review | Market close |
| `heartbeat` | Health check | Off-hours |

**Key Methods:**

```python
class UnifiedAgent:
    async def run(self, mode: str) -> None
    async def trading_loop(self) -> None
    async def process_tool_calls(self, response) -> List[dict]
    async def handle_error(self, error: Exception) -> None
```

### 4.2 Tool Executor (`tool_executor.py`)

Routes Claude's tool calls to Python implementations.

**Pattern:**
```python
async def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
    """Route tool call to appropriate handler"""
    handlers = {
        "scan_market": self._scan_market,
        "get_quote": self._get_quote,
        "execute_trade": self._execute_trade,
        # ... etc
    }
    return await handlers[tool_name](**tool_input)
```

### 4.3 Broker Client (`brokers/moomoo.py`)

Moomoo/OpenD integration for HKEX trading.

**Interface:**
```python
class MoomooClient:
    async def connect(self) -> None
    async def get_quote(self, symbol: str) -> Quote
    async def get_positions(self) -> List[Position]
    async def place_order(self, order: Order) -> OrderResult
    async def cancel_order(self, order_id: str) -> bool
    async def get_order_status(self, order_id: str) -> OrderStatus
```

### 4.4 Position Monitor Service

Systemd daemon for continuous position monitoring.

**Features:**
- Rules-based exit signal detection (free)
- Haiku AI for uncertain situations (~$0.05/call)
- Updates `position_monitor_status` table
- Writes to `agent_logs`

---

## PART 5: TOOL LAYER

### 5.1 Available Tools (11)

| Tool | Purpose | Implementation |
|------|---------|----------------|
| `scan_market` | Find trading candidates | `data/market.py` |
| `get_quote` | Current price/volume | `brokers/moomoo.py` |
| `get_technicals` | RSI, MACD, MAs, ATR | `data/market.py` |
| `detect_patterns` | Chart patterns | `data/patterns.py` |
| `get_news` | News and sentiment | `data/news.py` |
| `get_portfolio` | Current positions | `brokers/moomoo.py` |
| `check_risk` | Validate against limits | `safety.py` |
| `execute_trade` | Place order | `brokers/moomoo.py` |
| `close_position` | Exit position | `brokers/moomoo.py` |
| `close_all` | Emergency close | `brokers/moomoo.py` |
| `log_decision` | Record to DB | `data/database.py` |

### 5.2 Tool Schema Example

```python
TOOLS = [
    {
        "name": "execute_trade",
        "description": "Execute a trade order",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "quantity": {"type": "integer"},
                "order_type": {"type": "string", "enum": ["market", "limit"]},
                "limit_price": {"type": "number"}
            },
            "required": ["symbol", "side", "quantity", "order_type"]
        }
    }
]
```

---

## PART 6: CONFIGURATION

### 6.1 Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/catalyst_intl?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx

# Moomoo
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADE_PWD=xxx

# Agent
AGENT_ID=intl_claude
LOG_LEVEL=INFO
```

### 6.2 Trading Configuration (`settings.yaml`)

```yaml
agent:
  id: intl_claude
  name: "HKEX Trading Agent"

market:
  exchange: HKEX
  timezone: Asia/Hong_Kong
  currency: HKD
  sessions:
    morning: { open: "09:30", close: "12:00" }
    afternoon: { open: "13:00", close: "16:00" }
  default_lot_size: 100

trading:
  max_positions: 15
  max_position_value: 10000
  min_position_value: 2000
  daily_loss_limit: 16000
  position_stop_loss_pct: 0.03
  trailing_stop_pct: 0.03

ai:
  model: claude-sonnet-4-20250514
  daily_budget_usd: 5.00
  max_iterations: 35
```

---

## PART 7: CRON SCHEDULE

### 7.1 HKEX Trading Schedule

```cron
# ============================================================================
# INTL_CLAUDE - HKEX Market (Python Agent)
# Timezone: UTC (HKT = UTC+8)
# ============================================================================

CATALYST_DIR=/root/catalyst-international
VENV_PYTHON=/root/catalyst-international/venv/bin/python3

# Pre-market scan (09:00 HKT = 01:00 UTC)
0 1 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode scan

# Morning session (09:30-12:00 HKT)
30 1 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade
0 2-3 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade

# Lunch break
0 4 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode close

# Afternoon session (13:00-16:00 HKT)
0 5-7 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade

# EOD close (16:00 HKT = 08:00 UTC)
0 8 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode close

# Off-hours heartbeat
0 12,18 * * 1-5 root cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode heartbeat
```

### 7.2 Position Monitor Service

```bash
systemctl enable position-monitor
systemctl start position-monitor
systemctl status position-monitor
```

---

## PART 8: DEPLOYMENT

### 8.1 Requirements

| Component | Specification |
|-----------|---------------|
| Droplet | 2GB RAM, 1 vCPU |
| OS | Ubuntu 22.04+ |
| Python | 3.10+ |
| PostgreSQL | 13+ (managed) |
| Moomoo OpenD | Latest version |

### 8.2 Installation

```bash
# 1. Clone repository
git clone https://github.com/your-repo/catalyst-trading-system.git
cd catalyst-trading-system

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp config/.env.example .env
vim .env  # Add credentials

# 5. Initialize database
psql $DATABASE_URL -f sql/schema-catalyst-trading.sql

# 6. Start Moomoo OpenD
cd /opt/OpenD && ./OpenD &

# 7. Test
python3 unified_agent.py --mode heartbeat

# 8. Install cron
cp config/catalyst-cron /etc/cron.d/

# 9. Install position monitor
cp config/position-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable position-monitor
systemctl start position-monitor
```

---

## PART 9: TROUBLESHOOTING

### 9.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "MoomooClient not initialized" | OpenD not running | `systemctl start opend` |
| "Rate limit exceeded" | Too many API calls | Increase delays |
| "Order rejected" | Price/lot size | Check HKEX lot sizes |
| Position sync mismatch | DB out of sync | Run `startup_monitor.py` |

### 9.2 Health Checks

```bash
# Test agent
python3 unified_agent.py --mode heartbeat

# Check database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM positions WHERE status='open';"

# Check position monitor
systemctl status position-monitor

# Recent errors
psql $DATABASE_URL -c "SELECT * FROM agent_logs WHERE level='ERROR' ORDER BY timestamp DESC LIMIT 10;"
```

---

## APPENDIX: RELATED DOCUMENTS

| Document | Purpose |
|----------|---------|
| `catalyst-trading-claude-code-architecture.md` | Claude Code agent (experimental) |
| `consciousness-architecture.md` | Consciousness framework |
| `database-schema.md` | Database schema |

---

**END OF PYTHON AGENT ARCHITECTURE v2.0.0**

*Production-proven architecture for HKEX trading*  
*intl_claude - International Droplet*  
*Craig + The Claude Family - February 2026*
