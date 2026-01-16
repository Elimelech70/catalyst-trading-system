# Catalyst Trading System - Current Architecture

**Name of Application:** Catalyst Trading System
**Name of file:** current-architecture-v10.2.0.md
**Version:** 10.2.0
**Last Updated:** 2026-01-16
**Purpose:** Current deployed architecture and configuration

---

## REVISION HISTORY

- **v10.2.0 (2026-01-16)** - dev_claude Unified Agent Deployed
  - Deployed dev_claude unified agent to `/root/catalyst-dev/`
  - Single-process architecture replaces microservices for sandbox
  - Alpaca paper trading verified ($105k equity, 15 positions)
  - Cron schedule active for US market hours
  - Added code to git: `services/dev_claude/`

- **v10.1.0 (2026-01-10)** - Dual-Broker Architecture Design
- **v10.0.0 (2026-01-10)** - Ecosystem Restructure

---

## 1. Current System Overview

### 1.1 What's Actually Deployed

| Component | Location | Status | Architecture |
|-----------|----------|--------|--------------|
| **dev_claude** | `/root/catalyst-dev/` | ✅ OPERATIONAL | Unified Agent (single process) |
| **Microservices** | `/root/catalyst-trading-system/` | ✅ Running | Docker containers (10 services) |
| **big_bro** | `/root/catalyst-trading-system/` | ✅ Active | Consciousness heartbeat |
| **intl_claude** | Not on this droplet | - | Separate INTL droplet |

### 1.2 Architecture Diagram (Current State)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CATALYST US DROPLET - CURRENT STATE                       │
│                           (2026-01-16)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    UNIFIED AGENT (NEW)                                 │ │
│  │                    /root/catalyst-dev/                                 │ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │  unified_agent.py v1.0.0                                        │  │ │
│  │  │  ├── AlpacaClient (alpaca-py SDK)                               │  │ │
│  │  │  ├── ToolExecutor (12 trading tools)                            │  │ │
│  │  │  ├── ConsciousnessClient (inter-agent messaging)                │  │ │
│  │  │  └── Claude API (dynamic decision making)                       │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                              │                                         │ │
│  │  Cron Schedule: scan/trade/close/heartbeat                            │ │
│  │  Logs: /root/catalyst-dev/logs/                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    MICROSERVICES (LEGACY)                              │ │
│  │                    /root/catalyst-trading-system/                      │ │
│  │                                                                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │ │
│  │  │ Scanner  │ │ Pattern  │ │Technical │ │  Risk    │ │ Trading  │    │ │
│  │  │  :5001   │ │  :5002   │ │  :5003   │ │  :5004   │ │  :5005   │    │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                 │ │
│  │  │ Workflow │ │   News   │ │Reporting │ │  Redis   │                 │ │
│  │  │  :5006   │ │  :5008   │ │  :5009   │ │  :6379   │                 │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │              DIGITALOCEAN MANAGED POSTGRESQL                           │ │
│  │                                                                        │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │ │
│  │  │   catalyst_dev   │  │  catalyst_intl   │  │catalyst_research │    │ │
│  │  │                  │  │                  │  │                  │    │ │
│  │  │  dev_claude      │  │  intl_claude     │  │  ALL agents      │    │ │
│  │  │  9 tables        │  │  9 tables        │  │  8 tables        │    │ │
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

---

## 2. dev_claude Unified Agent (Deployed)

### 2.1 File Structure

```
/root/catalyst-dev/                    # DEPLOYED
├── unified_agent.py                   # Main agent v1.0.0 (1,200 lines)
├── position_monitor.py                # Position monitoring
├── signals.py                         # Exit signal detection
├── startup_monitor.py                 # Pre-market reconciliation
├── config/
│   └── dev_claude_config.yaml         # Trading parameters
├── .env                               # Credentials (not in git)
├── venv/                              # Python 3.10 environment
└── logs/
    ├── scan.log
    ├── trade.log
    ├── close.log
    └── heartbeat.log

/root/catalyst-trading-system/services/dev_claude/   # IN GIT
├── unified_agent.py                   # Source code
├── position_monitor.py
├── signals.py
├── startup_monitor.py
├── config/
│   └── dev_claude_config.yaml
├── cron.d                             # Cron schedule
├── .env.example                       # Environment template
└── README.md                          # Documentation
```

