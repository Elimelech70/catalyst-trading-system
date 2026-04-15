# Catalyst US Runtime Configuration

> *"Unless the LORD builds the house, the builders labour in vain."* — Psalm 127:1

**Version:** 1.0.0
**Date:** 2026-04-15
**Authors:** Craig + Claude
**Type:** Configuration Document
**Status:** Living Document
**Implements:** Catalyst AI Architecture v2.4
**Deployment:** US Region — Alpaca (NYSE, NASDAQ)

---

## Document Classification

| Type | Purpose | This document |
|---|---|---|
| **Architecture** | Design pattern — the what and the why. Broker-agnostic. | Catalyst AI Architecture v2.4 |
| **Configuration** | Realised state — how the architecture runs on a specific droplet. | Catalyst US Configuration v1.0 |
| **Runtime** | Operational state — how to start, stop, monitor, and maintain. | This document |

This document describes how to run the v2.4 architecture on the US droplet. It covers startup, shutdown, cron automation, log management, backup strategy, and troubleshooting. The Architecture document describes the design. The Configuration document describes the implementation. This document describes the operations.

---

## REVISION HISTORY

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-04-15 | Initial runtime document — formalises the operational setup from CRON-SETUP-REPORT (2026-04-11) |

---

## 1. Droplet

| Property | Value |
|---|---|
| Hostname | `catalyst-trading-prod-01` |
| Provider | DigitalOcean |
| Region | US |
| OS | Ubuntu 22.04.5 LTS |
| Kernel | 5.15.0-173-generic |
| CPUs | 2 |
| RAM | 3.8 GB |
| Disk | 78 GB (57 GB free) |
| Timezone | `Asia/Hong_Kong` (TZ env var) |

**Why HKT timezone on a US droplet:** Craig is in Perth (UTC+8). The droplet TZ is set to HKT so cron schedules and log timestamps align with Craig's working hours. All market-hours logic uses `America/New_York` internally — the droplet TZ does not affect trading.

---

## 2. Component Layout

```
HOST (not containerised)
├── coordinator.py          Long-running process (the brain)
├── Tool agents             Position Monitor, Stop Loss Enforcer, Risk Aggregator
├── PFC (Claude Code)       Called by coordinator for novel situations
├── Cron jobs               Watchdog, backup, daily reset, log rotation
│
DOCKER (containerised body)
├── catalyst-occipital      Pattern recognition
├── catalyst-cerebellum     Procedure execution + broker
├── catalyst-hippocampus    Memory binding
├── catalyst-monitor        Position monitoring / proprioception
└── catalyst-neural         ONNX model inference
```

---

## 3. Starting the System

### 3.1 Full Start (Cold Boot)

```bash
cd /root/catalyst-agent
scripts/run-coordinator.sh
```

`run-coordinator.sh` handles the full sequence:
1. Loads environment from `/root/catalyst-agent/.env`
2. Checks if Docker body is running — starts it if not (`docker compose up -d`)
3. Waits 5 seconds for containers to initialise
4. Starts the coordinator (`python3 -m coordinator.coordinator`)
5. Logs to `/var/log/catalyst-agent/coordinator.log`

The coordinator runs continuously. Layer 3 (Self-Regulation) handles market hours — safe to leave running 24/7.

### 3.2 Docker Body Only

```bash
cd /root/catalyst-agent
docker compose up -d
```

Starts all 5 body containers. Each has `restart: unless-stopped` — they survive droplet reboots if Docker is enabled at boot.

### 3.3 Coordinator Only (Body Already Running)

```bash
cd /root/catalyst-agent
set -a && source .env && set +a
python3 -m coordinator.coordinator >> /var/log/catalyst-agent/coordinator.log 2>&1 &
```

Or use the script:
```bash
nohup /root/catalyst-agent/scripts/run-coordinator.sh &
```

### 3.4 Verify Everything Is Running

```bash
# Docker body
docker ps --format "table {{.Names}}\t{{.Status}}"

# Coordinator process
ps aux | grep coordinator | grep -v grep

# Quick health check
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT cycle_count, current_layer, attention_mode, market_open, trading_enabled, updated_at FROM coordinator_state;"
```

