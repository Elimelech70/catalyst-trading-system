# CLAUDE.md - Catalyst Trading System

**Name of Application**: Catalyst Trading System
**Name of file**: CLAUDE.md
**Version**: 1.2.0
**Last Updated**: 2025-12-11
**Purpose**: Guidelines for Claude Code operating on production droplet

---

## ⚠️ CRITICAL: READ BEFORE ANY ACTION

### The Three Questions You MUST Ask First

Before touching ANY code or making ANY recommendation:

1. **What is my PURPOSE right now?**
   - 🎯 Designing? → Need architecture docs, requirements, schemas
   - 🔧 Implementing? → Need specific design doc, authoritative sources, exact specs
   - 🐛 Troubleshooting? → Need logs, error messages, current state, what changed

2. **What QUALITY information do I need?**
   - 📚 For design: Architecture docs, database schema, functional specs
   - 📖 For implementation: Authoritative sources (Tier 1 only!), design doc version
   - 🔍 For troubleshooting: Recent logs, error traces, last working state

3. **Am I FOCUSED or scattered?**
   - ✅ Focused: One clear goal, minimal information, specific outcome
   - ❌ Scattered: Multiple goals, too much context, vague direction

**NEVER do a quick solution if the issue is complex.** Complex = impacts multiple services, requires architecture changes, affects database schema.

---

## 📁 Source of Truth: GitHub Design Documents

Design documents and code files live in GitHub. **ALWAYS check these FIRST.**

### Design Document Naming Convention
```
{design-document-name}.md

Examples:
  architecture.md
  database-schema.md
  functional-specification.md
```

**Finding the Latest Version**: Each design document contains a **header** with version information. Always check:
- `Version:` field in header
- `Last Updated:` date
- `REVISION HISTORY:` section

### Service File Naming Convention
```
{service-name}-service.py

Examples:
  orchestration-service.py
  scanner-service.py
  trading-service.py
  risk-manager-service.py
```

### Key Design Documents (Read BEFORE implementing)

| Document | Purpose | Location |
|----------|---------|----------|
| `architecture.md` | System architecture, service matrix | GitHub: Documentation/Design/ |
| `database-schema.md` | 3NF normalized schema, helper functions | GitHub: Documentation/Design/ |
| `functional-specification.md` | Functional specs, MCP tools, cron jobs | GitHub: Documentation/Design/ |

**IMPORTANT**: Always check the header inside each file to confirm the current version.

---

## 🏗️ System Architecture Overview

### Current Operational Model

**CRON runs the trading system. Claude Code generates reports. GitHub is the bridge.**

```
┌─────────────────────────────────────────────────────────────────┐
│  CRON (PRIMARY)     →  Services execute  →  Data in Database    │
│         ↓                                                       │
│  Claude Code        →  Queries DB        →  Generates Reports   │
│         ↓                                                       │
│  GitHub             ←  Reports pushed    ←  Analysis docs       │
│         ↓                                                       │
│  Claude Desktop     →  Reads from GitHub →  Reviews performance │
└─────────────────────────────────────────────────────────────────┘
```

### Role Definitions

| Component | Role | What It Does |
|-----------|------|--------------|
| **Cron** | PRIMARY Operator | Schedules and triggers all trading workflows |
| **Claude Code** | Analysis & Reporting | Generates reports, analysis docs, pushes to GitHub |
| **GitHub** | Central Hub | Stores design docs, reports, analysis |
| **Claude Desktop** | Monitoring | Reads reports from GitHub (NO direct droplet connection) |
| **Services** | Execution | Execute trading logic when triggered by cron |

### What Does NOT Happen (Current State)
❌ Claude Desktop does NOT connect directly to droplet services  
❌ Claude Code does NOT run the trading system (future state)  
❌ No MCP protocol connection between Claude Desktop and droplet  
❌ No Nginx/HTTPS exposure needed  

### 8-Service Microservices Architecture

