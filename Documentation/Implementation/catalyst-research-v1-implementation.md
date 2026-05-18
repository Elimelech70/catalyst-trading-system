# Catalyst Research — v1 Implementation Guide

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-research-v1-implementation.md
**Version:** 1.1.0
**Created:** 2026-05-18
**Updated by:** Craig + Claude
**Companion to:** `Documentation/Design/catalyst-research-architecture-v1.md` (v1.2.0, 2026-05-18)
**Purpose:** Buildable specification for v1 of the catalyst-research system. Translates the architecture document into concrete artefacts: full DDL, ingestion job specs, archetype orchestration design, folder layout, and cron schedule. This is the document the v1 build executes against.

---

## REVISION HISTORY

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-05-18 | Craig + Claude | Initial guide. Spec drawn from architecture v1.1.0. |
| 1.1.0 | 2026-05-18 | Craig + Claude | Schema home moved to the dedicated `catalyst_research` database (matching architecture v1.2.0). `` table prefix dropped — namespace isolation now comes from the DB. Phase 0.3, Phase 1, Phase 2 writes-to column, Phase 4.3 env vars, and Phase 4.5 cleanup updated accordingly. |

---

## HOW TO READ THIS DOCUMENT

This guide assumes the architecture document has been read. It does not restate the *why*; it specifies the *what* and *how*. The architecture is the source of truth for mission, layers, archetypes, and review cadences. This document is the source of truth for table definitions, file paths, job schedules, and operational procedure.

The build is staged in four phases that map to Migration Steps 2–6 in the architecture:

- **Phase 0** — preparation: credential rotation, DB snapshot, agent decommissioning confirmation
- **Phase 1** — schema: full DDL applied to the dedicated `catalyst_research` database
- **Phase 2** — ingestion: country-by-country build of Layer 1–5 ingestion jobs
- **Phase 3** — archetypes: orchestration of the four analytical Claude Code instances
- **Phase 4** — operations: folder layout, cron schedule, inspection utilities, cleanup of old agent tables

Each phase has explicit entry and exit criteria. A phase is not complete until its exit criteria pass.

---

## PHASE 0 — PREPARATION

**Entry criteria:** the agent crons on the US droplet are confirmed stopped (architecture Migration Step 1 — completed 2026-05-18 per repo-root `CLAUDE.md`).

### 0.1 Snapshot the databases

DigitalOcean managed PostgreSQL snapshot of `catalyst_research` taken before any DDL runs. The snapshot is insurance against the Phase 0.3 legacy-table drops and against schema mistakes during Phase 1. `catalyst_intl` is not modified by this build so does not strictly need a fresh snapshot, but one is cheap and prudent.

```bash
# Triggered via DigitalOcean control panel or doctl:
doctl databases backups list catalyst-research
doctl databases backups list catalyst-intl  # prudent, not required
# Confirm a backup exists from today before proceeding.
```

### 0.2 Rotate exposed credentials

The following credentials were known-exposed during the agent era and are rotated before any new code is written. The new system has no agent runtime API calls except the archetype Claude Code instances, so the previous Anthropic key can be retired entirely; a new key is provisioned scoped only to archetype usage.

| Credential | Action | Stored in |
|---|---|---|
| Anthropic API key (agent-era) | Revoke | — |
| Anthropic API key (archetypes) | Provision new | `.env` → `ANTHROPIC_API_KEY` |
| PostgreSQL password (catalyst_research) | Rotate via DO panel | `.env` → `RESEARCH_DATABASE_URL` |
| Alpaca paper/live keys | Revoke (US droplet decommissioned) | — |
| Moomoo trade-unlock password | Rotate (kept; intl still uses Moomoo for data) | intl droplet `.env` |
| GitHub token | Confirm current (rotated 2026-03-29 per memory) | local only |

### 0.3 Prepare the target database

Architecture Section 6 (v1.2.0) specifies the dedicated `catalyst_research` database — the cluster DB originally provisioned for this purpose, currently holding only legacy consciousness-era tables. Phase 0 drops those legacy tables so Phase 1 lands in a clean DB.

Identify the legacy tables (they vary slightly by deployment history) and confirm with `psql`:

```bash
psql "$RESEARCH_DATABASE_URL" -c "\dt"
```

Expected legacy candidates include `observations`, `learnings`, `messages`, and any consciousness-cycle artefacts. None of these share names with the new schema, so the drop is safe relative to the new build. Confirm against the snapshot from 0.1 before issuing the drops.

```sql
-- Wrapped in a transaction; abort if anything unexpected appears.
BEGIN;
DROP TABLE IF EXISTS observations CASCADE;
DROP TABLE IF EXISTS learnings CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
-- ...one DROP per legacy table identified at audit time...
COMMIT;
```

> ⚠️ The `catalyst_intl` trading database is **not touched** by this build. Research and intl trading live in separate databases on the same cluster.

`catalyst_dev` remains deprecated and may be dropped at Migration Step 6 (Phase 4.5).

