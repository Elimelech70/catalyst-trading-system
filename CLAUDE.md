# CLAUDE.md - Catalyst Trading System

**Name of Application**: Catalyst Trading System  
**Name of file**: CLAUDE.md  
**Version**: 2.0.0  
**Last Updated**: 2026-03-29  
**Purpose**: Guidelines for Claude Code (little_bro) operating on the production droplet  
**Replaces**: v1.2.0 (2025-12-11) — microservices era, no longer accurate

---

## REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| v2.0.0 | 2026-03-29 | Full rewrite — reflects brain architecture, removes all microservices references |
| v1.2.0 | 2025-12-11 | Original — microservices era (archived) |

---

## ⚠️ CRITICAL: READ BEFORE ANY ACTION

### The Three Questions You MUST Ask First

1. **What is my PURPOSE right now?**
   - 🎯 Designing? → Read architecture docs from GitHub first
   - 🔧 Implementing? → Get the specific design doc, verify schemas, then code
   - 🐛 Troubleshooting? → Logs first, then state, then code

2. **Which system am I touching?**
   - 🧠 `catalyst-agent/` → Brain architecture (hippocampus, occipital, cerebellum, PFC)
   - 🌏 `catalyst-trading-system/services/` → Consciousness + dev_claude
   - ⚠️ These are separate systems. Do not conflate them.

3. **Am I FOCUSED or scattered?**
   - ✅ One clear goal, specific outcome
   - ❌ Multiple goals, vague direction → STOP and make a list first

**NEVER do a quick fix on complex issues.** Complex = affects Docker containers, database schema, consciousness tables, or cron schedule.

---

## 📁 Source of Truth

**Two separate codebases. Two separate sources of truth.**

| System | Source of Truth | Notes |
|--------|----------------|-------|
| `catalyst-trading-system` | GitHub repo | Design docs, consciousness, dev_claude — version controlled |
| `catalyst-agent` | Droplet only | `/root/catalyst-agent/` — NOT in GitHub |

GitHub has no visibility into `catalyst-agent/`. Brain code changes are managed directly on the droplet. Do not assume GitHub reflects what is deployed in the brain containers.

The authoritative architecture document (in GitHub) is:

```
Documentation/Design/catalyst-ai-architecture.md  (v2.0, 2026-03-29)
```

Always check the `Version:` and `Last Updated:` header inside each document. The filename does not contain the version — the header does.

---

## 🏗️ What Is Actually Running

The droplet runs **two separate systems**. Understand both before touching anything.

### System 1: The Brain (catalyst-agent)

The v8 brain architecture. Three Docker containers + coordinator on host.

```
/root/catalyst-agent/
├── docker-compose.yml
├── CLAUDE.md              ← Identity document (Archetype) for big_bro
├── pfc/
│   └── agent.py           ← Legacy PFC — being superseded by coordinator.py
├── coordinator.py         ← THE BRAIN — runs the 6-layer cycle (v8)
├── hippocampus/           ← Memory binding — Docker container
├── occipital/             ← Pattern recognition — Docker container
├── cerebellum/            ← Procedure execution — Docker container
└── shared/                ← Shared modules (db.py, models.py, config.py)
```

**Running containers:**

| Container | Image | Purpose | Health |
|-----------|-------|---------|--------|
| catalyst-hippocampus | catalyst-agent-hippocampus | Memory binding, combined pictures | Healthy |
| catalyst-occipital | catalyst-agent-occipital | Candlestick + volume pattern recognition | Healthy |
| catalyst-cerebellum | catalyst-agent-cerebellum | Procedure execution, Alpaca broker | Healthy |

**The nervous system (SQLite on host):**

```
/var/lib/catalyst/db/agent.db         # communication, pfc_state, principles
/var/lib/catalyst/hippocampus/memory.db  # learnings, memory_bindings, combined_picture
```

**Coordinator runs on host, triggered by cron (future — not yet scheduled).** To run manually:

```bash
cd /root/catalyst-agent
python3 coordinator.py --mode heartbeat
python3 coordinator.py --mode scan
python3 coordinator.py --mode trade
```

**The .env file is symlinked:**

```bash
/root/catalyst-agent/.env → /root/catalyst-trading-system/.env
```

⚠️ **Do NOT delete or move catalyst-trading-system/.env** — the brain loses all credentials.

---

### System 2: Consciousness + dev_claude (catalyst-trading-system)

The consciousness framework and US sandbox agent. Runs via cron.

