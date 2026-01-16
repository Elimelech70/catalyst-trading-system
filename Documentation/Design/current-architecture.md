# Catalyst Trading System - Current Architecture

**Name of Application:** Catalyst Trading System
**Name of file:** current-architecture.md
**Version:** 10.3.0
**Last Updated:** 2026-01-16
**Purpose:** Current deployed architecture and repository structure

---

## REVISION HISTORY

- **v10.3.0 (2026-01-16)** - Repository Cleanup
  - Archived microservices to `archive/`
  - Clean repository structure with unified agent
  - Retained consciousness framework in `services/`
  - Retained shared common modules

- **v10.2.0 (2026-01-16)** - dev_claude Unified Agent Deployed
- **v10.1.0 (2026-01-10)** - Dual-Broker Architecture Design
- **v10.0.0 (2026-01-10)** - Ecosystem Restructure

---

## 1. Repository Structure

### 1.1 Clean Structure (Current)

```
catalyst-trading-system/
├── CLAUDE.md                           # AI assistant instructions
├── README.md                           # Project overview
│
├── services/                           # Active services
│   ├── dev_claude/                     # Unified trading agent
│   │   ├── unified_agent.py            # Main agent (1,200 lines)
│   │   ├── position_monitor.py         # Position monitoring
│   │   ├── signals.py                  # Exit signal detection
│   │   ├── startup_monitor.py          # Pre-market reconciliation
│   │   ├── config/
│   │   │   └── dev_claude_config.yaml  # Trading parameters
│   │   ├── cron.d                      # Cron schedule
│   │   ├── .env.example                # Environment template
│   │   └── README.md                   # Documentation
│   │
│   ├── consciousness/                  # Agent heartbeat system
│   │   ├── heartbeat.py                # big_bro heartbeat
│   │   ├── heartbeat_public.py         # public_claude heartbeat
│   │   ├── task_executor.py            # Task execution
│   │   ├── web_dashboard.py            # Status dashboard
│   │   ├── run-heartbeat.sh
│   │   ├── run-heartbeat-public.sh
│   │   └── run-dashboard.sh
│   │
│   └── shared/                         # Shared modules
│       └── common/
│           ├── __init__.py
│           ├── consciousness.py        # Inter-agent messaging
│           ├── database.py             # DB connection management
│           ├── alerts.py               # Email notifications
│           └── doctor_claude.py        # Health monitoring
│
├── Documentation/
│   ├── Design/                         # Architecture documents
│   │   ├── current-architecture.md     # This document
│   │   ├── database-schema.md          # Database schema
│   │   ├── claude-consciousness-framework.md
│   │   ├── concepts-catalyst-trading.md
│   │   ├── operations.md
│   │   ├── strategy-ml-roadmap.md
│   │   ├── webdash-design-mcp.md
│   │   └── Archive/                    # Old design docs
│   │
│   ├── Implementation/                 # Implementation docs
│   │   ├── dev_claude_implementation_summary.md
│   │   ├── dev_claude_us_implementation.md
│   │   └── dev_claude_deployment_complete.md
│   │
│   ├── Reports/                        # Trading reports
│   └── Analysis/                       # Analysis documents
│
└── archive/                            # Legacy code (not active)
    ├── microservices/                  # Docker-based services
    ├── documentation/                  # Old documentation
    ├── config/                         # Old configurations
    ├── scripts/                        # Legacy scripts
    ├── sql/                            # Migration scripts
    ├── backups/                        # Database backups
    └── ...
```

---

## 2. System Architecture

