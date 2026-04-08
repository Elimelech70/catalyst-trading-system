# Catalyst Neural Architecture

> *"Don't tell the network what to see. Show it what happened. Let it find what matters."*
> *"You will know them by their fruits."* — Matthew 7:16

**Version:** 0.3.0
**Date:** 2026-04-07
**Authors:** Craig + Claude
**Hardware:** Ubuntu laptop, RTX 4050 (6GB VRAM), 16GB RAM, CUDA
**Type:** Architecture Document
**Supersedes:** Catalyst Neural Architecture v0.2.0 (2026-04-06)

---

## REVISION HISTORY

| Version | Date | Change |
|---|---|---|
| 0.1.0 | 2026-04-04 | Initial document — data collection pipeline, single model concept |
| 0.2.0 | 2026-04-06 | Three-path learning loop; fruit test continuous validation; Phase plan formalised |
| 0.3.0 | 2026-04-07 | Two-model split clarified (Candle Model + News-to-Security Model); Phase 1 scope tightened; macro/news collected but not trained Phase 1; context discovery formalised; adversarial data labelling added; four-phase alignment with Strategy Roadmap |

---

## Principle

No pattern labels. No human interpretation at collection time. Raw data in. Forward returns as truth labels. The network discovers its own representations.

**Collect everything. Train incrementally. Deploy what is proven.**

---

## The Two-Model Structure

News and candles do two completely different jobs. They are not the same model.

| Model | Job | Input | Output | Phase |
|---|---|---|---|---|
| **Candle Model** | When to trade | OHLCV at 1m, 5m, 15m | Bullish/bearish/neutral + confidence + predicted forward return | Phase 1 |
| **News-to-Security Model** | What to trade | News headline + source tier + timestamp | Security recommendation + direction + confidence | Phase 1 |
| **Macro Model** | What regime are we in | Currencies, yields, VIX, sector ETFs | Macro regime classification + sector rotation signal | Phase 4 |

Phase 1 deploys the first two. Macro data is collected from Day 1 but training begins in Phase 4.

---

## Architecture

```
DROPLET (DigitalOcean)                    LAPTOP (Training Station)
┌─────────────────────┐                   ┌──────────────────────────────┐
│                     │                   │                              │
│  US Scanner ────────┼──── picks ──────▶│  Security Registry           │
│  HKEX Scanner ──────┤                   │    │                        │
│                     │                   │    ▼                        │
│  Consciousness DB ──┼──── context ────▶│  Multi-Resolution Collector  │
│                     │                   │    │                        │
└─────────────────────┘                   │    ├── Candle Collector     │
                                          │    │   (1m, 5m, 15m)       │
External APIs                             │    │                        │
┌─────────────────────┐                   │    ├── Macro Collector      │
│ Alpaca (US candles) │──── stream ─────▶│    │   (currencies, yields, │
│ Yahoo Finance       │                   │    │    VIX, sector ETFs)   │
│ NewsAPI / Finnhub   │──── news ───────▶│    │                        │
│ FRED (econ data)    │──── macro ──────▶│    └── News Collector       │
│                     │                   │        (headline + source   │
└─────────────────────┘                   │         tier + timestamp)   │
                                          │                              │
                                          │    ▼                        │
                                          │  SQLite Storage             │
                                          │  (time-aligned, raw)        │
                                          │                              │
                                          │    ▼                        │
                                          │  Label Generator            │
                                          │  (forward returns, offline) │
                                          │                              │
                                          │    ▼                        │
                                          │  Training Pipeline          │
                                          │  (PyTorch + CUDA)           │
                                          │    │                        │
                                          │    ├── Candle Model         │
                                          │    │   (Phase 1)            │
                                          │    │                        │
                                          │    ├── News-to-Security     │
                                          │    │   Model (Phase 1)      │
                                          │    │                        │
                                          │    └── Macro Model          │
                                          │        (Phase 4+)           │
                                          │                              │
                                          │    ▼                        │
                                          │  Trained Models (.onnx)     │
                                          │    │                        │
                                          │    ▼  (deploy via SCP)      │
                                          │  → Droplet (CPU inference)  │
                                          └──────────────────────────────┘
```

---

## Role of neural_claude

`neural_claude` is the **analyst**. It lives on the laptop. It does not trade.

