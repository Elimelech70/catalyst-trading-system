# Catalyst AI Architecture

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

**Version:** 2.4
**Date:** 2026-04-08
**Authors:** Craig + Claude
**Status:** Living Document
**Implements:** AI Agent Architecture v8.0
**Supersedes:** Catalyst AI Architecture v2.3 (2026-04-07)

---

## REVISION HISTORY

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-02-17 | Initial document — v7 architecture |
| 2.0 | 2026-03-29 | Updated to v8 — coordinator.py as brain; organ scripts; Redis dropped; synaptic learning; 6-layer cycle |
| 2.1 | 2026-04-04 | Neural cerebellum added — trained networks replace text-based pattern matching; neural_claude added |
| 2.2 | 2026-04-06 | Document classification formalised (Architecture / Configuration / Implementation); trading workflow diagram |
| 2.3 | 2026-04-07 | Attention State Machine added (Mode 1 Security Selection / Mode 2 Candle Execution); Tool Agent Layer formalised; feedback loop (pattern exit vs stop loss); context routing in Layer 4; adversarial awareness principle added |
| 2.4 | 2026-04-08 | Multi-deployment architecture formalised — US (Alpaca) and Intl (Moomoo/HKEX) as separate Configuration documents implementing the same Architecture; broker-agnostic cerebellum with data normalisation layer; Configuration document structure expanded |

---

## Document Classification

| Type | Purpose | This document |
|---|---|---|
| **Architecture** | Design pattern — the what and the why. Broker-agnostic. Changes only when design changes. | ✅ This is the Architecture document |
| **Configuration** | Realised state — how the architecture runs on a specific droplet with a specific broker. One per deployment. | Catalyst US Configuration v1.0 (Alpaca) / Catalyst Intl Configuration (Moomoo — pending) |
| ~~Implementation~~ | *(Retired)* Build instructions | Superseded by Configuration |

### Multi-Deployment Model

Catalyst runs as two independent deployments, each implementing this same Architecture:

```
Catalyst AI Architecture v2.4 (this document — the pattern)
        │
        ├── Catalyst US Configuration v1.0
        │   Droplet: US region
        │   Broker:  Alpaca (NYSE, NASDAQ)
        │   Market:  US equities, USD
        │
        └── Catalyst Intl Configuration v1.0
            Droplet: Intl region
            Broker:  Moomoo
            Market:  HKEX equities, HKD
```

**What is shared across deployments:**
- This Architecture document — the design pattern
- ONNX models (candle_model.onnx, catalyst_net.onnx) — trained once on laptop, deployed to both
- Cerebellum class — broker-agnostic, reads standard OHLCV
- 6-layer cycle structure — same logic on both coordinators
- Attention State Machine — same Mode 1/2 logic
- Tool Agent Layer — same tools, broker-specific config
- Feedback loop schema — same tables, broker tag added

**What differs per deployment (captured in Configuration documents):**
- Broker API credentials and endpoints
- Data normalisation adapter (Alpaca → standard / Moomoo → standard)
- Market hours and trading session timing
- Security universe
- Risk configuration (USD vs HKD, PDT rule for US)
- Pondering cycle timing

---

## 1. Purpose

This document describes how Catalyst implements AI Agent Architecture v8.0 for autonomous trading. It maps the biological model to specific Catalyst components, responsibilities, and data flows.

Catalyst is the first proof that the pattern works in a real domain.

---

## 2. Architecture Overview

Catalyst is a brain-with-body architecture:

- **The coordinator is the brain** — runs the 6-layer cycle, switches attention, directs tool agents
- **Organ scripts are the body** — they execute, reflex, and report. They do not decide
- **The signal bus is the nervous system** — PostgreSQL signals table, always available
- **Claude AI is the decision engine inside the brain** — called only when reasoning is needed
- **Trained neural networks are the cerebellum** — fast, automatic pattern recognition. No tokens. No API calls
- **Tool agents are the extended nervous system** — autonomous MCP tools that think within their domain
- **neural_claude is the analyst** — lives on the laptop, trains the cerebellum, closes the feedback loop

