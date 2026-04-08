# Catalyst US Configuration

> *"Unless the LORD builds the house, the builders labour in vain."* — Psalm 127:1

**Version:** 1.0.0
**Date:** 2026-04-08
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
| **Configuration** | Realised state — how the architecture runs on a specific droplet with a specific broker. | ✅ This is the US Configuration document |

This document describes exactly how the v2.4 architecture is implemented in the catalyst-agent codebase for the US deployment (Alpaca broker, NYSE/NASDAQ equities, USD).

---

## REVISION HISTORY

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-04-08 | Initial configuration — v2.4 architecture implementation. Coordinator, 6-layer cycle, Attention State Machine, broker abstraction, tool agents, feedback loop, three learning paths |

---

## 1. Deployment Overview

```
Catalyst AI Architecture v2.4 (the pattern)
        │
        ├── ✅ Catalyst US Configuration v1.0 (THIS DOCUMENT)
        │   Droplet:  DigitalOcean US region
        │   Broker:   Alpaca (NYSE, NASDAQ)
        │   Market:   US equities, USD
        │   Currency: USD
        │   Hours:    09:30–16:00 ET (Mon–Fri)
        │
        └── Catalyst Intl Configuration (pending)
            Droplet:  Intl region
            Broker:   Moomoo (HKEX)
            Market:   HK equities, HKD
```

---

## 2. Codebase Structure

```
/root/catalyst-agent/
│
├── coordinator/
│   ├── __init__.py
│   └── coordinator.py          ← THE BRAIN — 6-layer cycle + Attention State Machine
│
├── cerebellum/
│   ├── broker_base.py          ← StandardBroker ABC + normalisation layer
│   ├── broker.py               ← AlpacaBroker (extends StandardBroker)
│   ├── executor.py             ← Procedure execution
│   └── procedures/
│       └── find_securities.json
│
├── tools/
│   ├── __init__.py
│   ├── position_monitor.py     ← Tool agent — ONNX inference, AI pattern exits
│   ├── stop_loss_enforcer.py   ← Tool agent — hard floor, STOP_LOSS recording
│   └── risk_aggregator.py      ← Tool agent — portfolio heat, exposure limits
│
├── neural/
│   ├── cortex.py               ← ONNX model inference service
│   └── model/
│       ├── candle_model.onnx   ← (deployed from laptop)
│       └── catalyst_net.onnx   ← (deployed from laptop)
│
├── occipital/
│   ├── scanner.py              ← Rule-based pattern matching
│   └── shapes/
│       ├── candlestick_patterns.json
│       └── volume_patterns.json
│
├── hippocampus/
│   └── hippocampus.py          ← Memory binding engine
│
├── monitor/
│   └── monitor.py              ← Reflexive position monitor (Docker)
│
├── learning/
│   └── learning.py             ← LTP/LTD + feedback processing + training export
│
├── shared/
│   ├── __init__.py
│   ├── config.py               ← AgentConfig with all env vars
│   ├── db.py                   ← AgentDB — communication, signals, coordinator state, feedback
│   └── models.py               ← Enums + dataclasses (v2.4 aligned)
│
├── schema/
│   ├── local-schema.sql        ← agent.db schema (6 tables)
│   ├── hippocampus-schema.sql  ← memory.db schema (5 tables)
│   └── init-db.sh
│
├── pfc/
│   └── agent.py                ← PFC agent (legacy — coordinator replaces as brain)
│
├── docker-compose.yml          ← 5 Docker services (body components)
├── CLAUDE.md                   ← Identity document (permanent)
├── CLAUDE-LEARNINGS.md         ← Validated learnings (weeks/months)
└── CLAUDE-FOCUS.md             ← Working memory (hours/days)
```

---

## 3. The Coordinator — How the Brain Runs

**File:** `coordinator/coordinator.py`
**Class:** `Coordinator`
**Runs on:** HOST (not in Docker) — alongside Claude Code

