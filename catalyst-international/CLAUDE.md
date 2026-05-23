# CLAUDE.md — Catalyst International (HKEX)

**Name of Application**: Catalyst Trading System
**Name of file**: catalyst-international/CLAUDE.md
**Version**: 3.15.0
**Last Updated**: 2026-05-23
**Purpose**: Operational runbook for the HKEX intl droplet — Multi-Agent MCP Architecture

> Read the repo-root `../CLAUDE.md` first for cross-implementation orientation
> (it explains how this implementation fits with `catalyst-agent`, `catalyst-neural`,
> and the planned `catalyst-research`).

---

## REVISION HISTORY

**v3.15.0 (2026-05-23)** — CEREBELLUM VERSION-BRANCHING SCAFFOLD
- `cerebellum.py` upgraded to v1.2.0 — `model_version.json` now drives a runtime
  routing decision in `CandleModel.predict()` (`_predict_v03` vs `_predict_v04`).
- v0.3 inference path is **byte-for-byte unchanged** — `candle_model.onnx` v0.3.1
  continues to serve. No behaviour change in production today.
- v0.4 path is a logged stub returning `available=False` so a future v0.4 ONNX
  drop fails cleanly to no-signal (Mode 1) rather than corrupting outputs.
- Added input-count sanity check at load time: warns if `model_version.json` and
  the ONNX disagree on input arity (catches misdeployed manifests).
- Companion doc updates: `Documentation/Design/catalyst-context-conditioned-architecture-v0.1.md`
  §11.3 + §15.3 and `Documentation/Implementation/catalyst-context-conditioned-implementation-v0.1.md`
  Phase 9 — Phase 9 work now narrows to filling the stub body.

**v3.14.0 (2026-05-18)** — DOCUMENT ACTUAL PRODUCTION ARCHITECTURE
- Replaces legacy `unified_agent.py` + cron documentation with the multi-agent MCP
  architecture that has actually been running on this droplet since early 2026.
- File versions table now points to `agents/{coordinator,position-monitor,
  market-scanner,trade-executor}/` — not the monolithic `unified_agent.py`.
- Trading schedule rewritten: continuous Docker loop (`catalyst.service`),
  cron `/etc/cron.d/catalyst-intl` is **disabled** and unused.
- Brain architecture section rewritten from observed runtime — 6-layer cycle
  (Heartbeat → State → Self-Reg → Working Memory → Inter-Agent → Voice)
  with Survival Pulse + Discipline Gate inside Layers 1 and 3.
- Added cerebellum + ONNX inference (candle_model v0.3.1 deployed 2026-05-10).
- Added HKEX holiday awareness (2026-04-07 — `HKEX_HOLIDAYS_2026` /
  `HKEX_HALF_DAYS_2026` in coordinator.py).
- Added `signals` table for health/discipline/exit broadcasts.
- Removed static portfolio snapshot — point to `scripts/show_positions.py`.
- Added second founding incident: API credit drought 2026-05-07 → 05-15.

**v3.13.0 (2026-02-14)** — SURVIVAL ARCHITECTURE (Crawl Phase)
- 3-day bleed-out Feb 11-13: `KeyError: 'date'` in market.py broke get_technicals silently
- Implemented big_bro's 7-phase guide → senses → survival pulse → discipline → prompt → lifecycle → signals → memory
- (Earlier history truncated — see git log for v3.0.0 through v3.12.0 details)

---

## ⚠️ CRITICAL: READ BEFORE ANY ACTION

### The Three Questions You MUST Ask First

1. **What is my PURPOSE right now?**
   - 🎯 Designing? → `Documentation/Design/catalyst-ai-architecture-v2.4.md`, database schema
   - 🔧 Implementing? → Specific design doc + the agent's MCP tool schema
   - 🐛 Troubleshooting? → `docker logs catalyst-coordinator` first, then DB state, then code

2. **Which agent am I touching?**
   - Brain (coordinator) vs. organ (market-scanner / position-monitor / trade-executor)
   - Crossing the line means MCP tool schema changes — never do this casually