### 2.1 Current Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CATALYST US DROPLET - CURRENT STATE                       │
│                           (2026-01-16)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    UNIFIED AGENT                                       │ │
│  │                    /root/catalyst-dev/                                 │ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │  unified_agent.py v1.0.0                                        │  │ │
│  │  │  ├── AlpacaClient (alpaca-py SDK)                               │  │ │
│  │  │  ├── ToolExecutor (12 trading tools)                            │  │ │
│  │  │  ├── ConsciousnessClient (inter-agent messaging)                │  │ │
│  │  │  └── Claude API (dynamic decision making)                       │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  │  Cron: /etc/cron.d/catalyst-dev                                       │ │
│  │  Logs: /root/catalyst-dev/logs/                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    CONSCIOUSNESS FRAMEWORK                             │ │
│  │                    /root/catalyst-trading-system/services/             │ │
│  │                                                                        │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │ │
│  │  │   consciousness/ │  │   shared/common/ │  │   dev_claude/    │    │ │
│  │  │                  │  │                  │  │   (source code)  │    │ │
│  │  │  heartbeat.py    │  │  consciousness.py│  │                  │    │ │
│  │  │  task_executor   │  │  database.py     │  │  unified_agent   │    │ │
│  │  │  web_dashboard   │  │  alerts.py       │  │  signals.py      │    │ │
│  │  │                  │  │  doctor_claude   │  │  monitors        │    │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │              DIGITALOCEAN MANAGED POSTGRESQL                           │ │
│  │                                                                        │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │ │
│  │  │   catalyst_dev   │  │  catalyst_intl   │  │catalyst_research │    │ │
│  │  │   (US sandbox)   │  │  (HKEX prod)     │  │  (consciousness) │    │ │
│  │  │   9 tables       │  │  9 tables        │  │  8 tables        │    │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         ALPACA (PAPER)                                 │ │
│  │                  https://paper-api.alpaca.markets                      │ │
│  │                                                                        │ │
│  │  Account: $105,458 equity | 15 open positions | Paper trading          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Overview

| Component | Location | Status | Purpose |
|-----------|----------|--------|---------|
| **dev_claude** | `/root/catalyst-dev/` | ✅ OPERATIONAL | US market trading |
| **consciousness** | `services/consciousness/` | ✅ Active | Agent heartbeat system |
| **shared/common** | `services/shared/common/` | ✅ Active | Shared Python modules |
| **Microservices** | `archive/microservices/` | 📦 Archived | Legacy Docker services |

---

## 3. Active Services

### 3.1 dev_claude (Unified Trading Agent)

**Deployed at:** `/root/catalyst-dev/`
**Source code:** `services/dev_claude/`

| Parameter | Value |
|-----------|-------|
| Agent ID | dev_claude |
| Market | US (NYSE/NASDAQ) |
| Broker | Alpaca (paper) |
| Max positions | 8 |
| Max position value | $5,000 |
| Stop loss | 5% |
| Take profit | 10% |
| API budget | $5/day |

**Trading Tools (12):**
- `scan_market`, `get_quote`, `get_technicals`, `detect_patterns`
- `get_news`, `get_portfolio`, `check_risk`
- `execute_trade`, `close_position`, `close_all`
- `send_alert`, `log_decision`

### 3.2 Consciousness Framework

**Location:** `services/consciousness/` and `services/shared/common/`

| Module | Purpose |
|--------|---------|
| `heartbeat.py` | big_bro agent heartbeat |
| `heartbeat_public.py` | public_claude heartbeat |
| `task_executor.py` | Execute pending tasks |
| `web_dashboard.py` | Status dashboard |
| `consciousness.py` | Inter-agent messaging API |
| `database.py` | Database connection pools |
| `alerts.py` | Email notification system |
| `doctor_claude.py` | Health monitoring |

### 3.3 Shared Common Modules

**Location:** `services/shared/common/`

```python
# consciousness.py - Inter-agent messaging
class ClaudeConsciousness:
    async def wake_up() -> AgentState
    async def sleep(status_message: str)
    async def send_message(to_agent, subject, body, ...)
    async def check_messages() -> List[Message]
    async def observe(observation_type, subject, content, ...)
    async def learn(category, learning, source, ...)

# database.py - Connection management
class DatabaseManager:
    async def connect()
    async def close()
    async def trading_fetch(query, *args)
    async def research_fetch(query, *args)

# alerts.py - Email notifications
class AlertManager:
    def send_email(subject, body, priority)
    def send_trade_alert(agent_id, action, symbol, ...)
    def send_error_alert(agent_id, error_type, ...)

# doctor_claude.py - Health monitoring
class DoctorClaude:
    async def check_agent_health()
    async def check_database_health()
    async def run_health_check()
```

---

## 4. Cron Schedules

### 4.1 dev_claude (`/etc/cron.d/catalyst-dev`)

| Time (EST) | Time (UTC) | Mode | Description |
|------------|------------|------|-------------|
| 08:00 | 13:00 | scan | Pre-market candidate search |
| 09:30 | 14:30 | trade | Market open |
| 10:00-15:00 | 15:00-20:00 | trade | Hourly trading cycles |
| 16:00 | 21:00 | close | EOD position review |
| Off-hours | - | heartbeat | Every 3h weekdays |

