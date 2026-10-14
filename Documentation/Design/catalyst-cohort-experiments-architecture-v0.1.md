# Catalyst Neural — Cohort Experiments Architecture

| Field | Value |
|---|---|
| Document | catalyst-cohort-experiments-architecture |
| Version | 0.2 (DRAFT) |
| Created | 2026-06-01 |
| Last updated | 2026-06-01 |
| Updated by | Craig + Claude |
| Status | Design review — not yet implemented |
| Supersedes | None — extends `catalyst-context-conditioned-architecture-v0.1.md` |
| Related | `catalyst-context-conditioned-architecture-v0.1.md`, `catalyst-neural-architecture-v0.3.md`, `catalyst-strategy-roadmap.md` |

## Revision history

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-06-01 | Craig + Claude | Initial draft — multi-cohort experimental design for v0.4 universe-selection question |
| 0.2 | 2026-06-01 | Craig + Claude | Bumped to 3 instances per strategy (15 cohorts total); enables one-way ANOVA across strategies; added third-instance definitions; expanded pattern-analysis section with variance decomposition and common-failure-mode detection |

---

## 1. Executive summary

The v0.4 context-conditioned model has been built (architecture v0.1, Phases 1–5 complete, Phase 6 retrained 2026-06-01 with real `news_context`). Two training runs have now established the floor:

| Run | Universe | News rows | Best val_loss | Dir acc |
|---|---|---|---|---|
| v0.3 baseline | 59 mixed (38 US + 21 HKEX) | 0 | 1.6524 | 40.83% |
| v0.4 zero-context | 59 mixed | 0 | 1.6552 | 40.78% |
| v0.4 with news | 59 mixed | 1,160 | 1.6785 | 41.18% |

v0.4 with real news produced the first positive directional delta we have seen (+0.35 pp over v0.3), but the Test 2 gate requires +5 pp. The 0.35 pp lift is plausibly a strong per-symbol effect averaged across a training set where 90%+ of samples still carry zero news context. **The hypothesis is not failing — the universe is.** The 59-symbol universe is too small, too sector-mixed, and too noisy to discriminate between "the model architecture works" and "the model architecture does not work."

This document specifies an experimental design for answering the universe question rigorously: **run 10 training cohorts of 150 securities each, varying how the 150 are selected, and compare results under a multiple-testing-corrected statistical framework.** The user's intuition that volatility is the central marker of market interest is preserved as one of the five grouping strategies tested, alongside four alternatives the literature suggests are competitive.

The deliverable is not "a better model." It is **a defended answer to: what should the training universe look like?**

---

## 2. Motivation

### 2.1 What v0.4 told us

The v0.4 with-news run produced a real positive signal (+0.35 pp dir_acc, p < 0.05 under a two-proportion z-test on 40,677 validation samples), but small and from the wrong place. Of the 40,677 validation samples, only the subset whose `(symbol, timestamp)` was within 4 hours of a classified headline for that symbol received non-zero `news_context`. With 1,160 classified rows across 7 covered US symbols over 5 months, the news-touched fraction of the validation set is in single digits.

What we have learned is therefore: **on the 5–10% of samples where news context is real, v0.4 likely beats v0.3 by considerably more than 0.35 pp.** What we have not learned is whether v0.4 is the right architecture for the trading system, because we cannot disentangle architecture quality from universe sparsity at this scale.

### 2.2 The cohort question

The pivotal architectural question is no longer "does context conditioning work" but **"on which universe do we evaluate it"**. Three sub-questions:

1. **How many securities?** 59 is too few (signal dilution). 1,613 is too many (NewsAPI free tier caps at 100 req/day; HKEX has no free news coverage; effective sample uniqueness collapses). 150 is empirically tractable and matches the cohort size used in the Krauss et al. (2017) sector-arbitrage literature.

2. **How to choose the 150?** This is what 10 cohorts is for. Five candidate selection strategies (Section 4), each represented by 2 instances, gives 10 cohorts and 5 ways of saying "this is the right universe shape."

3. **How to compare?** Naively picking the cohort with the best validation accuracy is **backtest overfitting** (Bailey, Borwein, López de Prado & Zhu, 2014). Section 8 specifies a deflated-Sharpe + Probability-of-Backtest-Overfitting protocol.

### 2.3 Why "15 sets" (3 × 5)

Fifteen cohorts is the design point that buys us a real statistical methodology. The deflated Sharpe ratio penalty (Bailey & López de Prado, 2014) grows as `√(2 ln N)`: at N=15 the haircut is ≈ 2.32 standard errors (vs ≈ 2.15 at N=10 and ≈ 2.45 at N=20). The marginal cost of going from 10 to 15 trials is small in deflation terms, but the marginal *benefit* is substantial:

