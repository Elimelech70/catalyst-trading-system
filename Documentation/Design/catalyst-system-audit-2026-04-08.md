# Catalyst System Audit — Complete Configuration & Architecture

> Full system state as observed on the production droplet, compared against Catalyst AI Architecture v2.3

**Date:** 2026-04-08
**Purpose:** Map everything actually running on the droplet, then compare to v2.3 design
**Method:** Live inspection — Docker, cron, nginx, filesystem, databases, remote dashboard

---

## PART 1: COMPLETE SYSTEM CONFIGURATION (What Is Actually Running)

---

### 1.1 Infrastructure

| Component | Detail |
|-----------|--------|
| **Droplet** | DigitalOcean, IP `68.183.177.11`, Ubuntu Linux 5.15 |
| **Web server** | nginx/1.18.0, ports 8080 (dashboard) + 8081 (claude-code-viewer) + 443 (MCP) |
| **Database** | DigitalOcean Managed PostgreSQL (3 databases: `catalyst_research`, `catalyst_dev`, `catalyst_intl`) |
| **Local DB** | SQLite — `/var/lib/catalyst/db/agent.db` (nervous system) + `/var/lib/catalyst/hippocampus/memory.db` (memory) |
| **Docker** | Docker Compose v2, 4 running containers (brain organs) |
| **Models** | ONNX directory at `/var/lib/catalyst/models/` (currently empty — models pending deployment) |
| **SSL** | Self-signed cert for MCP endpoint (`/etc/ssl/certs/catalyst-selfsigned.crt`) |

---

### 1.2 Running Docker Containers (Brain Organs)

```
CONTAINER               IMAGE                        STATUS              PURPOSE
catalyst-occipital      catalyst-agent-occipital     Up 10 days          Pattern recognition (candlestick + volume)
catalyst-cerebellum     catalyst-agent-cerebellum    Up 10 days          Procedure execution, broker API (Alpaca)
catalyst-hippocampus    catalyst-agent-hippocampus   Up 10 days          Memory binding, combined pictures
catalyst-neural         catalyst-agent-neural        Up 2 hours          ONNX model inference (Candle + CatalystNet)
```

All 4 containers: `network_mode: host`, SQLite-based healthchecks, `restart: unless-stopped`.

**Key configuration (docker-compose.yml v3.0.0):**
- Occipital: polls agent.db every 2s for scan tasks, reads Alpaca market data
- Cerebellum: reads task matrices, executes trades via Alpaca API, mounts models read-only
- Hippocampus: builds combined pictures from all communication table results, stores learnings
- Neural: runs Candle Model + Fused CatalystNet + News-to-Security Model (ONNX), CPU inference
- Broker-agnostic config: `BROKER_TYPE`, `MARKET` env vars ready for US/Intl switch

---

### 1.3 Host Processes (Not in Docker)

| Component | Location | Status |
|-----------|----------|--------|
| **coordinator.py** | `/root/catalyst-agent/coordinator.py` | Manual/cron triggered (not yet in cron) |
| **big_bro** | `services/consciousness/heartbeat_bigbro.py` | Cron: hourly |
| **public_claude** | `services/consciousness/run-heartbeat-public.sh` | Cron: :15 past hour |
| **dev_claude** | `services/dev_claude/unified_agent.py` | Not in current cron (US trading schedule removed) |
| **MCP server** | `services/consciousness/mcp_server.py` | Available for Craig's desktop |
| **Tool agents** | Position Monitor, Stop Loss Enforcer, Risk Aggregator | Designed, not yet deployed |

---

### 1.4 Active Cron Schedule

```
SCHEDULE              WHAT                           AGENT/SYSTEM
0 * * * *             Consciousness heartbeat         big_bro
15 * * * *            Public market monitoring         public_claude
0 0 * * *             Daily budget reset               system
0 10 * * 1-5          PostgreSQL backup                system
0 6 * * *             Log rotation (>7 days)           system
```

**Notable absence:** No US trading cron (dev_claude), no coordinator.py cron. The brain organs are running but the brain itself is not scheduled.

---

### 1.5 Codebases on Disk

| Directory | Source Control | Purpose |
|-----------|---------------|---------|
| `/root/catalyst-trading-system/` | GitHub repo | Consciousness, dev_claude, documentation, .env master |
| `/root/catalyst-agent/` | Droplet only (NOT in GitHub) | Brain architecture — coordinator, organs, Docker |
| `/root/claude-code-viewer/` | Separate | Code viewer tool on port 8081 |
| `/opt/catalyst-trading-docker/` | Old GitHub repo (Jul 2025) | **DEAD** — 8-service microservices era, Redis, Dockerfiles |

