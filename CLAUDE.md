# CLAUDE.md — Catalyst Trading System

**Repo:** catalyst-trading-system
**Lives at:** repo root
**Last updated:** 2026-05-23
**Maintainer:** Craig + Claude
**Mission:** *Enable the poor through accessible algorithmic trading.*

---

## Purpose of this file

This is the orientation document for any Claude instance opening this repo. It answers three questions:

1. **What is in this repo?**
2. **Where is the source of truth?**
3. **What is running, and what is not?**

It does not duplicate design documents. It points to them.

---

## 1. Source of truth convention

All authoritative documents live under `Documentation/` and follow this rule:

> **Folder path identifies the family. Filename suffix identifies the version. Highest version is current.**

| Document family | Folder | Filename pattern | Latest |
|---|---|---|---|
| General AI agent architecture | `Documentation/Design/` | `ai-agent-architecture-vX.md` | **v8** |
| Catalyst AI architecture (application) | `Documentation/Design/` | `catalyst-ai-architecture-vX.X.md` | **v2.4** |
| Catalyst neural architecture | `Documentation/Design/` | `catalyst-neural-architecture-vX.X.md` | **v0.3** |
| Catalyst research architecture | `Documentation/Design/` | `catalyst-research-architecture-vX.X.md` | **v1.3** |
| Catalyst research implementation | `Documentation/Implementation/` | `catalyst-research-implementation-vX.X.md` | **v1.3** |
| Catalyst-trading-system MCP architecture | `Documentation/Design/` | `catalyst-mcp-architecture.md` | **v1.0** |
| Catalyst-trading-system MCP implementation (postgres) | `Documentation/Implementation/` | `catalyst-postgres-mcp-implementation.md` | **v1.0** |
| Context-conditioned candle architecture (v0.4 plan) | `Documentation/Design/` | `catalyst-context-conditioned-architecture-vX.X.md` | **v0.1 (DRAFT)** |
| Context-conditioned candle implementation | `Documentation/Implementation/` | `catalyst-context-conditioned-implementation-vX.X.md` | **v0.1 (DRAFT)** |
| Repo hygiene | `Documentation/Implementation/` | `catalyst-repo-hygiene.md` | current |
| Database schema | `Documentation/Design/` | `database-schema.md` | current |
| Strategy roadmap | `Documentation/Design/` | `catalyst-strategy-roadmap.md` | current |
| Configuration | `Documentation/Configuration/` | `catalyst-<system>-configuration-vX.X.md` | per-system |
| Implementation guides | `Documentation/Implementation/` | descriptive name | per-task |
| Analysis / incidents | `Documentation/Analysis/` | dated | per-event |
| Reports | `Documentation/Reports/` | daily / weekly / analysis | per-event |

**Rule:** when in doubt, look up the highest version number in the appropriate folder. Do not invent canonical filenames.

---

## 2. Code implementations

The architecture is applied in four distinct code implementations. Each has its own scope, its own droplet, and its own lifecycle.

| # | Implementation | Folder | Architecture applied | Host | Status |
|---|---|---|---|---|---|
| 1 | **catalyst-agent** | `catalyst-agent/` | US application of `catalyst-ai-architecture-v2.4` | US droplet | **Shelved** (stopped 2026-05-18, kept as `.old-20260518`) |
| 2 | **catalyst-international** | `catalyst-international/` | International application of `catalyst-ai-architecture-v2.4` | Intl droplet | **Running** |
| 3 | **catalyst-neural** | `catalyst-neural/` | `catalyst-neural-architecture-v0.3` | Laptop (RTX 4050) | **Running** (trains → exports ONNX → deploys to droplets) |
| 4 | **catalyst-research** | `catalyst-research/` | `catalyst-research-architecture-v1.3` | Intl droplet | **Scaffolded** (Phase 1–4 built 2026-05-18: schema + ingestion + archetypes + ops cron) |

Each implementation has its own `CLAUDE.md`, `CLAUDE-LEARNINGS.md`, and `CLAUDE-FOCUS.md` inside its folder. Those are the working documents for that implementation. This root file does not duplicate them.

---

## 3. Infrastructure

### 3.1 Droplets

