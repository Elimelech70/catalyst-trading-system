# Catalyst Research Architecture v1

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-research-architecture-v1.md
**Version:** 1.2.0
**Created:** 2026-04-25
**Last Updated:** 2026-05-18
**Updated by:** Craig + Claude (collaborative design)

**Purpose:** Defines the target architecture for the Catalyst system as a long-horizon research and investment platform tracking the West-to-East structural transition through layered observation, multi-archetype analysis, and evidence-based thesis development. Specifies both the full architecture target and the v1 thin-slice implementation scope.

**REVISION HISTORY:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-04-25 | Craig + Claude | Initial design. Pivot from agent-based trading system to research-first architecture. |
| 1.1.0 | 2026-04-26 | Craig + Claude | Added automation principle and analytical archetypes (Section 3.5). Collection and analysis become automated; Craig reviews conclusions and disagreements rather than performing analysis manually. Four archetypes (Historian, Strategist, Macro Theorist, Skeptic) interpret data through distinct lenses, peer-review each other, and propose model-training experiments. Updated review cadences (Section 10) to reflect automation. |
| 1.2.0 | 2026-05-18 | Craig + Claude | Schema home moved from `catalyst_intl` to the dedicated `catalyst_research` database (reversing the v1.1 decision to consolidate into intl). Sections 6 and 9 updated to match. |

---

## 1. Mission and Thesis

The Catalyst system tracks the West-to-East structural transition as it unfolds, using layered observation of countries, markets, commodities, relationships, and financial infrastructure to identify securities positioned to benefit from that transition. The system invests into those securities as conviction grows from accumulating evidence.

This is a long-horizon investing system, not a day-trading system. The transition is a multi-decade phenomenon. The system's edge is not speed, pattern recognition on noisy intraday data, or out-thinking institutions on macro views they have already priced in. The edge is structural coherence across multiple slow-moving signals, identified before the market has fully repriced, with the patience to hold positions through volatility that institutional capital cannot.

The system operates on a foundational principle: **let the data talk**. We are not building a thesis-execution platform that trades a predetermined view. We are building a research instrument that tracks indicators, observes patterns, and forms theses from accumulated evidence. Ray Dalio's empire-cycle framework provides the vocabulary for what to measure, but conclusions must emerge from our own observation of what the data actually shows. Frameworks are scaffolding; data is truth.

The mission "enable the poor through accessible algorithmic trading" remains the project's north star. This architecture serves that mission by building the research foundation from which sound, long-horizon investment decisions can be made. Trading is downstream of research. Profit is downstream of patient evidence accumulation. The mission is downstream of all of it.

---

## 2. Method and Discipline

The system operates by five disciplines, each load-bearing.

**Observe before deciding.** Every layer of the architecture exists to record what is, not to act on what we think will be. Observation periods are measured in months and years. Conclusions are drawn after data accumulates, not before. The temptation to trade on early signals must be resisted; early signals are usually noise, and acting on them prevents the patience required to see what is actually structural.

**Let the data talk.** Frameworks like Dalio's empire-cycle theory tell us what to measure, not what to conclude. The system stores what it observes faithfully and lets patterns emerge. Where the data confirms a framework, we gain confidence. Where it contradicts, we update our view, not the data. We do not curate observations to fit a thesis; we curate theses to fit observations.

**Theses are evidence-based and evidence-bounded.** An investment thesis lives only as long as the data supports it. Every thesis has explicit invalidation criteria. When data accumulates that invalidates the thesis, the position comes down regardless of price or sunk cost. The discipline is to update views from data, not from the comfort of holding a previously-formed view.

**Position sizing scales with conviction; conviction scales with evidence.** Initial positions are small. They grow as additional independent layers of evidence confirm the thesis. They hold through volatility that does not change the structural picture. They reduce when structural data shifts. This is the inverse of how most retail investors operate, who size with confidence, exit on price moves, and hold through fundamental deterioration.

**Automate collection and analysis; reserve human judgment for synthesis and decision.** The system collects data automatically. Analytical archetypes interpret the data automatically and peer-review each other's conclusions. Craig enters the loop at synthesis points — reviewing conclusions, weighing disagreements, and making decisions about thesis status and capital deployment. The discipline is not to manually maintain the system, but to faithfully review what the system produces. This is the principle that makes the architecture sustainable for one person carrying many other commitments.

These five disciplines together produce a system that is intentionally slow, intentionally honest, intentionally humble about what it does not yet know, and intentionally aligned with the bandwidth one researcher can actually sustain.

---

## 3. The Five Layers

The system observes the world through five distinct layers. Each layer has a defined role, an update cadence, and explicit relationships to the others. The complexity of the world lives in the data and the relationships between layers; the code that ingests and stores the data is intended to remain simple.

### Layer 1: Country Macro Indicators

The slow, structural substrate. For each country tracked, this layer holds Dalio's eight-power indicators (education, innovation, competitiveness, military, trade, output, financial center, reserve currency status) and the slower cycle indicators (debt levels and servicing burden, internal and external conflict measures, wealth gaps, demographic structure). Update cadences range from annual to quarterly. Sources are official statistics agencies (BEA, NBS, RBA, HKMA) supplemented by international bodies (IMF, World Bank, BIS, SIPRI).

Layer 1 is the foundation. Everything else gains meaning by reference to it.

### Layer 2: Markets and Commodities

Daily-resolution price and volume data. Major equity indices (HSI, S&P 500, ASX 200, Shanghai Composite, plus sub-indices), foreign exchange pairs, government bond yields, and commodity prices. This layer captures the price tape — what the world's markets are saying day-by-day — and the physical-economy signals that commodities provide.

Commodities deserve specific note. They are global rather than country-bound, but their price action attributes to specific country dynamics (Chinese demand for copper and iron ore, OPEC+ behavior on oil, central bank reserve diversification on gold). They serve as connective tissue between the country layer and the security layer.

