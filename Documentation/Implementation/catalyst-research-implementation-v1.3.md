# Catalyst Research — v1 Implementation Guide

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-research-v1-implementation.md
**Version:** 1.3.0
**Created:** 2026-05-18
**Updated by:** Craig + Claude
**Companion to:** `Documentation/Design/catalyst-research-architecture-v1.md` (v1.3.0, 2026-05-18)
**Purpose:** Buildable specification for v1 of the catalyst-research system. Translates the architecture document into concrete artefacts: full DDL, ingestion job specs, archetype orchestration design, folder layout, and cron schedule. This is the document the v1 build executes against.

---

## REVISION HISTORY

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0.0 | 2026-05-18 | Craig + Claude | Initial guide. Spec drawn from architecture v1.1.0. |
| 1.1.0 | 2026-05-18 | Craig + Claude | Schema home moved to dedicated `catalyst_research` DB (architecture v1.2.0). `cr_` prefix dropped — namespace from DB. |
| 1.2.0 | 2026-05-18 | Craig + Claude | Schema home moved back to `catalyst_intl` (architecture v1.3.0). Shared `securities`, `exchanges`, and one Moomoo ingestion serving both research and intl trading. `cr_` prefix returns on research fact tables. Phase 1 DDL rewritten with `ALTER TABLE` clauses and role creation. |
| 1.3.0 | 2026-05-18 | Craig + Claude | Review fixes from little_bro: corrected Anthropic budget math to ~36 runs/month (was understated 3×); replaced fictional `--system-prompt-file` flag with concatenated `--append-system-prompt` invocations and a Phase 3 smoke-test gate; added Phase 0.3 `security_id` type verification; scoped seed `UPDATE` to `WHERE ... IS NULL` to never overwrite intl-side values; tightened sequence grants to `cr_*` only; added `recorded_by` provenance column on fact tables; added `updated_at` triggers on `cr_learning_plans` and `cr_investment_theses`; clarified sectors-vs-themes distinction in 1.1; added Phase 0.4 rollback procedure. |

---

## HOW TO READ THIS DOCUMENT

This guide assumes the architecture document has been read. It does not restate the *why*; it specifies the *what* and *how*. The architecture is the source of truth for mission, layers, archetypes, and review cadences. This document is the source of truth for table definitions, file paths, job schedules, and operational procedure.

The build is staged in four phases that map to Migration Steps 2–6 in the architecture:

- **Phase 0** — preparation: credential rotation, DB snapshot, intl-state verification, rollback plan
- **Phase 1** — schema: full DDL applied to `catalyst_intl` (extending existing tables, adding shared dimensional tables, adding `cr_*` research tables) plus role creation
- **Phase 2** — ingestion: country-by-country build of Layer 1–5 ingestion jobs
- **Phase 3** — archetypes: orchestration of the four analytical Claude Code instances
- **Phase 4** — operations: folder layout, cron schedule, inspection utilities, cleanup of old agent tables and decommissioned databases

Each phase has explicit entry and exit criteria. A phase is not complete until its exit criteria pass.

---

## PHASE 0 — PREPARATION

**Entry criteria:** the agent crons on the US droplet are confirmed stopped (architecture Migration Step 1 — completed 2026-05-18 per repo-root `CLAUDE.md`).

### 0.1 Snapshot the databases

DigitalOcean managed PostgreSQL snapshot of `catalyst_intl` taken before any DDL runs. This is the primary safety net — Phase 1 extends the live trading DB with research tables and `ALTER TABLE` statements on `securities` and `exchanges`. The snapshot is the rollback path if anything goes wrong (see 0.4 for restore procedure).

A snapshot of `catalyst_research` is prudent because that database is dropped entirely at Phase 4.5.

```bash
# Triggered via DigitalOcean control panel or doctl:
doctl databases backups list catalyst-intl
doctl databases backups list catalyst-research
# Confirm a backup exists from today before proceeding.
```

### 0.2 Rotate exposed credentials

The following credentials were known-exposed during the agent era and are rotated before any new code is written. The new system has no agent runtime API calls except the archetype Claude Code instances, so the previous Anthropic key can be retired entirely; a new key is provisioned scoped only to archetype usage.

| Credential | Action | Stored in |
|---|---|---|
| Anthropic API key (agent-era) | Revoke | — |
| Anthropic API key (archetypes) | Provision new | `.env` → `ANTHROPIC_API_KEY` |
| PostgreSQL password (catalyst_intl) | Rotate via DO panel | `.env` → `INTL_DATABASE_URL` |
| Alpaca paper/live keys | Revoke (US trading dormant) | — |
| Moomoo trade-unlock password | Rotate (kept; intl still uses Moomoo) | intl droplet `.env` |
| GitHub token | Confirm current (rotated 2026-03-29 per memory) | local only |

### 0.3 Verify intl trading state and column types

Phase 1 will add columns to live intl trading tables (`securities`, `exchanges`) and add new tables alongside them. Before doing this, verify the intl trading repo is clean and — critically — verify the actual column types that Phase 1 will FK against.

```bash
# Confirm no schema migrations are in flight on the intl side:
cd /root/catalyst-international && git status
# Expected: clean working tree on main

# Confirm Moomoo OpenD is reachable from the intl droplet (data source for
# cr_security_prices and cr_news_events ingestion in Phase 2):
nc -zv 127.0.0.1 11111
# Expected: succeeded
```

**Column-type verification.** The Phase 1 DDL assumes `securities.security_id` is `integer` (from `SERIAL PRIMARY KEY`) and `exchanges.exchange_id` is `integer`. Confirm before running:

```bash
psql "$INTL_DATABASE_URL" -c "\d securities"  | grep security_id
psql "$INTL_DATABASE_URL" -c "\d exchanges"   | grep exchange_id
```

If either column is `bigint` or `bigserial`, the Phase 1 FK types in `cr_security_prices.security_id` and `cr_news_securities.security_id` must be updated to match before the migration runs. A type mismatch breaks the migration mid-transaction; better to catch it here.

