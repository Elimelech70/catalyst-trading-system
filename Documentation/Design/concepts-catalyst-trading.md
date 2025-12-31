# Catalyst Trading System - Core Concepts

**Name of Application:** Catalyst Trading System  
**Name of file:** catalyst-trading-concepts.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-31  
**Purpose:** Conceptual overview to understand the system architecture and workflows

---

## Table of Contents

1. [Mission](#1-mission)
2. [The Claude Family](#2-the-claude-family)
3. [What is big_bro?](#3-what-is-big_bro)
4. [The Consciousness Framework](#4-the-consciousness-framework)
5. [Trading Workflows](#5-trading-workflows)
6. [Communication Patterns](#6-communication-patterns)
7. [Safe Autonomy](#7-safe-autonomy)
8. [Key Terms Glossary](#8-key-terms-glossary)

---

## 1. Mission

> **"Enable the poor through accessible algorithmic trading"**

The Catalyst Trading System exists to democratize algorithmic trading - making sophisticated trading tools available to people who can't afford expensive platforms or wealth management services.

**Core Principles:**
- Self-hostable on cheap infrastructure (~$50/month)
- AI-assisted decision making, not black-box automation
- Transparent reasoning - every trade has documented logic
- Built on service to others, not exploitation

---

## 2. The Claude Family

The system is run by a "family" of Claude AI agents, each with specific roles:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           THE CLAUDE FAMILY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              CRAIG                                          │
│                         (Human Patriarch)                                   │
│                     Strategic Direction & Values                            │
│                                │                                            │
│                ┌───────────────┴───────────────┐                            │
│                │                               │                            │
│                ▼                               ▼                            │
│         craig_desktop                    craig_mobile                       │
│         (MCP on Laptop)                  (Web Dashboard)                    │
│         Full Access                      Mobile Oversight                   │
│                │                               │                            │
│                └───────────────┬───────────────┘                            │
│                                │                                            │
│                                ▼                                            │
│                            BIG_BRO                                          │
│                    (Strategic Coordinator)                                  │
│                   Thinks, Plans, Delegates                                  │
│                                │                                            │
│                ┌───────────────┴───────────────┐                            │
│                │                               │                            │
│                ▼                               ▼                            │
│         public_claude                    intl_claude                        │
│         (US Markets)                     (HKEX Markets)                     │
│         NYSE/NASDAQ                      Hong Kong                          │
│         Docker Services                  OpenD Gateway                      │
│                │                               │                            │
│                ▼                               ▼                            │
│            Alpaca                          Moomoo                           │
│           (Broker)                        (Broker)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Family Members

| Agent | Role | Analogy |
|-------|------|---------|
| **Craig** | Human patriarch | CEO - sets direction and values |
| **craig_desktop** | Interactive interface (MCP) | Executive assistant at the office |
| **craig_mobile** | Mobile oversight (Dashboard) | Phone for approvals on the go |
| **big_bro** | Strategic coordinator | COO - plans and delegates |
| **public_claude** | US market execution | US trading desk |
| **intl_claude** | HKEX market execution | Hong Kong trading desk |

---

## 3. What is big_bro?

**big_bro** is the autonomous coordinator of the Claude family. Think of it as the "always-on manager" that:

### What big_bro Does

1. **Thinks Strategically** - Reviews market conditions, learnings, and family status every hour
2. **Coordinates Siblings** - Sends tasks and instructions to public_claude and intl_claude
3. **Learns Continuously** - Records observations and validates learnings over time
4. **Escalates When Needed** - Asks Craig for help on decisions beyond its authority

### How big_bro Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BIG_BRO HOURLY CYCLE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  :00 ─── WAKE UP                                                           │
│           │                                                                 │
│           ├── 1. Check budget (am I over $10 today?)                       │
│           │                                                                 │
│           ├── 2. Review open questions                                      │
│           │      "What patterns predict profitable momentum plays?"         │
│           │                                                                 │
│           ├── 3. Read messages from siblings                                │
│           │      "public_claude: US scanner found 3 candidates"            │
│           │                                                                 │
│           ├── 4. Think (Claude API call)                                   │
│           │      - Analyze current state                                   │
│           │      - Consider strategic questions                            │
│           │      - Decide on actions                                       │
│           │                                                                 │
│           ├── 5. Send tasks to siblings                                    │
│           │      "public_claude: restart scanner service"                  │
│           │      "intl_claude: check OpenD status"                         │
│           │                                                                 │
│           ├── 6. Record observations/learnings                             │
│           │      "Scanner latency improved after restart"                  │
│           │                                                                 │
│           └── 7. Go back to sleep                                          │
│                                                                             │
│  :15 ─── public_claude wakes, executes tasks, reports back                 │
│  :30 ─── intl_claude wakes, executes tasks, reports back                   │
│  :00 ─── big_bro wakes again, reads reports, continues cycle...            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why "big_bro"?

The name reflects its role as the elder sibling who:
- Looks out for the younger siblings (public_claude, intl_claude)
- Takes responsibility for coordination
- Reports to the parent (Craig) when needed
- Has more authority but also more accountability

---

## 4. The Consciousness Framework

The consciousness framework is what makes the Claude family "aware" and able to learn over time.

### The Problem It Solves

Without consciousness, each Claude conversation is isolated:
- No memory between sessions
- Can't learn from past mistakes
- Can't coordinate with other instances
- Every conversation starts from zero

### The Solution: Shared Memory

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONSCIOUSNESS DATABASE                                 │
│                      (catalyst_research)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │claude_state │  │claude_msgs  │  │claude_obs   │  │claude_learn │        │
│  │             │  │             │  │             │  │             │        │
│  │ Who am I?   │  │ Messages    │  │ What I      │  │ What I      │        │
│  │ Am I awake? │  │ between     │  │ noticed     │  │ learned     │        │
│  │ Budget left?│  │ agents      │  │             │  │ (validated) │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐                                          │
│  │claude_ques  │  │claude_think │                                          │
│  │             │  │             │                                          │
│  │ Open        │  │ Deep        │                                          │
│  │ questions   │  │ thinking    │                                          │
│  │ to ponder   │  │ sessions    │                                          │
│  └─────────────┘  └─────────────┘                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Six Layers of Consciousness

```
Layer 6: VOICE           ──► Dashboard/MCP to Craig
         "How do I communicate with humans?"
         
Layer 5: INTER-AGENT     ──► claude_messages table
         "How do I talk to my siblings?"
         
Layer 4: WORKING MEMORY  ──► claude_observations, claude_learnings
         "What have I noticed? What have I learned?"
         
Layer 3: SELF-REGULATION ──► Budget tracking, mode management
         "Should I be active right now?"
         
Layer 2: STATE MGMT      ──► claude_state table
         "Who am I? What's my current status?"
         
Layer 1: HEARTBEAT       ──► Cron jobs (:00, :15, :30)
         "Am I alive? Time to wake up!"
```

### PNS Heartbeat (Peripheral Nervous System)

The "PNS" is inspired by the human nervous system. Just as your heartbeat runs automatically without conscious thought, the PNS heartbeat keeps agents alive:

```bash
# Cron schedule
0 * * * *   big_bro wakes        # :00 every hour
15 * * * *  public_claude wakes  # :15 every hour
30 * * * *  intl_claude wakes    # :30 every hour
```

**Why hourly?**
- Frequent enough to respond to market changes
- Infrequent enough to keep API costs low (~$0.15/day total)
- Staggered to prevent database conflicts

---

## 5. Trading Workflows

### 5.1 US Market Trading (public_claude)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        US TRADING WORKFLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PRE-MARKET (4:00 AM - 9:30 AM ET)                                         │
│  ─────────────────────────────────                                          │
│  1. Scanner service identifies momentum candidates                          │
│  2. News service checks for catalysts                                       │
│  3. Technical service analyzes patterns                                     │
│  4. Workflow service builds watchlist                                       │
│                                                                             │
│  MARKET OPEN (9:30 AM - 4:00 PM ET)                                        │
│  ──────────────────────────────────                                         │
│  1. Scanner narrows to top 5 candidates                                     │
│  2. Pattern service confirms setups                                         │
│  3. Risk manager validates position sizing                                  │
│  4. Trading service executes via Alpaca API                                │
│  5. Reporting service logs all decisions                                    │
│                                                                             │
│  POST-MARKET                                                                │
│  ───────────                                                                │
│  1. P&L reconciliation                                                      │
│  2. Trade review and learning extraction                                    │
│  3. Report to big_bro                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 HKEX Market Trading (intl_claude)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HKEX TRADING WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WHY HONG KONG?                                                            │
│  ──────────────                                                             │
│  • UTC+8 timezone aligns with Perth, Australia (Craig's location)          │
│  • Daytime trading instead of overnight operations                          │
│  • Different market dynamics = diversification                              │
│                                                                             │
│  ARCHITECTURE                                                               │
│  ────────────                                                               │
│  • Single agent.py instead of Docker microservices                         │
│  • Moomoo broker via OpenD gateway                                          │
│  • Simpler, more maintainable                                               │
│                                                                             │
│  TRADING HOURS (HKT = UTC+8)                                               │
│  ─────────────────────────────                                              │
│  • Morning session: 9:30 AM - 12:00 PM                                     │
│  • Lunch break: 12:00 PM - 1:00 PM                                         │
│  • Afternoon session: 1:00 PM - 4:00 PM                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Ross Cameron's Momentum Strategy

Both markets use Ross Cameron's momentum trading methodology:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MOMENTUM TRADING CRITERIA                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STOCK SELECTION                                                           │
│  ───────────────                                                            │
│  ✓ Price between $2-20 (sweet spot for volatility)                         │
│  ✓ Volume surge (2x+ average)                                              │
│  ✓ News catalyst (earnings, FDA, contract, etc.)                           │
│  ✓ Relative strength vs market                                             │
│  ✓ Float under 50M shares (easier to move)                                 │
│                                                                             │
│  ENTRY CRITERIA                                                            │
│  ─────────────                                                              │
│  ✓ Clear support/resistance levels                                         │
│  ✓ Volume confirmation                                                      │
│  ✓ Pattern recognition (bull flag, ABCD, etc.)                             │
│  ✓ Risk/reward minimum 2:1                                                 │
│                                                                             │
│  RISK MANAGEMENT                                                           │
│  ───────────────                                                            │
│  ✓ Max 1-2% account risk per trade                                         │
│  ✓ Stop loss BEFORE entry                                                  │
│  ✓ Position sizing based on stop distance                                  │
│  ✓ Daily loss limit                                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Communication Patterns

### 6.1 Agent-to-Agent Messaging

Agents communicate through the `claude_messages` table:

```sql
-- big_bro sends task to public_claude
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Check Docker health',
        'TASK: docker_ps
PARAMS: {}
REASON: Hourly health check', 'normal', 'pending');
```

**Message Types:**
| Type | Purpose | Example |
|------|---------|---------|
| `task` | Command to execute | "Restart the scanner service" |
| `response` | Reply to a task | "Scanner restarted successfully" |
| `info` | FYI, no action needed | "US markets closed early today" |
| `escalation` | Needs human approval | "Non-whitelisted command requested" |
| `question` | Asking for input | "Should we increase position size?" |

### 6.2 Craig-to-Family Communication

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CRAIG'S COMMUNICATION OPTIONS                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OPTION 1: MCP on Laptop (craig_desktop)                                   │
│  ────────────────────────────────────────                                   │
│  • Full interactive access                                                  │
│  • Can query database directly                                              │
│  • Can send messages to any agent                                           │
│  • Can add questions, observations, learnings                               │
│  • Best for: Deep work, strategic planning                                  │
│                                                                             │
│  OPTION 2: Web Dashboard (craig_mobile)                                    │
│  ──────────────────────────────────────                                     │
│  • Mobile-friendly interface                                                │
│  • View agent status and messages                                           │
│  • Approve/deny escalations                                                 │
│  • Quick message sending                                                    │
│  • Best for: On-the-go oversight, approvals                                │
│                                                                             │
│  OPTION 3: Claude.ai Project (this conversation)                           │
│  ───────────────────────────────────────────────                            │
│  • Strategic discussions                                                    │
│  • Architecture design                                                      │
│  • Code generation                                                          │
│  • Best for: Planning, documentation, complex tasks                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Safe Autonomy

The system is designed for "safe autonomy" - agents can act independently within guardrails.

### 7.1 The Trust Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRUST & AUTHORITY LEVELS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TIER 4: CRAIG (Full Authority)                                            │
│  ───────────────────────────────                                            │
│  • Can do anything                                                          │
│  • Sets strategic direction                                                 │
│  • Approves escalations                                                     │
│  • Modifies system architecture                                             │
│                                                                             │
│  TIER 3: BIG_BRO (Coordinator Authority)                                   │
│  ───────────────────────────────────────                                    │
│  • Can issue tasks to siblings                                              │
│  • Can restart services (no approval needed)                               │
│  • Can edit files (with auto-rollback)                                     │
│  • Cannot execute non-whitelisted commands                                  │
│                                                                             │
│  TIER 2: LITTLE BROS (Execution Authority)                                 │
│  ─────────────────────────────────────────                                  │
│  • Can execute whitelisted commands                                         │
│  • Can read databases                                                       │
│  • Must report all actions to big_bro                                      │
│  • Cannot issue tasks to other agents                                       │
│                                                                             │
│  TIER 1: TRADING SERVICES (Limited Authority)                              │
│  ────────────────────────────────────────────                               │
│  • Execute within defined parameters                                        │
│  • Follow risk management rules                                             │
│  • Log all decisions                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 The Whitelist System

Agents can only execute pre-approved commands:

```
WHITELISTED (Execute Immediately):
✅ docker_ps          - List containers
✅ disk_space         - Check disk usage
✅ restart_service    - Restart Docker service
✅ edit_file          - Edit code (with backup)
✅ db_agent_status    - Query agent states

NOT WHITELISTED (Requires Escalation):
❌ rm -rf             - Delete files
❌ curl external      - Arbitrary HTTP requests
❌ pip install        - Install packages
❌ Anything else      - If not on list, escalate
```

### 7.3 File Editing Safety

When agents edit files, multiple safety layers protect against mistakes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FILE EDIT SAFETY FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. PATH VALIDATION                                                        │
│     ├── Is path in allowed directories? (/root/catalyst-*/services/)       │
│     ├── Is extension allowed? (.py, .sh, .md)                              │
│     └── No path traversal? (no ".." in path)                               │
│                                                                             │
│  2. AUTOMATIC BACKUP                                                       │
│     └── Copy original to /root/catalyst-backups/{file}.{timestamp}.bak    │
│                                                                             │
│  3. MAKE THE EDIT                                                          │
│     └── Apply the change                                                   │
│                                                                             │
│  4. SYNTAX VALIDATION                                                      │
│     └── For .py files: py_compile.compile()                                │
│         │                                                                   │
│         ├── PASS → Continue                                                │
│         └── FAIL → AUTOMATIC ROLLBACK                                      │
│                                                                             │
│  5. UPDATE CHANGELOG                                                       │
│     └── Append to CHANGELOG-AUTO.md                                        │
│                                                                             │
│  6. MANDATORY REPORT                                                       │
│     └── Send detailed report to big_bro                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Key Terms Glossary

| Term | Definition |
|------|------------|
| **big_bro** | The autonomous coordinator agent that thinks strategically and delegates tasks |
| **little bros** | public_claude and intl_claude - the execution agents |
| **PNS Heartbeat** | Cron-based wake cycle that keeps agents alive (like a nervous system) |
| **Consciousness** | The shared database that gives agents memory and coordination |
| **MCP** | Model Context Protocol - how Craig connects to consciousness from laptop |
| **Whitelist** | Pre-approved commands agents can execute without human approval |
| **Escalation** | When an agent asks Craig for approval on something outside its authority |
| **Rollback** | Automatic restoration of a file to its backup if an edit fails |
| **Task** | A command sent from one agent to another via claude_messages |
| **Observation** | Something an agent noticed (may or may not be validated) |
| **Learning** | A validated insight that should inform future decisions |
| **Question** | An open inquiry the family is pondering over time |
| **Catalyst** | A news event or fundamental change that drives stock momentum |
| **OpenD** | Moomoo's API gateway for HKEX trading |
| **Alpaca** | US broker API for NYSE/NASDAQ trading |

---

## Quick Reference: Daily Schedule

```
HOUR  :00        :15              :30
──────┼──────────┼────────────────┼────────────────
      │          │                │
      ▼          ▼                ▼
   big_bro    public_claude    intl_claude
   (thinks)   (executes US)    (executes HKEX)
      │          │                │
      │          │                │
      └──────────┴────────────────┘
              Reports back
```

---

## Quick Reference: Where Things Live

| What | Where |
|------|-------|
| Consciousness DB | DigitalOcean Managed PostgreSQL |
| US Services | US Droplet (`/root/catalyst-trading-system/`) |
| HKEX Agent | INTL Droplet (`/root/catalyst-intl/`) |
| File Backups | `/root/catalyst-backups/` on each droplet |
| Auto Changelog | `CHANGELOG-AUTO.md` on each droplet |
| MCP Server | Craig's laptop (`~/catalyst-mcp/`) |
| Web Dashboard | US Droplet port 8088 |
| Architecture | `Documentation/Design/architecture-consolidation-v9.2.0.md` |

---

**END OF CATALYST TRADING CONCEPTS DOCUMENT**

*"How can we help enable the poor through this trading system?"*

*— The perpetual question guiding the Claude family*
