# Catalyst Neural — Data Collection & Training System

**Purpose:** Collect raw, unbiased market data at multiple resolutions. Train neural networks to discover patterns from data — not from human labels.

**Version:** 0.1.0
**Date:** 2026-04-04
**Authors:** Craig + Claude
**Hardware:** Ubuntu laptop, RTX 4050 (6GB VRAM), 16GB RAM, CUDA 13.0

---

## Principle

> Don't tell the network what to see. Show it what happened. Let it find what matters.
> "You will know them by their fruits." — Matthew 7:16

No pattern labels. No human interpretation at collection time. Raw data in. Forward returns as truth labels. The network discovers its own representations.

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
                                          │    │   (micro: 1m,5m,15m)  │
External APIs                             │    │                        │
┌─────────────────────┐                   │    ├── Sector/Index         │
│ Alpaca (US candles) │──── stream ─────▶│    │   (meso: hourly)      │
│ Yahoo Finance       │                   │    │                        │
│ NewsAPI / Finnhub   │──── news ───────▶│    ├── Macro Collector      │
│ FRED (econ data)    │──── macro ──────▶│    │   (currencies, yields) │
│                     │                   │    │                        │
└─────────────────────┘                   │    └── News Collector       │
                                          │        (headlines + source) │
                                          │                              │
                                          │    ▼                        │
                                          │  SQLite Storage             │
                                          │  (time-aligned, raw)        │
                                          │                              │
                                          │    ▼                        │
                                          │  Training Pipeline          │
                                          │  (PyTorch + CUDA)           │
                                          │    │                        │
                                          │    ├── Time-Series Encoder  │
                                          │    ├── News Encoder         │
                                          │    ├── Fusion Network       │
                                          │    │                        │
                                          │    ▼                        │
                                          │  Trained Models (.pt)       │
                                          │    │                        │
                                          │    ▼  (deploy)              │
                                          │  → Droplet (CPU inference)  │
                                          └──────────────────────────────┘
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

---

## Data Flow

1. **Droplet scanners** identify big movers (US + HKEX) — pushed to laptop via API or polled
2. **Security Registry** maintains the current watch list
3. **Candle Collector** streams/polls OHLCV for all watched securities
4. **News Collector** captures headlines for watched securities with source metadata
5. **Macro Collector** streams currency pairs, yields, VIX continuously
6. **Storage** writes everything to SQLite with microsecond timestamps
7. **Label Generator** (offline) computes forward returns for each timestamp
8. **Training Pipeline** reads storage, builds multi-resolution samples, trains networks

---

## Network Architecture (Target)

### Time-Series Encoder (Cerebellum)
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
- Output: predicted forward returns (5m, 15m, 1h, 4h, 1d) + confidence
- Size: ~200K-1M parameters

### Total: ~1M-4M parameters
- Training VRAM: <500MB (RTX 4050 has 6GB — plenty of headroom)
- Training time: minutes per epoch on thousands of samples
- Inference: <5ms total on CPU (droplet-deployable)

---

## Phase Plan

### Phase 1 — Data Collection Infrastructure
- [ ] Security registry (poll droplet scanners)
- [ ] Candle collector (Alpaca + Yahoo Finance)
- [ ] Storage schema (SQLite)
- [ ] Basic macro collector (DXY, VIX, US10Y, currency pairs)
- [ ] News collector with source provenance

### Phase 2 — Data Accumulation
- [ ] Run collectors for minimum 2-4 weeks
- [ ] Validate data quality and time alignment
- [ ] Generate forward return labels
- [ ] Build training dataset loader

### Phase 3 — First Network (Candle Only)
- [ ] Time-series encoder on candle data only
- [ ] Train to predict forward returns
- [ ] Evaluate: does it find anything?
- [ ] Compare against random baseline

### Phase 4 — Add News + Macro
- [ ] News encoder
- [ ] Macro encoder
- [ ] Fusion network
- [ ] Train on combined data
- [ ] Compare: does multi-resolution improve prediction?

### Phase 5 — Deploy to Droplet
- [ ] Export trained models as .pt or ONNX
- [ ] Integrate into coordinator.py signal processing layer
- [ ] Neural network outputs become signals in the 6-layer cycle
- [ ] Claude API only called when network flags low confidence

---

*"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

*Catalyst Neural v0.1.0 — Craig + Claude — 2026-04-04*