**Exit criteria:** snapshot exists, credentials rotated, `catalyst_research` legacy tables dropped, `RESEARCH_DATABASE_URL` set in the droplet `.env`.

---

## PHASE 1 — SCHEMA

**Entry criteria:** Phase 0 complete.

The full DDL lives in a single migration file:

```
catalyst-research/sql/001_initial_schema.sql
```

It is applied to `catalyst_research` as a single transaction. If any statement fails, the entire migration rolls back and the snapshot stays as fallback.

### 1.1 Naming and discipline rules

- Table names are unprefixed. The dedicated `catalyst_research` database provides namespace isolation; no prefix is needed.
- Every fact-bearing table carries: `event_date` (or `period_start` + `period_end`), `source`, `recorded_at`, `backfill`.
- Facts are never updated in place. Revisions append a new row with the same business key and a later `recorded_at`. "Current best estimate" is a query, not a stored value.
- Indexes are time-first on every fact table.
- All timestamps are `timestamptz`; all stored UTC.
- ISO 3166-1 alpha-3 country codes (`USA`, `CHN`, `HKG`, `AUS`).

### 1.2 DDL

```sql
-- catalyst-research/sql/001_initial_schema.sql
-- Applied to the dedicated catalyst_research database (legacy tables already dropped in Phase 0.3).
-- Run inside a single transaction.

BEGIN;

-- ============================================================
-- Reference and entity tables
-- ============================================================

CREATE TABLE countries (
    country_code      char(3)        PRIMARY KEY,
    name              varchar(128)   NOT NULL,
    region            varchar(64),
    primary_currency  char(3),
    notes             text,
    created_at        timestamptz    NOT NULL DEFAULT now()
);

CREATE TABLE sectors (
    id                bigserial      PRIMARY KEY,
    code              varchar(32)    NOT NULL,
    name              varchar(128)   NOT NULL,
    country_code      char(3)        REFERENCES countries(country_code),  -- NULL means 'global'
    parent_sector_id  bigint         REFERENCES sectors(id),
    notes             text,
    created_at        timestamptz    NOT NULL DEFAULT now(),
    UNIQUE (code, country_code)
);

CREATE TABLE themes (
    id                bigserial      PRIMARY KEY,
    name              varchar(128)   NOT NULL UNIQUE,
    description       text,
    created_at        timestamptz    NOT NULL DEFAULT now()
);

CREATE TABLE securities (
    id                bigserial      PRIMARY KEY,
    symbol            varchar(32)    NOT NULL,
    exchange          varchar(16)    NOT NULL,
    name              varchar(256),
    listing_country   char(3)        REFERENCES countries(country_code),
    primary_sector_id bigint         REFERENCES sectors(id),
    notes             text,
    created_at        timestamptz    NOT NULL DEFAULT now(),
    UNIQUE (symbol, exchange)
);

CREATE TABLE security_themes (
    security_id  bigint  NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
    theme_id     bigint  NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    PRIMARY KEY (security_id, theme_id)
);

CREATE TABLE commodities (
    id                bigserial      PRIMARY KEY,
    name              varchar(64)    NOT NULL UNIQUE,
    category          varchar(32)    NOT NULL,  -- energy, industrial_metals, critical_minerals, precious_metals, agricultural
    reference_benchmark varchar(128),
    unit              varchar(32),
    notes             text,
    created_at        timestamptz    NOT NULL DEFAULT now()
);

-- ============================================================
-- Layer 1: Country macro indicators
-- ============================================================

CREATE TABLE country_indicators (
    id             bigserial     PRIMARY KEY,
    country_code   char(3)       NOT NULL REFERENCES countries(country_code),
    indicator_name varchar(64)   NOT NULL,        -- e.g. 'debt_to_gdp', 'military_spending_pct_gdp'
    dalio_power    varchar(32),                   -- education|innovation|competitiveness|military|trade|output|financial_center|reserve_currency|cycle|NULL
    value          numeric        NOT NULL,
    unit           varchar(32)    NOT NULL,
    period_start   date           NOT NULL,
    period_end     date           NOT NULL,
    event_date     date           NOT NULL,
    source         varchar(64)    NOT NULL,
    recorded_at    timestamptz    NOT NULL DEFAULT now(),
    backfill       boolean        NOT NULL DEFAULT false,
    notes          text
);

CREATE INDEX idx_country_indicators_lookup
    ON country_indicators (country_code, indicator_name, period_end DESC, recorded_at DESC);

CREATE TABLE country_cycle_estimates (
    id                    bigserial     PRIMARY KEY,
    country_code          char(3)       NOT NULL REFERENCES countries(country_code),
    as_of_date            date          NOT NULL,
    composite_power_score numeric       NOT NULL CHECK (composite_power_score BETWEEN 0 AND 1),
    cycle_phase           varchar(32)   NOT NULL
        CHECK (cycle_phase IN ('rising_early','rising_mid','rising_late','top',
                               'declining_early','declining_mid','declining_late')),
    direction             varchar(16)   NOT NULL
        CHECK (direction IN ('strengthening','stable','weakening')),
    direction_magnitude   numeric,
    confidence            varchar(8)    NOT NULL
        CHECK (confidence IN ('high','medium','low')),
    supporting_indicators jsonb,
    notes                 text,
    recorded_at           timestamptz   NOT NULL DEFAULT now()
);

CREATE INDEX idx_cycle_estimates_lookup
    ON country_cycle_estimates (country_code, as_of_date DESC, recorded_at DESC);

-- ============================================================
-- Layer 2: Markets and commodities
-- ============================================================

CREATE TABLE market_prices (
    id          bigserial   PRIMARY KEY,
    series_id   varchar(64) NOT NULL,             -- e.g. 'index.HSI', 'fx.USDHKD', 'commodity.iron_ore', 'yield.US10Y'
    series_type varchar(16) NOT NULL CHECK (series_type IN ('index','fx','yield','commodity')),
    trade_date  date        NOT NULL,
    open        numeric,
    high        numeric,
    low         numeric,
    close       numeric     NOT NULL,
    volume      bigint,
    source      varchar(64) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    backfill    boolean     NOT NULL DEFAULT false
);

CREATE INDEX idx_market_prices_lookup
    ON market_prices (series_id, trade_date DESC, recorded_at DESC);

CREATE TABLE security_prices (
    id           bigserial   PRIMARY KEY,
    security_id  bigint      NOT NULL REFERENCES securities(id),
    trade_date   date        NOT NULL,
    open         numeric,
    high         numeric,
    low          numeric,
    close        numeric     NOT NULL,
    volume       bigint,
    adj_close    numeric,
    source       varchar(64) NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    backfill     boolean     NOT NULL DEFAULT false
);

CREATE INDEX idx_security_prices_lookup
    ON security_prices (security_id, trade_date DESC, recorded_at DESC);

-- ============================================================
-- Layer 3: News and events
-- ============================================================

CREATE TABLE news_events (
    id             bigserial   PRIMARY KEY,
    source         varchar(64) NOT NULL,        -- e.g. 'HKEX_disclosure'
    external_id    varchar(128),                -- source-side unique id, for dedup
    headline       text        NOT NULL,
    body           text,
    event_date     timestamptz NOT NULL,
    recorded_at    timestamptz NOT NULL DEFAULT now(),
    classification varchar(32),                 -- earnings|m_and_a|regulatory|policy|other|NULL
    sentiment      varchar(16),                 -- reserved for later
    raw_payload    jsonb       NOT NULL,
    UNIQUE (source, external_id)
);

CREATE INDEX idx_news_events_time ON news_events (event_date DESC);

CREATE TABLE news_securities (
    news_event_id bigint NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
    security_id   bigint NOT NULL REFERENCES securities(id) ON DELETE CASCADE,
    PRIMARY KEY (news_event_id, security_id)
);

CREATE TABLE news_themes (
    news_event_id bigint NOT NULL REFERENCES news_events(id) ON DELETE CASCADE,
    theme_id      bigint NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    PRIMARY KEY (news_event_id, theme_id)
);

-- ============================================================
-- Layer 4: Bilateral relationships
-- ============================================================

CREATE TABLE country_pair_observations (
    id           bigserial   PRIMARY KEY,
    country_a    char(3)     NOT NULL REFERENCES countries(country_code),  -- alphabetically first
    country_b    char(3)     NOT NULL REFERENCES countries(country_code),  -- alphabetically second
    dimension    varchar(64) NOT NULL,
    value        numeric     NOT NULL,
    unit         varchar(32) NOT NULL,
    period_start date,
    period_end   date,
    event_date   date        NOT NULL,
    source       varchar(64) NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    backfill     boolean     NOT NULL DEFAULT false,
    CHECK (country_a < country_b)
);

CREATE INDEX idx_pair_observations_lookup
    ON country_pair_observations (country_a, country_b, dimension, event_date DESC, recorded_at DESC);

-- ============================================================
-- Layer 5: Financial infrastructure
-- ============================================================

CREATE TABLE financial_infra_observations (
    id           bigserial   PRIMARY KEY,
    infra_type   varchar(64) NOT NULL,            -- e.g. 'cofer_reserve_composition', 'hkex_listing'
    entity_id    varchar(64),                     -- e.g. 'CNY', 'HKEX'
    metric_name  varchar(64) NOT NULL,
    value        numeric     NOT NULL,
    unit         varchar(32) NOT NULL,
    period_start date,
    period_end   date,
    event_date   date        NOT NULL,
    source       varchar(64) NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    backfill     boolean     NOT NULL DEFAULT false,
    metadata     jsonb
);

CREATE INDEX idx_infra_observations_lookup
    ON financial_infra_observations (infra_type, metric_name, event_date DESC, recorded_at DESC);

-- ============================================================
-- Theses and learning plans
-- ============================================================

CREATE TABLE learning_plans (
    id                    bigserial   PRIMARY KEY,
    name                  varchar(128) NOT NULL UNIQUE,
    question              text         NOT NULL,
    period_start          date         NOT NULL,
    period_end            date         NOT NULL,
    expected_observations text,
    null_hypothesis       text,
    data_sources          jsonb,
    status                varchar(16)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','under_review','concluded','abandoned')),
    outcome_notes         text,
    created_at            timestamptz  NOT NULL DEFAULT now(),
    updated_at            timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE investment_theses (
    id                    bigserial   PRIMARY KEY,
    name                  varchar(128) NOT NULL UNIQUE,
    description           text         NOT NULL,
    supporting_layers     jsonb,
    invalidation_criteria text         NOT NULL,
    conviction_score      numeric      NOT NULL CHECK (conviction_score BETWEEN 0 AND 1),
    target_securities     jsonb,
    status                varchar(16)  NOT NULL DEFAULT 'forming'
        CHECK (status IN ('forming','active','under_pressure','invalidated','fully_priced')),
    created_at            timestamptz  NOT NULL DEFAULT now(),
    updated_at            timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE thesis_history (
    id            bigserial   PRIMARY KEY,
    thesis_id     bigint      NOT NULL REFERENCES investment_theses(id) ON DELETE CASCADE,
    snapshot      jsonb       NOT NULL,            -- full thesis row at this moment
    change_reason text,
    recorded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_thesis_history_thesis ON thesis_history (thesis_id, recorded_at DESC);

-- ============================================================
-- Archetype analysis
-- ============================================================

CREATE TABLE archetype_analyses (
    id                      bigserial   PRIMARY KEY,
    archetype               varchar(16) NOT NULL
        CHECK (archetype IN ('historian','strategist','macro_theorist','skeptic')),
    run_date                date        NOT NULL,
    period_start            date        NOT NULL,
    period_end              date        NOT NULL,
    scope                   varchar(32) NOT NULL
        CHECK (scope IN ('weekly','monthly','quarterly','learning_plan_review','ad_hoc')),
    conclusions             text        NOT NULL,
    uncertainties           text,
    supporting_observations jsonb,
    recorded_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_archetype_analyses_lookup
    ON archetype_analyses (archetype, run_date DESC);

CREATE TABLE archetype_peer_reviews (
    id                   bigserial   PRIMARY KEY,
    reviewer_archetype   varchar(16) NOT NULL,
    reviewed_analysis_id bigint      NOT NULL REFERENCES archetype_analyses(id) ON DELETE CASCADE,
    agreement            varchar(16) NOT NULL
        CHECK (agreement IN ('strong_agree','agree','disagree','strong_disagree')),
    critique             text        NOT NULL,
    recorded_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_peer_reviews_reviewed ON archetype_peer_reviews (reviewed_analysis_id);

CREATE TABLE model_proposals (
    id                   bigserial   PRIMARY KEY,
    proposing_archetype  varchar(16) NOT NULL,
    pattern_description  text        NOT NULL,
    data_series          jsonb       NOT NULL,
    model_structure      text        NOT NULL,
    success_criteria     text        NOT NULL,
    risks                text,
    status               varchar(24) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed','training','evaluated_success','evaluated_failure','integrated')),
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE models_trained (
    id                           bigserial   PRIMARY KEY,
    proposal_id                  bigint      REFERENCES model_proposals(id),
    name                         varchar(128) NOT NULL UNIQUE,
    training_dataset_description text,
    validation_results           jsonb,
    in_use                       boolean     NOT NULL DEFAULT false,
    created_at                   timestamptz NOT NULL DEFAULT now(),
    retired_at                   timestamptz
);

COMMIT;
```

