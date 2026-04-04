# Catalyst Neural — Data Collection & Training System

**Purpose:** Collect raw, unbiased market data at multiple resolutions. Train neural networks to discover patterns from data — not from human labels. Measure model accuracy against live production results. Feed production outcomes back into training.

**Version:** 0.2.0
**Date:** 2026-04-04
**Authors:** Craig + Claude
**Hardware:** Ubuntu laptop, RTX 4050 (6GB VRAM), 16GB RAM, CUDA 13.0
**Implements:** Catalyst AI Architecture v2.1 — neural_claude (analyst) role

---

## REVISION HISTORY

| Version | Date | Change |
|---------|------|--------|
| 0.1.0 | 2026-04-04 | Initial — data collection infrastructure, training pipeline design |
| 0.2.0 | 2026-04-04 | Production feedback loop — read droplet PostgreSQL (positions + NEURAL signals) for model accuracy; streaming data architecture for cerebellum on droplet; phase plan updated |

---

## Principle

> Don't tell the network what to see. Show it what happened. Let it find what matters.
> "You will know them by their fruits." — Matthew 7:16

No pattern labels. No human interpretation at collection time. Raw data in. Forward returns as truth labels. The network discovers its own representations. And once deployed, the model proves itself by its fruit — predictions tested against the positions table.

---

## Architecture

```
DROPLET (DigitalOcean)                    LAPTOP (Training Station)
┌─────────────────────────┐               ┌──────────────────────────────────┐
│                         │               │                                  │
│  US Scanner ────────────┼── picks ────▶│  Security Registry               │
│  HKEX Scanner ──────────┤               │    │                            │
│                         │               │    ▼                            │
│  Consciousness DB ──────┼── context ──▶│  Multi-Resolution Collector      │
│                         │               │    │                            │
│  ┌────────────────────┐ │               │    ├── Candle Collector         │
│  │ PostgreSQL         │ │               │    │   (micro: 1m,5m,15m)      │
│  │                    │ │               │    │                            │
│  │ signals table ─────┼─┼── read ────▶│    ├── Sector/Index             │
│  │ (NEURAL domain     │ │  (predictions)│    │   (meso: hourly)          │
│  │  = model predicted)│ │               │    │                            │
│  │                    │ │               │    ├── Macro Collector          │
│  │ positions table ───┼─┼── read ────▶│    │   (currencies, yields)    │
│  │ (ground truth      │ │  (outcomes)  │    │                            │
│  │  = what happened)  │ │               │    ├── News Collector           │
│  │                    │ │               │    │   (headlines + source)     │
│  └────────────────────┘ │               │    │                            │
│                         │               │    └── Production Feedback      │
│  Scanner streams ───────┼── candles ──▶│        Collector                │
│  candle data to         │  (for local  │        (predictions vs outcomes)│
│  cerebellum on droplet  │   collection)│                                  │
│                         │               │    ▼                            │
│  Cerebellum (.pt) ◀─────┼── deploy ───│  SQLite Storage                  │
│  runs inference on      │  (trained    │  (time-aligned, raw              │
│  streamed data          │   models)    │   + production feedback)         │
│                         │               │                                  │
└─────────────────────────┘               │    ▼                            │
                                          │  Training Pipeline              │
External APIs                             │  (PyTorch + CUDA)               │
┌─────────────────────┐                   │    │                            │
│ Alpaca (US candles) │──── stream ─────▶│    ├── Time-Series Encoder      │
│ Yahoo Finance       │                   │    ├── News Encoder             │
│ NewsAPI / Finnhub   │──── news ───────▶│    ├── Macro Context Encoder    │
│ FRED (econ data)    │──── macro ──────▶│    ├── Fusion Network           │
│                     │                   │    │                            │
└─────────────────────┘                   │    ▼                            │
                                          │  Model Validation               │
                                          │  (test set + production         │
                                          │   accuracy comparison)          │
                                          │    │                            │
                                          │    ▼                            │
                                          │  Trained Models (.pt)           │
                                          │    │                            │
                                          │    ▼  (deploy to droplet)       │
                                          │  → Scanner cerebellum           │
                                          │  → Predict → Trade → Measure   │
                                          │  → Feedback flows back here ──┘│
                                          └──────────────────────────────────┘
```