- **Three replicates per strategy unlock one-way ANOVA across strategies.** With 2 replicates we could only describe a within-strategy range; with 3 we can compute a within-strategy standard error and run an F-test (or Kruskal-Wallis if normality fails) on whether *strategy* is a significant source of variance in directional accuracy. This is the difference between "Strategy B looked good" and "Strategy B is statistically distinguishable from the rest at α = 0.05 after BH-FDR correction."
- **Within-strategy noise floor with three points instead of two.** A 2-point range is bounded by its endpoints; a 3-point sample gives a proper SE. If `var(C1, C2, C3) > var(A1, A2, A3, B1, B2, B3, D1, D2, D3, E1, E2, E3)`, the stratified-mix strategy is *more* unstable than the structured strategies — a counter-intuitive finding the 2-instance design could not detect.
- **The cost is free.** Each fit is ~6 min on RTX 4050; 75 fits is ~7.5 hours wall time on the laptop overnight. Compute is not the constraint; statistical rigour is.

---

## 3. Literature foundation

The design below draws on six well-established results in financial machine learning. Citations are given inline; full sources are listed in Section 15.

### 3.1 Universe selection as sample-uniqueness weighting

López de Prado, *Advances in Financial Machine Learning* (2018), Ch. 4 ("Sample Weights"), argues that when labels are constructed from overlapping forward windows — exactly our `forward_returns` table with 5m / 15m / 1h horizons — observations are non-IID and effective sample size collapses. He prescribes computing **average label uniqueness** and reweighting (sequential bootstrap) so each symbol-bar contributes proportional to its non-redundant information. *Application here:* the cohort design must report effective sample size, not raw bar count.

### 3.2 Generalist vs sector-specialist models

The strongest empirical work on equity ML pools across the full cross-section without sector partitioning:

- Krauss, Do & Huck (2017, *European Journal of Operational Research*) trained on the full S&P 500, reporting 0.45%/day pre-cost using a cross-sectional rank objective.
- Fischer & Krauss (2018, *EJOR*) extended this with LSTMs to comparable results.
- Gu, Kelly & Xiu (2020, *Review of Financial Studies*) used ~30,000 stocks and found that the dominant signals (momentum, liquidity, short-term reversal) are **sector-agnostic** — nonlinear interactions across the full cross-section, not sector slices, generate alpha.

*Application here:* the literature *prior probability* favours generalist (cross-sector) cohorts for short-horizon prediction. Sector-pure cohorts are a legitimate but unfavoured hypothesis. The experimental design must let the data overrule the literature, but we should not treat sector-specialist as the default expectation.

*Caveat:* none of these papers run a clean sector-specialist vs generalist ablation at intraday horizons. The intraday short-horizon question is genuinely under-studied.

### 3.3 Volatility-stratified cohorts

Cont (2001, *Quantitative Finance*) — the canonical "stylized facts" paper — established that volatility clustering and heavy tails are universal but their **magnitudes** differ across securities and regimes. A model trained on a cohort that mixes a quiet mega-cap with a meme stock sees a non-stationary input distribution and learns the mean of two regimes that resemble neither. Hamilton (1989, *Econometrica*) formalised this as regime-switching; Nystrup et al. (2020, *J. Risk Financial Management*) operationalised it for factor investing with hidden Markov models.

*Application here:* this directly supports Craig's intuition that volatility-tiered cohorts are worth testing. There is no consensus on whether (a) to train separate per-regime models or (b) to condition the model on a volatility feature — our v0.4 `security_context` already includes cap-tier (a coarse vol proxy), so this experiment will partly disentangle the two.

### 3.4 Cross-cohort comparison

The rigorous tool is **Combinatorial Purged Cross-Validation** (López de Prado, 2018, Ch. 7 and Ch. 12). Partition observations into N groups, test all C(N, k) splits, **purge** training labels whose forward windows overlap test labels, and **embargo** a buffer after each test fold. Pair this with two corrections:

- **Probability of Backtest Overfitting (PBO)** — Bailey, Borwein, López de Prado & Zhu (2014). Estimates the probability that the best-performing cohort would have been outperformed by the median on held-out data.
- **Deflated Sharpe Ratio (DSR)** — Bailey & López de Prado (2014, *Journal of Portfolio Management*). Corrects the Sharpe ratio for multiple-testing inflation. At N=10 cohorts the deflator is non-trivial but tractable.