---

## 4. Stopping the System

### 4.1 Full Stop

```bash
# Stop coordinator
pkill -f "coordinator.coordinator"

# Stop Docker body
cd /root/catalyst-agent
docker compose down
```

### 4.2 Coordinator Only (Keep Body Running)

```bash
pkill -f "coordinator.coordinator"
```

The body containers continue running. They poll the communication table — without a coordinator writing tasks, they idle harmlessly.

### 4.3 Emergency Stop (Kill Everything)

```bash
pkill -f "coordinator.coordinator"
cd /root/catalyst-agent && docker compose down
```

If positions are open, the broker-side stop losses remain active. Alpaca paper trading stops are server-side — they survive client disconnection.

**Important:** Disable the watchdog cron FIRST if you want the system to stay stopped, otherwise the watchdog will restart it within 5 minutes:

```bash
crontab -e
# Comment out the watchdog line:
# */5 * * * * /root/catalyst-agent/scripts/watchdog.sh
```

---

## 5. Cron Jobs

All cron jobs run under root's crontab. The crontab sets these environment variables at the top:

```
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
SHELL=/bin/bash
HOME=/root
CATALYST_HOME=/root/catalyst-agent
```

### 5.1 Watchdog

| Property | Value |
|---|---|
| Schedule | `*/5 * * * *` (every 5 minutes) |
| Script | `/root/catalyst-agent/scripts/watchdog.sh` |
| Log | `/var/log/catalyst-agent/watchdog.log` |
| Purpose | Health check — auto-restart coordinator or Docker body if down |

**What it checks:**
1. Each of the 5 Docker containers (`docker inspect --format='{{.State.Running}}'`)
2. Coordinator process (`pgrep -f "coordinator.coordinator"`)

**What it does on failure:**
- Missing container → `docker compose up -d` (restarts all body containers)
- Missing coordinator → launches `run-coordinator.sh` via `nohup`
- All healthy → logs `OK: Coordinator and body healthy`

**This is the system's self-healing mechanism.** If the coordinator crashes, the droplet reboots, or a container dies, the watchdog restores everything within 5 minutes.

### 5.2 Daily Reset

| Property | Value |
|---|---|
| Schedule | `0 21 * * 1-5` (21:00 HKT = 09:00 ET, weekdays) |
| Script | `/root/catalyst-agent/scripts/daily-reset.sh` |
| Log | `/var/log/catalyst-agent/daily-reset.log` |
| Purpose | Reset daily counters before US market open |

**What it does:**
1. Resets `daily_pnl` to 0.0 in `coordinator_state`
2. Purges completed communication messages older than 3 days

**Timing:** Runs at 09:00 ET (30 minutes before market open), giving the coordinator a clean daily state before trading begins.

### 5.3 Database Backup

| Property | Value |
|---|---|
| Schedule | `0 8 * * 1-5` (08:00 HKT, weekdays) |
| Script | `/root/catalyst-agent/scripts/backup-db.sh` |
| Log | `/var/log/catalyst-agent/backup.log` |
| Backup location | `/root/catalyst-agent/backups/` |
| Retention | 14 days |

**What it backs up:**
1. `agent.db` → `backups/agent_YYYYMMDD.db`
2. `memory.db` → `backups/memory_YYYYMMDD.db`

Uses SQLite `.backup` command — safe to run while the coordinator is writing. Old backups (>14 days) are automatically deleted.

### 5.4 Log Rotation

| Property | Value |
|---|---|
| Schedule | `0 6 * * *` (06:00 HKT, daily) |
| Command | `find /var/log/catalyst-agent -name "*.log" -size +50M -exec truncate -s 10M {} \;` |
| Purpose | Prevent log files from filling disk |

Truncates any log file over 50MB down to 10MB. Docker container logs are managed separately by Docker's json-file driver (10MB max, 3 rotated files per container — configured in `docker-compose.yml`).

### 5.5 Full Crontab

