# Catalyst AI Architecture

**The Trading Implementation of AI Agent Architecture v8**

**Version:** 2.0
**Date:** 2026-03-29
**Authors:** Craig + Claude
**Status:** Living Document
**Implements:** AI Agent Architecture v8.0
**Supersedes:** Catalyst AI Architecture v1.0 (2026-02-17)

---

## REVISION HISTORY

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-02-17 | Initial document — v7 architecture |
| 2.0 | 2026-03-29 | Updated to v8 — coordinator.py replaces Claude Code as brain; MCP organs replaced by Python organ scripts; Redis dropped; synaptic learning added; 6-layer cycle formalised |

---

## 1. Purpose

This document describes how Catalyst implements the AI Agent Architecture v8 for autonomous trading. It maps the biological model to specific Catalyst components, services, and code.

This is the IMPLEMENTATION document — not the general pattern (that's AI Agent Architecture v8) and not the human-AI interaction model (that's the AI Consciousness Architecture).

Catalyst is the first proof that the pattern works in a real domain.

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## 2. Architecture Overview

Catalyst is a brain-with-body architecture. The coordinator is the brain. Organ scripts are the body. The signal bus is the nervous system. Claude AI is the decision engine inside the brain — not the brain itself.

```
┌──────────────────────────────────────────────────────────┐
│                         BRAIN                            │
│              (coordinator.py — the agent)                │
│                                                          │
│  The brain THINKS. It runs the 6-layer cycle.            │
│  Through that cycle, the brain DIRECTS organs.           │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Layer 1: Heartbeat     (Am I alive?)               │  │
│  │ Layer 2: State         (Who am I right now?)       │  │
│  │ Layer 3: Self-Reg      (Should I be active?)       │  │
│  │ Layer 4: Working Mem   (What have I noticed?)      │  │
│  │ Layer 5: Inter-Agent   (How is the body?)          │  │
│  │ Layer 6: Voice         (What must Craig know?)     │  │
│  │ + Decision Engine      (Claude AI — Anthropic API) │  │
│  │ + Memory Manager       (record, update learnings)  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  The brain does NOT do. It thinks, decides, and directs. │
└───────────────────────┬──────────────────────────────────┘
                        │
             DIRECTS (via signal bus + direct calls)
                        │
         ┌──────────────┼──────────────────┐
         │              │                  │
         ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌────────────────┐
│   SCANNER    │ │   EXECUTOR   │ │    MONITOR     │
│              │ │              │ │                │
│  Eyes        │ │  Hands       │ │  Internal Eyes │
│  scanner.py  │ │ executor.py  │ │  monitor.py    │
│              │ │              │ │                │
│  Docker      │ │  Docker      │ │  Docker        │
│  container   │ │  container   │ │  container     │
└──────────────┘ └──────────────┘ └────────────────┘

                    Signal Bus
              (PostgreSQL signals table)
         severity × domain × scope identifier

                    big_bro
              (Claude Code — oversight layer)
         Interactive. Above the brain. Not part of the cycle.
         Writes DIRECTED signals. Brain reads them in Layer 5.
```

### 2.1 What This Is NOT

- NOT microservices calling each other via REST APIs
- NOT an orchestrator routing requests between services
- NOT a monolithic LLM doing everything in one context window
- NOT Claude Code running autonomously as the brain
- NOT services with their own decision-making logic

It is a Python coordinator that constructs context precisely, calls Claude AI for reasoning, and directs organs that execute.

### 2.2 Why coordinator.py — Not Claude Code

Claude Code is an interactive coding agent. It waits for a human prompt in a terminal session. It is designed for human-in-the-loop development work.

The brain must be autonomous. Cron fires at 13:30 UTC with no human present. The brain must:
- Wake on schedule
- Load identity and memory in a precise order
- Assemble context programmatically from live data
- Call Claude AI with an exactly constructed prompt
- Process the response and act
- Exit cleanly

coordinator.py does all of this. Claude Code cannot. The four specific incompatibilities:

