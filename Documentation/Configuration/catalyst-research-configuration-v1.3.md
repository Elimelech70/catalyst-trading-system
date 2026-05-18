# Catalyst Research — Configuration

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-research-configuration-v1.3.md
**Version:** 1.3.0
**Created:** 2026-05-18
**Updated by:** Craig + Claude
**Implements:** `Documentation/Design/catalyst-research-architecture-v1.3.md` (v1.3.0)
**Buildable spec:** `Documentation/Implementation/catalyst-research-implementation-v1.3.md` (v1.3.0)
**Build maturity:** code at `catalyst-research/` is v0.1.0 (initial; pre-Phase-0)
**Purpose:** Operational reference. Lists every environment variable, every PostgreSQL role and grant, every cron entry and its dependencies, the smoke-verifications to run after each phase, and the locations of all state (DB tables, env vars, files, logs). Designed for the operator deploying or maintaining catalyst-research on the intl droplet.

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.3.0 | 2026-05-18 | Craig + Claude | Initial configuration doc, aligned with architecture v1.3.0 / implementation v1.3.0 / build v0.1.0. |

---

## 1. What this document is and is not

**Is:** the operator's reference for deploying and running catalyst-research v1. Lists every knob and where each piece of state lives.

**Is not:**
- A design document → see [`../Design/catalyst-research-architecture-v1.3.md`](../Design/catalyst-research-architecture-v1.3.md)
- A build spec → see [`../Implementation/catalyst-research-implementation-v1.3.md`](../Implementation/catalyst-research-implementation-v1.3.md)
- A learning document → see `catalyst-research/CLAUDE.md`, `CLAUDE-LEARNINGS.md`, `CLAUDE-FOCUS.md`

When the architecture and this document disagree, the architecture wins and this document is wrong. Open an issue.

---

## 2. Deployment topology

| Component | Lives on | Notes |
|---|---|---|
| `catalyst_intl` database (PostgreSQL) | DigitalOcean managed cluster | Shared with `catalyst-international` trading. v1.3.0 reverses earlier dedicated-DB plan; RBAC isolates research from trading. |
| `catalyst-research/` code tree | intl droplet (`catalyst-trading-system-international`, SYD1, 209.38.87.27) | Co-located with Moomoo OpenD (`127.0.0.1:11111`) and existing intl-trading cron. |
| Moomoo OpenD daemon | intl droplet, `127.0.0.1:11111` | Reused from intl trading. Source for `cr_security_prices` and (future) HKEX bars. |
| US droplet (`catalyst-trading-prod-01`, SGP1) | Dormant | Awaiting next workload. **Not** used by catalyst-research v1. |
| Claude Code CLI (for archetypes) | intl droplet | System-level install. Verified via `claude --version` (Phase 3 entry criterion). |
| GitHub repo | github.com/Elimelech70/catalyst-trading-system | `main` branch. PATs rotated 2026-05-18. |

---

## 3. PostgreSQL — roles and grants

Four roles, **all targeting the same `catalyst_intl` database**. Role determines what each connection can read and write. The grants are applied by `sql/001_initial_schema.sql` inside a single transaction.

### 3.1 Role inventory

| Role | Provisioned by | Used by | Privileges |
|---|---|---|---|
| `catalyst_trading_writer` | Pre-existing (intl trading) | catalyst-international agents | INSERT/UPDATE/DELETE on trading tables (`positions`, `orders`, `decisions`, `trading_cycles`, `scan_results`, `pattern_outcomes`, `pattern_confidence`, etc.). No DDL. Unchanged by this build. |
| `catalyst_research_admin` | `sql/001_initial_schema.sql` | One-shot DDL migrations only (Phase 1, future v1.5) | Full schema access. Used to apply schema + seed; otherwise idle. |
| `catalyst_research_ingestion` | `sql/001_initial_schema.sql` | All 11 Layer 1-5 ingestion jobs | SELECT on dimensional tables (`countries`, `sectors`, `themes`, `commodities`, `security_themes`, `securities`, `exchanges`). INSERT only on `cr_*` fact tables. **No access to trading tables.** USAGE/SELECT on `cr_*` sequences only (trading sequences NOT granted). |
| `catalyst_research_archetype` | `sql/001_initial_schema.sql` | Four archetype Claude Code instances + read-only inspection scripts | SELECT on **all** tables (incl. trading — archetypes learn from real outcomes). INSERT only on `cr_archetype_analyses`, `cr_archetype_peer_reviews`, `cr_model_proposals`. |

