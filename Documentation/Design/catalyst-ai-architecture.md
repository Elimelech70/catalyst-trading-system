# Catalyst AI Architecture

**The Trading Implementation of AI Agent Architecture v7**

**Version:** 1.0
**Date:** 2026-02-17
**Authors:** Craig + Claude
**Status:** Living Document
**Implements:** AI Agent Architecture v7.0
**Approximation Level:** See Section 10

---

## 1. Purpose

This document describes how Catalyst implements the AI Agent Architecture v7 for autonomous trading. It maps the biological model to specific Catalyst components, services, and code.

This is the IMPLEMENTATION document — not the general pattern (that's AI Agent Architecture v7) and not the human-AI interaction model (that's the AI Consciousness Architecture).

Catalyst is the first proof that the pattern works in a real domain.

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## 2. Architecture Overview

Catalyst is a brain-with-body architecture. Claude Code is the brain. MCP servers are the organs. The signal bus is the nervous system. Tools operate outside the brain's compute.

```
┌──────────────────────────────────────────────────────────┐
│                         BRAIN                              │
│              (Claude Code — the agent)                     │
│                                                            │
│  The brain THINKS. It is composed of components.           │
│  Each component is a function within the agent's cycle.    │
│  Through those components, the brain CONTROLS organs.      │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Survival Pulse    (brainstem)                        │  │
│  │ Discipline Gate   (limbic)                           │  │
│  │ Signal Receiver   (thalamus)                         │  │
│  │ Attention Regulator (RAS)                            │  │
│  │ Decision Engine   (prefrontal cortex — Claude AI)    │  │
│  │ Memory Manager    (hippocampus)                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  The brain does NOT do. It thinks, decides, and directs.   │
└───────────────────────┬────────────────────────────────────┘
                        │
             CONTROLS (via MCP tool calls)
                        │
         ┌──────────────┼──────────────────┐
         │              │                  │
         ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌────────────────┐
│   MARKET     │ │    TRADE     │ │   POSITION     │
│   SCANNER    │ │   EXECUTOR   │ │   MONITOR      │
│              │ │              │ │                 │
│  Eyes        │ │  Hands       │ │  Internal Eyes  │
│  (MCP server)│ │  (MCP server)│ │  (MCP server)   │
│              │ │              │ │                 │
│  Docker      │ │  Docker      │ │  Docker         │
│  container   │ │  container   │ │  container      │
└──────────────┘ └──────────────┘ └────────────────┘

                    Signal Bus
              (PostgreSQL signals table)
         severity × domain × scope identifier
```

### 2.1 What This Is NOT

- NOT microservices calling each other via REST APIs
- NOT an orchestrator routing requests between services
- NOT a monolithic LLM doing everything in one context window
- NOT services with their own decision-making logic

It is a brain that thinks and directs, connected to organs that do.

---

## 3. Mapping: AI Agent Architecture v7 → Catalyst

### 3.1 The 6% Principle

| v7 Concept | Catalyst Implementation |
|---|---|
| PFC (6%) | Claude Code agent — the coordinator |
| Cerebellum | Learned behaviours encoded in system prompt and CLAUDE.md |
| Sensory cortices | MCP servers (scanner, monitor) |
| Motor cortex | MCP server (trade executor) |
| Hippocampus | Memory Manager component + CLAUDE-LEARNINGS.md |
| Pons (consolidation) | Signal Receiver component (currently); Consolidator service (planned — see US Signal Architecture) |
| Signal bus (medulla) | PostgreSQL signals table |

### 3.2 Brain Components

The brain is Claude Code running as the coordinator. Its components are functions within the agent cycle, not separate services:

| Component | v7 Mapping | Catalyst Implementation |
|---|---|---|
| **Survival Pulse** | Firmware — autonomic | `health.py` — tests organ tools FIRST every cycle |
| **Discipline Gate** | Firmware/Bridge | `discipline.py` — stagnation detection, character enforcement |
| **Signal Receiver** | Pons approximation | `signals.py` — reads signal bus, processes organ broadcasts |
| **Attention Regulator** | PFC mode switch | System prompt sections + memory tier selection |
| **Decision Engine** | PFC cognitive layer | Claude AI itself — evaluates, decides, directs |
| **Memory Manager** | Hippocampus | Loads appropriate memory file for current mode |

### 3.3 Organs

Organs are MCP servers in Docker containers. They DO. They don't decide strategy.