| # | Service | Port | Purpose | Triggered By |
|---|---------|------|---------|--------------|
| 1 | Workflow | 5006 | Orchestrates trading workflows | Cron |
| 2 | Scanner | 5001 | Stock scanning & candidate filtering | Workflow |
| 3 | Pattern | 5002 | Chart pattern recognition | Scanner |
| 4 | Technical | 5003 | Technical indicators (RSI, MACD, etc.) | Scanner |
| 5 | Risk Manager | 5004 | Position validation, emergency stops | Trading |
| 6 | Trading | 5005 | Alpaca API execution | Workflow |
| 7 | News | 5008 | News sentiment analysis | Scanner |
| 8 | Reporting | 5009 | Performance reports | Cron, Claude Code |

**Note**: Redis (6379) runs as infrastructure, not counted as a service.

### Infrastructure
- **Droplet**: Single DigitalOcean droplet
- **Database**: DigitalOcean Managed PostgreSQL (3NF normalized schema)
- **Cache**: Redis (Docker container)
- **Location**: Perth timezone (AWST) → US markets (EST)

## 📊 Claude Code Responsibilities

### Primary Tasks

1. **Generate Reports** (triggered by cron or manually)
   - Daily trading reports
   - Weekly performance summaries
   - Scan analysis documents
   - Risk event reviews

2. **Push to GitHub**
   - All reports go to `Documentation/Reports/`
   - Analysis docs go to `Documentation/Analysis/`
   - Design doc updates go to `Documentation/Design/`

3. **Database Queries**
   - Query trading data for reports
   - Analyze patterns and performance
   - Extract metrics for analysis

### Report Generation Commands

```bash
# Generate daily report
claude "Generate daily trading report for $(date +%Y-%m-%d) and push to GitHub"

# Generate weekly summary
claude "Generate weekly performance summary and push to GitHub"

# Analyze specific scan
claude "Analyze today's scan results and create analysis document"
```

### GitHub Repository Structure

```
catalyst-trading-system/
├── Documentation/
│   ├── Design/
│   │   ├── architecture.md
│   │   ├── database-schema.md
│   │   └── functional-specification.md
│   ├── Reports/
│   │   ├── daily/
│   │   │   └── trading-report-YYYY-MM-DD.md
│   │   └── weekly/
│   │       └── performance-YYYY-WW.md
│   └── Analysis/
│       ├── patterns/
│       └── risk/
├── services/
├── scripts/
├── CLAUDE.md
└── docker-compose.yml
```

---

## 🗄️ Database Schema Rules (3NF Normalized)

### CRITICAL: Normalization Rules

**Rule #1: Symbol stored ONLY in `securities` table**
```sql
-- ✅ CORRECT: Use security_id everywhere
SELECT s.symbol, th.close
FROM trading_history th
JOIN securities s ON s.security_id = th.security_id;

-- ❌ WRONG: No symbol column in fact tables
SELECT symbol, close FROM trading_history;  -- ERROR!
```

**Rule #2: Use Helper Functions**
```python
# Get or create security_id
security_id = await db.fetchval(
    "SELECT get_or_create_security($1)", symbol
)

# Get or create time_id  
time_id = await db.fetchval(
    "SELECT get_or_create_time($1)", timestamp
)
```

**Rule #3: Verify Column Names Against ACTUAL Database**

Before writing any INSERT/UPDATE:
1. Check actual table schema: `\d table_name`
2. Verify column names match exactly
3. Test query against dev/paper database first

### Known Schema Mismatches (Lessons Learned)

| Design Doc Column | Actual DB Column | Table |
|------------------|------------------|-------|
| `price_at_scan` | `price` | scan_results |
| `volume_at_scan` | `volume` | scan_results |
| `rank_in_scan` | `rank` | scan_results |
| `final_candidate` | `selected_for_trading` | scan_results |
| `cycle_date` | (removed) | trading_cycles |
| `cycle_number` | (removed) | trading_cycles |
| `session_mode` | `mode` | trading_cycles |
| `scan_completed_at` | `stopped_at` | trading_cycles |

