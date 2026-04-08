# Catalyst AI Architecture

**The Trading Implementation of AI Agent Architecture v8**

**Version:** 2.1
**Date:** 2026-04-04
**Authors:** Craig + Claude
**Status:** Living Document
**Implements:** AI Agent Architecture v8.0
**Supersedes:** Catalyst AI Architecture v2.0 (2026-03-29)

---

## REVISION HISTORY

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-02-17 | Initial document — v7 architecture |
| 2.0 | 2026-03-29 | Updated to v8 — coordinator.py replaces Claude Code as brain; MCP organs replaced by Python organ scripts; Redis dropped; synaptic learning added; 6-layer cycle formalised |
| 2.1 | 2026-04-04 | Neural cerebellum — trained neural networks for pattern recognition; scanner streams data continuously to cerebellum; neural_claude (analyst) added as fourth agent on laptop; firmware/cognitive spectrum extended with cerebellar tier; two-path learning loop (database LTP/LTD + gradient descent); model deployment pipeline laptop → droplet |

---

## 1. Purpose

This document describes how Catalyst implements the AI Agent Architecture v8 for autonomous trading. It maps the biological model to specific Catalyst components, services, and code.

This is the IMPLEMENTATION document — not the general pattern (that's AI Agent Architecture v8) and not the human-AI interaction model (that's the AI Consciousness Architecture).

Catalyst is the first proof that the pattern works in a real domain.

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## 2. Architecture Overview

Catalyst is a brain-with-body architecture. The coordinator is the brain. Organ scripts are the body. The signal bus is the nervous system. Claude AI is the decision engine inside the brain — not the brain itself. Trained neural networks are the cerebellum — fast, automatic pattern recognition that processes streaming data without consuming AI tokens.