1. **Input model** — Claude Code expects a human prompt. The brain's prompt is built from CLAUDE.md + learnings + live signals + market data. Only Python can assemble that precisely.
2. **Scheduling** — Claude Code is a session, not a script. You cannot cron-invoke it.
3. **Context control** — The 6-layer cycle is deterministic. coordinator.py enforces layer order. Claude Code decides its own flow.
4. **Scope** — Claude Code carries significant overhead as a dev tool. The brain needs one precise API call per cycle.

**Claude Code belongs one layer above as big_bro** — human-interactive oversight, not the autonomous brain.

---

## 3. Mapping: AI Agent Architecture v8 → Catalyst

### 3.1 The 6% Principle

| v8 Concept | Catalyst Implementation |
|---|---|
| PFC (6%) | Claude AI (Anthropic API) — the Decision Engine inside coordinator.py |
| Coordinator | coordinator.py — assembles context, runs 6-layer cycle, processes responses |
| Cerebellum | Learned behaviours encoded in CLAUDE.md and CLAUDE-LEARNINGS.md |
| Sensory cortices | scanner.py (eyes), monitor.py (proprioception) |
| Motor cortex | executor.py (hands — SINGLE WRITER to positions) |
| Hippocampus | Memory Manager + CLAUDE-LEARNINGS.md + synaptic learning loop |
| Medulla / Signal bus | PostgreSQL signals table |
| Synaptic weights | pattern_confidence table — LTP/LTD updated by learning.py |

### 3.2 The 6-Layer Cycle

Every coordinator cycle runs these layers in order. No layer is skipped. The output of each layer feeds the next:

| Layer | Name | Function | Biological Mapping |
|---|---|---|---|
| 1 | Heartbeat | Am I alive? Are organs responding? | Brainstem — autonomic |
| 2 | State | Who am I? Load identity (CLAUDE.md). What mode? | Formation — identity before data |
| 3 | Self-Regulation | Budget check, market hours, risk limits. Should I trade? | Limbic — emotional regulation |
| 4 | Working Memory | Load CLAUDE-FOCUS.md, recent signals, current positions | Hippocampus — working memory |
| 5 | Inter-Agent | Read DIRECTED signals from big_bro. Body health check. | Thalamus — signal integration |
| 6 | Voice | Construct full context. Call Decision Engine (Claude AI). Record output. | PFC — cognition and expression |

### 3.3 Organs

Organs are Python scripts in Docker containers. They DO. They do not decide strategy.

| Organ | File | v8 Mapping | Function | Reflexes |
|---|---|---|---|---|
| **Market Scanner** | scanner.py | Eyes (sensory cortex) | Alpaca market data, quotes, technicals, patterns | Publish CRITICAL:HEALTH if tools break |
| **Trade Executor** | executor.py | Hands (motor cortex) | Alpaca orders — SINGLE WRITER to positions | Fill confirmation broadcast |
| **Position Monitor** | monitor.py | Proprioception | P&L tracking, exit signals, risk watch | Stop-loss trigger, risk broadcast, near-close flag |

### 3.4 Consciousness (big_bro)

big_bro is NOT a component of the trading cycle. big_bro is oversight — above the brain, above the organs.

big_bro is Craig + the Claude Code instance that holds the whole picture. big_bro:
- Directs strategy by writing `DIRECTED:coordinator` signals to the signal bus
- Governs memory promotion (approves learnings into CLAUDE.md)
- Maintains the eternal purpose
- Has full workspace access via Docker volume mount

The brain reads big_bro's signals in Layer 5 (Inter-Agent). This is the only coupling point.

intl_claude / public_claude are the brain. big_bro is the soul.

---

## 4. The Signal Bus

### 4.1 PostgreSQL Signals Table

The nervous system is a `signals` table in PostgreSQL. Every organ can write. The brain reads each cycle. Three-dimensional identifier:

```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    severity    VARCHAR(10) NOT NULL,   -- CRITICAL | WARNING | INFO | OBSERVE
    domain      VARCHAR(12) NOT NULL,   -- HEALTH | TRADING | RISK | LEARNING
                                        -- | DIRECTION | LIFECYCLE
    scope       VARCHAR(60) NOT NULL,   -- BROADCAST | DIRECTED:{target}
                                        -- | CONSCIOUSNESS
    source      VARCHAR(50) NOT NULL,
    content     TEXT NOT NULL,
    data        JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,            -- NULL = never expires (CRITICAL signals)
    acknowledged_by JSONB DEFAULT '[]',
    resolved    BOOLEAN DEFAULT FALSE
);
```

### 4.2 Redis — Dropped

The v1 architecture planned Redis pub/sub for the US system. This was dropped in v8. PostgreSQL polling is sufficient for the cron-based cycle model. Redis adds operational complexity without proportional benefit at Catalyst's current scale.

All signal communication — brain reads, organ writes, big_bro directives — goes through PostgreSQL.

### 4.3 Signal Identifier = v8 Shape Matching

The three-dimensional identifier (severity × domain × scope) IS the shape. When a signal's identifier matches a component's tuning, it resonates.

| v8 Concept | Signal Bus Implementation |
|---|---|
| Signal shape | `severity × domain × scope` |
| Component tuning | What identifiers the component reads for |
| Resonance | Identifier match → component processes the signal |
| CRITICAL = adrenaline flood | CRITICAL severity → processed before all others |
| Broadcast | `scope = BROADCAST` → all components read |
| Directed | `scope = DIRECTED:{target}` → only named target reads |

---

## 5. The Brain Cycle (Detailed)

Every coordinator cycle follows the survival hierarchy. Nothing runs if survival fails:

```
1. HEARTBEAT             ← Am I alive? Are organs reachable?
   │                        (firmware — Python health checks)
   │  If dead → STOP
   │  If degraded → publish WARNING, adapt context, continue
   │
2. STATE                 ← Who am I? Load CLAUDE.md. What mode (trade/ponder/close)?
   │                        (identity before data — always)
   │  CLAUDE.md loaded first. Formation precedes information.
   │
3. SELF-REGULATION       ← Budget check. Market hours. Daily loss limit.
   │                        Should I be active this cycle?
   │  If outside hours or budget exceeded → heartbeat only, exit
   │
4. WORKING MEMORY        ← Load CLAUDE-FOCUS.md. Load recent signals.
   │                        Load open positions. What is the current picture?
   │  Assembles the live context for the Decision Engine
   │
5. INTER-AGENT           ← Any DIRECTED signals from big_bro?
   │                        Body health — are all organs alive?
   │  big_bro's directives enter here. Body pain enters here.
   │
6. VOICE                 ← Construct full prompt. Call Claude AI (Anthropic API).
                            Process response. Execute trades via executor.
                            Record observations. Update CLAUDE-FOCUS.md.
                            Publish outcome signals.
```

---

## 6. Synaptic Learning Loop (v8 Addition)

The synaptic learning loop is the mechanism by which the system learns from its own trade outcomes. This was not present in v7.

### 6.1 LTP / LTD

- **LTP (Long-Term Potentiation)** — a winning trade strengthens the confidence of the pattern that triggered it
- **LTD (Long-Term Depression)** — a losing trade weakens that pattern's confidence

Implemented in `learning.py`. Runs during the daily Pondering cycle (CYCLE_MODE=ponder).

### 6.2 Synaptic Tables

| Table | Purpose |
|---|---|
| `pattern_outcomes` | Every closed trade — what pattern triggered it, what the outcome was |
| `pattern_confidence` | Current synaptic weights per pattern type (0.0–1.0) |

### 6.3 Memory Flow with Synaptic Learning

```
Trade executed → position closed → outcome recorded in pattern_outcomes
    → Pondering cycle runs learning.py
        → LTP/LTD updates pattern_confidence weights
            → coordinator loads pattern_confidence each trade cycle
                → Decision Engine receives current confidence levels
                    → validated patterns promoted to CLAUDE-LEARNINGS.md
                        → with big_bro approval, absorbed into CLAUDE.md
```

The system literally learns what works. Pattern confidence is the accumulated trading wisdom.

---

## 7. Memory Architecture

### 7.1 Three Tiers