### 1.3 Seed data

Immediately after the migration, a separate idempotent seed script (`catalyst-research/sql/002_seed_v1.sql`) inserts:

- The four v1 countries (USA, CHN, HKG, AUS).
- The four v1 commodities (iron_ore, copper, gold, brent_crude).
- A starter set of v1 themes: `yuan_internationalization`, `critical_minerals`, `chinese_demand`, `financial_infrastructure_east`, `reserve_diversification`.
- The 20–30 HKEX security rows (final list selected at implementation time per architecture Section 8).
- The three v1 learning plans as `learning_plans` rows (full text from architecture Section 7).

The seed script uses `INSERT ... ON CONFLICT DO NOTHING` so re-running it is safe.

### 1.4 Phase 1 exit criteria

- `001_initial_schema.sql` applied cleanly inside a transaction.
- `002_seed_v1.sql` applied; the four countries, four commodities, and three learning plans exist.
- A read-only smoke query (`SELECT count(*) FROM countries;` etc.) returns expected counts.

---

## PHASE 2 — INGESTION

**Entry criteria:** Phase 1 complete.

Per architecture Migration Step 4, ingestion is built **country by country, layer by layer**: Australia first, then US, then China, then Hong Kong. The reason: Australia has clean accessible data, US validates schema handling of dense series, China validates handling of mixed-quality data, HK validates the trading-venue layer.

