# Catalyst Trading System - Functional Specification

**Name of Application:** Catalyst Trading System  
**Name of file:** functional-specification.md  
**Version:** 8.0.0  
**Last Updated:** 2025-12-28  
**Purpose:** Complete functional specification including consciousness modules

---

## REVISION HISTORY

- **v8.0.0 (2025-12-28)** - Consciousness Framework Modules
  - Added consciousness.py module specification
  - Added database.py module specification
  - Added alerts.py module specification
  - Added doctor_claude.py module specification
  - Agent lifecycle documentation
  
- **v7.0.0 (2025-12-27)** - Doctor Claude, orders table
- **v6.0.0 (2025-12-14)** - MCP tools, service specifications

---

## 1. Overview

### 1.1 System Purpose

The Catalyst Trading System is an autonomous day trading platform implementing Ross Cameron's momentum methodology, enhanced with Claude AI agents that have persistent memory and learning capabilities.

### 1.2 Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Trading Services | Market execution | Docker containers |
| Consciousness Modules | AI agent capabilities | services/shared/common/ |
| Research Database | Persistent memory | catalyst_research |
| Doctor Claude | Health monitoring | Cron + shared module |

---

## 2. Consciousness Modules

### 2.1 consciousness.py

**Purpose:** Core consciousness framework for all Claude agents

**Location:** `services/shared/common/consciousness.py`

**Version:** 1.0.0

**Dependencies:** asyncpg, smtplib

#### 2.1.1 Classes

| Class | Purpose |
|-------|---------|
| `ClaudeConsciousness` | Main consciousness class |
| `AgentState` | Dataclass for agent state |
| `Message` | Dataclass for inter-agent messages |
| `Observation` | Dataclass for observations |
| `Learning` | Dataclass for learnings |
| `Question` | Dataclass for questions |

#### 2.1.2 Enums

| Enum | Values |
|------|--------|
| `AgentMode` | sleeping, awake, thinking, trading, researching, error |
| `MessageType` | message, signal, question, task, response, alert |
| `Priority` | low, normal, high, urgent |
| `Horizon` | h1, h2, h3, perpetual |

#### 2.1.3 ClaudeConsciousness Methods

**State Management:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | agent_id: str, pool: asyncpg.Pool | None | Initialize consciousness |
| `wake_up` | None | AgentState | Wake agent, update state |
| `sleep` | status_message: str = "Cycle complete" | None | Put agent to sleep |
| `update_status` | mode: str, message: str = None | None | Update agent status |
| `record_api_spend` | cost: float | None | Record API spending |
| `record_error` | error_message: str | None | Record error occurrence |
| `check_budget` | None | bool | Check if within budget |
| `get_budget_remaining` | None | float | Get remaining budget |

**Inter-Agent Messaging:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `send_message` | to_agent, subject, body, msg_type='message', priority='normal', data=None, requires_response=False, expires_in_hours=None | int | Send message to another agent |
| `check_messages` | limit: int = 10 | List[Message] | Check for pending messages |
| `mark_read` | message_id: int | None | Mark message as read |
| `mark_processed` | message_id: int | None | Mark message as processed |
| `reply_to_message` | original_message_id, body, data=None | int | Reply to a message |

**Observations:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `observe` | observation_type, subject, content, confidence=None, horizon=None, market=None, tags=None, expires_in_hours=None | int | Record an observation |
| `get_recent_observations` | observation_type=None, market=None, limit=20 | List[Observation] | Get recent observations |

**Learnings:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `learn` | category, learning, source=None, confidence=0.5, applies_to_markets=None | int | Record a learning |
| `validate_learning` | learning_id: int | None | Increase confidence |
| `contradict_learning` | learning_id: int | None | Decrease confidence |
| `get_learnings` | category=None, min_confidence=0.5, limit=20 | List[Learning] | Get learnings |

**Questions:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `ask_question` | question, horizon='h1', priority=5, category=None, hypothesis=None | int | Record a question |
| `get_open_questions` | limit: int = 10 | List[Question] | Get open questions |
| `update_question` | question_id, status=None, hypothesis=None, evidence_for=None, evidence_against=None, answer=None | None | Update question |

**Communication:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `email_craig` | subject, body, priority='normal' | bool | Send email to Craig |
| `get_sibling_status` | None | List[Dict] | Get status of siblings |
| `broadcast_to_siblings` | subject, body, msg_type='message', priority='normal' | List[int] | Message all siblings |