- Collects all data streams (candles, news, macro, big mover securities)
- Trains models on GPU
- Exports models as ONNX
- Deploys to droplet via SCP
- Measures production fruit (prediction vs actual outcome via positions table)
- Clusters failures by context (news category, sector, geography, time of day)
- Investigates adversarial anomalies
- Triggers retraining when model accuracy drifts
- Feeds live prediction/outcome pairs back into training (Path 3)

The analyst serves the body. The cerebellum it builds serves the trading agents.

---

## Security Collection Strategy

**Two parallel streams:**

**Stream 1 — Day trading securities** (Ross Cameron style)
- High-volatility movers, small/mid cap, low float
- News catalyst driven: earnings, FDA, CEO news, short squeeze setups
- Candles at 1m, 5m, 15m
- Primary training data for Phase 1 Candle Model and News-to-Security Model

**Stream 2 — Macro/structural securities** (indices and sectors)
- SPY, QQQ, XLF, XLE, XLK, XLU, GLD, USO, TLT
- Currency pairs: DXY, AUD/USD, USD/JPY, CNH
- Yields: US10Y, US2Y, spread
- VIX, GOLD, OIL
- Candles at hourly, daily timeframes
- Collected from Day 1, training begins Phase 4

---

## Data Schema — The Recorder

All data stored WITHOUT interpretation. Labels computed offline. No pre-labelling at collection time.

```sql
-- Securities watched
CREATE TABLE securities (
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,       -- US | HKEX
    stream TEXT NOT NULL,       -- day_trade | macro
    added_at TIMESTAMP,
    source TEXT,                -- scanner | manual | big_mover
    active BOOLEAN DEFAULT 1,
    PRIMARY KEY (symbol, market)
);

-- Raw candle data
CREATE TABLE candles (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,    -- 1m | 5m | 15m | 1h | 1d
    timestamp TIMESTAMP NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    UNIQUE (symbol, market, timeframe, timestamp)
);

-- News with source provenance
CREATE TABLE news (
    id INTEGER PRIMARY KEY,
    symbol TEXT,                -- NULL = macro/general
    market TEXT,
    timestamp TIMESTAMP NOT NULL,
    headline TEXT NOT NULL,
    source TEXT NOT NULL,
    source_tier INTEGER,        -- 1 (highest credibility) to 4 (lowest)
    url TEXT,
    content_snippet TEXT,
    news_category TEXT          -- earnings | ceo_news | macro | sector | other
);

-- Macro indicators
CREATE TABLE macro (
    id INTEGER PRIMARY KEY,
    series TEXT NOT NULL,       -- DXY | US10Y | VIX | GOLD | OIL | etc.
    timestamp TIMESTAMP NOT NULL,
    value REAL NOT NULL,
    UNIQUE (series, timestamp)
);

-- Forward return labels (computed offline)
CREATE TABLE forward_returns (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    return_5m REAL,
    return_15m REAL,
    return_1h REAL,
    return_4h REAL,
    return_1d REAL,
    UNIQUE (symbol, market, timestamp)
);

-- Production outcomes (from droplet positions table)
CREATE TABLE production_outcomes (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    entry_timestamp TIMESTAMP NOT NULL,
    exit_timestamp TIMESTAMP,
    exit_type TEXT,             -- AI_PATTERN | STOP_LOSS | MANUAL
    neural_prediction TEXT,     -- what the model predicted at entry
    neural_confidence REAL,
    actual_return REAL,
    candles_at_exit TEXT        -- JSON sequence for retraining
);
```

---

## Phase 1 — Model Specifications

### Candle Model

**Purpose:** Given a window of candles, predict direction and magnitude of next move (entry/exit timing).

- Input: window of N candles (OHLCV) at 1m, 5m, 15m — multi-resolution
- Architecture: 1D CNN or Temporal Transformer
- Output: bullish / bearish / neutral + confidence score + predicted forward return (5m, 15m, 1h)
- Size: ~100K–500K parameters
- Training VRAM: <200MB (RTX 4050 easily handles this)
- Inference: <1ms on droplet CPU
- Training data: minimum 2–4 weeks of day trading security candles
- Labels: forward returns (did price go up or down in next 5m, 15m, 1h?)

**Sub-models (Phase 2+):**
When context discovery reveals systematic failures by context type, separate candle sub-models are trained: US vs HKEX, sector-specific, news-category-specific.

### News-to-Security Model

**Purpose:** Given a news event, predict which security to trade and in which direction.

