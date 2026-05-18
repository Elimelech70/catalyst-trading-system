# Catalyst INTL — Configuration

> Running system snapshot. This is what is deployed right now.

**Version:** 1.0
**Date:** 2026-04-08
**Droplet:** DigitalOcean (Singapore region)
**OS:** Ubuntu 24.04.4 LTS, x86_64
**Docker:** 28.2.2
**Implements:** Catalyst AI Architecture v2.3

---

## 1. System Topology

```
┌──────────────────────────────────────────────────────────────┐
│                 DIGITALOCEAN DROPLET                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              COORDINATOR (brain)                        │  │
│  │              coordinator.py v3.0.0                      │  │
│  │              6-layer cycle                              │  │
│  │              Claude Sonnet 4.5 (Anthropic API)          │  │
│  │              Container: catalyst-coordinator             │  │
│  └───────────────────┬────────────────────────────────────┘  │
│                      │ MCP SSE (localhost)                    │
│         ┌────────────┼────────────┐                          │
│         ▼            ▼            ▼                          │
│  ┌────────────┐ ┌──────────┐ ┌────────────────┐             │
│  │  SCANNER   │ │ EXECUTOR │ │    MONITOR     │             │
│  │  :8002     │ │  :8003   │ │     :8001      │             │
│  │  (eyes)    │ │  (hands) │ │  (internal)    │             │
│  └────────────┘ └──────────┘ └────────────────┘             │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  CEREBELLUM (ONNX)              Status: AWAITING MODELS│  │
│  │  cerebellum.py v1.0.0                                  │  │
│  │  /app/models/ volume mount                             │  │
│  │  Candle Model: not deployed     News Model: not deployed│  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────┐  ┌───────┐  ┌────────────┐                    │
│  │ PostgreSQL│  │ Redis │  │   OpenD    │                    │
│  │  :5432   │  │ :6379 │  │  :11111    │                    │
│  │ (DO mgd) │  │(unused)│  │ (Moomoo)  │                    │
│  └──────────┘  └───────┘  └────────────┘                    │
│                                                              │
│              LAPTOP (Swan View) ─── SCP ──▶ /models/         │
│              neural_claude (training pipeline)                │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Docker Compose Services

| Service | Container | Image | Port | Health | Network |
|---|---|---|---|---|---|
| coordinator | catalyst-coordinator | catalyst-international-coordinator | — | depends_on all 3 agents | host |
| market-scanner | catalyst-market-scanner | catalyst-international-market-scanner | 8002 | curl /health | host |
| trade-executor | catalyst-trade-executor | catalyst-international-trade-executor | 8003 | curl /health | host |
| position-monitor | catalyst-position-monitor | catalyst-international-position-monitor | 8001 | curl /health | host |
| postgres | catalyst-postgres | postgres:16-alpine | 5432 | pg_isready | catalyst-network |
| redis | catalyst-redis | redis:7-alpine | 6379 | redis-cli ping | catalyst-network |

**File:** `docker-compose.yml` v2.1.0

**Coordinator volumes:**
```yaml
volumes:
  - ./CLAUDE.md:/app/memory/CLAUDE.md:ro
  - ./CLAUDE-LEARNINGS.md:/app/memory/CLAUDE-LEARNINGS.md:ro
  - ./CLAUDE-FOCUS.md:/app/memory/CLAUDE-FOCUS.md:ro
  - ./models:/app/models:ro