### 4.2 Consciousness (User Crontab)

| Schedule | Script | Purpose |
|----------|--------|---------|
| Hourly (:00) | `run-heartbeat.sh` | big_bro heartbeat |
| Hourly (:15) | `run-heartbeat-public.sh` | public_claude heartbeat |

---

## 5. Database Schema

### 5.1 Three Databases

| Database | Purpose | Used By |
|----------|---------|---------|
| `catalyst_dev` | US sandbox trading | dev_claude |
| `catalyst_intl` | HKEX production | intl_claude |
| `catalyst_research` | Consciousness | All agents |

### 5.2 catalyst_research Tables (Consciousness)

```
claude_state           # Agent status and budgets
claude_messages        # Inter-agent communication
claude_observations    # What agents notice
claude_learnings       # Validated knowledge
claude_questions       # Open questions
claude_conversations   # Key exchanges
claude_thinking        # Extended thinking
sync_log               # Cross-database sync
```

### 5.3 catalyst_dev Tables (Trading)

```
securities             # Stock registry
positions              # Open/closed positions
orders                 # Order history
decisions              # AI decision audit
scan_results           # Scanner output
trading_cycles         # Cycle logs
patterns               # Detected patterns
position_monitor_status # Real-time monitoring
v_monitor_health       # Health view
```

---

## 6. Deployment Locations

### 6.1 Runtime (Deployed)

```
/root/catalyst-dev/                    # dev_claude runtime
├── unified_agent.py
├── position_monitor.py
├── signals.py
├── startup_monitor.py
├── config/
├── venv/
├── logs/
└── .env

/root/catalyst-trading-system/         # Git repository
├── services/                          # Source code
├── Documentation/                     # Docs
└── archive/                           # Legacy code
```

### 6.2 Source Code (Git)

```
services/
├── dev_claude/                        # Trading agent source
├── consciousness/                     # Heartbeat scripts
└── shared/common/                     # Shared modules
```

---

## 7. Monitoring Commands

### 7.1 dev_claude

```bash
# Test agent
cd /root/catalyst-dev && source .env
./venv/bin/python3 unified_agent.py --mode heartbeat

# View logs
tail -50 /root/catalyst-dev/logs/trade.log
tail -50 /root/catalyst-dev/logs/heartbeat.log

# Check cron
cat /etc/cron.d/catalyst-dev
```

### 7.2 Consciousness

```bash
# Check agent state
source /root/catalyst-trading-system/.env
psql "$RESEARCH_DATABASE_URL" -c "SELECT agent_id, current_mode, last_wake_at FROM claude_state;"

# Check messages
psql "$RESEARCH_DATABASE_URL" -c "SELECT * FROM claude_messages WHERE status = 'pending';"
```

### 7.3 Database

```bash
# Check dev_claude positions
psql "$DATABASE_URL" -c "SELECT s.symbol, p.status, p.side FROM positions p JOIN securities s ON s.security_id = p.security_id ORDER BY p.opened_at DESC LIMIT 10;"
```

---

## 8. Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| **current-architecture.md** | Design/ | This document |
| database-schema.md | Design/ | Database schema |
| claude-consciousness-framework.md | Design/ | Consciousness spec |
| dev_claude_implementation_summary.md | Implementation/ | Deployment status |
| dev_claude_us_implementation.md | Implementation/ | Full implementation |

---

## 9. Archive Contents

The `archive/` folder contains legacy microservices code:

| Folder | Contents |
|--------|----------|
| `microservices/` | Docker services (scanner, trading, workflow, etc.) |
| `documentation/` | Old implementation guides |
| `config/` | Old YAML configurations |
| `scripts/` | Legacy bash/python scripts |
| `sql/` | Database migration scripts |
| `backups/` | Database backup files |

**Note:** Microservices are archived, not deleted. They can be restored if needed.

---

## 10. Summary

**Current Architecture:** Unified Agent + Consciousness Framework

| Component | Status |
|-----------|--------|
| dev_claude unified agent | ✅ Operational |
| Consciousness heartbeat | ✅ Active |
| Shared common modules | ✅ Active |
| Microservices | 📦 Archived |

**Key Principle:** Single-process agent with Claude API for dynamic decisions, consciousness framework for inter-agent communication.

---

*Current Architecture v10.3.0*
*Updated: 2026-01-16*
*Craig + Claude Family*
