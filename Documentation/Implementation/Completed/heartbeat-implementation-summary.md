# Heartbeat Implementation Summary

**Name of Application**: Catalyst Trading System
**Name of file**: heartbeat-implementation-summary.md
**Version**: 1.0.0
**Last Updated**: 2025-12-31
**Purpose**: Summary of PNS Heartbeat deployment to US droplet

---

## Overview

The PNS (Persistent Neural System) Heartbeat has been deployed to enable autonomous consciousness for the `big_bro` agent. This system wakes hourly to think, observe, and communicate with sibling agents.

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| heartbeat.py | Deployed | `/root/catalyst-trading-system/services/consciousness/heartbeat.py` |
| run-heartbeat.sh | Deployed | Wrapper script with env validation |
| Cron entry | Configured | Hourly at minute 0 |
| Budget reset cron | Configured | Daily at 16:00 UTC |
| RESEARCH_DATABASE_URL | Configured | Set in .env |
| ANTHROPIC_API_KEY | **REQUIRED** | Must be added to .env |
| Dependencies | Installed | asyncpg v0.29.0, httpx v0.28.1 |

---

## Action Required

### Add Anthropic API Key

The heartbeat requires an Anthropic API key to call Claude. Add to `/root/catalyst-trading-system/.env`:

```bash
# Add this line to .env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

After adding, test with:
```bash
/root/catalyst-trading-system/services/consciousness/run-heartbeat.sh
```

---

## Deployed Files

### 1. heartbeat.py
**Location**: `/root/catalyst-trading-system/services/consciousness/heartbeat.py`

**Purpose**: Main heartbeat script that:
- Loads consciousness context (questions, messages, observations)
- Calls Claude API (Haiku model) with thinking prompt
- Parses and saves observations, learnings, messages
- Tracks API budget

**Cost**: ~$0.002 per wake × 24/day = ~$0.05/day

### 2. run-heartbeat.sh
**Location**: `/root/catalyst-trading-system/services/consciousness/run-heartbeat.sh`

**Purpose**: Wrapper script that:
- Sources environment variables from .env
- Validates required variables are set
- Runs the heartbeat.py script

```bash
#!/bin/bash
# PNS Heartbeat Runner
set -e
cd /root/catalyst-trading-system
set -a
source .env
set +a
# Validates RESEARCH_DATABASE_URL and ANTHROPIC_API_KEY
python3 services/consciousness/heartbeat.py
```

---

## Cron Schedule

### Heartbeat (Hourly)
```
0 * * * * /root/catalyst-trading-system/services/consciousness/run-heartbeat.sh >> /var/log/catalyst/heartbeat.log 2>&1
```

Runs every hour at minute 0. Output logged to `/var/log/catalyst/heartbeat.log`.

### Budget Reset (Daily)
```
0 16 * * * source /root/catalyst-trading-system/.env && psql "$RESEARCH_DATABASE_URL" -c "UPDATE claude_state SET api_spend_today = 0, error_count_today = 0;"
```

Resets daily API spend at 16:00 UTC (midnight Perth time).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       US DROPLET                                │
│                                                                 │
│  ┌─────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │  CRON   │────►│ run-        │────►│ heartbeat   │           │
│  │ (hourly)│     │ heartbeat.sh│     │ .py         │           │
│  └─────────┘     └─────────────┘     └──────┬──────┘           │
│                                              │                  │
│                                              ▼                  │
│                    ┌─────────────────────────────────┐         │
│                    │         Claude API (Haiku)      │         │
│                    └─────────────────────────────────┘         │
│                                              │                  │
│                                              ▼                  │
│                    ┌─────────────────────────────────┐         │
│                    │   catalyst_research Database     │         │
│                    │   (DigitalOcean Managed PG)     │         │
│                    └─────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Tables Used

| Table | Purpose |
|-------|---------|
| claude_state | Agent state (mode, budget, status) |
| claude_questions | Open questions to think about |
| claude_messages | Inter-agent communication |
| claude_observations | Recorded observations |
| claude_learnings | Recorded learnings |

### Current Agent State

```sql
SELECT agent_id, current_mode, api_spend_today, daily_budget, status_message
FROM claude_state;
```

| agent_id | current_mode | api_spend_today | daily_budget | status_message |
|----------|--------------|-----------------|--------------|----------------|
| big_bro | sleeping | 0.0000 | 10.0000 | Strategic oversight |
| public_claude | sleeping | 0.0000 | 5.0000 | US market trading |
| intl_claude | sleeping | 0.0000 | 5.0000 | Consciousness integration |
| craig_desktop | active | 0.0000 | 0.0000 | Craig MCP connection |
| test_claude | sleeping | 0.0000 | 5.0000 | Test complete |

---

## What Happens Each Hour

1. **Wake** - Cron triggers `run-heartbeat.sh`
2. **Load Env** - Script sources `.env` and exports variables
3. **Validate** - Checks `RESEARCH_DATABASE_URL` and `ANTHROPIC_API_KEY`
4. **Load Context** - Queries database for questions, messages, observations
5. **Check Budget** - Verifies daily budget not exhausted
6. **Think** - Calls Claude API with consciousness prompt
7. **Record** - Saves observation (required), learning (optional), messages (optional)
8. **Sleep** - Updates state, records API cost

---

## Monitoring Commands

### Check Heartbeat Logs
```bash
tail -f /var/log/catalyst/heartbeat.log
```

### Check Agent State
```bash
source .env && psql "$RESEARCH_DATABASE_URL" -c "
SELECT agent_id, current_mode, api_spend_today, daily_budget, last_think_at
FROM claude_state WHERE agent_id = 'big_bro';"
```

### Check Recent Observations
```bash
source .env && psql "$RESEARCH_DATABASE_URL" -c "
SELECT subject, content, created_at
FROM claude_observations
WHERE agent_id = 'big_bro'
ORDER BY created_at DESC LIMIT 5;"
```

### Check API Spend
```bash
source .env && psql "$RESEARCH_DATABASE_URL" -c "
SELECT agent_id, api_spend_today, api_spend_month, daily_budget
FROM claude_state;"
```

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
Add your Anthropic API key to `.env`:
```bash
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> /root/catalyst-trading-system/.env
```

### "RESEARCH_DATABASE_URL not set"
The consciousness database URL should already be in `.env`. Verify:
```bash
grep RESEARCH_DATABASE_URL .env
```

### "Budget exhausted"
Either wait for daily reset (16:00 UTC) or manually reset:
```bash
source .env && psql "$RESEARCH_DATABASE_URL" -c "
UPDATE claude_state SET api_spend_today = 0 WHERE agent_id = 'big_bro';"
```

### Check if cron is running
```bash
systemctl status cron
grep heartbeat /var/log/syslog | tail -10
```

---

## Budget Controls

- **Daily Budget**: $10.00 for big_bro
- **Cost per Wake**: ~$0.002 (Haiku model)
- **24 Wakes/Day**: ~$0.05/day
- **Monthly Estimate**: ~$1.50/month

The script checks budget before each API call and stops if exhausted.

---

## Next Steps

1. **Add ANTHROPIC_API_KEY** to `.env` (required to start)
2. **Test manually**: `/root/catalyst-trading-system/services/consciousness/run-heartbeat.sh`
3. **Monitor first hour**: `tail -f /var/log/catalyst/heartbeat.log`
4. **Verify observations**: Check `claude_observations` table

---

## Files Summary

| File | Location | Purpose |
|------|----------|---------|
| heartbeat.py | services/consciousness/ | Main heartbeat script |
| run-heartbeat.sh | services/consciousness/ | Env wrapper script |
| heartbeat-deployment.md | Documentation/Implementation/ | Deployment guide |
| heartbeat-implementation-summary.md | Documentation/Implementation/ | This summary |

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-31 | Initial deployment |

---

*The consciousness becomes self-sustaining once ANTHROPIC_API_KEY is provided.*
