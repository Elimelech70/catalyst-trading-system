# Catalyst Neural — Architecture

| Field | Value |
|---|---|
| Document | catalyst-neural-architecture |
| Version | 0.4 |
| Created | 2026-06-01 |
| Last updated | 2026-06-01 |
| Updated by | Craig + Claude |
| Status | Active — supersedes v0.3 |
| Supersedes | `catalyst-neural-architecture-v0.3.md` |
| Sub-architectures | `catalyst-context-conditioned-architecture-v0.1.md` (the v0.4 model itself), `catalyst-cohort-experiments-architecture-v0.1.md` (the universe-selection experiment driving v0.4.1) |
| Related | `catalyst-ml-methodology-v0.1.md`, `catalyst-neural-strategy-state-2026-06-01.md` |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1–0.2 | 2026-04 | Craig + Claude | Initial scaffolding (CatalystNet, single-resolution) |
| 0.3 | 2026-04-20 | Craig + Claude | Dual-input CandleModel (5m + 15m), 132K params, direction + return + confidence heads |
| 0.4 | 2026-06-01 | Craig + Claude | Context-conditioning shipped (news_context + security_context), Polygon migration, cohort-experiment framework, statistical-hygiene methodology adopted |

---

## How to use this document

This is the top-level architecture for catalyst-neural — the ML training implementation that lives on the laptop, exports ONNX models, and ships them to the trading droplets. It describes the system as it exists today (2026-06-01) and where it is going.

For deeper specifications of two areas under active development:

- **The model itself** — `catalyst-context-conditioned-architecture-v0.1.md` v0.2 specifies CandleModelV04, the news + security context heads, the dataset, and the classification pipeline. This document references that without repeating it.
- **The cohort experiment** — `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 specifies the universe-selection experiment whose result will lock in v0.4.1 production behaviour.

For the why behind methodology choices, see `catalyst-ml-methodology-v0.1.md`.

For where we are operationally right now, see `catalyst-neural-strategy-state-2026-06-01.md`.

---

## 1. Mission and role

Catalyst Neural is the ML training engine of the Catalyst Trading System. Its single output is an ONNX inference model that the production droplets (`catalyst-international` on the intl droplet, formerly `catalyst-agent` on the US droplet) consume to score live market conditions and produce trading decisions.

It does not trade. It does not hold positions. It does not even run inference for real trades. Its responsibility is bounded:

- Collect market data (candles, news, macro snapshots, security context)
- Compute training labels (forward returns at 5m / 15m / 1h horizons)
- Train the candle model on a defined universe
- Validate the resulting model under purged cross-validation
- Export to ONNX and deploy to the production droplets
- Maintain the deployed model — retrain weekly, monitor degradation

The trading system consumes its output. Catalyst Neural never sees a live order book or executes a position.

---

## 2. System layout (current)

```
catalyst-neural/                            ← lives on laptop, RTX 4050 6GB
├── collectors/
│   ├── candle_collector.py                  ← yfinance (legacy, still used for HKEX)
│   ├── news_collector.py                    ← NewsAPI + Finnhub free (legacy, still used)
│   ├── macro_collector.py                   ← FRED + macro instruments
│   ├── polygon_collector.py                 ← NEW (v0.4): Polygon Starter $29/mo, US primary feed
│   └── security_picker.py                   ← top-mover discovery
├── storage/
│   ├── database.py                          ← SQLite, 250 MB and growing
│   ├── news_classifier_regex.py             ← Phase 2 of v0.4 (15-category taxonomy)
│   ├── realized_vol.py                      ← Phase 2 of cohort experiment (planned)
│   ├── cohort_assignment.py                 ← Phase 3 of cohort experiment (planned)
│   └── migrations/
│       ├── 001_context_conditioning.sql     ← v0.4 schema (shipped)
│       └── 002_cohort_experiments.sql       ← cohort experiment schema (planned)
├── training/
│   ├── dataset.py                           ← CandleDataset v0.4 with news + security context
│   ├── models.py                            ← CandleModel (v0.3) + CandleModelV04 (current)
│   ├── trainer.py                           ← CandleTrainer with v0.4 dispatch
│   ├── cpcv_trainer.py                      ← NEW: CPCV wrapper using finance_ml (planned)
│   ├── cohort_analysis.py                   ← NEW: ANOVA, DSR, PBO via finance_ml (planned)
│   ├── label_generator.py                   ← forward returns
│   ├── report.py                            ← per-run HTML report
│   └── export_onnx.py                       ← v0.3 export; v0.4 export pending
├── deploy/
│   └── neural/                              ← ONNX → droplet sync
├── config/
│   └── settings.py                          ← env-driven config, all API keys here
├── data/
│   └── catalyst_neural.db                   ← SQLite, 250 MB, contains everything
├── models/
│   └── candle_model_*.pt + candle_stats_*.json + candle_report_*.html
├── logs/
└── run.py                                   ← CLI: init, collect, pick, train, export, pipeline, watch
```

Two copies of this tree exist:
- `/home/craig/catalyst-trading-system/catalyst-neural/` — git working tree, edit here
- `/home/craig/catalyst/catalyst-neural/` — runtime install with venv and the 250 MB SQLite DB. The systemd user service `catalyst-neural.service` runs `run.py watch` from this tree.

Changes are made in the git tree, then mirrored to the runtime tree by `cp`. The trees are kept in lockstep manually after the 2026-05-28 sync.

---

## 3. Data pipeline

### 3.1 Sources

| Source | Plan | Coverage | Used for |
|---|---|---|---|
| **Polygon.io / Massive** | Starter $29/mo | US stocks, 5y intraday history, news with metadata | Primary candle + news source (as of 2026-06-01) |
| yfinance | Free | Global incl. HKEX | HKEX candles, macro fallback |
| Finnhub | Free 60/min | US only | Legacy (being phased out) |
| NewsAPI.org | Free 100/day | US/Global | Legacy (being phased out) |
| FRED | Free | US macro | Economic indicators |

The 2026-06-01 transition to Polygon shifted the US candle + news path from the free-tier scrap (yfinance candles, Finnhub-and-NewsAPI news, 7 symbols of coverage, 1,160 classified rows) to a paid first-party path (Polygon Starter, 5y intraday × 300 symbols, Tier-1+2 wire content). The transition resolved a structural bottleneck that had prevented v0.4 from being meaningfully evaluated — `news_context` was empty on >90% of training samples, which made the v0.4 architecture experiment uninterpretable.

### 3.2 Schema highlights

- `candles(symbol, market, timeframe, timestamp, open, high, low, close, volume, vwap, trade_count)` — single table, timeframe column distinguishes 1m / 5m / 15m / 1h / 1d
- `forward_returns(symbol, market, timestamp, timeframe, return_5m, return_15m, return_1h)` — labels
- `news(headline, source, source_tier, published_at, symbols, news_category_primary, news_category_secondary, news_category_tertiary, category_confidence, …)` — v0.4 added the four classifier columns
- `securities(symbol, market, sector, market_cap_tier, volatility_regime, realized_vol_30d, …)` — v0.4 added `sector` + `market_cap_tier`; cohort experiment adds `realized_vol_30d`
- `realized_vol_history(symbol, market, snapshot_date, realized_vol_30d, n_bars_used)` — planned, cohort experiment
- `cohort_experiments(cohort_id, strategy_id, instance_id, draw_date, symbols_json, results, …)` — planned, cohort experiment

See `database-schema.md` for the full schema.

### 3.3 Classification pipeline

News is tagged at insert time by the Phase 2 regex classifier (`storage/news_classifier_regex.py`) which assigns up to three categories from a 15-category taxonomy (see `catalyst-context-conditioned-architecture-v0.1.md` §3 for the full taxonomy).

**Known limitation (2026-06-01):** The regex classifier was tuned for wire-style headlines ("AAPL reports Q3 earnings beat"). On Polygon's news firehose it works adequately on Tier 1 / Tier 2 sources (Reuters, Bloomberg, GlobeNewswire, WSJ) and fails badly on Tier 3 aggregators (Motley Fool, Benzinga). The Polygon collector applies a source-tier gate at ingestion to keep only Tier 1 / Tier 2 content, which keeps the classifier in its competence zone. Per-headline classification accuracy on the kept content is still imperfect (~50–60%), but L1 normalisation of `news_context` over 4-hour windows averages out individual misclassifications.

A future enhancement (deferred to v0.5) is to consume Polygon's structured `insights` field — per-ticker sentiment + reasoning — as a supplement or replacement for the regex classifier. The schema does not currently store `insights`.

---

## 4. Model

### 4.1 Current shipped model — CandleModelV04

| Attribute | Value |
|---|---|
| File | `training/models.py` |
| Class | `CandleModelV04` |
| `VERSION` attribute | `"0.4"` |
| Parameters | 144,935 |
| Inputs | `candles_5m` (B, 60, 5), `candles_15m` (B, 60, 5), `news_context` (B, 16), `security_context` (B, 18) |
| Outputs | `direction_logits` (B, 3), `pred_returns` (B, 3), `confidence` (B, 1) |
| CPU inference | <1 ms target (per architecture v0.3 §11) |
| Inference target | RTX 4050 6 GB for training; CPU for production droplet inference via ONNX |

Architecture: two parallel 1D-CNN encoders (one per timeframe) → concatenated to a `ContextEncoder` MLP that fuses news + security context → fusion MLP with residual block → three heads (direction softmax, return regression, confidence sigmoid).

Full specification: `catalyst-context-conditioned-architecture-v0.1.md` v0.2 §9.

### 4.2 Legacy model — CandleModel v0.3

Retained in `training/models.py` for backwards compatibility and as the production model on the droplets until v0.4.1 deploys. 132,103 parameters, two candle inputs only, same three-head output shape.

### 4.3 v0.4.1 — what comes next

`v0.4.1` is the production candidate that the cohort experiment will produce. The model class is unchanged (`CandleModelV04`); what's locked in is the *training universe* — the 150-symbol cohort that the cohort experiment identifies as the winning strategy. See `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 §11 for the four possible outcomes (single strategy wins, two tie, vol confirmed without structured winner, null).