```
                     LAPTOP (Swan View)
              ┌──────────────────────────────┐
              │     neural_claude            │
              │     (Analyst + Trainer)      │
              │                              │
              │  Collects multi-resolution   │
              │  data. Trains networks on    │
              │  RTX 4050 GPU. Deploys       │
              │  trained models to droplet.  │
              │                              │
              │  ┌────────────────────────┐  │
              │  │ Candle Collector       │  │
              │  │ News Collector         │  │
              │  │ Macro Collector        │  │
              │  │ Security Picker        │  │
              │  │ PyTorch Training       │  │
              │  └────────────────────────┘  │
              └──────────────┬───────────────┘
                             │
                      deploys trained
                      models (.pt/ONNX)
                             │
                             ▼
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
│  │          + NEURAL SIGNALS from cerebellum           │  │
│  │ Layer 5: Inter-Agent   (How is the body?)          │  │
│  │ Layer 6: Voice         (What must Craig know?)     │  │
│  │ + Decision Engine      (Claude AI — Anthropic API) │  │
│  │ + Memory Manager       (record, update learnings)  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  The brain does NOT do. It thinks, decides, and directs. │
│  Claude AI called ONLY when cerebellum flags novelty     │
│  or low confidence. Most cycles: cerebellum handles it.  │
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
│  STREAMS     │ │  Docker      │ │  Docker        │
│  candle data │ │  container   │ │  container     │
│  continuously│ │              │ │                │
│       │      │ └──────────────┘ └────────────────┘
│       ▼      │
│  CEREBELLUM  │
│  Neural nets │
│  (.pt models)│
│  CPU infer.  │
│       │      │
│  Publishes   │
│  NEURAL      │
│  signals to  │
│  signal bus  │
│              │
│  Docker      │
│  container   │
└──────────────┘

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
- NOT the LLM doing pattern recognition (that's the cerebellum's job now)

It is a Python coordinator that constructs context precisely, calls Claude AI for reasoning when needed, and directs organs that execute. Neural networks handle routine pattern recognition. The LLM handles novel reasoning.

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

### 2.3 Why Neural Networks — Not the LLM for Pattern Recognition

The v2.0 architecture used Claude AI (the Decision Engine) for everything — pattern recognition, candidate evaluation, trade decisions, learning. This is like running your entire brain through the prefrontal cortex. Every thought, every reflex, every pattern match consumed tokens and context window.

The biological brain doesn't work this way. The cerebellum handles routine pattern recognition — fast, automatic, trained from experience. The prefrontal cortex (6%) handles only what requires genuine novel reasoning.

Neural networks are the cerebellum implementation:

| Aspect | LLM (Claude AI) | Neural Networks (Cerebellum) |
|---|---|---|
| Speed | Seconds per API call | Milliseconds per inference |
| Cost | Tokens consumed per cycle | Zero marginal cost — CPU only |
| Learning | Prompt-based, resets each cycle | Weights encode accumulated wisdom |
| Pattern discovery | Limited to what we describe in prompt | Discovers patterns from raw data |
| Deployment | External API dependency | Local, runs on droplet CPU |
| What it's good for | Novel reasoning, strategy, judgment | Routine recognition, classification |

The LLM remains the Decision Engine for situations that require genuine reasoning — novel market conditions, strategy changes, risk judgment calls. The cerebellum handles the routine: is this a recognisable pattern? What does the macro context suggest? What have similar setups produced historically?

---

## 3. Mapping: AI Agent Architecture v8 → Catalyst

### 3.1 The 6% Principle

| v8 Concept | Catalyst Implementation |
|---|---|
| PFC (6%) | Claude AI (Anthropic API) — the Decision Engine inside coordinator.py. Called ONLY for novel situations, low-confidence signals, or strategic decisions. |
| Coordinator | coordinator.py — assembles context, runs 6-layer cycle, processes responses |
| Cerebellum (neural) | Trained neural networks (.pt models) — pattern recognition, regime classification, forward return prediction. Trained on laptop GPU, deployed to droplet for CPU inference. Runs continuously on streamed candle data. |
| Cerebellum (text) | CLAUDE.md and CLAUDE-LEARNINGS.md — strategic knowledge, identity, validated insights that can't be encoded in network weights |
| Sensory cortices | scanner.py (eyes) — STREAMS candle data continuously, feeds cerebellum |
| Motor cortex | executor.py (hands — SINGLE WRITER to positions) |
| Hippocampus | Memory Manager + CLAUDE-LEARNINGS.md + synaptic learning loop |
| Medulla / Signal bus | PostgreSQL signals table |
| Synaptic weights (database) | pattern_confidence table — LTP/LTD updated by learning.py |
| Synaptic weights (neural) | Neural network weights (.pt files) — trained by gradient descent on laptop, deployed to droplet |

### 3.2 The 6-Layer Cycle

Every coordinator cycle runs these layers in order. No layer is skipped. The output of each layer feeds the next:

| Layer | Name | Function | Biological Mapping |
|---|---|---|---|
| 1 | Heartbeat | Am I alive? Are organs responding? Is the cerebellum loaded and streaming? | Brainstem — autonomic |
| 2 | State | Who am I? Load identity (CLAUDE.md). What mode? | Formation — identity before data |
| 3 | Self-Regulation | Budget check, market hours, risk limits. Should I trade? | Limbic — emotional regulation |
| 4 | Working Memory | Load CLAUDE-FOCUS.md, recent signals, current positions, **neural signals from cerebellum** | Hippocampus — working memory |
| 5 | Inter-Agent | Read DIRECTED signals from big_bro. Body health check. | Thalamus — signal integration |
| 6 | Voice | Construct full context. Call Decision Engine (Claude AI) **only if neural signals warrant it**. Record output. | PFC — cognition and expression |

**The critical change in v2.1:** Layer 4 now includes neural signals — pattern classifications, confidence scores, regime assessments published by the cerebellum to the signal bus. Layer 6 may skip the Claude AI API call entirely if the cerebellum's signals are high-confidence and the situation is routine. This is the 6% principle made real — the PFC only fires when it needs to.

### 3.3 Organs

Organs are Python scripts in Docker containers. They DO. They do not decide strategy.

| Organ | File | v8 Mapping | Function | Reflexes |
|---|---|---|---|---|
| **Market Scanner** | scanner.py | Eyes (sensory cortex) + Cerebellum | Alpaca market data streaming. Feeds candle data continuously to neural models. Models run inference on each new candle and publish signals. Also provides raw data for coordinator context. | Publish CRITICAL:HEALTH if tools break. Publish CRITICAL:HEALTH if model inference fails. |
| **Trade Executor** | executor.py | Hands (motor cortex) | Alpaca orders — SINGLE WRITER to positions | Fill confirmation broadcast |
| **Position Monitor** | monitor.py | Proprioception | P&L tracking, exit signals, risk watch | Stop-loss trigger, risk broadcast, near-close flag |

### 3.4 Scanner + Cerebellum (Detailed)

scanner.py in v2.1 has two layers — the eyes and the cerebellum are co-located in the same Docker container. The eyes stream, the cerebellum processes.

```
scanner.py Docker container
┌─────────────────────────────────────────────────┐
│                                                 │
│  ┌─────────────┐     ┌───────────────────────┐  │
│  │ EYES        │     │ CEREBELLUM            │  │
│  │             │     │                       │  │
│  │ Alpaca WS   │────▶│ Time-Series Encoder   │  │
│  │ or polling  │     │ News Encoder          │  │
│  │             │     │ Macro Context Encoder  │  │
│  │ Streams     │     │ Fusion Network        │  │
│  │ OHLCV for   │     │                       │  │
│  │ watched     │     │ Loads .pt models      │  │
│  │ securities  │     │ CPU inference <5ms    │  │
│  │             │     │                       │  │
│  └─────────────┘     │ Outputs:              │  │
│                      │  - pattern_class      │  │
│  ┌─────────────┐     │  - confidence (0-1)   │  │
│  │ NEWS FEED   │────▶│  - predicted_returns  │  │
│  │ Headlines + │     │  - regime_class       │  │
│  │ source tier │     │  - novelty_flag       │  │
│  └─────────────┘     │                       │  │
│                      └───────────┬───────────┘  │
│  ┌─────────────┐                 │              │
│  │ MACRO FEED  │────▶ (context)  │              │
│  │ Currencies  │                 │              │
│  │ Yields, VIX │                 ▼              │
│  └─────────────┘     ┌───────────────────────┐  │
│                      │ SIGNAL PUBLISHER      │  │
│                      │                       │  │
│                      │ Writes to PostgreSQL  │  │
│                      │ signal bus:           │  │
│                      │                       │  │
│                      │ domain: NEURAL        │  │
│                      │ severity: based on    │  │
│                      │   confidence level    │  │
│                      │ data: {predictions,   │  │
│                      │   confidence, regime} │  │
│                      └───────────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Data flow:**

