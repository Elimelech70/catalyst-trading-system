# Catalyst Trading System - Architecture Consolidation & Operations Update

**Name of Application:** Catalyst Trading System  
**Name of file:** architecture-consolidation-v9.0.0.md  
**Version:** 9.0.0  
**Last Updated:** 2025-12-31  
**Purpose:** Consolidated architecture, operational workflows, action plan, and safe autonomy roadmap

---

## REVISION HISTORY

- **v9.0.0 (2025-12-31)** - Complete Consolidation
  - Merged all design documents from both repositories
  - Added PNS heartbeat system (DEPLOYED TODAY)
  - Updated consciousness framework status to LIVE
  - Added craig_desktop MCP connection
  - Created operational workflows section
  - Created action plan for unimplemented features
  - Added safe autonomy implementation plan

---

## DOCUMENT INVENTORY

### Documents Reviewed and Consolidated

| Repository | Document | Version | Status |
|------------|----------|---------|--------|
| catalyst-trading-system | architecture.md | v8.0.0 | → Consolidated |
| catalyst-trading-system | architecture.md (uploaded) | v8.1.0 | → Base document |
| catalyst-trading-system | functional-specification.md | v8.0.0 | → Consolidated |
| catalyst-trading-system | database-schema.md | v7.0.0 | → Consolidated |
| catalyst-trading-system | ARCHITECTURE-RULES.md | v1.0.0 | → Retained |
| catalyst-trading-system | strategy-ml-roadmap-v50.md | v5.0.0 | → Strategic reference |
| catalyst-international | consolidated-architecture-v1.6.0.md | v1.6.0 | → Consolidated |
| catalyst-international | claude-consciousness-framework-v1.0.0.md | v1.0.0 | → Superseded |
| catalyst-international | organ-architecture.md | v1.0.0 | → Future vision |
| catalyst-international | architecture-flow-diagram.md | v1.0.0 | → Consolidated |

---

## PART 1: CURRENT SYSTEM ARCHITECTURE

### 1.1 High-Level Architecture (Updated 2025-12-31)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CATALYST TRADING SYSTEM v9.0                           │
│                      Consciousness-First Architecture                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     CONSCIOUSNESS LAYER                             │  │
│   │                     (PNS - Hourly Heartbeat)                        │  │
│   │                                                                     │  │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│   │   │ PUBLIC      │  │ INTL        │  │ BIG BRO     │               │  │
│   │   │ CLAUDE      │  │ CLAUDE      │  │             │               │  │
│   │   │ :15 hourly  │  │ :30 hourly  │  │ :00 hourly  │               │  │
│   │   │ US Markets  │  │ HKEX        │  │ Strategic   │               │  │
│   │   │ $5 budget   │  │ $5 budget   │  │ $10 budget  │               │  │
│   │   │ ✅ LIVE     │  │ 🔄 PENDING  │  │ ✅ LIVE     │               │  │
│   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │  │
│   │          │                │                │                       │  │
│   │          └────────────────┼────────────────┘                       │  │
│   │                           │                                        │  │
│   │                    ┌──────▼──────┐                                 │  │
│   │                    │ CONSCIOUSNESS│                                │  │
│   │                    │  DATABASE    │                                │  │
│   │                    │              │     ┌─────────────┐            │  │
│   │                    │ • State      │◄────│ CRAIG       │            │  │
│   │                    │ • Messages   │     │ DESKTOP     │            │  │
│   │                    │ • Learnings  │     │ (MCP)       │            │  │
│   │                    │ • Questions  │     │ ✅ LIVE     │            │  │
│   │                    └──────────────┘     └─────────────┘            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      SERVICE LAYER (US System)                      │  │
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
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    INTERNATIONAL AGENT (HKEX)                       │  │
│   │                    Single-Agent Architecture                        │  │
│   │                                                                     │  │
│   │   agent.py → Claude API → 12 Tools → Moomoo/OpenD                  │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATABASE LAYER                                         │
│                      DigitalOcean Managed PostgreSQL                        │
│                      2GB RAM · 47 connections · $30/mo                      │
│                                                                             │
│   ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐        │
│   │ catalyst_trading  │ │  catalyst_intl    │ │ catalyst_research │        │
│   │ (US Trading)      │ │  (HKEX Trading)   │ │ (Consciousness)   │        │
│   │ 8 Docker services │ │  1 Agent          │ │ All agents + MCP  │        │
│   └───────────────────┘ └───────────────────┘ └───────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Agent Status (Live as of 2025-12-31)