#### 2.1.4 Usage Example

```python
from consciousness import ClaudeConsciousness
import asyncpg

async def run_agent():
    pool = await asyncpg.create_pool(RESEARCH_DATABASE_URL)
    consciousness = ClaudeConsciousness('public_claude', pool)
    
    # Wake up
    state = await consciousness.wake_up()
    print(f"Budget: ${state.api_spend_today}/{state.daily_budget}")
    
    # Check messages
    messages = await consciousness.check_messages()
    for msg in messages:
        print(f"From {msg.from_agent}: {msg.subject}")
        await consciousness.mark_processed(msg.id)
    
    # Record observation
    await consciousness.observe(
        observation_type='market',
        subject='AAPL unusual volume',
        content='3x average volume in first 30 minutes',
        confidence=0.85,
        horizon='h1',
        market='US'
    )
    
    # Record learning
    await consciousness.learn(
        category='pattern',
        learning='Bull flags after gap ups have 68% success rate',
        source='backtested 200 samples',
        confidence=0.75
    )
    
    # Sleep
    await consciousness.sleep("Trading cycle complete")
    await pool.close()
```

---

### 2.2 database.py

**Purpose:** Unified database connection management

**Location:** `services/shared/common/database.py`

**Version:** 1.0.0

**Dependencies:** asyncpg

#### 2.2.1 Classes

| Class | Purpose |
|-------|---------|
| `DatabaseManager` | Manages trading and research database pools |

#### 2.2.2 DatabaseManager Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | trading_url, research_url, trading_pool_size=(2,10), research_pool_size=(1,5) | None | Initialize manager |
| `connect` | None | DatabaseManager | Create connection pools |
| `close` | None | None | Close all pools |
| `trading` | Property | asyncpg.Pool | Get trading pool |
| `research` | Property | asyncpg.Pool | Get research pool |
| `is_connected` | Property | bool | Check connection status |
| `trading_transaction` | Context manager | Connection | Transaction wrapper |
| `research_transaction` | Context manager | Connection | Transaction wrapper |
| `trading_fetch` | query, *args | List | Fetch from trading DB |
| `trading_fetchrow` | query, *args | Row | Fetch row from trading DB |
| `trading_fetchval` | query, *args | Value | Fetch value from trading DB |
| `trading_execute` | query, *args | str | Execute on trading DB |
| `research_fetch` | query, *args | List | Fetch from research DB |
| `research_fetchrow` | query, *args | Row | Fetch row from research DB |
| `research_fetchval` | query, *args | Value | Fetch value from research DB |
| `research_execute` | query, *args | str | Execute on research DB |
| `get_pool_stats` | None | Dict | Get pool statistics |

#### 2.2.3 Factory Functions

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `get_database_manager` | trading_url=None, research_url=None | DatabaseManager | Create from environment |
| `managed_database` | trading_url=None, research_url=None | Context manager | Auto-connect/close |

#### 2.2.4 Usage Example

```python
from database import get_database_manager, managed_database

# Option 1: Manual management
db = get_database_manager()
await db.connect()

positions = await db.trading_fetch("SELECT * FROM positions WHERE status = 'open'")
state = await db.research_fetchrow("SELECT * FROM claude_state WHERE agent_id = $1", 'public_claude')

await db.close()

# Option 2: Context manager
async with managed_database() as db:
    positions = await db.trading_fetch("SELECT * FROM positions")
```

---

### 2.3 alerts.py

**Purpose:** Email notification system

**Location:** `services/shared/common/alerts.py`

**Version:** 1.0.0

**Dependencies:** smtplib

#### 2.3.1 Classes

| Class | Purpose |
|-------|---------|
| `AlertManager` | Manages email alerts |

#### 2.3.2 Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SMTP_HOST` | SMTP server | smtp.gmail.com |
| `SMTP_PORT` | SMTP port | 587 |
| `SMTP_USER` | SMTP username | Required |
| `SMTP_PASSWORD` | SMTP password | Required |
| `ALERT_EMAIL` | Recipient email | Required |