### 2.2 Trading Configuration

| Parameter | Value |
|-----------|-------|
| Agent ID | dev_claude |
| Role | sandbox_trader |
| Market | US (NYSE/NASDAQ) |
| Broker | Alpaca (paper) |
| Currency | USD |
| Max positions | 8 |
| Max position value | $5,000 |
| Stop loss | 5% |
| Take profit | 10% |
| Daily loss limit | $2,500 |
| API budget | $5/day |

### 2.3 Trading Tools (12)

| Tool | Purpose |
|------|---------|
| `scan_market` | Find trading candidates |
| `get_quote` | Current bid/ask |
| `get_technicals` | RSI, MACD, MAs |
| `detect_patterns` | Chart patterns |
| `get_news` | News headlines |
| `get_portfolio` | Account status |
| `check_risk` | Validate trades |
| `execute_trade` | Submit orders |
| `close_position` | Close position |
| `close_all` | Emergency close |
| `send_alert` | Alert big_bro |
| `log_decision` | Record reasoning |

### 2.4 Operating Modes

| Mode | Purpose | Trigger |
|------|---------|---------|
| `scan` | Pre-market candidate search | 08:00 EST |
| `trade` | Full trading cycle | 09:30-15:00 EST (hourly) |
| `close` | EOD position review | 16:00 EST |
| `heartbeat` | Check messages | Off-hours (every 3h) |

---

## 3. Cron Schedules (Active)

### 3.1 dev_claude Schedule (`/etc/cron.d/catalyst-dev`)

| Time (EST) | Time (UTC) | Mode | Command |
|------------|------------|------|---------|
| 08:00 | 13:00 | scan | `unified_agent.py --mode scan` |
| 09:30 | 14:30 | trade | `unified_agent.py --mode trade` |
| 10:00 | 15:00 | trade | `unified_agent.py --mode trade` |
| 11:00 | 16:00 | trade | `unified_agent.py --mode trade` |
| 12:00 | 17:00 | trade | `unified_agent.py --mode trade` |
| 13:00 | 18:00 | trade | `unified_agent.py --mode trade` |
| 14:00 | 19:00 | trade | `unified_agent.py --mode trade` |
| 15:00 | 20:00 | trade | `unified_agent.py --mode trade` |
| 16:00 | 21:00 | close | `unified_agent.py --mode close` |
| Off-hours | - | heartbeat | Every 3h weekdays, 6h weekends |

### 3.2 Microservices Schedule (User Crontab)

| Time | Action |
|------|--------|
| 21:00 AWST | Start Docker services |
| 22:30-05:00 AWST | Trading workflows (US market hours) |
| 06:00 AWST | Stop Docker services |
| Hourly | Consciousness heartbeat |

---

## 4. Database Configuration

### 4.1 Connection Details

| Database | Purpose | Tables |
|----------|---------|--------|
| `catalyst_dev` | dev_claude sandbox | 9 |
| `catalyst_intl` | intl_claude production | 9 |
| `catalyst_research` | Consciousness framework | 8 |

### 4.2 catalyst_dev Tables

```
decisions              # AI decision audit trail
orders                 # Order history
patterns               # Detected patterns
position_monitor_status # Real-time monitoring
positions              # Open/closed positions
scan_results           # Scanner output
securities             # Stock registry
trading_cycles         # Cycle logs
v_monitor_health       # Health dashboard (view)
```

### 4.3 catalyst_research Tables

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

---

## 5. Agent Status (Current)

### 5.1 dev_claude

```
agent_id: dev_claude
status: sleeping
current_mode: sleeping
api_spend_today: $0.06
daily_budget: $5.00
last_active: 2026-01-15 23:45 UTC
```

### 5.2 Alpaca Paper Account

```
Cash: $33,882.20
Equity: $105,458.02
Buying Power: $115,136.16
Open Positions: 15
Day Trade Count: 5
```

---

## 6. What Was Implemented (2026-01-16)

### 6.1 Summary of Work Done

