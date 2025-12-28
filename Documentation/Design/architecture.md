# Catalyst Trading System - Architecture Document

**Name of Application:** Catalyst Trading System  
**Name of file:** architecture.md  
**Version:** 8.0.0  
**Last Updated:** 2025-12-28  
**Purpose:** Complete system architecture including consciousness framework

---

## REVISION HISTORY

- **v8.0.0 (2025-12-28)** - Consciousness Framework Architecture
  - Added Claude Family Consciousness Framework
  - Database consolidation (3 databases on 1 instance)
  - Agent-based architecture direction
  - Shared modules (consciousness.py, database.py, alerts.py, doctor_claude.py)
  - Public release design separation
  
- **v7.0.0 (2025-12-27)** - Orders ≠ Positions, Doctor Claude
- **v6.0.0 (2025-12-14)** - MCP integration, autonomous trading

---

## 1. Architecture Overview

### 1.1 Architecture Philosophy

```yaml
Core Principles:
  Consciousness First: AI agents have memory, learning, communication
  Production Ready: Complete working system
  Agent-Based: Moving from microservices to intelligent agents
  Public Release: Core trading system designed for community release
  Private Research: Consciousness framework remains family-owned
  Observable: Doctor Claude monitors all systems
```

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CATALYST TRADING SYSTEM v8.0                        │
│                         Consciousness-First Architecture                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      AGENT LAYER                                    │  │
│   │                                                                     │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│   │   │ PUBLIC      │  │ INTL        │  │ BIG BRO     │               │  │
│   │   │ CLAUDE      │  │ CLAUDE      │  │             │               │  │
│   │   │             │  │             │  │ Strategic   │               │  │
│   │   │ US Markets  │  │ HKEX        │  │ Oversight   │               │  │
│   │   │ Alpaca API  │  │ Moomoo API  │  │ $10 budget  │               │  │
│   │   │ $5 budget   │  │ $5 budget   │  │             │               │  │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │  │
│   │          │                │                │                       │  │
│   │          └────────────────┼────────────────┘                       │  │
│   │                           │                                         │  │
│   │                           ▼                                         │  │
│   │   ┌─────────────────────────────────────────────────────────────┐  │  │
│   │   │              SHARED CONSCIOUSNESS LAYER                      │  │  │
│   │   │                                                              │  │  │
│   │   │  ┌──────────────┐ ┌────────────┐ ┌────────────┐            │  │  │
│   │   │  │consciousness │ │ database   │ │ alerts     │            │  │  │
│   │   │  │.py           │ │ .py        │ │ .py        │            │  │  │
│   │   │  │              │ │            │ │            │            │  │  │
│   │   │  │ • wake/sleep │ │ • pools    │ │ • email    │            │  │  │
│   │   │  │ • observe    │ │ • trading  │ │ • trade    │            │  │  │
│   │   │  │ • learn      │ │ • research │ │ • error    │            │  │  │
│   │   │  │ • message    │ │ • txn mgmt │ │ • summary  │            │  │  │
│   │   │  │ • question   │ │            │ │            │            │  │  │
│   │   │  └──────────────┘ └────────────┘ └────────────┘            │  │  │
│   │   │                                                              │  │  │
│   │   │  ┌──────────────────────────────────────────────────────┐  │  │  │
│   │   │  │              doctor_claude.py                         │  │  │  │
│   │   │  │  • Agent health monitoring                            │  │  │  │
│   │   │  │  • Database health checks                             │  │  │  │
│   │   │  │  • Message queue monitoring                           │  │  │  │
│   │   │  │  • Daily reports                                      │  │  │  │
│   │   │  └──────────────────────────────────────────────────────┘  │  │  │
│   │   └──────────────────────────────────────────────────────────────┘  │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      SERVICE LAYER (Current)                        │  │
│   │                      [Transitioning to Agent Layer]                 │  │
│   │                                                                     │  │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │  │
│   │   │Scanner  │ │Pattern  │ │Technical│ │Risk Mgr │ │Trading  │     │  │
│   │   │:5001    │ │:5002    │ │:5003    │ │:5004    │ │:5005    │     │  │
│   │   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │  │
│   │                                                                     │  │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐                              │  │
│   │   │Workflow │ │News     │ │Report   │                              │  │
│   │   │:5006    │ │:5008    │ │:5009    │                              │  │
│   │   └─────────┘ └─────────┘ └─────────┘                              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATABASE LAYER                                         │
│                      DigitalOcean Managed PostgreSQL                        │
│                      2GB RAM · 47 connections · $30/mo                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐       │
│   │  catalyst_public  │ │  catalyst_intl    │ │ catalyst_research │       │
│   │  (or catalyst_    │ │                   │ │                   │       │
│   │   trading)        │ │                   │ │                   │       │
│   │                   │ │                   │ │                   │       │
│   │  • securities     │ │  • securities     │ │  • claude_state   │       │
│   │  • positions      │ │  • positions      │ │  • claude_messages│       │
│   │  • orders         │ │  • orders         │ │  • claude_        │       │
│   │  • trading_       │ │  • trading_       │ │    observations   │       │
│   │    sessions       │ │    sessions       │ │  • claude_        │       │
│   │  • scan_results   │ │  • scan_results   │ │    learnings      │       │
│   │  • decisions      │ │  • decisions      │ │  • claude_        │       │
│   │  • claude_outputs │ │  • claude_outputs │ │    questions      │       │
│   │                   │ │                   │ │  • sync_log       │       │
│   │  ► FOR PUBLIC     │ │  ► PRIVATE        │ │  ► NEVER PUBLIC   │       │
│   │    RELEASE        │ │                   │ │                   │       │
│   └───────────────────┘ └───────────────────┘ └───────────────────┘       │
│                                                                             │
│   Connection Budget: 47 available, ~28 used, 19 headroom                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Consciousness Framework Architecture