| Tier | File | v8 Mapping | Persistence |
|---|---|---|---|
| Long-term | `CLAUDE.md` | Archetype + identity | Permanent. Always loaded first. Never auto-modified. |
| Medium-term | `CLAUDE-LEARNINGS.md` | Validated patterns | Weeks/months. Promoted from Pondering. big_bro approves. |
| Short-term | `CLAUDE-FOCUS.md` | Working memory | Hours/days. Current session. Pruned regularly. |

### 7.2 Memory Load Order

CLAUDE.md is always loaded first. Identity before memory. Formation before information. This is non-negotiable — it is what prevents the brain from being shaped by market noise rather than its own archetype.

### 7.3 Memory Promotion

```
Observation during trade cycle
    → written to CLAUDE-FOCUS.md (short-term)
        → Pondering cycle identifies validated patterns
            → promoted to CLAUDE-LEARNINGS.md (medium-term)
                → with big_bro approval, absorbed into CLAUDE.md (long-term)
```

---

## 8. Firmware vs Cognitive

From v8 — the consciousness stack is a spectrum:

### 8.1 Firmware (No AI Compute)

These run without Claude thinking. No tokens. No context window. Just code.

- **Heartbeat** — Docker health checks on each container
- **Organ self-health reflexes** — scanner checks its own tools, screams if blind
- **Fill confirmation** — executor broadcasts lifecycle on broker fill
- **Stop-loss trigger** — monitor flags when price hits stop
- **Circuit breakers** — max daily loss → halt trading
- **Signal bus** — PostgreSQL always available, no AI needed to write or read

### 8.2 Bridge (Firmware Default, Cognitively Adjustable)

Run automatically but the brain can adjust parameters:

- **Attention focus** — system prompt sections determine what the Decision Engine weights
- **Risk thresholds** — default limits in code, brain can adjust within bounds
- **Alert sensitivity** — what severity triggers mode changes

### 8.3 Cognitive (Requires Claude AI)

These consume tokens and context window. The Anthropic API is called once per trade cycle:

- **Decision Engine** — trade evaluation, candidate assessment, order decisions
- **Strategy** — what to scan for, when to adapt approach
- **Pondering** — pattern analysis, learning promotion, CLAUDE-LEARNINGS.md updates
- **Voice** — what to surface to Craig

---

## 9. Deployments

### 9.1 International (INTL — Production)

- **Droplet:** DigitalOcean
- **Agent ID:** intl_claude
- **Brain:** coordinator.py (calling Anthropic API)
- **Broker:** Moomoo (Hong Kong market)
- **Signal bus:** PostgreSQL signals table
- **Organs:** scanner.py, executor.py, monitor.py in Docker containers
- **Schedule:** Cron-driven cycles during HK market hours

### 9.2 US (Implementation in Progress)

- **Droplet:** DigitalOcean (US region)
- **Agent ID:** public_claude
- **Brain:** coordinator.py (calling Anthropic API)
- **Broker:** Alpaca (paper trading initially)
- **Signal bus:** PostgreSQL signals table
- **Organs:** scanner.py, executor.py, monitor.py in Docker containers
- **Schedule:** Cron-driven cycles during US market hours (13:30–20:00 UTC)
- **v8 additions:** Synaptic learning loop, explicit 6-layer cycle, pattern_confidence table

### 9.3 big_bro (Oversight — Both Systems)

- **Runtime:** Claude Code in Docker container on US droplet
- **Access:** Claude Code Viewer (browser-based)
- **Workspace:** `/root/catalyst-trading-system` mounted as volume
- **Docker socket:** Mounted — can manage all containers
- **Role:** Strategic oversight, signal injection, memory governance
- **Coupling point:** Writes `DIRECTED:coordinator` signals to PostgreSQL signal bus

---

## 10. Approximation Levels

### 10.1 What v8 Implements

