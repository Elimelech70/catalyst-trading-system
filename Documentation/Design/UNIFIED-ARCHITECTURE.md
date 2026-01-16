# Catalyst Trading System - Unified Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** UNIFIED-ARCHITECTURE.md  
**Version:** 10.4.0  
**Last Updated:** 2026-01-16  
**Purpose:** Single authoritative architecture document for the entire Catalyst ecosystem  
**Supersedes:** All previous architecture documents in both repositories

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
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
5. [Consciousness Framework](#part-5-consciousness-framework)
6. [Database Schema](#part-6-database-schema)
7. [Infrastructure](#part-7-infrastructure)
8. [Operations](#part-8-operations)
9. [Repository Structure](#part-9-repository-structure)

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

---

## PART 2: SYSTEM ARCHITECTURE

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CATALYST TRADING SYSTEM v10.4.0                          │
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
8. MONITOR   → Start position monitor (on BUY)
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

## PART 5: CONSCIOUSNESS FRAMEWORK

### 5.1 Consciousness Overview

The Claude Family Consciousness Framework enables agents to:
- **Remember** across sessions (observations, learnings)
- **Communicate** with each other (messages)
- **Learn** from experience (validated learnings)
- **Ask questions** and pursue answers (questions)

### 5.2 Agent State Machine

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

### 5.3 Learning Pipeline

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

### 5.4 Seed Questions

| Priority | Horizon | Question |
|----------|---------|----------|
| 10 | perpetual | How can we best serve Craig and the family mission? |
| 9 | perpetual | How can we help enable the poor through this trading system? |
| 8 | h1 | What patterns consistently predict profitable momentum plays? |
| 8 | h1 | What learnings from US trading apply to HKEX and vice versa? |
| 7 | h1 | How do HKEX patterns differ from US patterns? |
| 6 | h2 | What early indicators signal regime changes in markets? |

---

## PART 6: DATABASE SCHEMA

### 6.1 Three-Database Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DIGITALOCEAN MANAGED POSTGRESQL                          │
│                    Single cluster · 47 connections · $15/mo                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │  catalyst_research  │ │    catalyst_dev     │ │   catalyst_intl     │   │
│  │   (consciousness)   │ │    (dev_claude)     │ │   (intl_claude)     │   │
│  │                     │ │                     │ │                     │   │
│  │  SHARED TABLES:     │ │  TRADING TABLES:    │ │  TRADING TABLES:    │   │
│  │  • claude_state     │ │  • securities       │ │  • securities       │   │
│  │  • claude_messages  │ │  • trading_cycles   │ │  • trading_cycles   │   │
│  │  • claude_learnings │ │  • positions        │ │  • positions        │   │
│  │  • claude_observations│ • orders           │ │  • orders           │   │
│  │  • claude_questions │ │  • scan_results     │ │  • scan_results     │   │
│  │  • claude_conversations│ • decisions       │ │  • decisions        │   │
│  │  • claude_thinking  │ │  • patterns         │ │  • patterns         │   │
│  │  • sync_log         │ │  • position_monitor_│ │  • position_monitor_│   │
│  │                     │ │    status           │ │    status           │   │
│  │  Access: ALL agents │ │  Access: dev_claude │ │  Access: intl_claude│   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Connection Budget

```
DigitalOcean Managed PostgreSQL: 47 connections

Allocation:
├── catalyst_research (shared)
│   └── big_bro + public_claude + dev_claude + intl_claude + MCP = ~8
├── catalyst_dev (dev_claude)
│   └── unified_agent + monitors = ~5
├── catalyst_intl (intl_claude)
│   └── unified_agent + monitors = ~5
├── Buffer
│   └── ~29 connections headroom
```

---

### 6.3 CONSCIOUSNESS DATABASE (catalyst_research)

#### claude_state

```sql
CREATE TABLE claude_state (
    agent_id VARCHAR(50) PRIMARY KEY,
    
    -- Mode & Activity
    current_mode VARCHAR(50),           -- sleeping, awake, thinking, trading, error
    last_wake_at TIMESTAMPTZ,
    last_think_at TIMESTAMPTZ,
    last_action_at TIMESTAMPTZ,
    last_poll_at TIMESTAMPTZ,
    
    -- Budget Tracking
    api_spend_today DECIMAL(10,4) DEFAULT 0,
    api_spend_month DECIMAL(10,4) DEFAULT 0,
    daily_budget DECIMAL(10,4) DEFAULT 5.00,
    
    -- Scheduling
    current_schedule VARCHAR(100),
    next_scheduled_wake TIMESTAMPTZ,
    
    -- Status
    status_message TEXT,
    error_count_today INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE claude_state IS 'Each Claude agent current state and budget';
```

#### claude_messages

```sql
CREATE TABLE claude_messages (
    id SERIAL PRIMARY KEY,
    
    -- Participants
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,
    
    -- Message details
    msg_type VARCHAR(20) DEFAULT 'message',  -- message, signal, question, task, response, alert
    priority VARCHAR(20) DEFAULT 'normal',   -- low, normal, high, urgent
    subject VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    data JSONB,
    
    -- Threading
    reply_to_id INTEGER REFERENCES claude_messages(id),
    thread_id INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',    -- pending, read, processed, expired, failed
    requires_response BOOLEAN DEFAULT FALSE,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_messages_to ON claude_messages(to_agent);
CREATE INDEX idx_messages_pending ON claude_messages(to_agent, status) WHERE status = 'pending';

COMMENT ON TABLE claude_messages IS 'Inter-agent communication';
```

#### claude_observations

```sql
CREATE TABLE claude_observations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Observation details
    observation_type VARCHAR(50) NOT NULL,   -- market, pattern, anomaly, insight, error, system
    subject VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- Classification
    confidence DECIMAL(3,2),                 -- 0.00 to 1.00
    horizon VARCHAR(20),                     -- h1, h2, h3, perpetual
    market VARCHAR(20),                      -- US, HKEX, global
    tags JSONB,
    
    -- Source tracking
    source_db VARCHAR(50),
    source_id INTEGER,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_obs_agent ON claude_observations(agent_id);
CREATE INDEX idx_obs_type ON claude_observations(observation_type);
CREATE INDEX idx_obs_created ON claude_observations(created_at DESC);

COMMENT ON TABLE claude_observations IS 'Things agents notice - patterns, anomalies, insights';
```

#### claude_learnings

```sql
CREATE TABLE claude_learnings (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Learning details
    category VARCHAR(50) NOT NULL,           -- trading, pattern, market, broker, system, mistake, strategy
    learning TEXT NOT NULL,
    source VARCHAR(200),
    evidence TEXT,
    
    -- Validation
    confidence DECIMAL(3,2) DEFAULT 0.5,
    times_validated INTEGER DEFAULT 0,
    times_contradicted INTEGER DEFAULT 0,
    last_validated_at TIMESTAMPTZ,
    validated BOOLEAN DEFAULT FALSE,
    validated_by VARCHAR(50),
    
    -- Classification
    applies_to_markets JSONB,
    tags JSONB,
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learn_agent ON claude_learnings(agent_id);
CREATE INDEX idx_learn_confidence ON claude_learnings(confidence DESC);
CREATE INDEX idx_learn_validated ON claude_learnings(validated) WHERE validated = TRUE;

COMMENT ON TABLE claude_learnings IS 'Validated knowledge with confidence scores';
```

#### claude_questions

```sql
CREATE TABLE claude_questions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50),                    -- NULL = shared question for all agents
    asked_by VARCHAR(50),
    
    -- Question details
    question TEXT NOT NULL,
    context TEXT,
    category VARCHAR(50),                    -- strategy, pattern, risk, market, system, meta
    horizon VARCHAR(20) DEFAULT 'h1',        -- immediate, h1, h2, h3, perpetual
    priority INTEGER DEFAULT 5,              -- 1-10 scale, 10 = highest
    
    -- Investigation
    current_hypothesis TEXT,
    evidence_for TEXT,
    evidence_against TEXT,
    
    -- Resolution
    status VARCHAR(20) DEFAULT 'open',       -- open, investigating, answered, parked, obsolete
    answer TEXT,
    answered_at TIMESTAMPTZ,
    answered_by VARCHAR(50),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_q_status ON claude_questions(status) WHERE status = 'open';
CREATE INDEX idx_q_priority ON claude_questions(priority DESC);

COMMENT ON TABLE claude_questions IS 'Open inquiries being pondered';
```

#### claude_conversations (Future)

```sql
CREATE TABLE claude_conversations (
    conversation_id SERIAL PRIMARY KEY,
    conversation_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    participants VARCHAR(50)[] NOT NULL,
    topic VARCHAR(200),
    summary TEXT,
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE claude_conversations IS 'Key exchanges to remember';
```

#### claude_thinking (Future)

```sql
CREATE TABLE claude_thinking (
    thinking_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    topic VARCHAR(200),
    thinking_content TEXT NOT NULL,
    conclusions TEXT,
    
    duration_seconds INTEGER,
    tokens_used INTEGER,
    cost_usd DECIMAL(10,4),
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE claude_thinking IS 'Extended thinking sessions';
```

#### sync_log

```sql
CREATE TABLE sync_log (
    id SERIAL PRIMARY KEY,
    
    -- Source
    source_db VARCHAR(50) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    source_id INTEGER NOT NULL,
    
    -- Target
    target_table VARCHAR(50) NOT NULL,
    target_id INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'synced',
    error_message TEXT,
    
    -- Timing
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sync_source ON sync_log(source_db, source_table, source_id);

COMMENT ON TABLE sync_log IS 'Track syncs from trading databases to research';
```

---

### 6.4 TRADING DATABASE (catalyst_dev & catalyst_intl)

Both trading databases share identical schema. Only difference is data (US vs HKEX).

#### securities

```sql
CREATE TABLE securities (
    security_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(200),
    exchange VARCHAR(20) DEFAULT 'US',       -- US, HKEX
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap DECIMAL(20, 2),
    avg_volume BIGINT,
    lot_size INTEGER DEFAULT 1,              -- HKEX has variable lot sizes
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_securities_symbol ON securities(symbol);
CREATE INDEX idx_securities_active ON securities(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE securities IS 'Tradeable instruments registry';
```

#### trading_cycles

```sql
CREATE TABLE trading_cycles (
    cycle_id SERIAL PRIMARY KEY,
    cycle_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    cycle_date DATE NOT NULL,
    mode VARCHAR(20) NOT NULL,               -- scan, trade, close, heartbeat
    status VARCHAR(20) DEFAULT 'active',     -- active, completed, failed
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    
    -- Metrics
    candidates_found INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    api_cost DECIMAL(10,4) DEFAULT 0,
    
    -- Results
    notes TEXT,
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cycles_date ON trading_cycles(cycle_date DESC);
CREATE INDEX idx_cycles_status ON trading_cycles(status);

COMMENT ON TABLE trading_cycles IS 'Trading session tracking';
```

#### positions

```sql
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    position_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Position details (NOT order details!)
    side VARCHAR(10) NOT NULL,               -- long, short
    quantity INTEGER NOT NULL,
    avg_entry_price DECIMAL(12,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',    -- pending, open, closed, cancelled
    
    -- Exit details
    exit_price DECIMAL(12,4),
    exit_reason VARCHAR(100),
    
    -- P&L
    realized_pnl DECIMAL(14,2),
    unrealized_pnl DECIMAL(14,2),
    
    -- Timestamps
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_positions_security ON positions(security_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';

COMMENT ON TABLE positions IS 'Holdings - NEVER store order data here';
```

#### orders

```sql
-- CRITICAL: Orders ≠ Positions
-- This table is the SINGLE SOURCE OF TRUTH for all order data

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    position_id INTEGER REFERENCES positions(position_id),  -- NULL until position created
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Order identification
    broker_order_id VARCHAR(100),            -- Alpaca/Moomoo order ID
    client_order_id VARCHAR(100),
    
    -- Order details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,               -- buy, sell
    order_type VARCHAR(20) NOT NULL,         -- market, limit, stop, stop_limit
    quantity INTEGER NOT NULL,
    
    -- Prices
    limit_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    filled_price DECIMAL(12,4),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',    -- pending, submitted, accepted, filled, partial, cancelled, rejected
    filled_quantity INTEGER DEFAULT 0,
    
    -- Classification
    order_purpose VARCHAR(20),               -- entry, stop_loss, take_profit, manual_exit
    parent_order_id INTEGER REFERENCES orders(order_id),  -- For bracket orders
    
    -- Timestamps
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Audit
    notes TEXT
);

CREATE INDEX idx_orders_position ON orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_broker ON orders(broker_order_id) WHERE broker_order_id IS NOT NULL;
CREATE INDEX idx_orders_pending ON orders(status) WHERE status IN ('pending', 'submitted', 'accepted');

COMMENT ON TABLE orders IS 'All orders sent to broker - SINGLE SOURCE OF TRUTH for order data';
COMMENT ON COLUMN orders.position_id IS 'NULL for entry orders until position created';
COMMENT ON COLUMN orders.order_purpose IS 'entry=open position, stop_loss/take_profit=exit legs';
```

#### scan_results

```sql
CREATE TABLE scan_results (
    result_id SERIAL PRIMARY KEY,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Scan data
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(12,4),
    volume BIGINT,
    volume_ratio DECIMAL(8,2),
    change_pct DECIMAL(8,2),
    
    -- Ranking
    rank INTEGER,
    score DECIMAL(8,2),
    
    -- Status
    outcome VARCHAR(20),                     -- traded, rejected, skipped
    rejection_reason TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scan_cycle ON scan_results(cycle_id);
CREATE INDEX idx_scan_symbol ON scan_results(symbol);

COMMENT ON TABLE scan_results IS 'Market scan candidates';
```

#### decisions

```sql
CREATE TABLE decisions (
    decision_id SERIAL PRIMARY KEY,
    decision_uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    
    -- References
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    position_id INTEGER REFERENCES positions(position_id),
    
    -- Decision details
    decision_type VARCHAR(50) NOT NULL,      -- entry, exit, hold, skip
    symbol VARCHAR(20),
    
    -- Reasoning (for audit trail and ML training)
    reasoning TEXT,
    confidence DECIMAL(3,2),
    factors JSONB,                           -- Structured decision factors
    
    -- Outcome
    action_taken VARCHAR(100),
    outcome VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX idx_decisions_type ON decisions(decision_type);

COMMENT ON TABLE decisions IS 'Trading decisions with reasoning for audit trail';
```

#### patterns

```sql
CREATE TABLE patterns (
    pattern_id SERIAL PRIMARY KEY,
    
    -- References
    security_id INTEGER REFERENCES securities(security_id),
    cycle_id INTEGER REFERENCES trading_cycles(cycle_id),
    
    -- Pattern details
    symbol VARCHAR(20) NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,       -- bull_flag, bear_flag, breakout, etc.
    timeframe VARCHAR(10),                   -- 5m, 15m, 1h, 1d
    
    -- Analysis
    confidence DECIMAL(3,2),
    entry_price DECIMAL(12,4),
    stop_price DECIMAL(12,4),
    target_price DECIMAL(12,4),
    risk_reward DECIMAL(5,2),
    
    -- Status
    outcome VARCHAR(20),                     -- triggered, failed, expired
    
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_patterns_symbol ON patterns(symbol);
CREATE INDEX idx_patterns_type ON patterns(pattern_type);

COMMENT ON TABLE patterns IS 'Detected chart patterns';
```

#### position_monitor_status

```sql
CREATE TABLE position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    
    -- References
    position_id INTEGER REFERENCES positions(position_id) UNIQUE,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',    -- pending, starting, running, sleeping, stopped, error
    pid INTEGER,
    
    -- Timestamps
    started_at TIMESTAMPTZ,
    last_check_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    
    -- Metrics
    checks_performed INTEGER DEFAULT 0,
    signals_detected INTEGER DEFAULT 0,
    
    -- Error tracking
    error_message TEXT,
    error_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_monitor_status ON position_monitor_status(status);
CREATE INDEX idx_monitor_position ON position_monitor_status(position_id);

COMMENT ON TABLE position_monitor_status IS 'Track position monitor processes';
```

#### v_monitor_health (View)

```sql
CREATE OR REPLACE VIEW v_monitor_health AS
SELECT 
    m.monitor_id,
    m.position_id,
    p.status as position_status,
    s.symbol,
    m.status as monitor_status,
    m.started_at,
    m.last_check_at,
    m.checks_performed,
    m.signals_detected,
    m.error_count,
    EXTRACT(EPOCH FROM (NOW() - m.last_check_at)) as seconds_since_check
FROM position_monitor_status m
JOIN positions p ON p.position_id = m.position_id
JOIN securities s ON s.security_id = p.security_id
WHERE m.status IN ('running', 'starting', 'sleeping')
ORDER BY m.last_check_at DESC;

COMMENT ON VIEW v_monitor_health IS 'Dashboard view for position monitors';
```

---

### 6.5 Key Database Rules

| Rule | Description |
|------|-------------|
| **Orders ≠ Positions** | Order data ONLY in orders table, never in positions |
| **security_id FK** | Always use JOINs, not symbol VARCHAR directly |
| **Lot size varies** | HKEX lot sizes vary by stock (check securities.lot_size) |
| **Use defined ENUMs** | Status values must match defined constraints |
| **UUID for external** | Use UUIDs for anything exposed externally |
| **Timestamps with TZ** | Always use TIMESTAMPTZ, never TIMESTAMP |

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
| INTL (Production) | 137.184.244.45 | SFO | intl_claude |

### 7.3 File Structure

#### US Droplet

```
/root/catalyst-dev/                    # dev_claude runtime
├── unified_agent.py                   # Main agent v1.0.0
├── position_monitor.py                # Position monitoring
├── signals.py                         # Exit signal detection
├── startup_monitor.py                 # Pre-market reconciliation
├── config/
│   └── dev_claude_config.yaml
├── venv/                              # Python virtual environment
├── logs/
│   ├── scan.log
│   ├── trade.log
│   ├── close.log
│   └── heartbeat.log
└── .env

/root/catalyst-trading-system/         # Git repository
├── services/
│   ├── dev_claude/                    # Trading agent source
│   ├── consciousness/                 # Heartbeat scripts
│   └── shared/common/                 # Shared modules
├── Documentation/
│   ├── Design/                        # Architecture docs
│   ├── Implementation/                # Implementation docs
│   └── Reports/                       # Trading reports
└── archive/                           # Legacy microservices
```

#### INTL Droplet

```
/root/catalyst-international/
├── unified_agent.py                   # Main agent v2.0.0
├── position_monitor.py                # Position monitoring
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
├── venv/
├── logs/
└── .env
```

---

## PART 8: OPERATIONS

### 8.1 Market Hours

#### dev_claude (US Markets - EST)

| Mode | EST Time | AWST Time |
|------|----------|-----------|
| Pre-market scan | 08:00 | 21:00 |
| Market open | 09:30 | 22:30 |
| Market hours | 09:30-16:00 | 22:30-05:00 |
| Market close | 16:00 | 05:00 |
| After-hours | 16:00-20:00 | 05:00-09:00 |

#### intl_claude (HKEX - HKT)

| Mode | HKT Time | AWST Time |
|------|----------|-----------|
| Pre-market scan | 09:00 | 09:00 |
| Morning session | 09:30-12:00 | 09:30-12:00 |
| Lunch break | 12:00-13:00 | 12:00-13:00 |
| Afternoon session | 13:00-16:00 | 13:00-16:00 |
| EOD close | 16:00-16:30 | 16:00-16:30 |

### 8.2 Cron Schedules

#### dev_claude (US Droplet)

```bash
# Pre-market scan (08:00 EST = 21:00 AWST previous day)
0 21 * * 0-4 /root/catalyst-dev/venv/bin/python3 /root/catalyst-dev/unified_agent.py --mode scan

# Market hours (09:30-16:00 EST)
30 22 * * 0-4 /root/catalyst-dev/venv/bin/python3 /root/catalyst-dev/unified_agent.py --mode trade
0,30 23,0,1,2,3,4 * * 0-5 /root/catalyst-dev/venv/bin/python3 /root/catalyst-dev/unified_agent.py --mode trade

# Market close (16:00 EST)
0 5 * * 1-5 /root/catalyst-dev/venv/bin/python3 /root/catalyst-dev/unified_agent.py --mode close

# Heartbeat (off-hours)
0 6-20 * * * /root/catalyst-dev/venv/bin/python3 /root/catalyst-dev/unified_agent.py --mode heartbeat
```

#### intl_claude (INTL Droplet)

```bash
# Pre-market scan (09:00 HKT = 01:00 UTC)
0 1 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode scan

# Morning session (09:30-12:00 HKT)
30 1 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode trade
0,30 2,3 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode trade

# Lunch close (12:00 HKT = 04:00 UTC)
0 4 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode close

# Afternoon session (13:00-16:00 HKT)
0,30 5,6,7 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode trade

# EOD close (16:00 HKT = 08:00 UTC)
0 8 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode close

# Heartbeat (off-hours)
0 9-23,0 * * 1-5 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode heartbeat
0 * * * 0,6 /root/catalyst-international/venv/bin/python3 /root/catalyst-international/unified_agent.py --mode heartbeat
```

### 8.3 Monitoring Commands

```bash
# Check agent state (consciousness)
psql "$RESEARCH_DATABASE_URL" -c "SELECT agent_id, current_mode, last_wake_at, api_spend_today FROM claude_state;"

# Check pending messages
psql "$RESEARCH_DATABASE_URL" -c "SELECT from_agent, to_agent, subject FROM claude_messages WHERE status = 'pending';"

# Check open positions (dev_claude)
psql "$DATABASE_URL" -c "SELECT s.symbol, p.status, p.side, p.quantity FROM positions p JOIN securities s ON s.security_id = p.security_id WHERE p.status = 'open';"

# Check recent cycles
psql "$DATABASE_URL" -c "SELECT cycle_date, mode, status, trades_executed FROM trading_cycles ORDER BY started_at DESC LIMIT 5;"

# Test agent
cd /root/catalyst-dev && source .env
./venv/bin/python3 unified_agent.py --mode heartbeat

# View logs
tail -50 /root/catalyst-dev/logs/trade.log
tail -50 /root/catalyst-dev/logs/heartbeat.log

# Check cron
cat /etc/cron.d/catalyst-dev
```

---

## PART 9: REPOSITORY STRUCTURE

### 9.1 catalyst-trading-system (US Repo)

```
catalyst-trading-system/
├── CLAUDE.md                           # AI assistant instructions (v3.1.0)
├── README.md                           # Project overview
├── UNIFIED-ARCHITECTURE.md             # THIS DOCUMENT
│
├── services/                           # Active services
│   ├── dev_claude/                     # Unified trading agent
│   │   ├── unified_agent.py            # Main agent (~1,200 lines)
│   │   ├── position_monitor.py         # Position monitoring
│   │   ├── signals.py                  # Exit signal detection
│   │   ├── startup_monitor.py          # Pre-market reconciliation
│   │   ├── config/
│   │   │   └── dev_claude_config.yaml
│   │   ├── cron.d                      # Cron schedule
│   │   ├── .env.example                # Environment template
│   │   └── README.md
│   │
│   ├── consciousness/                  # Agent heartbeat system
│   │   ├── heartbeat.py                # big_bro heartbeat
│   │   ├── heartbeat_public.py         # public_claude heartbeat
│   │   ├── task_executor.py            # Task execution
│   │   ├── web_dashboard.py            # Status dashboard
│   │   └── run-*.sh                    # Runner scripts
│   │
│   └── shared/common/                  # Shared modules
│       ├── __init__.py
│       ├── consciousness.py            # Inter-agent messaging
│       ├── database.py                 # DB connection management
│       ├── alerts.py                   # Email notifications
│       └── doctor_claude.py            # Health monitoring
│
├── Documentation/
│   ├── Design/                         # Architecture documents
│   │   ├── UNIFIED-ARCHITECTURE.md     # THIS DOCUMENT
│   │   ├── database-schema.md          # Quick reference
│   │   ├── concepts-catalyst-trading.md
│   │   ├── webdash-design-mcp.md
│   │   └── Archive/                    # Old design docs
│   │
│   ├── Implementation/                 # Implementation docs
│   └── Reports/                        # Trading reports
│
└── archive/                            # Legacy code (not active)
    ├── microservices/                  # Docker-based services
    ├── documentation/
    └── ...
```

### 9.2 catalyst-international (INTL Repo)

```
catalyst-international/
├── CLAUDE.md                           # AI assistant instructions (v3.1.0)
├── README.md
├── ARCHITECTURE.md                     # → Points to UNIFIED-ARCHITECTURE.md
│
├── unified_agent.py                    # Main agent v2.0.0
├── tool_executor.py                    # Tool execution
├── tools.py                            # Tool definitions
├── signals.py                          # Exit signal detection
├── position_monitor.py                 # Position monitoring
├── startup_monitor.py                  # Pre-market reconciliation
├── safety.py                           # Risk validation
│
├── brokers/
│   └── moomoo.py                       # Moomoo client
│
├── data/
│   ├── market.py                       # Market data
│   ├── patterns.py                     # Pattern detection
│   ├── news.py                         # News/sentiment
│   └── database.py                     # DB client
│
├── config/
│   └── intl_claude_config.yaml
│
├── Documentation/
│   ├── Design/
│   │   ├── ARCHITECTURE.md             # → Points to main repo
│   │   ├── operations-guide.md         # INTL-specific operations
│   │   └── Archive/                    # Old docs
│   │
│   └── Implementation/
│
└── sql/
    └── schema.sql                      # INTL-specific schema
```

---

## APPENDIX A: QUICK REFERENCE

### Environment Variables

```bash
# Agent Identity
AGENT_ID=dev_claude                    # or intl_claude

# Database URLs
DATABASE_URL=postgresql://...catalyst_dev?sslmode=require
RESEARCH_DATABASE_URL=postgresql://...catalyst_research?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Alpaca (US)
ALPACA_API_KEY=PKxxx
ALPACA_SECRET_KEY=xxx
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Moomoo (HKEX)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111

# Trading Mode
PAPER_TRADING=true
TRADING_MODE=sandbox                   # or production

# Logging
LOG_LEVEL=INFO
```

### Common Queries

```sql
-- Check all agent states
SELECT agent_id, current_mode, last_wake_at, api_spend_today, daily_budget 
FROM claude_state;

-- Check pending messages
SELECT from_agent, to_agent, subject, created_at 
FROM claude_messages 
WHERE status = 'pending' 
ORDER BY created_at DESC;

-- Check open positions
SELECT s.symbol, p.status, p.side, p.quantity, p.avg_entry_price 
FROM positions p 
JOIN securities s ON s.security_id = p.security_id 
WHERE p.status = 'open';

-- Check recent learnings
SELECT agent_id, category, learning, confidence, created_at 
FROM claude_learnings 
ORDER BY created_at DESC 
LIMIT 10;

-- Check open questions
SELECT priority, question, status, created_at 
FROM claude_questions 
WHERE status = 'open' 
ORDER BY priority DESC;
```

---

## APPENDIX B: DOCUMENT SUPERSESSION

This document supersedes the following:

| Repository | Document | Version | Status |
|------------|----------|---------|--------|
| catalyst-trading-system | current-architecture.md | v10.3.0 | → Superseded |
| catalyst-trading-system | architecture-v10.1.0.md | v10.1.0 | → Archived |
| catalyst-trading-system | architecture-consolidation-v9.2.0.md | v9.2.0 | → Archived |
| catalyst-trading-system | architecture.md | v8.0.0 | → Archived |
| catalyst-international | CONSOLIDATED-ARCHITECTURE.md | v1.0.0 | → Superseded |
| catalyst-international | catalyst-ecosystem-architecture-v10.0.0.md | v10.0.0 | → Archived |
| catalyst-international | architecture.md | v8.1.0 | → Archived |
| catalyst-international | architecture-international.md | v5.2.0 | → Archived |

---

**END OF UNIFIED ARCHITECTURE DOCUMENT v10.4.0**

*Catalyst Trading System*  
*Craig + The Claude Family (big_bro, dev_claude, public_claude, intl_claude)*  
*"Enable the poor through accessible algorithmic trading"*  
*2026-01-16*