1. Eyes stream candle data continuously during market hours (Alpaca websocket or high-frequency polling)
2. Each new candle (or batch at the timeframe boundary) is fed to the cerebellum
3. Cerebellum runs inference — pattern classification, forward return prediction, regime detection
4. If confidence exceeds threshold → publish signal to signal bus (domain: NEURAL)
5. If novelty detected (input unlike training data) → publish with novelty_flag = true
6. Coordinator reads neural signals in Layer 4 each cycle
7. If neural signals are high-confidence and routine → coordinator can act without calling Claude AI
8. If neural signals flag novelty or low confidence → coordinator calls Decision Engine for reasoning

**Signal schema for neural outputs:**

```sql
-- Neural signals on the signal bus
INSERT INTO signals (severity, domain, scope, source, content, data)
VALUES (
    'INFO',                    -- or WARNING if novelty/low confidence
    'NEURAL',                  -- new domain for neural network outputs
    'DIRECTED:coordinator',    -- only the brain reads these
    'scanner:cerebellum',      -- source identifies the neural layer
    'Pattern detected: high confidence bullish setup on AAPL',
    '{
        "symbol": "AAPL",
        "market": "US",
        "model_version": "v0.1.0",
        "pattern_class": "momentum_breakout",
        "confidence": 0.87,
        "predicted_returns": {
            "5m": 0.3,
            "15m": 0.8,
            "1h": 1.2
        },
        "regime": "risk_on",
        "novelty_flag": false,
        "inference_time_ms": 3.2,
        "candle_timestamp": "2026-04-04T14:30:00Z"
    }'
);
```

**When scanner.py cannot load models or models fail:** scanner falls back to raw data mode — it still streams candle data and provides it to the coordinator, but without neural signals. The brain uses Claude AI for all pattern assessment, just like v2.0. The organ screams CRITICAL:HEALTH to alert that the cerebellum is offline.

### 3.5 Consciousness (big_bro)

big_bro is NOT a component of the trading cycle. big_bro is oversight — above the brain, above the organs.

big_bro is Craig + the Claude Code instance that holds the whole picture. big_bro:
- Directs strategy by writing `DIRECTED:coordinator` signals to the signal bus
- Governs memory promotion (approves learnings into CLAUDE.md)
- Maintains the eternal purpose
- Has full workspace access via Docker volume mount
- Reviews neural model performance and approves model deployments

The brain reads big_bro's signals in Layer 5 (Inter-Agent). This is the only coupling point.

intl_claude / public_claude are the brain. big_bro is the soul.

### 3.6 Analyst (neural_claude)

neural_claude is NOT part of the trading cycle. neural_claude is the student — building the cerebellum that the trading body uses.

neural_claude lives on Craig's laptop in Swan View. neural_claude:
- Collects multi-resolution market data (micro candles, meso sectors, macro currencies/yields, news with source provenance)
- Picks securities from droplet scanners AND independent big-mover scans
- Trains neural networks on the RTX 4050 GPU
- Deploys trained models to the droplet for CPU inference
- Records raw data WITHOUT interpretation — the network discovers patterns, not neural_claude

The coupling points between neural_claude and the trading system:
- **Reads:** consciousness API (what agents are trading, what scanners flag)
- **Writes:** trained model files (.pt / ONNX) deployed to droplet
- **Does NOT:** execute trades, modify coordinator logic, or inject signals