#### 2.3.3 AlertManager Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | smtp_host=None, smtp_port=None, smtp_user=None, smtp_password=None, alert_email=None | None | Initialize manager |
| `is_configured` | Property | bool | Check if configured |
| `send_email` | subject, body, priority='normal', agent_id='system', html=False | bool | Send email |
| `send_trade_alert` | agent_id, action, symbol, quantity, price, reason, stop_loss=None, take_profit=None, position_value=None | bool | Trade notification |
| `send_position_closed_alert` | agent_id, symbol, quantity, entry_price, exit_price, pnl, pnl_pct, hold_time, exit_reason | bool | Position closed |
| `send_error_alert` | agent_id, error_type, error_message, context=None, stack_trace=None | bool | Error notification |
| `send_risk_alert` | agent_id, alert_type, current_value, limit_value, action_taken | bool | Risk alert |
| `send_daily_summary` | agent_id, date, trades, winning_trades, losing_trades, gross_pnl, commissions, net_pnl, win_rate, observations=None, learnings=None | bool | Daily summary |
| `send_startup_notification` | agent_id, mode, version, components | bool | Startup notification |
| `send_shutdown_notification` | agent_id, reason, runtime, trades_today, pnl_today | bool | Shutdown notification |

#### 2.3.4 Priority Prefixes

| Priority | Prefix |
|----------|--------|
| urgent | 🚨 URGENT: |
| high | ⚠️ |
| normal | (none) |
| low | 📝 |

#### 2.3.5 Usage Example

```python
from alerts import AlertManager, get_alert_manager

# Option 1: Create instance
alerts = AlertManager()
alerts.send_trade_alert(
    agent_id='public_claude',
    action='buy',
    symbol='AAPL',
    quantity=100,
    price=150.00,
    reason='Bull flag pattern detected'
)

# Option 2: Use singleton
alerts = get_alert_manager()
alerts.send_error_alert(
    agent_id='public_claude',
    error_type='broker_api',
    error_message='Order rejected: insufficient buying power'
)
```

---

### 2.4 doctor_claude.py

**Purpose:** Health monitoring for all agents and systems

**Location:** `services/shared/common/doctor_claude.py`

**Version:** 1.0.0

**Dependencies:** consciousness, alerts, asyncpg

#### 2.4.1 Classes

| Class | Purpose |
|-------|---------|
| `DoctorClaude` | Health monitoring system |
| `HealthCheckResult` | Dataclass for check results |

#### 2.4.2 DoctorClaude Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | research_pool, trading_pool=None | None | Initialize doctor |
| `check_agent_health` | None | HealthCheckResult | Check all agents |
| `check_database_health` | None | HealthCheckResult | Check database connectivity |
| `check_message_health` | None | HealthCheckResult | Check message queues |
| `check_trading_health` | None | HealthCheckResult | Check trading system |
| `run_health_check` | None | Dict | Run complete health check |
| `generate_daily_report` | None | Dict | Generate daily report |

#### 2.4.3 Health Check Thresholds

| Check | Warning | Critical |
|-------|---------|----------|
| Agent stale | > 2 hours | > 4 hours |
| Error count | ≥ 5/day | ≥ 10/day |
| Budget usage | ≥ 90% | 100% |
| DB connections | > 40 | > 45 |
| DB response | > 500ms | > 1000ms |
| Pending messages | > 1 hour old | N/A |
| Stuck orders | > 5 minutes | N/A |

#### 2.4.4 Usage Example

```python
from doctor_claude import DoctorClaude
import asyncpg

async def run_health_check():
    research_pool = await asyncpg.create_pool(RESEARCH_DATABASE_URL)
    trading_pool = await asyncpg.create_pool(DATABASE_URL)
    
    doctor = DoctorClaude(research_pool, trading_pool)
    
    # Run health check
    results = await doctor.run_health_check()
    
    if results['overall_healthy']:
        print("✅ All systems healthy")
    else:
        print(f"❌ Issues: {results['issues']}")
    
    await research_pool.close()
    await trading_pool.close()

# Run via command line
python doctor_claude.py           # Health check
python doctor_claude.py daily_report  # Daily report
```

---

## 3. Agent Lifecycle