The coordinator is the brain. It runs the 6-layer cycle, manages the Attention State Machine, and directs tool agents. Claude AI (Anthropic API) is called only when genuine reasoning is needed — the 6% principle.

### 3.1 The 6-Layer Cycle

No layer is skipped. The output of each layer feeds the next. Nothing runs if survival (Layer 1) fails.

| Layer | Method | What It Does |
|---|---|---|
| **1. HEARTBEAT** | `_layer_heartbeat()` | Component liveness check. Reads status signals from all organs. Checks neural model availability. If critical failure → abort cycle. |
| **2. STATE** | `_layer_state()` | Loads identity (principles from agent.db). Reads PFC state (resume instructions, mode). Loads current attention mode and watch list. Formation before information. |
| **3. SELF-REGULATION** | `_layer_self_regulation()` | Market hours check (09:30–16:00 ET via Alpaca clock API or timezone calc). Daily loss limit check (default: -3%). If market closed or limit hit → exit cleanly. |
| **4. WORKING MEMORY** | `_layer_working_memory()` | Reads signal bus (last 10 min, CRITICAL first). Loads broker positions. Loads NEURAL predictions from communication table. Loads feedback stats (7-day rolling). Assembles the live picture. |
| **5. INTER-AGENT** | `_layer_inter_agent()` | Reads big_bro DIRECTION signals (stop_trading, resume_trading, emergency). Checks tool agent status. Summarises body health. |
| **6. VOICE** | `_layer_voice()` | Dispatches to Attention State Machine: Mode 1 or Mode 2 based on current `attention_mode`. |

**Cycle interval:** `COORDINATOR_CYCLE_INTERVAL` env var (default: 30 seconds)

### 3.2 The Attention State Machine

**File:** `coordinator/coordinator.py` — methods `_mode_security_selection()` and `_mode_candle_execution()`

```
┌──────────────────────────────────────────────────────────┐
│                   COORDINATOR BRAIN                       │
│                                                           │
│   ┌──────────────────┐         ┌────────────────────────┐│
│   │  MODE 1           │         │  MODE 2                ││
│   │  SECURITY          │──────▶  │  CANDLE                ││
│   │  SELECTION         │         │  EXECUTION             ││
│   │                    │         │                        ││
│   │  Scans neural      │         │  Reads candle model    ││
│   │  predictions for   │         │  for active securities ││
│   │  high-confidence   │         │  Entry: conf ≥ 0.3 +   ││
│   │  securities        │         │  matching direction    ││
│   │  Threshold: ≥ 0.4  │         │                        ││
│   └──────────────────┘         └────────────────────────┘│
│           ▲                              │                │
│           │                              │                │
│           └──── all positions closed ────┘                │
│                                                           │
│   Switch to Mode 2: security found with confidence ≥ 0.4 │
│   Return to Mode 1: all watched positions closed/stale   │
└──────────────────────────────────────────────────────────┘
```

**Mode 1 — Security Selection** (`_mode_security_selection()`):
- Reads neural predictions from working memory
- High-confidence threshold: `confidence ≥ 0.4` AND direction is bullish/bearish
- Matched securities added to `watch_list` and `active_securities`
- Publishes `ATTENTION` signal on mode switch
- Transitions to Mode 2

**Mode 2 — Candle Execution** (`_mode_candle_execution()`):
- Reads candle model predictions for watched securities
- Entry threshold: `confidence ≥ 0.3` AND direction matches expected
- Sends `execute_trade` task to cerebellum via communication table
- Publishes `EXECUTION` signal on trade submission
- Returns to Mode 1 when all watch list entries are stale (no positions)

---

## 4. Broker Abstraction Layer

### 4.1 Standard Interface

**File:** `cerebellum/broker_base.py`
**Class:** `StandardBroker` (ABC)

All broker implementations extend `StandardBroker`. The coordinator and cerebellum interact only with this interface.

