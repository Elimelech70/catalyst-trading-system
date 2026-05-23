# Catalyst Neural — Context-Conditioned Candle Architecture

| Field | Value |
|---|---|
| Document | catalyst-context-conditioned-architecture |
| Version | 0.1 (DRAFT) |
| Created | 2026-05-23 |
| Last updated | 2026-05-23 |
| Updated by | Craig + Claude |
| Status | Design review — Phase 1 (schema) + HKEX inference scaffold landed; v0.4 ONNX not yet trained |
| Supersedes | Sections of `catalyst-neural-architecture-v0.3.md` related to inputs/training |
| Related | `catalyst-ai-architecture-v2.4.md`, `catalyst-us-configuration-v1.0.md` |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-05-23 | Craig + Claude | Initial draft — news/security taxonomy, two-dimensional context conditioning of the candle model |
| 0.1a | 2026-05-23 | Craig + Claude | §11.3 + §15.3 amended — HKEX `cerebellum.py` v1.2.0 ships the version-branching scaffold ahead of v0.4 ONNX. v0.3 inference unchanged; v0.4 path is a logged stub returning `available=False` so Phase 9 only needs to fill the body. |

---

## 1. Executive summary

The current v0.3 candle model achieves ~40.65% direction accuracy on validation (latest run 2026-05-18) — only ~6 percentage points above the 34.8% majority-class baseline, and the return-magnitude head is worse than naive (R² near zero, MAE worse than baseline on every horizon). The hypothesis explored in this document is that this underperformance is not a data-volume problem but a **regime-mixing** problem: the same OHLCV pattern means structurally different things depending on what news context surrounds it and what kind of security it is happening to. A 1% upward 5-minute move in a small-cap biotech under FDA-pending news is a completely different signal from a 1% upward 5-minute move in a mega-cap bank under FOMC release. The current model averages these together and produces mush.

This document specifies the v0.4 architecture: a two-dimensional context model (news type × security type) that conditions the candle model so it can learn regime-specific behaviour without us hand-coding any rules. The change resolves three of the inter-document inconsistencies identified in the April 2026 gap analysis, in addition to the accuracy problem.

---

## 2. Motivation

### 2.1 The 40% problem

Latest training run (`training_meta_20260518_003353.json`):
- 132,103 parameters, 23 epochs (early-stopped)
- Final validation direction accuracy: **40.65%** (random / majority-class baseline ≈ 34.8% for the 34.8 / 34.3 / 30.9 bull / bear / neutral class balance)
- Final validation MAE on forward returns: 0.378 (worse than naive-baseline MAE by ~1.1% on the 5m horizon — return-magnitude head is currently not useful)
- Best validation loss: 1.626
- R² on returns hovers near zero across 5m / 15m / 1h horizons

Earlier runs (Apr 8 → Apr 22) hovered between 37.75% and 42.39% direction accuracy. The model is learning *something* — about 6 pp above majority-class baseline — but the magnitude prediction is essentially noise. This is consistent with the 10,690+ US coordinator cycles with no confirmed trades.

### 2.2 The hypothesis

Different news types attract different trader populations. Different trader populations leave different OHLCV fingerprints. A single candle model trained across all news contexts is implicitly averaging these populations together, learning the mean response while none of the actual regimes look like the mean.

### 2.3 Literature foundation

The academic literature triangulates on three claims that support the hypothesis:

**News creates distinct intraday signatures.** Christensen, Timmermann and Veliyev (2024) showed using tick-by-tick data that earnings announcements almost always induce jumps in the announcing firm's stock price and significantly raise the probability of co-jumps in non-announcing firms — distinct from the smaller, more diffuse reaction to most other news types.

**Different news types produce different patterns.** FDA event studies (1980-1999 sample, 167 approvals) found significant positive abnormal returns on announcement day but not before — a clean jump-and-stop signature. By contrast, post-earnings announcement drift (Bernard and Thomas, 1989, and subsequent literature) shows prices continue to drift in the surprise direction for up to 60 days post-earnings — a jump-and-drift signature. Macro/FOMC events produce synchronized market-wide moves detectable in 30-minute windows around statements (San Francisco Fed USMPD database).