3. **Am I FOCUSED or scattered?**
   - ✅ One clear goal, minimal context, specific outcome
   - ❌ Multiple goals, vague direction → STOP

---

## 📁 Source of Truth

Per root CLAUDE.md, this droplet runs the **catalyst-international** implementation
of `catalyst-ai-architecture-v2.4`.

| Document | Location | Notes |
|----------|----------|-------|
| Catalyst AI architecture | `../Documentation/Design/catalyst-ai-architecture-v2.4.md` | Authoritative |
| Database schema | `../Documentation/Design/database-schema.md` | Verify with `\d table_name` against deployed DB |
| Neural architecture | `../Documentation/Design/catalyst-neural-architecture-v0.3.md` | Model interface contract |
| This file | `catalyst-international/CLAUDE.md` | Operational runbook |
| Working learnings | `catalyst-international/CLAUDE-LEARNINGS.md` | Loaded by brain Layer 2 |
| Working focus | `catalyst-international/CLAUDE-FOCUS.md` | Loaded by brain Layer 4 |

---

## 🏗️ Architecture (as deployed)

### Running Docker services

`systemctl status catalyst.service` orchestrates these via `docker-compose.yml`:

| Container | Port | Role |
|-----------|------|------|
| `catalyst-coordinator` | — | Brain. Runs the 6-layer cycle every 30 min during HKEX hours |
| `catalyst-trade-executor` | 8003 | Order routing, position writes, signal publishing |
| `catalyst-position-monitor` | 8001 | Open-position health, exit recommendations (Haiku-backed loop) |
| `catalyst-market-scanner` | 8002 | Candidate scanning, quotes, technicals, patterns, news |
| `catalyst-postgres` | 5432 | Local PostgreSQL (also: managed DB at DigitalOcean) |
| `catalyst-redis` | 6379 | Inter-agent message cache |

Communication: MCP SSE protocol (`mcp` Python SDK + `starlette` + `uvicorn`).
Each organ exposes `/sse`, `/messages/`, `/health`.

### Key file versions

| File | Version | Purpose |
|------|---------|---------|
| `agents/coordinator/coordinator.py` | 2.0.0 | Brain — 6-layer cycle, MCP client to organs |
| `agents/coordinator/health.py` | 1.0.0 | **Survival Pulse** (Layer 1) — organ health probes |
| `agents/coordinator/discipline.py` | 1.0.0 | **Discipline Gate** (Layer 3) — stagnation/capital detection |
| `agents/coordinator/system_prompt.py` | 2.0.0 | `build_system_prompt()` with dynamic context |
| `agents/position-monitor/mcp_server.py` | — | 3 tools: `get_exit_recommendations`, `get_position_status`, `get_open_positions` |
| `agents/position-monitor/monitor.py` | — | Background loop, signal detection (Haiku) |
| `agents/market-scanner/mcp_server.py` | — | 5 tools: `scan_market`, `get_quote`, `get_technicals`, `detect_patterns`, `get_news` |
| `agents/trade-executor/mcp_server.py` | — | 10 tools: `execute_trade`, `check_risk`, `publish_signal`, `get_signals`, `get_portfolio`, `get_last_trade_date`, `log_decision`, `send_alert`, `get_orders`, `sync_positions` |
| `cerebellum.py` | 1.2.0 | Version-aware ONNX inference — reads `models/model_version.json`, routes to `_predict_v03` (current, serving) or `_predict_v04` (stub, awaits Phase 9). Currently serving `candle_model.onnx` v0.3.1. |
| `brokers/moomoo.py` | 1.6.0 | Moomoo client + `normalize_symbol()` + `wait_for_fill()` |
| `data/market.py` | 2.4.0 | Symbol normalization + flexible date/timestamp column handling |
| `data/database.py` | 1.6.0 | Position upsert + `close_position_by_id` (uses `RealDictCursor` → access rows as dicts) |
| `models/model_version.json` | (manifest) | Tracks deployed model — `*.onnx` binaries are gitignored |