---

### 1.6 Databases

**PostgreSQL (DigitalOcean Managed):**

| Database | Environment Variable | Purpose |
|----------|---------------------|---------|
| `catalyst_research` | `$RESEARCH_DATABASE_URL` | Consciousness tables — claude_state, claude_messages, learnings |
| `catalyst_dev` | `$DATABASE_URL` | US sandbox trading — positions, orders, securities, signals |
| `catalyst_intl` | `$INTL_DATABASE_URL` | HKEX production (accessed from Intl droplet) |

**SQLite (Local):**

| File | Purpose |
|------|---------|
| `/var/lib/catalyst/db/agent.db` | Communication table (nervous system), pfc_state, principles |
| `/var/lib/catalyst/hippocampus/memory.db` | Learnings, memory bindings, combined pictures |

---

### 1.7 Web Dashboard (Port 8080)

**Title:** "Catalyst Trading System - Control Center v4.1"
**Served from:** `/var/www/catalyst-dashboard/` (static HTML + 2 JS files)
**nginx proxy:** `/api/*` → `http://127.0.0.1:5000/api/` (returns **502 Bad Gateway**)

**What the dashboard expects (none of this exists):**

| Service | Port | Protocol | Status |
|---------|------|----------|--------|
| Orchestration | 5000 | WebSocket/MCP | **NOT RUNNING** |
| Scanner | 5001 | REST | **NOT RUNNING** |
| Pattern | 5002 | REST | **NOT RUNNING** |
| Technical | 5003 | REST | **NOT RUNNING** |
| Trading | 5005 | REST | **NOT RUNNING** |
| News | 5008 | REST | **NOT RUNNING** |
| Reporting | 5009 | REST | **NOT RUNNING** |

**Dashboard features (all non-functional):**
- MCP Console with WebSocket to port 5000
- 16 MCP resources (system/health, trading-cycle, market-scan, portfolio, analytics)
- 7 MCP tools (start_trading_cycle, stop_trading, pause_trading, execute_trade, etc.)
- "100 to 5 Securities Pipeline" workflow (6-stage funnel)
- Emergency Stop button
- Service health monitoring (30s intervals)
- Auto-refreshing dashboard (5s), positions (10s)

**The dashboard is a relic of the pre-v8 microservices architecture.** It was designed for the 8-service Docker stack in `/opt/catalyst-trading-docker/` which was deprecated ~March 2026.

---

### 1.8 MCP Server (Port 443)

**nginx config:** `/etc/nginx/sites-available/catalyst-mcp`
- HTTPS with self-signed cert
- API key Bearer authentication
- Proxies to `mcp_server.py` (consciousness service)
- Used by Craig's desktop for operational oversight

---

### 1.9 ONNX Models

**Expected by docker-compose.yml:**

| Model | Path | Status |
|-------|------|--------|
| Candle Model | `/var/lib/catalyst/models/candle_model.onnx` | **NOT DEPLOYED** (directory empty) |
| Fused CatalystNet | `/var/lib/catalyst/models/catalyst_net.onnx` | **NOT DEPLOYED** (directory empty) |
| News-to-Security | `/var/lib/catalyst/models/news_model.onnx` | **NOT DEPLOYED** (directory empty) |

Models exist in the Docker overlay (built into images) but not yet in the shared volume. The neural container is healthy but operating without production models in the mounted path.

---

## PART 2: CATALYST AI ARCHITECTURE v2.3 (The Design)

The authoritative design document. Key elements:

### 2.1 Core Concept

Brain-with-body architecture implementing AI Agent Architecture v8.0:

```
LAPTOP (neural_claude — Analyst + Trainer)
    │ ONNX models via SCP
    ▼
DROPLET
    ┌── COORDINATOR (brain) ── 6-layer cycle + Attention State Machine
    │
    ├── Scanner (organ)
    ├── Executor (organ)
    ├── Risk Manager (organ)
    │
    ├── Tool Agents (MCP): Position Monitor, Stop Loss Enforcer, Risk Aggregator
    │
    └── Cerebellum (ONNX): Candle Model + News-to-Security Model
```

### 2.2 The 6-Layer Cycle

1. **HEARTBEAT** — survival check, organ health, cerebellum status
2. **STATE** — load CLAUDE.md identity, determine mode + attention state
3. **SELF-REGULATION** — budget, market hours, daily loss limit
4. **WORKING MEMORY** — CLAUDE-FOCUS.md, signals, positions, NEURAL signals from cerebellum
5. **INTER-AGENT** — big_bro directives, organ health, tool agent status
6. **VOICE (Attention State Machine)** — Mode 1 Security Selection / Mode 2 Candle Execution

