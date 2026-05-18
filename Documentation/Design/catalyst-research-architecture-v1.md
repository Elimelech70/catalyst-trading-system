# Catalyst Research Architecture v1

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-research-architecture-v1.md
<<<<<<< HEAD
**Version:** 1.3.0
=======
**Version:** 1.2.0
>>>>>>> 260c9a651b7a80966ad36c08bb8fb16680b2ee98
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
<<<<<<< HEAD
| 1.3.0 | 2026-05-18 | Craig + Claude | Schema home moved back to `catalyst_intl`, this time as the deliberate long-term choice rather than a default. Driven by the recognition that research and intl trading describe the same real-world securities, prices, and news events — a shared `securities` registry, shared price bars, and shared news feed eliminate sync drift and cross-DB query friction. Safety properties previously achieved by DB separation are now provided by PostgreSQL role-based access control (Section 6.1). Sections 6 and 9 updated to match. The `catalyst_research` cluster database is freed for archive or drop. |
=======
>>>>>>> 260c9a651b7a80966ad36c08bb8fb16680b2ee98

---

## 1. Mission and Thesis

The Catalyst system tracks the West-to-East structural transition as it unfolds, using layered observation of countries, markets, commodities, relationships, and financial infrastructure to identify securities positioned to benefit from that transition. The system invests into those securities as conviction grows from accumulating evidence.

This is a long-horizon investing system, not a day-trading system. The transition is a multi-decade phenomenon. The system's edge is not speed, pattern recognition on noisy intraday data, or out-thinking institutions on macro views they have already priced in. The edge is structural coherence across multiple slow-moving signals, identified before the market has fully repriced, with the patience to hold positions through volatility that institutional capital cannot.

The system operates on a foundational principle: **let the data talk**. We are not building a thesis-execution platform that trades a predetermined view. We are building a research instrument that tracks indicators, observes patterns, and forms theses from accumulated evidence. Ray Dalio's empire-cycle framework provides the vocabulary for what to measure, but conclusions must emerge from our own observation of what the data actually shows. Frameworks are scaffolding; data is truth.

The mission "enable the poor through accessible algorithmic trading" remains the project's north star. This architecture serves that mission by building the research foundation from which sound, long-horizon investment decisions can be made. Trading is downstream of research. Profit is downstream of patient evidence accumulation.

---

## 6. Schema

The schema is sketched here at the level of tables and key columns. Full DDL with constraints, indexes, and foreign keys is the work of a companion implementation file written when the v1 build begins.

<<<<<<< HEAD
### 6.1 Database Home and Access Control
=======
The database is PostgreSQL: the existing `catalyst_research` cluster database, which was originally provisioned for this purpose and is currently holding only legacy consciousness-era tables. Those legacy tables are dropped before the new schema is applied. Sharing a database with `catalyst-international` was considered (and was the v1.1 plan) but rejected — research and trading have different access patterns, different access controls, and different operational risks; keeping them in separate databases on the same cluster is cleaner. The `catalyst_dev` US trading DB remains deprecated and may be archived or dropped after the migration completes.
>>>>>>> 260c9a651b7a80966ad36c08bb8fb16680b2ee98

The schema lives in the **`catalyst_intl` PostgreSQL database**, alongside the existing intl trading tables. This is the v1.3.0 decision, and it reverses the v1.2.0 split.

The reasoning is integration value. Catalyst-research and catalyst-international describe the same real-world entities: the same HKEX-listed securities, the same daily price bars from the same Moomoo OpenD daemon, the same disclosure-feed news events. Splitting the schema across two databases meant duplicating the `securities` registry (two `id` spaces for the same tickers, requiring symbol resolution on every cross-system reference), running two ingestion pipelines for the same Moomoo data, and forcing cross-database queries for what is conceptually a single graph. The cost of this duplication compounds over years. Eliminating it is worth a one-time setup cost.

Sharing a database with a live trading system creates two legitimate concerns: that archetype Claude Code instances could accidentally write to trading tables (`positions`, `orders`, `decisions`), and that a research-side DDL mistake could break trading. Both concerns are addressed through **PostgreSQL role-based access control** rather than through DB separation:

- **`catalyst_trading_writer`** — the existing role used by catalyst-international. INSERT/UPDATE/DELETE on trading tables (`positions`, `orders`, `decisions`, `trading_cycles`, `scan_results`, `pattern_outcomes`, `pattern_confidence`, etc.). No DDL.
- **`catalyst_research_ingestion`** — new role used by Layer 1–5 ingestion jobs. INSERT only on research fact tables (`cr_country_indicators`, `cr_market_prices`, `cr_security_prices`, `cr_news_events`, `cr_country_pair_observations`, `cr_financial_infra_observations`). SELECT on reference tables (`countries`, `sectors`, `themes`, `commodities`, `securities`). No access to trading tables.
- **`catalyst_research_archetype`** — new role used by the four archetype Claude Code instances. INSERT only on `cr_archetype_analyses`, `cr_archetype_peer_reviews`, `cr_model_proposals`. SELECT on all research and trading tables (archetypes need to read trading outcomes to learn from them). No write access to trading tables, no write access to other research tables.
- **`catalyst_research_admin`** — role used for DDL migrations. Full schema access. Used once for Phase 1 and then again only for v1.5 migrations.

Within `catalyst_intl`, research tables are distinguished by the **`cr_`** prefix (catalyst-research). Reference tables shared between trading and research (`securities`, `sectors`, `themes`, `commodities`, `countries`, `exchanges`) carry no prefix because they are dimensional tables describing real-world entities, not artefacts of either subsystem. The existing intl `securities` and `exchanges` tables are extended with the research columns needed (Section 6.2); the new shared dimensional tables (`countries`, `sectors`, `themes`, `commodities`) are added by the research migration.

The `catalyst_research` cluster database is freed by this decision. It currently holds only legacy consciousness-era tables. It can be dropped at Migration Step 6 along with `catalyst_dev`.

### 6.2 Reference and Entity Tables (shared)

**`countries`** — country registry with ISO code, full name, region, primary currency, and notes. New table introduced by the research migration. Initially populated with the four v1 countries (US, China, Hong Kong, Australia) and extended as the country set grows.

**`exchanges`** — already exists in `catalyst_intl`. Extended with `country_code` (FK to `countries`) to support cross-layer queries.

**`sectors`** — new table introduced by the research migration. Sector taxonomy spanning HKEX sector codes (HK.BK1587 etc.) and broader thematic categories (critical minerals, financial infrastructure, energy, defense). A sector belongs to a country or to "global." Sectors can have parent sectors for hierarchical grouping.

**`securities`** — already exists in `catalyst_intl` (the intl trading registry). Extended with `listing_country` (FK to `countries`) and `primary_sector_id` (FK to `sectors`). A separate join table `security_themes` provides thematic exposure tagging. The existing `security_id`, `symbol`, `exchange_id`, `name`, `sector`, `industry` columns remain in place; intl trading code continues to use them unchanged.

**`security_themes`** — new join table. Many-to-many between `securities` and named transition themes (e.g., "yuan internationalization," "critical minerals reshoring," "Chinese demand resilience"). One security can carry multiple themes.

**`themes`** — new table. The registry referenced by `security_themes` and by `cr_news_themes`.

**`commodities`** — new table introduced by the research migration. Commodity registry with name, category (energy, industrial metals, critical minerals, precious metals, agricultural), reference benchmark, and unit.

### 6.3 Research Fact Tables

All research fact tables carry the `cr_` prefix and follow the discipline rules in Section 5 (every fact-bearing table has `event_date` or `period_start`/`period_end`, `source`, `recorded_at`, and `backfill`; no UPDATE on facts; revisions append).

The Layer 1–5 tables (`cr_country_indicators`, `cr_country_cycle_estimates`, `cr_market_prices`, `cr_security_prices`, `cr_news_events`, `cr_news_securities`, `cr_news_themes`, `cr_country_pair_observations`, `cr_financial_infra_observations`) and the analytical tables (`cr_archetype_analyses`, `cr_archetype_peer_reviews`, `cr_model_proposals`, `cr_models_trained`) and the planning tables (`cr_learning_plans`, `cr_investment_theses`, `cr_thesis_history`) are all new. The full DDL is specified in the companion implementation file.

The critical integration points where shared-DB pays off:

- **`cr_news_securities`** FKs to `securities(security_id)` — meaning a news event tagged to a security is *directly* visible to intl trading code via SQL JOIN, with no symbol-resolution layer.
- **`cr_security_prices`** FKs to `securities(security_id)` — meaning the daily HKEX bars that intl trading code already has access to are the same rows the research archetypes analyse. One Moomoo ingestion job, one set of rows, two readers.
- **`cr_market_prices`** carries non-security series (indices, FX, commodities) that intl trading code can also read without cross-DB plumbing.

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
- The `catalyst_research` consciousness database — both its legacy tables AND the database itself (v1.3.0 hosts research in `catalyst_intl`, freeing the `catalyst_research` cluster DB entirely)
- The position monitor signal taxonomy and Haiku consultation logic
- The scanner's tiered scoring and composite ranking
- The `MAX_HAIKU_CALLS_PER_CYCLE` budget and all Anthropic API budget allocations
- Multi-agent droplet deployments

This is sunk cost. It served its purpose by clarifying what does not work. Keeping it around as "we might come back to it" creates fragmentation. Clean deletion frees attention.

### What Is Repurposed

<<<<<<< HEAD
- The Moomoo client and OpenD integration — directly reusable for HKEX market data ingestion in Layer 2 and Layer 3. The same connection that places intl trading orders pulls quotes and historical bars for research. Because research and intl now share the database, the Moomoo ingestion writes once and serves both readers.
- The `catalyst_intl` PostgreSQL database — extended with research tables (`cr_*`) and shared dimensional tables (`countries`, `sectors`, `themes`, `commodities`). Intl trading tables remain untouched in shape; only `securities` and `exchanges` gain additional optional columns.
- The existing `securities` and `exchanges` tables — extended with theme tags, country exposure metadata, and country FK.
=======
- The Moomoo client and OpenD integration — directly reusable for HKEX market data ingestion in Layer 2 and Layer 3, even though we are not trading. The same connection that places orders can pull quotes and historical bars.
- The `catalyst_research` PostgreSQL database — the database itself stays, dedicated to this system. Its legacy consciousness-era tables are dropped; the new schema replaces them. The intl trading database (`catalyst_intl`) is untouched by the research build.
- The existing `securities` table — extended with theme tags and country exposure metadata.
>>>>>>> 260c9a651b7a80966ad36c08bb8fb16680b2ee98
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
- PostgreSQL role-based access control inside `catalyst_intl` providing the safety isolation that previously came from DB separation

### Migration Sequence

The sequence matters. Each step is reversible until the next begins; nothing is deleted until what replaces it works.

**Step 1.** Stop all running agent cron jobs on the production droplet. The system goes idle. This is acceptable because the system was producing zero economic value and was at risk of producing negative value from misfiring agent cycles. *(Completed 2026-05-18.)*

**Step 2.** Snapshot `catalyst_intl`. This is insurance against the Phase 1 DDL migration that extends the trading database with research tables. Also snapshot `catalyst_research` before dropping its legacy tables (cheap, prudent, single command).

<<<<<<< HEAD
**Step 3.** In `catalyst_intl`, create the four PostgreSQL roles (`catalyst_research_admin`, `catalyst_research_ingestion`, `catalyst_research_archetype`, and confirm the existing `catalyst_trading_writer` role exists or create it). Apply the Phase 1 DDL migration as `catalyst_research_admin`: extend `securities` and `exchanges`, add the shared dimensional tables, add all `cr_*` research tables. Grant the appropriate per-role privileges.
=======
**Step 3.** Drop the legacy consciousness-era tables from `catalyst_research`. Build the new schema in `catalyst_research`. The new tables share no names with the legacy ones, so this is a clean replacement rather than a coexistence migration.
>>>>>>> 260c9a651b7a80966ad36c08bb8fb16680b2ee98

**Step 4.** Build and test ingestion jobs against the new schema, country by country, layer by layer. Australia first (Craig's home, easy data), then US (deepest data, validates the schema's handling of dense series), then China (validates handling of mixed-quality data), then Hong Kong. All ingestion jobs connect as `catalyst_research_ingestion`.

**Step 5.** Once ingestion is working and producing observable data for at least four weeks, set up archetype scheduling. Archetypes connect as `catalyst_research_archetype` — they can read everything (including intl trading outcomes, which is intentional: archetypes learn from trade results), but write only to their own analysis tables.

**Step 6.** Drop the legacy `catalyst_research` cluster database entirely. Drop the deprecated `catalyst_dev` cluster database. Archive the `catalyst-agent/` directory on the US droplet. Update repo-root CLAUDE.md and architecture documentation to reflect the new shape.

**Step 7.** Begin the three v1 learning plans formally. Set their review dates. Begin observation.

The expected calendar time for steps 1–7 is approximately four to six weeks, executed by little_bro under Craig's direction with the companion implementation file as the specification.

---

*End of document.*