**The interaction with security type is real and measurable.** Boudoukh, Feldman, Kogan and Richardson (2019, Review of Financial Studies) found that firm-specific news accounts for 49.6% of overnight idiosyncratic volatility, with considerable variation by news type *and* by firm characteristics. Multiple studies confirm that small-cap stocks show amplified asymmetric reactions to negative news compared to large-caps, that biotech is structurally high-beta, and that the post-earnings drift is liquidity-risk-driven and strong in small-cap stocks but largely absent in large-cap stocks.

The consensus position in the literature is that the candle response is jointly determined by (news_type, security_type), not by either alone.

---

## 3. News taxonomy

### 3.1 Design principles

- **Harmonized across the three existing schemes** — resolves the catalyst-neural design doc (5 categories), catalyst-international HKEX yaml (5 catalyst tiers), and catalyst-research consciousness DB (5 classifications) inconsistencies into one canonical taxonomy
- **Boudoukh-aligned** — uses 15 categories rather than 5, matching the granularity of the most-cited academic paper on news-driven volatility
- **Hierarchical** — categories group into five families so we can train at either granularity depending on data volume
- **Operationally tractable** — every category can be initially populated by keyword regex against headlines, with LLM-based refinement later

### 3.2 The 15 categories

**Family A — Corporate fundamentals**

| ID | Category | Description | Example keywords |
|---|---|---|---|
| 01 | `earnings` | Quarterly/annual results, guidance changes | reports, earnings, beats, misses, guidance, EPS, revenue |
| 02 | `corporate_action` | M&A, buybacks, spinoffs, IPO, listings | acquires, acquisition, merger, buyback, repurchase, spinoff, IPO, listing |
| 03 | `executive` | Leadership changes | CEO, resign, appointed, departure, succession, founder |
| 04 | `capital` | Debt/equity raises, dividend changes | raises, offering, dividend, distribution, refinance |

**Family B — Regulatory and legal**

| ID | Category | Description | Example keywords |
|---|---|---|---|
| 05 | `regulatory_approval` | FDA, agency clearances, court rulings, settlements | FDA, approval, approved, clearance, granted, ruling, settlement |
| 06 | `regulatory_action` | SEC investigations, lawsuits, fines | SEC, lawsuit, investigation, probe, fine, charged, sued |
| 07 | `bankruptcy` | Restructuring, default, Chapter 11 | bankruptcy, default, restructuring, Chapter 11, insolvency |

**Family C — Operations and business**

| ID | Category | Description | Example keywords |
|---|---|---|---|
| 08 | `product` | Launches, recalls, partnerships, contracts | launches, releases, recall, partnership, deal, contract, orders |
| 09 | `operational` | Production, supply chain, labor | production, factory, strike, layoff, supply, shortage |

**Family D — Market and analyst**

| ID | Category | Description | Example keywords |
|---|---|---|---|
| 10 | `analyst` | Upgrades, downgrades, initiations, price targets | upgrade, downgrade, initiates, target, overweight, underweight |
| 11 | `credit_rating` | Moody's, S&P, Fitch rating changes | Moody's, S&P, Fitch, downgrade rating, upgrade rating |

**Family E — Macro and sector**

| ID | Category | Description | Example keywords |
|---|---|---|---|
| 12 | `monetary_policy` | Fed/PBOC/ECB decisions, FOMC, central bank speeches | Fed, FOMC, rate, hike, cut, basis points, Powell, PBOC |
| 13 | `macro_economic` | CPI, GDP, employment, trade data | CPI, GDP, payrolls, unemployment, inflation, trade deficit |
| 14 | `policy_regulation` | Tariffs, subsidies, sanctions, trade policy | tariff, sanction, subsidy, stimulus, trade war, ban |
| 15 | `sector_wide` | Industry-wide events, peer-correlated moves | sector, industry, peers |

**Catch-all**

| ID | Category | Description |
|---|---|---|
| 99 | `other` | Anything not matching the above |

### 3.3 Mapping to existing schemes

| catalyst-international (HKEX) tier | catalyst-research classification | This document |
|---|---|---|
| `binary_event` | — | 05 `regulatory_approval`, sometimes 02 |
| `corporate_action` | `m_and_a` | 02 `corporate_action` |
| `policy` | `policy`, `regulatory` | 14 `policy_regulation`, 12 `monetary_policy` |
| `analyst` | — | 10 `analyst` |
| `general` | `other` | 99 `other` (decompose further over time) |
| — | `earnings` | 01 `earnings` |

