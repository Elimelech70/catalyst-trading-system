# Catalyst Neural — Strategic State

| Field | Value |
|---|---|
| Document | catalyst-neural-strategy-state |
| Snapshot date | 2026-06-01 |
| Authors | Craig + Claude |
| Status | Current snapshot — supersedes nothing; will be superseded by the next dated snapshot |
| Companion docs | `catalyst-neural-architecture-v0.4.md`, `catalyst-ml-methodology-v0.1.md`, `catalyst-cohort-experiments-architecture-v0.1.md` |

## Purpose of this document

This is the **honest, dated state of catalyst-neural** as of 2026-06-01. Three sections:

1. **Where we are.** What is built, what is running, what is hurting.
2. **What we have learned.** The findings of the last 30 days that changed how we think about the problem.
3. **What we are doing next.** The decision tree, the gates, the dependencies, and the calendar.

It is a snapshot. It will go stale. When it does, write a new dated one — do not edit this one in place. The historical sequence of these documents is the record of what we believed when.

---

## 1. Where we are

### 1.1 What is built and running

- **catalyst-international** — the trading agent on the intl droplet (Sydney, HKEX-focused). Six Docker containers, all healthy, all running on the v0.3 candle model. Has been doing real trades since January 2026.
- **catalyst-neural watch service** — the data-collection loop on the laptop. Running, recently fixed (sudo-suspend infinite-loop bug patched 2026-05-28).
- **Polygon backfill** — 5 years × 300 top-dollar-volume US symbols × candles + Tier 1+2 news, running as of 2026-06-01 evening. ETA 4–6 hours.

### 1.2 What is built but not running

- **v0.4 model (CandleModelV04)** — context-conditioned, 144,935 parameters, two training runs done. Not yet deployed to the droplet.
- **Cohort experiment framework** — architecture and implementation docs complete (`catalyst-cohort-experiments-architecture-v0.1.md` v0.2 + impl v0.1). Code not yet written; needs Polygon backfill to finish first.
- **Polygon collector** — `collectors/polygon_collector.py`, 280 lines, source-tier filter at door, idempotent inserts. Smoke-tested. Running its first full backfill now.

### 1.3 What is hurting

- **Three months of negative P&L on production.** From the 2026-05-28 trading review: Mar 2026 −968 HKD, Apr 2026 +1,657 HKD, May 2026 −4,461 HKD. Net over the three real-trading months: **−3,772 HKD**. The system is **active** (28 orders in the last 7 days, daily heartbeat) but **underperforming**. Loser-to-winner ratio is ~1.5:1 and the average win does not compensate for the average loss.
- **v0.3 model has plateaued and is degrading with more data.** Six weekly retrains from 2026-04-20 to 2026-05-18 show train_loss falling but val_loss rising — classic overfitting. Directional accuracy drifted from 43.03% to 40.65%. R² on returns hovers near zero across all horizons. The model is barely above chance and getting worse.
- **HKEX news coverage is structurally zero.** No free-tier API covers Hong Kong meaningfully. Polygon does not cover Hong Kong. The v0.4 architecture cannot help on HKEX without news context — which means the production trades happening *right now* are on a model that has only seen the candle channel of its supposed context.

### 1.4 What is shelved

- **catalyst-agent** — the US trading agent. Stopped 2026-05-18 to prevent wasted API spend. Will not be revived until a clear strategy for US execution exists.
- **services/consciousness** — heartbeats, dashboard, task executor. Was running on US droplet. Not being continued.

---

## 2. What we have learned (last 30 days)

Five findings, in order of how they reshaped our thinking.

### 2.1 v0.4 + zero news context is indistinguishable from v0.3

The 2026-05-28 v0.4 training run on the 59-symbol legacy universe with zero classified news rows produced:

| | v0.3 baseline | v0.4 zero-news |
|---|---|---|
| Best val_loss | 1.6524 | 1.6552 |
| Final dir_acc | 40.83% | 40.78% |
| Final val_mae | 0.3877 | 0.3900 |

Essentially identical. The extra 13K parameters of `CandleModelV04`'s `ContextEncoder` did not pay off when both `news_context` and 90%+ of `security_context` were degenerate.

**Implication:** v0.4's marginal benefit is entirely in the context channels. Without real news coverage, the architecture is academic. Either the news pipeline gets fixed, or v0.4 is a no-op.

### 2.2 v0.4 + 1,160 classified news rows shows the first real positive delta

The 2026-06-01 retrain after the news pipeline started flowing (NewsAPI + Finnhub free tier, 1,160 classified rows, 7 US symbols with coverage):

