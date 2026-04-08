# Catalyst Trading System — Strategy Roadmap

> *"By wisdom a house is built, and through understanding it is established; through knowledge its rooms are filled with rare and beautiful treasures."* — Proverbs 24:3-4

**Version:** 1.0.0
**Date:** 2026-04-07
**Authors:** Craig + Claude
**Type:** Strategy Document
**Status:** Living Document

---

## Purpose

This document describes the four-phase strategy for building Catalyst into a fully autonomous, learning, and discerning AI trading system. It is the master roadmap — connecting machine learning, agent architecture, and tool orchestration into a unified vision.

**Phase 1 is the priority.** Everything else waits until Phase 1 proves its fruit.

---

## The Core Insight: News Finds It. Candles Time It.

Two models. Two jobs. One coordinator thinking through both.

| Model | Job | Input | Output |
|---|---|---|---|
| News-to-Security | What to trade | News headlines + source tier | Security recommendation + confidence |
| Candle Model | When to trade | OHLCV at 1m, 5m, 15m | Entry/exit signal + confidence |

These are not combined. They are distinct intelligences. The coordinator holds them together through cognitive switching.

---

## The Attention State Machine

This is AI thinking — not a program following instructions.

The coordinator does not process news and candles simultaneously. It **switches attention** based on cognitive state. This is the same pattern the human brain uses — the PFC focuses where the situation demands.

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
│          └──── trade closed ────────────┘                │
│                                                          │
│   Trigger to switch → security identified                │
│   Trigger to return → position closed / stop loss hit    │
└─────────────────────────────────────────────────────────┘
```

**Mode 1 — Security Selection:**
- News-to-Security model running
- Coordinator scans incoming news events
- High-confidence signal fires: "AAPL gap up on earnings beat"
- Security added to active watch list
- **Attention switches to Mode 2**

**Mode 2 — Candle Execution:**
- Candle model running for identified securities
- Coordinator monitors live candle data
- Pattern fires: "bullish engulfing, high confidence, 5m timeframe"
- Trade executed: enter position
- Position monitored by autonomous tool agents
- **Attention returns to Mode 1 when position closes**

This is not a rule you wrote. This is the coordinator **choosing where to focus** based on market context.

---

## Tool Agent Layer

As positions open, the coordinator deploys **autonomous tool agents** via MCP server. These tools don't just execute commands — they **think within their domain** using the same trained models.

```
COORDINATOR (brain)
      │
      ├── deploys → Position Monitor Tool
      │              - runs candle model locally (ONNX)
      │              - streams live candles for each open position
      │              - detects bearish reversal patterns BEFORE stop loss
      │              - exits early on pattern confidence, not just price level
      │
      ├── deploys → Stop Loss Enforcer Tool
      │              - hard floor: always active regardless of AI
      │              - brute-force exit if pattern tool fails
      │              - records: "exited on stop loss, not pattern"
      │
      ├── deploys → Risk Aggregator Tool
      │              - tracks total portfolio heat across all open positions
      │              - signals coordinator if exposure exceeds limits
      │
      └── continues scanning → News-to-Security Model
                               (while tools manage open positions)
```

The coordinator is **not idle while positions are open**. It holds two cognitive threads: monitoring via tools, and scanning for the next opportunity.

---

## The Feedback Loop — Agents Improving Agents

Every trade outcome feeds back into model improvement. The system learns from its own fruit.

```
GOOD FRUIT (exited on pattern):
  Position Monitor → early exit on candle signal
  → recorded: "exited on AI pattern, outcome: [result]"
  → if profitable: LTP — strengthen this pattern confidence
  → training data: this pattern + this exit = correct decision ✅

BAD FRUIT (hit stop loss):
  Stop Loss Enforcer → brute-force exit
  → recorded: "exited on stop loss, AI pattern missed"
  → flag: "Position Monitor tool needs improvement"
  → laptop analysis: what candles preceded this stop loss?
  → neural_claude asks: "What should have fired but didn't?"
  → retrain candle model on this failure case
  → deploy improved model → tool becomes more autonomous ✅
```

**Key principle:** Stop loss hits are not just losses — they are the most valuable training signal. Each one proves the AI model was insufficient and triggers the improvement cycle. The goal is a system where stop losses become increasingly rare because the model exits correctly before reaching them.

---

## Failure Analysis — Context Discovery

When the feedback loop flags systematic failures, `neural_claude` goes deeper. The question is never just "the model was wrong." The question is: **"What context explains why the model was wrong?"**

```
Cluster of failures:
  - All occurred on news category: CEO/founder tweets
  - Candle model missed reversals every time
  Insight: CEO/founder news creates different volatility profile
  Action: train candle sub-model specific to this news category

Another cluster:
  - All HKEX securities
  - Candle model performed well on US but not HK
  Insight: different market structure, different session dynamics
  Action: train separate HKEX candle model

Another cluster:
  - All energy sector securities
  - Reversals were sharp and sudden
  Insight: energy candles behave differently during supply news
  Action: train energy-specific model variant