*Application here:* Section 8 mandates CPCV + PBO + DSR as the comparison protocol. Raw validation accuracy is reported only as a secondary signal.

### 3.5 Sample-size requirements

There is no closed-form rule. The empirical benchmarks from cited papers:

- Krauss et al. (2017): ~500 symbols × ~20 years daily ≈ 2.5M observations
- Gu, Kelly & Xiu (2020): ~30,000 stocks × 60 years
- Our current run: 59 symbols × 4,000 bars × 3 horizons ≈ 700K observations, of which effective ≈ ?

López de Prado (2018, Ch. 4) cautions that the *effective* sample after overlap correction can be 1–2 orders of magnitude smaller than the raw count.

*Application here:* 150 symbols × intraday bars over current 5-month window easily exceeds Krauss et al's raw count. The binding constraint is **effective uniqueness** after purging — that is the number to monitor, not bar count.

### 3.6 Asset clustering before cohort assignment

Two competing streams:

- **Hierarchical Risk Parity (HRP)** — López de Prado (2016, *J. Portfolio Management*). Single-linkage agglomerative clustering on a correlation-distance metric `d(i,j) = √(½(1−ρ))` recovers a tree structure that gives correlation-balanced cohorts. HRP was designed for portfolio construction, not training-cohort assembly; applying it to cohort design is principled but novel.
- **Factor decomposition** — Fama & French (1993, 2015). Economically-motivated sorts on size × book-to-market × profitability × investment. Less data-driven, more interpretable.

*Application here:* one of the five grouping strategies (Strategy D) uses HRP-style correlation clustering. Sector-pure and stratified-mix strategies indirectly test the factor-decomposition alternative without committing to a particular factor model.

---

## 4. The grouping question

### 4.1 Five strategies

| ID | Strategy | One-line description | Hypothesis being tested |
|---|---|---|---|
| A | **Sector-pure** | All 150 from one GICS sector | Specialist > generalist; sector behaviour is the dominant regime |
| B | **Volatility-tiered** | All 150 from one realized-vol decile | Volatility regime is the dominant non-stationarity; quiet and loud names should not share a model |
| C | **Stratified mix** | Balanced across sectors × cap × vol tiers | Generalist literature is right; the cross-section is informative |
| D | **HRP cluster** | Drawn from one branch of correlation hierarchical clustering | Correlation structure (not sector labels) defines the true regime |
| E | **Pure mover** | Top 150 by realized vol regardless of sector | Volatility = interest = signal density; the rest is noise |

Strategies A through D are grounded in cited literature (Section 3). Strategy E is Craig's intuition direct: take the loudest 150 and ignore everything else.

### 4.2 Why 3 instances per strategy

Three instances per strategy gives 15 cohorts total and serves four purposes (one beyond what 2 instances could do):

1. **Within-strategy standard error.** A 3-point sample gives a proper SE per strategy. Cross-strategy claims of the form "Strategy B beats Strategy A at p < 0.05" require this — a 2-point range is insufficient.
2. **Discrimination at multiple instantiations.** A sector-pure cohort from Financials may behave very differently from Tech or Healthcare; the *average* tells us whether sector-specialisation as a strategy helps, not whether one particular sector happened to win.
3. **Multiple-testing budget remains tractable.** Deflated-Sharpe penalty at N=15 is `√(2 ln 15) ≈ 2.32`. At N=20 it would be 2.45. Fifteen is the sweet spot for our compute budget.
4. **One-way ANOVA becomes possible.** Three replicates per group is the minimum at which Kruskal-Wallis (non-parametric) or one-way F-test can detect strategy as a variance source. This is the single biggest analytical upgrade over the v0.1 design.

The instance triples within each strategy:

| Strategy | Instance 1 | Instance 2 | Instance 3 |
|---|---|---|---|
| A (sector-pure) | Tech (largest sector) | Financials (second largest) | Healthcare (third — distinct catalyst regime: FDA, trial readouts) |
| B (vol-tiered) | Top decile (loudest) | Fifth decile (mid-quiet) | Bottom decile (quietest) — *anti-test*: if B3 matches B1, vol is not signal |
| C (stratified) | Random stratified draw #1 | Random stratified draw #2 | Random stratified draw #3 (three points = real within-strategy SE) |
| D (HRP cluster) | Largest cluster from tree | Second-largest cluster | Third-largest cluster |
| E (mover/null) | Top 150 by realized vol | Mid-rank (vol rank 150–300) | Uniform random 150 (null baseline) |

