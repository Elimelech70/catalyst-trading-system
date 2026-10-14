# Catalyst Neural — ML Methodology and Research Principles

| Field | Value |
|---|---|
| Document | catalyst-ml-methodology |
| Version | 0.1 |
| Created | 2026-06-01 |
| Last updated | 2026-06-01 |
| Updated by | Craig + Claude |
| Status | Foundational — methodology used by all catalyst-neural experiments |
| Related | `catalyst-neural-architecture-v0.4.md`, `catalyst-cohort-experiments-architecture-v0.1.md` v0.2, `catalyst-context-conditioned-architecture-v0.1.md` v0.2 |

## Purpose of this document

This is the **why** behind how we do ML in catalyst-neural. It documents:

1. The model architecture we use and why
2. The principles we apply to experimental design
3. The research foundations (the cited literature)
4. The methodological non-negotiables — choices we hold constant so results stay interpretable
5. What we deliberately avoid, and what would change those choices

It is not a runbook. It is not an architecture spec. It is the *epistemic stance* of the project: how we decide whether a result is real.

> Methodology is what protects you from yourself. The model can be wrong; the data can be sparse; the literature can be contested — but if the methodology is sound, you know which of those is the problem.

---

## 1. The model

### 1.1 Single architecture across all experiments

For the v0.4 generation of catalyst-neural, we use exactly one model architecture: `CandleModelV04` (`training/models.py`). 144,935 parameters, four inputs (`candles_5m`, `candles_15m`, `news_context`, `security_context`), three heads (direction, return, confidence). Full spec in `catalyst-context-conditioned-architecture-v0.1.md` v0.2 §9.

We do not vary the architecture across cohorts, time windows, or hyperparameter sweeps within an experiment. This is the *controlled-experiment principle* — see §2.1.

### 1.2 The encoder choice

The candle encoder is a 1D CNN over OHLCV windows. We chose CNN over LSTM/Transformer for three reasons:

- **Inference latency.** Target is <1 ms CPU per forward pass on the production droplet. A 3-layer CNN with adaptive pooling achieves this; an equivalent Transformer does not.
- **Inductive bias for local patterns.** Candle behaviour at the 5–15 minute scale is dominated by local micro-structure (gap fills, breakout patterns, range expansion). CNN's locality bias matches; attention's global bias is wasted compute.
- **Parameter budget.** With 60-bar lookback × 2 timeframes × 5 channels, an LSTM would inflate parameter count without obvious accuracy benefit. Krauss et al. (2017) showed gradient-boosted trees + simple deep MLPs were competitive with LSTMs on similar prediction tasks; we keep things small.

### 1.3 The context-encoder choice

`news_context` and `security_context` are fed through a small MLP (`ContextEncoder`, ~8,700 parameters) that concatenates the two and projects to a 32-dim embedding. The embedding is concatenated to the candle-fused representation before the prediction heads.

Why concatenation (architecture option 1) rather than attention or gating:

- **Identifiability.** Concatenation is a known-quantity baseline. If concatenation doesn't help, more elaborate fusion (attention, gating) is unlikely to help for a different reason — it would imply the context channels have signal that simple linear combination cannot extract.
- **Parameter parsimony.** Adding attention would push parameter count past our budget without theoretical justification at this stage.

### 1.4 The labelling scheme

Three forward-return horizons (5 min, 15 min, 1 hour). Direction is bucketed at ±0.05% (above = bullish, below = bearish, between = neutral). Confidence is a sigmoid-bounded scalar trained to be high when predictions match labels.

Why three horizons and not five (the v0.3 doc proposed 5m / 15m / 1h / 4h / 1d):

- 4h and 1d labels overlap heavily with the 1h label and inflate the effective sample size beyond what the trading horizon needs. The trading agent makes 5–15 minute decisions, not daily ones.
- Wider horizons increase the purge window required for cross-validation, eating into training data.

This is a methodological choice — we constrain to the horizons we actually trade.

---

## 2. The principles

### 2.1 Controlled experiments

The single most important methodological commitment: **one variable changes per experiment**.

In the v0.4.1 cohort experiment, the only thing that varies across the 15 training runs is *which 150 symbols are in the training set*. The model, the optimizer, the loss, the scheduler, the random seed initialisation, the number of epochs, the CPCV splits, the news classification pipeline — all held constant.