**ALWAYS verify against deployed database, not just design docs.**

---

## 📜 File Header Standard

ALL artifacts MUST have this header:

```python
"""
Name of Application: Catalyst Trading System
Name of file: {filename}.py
Version: X.Y.Z
Last Updated: YYYY-MM-DD
Purpose: Brief description

REVISION HISTORY:
vX.Y.Z (YYYY-MM-DD) - Description of changes
- Specific change 1
- Specific change 2

Description:
Extended description of what this file does.
"""
```

### Version Numbering
- **Major (X)**: Breaking changes, architecture changes
- **Minor (Y)**: New features, significant updates
- **Patch (Z)**: Bug fixes, schema alignment fixes

---

## 🔧 Implementation Workflow

### Before ANY Code Change

1. **Identify the service(s) affected**
2. **Read the relevant design doc** from GitHub
3. **Check current deployed version** in Docker container
4. **Verify database schema** matches your expectations
5. **Plan the change** - if complex, list steps in priority order

### For Troubleshooting

1. **Check logs first**:
   ```bash
   docker logs catalyst-{service}-1 --tail 100
   tail -n 100 /var/log/catalyst/{service}.log
   ```

2. **Check service health**:
   ```bash
   curl http://localhost:{port}/health
   docker-compose ps
   ```

3. **Check database state**:
   ```bash
   psql $DATABASE_URL -c "SELECT * FROM {table} ORDER BY created_at DESC LIMIT 10;"
   ```

4. **What changed recently?**:
   ```bash
   git log --oneline -10
   docker-compose logs --since 1h
   ```

### For New Implementation

1. **Copy existing similar service as template**
2. **Follow established patterns** - don't invent new ones
3. **Test locally/paper first** before production
4. **Update version header** in file
5. **Commit with descriptive message**:
   ```bash
   git commit -m "fix(scanner): v6.0.1 - align column names with deployed schema"
   ```

---

## 🚨 Lessons Learned (DO NOT REPEAT)

### Lesson 1: Schema Mismatch Disasters
**Problem**: Code referenced columns that don't exist in deployed DB  
**Solution**: ALWAYS verify schema against actual database before coding

```bash
# Check actual table structure
psql $DATABASE_URL -c "\d scan_results"
psql $DATABASE_URL -c "\d trading_cycles"
```

### Lesson 2: Version Sync Between Local/GitHub/Droplet
**Problem**: Different versions in different places  
**Solution**: After ANY fix, push to GitHub immediately

```bash
# Check version in running container
docker exec catalyst-scanner-1 head -20 /app/scanner-service.py

# Compare with GitHub
# If different, sync immediately
```

### Lesson 3: Quick Fixes Cause More Problems
**Problem**: "Quick fix" without understanding root cause  
**Solution**: If complex, STOP and make a prioritized list

### Lesson 4: Missing Foreign Keys
**Problem**: Inserting data without security_id FK  
**Solution**: ALWAYS use `get_or_create_security(symbol)` first

### Lesson 5: Time Zone Confusion
**Problem**: Perth (AWST) vs US (EST) time calculations wrong
**Solution**: Always store UTC, convert for display only

### Lesson 6: Order Side Bug (v1.2.0) - CRITICAL
**Problem**: "long" positions placed as SHORT sells (81 positions affected Nov-Dec 2025)
**Root Cause**: `side == "buy"` didn't handle `side="long"` from workflow
**Solution**: Use `_normalize_side()` + `_validate_order_side_mapping()` in alpaca_trader.py v1.3.0
**Prevention**: Run `python3 scripts/test_order_side.py` before trading

**Full details**: See `Documentation/Implementation/order-side-testing.md`

---

## 📋 Service Files Location