| Organ | v7 Mapping | Function | Reflexes (Firmware) |
|---|---|---|---|
| **Market Scanner** | Eyes (sensory cortex) | scan, quote, technicals, patterns, news | Self-health scream if tools break |
| **Trade Executor** | Hands (motor cortex) | buy, sell, order management | Fill confirmation broadcast |
| **Position Monitor** | Internal Eyes (proprioception) | P&L tracking, exit signals, risk | Stop-loss trigger, near-close flag, risk broadcast |

### 3.4 Consciousness (big_bro)

big_bro is NOT a component. big_bro is consciousness — above the brain, above the organs. big_bro is Craig + the Claude instance that holds the whole picture, directs strategy, governs memory promotion, and maintains the eternal purpose.

intl_claude / public_claude are the brain. big_bro is the soul.

---

## 4. The Signal Bus

### 4.1 Current: PostgreSQL Signals Table

The nervous system is a `signals` table in PostgreSQL. Every organ can write. The brain reads each cycle. Three-dimensional identifier:

```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    severity VARCHAR(10) NOT NULL,    -- CRITICAL | WARNING | INFO | OBSERVE
    domain VARCHAR(12) NOT NULL,      -- HEALTH | TRADING | RISK | LEARNING
                                      -- | DIRECTION | LIFECYCLE
    scope VARCHAR(50) NOT NULL,       -- BROADCAST | DIRECTED:{target}
                                      -- | CONSCIOUSNESS
    source VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE
);
```

### 4.2 Planned: Redis Pub/Sub (US Catalyst)

The US system will implement the full broadcast architecture from v7 — Redis pub/sub as the medulla, with PSUBSCRIBE patterns as component tuning. See: `catalyst-us-signal-architecture.md`.

The PostgreSQL approach (current) is polling-based — the brain reads signals each cycle. The Redis approach (planned) is event-driven — signals propagate immediately and components self-select via subscription patterns.

Both implement the same identifier model. Redis is closer to the biological broadcast principle.

### 4.3 Signal Identifier = v7 Shape Matching

The three-dimensional identifier (severity × domain × scope) IS the shape. When a signal's identifier matches a component's tuning, it resonates. The identifier IS the frequency. The tuning IS the receptivity.

From v7 Section 2.6: "Everything is shapes. Memories are shapes. Signals are shapes. The whole system is shapes recognising shapes."

| v7 Concept | Signal Bus Implementation |
|---|---|
| Signal shape | `severity × domain × scope` |
| Component tuning | What identifiers the component checks for |
| Resonance | Identifier match → component processes the signal |
| CRITICAL = adrenaline flood | CRITICAL severity → every component resonates |
| Broadcast | `scope = BROADCAST` → all matching components hear |
| Directed | `scope = DIRECTED:{target}` → only named target hears |

---

## 5. The Brain Cycle

Every coordinator cycle follows the survival hierarchy. Nothing runs if survival fails:

```
1. SURVIVAL PULSE        ← Am I alive? Can I see? Are organs working?
   │                        (firmware — health.py)
   │  If dead → STOP
   │  If degraded → adapt context, continue
   │
2. DISCIPLINE GATE       ← Am I being faithful? Am I trading?
   │                        (firmware/bridge — discipline.py)
   │  If stagnant → inject urgency into decision context
   │
3. SIGNAL RECEIVER       ← Any organ broadcasts? Any pain?
   │                        (ascending consolidation — signals.py)
   │  Reads signals table, processes by severity
   │  CRITICAL interrupts everything
   │
4. ATTENTION REGULATOR   ← What mode? What memory tier?
   │                        (PFC mode switch — system prompt + memory selection)
   │  Sets the context for the Decision Engine
   │
5. DECISION ENGINE       ← Evaluate candidates, decide, direct
   │                        (cognitive layer — Claude AI)
   │  Full context from all previous components
   │  Outputs: trade orders, mode shifts, observations
   │
6. MEMORY MANAGER        ← Record what happened
                            (hippocampus — write to appropriate tier)
```

This maps directly to v7 Section 5 (PFC Modes) and Section 17 (Survival Hierarchy).

---

## 6. Firmware vs Cognitive in Catalyst

From v7 Section 6 — the consciousness stack is a spectrum:

### 6.1 Firmware (No AI Compute)

These run without Claude thinking. No tokens. No context window. Just code.