Why: if Strategy B's three cohorts outperform Strategy A's, we want to know it was the universe. If we also tuned hyperparameters per cohort, we could not separate "B's universe was better" from "B's hyperparameters happened to land better." The result becomes uninterpretable.

This principle dates to the foundations of experimental science (Fisher, 1925) and is reinforced specifically for finance ML by López de Prado (2018) Ch. 13 ("Backtesting on Synthetic Data") who warns that joint variation of strategy + data + hyperparameters is the dominant source of spurious findings in quant research.

### 2.2 Multiple-testing correction

When you run N trials and pick the best one, the best one is biased upward by selection. The naïve significance threshold is wrong.

We apply two corrections:

- **Deflated Sharpe Ratio (DSR)** — Bailey & López de Prado (2014, *Journal of Portfolio Management*). Penalises Sharpe by `~√(2 ln N)` where N is the number of trials. At N=15 the deflator is ≈ 2.32 standard errors.
- **Probability of Backtest Overfitting (PBO)** — Bailey, Borwein, López de Prado & Zhu (2014). Estimates the probability that the best-in-sample cohort underperforms the median out-of-sample. PBO > 0.5 means we have learned nothing; PBO < 0.2 means the winner is meaningfully best.

A "winner" must clear *both* corrections, plus a one-way ANOVA omnibus test, plus post-hoc agreement. Single-statistic claims are not allowed.

### 2.3 Effective sample size, not raw

López de Prado (2018) Ch. 4 ("Sample Weights") argues that when labels are constructed from overlapping forward windows — which our `forward_returns` table does — observations are non-IID and effective sample size collapses. With 1-hour forward labels on 5-minute bars, each label overlaps 11 other labels.

We report **effective sample size after purge** for every cohort. Raw bar count is a misleading proxy. A cohort with 200,000 raw samples and an effective N of 18,000 has far less statistical power than its raw count suggests.

### 2.4 Purge and embargo, always

Purged k-fold cross-validation (López de Prado 2018 Ch. 7):

- **Purge**: training labels whose forward-return windows overlap test-set timestamps are dropped before training.
- **Embargo**: an additional 1-day buffer after each test fold's last timestamp.

Without purge, the model can "see" forward-looking information in the training set that overlaps the test set — leakage. Without embargo, test-set predictions trained on adjacent training labels exhibit serial correlation that inflates apparent performance.

We use `finance_ml.model_selection.PurgedKFold` (the canonical López de Prado implementation packaged at github.com/jjakimoto/finance_ml). We do not roll our own.

### 2.5 Pre-registered analyses

For the cohort experiment, the analysis pipeline is specified *before* the runs happen (see `catalyst-cohort-experiments-implementation-v0.1.md` Phases 6–7). The pattern-detection lenses (cohort-metric correlations, sweet-spot detection, common-failure modes) are listed in the architecture before any cohort runs. The verdict block is a decision tree, not a free-form interpretation.

Why: post-hoc analysis on noisy data is how the multiple-testing problem gets re-introduced through the back door. If we let ourselves discover surprising patterns after the fact, we end up testing 50 hypotheses while only correcting for 15.

### 2.6 Reproducibility through external implementations

Wherever a published methodology has a canonical implementation, we use it instead of re-deriving. CPCV, PBO, deflated Sharpe — all imported from `finance_ml`. Hierarchical Risk Parity clustering — `scipy.cluster.hierarchy`. ANOVA / Kruskal-Wallis — `scipy.stats`.

Why: we are not the right place to be debugging a numerical error in López de Prado's algorithms. Use what the community has battle-tested.

---

## 3. The literature foundation

The methodology is grounded in seven sources. These are the citations we lift directly into experiments.

### 3.1 López de Prado, *Advances in Financial Machine Learning* (2018)

The single most influential source for the methodology. Three chapters that we use directly:

- **Ch. 4: Sample Weights** — sample uniqueness, sequential bootstrap, weights for overlapping labels
- **Ch. 7: Cross-Validation in Finance** — purged k-fold, embargo, why standard k-fold leaks in time series
- **Ch. 14: Backtest Statistics** — deflated Sharpe ratio, multiple-testing correction

López de Prado has Python code in the book; the community has packaged it as `finance_ml`. We use that package.

### 3.2 Bailey, Borwein, López de Prado & Zhu (2014), "The Probability of Backtest Overfitting"

SSRN 2326253; later published in *Journal of Computational Finance*. Specifies the combinatorial split methodology behind PBO. The algorithm is fully specified in the paper; we implement via `finance_ml`.