### 3.4 Multi-label support

Boudoukh et al. found that days with *multiple* news types produce disproportionately large reactions. The taxonomy must support multi-label tagging: a single headline can match multiple categories. Storage will allow up to 3 categories per headline ranked by match strength.

---

## 4. Security taxonomy

Three orthogonal dimensions, encoded as one-hot vectors.

### 4.1 Market (2 values)

`US` | `HKEX`

### 4.2 Sector (11 values, GICS-aligned but simplified)

| ID | Sector | Examples |
|---|---|---|
| TECH | Information Technology | semiconductors, software, hardware |
| BIO | Biotech / Pharma | drug developers, medical devices, clinical-stage |
| FIN | Financials | banks, insurance, asset managers |
| CONS_D | Consumer Discretionary | retail, auto, leisure |
| CONS_S | Consumer Staples | food, beverages, household |
| ENERGY | Energy | oil/gas, coal, renewables |
| INDUSTRIAL | Industrials | machinery, transport, defense |
| MATERIALS | Materials | mining, chemicals, gold |
| UTIL | Utilities | electric, water, gas distribution |
| COMMS | Communication Services | telecom, media, internet platforms |
| REAL_ESTATE | Real Estate | REITs, developers |

### 4.3 Market cap tier (5 values)

| ID | Tier | Range (USD) |
|---|---|---|
| MICRO | Micro-cap | < $300M |
| SMALL | Small-cap | $300M – $2B |
| MID | Mid-cap | $2B – $10B |
| LARGE | Large-cap | $10B – $200B |
| MEGA | Mega-cap | > $200B |

For HKEX, use HKD equivalent at HKD/USD = 7.8 baseline.

### 4.4 Encoding

Total security context vector = 2 + 11 + 5 = **18 dimensions** (one-hot concatenation).

This is small and stable. Sector and cap tier rarely change for a given symbol; market never changes. Pre-compute and cache.

### 4.5 Volatility regime (Phase 2 addition)

Initially excluded to keep v0.4 scope tight. Phase 2 may add a derived 4-state volatility regime tag (low / medium / high / extreme) computed from rolling 20-day ATR percentile, raising the security context to 22 dimensions.

---

## 5. Joint context — the relationship to candle behaviour

The literature establishes that candle response is jointly determined by `(news_type, security_type)`. The model design must reflect this.

### 5.1 What "jointly determined" means in practice

The same news category produces different candle behaviour depending on security type, as documented in the literature:

| News × Security | Expected candle signature | Source |
|---|---|---|
| `regulatory_approval` × `BIO` × `SMALL/MICRO` | 50-200% jump, single candle, asymmetric (rejections larger than approvals) | Industry research on FDA / biotech trading; PubMed FDA event studies |
| `regulatory_approval` × `BIO` × `LARGE/MEGA` | Muted single-digit move, no follow-through | Same source, large-cap dilution |
| `earnings` × `*` × `SMALL` | Jump + sustained drift over days (PEAD) | Bernard and Thomas (1989); Quantpedia |
| `earnings` × `*` × `LARGE/MEGA` | Jump, then rapid mean reversion, weak drift | Martineau (2022) "Rest in Peace PEAD" |
| `monetary_policy` × `FIN` × `*` | Sharp synchronized move; sign depends on rate direction and bank business mix | NY Fed staff reports; SF Fed USMPD |
| `monetary_policy` × `BIO` × `*` | Risk-off proxy; high-beta downside on hawkish surprises | Industry research on biotech as rate-sensitive |
| `analyst` × `*` × `MICRO/SMALL` | Amplified reaction (low liquidity, high info asymmetry) | Baker and Wurgler (2006); ScienceDirect 2025 |
| `analyst` × `*` × `MEGA` | Muted; institutional flow dampens | Same source |
| `corporate_action` (M&A target) × `*` × `*` | Gap to deal price, then flat | Standard event-study finding |
| `bankruptcy` × `*` × `SMALL` | Cascading sells, liquidity gaps | Default literature |

The number of joint regimes is large (15 × 11 × 5 × 2 = 1,650 cells in principle), but real data will concentrate in a much smaller set of well-populated cells. The model learns the populated cells; the empty cells get neutral context.