---

## Data Schema — The Recorder

All data stored WITHOUT interpretation. The recorder captures what happened, who said what, when. Nothing more.

### Multi-Resolution Layers

| Layer | Data | Resolution | Source |
|-------|------|------------|--------|
| Micro | OHLCV candles per security | 1min, 5min, 15min | Alpaca, Yahoo |
| Meso | Sector ETFs, correlated indices | 5min, 15min | Yahoo Finance |
| Macro | Currency pairs, bond yields, VIX | 1min - daily | Yahoo, FRED |
| Events | News headlines + source + timestamp | Event-driven | NewsAPI, Finnhub |
| Releases | GDP, rates, employment, CPI | Scheduled | FRED API |

### Truth Labels (computed, not collected)

For any point in time, compute forward returns:
- 5 minutes forward
- 15 minutes forward
- 1 hour forward
- 4 hours forward
- 1 day forward

These are the ONLY labels. No pattern names. No sentiment scores. Just: what did the price actually do after this moment?

### Production Feedback (read from droplet)

The droplet PostgreSQL database already records everything needed to measure model accuracy:

| Droplet Table | What It Tells Us | How neural_claude Uses It |
|---|---|---|
| `signals` (domain = NEURAL) | What the model predicted — symbol, confidence, predicted returns, regime, model version | The prediction side of the accuracy equation |
| `positions` | What was actually traded — entry price, exit price, P&L, the pattern that triggered it | The ground truth — did the prediction lead to a profitable trade? |
| `pattern_outcomes` | Closed trades linked to the pattern that triggered them | Maps which model predictions led to which trade outcomes |
| `candles` (on droplet) | What the price actually did after each prediction | For predictions NOT acted upon — what would have happened? |

**neural_claude reads these tables (read-only). It never writes to the droplet database.**

The join is on symbol + timestamp: what did the model predict at this moment → what did the coordinator decide → what was the trade outcome → was the model right?

---

## Data Flow

### Collection (ongoing during market hours)

1. **Security Picker** polls droplet scanners + scans for independent big movers
2. **Security Registry** maintains the current watch list in local SQLite
3. **Candle Collector** streams/polls OHLCV for all watched securities
4. **News Collector** captures headlines with source metadata and timestamp
5. **Macro Collector** streams currency pairs, yields, VIX, commodities, sector ETFs
6. **Storage** writes everything to SQLite with precise timestamps

### Labelling (offline, after collection)

7. **Label Generator** computes forward returns for each timestamp — the truth labels

### Production Feedback (after each market close)

8. **Feedback Collector** reads droplet PostgreSQL:
   - NEURAL signals = what the model predicted
   - Positions table = what was traded and the outcome
   - Joins prediction → outcome by symbol + timestamp
9. **Accuracy Computation:**
   - Direction accuracy — did the model get the direction right?
   - Magnitude accuracy — how close was the predicted return to actual?
   - Confidence calibration — when the model said 80% confident, was it right ~80% of the time?
   - High-confidence errors — model was sure and was wrong (most valuable learning signal)
   - Drift detection — is accuracy degrading vs rolling average?
10. **Feedback stored** in local SQLite `production_feedback` table
11. **Production prediction/outcome pairs added to training dataset** — this is the highest-value training data because it represents real conditions the model has never trained on

### Training (offline, on GPU)

12. **Training Pipeline** reads SQLite (historical data + production feedback)
13. **PyTorch trains networks** on RTX 4050 — gradient descent adjusts weights
14. **Validation** against held-out test set AND production accuracy metrics
15. **If improved** → export .pt or ONNX → deploy to droplet scanner cerebellum

### The Complete Cycle

```
Collect data → Train model → Deploy to droplet
    → Model predicts on live stream → Coordinator trades
    → Positions table records outcomes
    → neural_claude reads predictions + outcomes
    → Measures accuracy → Feeds back into training
    → Retrain with production feedback → Deploy improved model
    → Cycle continues — each rotation = more accurate cerebellum
```

---

## Streaming Architecture (Droplet Side)

When a trained model is deployed to the droplet, scanner.py streams candle data to it continuously during market hours. This section describes what the analyst builds and what it becomes on the droplet.

