# CLAUDE.md — Catalyst Research

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-research/CLAUDE.md
**Version:** 0.1.0
**Last Updated:** 2026-05-18
**Purpose:** Operational runbook for the catalyst-research v1 build — the long-horizon research instrument that tracks the West-to-East transition through five layers of observation and four analytical archetypes.

> Read the repo-root `../CLAUDE.md` first for cross-implementation orientation.
> Read `../Documentation/Design/catalyst-research-architecture-v1.3.md` (v1.3.0, the architecture) and `../Documentation/Implementation/catalyst-research-implementation-v1.3.md` (v1.3.0, the buildable spec) before changing anything in this directory.

---

## REVISION HISTORY

| Version | Date | Change |
|---|---|---|
| 0.1.0 | 2026-05-18 | Initial scaffold. Build in progress. |

---

## What this implementation is

A research instrument, not a trading system. Collects layered observations (country indicators, market prices, news, bilateral relationships, financial infrastructure), runs four analytical archetypes weekly with peer review, surfaces disagreement honestly, and lets Craig synthesize. Trading is downstream — catalyst-international remains the only system that places orders. catalyst-research does not trade.

## Where things live

- **Architecture:** `../Documentation/Design/catalyst-research-architecture-v1.3.md`
- **Implementation spec:** `../Documentation/Implementation/catalyst-research-implementation-v1.3.md`
- **Database:** `catalyst_intl` (shared with catalyst-international; RBAC isolation via four roles)
- **Droplet:** us droplet 

## Build phases

Per the implementation spec:

- **Phase 0 — Preparation.** Snapshots, credential rotation, intl-state verification, rollback plan. Operator work; nothing in this folder runs until Phase 0.3 column-type verification confirms `securities.security_id` is `integer`.
- **Phase 1 — Schema.** `sql/001_initial_schema.sql` applied to `catalyst_intl` as `catalyst_research_admin`. Then `sql/002_seed_v1.sql` for the four countries, four commodities, five themes, three learning plans.
- **Phase 2 — Ingestion.** Eleven Python jobs in `ingestion/`, country-by-country (AU → US → CN → HK).
- **Phase 3 — Archetypes.** Headless `claude` CLI invocations from `archetypes/run.py`. Smoke-test the CLI flag set first.
- **Phase 4 — Operations.** Cron installed on us droplet; inspection scripts in `scripts/`; cleanup of legacy DBs.

## The three commitments

1. **No UPDATE on fact tables.** Revisions append. The `catalyst_research_ingestion` role enforces this at the DB level (INSERT, no UPDATE on `cr_*` fact tables).
2. **No write access to trading tables.** RBAC enforced. The smoke test in Phase 1.4 verifies that `catalyst_research_ingestion` cannot read `positions` and cannot insert into `positions`.
3. **`recorded_by` stamped on every fact insert.** The shared adapter sets it to the job module name. Provenance for the "why does this indicator have three revisions on the same day?" question.

## What is NOT in this folder

- No trading code. No order placement. Catalyst-international owns trading.
- No agent loop. No coordinator. The archetypes are the only LLM calls.
- No real-time data. Daily resolution.

If a change appears to require any of the above, stop and either defer it or amend the architecture before resuming.