### 5.2 How the model uses the joint context

Three design options, in order of complexity:

**Option 1 — Concatenation (recommended for v0.4):** the context vectors are concatenated to the fused candle representation before the prediction heads. Simple, follows the existing fused-CatalystNet pattern, easy to debug.

**Option 2 — FiLM modulation (v0.5):** the context vector generates per-feature scale and shift parameters (γ, β) that modulate the candle features: `x_modulated = γ(context) * x_candle + β(context)`. More powerful because the context literally changes how the candle features are read, not just adds a parallel signal. Standard technique in conditional neural networks.

**Option 3 — Per-context sub-models (v0.6+):** train separate candle models per well-populated joint cell (e.g., a dedicated `bio_small_fda_model.onnx`). The coordinator routes inference to the appropriate sub-model based on context. Most powerful but requires sufficient data per cell.

v0.4 ships with Option 1. Phase 2 may upgrade to Option 2 if Option 1 underperforms.

---

## 6. Database schema changes

### 6.1 News table additions

```sql
ALTER TABLE news ADD COLUMN news_category_primary TEXT;       -- one of 15 + 'other'
ALTER TABLE news ADD COLUMN news_category_secondary TEXT;     -- nullable
ALTER TABLE news ADD COLUMN news_category_tertiary TEXT;      -- nullable
ALTER TABLE news ADD COLUMN category_confidence REAL;         -- 0.0-1.0, from classifier
ALTER TABLE news ADD COLUMN classified_by TEXT;               -- 'regex_v1' | 'llm_v1' | 'manual'
ALTER TABLE news ADD COLUMN classified_at TEXT;               -- ISO timestamp

CREATE INDEX idx_news_category_primary ON news(news_category_primary);
CREATE INDEX idx_news_category_published ON news(news_category_primary, published_at);
```

### 6.2 Securities table additions

`securities.sector` **already exists** in `storage/database.py` (NULL on all 1,532 rows at the time of writing). The migration adds only the cap-tier columns; Phase 3 of the implementation guide populates both the existing `sector` column and the new ones.

```sql
-- NOTE: securities.sector already exists — do NOT re-ALTER it
ALTER TABLE securities ADD COLUMN market_cap_tier TEXT;       -- MICRO|SMALL|MID|LARGE|MEGA
ALTER TABLE securities ADD COLUMN market_cap_usd REAL;        -- snapshot, refreshed weekly
ALTER TABLE securities ADD COLUMN context_updated_at TEXT;

CREATE INDEX idx_securities_sector ON securities(sector);
CREATE INDEX idx_securities_cap_tier ON securities(market_cap_tier);
```

### 6.3 Forward returns table — unchanged

Labels are the truth. They do not depend on context. The model learns the context-conditional mapping.

### 6.4 New table — context_regime_summary (for analytics, not training)

```sql
CREATE TABLE context_regime_summary (
    id INTEGER PRIMARY KEY,
    news_category TEXT NOT NULL,
    sector TEXT NOT NULL,
    cap_tier TEXT NOT NULL,
    market TEXT NOT NULL,
    sample_count INTEGER,
    mean_return_5m REAL,
    std_return_5m REAL,
    mean_return_1h REAL,
    std_return_1h REAL,
    direction_bullish_pct REAL,
    direction_bearish_pct REAL,
    last_computed TEXT,
    UNIQUE(news_category, sector, cap_tier, market)
);
```

Populated by an offline analytics job. This is the data structure that makes Test 1 (distribution comparison) trivial to run.

---

## 7. News tagging pipeline

### 7.1 Stage 1 — Regex baseline (immediate)

Build `news_classifier_regex.py` that:
- Loads keyword sets per category (extending the HKEX yaml)
- Scores each headline against each category by matched-keyword count
- Assigns top 3 categories above a confidence threshold
- Backfills all existing rows in the `news` table
- Tags new headlines at collection time

Expected accuracy: 60-75% on clearly-typed headlines, lower on ambiguous ones. Acceptable as a baseline.

### 7.2 Stage 2 — LLM classifier (Phase 1.5)

A zero-shot LLM (Claude) classifies headlines against the 15-category taxonomy via prompt. The recent LabelFusion paper (arXiv 2025) showed that LLMs achieve macro F1 ~76% zero-shot on Reuters-21578 financial classification and beat fine-tuned classifiers in low-data regimes. We are in a low-data regime, so this is the right tool for the job.