The legacy `catalyst_research` cluster database is **not modified** in Phase 0. It remains untouched until Phase 4.5, where it is dropped entirely.

> ⚠️ Phase 1 modifies the live trading database (`catalyst_intl`). All Phase 1 statements are additive — no column drops, no type changes, no row deletions. Intl trading code is unaffected. But the snapshot from 0.1 plus the rollback in 0.4 are the safety nets if a constraint or grant statement misfires.

### 0.4 Rollback procedure (read before Phase 1, do not execute)

If Phase 1 fails or produces unexpected behaviour in live intl trading, there are three rollback options ordered by destructiveness. The Phase 1 migration runs inside a single transaction, so a SQL-level failure rolls back automatically. These procedures address the rarer case where the migration completes but intl trading subsequently misbehaves.

**Option A: Reverse ALTER TABLE additions (least destructive, preferred).** Because Phase 1 is additive (`ADD COLUMN IF NOT EXISTS`, never `DROP`, never type change), the additions can be reversed in place without touching data:

```sql
-- Connect as catalyst_research_admin
BEGIN;
ALTER TABLE securities
    DROP CONSTRAINT IF EXISTS fk_securities_listing_country,
    DROP CONSTRAINT IF EXISTS fk_securities_primary_sector,
    DROP COLUMN IF EXISTS listing_country,
    DROP COLUMN IF EXISTS primary_sector_id;

ALTER TABLE exchanges
    DROP CONSTRAINT IF EXISTS fk_exchanges_country,
    DROP COLUMN IF EXISTS country_code;

-- Drop all cr_* tables and shared dimensional tables in reverse-FK order:
DROP TABLE IF EXISTS cr_models_trained CASCADE;
DROP TABLE IF EXISTS cr_model_proposals CASCADE;
DROP TABLE IF EXISTS cr_archetype_peer_reviews CASCADE;
DROP TABLE IF EXISTS cr_archetype_analyses CASCADE;
DROP TABLE IF EXISTS cr_thesis_history CASCADE;
DROP TABLE IF EXISTS cr_investment_theses CASCADE;
DROP TABLE IF EXISTS cr_learning_plans CASCADE;
DROP TABLE IF EXISTS cr_financial_infra_observations CASCADE;
DROP TABLE IF EXISTS cr_country_pair_observations CASCADE;
DROP TABLE IF EXISTS cr_news_themes CASCADE;
DROP TABLE IF EXISTS cr_news_securities CASCADE;
DROP TABLE IF EXISTS cr_news_events CASCADE;
DROP TABLE IF EXISTS cr_security_prices CASCADE;
DROP TABLE IF EXISTS cr_market_prices CASCADE;
DROP TABLE IF EXISTS cr_country_cycle_estimates CASCADE;
DROP TABLE IF EXISTS cr_country_indicators CASCADE;

DROP TABLE IF EXISTS security_themes CASCADE;
DROP TABLE IF EXISTS commodities CASCADE;
DROP TABLE IF EXISTS themes CASCADE;
DROP TABLE IF EXISTS sectors CASCADE;
DROP TABLE IF EXISTS countries CASCADE;

DROP ROLE IF EXISTS catalyst_research_archetype;
DROP ROLE IF EXISTS catalyst_research_ingestion;
DROP ROLE IF EXISTS catalyst_research_admin;
COMMIT;
```

After Option A, intl trading is in exactly its pre-Phase-1 state.

**Option B: Restore from snapshot (destructive — loses intl trades since snapshot).** DigitalOcean managed PostgreSQL does not support in-place rollback. Restore creates a new database cluster from the snapshot, which means any intl trades placed between Phase 0.1 (snapshot time) and now are lost. Only acceptable if:

1. The damage is severe enough that Option A cannot recover (rare — Option A handles all additive-only damage), AND
2. Intl trading has been halted or no trades have been placed since the snapshot.

Procedure: via DO control panel, restore the snapshot to a new cluster, redirect `INTL_DATABASE_URL` to the new cluster, manually replay any intl trades that happened between snapshot and now.

**Option C: Point-in-time recovery (DO managed Postgres feature, if enabled).** Same trade-offs as Option B but with finer time resolution. Check DO docs for current availability and lag.

Option A handles all realistic failure modes for an additive migration. Options B and C are documented for completeness but should not be needed.

**Exit criteria:** snapshot of `catalyst_intl` exists from today, credentials rotated, intl trading repo clean, Moomoo OpenD reachable, column types verified, rollback procedure read, `INTL_DATABASE_URL` set in the droplet `.env`.

---

## PHASE 1 — SCHEMA

**Entry criteria:** Phase 0 complete.

The full DDL lives in a single migration file:

```
catalyst-research/sql/001_initial_schema.sql
```

It is applied to `catalyst_intl` as a single transaction. If any statement fails, the entire migration rolls back and the snapshot from Phase 0.1 stays as the second-line fallback (with Phase 0.4 Option A as the recovery procedure if needed).

### 1.1 Naming and discipline rules

- Research-only fact and analytical tables carry the **`cr_`** prefix (catalyst-research) to distinguish them from trading tables within the shared `catalyst_intl` database.
- Shared dimensional tables — `countries`, `sectors`, `themes`, `commodities`, `security_themes` — carry no prefix because they describe real-world entities relevant to both subsystems.
- Existing intl tables `securities` and `exchanges` are extended via `ALTER TABLE ... ADD COLUMN` only. No drops, no type changes, no existing-row modifications.
- Every fact-bearing table carries: `event_date` (or `period_start` + `period_end`), `source`, `recorded_at`, `recorded_by`, `backfill`.
- The `recorded_by` column carries the name of the ingestion job that wrote the row (e.g. `'ingest_country_indicators_imf'`). Cheap insurance against the "why does this indicator have three revisions on the same day?" question that comes up months later.
- Facts are never updated in place. Revisions append a new row with the same business key and a later `recorded_at`. "Current best estimate" is a query, not a stored value.
- Indexes are time-first on every fact table.
- All timestamps are `timestamptz`; all stored UTC.
- ISO 3166-1 alpha-3 country codes (`USA`, `CHN`, `HKG`, `AUS`).