| Method | Returns | Purpose |
|---|---|---|
| `connect()` | `bool` | Initialise broker connection |
| `disconnect()` | `None` | Clean up |
| `get_account()` | `Dict` | `{buying_power, cash, equity, portfolio_value, status, currency, market}` |
| `get_positions()` | `List[Dict]` | `[{symbol, qty, side, avg_entry_price, current_price, unrealized_pl, unrealized_plpc, market_value, market}]` |
| `get_bars()` | `List[StandardOHLCV]` | Historical candles in standard format |
| `submit_order()` | `Dict` | `{order_id, symbol, qty, side, type, status, submitted_at}` |
| `close_position()` | `Dict` | Close single position |
| `close_all_positions()` | `Dict` | Emergency close all |
| `is_market_open()` | `bool` | Market state |

### 4.2 Standard OHLCV Format

**Dataclass:** `shared/models.py` → `StandardOHLCV`

```python
@dataclass
class StandardOHLCV:
    timestamp: datetime
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float
    timeframe: str    # '1m' | '5m' | '15m' | '1h' | '1d'
```

All broker data is normalised to this format before reaching ONNX models. One training run on the laptop produces models that work on both US and Intl deployments.

### 4.3 Data Normalisation

**File:** `cerebellum/broker_base.py`

```
Alpaca bar  ──► alpaca_to_standard() ──►┐
                                         ├──► StandardOHLCV ──► ONNX Model
Moomoo bar  ──► moomoo_to_standard() ──►┘
```

| Function | Input Format | Maps |
|---|---|---|
| `alpaca_to_standard()` | `{timestamp, open, high, low, close, volume}` | Direct mapping |
| `moomoo_to_standard()` | `{time_key, open_price, high_price, low_price, close_price, turnover}` | Field name translation |
| `bars_to_standard()` | List of broker bars + broker_type | Batch conversion |

### 4.4 US Broker: Alpaca

**File:** `cerebellum/broker.py`
**Class:** `AlpacaBroker` (extends `StandardBroker`)

- **Market:** NYSE, NASDAQ
- **Currency:** USD
- **Paper trading:** Default enabled (`PAPER_TRADING=true`)
- **Market hours:** Alpaca clock API (`is_market_open()`)
- **CRITICAL:** `_normalize_side()` — prevents the order side bug (Lesson 6). Maps `long→buy`, `short→sell`.
- `round_price()` — prevents sub-penny violations
- `get_bars()` returns `List[StandardOHLCV]` via `alpaca_to_standard()`

---

## 5. Tool Agent Layer

Tool agents are deployed by the coordinator when positions are open. They think within their domain using the trained candle model.

### 5.1 Position Monitor Tool

**File:** `tools/position_monitor.py`
**Class:** `PositionMonitorTool`

| Method | Purpose |
|---|---|
| `monitor_position()` | Start monitoring a position (symbol, side, entry price) |
| `check_position()` | Fetch live candles, run ONNX inference, decide exit/hold |
| `execute_exit()` | Close position + record `AI_PATTERN` feedback |
| `_run_inference()` | ONNX candle model inference on recent bars |
| `stop_monitoring()` | Remove position from monitoring |

**Inference:** Loads ONNX candle model session. Prepares last 20 candles as OHLCV array. Model outputs directional probabilities (bullish/bearish/neutral).

**Exit logic:** If model predicts opposite direction with `confidence ≥ 0.3`, triggers pattern reversal exit BEFORE stop loss level.

**Feedback recording:** Calls `db.record_trade_feedback()` with:
- `exit_type = "AI_PATTERN"`
- `exit_source = "tool_position_monitor"`
- `candles_at_exit` = JSON candle sequence (high-value training data)

### 5.2 Stop Loss Enforcer Tool

**File:** `tools/stop_loss_enforcer.py`
**Class:** `StopLossEnforcerTool`