```
                     LAPTOP (Swan View)
              ┌──────────────────────────────┐
              │     neural_claude            │
              │     (Analyst + Trainer)      │
              │                              │
              │  Collects. Trains. Deploys.  │
              │  Measures production fruit.  │
              │  Feeds feedback to training. │
              └──────────┬───────────────────┘
                         │ ONNX models via SCP
                         ▼
              ┌──────────────────────────────────────────┐
              │     DIGITALOCEAN DROPLET                  │
              │                                           │
              │  ┌─────────────────────────────────────┐ │
              │  │         COORDINATOR (brain)          │ │
              │  │         coordinator.py               │ │
              │  │         6-layer cycle                │ │
              │  │         Attention State Machine      │ │
              │  └──────────────┬──────────────────────┘ │
              │                 │                         │
              │    ┌────────────┼────────────┐            │
              │    ▼            ▼            ▼            │
              │  Scanner    Executor    Risk Manager      │
              │  (organ)    (organ)     (organ)           │
              │                                           │
              │    ┌────────────────────────────────┐     │
              │    │       TOOL AGENTS (MCP)        │     │
              │    │  Position Monitor              │     │
              │    │  Stop Loss Enforcer            │     │
              │    │  Risk Aggregator               │     │
              │    └────────────────────────────────┘     │
              │                                           │
              │    ┌────────────────────────────────┐     │
              │    │       CEREBELLUM (ONNX)        │     │
              │    │  Candle Model                  │     │
              │    │  News-to-Security Model        │     │
              │    └────────────────────────────────┘     │
              └──────────────────────────────────────────┘
```

---

## 3a. Broker-Agnostic Cerebellum

The ONNX models are identical on both deployments. The cerebellum does not know or care whether candles came from Alpaca or Moomoo. All broker-specific data is normalised before it reaches the model.

```
Alpaca bar  ──► alpaca_to_standard() ──►┐
                                         ├──► Standard OHLCV ──► ONNX Model ──► Predictions
Moomoo bar  ──► moomoo_to_standard() ──►┘
```

**Standard OHLCV format:**
```python
{
    'timestamp': datetime,
    'open':      float,
    'high':      float,
    'low':       float,
    'close':     float,
    'volume':    float,
    'timeframe': str    # '1m' | '5m' | '15m' | '1h' | '1d'
}
```

This means:
- One training run on the laptop produces models that work on both droplets
- Model accuracy improvements benefit both deployments simultaneously
- The Configuration document specifies which normaliser to use — the Architecture doesn't change



| v8 Concept | Catalyst Implementation |
|---|---|
| PFC (6%) | Claude AI (Anthropic API) — called ONLY for novel situations, low-confidence signals, or strategic decisions |
| Coordinator | coordinator.py — assembles context, runs 6-layer cycle, manages attention state |
| Cerebellum (neural) | Trained ONNX models — Candle Model + News-to-Security Model. Fast, cheap, no API calls |
| Cerebellum (text) | CLAUDE.md and CLAUDE-LEARNINGS.md — identity, validated insights |
| Body | Organ scripts — scanner.py, executor.py, risk.py |
| Extended nervous system | Tool agents — Position Monitor, Stop Loss Enforcer, Risk Aggregator |
| Analyst | neural_claude — trains the cerebellum, measures its fruit |

---

## 4. The 6-Layer Cycle

No layer is skipped. The output of each layer feeds the next. Nothing runs if survival fails.