**Sectors vs themes — the distinction matters.** Both can carry names like "critical minerals" or "financial infrastructure," and v1 deliberately separates them:

- **Sectors are industry classifications.** What business is this company in. Drawn from HKEX's published sector codes (e.g. `HK.BK1587`) and broader formal taxonomies. A lithium miner is in the `industrial_metals` or `mining` sector. The sector table is populated sparsely in v1 — HKEX codes load as encountered during security registration, broader categories fill in as the country set expands.
- **Themes are transition-exposure tags.** What structural narrative this security expresses for the West-to-East transition. The same lithium miner carries the `critical_minerals` and `chinese_demand` themes. The theme table is fully populated by the v1 seed script with the five starter themes.

A security typically has one sector and multiple themes. Cross-layer queries use themes to filter for transition relevance and sectors to filter for industry comparability.

### 1.2 DDL

```sql
-- catalyst-research/sql/001_initial_schema.sql
-- Applied to catalyst_intl. Extends the live intl trading DB with the
-- catalyst-research schema. Run inside a single transaction by the
-- catalyst_research_admin role.

BEGIN;

-- ============================================================
-- Roles (idempotent; safe on re-run)
-- Passwords are passed as psql variables (-v) at invocation time.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_research_admin') THEN
        EXECUTE format('CREATE ROLE catalyst_research_admin LOGIN PASSWORD %L',
                       current_setting('research.admin_pwd'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_research_ingestion') THEN
        EXECUTE format('CREATE ROLE catalyst_research_ingestion LOGIN PASSWORD %L',
                       current_setting('research.ingestion_pwd'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'catalyst_research_archetype') THEN
        EXECUTE format('CREATE ROLE catalyst_research_archetype LOGIN PASSWORD %L',
                       current_setting('research.archetype_pwd'));
    END IF;
END $$;

-- ============================================================
-- Helper: updated_at trigger function (idempotent)
-- ============================================================

CREATE OR REPLACE FUNCTION cr_set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Extensions to existing intl tables (ADDITIVE ONLY)
-- ============================================================

ALTER TABLE securities
    ADD COLUMN IF NOT EXISTS listing_country   char(3),
    ADD COLUMN IF NOT EXISTS primary_sector_id bigint;

ALTER TABLE exchanges
    ADD COLUMN IF NOT EXISTS country_code char(3);

-- FKs added after the reference tables exist (see below).

-- ============================================================
-- Shared reference tables (no prefix — dimensional)
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

CREATE TABLE security_themes (
    security_id  integer NOT NULL REFERENCES securities(security_id) ON DELETE CASCADE,
    theme_id     bigint  NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    PRIMARY KEY (security_id, theme_id)
);

CREATE TABLE commodities (
    id                  bigserial      PRIMARY KEY,
    name                varchar(64)    NOT NULL UNIQUE,
    category            varchar(32)    NOT NULL,
    reference_benchmark varchar(128),
    unit                varchar(32),
    notes               text,
    created_at          timestamptz    NOT NULL DEFAULT now()
);

-- Now that reference tables exist, add the FKs to the extended intl tables:
ALTER TABLE securities
    ADD CONSTRAINT fk_securities_listing_country
        FOREIGN KEY (listing_country) REFERENCES countries(country_code),
    ADD CONSTRAINT fk_securities_primary_sector
        FOREIGN KEY (primary_sector_id) REFERENCES sectors(id);

ALTER TABLE exchanges
    ADD CONSTRAINT fk_exchanges_country
        FOREIGN KEY (country_code) REFERENCES countries(country_code);

-- ============================================================
-- Layer 1: Country macro indicators
-- ============================================================

CREATE TABLE cr_country_indicators (
    id             bigserial     PRIMARY KEY,
    country_code   char(3)       NOT NULL REFERENCES countries(country_code),
    indicator_name varchar(64)   NOT NULL,
    dalio_power    varchar(32),
    value          numeric       NOT NULL,
    unit           varchar(32)   NOT NULL,
    period_start   date          NOT NULL,
    period_end     date          NOT NULL,
    event_date     date          NOT NULL,
    source         varchar(64)   NOT NULL,
    recorded_at    timestamptz   NOT NULL DEFAULT now(),
    recorded_by    varchar(64)   NOT NULL,
    backfill       boolean       NOT NULL DEFAULT false,
    notes          text
);

CREATE INDEX idx_cr_country_indicators_lookup
    ON cr_country_indicators (country_code, indicator_name, period_end DESC, recorded_at DESC);

CREATE TABLE cr_country_cycle_estimates (
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
    recorded_at           timestamptz   NOT NULL DEFAULT now(),
    recorded_by           varchar(64)   NOT NULL
);

CREATE INDEX idx_cr_cycle_estimates_lookup
    ON cr_country_cycle_estimates (country_code, as_of_date DESC, recorded_at DESC);

-- ============================================================
-- Layer 2: Markets and commodities
-- ============================================================

CREATE TABLE cr_market_prices (
    id          bigserial   PRIMARY KEY,
    series_id   varchar(64) NOT NULL,
    series_type varchar(16) NOT NULL CHECK (series_type IN ('index','fx','yield','commodity')),
    trade_date  date        NOT NULL,
    open        numeric,
    high        numeric,
    low         numeric,
    close       numeric     NOT NULL,
    volume      bigint,
    source      varchar(64) NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    recorded_by varchar(64) NOT NULL,
    backfill    boolean     NOT NULL DEFAULT false
);

CREATE INDEX idx_cr_market_prices_lookup
    ON cr_market_prices (series_id, trade_date DESC, recorded_at DESC);

-- security_id type MUST match intl securities.security_id type (verified in Phase 0.3)
CREATE TABLE cr_security_prices (
    id           bigserial   PRIMARY KEY,
    security_id  integer     NOT NULL REFERENCES securities(security_id),
    trade_date   date        NOT NULL,
    open         numeric,
    high         numeric,
    low          numeric,
    close        numeric     NOT NULL,
    volume       bigint,
    adj_close    numeric,
    source       varchar(64) NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    recorded_by  varchar(64) NOT NULL,
    backfill     boolean     NOT NULL DEFAULT false
);

CREATE INDEX idx_cr_security_prices_lookup
    ON cr_security_prices (security_id, trade_date DESC, recorded_at DESC);

-- ============================================================
-- Layer 3: News and events
-- ============================================================

CREATE TABLE cr_news_events (
    id             bigserial   PRIMARY KEY,
    source         varchar(64) NOT NULL,
    external_id    varchar(128),
    headline       text        NOT NULL,
    body           text,
    event_date     timestamptz NOT NULL,
    recorded_at    timestamptz NOT NULL DEFAULT now(),
    recorded_by    varchar(64) NOT NULL,
    classification varchar(32),
    sentiment      varchar(16),
    raw_payload    jsonb       NOT NULL,
    UNIQUE (source, external_id)
);

CREATE INDEX idx_cr_news_events_time ON cr_news_events (event_date DESC);

CREATE TABLE cr_news_securities (
    news_event_id bigint  NOT NULL REFERENCES cr_news_events(id) ON DELETE CASCADE,
    security_id   integer NOT NULL REFERENCES securities(security_id) ON DELETE CASCADE,
    PRIMARY KEY (news_event_id, security_id)
);

CREATE TABLE cr_news_themes (
    news_event_id bigint NOT NULL REFERENCES cr_news_events(id) ON DELETE CASCADE,
    theme_id      bigint NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    PRIMARY KEY (news_event_id, theme_id)
);

-- ============================================================
-- Layer 4: Bilateral relationships
-- ============================================================

CREATE TABLE cr_country_pair_observations (
    id           bigserial   PRIMARY KEY,
    country_a    char(3)     NOT NULL REFERENCES countries(country_code),
    country_b    char(3)     NOT NULL REFERENCES countries(country_code),
    dimension    varchar(64) NOT NULL,
    value        numeric     NOT NULL,
    unit         varchar(32) NOT NULL,
    period_start date,
    period_end   date,
    event_date   date        NOT NULL,
    source       varchar(64) NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    recorded_by  varchar(64) NOT NULL,
    backfill     boolean     NOT NULL DEFAULT false,
    CHECK (country_a < country_b)
);

CREATE INDEX idx_cr_pair_observations_lookup
    ON cr_country_pair_observations (country_a, country_b, dimension, event_date DESC, recorded_at DESC);

-- ============================================================
-- Layer 5: Financial infrastructure
-- ============================================================

CREATE TABLE cr_financial_infra_observations (
    id           bigserial   PRIMARY KEY,
    infra_type   varchar(64) NOT NULL,
    entity_id    varchar(64),
    metric_name  varchar(64) NOT NULL,
    value        numeric     NOT NULL,
    unit         varchar(32) NOT NULL,
    period_start date,
    period_end   date,
    event_date   date        NOT NULL,
    source       varchar(64) NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    recorded_by  varchar(64) NOT NULL,
    backfill     boolean     NOT NULL DEFAULT false,
    metadata     jsonb
);

CREATE INDEX idx_cr_infra_observations_lookup
    ON cr_financial_infra_observations (infra_type, metric_name, event_date DESC, recorded_at DESC);

-- ============================================================
-- Theses and learning plans
-- ============================================================

CREATE TABLE cr_learning_plans (
    id                    bigserial    PRIMARY KEY,
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

CREATE TRIGGER trg_cr_learning_plans_updated
    BEFORE UPDATE ON cr_learning_plans
    FOR EACH ROW EXECUTE FUNCTION cr_set_updated_at();

CREATE TABLE cr_investment_theses (
    id                    bigserial    PRIMARY KEY,
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

CREATE TRIGGER trg_cr_investment_theses_updated
    BEFORE UPDATE ON cr_investment_theses
    FOR EACH ROW EXECUTE FUNCTION cr_set_updated_at();

CREATE TABLE cr_thesis_history (
    id           bigserial   PRIMARY KEY,
    thesis_id    bigint      NOT NULL REFERENCES cr_investment_theses(id) ON DELETE CASCADE,
    snapshot     jsonb       NOT NULL,
    change_note  text,
    recorded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_cr_thesis_history_thesis ON cr_thesis_history (thesis_id, recorded_at DESC);

-- ============================================================
-- Archetype analyses
-- ============================================================

CREATE TABLE cr_archetype_analyses (
    id                      bigserial   PRIMARY KEY,
    archetype               varchar(16) NOT NULL
        CHECK (archetype IN ('historian','strategist','macro_theorist','skeptic')),
    run_date                date        NOT NULL,
    period_start            date        NOT NULL,
    period_end              date        NOT NULL,
    scope                   varchar(24) NOT NULL
        CHECK (scope IN ('weekly','monthly','quarterly','learning_plan_review','ad_hoc')),
    conclusions             text        NOT NULL,
    uncertainties           text,
    supporting_observations jsonb,
    recorded_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_cr_archetype_analyses_lookup
    ON cr_archetype_analyses (archetype, period_end DESC, recorded_at DESC);

CREATE TABLE cr_archetype_peer_reviews (
    id                   bigserial   PRIMARY KEY,
    reviewer_archetype   varchar(16) NOT NULL,
    reviewed_analysis_id bigint      NOT NULL REFERENCES cr_archetype_analyses(id) ON DELETE CASCADE,
    agreement            varchar(16) NOT NULL
        CHECK (agreement IN ('strong_agree','agree','disagree','strong_disagree')),
    critique             text        NOT NULL,
    recorded_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_cr_peer_reviews_reviewed ON cr_archetype_peer_reviews (reviewed_analysis_id);

CREATE TABLE cr_model_proposals (
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

CREATE TABLE cr_models_trained (
    id                           bigserial    PRIMARY KEY,
    proposal_id                  bigint       REFERENCES cr_model_proposals(id),
    name                         varchar(128) NOT NULL UNIQUE,
    training_dataset_description text,
    validation_results           jsonb,
    in_use                       boolean      NOT NULL DEFAULT false,
    created_at                   timestamptz  NOT NULL DEFAULT now(),
    retired_at                   timestamptz
);

-- ============================================================
-- Grants — the safety property that replaces DB separation
-- Sequence grants are SCOPED to cr_* sequences (not all in schema).
-- ============================================================

-- ingestion role: INSERT only on research fact tables; SELECT on dimensional;
-- NO access to trading tables (positions, orders, decisions, etc.).
GRANT SELECT ON countries, sectors, themes, commodities, security_themes,
                securities, exchanges TO catalyst_research_ingestion;

GRANT INSERT ON cr_country_indicators,
                cr_country_cycle_estimates,
                cr_market_prices,
                cr_security_prices,
                cr_news_events,
                cr_news_securities,
                cr_news_themes,
                cr_country_pair_observations,
                cr_financial_infra_observations
    TO catalyst_research_ingestion;

-- Sequence grants scoped to cr_* and shared-table sequences ONLY.
-- Trading-table sequences (positions_position_id_seq, etc.) are NOT granted.
GRANT USAGE, SELECT ON
    cr_country_indicators_id_seq,
    cr_country_cycle_estimates_id_seq,
    cr_market_prices_id_seq,
    cr_security_prices_id_seq,
    cr_news_events_id_seq,
    cr_country_pair_observations_id_seq,
    cr_financial_infra_observations_id_seq,
    sectors_id_seq,
    themes_id_seq,
    commodities_id_seq
    TO catalyst_research_ingestion;

-- archetype role: SELECT on everything (including intl trading tables, so
-- archetypes can learn from real trade outcomes); INSERT on its own three tables.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO catalyst_research_archetype;

GRANT INSERT ON cr_archetype_analyses,
                cr_archetype_peer_reviews,
                cr_model_proposals
    TO catalyst_research_archetype;

GRANT USAGE, SELECT ON
    cr_archetype_analyses_id_seq,
    cr_archetype_peer_reviews_id_seq,
    cr_model_proposals_id_seq
    TO catalyst_research_archetype;

-- Future-proofing: new tables created by admin grant SELECT to archetype by default.
ALTER DEFAULT PRIVILEGES FOR ROLE catalyst_research_admin IN SCHEMA public
    GRANT SELECT ON TABLES TO catalyst_research_archetype;

COMMIT;
```