### 3.2 What the grants enforce

The smoke queries at the bottom of `sql/001_initial_schema.sql` verify each property:

```sql
SET ROLE catalyst_research_ingestion;
SELECT count(*) FROM securities;            -- succeeds (dimensional read)
SELECT count(*) FROM positions;             -- FAILS: permission denied (no trading read)
INSERT INTO positions (symbol, side, quantity, entry_price)
     VALUES ('TEST', 'long', 1, 1.00);      -- FAILS: permission denied
RESET ROLE;

SET ROLE catalyst_research_archetype;
SELECT count(*) FROM positions;             -- succeeds (reads outcomes)
INSERT INTO positions (symbol, side, quantity, entry_price)
     VALUES ('TEST', 'long', 1, 1.00);      -- FAILS: permission denied
RESET ROLE;
```

Both queries must behave as commented. If either passes when it should fail, the migration is incomplete; restore from the snapshot taken in Phase 0.1.

### 3.3 Role passwords

Provisioned at Phase 0.2 and passed to the migration as `psql -v` variables:

```bash
psql "$SUPERUSER_DATABASE_URL" \
     -v research.admin_pwd='<strong-pwd-1>' \
     -v research.ingestion_pwd='<strong-pwd-2>' \
     -v research.archetype_pwd='<strong-pwd-3>' \
     -f catalyst-research/sql/001_initial_schema.sql
```

The three passwords are then stored in the intl droplet's `.env` as the password components of `RESEARCH_*_DATABASE_URL` (see §4). They are **not** stored in git.

---

## 4. Environment variables

All variables live in the intl droplet's `.env` at `/root/.env` (or wherever the existing intl cron expects). The template is `catalyst-research/.env.template`. Never commit a populated `.env`.

### 4.1 Existing (intl trading) — unchanged

| Variable | Read by | Purpose |
|---|---|---|
| `INTL_DATABASE_URL` | catalyst-international agents | Trading-side DB connection as `catalyst_trading_writer`. catalyst-research does **not** use this URL. |
| `MOOMOO_HOST` | intl trading + research `ingest_security_prices_daily` | Defaults to `127.0.0.1`. |
| `MOOMOO_PORT` | intl trading + research | Defaults to `11111`. |

### 4.2 New — catalyst-research