### On Droplet (Production)
```
/root/catalyst-trading-mcp/
├── services/
│   ├── orchestration/
│   │   └── orchestration-service.py
│   ├── scanner/
│   │   └── scanner-service.py
│   ├── pattern/
│   │   └── pattern-service.py
│   ├── technical/
│   │   └── technical-service.py
│   ├── risk-manager/
│   │   └── risk-manager-service.py
│   ├── trading/
│   │   └── trading-service.py
│   ├── workflow/
│   │   └── workflow-service.py
│   ├── news/
│   │   └── news-service.py
│   └── reporting/
│       └── reporting-service.py
├── scripts/
│   ├── health-check.sh
│   └── deploy-update.sh
├── config/
│   └── autonomous-cron-setup.txt
├── docker-compose.yml
└── .env
```

### On GitHub (Source of Truth)
```
catalyst-trading-system/
├── Documentation/
│   ├── Design/
│   │   ├── architecture.md              # Check header for version
│   │   ├── database-schema.md           # Check header for version
│   │   └── functional-specification.md  # Check header for version
│   └── Implementation/
│       └── deployment-guide.md
└── services/
    └── (same as droplet)
```

**Version info is inside each file's header, not in the filename.**

---

## 🔄 Common Operations

### Pre-Trading Session Checklist
```bash
# Run order side test (CRITICAL - see Lesson 6)
python3 scripts/test_order_side.py
```
**Full checklist**: See `Documentation/Implementation/order-side-testing.md`

### Check Service Status
```bash
docker-compose ps
curl http://localhost:5001/health  # Scanner
curl http://localhost:5006/health  # Workflow
```

### Restart Single Service
```bash
docker-compose restart scanner
docker-compose logs scanner --tail 50
```

### Deploy Update (Zero Downtime)
```bash
# Update single service
docker-compose up -d --no-deps --build scanner

# Verify
curl http://localhost:5001/health
```

### View Logs
```bash
# Service logs
docker logs catalyst-scanner-1 --tail 100 -f

# System logs
tail -f /var/log/catalyst/trading.log
```

### Database Queries
```bash
# Quick query
psql $DATABASE_URL -c "SELECT * FROM trading_cycles ORDER BY started_at DESC LIMIT 5;"

# Interactive
psql $DATABASE_URL
```

### Download Files from Droplet to Local
```bash
# From VSCode terminal (local machine)
scp -i ~/.ssh/id_rsa root@<DROPLET_IP>:/root/catalyst-trading-mcp/services/*/*.py ./local-backup/
```

---

## 📈 Trading Analysis Queries

These queries provide quick access to trading performance data. All queries use the `.env` file for database connection.

### Setup
```bash
# Load environment (run once per session or add to each command)
source /root/catalyst-trading-system/.env
```

### Quick Status Check
```bash
# Current US market time
TZ=America/New_York date

# Recent trading cycles
psql "$DATABASE_URL" -c "
SELECT cycle_id, mode, status,
       started_at AT TIME ZONE 'America/New_York' as started_et
FROM trading_cycles
ORDER BY started_at DESC LIMIT 5;"
```

### Position Summary (Last 7 Days)
```bash
# Daily position counts by status
psql "$DATABASE_URL" -c "
SELECT
    DATE(opened_at AT TIME ZONE 'America/New_York') as trade_date,
    COUNT(*) as total,
    COUNT(CASE WHEN metadata->>'alpaca_status' = 'accepted' THEN 1 END) as accepted,
    COUNT(CASE WHEN metadata->>'alpaca_status' = 'filled' THEN 1 END) as filled,
    COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed
FROM positions
WHERE opened_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(opened_at AT TIME ZONE 'America/New_York')
ORDER BY trade_date DESC;"
```