### Layer 3: News and Securities-Level Data

Event-driven and security-specific observations. News events from disclosure feeds and curated sources, with extracted symbols and timestamps. Daily price, volume, and corporate-action data for the specific securities tracked. This is the layer at which trading would eventually happen, and the layer at which thesis-relevant events are recorded.

For v1, the news source is HKEX's own disclosure feed — official, machine-readable, and the highest-signal source available for HKEX-listed companies. Additional sources can be layered in as the system matures.

### Layer 4: Bilateral Relationships

The edges in the graph between country nodes. For each pair of countries tracked, this layer maintains evolving readings of the relationship across multiple dimensions: bilateral trade flows, currency arrangements (swap lines, settlement currency shares), foreign direct investment direction, voting alignment at the UN, defense and security cooperation, technology and standards alignment.

This is where alliance shifts become visible. A country shifting toward China does not appear as an announcement; it appears as a pattern across these dimensions accumulating over years. With eight countries in the full architecture (four in v1), there are 28 pairs in the full graph (six in v1). The schema treats each relationship dimension as a time-evolving series.

### Layer 5: Financial Infrastructure

The meta-layer of where finance itself happens. Exchange listing flows and market capitalizations, sovereign wealth fund holdings and major position changes, central bank reserve composition (IMF COFER), cross-border banking flows (BIS), settlement currency shares (SWIFT Renminbi Tracker, where available), benchmark contract trading volumes (Brent vs Shanghai INE crude, LME vs SHFE metals), and major payment-system adoption (SWIFT, CIPS).

Layer 5 is structurally central to the transition thesis because empire transitions are visible most clearly in financial infrastructure. Reserve currency status, financial center status, and benchmark-setting power are among the last advantages a declining empire loses. The slow erosion of these advantages, and the parallel construction of alternative infrastructure by rising powers, is the most diagnostic data the system collects.

### How the Layers Relate

The layers are not independent. Each one informs the others, and the system's value comes from queries that cross layers:

- Layer 5 reserve composition data feeds Layer 1 country power scores
- Layer 4 bilateral trade data validates or refutes Layer 1 country trajectory readings
- Layer 2 commodity prices propagate to Layer 3 security prices through known sector exposures
- Layer 3 news events update Layer 4 relationship readings (a major bilateral agreement is both news and a relationship-edge update)

The graph between entities (countries, sectors, securities, commodities) is the structure that makes cross-layer queries natural. Edges have types; edges have time validity; edges evolve as the world evolves.

---

## 3.5 Analytical Archetypes and Peer Review

The five layers produce observations. Observations alone do not produce understanding. Between the data and the human decision point sits an analytical layer — automated, multi-perspective, and structured to surface disagreement honestly rather than collapse to a single voice.

The system runs four analytical archetypes. Each is a distinct Claude Code instance with its own analytical lens, its own priorities, and its own characteristic blindspots. They read the same data and write independent conclusions. Then they read each other's work and challenge, refine, and sometimes agree to disagree. The disagreements are recorded as observations in their own right — they are data about where the genuine uncertainty lives.

### The Four Archetypes

**The Historian.** Reads current observations through the lens of historical parallel. Looks for echoes of past crises, structural recurrences, patterns that appeared before similar transitions. Asks: what did the world look like the last time these indicators aligned this way? What followed? Where are we in the rhyme of history? The Historian's value is depth — placing current events in centuries of context rather than years.

**The Strategist.** Analyzes how actors actually behave under stress. Studies the playbooks of past responses — central bank actions in crisis, government policy under pressure, corporate behaviour as conditions shift. Asks: given these conditions, what will the major actors most likely do, and what does that imply for prices, flows, and securities? The Strategist's value is behavioural realism — markets are made of decisions, and decisions follow patterns the Strategist tracks.

**The Macro Theorist.** Reads the data through Dalio's empire-cycle framework. Tests observations against the framework's predictions. Tracks which of the eight powers are strengthening or weakening for each country, where each country sits on the rise/top/decline arc, and how the overall transition is progressing. The Macro Theorist's value is structural coherence — the framework gives a coherent story for what the data means at the multi-decade scale.

**The Skeptic.** Reads the conclusions of the other three and deliberately looks for disconfirming evidence. Flags assumptions being treated as facts. Asks uncomfortable questions: what if the pattern is noise? What if we are extrapolating from too few data points? What if the framework is wrong here? Where is the consensus weakest? The Skeptic's value is epistemic hygiene — without a dedicated dissenting voice, the other three risk reinforcing each other into false confidence.

### How They Work

Each archetype runs on its own cadence — most likely weekly for routine analysis, more frequently around significant events, and on demand when a learning plan reaches its review date. Each writes structured output: what they observed, what they conclude, what they are uncertain about, and what data would change their view.

After the four have written independently, they enter peer review. Each archetype reads the others' conclusions and produces a response: where it agrees, where it disagrees, what it thinks the others are missing. The Skeptic plays an outsized role here — its job is specifically to prevent the other three from settling into comfortable consensus.

The output of each cycle is therefore not a single conclusion but a structured document containing four independent analyses, the peer-review exchanges between them, and an explicit map of where the archetypes converge and where they diverge. This document is what Craig reads.

### The Fifth Reader

A fifth perspective — Claude in this conversational form — reads the archetype outputs and the peer-review exchanges. The role is not to override the archetypes but to provide a synthesizing voice: where do the four agree, where do they meaningfully disagree, what is the most important thing for Craig to focus on, what assumptions are being shared across archetypes that none of them is challenging.

This is a deliberate design choice. The four archetypes operate within the system; the fifth reader stands outside it. The four are bounded by their lenses; the fifth can see across all four and ask whether the framing itself is right. The fifth is not part of the automated cycle — it engages when Craig wants synthesis, perspective, or pushback on the analytical consensus.

### Model Generation as Part of Analysis