Workflow:
- Stage 1 regex runs first (fast, free)
- Headlines below confidence threshold get sent to LLM (slower, paid)
- LLM output stored with `classified_by = 'llm_v1'` for traceability
- LLM disagreements with regex flagged for review — these are the training examples for a future fine-tuned classifier

### 7.3 Stage 3 — Fine-tuned classifier (Phase 2+)

Once we have several thousand human-validated examples, train a small RoBERTa-style classifier locally. Per LabelFusion findings, this becomes more accurate than the LLM alone above ~80% training data availability.

---

## 8. Dataset changes — CandleDataset v0.4

### 8.1 New sample structure

Each sample returns:

```python
{
    "candles_5m":       (lookback, 5),      # unchanged
    "candles_15m":      (lookback, 5),      # unchanged
    "news_context":     (16,),              # 15 categories + 'other' one-hot
    "security_context": (18,),              # 2 + 11 + 5 one-hot
    "direction":        scalar,             # unchanged
    "returns":          (3,),               # unchanged
    "return_mask":      (3,),               # unchanged
}
```

### 8.2 News context construction

For each candle timestamp `t`:
- Pull all news for the symbol in `[t - 4 hours, t]` window
- For each headline, fetch its `news_category_primary` (and secondary if present)
- Build a 16-dim vector: weighted count of categories, weighted by `tier_weight × recency_decay`
  - `tier_weight`: 1.5 / 1.3 / 1.0 / 0.8 / 0.8 for source tiers 1/2/3/4/5
  - `recency_decay`: `1.0 - (hours_before / 4.0)`
- L1-normalize so the vector sums to 1 when news is present, all-zero when absent

This replaces the existing bag-of-character-trigrams news feature, which never carried explicit category signal.

### 8.3 Security context construction

For each sample:
- Look up the security's `sector`, `market_cap_tier`, `market`
- One-hot encode each, concatenate to 18-dim vector
- Cache per-symbol so this is O(1) per sample

### 8.4 Handling missing context

- No recent news → `news_context` is all zeros (legitimate "quiet market" signal, model learns this)
- Security not classified yet (sector/cap_tier null) → use 'other' fallback bit in each axis

---

## 9. Model architecture — CandleModel v0.4

### 9.1 Architecture diagram

```
Input:
  candles_5m  ──► TimeSeriesEncoder_5m  ──► (64,)
  candles_15m ──► TimeSeriesEncoder_15m ──► (64,)              ┐
                                                                ├──► concat ──► (160,) ──► fusion MLP ──► (128,) ──► heads
  news_context (16,)     ──┐                                    │
                            ├──► ContextEncoder MLP ──► (32,)  ─┘
  security_context (18,)  ──┘

Output heads (unchanged):
  direction_head    (128,) → (3,)   logits
  return_head       (128,) → (3,)   regression
  confidence_head   (128,) → (1,)   sigmoid
```

### 9.2 ContextEncoder (new module)

```python
class ContextEncoder(nn.Module):
    """
    Encodes news + security context into a dense vector.
    Input:  (batch, 16 + 18) = (batch, 34)
    Output: (batch, embed_dim) = (batch, 32)
    """
    def __init__(self, news_dim=16, security_dim=18, embed_dim=32, hidden_dim=64):
        super().__init__()
        input_dim = news_dim + security_dim  # 34
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, embed_dim)
        self.dropout = nn.Dropout(0.2)

    def forward(self, news_ctx, security_ctx):
        x = torch.cat([news_ctx, security_ctx], dim=1)
        x = F.gelu(self.bn1(self.fc1(x)))
        x = self.dropout(x)
        x = F.gelu(self.bn2(self.fc2(x)))
        return self.fc3(x)
```

### 9.3 Modified CandleModel forward

```python
def forward(self, candles_5m, candles_15m, news_context, security_context):
    candle_fused = self.multi_res([candles_5m, candles_15m])        # (B, 128)
    context_embed = self.context_encoder(news_context, security_context)  # (B, 32)
    combined = torch.cat([candle_fused, context_embed], dim=1)      # (B, 160)
    # ... existing fusion MLP and three heads, with input_proj resized 128 → 160
```

