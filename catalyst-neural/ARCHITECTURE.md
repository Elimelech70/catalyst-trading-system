# Catalyst Neural — Architecture

> *"Don't tell the network what to see. Show it what happened. Let it find what matters."*
> *"You will know them by their fruits."* — Matthew 7:16

**Version:** 0.3.1
**Updated:** 2026-04-20
**Authors:** Craig + Claude
**Hardware:** Ubuntu laptop, RTX 4050 (6GB VRAM), 16GB RAM, CUDA

---

## Principle

No pattern labels. No human interpretation at collection time. Raw data in. Forward returns as truth labels. The network discovers its own representations.

**Collect everything. Train incrementally. Deploy what is proven.**

---

## The Two-Model Structure

| Model | Job | Input | Output | Status |
|---|---|---|---|---|
| **Candle Model** | When to trade | OHLCV at 5m + 15m (dual-timeframe) | Direction + confidence + forward returns | Deployed |
| **News-to-Security Model** | What to trade | Headline + source tier + timestamp | Security + direction + confidence | Planned |
| **Macro Model** | What regime | Currencies, yields, VIX, sectors | Regime classification | Phase 4 |

---

## Architecture

```
US DROPLET (68.183.177.11)                LAPTOP (Training Station)
┌─────────────────────┐                   ┌──────────────────────────────┐
│ v8 Agent Body       │                   │                              │
│  US Scanner ────────┼──── picks ──────▶│  Security Registry           │
│  SQLite agent.db    │                   │    │                        │
│  Signal Bus         │                   │    ▼                        │
│  Neural Container ◀─┼── deploy ────────│  Multi-Resolution Collector  │
│  (standalone ONNX)  │                   │    │                        │
└─────────────────────┘                   │    ├── Candle Collector     │
                                          │    │   (1m, 5m, 15m)       │
INTL DROPLET (209.38.87.27)              │    │                        │
┌─────────────────────┐                   │    ├── Macro Collector      │
│ MCP Architecture    │                   │    │   (currencies, yields, │
│  HKEX Scanner ──────┼──── picks ──────▶│    │    VIX, sector ETFs)   │
│  PostgreSQL + Redis │                   │    │                        │
│  Moomoo/OpenD       │                   │    └── News Collector       │
│  Coordinator ◀──────┼── deploy ────────│        (headline + source   │
│  (cerebellum.py     │                   │         tier + timestamp)   │
│   embedded ONNX)    │                   │                              │
└─────────────────────┘                   │    ▼                        │
                                          │  SQLite Storage             │
External APIs                             │  (time-aligned, raw)        │
┌─────────────────────┐                   │                              │
│ Yahoo Finance       │──── candles ────▶│    ▼                        │
│ NewsAPI / Finnhub   │──── news ───────▶│  Label Generator            │
│ FRED (econ data)    │──── macro ──────▶│  (forward returns, offline) │
└─────────────────────┘                   │                              │
                                          │    ▼                        │
                                          │  Training Pipeline          │
                                          │  (PyTorch + CUDA)           │
                                          │    │                        │
                                          │    ├── Candle Model (v0.3)  │
                                          │    │   132K params, deployed │
                                          │    │                        │
                                          │    ├── News-to-Security     │
                                          │    │   (planned)            │
                                          │    │                        │
                                          │    └── Macro Model          │
                                          │        (Phase 4)            │
                                          │                              │
                                          │    ▼                        │
                                          │  ONNX Export + Deploy       │
                                          │    ├── → US Droplet         │
                                          │    └── → Intl Droplet       │
                                          └──────────────────────────────┘
```

---

## CandleModel v0.3 — Current Production Model

**132,103 parameters. <1ms CPU inference. Deployed to both droplets.**

```
Input:  candles_5m  (batch, 5, 60)    ─┐
                                        ├─ MultiResolutionEncoder ─── Fusion MLP ─┬─ direction_head  → (batch, 3)
Input:  candles_15m (batch, 5, 60)    ─┘     (2 × TimeSeriesEncoder)   (residual)  ├─ return_head     → (batch, 3)
                                              40K params each           50K params  └─ confidence_head → (batch, 1)
```

| Component | Parameters |
|-----------|-----------|
| TimeSeriesEncoder (5m) | 40,448 |
| TimeSeriesEncoder (15m) | 40,448 |
| Fusion MLP | 50,304 |
| Direction head (3-class softmax) | 387 |
| Return head (5m, 15m, 1h regression) | 387 |
| Confidence head (sigmoid) | 129 |
| **Total** | **132,103** |