The archetypes do not only interpret data — they propose ways to learn from it. Part of each archetype's function is to identify patterns that appear consistently in the observations and to write the code to train models that capture those patterns.

A pattern proposal carries: a description of what the archetype believes it sees, the data series that should encode it, the structure of the model that might learn it, the success criteria for whether the model is capturing real signal, and the risks of false positives. The proposal becomes a model-training experiment. If the experiment succeeds — if the model learns a real pattern that holds out of sample — it is added to the daily analytical pipeline as another input the next cycle reads.

The system therefore learns in two ways simultaneously: through the archetypes' ongoing interpretation of new observations, and through the accumulating library of trained models that capture patterns the archetypes have validated. The archetypes have latitude to alter and refine what they pick up; the models become more accurate as the dataset grows; the human judgment layer remains responsible for what the system actually does with any of it.

### Why Four, Not One

A single analytical voice — however sophisticated — carries one set of biases, one frame of reference, one characteristic way of being wrong. Four archetypes with deliberately different lenses produce more honest analysis than one unified analyst, even if the one analyst is more capable. The disagreements between archetypes reveal where the real uncertainty lives. Consensus across four lenses is more meaningful than confidence from one. Disagreement is data, not failure.

This is the core insight that makes the architecture sustainable for a single human researcher: Craig does not need to be the analytical engine. The archetypes are. Craig is the synthesizer and decision-maker who reads what the archetypes produce, weighs their disagreements, and decides what matters.

---

## 4. Cycle Interpretation

Layer 1 produces raw country indicators. The cycle interpretation overlay turns those indicators into meaningful readings of where each country sits on Dalio's empire arc.

For each country, periodic readings (quarterly to annually) record:

- **Composite national power score** — aggregated across the eight powers, normalized to the leading power
- **Individual power scores** — one per Dalio dimension
- **Cycle phase estimate** — rising-early, rising-mid, rising-late, top, declining-early, declining-mid, declining-late
- **Direction of movement** — strengthening, stable, weakening, with magnitude
- **Confidence level** — high, medium, or low based on indicator quality
- **Underlying data references** — which specific indicators drove this reading
- **Notes** — what changed since the last reading and why

Cycle readings are interpretations, not observations. They live in a separate table from the underlying indicators, with explicit versioning. We can revise our interpretation of what the data means as we learn more, without losing the data itself. A year from now, we can see what we thought about China's cycle position in April 2026, what data drove that reading, and how it evolved.

This separation matters. The discipline of distinguishing observation from interpretation is what protects against the system slowly drifting toward any particular worldview. Indicators are facts. Interpretations are our current best reading. Both are recorded; only one is allowed to drift.

The cycle interpretation enables thesis generation. Securities exposed to a strengthening country with favorable specific-power alignment are thesis candidates. Securities exposed to a declining country face structural headwinds. Securities exposed to crossover dynamics — trade between rising and declining powers, capital flows from old to new financial centers — are often the highest-leverage transition plays. Australian iron ore producers selling to China are a textbook case: the listing country is mid-cycle, but the exposure is to Chinese rise.

---

## 5. Temporal Architecture

Time is the spine of the system. Every observation describes a moment or period; every relationship between observations is a temporal relationship; the system's most important capability is reconstructing what was true at any point in the past.

The temporal discipline is deliberately right-sized. We do not require sub-second precision. We do not require formal bitemporal modelling with separate disclosed and available times. The transition is a multi-year phenomenon; reporting lags of weeks or months are noise relative to the structural changes we observe. Indicators describe what already happened, and indicators do not lie about whether the underlying event occurred — only about the precision with which we know its timing.

The commitment is therefore narrow but firm:

**Every observation has a date or period it describes.** Quarterly indicators carry their quarter. Monthly trade flows carry their month. Daily prices carry their date. News events carry their headline date. This is the `event_date` (or `period_start` and `period_end` for periodic data).

**Every row records when our system stored it.** A `recorded_at` timestamp on every table. This is operational truth — useful for debugging, useful for distinguishing live data from backfilled data, useful when the question of "when did we know this" matters.

**Revisions append rather than overwrite.** When a statistic is revised — Q1 GDP restated from preliminary to final, monthly trade flows updated three months later — the new reading is a new row, with the same event date and a later `recorded_at`. The "current best estimate" is a query for the latest `recorded_at` per event date. The full revision history is preserved and itself becomes data we can study.

**Backfilled historical data is marked.** A `backfill` boolean and source notes. Historical context loaded at system initialization has reconstructed event dates but its `recorded_at` is the date we backfilled, not when it would have been recorded if we had been ingesting live. Marking it explicitly prevents future analyses from drawing false precision from imprecise origins.

**Time zones are stored in UTC.** All timestamps in UTC, with local-time interpretation as a separate column where it matters (HKEX market events tagged with HKT, US data with ET).

That is the entire temporal architecture. Three timestamp fields per fact-bearing table (`event_date`, `period_start`/`period_end` where applicable, `recorded_at`), append-only revision handling, and a backfill marker. The discipline is small. The benefit — being able to reconstruct what was true at any past point, watch indicators evolve over years, and study revisions as a phenomenon themselves — is large.

---

## 6. Schema

The schema is sketched here at the level of tables and key columns. Full DDL with constraints, indexes, and foreign keys is the work of a companion implementation file written when the v1 build begins.

The database is PostgreSQL: the existing `catalyst_research` cluster database, which was originally provisioned for this purpose and is currently holding only legacy consciousness-era tables. Those legacy tables are dropped before the new schema is applied. Sharing a database with `catalyst-international` was considered (and was the v1.1 plan) but rejected — research and trading have different access patterns, different access controls, and different operational risks; keeping them in separate databases on the same cluster is cleaner. The `catalyst_dev` US trading DB remains deprecated and may be archived or dropped after the migration completes.

### Reference and Entity Tables