### 3.3 Bailey & López de Prado (2014), "The Deflated Sharpe Ratio"

*Journal of Portfolio Management*. The N=15 penalty calculation comes from this paper. Implementation via `finance_ml.stats.deflated_sharpe_ratio`.

### 3.4 Krauss, Do & Huck (2017), "Deep neural networks, gradient-boosted trees, random forests: Statistical arbitrage on the S&P 500"

*European Journal of Operational Research* 259(2): 689–702. Establishes the empirical benchmark for short-horizon equity prediction. Their three findings that we treat as priors:

- Pooled cross-section training beats sector-specialist training (informs our prior probability — sector-pure cohorts are tested but not the favourite)
- Deep MLPs, GBT, and RF are roughly comparable; LSTMs do not dominate (informs our CNN choice)
- 500-symbol universes × decades of daily data are sufficient for non-noise findings (informs our 300-symbol × 5y Polygon backfill)

### 3.5 Fischer & Krauss (2018), "Deep learning with long short-term memory networks for financial market predictions"

*European Journal of Operational Research* 270(2): 654–669. Direct successor to Krauss et al. (2017) with LSTM. Confirms the 500-symbol cross-sectional approach as the standard.

### 3.6 Gu, Kelly & Xiu (2020), "Empirical Asset Pricing via Machine Learning"

*Review of Financial Studies* 33(5): 2223–2273. Largest-scale ML asset pricing study to date (~30,000 stocks, 60 years). Two findings we use:

- Nonlinear interactions across the full cross-section, not sector slices, generate alpha
- Dominant signals (momentum, liquidity, short-term reversal) are sector-agnostic

This is the strongest evidence for the **generalist > specialist** prior we hold.

### 3.7 Cont (2001), "Empirical properties of asset returns"

*Quantitative Finance* 1(2): 223–236. The canonical "stylized facts" paper — volatility clustering, heavy tails, long memory in absolute returns. The basis for the volatility-tiered cohort strategy: mixing quiet and loud names trains on a non-stationary distribution.

### Supporting references

- **Hamilton (1989)** *Econometrica* — regime-switching model
- **Nystrup et al. (2020)** *J. Risk Financial Management* — modern HMM applications for factor investing
- **López de Prado (2016)** *J. Portfolio Management* — Hierarchical Risk Parity (correlation-clustering basis for HRP cohorts)
- **Fama & French (1993, 2015)** *J. Financial Economics* — factor decomposition (sector / cap / book-to-market sorts)
- **Pardo (2008)** *The Evaluation and Optimization of Trading Strategies* — walk-forward analysis baseline