### 2.1 Ingestion job inventory

Each job is a single Python entry point in `catalyst-research/ingestion/`, invoked by cron, writing to one or more Layer tables. All jobs share a common adapter (`catalyst-research/ingestion/_adapter.py`) that handles DB connection, idempotency (append-on-revision), and structured logging.

| Layer | Job | Source | Cadence | Cron | Writes to |
|---|---|---|---|---|---|
| 1 | `ingest_country_indicators_imf` | IMF WEO + IMF datamapper API | Quarterly (after release dates) | `0 6 1 1,4,7,10 *` | `country_indicators` |
| 1 | `ingest_country_indicators_worldbank` | World Bank Indicators API | Quarterly | `0 7 1 1,4,7,10 *` | `country_indicators` |
| 1 | `ingest_country_indicators_national` | BEA (US), NBS (CN), HKMA (HK), RBA/ABS (AU) | Quarterly (staggered) | per-country | `country_indicators` |
| 2 | `ingest_market_prices_daily` | Yahoo Finance + Stooq fallback | Daily, post-close | `30 22 * * 1-5` UTC | `market_prices` |
| 2 | `ingest_commodity_prices_daily` | Yahoo Finance + Investing.com | Daily, post-close | `45 22 * * 1-5` UTC | `market_prices` |
| 2/3 | `ingest_security_prices_daily` | Moomoo OpenD (reused from intl) | Daily, post-HKEX-close | `30 8 * * 1-5` UTC (HKEX 16:00 HKT close) | `security_prices` |
| 3 | `ingest_hkex_disclosure_feed` | HKEX disclosure feed | Continuous (poll every 15 min during HKEX hours) | `*/15 1-9 * * 1-5` UTC | `news_events`, `news_securities` |
| 4 | `ingest_un_comtrade` | UN Comtrade API | Monthly (with ~3 month lag) | `0 8 5 * *` | `country_pair_observations` |
| 4 | `ingest_un_voting_alignment` | Voeten UN voting dataset | Annual | `0 8 1 6 *` | `country_pair_observations` |
| 5 | `ingest_imf_cofer` | IMF COFER | Quarterly (with ~6 month lag) | `0 9 5 1,4,7,10 *` | `financial_infra_observations` |
| 5 | `ingest_hkex_listing_stats` | HKEX monthly listing statistics | Monthly | `0 9 7 * *` | `financial_infra_observations` |