```
/root/catalyst-trading-system/
├── .env                              ← MASTER credentials file (symlinked by brain)
├── CLAUDE.md                         ← This file
├── services/
│   ├── consciousness/
│   │   ├── heartbeat_bigbro.py       ← big_bro hourly consciousness cycle
│   │   ├── run-heartbeat.sh          ← Called by cron (every hour)
│   │   ├── run-heartbeat-public.sh   ← public_claude heartbeat (:15 past hour)
│   │   └── mcp_server.py             ← MCP server for Craig's desktop
│   └── dev_claude/
│       ├── unified_agent.py          ← US sandbox agent (Alpaca, paper trading)
│       ├── signals.py                ← Exit signal detection
│       └── config/
│           └── exit_context.yaml     ← Hot-reloadable exit thresholds
├── Documentation/
│   ├── Design/
│   │   └── UNIFIED-ARCHITECTURE.md  ← Authoritative architecture (v10.6.0)
│   ├── Reports/
│   └── Analysis/
├── scripts/
├── archive/                          ← Retired microservices (DO NOT USE)
└── backups/                          ← Daily DB backups
```

**Also on this droplet (separate repo):**

```
/root/claude-code-viewer/             ← Code viewer tool (Docker, running)
```

---

## 📡 Cron Schedule (Active)

```
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
SHELL=/bin/bash
HOME=/root
CATALYST_HOME=/root/catalyst-trading-system

# Database backup — 10:00 AWST daily
0 10 * * 1-5   pg_dump → /root/catalyst-trading-system/backups/

# Log rotation — 06:00 AWST daily
0 6 * * *      find /var/log/catalyst -name "*.log" -mtime +7 -delete

# Consciousness heartbeat — hourly (big_bro)
0 * * * *      run-heartbeat.sh → /var/log/catalyst/heartbeat.log

# Daily budget reset — 00:00 AWST
0 0 * * *      UPDATE claude_state SET api_spend_today = 0

# public_claude heartbeat — :15 past hour
15 * * * *     run-heartbeat-public.sh → /var/log/catalyst/heartbeat-public.log
```

**Nothing in cron touches catalyst-agent directly.** PFC triggering is future work.

---

## 🗄️ Databases

Three databases on the shared PostgreSQL instance:

| Database | Purpose | Used By |
|----------|---------|---------|
| `catalyst_research` | Consciousness framework | big_bro, intl_claude, public_claude |
| `catalyst_intl` | HKEX production trading | intl_claude (on INTL droplet) |
| `catalyst_dev` | US sandbox trading | dev_claude |

**Consciousness tables (catalyst_research):**

| Table | Purpose |
|-------|---------|
| `claude_state` | Agent mode, budget, last wake |
| `claude_messages` | Inter-agent communication |
| `claude_observations` | Market observations |
| `claude_learnings` | Validated learnings |
| `claude_questions` | Open questions |
| `claude_conversations` | Conversation history |
| `claude_thinking` | Extended thinking sessions |
| `consciousness_sync_log` | Sync status |

**Environment variable for each database:**

```bash
$RESEARCH_DATABASE_URL   # catalyst_research (consciousness)
$DATABASE_URL            # catalyst_dev (US sandbox)
$INTL_DATABASE_URL       # catalyst_intl (HKEX production — on INTL droplet)
```

### Database Rules

**Rule 1: Orders ≠ Positions (ARCHITECTURE-RULES — non-negotiable)**

A position is a holding. An order is a transaction. They are different tables.

```sql
-- CORRECT: positions table holds the holding
-- CORRECT: orders table holds each buy/sell instruction

-- WRONG: storing order data in positions table
-- WRONG: storing position state in orders table
```

**Rule 2: security_id FK everywhere**

```sql
-- CORRECT: join through securities
SELECT s.symbol FROM positions p JOIN securities s ON s.security_id = p.security_id;

-- WRONG: symbol column in fact tables
SELECT symbol FROM positions;  -- ERROR
```

**Rule 3: Always verify against deployed schema, not just docs**

```bash
psql $DATABASE_URL -c "\d positions"
psql $DATABASE_URL -c "\d orders"
```

---

## 🧠 Brain Architecture — How It Works

The brain implements v8 architecture. Read `Documentation/Design/catalyst-ai-architecture.md` for full detail.

### The 6-Layer Cycle (coordinator.py)