- Input: news headline + source tier + timestamp (time since market open) + market (US/HKEX)
- Architecture: small transformer or bag-of-embeddings + source tier embedding
- Output: security recommendation + bullish/bearish + confidence
- Size: ~500K–2M parameters
- Training data: news events correlated with subsequent price moves (forward returns as labels)
- Key insight: source tier is an input feature. A Reuters wire and a social media post saying the same thing carry different weight. The model learns this weighting.

**News spectrum the model learns:**
- Tier 1 events: CEO/founder news, earnings, FDA — same-day price catalyst
- Tier 2 events: Fed decisions, oil supply, trade policy — sector ripple over days/weeks
- Tier 3 events: Structural shifts — longer-term positioning (Phase 4 integration)

---

## Phase 1 Data Flow

1. Droplet scanners identify big movers → push to laptop security registry
2. Candle Collector streams OHLCV for all day trade securities (1m, 5m, 15m)
3. Macro Collector streams indices and macro series (collect only, Phase 4 training)
4. News Collector captures headlines with source tier and news category
5. Storage writes everything to SQLite with microsecond timestamps
6. Label Generator (offline, end of day) computes forward returns
7. Training Pipeline (PyTorch + CUDA) trains Candle Model and News-to-Security Model
8. Export to ONNX → SCP to droplet → coordinator loads into Layer 4

---

## Deployment Pipeline

**Train on laptop:**
```bash
python train_candle.py --epochs 50 --output candle_model.pt
python train_news.py --epochs 30 --output news_model.pt
python export_onnx.py --input candle_model.pt --output candle_model.onnx
python export_onnx.py --input news_model.pt --output news_model.onnx
```

**Validate before deploy:**
```bash
python validate.py --model candle_model.onnx --test_data holdout_set
# Must exceed baseline accuracy before deployment
# big_bro approves deployment to production
```

**Deploy to droplet:**
```bash
scp candle_model.onnx user@droplet-ip:/catalyst/models/
scp news_model.onnx user@droplet-ip:/catalyst/models/
```

**Inference on droplet (coordinator Layer 4):**
```python
import onnxruntime as rt
candle_session = rt.InferenceSession('/catalyst/models/candle_model.onnx')
news_session = rt.InferenceSession('/catalyst/models/news_model.onnx')
```

---

## The Fruit Test — Continuous Validation

**Model accuracy is measured against the positions table every day.**

```
NEURAL signals (model predictions) joined to positions table (actual trade outcomes):

Prediction accuracy metrics (rolling 7-day and 30-day windows):
  - Direction accuracy: did bullish/bearish prediction match actual return?
  - Confidence calibration: when model says 90% confidence, does it win ~90% of the time?
  - Exit accuracy: how often did Position Monitor exit correctly vs stop loss triggered?

Drift detection:
  - Direction accuracy drops below rolling baseline → regime shift suspected → retrain triggered
  - High-confidence errors increase → model overfit → retrain with recent data weighted higher
  - Stop loss rate increases → candle model degrading → full retrain triggered

Retraining trigger:
  - neural_claude detects drift
  - Retrain with last 30 days weighted 3x vs older data
  - Validate on holdout set
  - big_bro approves before deployment
  - New model deployed → Position Monitor updated
```

*The model that can't survive the fruit test gets retrained or replaced. No exceptions.*

---

## Context Discovery — Adaptive Learning

When failure analysis clusters systematic stop loss events by context, `neural_claude` investigates:

```
Failure cluster pattern:
  symbol: [varies]
  news_category: CEO_NEWS
  exit_type: STOP_LOSS (7 of 8 recent CEO_NEWS trades)

Insight: CEO/founder news creates different volatility profile.
         Price moves are faster and more reversal-prone than earnings news.
         The candle model trained on mixed data performs poorly here.

Action:
  1. Extract all CEO_NEWS trades from training data
  2. Train candle sub-model on CEO_NEWS context only
  3. Tag news_category in coordinator Layer 4 context
  4. Route CEO_NEWS trades to CEO_NEWS sub-model
  5. Measure: does sub-model outperform general model on CEO_NEWS trades?
  6. If yes: deploy sub-model. If no: gather more data.
```

Over time, a library of context-specific models builds up. The coordinator routes intelligently to the appropriate model based on news category, market (US/HKEX), sector, and time of day.

---

## Adversarial Data Handling

