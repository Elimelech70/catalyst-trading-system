-- =============================================================================
-- Name of Application : Catalyst Trading System
-- Name of file        : catalyst-research/sql/002_seed_v1.sql
-- Version             : 0.1.0
-- Created             : 2026-05-18
-- Purpose             : Idempotent v1 seed for catalyst-research. Inserts the
--                       four v1 countries, four v1 commodities, five starter
--                       themes, and three v1 learning plans. Sets country_code
--                       on the existing HKEX row in `exchanges` (NULL-only).
--
--                       Securities seed is intentionally NOT in this file —
--                       the 20-30 HKEX security list is selected at Phase 1
--                       implementation time and lives in a separate
--                       003_seed_securities.sql so it can be evolved
--                       independently.
--
-- Reference           : Documentation/Implementation/catalyst-research-implementation-v1.3.md §1.3
--                       Documentation/Design/catalyst-research-architecture-v1.3.md §7
--
-- Idempotency         : Every INSERT uses ON CONFLICT DO NOTHING. Every UPDATE
--                       is scoped WHERE ... IS NULL so it never overwrites
--                       intl-side values. Re-running this script is a no-op.
--
-- Run as              : catalyst_research_admin (it touches exchanges and
--                       creates cr_learning_plans rows; ingestion role
--                       cannot do the former).
-- =============================================================================

BEGIN;

-- =============================================================================
-- Countries (ISO 3166-1 alpha-3)
-- =============================================================================

INSERT INTO countries (country_code, name, region, primary_currency, notes) VALUES
    ('USA', 'United States',  'Americas',     'USD',
        'Incumbent reserve-currency power; reference point for transition measurement.'),
    ('CHN', 'China',           'Asia-Pacific', 'CNY',
        'Central transition story; rising power per Dalio''s framework.'),
    ('HKG', 'Hong Kong',       'Asia-Pacific', 'HKD',
        'Trading venue (HKEX); structural meeting point of West and East capital.'),
    ('AUS', 'Australia',       'Asia-Pacific', 'AUD',
        'Home country; resource trade exposes to Chinese rise, security alignment to US.')
ON CONFLICT (country_code) DO NOTHING;

-- =============================================================================
-- Commodities
-- =============================================================================

INSERT INTO commodities (name, category, reference_benchmark, unit, notes) VALUES
    ('iron_ore',    'industrial_metals',
        'CFR Qingdao, 62% Fe',          'usd_per_tonne',
        'Cleanest test case for the China-demand structural-exposure thesis (Plan 1).'),
    ('copper',      'industrial_metals',
        'LME spot (COMEX cross-ref)',   'usd_per_tonne',
        'Industrial-cycle bellwether.'),
    ('gold',        'precious_metals',
        'London PM fix',                'usd_per_oz',
        'Reserve-diversification proxy (Plan 2).'),
    ('brent_crude', 'energy',
        'ICE settlement',               'usd_per_bbl',
        'Energy / OPEC+ dynamics; check on Shanghai INE vs ICE benchmark migration.')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- Themes (transition-exposure tags)
-- =============================================================================

INSERT INTO themes (name, description) VALUES
    ('yuan_internationalization',
        'Reserve diversification away from USD; SWIFT vs CIPS settlement share; bilateral yuan invoicing.'),
    ('critical_minerals',
        'Lithium, rare earths, cobalt, copper supply chains as transition battlegrounds.'),
    ('chinese_demand',
        'Securities whose fundamentals are determined by Chinese industrial demand (iron ore, copper, etc.).'),
    ('financial_infrastructure_east',
        'HKEX listings, Stock Connect flows, Shanghai/Shenzhen capital deepening, mainland index inclusions.'),
    ('reserve_diversification',
        'COFER composition shifts; central bank gold buying; non-USD reserve growth.')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- exchanges — set country_code on the HKEX row (NULL-only; never overwrite)
-- =============================================================================
-- Existing intl `exchanges` table is assumed to have a row for HKEX. The
-- precise column used to identify it depends on the intl schema; common
-- patterns are `code = 'HKEX'` or `name ILIKE 'Hong Kong%'`. Adjust the WHERE
-- clause to match the actual intl row at Phase 1 application time.