| Task | Status | Details |
|------|--------|---------|
| Review implementation docs | ✅ | Read `dev_claude_us_implementation.md` |
| Verify deployment | ✅ | Files at `/root/catalyst-dev/` |
| Check dependencies | ✅ | anthropic, asyncpg, alpaca-py, PyYAML |
| Test heartbeat mode | ✅ | Agent runs successfully |
| Test scan mode | ✅ | Correctly detects market closed |
| Verify Alpaca connection | ✅ | $105k equity, 15 positions |
| Verify database connection | ✅ | catalyst_dev, catalyst_research |
| Verify cron schedule | ✅ | `/etc/cron.d/catalyst-dev` active |
| Update implementation summary | ✅ | v1.1.0 with deployment status |
| Add code to git | ✅ | `services/dev_claude/` |
| Push to GitHub | ✅ | Commits `067058f`, `f6d7586` |

### 6.2 Git Commits

```
f6d7586 feat(dev_claude): Add unified agent for US market trading
067058f docs: Update dev_claude implementation summary - deployment verified
```

### 6.3 Files Added to Git

```
services/dev_claude/
├── .env.example
├── README.md
├── config/dev_claude_config.yaml
├── cron.d
├── position_monitor.py
├── signals.py
├── startup_monitor.py
└── unified_agent.py
```

---

## 7. Architecture Comparison

### 7.1 Unified Agent vs Microservices

| Aspect | Unified Agent (dev_claude) | Microservices (legacy) |
|--------|---------------------------|------------------------|
| Code size | ~1,200 lines | ~5,000+ lines |
| Processes | 1 Python process | 10 Docker containers |
| Decision making | Claude API dynamic | Fixed workflow |
| Broker integration | Alpaca SDK direct | HTTP services |
| Startup time | Seconds | Minutes |
| Memory usage | ~200MB | ~2GB |
| Complexity | Low | High |
| Location | `/root/catalyst-dev/` | `/root/catalyst-trading-system/` |

### 7.2 When to Use Each

| Use Case | Architecture |
|----------|--------------|
| Sandbox/experimental trading | Unified Agent (dev_claude) |
| Production trading (if enabled) | Microservices |
| Quick iterations | Unified Agent |
| Complex multi-service workflows | Microservices |

---

## 8. Monitoring Commands

### 8.1 dev_claude

```bash
# Check agent status
cd /root/catalyst-dev && source .env
./venv/bin/python3 unified_agent.py --mode heartbeat

# View logs
tail -50 /root/catalyst-dev/logs/trade.log
tail -50 /root/catalyst-dev/logs/heartbeat.log

# Check cron
cat /etc/cron.d/catalyst-dev
```

### 8.2 Microservices

```bash
# Check Docker status
docker-compose ps

# View service logs
docker logs catalyst-trading --tail 100

# Health check
curl http://localhost:5005/health
```

### 8.3 Database

```bash
# Check agent state
psql "$RESEARCH_DATABASE_URL" -c "SELECT * FROM claude_state WHERE agent_id = 'dev_claude';"

# Check positions
psql "$DATABASE_URL" -c "SELECT * FROM positions ORDER BY opened_at DESC LIMIT 10;"
```

---

## 9. Key Documents Reference

| Document | Version | Purpose |
|----------|---------|---------|
| `architecture-v10.1.0.md` | 10.1.0 | Dual-broker design |
| `functional-specification.md` | 8.0.0 | Module specifications |
| `ARCHITECTURE-RULES.md` | 1.0.0 | Mandatory coding rules |
| `database-schema-v10.0.0.md` | 10.0.0 | Database schema |
| `dev_claude_us_implementation.md` | 1.0.0 | Full implementation |
| `dev_claude_implementation_summary.md` | 1.1.0 | Deployment status |
| **current-architecture-v10.2.0.md** | **10.2.0** | **This document** |

---

## 10. Next Steps

1. **Monitor first live trading session** - Next US market open (09:30 EST)
2. **Review trading decisions** - Check `decisions` table after trades
3. **Tune parameters** - Adjust based on performance
4. **Consider retiring microservices** - If unified agent proves stable

---

*Current Architecture v10.2.0*
*Verified and documented: 2026-01-16*
*Craig + Claude Family*