### 9.4 Parameter budget

- Existing CandleModel: 132,103 parameters
- New ContextEncoder: ~5,000 parameters
- Resized fusion input projection (128→160): ~4,000 extra
- **v0.4 total: ~141,000 parameters** — still under the 200K target, well within RTX 4050 limits, <1ms CPU inference preserved

---

## 10. Training pipeline changes

### 10.1 Trainer modifications

`CandleTrainer.train_epoch` and `validate` need to:
- Read `news_context` and `security_context` from the batch
- Pass them through the model in the forward call
- Otherwise unchanged

### 10.2 Loss weighting consideration

Rare news categories (FDA approvals, bankruptcies, monetary policy events) will be heavily outnumbered by routine `earnings` and `other`. Without intervention the model will learn the dominant classes and ignore the rare-but-high-impact ones.

Two mitigations, applied in this order:

**A. Stratified sampling:** the DataLoader can use a `WeightedRandomSampler` that oversamples rare-category samples during training. The validation set stays untouched and represents true distribution.

**B. Category-weighted loss (optional):** scale the per-sample loss by `inverse_category_frequency`. Risk: instability if a rare category has very few samples.

Recommend starting with stratified sampling only. Add category-weighted loss only if direction accuracy on rare categories lags by >10 percentage points.

### 10.3 Reporting additions

The training report (`report.py`) should add:

- Per-news-category direction accuracy (15 + 'other' rows)
- Per-sector direction accuracy (11 rows)
- Per-cap-tier direction accuracy (5 rows)
- Joint heatmap: news_category × sector accuracy
- Joint heatmap: news_category × cap_tier accuracy

These are the diagnostics that will tell us whether the hypothesis is paying off — and *which* joint cells the model is learning vs. failing.

---

## 11. Inference changes — cerebellum.py

Both the US droplet's `neural` container and the HKEX `cerebellum.py` need updates.

### 11.1 ONNX export shape change

`torch.onnx.export` needs the new 4-input signature: `(candles_5m, candles_15m, news_context, security_context)`. Document the input names and expected shapes in `model_version.json`.

### 11.2 Cerebellum loading