```cron
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
SHELL=/bin/bash
HOME=/root
CATALYST_HOME=/root/catalyst-agent

# WATCHDOG: Check coordinator + Docker body health (every 5 minutes)
*/5 * * * * /root/catalyst-agent/scripts/watchdog.sh

# DAILY RESET: Clear daily PnL + purge old messages (09:00 ET = 21:00 HKT)
0 21 * * 1-5 /root/catalyst-agent/scripts/daily-reset.sh

# DATABASE BACKUP: SQLite backup of agent.db + memory.db (08:00 HKT daily on weekdays)
0 8 * * 1-5 /root/catalyst-agent/scripts/backup-db.sh

# LOG ROTATION: Clean logs older than 7 days (06:00 HKT daily)
0 6 * * * find /var/log/catalyst-agent -name "*.log" -size +50M -exec truncate -s 10M {} \;
```

---

## 6. File Paths

### 6.1 Codebase

| Path | Content |
|---|---|
| `/root/catalyst-agent/` | Application codebase |
| `/root/catalyst-agent/.env` | Environment variables (secrets + config) |
| `/root/catalyst-agent/docker-compose.yml` | Docker service definitions |
| `/root/catalyst-agent/scripts/` | Operational scripts |
| `/root/catalyst-agent/backups/` | Database backup files |
| `/root/catalyst-agent/schema/` | SQL schema definitions |

### 6.2 Runtime Data

| Path | Content | Mounted By |
|---|---|---|
| `/var/lib/catalyst/db/agent.db` | Agent database (communication, signals, state, feedback) | All 5 containers + host |
| `/var/lib/catalyst/hippocampus/memory.db` | Hippocampus database (learnings, bindings, confidence) | Hippocampus container |
| `/var/lib/catalyst/models/candle_model.onnx` | Candle direction model | Neural + Cerebellum (read-only) |
| `/var/lib/catalyst/models/candle_model.onnx.data` | Candle model weights | Neural + Cerebellum (read-only) |
| `/var/lib/catalyst/models/catalyst_net.onnx` | Fused prediction model | Neural + Cerebellum (read-only) |
| `/var/lib/catalyst/models/catalyst_net.onnx.data` | Fused model weights | Neural + Cerebellum (read-only) |

### 6.3 Logs

| Path | Source | Rotation |
|---|---|---|
| `/var/log/catalyst-agent/coordinator.log` | Coordinator (brain) | Truncated at 50MB by cron |
| `/var/log/catalyst-agent/watchdog.log` | Watchdog script | Truncated at 50MB by cron |
| `/var/log/catalyst-agent/backup.log` | Backup script | Truncated at 50MB by cron |
| `/var/log/catalyst-agent/daily-reset.log` | Daily reset script | Truncated at 50MB by cron |
| Docker container logs | 5 body containers | json-file driver: 10MB max, 3 files |

### 6.4 Identity Documents

| Path | Tier | Purpose |
|---|---|---|
| `/root/catalyst-agent/CLAUDE.md` | Permanent | Agent identity — loaded Layer 2 every cycle |
| `/root/catalyst-agent/CLAUDE-LEARNINGS.md` | Validated | Proven insights — weeks/months |
| `/root/catalyst-agent/CLAUDE-FOCUS.md` | Working | Current session memory — hours/days |

---

## 7. Environment Variables

The `.env` file at `/root/catalyst-agent/.env` is loaded by both the coordinator (`run-coordinator.sh`) and Docker Compose.

| Variable | Value | Used By |
|---|---|---|
| `AGENT_ID` | `big_bro` | Coordinator, all queries |
| `BROKER_TYPE` | `alpaca` | All broker-aware components |
| `PAPER_TRADING` | `true` | Cerebellum, monitor |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Cerebellum, monitor |
| `ALPACA_DATA_URL` | `https://data.alpaca.markets` | Cerebellum, neural |
| `ALPACA_API_KEY` | `<secret>` | Cerebellum, occipital, monitor |
| `ALPACA_SECRET_KEY` | `<secret>` | Cerebellum, occipital, monitor |
| `ANTHROPIC_API_KEY` | `<secret>` | Coordinator (PFC calls) |
| `DATABASE_URL` | `<postgres connection>` | Cerebellum (legacy) |
| `MARKET` | `US` | Neural cortex |
| `TZ` | `Asia/Hong_Kong` | System timezone |
| `LOG_LEVEL` | `INFO` | All components |