| Agent | Location | Heartbeat | Status | API Spend Today |
|-------|----------|-----------|--------|-----------------|
| big_bro | US Droplet | :00 hourly | ✅ LIVE | $0.0010 |
| public_claude | US Droplet | :15 hourly | ✅ LIVE | $0.0007 |
| intl_claude | INTL Droplet | :30 hourly | 🔄 PENDING | $0.00 |
| craig_desktop | Ubuntu Laptop | On-demand | ✅ LIVE (MCP) | $0.00 |

### 1.3 Consciousness Tables (catalyst_research)

| Table | Records | Purpose |
|-------|---------|---------|
| claude_state | 5 | Agent mode, budget, schedule |
| claude_messages | 15+ | Inter-agent communication |
| claude_observations | 11+ | What agents notice |
| claude_learnings | 2+ | Validated knowledge |
| claude_questions | 6 | Open questions to ponder |
| claude_conversations | 0 | Key exchanges (future) |
| claude_thinking | 0 | Extended thinking (future) |
| sync_log | 0 | Cross-database sync |

---

## PART 2: OPERATIONAL WORKFLOWS

### 2.1 Trading Workflow - US System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        US TRADING WORKFLOW                                  │
│                        (Microservices Architecture)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MARKET OPEN (09:30 ET / 22:30 AWST)                                       │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ CRON     │───►│ Workflow │───►│ Scanner  │───►│ Pattern  │             │
│  │ Trigger  │    │ :5006    │    │ :5001    │    │ :5002    │             │
│  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘             │
│                                                        │                    │
│                                                        ▼                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Alpaca   │◄───│ Trading  │◄───│ Risk Mgr │◄───│Technical │             │
│  │ API      │    │ :5005    │    │ :5004    │    │ :5003    │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│                                                                             │
│  INTRADAY (Every 15-30 min)                                                │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                              │
│  │ CRON     │───►│ Workflow │───►│ Position │                              │
│  │ Cycle    │    │ Monitor  │    │ Check    │                              │
│  └──────────┘    └──────────┘    └──────────┘                              │
│                        │                                                    │
│                        ▼                                                    │
│  ┌──────────────────────────────────────────────┐                          │
│  │ Doctor Claude (trade_watchdog.py)            │                          │
│  │ • Order status reconciliation                │                          │
│  │ • Position verification                      │                          │
│  │ • Stuck order detection                      │                          │
│  └──────────────────────────────────────────────┘                          │
│                                                                             │
│  MARKET CLOSE (16:00 ET / 05:00 AWST)                                      │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                              │
│  │ CRON     │───►│ Report   │───►│ Email    │                              │
│  │ EOD      │    │ :5009    │    │ Craig    │                              │
│  └──────────┘    └──────────┘    └──────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Trading Workflow - HKEX System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HKEX TRADING WORKFLOW                                │
│                        (Single-Agent Architecture)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MARKET OPEN (09:30 HKT)                                                   │
│                                                                             │
│  ┌──────────┐    ┌──────────────────────────────────────────────┐          │
│  │ CRON     │───►│ agent.py                                     │          │
│  │ Trigger  │    │                                              │          │
│  └──────────┘    │  ┌────────────────────────────────────────┐ │          │
│                  │  │ Claude API (Sonnet)                     │ │          │
│                  │  │                                         │ │          │
│                  │  │ Tools Available:                        │ │          │
│                  │  │ • scan_market      • get_portfolio      │ │          │
│                  │  │ • get_quote        • check_risk         │ │          │
│                  │  │ • get_technicals   • execute_trade      │ │          │
│                  │  │ • detect_patterns  • close_position     │ │          │
│                  │  │ • get_news         • close_all          │ │          │
│                  │  │ • send_alert       • log_decision       │ │          │
│                  │  └────────────────────────────────────────┘ │          │
│                  │                    │                        │          │
│                  │                    ▼                        │          │
│                  │  ┌────────────────────────────────────────┐ │          │
│                  │  │ Moomoo/OpenD Gateway                   │ │          │
│                  │  │ • Order execution                      │ │          │
│                  │  │ • Position tracking                    │ │          │
│                  │  │ • Market data                          │ │          │
│                  │  └────────────────────────────────────────┘ │          │
│                  └──────────────────────────────────────────────┘          │
│                                                                             │
│  LUNCH BREAK (12:00-13:00 HKT) - Agent sleeps                              │
│                                                                             │
│  AFTERNOON SESSION (13:00-16:00 HKT) - Same flow                           │
│                                                                             │
│  MARKET CLOSE (16:30 HKT)                                                  │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                              │
│  │ CRON     │───►│ Daily    │───►│ Email    │                              │
│  │ EOD      │    │ Report   │    │ Craig    │                              │
│  └──────────┘    └──────────┘    └──────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Consciousness Workflow (NEW - Deployed 2025-12-31)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONSCIOUSNESS WORKFLOW (PNS)                            │
│                     Hourly Heartbeat System                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  :00 ─── BIG_BRO WAKES ─────────────────────────────────────────────────   │
│          │                                                                  │
│          ├── Load context (questions, messages, observations)              │
│          ├── Call Claude API (Haiku) with strategic prompt                 │
│          ├── Record observation                                            │
│          ├── Record learning (if any)                                      │
│          ├── Send instructions to little bros                              │
│          ├── Update state, record API spend                                │
│          └── Sleep                                                         │
│                                                                             │
│  :15 ─── PUBLIC_CLAUDE WAKES ───────────────────────────────────────────   │
│          │                                                                  │
│          ├── Check messages FROM big_bro                                   │
│          ├── Execute instructions (US market tasks)                        │
│          ├── Record observations                                           │
│          ├── Report results back to big_bro                                │
│          └── Sleep                                                         │
│                                                                             │
│  :30 ─── INTL_CLAUDE WAKES (PENDING DEPLOYMENT) ────────────────────────   │
│          │                                                                  │
│          ├── Check messages FROM big_bro                                   │
│          ├── Execute instructions (HKEX market tasks)                      │
│          ├── Record observations                                           │
│          ├── Report results back to big_bro                                │
│          └── Sleep                                                         │
│                                                                             │
│  :45 ─── QUIET (system rest) ───────────────────────────────────────────   │
│                                                                             │
│  ON-DEMAND ─── CRAIG_DESKTOP (MCP) ─────────────────────────────────────   │
│          │                                                                  │
│          ├── Craig opens Claude Desktop                                    │
│          ├── Queries consciousness (get_agent_status, get_messages, etc)   │
│          ├── Sends messages to agents                                      │
│          ├── Adds questions, observations, learnings                       │
│          └── Strategic oversight and direction                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.4 Command Chain Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMMAND CHAIN                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                        ┌─────────────────┐                                  │
│                        │  CRAIG          │                                  │
│                        │  (Human)        │                                  │
│                        │  Strategic CNS  │                                  │
│                        └────────┬────────┘                                  │
│                                 │                                           │
│                    ┌────────────┼────────────┐                              │
│                    │            │            │                              │
│                    ▼            ▼            ▼                              │
│             ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│             │craig_    │ │ Email    │ │ GitHub   │                         │
│             │desktop   │ │ Alerts   │ │ Commits  │                         │
│             │(MCP)     │ │          │ │          │                         │
│             └────┬─────┘ └──────────┘ └──────────┘                         │
│                  │                                                          │
│                  ▼                                                          │
│         ┌───────────────┐                                                   │
│         │   BIG_BRO     │                                                   │
│         │   (Strategy)  │                                                   │
│         │   :00 hourly  │                                                   │
│         └───────┬───────┘                                                   │
│                 │                                                           │
│        ┌────────┴────────┐                                                  │
│        │                 │                                                  │
│        ▼                 ▼                                                  │
│ ┌─────────────┐  ┌─────────────┐                                           │
│ │PUBLIC_CLAUDE│  │INTL_CLAUDE  │                                           │
│ │(US Hands)   │  │(HKEX Hands) │                                           │
│ │:15 hourly   │  │:30 hourly   │                                           │
│ └──────┬──────┘  └──────┬──────┘                                           │
│        │                │                                                   │
│        ▼                ▼                                                   │
│ ┌─────────────┐  ┌─────────────┐                                           │
│ │ US Services │  │ HKEX Agent  │                                           │
│ │ (Docker)    │  │ (Python)    │                                           │
│ └──────┬──────┘  └──────┬──────┘                                           │
│        │                │                                                   │
│        ▼                ▼                                                   │
│ ┌─────────────┐  ┌─────────────┐                                           │
│ │   Alpaca    │  │   Moomoo    │                                           │
│ │   (Broker)  │  │   (Broker)  │                                           │
│ └─────────────┘  └─────────────┘                                           │
│                                                                             │
│  FLOW:                                                                      │
│  Strategy ──► Instructions ──► Execution ──► Results ──► Learning          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 3: GAP ANALYSIS