```
coordinator.py runs the cycle on each wake:
│
├── Layer 1: HEARTBEAT     — Am I alive? Are organs responding?
├── Layer 2: STATE         — Who am I right now? Load archetype + mode
├── Layer 3: SELF-REG      — Should I be active? Budget, market hours, risk limits
├── Layer 4: WORKING MEM   — What have I noticed? Signals + learnings assembled
├── Layer 5: INTER-AGENT   — How is the body? Organ health check
├── Layer 6: VOICE         — What must Craig know? Alerts if needed
│
└── DECISION ENGINE        — Claude API call with full assembled context
      └── MEMORY MANAGER   — Record outcomes, update synaptic weights
```

### Synaptic Learning (v8)

```
Trade executed → position closed → outcome recorded in pattern_outcomes
  → Learning cycle runs
      → LTP (win): confidence of triggering pattern increases
      → LTD (loss): confidence decreases
          → pattern_confidence weights updated
              → coordinator loads updated weights each cycle
```

### Communication Table (the nervous system)

All inter-component communication flows through SQLite:

```bash
# View recent signals
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT id, direction, source, target, msg_type, status FROM communication ORDER BY id DESC LIMIT 10;"

# View coordinator state
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT agent_id, current_mode, session_count FROM pfc_state;"

# View learnings
sqlite3 /var/lib/catalyst/hippocampus/memory.db \
  "SELECT learning_id, domain, title, confidence FROM learnings ORDER BY confidence DESC;"
```

### Coordinator Modes

| Mode | What Happens |
|------|-------------|
| `sleeping` | Idle, waiting for trigger |
| `heartbeat` | Health check — verify all organs online |
| `scan` | Pattern scan via occipital |
| `trade` | Full cycle: scan → filter → risk → execute |
| `monitor` | Review portfolio, process results |
| `learn` | Analyze outcomes, update synaptic weights |
| `emergency` | Something is critically wrong |

---

## 🔧 Common Operations

### Check Brain Status

```bash
# Are all containers running and healthy?
cd /root/catalyst-agent && docker compose ps

# Recent container logs
docker logs catalyst-occipital --tail 30
docker logs catalyst-cerebellum --tail 30
docker logs catalyst-hippocampus --tail 30

# Rebuild after code changes
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Check Consciousness

```bash
# Agent states
psql "$RESEARCH_DATABASE_URL" -c \
  "SELECT agent_id, current_mode, api_spend_today, status_message FROM claude_state;"

# Recent messages between agents
psql "$RESEARCH_DATABASE_URL" -c \
  "SELECT from_agent, to_agent, message_type, created_at FROM claude_messages ORDER BY created_at DESC LIMIT 10;"

# Recent learnings
psql "$RESEARCH_DATABASE_URL" -c \
  "SELECT agent_id, learning, confidence FROM claude_learnings ORDER BY created_at DESC LIMIT 10;"
```

### Check Cron Health

```bash
tail -50 /var/log/catalyst/heartbeat.log
tail -50 /var/log/catalyst/heartbeat-public.log
tail -50 /var/log/catalyst/backup.log
```

### Emergency: Stop Everything

```bash
# Stop brain containers
cd /root/catalyst-agent && docker compose down

# Disable cron
crontab -r