| | v0.3 baseline | v0.4 + news |
|---|---|---|
| Best val_loss | 1.6524 | 1.6785 (worse — magnitude calibration regressed) |
| Final dir_acc | 40.83% | **41.18%** (+0.35 pp) |

**Direction got better, magnitude got worse.** The news signal reached the gradients and shifted the directional softmax in the right direction, but the model is more confident in wrong magnitudes. The +0.35 pp on the full validation set is plausibly a much larger lift on the 5–10% of samples that have non-zero `news_context`, diluted by 90%+ zero-context samples.

**Implication:** the hypothesis is not failing — coverage is the bottleneck. Need broader news ingestion before any v0.4 comparison is interpretable.

### 2.3 The regex classifier is brittle on aggregator content

Sampling 8 random AAPL headlines from the Polygon news firehose through the Phase 2 regex classifier showed mostly wrong categorisations:

- "Wall Street Just Cut Figma's Price Target..." → `corporate_action` (should be `analyst`)
- "Greg Abel Just Dumped Amazon Stock. Here Are 5 Reasons to Buy It." → `product` (should be insider activity / editorial)
- "Stop Trying to Beat the Market: This Vanguard ETF Outperforms 90%..." → `earnings` (should be commentary)

Polygon's news firehose is **94% Tier 3** (Motley Fool, Benzinga, Seeking Alpha) — editorial blog content that hits regex keywords without context. The classifier was tuned for wire-style headlines and fails on this content shape.

**Implication:** we cannot accept Polygon's news as-is. A source-tier gate at ingestion is required to keep the classifier in its competence zone (Reuters, Bloomberg, GlobeNewswire press releases). Done — filter is in production at `polygon_collector.py:_PUBLISHER_TIER`.

### 2.4 GlobeNewswire is the dominant primary catalyst source on Polygon

When the source-tier filter was first applied, **zero articles passed** on a 7-day AAPL pull. Investigating revealed that 155 of 174 "unknown" publishers were GlobeNewswire — a primary press-release wire that companies use for **official earnings releases, FDA approvals, M&A announcements**.

GlobeNewswire is closer to the source than Reuters for these events. After adding GlobeNewswire (and Business Wire, PR Newswire, Accesswire) to Tier 1, market-wide retention rose from 0% to 42% with all Tier 3 noise still filtered out.

**Implication:** wire services in the Reuters/Bloomberg sense are present but rare on Polygon's per-symbol feeds. Primary corporate news comes through press-release wires. The publisher whitelist needs to evolve as we observe more of the firehose.

### 2.5 The universe choice may dominate the model choice

The 59-symbol legacy universe contains too few news-covered symbols (7) and too little sector diversity (mixed US + HKEX, no sector-pure cohorts possible). Strategy questions like "does sector specialisation help" and "is volatility a real driver" cannot be answered on this universe.

This learning produced the cohort experiment design (architecture v0.2): test 5 grouping strategies × 3 instances = 15 cohorts of 150 symbols, hold the model architecture constant, compare under deflated Sharpe + PBO + one-way ANOVA. The literature (Krauss, Fischer, Gu/Kelly/Xiu) consistently uses 500-symbol universes; we've been training on 59.

**Implication:** the universe question is now the architecture question. Until it's answered, we don't know whether v0.4 is "the architecture" or "an architecture that needs the right universe to work."

---

## 3. What we are doing next

### 3.1 Critical path (in order)

| Step | What | Status | Blocked by | ETA |
|---|---|---|---|---|
| 1 | Polygon 5y × 300 backfill complete | Running | nothing | overnight 2026-06-01 → 2026-06-02 |
| 2 | Verify backfill quality (totals, classification, coverage per symbol) | Pending | step 1 | morning 2026-06-02 |
| 3 | Build cohort experiment infrastructure (Phases 1–4 of impl doc) | Not started | nothing structurally; can start in parallel with step 1 | 2026-06-02 → 2026-06-05 |
| 4 | Run 15-cohort × 5-fold experiment (Phase 5) | Not started | steps 2 + 3 | overnight 2026-06-05 → 2026-06-06, ~7.5 hours GPU |
| 5 | Pattern analysis (Phase 6–7): DSR, PBO, ANOVA, common-failure-modes | Not started | step 4 | 2026-06-06 |
| 6 | Gate decision: which strategy wins, if any (Phase 8) | Not started | step 5 | 2026-06-06 |
| 7 | If win: train v0.4.1 on winning cohort, export ONNX, deploy to droplet | Not started | step 6 | 2026-06-07 → 2026-06-08 |

Realistic timeline: **first v0.4.1 production deploy by mid-June 2026**, contingent on the experiment producing an interpretable winner.