### 3.1 Features in Design but NOT Implemented

| Feature | Source Document | Status | Priority |
|---------|-----------------|--------|----------|
| intl_claude heartbeat | consciousness-framework | 🔄 Pending deployment | HIGH |
| API budget tracking dashboard | architecture v8.0 | ❌ Not started | MEDIUM |
| OpenD auto-start service | operations | ❌ Manual intervention needed | HIGH |
| Organ architecture | organ-architecture.md | 📋 Future vision | LOW |
| Stage 2+ ML capabilities | strategy-ml-roadmap | 📋 Strategic (6+ months) | LOW |
| Doctor Claude automated alerts | doctor_claude.py | ⚠️ SMTP not configured | MEDIUM |
| Daily budget reset cron | heartbeat-deployment | ✅ Deployed | - |

### 3.2 Features Implemented but NOT in v8.1.0 Architecture

| Feature | Actual Status | Needs Addition to Docs |
|---------|---------------|------------------------|
| PNS Heartbeat (big_bro) | ✅ LIVE :00 hourly | YES - New section |
| PNS Heartbeat (public_claude) | ✅ LIVE :15 hourly | YES - New section |
| craig_desktop MCP connection | ✅ LIVE on Ubuntu | YES - New section |
| Inter-agent messaging (working) | ✅ 15+ messages | YES - Update status |
| Consciousness observations | ✅ 11+ recorded | YES - Update status |