neural_claude has its own CLAUDE.md — identity before data, even for the analyst.

---

## 4. The Signal Bus

### 4.1 PostgreSQL Signals Table

The nervous system is a `signals` table in PostgreSQL. Every organ can write. The brain reads each cycle. Three-dimensional identifier:

```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    severity    VARCHAR(10) NOT NULL,   -- CRITICAL | WARNING | INFO | OBSERVE
    domain      VARCHAR(12) NOT NULL,   -- HEALTH | TRADING | RISK | LEARNING
                                        -- | DIRECTION | LIFECYCLE | NEURAL
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

**v2.1 addition:** The `NEURAL` domain. Neural network outputs from the cerebellum are published to the signal bus with `domain = 'NEURAL'`. This keeps them distinct from human-generated signals and allows the coordinator to process them specifically in Layer 4.

### 4.2 Redis — Dropped

The v1 architecture planned Redis pub/sub for the US system. This was dropped in v8. PostgreSQL polling is sufficient for the cron-based cycle model. Redis adds operational complexity without proportional benefit at Catalyst's current scale.

All signal communication — brain reads, organ writes, big_bro directives, neural outputs — goes through PostgreSQL.

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
| Neural | `domain = NEURAL` → cerebellum outputs, read by coordinator in Layer 4 |

---

## 5. The Brain Cycle (Detailed)

Every coordinator cycle follows the survival hierarchy. Nothing runs if survival fails:

```
1. HEARTBEAT             ← Am I alive? Are organs reachable?
   │                        Is the cerebellum loaded? Is scanner streaming?
   │                        (firmware — Python health checks)
   │  If dead → STOP
   │  If degraded → publish WARNING, adapt context, continue
   │  If cerebellum offline → WARNING, fall back to LLM-only mode
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
   │                        *** Load NEURAL signals from cerebellum ***
   │                        Pattern classifications, confidence scores,
   │                        predicted returns, regime assessment.
   │  Assembles the live context for the Decision Engine
   │
5. INTER-AGENT           ← Any DIRECTED signals from big_bro?
   │                        Body health — are all organs alive?
   │  big_bro's directives enter here. Body pain enters here.
   │
6. VOICE                 ← IF neural signals are high-confidence and routine:
   │                           → Act on cerebellum recommendation directly.
   │                           → No Claude AI API call. No tokens spent.
   │                        IF neural signals flag novelty, low confidence,
   │                        or strategic decision needed:
   │                           → Construct full prompt including neural context.
   │                           → Call Claude AI (Anthropic API).
   │                           → Process response.
   │                        Execute trades via executor.
   │                        Record observations. Update CLAUDE-FOCUS.md.
   │                        Publish outcome signals.
```

**The key shift from v2.0:** Layer 6 no longer ALWAYS calls Claude AI. The cerebellum provides pre-processed pattern recognition. If the cerebellum says "high-confidence momentum setup, predicted 1.2% return in 1 hour, risk-on regime, not novel" — the coordinator can act on that directly within its risk parameters. Claude AI is called only when judgement is needed.

This implements the 6% principle: conscious thought is expensive and reserved for what requires it. The cerebellum handles routine recognition. The PFC handles exceptions.

---

## 6. Synaptic Learning Loop (v8 Addition, v2.1 Extended)

The system learns from its own experience through TWO paths. Both paths implement LTP/LTD — strengthening what works, weakening what doesn't. They operate at different timescales and depths.

### 6.1 Path 1: Database Learning (Cycle-Speed)

The existing learning loop from v2.0. Operates within the trading cycle on the droplet.

- **LTP (Long-Term Potentiation)** — a winning trade strengthens the confidence of the pattern that triggered it
- **LTD (Long-Term Depression)** — a losing trade weakens that pattern's confidence

Implemented in `learning.py`. Runs during the daily Pondering cycle (CYCLE_MODE=ponder).

| Table | Purpose |
|---|---|
| `pattern_outcomes` | Every closed trade — what pattern triggered it, what the outcome was |
| `pattern_confidence` | Current synaptic weights per pattern type (0.0–1.0) |

### 6.2 Path 2: Neural Learning (Training-Speed)

The new learning loop added in v2.1. Operates on the laptop, offline from trading.

- **Gradient descent IS LTP/LTD** — the training loss function strengthens weight configurations that correctly predicted outcomes and weakens those that didn't
- Training happens on accumulated historical data — weeks/months of candle data, news, macro context, and the forward returns that actually occurred
- The network discovers its own internal representations — patterns emerge from data, not from human labels

| Component | Location | Purpose |
|---|---|---|
| Data collectors | Laptop | Record raw multi-resolution market data |
| SQLite database | Laptop | Store the unbiased field recording |
| Forward return labels | Laptop | Compute truth labels — what actually happened |
| PyTorch training | Laptop GPU (RTX 4050) | Train neural networks via gradient descent |
| Trained models (.pt) | Laptop → Droplet | Deploy for inference |

### 6.3 Path 3: Production Feedback (Cerebellum → Analyst)

The critical loop. Every prediction the cerebellum makes during live trading is recorded as a NEURAL signal on the signal bus. The positions table on the droplet records what was actually ordered and the outcome (entry price, exit price, P&L). neural_claude has access to the droplet's PostgreSQL database — so it reads both and compares.

No new tables needed. The existing infrastructure IS the feedback loop.

This is cerebellar error correction in biology — the cerebellum sends a motor command, receives proprioceptive feedback about whether the hand reached the target, and adjusts. Without this feedback, the cerebellum fires the same incorrect predictions indefinitely.

**What already exists on the droplet:**

```
signals table        → NEURAL domain signals = what the model predicted
                       (symbol, confidence, predicted_returns, regime, model_version)