| Variable | Required | Read by | Notes |
|---|---|---|---|
| `RESEARCH_ADMIN_DATABASE_URL` | Yes (Phase 1 + future migrations only) | `psql` migrations, `scripts/seed_learning_plans.py` | `postgres://catalyst_research_admin:<pwd>@host:25060/catalyst_intl?sslmode=require` |
| `RESEARCH_INGESTION_DATABASE_URL` | Yes (Phase 2 onward) | `ingestion/_adapter.py` → every `ingestion/ingest_*.py` | Same host/DB as admin URL but different role + password. |
| `RESEARCH_ARCHETYPE_DATABASE_URL` | Yes (Phase 3 onward) | `archetypes/db.py`, `scripts/_db.py` (used by all `scripts/show_*.py`) | Same host/DB, archetype role. |
| `ANTHROPIC_API_KEY` | Yes (Phase 3 onward) | `claude` CLI invoked by `archetypes/run.py` | **Archetype-only key**, with a monthly spend cap set in the Anthropic console. Provisioned fresh in Phase 0.2; the agent-era key is revoked. |
| `CLAUDE_CLI` | No | `archetypes/run.py:_claude_cli()` | Defaults to `claude`. Override if the CLI is installed at a non-PATH location. |
| `HKEX_FEED_URL` | No | `ingestion/ingest_hkex_disclosure_feed.py` | Defaults to `https://www1.hkexnews.hk/ncms/script/eds/eds_newsfile_en.json`. Override if HKEX changes the public feed URL. |
| `BEA_API_KEY` | Required for `ingest_country_indicators_national` US fetcher | `ingestion/ingest_country_indicators_national.py` | Without it, the US fetcher logs `national.us.skip` and returns empty. AUS/CHN/HKG fetchers are unaffected. |
| `UN_COMTRADE_API_KEY` | No (raises rate limit if set) | `ingestion/ingest_un_comtrade.py` | Free tier ~100 calls/day unkeyed; ~10x with a free key. |
| `COFER_CSV_PATH` or `COFER_CSV_URL` | One required for COFER ingestion | `ingestion/ingest_imf_cofer.py` | Path takes precedence if both set. Without either, the job logs `cofer.no_source` and returns empty (no-op, not an error). |
| `HKEX_STATS_JSON_PATH` | Required for HKEX listing-stats ingestion | `ingestion/ingest_hkex_listing_stats.py` | Local JSON file; expected shape documented in the job's docstring. Without it, the job logs `hkex_stats.no_source` and returns empty. |
| `CR_LOG_DIR` | No | Convention used by cron stdout/stderr | Defaults to `/root/catalyst-research/logs`. Cron entries write to `${CR_LOG_DIR}/cron.log` and `${CR_LOG_DIR}/archetypes.log`. |

### 4.3 What is **not** an environment variable

- **Watchlist** — there is no `WATCHLIST_PATH`. The shared `securities` table (rows with `listing_country = 'HKG'`) **is** the watchlist for `ingest_security_prices_daily` and for HKEX disclosure→security linking. To add a security, INSERT it into `securities` and set `listing_country = 'HKG'`.
- **Archetype lens prompts** — files at `catalyst-research/archetypes/<archetype>/system.md`. Edited in git, not via env vars.
- **Cron schedule** — `catalyst-research/crontab.txt`, installed to `/etc/cron.d/catalyst-research`. Edited in git, not via env vars.

---

## 5. Schema migration

The schema is applied **as a single transaction** by `catalyst_research_admin`. If any statement fails, the entire migration rolls back and Phase 0.1's snapshot stays as the rollback path (with Phase 0.4 Option A as the cleanup procedure).

### 5.1 Files

| File | Run by | Purpose |
|---|---|---|
| `catalyst-research/sql/001_initial_schema.sql` | `catalyst_research_admin` | Creates the three new roles (idempotent), the `cr_set_updated_at()` trigger function, ALTER TABLE additions to `securities` and `exchanges`, shared dimensional tables, all 14 `cr_*` fact / analytical / planning tables, indexes, triggers, and grants. |
| `catalyst-research/sql/002_seed_v1.sql` | `catalyst_research_admin` | Seeds the four v1 countries, four commodities, five themes, three learning plans (verbatim from architecture §7), and `country_code='HKG'` on the HKEX `exchanges` row. Fully idempotent: `INSERT ... ON CONFLICT DO NOTHING`; all UPDATEs scoped `WHERE ... IS NULL`. |
| `catalyst-research/sql/003_seed_securities.sql` (NOT YET WRITTEN) | `catalyst_research_admin` | Will seed the 20-30 HKEX security rows (the v1 starter watchlist). Deferred until Craig finalises the name list (architecture §8 lists thematic coverage; specific tickers chosen at Phase 1 application time). |

### 5.2 Pre-migration verification (Phase 0.3)

Run on the intl droplet **before** applying `001`:

```bash
psql "$INTL_DATABASE_URL" -c "\d securities" | grep security_id
psql "$INTL_DATABASE_URL" -c "\d exchanges"  | grep exchange_id
```

The Phase 1 DDL declares `security_id integer REFERENCES securities(security_id)` in three places (`cr_security_prices`, `cr_news_securities`, `security_themes`). If the intl `securities.security_id` is `bigint` or `bigserial`, edit `001_initial_schema.sql` to match **before applying**. A type mismatch breaks the migration mid-transaction.