### 1.3 Seed data

Immediately after the migration, a separate idempotent seed script (`catalyst-research/sql/002_seed_v1.sql`) inserts:

- The four v1 countries (USA, CHN, HKG, AUS).
- The four v1 commodities (iron_ore, copper, gold, brent_crude).
- A starter set of v1 themes: `yuan_internationalization`, `critical_minerals`, `chinese_demand`, `financial_infrastructure_east`, `reserve_diversification`.
- The 20–30 HKEX securities — via `INSERT ... ON CONFLICT DO NOTHING` against the existing `securities` table, then `UPDATE` to set `listing_country` and `primary_sector_id` for them. The UPDATE is scoped with `WHERE listing_country IS NULL` / `WHERE primary_sector_id IS NULL` so it **never overwrites values intl already set** — research only fills nulls.
- The three v1 learning plans as `cr_learning_plans` rows (full text from architecture Section 7).
- `country_code` populated on the existing HKEX row in `exchanges` (also scoped `WHERE country_code IS NULL`).

Example pattern for the safe extend-don't-overwrite:

```sql
-- Seed (or no-op if already exists)
INSERT INTO securities (symbol, exchange_id, name) VALUES (...)
    ON CONFLICT (symbol, exchange_id) DO NOTHING;

-- Fill nulls only — never overwrite intl-side values
UPDATE securities
   SET listing_country = 'HKG'
 WHERE symbol = '0700'
   AND listing_country IS NULL;
```