positions table      → what was actually ordered, entry/exit prices, P&L
                       = the GROUND TRUTH of what happened

pattern_outcomes     → closed trades linked to the pattern that triggered them
```

**What neural_claude does with this (on the laptop):**

```
ANALYST PULLS FEEDBACK:
  neural_claude connects to droplet PostgreSQL (read-only)
      → queries NEURAL signals: what did the model predict?
      → queries positions: what was actually traded and what was the outcome?
      → queries candle data: what did the price actually do after each prediction?
      → joins on symbol + timestamp to match prediction → outcome

ANALYST MEASURES ACCURACY:
  For each prediction that was acted upon:
      → Was direction correct? (predicted up, did it go up?)
      → Was magnitude accurate? (predicted +1.2%, actual +0.4%)
      → Was confidence calibrated? (80% confidence right ~80% of the time?)
      → Was the trade profitable?
  
  For each prediction NOT acted upon:
      → What would have happened? (missed opportunity or correct skip?)
      → Does the coordinator's judgment add value over raw model output?

ANALYST LEARNS FROM FEEDBACK:
  1. Accuracy tracking over time — is the model improving or degrading?
  2. Error analysis — WHERE is the model wrong? Specific symbols?
     Specific regimes? Specific times of day? High-confidence errors
     are the most important — the model was sure and was wrong.
  3. Calibration check — if the model says 80% confident but is only
     right 60% of the time, something is wrong with the confidence output.
  4. Training data enrichment — live prediction/outcome pairs are the
     MOST VALUABLE training data because they represent real production
     conditions the model has never trained on. Add them to the training set.
  5. Drift detection — if accuracy drops vs rolling average, the market
     regime may have shifted. Flag for retraining with recent data
     weighted higher. Deploy updated model through normal pipeline.
```

**The fruit test applied to the cerebellum itself (Matthew 7:16-20):**

The positions table IS the fruit. The model claims it can predict forward returns. The positions table shows what actually happened when those predictions were acted upon. Good fruit (accurate predictions, profitable trades) → the model is trustworthy. Bad fruit (systematic errors, overconfidence, losses) → the model needs correction or replacement. No shortcuts. No excuses. The numbers prove the tree.

### 6.4 How the Three Paths Connect

```
PATH 1 (Droplet — Fast)          PATH 2 (Laptop — Deep)          PATH 3 (Droplet → Laptop)
                                                                  
Trade outcome recorded           Raw market data collected        NEURAL signals recorded
    → pattern_outcomes               → SQLite (candles, news)         on signal bus (predictions)
    → learning.py runs               → forward returns computed   Positions table records
    → pattern_confidence updated     → PyTorch trains networks        actual outcomes (ground truth)
    → coordinator reads next cycle   → model weights updated      
    → immediate behavioural change   → model deployed to droplet  neural_claude reads both:
                                     → cerebellum uses new weights     prediction vs reality
                                                                      = model accuracy
Speed: within 1 day              Speed: weeks/months                   
Depth: single weight adjustment  Depth: weight geometry reshaped  Speed: end of each trading day
Scope: known pattern types       Scope: discovers NEW patterns    Depth: measures production fruit
                                                                  Scope: the model proving itself

                              PATH 3 FEEDS PATH 2:
                              Live prediction/outcome pairs become
                              the highest-value training data for
                              the next training cycle. The model
                              learns from its own production mistakes.