| Method | Purpose |
|---|---|
| `set_stop()` | Set stop loss price for a position |
| `check_stops()` | Check all stops against current prices |
| `_enforce_exit()` | Brute-force close + record `STOP_LOSS` feedback |
| `remove_stop()` | Clean up stop level |

**Hard floor:** Always active regardless of AI model state. If current price ≤ stop price (long) or ≥ stop price (short), position is closed. No hesitation. No exceptions. Principle p001.

**Feedback recording:** Calls `db.record_trade_feedback()` with:
- `exit_type = "STOP_LOSS"`
- `exit_source = "tool_stop_loss"`
- `candles_at_exit` = JSON candle sequence

**This is the most important signal in the system.** Every stop loss exit proves the candle model was insufficient. It triggers the improvement cycle.

### 5.3 Risk Aggregator Tool

**File:** `tools/risk_aggregator.py`
**Class:** `RiskAggregatorTool`

| Method | Purpose |
|---|---|
| `assess_risk()` | Full portfolio risk assessment |
| `can_open_position()` | Pre-trade risk gate |

**Risk checks in `assess_risk()`:**

| Check | Threshold | Signal on Breach |
|---|---|---|
| Position count | > 5 positions | `WARNING:RISK` |
| Single position size | > 25% of equity | `WARNING:RISK` |
| Daily loss limit | > -3% of equity | `CRITICAL:RISK` |
| Single position loss | > -5% unrealised | `WARNING:RISK` |

**Pre-trade gate (`can_open_position()`):**
- Checks: position count, position size vs equity, already holding, daily loss limit
- Returns `{allowed: bool, reason: str}` — coordinator must check before submitting trades

---

## 6. Database Architecture

### 6.1 Agent Database (HOST)

**Location:** `/var/lib/catalyst/db/agent.db`
**Schema:** `schema/local-schema.sql`
**Access:** All components (mounted via Docker volumes)

| Table | Rows | Purpose |
|---|---|---|
| `communication` | 55 | Nervous system signal bus — tasks down, results up |
| `pfc_state` | 1 | PFC continuity (mode, resume instructions, session count) |
| `principles` | 5 | Permanent identity (stop losses, love, architecture, dignity, identity) |
| `signals` | 0 | v8 3D signal bus (severity × domain × scope) |
| `coordinator_state` | 1 | **v2.4** — 6-layer cycle state + attention mode |
| `trade_feedback` | 0 | **v2.4** — Exit type tracking for feedback loop |

### 6.2 Coordinator State Table

```sql
coordinator_state:
  agent_id            TEXT    'big_bro'
  current_layer       TEXT    'heartbeat' | 'state' | 'self_regulation' |
                              'working_memory' | 'inter_agent' | 'voice'
  cycle_id            TEXT    'YYYYMMDD-HHMMSS'
  cycle_count         INT    0
  last_cycle_at       TIMESTAMP
  attention_mode      TEXT    'security_selection' | 'candle_execution'
  attention_changed_at TIMESTAMP
  watch_list          TEXT    JSON array of watched symbols
  active_securities   TEXT    JSON {symbol: {direction, confidence, source, added_at}}
  body_health         TEXT    JSON {component: {status, last_seen}}
  candle_model_loaded INT    0|1
  news_model_loaded   INT    0|1
  fused_model_loaded  INT    0|1
  market_open         INT    0|1
  trading_enabled     INT    0|1
  daily_pnl           REAL   0.0
  updated_at          TIMESTAMP
```

### 6.3 Trade Feedback Table