```bash
nc -zv 127.0.0.1 11111   # Moomoo OpenD reachable from the intl droplet?
```

### 5.3 Apply

```bash
cd /root/catalyst-trading-system

# Schema + roles
psql "$SUPERUSER_DATABASE_URL" \
     -v research.admin_pwd='...' \
     -v research.ingestion_pwd='...' \
     -v research.archetype_pwd='...' \
     -f catalyst-research/sql/001_initial_schema.sql

# Seed
psql "$RESEARCH_ADMIN_DATABASE_URL" \
     -f catalyst-research/sql/002_seed_v1.sql

# Securities seed (once 003_seed_securities.sql is written)
# psql "$RESEARCH_ADMIN_DATABASE_URL" \
#      -f catalyst-research/sql/003_seed_securities.sql
```

### 5.4 Phase 1 exit smoke (run all of these; all must behave as commented)

```sql
-- Reference data
SELECT count(*) FROM countries;             -- 4
SELECT count(*) FROM commodities;           -- 4
SELECT count(*) FROM themes;                -- 5
SELECT count(*) FROM cr_learning_plans;     -- 3
SELECT country_code FROM exchanges WHERE code = 'HKEX';   -- HKG

-- Role isolation (see §3.2)
SET ROLE catalyst_research_ingestion;
SELECT count(*) FROM securities;            -- succeeds
SELECT count(*) FROM positions;             -- FAILS
INSERT INTO positions (symbol, side, quantity, entry_price)
     VALUES ('TEST', 'long', 1, 1.00);      -- FAILS
RESET ROLE;

SET ROLE catalyst_research_archetype;
SELECT count(*) FROM positions;             -- succeeds
INSERT INTO positions (symbol, side, quantity, entry_price)
     VALUES ('TEST', 'long', 1, 1.00);      -- FAILS
RESET ROLE;
```

Then verify intl trading is **unaffected**: run one full intl trading cycle and confirm `positions`, `orders`, `decisions` writes still succeed. If they don't, restore from snapshot.

---

## 6. Cron schedule

Installed to `/etc/cron.d/catalyst-research` on the **intl droplet** (not US). Source of truth: `catalyst-research/crontab.txt`.

### 6.1 Install

```bash
sudo cp /root/catalyst-trading-system/catalyst-research/crontab.txt \
        /etc/cron.d/catalyst-research
sudo chown root:root /etc/cron.d/catalyst-research
sudo chmod 0644      /etc/cron.d/catalyst-research
sudo systemctl restart cron
```

The intl trading cron is unchanged. Both cron files coexist.

### 6.2 Schedule and per-job dependencies

All times UTC. Cron working directory is `/root/catalyst-research` (set per line).

