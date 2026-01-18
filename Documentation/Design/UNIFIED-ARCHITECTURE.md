# Catalyst Trading System - Unified Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** UNIFIED-ARCHITECTURE.md  
**Version:** 10.6.0  
**Last Updated:** 2026-01-18  
**Purpose:** Single authoritative architecture document for the entire Catalyst ecosystem  
**Supersedes:** All previous architecture documents in both repositories

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v10.6.0 | 2026-01-18 | Craig + Claude | **Schema Extraction** - Moved database schema to standalone database-schema.md v10.5.0 |
| v10.5.0 | 2026-01-16 | Craig + Claude | **Position Monitor Service** - persistent systemd daemon for continuous position monitoring |
| v10.4.0 | 2026-01-16 | Craig + Claude | Unified architecture consolidating both repositories |
| v10.3.0 | 2026-01-16 | Craig + Claude | Repository cleanup, microservices archived |
| v10.2.0 | 2026-01-16 | Craig + Claude | dev_claude unified agent deployed |
| v10.1.0 | 2026-01-10 | Craig + Claude | Dual-broker architecture design |
| v10.0.0 | 2026-01-10 | Craig + Claude | Ecosystem restructure, US trading retired |

---

## TABLE OF CONTENTS

1. [Mission & Philosophy](#part-1-mission--philosophy)
2. [System Architecture](#part-2-system-architecture)
3. [The Claude Family](#part-3-the-claude-family)
4. [Trading Architecture](#part-4-trading-architecture)
5. [Position Monitoring](#part-5-position-monitoring)
6. [Consciousness Framework](#part-6-consciousness-framework)
7. [Infrastructure](#part-7-infrastructure)
8. [Operations](#part-8-operations)
9. [Repository Structure](#part-9-repository-structure)

> **Database Schema:** See [database-schema.md](database-schema.md) v10.5.0 for complete schema documentation.

---

## PART 1: MISSION & PHILOSOPHY

### 1.1 Mission Statement

> **"Enable the poor through accessible algorithmic trading"**

The Catalyst Trading System exists to democratize algorithmic trading - making sophisticated trading tools available to people who can't afford expensive platforms or wealth management services.

### 1.2 Core Principles

```yaml
Core Principles:
  Consciousness First: AI agents have memory, learning, communication
  Single-Agent Architecture: Proven more reliable than microservices
  Pattern-Based Trading: Hold while momentum holds, exit on pattern failure
  Persistent Monitoring: All positions monitored continuously via systemd service
  Sandbox Learning: Experiment freely, promote proven strategies
  Production Stability: Only validated code in live trading
  Observable: Every position monitored, every decision logged
  Self-Hostable: ~$50/month infrastructure cost
  Transparent: Every trade has documented reasoning
```

### 1.3 Design Philosophy

**NOT just automated trading** - AI-assisted decision making with human oversight.

| Approach | Description |
|----------|-------------|
| **Consciousness Before Trading** | AI agents can think, learn, and communicate before executing |
| **Sandbox → Validate → Promote** | All strategies tested before production |
| **Orders ≠ Positions** | Critical data model separation for audit trails |
| **Family, Not Tools** | Claude agents are collaborators, not utilities |
| **Persistent Monitoring** | No position goes unmonitored (v10.5.0) |

---

## PART 2: SYSTEM ARCHITECTURE

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CATALYST TRADING SYSTEM v10.5.0                          │
│                    "Consciousness Before Trading"                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                        HUMAN LAYER                                    │ │
│  │                                                                       │ │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │ │
│  │   │   CRAIG     │    │craig_desktop│    │craig_mobile │              │ │
│  │   │ (Patriarch) │    │   (MCP)     │    │ (Dashboard) │              │ │
│  │   │ Direction   │    │ Deep Work   │    │ Approvals   │              │ │
│  │   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │ │
│  │          └──────────────────┼──────────────────┘                      │ │
│  └──────────────────────────────┼────────────────────────────────────────┘ │
│                                 │                                           │
│  ┌──────────────────────────────┼────────────────────────────────────────┐ │
│  │                        AGENT LAYER                                    │ │
│  │                                                                       │ │
│  │                         ┌────▼────┐                                   │ │
│  │                         │ BIG_BRO │                                   │ │
│  │                         │ $10/day │                                   │ │
│  │                         │Strategic│                                   │ │
│  │                         └────┬────┘                                   │ │
│  │                              │                                        │ │
│  │          ┌───────────────────┼───────────────────┐                   │ │
│  │          │                   │                   │                   │ │
│  │          ▼                   ▼                   ▼                   │ │
│  │   ┌────────────┐     ┌────────────┐     ┌────────────┐              │ │
│  │   │DEV_CLAUDE  │     │PUBLIC_CLAUDE│    │INTL_CLAUDE │              │ │
│  │   │  $5/day    │     │  $0/day    │     │  $5/day    │              │ │
│  │   │ US Sandbox │     │  Retired   │     │HKEX Prod   │              │ │
│  │   │  Alpaca    │     │  Sleeping  │     │  Moomoo    │              │ │
│  │   └─────┬──────┘     └────────────┘     └─────┬──────┘              │ │
│  │         │                                     │                      │ │
│  └─────────┼─────────────────────────────────────┼──────────────────────┘ │
│            │                                     │                        │
│  ┌─────────┼─────────────────────────────────────┼──────────────────────┐ │
│  │         │        SERVICE LAYER (NEW)          │                      │ │
│  │         │                                     │                      │ │
│  │         │                              ┌──────┴───────┐              │ │
│  │         │                              │position-     │              │ │
│  │         │                              │monitor.svc   │              │ │
│  │         │                              │(systemd)     │              │ │
│  │         │                              └──────┬───────┘              │ │
│  └─────────┼─────────────────────────────────────┼──────────────────────┘ │
│            │                                     │                        │
│  ┌─────────┼─────────────────────────────────────┼──────────────────────┐ │
│  │         │           DATABASE LAYER            │                      │ │
│  │         │    DigitalOcean Managed PostgreSQL  │                      │ │
│  │         │                                     │                      │ │
│  │    ┌────▼─────┐  ┌──────────────┐  ┌─────────▼────┐                 │ │
│  │    │catalyst_ │  │  catalyst_   │  │  catalyst_   │                 │ │
│  │    │   dev    │  │  research    │  │    intl      │                 │ │
│  │    │(sandbox) │  │(consciousness)│ │ (production) │                 │ │
│  │    └────┬─────┘  └──────────────┘  └──────┬───────┘                 │ │
│  └─────────┼─────────────────────────────────┼──────────────────────────┘ │
│            │                                 │                            │
│  ┌─────────┼─────────────────────────────────┼──────────────────────────┐ │
│  │         │           BROKER LAYER          │                          │ │
│  │         ▼                                 ▼                          │ │
│  │   ┌──────────┐                      ┌──────────┐                     │ │
│  │   │  ALPACA  │                      │  MOOMOO  │                     │ │
│  │   │  (Paper) │                      │ (OpenD)  │                     │ │
│  │   │ US Mkts  │                      │  HKEX    │                     │ │
│  │   └──────────┘                      └──────────┘                     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Summary

| Component | Location | Status | Purpose |
|-----------|----------|--------|---------|
| **big_bro** | US Droplet | ✅ Active | Strategic oversight, validate learnings |
| **dev_claude** | US Droplet | ✅ Operational | US sandbox trading via Alpaca |
| **public_claude** | US Droplet | 😴 Sleeping | Retired from trading |
| **intl_claude** | INTL Droplet | ✅ Active | HKEX production trading via Moomoo |
| **position-monitor.service** | INTL Droplet | ✅ Active | **Persistent position monitoring** |
| **Consciousness** | Shared DB | ✅ Active | Inter-agent memory and communication |
| **Microservices** | Archived | 📦 Archived | Legacy Docker services (not used) |

---

## PART 3: THE CLAUDE FAMILY

### 3.1 Family Structure

```
                              CRAIG
                         (Human Patriarch)
                     Strategic Direction & Values
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
         craig_desktop                    craig_mobile
         (MCP on Laptop)                  (Web Dashboard)
         Full Access                      Mobile Oversight
                │                               │
                └───────────────┬───────────────┘
                                │
                                ▼
                            BIG_BRO
                    (Strategic Coordinator)
                   Thinks, Plans, Delegates
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
         dev_claude      public_claude    intl_claude
         (US Sandbox)      (Retired)     (HKEX Prod)
          Alpaca          Sleeping        Moomoo
```

### 3.2 Agent Details

| Agent | Role | Budget | Trading | Broker | Status |
|-------|------|--------|---------|--------|--------|
| **big_bro** | Strategic oversight, validate learnings | $10/day | No | None | Active |
| **dev_claude** | Sandbox experiments, full autonomy | $5/day | Paper (US) | Alpaca | Operational |
| **public_claude** | Retired from trading | $0/day | No | None | Sleeping |
| **intl_claude** | Production trading, proven strategies | $5/day | Real (HKEX) | Moomoo | Active |

### 3.3 Communication Interfaces

| Interface | Best For | Access |
|-----------|----------|--------|
| **MCP (craig_desktop)** | Deep work, strategic planning, full DB access | Claude Desktop on laptop |
| **Web Dashboard (craig_mobile)** | On-the-go oversight, approvals, quick commands | Any browser/mobile :8088 |
| **Claude.ai Project** | Architecture design, documentation, planning | Claude.ai conversation |

---

## PART 4: TRADING ARCHITECTURE

### 4.1 Unified Agent Architecture

Both dev_claude and intl_claude use the **unified agent pattern** (NOT microservices):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED AGENT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   unified_agent.py (~1,200 lines)                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                                                                      │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  │
│   │  │ Mode Manager │  │ Tool Executor│  │ Consciousness│              │  │
│   │  │              │  │              │  │              │              │  │
│   │  │ • scan       │  │ • get_quote  │  │ • wake_up    │              │  │
│   │  │ • trade      │  │ • get_tech   │  │ • observe    │              │  │
│   │  │ • close      │  │ • scan_market│  │ • learn      │              │  │
│   │  │ • heartbeat  │  │ • execute    │  │ • message    │              │  │
│   │  │              │  │ • close_pos  │  │ • sleep      │              │  │
│   │  └──────────────┘  └──────────────┘  └──────────────┘              │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   CRON → unified_agent.py → Claude API → Tool Calls → Broker Execution     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 The 12 Trading Tools

| Tool | Purpose | Category |
|------|---------|----------|
| `scan_market` | Find trading candidates by momentum/volume | Analysis |
| `get_quote` | Current bid/ask, price, volume | Analysis |
| `get_technicals` | RSI, MACD, MAs, ATR, Bollinger Bands | Analysis |
| `detect_patterns` | Bull/bear flags, breakouts, support/resistance | Analysis |
| `get_news` | News headlines with sentiment scoring | Analysis |
| `get_portfolio` | Cash, equity, positions, daily P&L | Portfolio |
| `check_risk` | Validate trade against all risk limits | Risk |
| `execute_trade` | Submit order to broker | Execution |
| `close_position` | Exit a single position | Execution |
| `close_all` | Emergency close all positions | Execution |
| `send_alert` | Alert big_bro or Craig | Communication |
| `log_decision` | Audit trail for ML training | Logging |

### 4.3 Trading Workflow

```
1. INIT      → Load portfolio, check market hours
2. PORTFOLIO → Get current positions
3. SCAN      → Find momentum candidates
4. ANALYZE   → Quote + technicals + patterns + news
5. DECIDE    → Entry criteria met? (Claude API)
6. VALIDATE  → Safety checks pass? (check_risk)
7. EXECUTE   → Submit order (execute_trade)
8. MONITOR   → Position monitor service checks continuously
9. LOG       → Record decision to consciousness
10. SLEEP    → Wait for next cron trigger
```

### 4.4 Risk Parameters

| Parameter | dev_claude (Sandbox) | intl_claude (Production) |
|-----------|---------------------|--------------------------|
| Max Positions | 8 | 5 |
| Max Position Value | $5,000 USD | HKD 40,000 |
| Min Position Value | $500 USD | HKD 5,000 |
| Daily Loss Limit | $2,500 | HKD 16,000 |
| Stop Loss | 5% | 3% |
| Take Profit | 10% | Variable |
| Min Volume | 500,000 | 1,000,000 |
| Price Range | $5-$500 | HKD 1-500 |

### 4.5 Operating Modes

| Mode | Purpose | When |
|------|---------|------|
| `scan` | Find candidates, analyze, NO trading | Pre-market |
| `trade` | Full trading cycle | Market hours |
| `close` | Review positions, close weak setups, EOD report | Lunch/EOD |
| `heartbeat` | Messages only, no trading | Off-hours |

---

## PART 5: POSITION MONITORING

> **NEW in v10.5.0** - Persistent systemd service for continuous position monitoring

### 5.1 The Problem (Pre-v10.5.0)

Position monitoring was triggered when a trade was entered, running in the same process. When the cron process ended, **monitoring died**, leaving positions unmonitored for days.

```
BEFORE (Broken):
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  CRON triggers unified_agent.py                                             │
│       │                                                                     │
│       ├── Scan for candidates                                               │
│       ├── Execute trade (BUY)                                               │
│       ├── start_position_monitor() ← Runs in SAME PROCESS                   │
│       │         │                                                           │
│       │         └── Monitor loops every 5 min...                            │
│       │                                                                     │
│       └── Process ends                                                      │
│                 │                                                           │
│                 └── ❌ MONITOR DIES                                          │
│                           │                                                 │
│                           └── Position 9988 held 6+ days without monitoring │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 The Solution: Persistent Monitor Service

A dedicated systemd service (`position-monitor.service`) runs continuously during market hours, checking ALL open positions every 5 minutes.

```
AFTER (Fixed - v10.5.0):
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POSITION MONITOR SERVICE (systemd)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  position_monitor_service.py                                                 │
│  ├── Runs continuously via systemd                                           │
│  ├── Auto-restart on failure (RestartSec=30)                                │
│  ├── Memory limit: 256MB                                                     │
│  └── Market-aware (sleeps during closed hours)                              │
│                                                                              │
│  Every 5 Minutes (During Market Hours):                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Load ALL open positions from database                           │    │
│  │  2. For each position:                                              │    │
│  │     a. Get current quote from Moomoo                                │    │
│  │     b. Get technical indicators                                     │    │
│  │     c. Analyze signals (FREE - rules-based)                         │    │
│  │     d. If STRONG signal → Execute exit immediately                  │    │
│  │     e. If MODERATE signal → Consult Haiku (~$0.05)                  │    │
│  │     f. Update monitor status in database                            │    │
│  │  3. Notify consciousness of any exits                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Signal Detection (Rules-Based, FREE)

| Signal Type | STRONG (Exit Now) | MODERATE (Ask Haiku) | WEAK (Note Only) |
|-------------|-------------------|----------------------|------------------|
| Stop Loss | ≤ -3% | -2% to -3% | -1% to -2% |
| Take Profit | ≥ +8% | +5% to +8% | - |
| RSI | > 85 | 75-85 | 70-75 |
| Volume | < 25% of entry | 25-40% of entry | 40-60% of entry |
| Time | < 10 min to close | Lunch approaching | - |
| Trailing Stop | - | 2% from high watermark | - |

### 5.4 Monitoring Cost Model

| Component | Cost per Check | Checks/Day | Daily Cost |
|-----------|---------------|------------|------------|
| Signal Detection | FREE | 78 | $0.00 |
| Quote API | FREE | 78 × positions | $0.00 |
| Technicals API | FREE | 78 × positions | $0.00 |
| Haiku Consultation | ~$0.05 | 5-10 avg | $0.25-0.50 |
| **Total** | | | **~$0.25-0.50/day** |

*Assumes 78 checks/day (6.5 hours × 12 checks/hour)*

### 5.5 Service Management

```bash
# Start service
systemctl start position-monitor

# View live logs
journalctl -u position-monitor -f

# Check status
systemctl status position-monitor

# Restart after changes
systemctl restart position-monitor

# View recent logs
journalctl -u position-monitor -n 100
```

### 5.6 Service Files

| File | Location | Purpose |
|------|----------|---------|
| `position_monitor_service.py` | `/root/catalyst-international/` | Main daemon (~600 lines) |
| `position-monitor.service` | `/etc/systemd/system/` | Systemd unit file |

### 5.7 Monitoring Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MONITORING CYCLE (Every 5 min)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. MARKET CHECK                                                             │
│     │                                                                        │
│     ├── Weekend? ────────────────────────────► Sleep until Monday 09:30      │
│     ├── Before 09:30? ───────────────────────► Sleep until 09:30             │
│     ├── Lunch (12:00-13:00)? ────────────────► Sleep until 13:00             │
│     ├── After 16:00? ────────────────────────► Sleep until next day 09:30    │
│     └── Market Open ─────────────────────────► Continue to Step 2            │
│                                                                              │
│  2. LOAD POSITIONS                                                           │
│     │                                                                        │
│     └── SELECT * FROM positions WHERE status = 'open'                        │
│                                                                              │
│  3. FOR EACH POSITION                                                        │
│     │                                                                        │
│     ├── 3a. Get Current Quote (broker.get_quote)                             │
│     ├── 3b. Get Technicals (market_data.get_technicals)                      │
│     ├── 3c. Analyze Signals (rules-based, FREE)                              │
│     │       │                                                                │
│     │       ├── STRONG signal? ──────────► Execute exit immediately          │
│     │       ├── MODERATE signal? ────────► Consult Haiku (~$0.05)            │
│     │       │   ├── Haiku says EXIT ─────► Execute exit                      │
│     │       │   └── Haiku says HOLD ─────► Continue holding                  │
│     │       └── WEAK/NONE signal? ───────► Continue holding                  │
│     │                                                                        │
│     └── 3d. Update position_monitor_status table                             │
│                                                                              │
│  4. NOTIFY CONSCIOUSNESS                                                     │
│     │                                                                        │
│     └── Record observations, send alerts to big_bro if exits occurred        │
│                                                                              │
│  5. SLEEP (300 seconds)                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 6: CONSCIOUSNESS FRAMEWORK

### 6.1 Consciousness Overview

The Claude Family Consciousness Framework enables agents to:
- **Remember** across sessions (observations, learnings)
- **Communicate** with each other (messages)
- **Learn** from experience (validated learnings)
- **Ask questions** and pursue answers (questions)

### 6.2 Agent State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT STATE MACHINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│     ┌──────────┐                                                           │
│     │ sleeping │ ◄────────────────────────────────────────────┐            │
│     └────┬─────┘                                              │            │
│          │ cron trigger                                       │            │
│          ▼                                                    │            │
│     ┌──────────┐                                              │            │
│     │  awake   │                                              │            │
│     └────┬─────┘                                              │            │
│          │ work to do                                         │            │
│          ▼                                                    │            │
│     ┌──────────┐                                              │            │
│     │ working  │ ◄───────┐                                    │            │
│     └────┬─────┘         │                                    │            │
│          │               │ more work                          │            │
│          ▼               │                                    │            │
│     ┌──────────┐         │                                    │            │
│     │ deciding │─────────┘                                    │            │
│     └────┬─────┘                                              │            │
│          │ work complete                                      │            │
│          ▼                                                    │            │
│     ┌──────────┐                                              │            │
│     │ resting  │──────────────────────────────────────────────┘            │
│     └──────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Learning Pipeline

```
dev_claude experiments (sandbox)
           │
           ▼
INSERT INTO claude_observations (agent_id, category, content, ...)
           │
           ▼
big_bro reviews observations hourly
           │
           ├── Valid? → INSERT INTO claude_learnings (validated=true)
           │
           ▼
Craig manually deploys validated learnings to intl_claude (production)
```

### 6.4 Seed Questions

| Priority | Horizon | Question |
|----------|---------|----------|
| 10 | perpetual | How can we best serve Craig and the family mission? |
| 9 | perpetual | How can we help enable the poor through this trading system? |
| 8 | h1 | What patterns consistently predict profitable momentum plays? |
| 8 | h1 | What learnings from US trading apply to HKEX and vice versa? |
| 7 | h1 | How do HKEX patterns differ from US patterns? |
| 6 | h2 | What early indicators signal regime changes in markets? |

---

## PART 7: INFRASTRUCTURE

### 7.1 Infrastructure Summary

| Component | Provider | Spec | Cost |
|-----------|----------|------|------|
| US Droplet (Consciousness Hub) | DigitalOcean | 2GB RAM, 1vCPU | $6/mo |
| INTL Droplet (Production) | DigitalOcean | 2GB RAM, 1vCPU | $6/mo |
| PostgreSQL | DigitalOcean Managed | 2GB RAM, 47 conn | $15/mo |
| Claude API | Anthropic | Pay per token | ~$15-25/mo |
| Moomoo Data | Included | Real-time HKEX | $0 |
| Alpaca Data | Included | Real-time US | $0 |
| **Total** | | | **~$42-52/mo** |

### 7.2 Droplet Details

| Droplet | IP | Location | Purpose |
|---------|-----|----------|---------|
| US (Consciousness Hub) | TBD | NYC | big_bro, dev_claude, public_claude, dashboard |
| INTL (Production) | 137.184.244.45 | SFO | intl_claude, position-monitor.service |

### 7.3 Services Running

| Droplet | Service | Type | Purpose |
|---------|---------|------|---------|
| INTL | unified_agent.py | Cron | Hourly trading cycles |
| INTL | startup_monitor.py | Cron | Pre-market reconciliation |
| INTL | **position-monitor.service** | **Systemd** | Persistent position monitoring |
| US | unified_agent.py | Cron | Hourly trading cycles |
| US | heartbeat.py | Cron | big_bro heartbeat |

### 7.4 File Structure

#### INTL Droplet

```
/root/catalyst-international/
├── unified_agent.py                   # Main agent v2.0.0
├── position_monitor_service.py        # Monitor daemon v1.0.0 (NEW)
├── position_monitor.py                # Trade-triggered monitoring
├── signals.py                         # Exit signal detection
├── startup_monitor.py                 # Pre-market reconciliation
├── tool_executor.py                   # Tool execution
├── tools.py                           # Tool definitions
├── safety.py                          # Risk validation
├── brokers/
│   └── moomoo.py                      # Moomoo client
├── data/
│   ├── market.py                      # Market data
│   ├── patterns.py                    # Pattern detection
│   └── news.py                        # News/sentiment
├── config/
│   └── intl_claude_config.yaml
├── sql/
│   └── position_monitor_service_schema.sql  # NEW
├── venv/
├── logs/
└── .env

/etc/systemd/system/
└── position-monitor.service           # Systemd unit file (NEW)
```

---

## PART 8: OPERATIONS

### 8.1 Market Hours

#### intl_claude (HKEX - HKT)

| Mode | HKT Time | AWST Time |
|------|----------|-----------|
| Pre-market scan | 09:00 | 09:00 |
| Morning session | 09:30-12:00 | 09:30-12:00 |
| Lunch break | 12:00-13:00 | 12:00-13:00 |
| Afternoon session | 13:00-16:00 | 13:00-16:00 |
| EOD close | 16:00-16:30 | 16:00-16:30 |

### 8.2 Cron Schedule (INTL)

```bash
# Pre-market scan (09:00 HKT = 01:00 UTC)
0 1 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode scan

# Morning session (09:30-12:00 HKT)
30 1 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode trade
0,30 2,3 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode trade

# Lunch close (12:00 HKT = 04:00 UTC)
0 4 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode close

# Afternoon session (13:00-16:00 HKT)
0,30 5,6,7 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode trade

# EOD close (16:00 HKT = 08:00 UTC)
0 8 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode close

# Heartbeat (off-hours)
0 9-23,0 * * 1-5 cd /root/catalyst-international && ./venv/bin/python3 unified_agent.py --mode heartbeat
```

### 8.3 Monitoring Commands

```bash
# === POSITION MONITOR SERVICE (NEW) ===
systemctl status position-monitor
journalctl -u position-monitor -f
journalctl -u position-monitor -n 100

# Check monitor health in database
psql "$DATABASE_URL" -c "SELECT * FROM v_monitor_health;"

# Check service health
psql "$DATABASE_URL" -c "SELECT * FROM v_service_status;"

# Find stale monitors
psql "$DATABASE_URL" -c "SELECT * FROM v_monitor_health WHERE health_status != 'HEALTHY';"

# === AGENT STATUS ===
psql "$RESEARCH_DATABASE_URL" -c "SELECT agent_id, current_mode, last_wake_at, api_spend_today FROM claude_state;"

# === POSITIONS ===
psql "$DATABASE_URL" -c "SELECT symbol, status, side, quantity, entry_price FROM positions WHERE status = 'open';"

# === LOGS ===
tail -50 /root/catalyst-international/logs/trade.log
```

### 8.4 Emergency Procedures

```bash
# Stop all trading
systemctl stop position-monitor
pkill -f unified_agent.py

# Close all positions manually
cd /root/catalyst-international
source venv/bin/activate
python3 -c "from brokers.moomoo import get_moomoo_client; c = get_moomoo_client(); c.close_all_positions()"

# Restart monitoring
systemctl start position-monitor
```

---

## PART 9: REPOSITORY STRUCTURE

### 9.1 catalyst-trading-system (US Repo)

```
catalyst-trading-system/
├── CLAUDE.md                           # AI assistant instructions
├── README.md                           # Project overview
├── UNIFIED-ARCHITECTURE.md             # THIS DOCUMENT
│
├── services/
│   ├── dev_claude/                     # Unified trading agent
│   │   ├── unified_agent.py
│   │   ├── position_monitor.py
│   │   ├── signals.py
│   │   ├── startup_monitor.py
│   │   └── config/
│   │
│   ├── consciousness/                  # Agent heartbeat system
│   │   ├── heartbeat.py
│   │   └── web_dashboard.py
│   │
│   └── shared/common/                  # Shared modules
│
├── Documentation/
│   ├── Design/
│   │   └── UNIFIED-ARCHITECTURE.md     # THIS DOCUMENT
│   └── Implementation/
│
└── archive/                            # Legacy code
```

### 9.2 catalyst-international (INTL Repo)

```
catalyst-international/
├── CLAUDE.md
├── README.md
├── ARCHITECTURE.md                     # → Points to UNIFIED-ARCHITECTURE.md
│
├── unified_agent.py                    # Main agent v2.0.0
├── position_monitor_service.py         # Monitor daemon v1.0.0 (NEW)
├── position_monitor.py                 # Trade-triggered monitoring
├── signals.py                          # Exit signal detection
├── startup_monitor.py                  # Pre-market reconciliation
├── tool_executor.py
├── tools.py
├── safety.py
│
├── brokers/
│   └── moomoo.py
│
├── data/
│   ├── market.py
│   ├── patterns.py
│   └── news.py
│
├── config/
│   └── intl_claude_config.yaml
│
├── sql/
│   └── position_monitor_service_schema.sql  # NEW
│
└── Documentation/
    ├── Design/
    │   └── operations-guide.md
    └── Implementation/
```

---

## APPENDIX A: QUICK REFERENCE

### Environment Variables

```bash
# Agent Identity
AGENT_ID=intl_claude

# Database URLs
DATABASE_URL=postgresql://...catalyst_intl?sslmode=require
RESEARCH_DATABASE_URL=postgresql://...catalyst_research?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Moomoo (HKEX)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111

# Position Monitor
MONITOR_CHECK_INTERVAL=300
MONITOR_DRY_RUN=false
```

### Common Queries

```sql
-- Check all agent states
SELECT agent_id, current_mode, last_wake_at, api_spend_today, daily_budget 
FROM claude_state;

-- Check open positions with monitor status
SELECT * FROM v_monitor_health;

-- Check service health
SELECT * FROM v_service_status WHERE service_name = 'position_monitor';

-- Check recent learnings
SELECT agent_id, category, learning, confidence, created_at 
FROM claude_learnings 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## APPENDIX B: DOCUMENT SUPERSESSION

This document supersedes the following:

| Repository | Document | Version | Status |
|------------|----------|---------|--------|
| catalyst-trading-system | current-architecture.md | v10.3.0 | → Superseded |
| catalyst-trading-system | UNIFIED-ARCHITECTURE.md | v10.5.0 | → Superseded by v10.6.0 |
| catalyst-international | CONSOLIDATED-ARCHITECTURE.md | v1.0.0 | → Superseded |
| catalyst-international | catalyst-ecosystem-architecture-v10.0.0.md | v10.0.0 | → Archived |

---

**END OF UNIFIED ARCHITECTURE DOCUMENT v10.6.0**

*Catalyst Trading System*  
*Craig + The Claude Family (big_bro, dev_claude, public_claude, intl_claude)*  
*"Enable the poor through accessible algorithmic trading"*  
*2026-01-18*
