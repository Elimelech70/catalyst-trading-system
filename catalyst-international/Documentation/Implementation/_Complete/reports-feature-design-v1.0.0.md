# Dashboard Reports Feature Design

**Name of Application:** Catalyst Trading System  
**Name of file:** reports-feature-design-v1.0.0.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-31  
**Purpose:** Add Reports section to consciousness dashboard

---

## REVISION HISTORY

- **v1.0.0 (2025-12-31)** - Initial design
  - Database table design
  - Dashboard UI updates
  - MCP tool addition
  - Agent integration pattern

---

## 1. Overview

Add a Reports section to the web dashboard so Craig can review trading reports from all agents in one place.

### Current State
- Reports generated as markdown files in `Documentation/Reports/`
- Scattered across repos (US and INTL)
- No central viewing interface
- Dashboard has: Agents, Messages, Observations, Questions, Approvals

### Target State
- Reports stored in consciousness database
- Viewable from dashboard (mobile-friendly)
- Queryable via MCP tools
- Both US and HKEX reports in one place

---

## 2. Database Schema

### 2.1 New Table: `claude_reports`

```sql
-- ============================================================================
-- CLAUDE REPORTS TABLE
-- Add to catalyst_research database
-- ============================================================================

CREATE TABLE claude_reports (
    id SERIAL PRIMARY KEY,
    
    -- Source
    agent_id VARCHAR(50) NOT NULL,
    market VARCHAR(10) NOT NULL,           -- 'US', 'HKEX', 'global'
    
    -- Report Identity
    report_type VARCHAR(50) NOT NULL,      -- 'daily', 'weekly', 'alert', 'analysis'
    report_date DATE NOT NULL,
    title VARCHAR(200) NOT NULL,
    
    -- Content
    summary TEXT,                          -- Short summary for list view
    content TEXT NOT NULL,                 -- Full markdown content
    
    -- Metrics (structured for querying)
    metrics JSONB,
    -- Example metrics:
    -- {
    --   "total_pnl": 6678.00,
    --   "positions_open": 3,
    --   "positions_closed": 0,
    --   "win_rate": 0.67,
    --   "total_trades": 5,
    --   "account_value": 1005890.27
    -- }
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent duplicates
    UNIQUE(agent_id, report_type, report_date, market)
);

-- Indexes for common queries
CREATE INDEX idx_reports_date ON claude_reports(report_date DESC);
CREATE INDEX idx_reports_agent ON claude_reports(agent_id);
CREATE INDEX idx_reports_type ON claude_reports(report_type);
CREATE INDEX idx_reports_market ON claude_reports(market);

COMMENT ON TABLE claude_reports IS 'Trading reports from all Claude agents';
COMMENT ON COLUMN claude_reports.metrics IS 'Structured metrics for dashboard cards';
```

### 2.2 Migration Script

```sql
-- Run on catalyst_research database
-- Migration: Add claude_reports table

BEGIN;

CREATE TABLE IF NOT EXISTS claude_reports (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    market VARCHAR(10) NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    report_date DATE NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, report_type, report_date, market)
);

CREATE INDEX IF NOT EXISTS idx_reports_date ON claude_reports(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_reports_agent ON claude_reports(agent_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON claude_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_market ON claude_reports(market);

COMMIT;

-- Verify
SELECT 'claude_reports table created' as status;
```

---

## 3. Dashboard Updates

### 3.1 New Endpoints

Add to `web_dashboard.py`:

```
GET  /reports              → List reports (paginated, filterable)
GET  /reports/{id}         → View single report (full content)
```