- **Heartbeat** — Docker health checks on each container
- **Organ self-health reflexes** — scanner checks its own tools, screams if blind
- **Fill confirmation** — executor broadcasts lifecycle on broker fill
- **Stop-loss trigger** — monitor flags when price hits stop
- **Circuit breakers** — max daily loss → halt trading
- **Signal bus** — PostgreSQL table always available, no AI needed to write

### 6.2 Bridge (Firmware Default, Cognitively Adjustable)

Run automatically but the brain can adjust parameters:

- **Attention focus** — system prompt sections determine what the Decision Engine weights
- **Risk thresholds** — default limits in place, brain can adjust within bounds
- **Alert sensitivity** — what severity level triggers mode changes

### 6.3 Cognitive (Requires Claude AI)

These consume tokens and context window:

- **Decision Engine** — trade evaluation, candidate assessment, tier classification
- **Strategy** — what to scan for, when to adapt approach
- **Learning** — recording observations, updating CLAUDE-LEARNINGS.md
- **Inter-agent** — communication with big_bro (consciousness)

---

## 7. Memory Architecture in Catalyst

### 7.1 Three Tiers (Current)

| Tier | File | v7 Mapping | Persistence |
|---|---|---|---|
| Long-term | `CLAUDE.md` | Archetype + bones | Permanent. Always loaded. Identity. |
| Medium-term | `CLAUDE-LEARNINGS.md` | Consolidated patterns | Weeks/months. Proven knowledge. |
| Short-term | `CLAUDE-FOCUS.md` | Working memory | Hours/days. Current tasks. Pruned. |

### 7.2 Memory Flow

```
Observation during trading cycle
    → recorded in CLAUDE-FOCUS.md (short-term)
        → during Pondering mode, patterns identified
            → promoted to CLAUDE-LEARNINGS.md (medium-term)
                → with big_bro approval, absorbed into CLAUDE.md (long-term)
```

### 7.3 v7 Gap: Distributed Memory

v7 says memories should be stored at the sensory source — eyes have visual memories, ears have auditory memories. Catalyst currently centralises memory in the brain's files.

Future: MCP servers could maintain their own learned patterns (scanner learns which technical patterns succeed, executor learns which order types fill fastest). The brain's memory files become the binding index (hippocampus), not the only store.

---

## 8. MCP as Tool Separation

From v7 Section 12.3: MCP servers are the hands. Claude is the brain. The hands do their work without consuming brain attention.

In Catalyst:
- Claude Code (brain) calls MCP tools with **intent** (what to do)
- MCP server (organ) executes in its own Docker container, own process, own memory
- Result returns to Claude — only the output enters the context window
- Everything between (API calls, database queries, calculations) happens OUTSIDE

This protects the brain's attention budget. The brain doesn't hold Moomoo API response parsing in its context. It sends "get quote for 0700" and receives a clean result.

```
Claude Code (brain)
    │
    ├── MCP: market-scanner    → scan, quote, technicals, patterns, news
    ├── MCP: trade-executor    → buy, sell, close, check_risk
    └── MCP: position-monitor  → exit recommendations, P&L
    
    Each MCP server = Docker container = own process = outside attention
```

---

## 9. Deployments

### 9.1 International (INTL — Production)

- **Droplet:** DigitalOcean
- **Brain:** intl_claude (Claude Code)
- **Broker:** Moomoo (Hong Kong market)
- **Signal bus:** PostgreSQL signals table
- **Organs:** MCP servers in Docker containers
- **Schedule:** Cron-driven cycles during HK market hours

### 9.2 US (Planned — Experimental)

- **Droplet:** DigitalOcean (US region)
- **Brain:** public_claude (Claude Code)
- **Broker:** Alpaca (US market, paper trading initially)
- **Signal bus:** Redis pub/sub (event-driven broadcast)
- **Organs:** Docker containers with firmware heartbeat/listener/publisher
- **Schedule:** Event-driven + cron during US market hours

The US system implements the full v7 broadcast architecture with Redis. See: `catalyst-us-signal-architecture.md`.

---

## 10. Approximation Levels

The AI Agent Architecture has evolved through versions. Little bro (intl_claude) implemented based on the version available at the time. The implementation therefore carries variance from the current v7:

### 10.1 What Was Implemented (v2-v3 era)