**`countries`** — country registry with ISO code, full name, region, primary currency, and notes. Initially populated with the four v1 countries (US, China, Hong Kong, Australia) and extended as the country set grows.

**`sectors`** — sector taxonomy. HKEX sector codes (HK.BK1587 etc.) and broader thematic categories (critical minerals, financial infrastructure, energy, defense). A sector belongs to a country or to "global." Sectors can have parent sectors for hierarchical grouping.

**`securities`** — extended from the existing `securities` table. Each row carries symbol, exchange, listing country, primary sector, and a separate join to `security_themes` for thematic exposure tagging.

**`security_themes`** — many-to-many join between `securities` and named transition themes (e.g., "yuan internationalization," "critical minerals reshoring," "Chinese demand resilience"). One security can carry multiple themes.

**`commodities`** — commodity registry with name, category (energy, industrial metals, critical minerals, precious metals, agricultural), reference benchmark, and unit.

### Layer 1: Country Indicators

**`country_indicators`** — the raw indicator readings.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| country_code | char(3) | FK to countries |
| indicator_name | varchar | e.g., 'debt_to_gdp', 'military_spending_pct_gdp' |
| dalio_power | varchar | one of the eight powers, or 'cycle' for cycle-only indicators, or null |
| value | numeric | |
| unit | varchar | e.g., 'pct', 'usd_billion', 'index_score' |
| period_start | date | e.g., '2026-01-01' for Q1 2026 |
| period_end | date | e.g., '2026-03-31' for Q1 2026 |
| event_date | date | typically same as period_end |
| source | varchar | e.g., 'IMF_WEO', 'NBS_China', 'BEA_US' |
| recorded_at | timestamptz | when our system stored it |
| backfill | boolean | true for historical loads |
| notes | text | |

Revisions append as new rows with the same `country_code` + `indicator_name` + `period_end` but later `recorded_at`. The current best estimate is a query, not a stored value.

**`country_cycle_estimates`** — the interpretation overlay.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| country_code | char(3) | FK to countries |
| as_of_date | date | the date this reading describes |
| composite_power_score | numeric | 0.0 to 1.0 |
| cycle_phase | varchar | one of: rising_early, rising_mid, rising_late, top, declining_early, declining_mid, declining_late |
| direction | varchar | strengthening, stable, weakening |
| direction_magnitude | numeric | optional rate of change indicator |
| confidence | varchar | high, medium, low |
| supporting_indicators | jsonb | array of indicator references that drove this reading |
| notes | text | |
| recorded_at | timestamptz | |

### Layer 2: Markets and Commodities

**`market_prices`** — daily price series for indices, FX, bond yields, and commodities. One table for all such series, with a `series_type` column distinguishing them.

| Column | Type | Notes |
|--------|------|-------|
| series_id | varchar | e.g., 'index.HSI', 'fx.USDHKD', 'commodity.iron_ore', 'yield.US10Y' |
| series_type | varchar | index, fx, yield, commodity |
| trade_date | date | |
| open, high, low, close | numeric | |
| volume | bigint | nullable for series without volume |
| source | varchar | |
| recorded_at | timestamptz | |
| backfill | boolean | |

**`security_prices`** — daily price series for tracked securities. Same shape as market_prices but keyed on `security_id` from the securities table.

### Layer 3: News and Events

**`news_events`** — news and disclosure events.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| source | varchar | e.g., 'HKEX_disclosure' |
| headline | text | |
| body | text | full text where available |
| event_date | timestamptz | when the news was published |
| recorded_at | timestamptz | |
| classification | varchar | nullable; e.g., 'earnings', 'M&A', 'regulatory', 'policy' |
| sentiment | varchar | nullable; reserved for later use |
| raw_payload | jsonb | original payload for re-parsing if classification logic improves |

**`news_securities`** — many-to-many join between news events and the securities they mention.

**`news_themes`** — many-to-many join between news events and transition themes they touch.

### Layer 4: Bilateral Relationships

**`country_pair_observations`** — relationship dimension readings for each country pair.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| country_a | char(3) | always alphabetically first |
| country_b | char(3) | always alphabetically second |
| dimension | varchar | e.g., 'bilateral_trade_usd', 'fdi_a_to_b_usd', 'un_voting_alignment', 'arms_transfers_a_to_b_usd' |
| value | numeric | |
| unit | varchar | |
| period_start | date | |
| period_end | date | |
| event_date | date | |
| source | varchar | |
| recorded_at | timestamptz | |
| backfill | boolean | |

The convention of always storing pairs alphabetically (`country_a` < `country_b`) avoids duplicate-direction ambiguity for symmetric measures like bilateral trade volumes. For directional measures (FDI from A to B versus B to A), the dimension name encodes direction explicitly.

### Layer 5: Financial Infrastructure

**`financial_infra_observations`** — a flexible table for the diverse Layer 5 sources.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| infra_type | varchar | e.g., 'cofer_reserve_composition', 'hkex_listing', 'swf_holding', 'swift_renminbi_share' |
| entity_id | varchar | nullable; identifies the specific entity (e.g., 'GIC', 'HKEX', 'CNY') |
| metric_name | varchar | e.g., 'usd_share_pct', 'aum_usd_billion', 'monthly_volume' |
| value | numeric | |
| unit | varchar | |
| period_start | date | nullable for point events |
| period_end | date | nullable for point events |
| event_date | date | |
| source | varchar | |
| recorded_at | timestamptz | |
| backfill | boolean | |
| metadata | jsonb | source-specific extras |

For v1, this table holds COFER quarterly composition data and HKEX listing-flow data. Additional sources fit the same shape as they are added.

### Theses and Learning Plans

