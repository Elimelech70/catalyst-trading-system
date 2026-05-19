-- =============================================================================
-- Name of Application : Catalyst Trading System
-- Name of file        : catalyst-research/sql/001_initial_schema.sql
-- Version             : 0.1.0
-- Created             : 2026-05-18
-- Purpose             : Phase 1 DDL migration for catalyst-research v1.
--                       Applied to the SHARED catalyst_intl database, as the
--                       catalyst_research_admin role, inside a single
--                       transaction. Additive ALTER TABLEs on the existing
--                       intl `securities` and `exchanges` tables; new shared
--                       dimensional tables; cr_* research fact tables; four
--                       PostgreSQL roles enforcing the safety property that
--                       previously came from DB separation.
--
-- Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §1.2
--
-- IMPORTANT — Phase 0 dependencies (verify BEFORE running this file):
--   1. catalyst_intl snapshot taken today (Phase 0.1).
--   2. securities.security_id type confirmed as `integer` (Phase 0.3).
--      If it is `bigint` or `bigserial`, change every `security_id integer`
--      below to match. A type mismatch breaks the migration mid-transaction.
--   3. exchanges.exchange_id type confirmed.
--   4. Passwords for the three new roles set in psql session variables:
--          psql ... -v research.admin_pwd=...
--                   -v research.ingestion_pwd=...
--                   -v research.archetype_pwd=...
--          -f 001_initial_schema.sql
-- =============================================================================

BEGIN;

-- =============================================================================
-- ROLES (idempotent — safe on re-run)
-- =============================================================================

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

-- =============================================================================
-- Helper: updated_at trigger function (idempotent)
-- =============================================================================

CREATE OR REPLACE FUNCTION cr_set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Extensions to existing intl tables (ADDITIVE ONLY — no DROP, no type change)
-- =============================================================================

ALTER TABLE securities
    ADD COLUMN IF NOT EXISTS listing_country   char(3),
    ADD COLUMN IF NOT EXISTS primary_sector_id bigint;

ALTER TABLE exchanges
    ADD COLUMN IF NOT EXISTS country_code char(3);

-- FKs are added after the reference tables exist (see below).

-- =============================================================================
-- Shared reference tables (no prefix — dimensional, used by both subsystems)
-- =============================================================================

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
    category            varchar(32)    NOT NULL,  -- energy | industrial_metals | critical_minerals | precious_metals | agricultural
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

-- =============================================================================
-- Layer 1 — Country macro indicators
-- =============================================================================

CREATE TABLE cr_country_indicators (
    id             bigserial     PRIMARY KEY,
    country_code   char(3)       NOT NULL REFERENCES countries(country_code),
    indicator_name varchar(64)   NOT NULL,        -- e.g. 'debt_to_gdp', 'military_spending_pct_gdp'
    dalio_power    varchar(32),                   -- education|innovation|competitiveness|military|trade|output|financial_center|reserve_currency|cycle|NULL
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

-- =============================================================================
-- Layer 2 — Markets and commodities (non-security)
-- =============================================================================

CREATE TABLE cr_market_prices (
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

-- =============================================================================
-- Layer 3 — News and events
-- =============================================================================

CREATE TABLE cr_news_events (
    id             bigserial   PRIMARY KEY,
    source         varchar(64) NOT NULL,        -- e.g. 'HKEX_disclosure'
    external_id    varchar(128),                -- source-side unique id, for dedup
    headline       text        NOT NULL,
    body           text,
    event_date     timestamptz NOT NULL,
    recorded_at    timestamptz NOT NULL DEFAULT now(),
    recorded_by    varchar(64) NOT NULL,
    classification varchar(32),                 -- earnings|m_and_a|regulatory|policy|other|NULL
    sentiment      varchar(16),                 -- reserved for later
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

-- =============================================================================
-- Layer 4 — Bilateral relationships
-- =============================================================================

CREATE TABLE cr_country_pair_observations (
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
    recorded_by  varchar(64) NOT NULL,
    backfill     boolean     NOT NULL DEFAULT false,
    CHECK (country_a < country_b)
);

CREATE INDEX idx_cr_pair_observations_lookup
    ON cr_country_pair_observations (country_a, country_b, dimension, event_date DESC, recorded_at DESC);

-- =============================================================================
-- Layer 5 — Financial infrastructure
-- =============================================================================

CREATE TABLE cr_financial_infra_observations (
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
    recorded_by  varchar(64) NOT NULL,
    backfill     boolean     NOT NULL DEFAULT false,
    metadata     jsonb
);

CREATE INDEX idx_cr_infra_observations_lookup
    ON cr_financial_infra_observations (infra_type, metric_name, event_date DESC, recorded_at DESC);

-- =============================================================================
-- Theses and learning plans
-- =============================================================================

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

-- =============================================================================
-- Archetype analyses
-- =============================================================================

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

-- =============================================================================
-- GRANTS — the safety property that replaces DB separation.
-- Trading-table sequences (positions_*, orders_*, decisions_*) are NOT granted.
-- =============================================================================

-- ingestion role: INSERT only on research fact tables; SELECT on dimensional.
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

-- Sequences scoped to cr_* fact-table sequences + shared dimensional sequences.
-- Trading-table sequences explicitly NOT granted.
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

-- Future-proofing: tables created by admin grant SELECT to archetype by default.
ALTER DEFAULT PRIVILEGES FOR ROLE catalyst_research_admin IN SCHEMA public
    GRANT SELECT ON TABLES TO catalyst_research_archetype;

COMMIT;

-- =============================================================================
-- Post-migration smoke (run as the operator, not inside the transaction):
--   SET ROLE catalyst_research_ingestion;
--   SELECT count(*) FROM securities;         -- should succeed
--   SELECT count(*) FROM positions;          -- should fail: permission denied
--   INSERT INTO positions (symbol, side, quantity, entry_price)
--        VALUES ('TEST', 'long', 1, 1.00);   -- should fail: permission denied
--   RESET ROLE;
--
--   SET ROLE catalyst_research_archetype;
--   SELECT count(*) FROM positions;          -- should succeed (read)
--   INSERT INTO positions (symbol, side, quantity, entry_price)
--        VALUES ('TEST', 'long', 1, 1.00);   -- should fail: permission denied
--   RESET ROLE;
-- =============================================================================