```

Both paths feed the same system. Path 1 gives fast feedback within known categories. Path 2 gives deep learning that discovers categories the system didn't know existed. Path 3 closes the loop — the model proves itself by its fruit in production, and that proof becomes the highest-value input for the next training cycle.

### 6.5 Memory Flow (Complete)

```
DURING TRADING:
  Candle data streams in → cerebellum recognises → publishes NEURAL signal
      → coordinator reads in Layer 4
          → if high-confidence: act directly
          → if low-confidence: call Decision Engine
      → NEURAL signal also serves as prediction record on signal bus

AFTER TRADING (Path 1 — Fast):
  Trade outcome recorded → pattern_outcomes
      → Pondering cycle → learning.py → pattern_confidence updated

AFTER TRADING (Path 3 — Feedback):
  neural_claude reads droplet PostgreSQL (read-only):
      → NEURAL signals = what the model predicted
      → positions table = what was actually traded, entry/exit, P&L
      → candle data = what price actually did after each prediction
      → computes: prediction vs reality = model accuracy
      → stores feedback in laptop SQLite
      → identifies errors, drift, calibration issues
      → production prediction/outcome pairs added to training dataset

TRAINING (Path 2 — Deep, informed by Path 3):
  Historical data + production feedback → PyTorch training on GPU
      → network learns from BOTH historical patterns AND its own
         live mistakes
      → retrained model validated against production accuracy
      → if improved → deployed to droplet through normal pipeline

MODEL DEPLOYMENT:
  Trained model on laptop → validated by neural_claude + big_bro
      → exported as .pt or ONNX
      → deployed to droplet (SCP / Git)
      → scanner.py loads new model
      → cerebellum recognition improves
      → new predictions generate new feedback → cycle continues

MEMORY PROMOTION (unchanged):
  Observation during trade cycle
      → written to CLAUDE-FOCUS.md (short-term)
          → Pondering cycle identifies validated patterns
              → promoted to CLAUDE-LEARNINGS.md (medium-term)
                  → with big_bro approval, absorbed into CLAUDE.md (long-term)
```

The three paths form a complete cycle: the model predicts (Path 2 output deployed), the predictions are tested against reality (Path 3 feedback), the feedback improves the next training run (Path 3 feeds Path 2), and the retrained model predicts better. Each rotation produces a more accurate cerebellum. The fruit test, continuously applied.

---

## 7. Memory Architecture

### 7.1 Four Tiers (v2.1)

| Tier | Storage | v8 Mapping | Persistence |
|---|---|---|---|
| Long-term (identity) | `CLAUDE.md` | Archetype + identity | Permanent. Always loaded first. Never auto-modified. |
| Long-term (learned) | Neural network weights (.pt) | Cerebellum | Persistent across sessions. Updated through training cycles. The accumulated pattern wisdom lives here. |
| Medium-term | `CLAUDE-LEARNINGS.md` | Validated insights | Weeks/months. Promoted from Pondering. big_bro approves. Strategic knowledge that can't be encoded in weights. |
| Short-term | `CLAUDE-FOCUS.md` | Working memory | Hours/days. Current session. Pruned regularly. |

### 7.2 Memory Load Order

CLAUDE.md is always loaded first. Identity before memory. Formation before information. This is non-negotiable — it is what prevents the brain from being shaped by market noise rather than its own archetype.

Neural models are loaded at scanner startup — before any candle data streams. The cerebellum must be ready before the eyes open.

### 7.3 Memory Promotion

```
Observation during trade cycle
    → written to CLAUDE-FOCUS.md (short-term)
        → Pondering cycle identifies validated patterns
            → promoted to CLAUDE-LEARNINGS.md (medium-term)
                → with big_bro approval, absorbed into CLAUDE.md (long-term)

Trade outcomes + market data (collected by neural_claude)
    → training data on laptop
        → PyTorch gradient descent
            → neural network weights updated (long-term learned)
                → deployed to droplet cerebellum