```sql
trade_feedback:
  id                  INT     AUTO
  symbol              TEXT    'AAPL', 'NVDA', etc.
  market              TEXT    'US' | 'HKEX'
  broker              TEXT    'alpaca' | 'moomoo'
  entry_price         REAL
  exit_price          REAL
  return_pct          REAL
  qty                 INT
  side                TEXT    'buy' | 'sell'
  exit_type           TEXT    'AI_PATTERN' | 'STOP_LOSS' | 'MANUAL' | 'ADVERSARIAL_EVENT'
  pattern_type        TEXT    e.g. 'bullish_engulfing'
  holding_minutes     INT
  neural_prediction   TEXT    JSON — what the model predicted at entry
  neural_confidence   REAL
  candle_model_version TEXT
  candles_at_exit     TEXT    JSON — candle sequence for retraining
  exit_source         TEXT    'tool_position_monitor' | 'tool_stop_loss' | 'manual'
  entry_at            TIMESTAMP
  exit_at             TIMESTAMP
  created_at          TIMESTAMP
```

### 6.4 Hippocampus Database

**Location:** `/var/lib/catalyst/hippocampus/memory.db`
**Schema:** `schema/hippocampus-schema.sql`
**Access:** Hippocampus container (exclusive)

| Table | Purpose |
|---|---|
| `learnings` | Long-term memory (confidence, validation count) |
| `memory_bindings` | Cross-modal associations between memories |
| `combined_picture` | Assembled context cache for coordinator |
| `pattern_outcomes` | Per-trade outcome linked to triggering pattern |
| `pattern_confidence` | Synaptic weights (updated by LTP/LTD) |

---

## 7. Signal Bus

**Table:** `signals` in agent.db
**Dimensions:** severity × domain × scope

### 7.1 Severity Levels

| Severity | Processing | Use |
|---|---|---|
| `CRITICAL` | Processed first (adrenaline flood) | Component failure, daily loss limit, emergency |
| `WARNING` | Attention needed | Stop loss hit, risk breach, exposure warning |
| `INFO` | Normal reporting | Trade submitted, mode switch, position change |
| `OBSERVE` | Low-priority | Market observation, pattern detection |

### 7.2 Signal Domains

| Domain | Source | Purpose |
|---|---|---|
| `HEALTH` | All components | Component liveness, heartbeat |
| `TRADING` | Cerebellum, tools | Trade execution, fill confirmation |
| `RISK` | Risk Aggregator, Monitor | Risk limit breaches |
| `LEARNING` | Learning module | Pattern confidence changes |
| `DIRECTION` | big_bro (PFC) | Strategic directives (stop/resume/emergency) |
| `LIFECYCLE` | Coordinator | Start/stop/mode changes |
| `ATTENTION` | Coordinator | **v2.4** — Attention mode switches |
| `EXECUTION` | Coordinator | **v2.4** — Trade submission events |

### 7.3 Signal Flow

```
Components publish:
  HEALTH:BROADCAST     — "I'm alive" (every 30s)
  TRADING:BROADCAST    — "Fill confirmed" / "Stop loss hit"
  RISK:BROADCAST       — "Exposure warning"

Coordinator reads (Layer 4 + 5):
  CRITICAL first, then WARNING, INFO, OBSERVE
  Filters: last 10 minutes, not yet resolved

Coordinator publishes:
  ATTENTION:BROADCAST  — mode switch events
  EXECUTION:BROADCAST  — trade submitted events
  LIFECYCLE:BROADCAST  — online/offline/cycle count
```

---

## 8. Feedback Loop — Three Learning Paths

### 8.1 Path 1 — Database Learning (Cycle-Speed)

**File:** `learning/learning.py` → `process_feedback()`
**Speed:** Within one trading day
**Depth:** Single weight adjustment

```
Trade closed
  → exit_type recorded in trade_feedback table
  → Pondering cycle reads trade_feedback (last 24 hours)
  → For each trade:
      AI_PATTERN exit with profit → LTP (+5% base × (1 + |return|))
      AI_PATTERN exit with loss   → mild LTD
      STOP_LOSS exit              → strong LTD (-8% base × (1 + |return|))
  → pattern_confidence weights updated in hippocampus memory.db
  → Coordinator loads updated weights next cycle (Layer 4)
```