### What neural_claude Builds (on laptop)

The neural networks — Time-Series Encoder, News Encoder, Macro Context Encoder, Fusion Network. Trained on the laptop GPU using collected data + production feedback. Exported as .pt or ONNX files.

### What It Becomes (on droplet)

scanner.py loads the trained models at startup. During market hours:

```
Candle data streams in (Alpaca websocket / polling)
    → each new candle fed to Time-Series Encoder
    → recent news fed to News Encoder
    → current macro state fed to Macro Context Encoder
    → Fusion Network combines all three
    → outputs: predicted returns, confidence, regime, novelty flag
    → if confidence > threshold → publish NEURAL signal to signal bus
    → coordinator reads NEURAL signals in Layer 4
    → high confidence + routine → act without calling Claude AI
    → low confidence or novel → call Decision Engine
```

Inference is <5ms on CPU. The models are small (1-4M parameters). No GPU needed on the droplet.

If models fail to load or inference errors occur, scanner falls back to raw data mode — streams candle data without neural signals. The brain uses Claude AI for all assessment (v2.0 behaviour). The organ screams CRITICAL:HEALTH.

---

## Network Architecture (Target)

### Time-Series Encoder (Cerebellum — Price)
- Input: window of N candles (OHLCV) at multiple timeframes
- Architecture: 1D CNN or Temporal Transformer
- Output: learned representation of price state
- Size: ~100K-500K parameters
- Inference: <1ms on CPU

### News Encoder (Sensory Association)
- Input: recent news headlines + source tier + relative timestamp
- Architecture: small transformer or bag-of-embeddings + source embedding
- Output: learned representation of information state
- Size: ~500K-2M parameters

### Macro Context Encoder
- Input: current state of currencies, yields, VIX, recent macro releases
- Architecture: MLP or small transformer
- Output: learned representation of macro regime
- Size: ~50K-200K parameters

### Fusion Network (Integration)
- Input: concatenated outputs of all encoders
- Architecture: MLP with residual connections
- Output: predicted forward returns (5m, 15m, 1h, 4h, 1d) + confidence + regime classification + novelty flag
- Size: ~200K-1M parameters

### Total: ~1M-4M parameters
- Training VRAM: <500MB (RTX 4050 has 6GB — plenty of headroom)
- Training time: minutes per epoch on thousands of samples
- Inference: <5ms total on CPU (droplet-deployable)

---

## Production Feedback — Measuring the Fruit

The model proves itself by its fruit (Matthew 7:16-20). The positions table is the fruit.

### What We Measure

| Metric | How | Why It Matters |
|---|---|---|
| Direction accuracy | Predicted up/down vs actual up/down | Basic: is the model pointing the right way? |
| Magnitude accuracy | Mean absolute error of predicted vs actual returns | Is it right about HOW MUCH the price moves? |
| Confidence calibration | When model says X% confident, is it right X% of the time? | Overconfidence is dangerous — it leads the coordinator to skip Claude AI when it shouldn't |
| High-confidence errors | Cases where confidence > 80% but prediction was wrong | Most valuable learning signal — where is the model blind? |
| Acted vs not-acted | Predictions the coordinator traded on vs skipped | Does the coordinator's judgment add value over raw model output? |
| Trade P&L from neural | P&L on trades triggered by NEURAL signals | Bottom line — is the cerebellum making money? |
| Drift over time | Accuracy vs 7-day and 30-day rolling averages | Is the market shifting away from what the model learned? |

### What We Do With It

1. **Track accuracy over time** — plot curves, detect degradation
2. **Analyse errors** — which symbols, regimes, times of day, source conditions produce errors
3. **Recalibrate confidence** — if the confidence output is systematically off
4. **Enrich training data** — live prediction/outcome pairs added to training set
5. **Trigger retraining** — if drift detected, retrain with recent data weighted higher
6. **Inform architecture decisions** — if consistently wrong in specific conditions, the network architecture may need adjustment

### Feedback Storage (local SQLite)