| Time | Job | Module | Required env vars |
|---|---|---|---|
| `30 22 * * 1-5` | Market prices (indices, FX, yields) | `ingestion.ingest_market_prices_daily` | `RESEARCH_INGESTION_DATABASE_URL` |
| `45 22 * * 1-5` | Commodity prices | `ingestion.ingest_commodity_prices_daily` | `RESEARCH_INGESTION_DATABASE_URL` |
| `30 8 * * 1-5` | HKEX security prices via Moomoo | `ingestion.ingest_security_prices_daily` | `RESEARCH_INGESTION_DATABASE_URL`, `MOOMOO_HOST`, `MOOMOO_PORT` |
| `*/15 1-9 * * 1-5` | HKEX disclosure feed | `ingestion.ingest_hkex_disclosure_feed` | `RESEARCH_INGESTION_DATABASE_URL`, optional `HKEX_FEED_URL` |
| `0 6 1 1,4,7,10 *` | IMF WEO indicators | `ingestion.ingest_country_indicators_imf` | `RESEARCH_INGESTION_DATABASE_URL` |
| `0 7 1 1,4,7,10 *` | World Bank indicators | `ingestion.ingest_country_indicators_worldbank` | `RESEARCH_INGESTION_DATABASE_URL` |
| `0 8 2 1,4,7,10 *` | National-source indicators | `ingestion.ingest_country_indicators_national` | `RESEARCH_INGESTION_DATABASE_URL`; `BEA_API_KEY` for US fetch |
| `0 8 5 * *` | UN Comtrade bilateral trade | `ingestion.ingest_un_comtrade` | `RESEARCH_INGESTION_DATABASE_URL`; optional `UN_COMTRADE_API_KEY` |
| `0 8 1 6 *` | UN voting alignment (annual) | `ingestion.ingest_un_voting_alignment` | `RESEARCH_INGESTION_DATABASE_URL` (currently stub) |
| `0 9 5 1,4,7,10 *` | IMF COFER (quarterly) | `ingestion.ingest_imf_cofer` | `RESEARCH_INGESTION_DATABASE_URL`, `COFER_CSV_PATH` or `COFER_CSV_URL` |
| `0 9 7 * *` | HKEX monthly listing stats | `ingestion.ingest_hkex_listing_stats` | `RESEARCH_INGESTION_DATABASE_URL`, `HKEX_STATS_JSON_PATH` |
| `0 2 * * 6` | Weekly archetype analyses (4 archetypes) | `archetypes.run --scope=weekly --phase=analysis` | `RESEARCH_ARCHETYPE_DATABASE_URL`, `ANTHROPIC_API_KEY` |
| `0 6 * * 6` | Weekly peer review (4 archetypes) | `archetypes.run --scope=weekly --phase=peer_review` | `RESEARCH_ARCHETYPE_DATABASE_URL`, `ANTHROPIC_API_KEY` |
| `0 2 1 * *` | Monthly synthesis | `archetypes.run --scope=monthly` | as above |
| `0 2 5 1,4,7,10 *` | Quarterly cycle update (Macro Theorist) | `archetypes.run --scope=quarterly --archetype=macro_theorist` | as above |

### 6.3 Anthropic budget — projection and ceiling

Per implementation §3.5:

- **Modelled spend:** ~37 substantial Claude Code runs/month (16 weekly analyses + 16 weekly peer reviews + ~4 monthly + ~1 quarterly).
- **Console-level cap:** 2× modelled spend (configured in Anthropic console — set explicitly).
- **Alarm threshold:** 1.5× modelled. `scripts/show_cron_health.py` reports month-to-date count and flags ≥55 runs.
- **Per-run ceiling:** `--max-turns 10` for analysis, 6 for peer review (`archetypes/run.py:TURNS_BY_PHASE`).
- **Graceful degradation:** if drift toward cap, demote Skeptic peer review to monthly (saves 4 runs/month). See implementation §3.5.

---

## 7. File and state locations

| What | Where | Owner |
|---|---|---|
| Schema migration | `catalyst-research/sql/001_initial_schema.sql` | git, applied by `catalyst_research_admin` |
| Seed data (countries, commodities, themes, plans) | `catalyst-research/sql/002_seed_v1.sql` | git, applied by `catalyst_research_admin` |
| v1 watchlist | `securities` table rows with `listing_country = 'HKG'` | DB |
| Active learning plans | `cr_learning_plans` rows | DB; new plans via `scripts/seed_learning_plans.py` |
| Investment theses | `cr_investment_theses` + `cr_thesis_history` | DB; updates via app code (TBD post-v1) |
| Layer 1–5 observations | `cr_country_indicators`, `cr_country_cycle_estimates`, `cr_market_prices`, `cr_security_prices`, `cr_news_events`, `cr_country_pair_observations`, `cr_financial_infra_observations` | DB; INSERT-only by ingestion role |
| Archetype outputs | `cr_archetype_analyses`, `cr_archetype_peer_reviews`, `cr_model_proposals`, `cr_models_trained` | DB; INSERT-only by archetype role |
| Raw archetype run artefacts (forensics) | `catalyst-research/archetypes/runs/<date>/<archetype>_<scope>_<phase>.json` | filesystem, gitignored |
| Ingestion logs | `${CR_LOG_DIR}/cron.log` (default `/root/catalyst-research/logs/cron.log`) | filesystem; rotate via standard logrotate (not configured by this build) |
| Archetype logs | `${CR_LOG_DIR}/archetypes.log` | filesystem |
| Lens prompts | `catalyst-research/archetypes/<archetype>/system.md` | git |
| Wrapper / orchestration code | `catalyst-research/archetypes/run.py` | git |
| Inspection scripts | `catalyst-research/scripts/show_*.py` | git |