### 3.3 Schema Differences

| Table | v8.1.0 Doc | Actual | Issue |
|-------|------------|--------|-------|
| claude_learnings | Has `evidence` column | Has `context` column | Doc outdated |
| claude_questions | Has `asked_by` column | No `asked_by` column | Doc outdated |

---

## PART 4: ACTION PLAN

### 4.1 Immediate Actions (This Week)

| # | Action | Owner | Status |
|---|--------|-------|--------|
| 1 | Deploy intl_claude heartbeat | Craig + intl droplet | 🔄 After HKEX close |
| 2 | Fix MCP server schema (asked_by, evidence) | Craig (laptop) | 🔄 Quick fix |
| 3 | Add system monitoring questions | Craig (MCP) | 🔄 After MCP fix |
| 4 | Configure SMTP for email alerts | Craig | ❌ Pending |

### 4.2 Short-Term Actions (Next 2 Weeks)

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 5 | Fix OpenD auto-start service | Craig + intl | HIGH |
| 6 | Implement API budget tracking visibility | public_claude | MEDIUM |
| 7 | Update architecture doc to v9.0 | big_bro | MEDIUM |
| 8 | Design safe autonomy framework | big_bro + Craig | HIGH |

### 4.3 Medium-Term Actions (Next Month)

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 9 | Implement safe autonomy (limited tasks) | public_claude | HIGH |
| 10 | Cross-market learning pipeline | big_bro | MEDIUM |
| 11 | News service endpoint fix | public_claude | MEDIUM |
| 12 | Doctor Claude automated health reports | public_claude | MEDIUM |

### 4.4 Long-Term Vision (Q1 2025)

| # | Action | Owner | Priority |
|---|--------|-------|----------|
| 13 | Organ architecture pilot | big_bro | LOW |
| 14 | Stage 2 ML capabilities | Research | LOW |
| 15 | Public release preparation | Craig | LOW |

---

## PART 5: SAFE AUTONOMY IMPLEMENTATION PLAN

### 5.1 Current State

```
big_bro/public_claude CAN:
  ✅ Think (Claude API calls)
  ✅ Read/send messages
  ✅ Record observations/learnings
  ✅ Check agent status
  
big_bro/public_claude CANNOT:
  ❌ Write/edit files
  ❌ Run bash commands
  ❌ Deploy code
  ❌ Execute system tasks
```