### 3.2 Reports List Page (`/reports`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  🧠 Catalyst Consciousness                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  📊 REPORTS                                                         │
│                                                                     │
│  [All] [Daily] [Weekly] [US] [HKEX]         ← Filter tabs          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 📈 HKEX Daily Report - 2025-12-30                           │   │
│  │ intl_claude · +HKD 6,678 · 3 positions                      │   │
│  │ [View]                                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 📈 US Daily Report - 2025-12-30                             │   │
│  │ public_claude · +$0.00 · 0 positions                        │   │
│  │ [View]                                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 📊 Weekly Strategy Review - 2025-12-29                      │   │
│  │ big_bro · System performance analysis                       │   │
│  │ [View]                                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  [← Prev] Page 1 of 5 [Next →]                                     │
│                                                                     │
│  ────────────────────────────────────────────────────────────────  │
│  [Agents] [Messages] [Observations] [Questions] [Reports]          │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 Single Report View (`/reports/{id}`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  🧠 Catalyst Consciousness                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ← Back to Reports                                                  │
│                                                                     │
│  📈 HKEX Daily Report - 2025-12-30                                 │
│  Generated by intl_claude at 21:37 HKT                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ METRICS                                                      │   │
│  │ Total P&L: +HKD 6,678    Positions: 3 open                  │   │
│  │ Account: HKD 1,005,890   Win Rate: 67%                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ## Portfolio Summary                                               │
│  | Metric | Value |                                                 │
│  |--------|-------|                                                 │
│  | Total Assets | HKD 1,005,890.27 |                               │
│  | Cash | HKD 468,624.27 |                                         │
│  ...                                                                │
│                                                                     │
│  ## Open Positions (3)                                              │
│  | Symbol | Qty | P&L |                                            │
│  |--------|-----|-----|                                            │
│  | 981 | 2,500 | +4,875 |                                          │
│  ...                                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. MCP Tool Addition

Add to `consciousness_mcp.py`:

```python
@mcp.tool()
async def get_reports(
    limit: int = 10,
    market: str = None,      # 'US', 'HKEX', or None for all
    report_type: str = None  # 'daily', 'weekly', etc.
) -> dict:
    """Get trading reports from all agents."""
    
@mcp.tool()
async def add_report(
    report_type: str,        # 'daily', 'weekly', 'alert', 'analysis'
    market: str,             # 'US', 'HKEX', 'global'
    title: str,
    content: str,
    summary: str = None,
    metrics: dict = None,
    report_date: str = None  # ISO date, defaults to today
) -> dict:
    """Store a trading report."""
```

---

## 5. Agent Integration

### 5.1 How Agents Store Reports

When an agent generates a daily report, instead of writing to a file:

```python
# OLD: Write to file
with open(f"Documentation/Reports/DAILY_REPORT_{date}.md", "w") as f:
    f.write(report_content)

# NEW: Store in consciousness
await consciousness.add_report(
    report_type="daily",
    market="HKEX",
    title=f"HKEX Daily Report - {date}",
    summary=f"+HKD {pnl:,.2f} · {positions} positions",
    content=report_content,
    metrics={
        "total_pnl": pnl,
        "positions_open": positions,
        "account_value": account_value,
        "win_rate": win_rate
    }
)
```

### 5.2 Report Types

| Type | Generated By | Frequency |
|------|--------------|-----------|
| `daily` | intl_claude, public_claude | End of each trading day |
| `weekly` | big_bro | Sunday evening |
| `alert` | Any agent | On significant events |
| `analysis` | big_bro | Ad-hoc market analysis |

---

## 6. Implementation Priority

### Phase 1: Database + Dashboard (Today)
1. ✅ Design document (this file)
2. Run migration on catalyst_research
3. Update web_dashboard.py with /reports endpoints
4. Test with manual INSERT

### Phase 2: MCP Tools (Next)
4. Add get_reports and add_report to MCP server
5. Test from Claude Desktop

### Phase 3: Agent Integration (Later)
6. Update intl_claude to store reports
7. Update public_claude to store reports
8. Update big_bro for weekly reports

---

## 7. Files to Modify

| File | Changes |
|------|---------|
| `schema-catalyst-research.sql` | Add claude_reports table |
| `web_dashboard.py` | Add /reports and /reports/{id} endpoints |
| `consciousness_mcp.py` | Add get_reports, add_report tools |
| `generate_daily_report.py` | Store to DB instead of file |

---

## 8. Testing Checklist

- [ ] Table created successfully
- [ ] Can INSERT sample report
- [ ] Dashboard shows reports list
- [ ] Can view individual report
- [ ] Filters work (market, type)
- [ ] MCP tools work from Claude Desktop
- [ ] intl_claude can store reports
- [ ] Mobile view is readable

---

## Appendix: Sample Data

```sql
-- Test insert for development
INSERT INTO claude_reports (agent_id, market, report_type, report_date, title, summary, content, metrics)
VALUES (
    'intl_claude',
    'HKEX',
    'daily',
    '2025-12-30',
    'HKEX Daily Report - 2025-12-30',
    '+HKD 6,678 · 3 positions open',
    '# Daily Trading Report - 2025-12-30

**Generated:** 21:37:00 HKT
**System:** Catalyst International (HKEX)

## Portfolio Summary
| Metric | Value |
|--------|-------|
| Total Assets | HKD 1,005,890.27 |
| Unrealized P&L | +HKD 6,678 |

## Open Positions (3)
| Symbol | P&L |
|--------|-----|
| 981 | +4,875 |
| 1810 | +2,208 |
| 2382 | -405 |
',
    '{
        "total_pnl": 6678.00,
        "positions_open": 3,
        "account_value": 1005890.27,
        "cash": 468624.27,
        "win_rate": 0.67
    }'::jsonb
);
```