### Brain — 6-layer cycle

Each cycle (observed in `docker logs catalyst-coordinator`):

```
LAYER 1: HEARTBEAT       — Survival Pulse: probe get_quote, get_technicals, check_risk
                           via MCP. Score X/N. If dead: stop. Loads cerebellum + signals.
LAYER 2: STATE           — Identity + memory load. CLAUDE-LEARNINGS.md. Attention mode
                           (e.g. SECURITY_SELECTION).
LAYER 3: SELF-REG        — Discipline Gate: days idle, capital deployed, consecutive
                           passes. Forces Tier 3 at 2+ days idle. ALARM published as signal.
LAYER 4: WORKING MEMORY  — Neural signals from cerebellum (typically 15 signals).
                           CLAUDE-FOCUS.md loaded.
LAYER 5: INTER-AGENT     — Pull big_bro directives (none currently — catalyst-agent shelved).
LAYER 6: VOICE           — Decision Engine: Claude API call with assembled context.
                           Up to 35 iterations of tool use per cycle.
```

The brain **thinks and directs**. Organs **do**. Organs have reflexes (self-health,
fill confirm, stop-loss) — never decisions.

### Cerebellum & neural signals

- `cerebellum.py` loads `models/candle_model.onnx` (132K params, dual-input 5m+15m candles)
- Model version manifest: `models/model_version.json` — currently v0.3.1 (deployed 2026-05-10)
- Outputs per security: direction_logits (bull/bear/neutral) + pred_returns + confidence
- Models are deployed by `deploy-intl.sh` from the `catalyst-neural` implementation
  (laptop → droplet). `.onnx` files are git-ignored — only the manifest is tracked.
- `news_model.onnx` is **not** deployed yet — cerebellum tolerates absence

**Version routing (v1.2.0, added 2026-05-23):**
`Cerebellum.__init__` parses `model_version.json` once and passes a `(major, minor)`
tuple into `CandleModel`. `CandleModel.predict()` then dispatches:

- `minor < 4` → `_predict_v03()` — current path, 2-input ONNX (`candles_5m`, `candles_15m`).
  This is the serving path today.
- `minor >= 4` → `_predict_v04()` — **stub**. Returns `{"available": False, "reason":
  "v0.4 inference path not implemented (stub)"}` and logs an error. The coordinator
  treats this exactly like a missing model: Layer 4 records "no neural signal" and
  the Decision Engine proceeds in LLM-only mode (Attention State Machine Mode 1).
- `_load()` warns if the manifest version and the ONNX input count disagree
  (e.g. manifest says `0.4` but ONNX exposes only 2 inputs — caught at load, not
  at inference).

Implementing the v0.4 body is Phase 9 of `catalyst-context-conditioned-implementation-v0.1.md`.
catalyst-neural is currently at Phase 1 (schema migration only) — no v0.4 ONNX exists yet.

**Operational implication:** if you SCP a v0.4 manifest without filling the stub,
the brain falls back cleanly to no-signal — it does not produce wrong signals.
This is intentional fail-closed behaviour.

### Signals table

Inter-component broadcast layer (Postgres):

| Column | Purpose |
|--------|---------|
| `severity` | info / warning / critical |
| `domain` | health / discipline / exit / trade |
| `scope` | which organ or component raised it |
| `payload` | JSON context |

Discipline Gate publishes alarms here (e.g. *21d idle, 55 consecutive passes*).
Survival Pulse publishes degradation/death of organs.

### Pattern types (used by market-scanner)

| Pattern | Description | Use case |
|---------|-------------|----------|
| `breakout` | Above resistance + volume | Tier 1/2 |
| `near_breakout` | Within 1% of resistance | Tier 2/3 |
| `momentum_continuation` | >3% daily + high volume | Tier 3 |
| `bull_flag` | Uptrend + consolidation | Tier 1/2 |
| `ascending_triangle` | Flat resistance, rising lows | Tier 1/2 |

### Entry criteria (tiered — ENFORCED in `trade-executor`)