### 3.1 Standard Agent Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. WAKE UP                                                     │
│   ──────────                                                     │
│   state = await consciousness.wake_up()                          │
│   • Updates mode to 'awake'                                      │
│   • Returns current budget, error count                          │
│                                                                  │
│   2. CHECK MESSAGES                                              │
│   ─────────────────                                              │
│   messages = await consciousness.check_messages()                │
│   for msg in messages:                                           │
│       # Process message                                          │
│       await consciousness.mark_processed(msg.id)                 │
│                                                                  │
│   3. CHECK BUDGET                                                │
│   ──────────────                                                 │
│   if not await consciousness.check_budget():                     │
│       await consciousness.sleep("Budget exhausted")              │
│       return                                                     │
│                                                                  │
│   4. RUN MODE                                                    │
│   ──────────                                                     │
│   await consciousness.update_status('trading', 'Scanning...')    │
│   # Execute trading logic                                        │
│   # Record observations, learnings                               │
│                                                                  │
│   5. SLEEP                                                       │
│   ───────                                                        │
│   await consciousness.sleep("Cycle complete")                    │
│   • Updates mode to 'sleeping'                                   │
│   • Records cycle duration                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Cron Schedules

**US Markets (public_claude):**
```cron
# Pre-market scan (09:00 EST = 14:00 UTC)
0 14 * * 1-5 /root/catalyst/public/run.sh scan

# Trading cycles (09:30-15:30 EST)
30 14-20 * * 1-5 /root/catalyst/public/run.sh trade

# End of day (16:00 EST = 21:00 UTC)
0 21 * * 1-5 /root/catalyst/public/run.sh close
```

**HKEX Markets (intl_claude):**
```cron
# Pre-market scan (09:00 HKT = 01:00 UTC)
0 1 * * 1-5 /root/catalyst/intl/run.sh scan

# Trading cycles (09:30-15:30 HKT)
30 1-7 * * 1-5 /root/catalyst/intl/run.sh trade

# End of day (16:00 HKT = 08:00 UTC)
0 8 * * 1-5 /root/catalyst/intl/run.sh close
```

**Doctor Claude:**
```cron
# Health check every 5 minutes
*/5 * * * * /root/catalyst/shared/doctor_check.sh

# Daily report (06:00 UTC)
0 6 * * * /root/catalyst/shared/doctor_report.sh
```

---

## 4. Trading Services

### 4.1 Service Matrix

| Service | Port | Purpose |
|---------|------|---------|
| Orchestration | 5000 | MCP interface |
| Scanner | 5001 | Market filtering |
| Pattern | 5002 | Chart patterns |
| Technical | 5003 | Indicators |
| Risk Manager | 5004 | Risk validation |
| Trading | 5005 | Alpaca execution |
| Workflow | 5006 | Orchestration |
| News | 5008 | Catalyst detection |
| Reporting | 5009 | Analytics |

### 4.2 alpaca_trader.py

**Purpose:** Consolidated Alpaca trading client (C2 fix)

**Location:** `services/shared/common/alpaca_trader.py`

**Version:** 2.0.0

**Critical Functions:**

| Function | Purpose |
|----------|---------|
| `map_side(side: str)` | Map 'buy'/'long'/'sell'/'short' to OrderSide |
| `round_price(price: float)` | Round to 2 decimals for sub-penny compliance |

**Symlinks Required:**
- `services/trading/common/alpaca_trader.py` → `services/shared/common/alpaca_trader.py`
- `services/risk-manager/common/alpaca_trader.py` → `services/shared/common/alpaca_trader.py`
- `services/workflow/common/alpaca_trader.py` → `services/shared/common/alpaca_trader.py`

---

## 5. Environment Variables

### 5.1 Required Variables

```bash
# Trading Database
DATABASE_URL=postgresql://user:pass@host:port/catalyst_trading?sslmode=require

# Research Database
RESEARCH_DATABASE_URL=postgresql://user:pass@host:port/catalyst_research?sslmode=require

# Alpaca API
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx
```

### 5.2 Optional Variables

```bash
# Email Alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=recipient@example.com

# Agent Identity
AGENT_ID=public_claude

# Logging
LOG_LEVEL=INFO
```

---

## 6. Related Documents

| Document | Purpose |
|----------|---------|
| `architecture.md` | System architecture |
| `database-schema.md` | Database schema |
| `ARCHITECTURE-RULES.md` | Development rules |
| `consciousness-framework-summary.md` | Implementation details |
| `pre-market-validation-2025-12-30.md` | Validation procedures |

---

**END OF FUNCTIONAL SPECIFICATION v8.0.0**