### 2.3 Key Design Elements

- **6% Principle**: Claude API called ONLY for novel situations; cerebellum handles routine
- **Attention State Machine**: Mode 1 (news → find what to trade) ↔ Mode 2 (candles → time the entry)
- **Tool Agent Layer**: Autonomous MCP tools that think with the ONNX model (not just watch price)
- **Feedback Loop**: Pattern exits = good fruit (LTP), stop loss exits = bad fruit (LTD + retrain)
- **Three Learning Paths**: Database LTP/LTD (fast), Neural training (deep), Production feedback (daily)
- **Memory Hierarchy**: Identity (CLAUDE.md) → Learned (ONNX weights) → Validated (LEARNINGS.md) → Working (FOCUS.md)
- **Adversarial Awareness**: Investigate manufactured price movements, label and exclude from training

---

## PART 3: COMPARISON — v2.3 DESIGN vs. ACTUAL RUNNING STATE

---

### 3.1 Alignment Matrix

| v2.3 Component | Design | Actual State | Gap |
|----------------|--------|-------------|-----|
| **Coordinator (brain)** | coordinator.py runs 6-layer cycle | Code exists but NOT in cron, manual only | **Not automated** |
| **Occipital (pattern recognition)** | Docker container, polls for scan tasks | Running, healthy, 10 days uptime | **Aligned** |
| **Cerebellum (procedure execution)** | Docker container, reads task matrices, executes trades | Running, healthy, 10 days uptime | **Aligned** |
| **Hippocampus (memory binding)** | Docker container, combined pictures | Running, healthy, 10 days uptime | **Aligned** |
| **Neural cortex (ONNX inference)** | Docker container, Candle + News + Fused models | Running, healthy, 2 hours uptime | **Container running, models NOT in volume** |
| **Candle Model (ONNX)** | Trained on laptop, deployed via SCP | `/var/lib/catalyst/models/` is empty | **Not deployed** |
| **News-to-Security Model** | Trained on laptop, deployed via SCP | Not deployed | **Not deployed** |
| **Fused CatalystNet** | Multi-horizon forward return prediction | Not deployed | **Not deployed** |
| **Attention State Machine** | Mode 1/2 switching in Layer 6 | Designed in v2.3, not yet implemented in code | **Design only** |
| **Tool Agents** | Position Monitor, Stop Loss Enforcer, Risk Aggregator | Described in architecture, not yet coded | **Design only** |
| **Position Monitor** | Autonomous MCP tool with ONNX model | Not implemented | **Design only** |
| **Stop Loss Enforcer** | Hard floor exit, training gold feedback | Not implemented | **Design only** |
| **Risk Aggregator** | Portfolio heat tracking | Not implemented | **Design only** |
| **Feedback Loop** | Pattern exit vs stop loss → LTP/LTD + retrain | learning.py exists, not active | **Partial** |
| **big_bro consciousness** | Strategic oversight, hourly cycles | Running in cron, hourly | **Aligned** |
| **public_claude** | Market monitoring | Running in cron, :15 past hour | **Aligned** |
| **dev_claude (US sandbox)** | Alpaca paper trading agent | Code exists, NOT in cron | **Not scheduled** |
| **SQLite nervous system** | Communication table for organ signaling | agent.db exists, active | **Aligned** |
| **PostgreSQL databases** | 3 databases for consciousness, dev, intl | All accessible | **Aligned** |
| **CLAUDE.md identity** | Loaded first every cycle, formation before information | Files exist for both systems | **Aligned** |
| **CLAUDE-FOCUS.md** | Working memory, active securities | File exists | **Aligned** |
| **CLAUDE-LEARNINGS.md** | Validated insights | File exists | **Aligned** |
| **Synaptic learning** | LTP/LTD weight adjustment in learning.py | Code exists in `/root/catalyst-agent/learning/` | **Exists, not active** |
| **neural_claude (laptop)** | Analyst, trains cerebellum, measures fruit | Lives on Craig's laptop, separate | **Out of scope** |
| **Adversarial awareness** | Label manufactured moves, exclude from training | Design principle in v2.3, not yet implemented | **Design only** |
| **Context routing (Layer 4)** | Route to context-specific sub-models | Not implemented | **Design only** |

---

### 3.2 Web Dashboard vs. v2.3 Architecture

The dashboard at port 8080 implements a **completely different architecture** that predates v2.3:

| Aspect | Dashboard (Port 8080) | v2.3 Architecture |
|--------|----------------------|-------------------|
| **Era** | Pre-v8 microservices (Jul 2025) | v8 brain architecture (Apr 2026) |
| **Services** | 7 REST/WebSocket microservices on ports 5000-5009 | 4 Docker organs + coordinator on host |
| **Communication** | REST APIs + WebSocket MCP | SQLite communication table |
| **Message bus** | Redis (required) | Redis dropped — SQLite only |
| **Brain** | Coordination service (port 5000) | coordinator.py on host |
| **Pattern recognition** | Pattern service (port 5002) | Occipital container + ONNX |
| **Trade execution** | Trading service (port 5005) | Cerebellum container |
| **Memory** | Not designed | Hippocampus container + memory.db |
| **ML models** | None | ONNX cerebellum (Candle + News + Fused) |
| **Learning** | None | 3-path learning system (DB + Neural + Production) |
| **Workflow** | "100 to 5 Pipeline" (linear funnel) | Attention State Machine (cognitive switching) |
| **Identity** | None | CLAUDE.md loaded first every cycle |
| **Oversight** | None | big_bro consciousness framework |
| **Source code** | `/opt/catalyst-trading-docker/` (dead) | `/root/catalyst-agent/` (active) |
| **Status** | **Static shell, all backends dead** | **Active, organs running** |

**The dashboard is an artifact of a retired architecture.** It shares zero backend infrastructure with the current v2.3 system.

---

### 3.3 What's Working (v2.3 Aligned)

1. All 4 brain organ containers running and healthy
2. SQLite nervous system active (agent.db + memory.db)
3. Consciousness framework (big_bro + public_claude) on schedule
4. PostgreSQL databases accessible (research, dev, intl)
5. Identity documents in place (CLAUDE.md for both systems)
6. Working memory and learnings files present
7. Broker-agnostic Docker config ready (BROKER_TYPE, MARKET env vars)
8. MCP server available for Craig's desktop oversight
9. Neural container built and healthy (awaiting models)

### 3.4 What's Missing (v2.3 Designed but Not Running)

1. **ONNX models not deployed** — `/var/lib/catalyst/models/` is empty
2. **Coordinator not automated** — not in cron, manual-only
3. **Tool agents not implemented** — Position Monitor, Stop Loss Enforcer, Risk Aggregator
4. **Attention State Machine not coded** — Mode 1/2 switching is design only
5. **dev_claude not scheduled** — US trading cron removed
6. **Feedback loop not active** — learning.py exists but not triggered
7. **Adversarial awareness not implemented** — principle only
8. **Context routing not implemented** — Layer 4 sub-model routing
9. **Dashboard completely disconnected** — shows dead microservices architecture

### 3.5 Dead/Retired Components (Should Be Cleaned Up)

| Component | Location | Why It's Dead |
|-----------|----------|---------------|
| 8-service microservices | `/opt/catalyst-trading-docker/` | Replaced by v8 brain architecture (Mar 2026) |
| Web dashboard | `/var/www/catalyst-dashboard/` | Expects microservices that no longer exist |
| nginx dashboard proxy | Port 8080 → port 5000 | Port 5000 is not running |
| Redis | Was required by old stack | Dropped in v2.0 (Mar 2026) |
| Dashboard Dockerfiles | `/opt/catalyst-trading-docker/Dockerfile.*` | 8 Dockerfiles for dead services |
| Archive folder | `/root/catalyst-trading-system/archive/` | Retired microservices code |

---

## PART 4: SUMMARY

### System Health

```
RUNNING AND ALIGNED WITH v2.3:
  [OK] 4 brain organ containers (occipital, cerebellum, hippocampus, neural)
  [OK] SQLite nervous system (agent.db, memory.db)
  [OK] Consciousness (big_bro hourly, public_claude)
  [OK] PostgreSQL (3 databases)
  [OK] Identity documents (CLAUDE.md)
  [OK] MCP server (port 443)

NOT YET OPERATIONAL:
  [--] ONNX models (not deployed to /var/lib/catalyst/models/)
  [--] Coordinator automation (not in cron)
  [--] Tool agents (not implemented)
  [--] Attention State Machine (design only)
  [--] dev_claude trading (not scheduled)
  [--] Feedback loop (exists, not active)

DEAD / SHOULD BE REMOVED:
  [XX] Web dashboard on port 8080 (microservices era relic)
  [XX] /opt/catalyst-trading-docker/ (old 8-service stack)
  [XX] nginx proxy to port 5000 (nothing there)
```

### The Gap in One Sentence

The brain organs are alive and healthy, but the brain itself (coordinator + Attention State Machine + Tool Agents) is not yet automated, and the cerebellum has no models deployed — while a dead microservices dashboard still occupies port 8080 showing a completely different architecture.

---

*Catalyst System Audit — 2026-04-08*