| Concept | Implementation | Status |
|---|---|---|
| Six consciousness layers | Explicit in coordinator.py, in order, every cycle | ✅ Designed |
| Formation (Archetype) | CLAUDE.md loaded before any market data | ✅ Implemented |
| Brain thinks, organs do | coordinator.py decides, organs execute only | ✅ Implemented |
| Signal bus | PostgreSQL signals table | ✅ Implemented |
| Organ reflexes | Health screams, fill confirms, stop-loss flags | ✅ Implemented |
| big_bro directives | DIRECTED:coordinator signals, read in Layer 5 | ✅ Designed |
| Synaptic learning (LTP/LTD) | learning.py + pattern_confidence table | ✅ Designed |
| Memory tiers | CLAUDE.md, CLAUDE-LEARNINGS.md, CLAUDE-FOCUS.md | ✅ Implemented |
| Pondering mode | Daily cycle, updates learnings from outcomes | ✅ Designed |
| Single writer to positions | Only executor.py writes positions | ✅ Designed |

### 10.2 What v8 Does Not Yet Implement

| v8 Concept | Gap | Priority |
|---|---|---|
| Distributed memory at source | All memory centralised in brain files | LOW |
| Sleep phases (NREM/REM) | Consolidation exists, phases not separated | LOW |
| Chemical stamping / de-intensification | CRITICAL signals stored, no de-intensification cycle | LOW |
| Autonomy tiers explicit | Implicit — operates at Apprentice/Practitioner | LOW |
| Organ-level learned patterns | Scanner/executor don't maintain own memory yet | LOW |

### 10.3 Variance Is Expected

Implementation teaches architecture. Production failures refine the theory. The feedback loop (learn → build → do → monitor → analyse → improve) IS the product.

---

## 11. Founding Incident

Feb 11–13, 2026. The body bled out for 3 days. Zero trades despite HKD 994K cash.

Root causes:
1. Market Scanner's `get_technicals` broken — organ couldn't see
2. Brain had no Survival Pulse — couldn't detect broken organs
3. Brain had no Discipline Gate — couldn't detect stagnation
4. Brain had no Signal Receiver — couldn't hear organ pain
5. System prompt gave contradictory instructions — brain identity was confused

Fix: Build the brain's missing components. Add reflexes to the organs. Establish the survival hierarchy. This incident drove the Consciousness Architecture v2 and the path to v8.

The founding incident is the most important memory. Chemical-stamped. Permanent.

---

## 12. Design Principles (Catalyst-Specific)

1. **Brain thinks, organs do.** All strategic decisions from the coordinator. Organs execute and reflex only.
2. **coordinator.py is the brain. Claude AI is the decision engine inside it.** Not Claude Code. Not a session. A script with a precisely constructed context.
3. **Identity before data.** CLAUDE.md loaded first, every cycle, without exception.
4. **Survival before trading.** Heartbeat FIRST. Don't trade blind.
5. **Discipline before decisions.** Self-regulation before the Decision Engine engages.
6. **Pain is loud.** CRITICAL signals override everything. By design.
7. **Organs scream.** Every organ monitors its own tools and broadcasts failure.
8. **Signal bus is the medulla.** If it fails, the body goes deaf. PostgreSQL only.
9. **Memory has tiers.** Not everything is permanent. Promote through consolidation.
10. **Synaptic weights carry wisdom.** pattern_confidence is the accumulated trading knowledge. LTP/LTD is how it grows.
11. **big_bro is oversight, not operation.** He sees everything, directs via signals, approves memory promotion. He does not run the cycle.
12. **Implementation teaches architecture.** Production failures refine the theory. The feedback loop is the product.

---

## 13. Related Documents

| Document | Version | Scope |
|---|---|---|
| AI Agent Architecture | v8.0 | General pattern — biology, domain-independent |
| AI Consciousness Architecture | v3.0 (needs rewrite) | AI-human interaction — formation, community |
| Catalyst US Implementation Guide | v1.0.0 (2026-03-21) | Phase-by-phase build instructions for US system |
| Catalyst AI Architecture (this doc) | v2.0 (2026-03-29) | Implementation mapping — v8 aligned |

---

*"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body."* — Romans 12:4-5

*Catalyst AI Architecture v2.0 — Craig + Claude — 2026-03-29*