State the operator should NEVER edit by hand:
- `cr_*` fact tables (revisions append; no UPDATE).
- `cr_archetype_*` and `cr_model_*` tables (append-only by design).

State the operator may edit:
- `cr_learning_plans` via `scripts/seed_learning_plans.py PATH.json`.
- `securities` (intl trading owns; coordinate with intl side before INSERT).
- Lens prompts in git (then deploy via pull).

---

## 8. Source-specific configuration

### 8.1 World Bank Indicators

No key required. Default rate limit comfortably handles the v1 query volume (4 countries × 8 indicators × quarterly cron = 32 calls/quarter).

### 8.2 IMF datamapper

No key required.

### 8.3 BEA (US national accounts)

Free key required. Register at <https://apps.bea.gov/API/signup/>.  Set `BEA_API_KEY` in `.env`. Without it the US fetcher in `ingest_country_indicators_national.py` is a no-op (logs `national.us.skip` and returns).

### 8.4 UN Comtrade

Free public endpoint allows ~100 calls/day. With a free key (`UN_COMTRADE_API_KEY`) the limit increases ~10×. Six pairs × ~24 months × 2 directions = 288 calls for a year's backfill — comfortably within keyed limits, tight without. Register at <https://comtradeplus.un.org/>.

### 8.5 Voeten UN voting

Annual dataset distributed via Harvard Dataverse. v1 ingestion is a stub (`fetch_voeten_rows` returns empty). To enable: download `UNVotes.csv` to a stable local path on the intl droplet, then implement the fetcher per the docstring's suggested approach.

### 8.6 IMF COFER

Quarterly CSV from <https://data.imf.org/cofer>. Either:

- Download manually each quarter, save to `${COFER_CSV_PATH}` (e.g. `/root/catalyst-research/data/cofer/cofer_latest.csv`), or
- Set `COFER_CSV_URL` to a stable mirror URL.

`COFER_CSV_PATH` takes precedence if both are set.

### 8.7 HKEX monthly listing statistics

HKEX publishes as monthly PDF + HTML tables. v1 ingestion reads a pre-staged local JSON file at `${HKEX_STATS_JSON_PATH}`. Shape (one record per metric per month):

```json
[
  {"year": 2026, "month": 4, "metric": "ipo_count", "value": 12},
  {"year": 2026, "month": 4, "metric": "ipo_funds_raised_hkd_million", "value": 4200.5},
  {"year": 2026, "month": 4, "metric": "secondary_listings_count", "value": 3},
  {"year": 2026, "month": 4, "metric": "stock_connect_northbound_net_hkd_million", "value": 15400.2},
  {"year": 2026, "month": 4, "metric": "stock_connect_southbound_net_hkd_million", "value": 22800.7}
]
```

Refresh monthly by hand (or build a parser in v1.1 — out of v1 scope).

### 8.8 HKEX disclosure feed

Polled every 15 minutes during HKEX trading hours. Default URL is the public English news file (`https://www1.hkexnews.hk/ncms/script/eds/eds_newsfile_en.json`). Override via `HKEX_FEED_URL` if HKEX changes the endpoint. The parser is defensive across known payload shapes (`items`, `results`, `data`, `newsList`); first live run should be spot-checked against the actual response.

### 8.9 Moomoo OpenD

Reused from intl. Must be running on the intl droplet (`MOOMOO_HOST=127.0.0.1`, `MOOMOO_PORT=11111`). Verify via `nc -zv 127.0.0.1 11111` before running `ingest_security_prices_daily`. Symbol normalization: research expects `securities.symbol` to contain digits (any of `0700`, `00700`, `700`, `HK.00700`, `0700.HK` work).

### 8.10 Yahoo Finance