Cron times in UTC. The intl droplet already runs in UTC.

### 2.2 Idempotency and revision-append

Every ingestion job follows the same pattern:

1. Fetch source data for the configured window.
2. For each candidate row, compute the business key (e.g. `(country_code, indicator_name, period_end)`).
3. Check whether a row already exists with that business key.
   - If no row exists → INSERT.
   - If a row exists and the `value` matches the latest → skip (no-op, idempotent re-run).
   - If a row exists but the `value` differs → INSERT a new row with the same business key and a fresh `recorded_at` (revision).
4. Log counts of inserted vs. revised vs. skipped.

There is no UPDATE on fact tables. Ever. This is the architectural commitment that makes the revision history first-class data.

### 2.3 Backfill discipline

Initial population draws historical data going back per the relevant learning plan:

- Layer 1 country indicators: 2015 onward
- Layer 2 markets and commodities: 2015 onward
- Layer 4 bilateral observations: 2015 onward
- Layer 5 COFER: 2020 onward (per Plan 2 in architecture Section 7)
- Layer 5 HKEX listings: 2015 onward
- Layer 3 news: from go-live forward only; historical news is not backfilled.

All historical rows are inserted with `backfill = true`. Live ongoing inserts use `backfill = false`. This distinction is consulted by any analysis sensitive to information-availability timing.

### 2.4 Phase 2 build order

1. `ingest_market_prices_daily` (simplest; validates the adapter pattern; useful immediately).
2. Layer 1 for Australia (RBA + ABS).
3. Layer 1 for the US (BEA + FRED).
4. Layer 1 for China (NBS + IMF for China-specific series).
5. Layer 1 for Hong Kong (HKMA).
6. `ingest_imf_cofer` and `ingest_hkex_listing_stats` (Layer 5).
7. `ingest_un_comtrade` and `ingest_un_voting_alignment` (Layer 4).
8. `ingest_security_prices_daily` and `ingest_hkex_disclosure_feed` (Layer 3, reusing Moomoo client from intl).

Each job is considered done only when it has run successfully on its cron for at least one full natural cadence (a week of daily runs; one quarterly release for quarterly jobs).

### 2.5 Phase 2 exit criteria

- All eleven jobs deployed and on cron.
- Each job has run successfully end-to-end at least once on real source data.
- A spot-check query confirms representative rows are present per country and per layer.
- Logs are flowing to a known location (Phase 4 specifies where).

---

## PHASE 3 — ARCHETYPES