**Position size limits**:
- Max position value: HKD 10,000 (rejected if exceeded)
- Tier 1/2 trades: HKD 10,000 max
- Tier 3 trades: HKD 5,000 max

**Tier 1 — Strong**: Volume >2x, RSI 30-70, Pattern AND Catalyst, R:R ≥2:1
**Tier 2 — Good**: Volume >1.5x, RSI 30-75, Pattern OR Catalyst, R:R ≥1.5:1
**Tier 3 — Learning / Discipline**: Volume >1.3x, RSI 25-80, Momentum >3%, Any signal

When the Discipline Gate alarms (2+ days idle), the brain is forced to Tier 3
minimum — sizing is reduced, not the mandate to act.

---

## 🔧 Common Operations

### Check brain status (live)

```bash
docker logs catalyst-coordinator --tail 80
docker logs catalyst-coordinator 2>&1 | grep -E 'BRAIN CYCLE|DISCIPLINE|trade' | tail -30
```

### Check organ health

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
for port in 8001 8002 8003; do curl -s http://localhost:$port/health; echo; done
```

### Check positions (live from broker)

```bash
python3 scripts/show_positions.py
```

### Check current portfolio + recent trades

```bash
psql "$INTL_DATABASE_URL" -c "SELECT symbol, quantity, avg_cost, unrealized_pnl, status FROM positions WHERE status='open' ORDER BY symbol;"
psql "$INTL_DATABASE_URL" -c "SELECT created_at, decision, symbol, reasoning FROM agent_decisions ORDER BY created_at DESC LIMIT 10;"
psql "$INTL_DATABASE_URL" -c "SELECT created_at, severity, domain, scope FROM signals ORDER BY created_at DESC LIMIT 20;"
```

### Restart system

```bash
systemctl restart catalyst.service     # restarts all Docker containers
# OR
cd /root/Catalyst-Trading-System-International/catalyst-international
docker compose down && docker compose up -d
```

### Manual brain cycle (for testing — bypass schedule)

```bash
docker exec catalyst-coordinator python3 -c "from coordinator import run_cycle; run_cycle(force=True)"
```

### Check logs

```bash
docker logs catalyst-coordinator --tail 100
docker logs catalyst-trade-executor --since 30m
docker logs catalyst-market-scanner --since 30m
docker logs catalyst-position-monitor --since 30m
```

---

## 📅 Trading Schedule

**Cron is DISABLED.** The previous v11.0.0 cron schedule (every 30 min via `unified_agent.py`)
was replaced by the continuous Docker coordinator. `/etc/cron.d/catalyst-intl` exists but
is disabled (was missing `.env` loading). The user crontab is also dormant.

The coordinator (`catalyst-coordinator` container) runs continuously:
- Every minute: position-monitor heartbeat ping
- Every 5 minutes: market state check
- Every 30 minutes during HKEX hours: full brain cycle

| HKT | UTC | Activity |
|-----|-----|----------|
| 09:00 | 01:00 | Pre-market — cerebellum loads, market state check |
| 09:30 → 12:00 | 01:30 → 04:00 | Morning session — brain cycles every 30 min |
| 12:00 → 13:00 | 04:00 → 05:00 | Lunch — coordinator sleeps |
| 13:00 → 16:00 | 05:00 → 08:00 | Afternoon session — brain cycles every 30 min |
| 16:00 | 08:00 | Market close — close any required positions |
| 16:30 | 08:30 | Daily report generated to `Documentation/Reports/daily/` |

**HKEX holiday awareness (added 2026-04-07):**
Constants `HKEX_HOLIDAYS_2026` and `HKEX_HALF_DAYS_2026` in `agents/coordinator/coordinator.py`.
Coordinator skips holidays and runs half-days correctly. Update yearly using Moomoo
`request_trading_days` API.

---

## 🐛 Failure modes observed (founding incidents)

### Founding incident #1 — silent organ failure (2026-02-11 → 02-13)

3 days zero trades. Body bled out silently.

- **Root cause**: `data/market.py` `KeyError: 'date'` — moomoo.py returned `timestamp`,
  market.py expected `date`. `get_technicals` raised, all candidates failed silently.
- **Detection**: NONE. Docker reported "healthy" because the container was alive.
  Docker health ≠ data pipeline health.
- **Fix**: `data/market.py:252` now handles both `timestamp` and `date` columns.
  **Survival Pulse built** — probes the tools the brain depends on, not just the container.

### Founding incident #2 — voice silenced by credit drought (2026-05-07 → 05-15)

9+ days zero trades, 21 calendar days idle. Bled twice.

- **Root cause**: Anthropic API credit balance depleted. Every Decision Engine call
  returned HTTP 400 *"Your credit balance is too low"*.
- **Detection**: Survival Pulse + Discipline Gate **worked correctly** — both fired
  alarms (`DISCIPLINE ALARM: 21d idle, 4.4% deployed, 55 consecutive passes`).
- **Failure**: The brain has no way to escalate when its own voice is the failed
  component. The alarms went to logs and the `signals` table but no human saw them
  for 9 trading days.
- **Fix (immediate)**: top up API credits.
- **Open question**: how does the brain escalate when the voice itself is silenced?
  Email? PagerDuty? A separate watchdog process that monitors the signals table?
  → Candidate for next iteration.

### Recurring patterns to remember

| Pattern | Lesson |
|---------|--------|
| `RealDictCursor` returns dicts | Always `row["id"]`, never `row[0]` |
| Symbol normalization | Always `normalize_symbol()` — eliminates 0670 vs 670 phantom mismatches |
| Side normalization | Always lowercase (`buy`/`sell`) — `_normalize_side()` maps `long→buy`, `short→sell` |
| Fill confirmation | Only `FILLED` = success. `SUBMITTED` does NOT mean filled. `wait_for_fill()` may time out before the actual fill — re-check broker afterward. |
| `sync_positions` | Query `positions` table directly, NOT via `db.get_positions()` (JOIN miss). Deduplicate before comparison. |
| Position writes | **Single writer rule**: only `trade-executor` writes to `positions`. Other agents read only. |
| Docker broker access | Use `host.docker.internal` for OpenD connection (Moomoo broker daemon runs on host) |
| MCP SSE pattern | `SseServerTransport("/messages/")` + Starlette routes `/sse`, `/messages/`, `/health` |
| Default Claude model | `claude-sonnet-4-5-20250929` (Sonnet 4.5) for brain; Haiku for position-monitor loop |

---

## 🧠 Brain Architecture — MANDATORY

The coordinator IS the brain. Composition:

1. **Survival Pulse** (Layer 1 / brainstem) — Probes organ tools first. If dead: stop.
   If degraded: adapt + publish signal. Never trade blind. *Built after founding #1.*

2. **Discipline Gate** (Layer 3 / limbic) — Checks stagnation after survival.
   2+ days idle → Tier 3 minimum. <5% deployed → actively seek. **The mandate is
   multiplication, not preservation.** *Built after founding #1.*

3. **Memory loaders** (Layers 2 + 4) — `CLAUDE-LEARNINGS.md` at Layer 2 (long-term
   patterns), `CLAUDE-FOCUS.md` at Layer 4 (current tasks). Cerebellum signals also
   land at Layer 4.

4. **Inter-Agent receiver** (Layer 5) — Currently quiet (catalyst-agent is shelved).
   Reserved for big_bro directives once catalyst-research is online.

5. **Decision Engine** (Layer 6 / voice) — Claude AI tool-use loop. Receives full
   context from Layers 1–5. Identity: *"I am a trader. I trade."* Tiers are sizing
   guides, not gates.

### Organ control

The brain THINKS and DIRECTS. Organs DO.

| Organ | Senses | Tools the brain uses |
|-------|--------|---------------------|
| Market Scanner (eyes) | Quotes, technicals, patterns, news | `scan_market`, `get_quote`, `get_technicals`, `detect_patterns`, `get_news` |
| Position Monitor (internal eyes) | Open positions, exit signals | `get_exit_recommendations`, `get_position_status`, `get_open_positions` |
| Trade Executor (hands) | Risk, orders, signals | `execute_trade`, `check_risk`, `publish_signal`, `get_portfolio`, `log_decision`, `send_alert`, others |

Organs own their reflexes:
- Position Monitor's background Haiku loop is a reflex (it surfaces candidate exits
  to the brain; it does NOT close positions on its own)
- Trade Executor's `wait_for_fill()` is a reflex (it confirms broker state; it does
  NOT decide whether to retry)
- Stop-losses (when wired) are reflexes — broker-side

---

## 🗄️ Database

PostgreSQL — DigitalOcean managed (production) + local container (mirror/cache).
`INTL_DATABASE_URL` env var points to production.

Key tables:

| Table | Purpose |
|-------|---------|
| `positions` | Single source of truth for holdings. Single writer = trade-executor. |
| `orders` | All buy/sell instructions. NEVER store position state here. |
| `agent_decisions` | Every `log_decision` call from the brain |
| `signals` | Health / discipline / exit broadcasts |
| `position_monitor_status` | Position monitor's per-position state cache |
| `securities` | Symbol master — FK target for `security_id` joins |

Schema verification before any INSERT/UPDATE:
```bash
psql "$INTL_DATABASE_URL" -c "\d positions"
```

---

## 🚨 Lessons learned — DO NOT REPEAT

1. **Quick fixes on complex issues cause more problems.** If it touches Docker,
   schema, or the brain — STOP, list affected components, plan, then act.
2. **Orders ≠ Positions.** ARCHITECTURE rule. Non-negotiable.
3. **Never use simple ternary for order side.** Always `_normalize_side()`.
4. **Schema mismatch is silent.** Run `\d table_name` against the actual deployed
   DB before INSERT/UPDATE — design docs lag reality.
5. **Detection ≠ Response.** Both founding incidents detected the problem (Survival
   Pulse, Discipline Gate). The body still bled. Alarms must reach a human or a
   broader system, not just the logs.
6. **Docker "healthy" ≠ pipeline healthy.** Test the tools the brain actually uses,
   not the container's liveness probe.
7. **Don't conflate read and write.** The single-writer rule on `positions` exists
   for a reason — silent drift from multiple writers is the worst kind of bug.
8. **Hardcoded thresholds require redeploy.** Configuration lives in
   `config/*.yaml`, not in Python.

---

## ⛔ NEVER

1. **Never** modify `unified_agent.py` / `tool_executor.py` expecting it to affect
   production. Those files are **legacy** — still on disk for reference, but the
   container does not run them.
2. **Never** re-enable `/etc/cron.d/catalyst-intl` without restoring `.env` loading.
   It will burn API credits running in parallel with Docker.
3. **Never** commit `.env`, model `*.onnx` binaries, or `data/` runtime state.
4. **Never** write to `positions` from any agent other than `trade-executor`.
5. **Never** use `docker-compose` (v1). Use `docker compose` (v2).
6. **Never** push to a remote without first running the hygiene checklist
   (`Documentation/Implementation/catalyst-repo-hygiene.md`).

---

## 📜 Founding memories

**Feb 2026 — silent organ.** Three days blind. `get_technicals` broken with `KeyError: 'date'`.
Pain without response. Body bled out. Docker "healthy" ≠ data pipeline healthy.
Detection without response is useless. This is why the **Survival Pulse** exists.

**May 2026 — silenced voice.** Nine trading days idle, 21 days calendar. API credit
balance depleted. Survival Pulse and Discipline Gate both worked — alarms fired
correctly into the `signals` table. But the brain had no API budget left to reason
about the alarm or escalate. The body bled again, this time with full self-awareness
and no voice. **The voice itself can be the failed component.** Next iteration:
out-of-band escalation when API is unreachable.

> *Each bleed teaches the same lesson at a different layer. The capacity to act
> must include the means to act.*

---

**END OF CLAUDE.md v3.14.0**