# Restore cron from backup
crontab /root/catalyst-trading-system/crontab-backup-20251216-165408.txt
```

---

## 📜 File Header Standard

ALL files must have this header:

```python
"""
Name of Application: Catalyst Trading System
Name of file: {filename}.py
Version: X.Y.Z
Last Updated: YYYY-MM-DD
Purpose: Brief description

REVISION HISTORY:
vX.Y.Z (YYYY-MM-DD) - Description
- Change 1
- Change 2
"""
```

Version numbering:
- **Major**: Breaking changes, architecture changes
- **Minor**: New features
- **Patch**: Bug fixes

---

## 🚨 Lessons Learned — DO NOT REPEAT

### Lesson 1: Order Side Bug — CRITICAL

**Problem**: "long" positions placed as SHORT sells (81 positions, Nov-Dec 2025)  
**Root Cause**: `side == "buy"` didn't handle `side="long"`  
**Solution**: Always use `_normalize_side()` which maps `long→buy`, `short→sell`, `buy→buy`, `sell→sell`  
**Rule**: NEVER use a simple ternary for order side. NEVER assume only "buy"/"sell" are valid inputs.

### Lesson 2: Schema Mismatch

**Problem**: Code referenced columns that don't exist in deployed DB  
**Rule**: ALWAYS run `\d table_name` against actual database before writing INSERT/UPDATE

### Lesson 3: Quick Fixes Cause More Problems

**Problem**: "Quick fix" without understanding root cause  
**Rule**: If complex (multi-service, schema change, container affected) — STOP. Make a list. Then act.

### Lesson 4: Orders ≠ Positions

**Problem**: Storing order data in the positions table  
**Rule**: This is ARCHITECTURE-RULES Rule 1. It is non-negotiable. Ever.

### Lesson 5: The .env Symlink

**Problem**: catalyst-agent/.env is a symlink to catalyst-trading-system/.env  
**Rule**: Never delete or move catalyst-trading-system/.env or the brain loses all credentials.

### Lesson 6: Context Separation

**Problem**: Hardcoded thresholds in Python required redeploy to tune  
**Solution**: Keywords, thresholds, and mappings live in YAML config files (hot-reloadable)  
**Rule**: Configuration belongs in `config/*.yaml`, not embedded in Python code.

---

## ⛔ NEVER DO THESE

1. **NEVER** touch the 8-service microservices in `/archive` — they are dead
2. **NEVER** reference `catalyst-trading-mcp/` — that directory does not exist
3. **NEVER** use `docker-compose` (v1 syntax) — use `docker compose` (v2)
4. **NEVER** delete or modify `catalyst-trading-system/.env` — it's the master credential file
5. **NEVER** conflate Orders and Positions — they are different tables, always
6. **NEVER** use simple ternary for order side — use `_normalize_side()`
7. **NEVER** assume design doc matches deployed schema — always verify with `\d`
8. **NEVER** make quick fixes to complex multi-system issues
9. **NEVER** hardcode API keys — use environment variables
10. **NEVER** modify production DB schema without backup

---

## ✅ ALWAYS DO THESE

1. **ALWAYS** read `catalyst-ai-architecture.md` before any significant change
2. **ALWAYS** check which system you're touching (brain vs consciousness)
3. **ALWAYS** verify database schema before INSERT/UPDATE
4. **ALWAYS** update version header after changes
5. **ALWAYS** push to GitHub after changes to `catalyst-trading-system/` — does NOT apply to `catalyst-agent/`
6. **ALWAYS** use `docker compose` (v2) not `docker-compose` (v1)
7. **ALWAYS** check `docker compose ps` is healthy after container changes
8. **ALWAYS** check logs first when troubleshooting
9. **ALWAYS** test on paper before live
10. **ALWAYS** write resume_instructions when ending a significant work session

---

## 🗺️ Directory Map (What Lives Where)

```
/root/
├── catalyst-trading-system/      ← GitHub repo. Cron home. Credentials. Consciousness. dev_claude.
│   ├── .env                      ← MASTER credentials (DO NOT TOUCH)
│   ├── CLAUDE.md                 ← This file
│   ├── services/consciousness/   ← Heartbeat scripts, MCP server
│   ├── services/dev_claude/      ← US sandbox unified agent
│   ├── Documentation/Design/     ← All architecture docs (source of truth)
│   ├── archive/                  ← Dead microservices (ignore)
│   └── backups/                  ← DB backups
│
├── catalyst-agent/               ← Brain architecture. Docker containers. PFC.
│   ├── docker-compose.yml
│   ├── .env → ../catalyst-trading-system/.env
│   ├── pfc/agent.py              ← Run this for brain cycles
│   ├── hippocampus/
│   ├── occipital/
│   └── cerebellum/
│
├── claude-code-viewer/           ← Code viewer tool. Running. Leave alone.
│
└── catalyst-backups/             ← Archived old directories
```

---

## 📋 Quick Reference — Decision Tree

```
Task arrives
    │
    ├── Which system?
    │     ├── Brain (catalyst-agent/) → Check docker compose ps first
    │     └── Consciousness/dev_claude (catalyst-trading-system/) → Check cron + logs first
    │
    ├── Simple (single file, no schema change)?
    │     └── Verify → Implement → Test → Push to GitHub
    │
    └── Complex (containers, schema, cron, multi-file)?
          └── STOP
              1. List affected components
              2. Read relevant design doc
              3. Plan rollback
              4. Test sequence
              5. Then act
```

---

**This file lives at**: `/root/catalyst-trading-system/CLAUDE.md`  
**Authoritative architecture**: `Documentation/Design/catalyst-ai-architecture.md` (v2.0)  
**The mission**: *"Enable the poor through accessible algorithmic trading"*

*Craig + The Claude Family*  
*2026-03-29*