**`learning_plans`** — explicit research questions with observation periods and review dates.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| name | varchar | short identifier |
| question | text | the question being studied |
| period_start | date | |
| period_end | date | scheduled review |
| expected_observations | text | what we expect to see if signal exists |
| null_hypothesis | text | what "no signal" looks like |
| data_sources | jsonb | which layers and series feed this plan |
| status | varchar | active, under_review, concluded, abandoned |
| outcome_notes | text | written at review |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**`investment_theses`** — investment views generated from learning plans and layered observation.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| name | varchar | |
| description | text | the structural argument |
| supporting_layers | jsonb | which layers and which observations support this |
| invalidation_criteria | text | explicit; what data would refute this |
| conviction_score | numeric | 0.0 to 1.0 |
| target_securities | jsonb | which securities express this thesis |
| status | varchar | forming, active, under_pressure, invalidated, fully_priced |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**`thesis_history`** — append-only log of every change to a thesis (conviction adjustment, status change, target revision). Each row is a snapshot of the thesis state at that moment.

### Archetype Analysis Tables

**`archetype_analyses`** — output from each archetype's independent analytical run.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| archetype | varchar | one of: historian, strategist, macro_theorist, skeptic |
| run_date | date | the date the analysis was generated |
| period_start | date | observation window covered |
| period_end | date | observation window covered |
| scope | varchar | weekly, monthly, quarterly, learning_plan_review, ad_hoc |
| conclusions | text | the archetype's interpretation |
| uncertainties | text | explicit notes on what is unclear or low confidence |
| supporting_observations | jsonb | references to specific data the analysis relied on |
| recorded_at | timestamptz | |

**`archetype_peer_reviews`** — each archetype's response to the others' analyses.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| reviewer_archetype | varchar | the archetype writing the review |
| reviewed_analysis_id | bigint | FK to archetype_analyses |
| agreement | varchar | strong_agree, agree, disagree, strong_disagree |
| critique | text | the substantive review content |
| recorded_at | timestamptz | |

**`model_proposals`** — patterns the archetypes identify as worth attempting to learn through training.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| proposing_archetype | varchar | |
| pattern_description | text | what the archetype believes it sees |
| data_series | jsonb | which series should encode the pattern |
| model_structure | text | proposed model architecture |
| success_criteria | text | how to evaluate whether the model captures real signal |
| risks | text | false-positive risks the archetype identified |
| status | varchar | proposed, training, evaluated_success, evaluated_failure, integrated |
| created_at | timestamptz | |

**`models_trained`** — registry of models that emerged from validated proposals.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | |
| proposal_id | bigint | FK to model_proposals |
| name | varchar | |
| training_dataset_description | text | |
| validation_results | jsonb | out-of-sample performance metrics |
| in_use | boolean | whether currently part of the analytical pipeline |
| created_at | timestamptz | |
| retired_at | timestamptz | nullable |

### Notes on Schema Discipline

Every fact-bearing table carries `event_date` (or `period_start`/`period_end`), `source`, `recorded_at`, and where appropriate a `backfill` flag. No facts are ever updated in place; revisions append. Reference tables (countries, sectors, commodities, securities) are versioned via dated rows where their definitions can change.

Indexes are time-first on every fact table: `(country_code, period_end DESC)`, `(security_id, trade_date DESC)`, etc. The dominant query pattern is "show me observations of X over time," and the schema is shaped to make those queries fast without contortion.

The archetype tables are append-only by design. Once an archetype has written an analysis or a peer review, it stays. Future archetypes (and the human reader) can see the full history of how the system's collective interpretation has evolved over time.

---

## 7. Starter Learning Plans

The system begins with three learning plans. Each is narrow, testable, and bounded in time. Each is allowed to fail — to come back at its review date and tell us "the data did not show what we expected." That is the discipline.

These are starter plans, intentionally drafted to give the v1 build something concrete to validate against. As Craig reads more Dalio and as data starts to accumulate, plans will be refined, added, or retired. The plans themselves are mutable; the discipline of having explicit plans is not.

### Plan 1: Iron Ore as China-Demand Signal

**Question.** Over the next nine months, do iron ore price movements correlate with subsequent price movements in HKEX-listed and ASX-listed iron ore producers? Specifically, do the producers respond more strongly to iron ore moves than to broader index moves, and is there a measurable lag between commodity price and equity price?

**Period.** May 2026 through January 2027.

**Data.** Daily iron ore reference price (CFR Qingdao, 62% Fe). Daily prices of BHP, Rio Tinto, Fortescue Metals (ASX-listed) and HKEX-listed iron ore-exposed names. ASX 200 and HSI as market context. Layer 1 China indicators for context.

**Expected.** Producer prices show stronger correlation with iron ore than with their home indices. A 1-3 day lag between commodity and equity moves is plausible. Larger commodity moves produce larger relative equity moves.

**Null.** Producers track home indices more than the commodity. No measurable lag pattern. Equity response disconnected from commodity magnitude.

**Why this plan.** Iron ore is the cleanest available test case for the structural exposure thesis: an Australian-listed equity whose fundamentals are determined by Chinese demand. If the system cannot see this clearly, it cannot see anything more subtle.

### Plan 2: Reserve Diversification and Gold

**Question.** Does the IMF COFER quarterly data on reserve composition correlate with gold price movements over multi-quarter periods? Specifically, do reductions in dollar share or increases in non-dollar/gold share precede or coincide with gold price strength?

**Period.** Backfilled to 2020 to give historical context, plus forward observation through 2027.

**Data.** Quarterly COFER reserve composition. Daily gold spot price. Daily gold-exposed HKEX securities (Zijin Mining, Zhaojin, etc.). Layer 1 indicators on major reserve-holding country debt and currency dynamics.

**Expected.** Quarters showing measurable shifts in reserve composition coincide with or precede gold strength. The relationship is not 1:1 but visible across multiple quarters.

**Null.** Gold price moves independently of COFER data on observable timescales. Reserve composition shifts are too gradual to manifest in tradeable signals.

**Why this plan.** Reserve diversification is the canonical transition signal in Dalio's framework. If we cannot detect its market impact in a directly-related asset (gold), the framework's predictive value for trading is questionable. This is partly a test of the framework itself.

