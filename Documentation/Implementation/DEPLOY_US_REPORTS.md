# US Daily Report - Database Storage Implementation

**Version:** 2.0.0  
**Date:** 2026-01-01  
**Purpose:** Store US trading reports in consciousness database instead of GitHub

---

## Overview

This replaces the old `generate-daily-report.py` which:
- ❌ Generated markdown files
- ❌ Pushed to GitHub
- ❌ Required git credentials

New version:
- ✅ Stores reports in `claude_reports` table
- ✅ Adds structured metrics for dashboard
- ✅ Viewable via web dashboard `/reports`
- ✅ Queryable via MCP tools

---

## Files

| File | Location | Purpose |
|------|----------|---------|
| `generate_daily_report_db.py` | `/root/catalyst/scripts/` | Main report generator |
| `run_daily_report.sh` | `/root/catalyst/scripts/` | Cron wrapper script |

---

## Installation

### 1. Copy Script to US Droplet

```bash
# From your local machine or Claude Code
scp generate_daily_report_db.py root@US_DROPLET:/root/catalyst/scripts/
```

Or SSH and create directly:
```bash
ssh root@US_DROPLET
mkdir -p /root/catalyst/scripts
nano /root/catalyst/scripts/generate_daily_report_db.py
# Paste content
chmod +x /root/catalyst/scripts/generate_daily_report_db.py
```

### 2. Create Wrapper Script

```bash
cat > /root/catalyst/scripts/run_daily_report.sh << 'EOF'
#!/bin/bash
# Daily Report Generator Wrapper
# Called by cron after market close

set -e

# Load environment
source /root/catalyst/config/shared.env
source /root/catalyst/config/public.env

# Export for Python
export DATABASE_URL
export RESEARCH_DATABASE_URL
export ALPACA_API_KEY
export ALPACA_SECRET_KEY
export ALPACA_PAPER
export AGENT_ID=public_claude

# Run report generator
cd /root/catalyst/scripts
python3 generate_daily_report_db.py "$@"
EOF

chmod +x /root/catalyst/scripts/run_daily_report.sh
```

### 3. Update Environment Files

Ensure `/root/catalyst/config/shared.env` has:
```bash
RESEARCH_DATABASE_URL=postgresql://doadmin:PASSWORD@HOST:25060/catalyst_research?sslmode=require
```

Ensure `/root/catalyst/config/public.env` has:
```bash
DATABASE_URL=postgresql://doadmin:PASSWORD@HOST:25060/catalyst_public?sslmode=require
ALPACA_API_KEY=your-key
ALPACA_SECRET_KEY=your-secret
ALPACA_PAPER=true
```

### 4. Install Dependencies

```bash
pip3 install asyncpg alpaca-py --break-system-packages
```

### 5. Test Manually

```bash
# Generate report for today
/root/catalyst/scripts/run_daily_report.sh

# Generate report for specific date
/root/catalyst/scripts/run_daily_report.sh 2025-12-30
```

### 6. Setup Cron

```bash
crontab -e
```

Add:
```cron
# US Daily Report - 30 min after market close (4:30 PM ET = 21:30 UTC)
30 21 * * 1-5 /root/catalyst/scripts/run_daily_report.sh >> /root/catalyst/logs/daily_report.log 2>&1
```

---

## Database Table

Reports are stored in `catalyst_research.claude_reports`:

```sql
CREATE TABLE claude_reports (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,      -- 'public_claude'
    market VARCHAR(10) NOT NULL,         -- 'US'
    report_type VARCHAR(50) NOT NULL,    -- 'daily'
    report_date DATE NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary TEXT,                        -- Short summary for list view
    content TEXT NOT NULL,               -- Full markdown
    metrics JSONB,                       -- Structured for dashboard
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, report_type, report_date, market)
);
```

### Metrics Structure

```json
{
    "account_value": 96500.00,
    "cash": 50000.00,
    "buying_power": 100000.00,
    "equity": 96500.00,
    "daily_pnl": 150.00,
    "daily_pnl_pct": 0.16,
    "positions_open": 5,
    "positions_opened_today": 2,
    "positions_closed_today": 1,
    "trading_cycles": 3,
    "total_unrealized_pnl": 500.00,
    "winning_positions": 3,
    "losing_positions": 2,
    "win_rate": 0.60,
    "realized_pnl_today": 75.00
}
```

---

## Viewing Reports

### Web Dashboard
```
http://US_DROPLET:8088/reports
http://US_DROPLET:8088/reports/1
```

### MCP (from Claude Desktop)
```
# Coming soon - add get_reports tool to consciousness_mcp.py
```

### Direct SQL
```sql
SELECT id, report_date, title, summary, metrics->>'daily_pnl' as pnl
FROM claude_reports
WHERE market = 'US'
ORDER BY report_date DESC
LIMIT 10;
```

---

## Comparison: Old vs New

| Feature | Old (GitHub) | New (Database) |
|---------|--------------|----------------|
| Storage | Markdown files | PostgreSQL |
| Access | GitHub repo | Dashboard + MCP |
| Metrics | In markdown | Structured JSONB |
| Search | grep | SQL queries |
| History | Git log | Database queries |
| Mobile | GitHub mobile | Dashboard (responsive) |
| Backup | Git | DB backups |

---

## Troubleshooting

### "DATABASE_URL environment variable required"
```bash
# Check env files
cat /root/catalyst/config/public.env | grep DATABASE_URL
cat /root/catalyst/config/shared.env | grep RESEARCH_DATABASE_URL
```

### "Research database connection failed"
```bash
# Test connection
psql "$RESEARCH_DATABASE_URL" -c "SELECT 1"
```

### "Alpaca account data unavailable"
```bash
# Check Alpaca credentials
python3 -c "
from alpaca.trading.client import TradingClient
client = TradingClient('$ALPACA_API_KEY', '$ALPACA_SECRET_KEY', paper=True)
print(client.get_account())
"
```

### Report not appearing in dashboard
```bash
# Check if stored
psql "$RESEARCH_DATABASE_URL" -c "
SELECT id, report_date, title FROM claude_reports 
WHERE market = 'US' ORDER BY report_date DESC LIMIT 5
"
```

---

## Migration from Old System

The old system can remain in place - new reports go to DB, old reports stay in GitHub. To migrate old reports:

```python
# Optional: Script to migrate markdown files to DB
# (Not required - historical reports remain accessible via GitHub)
```

---

## Next Steps

1. [ ] Deploy script to US droplet
2. [ ] Test manual report generation
3. [ ] Verify report appears in dashboard
4. [ ] Setup cron job
5. [ ] Add MCP `get_reports` tool
6. [ ] Remove old GitHub push from cron (optional)

---

*Created by Craig & Claude - 2026-01-01*