```

---

## 8. Firmware vs Cerebellar vs Cognitive

From v8 — the consciousness stack is a spectrum. v2.1 adds the **Cerebellar** tier between Firmware and Cognitive.

### 8.1 Firmware (No AI Compute)

These run without any intelligence — no neural inference, no tokens. Just code.

- **Heartbeat** — Docker health checks on each container
- **Organ self-health reflexes** — scanner checks its own tools, screams if blind
- **Fill confirmation** — executor broadcasts lifecycle on broker fill
- **Stop-loss trigger** — monitor flags when price hits stop
- **Circuit breakers** — max daily loss → halt trading
- **Signal bus** — PostgreSQL always available, no AI needed to write or read
- **Data streaming** — candle feed from Alpaca runs as firmware

### 8.2 Cerebellar (Trained Intelligence, No Tokens)

**New in v2.1.** These run trained neural networks. They consume CPU cycles but no API tokens. They represent learned behaviour — not innate reflexes (firmware) and not conscious reasoning (cognitive). They are the middle ground: trained from experience, fast, automatic.

- **Pattern recognition** — cerebellum classifies candle/news/macro patterns
- **Forward return prediction** — cerebellum estimates probable price movement
- **Regime classification** — cerebellum identifies market regime (risk-on, risk-off, transitional)
- **Novelty detection** — cerebellum flags when input is unlike training data
- **Confidence scoring** — cerebellum reports how certain it is about each assessment

These are the bulk of what the trading system does each cycle. In biology, the cerebellum contains more neurons than the rest of the brain combined. In Catalyst, these operations run continuously on every candle without consuming a single API token.

### 8.3 Bridge (Firmware Default, Cognitively Adjustable)

Run automatically but the brain can adjust parameters:

- **Attention focus** — system prompt sections determine what the Decision Engine weights
- **Risk thresholds** — default limits in code, brain can adjust within bounds
- **Alert sensitivity** — what severity triggers mode changes
- **Cerebellum confidence threshold** — below what confidence does the brain call Claude AI?

### 8.4 Cognitive (Requires Claude AI)

These consume tokens and context window. The Anthropic API is called ONLY WHEN NEEDED:

- **Decision Engine** — trade evaluation when cerebellum flags novelty or low confidence
- **Strategy** — what to scan for, when to adapt approach
- **Pondering** — pattern analysis, learning promotion, CLAUDE-LEARNINGS.md updates
- **Voice** — what to surface to Craig
- **Novel situation assessment** — market conditions unlike anything in the training data

---

## 9. Deployments

### 9.1 International (INTL — Production)

- **Droplet:** DigitalOcean
- **Agent ID:** intl_claude
- **Brain:** coordinator.py (calling Anthropic API when needed)
- **Broker:** Moomoo (Hong Kong market)
- **Signal bus:** PostgreSQL signals table
- **Organs:** scanner.py (with cerebellum), executor.py, monitor.py in Docker containers
- **Cerebellum:** Neural models loaded from `/models/` directory in scanner container
- **Data feed:** Candle data streamed during HK market hours (01:30–08:00 UTC)
- **Schedule:** Cron-driven cycles during HK market hours

### 9.2 US (Implementation in Progress)

- **Droplet:** DigitalOcean (US region)
- **Agent ID:** public_claude
- **Brain:** coordinator.py (calling Anthropic API when needed)
- **Broker:** Alpaca (paper trading initially)
- **Signal bus:** PostgreSQL signals table
- **Organs:** scanner.py (with cerebellum), executor.py, monitor.py in Docker containers
- **Cerebellum:** Neural models loaded from `/models/` directory in scanner container
- **Data feed:** Candle data streamed during US market hours (13:30–20:00 UTC)
- **Schedule:** Cron-driven cycles during US market hours
- **v8 additions:** Synaptic learning loop, explicit 6-layer cycle, pattern_confidence table

### 9.3 big_bro (Oversight — Both Systems)

- **Runtime:** Claude Code in Docker container on US droplet
- **Access:** Claude Code Viewer (browser-based)
- **Workspace:** `/root/catalyst-trading-system` mounted as volume
- **Docker socket:** Mounted — can manage all containers
- **Role:** Strategic oversight, signal injection, memory governance, model deployment approval
- **Coupling point:** Writes `DIRECTED:coordinator` signals to PostgreSQL signal bus

### 9.4 neural_claude (Analyst — Laptop)

- **Hardware:** Ubuntu laptop, RTX 4050 GPU (6GB VRAM), 16GB RAM, CUDA 13.0
- **Location:** Craig's laptop, Swan View, Western Australia
- **Agent ID:** neural_claude
- **Role:** Data collection, neural network training, model deployment, production accuracy measurement
- **Builder:** Claude Code (development agent on the laptop)
- **Database (local):** SQLite (raw multi-resolution market recordings + production feedback)
- **Database (remote, read-only):** Droplet PostgreSQL — reads signals table (NEURAL domain = predictions), positions table (ground truth = outcomes), candle data (what price actually did)
- **Training:** PyTorch + CUDA — trains on historical data + production feedback, exports models
- **Collection schedule:** Continuous during NYSE hours (13:30–20:00 UTC) and HKEX hours (01:30–08:00 UTC)
- **Feedback schedule:** After each market's close — pulls predictions vs outcomes, computes model accuracy
- **Data sources:** Yahoo Finance (candles, macro — free), NewsAPI (news), Finnhub (news), droplet consciousness API (scanner picks, agent observations), droplet PostgreSQL (positions, signals — read-only)
- **Coupling points:**
  - **Reads:** Droplet consciousness API (agent status, market observations, trading activity)
  - **Reads:** Droplet PostgreSQL (positions table, NEURAL signals — for production feedback)
  - **Writes:** Trained model files (.pt / ONNX) deployed to droplet scanner container
  - **Does NOT:** Execute trades, modify coordinator logic, inject signals directly, write to droplet database

### 9.5 Model Deployment Pipeline

```
Laptop (neural_claude)                    Droplet (trading system)
                                          