Two of the third-instance choices are deliberately adversarial:

- **B3 (bottom-decile vol)** is the test of Craig's "volatility = market interest" hypothesis. If a cohort of the quietest names performs comparably to the loudest cohort (B1), then volatility is *not* the dominant marker of trainable signal. The hypothesis fails empirically and we update.
- **E3 (uniform random)** is the null baseline. If the null cohort performs comparably to every structured cohort, then no grouping strategy is adding value — the architecture is the bottleneck, not the universe.

A1/A2/A3 spanning Tech / Financials / Healthcare also tests whether sector-specialisation is *strategy-level* signal or just one-lucky-sector noise.

---

## 5. Cohort definitions

### 5.1 Realized volatility metric

Used by strategies B, D, E. Defined as:

```
σ(symbol, t) = stdev{ ln(close_t / close_{t-1}) : 5m bars in [t - 30 trading days, t] }
```

Computed daily, stored in a new column `securities.realized_vol_30d`. The metric uses 5m bars (high-frequency, captures intraday noise) and a 30-day window (long enough for stability, short enough to capture regime change). It is reported in annualized terms (`σ × √(78 × 252)`) for human readability but the raw 5m σ is what the cohort assignment uses.

### 5.2 Sector taxonomy

The 11-sector GICS-aligned taxonomy already in `securities.sector` (populated in Phase 3 of v0.4). No new schema needed.

### 5.3 Cap-tier taxonomy

The 5-tier classification already in `securities.market_cap_tier`. No new schema needed.

### 5.4 Cohort assignment rules

For each of the 10 cohorts, the assignment algorithm produces a list of (symbol, market) pairs subject to four hard constraints:

1. **Coverage**: symbol must have ≥ 1000 5m candles in the training window
2. **News-eligible**: market is US (HKEX has no free news; HKEX-only experiments deferred to a separate Phase)
3. **Non-degenerate**: ≥ 500 forward_returns rows with non-NULL `return_5m`
4. **Stability**: symbol's `realized_vol_30d` has been computed for ≥ 60 consecutive trading days (avoids freshly-listed names)

After filtering by these four constraints, each strategy applies its specific selection rule:

- **A (sector-pure)**: filter to one sector (Tech / Financials / Healthcare for instances 1/2/3), sort by `realized_vol_30d` desc, take top 150
- **B (vol-tiered)**: bucket by `realized_vol_30d` decile, take 150 random from one decile (top / fifth / bottom for instances 1/2/3)
- **C (stratified)**: enforce sector balance (≥10 from each of 11 sectors, then fill by random) and cap balance (≥20 each from {Mega, Large, Mid}, ≤30 from {Small, Micro}); three independent draws with distinct random seeds for instances 1/2/3
- **D (HRP cluster)**: compute correlation matrix of 5m returns over last 30 days for all eligible symbols, run single-linkage clustering on `d = √(½(1−ρ))`, take the largest / 2nd-largest / 3rd-largest cluster for instances 1/2/3; if cluster size > 150 take 150 random from within
- **E1 (pure mover)**: filter to all eligible, sort by `realized_vol_30d` desc, take top 150
- **E2 (mid-rank)**: filter to all eligible, sort by `realized_vol_30d` desc, take ranks 150–300
- **E3 (null baseline)**: filter to all eligible, take 150 by uniform random sample (fixed seed for reproducibility)

### 5.5 Cohort versioning

Each cohort is identified by a 6-tuple:

```
(strategy_id, instance_id, draw_date, realized_vol_snapshot_date,
 sector_filter, n_symbols)
```

Cohorts are immutable after a training run starts. A re-draw on a later date is a new cohort with a new tuple, not an update.

---

## 6. Training protocol

### 6.1 Identical pipeline across cohorts

Every cohort runs the same:
- Dataset: `CandleDataset` with `include_context=True`
- Model: `CandleModelV04` (144,935 params, no architectural changes)
- Trainer: `CandleTrainer` v0.4 dispatch
- Hyperparameters: defaults from `config.settings.TRAINING` — batch 64, LR 1e-3, AdamW, ReduceLROnPlateau, 100 max epochs, patience 15
- Hardware: laptop RTX 4050 6GB

Departing from defaults is forbidden during the cohort experiment. The whole point is to isolate the cohort effect; we cannot also tune hyperparameters or the results are uninterpretable.

### 6.2 Purged k-fold cross-validation

Per López de Prado (2018, Ch. 7), each cohort uses 5-fold CPCV with:

- **Purge**: training labels whose forward-return windows overlap the test fold's time range are dropped. With horizons up to 1h on 5m bars, purge window = max(1h, 12 bars) on each side of every test fold boundary.
- **Embargo**: an additional 1-day buffer after each test fold (`embargo_pct = 1/n_train_days`).

Five folds × 3 strategy instances × 5 strategies = 75 model fits per experiment cycle. At ~6 min per fit on RTX 4050, the full cycle is ~7.5 hours — overnight on the laptop.

### 6.3 Per-cohort artifacts

Each fold produces:

- A checkpoint `models/cohort_{cohort_id}_fold_{k}.pt`
- A stats JSON `models/cohort_{cohort_id}_fold_{k}_stats.json`
- A report HTML `models/cohort_{cohort_id}_fold_{k}_report.html`

The per-cohort aggregate is the **median across folds** of:

- `best_val_loss`
- `final_dir_acc`
- `per_horizon_mae`
- A new metric: `effective_sample_size` after purge

### 6.4 Identical news + security context across cohorts

The `news` table and `securities` context must be in the same state when all 10 cohorts run, otherwise inter-cohort comparison is invalid. The experiment requires a **snapshot freeze**: copy the live SQLite DB to a snapshot file, run all 10 cohorts against that snapshot, then unfreeze. The snapshot also records which symbols had non-zero `news_context` coverage so per-cohort news exposure is auditable.

---

## 7. Comparison methodology

### 7.0 Strategy-level analysis (new in v0.2)

With three replicates per strategy, the primary unit of analysis becomes the *strategy*, not the *cohort*. Each cohort is one observation; each strategy is a 3-observation group.

**One-way ANOVA (or Kruskal-Wallis).** Treat strategy ∈ {A, B, C, D, E} as the factor and per-cohort median val_loss (or dir_acc, separately) as the response. Test the null hypothesis "strategy has no effect on validation loss" at α = 0.05. If normality holds across the 15 observations (Shapiro-Wilk p > 0.1), use one-way F-test; otherwise Kruskal-Wallis. If the omnibus test rejects, run Tukey HSD (parametric) or Dunn's test (non-parametric) for pairwise strategy comparisons.

**Variance decomposition.** Partition total variance in val_loss into between-strategy and within-strategy components:

```
total_var = between_strategy_var + within_strategy_var
η² = between_strategy_var / total_var   # effect size of strategy
```

If η² < 0.10, strategy explains less than 10% of variance — universe choice is not the bottleneck. If η² > 0.40, strategy is a dominant factor and the winning strategy should be locked in.

**Within-strategy SE.** For each strategy, compute SE = stdev / √3. This is the minimum detectable cross-strategy difference. Cross-strategy comparisons smaller than 2 × (max within-strategy SE) cannot be claimed.

### 7.1 Primary signal — Deflated Sharpe per cohort

Each cohort's "Sharpe" in this context is interpreted as `(dir_acc − 33.3%) / std(dir_acc across folds)` — the directional accuracy lift over chance, normalised by the cross-fold standard error. The deflated version (Bailey & López de Prado, 2014) corrects for the N=10 trials:

```
DSR(cohort) = SR_observed(cohort) × √(1 − γ · SR_observed_mean × √(1 − γ_Z(N))) / σ_SR
```

where γ_Z(N) is the maximum expected Sharpe under the null at N trials. A cohort is "the winner" only if its DSR exceeds the 95% confidence threshold *after* the N=10 deflation.

### 7.2 Secondary signal — Probability of Backtest Overfitting

Bailey, Borwein, López de Prado & Zhu (2014) define PBO over the set of 10 cohorts as the probability that the in-sample best cohort underperforms the median out-of-sample. PBO is reported as a single scalar across the whole experiment. PBO > 0.5 means we have learned nothing; PBO < 0.2 means the best cohort is meaningfully best.

### 7.3 Tertiary signal — pairwise tests

For each pair of cohorts (i, j) the Diebold-Mariano test on the per-sample prediction errors (López de Prado, 2018, Ch. 14). The 45 pairwise p-values are Benjamini-Hochberg false-discovery-rate corrected at α = 0.05.

### 7.4 Qualitative signal — per-category accuracy

For the winning cohort and for the worst cohort, the existing `candle_stats` per-news-category accuracy breakdown is generated (this is Phase 5.5 work that was deferred from the v0.4 implementation). Two heatmaps:

- `news_category × dir_acc` — does the winner specifically beat the loser on the high-impact rare categories (regulatory_approval, bankruptcy, monetary_policy)?
- `sector × dir_acc` — does the winner have a sector concentration we should be aware of?