UPDATE exchanges
   SET country_code = 'HKG'
 WHERE code = 'HKEX'
   AND country_code IS NULL;

-- =============================================================================
-- Learning plans — verbatim from architecture v1.3.0 §7
-- =============================================================================

INSERT INTO cr_learning_plans
    (name, question, period_start, period_end,
     expected_observations, null_hypothesis, data_sources, status)
VALUES
(
    'iron_ore_china_demand',
    'Over the next nine months, do iron ore price movements correlate with subsequent price movements in HKEX-listed and ASX-listed iron ore producers? Specifically, do the producers respond more strongly to iron ore moves than to broader index moves, and is there a measurable lag between commodity price and equity price?',
    DATE '2026-05-01',
    DATE '2027-01-31',
    'Producer prices show stronger correlation with iron ore than with their home indices. A 1-3 day lag between commodity and equity moves is plausible. Larger commodity moves produce larger relative equity moves.',
    'Producers track home indices more than the commodity. No measurable lag pattern. Equity response disconnected from commodity magnitude.',
    jsonb_build_object(
        'commodities',  jsonb_build_array('iron_ore'),
        'securities',   jsonb_build_array('BHP.AX','RIO.AX','FMG.AX','0001.HK_iron_ore_exposed_TBD'),
        'indices',      jsonb_build_array('ASX200','HSI'),
        'country_indicators', jsonb_build_array('CHN.industrial_production','CHN.steel_output')
    ),
    'active'
),
(
    'cofer_gold_reserve_diversification',
    'Does the IMF COFER quarterly data on reserve composition correlate with gold price movements over multi-quarter periods? Specifically, do reductions in dollar share or increases in non-dollar/gold share precede or coincide with gold price strength?',
    DATE '2020-01-01',  -- backfilled per architecture §7
    DATE '2027-12-31',
    'Quarters showing measurable shifts in reserve composition coincide with or precede gold strength. The relationship is not 1:1 but visible across multiple quarters.',
    'Gold price moves independently of COFER data on observable timescales. Reserve composition shifts are too gradual to manifest in tradeable signals.',
    jsonb_build_object(
        'infra_types',  jsonb_build_array('cofer_reserve_composition'),
        'commodities',  jsonb_build_array('gold'),
        'securities',   jsonb_build_array('2899.HK_zijin','1818.HK_zhaojin'),
        'country_indicators', jsonb_build_array('USA.debt_to_gdp','USA.current_account_pct_gdp')
    ),
    'active'
),
(
    'hkex_listing_flows_financial_center',
    'Over a twelve-month observation window, do HKEX listing flows (new IPOs, secondary listings, Stock Connect activity) correlate with broader transition signals — China-US bilateral relationship readings, yuan settlement share, and Chinese cycle position estimates?',
    DATE '2026-05-01',
    DATE '2027-04-30',
    'Periods of strengthening Chinese cycle indicators and weakening China-US bilateral readings coincide with stronger HKEX listing activity, particularly for mainland-domiciled companies. Stock Connect flows show directional shifts aligned with major bilateral events.',
    'HKEX listing activity is driven by idiosyncratic factors (specific company readiness, market window timing) that swamp any structural transition signal.',
    jsonb_build_object(
        'infra_types',  jsonb_build_array('hkex_listing','stock_connect_flow','swift_renminbi_share'),
        'country_pairs', jsonb_build_array(jsonb_build_array('CHN','USA')),
        'cycle_estimates', jsonb_build_array('CHN')
    ),
    'active'
)
ON CONFLICT (name) DO NOTHING;

COMMIT;

-- =============================================================================
-- Post-seed sanity:
--   SELECT count(*) FROM countries;          -- expect 4
--   SELECT count(*) FROM commodities;        -- expect 4
--   SELECT count(*) FROM themes;             -- expect 5
--   SELECT count(*) FROM cr_learning_plans;  -- expect 3
--   SELECT country_code FROM exchanges WHERE code = 'HKEX';  -- expect 'HKG'
-- =============================================================================