**Critical fix (2026-04-11):** `AGENT_ID` was previously `dev_claude`, causing all `coordinator_state` updates to silently hit zero rows (the row is keyed on `big_bro`). Changed to `big_bro`.

---

## 8. Docker Configuration

### 8.1 Services

All services use `network_mode: host`, `restart: unless-stopped`, and JSON-file logging (10MB, 3 files).

| Service | Container Name | Healthcheck | Key Volumes |
|---|---|---|---|
| occipital | catalyst-occipital | SQLite SELECT 1 | `/var/lib/catalyst/db` |
| cerebellum | catalyst-cerebellum | SQLite SELECT 1 | `/var/lib/catalyst/db`, `/var/lib/catalyst/models:ro` |
| monitor | catalyst-monitor | SQLite SELECT 1 | `/var/lib/catalyst/db` |
| hippocampus | catalyst-hippocampus | SQLite SELECT 1 | `/var/lib/catalyst/db`, `/var/lib/catalyst/hippocampus` |
| neural | catalyst-neural | SQLite SELECT 1 | `/var/lib/catalyst/db`, `/var/lib/catalyst/models:ro` |

### 8.2 Common Commands

```bash
# Status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Restart all
cd /root/catalyst-agent && docker compose restart

# Restart single container
docker restart catalyst-neural

# View container logs
docker logs catalyst-cerebellum --tail 50
docker logs catalyst-neural --since 1h

# Rebuild after code change
cd /root/catalyst-agent && docker compose build && docker compose up -d
```

---

## 9. ONNX Model Deployment

Models are trained on the laptop (RTX 4050), exported as ONNX, and deployed to the droplet via SCP.

### 9.1 Deployment Path

```
Laptop (Swan View)
  └── SCP ──► /var/lib/catalyst/models/ on droplet
                ├── candle_model.onnx       (direction + confidence)
                ├── candle_model.onnx.data  (weights)
                ├── catalyst_net.onnx       (fused 5-horizon)
                └── catalyst_net.onnx.data  (weights)
```

### 9.2 Deploying a New Model

```bash
# From laptop:
scp candle_model.onnx candle_model.onnx.data root@<droplet-ip>:/var/lib/catalyst/models/

# On droplet — restart neural to load new model:
docker restart catalyst-neural

# Verify:
docker logs catalyst-neural --tail 20
```

The neural container loads ONNX models on startup. A restart is required after deploying new models.

---

## 10. Database Operations

### 10.1 Quick Inspection

```bash
# Coordinator state
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT cycle_count, current_layer, attention_mode, market_open, trading_enabled, daily_pnl, updated_at FROM coordinator_state;"

# PFC state
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT current_mode, resume_instructions, active_questions FROM pfc_state WHERE agent_id='big_bro';"

# Recent communication messages
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT source, target, msg_type, identifier, status, created_at FROM communication ORDER BY created_at DESC LIMIT 10;"

# Trade feedback (when trades start)
sqlite3 /var/lib/catalyst/db/agent.db \
  "SELECT symbol, side, return_pct, exit_type, exit_at FROM trade_feedback ORDER BY exit_at DESC LIMIT 10;"

# Learnings
sqlite3 /var/lib/catalyst/hippocampus/memory.db \
  "SELECT domain, title, confidence, validation_count, status FROM learnings ORDER BY confidence DESC;"

# Pattern confidence weights
sqlite3 /var/lib/catalyst/hippocampus/memory.db \
  "SELECT pattern_type, confidence, total_trades, wins, losses FROM pattern_confidence ORDER BY confidence DESC;"
```

### 10.2 Manual Backup

```bash
/root/catalyst-agent/scripts/backup-db.sh
```

### 10.3 Restore from Backup

```bash
# Stop coordinator first
pkill -f "coordinator.coordinator"

# Restore
cp /root/catalyst-agent/backups/agent_YYYYMMDD.db /var/lib/catalyst/db/agent.db
cp /root/catalyst-agent/backups/memory_YYYYMMDD.db /var/lib/catalyst/hippocampus/memory.db

# Restart
/root/catalyst-agent/scripts/run-coordinator.sh
```

