# Catalyst Research — Current Focus (Short-Term Memory)

## Active phase: Phase 0 (ops; blocked on Craig)

The full v1 build is authored and committed. **Nothing runs against the live DB until Phase 0 ops are done.**

### Done

- [x] Folder scaffold + CLAUDE.md trio + README + requirements/env/gitignore.
- [x] `sql/001_initial_schema.sql` — full Phase 1 DDL (roles, ALTER TABLEs, all `cr_*` tables, RBAC grants).
- [x] `sql/002_seed_v1.sql` — countries, commodities, themes, three learning plans, HKEX exchange country_code.
- [x] `ingestion/_adapter.py` — append-on-revision idempotency, `recorded_by` auto-stamping, news-event insert helper.
- [x] All 11 ingestion jobs (`ingestion/ingest_*.py`). Real fetch for Yahoo, IMF, World Bank, UN Comtrade. Stubs (with adapter pattern wired) for BEA / NBS / HKMA / RBA / Voeten / HKEX feed JSON / HKEX listing stats — fill in source-specific parsing in Phase 2 build order.
- [x] Archetype suite: `archetypes/run.py` (orchestrator), `build_context.py`, `db.py`, four `system.md` lens prompts.
- [x] 5 inspection scripts + `scripts/seed_learning_plans.py` + `scripts/_db.py`.
- [x] `crontab.txt` — reference cron for the intl droplet.
- [x] Tests: `tests/test_adapter_idempotency.py` (10 passing), `tests/test_archetype_wrapper.py`.

### Next (blocked on Craig — ops)

1. **Phase 0.1** — DigitalOcean snapshot of `catalyst_intl` (fresh, dated today).
2. **Phase 0.2** — Rotate credentials per `Documentation/Implementation/catalyst-research-implementation-v1.3.md` §0.2.
3. **Phase 0.3** — On the intl droplet:
   ```
   psql "$INTL_DATABASE_URL" -c "\d securities" | grep security_id
   psql "$INTL_DATABASE_URL" -c "\d exchanges"  | grep exchange_id
   nc -zv 127.0.0.1 11111   # Moomoo OpenD reachable?
   ```
   If `security_id` is not `integer`, edit `sql/001_initial_schema.sql` (3 occurrences of `security_id integer REFERENCES securities(security_id)`) to match the real type before applying.
4. **Phase 0.4** — Read the rollback procedure (no action; just be ready).
5. **Phase 1.2** — Apply `001_initial_schema.sql` then `002_seed_v1.sql` as `catalyst_research_admin`:
   ```bash
   psql "$RESEARCH_ADMIN_DATABASE_URL" \
        -v research.admin_pwd=...  -v research.ingestion_pwd=...  -v research.archetype_pwd=... \
        -f catalyst-research/sql/001_initial_schema.sql
   psql "$RESEARCH_ADMIN_DATABASE_URL" \
        -f catalyst-research/sql/002_seed_v1.sql
   ```
6. **Phase 1.4 smoke** — run the SET ROLE / INSERT / SELECT verifications at the bottom of `001_initial_schema.sql`. Both research roles must be denied write to `positions`.

### Then (Phase 2, can begin)

7. `pip install -r catalyst-research/requirements.txt` on the intl droplet.
8. Run one job manually: `python -m ingestion.ingest_market_prices_daily` — should INSERT 5 days × 9 series. Run twice; second run should be all "skipped".
9. Country-by-country fill in for `ingest_country_indicators_national.py` (AUS first per arch §9 Step 4). Currently a stub.
10. Install crontab once Phase 2 jobs are individually verified.

### Phase 3 entry gate

11. `claude --version` works on the intl droplet, and the `--print --output-format=json --append-system-prompt … --max-turns N --permission-mode plan` invocation in `archetypes/run.py:invoke_claude` actually runs end-to-end against a throwaway test prompt. Update flag names if the installed CLI version differs.

### Phase 4

12. Install `crontab.txt` → `/etc/cron.d/catalyst-research`.
13. Four weeks of clean weekly reports.
14. Cleanup: drop `catalyst_research` + `catalyst_dev` DBs; archive `catalyst-agent/`; update repo-root CLAUDE.md.