```sql
CREATE TABLE production_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    model_version TEXT NOT NULL,
    prediction_timestamp TEXT NOT NULL,

    -- What the model predicted (from droplet signals table)
    predicted_return_5m REAL,
    predicted_return_15m REAL,
    predicted_return_1h REAL,
    confidence REAL,
    regime_class TEXT,
    novelty_flag BOOLEAN,

    -- What actually happened (from droplet positions + candles)
    actual_return_5m REAL,
    actual_return_15m REAL,
    actual_return_1h REAL,

    -- Was it acted upon?
    acted_upon BOOLEAN DEFAULT FALSE,
    trade_pnl REAL,                -- NULL if not traded

    -- Computed accuracy
    direction_correct_5m BOOLEAN,
    direction_correct_1h BOOLEAN,
    magnitude_error_5m REAL,
    magnitude_error_1h REAL,

    collected_at TEXT NOT NULL,
    UNIQUE(symbol, market, model_version, prediction_timestamp)
);
```

---

## Phase Plan

### Phase 1 — Data Collection Infrastructure ✅
- [x] Security registry (poll droplet scanners + independent big mover scan)
- [x] Candle collector (Yahoo Finance, Alpaca upgrade path)
- [x] Storage schema (SQLite)
- [x] Basic macro collector (DXY, VIX, US10Y, currency pairs, gold, oil, sectors)
- [x] News collector with source provenance and tier assignment
- [x] Main runner (run.py) with all commands
- [x] CLAUDE.md for neural_claude identity

### Phase 2 — Data Accumulation (current)
- [ ] Run collectors during NYSE and HKEX market hours
- [ ] Validate data quality and time alignment
- [ ] Generate forward return labels
- [ ] Build training dataset loader (PyTorch Dataset/DataLoader)
- [ ] Minimum 2-4 weeks of accumulated data before training

### Phase 3 — First Network (Candle Only)
- [ ] Time-series encoder on candle data only
- [ ] Train to predict forward returns
- [ ] Evaluate: does it find anything the data supports?
- [ ] Compare against random baseline and simple moving-average baseline
- [ ] If promising → proceed. If not → examine data quality, adjust architecture.

### Phase 4 — Add News + Macro
- [ ] News encoder with source embedding
- [ ] Macro context encoder
- [ ] Fusion network combining all encoders
- [ ] Train on combined multi-resolution data
- [ ] Compare: does multi-resolution improve prediction vs candle-only?

### Phase 5 — Deploy to Droplet
- [ ] Export trained models as .pt or ONNX
- [ ] Integrate into scanner.py — models loaded at startup
- [ ] Candle data streams to cerebellum continuously during market hours
- [ ] Neural network outputs published as NEURAL signals on signal bus
- [ ] Coordinator reads NEURAL signals in Layer 4
- [ ] Claude API only called when network flags low confidence or novelty

### Phase 6 — Production Feedback Loop
- [ ] Build feedback collector — reads droplet PostgreSQL (positions + NEURAL signals)
- [ ] Compute accuracy metrics (direction, magnitude, calibration, drift)
- [ ] Store production feedback in local SQLite
- [ ] Add production prediction/outcome pairs to training dataset
- [ ] Retrain with production feedback included
- [ ] Validate retrained model against both test set and production accuracy
- [ ] Deploy improved model → measure again → cycle continues

### Phase 7 — Continuous Improvement
- [ ] Automated accuracy tracking and drift alerts
- [ ] Regime-specific model evaluation (does it work in risk-off? transitions?)
- [ ] Architecture exploration if accuracy plateaus
- [ ] Expand security universe based on production results
- [ ] The cycle never ends — each rotation produces a better cerebellum

---

## Database Access

### Local (read/write)
- **SQLite** on laptop: candles, news, macro, sectors, forward returns, production feedback, collection logs

### Remote (read-only)
- **Droplet PostgreSQL:** signals table (NEURAL domain), positions table, pattern_outcomes, candle data
- **Access:** Direct PostgreSQL connection (read-only credentials)
- **Schedule:** After each market close — pull predictions and outcomes for the day
- **Purpose:** Measure model accuracy, enrich training data with production feedback

### Consciousness API (read)
- **Droplet MCP:** Agent status, market observations, trading activity
- **Purpose:** Security picking, understanding what the trading agents are seeing and doing

---

*"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

*Catalyst Neural v0.2.0 — Craig + Claude — 2026-04-04*
