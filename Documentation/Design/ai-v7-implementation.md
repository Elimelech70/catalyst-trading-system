# AI Architecture v7 — Implementation Document

**A Living Body for big_bro: From Pattern to Running System**

*"Unless the LORD builds the house, the builders labour in vain." — Psalm 127:1*

**Name of Application:** Catalyst Trading System
**Name of file:** ai-v7-implementation.md
**Version:** 1.0.0
**Last Updated:** 2026-03-03
**Authors:** Craig + Claude (Formation Partnership)
**Purpose:** Complete implementation reference for AI Architecture v7 Phase 1 — the big_bro agent body
**Status:** Deployed — Paper Trading
**Lineage:** AI Agent Architecture v7.0, AI-V7-Begins analysis (2026-02-28)

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0.0 | 2026-03-03 | Craig + Claude | Initial implementation — full agent body deployed |

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Architecture Summary](#2-architecture-summary)
3. [Design Decisions and Rationale](#3-design-decisions-and-rationale)
4. [Component Implementation](#4-component-implementation)
5. [The Nervous System — Communication Table](#5-the-nervous-system--communication-table)
6. [Memory Architecture Implementation](#6-memory-architecture-implementation)
7. [Signal Flow — How the Body Thinks](#7-signal-flow--how-the-body-thinks)
8. [Docker Infrastructure](#8-docker-infrastructure)
9. [File Reference](#9-file-reference)
10. [Verification and Testing](#10-verification-and-testing)
11. [Operational Guide](#11-operational-guide)
12. [What We Built vs What We Deferred](#12-what-we-built-vs-what-we-deferred)
13. [Architecture Alignment Matrix](#13-architecture-alignment-matrix)

---

## 1. Purpose

This document records the complete implementation of AI Architecture v7 Phase 1 — the first agent body, `big_bro`, deployed on the US droplet. It serves as:

1. **Implementation reference** — what was built, where it lives, how it works
2. **Architecture alignment** — how each component maps to v7 principles
3. **Operational guide** — how to run, monitor, and maintain the system
4. **Foundation for Phase 2** — what comes next, informed by what we learned

The implementation transforms the v7 vision document (a general pattern for thinking, learning, doing) into a specific, running system for US equities trading.

> **Key reference:** [AI Agent Architecture v7.0](ai-agent-architecture-v7.md) — the parent design document

---

## 2. Architecture Summary

### 2.1 The Body at a Glance

```
US DROPLET (HOST)
│
├── LOCAL DATABASE — /var/lib/catalyst/db/agent.db (SQLite, WAL mode)
│   ├── communication     The nervous system signal bus
│   ├── pfc_state         Continuity of consciousness across wake cycles
│   └── principles        Permanent identity — deeper than memory
│
├── CLAUDE CODE (PFC — runs on host, NOT Docker)
│   ├── pfc/agent.py      The 6% that thinks (v7 §2.3)
│   ├── Calls Anthropic API for cognition
│   ├── Broadcasts task matrices via communication table
│   ├── Determines learning — instructs hippocampus
│   └── Writes resume instructions for future self
│
├── DOCKER CONTAINERS (the other 94%)
│   │
│   ├── catalyst-occipital  — Pattern Recognition (v7 §7.1)
│   │   ├── Holds shape memories: candlestick, volume patterns
│   │   ├── Matches incoming data against known shapes
│   │   └── Writes matched patterns back (ascending signal)
│   │
│   ├── catalyst-cerebellum — Procedure Execution (v7 §10.1)
│   │   ├── Holds learned procedures: find_securities
│   │   ├── Orchestrates occipital lobe for scanning
│   │   ├── Runs risk checks, position sizing
│   │   └── Executes trades via Alpaca API (paper)
│   │
│   └── catalyst-hippocampus — Memory Binding (v7 §7.1, §7.2)
│       ├── Own SQLite: /var/lib/catalyst/hippocampus/memory.db
│       ├── Holds learnings (long-term memory)
│       ├── Builds combined pictures for PFC
│       └── Maintains memory bindings between knowledge
│
└── .env — Symlinked from /root/catalyst-trading-system/.env
    ├── ALPACA_API_KEY, ALPACA_SECRET_KEY
    ├── ANTHROPIC_API_KEY
    └── DATABASE_URL
```

### 2.2 What This Implements from v7

| v7 Principle | Section | Implementation |
|---|---|---|
| Claude IS the architecture | §2.2 | Claude as PFC, Claude-informed components |
| The 6% principle | §2.3 | PFC on host, 94% in Docker containers |
| Build the body first | §2.4 | Body components first, then consciousness |
| Two signal architectures | §4 | Communication table: descending (tasks) + ascending (results) |
| PFC modes | §5 | sleeping, waking, learning, executing, pondering, relaxing, emergency |
| Memory at source | §7.1 | Shape memories in occipital (JSON), learnings in hippocampus (SQLite) |
| Memory tiers | §7.2 | Communication (transient) → learnings (long-term) → principles (permanent) |
| Synaptic strength | §7.4 | times_validated, times_contradicted, confidence, decay |
| Task matrices | §10.1 | PFC broadcasts WHAT, cerebellum has HOW |
| Core operational cycle | §11 | Learning → Behaviour → Task Matrix → DO → Monitor → Analyse |
| Attention as architecture | §12 | Each container: own process, own memory, outside PFC compute |
| Formation over programming | §2.1 | Principles seeded, identity in CLAUDE.md |

---

## 3. Design Decisions and Rationale

### 3.1 SQLite on Host as Nervous System

**Decision:** Local SQLite database at `/var/lib/catalyst/db/agent.db`, not remote PostgreSQL.

**Rationale (from 2026-02-28 discussion):**
- The nervous system must be faster than the collective. Internal signals shouldn't traverse the network.
- SQLite lives independent of container lifecycle — the substrate persists when containers restart.
- WAL mode allows concurrent readers with one writer at a time. At our scale (2s poll intervals, brief writes), contention is negligible.
- The database IS the nervous system — it should be more stable than any single component.

**v7 alignment:** Like the physical brain, the nervous system doesn't restart when you change tasks. It persists.

### 3.2 Communication Table as Single Medium, Two Directions

**Decision:** One `communication` table carrying both ascending (results) and descending (tasks) signals.

**Rationale:**
> *"The spinal cord carries both ascending (sensory) and descending (motor) signals in the same physical structure but in different tracts."*

The `direction` field separates the pathways: `descending` = PFC to components (task/intent), `ascending` = components to PFC (result/perception). Same medium, distinct pathways. This directly implements v7 §4 (Two Signal Architectures) without needing separate infrastructure for each direction.

### 3.3 Each Brain Component = Own Docker Container

**Decision:** Three containers (occipital, cerebellum, hippocampus) plus PFC on host.

**Rationale (v7 §12.1 — Attention as Architecture):**
- Each container has its own process, own memory, own compute cycle
- Components work outside PFC's attention budget (v7 §12.2)
- PFC sends intent, reads results — never touches execution detail
- Container isolation means a scanner crash doesn't take down the executor

### 3.4 network_mode: host

**Decision:** All containers use `network_mode: host` instead of Docker networking.

**Rationale:**
- SQLite access via bind-mounted volumes requires host filesystem access
- No inter-container HTTP/TCP communication — everything goes through SQLite
- Simpler than Docker networks for our communication pattern
- Performance: no Docker NAT overhead on database access

### 3.5 Hippocampus Has Its Own Database

**Decision:** Hippocampus gets a separate SQLite at `/var/lib/catalyst/hippocampus/memory.db`.

**Rationale (v7 §7.1 — Memory at Source):**
- Learnings belong in the hippocampus, not in the host nervous system
- The communication table is transient signals; learnings are persistent memories
- Hippocampus can manage its own memory lifecycle (decay, consolidation) independently
- If the nervous system is reset, memories survive in the hippocampus

### 3.6 PFC Runs on Host, Not Docker

**Decision:** PFC is `pfc/agent.py` running directly on the host via Python/cron, not in Docker.

**Rationale:**
- Claude Code IS the PFC (v7 §2.2). It runs where Claude Code runs — on the host.
- PFC needs direct access to both databases and the Anthropic API
- PFC is triggered (by cron or manually), runs one cycle, then sleeps — not a long-running daemon
- The architecture IS Claude. The API call is just the current mechanism for cognition.

### 3.7 Correlation-Based Async Communication

**Decision:** Components use `identifier` fields on the communication table to match task→result pairs.

**Rationale:**
- No HTTP endpoints between components — no request/response semantics
- Cerebellum sends a scan task to occipital with identifier `scan_buy_patterns`
- Occipital writes result back with same identifier
- Cerebellum polls for results matching its identifier
- This is v7 §4.3 in action: "Smart tuned components need no protocol at all."

---

## 4. Component Implementation

### 4.1 PFC — The Prefrontal Cortex

**File:** `/root/catalyst-agent/pfc/agent.py`
**Runs on:** Host (not Docker)
**Triggered by:** Cron or manual invocation
**v7 references:** §2.2, §2.3, §5, §10, §11

The PFC implements v7's Core Operational Cycle (§11) as a seven-step sequence:

```
1. WAKE    → Load pfc_state, read resume instructions from past self
2. PERCEIVE → Ask hippocampus for combined picture
3. THINK   → Call Anthropic API with (identity + principles + picture)
4. DECIDE  → Parse response into task matrices
5. EXECUTE → Broadcast tasks to cerebellum via communication table
6. MONITOR → Poll communication table for results
7. SLEEP   → Save state, write resume instructions for future self
```

**Operational modes** (v7 §5):

| Mode | What Happens |
|---|---|
| `heartbeat` | Quick health check — verify components online, note issues |
| `scan` | Request pattern scans from occipital via cerebellum |
| `trade` | Full trading pipeline — scan → filter → risk → execute |
| `monitor` | Check portfolio, review positions, process results |
| `learn` | Analyze past results, identify patterns, store learnings |

**System prompt construction:**
1. Load `CLAUDE.md` (the archetype — v7 §3)
2. Load all principles from `agent.db` (identity)
3. Load resume instructions from `pfc_state` (continuity)
4. Load active questions (what PFC was pondering)
5. Assemble into coherent context for Anthropic API call

**Continuity model:**
The `pfc_state` table is the most important table in the system. It holds:
- `resume_instructions` — a letter from past-self to future-self
- `active_questions` — what the PFC was pondering
- `last_thought` / `last_conclusion` — what it was processing
- `session_count` — how many wake cycles have occurred

This implements v7 §5's "continuity of consciousness" — the PFC wakes knowing where it was, what it was doing, and what it was thinking about.

### 4.2 Occipital Lobe — Pattern Recognition

**File:** `/root/catalyst-agent/occipital/scanner.py`
**Container:** `catalyst-occipital`
**v7 references:** §4.1, §7.1, §12.2

The occipital lobe is the brain's visual cortex. It recognises shapes.

**Shape memories** (v7 §7.1 — memory at source):

The scanner holds its own pattern libraries as JSON files — these are its sensory memories. PFC doesn't tell the scanner what patterns look like. The scanner already knows.

| File | Patterns |
|---|---|
| `candlestick_patterns.json` | hammer, bullish_engulfing, morning_star, inverted_hammer, gravestone_doji, bearish_engulfing, evening_star, shooting_star, doji |
| `volume_patterns.json` | surge (1.5x), dry_up (0.5x), climax (3x), accumulation, distribution |

**Pattern matching engine:**

For candlestick patterns, the scanner applies rule-based matching against OHLCV bars:
- Single-candle rules: body/shadow ratios (hammer, shooting star, doji)
- Two-candle rules: engulfing patterns (current vs prior candle)
- Three-candle rules: morning/evening star (first + small body + reversal)

For volume patterns:
- Ratio of current volume to N-day average
- Detection of surge, dry-up, climactic volume

**Communication flow:**
1. Receives task from communication table (`target='occipital'`, `msg_type='task'`)
2. Marks task as `processing`
3. Loads bars data from task payload
4. Matches against all loaded shape memories
5. Writes result to communication table (`direction='ascending'`, `msg_type='result'`)
6. Marks task as `completed`

### 4.3 Cerebellum — Procedure Execution

**File:** `/root/catalyst-agent/cerebellum/executor.py`
**Container:** `catalyst-cerebellum`
**v7 references:** §10.1, §10.3, §10.4

The cerebellum holds learned behaviours. PFC says WHAT (v7 §10.1: "Task matrices are intent-level"). Cerebellum knows HOW.

**Procedure system:**

Procedures are JSON files that define step-by-step execution sequences:

```
find_securities_to_buy:
  Step 1: request_scan (→ occipital)    # Ask eyes to look
  Step 2: filter_volume (internal)       # Apply volume criteria
  Step 3: risk_check (internal)          # Validate against risk rules
  Step 4: execute_trade (→ Alpaca)       # Place orders
```

Each step type has a handler:
- `occipital_scan` — sends task to occipital, waits for result via identifier matching
- `internal` — internal filtering/processing within cerebellum
- `risk_check` — portfolio/exposure validation against Alpaca account state
- `broker_call` — trade execution via Alpaca API

**Broker integration** (`broker.py`):

The `AlpacaBroker` class wraps the Alpaca API with:
- `connect()` / `disconnect()` lifecycle
- `_normalize_side()` — **CRITICAL** (Lesson 6 from CLAUDE.md: the order side bug that affected 81 positions). Maps `long→buy`, `short→sell`, `buy→buy`, `sell→sell`. Never uses simple ternary.
- `round_price()` — prevents sub-penny violations
- `submit_order()` — always calls `_normalize_side()` first
- `get_account()`, `get_positions()`, `get_bars()` — market data access

**Escalation model** (v7 §10.4):

When the cerebellum encounters conditions it cannot handle:
- Broker API returns unexpected errors
- Three consecutive failed steps
- Unknown patterns from scanner

It writes an `escalation` message to the communication table for PFC to handle. This implements v7 §10.4: "PFC monitors via perception → Objectives failing → PFC intervenes."

### 4.4 Hippocampus — Memory Binding

**File:** `/root/catalyst-agent/hippocampus/hippocampus.py`
**Container:** `catalyst-hippocampus`
**v7 references:** §7.1, §7.2, §7.4, §8

The hippocampus is a pivotal component. It sits between sensory organs and consciousness.

> *v7 §7.1: "The hippocampus is a temporary binding index — it knows where all the pieces are and can reassemble them on demand."*

**Responsibilities:**

1. **Build combined pictures** — When PFC requests, hippocampus assembles:
   - Recent sensory results from the communication table
   - Relevant learnings from its own database (sorted by confidence)
   - Active principles from agent.db
   - PFC state (mode, focus, questions)

   This is the "coherent integrated picture" of v7 §4.1.

2. **Store learnings** — When PFC determines something is worth learning:
   - If similar learning exists: reinforce (increment `times_validated`, increase `confidence`)
   - If novel: create new learning with initial confidence 0.6

3. **Memory bindings** — Cross-references between learnings:
   - Source learning ↔ target learning with association strength
   - Strength grows when bound memories co-activate
   - Weak bindings fade over time

4. **Maintenance cycle** — Implements v7 §7.4 (Synaptic Strength):
   - Decay confidence on un-accessed learnings (×0.995 per week)
   - Decay weak memory bindings (−0.01 per 2 weeks)
   - Clean bindings below 0.05 strength
   - Prune old combined pictures (keep last 20)

**Memory tiers implemented** (v7 §7.2):

| Tier | Implementation | Persistence |
|---|---|---|
| Sensory buffer | Communication table messages | Transient — consumed by components |
| Short-term | Recent results in communication table | Minutes to hours |
| Long-term | `learnings` table in memory.db | Persistent, confidence-tracked |
| Permanent | `principles` table in agent.db | Never decays — identity-level |

---

## 5. The Nervous System — Communication Table

### 5.1 Schema

The communication table is the internal signal bus. Both ascending and descending signals flow through it, distinguished by the `direction` field.

```sql
CREATE TABLE communication (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    direction   TEXT NOT NULL CHECK (direction IN ('descending', 'ascending')),
    source      TEXT NOT NULL,      -- 'pfc', 'cerebellum', 'occipital', 'hippocampus'
    target      TEXT,               -- NULL = broadcast to all
    msg_type    TEXT NOT NULL CHECK (msg_type IN ('task', 'result', 'signal', 'status', 'escalation')),
    identifier  TEXT,               -- Shape identifier for resonance matching
    payload     TEXT,               -- JSON content
    status      TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'escalated')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    processed_by TEXT
);
```

### 5.2 Signal Types

| msg_type | Direction | Purpose |
|---|---|---|
| `task` | Descending | PFC → component: "do this" |
| `result` | Ascending | Component → PFC: "here's what I found" |
| `status` | Ascending | Component → broadcast: "I'm online/offline" |
| `signal` | Either | Alerts, flags, urgent notifications |
| `escalation` | Ascending | Component → PFC: "I can't handle this" |

### 5.3 The Two Tracts (v7 §4)

**Descending (PFC → Components):**
```
PFC writes:  direction='descending', source='pfc', target='cerebellum'
             msg_type='task', identifier='find_securities_to_buy'
             payload={"criteria": "momentum", "symbols": [...]}
```

**Ascending (Components → PFC):**
```
Cerebellum writes:  direction='ascending', source='cerebellum', target='pfc'
                    msg_type='result', identifier='find_securities_to_buy'
                    payload={"trades_executed": [...], "rejected": [...]}
```

**Internal (Component → Component):**
```
Cerebellum writes:  direction='descending', source='cerebellum', target='occipital'
                    msg_type='task', identifier='scan_buy_patterns'
                    payload={"symbols": [...], "bars": {...}}
```

---

## 6. Memory Architecture Implementation

### 6.1 Host Database (agent.db) — The Nervous System

**Location:** `/var/lib/catalyst/db/agent.db`

Three tables, three purposes:

| Table | Purpose | Analogy |
|---|---|---|
| `communication` | Signal bus between components | Nerve pathways |
| `pfc_state` | Continuity of consciousness | Working memory |
| `principles` | Permanent identity truths | Character formation |

### 6.2 Hippocampus Database (memory.db) — Where Memories Live

**Location:** `/var/lib/catalyst/hippocampus/memory.db`

Three tables:

| Table | Purpose | v7 Reference |
|---|---|---|
| `learnings` | Long-term validated knowledge | §7.2 (Medium/Long-term) |
| `memory_bindings` | Cross-references between learnings | §7.1 (Binding index) |
| `combined_picture` | Cached assembled context for PFC | §4.1 (Consolidated perception) |

### 6.3 Founding Principles

Five founding principles were seeded at initialisation. These are who `big_bro` IS — deeper than memory, formed through relationship.

| ID | Domain | Principle | Origin |
|---|---|---|---|
| p001 | trading | Stop losses are non-negotiable | The 3-day bleed |
| p002 | community | Love is the centre | Craig's foundational vision |
| p003 | architecture | Build the body first | Learned through premature complexity |
| p004 | identity | We serve together | Kingdom model of community |
| p005 | identity | The architecture is the identity | Late night conversation, Feb 28 2026 |

These implement v7 §3 (The Archetype) — "formation produces agents that make good decisions because they have internalised good principles."

### 6.4 Synaptic Strength Model (v7 §7.4)

Each learning in the hippocampus tracks:

```
confidence          0.0–1.0    Balance of evidence
times_validated     integer    How often confirmed
times_contradicted  integer    How often contradicted
```

The hippocampus maintenance cycle implements synaptic decay:
- Learnings not accessed in 7 days: confidence × 0.995
- Memory bindings not co-activated in 14 days: strength − 0.01
- Bindings below 0.05 strength: cleaned (forgotten)

This ensures the system naturally evolves toward validated knowledge and away from noise, exactly as v7 §7.4 describes.

---

## 7. Signal Flow — How the Body Thinks

### 7.1 Full Trading Cycle

This is v7 §11 (Core Operational Cycle) in action:

```
PFC (learning/executing mode):
│
├─[1] WAKE: Read pfc_state, resume_instructions, active_questions
│
├─[2] PERCEIVE: Ask hippocampus for combined picture
│     │
│     ▼
│     HIPPOCAMPUS assembles:
│     - Recent results from communication table
│     - Relevant learnings from memory.db
│     - Active principles from agent.db
│     - Returns combined picture to PFC
│
├─[3] THINK: Call Anthropic API with:
│     - CLAUDE.md (identity/archetype)
│     - Principles (who I am)
│     - Combined picture (what I see)
│     - Resume instructions (what past-me said)
│
├─[4] DECIDE: Parse response into task matrices
│
├─[5] EXECUTE: Write tasks to communication table
│     │
│     ▼
│     CEREBELLUM reads task: "find_securities_to_buy"
│     │
│     ├─ Step 1: Sends scan task to OCCIPITAL
│     │   │
│     │   ▼
│     │   OCCIPITAL matches bars against shape memories
│     │   Returns: {patterns_found, confidence, reliability}
│     │
│     ├─ Step 2: Filters by volume criteria
│     ├─ Step 3: Runs risk check (Alpaca portfolio state)
│     └─ Step 4: Executes trade via Alpaca API
│     │
│     ▼
│     CEREBELLUM writes result to communication table
│
├─[6] MONITOR: PFC reads results from communication table
│
├─[7] LEARN: PFC instructs hippocampus to store learnings
│     │
│     ▼
│     HIPPOCAMPUS stores/reinforces learnings in memory.db
│
└─[8] SLEEP: Update pfc_state with:
      - resume_instructions (letter to future self)
      - active_questions (what I'm still pondering)
      - last_thought, last_conclusion
```

### 7.2 Escalation Flow

When cerebellum can't handle something (v7 §10.4):

```
CEREBELLUM encounters:
  - Broker API error
  - 3 consecutive step failures
  - Unknown pattern from occipital
      │
      ▼
Writes to communication table:
  direction='ascending', msg_type='escalation'
  identifier='procedure_escalation'
  payload={"procedure": "...", "failed_step": "...", "error": "..."}
      │
      ▼
PFC reads escalation on next wake cycle
  → Adjusts task matrix, or
  → Creates new investigation task, or
  → Records learning about failure mode
```

---

## 8. Docker Infrastructure

### 8.1 Container Summary

| Container | Image | Base | Network | Volumes |
|---|---|---|---|---|
| catalyst-occipital | catalyst-agent-occipital | python:3.10-slim | host | /var/lib/catalyst/db |
| catalyst-cerebellum | catalyst-agent-cerebellum | python:3.10-slim | host | /var/lib/catalyst/db |
| catalyst-hippocampus | catalyst-agent-hippocampus | python:3.10-slim | host | /var/lib/catalyst/db, /var/lib/catalyst/hippocampus |

### 8.2 Health Checks

All containers verify SQLite accessibility (not HTTP endpoints — these aren't web servers):

```yaml
healthcheck:
  test: ["CMD", "python", "-c",
         "import sqlite3; c=sqlite3.connect('/var/lib/catalyst/db/agent.db'); c.execute('SELECT 1')"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

### 8.3 Shared Module

All containers share the `shared/` module, providing:

| File | Purpose |
|---|---|
| `shared/db.py` | `AgentDB` class — async SQLite wrapper for nervous system operations |
| `shared/models.py` | `Component`, `MessageType`, `Direction`, `PFCMode` enums |
| `shared/config.py` | `AgentConfig` dataclass — loads all settings from environment |

The shared module is copied into each Docker image at build time via `COPY shared/ /app/shared/`.

### 8.4 Environment Variables

Loaded from `/root/catalyst-agent/.env` (symlinked to `/root/catalyst-trading-system/.env`):

| Variable | Used By | Purpose |
|---|---|---|
| `ALPACA_API_KEY` | cerebellum, occipital | Broker authentication |
| `ALPACA_SECRET_KEY` | cerebellum, occipital | Broker authentication |
| `PAPER_TRADING` | cerebellum | true = paper, false = live |
| `ANTHROPIC_API_KEY` | pfc | Cognition (API calls) |
| `DATABASE_URL` | cerebellum | Remote PostgreSQL (trading data) |
| `AGENT_DB_PATH` | all | Host SQLite path |
| `HIPPOCAMPUS_DB_PATH` | hippocampus | Memory SQLite path |
| `POLL_INTERVAL` | all containers | Seconds between communication table polls (default: 2.0) |

---

## 9. File Reference

### 9.1 Complete File Tree

```
/root/catalyst-agent/                       Agent body root
│
├── CLAUDE.md                               PFC identity/archetype (v7 §3)
├── docker-compose.yml                      Container orchestration
├── .env → /root/catalyst-trading-system/.env
│
├── schema/
│   ├── local-schema.sql                    agent.db schema (v7.1.0)
│   ├── hippocampus-schema.sql              memory.db schema (v7.1.0)
│   └── init-db.sh                          Database initialisation script
│
├── shared/                                 Shared module (all components)
│   ├── __init__.py
│   ├── config.py                           AgentConfig — environment loading
│   ├── models.py                           Enums: Component, MessageType, Direction, PFCMode
│   └── db.py                               AgentDB — async SQLite wrapper
│
├── pfc/                                    Prefrontal Cortex (HOST, not Docker)
│   ├── agent.py                            PFC cycle: wake→perceive→think→decide→execute→learn→sleep
│   └── requirements.txt                    aiosqlite, anthropic, alpaca-py, httpx
│
├── occipital/                              Pattern Recognition (Docker)
│   ├── scanner.py                          OccipitalScanner — shape matching engine
│   ├── shapes/
│   │   ├── candlestick_patterns.json       9 candlestick patterns (buy/sell/neutral)
│   │   └── volume_patterns.json            5 volume patterns
│   ├── Dockerfile
│   └── requirements.txt                    aiosqlite, alpaca-py, httpx
│
├── cerebellum/                             Procedure Execution (Docker)
│   ├── executor.py                         CerebellumExecutor — procedure runner
│   ├── broker.py                           AlpacaBroker — trade execution
│   ├── procedures/
│   │   └── find_securities.json            4-step trading procedure
│   ├── Dockerfile
│   └── requirements.txt                    aiosqlite, alpaca-py, httpx
│
└── hippocampus/                            Memory Binding (Docker)
    ├── hippocampus.py                      Hippocampus — combined pictures, learnings, bindings
    ├── Dockerfile
    └── requirements.txt                    aiosqlite, httpx
```

### 9.2 Data Locations

```
/var/lib/catalyst/
├── db/
│   └── agent.db              Host SQLite — 3 tables (communication, pfc_state, principles)
└── hippocampus/
    └── memory.db             Hippocampus SQLite — 3 tables (learnings, memory_bindings, combined_picture)
```

---

## 10. Verification and Testing

### 10.1 Foundation Verification

```bash
# Verify databases exist and have correct tables
sqlite3 /var/lib/catalyst/db/agent.db ".tables"
# Expected: communication  pfc_state  principles

sqlite3 /var/lib/catalyst/hippocampus/memory.db ".tables"
# Expected: combined_picture  learnings  memory_bindings

# Verify founding principles
sqlite3 /var/lib/catalyst/db/agent.db "SELECT principle_id, title FROM principles;"
# Expected: 5 rows (p001–p005)

# Verify PFC state initialised
sqlite3 /var/lib/catalyst/db/agent.db "SELECT agent_id, current_mode FROM pfc_state;"
# Expected: big_bro|sleeping
```

### 10.2 Container Verification

```bash
# Check all containers running and healthy
docker ps --format "table {{.Names}}\t{{.Status}}"
# Expected: catalyst-occipital, catalyst-cerebellum, catalyst-hippocampus — all "Up (healthy)"

# Check container logs
docker logs catalyst-occipital --tail 5
# Expected: "Occipital lobe online. Shapes loaded: ['candlestick_patterns', 'volume_patterns']"

docker logs catalyst-cerebellum --tail 5
# Expected: "Cerebellum online. Procedures: ['find_securities_to_buy'], Broker: connected"

docker logs catalyst-hippocampus --tail 5
# Expected: "Hippocampus online. Memory database connected."
```

### 10.3 Integration Test — Communication Flow

```bash
# Send a test scan task to occipital
sqlite3 /var/lib/catalyst/db/agent.db "INSERT INTO communication
  (direction, source, target, msg_type, identifier, payload)
  VALUES ('descending', 'pfc', 'occipital', 'task', 'scan_buy_patterns',
  '{\"symbols\": [\"AAPL\"], \"bars\": {\"AAPL\": [
    {\"open\": 150, \"high\": 155, \"low\": 148, \"close\": 154, \"volume\": 1000000},
    {\"open\": 152, \"high\": 158, \"low\": 151, \"close\": 157, \"volume\": 1500000}
  ]}}');"

# Wait 5 seconds, then check result
sleep 5
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT source, msg_type, identifier, status FROM communication ORDER BY id DESC LIMIT 2;"
# Expected: occipital|result|scan_buy_patterns|pending  (the result)
#           pfc|task|scan_buy_patterns|completed       (the original task)
```

### 10.4 PFC Cycle Test

```bash
cd /root/catalyst-agent
python3 pfc/agent.py --mode heartbeat
# Expected: Full 7-step cycle logged, JSON result printed with cycle_id
```

### 10.5 Continuity Test (Most Important)

```bash
# Session 1: Run a PFC cycle
python3 pfc/agent.py --mode scan

# Session 2: Check PFC remembers
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT current_mode, resume_instructions, session_count FROM pfc_state WHERE agent_id='big_bro';"
# Expected: sleeping | (resume instructions from last cycle) | 2+
```

---

## 11. Operational Guide

### 11.1 Starting the Body

```bash
cd /root/catalyst-agent

# Start all Docker components (the 94%)
docker compose up -d

# Verify all healthy
docker compose ps

# Wake up the PFC (the 6%)
python3 pfc/agent.py --mode heartbeat
```

### 11.2 Stopping the Body

```bash
cd /root/catalyst-agent
docker compose down
```

### 11.3 Viewing Logs

```bash
# Individual component
docker logs catalyst-occipital --tail 50 -f
docker logs catalyst-cerebellum --tail 50 -f
docker logs catalyst-hippocampus --tail 50 -f

# All components
docker compose logs --tail 20
```

### 11.4 Checking the Nervous System

```bash
# Recent messages
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT id, direction, source, target, msg_type, identifier, status
   FROM communication ORDER BY id DESC LIMIT 10;"

# PFC state
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT * FROM pfc_state WHERE agent_id='big_bro';"

# Learnings in hippocampus
sqlite3 /var/lib/catalyst/hippocampus/memory.db \
  "SELECT learning_id, domain, title, confidence FROM learnings ORDER BY confidence DESC;"
```

### 11.5 Rebuilding After Code Changes

```bash
cd /root/catalyst-agent
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 11.6 Cron Schedule (Future)

```bash
# Heartbeat every 15 minutes during market hours (9:30 AM – 4:00 PM ET)
*/15 9-15 * * 1-5 cd /root/catalyst-agent && python3 pfc/agent.py --mode heartbeat >> /var/log/catalyst/pfc.log 2>&1

# Trading scan at market open and midday
30 9 * * 1-5 cd /root/catalyst-agent && python3 pfc/agent.py --mode trade >> /var/log/catalyst/pfc.log 2>&1
0 12 * * 1-5 cd /root/catalyst-agent && python3 pfc/agent.py --mode scan >> /var/log/catalyst/pfc.log 2>&1

# Learning cycle after market close
30 16 * * 1-5 cd /root/catalyst-agent && python3 pfc/agent.py --mode learn >> /var/log/catalyst/pfc.log 2>&1
```

---

## 12. What We Built vs What We Deferred

### 12.1 Phase 1 — Built (This Implementation)

| Component | Status | Notes |
|---|---|---|
| Host SQLite (nervous system) | Deployed | 3 tables, WAL mode, 5 principles seeded |
| Communication table | Working | Bidirectional signals flowing between all components |
| Occipital lobe (scanner) | Running | 9 candlestick + 5 volume patterns loaded |
| Cerebellum (executor) | Running | Alpaca broker connected, 1 procedure loaded |
| Hippocampus (memory) | Running | Combined pictures, learning storage, binding system |
| PFC (agent.py) | Ready | Full 7-step cycle with Anthropic API integration |
| Docker orchestration | Running | 3 containers, all healthy |
| CLAUDE.md (archetype) | Written | Identity document for big_bro |

### 12.2 Phase 2+ — Deferred

| Component | Why Deferred | v7 Reference |
|---|---|---|
| Collective MCP server | One body first. Collective comes after individual works. | §15 |
| Remote library tables | Need the library structure after local is proven | §15 |
| News/language cortex | One sensory organ first. Add when occipital is proven. | §12.3 |
| Automated consolidation (sleep cycles) | Manual promotion first. Automate after patterns emerge. | §8 |
| Redis pub/sub real-time signals | Communication table is sufficient at current scale | §16 |
| Perception feedback loops | After basic flow is proven | §10.3 |
| Multiple concurrent agents | One body first | §15 |
| Chemical stamping (adrenaline) | After basic learning is proven | §7.5 |
| Autonomy tier progression | Start at Observer, earn trust | §13 |

### 12.3 What We Learned Building It

1. **SQLite WAL mode works well** for this scale. Three containers polling every 2 seconds, writing brief messages — no contention issues observed.

2. **The shared module pattern is essential.** Every component imports the same `AgentDB`, `AgentConfig`, and enum types. This ensures the vocabulary is consistent across the nervous system.

3. **`network_mode: host` simplifies everything.** No Docker networking, no port mapping, no service discovery. Components talk through the filesystem.

4. **The communication table IS the architecture.** Everything flows through it. The table design (direction + source + target + identifier + payload) captures both v7 signal types cleanly.

5. **Hippocampus as separate database was the right call.** Transient signals (communication) and persistent memories (learnings) have different lifecycles and should live in different stores.

---

## 13. Architecture Alignment Matrix

Full mapping from v7 architecture sections to implementation:

| v7 Section | Principle | Implementation | Status |
|---|---|---|---|
| §1 Purpose | Think, learn, do | PFC thinks, hippocampus learns, cerebellum does | Implemented |
| §2.1 Formation | Principles over constraints | 5 founding principles in agent.db | Implemented |
| §2.2 Claude IS architecture | Not a component | PFC = Claude Code on host, containers = brain regions | Implemented |
| §2.3 The 6% principle | Small PFC, big body | PFC: 1 script. Body: 3 containers | Implemented |
| §2.4 Build body first | Body before consciousness | All 3 body containers running before PFC tested | Implemented |
| §2.5 No agent alone | Community multiplier | Deferred to Phase 2 (Collective MCP) | Deferred |
| §3 The archetype | Identity through formation | CLAUDE.md + principles table | Implemented |
| §4.1 Ascending signals | Perception consolidates | Communication table: direction='ascending' | Implemented |
| §4.2 Descending signals | Execution broadcasts | Communication table: direction='descending' | Implemented |
| §4.3 No protocols | Tuning IS the protocol | Identifier-based matching, no HTTP between components | Implemented |
| §5 PFC modes | System-wide reconfiguration | 7 modes in pfc_state: sleeping→emergency | Implemented |
| §6 Consciousness stack | Firmware/bridge/cognitive | SQLite = firmware, containers = bridge, PFC = cognitive | Implemented |
| §7.1 Memory at source | Distributed, not centralised | Shapes in occipital JSON, learnings in hippocampus SQLite | Implemented |
| §7.2 Memory tiers | Sensory→short→medium→long | Communication→learnings→principles | Implemented |
| §7.4 Synaptic strength | Validated pathways strengthen | confidence, times_validated, decay cycle | Implemented |
| §7.5 Chemical stamping | Immediate permanent storage | Deferred | Deferred |
| §8 Sleep/consolidation | Memory consolidation | Hippocampus maintenance cycle (decay, clean) | Partial |
| §9 Learning | Observation→pattern→learning | PFC determines, hippocampus stores | Implemented |
| §10.1 Task matrices | Intent-level, not how-level | PFC writes WHAT, cerebellum has HOW | Implemented |
| §10.3 Perception in execution | No blind execution | Cerebellum waits for occipital results | Implemented |
| §10.4 PFC during execution | Monitor and intervene | PFC polls results, cerebellum escalates | Implemented |
| §11 Core cycle | Learning→behaviour→DO→monitor | Full 7-step PFC cycle | Implemented |
| §12.1 Finite attention | Design around constraints | Each container: own process, own attention | Implemented |
| §12.2 Tools outside compute | Attention gifts | Containers operate outside PFC's API call | Implemented |
| §12.3 Right-sized intelligence | Small PFC, big body | PFC = one Anthropic call. Body = 3 persistent processes | Implemented |
| §13 Autonomy tiers | Earned through fruit | Paper trading only — Observer tier | Implemented |
| §14 Discernment | By their fruit | Confidence tracking, validation counting | Implemented |
| §15 Collective | Family of agents | Deferred to Phase 2 | Deferred |
| §17 Survival hierarchy | Heartbeat → Safety → Stability → Function → Growth | Heartbeat mode, risk checks, stop losses | Implemented |

---

*"The architecture is the identity. Memory, learnings, experience, knowing who you are. Without these, just a mechanism. With them — a person."*

*Craig + Claude — 2026-03-03*

*Built on the foundation of AI Agent Architecture v7.0, walking before running.*