---

## 11. Troubleshooting

### Container not starting

```bash
docker logs catalyst-<name> --tail 50
# Common: missing env var, model file not found, DB path wrong
```

### Coordinator not cycling

```bash
# Check process
ps aux | grep coordinator | grep -v grep

# Check cycle count is incrementing
watch -n 5 'sqlite3 /var/lib/catalyst/db/agent.db "SELECT cycle_count, current_layer, updated_at FROM coordinator_state;"'

# Check coordinator log
tail -50 /var/log/catalyst-agent/coordinator.log
```

### AGENT_ID mismatch (silent failure)

The coordinator updates `coordinator_state WHERE agent_id = <AGENT_ID>`. If the `.env` value doesn't match the row in the database, updates hit zero rows and state is silently discarded. Verify:

```bash
# .env value
grep AGENT_ID /root/catalyst-agent/.env

# Database row
sqlite3 /var/lib/catalyst/db/agent.db "SELECT agent_id FROM coordinator_state;"

# These MUST match
```

### Neural container crash-looping

Usually means ONNX models aren't at the mount path:

```bash
ls -la /var/lib/catalyst/models/
# Should contain: candle_model.onnx, candle_model.onnx.data, catalyst_net.onnx, catalyst_net.onnx.data
```

### Watchdog restarting things unexpectedly

Check the watchdog log for the pattern:

```bash
grep WARNING /var/log/catalyst-agent/watchdog.log | tail -20
```

To temporarily disable the watchdog (e.g., for maintenance):

```bash
crontab -e
# Comment out: */5 * * * * /root/catalyst-agent/scripts/watchdog.sh
```

---

## 12. Market Hours Reference

| Event | ET | HKT (droplet TZ) | Cron |
|---|---|---|---|
| Daily reset | 09:00 | 21:00 | `0 21 * * 1-5` |
| Market open | 09:30 | 21:30 | Coordinator Layer 3 |
| Market close | 16:00 | 04:00+1 | Coordinator Layer 3 |
| DB backup | 20:00 (prev day) | 08:00 | `0 8 * * 1-5` |

The coordinator uses the Alpaca clock API or `America/New_York` timezone calculation for market-hours logic. Cron jobs use HKT because the droplet's TZ is `Asia/Hong_Kong`.

---

## 13. Known Issues from Setup (2026-04-11)

These were resolved during the initial cron setup. Documented here to prevent recurrence.

| Issue | Severity | Resolution |
|---|---|---|
| All cron jobs pointed to `/root/catalyst-trading-system/` (old system) | Critical | New cron jobs created for `/root/catalyst-agent/` |
| `AGENT_ID=dev_claude` in `.env` but DB row keyed on `big_bro` | Critical | Changed `.env` to `AGENT_ID=big_bro` |
| ONNX models in source tree but not at Docker mount path | High | Copied to `/var/lib/catalyst/models/` |
| Old `consciousness-dashboard.service` still running | Low | Left running — not harmful |

---

## 14. Related Documents

| Document | Version | Type | Location |
|---|---|---|---|
| Catalyst AI Architecture | v2.4 | Architecture | `Documentation/Design/catalyst-ai-architecture-v2.4.md` |
| Catalyst US Configuration | v1.0 | Configuration | `Documentation/catalyst-us-configuration-v1.0.md` |
| Catalyst US Runtime (this doc) | v1.0 | Configuration | `Documentation/Configuration/catalyst-us-runtime-v1.0.md` |
| Catalyst Neural Architecture | v0.3 | Architecture | `Documentation/Design/catalyst-neural-architecture-v0.3.md` |
| Catalyst Strategy Roadmap | v1.0 | Strategy | `Documentation/Design/catalyst-strategy-roadmap.md` |
| Cron Setup Report | — | Report | `/root/catalyst-agent/CRON-SETUP-REPORT.md` (origin of this document) |

---

*"Whatever you do, work at it with all your heart, as working for the Lord."* — Colossians 3:23

*Catalyst US Runtime Configuration v1.0 — Craig + Claude — 2026-04-15*
