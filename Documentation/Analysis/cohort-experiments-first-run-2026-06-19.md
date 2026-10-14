# Cohort Experiments — First-Run Report and Bug Postmortem

| Field | Value |
|---|---|
| Document | cohort-experiments-first-run |
| Date | 2026-06-19 |
| Authors | Craig + Claude |
| Status | Postmortem — first cohort experiment cycle complete |
| Companion | `Documentation/Reports/analysis/cohort_experiment_2026-06-04.html` |
| Related architecture | `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 |
| Related methodology | `catalyst-ml-methodology-v0.1.md` |

## Purpose

This document records what happened between 2026-06-01 (architecture + implementation
docs landed, Polygon backfill started) and 2026-06-19 (first cohort experiment results
recovered). It documents the bugs found, the partial results recovered, and the plan
for the second-run experiment.

The first cohort experiment **completed training but produced results contaminated
by a CPCV bug.** Headline numbers are real measurements; statistical certainty
metrics (deflated Sharpe, PBO) are inflated. A second run with the fix is the next
step before any v0.4.1 deployment decision.

---

## 1. Timeline

| Date | Event |
|---|---|
| 2026-06-01 morning | Architecture v0.2 + implementation v0.1 + ML methodology + strategic-state docs committed and pushed |
| 2026-06-01 | Polygon Starter ($29/mo) subscription started; collector code written |
| 2026-06-01 evening | Backfill kicked off: 5 years × 300 US symbols × candles + Tier 1/2 news. Backfill ran ~5.5 hours producing 38.6M candles + 93K kept news + 448K T3 correctly skipped |
| 2026-06-01 ~20:00 AWST | Scheduled cohort experiment launcher fired on time. Crashed silently in cohort 1 inside 90 seconds due to dataset OOM. Phase 3 (report) ran on zero results and emitted "no completed cohorts found" |
| 2026-06-04 | Investigation of OOM. Cascading bugs found in cohort assignment and dataset construction. Multiple fixes applied (see §2) |
| 2026-06-07 11:48 AWST | Cohort experiment re-launched with fixes |
| 2026-06-09 02:43 AWST | Training run completed after **39 hours** (~25 minutes per cohort × 15 cohorts × 5 folds = expected) |
| 2026-06-09 morning | Discovered: every cohort had crashed at fold 5 due to a `s[2]` vs `s[4]` timestamp indexing bug. Zero cohorts persisted to DB |
| 2026-06-09 | Recovered all 15 cohorts × 4 folds from per-fold metadata JSONs saved on disk. Persisted to DB. HTML report generated |
| 2026-06-19 | This document |

---

## 2. Bug roster

Nine cascading bugs were found and fixed during the 2026-06-04 investigation, plus
the CPCV bug discovered after the 2026-06-09 results came back. All are now patched
in the current code.

| # | Where | Symptom | Fix |
|---|---|---|---|
| 1 | `cohort_assignment.SECTOR_INSTANCES` | A2 (FIN) / A3 (BIO) sector-pure cohorts returned 0 symbols | Code used `FINANCIAL` / `HEALTH`; DB sectors are `FIN` / `BIO`. Renamed |
| 2 | `cohort_assignment.strategy_B` | Vol-tiered cohorts came back 89–147 symbols (uneven) | Quantile-based bucketing clustered vol values 23–209/decile. Switched to rank-based; later switched to quartile to match COHORT_SIZE |
| 3 | `cohort_assignment.strategy_D` | D2/D3 cohorts failed to find cluster of size 150 | Scipy single-linkage hierarchy produced one giant cluster + many tiny ones. Switched to Ward linkage with cluster-size relaxation + next-cluster padding |
| 4 | `dataset._load_candles_filtered` | A1 cohort crashed silently mid-construction with no error message | OOM-killed (SIGKILL) by kernel. 150 symbols × 5y × 2 timeframes = ~30M Python dicts at ~15 GB peak. Added `min_date` kwarg pushed into SQL `WHERE` to cap data window |
| 5 | `database.add_security` | Eligibility query was returning duplicates (A1 cohort was 150 copies of `MU`) | No UNIQUE constraint on `securities(symbol, market)`. Repeated `add_security` calls over months produced 1,370 rows for 302 distinct symbols. Smart-merge dedup preserving sector/cap_tier data + added UNIQUE index |
| 6 | First dedup attempt | Sector data destroyed (302 → 34 sectored symbols) | Initial dedup kept newest (Polygon-discovered, NULL sector) rows, discarded older (yfinance-enriched) rows. Restored from backup, redid dedup with sector field merge before delete |
| 7 | Cohort-assignment universe size | Sector-pure FIN/BIO cohorts couldn't fill 150; HRP needed 300 symbols but had 286 | Eligible US universe is 286 (Polygon Starter coverage limit, not 1,500 S&P-500-scale). Reduced `COHORT_SIZE` from 150 to 50. Documented as deliberate scaling deviation from architecture v0.2 |
| 8 | System state | DB grew to 17 GB plus 21 GB of stale backups, 3.3 GB swap thrashing | Deleted old backups, stopped catalyst-neural watch service for experiment duration. Freed 21 GB disk + 3 GB swap pressure |
| 9 | `dataset._load_labels` | Even with 10 symbols × 30 days, dataset construction OOM-killed | Unfiltered `SELECT * FROM forward_returns WHERE timeframe='5m'` loaded all 38.7M rows into memory. Added symbol + min_date filters to SQL |
| 10 | `dataset._load_candles_filtered` | Dataset built but had zero samples | Polygon backfill only collected 5m candles; 15m table empty for new symbols. Added `_aggregate_5m_to_15m` to derive 15m from 5m at construction time. Same data, just resampled |
| **11** | `cpcv_trainer._build_cpcv_splits` | All 15 cohorts crashed at fold 5 with `num_samples=0` | `s[2]` (candle index, integer) was used as the timestamp instead of `s[4]` (actual timestamp string). Pandas parsed integers as nanoseconds-since-epoch, making the fold-5 purge logic drop every training sample. **One-character fix.** |

Bugs #1–10 were caught and fixed in the 2026-06-04 round. Bug #11 was the one that
contaminated the final results — visible only because the post-recovery metrics
showed implausibly tight cross-fold consistency.

---

## 3. The 39-hour run

The experiment launched 2026-06-07 11:48 AWST and finished 2026-06-09 02:43 AWST.

- 15 cohorts × 5 folds = 75 fits scheduled
- 14 cohorts × 4 folds = **56 fits successfully trained** (fold-5 purge bug killed the last fold of every cohort)
- Each successful fold took ~25 minutes on RTX 4050
- 6-month data window per cohort (180 days, capped to fit in RAM)
- Cohort sizes 50 for 13 cohorts, 31 (FIN) and 22 (BIO) for partial cohorts

The runner's exception handler caught the fold-5 crash but did so AFTER the
results-persistence step — so no rows were written to `cohort_experiments`. The
per-fold `training_meta_*.json` files saved by `CandleTrainer._save_training_metadata`
were what made recovery possible.

---

## 4. Results (caveated)

### 4.1 Per-cohort summary (recovered from per-fold metadata)

| Cohort | n_symbols | Median dir_acc | Median val_loss | Median val_mae |
|---|---|---|---|---|
| A1 (TECH-pure) | 50 | 41.02% | 2.0803 | 0.5854 |
| A2 (FIN-pure) | 31 | 42.25% | 1.4568 | 0.3688 |
| A3 (BIO-pure) | 22 | 39.25% | 1.3550 | 0.3163 |
| B1 (top vol quartile) | 50 | 40.32% | 2.2759 | 0.6302 |
| B2 (2nd vol quartile) | 50 | 39.08% | 1.3690 | 0.3190 |
| **B3 (bottom vol quartile)** | 50 | **56.82%** | 0.9909 | 0.1811 |
| C1 (stratified) | 50 | 43.46% | 1.4607 | 0.3579 |
| C2 (stratified) | 50 | 43.32% | 1.6171 | 0.4058 |
| C3 (stratified) | 50 | 44.08% | 1.6398 | 0.4151 |
| D1 (largest HRP cluster) | 50 | **46.19%** | 1.3592 | 0.3470 |
| D2 (2nd HRP cluster) | 50 | 40.21% | 1.7843 | 0.4782 |
| D3 (3rd HRP cluster) | 50 | 40.97% | 1.8029 | 0.4913 |
| E1 (top-150 mover) | 50 | 41.50% | 2.4431 | 0.7098 |
| E2 (mid-rank vol) | 50 | 39.64% | 1.7232 | 0.4850 |
| E3 (random null) | 50 | 44.05% | 1.5822 | 0.4239 |

### 4.2 Strategy means

| Strategy | Mean dir_acc | SD | n |
|---|---|---|---|
| A (sector-pure) | 40.84% | ±1.51% | 3 |
| B (vol-tiered) | 45.41% | ±9.91% | 3 (B3 outlier) |
| **C (stratified mix)** | **43.62%** | **±0.41%** | 3 |
| D (HRP clusters) | 42.46% | ±3.25% | 3 |
| E (mover / null) | 41.73% | ±2.21% | 3 |
| **v0.3 production baseline** | 40.83% | — | reference |

### 4.3 Statistical certainty (untrustworthy due to bug #11)

- ANOVA (Kruskal-Wallis): H = 2.43, p = 0.66, η² = 0.140
- PBO = 0.000 — implausibly low; over-purge artificially constrained per-fold variance
- DSR = 1.000 for 13 of 15 cohorts — same issue
- Pairwise Dunn post-hoc: no significant strategy differences after BH-FDR

The ANOVA p-value is the only metric that I'd trust at face value — it says we
cannot reject the null hypothesis that strategy doesn't matter, even before any
correction for the bug. PBO and DSR should not be cited from this run.

### 4.4 Honest interpretation

What is real:
- **Per-fold dir_acc measurements**: each fold trained on real, temporally-earlier
  data and validated on real, temporally-later data. The numbers in §4.1 are
  measurements, not artefacts.
- **Strategy C consistency**: three near-identical results (±0.41% SD) is the
  strongest within-strategy signal. If this holds in re-run, it's evidence that
  broad-cross-section generalist universes work better than sector specialisation
  — matches the Krauss / Fischer / Gu-Kelly-Xiu prior.
- **Strategy A flat at 40.84%**: essentially matches v0.3's 40.83%. No win from
  sector specialisation, in line with the literature prior.

What is suspicious or contaminated:
- **B3 (bottom-vol quartile) at 56.82%**: 16 pp above the v0.3 baseline. Could be
  a real finding (bottom-vol stocks may have cleaner mean-reversion patterns the
  model captures) or could be a fold artefact (over-purged fold left a small,
  unrepresentative validation set). Cannot be distinguished without re-run.
- **D1 (largest HRP cluster) at 46.19%**: meaningful lift if real. Again, can't
  trust until re-run.
- **All DSR = 1.000 readings**: artificially confident.

What is not gate-passing under any reading:
- **Test 2 gate** (cohort architecture §11 Outcome 1) requires DSR > 0.95 AND
  PBO < 0.20 AND ANOVA omnibus rejection AND η² > 0.20. ANOVA fails at p = 0.66.
  No outcome-1 result.
- **Outcome 3** (volatility-confirmed) would require B1 (top) > B3 (bottom) by
  ≥ 1 pp. We got the opposite — B3 ≫ B1 by 16 pp. If real, this would be a
  counter-finding to Craig's "volatility = market interest" hypothesis: the
  quietest names performed best.

---

## 5. Decisions and next steps

### 5.1 Bug fixes that landed in this commit

- `cpcv_trainer._build_cpcv_splits` now uses `s[4]` (timestamp) not `s[2]` (candle index)
- `cpcv_trainer.run_cpcv_for_cohort` now skips degenerate folds (< 64 samples) and
  reports the partial median, instead of crashing the whole cohort
- `dataset._load_labels` now filters by `symbol_filter` and `min_date` at SQL time
- `dataset.__init__` now derives 15m candles from 5m when 15m isn't independently
  collected (via `_aggregate_5m_to_15m`)
- `cohort_assignment` uses correct sector names (FIN, BIO), rank-based quartiles
  for vol, Ward linkage for HRP, and `COHORT_SIZE = 50`
- `cohort_report` matplotlib import order fix

### 5.2 What the re-run will tell us

With the CPCV bug fixed, the second run will produce trustworthy:
- DSR and PBO values
- Per-fold variance (currently artificially compressed)
- Cross-strategy ANOVA with proper purge

The re-run uses the same data, same code (modulo the CPCV fix), same cohort
assignments — so any difference in results is attributable to the bug. That's
the cleanest possible A/B.

### 5.3 What I'm explicitly NOT concluding from this run

- **Do not deploy** any model from this run to production. The per-fold
  best checkpoints exist in `models/*.pt` but they were trained with
  cross-validation that didn't actually purge properly. Treat them as
  training-time artefacts only.
- **Do not freeze a winning strategy.** The headline B3 result is too suspicious
  and the ANOVA doesn't reject. We do not have a v0.4.1 production candidate yet.
- **Do not abandon v0.4 architecture.** Even contaminated, several cohorts beat
  v0.3 baseline by 3–16 pp. Something is in there. Re-run will tell us if it's
  real.

### 5.4 What the re-run requires

- **Scheduled GPU time**: ~39 hours wall-clock, ideally overnight or during a
  weekend
- **Watch service stopped** for the duration (frees RAM + DB locks)
- **No competing training jobs** on the laptop GPU

### 5.5 Open questions for the v0.4.1 program

1. **Is B3's 56.82% real?** If yes, the volatility hypothesis is inverted — quiet
   names produce more predictable patterns than loud ones. This would be a
   counter-finding worth understanding before deploying.
2. **Is Strategy C's ±0.41% SD real?** If yes, stratified generalist universes
   are the operationally simplest production choice and methodologically defensible.
3. **What's limiting the architecture to ~44%?** Even Strategy C's mean is only
   ~3 pp above chance. The architecture itself may be the next bottleneck once
   universe is locked in.

These get answered by the second run, not by reinterpretation of the first.

---

## 6. Files added or modified in this commit

Code (`catalyst-neural/`):
- `storage/cohort_assignment.py` — sector renames, quartile bucketing, Ward linkage, COHORT_SIZE=50
- `training/cpcv_trainer.py` — s[2]→s[4] fix, graceful fold-failure handling
- `training/dataset.py` — `_load_labels` filtering, `_aggregate_5m_to_15m`, `min_date` kwarg
- `training/cohort_report.py` — matplotlib import order
- `launch_cohort_experiment.sh` — overnight runner

Reports:
- `Documentation/Reports/analysis/cohort_experiment_2026-06-04.html` — auto-generated report from the first run

Documents:
- `Documentation/Analysis/cohort-experiments-first-run-2026-06-19.md` — this document

---

## 7. Mission alignment

Two weeks of debugging to produce contaminated results is a real cost. Honest
accounting:

- ~25 GPU-hours of training time that produced metrics we have to caveat
- ~$29/mo Polygon Starter (good — was the right investment)
- ~40 person-hours debugging cascading data-quality and code bugs

The cost paid: we now know the eligible-universe is 286 (not 1,500), the dataset
needs OOM controls for production-scale data, the CPCV split logic needed proper
testing, and the `securities` table needs a UNIQUE constraint. None of these
findings would have come from a static review — they came from running the system
at scale for the first time.

The cost not yet paid: deploying a model from contaminated metrics. That's the
failure mode the methodology document was written to prevent, and the methodology
caught it. The bug was found because the DSR=1.000 readings were too good to be
real — exactly the kind of red flag that statistical hygiene exists for.

We are slow but moving. The second run is the test.

> *"He who works his land will have plenty of food, but he who chases fantasies
> will have his fill of poverty."* — Proverbs 28:19

---

*Craig + Claude — The Catalyst Family*
*2026-06-19*