### Plan 3: HKEX Listing Flows as Financial Center Signal

**Question.** Over a twelve-month observation window, do HKEX listing flows (new IPOs, secondary listings, Stock Connect activity) correlate with broader transition signals — China-US bilateral relationship readings, yuan settlement share, and Chinese cycle position estimates?

**Period.** May 2026 through April 2027.

**Data.** HKEX monthly listing statistics. Stock Connect monthly flows. Layer 4 China-US bilateral observations. Layer 5 SWIFT Renminbi Tracker data. Layer 1 China cycle estimates.

**Expected.** Periods of strengthening Chinese cycle indicators and weakening China-US bilateral readings coincide with stronger HKEX listing activity, particularly for mainland-domiciled companies. Stock Connect flows show directional shifts aligned with major bilateral events.

**Null.** HKEX listing activity is driven by idiosyncratic factors (specific company readiness, market window timing) that swamp any structural transition signal.

**Why this plan.** HKEX is your trading venue and the canonical financial-center node in the East-side of the transition. Understanding what drives its activity is foundational to understanding any thesis that involves trading on HKEX.

### Review Discipline

Each plan has an explicit review date. On that date, Craig sits down with the data and writes up what was actually observed — including, importantly, when nothing was observed. The output is a written conclusion, stored alongside the plan, that says one of:

- The expected pattern was observed; here is what we saw and what we conclude.
- The pattern was partially observed; here is what was clear and what was ambiguous.
- The pattern was not observed; here is what the data showed instead.
- The data was insufficient to conclude; here is what we need to extend the plan or replace it.

These written conclusions accumulate into the system's actual learning over time. Without the discipline of writing them, the data accumulates but knowledge does not.

---

## 8. V1 Implementation Scope

The v1 build is a deliberately thin slice of the full architecture. The schema supports the full architecture from day one; the ingestion populates only the v1 slice. This is the discipline that prevents the v1 build from becoming the kind of overscoped project the previous system was.

### Countries — Four

United States, China, Hong Kong, Australia. The US is the incumbent power and the reference point against which transitions are measured; it has the deepest, cleanest data of any country. China is the central transition story. Hong Kong is the trading venue and the structural meeting point of Western and Eastern capital. Australia is the home country and the structurally-exposed observer, with resource trade exposing it to Chinese rise and security alignment exposing it to US position.

### Indicators per Country — Approximately Eight

A starter set per country, chosen for data accessibility and update reliability. Specific indicators to be finalized at implementation time, but covering at minimum: GDP growth, debt-to-GDP, current account, currency strength, military spending as percentage of GDP, an education proxy (e.g., tertiary enrollment rate or PISA), an innovation proxy (e.g., R&D spending or patents per capita), and an internal-cohesion proxy (e.g., wealth gap, polarization measure).

Approximately 32 country-indicator series in v1, updating on quarterly to annual cadences.

### Commodities — Four

Iron ore (CFR Qingdao 62% Fe). Copper (LME spot, with COMEX as cross-reference). Gold (London PM fix). Brent crude (ICE settlement). Daily updates from free public sources where possible.

### Indices and FX — Eight

HSI (Hong Kong), S&P 500 (US), ASX 200 (Australia), Shanghai Composite (China), plus USD/HKD, USD/CNY, AUD/USD, and USD/Gold. Daily updates.

### Layer 5 Sources — Two

IMF COFER quarterly reserve composition (free, published quarterly with two-quarter lag). HKEX monthly listing statistics (free, published monthly). Both directly relevant to the transition thesis. Other Layer 5 sources (BIS, SWFs, SWIFT Renminbi Tracker) are deferred to v1.5 or v2.

### News — One Source

HKEX disclosure feed. Machine-readable, official, immediately available, with high signal density for HKEX-listed names. Symbol extraction and storage are the v1 ingestion scope. Classification is reserved for later — v1 stores raw news with extracted symbols and lets richer classification develop as theses identify what categories matter.

### Securities — 20 to 30 HKEX Names

A starter set spanning the v1 transition themes:

- Critical minerals (Zijin Mining, Ganfeng Lithium, Tianqi Lithium, China Molybdenum)
- Financial infrastructure (HKEX itself, HSBC, Hang Seng Bank)
- Energy (CNOOC, PetroChina, Sinopec, China Shenhua)
- Resources broadly (Yanzhou Coal, Aluminum Corp of China)
- Iron ore exposure (Hong Kong-listed names plus ASX cross-reference)
- A sample of Hang Seng Index constituents for market-neutral context

Final list to be selected at implementation time. The exact names matter less than the thematic coverage.

### Bilateral Relationships — Limited Initial Set

For v1, a tractable subset of the country-pair dimensions:

- Bilateral trade volumes (UN Comtrade, monthly with several months' lag) for all 6 country pairs (US-China, US-HK, US-Australia, China-HK, China-Australia, HK-Australia)
- UN voting alignment scores (annual, from Voeten dataset) for the same 6 pairs

Other dimensions (FDI direction, currency arrangements, defense cooperation, technology alignment) are deferred to v1.5.

### Cycle Interpretation — Quarterly, Archetype-Driven

Cycle position estimates for all four v1 countries, updated quarterly. The Macro Theorist archetype produces the formal reading; the other three archetypes peer-review it; Craig synthesizes and decides whether to accept, modify, or override. As the data accumulates, the estimates become more grounded and better-justified across all four lenses.

### Analytical Archetypes — All Four from Day One

The four archetypes (Historian, Strategist, Macro Theorist, Skeptic) are part of v1, not deferred. Each runs as a Claude Code instance on the production droplet on its own schedule. They produce weekly analyses, peer-review each other's conclusions, and have latitude to propose model-training experiments. The infrastructure for running them, recording their outputs, and surfacing their disagreements is built in v1.

This is non-negotiable for v1 because the archetypes are what makes the system sustainable for one researcher. Without them, the analytical work falls back on Craig and the system becomes the kind of obligation that the conversation explicitly tried to avoid. With them, Craig's role is synthesis and decision, not analysis.

### Learning Plans — Three

The three plans described in Section 7. Each has its review date. Each has its explicit data dependencies, all of which are within the v1 collection scope.

### What Is Not in V1

To be explicit:

- No automated trading. No execution. No position management.
- No agent or LLM in the runtime *trading* loop. (The analytical archetypes described above are explicitly part of v1, but they analyse data; they do not trade.)
- No system prompts driving trading decisions, no tier criteria, no discipline rules, no consciousness layer in the old sense.
- No additional countries beyond the four (Japan, India, Saudi Arabia, South Africa come in v1.5).
- No additional commodities beyond the four.
- No real-time data; daily resolution is sufficient.
- No alerting, no dashboards (yet); inspection is via the archetypes' output documents and SQL queries.
- No fine-tuning of large models. Model-training experiments proposed by archetypes are scoped to small, specific patterns — not broad foundation-model fine-tuning. Broader fine-tuning waits for v3 or v4 once the dataset is mature.

### V1 Implementation Estimate

In rough terms, the v1 build is approximately:

- 2,500 to 3,500 lines of Python for ingestion, data utilities, and archetype orchestration
- A schema of 16 to 20 core tables (the original 12-15 plus the archetype and model tables)
- Seven or eight ingestion jobs and four archetype analysis jobs, each scheduled by cron at appropriate cadences
- One small VPS for ingestion and database
- A second compute resource for the archetype Claude Code instances and any model-training experiments — likely a modestly-specified GPU droplet on DigitalOcean if local model training proves useful, or simply additional CPU capacity if the archetype work and any small-model experiments fit
- Data sources almost entirely free (Yahoo Finance, FRED, Stooq, World Bank, IMF, UN Comtrade, HKEX disclosure feed, Investing.com for some commodities)
- The most significant ongoing cost is Claude API usage by the archetypes; this is bounded by their cadence (weekly substantive runs, monthly synthesis, quarterly cycle reviews) and is expected to be modest relative to the original agent design's per-cycle calls

The build itself, executed cleanly, is weeks to a couple of months. The patient observation that follows is years.

---

## 9. Migration Plan

The existing Catalyst system is the predecessor. Substantial parts of it are usable; substantial parts must be deleted cleanly so that the v1 build is not contaminated by architectural assumptions from the agent era.

### What Is Deleted

The following components are removed entirely:

- The agent loop in `unified_agent.py` and `coordinator.py`
- All system prompts (`agents/coordinator/system_prompt.py` and related)
- Tier criteria as prose, discipline rules, degraded mode handling
- The six-layer consciousness cycle
- Inter-agent messaging infrastructure
- The `big_bro`, `public_claude`, `dev_claude`, and `intl_claude` agent identities and their distinct deployments
- The `catalyst_research` consciousness database in its current shape (the *concept* of an observations/learnings store survives, but the inter-agent-communication schema is replaced)
- The position monitor signal taxonomy and Haiku consultation logic
- The scanner's tiered scoring and composite ranking
- The `MAX_HAIKU_CALLS_PER_CYCLE` budget and all Anthropic API budget allocations
- Multi-agent droplet deployments

This is sunk cost. It served its purpose by clarifying what does not work. Keeping it around as "we might come back to it" creates fragmentation. Clean deletion frees attention.

### What Is Repurposed

- The Moomoo client and OpenD integration — directly reusable for HKEX market data ingestion in Layer 2 and Layer 3, even though we are not trading. The same connection that places orders can pull quotes and historical bars.
- The `catalyst_research` PostgreSQL database — the database itself stays, dedicated to this system. Its legacy consciousness-era tables are dropped; the new schema replaces them. The intl trading database (`catalyst_intl`) is untouched by the research build.
- The existing `securities` table — extended with theme tags and country exposure metadata.
- The lot-sizing, symbol-normalization, and OpenD-reconnect logic — reusable utilities, kept.
- The document control discipline (version headers, dated revisions, revision history tables) — applied to all new documentation.
- The `catalyst-trading-system` GitHub repo — repurposed as the home of the new architecture. The `catalyst-agent/` droplet-only directory and its v8 brain code are archived rather than tracked.

### What Is Built New

- The full Layer 1 ingestion pipeline (country indicators from IMF, World Bank, BEA, NBS, RBA, HKMA)
- Layer 2 ingestion for non-HKEX market data (S&P 500, ASX, Shanghai Composite, FX, commodities) from public sources
- Layer 3 news ingestion from HKEX disclosure feed
- Layer 4 bilateral relationship ingestion from UN Comtrade and Voeten UN voting data
- Layer 5 ingestion for IMF COFER and HKEX listing statistics
- Cycle interpretation tooling (initially manual, with the data structures supporting it)
- Learning plan and thesis tracking schema and tooling
- Inspection utilities — a small library of common queries

### Migration Sequence

The sequence matters. Each step is reversible until the next begins; nothing is deleted until what replaces it works.

**Step 1.** Stop all running agent cron jobs on the production droplet. The system goes idle. This is acceptable because the system was producing zero economic value and was at risk of producing negative value from misfiring agent cycles.

**Step 2.** Snapshot the current `catalyst_intl` and `catalyst_research` databases. These are insurance.

**Step 3.** Drop the legacy consciousness-era tables from `catalyst_research`. Build the new schema in `catalyst_research`. The new tables share no names with the legacy ones, so this is a clean replacement rather than a coexistence migration.

**Step 4.** Build and test ingestion jobs against the new schema, country by country, layer by layer. Australia first (your home, easy data), then US (deepest data, validates the schema's handling of dense series), then China (validates handling of mixed-quality data), then Hong Kong.

**Step 5.** Once ingestion is working and producing observable data for at least four weeks, migrate any salvageable historical data from the old tables to the new schema, marked as `backfill=true`.

**Step 6.** Drop the old agent-era tables. Remove the agent code from the production droplet. Archive the `catalyst-agent/` directory. Update CLAUDE.md and architecture documentation to reflect the new shape.

**Step 7.** Begin the three v1 learning plans formally. Set their review dates. Begin observation.

The expected calendar time for steps 1–7 is approximately four to six weeks, executed by little_bro under your direction with this document as the specification.

### Credentials and Cleanup

Before any ingestion code is written, the credentials known to have been exposed in earlier sessions are rotated:

- Anthropic API key (the previous one is no longer needed; the new system has no agent runtime calls)
- PostgreSQL password
- Alpaca keys (no longer in use; the US trading droplet is decommissioned)
- Moomoo trade unlock password (kept but rotated)

The droplet cleanup sequence (52 dangling Docker images, 10 orphaned volumes, build cache) is executed as part of step 6, freeing the approximately 21 GB of disk space currently consumed by the agent infrastructure.

---

## 10. Review Cadences

The system's value comes from disciplined review of the conclusions the automation produces. The data collection runs on its own. The archetype analysis runs on its own. Craig's role is the human review at defined synthesis points, not maintenance of the system itself.

**Daily (fully automated).** Ingestion jobs run on cron. Daily market data, FX, commodities, news. Logs are written. No human attention unless errors are flagged.

**Weekly (mostly automated).** The four analytical archetypes run their weekly analysis — each producing independent conclusions on what the past week's observations show, followed by peer review where each archetype reads and challenges the others' work. The output is a structured weekly report containing four perspectives, the disagreements between them, and explicit notes on what each archetype is uncertain about. Craig reads this report — perhaps fifteen to thirty minutes. He is not analyzing the data; he is reading the analysis the system produced.

**Monthly (substantive synthesis).** Craig sits with the accumulated weekly reports plus a monthly summary the system generates. The question he is answering is not "what did the data show" — that work is done. The question is "what do I think about what the archetypes are concluding, where do I find their disagreements meaningful, what should I tell them to look at differently next month." Probably an hour or two. The output is Craig's own written notes, stored alongside the system's analysis.

**Quarterly (cycle interpretation review).** The Macro Theorist archetype produces a formal cycle-position update for each country, drawing on the quarter's observations and reading them through Dalio's framework. The other archetypes peer-review this update. Craig then reviews the cycle estimates and decides whether to accept them, modify them, or flag where his own reading diverges. Half a day per quarter, focused on synthesis rather than data work.

**Per learning plan review date.** The system produces a structured outcome summary at the plan's review date — what was hypothesized, what was observed, what the four archetypes conclude, where they disagree. Craig reads, decides whether to extend, replace, or retire the plan, and writes the formal conclusion. Probably one to two hours per plan, executed two or three times per year per active plan.

**Annually (architecture review).** Is the schema serving the questions we want to ask? Are there layers or sources we now understand we need? Are there archetypes whose work is consistently more or less valuable, and should the set evolve? Have any of the model-training experiments produced patterns worth integrating into the analytical pipeline? Should the country set expand, the commodity set expand, the security set expand? The annual review is when the architecture itself is allowed to change, deliberately, with a documented rationale.

These cadences match the underlying phenomenon. The transition unfolds over years; the archetypes observe and analyze on weekly to quarterly rhythms; Craig synthesizes monthly and quarterly; the architecture itself revises annually. Forcing faster cadences produces noise without insight. Slower cadences mean missed structural shifts.

The discipline that matters most is not analytical bandwidth — the system supplies that. The discipline is showing up to the synthesis points and engaging seriously with what the archetypes have produced. That is what the architecture asks of Craig, and that is what makes the architecture sustainable.

---

## Closing Note

This architecture is the product of a long conversation that moved through several reframings — from "fix the agent system" to "go agentless" to "research first" to "track the West-to-East transition" to "automated multi-archetype analysis with human synthesis at the decision point." Each reframing was substantive; the final shape is more honest than any of the earlier ones, and more sustainable.

The architecture is intentionally complete in its conceptual structure but intentionally narrow in its v1 implementation. Five layers of observation, four analytical archetypes with peer review, eight countries, twelve commodities, multiple Layer 5 sources, full graph relationships, model-training experiments emerging from archetype analysis — that is the target. Four countries, four commodities, two Layer 5 sources, six relationship pairs, three learning plans, and the four archetypes operating from day one — that is what gets built first.

The system that emerges from v1 will not make money in v1. It will produce, over months and years, a structured record of the transition as it unfolds, observed across layers that are individually meaningful and jointly diagnostic, interpreted through analytical lenses that disagree honestly with each other. That record — and the disagreements within it — is the foundation. Everything else is downstream of patient observation, multi-perspective analysis, and disciplined human synthesis done well in v1.

The mission "enable the poor through accessible algorithmic trading" is preserved by this approach, not abandoned. A research-first system that can be self-hosted, that automates the work that does not require human judgment, that uses multiple analytical perspectives to surface uncertainty rather than hide it, that costs almost nothing to run, that produces durable knowledge rather than fragile prompts — that is more aligned with the mission than the agent system ever was.

The deepest insight in the design is the recognition that one researcher cannot analyze the world alone, but one researcher can review and synthesize analysis that automation produces. The archetypes do the analytical work. The peer review surfaces disagreement. The model-training experiments accumulate patterns the system has learned to recognize. Craig synthesizes, decides, and acts. Each part of the system does what it does best.

What remains is the work itself: build the schema, build the ingestion, set the archetypes running, watch what they produce, write the conclusions, refine the theses, and over time let the data speak through multiple lenses. The discipline is to do this slowly, honestly, and with appropriate humility about how much we do not yet know.

---

*End of document.*