### 3.2 The four-outcome decision tree

Per `catalyst-cohort-experiments-architecture-v0.1.md` v0.2 §11:

1. **Outcome 1: A single strategy wins clearly.** DSR > 95% threshold on all three instances of one strategy, PBO < 0.2, ANOVA omnibus rejects, post-hoc names the winner. *Action:* freeze that strategy as the v0.4.1 universe-selection rule, deploy.
2. **Outcome 2: Two strategies tie within noise.** *Action:* pick the operationally simpler (probably Stratified mix C, lowest data-engineering burden), deploy.
3. **Outcome 3: Volatility is confirmed but no single strategy dominates.** B1 (top-vol) ≫ B3 (bottom-vol) AND E1 (pure mover) > E3 (null). *Action:* adopt vol-rank-filtered universes; deploy.
4. **Outcome 4: No strategy beats the null.** *Action:* the universe is not the bottleneck. Return to the v0.4 architecture. Revisit news coverage, or revisit the model entirely.

Outcomes 1, 2, 3 deploy v0.4.1. Outcome 4 sends us back to architecture work — no production deploy.

### 3.3 What we are deliberately NOT doing

- **Not deploying v0.4 to production today.** The 2026-06-01 retrain failed the Test 2 gate (+5 pp dir_acc). Deploying a marginal +0.35 pp model risks adding architectural noise without solving the underlying P&L problem.
- **Not running ad-hoc architecture variants during the cohort experiment.** Hyperparameter tuning per cohort would confound the universe variable. Methodology doc spells this out (§4 of `catalyst-ml-methodology-v0.1.md`).
- **Not upgrading to Polygon Developer ($79) or Advanced ($199) yet.** Starter ($29) covers all training-data needs (delayed real-time is fine because the laptop does not run live inference). Upgrade decision deferred to post-deploy.
- **Not investing in HKEX news coverage.** Free APIs do not cover it; Refinitiv at $22K/yr is mission-incompatible. The v0.4 architecture cannot help on HKEX without context. We accept this and let the HKEX trades continue on v0.3 while the US side moves forward.

### 3.4 What success looks like by 2026-06-30

By end of June we should be able to answer, with statistical defensibility:

- Which universe-selection strategy produces the best v0.4 model on our data
- Whether v0.4 is materially better than v0.3 once the universe is right
- Whether HKEX trading should be paused while we focus on US (only if US v0.4.1 deploys successfully and intl losses continue)
- What the v0.5 architecture experiment should be (likely: do news_category-weighted loss + Polygon insights field)

If we get there, the system has moved from "underperforming and worsening" to "evidence-based with a known winner." That is the minimum bar for the mission to continue without further capital depletion.

### 3.5 What success does NOT look like

- Choosing a v0.4.1 universe by picking the cohort with the highest validation accuracy (backtest overfitting, Bailey-Borwein-Lopez de Prado).
- Tuning hyperparameters until something works (overfit to validation).
- Deploying a model whose deflated Sharpe is below threshold (deploying noise).
- Skipping the cohort experiment because backfill takes too long (false economy — we lose more on production every day than the experiment costs).

---

## 4. Open strategic questions (not in scope for the cohort experiment)

1. **Should the intl trading agent be paused while we focus on US?** Currently losing money; case for pausing it grows with each negative month. Requires Craig's call.
2. **Should we acquire HKEX news coverage at any cost?** The cheapest viable path is Refinitiv at $22K/yr, which exceeds the trading account by 10×. Probably "no" — but worth a yearly review.
3. **What is the right risk-adjusted threshold for v0.4.1 production deployment?** Currently informal. By the time the experiment finishes we should have an explicit dollar-amount-at-risk threshold above which deployment is held until further evaluation.
4. **Does the mission require a more concentrated focus?** Three implementations (catalyst-international running, catalyst-research scaffolded, catalyst-neural training) for one part-time team. Some pruning may be unavoidable.

These are not engineering questions. They are stewardship questions. Document so they don't get forgotten; resolve when there's evidence.

---

## 5. What this document is not

- Not the architecture → see `catalyst-neural-architecture-v0.4.md`
- Not the experiment design → see `catalyst-cohort-experiments-architecture-v0.1.md` v0.2
- Not the methodology → see `catalyst-ml-methodology-v0.1.md`
- Not the implementation plan → see `catalyst-cohort-experiments-implementation-v0.1.md`
- Not the trading-system roadmap → see `catalyst-strategy-roadmap.md`

This is the dated state. When state changes, write a new one. Do not edit this one to keep it "current" — the sequence is the record.

---

*Craig + Claude — The Catalyst Family*
*2026-06-01*