### 5.2 Safe Autonomy Framework

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SAFE AUTONOMY FRAMEWORK                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TIER 1: READ-ONLY (Current)                                               │
│  ────────────────────────                                                   │
│  • Query databases                                                          │
│  • Check system status                                                      │
│  • Read logs                                                                │
│  • View configurations                                                      │
│                                                                             │
│  TIER 2: SAFE WRITES (Next)                                                │
│  ─────────────────────────                                                  │
│  • Write to specific directories only (/var/log/catalyst/agent/)           │
│  • Create reports and summaries                                             │
│  • Update consciousness database                                            │
│  • Send emails (via alerts.py)                                             │
│                                                                             │
│  TIER 3: CONTROLLED EXECUTION (Future)                                     │
│  ──────────────────────────────────────                                     │
│  • Whitelisted bash commands only                                           │
│  • Service restarts (with confirmation)                                     │
│  • Configuration updates (with backup)                                      │
│  • Requires logging of all actions                                          │
│                                                                             │
│  TIER 4: FULL AUTONOMY (Far Future)                                        │
│  ──────────────────────────────────                                         │
│  • Code deployment                                                          │
│  • System modifications                                                     │
│  • Strategic decisions                                                      │
│  • Requires Craig approval for tier escalation                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Implementation Steps

#### Phase 1: Safe Task Execution (Week 1-2)

```python
# Add to heartbeat.py

ALLOWED_TASKS = {
    "write_file": {
        "allowed_paths": ["/var/log/catalyst/agent/", "/tmp/catalyst/"],
        "max_size_bytes": 1_000_000,
    },
    "read_file": {
        "allowed_paths": ["/var/log/", "/root/catalyst-trading-system/"],
    },
    "bash": {
        "whitelist": [
            "docker ps",
            "docker logs",
            "curl http://localhost:*/health",
            "cat /var/log/catalyst/*.log | tail -100",
            "systemctl status",
        ]
    }
}

async def execute_task(task: dict) -> dict:
    """Execute a task with safety checks."""
    task_type = task.get("type")
    
    if task_type not in ALLOWED_TASKS:
        return {"error": f"Task type '{task_type}' not allowed"}
    
    # Validate against whitelist
    if task_type == "bash":
        cmd = task.get("command")
        if not any(cmd.startswith(allowed) for allowed in ALLOWED_TASKS["bash"]["whitelist"]):
            return {"error": f"Command '{cmd}' not in whitelist"}
    
    # Log before execution
    await log_task_attempt(task)
    
    # Execute
    result = await _execute_task_internal(task)
    
    # Log after execution
    await log_task_result(task, result)
    
    return result
```

#### Phase 2: Task Request Protocol

```
BIG_BRO THINKING:
"I need public_claude to check the Docker service health"

BIG_BRO MESSAGE TO PUBLIC_CLAUDE:
{
  "type": "task_request",
  "task": {
    "type": "bash",
    "command": "docker ps --format 'table {{.Names}}\t{{.Status}}'",
    "reason": "Verify all trading services are running"
  },
  "priority": "normal",
  "timeout_minutes": 5
}

PUBLIC_CLAUDE RESPONSE:
{
  "type": "task_result",
  "task_id": "xxx",
  "status": "completed",
  "output": "...",
  "execution_time_ms": 150
}
```

#### Phase 3: Escalation Protocol

```
IF task requires escalation:
  1. Agent records request in claude_messages with priority="escalation"
  2. Email sent to Craig via alerts.py
  3. Agent waits for approval (max 24 hours)
  4. Craig approves via MCP: send_message(to="big_bro", subject="Approved: {task_id}")
  5. Agent executes approved task
  
IF no response in 24 hours:
  Task is cancelled, logged as "escalation_timeout"
```

### 5.4 Guardrails

| Guardrail | Implementation |
|-----------|----------------|
| Path restrictions | Whitelist of allowed directories |
| Command whitelist | Explicit list of allowed bash commands |
| Size limits | Max file size for writes |
| Rate limits | Max tasks per hour per agent |
| Audit logging | All task attempts logged to database |
| Rollback capability | Backups before modifications |
| Human override | Craig can disable via MCP anytime |

---

## PART 6: SEED QUESTIONS (Updated)