**Entry criteria:** Phase 2 has been producing data for at least four weeks (architecture Migration Step 5 sequencing). Archetypes need data to analyse before they are switched on.

### 3.1 Orchestration model

Each archetype is a **headless Claude Code invocation** run by cron. Concretely:

```bash
claude --print --output-format=json \
       --system-prompt-file=catalyst-research/archetypes/<archetype>/system.md \
       --append-system-prompt "$(catalyst-research/archetypes/build_context.py --archetype <archetype> --scope weekly)" \
       --max-turns 30 \
       --permission-mode acceptEdits \
       > catalyst-research/archetypes/runs/<archetype>_<date>.json
```

The wrapper script `catalyst-research/archetypes/run.py` orchestrates this — it builds the context bundle, invokes Claude Code, and writes the resulting analysis row into `archetype_analyses`.

The archetype has access (via its working directory and a small read-only DB adapter) to:

- Its own system prompt (the archetype's lens).
- The relevant data tables (read-only views).
- Previous analyses from all four archetypes (so it sees historical context).
- The learning plans currently active.

It writes its output as a single structured JSON document with the fields required by `archetype_analyses` (conclusions, uncertainties, supporting_observations). The wrapper validates and inserts.

### 3.2 The four archetypes

Each lives in its own folder with its own system prompt:

```
catalyst-research/archetypes/
├── historian/system.md
├── strategist/system.md
├── macro_theorist/system.md
├── skeptic/system.md
├── run.py              ← invocation wrapper
├── build_context.py    ← context-bundle builder
└── runs/               ← raw run artefacts (json), filed by date
```

Each system prompt is short and lens-focused — fewer than 500 words. The lens is the architecture Section 3.5 description: the Historian places events in historical parallel; the Strategist analyses actor behaviour; the Macro Theorist applies Dalio's framework; the Skeptic looks for disconfirming evidence.

The system prompts are deliberately not over-engineered. The architecture's discipline is that the lens does the work, not the prompt.

### 3.3 Peer review cycle

After the four independent analyses for a given period are written, a second cron job runs the peer-review cycle. Each archetype reads the others' analyses (loaded into context) and produces a review row per analysis reviewed, written to `archetype_peer_reviews`.

The Skeptic's peer-review runs last and is given an explicit instruction in its system prompt to look hardest at the consensus emerging from the other three.

### 3.4 Model proposals

When an archetype identifies a pattern it believes worth attempting to learn, it writes a row to `model_proposals` via the wrapper. Proposals are reviewed manually before any training runs; this is not automated in v1. The training pipeline itself is deferred to v1.5 — for v1, the architecture's commitment is only that the *capture* mechanism exists.

### 3.5 Archetype run schedule

| Run | Cadence | Cron (UTC) |
|---|---|---|
| Four-archetype weekly analysis | Weekly, Saturday 02:00 UTC | `0 2 * * 6` |
| Peer-review cycle for the week | Weekly, Saturday 06:00 UTC | `0 6 * * 6` |
| Monthly synthesis run (longer scope) | Monthly, 1st 02:00 UTC | `0 2 1 * *` |
| Quarterly cycle-position update (Macro Theorist) | Quarterly, 5th 02:00 UTC | `0 2 5 1,4,7,10 *` |
| Learning-plan review (per plan review date) | Ad hoc | manual trigger |

Anthropic API spend is bounded by these cadences. At weekly + monthly + quarterly cadence with four archetypes plus peer review, the system makes roughly 4 + 4 + 4 + 1 = 13 substantial Claude Code runs per month. This is well within a modest monthly budget.

### 3.6 Phase 3 exit criteria

- All four archetypes have completed at least one weekly run end-to-end.
- The peer-review cycle has run at least once and produced reviews against those analyses.
- The output is readable by Craig — a small inspection utility (`scripts/show_weekly_report.py`) produces a human-readable Markdown summary from a week's analyses + reviews.

---

## PHASE 4 — OPERATIONS, FOLDER LAYOUT, CLEANUP

**Entry criteria:** Phase 3 complete and producing weekly reports.

### 4.1 Final folder layout

```
catalyst-trading-system/
├── catalyst-research/                    ← NEW (this implementation)
│   ├── CLAUDE.md                         ← implementation-local runbook
│   ├── CLAUDE-LEARNINGS.md
│   ├── CLAUDE-FOCUS.md
│   ├── README.md
│   ├── requirements.txt
│   ├── .env.template
│   │
│   ├── sql/
│   │   ├── 001_initial_schema.sql
│   │   └── 002_seed_v1.sql
│   │
│   ├── ingestion/
│   │   ├── _adapter.py                   ← shared DB adapter, idempotency, logging
│   │   ├── ingest_market_prices_daily.py
│   │   ├── ingest_commodity_prices_daily.py
│   │   ├── ingest_security_prices_daily.py
│   │   ├── ingest_country_indicators_imf.py
│   │   ├── ingest_country_indicators_worldbank.py
│   │   ├── ingest_country_indicators_national.py
│   │   ├── ingest_hkex_disclosure_feed.py
│   │   ├── ingest_un_comtrade.py
│   │   ├── ingest_un_voting_alignment.py
│   │   ├── ingest_imf_cofer.py
│   │   └── ingest_hkex_listing_stats.py
│   │
│   ├── archetypes/
│   │   ├── run.py
│   │   ├── build_context.py
│   │   ├── historian/system.md
│   │   ├── strategist/system.md
│   │   ├── macro_theorist/system.md
│   │   ├── skeptic/system.md
│   │   └── runs/                         ← gitignored; raw run artefacts
│   │
│   ├── scripts/
│   │   ├── show_weekly_report.py         ← Markdown synthesis of a week
│   │   ├── show_learning_plan.py         ← status + evidence summary per plan
│   │   ├── show_country_indicators.py
│   │   └── seed_learning_plans.py        ← idempotent learning-plan inserter
│   │
│   ├── tests/
│   │   ├── test_adapter_idempotency.py
│   │   └── test_archetype_wrapper.py
│   │
│   └── crontab.txt                       ← reference cron file installed to /etc/cron.d/catalyst-research
│
```

This mirrors the catalyst-international layout pattern (CLAUDE.md trio + agents/ + scripts/ + sql/ + tests/) so that any Claude session opening into `catalyst-research/` finds a familiar shape.

### 4.2 Cron schedule

Installed as `/etc/cron.d/catalyst-research` on the US droplet:

```cron
# /etc/cron.d/catalyst-research
# All times UTC. Conservative offsets between jobs to avoid burst load on free APIs.

PATH=/usr/local/bin:/usr/bin:/bin
SHELL=/bin/bash
MAILTO=""

# Layer 2 daily
30 22 * * 1-5  root  cd /root/catalyst-research && python -m ingestion.ingest_market_prices_daily       >> logs/cron.log 2>&1
45 22 * * 1-5  root  cd /root/catalyst-research && python -m ingestion.ingest_commodity_prices_daily    >> logs/cron.log 2>&1
30 8  * * 1-5  root  cd /root/catalyst-research && python -m ingestion.ingest_security_prices_daily     >> logs/cron.log 2>&1

# Layer 3 news (every 15 min during HKEX trading hours, UTC 01:00-09:00 = HKT 09:00-17:00)
*/15 1-9 * * 1-5  root  cd /root/catalyst-research && python -m ingestion.ingest_hkex_disclosure_feed   >> logs/cron.log 2>&1

# Layer 1 quarterly (staggered across the first week of each quarter)
0 6 1 1,4,7,10 *  root  cd /root/catalyst-research && python -m ingestion.ingest_country_indicators_imf       >> logs/cron.log 2>&1
0 7 1 1,4,7,10 *  root  cd /root/catalyst-research && python -m ingestion.ingest_country_indicators_worldbank >> logs/cron.log 2>&1
0 8 2 1,4,7,10 *  root  cd /root/catalyst-research && python -m ingestion.ingest_country_indicators_national  >> logs/cron.log 2>&1

# Layer 4 monthly / annual
0 8 5 * *      root  cd /root/catalyst-research && python -m ingestion.ingest_un_comtrade               >> logs/cron.log 2>&1
0 8 1 6 *      root  cd /root/catalyst-research && python -m ingestion.ingest_un_voting_alignment       >> logs/cron.log 2>&1

# Layer 5 quarterly / monthly
0 9 5 1,4,7,10 *  root  cd /root/catalyst-research && python -m ingestion.ingest_imf_cofer              >> logs/cron.log 2>&1
0 9 7 * *      root  cd /root/catalyst-research && python -m ingestion.ingest_hkex_listing_stats        >> logs/cron.log 2>&1

# Archetypes
0 2 * * 6      root  cd /root/catalyst-research && python -m archetypes.run --scope=weekly --phase=analysis    >> logs/archetypes.log 2>&1
0 6 * * 6      root  cd /root/catalyst-research && python -m archetypes.run --scope=weekly --phase=peer_review >> logs/archetypes.log 2>&1
0 2 1 * *      root  cd /root/catalyst-research && python -m archetypes.run --scope=monthly                    >> logs/archetypes.log 2>&1
0 2 5 1,4,7,10 *  root  cd /root/catalyst-research && python -m archetypes.run --scope=quarterly --archetype=macro_theorist >> logs/archetypes.log 2>&1
```

### 4.3 Environment variables

Added to the droplet's `.env`:

```
RESEARCH_DATABASE_URL=postgres://...       # dedicated catalyst_research DB
ANTHROPIC_API_KEY=...                      # archetype-only key, scoped budget
HKEX_FEED_URL=...
UN_COMTRADE_API_KEY=...                    # if/when registered
MOOMOO_HOST=127.0.0.1                      # OpenD client reused from intl
MOOMOO_PORT=11111
CR_LOG_DIR=/root/catalyst-research/logs
```

### 4.4 Inspection utilities

The system has no dashboard in v1. Inspection is via SQL and three small scripts:

- `scripts/show_weekly_report.py [WEEK]` — prints a Markdown report of the week's archetype analyses and peer reviews. This is what Craig reads on the weekly review.
- `scripts/show_learning_plan.py PLAN_NAME` — prints the plan, current status, the data series it depends on, and a sparkline-style summary of recent values.
- `scripts/show_country_indicators.py COUNTRY` — prints the indicator series for a country with their latest values and most recent revision dates.

### 4.5 Cleanup (Migration Step 6)

Once Phases 1–4 are running and producing weekly reports cleanly for at least four consecutive weeks:

1. Drop the old agent-era tables from `catalyst_dev` (and optionally drop the `catalyst_dev` database itself).
2. The legacy consciousness tables in `catalyst_research` were already dropped in Phase 0.3; the DB itself is now in active use and stays.
3. Archive `catalyst-agent/` per repo-root CLAUDE.md — already partially done as `catalyst-agent.old-20260518/`. Confirm the live tree is removed once the research system is stable.
4. Update repo-root `CLAUDE.md` to mark catalyst-research as **Running** and remove the "Planned" status. Update the implementation table in Section 2, and the database table in Section 3.2 to show `catalyst_research` as "Active — catalyst-research v1".
5. Reclaim droplet disk: prune Docker images, orphaned volumes, build cache (architecture Section 9 estimates ~21 GB recoverable).

### 4.6 Phase 4 exit criteria

- Folder layout in place; CLAUDE.md trio populated.
- Cron file installed and surviving a droplet reboot.
- Four consecutive weekly reports produced cleanly with no human intervention.
- Repo-root CLAUDE.md updated to reflect catalyst-research as Running.

---

## APPENDIX A — DATA SOURCES (v1)

| Layer | Source | Endpoint / format | Free? | Notes |
|---|---|---|---|---|
| 1 | IMF WEO | datasets via SDMX + datamapper API | Yes | Slow update cadence; canonical macro |
| 1 | World Bank Indicators | REST API | Yes | Broad country coverage |
| 1 | BEA (US) | REST API (API key) | Yes (key required) | National accounts, trade |
| 1 | NBS (China) | HTML scrape + occasional JSON | Yes | Quality varies; archetypes flag |
| 1 | RBA / ABS (Australia) | Bulletin downloads + ABS time-series CSV | Yes | Clean |
| 1 | HKMA | Statistics portal | Yes | Clean |
| 2 | Yahoo Finance | yfinance library | Yes | Primary daily price source |
| 2 | Stooq | CSV downloads | Yes | Fallback when yfinance breaks |
| 2 | Investing.com | scrape | Yes | Some commodities only |
| 3 | HKEX disclosure feed | RSS/JSON | Yes | Primary news for HKEX-listed |
| 3 | Moomoo OpenD | local daemon | Yes | Reused from intl; security prices and bars |
| 4 | UN Comtrade | REST API | Free tier sufficient | Monthly trade flows; key registers free |
| 4 | Voeten UN voting | dataset download | Yes | Annual file |
| 5 | IMF COFER | downloadable CSV | Yes | Quarterly, two-quarter lag |
| 5 | HKEX listing stats | monthly PDF + HTML tables | Yes | Some parsing required |

## APPENDIX B — V1 NON-GOALS

Explicitly **not** in v1, restated from architecture Section 8 to prevent scope creep during build:

- No automated trading. No order placement. No position management code.
- No additional countries beyond USA/CHN/HKG/AUS.
- No additional commodities beyond iron ore / copper / gold / Brent.
- No real-time data; daily is sufficient.
- No alerting, no dashboards.
- No model training pipeline (proposals are captured; training is v1.5).
- No fine-tuning of LLMs.
- No additional Layer 5 sources beyond COFER and HKEX listings.
- No FDI direction, defense cooperation, technology alignment, currency swap data (deferred to v1.5).

If a Phase 2 or Phase 3 task starts requiring any item above, stop and either defer it or explicitly amend the architecture before resuming.

## APPENDIX C — V1 NOMINAL TIMELINE

Per architecture Migration Step 7 ("four to six weeks"):

| Week | Phase | Output |
|---|---|---|
| 1 | Phase 0 + Phase 1 | Snapshots, credentials rotated, schema applied, seed data in place |
| 2 | Phase 2 start | Layer 2 daily jobs running; Australia Layer 1 first |
| 3 | Phase 2 | US + China + HK Layer 1; Layer 5 jobs |
| 4 | Phase 2 | Layer 3 + Layer 4 jobs; backfills running |
| 5 | Phase 2 close + Phase 3 prep | Four weeks of clean data accumulated; archetype scaffolding written |
| 6 | Phase 3 + Phase 4 | First archetype runs; cron file installed; cleanup |

The calendar is nominal. The discipline is that each phase's exit criteria pass before the next begins, even if that slips weeks.

---

*End of document.*