The seed script runs as `catalyst_research_admin` (it touches both `securities` and `cr_*` tables) and is fully idempotent so re-running is safe.

### 1.4 Phase 1 exit criteria

- `001_initial_schema.sql` applied cleanly inside a transaction.
- The three new roles exist with passwords set and stored in the droplet `.env`.
- `002_seed_v1.sql` applied; the four countries, four commodities, three learning plans, five themes, and 20–30 securities exist.
- A read-only smoke query as `catalyst_research_ingestion` confirms it can read `securities` but not write to trading tables:
  ```sql
  SET ROLE catalyst_research_ingestion;
  SELECT count(*) FROM securities;           -- should succeed
  SELECT count(*) FROM positions;            -- should fail with permission denied
  INSERT INTO positions (symbol, side, quantity, entry_price)
       VALUES ('TEST', 'long', 1, 1.00);    -- should fail with permission denied
  RESET ROLE;
  ```
- Equivalent smoke as `catalyst_research_archetype` confirms it can SELECT from `positions` but not INSERT/UPDATE there.
- Intl trading code on the intl droplet continues to run unchanged. Verify by running one full trading cycle and confirming `positions`, `orders`, and `decisions` writes succeed.

---

## PHASE 2 — INGESTION

**Entry criteria:** Phase 1 complete.

Per architecture Migration Step 4, ingestion is built **country by country, layer by layer**: Australia first, then US, then China, then Hong Kong. Reasoning: Australia has clean accessible data, US validates schema handling of dense series, China validates handling of mixed-quality data, HK validates the trading-venue layer.

### 2.1 Ingestion job inventory