`yfinance` library; no key. Best-effort source. If a series goes silently empty, the job logs `market_prices.empty` / `commodity.empty` and skips. The `show_cron_health.py` weekly heartbeat will surface a drift in row counts.

### 8.11 Anthropic API

Archetype-only key. **Required actions in the Anthropic console:**

1. Provision a fresh API key (Phase 0.2).
2. Set a hard monthly spend cap at **2× modelled** spend (the modelled cost depends on per-archetype context size; estimate after the first weekly run).
3. Enable usage alerts at 50%, 75%, 100% of cap.

If the cap is reached mid-month, the cron's `claude` invocations fail; ingestion continues unaffected. `show_cron_health.py` will report the gap.

---

## 9. Operational runbook

### 9.1 First-time deploy on intl droplet

```bash
# Pull
cd /root && git clone https://github.com/Elimelech70/catalyst-trading-system.git || \
    (cd /root/catalyst-trading-system && git pull origin main)
cd /root/catalyst-trading-system/catalyst-research

# Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Env
cp .env.template /root/.env.research   # then edit to fill in real values
# OR merge into the existing intl /root/.env

# Verify (Phase 0.3)
psql "$INTL_DATABASE_URL" -c "\d securities" | grep security_id   # confirm 'integer'
nc -zv 127.0.0.1 11111                                            # Moomoo reachable?

# Apply schema (Phase 1)
psql "$SUPERUSER_DATABASE_URL" \
     -v research.admin_pwd='...' \
     -v research.ingestion_pwd='...' \
     -v research.archetype_pwd='...' \
     -f sql/001_initial_schema.sql
psql "$RESEARCH_ADMIN_DATABASE_URL" -f sql/002_seed_v1.sql

# Smoke (Phase 1 exit criteria — see §5.4)
psql "$INTL_DATABASE_URL" <<'EOF'
SELECT count(*) FROM countries;
SELECT count(*) FROM commodities;
SELECT count(*) FROM themes;
SELECT count(*) FROM cr_learning_plans;
SELECT country_code FROM exchanges WHERE code = 'HKEX';
EOF

# First manual run (Phase 2 sanity)
PYTHONPATH=. python -m ingestion.ingest_market_prices_daily
# Run again — second run should be all "skipped" (idempotency)
PYTHONPATH=. python -m ingestion.ingest_market_prices_daily

# Smoke-test the claude CLI (Phase 3 entry criterion)
claude --version
# If a flag in archetypes/run.py:invoke_claude is unrecognised by your
# installed Claude Code version, fix run.py and rerun before installing cron.

# Install cron once each job has been manually verified
sudo cp crontab.txt /etc/cron.d/catalyst-research
sudo chown root:root /etc/cron.d/catalyst-research
sudo chmod 0644 /etc/cron.d/catalyst-research
sudo systemctl restart cron
```

### 9.2 Add a security to the v1 watchlist

```sql
-- 1. INSERT into the shared securities table (may already exist — intl trading
--    may have rows). Coordinate with the intl side if uncertain.
INSERT INTO securities (symbol, exchange_id, name)
     VALUES ('0388', (SELECT exchange_id FROM exchanges WHERE code = 'HKEX'),
             'Hong Kong Exchanges and Clearing Limited')
ON CONFLICT (symbol, exchange_id) DO NOTHING;

-- 2. Set research-side metadata. Only fills nulls.
UPDATE securities
   SET listing_country   = 'HKG',
       primary_sector_id = (SELECT id FROM sectors
                            WHERE code = 'HKEX_FINANCIAL_INFRASTRUCTURE')
 WHERE symbol = '0388'
   AND listing_country IS NULL;

-- 3. Tag with themes.
INSERT INTO security_themes (security_id, theme_id)
SELECT s.security_id, t.id
  FROM securities s, themes t
 WHERE s.symbol = '0388'
   AND t.name IN ('financial_infrastructure_east')
ON CONFLICT DO NOTHING;
```

The next `ingest_security_prices_daily` cron run will pick it up automatically (the watchlist IS the table).

### 9.3 Add or revise a learning plan