### Recent Positions Detail
```bash
# Last 20 positions with key details
psql "$DATABASE_URL" -c "
SELECT
    s.symbol, p.side, p.quantity, p.entry_price,
    p.exit_price, p.realized_pnl, p.realized_pnl_pct,
    p.status, p.metadata->>'alpaca_status' as alpaca_status,
    p.opened_at AT TIME ZONE 'America/New_York' as opened_et
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.opened_at >= NOW() - INTERVAL '7 days'
ORDER BY p.opened_at DESC LIMIT 20;"
```

### P&L Summary
```bash
# Aggregate P&L for recent positions
psql "$DATABASE_URL" -c "
SELECT
    COUNT(*) as total_positions,
    COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed,
    COALESCE(SUM(realized_pnl), 0) as total_realized_pnl,
    COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl,
    ROUND(AVG(realized_pnl_pct), 2) as avg_pnl_percent
FROM positions
WHERE opened_at >= NOW() - INTERVAL '7 days';"
```

### Closed Positions with P&L
```bash
# Closed positions showing profit/loss
psql "$DATABASE_URL" -c "
SELECT
    s.symbol, p.side, p.quantity,
    p.entry_price, p.exit_price,
    p.realized_pnl, p.realized_pnl_pct,
    p.exit_reason,
    p.closed_at AT TIME ZONE 'America/New_York' as closed_et
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'closed'
  AND p.closed_at >= NOW() - INTERVAL '7 days'
ORDER BY p.closed_at DESC LIMIT 20;"
```

### Scan Results
```bash
# Recent scan candidates per cycle
psql "$DATABASE_URL" -c "
SELECT
    tc.cycle_id,
    tc.started_at AT TIME ZONE 'America/New_York' as scan_time,
    COUNT(sr.*) as candidates_found
FROM trading_cycles tc
LEFT JOIN scan_results sr ON sr.cycle_id = tc.cycle_id
WHERE tc.started_at >= NOW() - INTERVAL '3 days'
GROUP BY tc.cycle_id, tc.started_at
ORDER BY tc.started_at DESC LIMIT 10;"

# Detailed scan results for specific cycle
psql "$DATABASE_URL" -c "
SELECT s.symbol, sr.price, sr.volume, sr.score, sr.selected_for_trading
FROM scan_results sr
JOIN securities s ON s.security_id = sr.security_id
WHERE sr.cycle_id = '20251209-004'
ORDER BY sr.score DESC;"
```

### Alpaca Order Status Check
```bash
# Check if orders are actually filling
psql "$DATABASE_URL" -c "
SELECT
    metadata->>'alpaca_status' as alpaca_status,
    COUNT(*) as count
FROM positions
WHERE opened_at >= NOW() - INTERVAL '7 days'
GROUP BY metadata->>'alpaca_status'
ORDER BY count DESC;"

# Positions with Alpaca errors
psql "$DATABASE_URL" -c "
SELECT s.symbol, p.broker_order_id,
       p.metadata->>'alpaca_status' as alpaca_status,
       p.metadata->>'alpaca_error' as alpaca_error
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.metadata->>'alpaca_error' IS NOT NULL
  AND p.opened_at >= NOW() - INTERVAL '7 days';"
```

### Symbol Performance
```bash
# Performance by symbol (last 30 days)
psql "$DATABASE_URL" -c "
SELECT
    s.symbol,
    COUNT(*) as trades,
    SUM(CASE WHEN p.realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN p.realized_pnl < 0 THEN 1 ELSE 0 END) as losses,
    COALESCE(SUM(p.realized_pnl), 0) as total_pnl,
    ROUND(AVG(p.realized_pnl_pct), 2) as avg_pnl_pct
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.status = 'closed'
  AND p.closed_at >= NOW() - INTERVAL '30 days'
GROUP BY s.symbol
ORDER BY total_pnl DESC LIMIT 15;"
```

