# Catalyst Research — Current Focus (Short-Term Memory)

## Active phase: pre-Phase-0 (scaffolding)

Build started 2026-05-18. Currently writing the v1 scaffold against architecture v1.3.0 and implementation v1.3.0.

### Done

- [x] Folder scaffold (`sql/`, `ingestion/`, `archetypes/{historian,strategist,macro_theorist,skeptic,runs}/`, `scripts/`, `tests/`, `logs/`).
- [x] CLAUDE.md trio.

### Next

- [ ] Write `requirements.txt`, `.env.template`, `.gitignore`.
- [ ] Write `sql/001_initial_schema.sql` per implementation §1.2.
- [ ] Write `sql/002_seed_v1.sql` per implementation §1.3.
- [ ] Phase 0.3 column-type verification on intl droplet — Craig.
- [ ] Apply migration → confirm Phase 1 exit criteria pass.
- [ ] Begin Phase 2 ingestion, starting with `ingest_market_prices_daily` (simplest; validates adapter pattern).

### Blocked on Craig (ops)

- Phase 0.1 DB snapshot via DigitalOcean (catalyst_intl).
- Phase 0.2 credential rotation (Anthropic, Moomoo).
- Phase 0.3 column-type verification — `psql "$INTL_DATABASE_URL" -c "\d securities" | grep security_id` from the intl droplet. The Phase 1 DDL assumes `integer`; needs confirmation before migration runs.
- Phase 0 role passwords — three new PostgreSQL roles (`catalyst_research_admin`, `catalyst_research_ingestion`, `catalyst_research_archetype`) need passwords provisioned and stored in the droplet `.env`.