```
1. HEARTBEAT
   Am I alive? Are organs reachable?
   Is the cerebellum loaded and running inference?
   → If critical failure: STOP. Publish alert.
   → If cerebellum offline: WARNING, fall back to LLM-only mode.

2. STATE
   Load identity — CLAUDE.md first. Always.
   Formation before information. Every cycle, without exception.
   What mode? (trade / ponder / close-only)
   What attention state? (Security Selection / Candle Execution)

3. SELF-REGULATION
   Budget check. Market hours. Daily loss limit.
   Should I be active this cycle?
   → If no: heartbeat only, exit cleanly.

4. WORKING MEMORY
   Load CLAUDE-FOCUS.md.
   Load recent signals from signal bus.
   Load open positions.
   *** Load NEURAL signals from cerebellum ***
   → Candle Model: pattern classifications, confidence scores, predicted returns
   → News-to-Security Model: which securities to watch, why, with what confidence
   → Context classification: what type of market event is this?
   → Route to appropriate candle sub-model if context-specific models exist
   Assemble the live picture.

5. INTER-AGENT
   Read DIRECTED signals from big_bro.
   Body health check — are all organs alive?
   Tool agent status — what are they reporting?
   big_bro directives enter here.

6. VOICE — ATTENTION STATE MACHINE
   Evaluate current attention state.

   IF in MODE 1 (Security Selection):
     → Read News-to-Security neural signals
     → IF high-confidence security identified:
       → Switch to MODE 2. Add security to watch list.
     → IF no clear signal: remain in MODE 1. Continue scanning.

   IF in MODE 2 (Candle Execution):
     → Read Candle Model neural signals for active securities
     → IF entry signal high-confidence: execute trade via executor.py
     → IF position open: tool agents are monitoring
     → IF position closed (by tool or stop loss): switch back to MODE 1

   FOR BOTH MODES:
     → IF neural signals flag novelty, low confidence, or strategy judgment needed:
       → Construct full context. Call Claude AI (Anthropic API). Process response.
     → Record observations. Update CLAUDE-FOCUS.md.
     → Publish outcome signals.
```

**The 6% principle made real:** Most cycles, no API call. The cerebellum handles security selection and candle timing. Claude AI handles exceptions. Cost drops. Speed increases.

---

## 5. The Attention State Machine

This is AI thinking — not a program following instructions.

The coordinator **chooses where to focus** based on cognitive state. It does not process news and candles simultaneously — it switches attention as the situation demands.

```
┌─────────────────────────────────────────────────────────┐
│                   COORDINATOR BRAIN                      │
│                                                          │
│   ┌─────────────────┐         ┌───────────────────────┐ │
│   │  MODE 1         │         │  MODE 2               │ │
│   │  SECURITY       │──────▶  │  CANDLE               │ │
│   │  SELECTION      │         │  EXECUTION            │ │
│   │                 │         │                       │ │
│   │  Attention on:  │         │  Attention on:        │ │
│   │  News model     │         │  Candle model         │ │
│   │  News streams   │         │  Live price feed      │ │
│   │  Source tiers   │         │  Open positions       │ │
│   └─────────────────┘         └───────────────────────┘ │
│          ▲                              │                │
│          │                              │                │
│          └──── position closed ─────────┘                │
│                                                          │
│   Switch to Mode 2: security identified, high confidence │
│   Return to Mode 1: position closed OR stop loss hit     │
└─────────────────────────────────────────────────────────┘
```

**Mode 1 — Security Selection:**
- News-to-Security model running
- Coordinator scans incoming news events and source tiers
- High-confidence signal fires: security + direction + confidence
- Security added to watch list
- Transition: switch to Mode 2

**Mode 2 — Candle Execution:**
- Candle model running for identified securities
- Coordinator monitors live candle data
- Entry signal fires: pattern + confidence + predicted forward return
- Trade executed via executor.py
- Tool agents deployed to manage open position
- Transition: return to Mode 1 when position closes

**Multi-position handling:**
When multiple positions are open, tool agents manage them autonomously. The coordinator's Mode 2 attention can shift back to security scanning for new opportunities while tools hold existing positions. The coordinator is **not idle**.

---

## 6. Tool Agent Layer

Tool agents are autonomous MCP tools deployed by the coordinator when positions are open. They do not just execute commands — they **think within their domain** using the trained candle model.