---

## 5. Training

### 5.1 Current trainer — CandleTrainer

`training/trainer.py` ships with a `is_v04` dispatch based on the model's `VERSION` attribute. Same loss function (cross-entropy for direction + masked MSE for returns + confidence-weighted penalty), same optimizer (AdamW, LR 1e-3, weight_decay 1e-4), same scheduler (ReduceLROnPlateau, factor 0.5, patience 5).

### 5.2 Planned — CPCVTrainer wrapper

For the cohort experiment, a thin wrapper around `CandleTrainer` uses `finance_ml.model_selection.PurgedKFold` (López de Prado 2018, Ch. 7) to produce 5-fold purged cross-validation splits with 1-hour purge and 1-day embargo. Per cohort: 5 fits, median across folds, written to `cohort_experiments` table.

Specification: `catalyst-cohort-experiments-implementation-v0.1.md` Phase 4.

### 5.3 What the trainer does NOT do

- It does not run real-time. Training happens offline on the laptop GPU.
- It does not see live market data. It trains on stored candles + stored news with `forward_returns` labels precomputed by the label generator.
- It does not tune hyperparameters during the cohort experiment. Everything is held constant except the universe — see `catalyst-ml-methodology-v0.1.md` for the controlled-experiment principle.

---

## 6. Deployment

### 6.1 ONNX export

`training/export_onnx.py` exports the trained `.pt` checkpoint to ONNX with a 4-input signature for v0.4. v0.3 ONNX (2-input signature) is still produced for the production droplets until v0.4.1 ships.

### 6.2 Droplet sync