Each job is a single Python entry point in `catalyst-research/ingestion/`, invoked by cron, writing to one or more Layer tables. All jobs share a common adapter (`catalyst-research/ingestion/_adapter.py`) that handles DB connection (as `catalyst_research_ingestion`), idempotency (append-on-revision), structured logging, and stamping `recorded_by` with the job name.

| Layer | Job | Source | Cadence | Cron | Writes to |
|---|---|---|---|---|---|
| 1 | `ingest_country_indicators_imf` | IMF WEO + IMF datamapper API | Quarterly (after release dates) | `0 6 1 1,4,7,10 *` | `cr_country_indicators` |
| 1 | `ingest_country_indicators_worldbank` | World Bank Indicators API | Quarterly | `0 7 1 1,4,7,10 *` | `cr_country_indicators` |
| 1 | `ingest_country_indicators_national` | BEA (US), NBS (CN), HKMA (HK), RBA/ABS (AU) | Quarterly (staggered) | per-country | `cr_country_indicators` |
| 2 | `ingest_market_prices_daily` | Yahoo Finance + Stooq fallback | Daily, post-close | `30 22 * * 1-5` UTC | `cr_market_prices` |
| 2 | `ingest_commodity_prices_daily` | Yahoo Finance + Investing.com | Daily, post-close | `45 22 * * 1-5` UTC | `cr_market_prices` |
| 2/3 | `ingest_security_prices_daily` | Moomoo OpenD (intl droplet) | Daily, post-HKEX-close | `30 8 * * 1-5` UTC | `cr_security_prices` |
| 3 | `ingest_hkex_disclosure_feed` | HKEX disclosure feed | Continuous (poll every 15 min during HKEX hours) | `*/15 1-9 * * 1-5` UTC | `cr_news_events`, `cr_news_securities` |
| 4 | `ingest_un_comtrade` | UN Comtrade API | Monthly (with ~3 month lag) | `0 8 5 * *` | `cr_country_pair_observations` |
| 4 | `ingest_un_voting_alignment` | Voeten UN voting dataset | Annual | `0 8 1 6 *` | `cr_country_pair_observations` |
| 5 | `ingest_imf_cofer` | IMF COFER | Quarterly (with ~6 month lag) | `0 9 5 1,4,7,10 *` | `cr_financial_infra_observations` |
| 5 | `ingest_hkex_listing_stats` | HKEX monthly listing statistics | Monthly | `0 9 7 * *` | `cr_financial_infra_observations` |

Cron times in UTC. The intl droplet already runs in UTC.

**Droplet placement.** Jobs that depend on Moomoo OpenD (`ingest_security_prices_daily` and any future OpenD-backed news ingestion) must run on the **intl droplet**, because OpenD is a local daemon listening on `127.0.0.1:11111` there. All other jobs can run on either droplet but, for v1, are co-located on the **intl droplet** to keep operational concerns in one place. The US droplet remains dormant pending its next assigned workload (architecture Section 4 of repo-root CLAUDE.md).

### 2.2 Idempotency and revision-append

Every ingestion job follows the same pattern:

1. Fetch source data for the configured window.
2. For each candidate row, compute the business key (e.g. `(country_code, indicator_name, period_end)`).
3. Check whether a row already exists with that business key.
   - If no row exists → INSERT.
   - If a row exists and the `value` matches the latest → skip (no-op, idempotent re-run).
   - If a row exists but the `value` differs → INSERT a new row with the same business key and a fresh `recorded_at` (revision).
4. Stamp `recorded_by` with the job's module name (e.g. `'ingest_country_indicators_imf'`).
5. Log counts of inserted vs. revised vs. skipped.

There is no UPDATE on fact tables. Ever. This is the architectural commitment that makes the revision history first-class data. The `catalyst_research_ingestion` role enforces it at the DB level — it has INSERT but not UPDATE on `cr_*` fact tables.

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

The order shakes down the adapter pattern on the simplest layer first, then proceeds country-by-country per architecture Migration Step 4:

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
- Intl trading code has continued to run undisturbed throughout Phase 2 — confirm by sampling intl `positions` and `decisions` for the period.

---

## PHASE 3 — ARCHETYPES

**Entry criteria:** Phase 2 has been producing data for at least four weeks (architecture Migration Step 5 sequencing). Archetypes need data to analyse before they are switched on.

### 3.1 Orchestration model

Each archetype is a **headless Claude Code invocation** run by cron. The invocation pattern is illustrated below; the wrapper script `catalyst-research/archetypes/run.py` orchestrates this — it builds the system prompt and context bundle, invokes Claude Code, and writes the resulting analysis row into `cr_archetype_analyses` via the `catalyst_research_archetype` role.

```bash
# Illustrative — verify flag set against installed Claude Code version (Phase 3 entry criterion).
# Concatenate the archetype's system prompt with the run's context bundle and pass via
# --append-system-prompt. (--system-prompt-file is not a real CLI flag.)
SYSTEM_PROMPT="$(cat catalyst-research/archetypes/<archetype>/system.md)
$(catalyst-research/archetypes/build_context.py --archetype <archetype> --scope weekly)"

claude --print --output-format=json \
       --append-system-prompt "$SYSTEM_PROMPT" \
       --max-turns 10 \
       --permission-mode acceptEdits \
       > catalyst-research/archetypes/runs/<archetype>_<date>.json
```

> 🔍 The `claude` CLI flag set above is illustrative. Flag names and `--max-turns` defaults change between Claude Code releases. **Smoke-testing this invocation against the actual Claude Code version installed on the intl droplet is a Phase 3 entry criterion** (Section 3.6). The wrapper's first responsibility is to fail fast with a clear error if `claude --version` produces an unexpected output or if any flag is unrecognised.

The archetype has access (via a small read-only DB adapter `archetypes/db.py`, connected as `catalyst_research_archetype`) to:

- Its own system prompt (the archetype's lens).
- The relevant data tables (read via the role's broad SELECT grant — this includes intl trading outcomes so archetypes can learn from real trades).
- Previous analyses from all four archetypes (so it sees historical context).
- The learning plans currently active.

The role-based grants enforce that the archetype cannot write to trading tables, cannot write to research ingestion tables, and cannot perform DDL. It can only write to its own three tables (`cr_archetype_analyses`, `cr_archetype_peer_reviews`, `cr_model_proposals`). This is the safety property that previously came from DB separation, now achieved by GRANT.

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
├── db.py               ← read-only DB adapter (catalyst_research_archetype)
└── runs/               ← raw run artefacts (json), filed by date; gitignored
```

Each system prompt is short and lens-focused — fewer than 500 words. The lens is the architecture Section 3.5 description: the Historian places events in historical parallel; the Strategist analyses actor behaviour; the Macro Theorist applies Dalio's framework; the Skeptic looks for disconfirming evidence.

The system prompts are deliberately not over-engineered. The architecture's discipline is that the lens does the work, not the prompt.

### 3.3 Peer review cycle

After the four independent analyses for a given period are written, a second cron job runs the peer-review cycle. Each archetype reads the others' analyses (loaded into context) and produces a review row per analysis reviewed, written to `cr_archetype_peer_reviews`.

The Skeptic's peer-review runs last and is given an explicit instruction in its system prompt to look hardest at the consensus emerging from the other three.

### 3.4 Model proposals

When an archetype identifies a pattern it believes worth attempting to learn, it writes a row to `cr_model_proposals` via the wrapper. Proposals are reviewed manually before any training runs; this is not automated in v1. The training pipeline itself is deferred to v1.5 — for v1, the architecture's commitment is only that the *capture* mechanism exists.

Craig reviews proposals via `scripts/show_model_proposals.py` (Section 4.4).

### 3.5 Archetype run schedule and budget

| Run | Cadence | Cron (UTC) | Runs/month |
|---|---|---|---|
| Weekly analysis (4 archetypes, each run independently) | Saturday 02:00 UTC | `0 2 * * 6` | 16 |
| Weekly peer review (4 archetypes, each reviews the others' work in one run) | Saturday 06:00 UTC | `0 6 * * 6` | 16 |
| Monthly synthesis (4 archetypes, longer scope) | 1st 02:00 UTC | `0 2 1 * *` | 4 |
| Quarterly cycle-position update (Macro Theorist only) | 5th 02:00 UTC | `0 2 5 1,4,7,10 *` | ~0.33 (1 per quarter) |
| Learning-plan review (ad hoc per plan review date) | manual trigger | — | ~0.5 |

**Total: ~37 substantial Claude Code runs per month.**

This is materially higher than the original "~13" estimate. The previous estimate collapsed peer review into a single run per week; the actual design has each archetype running its own peer-review pass. Two prior Catalyst systems (`public_claude` and the v8 agent loop) hit credit exhaustion mid-month; this budget warrants a hard ceiling and a monitor.

**Budget controls:**

- The archetype-only Anthropic API key is provisioned with an explicit monthly spend cap set in the Anthropic console. Cap at 2× the modelled spend so a noisy month doesn't kill the month entirely; alarm at 1.5×.
- `scripts/show_cron_health.py` (Section 4.4) reports per-job run count for the current month so Craig can see drift toward the cap before it hits.
- Per-run token budget is enforced via `--max-turns` (10 for analysis, lower for peer review) so a runaway archetype can't burn the cap in a single Saturday.
- If usage trends above 1.5× projected, the Skeptic's peer review (the highest-leverage cut) gets demoted to monthly instead of weekly. This keeps the architecture intact while reducing run count by 4/month.

### 3.6 Phase 3 exit criteria

- **Claude CLI smoke test passes:** `claude --version` returns successfully on the intl droplet; the illustrative invocation in 3.1 is adapted to the actual installed flag names and runs end-to-end against a one-shot test prompt; the JSON output parses cleanly. The exact verified flag set is committed to `archetypes/run.py`.
- Per-archetype `--max-turns` and `--permission-mode` settings confirmed working.
- All four archetypes have completed at least one weekly run end-to-end.
- The peer-review cycle has run at least once and produced reviews against those analyses.
- The output is readable by Craig — `scripts/show_weekly_report.py` produces a human-readable Markdown summary from a week's analyses + reviews.
- Anthropic API spend for the test runs is within projected per-run cost; monthly cap is set in console.

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
│   │   ├── _adapter.py                   ← shared DB adapter, idempotency, logging, recorded_by stamping
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
│   │   ├── run.py                        ← invocation wrapper; verified flag set
│   │   ├── build_context.py
│   │   ├── db.py                         ← read-only DB adapter (archetype role)
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
│   │   ├── show_model_proposals.py       ← list proposals awaiting review
│   │   ├── show_cron_health.py           ← heartbeat: last run + status per job; archetype monthly run count
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

Installed as `/etc/cron.d/catalyst-research` on the **intl droplet** (co-located with Moomoo OpenD and existing intl trading cron):

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

> ⚠️ The intl droplet's existing cron continues to run catalyst-international trading jobs untouched. The catalyst-research cron file is installed alongside, not merged with, those entries.

### 4.3 Environment variables

Added to the intl droplet's `.env` (which already holds intl trading credentials):

```
# Existing (intl trading) — unchanged:
INTL_DATABASE_URL=postgres://catalyst_trading_writer:...@.../catalyst_intl
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111

# New (catalyst-research) — three role-scoped connection strings into the SAME DB:
RESEARCH_ADMIN_DATABASE_URL=postgres://catalyst_research_admin:...@.../catalyst_intl
RESEARCH_INGESTION_DATABASE_URL=postgres://catalyst_research_ingestion:...@.../catalyst_intl
RESEARCH_ARCHETYPE_DATABASE_URL=postgres://catalyst_research_archetype:...@.../catalyst_intl

ANTHROPIC_API_KEY=...                      # archetype-only key, monthly cap set in console
HKEX_FEED_URL=...
UN_COMTRADE_API_KEY=...                    # if/when registered
CR_LOG_DIR=/root/catalyst-research/logs
```

Each connection string targets the **same** `catalyst_intl` database but as a different role. The role determines what the connection can read and write. The admin URL is used only by migration scripts; ingestion and archetype URLs are used by their respective runtime jobs.

### 4.4 Inspection utilities

The system has no dashboard in v1. Inspection is via SQL and these scripts:

- `scripts/show_weekly_report.py [WEEK]` — prints a Markdown report of the week's archetype analyses and peer reviews. This is what Craig reads on the weekly review.
- `scripts/show_learning_plan.py PLAN_NAME` — prints the plan, current status, the data series it depends on, and a sparkline-style summary of recent values.
- `scripts/show_country_indicators.py COUNTRY` — prints the indicator series for a country with their latest values and most recent revision dates.
- `scripts/show_model_proposals.py [STATUS]` — lists model proposals filtered by status (default: `proposed`). Without this, proposals accumulate in a table no one reads.
- `scripts/show_cron_health.py` — heartbeat. For each cron'd ingestion job, shows the most recent successful insert date and row count; for archetype runs, shows month-to-date run count vs budget cap. The doc commits to no alerting (Appendix B), so this is Craig's discovery mechanism for silently-failing jobs and budget drift. Run weekly alongside the weekly report.

### 4.5 Cleanup (Migration Step 6)

Once Phases 1–4 are running and producing weekly reports cleanly for at least four consecutive weeks:

1. **Drop the `catalyst_research` cluster database entirely.** It is unused in v1.3.0 architecture — research data lives in `catalyst_intl`. Confirm via `\dt` that only legacy consciousness-era tables remain, then drop the whole DB. (~$15/mo saving.)
2. **Drop the `catalyst_dev` cluster database.** Legacy US sandbox data; agent shelved; not needed.
3. **Archive `catalyst-agent/`** per repo-root CLAUDE.md — already partially done as `catalyst-agent.old-20260518/`. Confirm the live tree is removed once the research system is stable.
4. Update repo-root `CLAUDE.md` to mark catalyst-research as **Running** and remove the "Planned" status. Update the implementation table in Section 2, and the database table in Section 3.2 to show `catalyst_intl` as the home of both intl trading AND catalyst-research, and to remove `catalyst_research` and `catalyst_dev`.
5. Reclaim US droplet disk: prune Docker images, orphaned volumes, build cache (~21 GB recoverable). The US droplet remains dormant awaiting its next workload.

Note that Phase 4.5 cleanup completes around week ~11 of the build calendar — four weeks of clean weekly reports after Phase 4 starts at week 6. The build itself completes at week 6; cleanup completes at ~week 11.

### 4.6 Phase 4 exit criteria

- Folder layout in place; CLAUDE.md trio populated.
- Cron file installed on intl droplet and surviving a droplet reboot.
- Four consecutive weekly reports produced cleanly with no human intervention.
- `show_cron_health.py` confirms no silent-failure jobs across the four-week window and archetype monthly spend within projection.
- Repo-root CLAUDE.md updated to reflect catalyst-research as Running and to remove the `catalyst_research` and `catalyst_dev` DBs from Section 3.2.

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
| 3 | Moomoo OpenD | local daemon on intl droplet | Yes | Reused from intl; one ingestion serves both subsystems |
| 4 | UN Comtrade | REST API | Free tier sufficient (500 calls/day unkeyed, more with free key) | Monthly trade flows |
| 4 | Voeten UN voting | dataset download | Yes | Annual file |
| 5 | IMF COFER | downloadable CSV | Yes | Quarterly, two-quarter lag |
| 5 | HKEX listing stats | monthly PDF + HTML tables | Yes | Some parsing required |

## APPENDIX B — V1 NON-GOALS

Explicitly **not** in v1, restated from architecture Section 8 to prevent scope creep during build:

- No automated trading. No order placement. No position management code. (Intl trading continues as it already does; catalyst-research does not touch trading code.)
- No additional countries beyond USA/CHN/HKG/AUS.
- No additional commodities beyond iron ore / copper / gold / Brent.
- No real-time data; daily is sufficient.
- No alerting (discovery via `show_cron_health.py` weekly).
- No dashboards.
- No model training pipeline (proposals are captured; training is v1.5).
- No fine-tuning of LLMs.
- No additional Layer 5 sources beyond COFER and HKEX listings.
- No FDI direction, defense cooperation, technology alignment, currency swap data (deferred to v1.5).
- No automatic synchronisation between the trading-side `securities` registry and any external watchlist — the shared `securities` table IS the watchlist for both subsystems.

If a Phase 2 or Phase 3 task starts requiring any item above, stop and either defer it or explicitly amend the architecture before resuming.

## APPENDIX C — V1 NOMINAL TIMELINE

Per architecture Migration Step 7 ("four to six weeks") for the build itself; cleanup follows in weeks 7–11:

| Week | Phase | Output |
|---|---|---|
| 1 | Phase 0 + Phase 1 | Snapshots, credentials rotated, column types verified, schema applied, roles created, seed data in place |
| 2 | Phase 2 start | Layer 2 daily jobs running; Australia Layer 1 first |
| 3 | Phase 2 | US + China + HK Layer 1; Layer 5 jobs |
| 4 | Phase 2 | Layer 3 + Layer 4 jobs; backfills running |
| 5 | Phase 2 close + Phase 3 prep | Four weeks of clean data accumulated; archetype scaffolding written; Claude CLI flags smoke-tested |
| 6 | Phase 3 + Phase 4 | First archetype runs; cron file installed; spend cap set |
| 7–10 | Operations | Four consecutive clean weekly reports accumulate |
| 11 | Phase 4.5 cleanup | Drop `catalyst_research` and `catalyst_dev` DBs; archive `catalyst-agent/`; update repo-root CLAUDE.md |

The calendar is nominal. The discipline is that each phase's exit criteria pass before the next begins, even if that slips weeks.

---

*End of document.*