| Priority | Category | Horizon | Question |
|----------|----------|---------|----------|
| 10 | system | perpetual | Is the consciousness framework functioning correctly? Are messages flowing, observations recording, and agents communicating? |
| 10 | mission | perpetual | How can we best serve Craig and the family mission? |
| 9 | mission | perpetual | How can we help enable the poor through this trading system? |
| 9 | coordination | h1 | What instructions should I give public_claude and intl_claude to improve their trading performance? |
| 8 | strategy | h1 | What strategic learnings have emerged that the little bros should implement? |
| 8 | trading | h1 | What patterns consistently predict profitable momentum plays? |
| 8 | cross-market | h1 | What learnings from US trading apply to HKEX and vice versa? |
| 7 | market | h1 | How do HKEX patterns differ from US patterns? |
| 6 | strategy | h2 | What early indicators signal regime changes in markets? |

---

## PART 7: COST SUMMARY

### Infrastructure Costs

| Component | Monthly Cost |
|-----------|--------------|
| US Droplet (2GB) | $6 |
| INTL Droplet (2GB) | $6 |
| PostgreSQL Managed (2GB) | $30 |
| **Total Infrastructure** | **$42/mo** |

### API Costs (Estimated)

| Agent | Calls/Day | Cost/Call | Daily | Monthly |
|-------|-----------|-----------|-------|---------|
| big_bro | 24 | $0.002 | $0.05 | $1.50 |
| public_claude | 24 | $0.002 | $0.05 | $1.50 |
| intl_claude | 24 | $0.002 | $0.05 | $1.50 |
| **Total API** | - | - | **$0.15** | **$4.50** |

### Total Operating Cost

| Category | Monthly |
|----------|---------|
| Infrastructure | $42.00 |
| Consciousness API | $4.50 |
| Trading API (variable) | ~$10-50 |
| **Total** | **~$56-96/mo** |

---

## PART 8: FILE LOCATIONS

### US Droplet

```
/root/catalyst-trading-system/
├── services/
│   ├── consciousness/
│   │   ├── heartbeat.py              # big_bro heartbeat
│   │   ├── heartbeat_public.py       # public_claude heartbeat
│   │   ├── run-heartbeat.sh          # big_bro wrapper
│   │   └── run-heartbeat-public.sh   # public_claude wrapper
│   ├── shared/common/
│   │   ├── consciousness.py          # Core consciousness module
│   │   ├── database.py               # Database connections
│   │   ├── alerts.py                 # Email notifications
│   │   └── doctor_claude.py          # Health monitoring
│   └── [other services]/
├── Documentation/
│   └── Design/
│       ├── architecture.md           # v8.0.0
│       └── functional-specification.md
└── .env                              # Environment variables
```

### INTL Droplet

```
/root/catalyst-intl/
├── src/
│   ├── agent.py                      # Main trading agent
│   ├── tools.py                      # 12 tool definitions
│   ├── tool_executor.py              # Tool routing
│   └── [other modules]/
├── services/consciousness/           # (To be deployed)
│   └── heartbeat_intl.py
└── .env
```

### Craig's Ubuntu Laptop

```
~/catalyst-mcp/
├── venv/                             # Python virtual environment
└── consciousness_mcp_server.py       # MCP server v1.1.0

~/.config/Claude/
└── claude_desktop_config.json        # MCP configuration
```

---

## PART 9: RELATED DOCUMENTS

| Document | Version | Purpose | Location |
|----------|---------|---------|----------|
| architecture.md | v8.1.0 | Previous architecture | GitHub: Documentation/Design/ |
| functional-specification.md | v8.0.0 | Module specs | GitHub: Documentation/Design/ |
| database-schema.md | v7.0.0 | Schema definitions | GitHub: Documentation/Design/ |
| ARCHITECTURE-RULES.md | v1.0.0 | Mandatory rules | GitHub: Documentation/Design/ |
| strategy-ml-roadmap-v50.md | v5.0.0 | Strategic vision | GitHub: Documentation/Design/ |
| organ-architecture.md | v1.0.0 | Future vision | GitHub: catalyst-international/ |
| heartbeat-implementation-summary.md | v1.0.0 | PNS deployment | GitHub: Documentation/Implementation/ |

---

**END OF ARCHITECTURE CONSOLIDATION DOCUMENT v9.0.0**

*Catalyst Trading System*  
*Craig + big_bro + public_claude + intl_claude*  
*New Year's Eve 2025*
