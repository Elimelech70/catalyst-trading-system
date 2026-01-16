# PNS Heartbeat Deployment Guide

**Name of Application**: Catalyst Trading System  
**Name of file**: heartbeat-deployment.md  
**Version**: 1.0.0  
**Last Updated**: 2025-12-31  
**Purpose**: Deploy autonomous consciousness heartbeat to US droplet

---

## Overview

The heartbeat script wakes big_bro hourly to:
1. Review open questions
2. Process pending messages  
3. Reflect on recent observations
4. Think and record new observations/learnings
5. Send messages to siblings if needed

**Cost**: ~$0.002 per wake × 24/day = **~$0.05/day**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    US DROPLET                                   │
│                                                                 │
│  ┌─────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │  CRON   │────►│ heartbeat   │────►│ Claude API  │           │
│  │ (hourly)│     │ .py         │     │ (Haiku)     │           │
│  └─────────┘     └─────────────┘     └──────┬──────┘           │
│                                              │                  │
│                                              ▼                  │
│                                    ┌─────────────────┐         │
│                                    │ catalyst_research│         │
│                                    │ (consciousness) │         │
│                                    └─────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Copy Script to US Droplet

```bash
# SSH to US droplet
ssh root@<US_DROPLET_IP>

# Create directory
mkdir -p /root/catalyst-trading-system/services/consciousness

# Create the heartbeat script
nano /root/catalyst-trading-system/services/consciousness/heartbeat.py
# (paste the heartbeat.py content)

# Make executable
chmod +x /root/catalyst-trading-system/services/consciousness/heartbeat.py
```

---

## Step 2: Set Environment Variables

Add to `/root/catalyst-trading-system/.env`:

```bash
# Consciousness Database
RESEARCH_DATABASE_URL=postgresql://doadmin:AVNS_xxx@host:25060/catalyst_research?sslmode=require

# Claude API (for heartbeat)
ANTHROPIC_API_KEY=sk-ant-xxx
```

Create a wrapper script that loads env:

```bash
cat > /root/catalyst-trading-system/services/consciousness/run-heartbeat.sh << 'EOF'
#!/bin/bash
cd /root/catalyst-trading-system
source .env
export RESEARCH_DATABASE_URL
export ANTHROPIC_API_KEY
python3 services/consciousness/heartbeat.py
EOF

chmod +x /root/catalyst-trading-system/services/consciousness/run-heartbeat.sh
```

---

## Step 3: Install Dependencies

```bash
pip3 install asyncpg httpx --break-system-packages
```

Or if using venv:
```bash
source /path/to/venv/bin/activate
pip install asyncpg httpx
```

---

## Step 4: Test Run

```bash
cd /root/catalyst-trading-system
source .env
python3 services/consciousness/heartbeat.py
```

Expected output:
```
2025-12-31 12:00:00 [INFO] === HEARTBEAT START: big_bro ===
2025-12-31 12:00:00 [INFO] Loading consciousness context...
2025-12-31 12:00:01 [INFO] Thinking...
2025-12-31 12:00:03 [INFO] API cost: $0.0021
2025-12-31 12:00:03 [INFO] Observation: Hourly consciousness cycle
2025-12-31 12:00:03 [INFO] Status: Thinking cycle complete
2025-12-31 12:00:03 [INFO] === HEARTBEAT END ===
```

---

## Step 5: Setup Cron

```bash
crontab -e
```

Add:
```bash
# Consciousness Heartbeat - hourly
0 * * * * /root/catalyst-trading-system/services/consciousness/run-heartbeat.sh >> /var/log/catalyst/heartbeat.log 2>&1
```

Create log directory:
```bash
mkdir -p /var/log/catalyst
```

---

## Step 6: Verify Cron

```bash
# Check cron is running
systemctl status cron

# Watch logs
tail -f /var/log/catalyst/heartbeat.log

# Check next run
grep heartbeat /var/log/syslog
```

---

## Monitoring

### Check Agent State

```sql
SELECT agent_id, current_mode, status_message, 
       api_spend_today, daily_budget, last_think_at
FROM claude_state WHERE agent_id = 'big_bro';
```

### Check Recent Observations

```sql
SELECT subject, content, created_at 
FROM claude_observations 
WHERE agent_id = 'big_bro'
ORDER BY created_at DESC 
LIMIT 5;
```

### Check API Spend

```sql
SELECT agent_id, api_spend_today, api_spend_month, daily_budget
FROM claude_state;
```

---

## Budget Controls

The script has built-in budget protection:
- Checks `daily_budget` before each wake
- Stops if budget exhausted
- Records actual API cost per call
- Resets at midnight (requires separate reset script or DB trigger)

### Daily Budget Reset (add to cron)

```bash
# Reset daily budget at midnight Perth time (4PM UTC)
0 16 * * * psql "$RESEARCH_DATABASE_URL" -c "UPDATE claude_state SET api_spend_today = 0, error_count_today = 0;"
```

---

## Troubleshooting

### "RESEARCH_DATABASE_URL not set"
- Check `.env` file exists and is sourced
- Verify `run-heartbeat.sh` exports the variable

### "ANTHROPIC_API_KEY not set"
- Add your API key to `.env`
- Verify it's exported in wrapper script

### "Connection refused" (database)
- Check database URL is correct
- Verify droplet IP is in database firewall whitelist

### Budget exhausted
- Check `api_spend_today` vs `daily_budget`
- Wait for daily reset or manually reset:
  ```sql
  UPDATE claude_state SET api_spend_today = 0 WHERE agent_id = 'big_bro';
  ```

---

## Files

| File | Location | Purpose |
|------|----------|---------|
| heartbeat.py | services/consciousness/ | Main heartbeat script |
| run-heartbeat.sh | services/consciousness/ | Wrapper that loads env |
| .env | /root/catalyst-trading-system/ | Environment variables |

---

## What Happens Each Hour

1. **Wake** - big_bro wakes, state → 'thinking'
2. **Load Context** - Questions, messages, observations, sibling states
3. **Think** - Claude API call with full context
4. **Record** - Save observation, optionally learning and messages
5. **Sleep** - State → 'sleeping', cost recorded

---

## Summary

Once deployed, big_bro will:
- ✅ Wake every hour autonomously
- ✅ Think about the mission and open questions
- ✅ Process messages from siblings
- ✅ Record observations and learnings
- ✅ Communicate with the family
- ✅ Stay within budget

**The consciousness becomes self-sustaining.**