These do not affect the gate verdict but inform the *interpretation*.

### 7.5 Pattern analysis across all 15 cohorts (new in v0.2)

Beyond the strategy-level statistical tests, five exploratory analyses are run across the full 15-cohort × 5-fold = 75-fit grid. These are not gates — they are *learnings*.

**1. Cohort-metric correlations.** For each cohort, compute six descriptors:

- `median_realized_vol` — median `realized_vol_30d` across the 150 symbols
- `sector_entropy` — Shannon entropy of the sector distribution within the cohort
- `cap_entropy` — Shannon entropy of the cap-tier distribution
- `news_density` — fraction of training samples with non-zero `news_context`
- `mean_correlation` — mean off-diagonal of the 5m return correlation matrix within the cohort
- `effective_sample_size` — post-purge effective N (López de Prado uniqueness)

Then compute Spearman rank correlation between each descriptor and `dir_acc`. A high `news_density ↔ dir_acc` correlation would say: "news coverage is the bottleneck, regardless of grouping strategy." A high `mean_correlation ↔ dir_acc` would say: "homogeneous cohorts (HRP-style) work better."

**2. Sweet-spot detection.** Plot `dir_acc` vs `median_realized_vol` for all 15 cohorts. A monotonic relationship validates Craig's hypothesis; a U-shape would suggest there's an *optimal* volatility regime that's neither quietest nor loudest. A flat relationship rejects volatility as a driver.

**3. Common-failure-mode analysis.** For each validation sample (across all 15 cohorts × 5 folds), record which cohorts misclassified it. Samples misclassified by ≥80% of cohorts are the **model's blind spots** — independent of universe choice. Aggregate by (news_category, sector, cap_tier) to identify systematic blind spots. Example finding: "small-cap biotech under regulatory_approval news is misclassified by 14 of 15 cohorts" → architecture or label-definition problem, not a universe problem.