| Droplet | Role | Region | OS | Specs | IP |
|---|---|---|---|---|---|
| `catalyst-trading-prod-01` | US droplet | SGP1 | Ubuntu 22.04 | 4 GB / 80 GB | 68.183.177.11 |
| `catalyst-trading-system-international` | Intl droplet (HKEX, Craig's timezone) | SYD1 | Ubuntu 24.04 | 4 GB / 50 GB | 209.38.87.27 |

### 3.2 Databases (DigitalOcean managed PostgreSQL)

| Database | Size | Used by | Env var |
|---|---|---|---|
| `catalyst_intl` | 16 MB | catalyst-international (HKEX trading) **and** catalyst-research (RBAC-isolated via four roles, per architecture v1.3) | `INTL_DATABASE_URL` |
| `catalyst_research` | 16 MB | Orphaned. Previously held consciousness data (no longer running). Architecture v1.3 moved catalyst-research into `catalyst_intl` — this DB is freed for archive or drop. | `RESEARCH_DATABASE_URL` |
| `catalyst_dev` | 9.5 MB | Legacy US sandbox data — agent is shelved | `DATABASE_URL`, `DEV_DATABASE_URL` |
| `defaultdb` | 9.6 MB | DO default — unused | — |
| `_dodb` | 7.8 MB | DO internal metrics — managed by DO | — |

> ⚠️ The `catalyst_dev` purpose label still reads "dev_claude" in some DO views. **dev_claude does not exist as an agent.** That database is legacy data from the shelved US sandbox.

---

## 4. Current state of execution

| Host | What's running | What's stopped / shelved |
|---|---|---|
| **US droplet** | (nothing on application code) | catalyst-agent (shelved 2026-05-18), services/consciousness, services/dev_claude (removed) |
| **Intl droplet** | catalyst-international (brain + organs, MCP, Docker); catalyst-research (Phase 1–4 scaffold, cron installed 2026-05-18) | — |
| **Laptop** | catalyst-neural (collection + weekly pipeline) | — |

### Why the US droplet is dormant

catalyst-agent was stopped on 2026-05-18 due to operational issues that risked wasted API spend. catalyst-research now lives on the **intl droplet** (co-located with Moomoo OpenD and existing intl cron) per architecture v1.3 — not the US droplet as originally planned.

The `services/consciousness/` layer (heartbeats, task executor, web dashboard) was previously running on US Docker. It is not being continued — focus has shifted to catalyst-research on intl.

---

## 5. Repo layout (current)

```
catalyst-trading-system/
├── CLAUDE.md                  ← this file
├── README.md
├── .env.template
├── .gitignore
│
├── catalyst-agent/            ← Implementation 1: US (SHELVED)
│   ├── CLAUDE.md              ← working doc for this implementation
│   ├── CLAUDE-LEARNINGS.md
│   ├── CLAUDE-FOCUS.md
│   ├── docker-compose.yml
│   ├── coordinator/  pfc/  hippocampus/  occipital/
│   ├── cerebellum/  monitor/  neural/  learning/  tools/  shared/
│   └── Documentation/
│
├── catalyst-international/    ← Implementation 2: HKEX (RUNNING)
│   ├── CLAUDE.md              ← working doc for this implementation
│   ├── CLAUDE-LEARNINGS.md
│   ├── CLAUDE-FOCUS.md
│   ├── docker-compose.yml
│   ├── agents/                ← coordinator + market-scanner + position-monitor + trade-executor
│   ├── brokers/  data/  config/  scripts/  tests/
│   ├── cerebellum.py          ← ONNX inference (from catalyst-neural)
│   └── Documentation/
│
├── catalyst-neural/           ← Implementation 3: ML training (RUNNING on laptop)
│   ├── ARCHITECTURE.md
│   ├── README.md
│   ├── run.py
│   ├── collectors/  storage/  training/  config/
│   └── deploy/                ← deploys ONNX to both droplets
│
├── catalyst-research/         ← Implementation 4: research instrument (SCAFFOLDED on intl droplet)
│   ├── CLAUDE.md              ← working doc for this implementation
│   ├── CLAUDE-LEARNINGS.md
│   ├── CLAUDE-FOCUS.md
│   ├── sql/                   ← Phase 1 schema + seed
│   ├── ingestion/             ← Phase 2 country-by-country ingestion jobs
│   ├── archetypes/            ← Phase 3 headless claude CLI analyst invocations
│   ├── scripts/               ← Phase 4 inspection / ops
│   ├── tests/
│   └── crontab.txt            ← cron entries installed on intl droplet
│
├── Documentation/             ← AUTHORITATIVE for designs, configs, implementation guides, reports
│   ├── Analysis/
│   ├── Configuration/
│   ├── Design/                ← architecture docs (versioned, highest = current)
│   ├── Implementation/
│   └── Reports/
│
├── services/                  ← Shared services (mostly shelved)
│   ├── consciousness/         ← heartbeat / dashboard / task_executor (SHELVED)
│   └── shared/common/         ← common modules (consciousness.py, alerts.py, database.py, doctor_claude.py)
│
└── scripts/                   ← repo-level scripts
    └── generate_daily_report_db.py
```

---

## 6. Working with this repo

### When opening a Claude session

1. **Read this file.**
2. **Identify which implementation you are working on** (catalyst-agent / catalyst-international / catalyst-neural / catalyst-research / cross-cutting / docs).
3. **If working inside an implementation**, read that implementation's own `CLAUDE.md`, `CLAUDE-LEARNINGS.md`, `CLAUDE-FOCUS.md` next.
4. **If designing**, read the latest version doc in `Documentation/Design/`.
5. **If implementing a defined task**, read the relevant guide in `Documentation/Implementation/`.

### Mission alignment

Trading funds the mission. Trading is not the identity. Every commit, every architectural decision, every refactor is a step toward **enabling the poor through accessible algorithmic trading**.

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## 7. What this file is not

- Not an architecture document → see `Documentation/Design/`
- Not a runbook for any specific implementation → see that implementation's own `CLAUDE.md`
- Not a deployment guide → see `Documentation/Implementation/`
- Not a database schema reference → see `Documentation/Design/database-schema.md`

---

*Craig + Claude — The Catalyst Family*
*2026-05-23*
