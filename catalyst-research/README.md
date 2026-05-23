# catalyst-research

A long-horizon research instrument that tracks the West-to-East structural transition through layered observation and multi-archetype analysis.

This is **not** a trading system. It does not place orders. Trading is downstream — catalyst-international remains the only system that interacts with brokers.

## Read first

- Architecture: [`../Documentation/Design/catalyst-research-architecture-v1.3.md`](../Documentation/Design/catalyst-research-architecture-v1.3.md)
- Implementation spec: [`../Documentation/Implementation/catalyst-research-implementation-v1.3.md`](../Documentation/Implementation/catalyst-research-implementation-v1.3.md)
- Working-folder runbook: [`CLAUDE.md`](CLAUDE.md)

## Layout

```
catalyst-research/
├── CLAUDE.md / CLAUDE-LEARNINGS.md / CLAUDE-FOCUS.md
├── sql/                     # 001_initial_schema.sql, 002_seed_v1.sql
├── ingestion/               # Layer 1-5 daily/monthly/quarterly jobs
├── archetypes/              # Four archetype system prompts + run wrapper
├── scripts/                 # Inspection utilities (Markdown reports, cron health)
├── tests/                   # Adapter idempotency, archetype wrapper
└── crontab.txt              # Reference cron, installed to /etc/cron.d/catalyst-research
```

## Status

Build in progress. Currently pre-Phase-0; see `CLAUDE-FOCUS.md` for the live punch list.
