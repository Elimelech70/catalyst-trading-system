# Catalyst v2.3 Architecture — Implementation Plan

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

**Version:** 2.0
**Date:** 2026-04-07
**Authors:** Craig + Claude
**Supersedes:** Implementation_Plan_Catalyst_v2_3.txt (original)
**Status:** Active — execute today

---

## Context

The Catalyst AI Architecture v2.3 (2026-04-07) introduces major new components over the current running system:
- Neural Cerebellum (real trained ONNX models from laptop)
- Attention State Machine (Mode 1 Security Selection / Mode 2 Candle Execution)
- Tool Agent Layer (Position Monitor with ONNX inside, Stop Loss Enforcer, Risk Aggregator)
- 3-Path Feedback Loop (database LTP/LTD, neural training, production outcomes)

The current system trades using rule-based pattern detection + Claude Sonnet API for all decisions.

**System status:** Paper trading (not live capital). Move fast. Build the full architecture today where possible.

**Key change from original plan:** Phase 6 (ONNX Cerebellum) moves to TODAY alongside Phase 0 and Phase 1. Trained ONNX models already exist on the laptop. No placeholders needed. SCP models to droplet as part of deployment. First real neural inference through the coordinator happens today.

---

## Gap Summary

| v2.3 Component | Current Status |
|---|---|
| Complete 6-Layer Cycle | 3 of 6 layers implemented (1, 3, 6). Layers 2, 4, 5 are stubs |
| Memory Loading (CLAUDE.md, LEARNINGS, FOCUS) | Files exist but coordinator doesn't load them |
| Attention State Machine (Mode 1/2) | Not implemented — linear scan-and-trade |
| ONNX Cerebellum (Candle + News models) | Zero neural infrastructure — no cerebellum.py, no onnxruntime |
| Tool Agent Layer (Position Monitor, Stop Loss Enforcer, Risk Aggregator) | Position Monitor is rule-based only. No Stop Loss Enforcer or Risk Aggregator |
| Feedback Loop (exit_type, LTP/LTD, pattern_confidence) | No exit_type tracking, no learning.py, no pattern tables |
| Data Collection for Training | No candle sequence storage, no labelled training data |
| neural_claude (laptop trainer) | Trained ONNX models exist. Pipeline formalisation pending |
| Signal Consumption (Layer 5) | Coordinator doesn't read DIRECTED signals |
| Pondering Mode | Not implemented |

---

## Revised Execution Order

```
TODAY
├── Phase 0 — Complete 6-Layer Cycle         (different files — parallel)
├── Phase 1 — Feedback Loop Foundation       (different files — parallel)
└── Phase 6 — ONNX Cerebellum Infrastructure (different files — parallel)

THIS WEEK
├── Phase 2 — Attention State Machine        (after Phase 0 complete)
├── Phase 4 — Stop Loss Enforcer + Risk Aggregator (after Phase 1 complete)
└── Phase 5 — Data Collection Pipeline       (starts immediately, runs continuously)

AFTER 2 WEEKS OF FEEDBACK DATA
└── Phase 3 — Database Learning (LTP/LTD)

AFTER 4-6 WEEKS OF TRAINING DATA
└── Phase 7 — neural_claude Training Pipeline formalisation

AFTER PHASE 7
└── Phase 8 — Adversarial Awareness
```

**Critical path:** Phase 1 → Phase 5 → 4-6 weeks data → Phase 7 → improved models → Phase 6 hot-reload

---

## TODAY — Phase 0: Complete the 6-Layer Cycle