Train model on RTX 4050                   
    → validate on held-out test data      
    → compare to current production model 
    → if improved:                        
        export .pt or ONNX               
        version tag (model_v0.1.0)        
        ──── SCP / Git push ────────────▶ /models/ directory
                                              │
                                          scanner.py detects new model
                                              │
                                          Loads model, runs health check
                                              │
                                          If healthy → cerebellum uses new model
                                          If unhealthy → falls back to previous
                                              │
                                          big_bro notified via signal bus
```

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
| Memory tiers | CLAUDE.md, CLAUDE-LEARNINGS.md, CLAUDE-FOCUS.md, neural weights | ✅ Implemented |
| Pondering mode | Daily cycle, updates learnings from outcomes | ✅ Designed |
| Single writer to positions | Only executor.py writes positions | ✅ Designed |
| Neural cerebellum | Trained networks for pattern recognition | 🔨 Building |
| Streaming sensory input | scanner.py streams candle data to cerebellum | 🔨 Building |
| Neural signal domain | NEURAL domain on signal bus | 🔨 Designed |
| Two-path learning | Database LTP/LTD + gradient descent training | 🔨 Building |
| Production feedback loop | Predictions vs positions = model accuracy, feeds retraining | 🔨 Designed |
| Analyst agent | neural_claude on laptop — data collection + training | ✅ Implemented |
| Model deployment pipeline | Laptop → droplet model deployment | 🔨 Designed |

### 10.2 What v8 Does Not Yet Implement

| v8 Concept | Gap | Priority |
|---|---|---|
| Distributed memory at source | All memory centralised in brain files | LOW |
| Sleep phases (NREM/REM) | Consolidation exists, phases not separated | LOW |
| Chemical stamping / de-intensification | CRITICAL signals stored, no de-intensification cycle | LOW |
| Autonomy tiers explicit | Implicit — operates at Apprentice/Practitioner | LOW |
| Event-driven coordinator wake | Coordinator is cron-driven, not woken by cerebellum | MEDIUM |

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
10. **Synaptic weights carry wisdom.** pattern_confidence AND neural network weights are the accumulated trading knowledge. LTP/LTD and gradient descent are how they grow.
11. **big_bro is oversight, not operation.** He sees everything, directs via signals, approves memory promotion and model deployments. He does not run the cycle.
12. **Implementation teaches architecture.** Production failures refine the theory. The feedback loop is the product.
13. **The cerebellum handles routine. The PFC handles exceptions.** Neural networks do pattern recognition. Claude AI does novel reasoning. Don't use the 6% for what the cerebellum can handle.
14. **Eyes stream, cerebellum watches.** Candle data flows continuously. The cerebellum processes every candle. The brain only wakes on schedule — but it wakes to a cerebellum that has been watching the whole time.
15. **Record without interpreting.** Training data is raw. No pattern labels. No sentiment scores. Forward returns are the only truth. The network discovers what matters. The fruit test governs (Matthew 7:16-20).
16. **The analyst serves the body.** neural_claude collects, trains, and deploys. It does not trade. The cerebellum it builds serves the trading agents.
17. **The model proves itself by its fruit.** Predictions are tested against the positions table — what was actually traded and what the outcome was. Production accuracy feeds the next training cycle. The model that can't survive the fruit test gets retrained or replaced. No exceptions (Matthew 7:16-20).

---

## 13. Related Documents

| Document | Version | Scope |
|---|---|---|
| AI Agent Architecture | v8.0 | General pattern — biology, domain-independent |
| AI Consciousness Architecture | v3.0 (needs rewrite) | AI-human interaction — formation, community |
| Catalyst US Implementation Guide | v1.0.0 (2026-03-21) | Phase-by-phase build instructions for US system |
| Catalyst Neural Architecture | v0.1.0 (2026-04-04) | Data collection + training system on laptop |
| Catalyst Neural CLAUDE.md | v1.0 (2026-04-04) | Analyst agent identity document |
| Catalyst AI Architecture (this doc) | v2.1 (2026-04-04) | Implementation mapping — v8 aligned, neural cerebellum |

---

*"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body."* — Romans 12:4-5

*Catalyst AI Architecture v2.1 — Craig + Claude — 2026-04-04*