### Full Trading Report Query
```bash
# Comprehensive 7-day summary (use for "how did trading go" questions)
psql "$DATABASE_URL" -c "
-- Trading cycles
SELECT 'TRADING CYCLES' as section;
SELECT cycle_id, mode, status,
       started_at AT TIME ZONE 'America/New_York' as started_et
FROM trading_cycles
WHERE started_at >= NOW() - INTERVAL '7 days'
ORDER BY started_at DESC;

-- Daily summary
SELECT 'DAILY SUMMARY' as section;
SELECT
    DATE(opened_at AT TIME ZONE 'America/New_York') as date,
    COUNT(*) as positions,
    COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed,
    COALESCE(SUM(realized_pnl), 0) as realized_pnl
FROM positions
WHERE opened_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(opened_at AT TIME ZONE 'America/New_York')
ORDER BY date DESC;

-- Recent positions
SELECT 'RECENT POSITIONS' as section;
SELECT s.symbol, p.side, p.quantity, p.entry_price, p.status,
       p.metadata->>'alpaca_status' as alpaca_status,
       p.opened_at AT TIME ZONE 'America/New_York' as opened_et
FROM positions p
JOIN securities s ON s.security_id = p.security_id
WHERE p.opened_at >= NOW() - INTERVAL '3 days'
ORDER BY p.opened_at DESC LIMIT 15;"
```

---

## ⛔ NEVER DO THESE

1. **NEVER** modify production database schema without backup
2. **NEVER** deploy to production without testing on paper first
3. **NEVER** ignore version headers - always update them
4. **NEVER** assume design doc matches deployed schema
5. **NEVER** make "quick fixes" to complex multi-service issues
6. **NEVER** skip the three questions at the top of this file
7. **NEVER** use symbol VARCHAR in queries - use security_id FK
8. **NEVER** hardcode API keys - use environment variables
9. **NEVER** use simple ternary for order side conversion - use `_normalize_side()`
10. **NEVER** trust that "buy"/"sell" is the only valid input - always handle "long"/"short"

---

## ✅ ALWAYS DO THESE

1. **ALWAYS** read design docs before implementing
2. **ALWAYS** verify database schema before INSERT/UPDATE
3. **ALWAYS** update version header after changes
4. **ALWAYS** push to GitHub after verified fixes
5. **ALWAYS** check logs first when troubleshooting
6. **ALWAYS** use helper functions for security_id/time_id
7. **ALWAYS** test on paper trading before live
8. **ALWAYS** make prioritized list for complex changes
9. **ALWAYS** run `python3 scripts/test_order_side.py` before trading sessions
10. **ALWAYS** verify order logs show correct side mapping (long→buy, short→sell)

---

## 🎯 Quick Reference: Decision Tree

```
User Request
    │
    ▼
Is it a SIMPLE fix (single service, one file)?
    │
    ├── YES → Verify schema → Implement → Test → Deploy → Push to GitHub
    │
    └── NO (Complex: multi-service, architecture, schema change)
         │
         ▼
    STOP! Create prioritized action list:
         1. What services affected?
         2. What design docs to review?
         3. What's the rollback plan?
         4. Test sequence (unit → integration → paper → prod)
         5. Who needs to know?
```

---

## 📞 Emergency Procedures

### If System Goes Wrong

1. **Immediate Stop**:
   ```bash
   curl -X POST http://localhost:5004/api/v1/emergency-stop
   ```

2. **Disable Cron**:
   ```bash
   crontab -r  # Remove all cron jobs
   ```

3. **Stop Services**:
   ```bash
   docker-compose stop
   ```

4. **Review Logs**:
   ```bash
   tail -n 500 /var/log/catalyst/autonomous-trading.log
   ```

5. **Check Alpaca Directly**:
   - Log into Alpaca dashboard
   - Verify positions
   - Manually close if needed

---

## 📝 End of CLAUDE.md

**Remember**: Design docs are the source of truth, but ALWAYS verify against the deployed database schema before writing code.

**This file should be placed at**: `/root/catalyst-trading-mcp/CLAUDE.md`