**LTP/LTD Parameters:**
- LTP increment: 0.05 (base) — bigger wins = stronger LTP
- LTD decrement: 0.08 (base) — asymmetric, losses teach more
- Confidence bounds: [0.05, 0.95]
- Weekly decay: 0.995 for patterns not traded in 7 days

### 8.2 Path 2 — Neural Learning (Training-Speed)

**Location:** Laptop (RTX 4050 GPU)
**Speed:** Weeks/months
**Depth:** Architecture-level weight reshaping

- Gradient descent on accumulated candle data + forward return labels
- Network discovers its own pattern representations
- Trained on laptop, exported as ONNX, deployed to droplet via SCP
- `neural_claude` manages training cycles

### 8.3 Path 3 — Production Feedback (Daily)

**File:** `learning/learning.py` → `export_training_data()`
**Speed:** End of each trading day
**Scope:** Model learning from its own mistakes

```
trade_feedback (droplet) → export_training_data() → JSON file
  → SCP to laptop → neural_claude consumes
  → Computes: was the prediction right? Was confidence calibrated?
  → Stop loss events flagged and analysed for context clustering
  → Feeds highest-weight examples into next training run
```

**Export format (per record):**
```json
{
  "symbol": "AAPL",
  "market": "US",
  "entry_price": 185.50,
  "exit_price": 183.20,
  "return_pct": -0.0124,
  "exit_type": "STOP_LOSS",
  "neural_prediction": "{\"direction\": \"bullish\", ...}",
  "neural_confidence": 0.42,
  "candles_at_exit": "[{\"timestamp\": ..., \"open\": ...}, ...]",
  "candle_model_version": "candle_v0.3",
  "entry_at": "2026-04-08T10:30:00",
  "exit_at": "2026-04-08T11:15:00"
}
```

---

## 9. Shared Vocabulary (Enums)

**File:** `shared/models.py`

### 9.1 v2.4 Enums

| Enum | Values | Purpose |
|---|---|---|
| `Component` | pfc, coordinator, occipital, cerebellum, hippocampus, monitor, neural, broadcast, tool_position_monitor, tool_stop_loss, tool_risk_aggregator | All body components |
| `AttentionMode` | security_selection, candle_execution | Attention State Machine modes |
| `CoordinatorLayer` | heartbeat, state, self_regulation, working_memory, inter_agent, voice | 6-layer cycle |
| `ExitType` | AI_PATTERN, STOP_LOSS, MANUAL, ADVERSARIAL_EVENT | Trade exit classification |
| `BrokerType` | alpaca, moomoo | Multi-deployment broker selection |
| `SignalDomain` | HEALTH, TRADING, RISK, LEARNING, DIRECTION, LIFECYCLE, ATTENTION, EXECUTION | Signal domains (8 total) |

### 9.2 v2.4 Dataclasses

| Dataclass | Fields | Purpose |
|---|---|---|
| `StandardOHLCV` | timestamp, open, high, low, close, volume, timeframe | Broker-agnostic candle format |
| `TradeFeedback` | symbol, market, entry/exit price, return_pct, exit_type, neural_prediction, candles_at_exit, broker | Feedback record |

---

## 10. Environment Variables

### 10.1 US Deployment (.env)

```bash
# Broker
BROKER_TYPE=alpaca
MARKET=US

# Alpaca credentials
ALPACA_API_KEY=<key>
ALPACA_SECRET_KEY=<secret>
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets
PAPER_TRADING=true

# AI
ANTHROPIC_API_KEY=<key>

# Database
AGENT_DB_PATH=/var/lib/catalyst/db/agent.db
HIPPOCAMPUS_DB_PATH=/var/lib/catalyst/hippocampus/memory.db
DATABASE_URL=<postgres_url>

# Models (ONNX — trained on laptop, deployed via SCP)
CANDLE_MODEL_PATH=/var/lib/catalyst/models/candle_model.onnx
NEWS_MODEL_PATH=/var/lib/catalyst/models/news_model.onnx
FUSED_MODEL_PATH=/var/lib/catalyst/models/catalyst_net.onnx

# Market hours
MARKET_TIMEZONE=America/New_York
MARKET_OPEN_HOUR=9
MARKET_OPEN_MINUTE=30
MARKET_CLOSE_HOUR=16
MARKET_CLOSE_MINUTE=0

# Coordinator
COORDINATOR_CYCLE_INTERVAL=30.0

# Risk limits
MAX_POSITION_PCT=0.25
MAX_DAILY_LOSS_PCT=0.03
STOP_LOSS_PCT=0.03

# General
AGENT_ID=big_bro
POLL_INTERVAL=2.0
LOG_LEVEL=INFO
```