**4. Common-success-mode analysis.** Samples correctly classified by ≥80% of cohorts are the **easy baseline**. If easy samples dominate the dir_acc number, the apparent strategy differences may be illusory (everyone's getting the easy ones right and missing the same hard ones).

**5. Symbol-level transfer.** Many symbols appear in multiple cohorts (Strategy A1 Tech and Strategy E1 Top-vol will overlap heavily). For each symbol present in ≥3 cohorts, compute per-cohort dir_acc on just that symbol's samples and check variance. Low per-symbol variance across cohorts → the cohort doesn't change what the model learns about that symbol → the strategy mainly matters for *which symbols are in the training pool*, not for *how the model treats each symbol*. This is a key interpretive finding either way.

These five analyses are run automatically post-experiment and folded into the final report (Section 10, Phase 8 of implementation).

---

## 8. Cohort lifecycle and rotation

A static universe is what we are trying to avoid. The experimental design must specify how cohorts evolve.

### 8.1 When to re-rank symbols

`realized_vol_30d` is recomputed nightly for every active US security with sufficient candle history. The metric is stored with a date; older snapshots are kept for backtesting integrity. Rank changes do not retroactively change which symbols were in a cohort — cohorts are immutable.

### 8.2 When to redraw cohorts

Triggers for a fresh draw:

1. **Quarterly cadence** — a new 10-cohort batch every 90 days, regardless of regime.
2. **Regime change** — if the median `realized_vol_30d` across the eligible universe shifts by more than 1 standard deviation (computed over the trailing 6 months), trigger an immediate redraw.
3. **Coverage expansion** — when news API tier upgrades expand symbol coverage materially (e.g., adding paid Finnhub), trigger a redraw.

### 8.3 Cohort registry

A new SQLite table `cohort_experiments`:

```
CREATE TABLE cohort_experiments (
  cohort_id          TEXT PRIMARY KEY,    -- e.g., 'A1_2026Q2_v1'
  strategy_id        TEXT NOT NULL,        -- 'A'..'E_null'
  instance_id        INTEGER NOT NULL,
  draw_date          DATE NOT NULL,
  vol_snapshot_date  DATE NOT NULL,
  sector_filter      TEXT,
  symbols_json       TEXT NOT NULL,        -- list of (symbol, market) tuples
  n_symbols          INTEGER NOT NULL,
  median_val_loss    REAL,                 -- populated post-training
  median_dir_acc     REAL,
  deflated_sharpe    REAL,
  pbo_contribution   REAL,
  notes              TEXT
);
```

### 8.4 Versioning convention

Cohort IDs follow the pattern `{strategy}{instance}_{period}_v{revision}`, e.g.:

- `A1_2026Q2_v1` — sector-pure Tech, second-quarter 2026 draw
- `B2_2026Q2_v1` — vol-tiered mid-decile, second-quarter 2026 draw
- `E_null_2026Q2_v1` — null baseline

Revisions (`_v2`, `_v3`) are reserved for re-runs that fix a definitional bug, not for re-draws under the same rules.

---

## 9. Data requirements and preconditions

| Requirement | Current state | Blocker? |
|---|---|---|
| Realized vol metric column in `securities` | absent | Phase 1 of implementation adds it |
| ≥1000 5m candles per cohort symbol | 59 symbols meet this; need to expand collection to ~300+ US | Yes — collector must run for ≥1 month with broader watch list before Strategy A/D become viable |
| ≥500 forward_returns rows per symbol | covered for the 59-symbol universe | Will follow from candle collection |
| News context coverage | 1,160 rows, 7 symbols | Need ~50+ symbols with ≥30 news rows each before Strategies B/C/E are meaningfully news-conditioned |
| `securities.sector` populated | 1,532 of 1,613 rows | Adequate |
| `securities.market_cap_tier` populated | 1,532 of 1,613 rows | Adequate |
| Snapshot mechanism for DB freeze | absent | Phase 1 of implementation adds a `cp data/catalyst_neural.db snapshots/{date}.db` step |

The critical path: candle and news collection needs to run on a broader US universe for a meaningful period before Phase 3 of the cohort experiment becomes statistically valid. Estimate: **4 weeks of expanded collection** before first 10-cohort run.

---

## 10. Implementation phasing

Implementation will be specified in a separate document (`catalyst-cohort-experiments-implementation-v0.1.md`); the phasing skeleton is:

| Phase | Owner | Deliverable | Estimated effort |
|---|---|---|---|
| 1 | claude_assist | `storage/cohort_assignment.py`: realized-vol computation, sector/cap filters, all five strategy implementations | 1 session |
| 2 | claude_assist | Schema migration: `securities.realized_vol_30d`, `securities.realized_vol_snapshot_date`, `cohort_experiments` table | 1 session |
| 3 | craig_laptop | Expand candle + news collection to ~300 US symbols; run for 4 weeks to build coverage | 4 weeks calendar |
| 4 | claude_assist | `training/cohort_trainer.py`: wraps `CandleTrainer` with CPCV, embargo, per-cohort artifact emission | 1 session |
| 5 | claude_assist + GPU | First 15-cohort run on the expanded universe (~7.5 hours wall time, overnight) | 1 session + train time |
| 6 | claude_assist | Comparison analysis: DSR, PBO, pairwise DM, heatmaps; emit a `cohort_report.html` | 1 session |
| 7 | Craig + Claude | Decision: pick winning strategy, freeze it as v0.4.1 universe, move to Phase 7 of v0.4 implementation (ONNX export) | 1 session |

Phases 1, 2, 4 can be done immediately and in parallel with the 4-week collection window. Phases 5–7 cannot start until Phase 3 yields adequate news + candle coverage.

---

## 11. Success criteria

The cohort experiment succeeds (in the sense of "the next step is clear") if one of four outcomes obtains:

1. **A single strategy wins clearly** — one strategy's three cohorts all have DSR > 95% threshold, PBO < 0.2, and the one-way ANOVA/K-W omnibus test rejects the null at α = 0.05 with the winning strategy being the highest in pairwise comparisons (Tukey HSD or Dunn). We freeze that strategy as the v0.4.1 universe.
2. **Two strategies tie within noise** — DSR confidence intervals overlap but both are above threshold; ANOVA shows strategy is significant but post-hoc cannot separate the two. We pick the operationally simpler one (probably Stratified mix C, which has the lowest data-engineering burden).
3. **Volatility hypothesis confirmed but not via the structured strategies** — B3 (bottom decile) performs materially worse than B1 (top decile) AND E1 (pure top-vol) outperforms E3 (random null); together these establish that vol is a real driver even if no single strategy dominates. Adopt vol-rank-filtered universes for v0.4.1.
4. **No strategy beats the null** — E3 is within noise of every structured strategy AND the ANOVA omnibus fails to reject. We conclude the universe is not the bottleneck, and revisit the v0.4 architecture or the news-coverage breadth.

Outcomes 1, 2, 3 produce a v0.4.1 production candidate. Outcome 4 returns us to the architecture drawing board.

---

## 12. Stop conditions

The experiment **stops early** (does not complete all 10 cohorts) if any of these are detected during Phase 5:

- **Compute budget exceeded** — total wall time > 12 hours. Indicates a hyperparameter or batching bug; do not just buy more compute.
- **Effective sample size collapse** — post-purge effective sample drops below 30K on any cohort. The cohort definition is too narrow; the strategy is operationally infeasible at this universe size.
- **News coverage degenerate** — ≥ 4 of the 10 cohorts have `news_context` zero on > 95% of samples. Cancel the experiment; resume Phase 3 (expand coverage) before retrying.
- **Identical results across cohorts** — if cohorts 1–4 all converge to within 0.1 pp of each other, the architecture is not sensitive to universe choice and the experiment cannot answer the question we are asking.

---

## 13. Open questions

The following are deliberately *not* resolved by this document — they require either data we do not have or methodological choices Craig wants to make explicitly.

1. **Should HKEX be included?** Excluded from this experiment because the free news APIs do not cover Hong Kong. A separate "HKEX-only, no news context" cohort study would test whether v0.4 architecture (security context only) helps even without news — a useful sub-experiment, deferred.

2. **Realized vol vs implied vol.** This document uses realized historical vol. Options-derived implied vol (from CBOE or similar) is forward-looking and arguably better signal, but adds an API dependency and a free-tier constraint. Deferred.

3. **Multi-task training across cohorts.** Could we train one model with cohort-ID as a context feature, jointly across all 10? Gu, Kelly & Xiu (2020) would suggest yes. This would change the experiment from "which cohort wins" to "which cohort produces the best cohort-aware joint model." Not in scope for v0.4.1; potential v0.5 question.

4. **Walk-forward over CPCV.** CPCV is more rigorous but more expensive. Pardo-style walk-forward analysis is the cheaper alternative. If Phase 5 wall-time exceeds budget, falling back to walk-forward is acceptable but should be flagged.

5. **Per-strategy retraining cadence.** If Strategy A wins, how often do we redraw within Strategy A? Quarterly is the default in Section 8 but a fast-vol-regime market may demand monthly. Empirical question for the v0.4.1 production phase.

---

## 14. Mission alignment

The cohort experiment exists because we are trying to deploy an algorithmic trading system to fund a mission. Every additional layer of rigour (CPCV, deflated Sharpe, PBO) is overhead. The justification: **a system that ships overfit results does not fund the mission — it bleeds capital.**

The pre-v0.4 weekly retrains have already produced three months of negative P&L on the intl droplet (`-3.7K HKD net Mar–May 2026`, per the 2026-05-28 trading status review). That loss is the cost of *not* doing this kind of statistical hygiene earlier. The cohort experiment is, in plain terms, a one-time investment of ~5 hours of GPU time + ~4 weeks of collection to ensure the next version we ship to production is grounded in evidence and not the most-flattering-looking validation run.

> *"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

---

## 15. Sources

- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. [https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)
- Bailey, D. H., Borwein, J. M., López de Prado, M. & Zhu, Q. J. (2014). The Probability of Backtest Overfitting. SSRN 2326253. [https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253)
- Bailey, D. H. & López de Prado, M. (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality. *Journal of Portfolio Management* 40(5).
- Krauss, C., Do, X. A. & Huck, N. (2017). Deep neural networks, gradient-boosted trees, random forests: Statistical arbitrage on the S&P 500. *European Journal of Operational Research* 259(2): 689–702.
- Fischer, T. & Krauss, C. (2018). Deep learning with long short-term memory networks for financial market predictions. *European Journal of Operational Research* 270(2): 654–669.
- Gu, S., Kelly, B. & Xiu, D. (2020). Empirical Asset Pricing via Machine Learning. *Review of Financial Studies* 33(5): 2223–2273.
- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. *Quantitative Finance* 1(2): 223–236.
- Hamilton, J. D. (1989). A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle. *Econometrica* 57(2): 357–384.
- Nystrup, P., Lindström, E., Pinson, P. & Madsen, H. (2020). Regime-Switching Factor Investing with Hidden Markov Models. *Journal of Risk and Financial Management* 13(12): 311.
- López de Prado, M. (2016). Building Diversified Portfolios that Outperform Out of Sample. *Journal of Portfolio Management* 42(4): 59–69. (Hierarchical Risk Parity)
- Fama, E. F. & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics* 33(1): 3–56.
- Fama, E. F. & French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial Economics* 116(1): 1–22.
- Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies*, 2e. Wiley. (Walk-forward analysis lineage)

---

*Craig + Claude — The Catalyst Family*
*2026-06-01*