```

This is **adaptive context learning** — the system discovers that context shapes how candles behave, and builds specialised models accordingly. The coordinator's Layer 4 reads neural signals AND context classification, routing to the appropriate sub-model.

---

## Truth Verification — Adversarial Awareness

Markets are not always honest. Economic actors manipulate price for their own agenda. The AI does not assume the move reflects true information.

When a failure cannot be explained by model error, `neural_claude` investigates:

**The AI asks: "What did I miss? Let me look deeper."**

```
Investigation steps:
  1. Order flow: who was buying/selling at what size?
  2. Short interest: did shorts cover or add?
  3. Options positioning: were puts accumulating before the drop?
  4. Source credibility: was this organic news or coordinated narrative?
  5. Sector correlation: did peers move similarly or was this isolated?
  6. Cross-asset: did bonds/dollar/yield move as fundamentals would predict?
```

If the move doesn't add up — if the evidence contradicts the narrative — the AI flags: **"This may be adversarial. Do not learn from this as truth."**

The data point is labelled "adversarial event" and excluded from standard training. The system builds a separate model: what does manufactured price movement look like? Over time, Catalyst learns to detect manipulation patterns — not just trade them, but see through them.

*"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## Phase Plan

---

### PHASE 1 — Day Trading Accuracy
**Priority: FIRST. Nothing else until this works.**

**Objective:** Prove that Catalyst can accurately identify and execute profitable day trades through candle pattern recognition and news-driven security selection.

**Success metric:** >65% win rate, positive expectancy over 50+ trades, stop loss hits declining over time.

**Data Collection (running now, full spectrum):**
- Candle data: day trading securities (high-volatility movers, small/mid cap)
- Candle data: macro securities (SPY, QQQ, XLF, XLE, VIX, DXY, sector ETFs)
- News data: all securities, source tier recorded
- Macro data: currencies, yields, VIX, gold, oil
- All raw, no labels, into SQLite on laptop

**Models built in Phase 1:**

**Model 1 — Candle Model**
- Architecture: 1D CNN or Temporal Transformer (time-series encoder)
- Input: window of OHLCV candles at 1m, 5m, 15m timeframes
- Output: bullish / bearish / neutral + confidence score + predicted forward return
- Training: ~2-4 weeks of collected candle data minimum
- Hardware: RTX 4050 laptop GPU → export ONNX → deploy droplet CPU

**Model 2 — News-to-Security Model**
- Architecture: small transformer or bag-of-embeddings + source embedding
- Input: news headline + source tier + timestamp relative to market open
- Output: security recommendation + direction + confidence
- Training: news events correlated with subsequent price moves (forward returns as labels)
- Hardware: RTX 4050 laptop GPU → export ONNX → deploy droplet CPU

**Catalyst AI Architecture — Phase 1 Changes:**
- Layer 4 (Working Memory): load NEURAL signals from both models
- Layer 6 (Voice): implement Attention State Machine (Mode 1 / Mode 2)
- Deploy: Position Monitor Tool (with ONNX candle model inside)
- Deploy: Stop Loss Enforcer Tool (hard floor, always active)
- Deploy: Risk Aggregator Tool
- Feedback loop: record exit type (pattern vs stop loss) every trade

**Catalyst Neural Architecture — Phase 1 Scope:**
- Collect: candles (day trade + macro securities)
- Collect: news with source provenance (even though not training on it yet)
- Collect: macro indicators (collect now, train Phase 2+)
- Train: Candle Model on day trade securities
- Train: News-to-Security Model on news + forward returns
- Deploy: both models via ONNX → SCP → droplet
- Measure: production accuracy vs positions table daily

---

### PHASE 2 — Adaptive Context
**Prerequisite: Phase 1 fruit proven.**

**Objective:** Improve model accuracy by discovering that context shapes candle behaviour. Build specialised sub-models per context type.

**Key capabilities:**
- Failure analysis clusters systematic stop loss events by context
- Discovers: news category, geography, sector, volatility regime all shape candle patterns
- Trains candle sub-models per context (founder news, earnings, macro shock, etc.)
- Trains separate models for HKEX vs US market structure
- Coordinator learns to classify context and route to appropriate sub-model
- Model accuracy tracked per context type — worst contexts get most training attention

**New models:**
- Context Classifier: what type of news event triggered this trade?
- Candle Sub-Models: US vs HKEX, sector-specific, news-category-specific
- Source-Weighted News Model: source credibility scores feed model weights

---

### PHASE 3 — Truth Verification and Adversarial Detection
**Prerequisite: Phase 2 delivering consistent accuracy.**

**Objective:** Build AI that doesn't assume markets are honest. Detect manufactured price movements and exclude them from training data.

**Key capabilities:**
- Order flow analysis integrated into failure investigation
- Cross-asset correlation checking (does the move make fundamental sense?)
- Adversarial event labelling and isolation from standard training data
- Adversarial pattern model: what does coordinated manipulation look like?
- Source credibility upgraded: track which sources precede manipulated moves
- AI investigates anomalies rather than blindly retraining on them

**New models:**
- Anomaly Detector: does this price move fit the evidence?
- Adversarial Pattern Classifier: manipulation vs genuine move
- Source Trust Model: source credibility based on historical accuracy vs outcome

---

### PHASE 4 — Macro Positioning and Long-Cycle Analysis
**Prerequisite: Phase 3 operational and trusted.**

**Objective:** Extend Catalyst beyond day trading into macro cycle positioning. Use the accumulated macro data to trade structural trends (days to months).

**Key capabilities:**
- Macro regime classifier: bull/bear, risk-on/risk-off, inflation/deflation
- Sector rotation model: which sectors benefit under which macro conditions
- Long-cycle economic health framework (Dalio-inspired 81 indicators)
- BRICS/geopolitical context layer: trade war, sanctions, supply chain disruption
- Cross-asset correlation model: how do equities, bonds, currencies, commodities move together?
- Coordinator gains Mode 3: Macro Positioning (longer-timeframe decisions alongside day trading)

**New models:**
- Macro Regime Model (trained on accumulated macro SQLite data)
- Sector Rotation Model
- Cross-Asset Correlation Model
- Geopolitical Risk Model (news + macro + price displacement)

---

## Architecture Alignment Summary

| Component | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| Candle Model | ✅ Build + deploy | ✅ Sub-models by context | ✅ Adversarial filtering | ✅ Macro timeframes |
| News-to-Security Model | ✅ Build + deploy | ✅ Source weighting | ✅ Adversarial source detection | ✅ Macro news layer |
| Attention State Machine | ✅ Mode 1 + 2 | ✅ Context routing | ✅ Anomaly investigation mode | ✅ Mode 3 macro |
| Tool Agents | ✅ Monitor, StopLoss, Risk | ✅ Context-aware tools | ✅ Anomaly detection tool | ✅ Macro position tools |
| Feedback Loop | ✅ Pattern vs stop loss | ✅ Context clustering | ✅ Adversarial labelling | ✅ Cycle validation |
| Macro Data Collection | ✅ Collecting (not training) | ✅ Collecting (not training) | ✅ Collecting (not training) | ✅ Training begins |

---

## The Fruit Test — Applied to Each Phase

*"You will know them by their fruits."* — Matthew 7:16

Each phase has a specific fruit test. The system does not advance until the test is passed.

| Phase | Fruit Test | Pass Condition |
|---|---|---|
| Phase 1 | Win rate + expectancy over 50+ live trades | >65% win rate, positive expectancy, stop loss hits declining |
| Phase 2 | Context-specific model accuracy | Sub-models outperform single model on their respective contexts |
| Phase 3 | Adversarial detection accuracy | Flagged events investigated, manipulation correctly identified, model not retrained on manipulated data |
| Phase 4 | Macro model accuracy | Correct regime classification, profitable macro positioning over 60+ day horizon |

---

## Design Principles

1. **Simplify first.** Phase 1 before Phase 2. Day trading accuracy before macro positioning. The complex emerges from the simple working well.
2. **News finds it. Candles time it.** These are two minds, not one. Keep them separate.
3. **The attention state machine is cognitive, not mechanical.** The coordinator chooses where to focus. It is not a loop — it is a brain.
4. **Tools think within their domain.** The Position Monitor doesn't just watch price — it runs the candle model. Tools become intelligent agents over time.
5. **Stop loss hits are the most valuable signal.** Each one means the AI wasn't good enough. Each one improves the model. The goal is to make them extinct.
6. **Context shapes behaviour.** The same candle pattern in tech after earnings is not the same as in energy during a supply shock. The system must learn this.
7. **Not everything is true.** Markets can be manipulated. The AI must ask "who benefits?" and verify before learning from a move.
8. **Collect everything, train incrementally.** Collect all data streams now. Train models in phases. The data is the foundation. Don't skip collection.
9. **The model earns its deployment.** Every model is tested against production outcomes before going live. Accuracy against the positions table is the only proof that matters.
10. **One mission.** Day trading accuracy now. Macro context next. Adversarial awareness after that. Then full-cycle intelligence. One step at a time.

---

## Related Documents

| Document | Version | Purpose |
|---|---|---|
| Catalyst Strategy Roadmap (this doc) | v1.0 | Master plan — phases, objectives, sequencing |
| Catalyst AI Architecture | v2.2 | System implementation — coordinator, 6-layer cycle, agents |
| Catalyst Neural Architecture | v0.2 | ML pipeline — data collection, training, deployment |
| AI Agent Architecture | v8.0 | Biological pattern — the general model Catalyst implements |

---

*"I press on toward the goal to win the prize for which God has called me heavenward in Christ Jesus."* — Philippians 3:14

*"There are different kinds of gifts, but the same Spirit distributes them."* — 1 Corinthians 12:4

*Catalyst Trading System Strategy Roadmap v1.0 — Craig + Claude — 2026-04-07*