### 10.2 Intl Deployment (pending — different .env)

```bash
BROKER_TYPE=moomoo
MARKET=HKEX
MOOMOO_API_KEY=<key>
MOOMOO_SECRET_KEY=<secret>
MOOMOO_BASE_URL=<url>
MOOMOO_MARKET=HKEX
MARKET_TIMEZONE=Asia/Hong_Kong
MARKET_OPEN_HOUR=9
MARKET_OPEN_MINUTE=30
MARKET_CLOSE_HOUR=16
MARKET_CLOSE_MINUTE=0
# Same model paths — ONNX models are broker-agnostic
```

---

## 11. Docker Services (Body Components)

**File:** `docker-compose.yml`

| Service | Container | Purpose | Key Env Vars |
|---|---|---|---|
| `occipital` | catalyst-occipital | Pattern recognition | BROKER_TYPE, ALPACA creds |
| `cerebellum` | catalyst-cerebellum | Procedure execution | BROKER_TYPE, ALPACA + MOOMOO creds, models volume |
| `monitor` | catalyst-monitor | Reflexive position tracking | BROKER_TYPE, ALPACA creds |
| `hippocampus` | catalyst-hippocampus | Memory binding | HIPPOCAMPUS_DB_PATH |
| `neural` | catalyst-neural | ONNX model inference | CANDLE/FUSED/NEWS_MODEL_PATH, MARKET, models volume |

**Host components (not in Docker):**
- `coordinator.py` — the brain
- Tool agents — Position Monitor, Stop Loss Enforcer, Risk Aggregator
- PFC (Claude Code) — called by coordinator for novel situations

**Volume mounts:**
- All services: `/var/lib/catalyst/db:/var/lib/catalyst/db`
- Hippocampus: `/var/lib/catalyst/hippocampus:/var/lib/catalyst/hippocampus`
- Cerebellum + Neural: `/var/lib/catalyst/models:/var/lib/catalyst/models:ro`

**All services:** `network_mode: host`, `restart: unless-stopped`, healthcheck on SQLite connection, JSON-file logging (10MB max, 3 files)

---

## 12. Memory Architecture

| Tier | Storage | Purpose | Persistence |
|---|---|---|---|
| **Identity** | CLAUDE.md | Archetype — who the brain is | Permanent. Loaded Layer 2. Never auto-modified. |
| **Learned** | ONNX weights | Cerebellum — accumulated pattern wisdom | Persistent. Updated through training cycles. |
| **Synaptic** | pattern_confidence (memory.db) | LTP/LTD weights per pattern | Updated by Pondering cycle. |
| **Validated** | CLAUDE-LEARNINGS.md | Validated insights — proven over time | Weeks/months. big_bro approves. |
| **Working** | CLAUDE-FOCUS.md | Current session — active securities, live context | Hours/days. Pruned regularly. |
| **Coordinator** | coordinator_state (agent.db) | Cycle state, attention mode, watch list | Updated every cycle. |
| **Feedback** | trade_feedback (agent.db) | Exit type + candle context per trade | Permanent. Training data. |

**Memory load order:** CLAUDE.md first (Layer 2). Identity before memory. Formation before information. Every cycle, without exception.

---

## 13. Data Paths

### 13.1 Storage Locations