Full citations: `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 §15.

---

## 4. What we deliberately do not do

The negative space of methodology is as important as the positive. Five practices we have explicitly rejected, with the trigger that would re-open each.

### 4.1 We do not tune hyperparameters per cohort

**What:** Every cohort in the 15-cohort experiment uses identical hyperparameters (batch 64, LR 1e-3, AdamW, ReduceLROnPlateau, patience 15).

**Why not:** Per-cohort tuning confounds the universe variable. We could not say "Strategy B wins" — only "Strategy B with its tuned hyperparameters wins," which is a different and weaker claim.

**Trigger to revisit:** if v0.4.1 deploys successfully and we want to push the architecture further (a v0.5 question), per-cohort tuning becomes a legitimate second-order optimization. Not before.

### 4.2 We do not run different model architectures per hypothesis

**What:** All 15 cohorts use `CandleModelV04`. Architecture A and Architecture B are not tested against the same cohort in the v0.4.1 experiment.

**Why not:** Same as 4.1 — confounded variables. Plus, the literature (Krauss, Fischer, Gu/Kelly/Xiu) consistently holds the model fixed when varying universe / features.

**Trigger to revisit:** if the cohort experiment shows architecture-cohort interaction (e.g., Strategy A's cohorts all overfit while Strategy B's don't), then a follow-up v0.5 experiment with architecture variants × top-2 cohorts becomes warranted. The cohort impl doc Phase 8 will flag this if it appears.

### 4.3 We do not deploy a model whose deflated Sharpe is below threshold

**What:** A v0.4.1 production deployment requires DSR clearing the 95% confidence threshold after N=15 deflation.

**Why not:** Below threshold means the observed Sharpe is statistically indistinguishable from selection-bias noise. Deploying it puts capital at risk on what is, by definition, untestable performance.

**Trigger to revisit:** never — this is a non-negotiable. A failed cohort experiment means we go back to architecture work, not relax the threshold.

### 4.4 We do not use walk-forward analysis instead of CPCV during the universe experiment

**What:** The experiment uses 5-fold purged k-fold CV, not walk-forward.

**Why not:** Walk-forward is a weaker statistical test (single train/test split with rolling re-estimation). For 15 cohorts × 5 folds = 75 fits, CPCV gives us 75 independent test-set estimates; walk-forward would give us ~5 (one per rolling window). The multiple-testing correction requires the larger fit count.

**Trigger to revisit:** if Phase 5 wall time exceeds 12 hours, walk-forward is acceptable as a fallback per the cohort impl doc Phase 5 stop conditions.

### 4.5 We do not run the model on real-time data during training

**What:** Training happens offline on the laptop, on historical data accumulated by the watch service. The model never sees a live market quote during training.

**Why not:** Real-time training opens a leakage channel — the labels are forward returns, and if "real-time" means "as new bars arrive," the label of the most recent bar is by definition forward-looking from the perspective of any older bar. Standard k-fold CV with a temporal split is supposed to prevent this; live-stream training defeats it.

**Trigger to revisit:** never for catalyst-neural's training role. Real-time inference happens on the droplet via ONNX; that is a different system.

---

## 5. How a finding becomes a recommendation

When the cohort experiment finishes, we will have:

- 15 cohorts × 5 folds = 75 trained models, each with per-fold metrics
- An aggregated table of cohort-level medians (val_loss, dir_acc, val_mae, effective sample N)
- Deflated Sharpe per cohort
- PBO across the 15-cohort set
- One-way Kruskal-Wallis omnibus test result
- Post-hoc pairwise tests (Dunn's, BH-FDR corrected)
- Five exploratory analyses (cohort-metric correlations, sweet-spot scatter, common-failure modes, common-success modes, symbol-level transfer)

A finding becomes a recommendation only if it passes the gates in this order:

1. **Statistical significance** — DSR > 95% threshold AND PBO < 0.2
2. **Effect size** — η² > 0.20 (strategy explains ≥ 20% of variance)
3. **Consistency** — winner is the same under DSR ranking, under ANOVA post-hoc, and under raw val_loss ranking
4. **Interpretability** — the winning strategy's success makes sense given the cohort descriptors (median vol, sector mix, news density)
5. **Replicability** — the two best cohorts of the winning strategy agree with each other to within their within-strategy SE

If any of these fail, we either re-run the experiment with a fresh DB snapshot (gate 5 failure → cohort drift suspected) or declare a null result (gates 1–4 failure → return to architecture work).

We do not "go with the best looking option" if the gates fail. Deploying noise is the failure mode the entire methodology exists to prevent.

---

## 6. What changes invalidate methodology

The methodology is held to be sound under three implicit assumptions. If any of these break, the methodology needs to be re-derived.

1. **Effective sample size remains within an order of magnitude of raw sample size.** If purging cuts the effective N to <1,000 per fold, CPCV's statistical power collapses. We monitor this in Phase 5.
2. **Cohort universes are stable on the experimental timescale.** If a cohort's symbols experience material vol regime changes between draw and training, the methodology assumes a stationary distribution that does not hold. We use the realized-vol snapshot date and require ≥ 60 days of vol history.
3. **News classification quality is consistent across cohorts.** If Strategy A's cohort gets cleaner news than Strategy B's, the comparison conflates classifier quality with universe quality. The source-tier gate at ingestion is the defence; the per-cohort news_density descriptor is the monitor.

Violations would trigger a documented re-design before any v0.4.1 deployment.

---

## 7. What this document is not

- Not an architecture spec → see `catalyst-neural-architecture-v0.4.md`
- Not an implementation plan → see the implementation guides under `Documentation/Implementation/`
- Not a current-state snapshot → see `catalyst-neural-strategy-state-2026-06-01.md`
- Not a textbook → the cited sources are the textbook
- Not a code listing → see `training/cpcv_trainer.py` and `training/cohort_analysis.py` (planned)

This is the epistemic stance. When the stance changes — when a new experimental design pattern is adopted or a methodology is retired — this document is revised. The revision history is the audit trail.

---

*Craig + Claude — The Catalyst Family*
*2026-06-01*