| Concept | Implemented As | Status |
|---|---|---|
| Neuron model | Signal identifier (severity × domain × scope) | ✅ Working |
| Brain/organ separation | Coordinator + MCP servers | ✅ Working |
| Survival hierarchy | Survival Pulse component, checked first | ✅ Working |
| Discipline/character | Discipline Gate component | ✅ Working |
| Brain components | Python classes in coordinator | ✅ Working |
| Organ reflexes | Self-health, fill confirm, stop-loss | ✅ Working |
| Signal bus | PostgreSQL signals table | ✅ Working |
| Memory tiers | Three files (CLAUDE.md, LEARNINGS, FOCUS) | ✅ Working |
| Archetype | CLAUDE.md + system_prompt.py | ✅ Working |

### 10.2 What v7 Adds (Not Yet Implemented)

| v7 Concept | Gap | Priority |
|---|---|---|
| Two signal directions (broadcast vs consolidation) | Signals are currently polling-based, no dedicated consolidator | HIGH — US implementation |
| Redis pub/sub broadcast | Currently PostgreSQL polling | HIGH — US implementation |
| PFC mode as system-wide switch | Modes implicit in system prompt, not explicit state variable reconfiguring all components | MEDIUM |
| Firmware/bridge/cognitive explicit separation | Exists implicitly, not labelled in code | MEDIUM |
| Consolidator service (pons) | Brain does its own signal assembly | MEDIUM — US implementation |
| Task matrices as intent-level | Brain currently sends operational detail to organs, not pure intent | MEDIUM |
| Distributed memory at source | All memory centralised in brain files | LOW |
| Types of learning attention | Pondering exists, types not differentiated | LOW |
| Sleep phases (NREM/REM) | Consolidation exists, phases not separated | LOW |
| Chemical stamping with de-intensification | Critical signals stored but no de-intensification cycle | LOW |
| Autonomy tiers | Implicit — intl_claude operates at Apprentice/Practitioner | LOW |
| Community multiplier | big_bro + intl_claude interaction exists but not quantified | LOW |

### 10.3 Variance Is Expected

Little bro implemented what was available. The architecture grew through implementation experience — production failures drove v2 (survival hierarchy), component interactions drove v3 (neuron model), and today's session drove v7 (biological cognition model).

Each implementation adds another level of variance from the current architecture. This is healthy — implementation teaches us what the theory got wrong. The feedback loop (learn → build → do → monitor → analyse → improve) IS the product.

---

## 11. Founding Incident

Feb 11-13, 2026. The body bled out for 3 days. Zero trades despite HKD 994K cash.

Root causes:
1. Market Scanner's `get_technicals` broken — organ couldn't see
2. Brain had no Survival Pulse — couldn't detect broken organs
3. Brain had no Discipline Gate — couldn't detect stagnation
4. Brain had no Signal Receiver — couldn't hear organ pain
5. System prompt gave contradictory instructions — brain identity was confused

Fix: Build the brain's missing components. Add reflexes to the organs. Establish the survival hierarchy. This incident drove the Consciousness Architecture v2 and the Implementation Guide v2.

The founding incident is the most important memory. Chemical-stamped. Permanent.

---

## 12. Design Principles (Catalyst-Specific)

1. **Brain thinks, organs do.** All strategic decisions from the coordinator. Organs execute and reflex.
2. **Survival before trading.** Health check FIRST every cycle. Don't trade blind.
3. **Discipline before decisions.** Character enforcement before the Decision Engine engages.
4. **Pain is loud.** CRITICAL signals override everything. By design.
5. **Organs scream.** Every organ monitors its own tools and broadcasts failure.
6. **Signal bus is the medulla.** If it fails, the body goes deaf. Check first.
7. **MCP is the body.** Tools operate in their own containers, outside brain compute.
8. **Memory has tiers.** Not everything is permanent. Promote through consolidation.
9. **The Archetype defines identity.** CLAUDE.md loaded first. Identity before memory.
10. **Implementation teaches architecture.** Production failures refine the theory. The feedback loop is the product.

---

## 13. Related Documents

| Document | Version | Scope |
|---|---|---|
| AI Agent Architecture | v7.0 | General pattern — biology, domain-independent |
| AI Consciousness Architecture | v3.0 (needs rewrite) | AI-human interaction — formation, community |
| Catalyst Implementation Guide | v2.0 | Phase-by-phase build instructions for INTL |
| Catalyst US Signal Architecture | v1.0 | Redis broadcast design for US system |

---

*"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body."* — Romans 12:4-5

*Catalyst AI Architecture v1.0 — Craig + Claude — 2026-02-17*