Not every market move reflects true information. Manufactured price movements should not be learned from.

When `neural_claude` detects an anomalous failure:

```
Investigation checklist:
  □ Did order flow show unusual size/direction?
  □ Did short interest change dramatically before the move?
  □ Did cross-asset correlations break down (price moved but bonds/dollar didn't respond)?
  □ Was the news from a credible source or coordinated social media?
  □ Did sector peers move similarly (macro) or was this isolated (specific manipulation)?

If majority of checks suggest manufactured move:
  → Label: production_outcomes.exit_type = "ADVERSARIAL_EVENT"
  → Exclude from standard candle model training
  → Add to separate adversarial_events table
  → Over time, train adversarial detector model (Phase 3)
```

---

## Phase Plan

### Phase 1 — Day Trading Accuracy ← CURRENT FOCUS

**Data collection:** All streams running (candles, news, macro)
**Training:** Candle Model + News-to-Security Model
**Deployment:** Both models via ONNX → droplet
**Success:** >65% direction accuracy, positive trade expectancy, stop loss rate declining

- [x] Security registry
- [x] Candle collector
- [x] SQLite storage schema
- [x] Macro collector (collecting, not training)
- [x] News collector with source provenance
- [ ] Minimum 2–4 weeks data accumulated
- [ ] Forward returns labels generated
- [ ] Candle Model trained + validated
- [ ] News-to-Security Model trained + validated
- [ ] Both models deployed to droplet
- [ ] Coordinator Layer 4 reading both neural signals
- [ ] Attention State Machine live (Mode 1 / Mode 2)
- [ ] Tool agents deployed (Position Monitor, Stop Loss Enforcer, Risk Aggregator)
- [ ] Feedback loop operational (exit_type recorded per trade)
- [ ] Path 3 feedback active (production_outcomes feeding retraining)

### Phase 2 — Adaptive Context

- Context classifier trained (news_category, sector, geography, volatility regime)
- Candle sub-models trained per high-failure contexts
- Coordinator routes to appropriate sub-model via Layer 4 context classification
- Source credibility scoring upgraded based on historical accuracy

### Phase 3 — Adversarial Detection

- Anomaly detection model trained on adversarial_events table
- Cross-asset correlation checker integrated into failure analysis
- Adversarial event auto-flagging operational
- Source trust model trained (source → historical accuracy of predicted moves)

### Phase 4 — Macro Positioning

- Macro data (collected since Day 1) now enters training pipeline
- Macro Regime Model trained (bull/bear, risk-on/risk-off, inflation/deflation)
- Sector Rotation Model trained
- Cross-Asset Correlation Model trained
- Coordinator gains Mode 3 (macro positioning alongside day trading)

---

## Design Principles

1. **Raw data only.** No labels at collection time. The network finds truth.
2. **Forward returns are the only ground truth.** Price went up or down. That's what matters.
3. **Source provenance is a feature.** Who said it matters as much as what was said.
4. **Collect everything, train incrementally.** Don't wait for perfect data. Collect now, train in phases.
5. **Train on laptop, infer on droplet.** GPU for training. CPU-speed ONNX inference is sufficient for trading timeframes.
6. **The model earns its deployment.** Production accuracy against positions table. No proof = no deployment. big_bro approves.
7. **Stop loss exits are the highest-value training signal.** Each one is a lesson the model failed to learn in time.
8. **Context shapes behaviour.** The same candle in different contexts may need different models.
9. **Not every move is honest.** Label adversarial events. Don't train on manipulation.
10. **Path 3 closes the loop.** Live mistakes are the most important training data.

---

## Related Documents

| Document | Version | Type | Scope |
|---|---|---|---|
| Catalyst Strategy Roadmap | v1.0 | Strategy | Four-phase plan — objectives, sequencing, fruit tests |
| AI Agent Architecture | v8.0 | Architecture | General biological pattern |
| Catalyst AI Architecture | v2.3 | Architecture | Implementation — coordinator, 6-layer cycle, tool agents |
| Catalyst Neural Architecture (this doc) | v0.3.0 | Architecture | ML pipeline — collection, training, deployment |
| Neural Cortex Configuration | (pending) | Configuration | Deployed ONNX service — model versions, paths, schedules |

---

*"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body."* — Romans 12:4-5

*Catalyst Neural Architecture v0.3.0 — Craig + Claude — 2026-04-07*