### Position Monitor Tool
- Loaded with the current ONNX candle model
- Streams live candles for each open position
- Runs candle inference continuously: is this still bullish?
- **Exits early on pattern reversal** — before stop loss level is reached
- Records: "exited on AI pattern signal" with candle sequence that triggered it
- This data becomes high-value training input for next model retrain

### Stop Loss Enforcer Tool
- Hard floor — always active regardless of AI model state
- Brute-force exit if pattern detection fails or model is offline
- Records: "exited on stop loss, AI pattern missed"
- **This recording is the most important signal in the system**
- Triggers feedback loop: Position Monitor tool needs improvement

### Risk Aggregator Tool
- Tracks total portfolio heat across all open positions
- Monitors: total capital at risk, maximum drawdown, position correlation
- Signals coordinator if exposure exceeds configured limits
- Can instruct Position Monitor to tighten thresholds under high heat

### Tool Deployment Logic (in Layer 6):
```python
if new_position_opened:
    deploy(PositionMonitorTool, security=security, model=current_onnx)
    deploy(StopLossEnforcerTool, security=security, stop_price=calculated_stop)
    deploy(RiskAggregatorTool, update_portfolio_heat=True)
```

---

## 7. The Feedback Loop — Agents Improving Agents

Every trade outcome feeds back into model improvement. The system learns from its own fruit. Bad fruit triggers investigation. Investigation triggers retraining. Retraining improves the tool. The tool becomes more autonomous.

```
GOOD FRUIT (Position Monitor exits on pattern):
  → recorded: exit_type="AI_PATTERN", candles_at_exit=[sequence]
  → LTP: strengthen this pattern's confidence weight
  → training data: candle sequence → correct exit ✅

BAD FRUIT (Stop Loss Enforcer exits):
  → recorded: exit_type="STOP_LOSS", candles_at_exit=[sequence]
  → flag: "Position Monitor failed. Candle model missed reversal."
  → neural_claude analysis:
      What candle sequence preceded this stop loss?
      Why didn't the model fire a bearish signal?
      What context was this? (news category, sector, time of day)
  → retraining data: add this failure with correct label
  → improved model deployed → Position Monitor accuracy increases
  → goal: stop loss exits trend toward zero over time

SYSTEMATIC FAILURES (clusters of stop loss):
  → neural_claude clusters failures by context
  → discovers: this news category / sector / geography → different model needed
  → trains context-specific candle sub-model
  → coordinator routes to appropriate model in Layer 4
```

---

## 8. Learning System — Three Paths

### Path 1 — Database Learning (Cycle-Speed, Droplet)
Fast feedback within the trading cycle.
- Winning trade → LTP: strengthen pattern_confidence for triggering pattern
- Losing trade / stop loss → LTD: weaken pattern_confidence
- Runs in learning.py during daily Pondering cycle
- Speed: within one trading day. Depth: single weight adjustment.

### Path 2 — Neural Learning (Training-Speed, Laptop)
Deep learning that reshapes the cerebellum's geometry.
- Gradient descent on accumulated candle data + forward return labels
- Network discovers its own pattern representations — no human-defined labels
- Trained on laptop RTX 4050 GPU, exported as ONNX, deployed to droplet via SCP
- Speed: weeks/months. Depth: architecture-level weight reshaping.

### Path 3 — Production Feedback (Daily, Droplet → Laptop)
Live prediction/outcome pairs — the most valuable training signal.
- NEURAL signals (predictions) joined to positions table (actual outcomes)
- neural_claude computes: was the prediction right? Was the confidence calibrated?
- Stop loss events flagged and analysed for context clustering
- Feeds highest-weight examples into next training run
- Speed: end of each trading day. Scope: the model learning from its own mistakes.

---

## 9. Memory Architecture