**Training:**
- Loss: CrossEntropy(direction) + MaskedMSE(returns) + 0.1 × Confidence
- Early stopping: patience 15, tracks validation loss
- Direction labels: >+0.05% = bullish, <-0.05% = bearish, else neutral
- Data: 97K+ training samples, 24K+ validation, 63 securities (US + HKEX)

---

## Automation Pipeline

Everything runs automatically via systemd:

```
┌─────────────────────────────────────────────────┐
│  catalyst-neural.service (continuous)            │
│  Runs: python run.py watch                       │
│  Collects: candles, macro, news during market hrs│
│  Suspends: between sessions (power management)   │
└─────────────────────────────────────────────────┘
                    │
                    ▼ (data accumulates in SQLite)
┌─────────────────────────────────────────────────┐
│  catalyst-pipeline.timer (weekly, Sunday 20:00)  │
│  Runs: python run.py pipeline                    │
│  Steps:                                          │
│    1. Compute forward return labels              │
│    2. Train CandleModel (GPU, early stopping)    │
│    3. Export to ONNX                             │
│    4. Deploy to US droplet (catalyst-neural)     │
│    5. Deploy to Intl droplet (cerebellum.py)     │
└─────────────────────────────────────────────────┘
```

---

## Deployment Targets

| Environment | IP | Architecture | Neural Integration | Deploy Script |
|---|---|---|---|---|
| **US Droplet** | 68.183.177.11 | v8 Agent Body, SQLite, signal bus | Standalone Docker container | `deploy/deploy-neural.sh` |
| **Intl Droplet** | 209.38.87.27 | MCP, PostgreSQL, Redis, Moomoo/OpenD | cerebellum.py in coordinator | `deploy/deploy-intl.sh` |

---

## Data Schema

All data stored WITHOUT interpretation. Labels computed offline.

### Multi-Resolution Layers

| Layer | Data | Resolution | Source |
|-------|------|------------|--------|
| Micro | OHLCV candles per security | 1m, 5m, 15m | Yahoo Finance |
| Meso | Sector ETFs (11 sectors) | Daily | Yahoo Finance |
| Macro | Currencies, yields, VIX, commodities | Daily | Yahoo Finance |
| Events | News headlines + source tier | Event-driven | NewsAPI, Finnhub |

### Truth Labels

Forward returns computed offline — the ONLY labels:
- 5 minutes, 15 minutes, 1 hour, 4 hours, 1 day
- Direction: bullish (>+0.05%), bearish (<-0.05%), neutral

---

## Configuration

All runtime config loaded from `.env` file via `python-dotenv`:

| Category | Variables | Where |
|----------|-----------|-------|
| Droplets | `CATALYST_US_DROPLET_IP`, `CATALYST_INTL_DROPLET_IP`, `CATALYST_SSH_KEY` | `.env` |
| APIs | `NEWSAPI_KEY`, `FINNHUB_KEY`, `ALPACA_API_KEY`, `FRED_API_KEY` | `.env` |
| Training | `TRAINING_DEVICE`, `TRAINING_EPOCHS`, `TRAINING_BATCH_SIZE`, `TRAINING_LR` | `.env` |
| Markets | Market hours, instruments, sector ETFs, news tiers | `config/settings.py` |

---

## Phase Plan

### Phase 1 — Day Trading Accuracy ← CURRENT

- [x] Security registry + candle collector
- [x] SQLite storage + macro collector
- [x] News collector with source provenance
- [x] Forward return labels
- [x] CandleModel v0.3 trained (132K params, direction + returns + confidence)
- [x] ONNX export + deployed to both droplets
- [x] Automated collection (systemd service)
- [x] Automated pipeline (weekly timer: train → export → deploy)
- [ ] News-to-Security Model trained
- [ ] >65% direction accuracy (currently ~43%)
- [ ] Feedback loop (production outcomes → retraining)

### Phase 2 — Adaptive Context
- [ ] Context classifier (news category, sector, volatility regime)
- [ ] Candle sub-models per failure context
- [ ] Coordinator routes to appropriate sub-model

### Phase 3 — Adversarial Detection
- [ ] Anomaly detection for manufactured moves
- [ ] Source trust model

### Phase 4 — Macro Positioning
- [ ] Macro Regime Model
- [ ] Sector Rotation Model
- [ ] Cross-Asset Correlation Model

---

*"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

*Catalyst Neural Architecture v0.3.1 — Craig + Claude — 2026-04-20*