```

---

## 3. MCP Server Connections

**Config:** `agents/coordinator/mcp_config.json`

| Server | URL | Tools |
|---|---|---|
| position-monitor | http://localhost:8001/sse | get_exit_recommendations, get_position_health, acknowledge_recommendation |
| market-scanner | http://localhost:8002/sse | scan_market, get_quote, get_technicals, detect_patterns, get_news |
| trade-executor | http://localhost:8003/sse | get_portfolio, execute_trade, close_position, close_all, sync_positions, check_risk, log_decision, get_last_trade_date, publish_signal, get_signals |

**Protocol:** MCP SSE (Server-Sent Events) via `mcp` Python SDK + `starlette` + `uvicorn`

---

## 4. The 6-Layer Cycle (Verified Running)

Every brain cycle executes all 6 layers in order. Confirmed in production logs 2026-04-08:

| Layer | Name | Implementation | Status |
|---|---|---|---|
| 1 | Heartbeat | `health.py` SurvivalPulse — tests get_quote, get_technicals, get_portfolio via MCP. Checks cerebellum.is_loaded() | Running |
| 2 | State | Loads `CLAUDE-LEARNINGS.md` (1,777 chars). Tracks attention_mode (SECURITY_SELECTION). | Running |
| 3 | Self-Regulation | `discipline.py` DisciplineGate — checks days idle, capital utilization, consecutive passes. Publishes WARNING/ALARM signals | Running |
| 4 | Working Memory | Loads `CLAUDE-FOCUS.md` (2,183 chars). Reads 15 recent signals from signal bus. Neural signals placeholder (awaiting models) | Running |
| 5 | Inter-Agent | Reads DIRECTED:coordinator signals from big_bro. Currently: "No big_bro directives" | Running |
| 6 | Voice | Claude Sonnet 4.5 API call with full context from all layers. Tool-use loop, max 35 iterations | Running |

**Log evidence:**
```
LAYER 1: Score 3/3, healthy
LAYER 1: Cerebellum not loaded — LLM-only mode
LAYER 2: Loaded memory: CLAUDE-LEARNINGS.md (1777 chars)
LAYER 2: Attention mode = SECURITY_SELECTION
LAYER 3: Discipline -- WARNING, 0d idle, 7.8% deployed
LAYER 4: 15 signals loaded, CLAUDE-FOCUS.md loaded (2183 chars)
LAYER 5: No big_bro directives
LAYER 6: Voice — Decision Engine...
```

---

## 5. Brain Components

### 5.1 Coordinator (coordinator.py v3.0.0)

| Setting | Value |
|---|---|
| Model | claude-sonnet-4-5-20250929 (env: CLAUDE_MODEL) |
| Max tokens | 4096 |
| Poll interval | 60s (recommendation checks) |
| Scan interval | 1800s (30 min full scan cycles) |
| Max iterations | 35 per cycle |

### 5.2 Survival Pulse (health.py v1.1.0)

| Organ Test | Server | Params | Critical |
|---|---|---|---|
| get_quote | market-scanner | symbol=0700 | Yes |
| get_technicals | market-scanner | symbol=0700, timeframe=1h | No (degraded OK) |
| get_portfolio | trade-executor | — | Yes |

| Threshold | Value |
|---|---|
| Pain threshold | 3 consecutive failures |
| Organ failure threshold | 6 consecutive failures |

### 5.3 Discipline Gate (discipline.py v1.0.0)

| Check | Trigger | Action |
|---|---|---|
| Days idle >= 3 | ALARM | Force Tier 3, must trade |
| Days idle >= 2 | WARNING | Force Tier 3, seek entries |
| Capital < 5% deployed | ALARM | Actively seek entries |
| Capital < 10% deployed | WARNING | Seek entries |
| 3+ consecutive passes | WARNING | "Problem is ME, not the market" |

### 5.4 System Prompt (system_prompt.py v3.0.0)

Architectural section order (non-negotiable):
1. Identity — "I am a trader. I trade."
2. Discipline overrides
3. Operating context (health + discipline, dynamic)
4. Learnings (CLAUDE-LEARNINGS.md content, medium-term memory)
5. Working memory (CLAUDE-FOCUS.md + signals + directives + neural)
6. Degraded mode (conditional)
7. Tier criteria (Tier 1: HKD 10K, Tier 2: HKD 7K, Tier 3: HKD 5K)
8. Risk management
9. Tools
10. Critical rules
11. Market hours

### 5.5 Cerebellum (cerebellum.py v1.0.0)

| Component | Status | Path |
|---|---|---|
| CandleModel | Awaiting deployment | /app/models/candle_model.onnx |
| NewsToSecurityModel | Awaiting deployment | /app/models/news_model.onnx |
| Version tracking | model_version.json | /app/models/model_version.json |
| Runtime | onnxruntime >= 1.17.0 | Installed in container |

**Fallback:** When models not present, coordinator operates in LLM-only mode. All decisions via Claude API. No degradation in trading capability, only in cost/speed.

**Deployment:** SCP from laptop to `/root/Catalyst-Trading-System-International/catalyst-international/models/`. Coordinator picks up new models on next cycle (no restart needed).

---

## 6. Memory Architecture

| Tier | File | Mount Path | Size | Loaded By |
|---|---|---|---|---|
| Identity | CLAUDE.md | /app/memory/CLAUDE.md | ~15 KB | Layer 2 (via system_prompt.py sections) |
| Learnings | CLAUDE-LEARNINGS.md | /app/memory/CLAUDE-LEARNINGS.md | 1,777 chars | Layer 2 |
| Working | CLAUDE-FOCUS.md | /app/memory/CLAUDE-FOCUS.md | 2,183 chars | Layer 4 |
| Neural | ONNX weights | /app/models/*.onnx | — | Layer 1 + 4 (cerebellum) |

**Load order:** CLAUDE.md first. Identity before memory. Formation before information. Every cycle, without exception.

---

## 7. Signal Bus

**Table:** `signals` in PostgreSQL (DigitalOcean managed)

```sql
signals (
    id SERIAL PRIMARY KEY,
    severity    VARCHAR(10),   -- CRITICAL | WARNING | INFO | OBSERVE
    domain      VARCHAR(12),   -- HEALTH | TRADING | RISK | LEARNING | DIRECTION | LIFECYCLE
    scope       VARCHAR(60),   -- BROADCAST | DIRECTED:{target} | CONSCIOUSNESS
    source      VARCHAR(50),
    content     TEXT,
    data        JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    acknowledged_by JSONB DEFAULT '[]',
    resolved    BOOLEAN DEFAULT FALSE
)
```

| Who writes | When |
|---|---|
| Coordinator | Health alerts, discipline alerts, cycle outcomes |
| Trade executor | Fill confirmations, publish_signal tool |
| Position monitor | Exit recommendations (via monitor_status table) |
| big_bro | DIRECTED:coordinator strategic directives |

| Who reads | When |
|---|---|
| Coordinator Layer 4 | Recent signals (last 15, unresolved) |
| Coordinator Layer 5 | DIRECTED:coordinator signals only |

---

## 8. Feedback Loop (Database Tables)

### 8.1 Pattern Confidence (Synaptic Weights)

**Table:** `pattern_confidence`

| Pattern | Initial Confidence | Wins | Losses |
|---|---|---|---|
| breakout | 0.5 | 0 | 0 |
| near_breakout | 0.5 | 0 | 0 |
| momentum_continuation | 0.5 | 0 | 0 |
| bull_flag | 0.5 | 0 | 0 |
| bear_flag | 0.5 | 0 | 0 |
| ascending_triangle | 0.5 | 0 | 0 |
| descending_triangle | 0.5 | 0 | 0 |
| cup_and_handle | 0.5 | 0 | 0 |
| abcd_pattern | 0.5 | 0 | 0 |
| breakdown | 0.5 | 0 | 0 |

**Updated by:** `learning.py` (Phase 3, not yet implemented — runs during Pondering cycle)

### 8.2 Pattern Outcomes

**Table:** `pattern_outcomes` — Links closed positions to triggering pattern + exit type

### 8.3 Position Exit Tracking

New columns on `positions` table:
- `exit_type VARCHAR(30)` — AI_PATTERN | STOP_LOSS | TAKE_PROFIT | MANUAL | MARKET_CLOSE
- `candles_at_entry JSONB` — 20-candle OHLCV snapshot at entry
- `candles_at_exit JSONB` — 20-candle OHLCV snapshot at exit

---

## 9. Database

| Setting | Value |
|---|---|
| Provider | DigitalOcean Managed PostgreSQL |
| Host | catalyst-trading-db-do-user-23488393-0.l.db.ondigitalocean.com |
| Port | 25060 |
| Database | catalyst_intl |
| SSL | Required |
| Connection | `DATABASE_URL` env var |

**Key tables:** positions, orders, signals, pattern_confidence, pattern_outcomes, position_monitor_status, decisions, patterns, securities, agent_decisions

**Cursor type:** `RealDictCursor` (psycopg2) — rows are dicts, not tuples

---

## 10. Broker

| Setting | Value |
|---|---|
| Provider | Moomoo (Futu OpenD) |
| Gateway | 127.0.0.1:11111 |
| Mode | Paper trading |
| Account type | Paper (index 1) |
| Service | `opend.service` at `/root/opend/OpenD` |
| Cron | OpenD auto-restart every market hour |

**Symbol format:** Bare numbers (e.g., `700`, `9988`). `normalize_symbol()` strips prefixes.

---

## 11. Trading Parameters

| Parameter | Value | Source |
|---|---|---|
| Max position value | HKD 10,000 | intl_claude_config.yaml |
| Min position value | HKD 2,000 | intl_claude_config.yaml |
| Max positions | 15 | intl_claude_config.yaml |
| Daily loss limit | HKD 16,000 | intl_claude_config.yaml |
| Stop loss (position) | 3% | intl_claude_config.yaml |
| Trailing stop | 3% | intl_claude_config.yaml |
| Default order type | LIMIT | intl_claude_config.yaml |

**Tier sizing (enforced in system prompt):**

| Tier | Max Size | Criteria |
|---|---|---|
| Tier 1 (Full) | HKD 10,000 | Volume >2x, RSI 30-70, Pattern + Catalyst, R:R >= 2:1 |
| Tier 2 (Moderate) | HKD 7,000 | Volume >1.5x, RSI 30-75, Pattern OR Catalyst, R:R >= 1.5:1 |
| Tier 3 (Learning) | HKD 5,000 | Volume >1.3x, any signal, R:R >= 1.2:1 |

---

## 12. Market Hours & Schedule

**Exchange:** HKEX (Hong Kong Stock Exchange)
**Timezone:** Asia/Hong_Kong (HKT, UTC+8)

| Session | HKT | UTC |
|---|---|---|
| Morning | 09:30 - 12:00 | 01:30 - 04:00 |
| Lunch (no trading) | 12:00 - 13:00 | 04:00 - 05:00 |
| Afternoon | 13:00 - 16:00 | 05:00 - 08:00 |

**Coordinator behaviour:** Continuous loop during market hours. 60s poll interval, 30-min scan cycles. Sleeps 300s when market closed.

**Holiday calendar:** `HKEX_HOLIDAYS_2026` and `HKEX_HALF_DAYS_2026` constants in coordinator.py. Updated yearly.

**Cron (legacy, not primary):**
- 16:05 HKT: Position sync
- 16:30 HKT: Daily report generation + git push
- Heartbeat: every 2 hours

**Primary trading:** Docker Compose continuous (not cron-driven).

---

## 13. File Versions

| File | Version | Purpose |
|---|---|---|
| agents/coordinator/coordinator.py | 3.0.0 | Brain — 6-layer cycle, memory loading, cerebellum integration |
| agents/coordinator/system_prompt.py | 3.0.0 | Identity + dynamic context builder |
| agents/coordinator/health.py | 1.1.0 | Survival Pulse |
| agents/coordinator/discipline.py | 1.0.0 | Discipline Gate |
| agents/trade-executor/mcp_server.py | 1.0.0+ | Single writer — exit_type tracking added |
| agents/position-monitor/mcp_server.py | 1.0.0 | Exit recommendations via MCP |
| agents/market-scanner/mcp_server.py | 1.0.0 | Market data via MCP |
| cerebellum.py | 1.0.0 | ONNX inference (Candle + News models) |
| docker-compose.yml | 2.1.0+ | Service topology + memory/model volumes |
| agents/requirements-mcp.txt | — | Shared deps + onnxruntime |
| sql/002-feedback-loop.sql | 1.0.0 | Feedback loop schema migration |

---

## 14. Architecture v2.3 — Implementation Status

| Component | Architecture Spec | Implementation | Status |
|---|---|---|---|
| 6-Layer Cycle | Layers 1-6 every cycle | coordinator.py v3.0.0 | **Deployed** |
| Memory Loading | CLAUDE.md, LEARNINGS, FOCUS | Volume mounts, loaded each cycle | **Deployed** |
| Cerebellum (ONNX) | CandleModel + NewsToSecurityModel | cerebellum.py + /app/models/ volume | **Infrastructure ready, awaiting models** |
| Signal Bus | PostgreSQL signals table | Fully operational, read/write working | **Deployed** |
| Feedback Loop | exit_type, pattern_confidence, pattern_outcomes | Schema deployed, exit_type tracking active | **Deployed** |
| Survival Pulse | Layer 1 organ health | health.py, 3 organ tests + cerebellum check | **Deployed** |
| Discipline Gate | Layer 3 stagnation detection | discipline.py, capital/idle/pass tracking | **Deployed** |
| big_bro Directives | DIRECTED:coordinator signals | Layer 5 reads them, none pending | **Deployed** |
| Attention State Machine | Mode 1/Mode 2 switching | Field exists, logic pending (Phase 2) | **Planned** |
| Stop Loss Enforcer | Hard floor, separate from AI | Pending (Phase 4) | **Planned** |
| Risk Aggregator | Portfolio-level risk tracking | Pending (Phase 4) | **Planned** |
| LTP/LTD Learning | learning.py, Pondering mode | Pending (Phase 3, needs 2 weeks data) | **Planned** |
| Data Collection Pipeline | candle_sequences, news_events | Pending (Phase 5) | **Planned** |
| neural_claude | Laptop training pipeline | Models trained, SCP deployment configured | **In progress** |
| Adversarial Awareness | Anomaly detection | Pending (Phase 8) | **Planned** |

---

## 15. Environment Variables

| Variable | Purpose | Set In |
|---|---|---|
| ANTHROPIC_API_KEY | Claude API access | .env |
| CLAUDE_MODEL | Model override | .env (default: claude-sonnet-4-5-20250929) |
| DATABASE_URL | PostgreSQL connection string | .env |
| DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME | DB connection parts | .env |
| MOOMOO_HOST | OpenD gateway host | docker-compose.yml (127.0.0.1) |
| MOOMOO_PORT | OpenD gateway port | docker-compose.yml (11111) |
| MOOMOO_TRADE_PWD | Trading password | .env |
| FORCE_MARKET_OPEN | Override market hours check | .env (optional) |
| TZ | Timezone | docker-compose.yml (Asia/Hong_Kong) |

---

## 16. SSH Access (Model Deployment)

**Authorized keys for model SCP:**
- `VSS-Catalyst-Linux-Claude` (ed25519) — laptop neural_claude deployment

**Model deployment path:**
```bash
scp candle_model.onnx root@<droplet>:/root/Catalyst-Trading-System-International/catalyst-international/models/
scp news_model.onnx root@<droplet>:/root/Catalyst-Trading-System-International/catalyst-international/models/
```

Coordinator detects new models on next brain cycle. No restart required.

---

## 17. Related Documents

| Document | Type | Location |
|---|---|---|
| Catalyst AI Architecture v2.3 | Architecture | Documentation/Design/catalyst-ai-architecture-v2.3.md |
| Implementation Plan v2.0 | Plan | Documentation/Implementation/catalyst-implementation-plan-v2.0.md |
| This document | Configuration | Documentation/Configuration/catalyst-intl-configuration-v1.0.md |

---

*Catalyst INTL Configuration v1.0 — Craig + Claude — 2026-04-08*