```bash
cat > /tmp/new_plan.json <<'JSON'
{
  "name": "copper_china_industrial_cycle",
  "question": "Does copper price lead Chinese industrial production by 2-3 months?",
  "period_start": "2026-06-01",
  "period_end":   "2027-06-30",
  "expected_observations": "...",
  "null_hypothesis":       "...",
  "data_sources":          {"commodities": ["copper"],
                            "country_indicators": ["CHN.industrial_production"]},
  "status": "active"
}
JSON

python -m scripts.seed_learning_plans /tmp/new_plan.json
```

Idempotent: revising an existing plan re-runs the same script with updated fields.

### 9.4 Weekly review (Craig's discipline)

```bash
cd /root/catalyst-research && source .venv/bin/activate

# Heartbeat — surfaces silent-failure jobs and budget drift
python -m scripts.show_cron_health

# Week's archetype output
python -m scripts.show_weekly_report

# Drill in to a specific plan
python -m scripts.show_learning_plan iron_ore_china_demand

# Review pending model proposals
python -m scripts.show_model_proposals
```

### 9.5 Rollback Phase 1 (Option A — preferred)

If Phase 1 completes but intl trading then misbehaves: see implementation §0.4 Option A. Reverses the additive ALTER TABLEs and drops every research table; intl trading returns to pre-Phase-1 state without restoring from snapshot.

---

## 10. Verifying the system is healthy

| Check | Command | Expected |
|---|---|---|
| Ingestion jobs running | `python -m scripts.show_cron_health` | `last_insert` within the past cadence for each job; `recent_n` > 0 for daily jobs |
| Archetype budget on track | `python -m scripts.show_cron_health` | Month-to-date total < 55 (1.5× modelled) |
| Learning plans tracked | `python -m scripts.show_learning_plan <name>` | Plan status `active`; recent commodity prices populated; tail of values appears |
| Trading unaffected | (intl-side) one full trading cycle writes `positions`, `orders`, `decisions` | All writes succeed |
| Role isolation intact | smoke queries in §5.4 | INSERTS to `positions` from research roles **fail with permission denied** |

---

## 11. Things that will change (and where they live)

| What | Where to change | When |
|---|---|---|
| Add a country (v1.5) | `sql/00X_add_country_<iso>.sql` + extend `INDICATORS` lists in Layer 1 jobs | v1.5 |
| Add a commodity | `sql/00X_add_commodity_<name>.sql` + add to `COMMODITIES` in `ingest_commodity_prices_daily.py` | v1.5 |
| Add a Layer 5 source | New ingestion module + crontab entry; `cr_financial_infra_observations` schema already accommodates | v1.5 / v2 |
| Promote a model proposal to a trained model | Manual: `cr_model_proposals.status='training'` → train offline → INSERT into `cr_models_trained` with results | v1.5 (training pipeline not in v1) |
| Demote Skeptic peer review to monthly (budget control) | Remove the Skeptic-related work from the `0 6 * * 6` cron line OR add archetype-filter logic in `archetypes.run` | When `show_cron_health.py` flags 1.5× drift |
| Add new archetype | `archetypes/<name>/system.md` + extend `ARCHETYPES` in `archetypes/run.py` + extend `cr_archetype_analyses.archetype` CHECK constraint via migration | v2 |
| Change the `claude` CLI invocation | `archetypes/run.py:invoke_claude` | Whenever Claude Code releases new flags |

---

## 12. Cross-references

- Architecture: [`../Design/catalyst-research-architecture-v1.3.md`](../Design/catalyst-research-architecture-v1.3.md)
- Buildable spec: [`../Implementation/catalyst-research-implementation-v1.3.md`](../Implementation/catalyst-research-implementation-v1.3.md)
- Repo orientation: [`../../CLAUDE.md`](../../CLAUDE.md)
- Implementation runbook: [`../../catalyst-research/CLAUDE.md`](../../catalyst-research/CLAUDE.md)
- Implementation focus (live punch list): [`../../catalyst-research/CLAUDE-FOCUS.md`](../../catalyst-research/CLAUDE-FOCUS.md)

---

*End of document.*