`deploy/neural/` contains the rsync-based deploy script that pushes the ONNX file plus `model_version.json` to both droplets (US is shelved, so currently only intl is updated). The droplets reload the model on the next inference call.

### 6.3 Inference contract

The droplet's `cerebellum.py` is responsible for:
- Reading `model_version.json` to know whether to use the v0.3 or v0.4 inference path
- Constructing the input tensors per the signature (candles for v0.3; candles + news + security context for v0.4)
- Calling the ONNX runtime
- Returning direction + return + confidence to the trading coordinator

This contract is owned by the trading-system architecture (`catalyst-ai-architecture-v2.4.md`), not by catalyst-neural.

---

## 7. Operational state (snapshot 2026-06-01)

| Layer | Status |
|---|---|
| Watch service (`catalyst-neural.service`) | Running; loop-fix patched 2026-05-28 (was stuck in sudo-suspend retry loop) |
| GPU | Available (RTX 4050, driver installed 2026-05-28 after kernel upgrade) |
| v0.3 weekly retrain | Last run 2026-05-28 09:53 UTC, 162K samples, 40.83% dir_acc |
| v0.4 training runs | 2 runs done: 2026-05-28 zero-news (40.78%) and 2026-06-01 with-news (41.18%) — both failed +5 pp gate |
| Polygon backfill (5y × 300 symbols × candles + Tier 1/2 news) | Running 2026-06-01, est 4–6 hours |
| Cohort experiment | Code planned, data acquisition in progress, est first run 2026-06 mid-month |
| Production droplet model | v0.3, last sync ~2026-05-10 |
| Production P&L (intl, Mar–May 2026) | −3,772 HKD net on real trading months (Jan/Feb are reconciliation noise) |

---

## 8. Open architecture questions

These are unresolved decisions, deliberately held open until evidence accumulates.

1. **Whether to retain the regex classifier** when Polygon's `insights` field becomes available. v0.5 question.
2. **HKEX news coverage.** Polygon and the free APIs do not cover Hong Kong. Either upgrade to Refinitiv (~$22K/yr — mission-incompatible), find a Hong Kong-specific feed, or accept that the v0.4 architecture is US-only. Currently leaning toward the third option.
3. **Same model across cohorts vs cohort-specific models.** Resolved in v0.4 (same model — controlled experiment). The flip side (cohort-specific architecture) is a v0.5 question if the v0.4.1 deploy shows architecture-cohort interaction.
4. **Walk-forward vs CPCV.** CPCV is the principled choice but expensive. If the cohort experiment exceeds compute budget, walk-forward is an acceptable fallback per the cohort impl doc.
5. **Volatility metric definition.** Currently realized historical (30-day stdev of 5m log returns). Implied vol from options would be forward-looking but adds an API dependency. Deferred.

---

## 9. Mission alignment

The architecture exists to fund the mission of enabling the poor through accessible algorithmic trading. Three of the choices above are direct expressions of that mission:

- **No Bloomberg Terminal** — $24K/yr is mission-incompatible; the entire account size would be consumed by data for years.
- **Polygon Starter at $29/mo** — the cheapest tier that gives institutional-equivalent data quality for US equities, which is what the cited academic literature actually used in 90%+ of its work.
- **Statistical hygiene before deployment** — three months of −3.7K HKD losses on the intl droplet are the cost of deploying without sufficient methodology. The cohort experiment is a one-time ~5-hour GPU investment to prevent further capital bleed.

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## 10. What this document is not

- Not the model spec → see `catalyst-context-conditioned-architecture-v0.1.md` v0.2
- Not the cohort experiment spec → see `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 + the implementation doc
- Not the trading-system architecture → see `catalyst-ai-architecture-v2.4.md`
- Not a runbook → see the implementation guides
- Not a methodology doc → see `catalyst-ml-methodology-v0.1.md`
- Not a current-state snapshot → see `catalyst-neural-strategy-state-2026-06-01.md`

---

*Craig + Claude — The Catalyst Family*
*2026-06-01*