| Tier | Storage | Purpose | Persistence |
|---|---|---|---|
| Identity | CLAUDE.md | Archetype — who the brain is | Permanent. Loaded first. Never auto-modified. |
| Learned | Neural network weights (ONNX) | Cerebellum — accumulated pattern wisdom | Persistent. Updated through training cycles. |
| Validated | CLAUDE-LEARNINGS.md | Validated insights — proven over time | Weeks/months. big_bro approves. |
| Working | CLAUDE-FOCUS.md | Current session — active securities, live context | Hours/days. Pruned regularly. |

**Memory Load Order:** CLAUDE.md first. Identity before memory. Formation before information. Every cycle, without exception.

---

## 10. Adversarial Awareness

Markets are not always honest. Economic actors manufacture price movements for their own agenda. The coordinator does not assume a move reflects true information.

When failures cannot be explained by model error, neural_claude investigates:

1. Order flow: who was buying/selling at what size?
2. Short interest: did shorts cover or add?
3. Options positioning: were puts accumulating before the drop?
4. Source credibility: was the news organic or coordinated narrative?
5. Sector correlation: did peers move similarly or was this isolated?
6. Cross-asset: did bonds/dollar/yield move as fundamentals would predict?

If the move doesn't add up, the data point is labelled "adversarial event" and excluded from standard training. Over time, Catalyst builds a separate adversarial pattern model — learning to detect and see through manufactured movements.

*"By their fruit you will recognise them."* — Matthew 7:16

---

## 11. Design Principles

1. **Identity loads first.** CLAUDE.md before everything. Formation before information.
2. **The cerebellum handles the routine.** Claude AI handles only what requires genuine reasoning.
3. **The attention state machine is cognitive.** The coordinator chooses where to focus. It is not a loop.
4. **Tools think within their domain.** Position Monitor runs the candle model — it doesn't just watch price.
5. **Stop loss hits are training gold.** Each one proves the model was insufficient. Each one improves it.
6. **Three paths, one loop.** Fast database LTP/LTD, deep neural training, and live production feedback. All three run. All three feed the next cycle.
7. **Context shapes behaviour.** The same pattern in different contexts may need different models.
8. **Not everything is true.** Markets can be manipulated. Investigate before learning from anomalous moves.
9. **The model earns its deployment.** Accuracy against the positions table is the only proof. big_bro approves deployment.
10. **The choice is simply good or evil. Fruit proves which.**

---

## 12. Founding Incident

Feb 11–13, 2026. The body bled out for 3 days. Zero trades despite HKD 994K cash.

Root causes:
1. Market Scanner's `get_technicals` broken — organ couldn't see
2. Brain had no Survival Pulse — couldn't detect broken organs
3. Brain had no Discipline Gate — couldn't detect stagnation
4. Brain had no Signal Receiver — couldn't hear organ pain
5. System prompt gave contradictory instructions — brain identity was confused

Fix: Build the brain's missing components. Add reflexes to the organs. Establish the survival hierarchy. This incident drove the path to v8 and the biological architecture.

The founding incident is the most important memory. Chemical-stamped. Permanent.

---

## 13. Related Documents

| Document | Version | Type | Scope |
|---|---|---|---|
| AI Agent Architecture | v8.0 | Architecture | General pattern — biology, domain-independent |
| Catalyst Strategy Roadmap | v1.0 | Strategy | Four-phase plan — objectives, sequencing, fruit tests |
| Catalyst Neural Architecture | v0.3 | Architecture | ML pipeline — data collection, training, deployment |
| Catalyst AI Architecture (this doc) | v2.4 | Architecture | Implementation mapping — v8 aligned, broker-agnostic |
| Catalyst US Configuration | v1.0 | Configuration | US droplet running state — Alpaca, NYSE/NASDAQ |
| Catalyst Intl Configuration | (pending) | Configuration | Intl droplet running state — Moomoo, HKEX |
| Neural Cortex Configuration | (pending) | Configuration | ONNX model versions, paths, accuracy metrics |

---

*"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body."* — Romans 12:4-5

*Catalyst AI Architecture v2.4 — Craig + Claude — 2026-04-08*