`CandleModel` ONNX session at inference time needs to:
- Construct `news_context` from recent news in the `news` table (same logic as the dataset's `_build_news_context`)
- Construct `security_context` from the `securities` table for the symbol being scored
- Run inference with all four inputs
- Cache `security_context` per symbol (it changes weekly at most)

### 11.3 Backwards compatibility

The v0.3 ONNX model (2-input signature) should remain runnable during the transition. The coordinator reads `model_version.json` to determine which inference path to use. After v0.4 deployment and a validation period, v0.3 can be retired.

**Status (2026-05-23):** The HKEX `cerebellum.py` (v1.2.0) ships the version-branching scaffold ahead of the v0.4 ONNX. Concretely:

- `Cerebellum.__init__` reads `model_version.json` *before* constructing `CandleModel` and passes a parsed `(major, minor)` tuple in.
- `CandleModel.predict()` routes to `_predict_v03()` (existing path, unchanged) when `minor < 4` and to `_predict_v04()` when `minor >= 4`.
- `_predict_v04()` is a logged stub that returns `{"available": False, "reason": "v0.4 inference path not implemented (stub)"}`. This means a misdeployed v0.4 manifest fails closed (coordinator falls back to no-signal / Attention State Machine Mode 1) rather than corrupting outputs.
- `CandleModel._load()` emits a warning if the manifest version disagrees with the actual ONNX input count (e.g. manifest says `0.4` but the loaded ONNX exposes only 2 inputs).

Phase 9 of the implementation guide therefore narrows to: fill `_predict_v04()` with the news/security context builders and the 4-input `session.run` call. No structural refactor of `cerebellum.py` is required at deploy time.

---

## 12. Testing methodology

### 12.1 Test 1 — Distribution analysis (pre-training, cheap)

Before training the v0.4 model at all, populate the `context_regime_summary` table and verify that the hypothesis is supported by the data. Specifically:

- Compute `mean_return_5m`, `std_return_5m`, and direction class balance per `(news_category, sector, cap_tier)` cell
- Identify cells with sample_count > 100 (statistically meaningful)
- Run pairwise Kolmogorov-Smirnov tests on return distributions between cells
- **Pass criterion:** at least 5 pairs of well-populated cells show statistically distinguishable return distributions (p < 0.01)

If Test 1 fails, the hypothesis is wrong for this data and we should not proceed with v0.4. (Probability of failure: low, given the literature support.)

### 12.2 Test 2 — A/B comparison vs v0.3

Train v0.4 and v0.3 on the same time-window, evaluate on the same held-out validation period (chronologically last 20%).

- **Primary metric:** direction accuracy on full validation set
- **Secondary metric:** direction accuracy on each populated news category
- **Pass criterion:** v0.4 ≥ v0.3 + 5 percentage points on full set, AND v0.4 outperforms v0.3 on at least 8 of 15 categories

### 12.3 Test 3 — Production fruit

Post-deployment, measure prediction → outcome accuracy in the `production_outcomes` table, broken down by `(news_category, sector, cap_tier)`. The model is working if:

- Stop loss rate declines in the 30 days post-v0.4 vs. 30 days pre
- Direction accuracy on closed positions > 55%
- Confidence calibration improves (high-confidence predictions win more often than low-confidence ones)

This is Path 3 in the existing three-paths learning architecture — already designed, just needs the new reporting fields.

---

## 13. Migration plan

### 13.1 Phase order

1. **Schema migration** — add columns to `news` and `securities` tables (idempotent SQL, deployable today)
2. **Regex tagger** — backfill `news_category_*` for all historical headlines (single offline run)
3. **Security tagger** — backfill `sector` and `market_cap_tier` for all securities (one-off, can be manual + spreadsheet for the small active universe)
4. **Test 1 distributions** — populate `context_regime_summary`, validate hypothesis on real data
5. **Dataset v0.4** — implement `CandleDataset` extensions, verify samples look correct
6. **Model v0.4** — implement `ContextEncoder` and modified `CandleModel`
7. **Training run** — Test 2 A/B vs v0.3 baseline
8. **ONNX export + cerebellum updates** — both droplets
9. **Deployment** — SCP to US neural container and HKEX cerebellum
10. **Test 3** — production fruit measured over 30 days
11. **LLM tagger** (Phase 1.5) — only after v0.4 is proven, replaces regex for ambiguous cases

### 13.2 Rollback

Each step is reversible:
- Schema additions don't break v0.3 (new columns are nullable)
- v0.3 ONNX stays deployable
- `model_version.json` controls which model runs

### 13.3 Estimated effort

| Step | Effort | Owner |
|---|---|---|
| Schema migration | 1 hour | little_bro |
| Regex tagger + backfill | 1 day | Claude + little_bro |
| Security tagger | 0.5 day | manual + little_bro |
| Test 1 distributions | 0.5 day | Claude |
| Dataset v0.4 | 1 day | Claude |
| Model v0.4 | 0.5 day | Claude |
| Training run | 0.5 day (mostly waiting) | Craig laptop |
| ONNX export + cerebellum | 1 day | little_bro |
| Deployment | 0.5 day | little_bro |
| Test 3 measurement | 30 days passive | system |

Total active engineering: ~6 days; calendar time including production measurement: ~5 weeks.

---

## 14. Risks and open questions

### 14.1 Risks

**Sparse cells.** Many `(news, sector, cap_tier)` cells will have very few samples. The model can't learn what isn't there. Mitigation: the hierarchical taxonomy lets us fall back to coarser groupings (family-level news, sector-level only) for sparse cells.

**Tagging noise.** Regex classification will be wrong sometimes. Mitigation: `category_confidence` field lets us downweight uncertain tags during training; LLM stage 2 cleans up the worst cases.

**Concept drift in news categories.** The way news is framed evolves over time. A 2020 "AI partnership" headline reads differently than a 2026 one. Mitigation: weight recent data more heavily during retraining (already designed in Path 3).

**Adversarial categorization.** A bad actor could write misleading headlines to spoof the classifier. Mitigation: source tier is still a feature; tier 4 social sources are weighted down; the adversarial detection work in Phase 3 of the roadmap addresses this directly.

### 14.2 Open questions for Craig

- **Volatility regime tag — defer or include?** Adding it in v0.4 would bump security_context from 18 to 22 dims. The literature strongly supports it (volatility regime conditions trader composition). Cost is small. Recommendation: defer to v0.5 to keep v0.4 scope tight, but the schema should include the column from day one.
- **Sub-models — when to start?** Option 3 (per-context sub-models) is the most powerful approach but only works for well-populated cells. Recommendation: not in v0.4; revisit after Test 3 results identify which cells have the most data and the largest model gaps.
- **HKEX vs US first?** HKEX has the richer existing news taxonomy (the yaml) and is in production trading. US has higher data volume but no trades yet. Recommendation: develop on US data (more samples for training stability), validate on HKEX (better-tagged news).
- **Should we use FiLM (Option 2) instead of concatenation (Option 1) from the start?** FiLM is more expressive but harder to interpret. Recommendation: stick with Option 1 for v0.4; if v0.4 shows context is being learned but underutilized, upgrade to Option 2 in v0.5.

---

## 15. Files affected

### 15.1 catalyst-neural (laptop)

| File | Change |
|---|---|
| `storage/database.py` | Add migration for new columns; update `init_db()` |
| `storage/news_classifier_regex.py` | NEW — regex tagger |
| `storage/security_classifier.py` | NEW — sector/cap_tier tagger |
| `storage/context_regime.py` | NEW — populate `context_regime_summary` |
| `collectors/news_collector.py` | Tag categories at collection time |
| `training/dataset.py` | Add news_context and security_context to `CandleDataset` |
| `training/models.py` | Add `ContextEncoder`; modify `CandleModel.forward` |
| `training/trainer.py` | Update batch handling for new inputs |
| `training/report.py` | Add per-category, per-sector, per-tier diagnostics |
| `training/export_onnx.py` | Update export signature |
| `run.py` | New commands: `python run.py tag-news`, `python run.py tag-securities`, `python run.py distributions` |

### 15.2 catalyst-agent (US droplet) — **DEFERRED**

catalyst-agent is **shelved as of 2026-05-18** (root `CLAUDE.md` v3.0.0). The files below are listed for the eventual restart; no work happens here in v0.4.

| File | Change (when un-shelved) |
|---|---|
| `neural/cerebellum_loader.py` (or equivalent) | Update ONNX inputs |
| `neural/news_context_builder.py` | NEW — runtime context construction |

### 15.3 catalyst-international (HKEX droplet)

| File | Change | Status |
|---|---|---|
| `cerebellum.py` | Version-aware dispatch scaffolding (`_predict_v03` / `_predict_v04`); manifest-driven branching; ONNX input-count sanity check | **Landed 2026-05-23 (v1.2.0)** — v0.3 path unchanged, v0.4 path is a stub |
| `cerebellum.py::_predict_v04` | Fill stub with news_context (16-dim) + security_context (18-dim) builders and 4-input `session.run` | Pending — Phase 9 |
| `config/news_context.yaml` | Map existing 5-tier scheme to 15-category taxonomy (compatibility shim) | Pending — Phase 9 |

### 15.4 Documentation

| File | Change |
|---|---|
| `catalyst-neural-architecture-v0.3.md` | Mark as superseded for input section; reference this doc |
| `database-schema.md` | Add new columns to schema reference |
| `catalyst-news-taxonomy.md` | NEW — extracted standalone reference (the 15 categories with full keyword lists) |
| Root `CLAUDE.md` | Add this doc + its implementation guide to the document-family table |

---

## 16. Design principles preserved

This document does not alter the foundational principles of catalyst-neural:

1. **Raw data only at collection time.** News categories are computed offline, not as part of the price label.
2. **The network finds truth.** We are giving the model context features, not telling it how news *should* affect candles. The model still learns the mapping from data.
3. **Forward returns remain the only ground truth label.** Nothing in this document changes what the model is trained to predict.
4. **AI that uses software, not software that uses AI.** The categorization pipeline is a tool the AI uses; the trading judgment still lives in the model's learned representations.
5. **One source of truth maintained.** All four implementations (`catalyst-international`, `catalyst-neural`, `catalyst-agent`, `catalyst-research`) live in the `catalyst-trading-system` GitHub repo as of the 2026-05-18 consolidation. Hygiene rules in `Documentation/Implementation/catalyst-repo-hygiene.md` govern what gets committed. This doc lives in the GitHub repo.

---

## End of document