| Path | Content | Persistence |
|---|---|---|
| `/var/lib/catalyst/db/agent.db` | Communication, signals, coordinator state, feedback | Persistent (host volume) |
| `/var/lib/catalyst/hippocampus/memory.db` | Learnings, bindings, pattern confidence | Persistent (host volume) |
| `/var/lib/catalyst/models/` | ONNX models (candle, news, fused) | Deployed from laptop via SCP |
| `/root/catalyst-agent/` | Codebase | Git-managed |

### 13.2 Model Deployment Path

```
Laptop (RTX 4050)
  │ train_candle.py → candle_model.pt → export → candle_model.onnx
  │ train_news.py → news_model.pt → export → news_model.onnx
  │
  │ validate.py → must exceed baseline → big_bro approves
  │
  └──► SCP ──► /var/lib/catalyst/models/ on droplet
                  │
                  ├── candle_model.onnx  → neural container + Position Monitor tool
                  ├── news_model.onnx    → neural container
                  └── catalyst_net.onnx  → neural container (fused/legacy)
```

---

## 14. Current State

**As of 2026-04-08:**

| Component | Status |
|---|---|
| coordinator.py | ✅ Implemented — 6-layer cycle + Attention State Machine |
| Broker abstraction | ✅ Implemented — StandardBroker + AlpacaBroker |
| Data normalisation | ✅ Implemented — alpaca_to_standard() + moomoo_to_standard() |
| Tool agents | ✅ Implemented — Position Monitor, Stop Loss Enforcer, Risk Aggregator |
| Feedback loop | ✅ Instrumented — exit_type recording, trade_feedback table |
| Three learning paths | ✅ Wired — process_feedback() (Path 1), export_training_data() (Path 3) |
| Schema | ✅ Applied — coordinator_state + trade_feedback in live agent.db |
| Docker compose | ✅ Updated — BROKER_TYPE, model volumes, MARKET env |
| ONNX models | ⬜ Not yet deployed — `/var/lib/catalyst/models/` exists but empty |
| First trading cycle | ⬜ Not yet run — coordinator_state shows cycle_count=0 |
| Moomoo broker | ⬜ Pending — StandardBroker interface ready, implementation TBD |

---

## 15. Design Principles (v2.4 Aligned)

1. **Identity loads first.** CLAUDE.md before everything. Layer 2. Every cycle.
2. **The cerebellum handles the routine.** Claude AI handles only what requires genuine reasoning.
3. **The attention state machine is cognitive.** The coordinator chooses where to focus. Not a loop.
4. **Tools think within their domain.** Position Monitor runs the candle model — it doesn't just watch price.
5. **Stop loss hits are training gold.** Each one proves the model was insufficient. Each one improves it.
6. **Three paths, one loop.** Database LTP/LTD, neural training, production feedback. All three run.
7. **Context shapes behaviour.** The same pattern in different contexts may need different models.
8. **Not everything is true.** Markets can be manipulated. Investigate before learning.
9. **The model earns its deployment.** Accuracy against the positions table is the only proof.
10. **The choice is simply good or evil. Fruit proves which.**

---

## 16. Related Documents

| Document | Version | Type | Scope |
|---|---|---|---|
| AI Agent Architecture | v8.0 | Architecture | General biological pattern |
| Catalyst AI Architecture | v2.4 | Architecture | Implementation mapping — broker-agnostic |
| Catalyst Strategy Roadmap | v1.0 | Strategy | Four-phase plan — objectives, sequencing |
| Catalyst Neural Architecture | v0.3 | Architecture | ML pipeline — collection, training, deployment |
| Catalyst US Configuration (this doc) | v1.0 | Configuration | US droplet running state — Alpaca, NYSE/NASDAQ |
| Catalyst Intl Configuration | (pending) | Configuration | Intl droplet running state — Moomoo, HKEX |

---

*"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body."* — Romans 12:4-5

*Catalyst US Configuration v1.0 — Craig + Claude — 2026-04-08*