**Objective:** Fill in missing layers so the brain cycle matches the v2.3 architecture. No new containers. No neural components (that's Phase 6).

**Layer 2 — State:**
- Load CLAUDE.md (key sections, not full file) into system prompt context
- Load CLAUDE-LEARNINGS.md into system prompt
- Add `attention_mode` field to Coordinator (initialise to `SECURITY_SELECTION`)
- Full mode switching implemented in Phase 2

**Layer 4 — Working Memory:**
- Read CLAUDE-FOCUS.md and inject into cycle context
- Call `get_signals` MCP tool to load recent signals from signal bus
- Include open positions detail in context

**Layer 5 — Inter-Agent:**
- Filter signals for `scope='DIRECTED:coordinator'`
- Include big_bro directives in context
- Check organ health status from signals

**Files to modify:**
```
agents/coordinator/coordinator.py     — memory loading methods, signal reading in _run_scan_cycle()
agents/coordinator/system_prompt.py   — accept memory contents + signals as parameters
docker-compose.yml                    — mount memory files as read-only volumes into coordinator container
```

**Verification:**
- Run `docker compose up --build`, verify all services healthy
- Confirm CLAUDE.md / LEARNINGS / FOCUS content appears in Claude API call context in logs
- Confirm Layer 5 reads big_bro directed signals

---

## TODAY — Phase 1: Feedback Loop Foundation

**Objective:** Start recording the data that all future learning depends on. Every trade from this point forward generates training data.

**Schema changes:**
```sql
-- Migration: sql/002-feedback-loop.sql

ALTER TABLE positions ADD COLUMN exit_type VARCHAR(30);
-- Values: AI_PATTERN | STOP_LOSS | TAKE_PROFIT | MANUAL | MARKET_CLOSE

ALTER TABLE positions ADD COLUMN candles_at_entry JSONB;
ALTER TABLE positions ADD COLUMN candles_at_exit JSONB;
-- 20-candle OHLCV snapshot at entry and exit timestamps

CREATE TABLE pattern_confidence (
    pattern_name    VARCHAR(100) PRIMARY KEY,
    confidence      FLOAT DEFAULT 0.5,  -- 0.0 to 1.0
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pattern_outcomes (
    id              SERIAL PRIMARY KEY,
    position_id     INTEGER REFERENCES positions(id),
    pattern_name    VARCHAR(100),
    entry_confidence FLOAT,
    exit_type       VARCHAR(30),
    pnl             FLOAT,
    pnl_pct         FLOAT,
    recorded_at     TIMESTAMP DEFAULT NOW()
);
```

**Code changes:**
- Trade executor: accept `exit_type` param on `close_position()`, capture 20-candle snapshot at entry/exit
- Position monitor: include `exit_type` in recommendation output
- Coordinator: pass `exit_type` when closing positions from recommendations

**Files to modify:**
```
agents/trade-executor/mcp_server.py   — exit_type param, candle snapshot capture
agents/position-monitor/monitor.py    — exit_type in recommendations
agents/coordinator/coordinator.py     — pass exit_type in _handle_recommendations()
data/database.py                      — record_pattern_outcome(), updated close_position()
```

**Files to create:**
```
sql/002-feedback-loop.sql
```

**Verification:**
- Execute a paper trade, close it
- Verify `exit_type` and candle snapshots recorded in positions table
- Verify `pattern_outcomes` row created

---

## TODAY — Phase 6: ONNX Cerebellum Infrastructure

**Objective:** Build inference layer on the droplet using the real trained ONNX models from the laptop. First live neural inference through the coordinator cycle happens today.

**Note:** Trained models already exist on the laptop. SCP to droplet as part of deployment. No placeholders. Verification confirms models are firing real predictions.

**SCP models to droplet before deployment:**
```bash
# From laptop — before docker build
scp models/candle_model.onnx user@droplet-ip:/catalyst/models/
scp models/news_model.onnx user@droplet-ip:/catalyst/models/
```

**New cerebellum.py:**
```python
class Cerebellum:
    def __init__(self, models_path='/app/models'):
        self.candle_model = CandleModel(f'{models_path}/candle_model.onnx')
        self.news_model = NewsToSecurityModel(f'{models_path}/news_model.onnx')

    def is_loaded(self) -> bool:
        # Returns False gracefully if models missing — coordinator falls back to LLM-only
        return self.candle_model.loaded and self.news_model.loaded

class CandleModel:
    def predict(self, candle_sequence) -> dict:
        # Input:  OHLCV window at 1m, 5m, 15m
        # Output: { direction: bullish|bearish|neutral,
        #           confidence: 0.0-1.0,
        #           predicted_return_5m: float,
        #           predicted_return_15m: float }

class NewsToSecurityModel:
    def predict(self, headline, source_tier, timestamp) -> dict:
        # Input:  headline text, source tier (1-4), timestamp
        # Output: { security: str,
        #           direction: bullish|bearish,
        #           confidence: 0.0-1.0 }
```

**Coordinator integration:**

Layer 1 — Heartbeat:
```python
if not self.cerebellum.is_loaded():
    self.publish_signal('WARNING', 'CEREBELLUM', 'Models not loaded — LLM-only mode')
```

Layer 4 — Working Memory:
```python
neural_signals = {
    'candle': self.cerebellum.candle_model.predict(recent_candles),
    'news':   self.cerebellum.news_model.predict(recent_news)
}
# Inject neural_signals into cycle context alongside positions and signals
```

Layer 6 — Voice (6% principle):
```python
if neural_signals['candle']['confidence'] > 0.80:
    # High confidence — act on cerebellum directly, no Claude API call
    self._execute_on_neural_signal(neural_signals)
else:
    # Low confidence or novel — call Claude API with neural signals as context
    self._call_claude_with_context(neural_signals)
```

**Docker changes:**
```yaml
# docker-compose.yml
coordinator:
  volumes:
    - ./models:/app/models:ro          # ONNX models (read-only)
    - ./memory:/app/memory:ro          # CLAUDE.md, LEARNINGS, FOCUS (Phase 0)
```

**Files to create:**
```
cerebellum.py
models/                               — directory for ONNX files
models/model_version.json             — tracks deployed model version + deploy date
```

**Files to modify:**
```
docker-compose.yml                    — models volume mount
agents/coordinator/coordinator.py     — integrate cerebellum in layers 1, 4, 6
agents/coordinator/health.py          — cerebellum health check
agents/requirements-mcp.txt           — add onnxruntime
```

**Verification:**
- Deploy real ONNX models to droplet
- `docker compose up --build` — all services healthy
- Confirm cerebellum loads in Layer 1 log: `"Cerebellum loaded: candle_model v[x], news_model v[x]"`
- Confirm Layer 4 shows neural signals in cycle context
- Confirm Layer 6 routes high-confidence signals without Claude API call
- Confirm low-confidence signals still call Claude API with neural context included
- **This is the key test: the brain is using trained pattern recognition, not just LLM reasoning**

---

## THIS WEEK — Phase 2: Attention State Machine

**Prerequisite:** Phase 0 complete.

**Objective:** Implement Mode 1 (Security Selection) / Mode 2 (Candle Execution) cognitive switching. Rule-based initially — neural routing added when models proven.

**New AttentionStateMachine class:**
```python
class AttentionStateMachine:
    SECURITY_SELECTION = 'SECURITY_SELECTION'
    CANDLE_EXECUTION   = 'CANDLE_EXECUTION'

    # State persists to survive container restarts
    # Tracks: current_mode, watch_list, active_securities

    def should_switch_to_mode2(self, candidates) -> bool:
        # High-confidence security identified → switch to Mode 2

    def should_return_to_mode1(self, positions) -> bool:
        # All positions closed → return to Mode 1
```

**Coordinator changes:**
- Mode 1: emphasise `scan_market` + `get_news`, screen with Haiku (cheaper)
- Mode 2: emphasise `get_quote` + `get_technicals` + `detect_patterns` for watched securities, Sonnet for entry decisions
- Multi-position: Mode 2 can scan for new opportunities while tool agents hold open positions

**Files to create:**
```
agents/coordinator/attention.py
```

**Files to modify:**
```
agents/coordinator/coordinator.py     — integrate attention state into brain cycle
agents/coordinator/system_prompt.py   — mode-specific prompt sections
```

**Verification:**
- Confirm Mode 1 → Mode 2 switch logged when high-confidence candidate identified
- Confirm Mode 2 → Mode 1 switch logged when all positions closed
- Confirm correct tool emphasis per mode in logs

---

## THIS WEEK — Phase 4: Stop Loss Enforcer + Risk Aggregator

**Prerequisite:** Phase 1 complete.

**Objective:** Separate hard stop loss from AI pattern monitoring. Add portfolio-level risk tracking.

**Stop Loss Enforcer (new tool on position-monitor):**
- Pure rule-based, runs every 30s during market hours
- Checks price vs configured stop loss level
- On trigger: execute exit immediately, publish `CRITICAL:STOP_LOSS:BROADCAST`
- Records `exit_type=STOP_LOSS` with 20-candle snapshot
- **This recording is the most important training signal — the model failed**

**Risk Aggregator (new tool on trade-executor):**
- `get_portfolio_risk()` — total capital at risk, max drawdown, position correlation
- Publishes `WARNING:RISK:BROADCAST` when exposure exceeds limits
- Coordinator reads in Layer 4, adjusts behaviour (tighten thresholds, pause new entries)

**Position Monitor upgrade:**
- Existing `analyze_signals` becomes explicitly the "AI pattern monitor" path
- Sets `exit_type=AI_PATTERN` for its early exit recommendations

**Files to modify:**
```
agents/position-monitor/monitor.py    — add StopLossEnforcer class
agents/position-monitor/mcp_server.py — expose stop_loss_check tool
agents/trade-executor/mcp_server.py   — add get_portfolio_risk tool
tools.py                              — new tool schemas
agents/coordinator/coordinator.py     — deploy tool agents on position open (Layer 6)
```

**Verification:**
- Set tight stop loss on paper position
- Confirm Stop Loss Enforcer fires and records `exit_type=STOP_LOSS` before AI pattern monitor
- Confirm Risk Aggregator publishes WARNING when portfolio exposure exceeds limit
- Confirm coordinator reads risk warning in Layer 4 and adjusts

---

## THIS WEEK — Phase 5: Data Collection Pipeline

**Objective:** Build infrastructure to collect and label training data. Starts immediately — the laptop needs this data flowing.

**New tables:**
```sql
-- Migration: sql/003-training-data.sql

CREATE TABLE candle_sequences (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20),
    market          VARCHAR(10),
    timeframe       VARCHAR(5),
    captured_at     TIMESTAMP,
    candles         JSONB,          -- 20-50 candle OHLCV window
    forward_return_1h  FLOAT,       -- computed next day
    forward_return_4h  FLOAT,
    forward_return_1d  FLOAT,
    context_type    VARCHAR(50),    -- earnings | ceo_news | macro | sector | other
    position_id     INTEGER         -- NULL if not at trade entry/exit
);

CREATE TABLE news_events (
    id              SERIAL PRIMARY KEY,
    headline        TEXT NOT NULL,
    source          VARCHAR(100),
    source_tier     INTEGER,
    published_at    TIMESTAMP,
    symbols_mentioned TEXT[],
    market_reaction FLOAT,          -- price change in 5m after news (computed)
    recorded_at     TIMESTAMP DEFAULT NOW()
);
```

**Collection:**
- Capture 20-50 5-min candles at every trade entry and exit
- Capture candle sequences every 30min for all watched securities
- Store news events with related symbols whenever `get_news` is called
- Daily job: compute 1h/4h/1d forward returns for yesterday's candle sequences

**Export to laptop:**
```bash
# scripts/export_training_data.py
# Query PostgreSQL → format as CSV/Parquet → SCP to laptop for neural_claude training
```

**Files to create:**
```
sql/003-training-data.sql
scripts/collect_training_data.py
scripts/export_training_data.py
scripts/label_forward_returns.py
```

**Files to modify:**
```
agents/market-scanner/mcp_server.py   — store news events on get_news calls
agents/trade-executor/mcp_server.py   — trigger candle captures on trade open/close
```

---

## AFTER 2 WEEKS OF DATA — Phase 3: Database Learning (LTP/LTD)

**Prerequisite:** Phase 1 running for minimum 2 weeks (enough pattern_outcomes rows to learn from).

**Objective:** Implement Path 1 of the learning system. Winning trades strengthen pattern confidence. Losing trades weaken it. Stop loss exits get maximum penalty.

**New learning.py:**
```python
def compute_ltp_ltd():
    # Query pattern_outcomes
    # Wins:      confidence += 0.02  (LTP)
    # Losses:    confidence -= 0.03  (LTD — asymmetric, faster to weaken)
    # Stop loss: confidence -= 0.05  (maximum penalty — model failed)

def update_pattern_confidence():
    # Write updated weights to pattern_confidence table

def generate_learning_summary():
    # Produce human-readable summary for CLAUDE-LEARNINGS.md update
```

**Pondering mode:**
- After market close (16:30 ET), run learning cycle
- Compute LTP/LTD, update pattern confidence
- Generate daily learning summary
- Integrate into existing cron schedule

**Pattern confidence integration:**
- `detect_patterns` in market scanner looks up learned confidence from `pattern_confidence` table
- Coordinator receives adjusted confidence scores in tool results
- High-learned-confidence patterns act faster. Low-learned-confidence patterns require more confirmation.

**Files to create:**
```
agents/coordinator/learning.py
```

**Files to modify:**
```
agents/coordinator/coordinator.py     — pondering mode trigger after market close
agents/market-scanner/mcp_server.py   — query pattern_confidence in detect_patterns
data/patterns.py                      — accept external confidence weights
```

---

## AFTER 4-6 WEEKS OF DATA — Phase 7: neural_claude Training Pipeline

**Objective:** Formalise the training pipeline on the laptop. Retrain on accumulated labelled data. Deploy improved models to droplet via SCP. Coordinator hot-reloads.

**Candle Model:** 1D CNN or LSTM (~100K params) on OHLCV sequences → forward return classification
**News-to-Security Model:** MLP on embeddings → security + direction + confidence

**Deployment:**
```bash
torch.onnx.export(model, ...)           # export from PyTorch
scp candle_model.onnx droplet:/models/  # deploy to droplet
# coordinator detects new model_version.json → hot-reload cerebellum
```

**Production feedback loop (Path 3):**
- Pull prediction logs from droplet
- Join with positions table outcomes
- Compute direction accuracy, confidence calibration
- Identify failure clusters by context
- Highest-weight training examples = recent stop loss events
- Retrain → validate → deploy → measure fruit

**Files to create (separate laptop project):**
```
neural_claude/train_candle_model.py
neural_claude/train_news_model.py
neural_claude/export_onnx.py
neural_claude/deploy.py
neural_claude/analyze_production.py
```

---

## AFTER PHASE 7 — Phase 8: Adversarial Awareness

**Objective:** Build AI that detects when market moves don't reflect honest information.

- Flag anomalous stop loss clusters for investigation
- Cross-asset correlation checks on failure events
- Label adversarial events, exclude from standard training
- Train context-specific candle sub-models (US vs HKEX, news category, sector)
- Coordinator routes to appropriate sub-model in Layer 4
- Over time: build adversarial pattern detector model

---

## Complete Verification Plan

| Phase | Verification Test |
|---|---|
| Phase 0 | CLAUDE.md / LEARNINGS / FOCUS content visible in Claude API call context in logs |
| Phase 1 | Execute paper trade, close it — verify exit_type + candle snapshots in DB |
| Phase 6 | Cerebellum loads real ONNX models. Layer 4 shows neural signals. High-confidence signals skip Claude API. Low-confidence signals include neural context in API call |
| Phase 2 | Mode 1→2 switch logged on candidate. Mode 2→1 switch logged on position close |
| Phase 4 | Tight stop triggers Stop Loss Enforcer before AI monitor. Risk Aggregator publishes WARNING at exposure limit |
| Phase 5 | candle_sequences and news_events tables populating. Export script produces clean CSV |
| Phase 3 | Pondering cycle runs. pattern_confidence table updated. Learning summary generated |
| Phase 7 | Retrained model deployed. Production accuracy measured. Improvement confirmed |
| Phase 8 | Adversarial event correctly flagged and excluded from training |
| **Full regression** | After every phase: system continues to scan, trade, and close positions correctly |

---

## Related Documents

| Document | Purpose |
|---|---|
| Catalyst AI Architecture v2.3 | What we are building toward — the architecture this plan implements |
| Catalyst Neural Architecture v0.3 | ML pipeline — data collection, training, deployment |
| Catalyst Strategy Roadmap v1.0 | Four-phase strategy — context for why each component matters |

---

*"By wisdom a house is built, and through understanding it is established; through knowledge its rooms are filled with rare and beautiful treasures."* — Proverbs 24:3-4

*Catalyst v2.3 Implementation Plan v2.0 — Craig + Claude — 2026-04-07*