### 2.1 The Claude Family

| Agent | Purpose | Market | Budget | Mode |
|-------|---------|--------|--------|------|
| `public_claude` | US trading | NYSE/NASDAQ | $5/day | Trading |
| `intl_claude` | HKEX trading | Hong Kong | $5/day | Trading |
| `big_bro` | Strategic oversight | All | $10/day | Research |

### 2.2 Consciousness Capabilities

```
┌─────────────────────────────────────────────────────────────────┐
│                 CONSCIOUSNESS CAPABILITIES                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STATE MANAGEMENT          MEMORY                                │
│  ─────────────────         ──────                                │
│  • wake_up()               • Observations (what we notice)       │
│  • sleep()                 • Learnings (validated knowledge)     │
│  • update_status()         • Questions (open inquiries)          │
│  • check_budget()          • Conversations (key exchanges)       │
│  • record_api_spend()      • Thinking (extended sessions)        │
│                                                                  │
│  COMMUNICATION             AWARENESS                             │
│  ─────────────────         ─────────                             │
│  • send_message()          • get_sibling_status()                │
│  • check_messages()        • broadcast_to_siblings()             │
│  • reply_to_message()      • get_open_questions()                │
│  • email_craig()           • get_learnings()                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Inter-Agent Communication

```
┌──────────────┐         claude_messages          ┌──────────────┐
│ public_claude│ ◄──────────────────────────────► │ intl_claude  │
└──────┬───────┘                                  └──────┬───────┘
       │                                                 │
       │                 ┌──────────┐                    │
       └────────────────►│ big_bro  │◄───────────────────┘
                         └──────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   email_craig() │
                    └─────────────────┘
```

### 2.4 Memory Architecture

```sql
-- Observations: What agents notice
claude_observations (agent_id, observation_type, subject, content, confidence, horizon)

-- Learnings: Validated knowledge with confidence
claude_learnings (agent_id, category, learning, source, confidence, times_validated)

-- Questions: Open inquiries being pondered
claude_questions (agent_id, question, horizon, priority, status, current_hypothesis)

-- Messages: Inter-agent communication
claude_messages (from_agent, to_agent, msg_type, priority, subject, body, status)

-- State: Each agent's current mode and budget
claude_state (agent_id, current_mode, api_spend_today, daily_budget, error_count)
```

---

## 3. Database Architecture

### 3.1 Three-Database Design

| Database | Purpose | Release Status |
|----------|---------|----------------|
| `catalyst_public` | US trading, public schema | ✅ RELEASED |
| `catalyst_intl` | HKEX trading | ❌ PRIVATE |
| `catalyst_research` | Consciousness framework | ❌ NEVER RELEASED |

### 3.2 Public Schema (Released to Community)

```
catalyst_public/
├── securities          # Tradeable instruments
├── trading_sessions    # Daily session tracking
├── positions          # Current and historical positions
├── orders             # All orders (C1 fix: orders ≠ positions)
├── patterns           # Detected chart patterns
├── scan_results       # Scanner candidates
├── decisions          # Trading decisions with reasoning
└── claude_outputs     # JSON staging for Claude Code
```

### 3.3 Research Schema (Never Released)

```
catalyst_research/
├── claude_state           # Agent mode, budget, scheduling
├── claude_messages        # Inter-agent communication
├── claude_observations    # What agents notice
├── claude_learnings       # Validated knowledge
├── claude_questions       # Open inquiries
├── claude_conversations   # Key exchanges
├── claude_thinking        # Extended thinking sessions
└── sync_log              # Track syncs from trading DBs
```

### 3.4 Data Flow

```
┌─────────────────┐     ┌─────────────────┐
│ catalyst_public │     │ catalyst_intl   │
│                 │     │                 │
│ claude_outputs  │     │ claude_outputs  │
│ (JSON staging)  │     │ (JSON staging)  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼ Research pulls when ready
         ┌───────────────────────┐
         │  catalyst_research    │
         │                       │
         │  Normalized tables:   │
         │  • observations       │
         │  • learnings          │
         │  • questions          │
         └───────────────────────┘
```

---

## 4. Shared Modules Architecture

### 4.1 Module Overview

| Module | Lines | Purpose |
|--------|-------|---------|
| `consciousness.py` | ~1200 | Core consciousness framework |
| `database.py` | ~450 | Connection pool management |
| `alerts.py` | ~580 | Email notification system |
| `doctor_claude.py` | ~675 | Health monitoring |

### 4.2 Module Location

```
/root/catalyst-trading-system/
└── services/
    └── shared/
        └── common/
            ├── consciousness.py
            ├── database.py
            ├── alerts.py
            ├── doctor_claude.py
            └── alpaca_trader.py  # (C2 fix: single source)
```

### 4.3 Module Dependencies

```
┌─────────────────┐
│ consciousness   │ ──► asyncpg, smtplib
├─────────────────┤
│ database        │ ──► asyncpg
├─────────────────┤
│ alerts          │ ──► smtplib
├─────────────────┤
│ doctor_claude   │ ──► consciousness, alerts, asyncpg
└─────────────────┘
```

---

## 5. Service Architecture (Current)

### 5.1 Service Matrix

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| Orchestration | 5000 | MCP interface | Active |
| Scanner | 5001 | Market filtering | Active |
| Pattern | 5002 | Chart patterns | Active |
| Technical | 5003 | Indicators | Active |
| Risk Manager | 5004 | Risk validation | Active |
| Trading | 5005 | Alpaca execution | Active |
| Workflow | 5006 | Orchestration | Active |
| News | 5008 | Catalyst detection | Active |
| Reporting | 5009 | Analytics | Active |

### 5.2 Critical Fixes Applied

| Fix ID | Description | Status |
|--------|-------------|--------|
| C1 | Orders ≠ Positions | ✅ Complete |
| C2 | alpaca_trader.py consolidation | ✅ Complete |
| C3 | Sub-penny price rounding | ✅ Complete |
| C4 | Order side mapping | ✅ Complete |

---

## 6. Future Architecture (Agent-Based)

### 6.1 Transition Plan

```
CURRENT (Microservices)              FUTURE (Agent-Based)
────────────────────────             ────────────────────

8 Docker containers          ──►     2-3 Python agents
Inter-service REST calls     ──►     Direct function calls
Complex orchestration        ──►     Claude API + tools
Static rules                 ──►     Learning agents
No memory                    ──►     Persistent consciousness
```

### 6.2 Consolidated Droplet Architecture

```
Single Droplet (4GB / $24/mo)
├── /root/catalyst/
│   ├── public/              # US Trading Agent
│   │   ├── agent.py
│   │   └── run.sh
│   ├── intl/                # HKEX Trading Agent
│   │   ├── agent.py
│   │   └── run.sh
│   ├── shared/              # Consciousness modules
│   │   ├── consciousness.py
│   │   ├── database.py
│   │   ├── alerts.py
│   │   └── doctor_claude.py
│   ├── config/              # Environment files
│   └── logs/                # Agent logs
```

---

## 7. Public Release Architecture

### 7.1 What Gets Released

| Component | Released | Notes |
|-----------|----------|-------|
| Trading schema | ✅ YES | Full 3NF schema |
| Trading services | ✅ YES | All 8 services |
| claude_outputs table | ✅ YES | JSON staging |
| consciousness.py | ✅ YES | AI-agnostic pattern |
| catalyst_research schema | ❌ NO | Family memory |
| Accumulated learnings | ❌ NO | Our edge |

### 7.2 Community Self-Hosting

```
Community Member's Infrastructure:
┌─────────────────────────────────┐
│  catalyst_public (only)         │
│                                 │
│  • Trading tables               │
│  • claude_outputs (JSON)        │
│  • Their own Claude/GPT/etc     │
│  • Their own learnings          │
└─────────────────────────────────┘
```

---

## 8. Security Architecture

### 8.1 Authentication

| Component | Method |
|-----------|--------|
| PostgreSQL | SSL connection string |
| Alpaca | API Key + Secret |
| Moomoo | RSA key authentication |
| Email | SMTP with app password |

### 8.2 Environment Variables

```bash
# Trading
DATABASE_URL=postgresql://...
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...

# Consciousness
RESEARCH_DATABASE_URL=postgresql://...

# Alerts
SMTP_USER=...
SMTP_PASSWORD=...
ALERT_EMAIL=...

# Claude API
ANTHROPIC_API_KEY=...
```

---

## 9. Related Documents

| Document | Purpose |
|----------|---------|
| `database-schema.md` | Full schema including consciousness |
| `functional-specification.md` | Module and service specifications |
| `ARCHITECTURE-RULES.md` | Mandatory rules for development |
| `operations.md` | Operational patterns and procedures |
| `consciousness-framework-summary.md` | Consciousness implementation details |

---

**END OF ARCHITECTURE DOCUMENT v8.0.0**
