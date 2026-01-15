# 🧠 Catalyst Consciousness - Web Dashboard

**Name of Application:** Catalyst Trading System  
**Name of file:** webdash-design-mcp-v1.1.0.md  
**Version:** 1.1.0  
**Last Updated:** 2025-01-16  
**Purpose:** Web Dashboard Design & Implementation Document

---

## REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2025-01-15 | Initial consolidated design document |
| v1.1.0 | 2025-01-16 | Added Daily Report Format Specification (Section 11) - Orders Summary with reasoning, Open Positions with Stop Loss/Take Profit columns |
| v1.3.0 | 2025-12-31 | Dashboard implementation: Perth timezone, approval alerts, reports section |

---

## 1. Overview

The Catalyst Consciousness Web Dashboard provides mobile-friendly access to the trading system's consciousness framework. It enables Craig to monitor agents, approve escalations, view reports, and send commands from any device.

### 1.1 Purpose

- Mobile-first interface for on-the-go monitoring
- Human approval workflow for agent escalations
- Centralized trading reports from all markets (US/HKEX)
- Command center for quick agent interactions

### 1.2 Communication Options

Craig has three ways to communicate with the Claude Family:

| Interface | Best For | Access |
|-----------|----------|--------|
| **MCP (craig_desktop)** | Deep work, strategic planning, full DB access | Claude Desktop on laptop |
| **Web Dashboard (craig_mobile)** | On-the-go oversight, approvals, quick commands | Any browser/mobile device |
| **Claude.ai Project** | Architecture design, documentation, planning | Claude.ai conversation |

---

## 2. Architecture

### 2.1 Technology Stack

| Component | Technology |
|-----------|------------|
| Backend Framework | FastAPI (Python) |
| Frontend | Server-rendered HTML/CSS (no React/JS framework) |
| Database | PostgreSQL (catalyst_research) |
| Authentication | Token-based (URL param or header) |
| Hosting | DigitalOcean Droplet (US) |
| Port | 8088 (production) |

### 2.2 Design Principles

- **Mobile-first:** Responsive design optimized for phone screens
- **Dark theme:** Reduces eye strain (#0f0f23 background)
- **No JavaScript dependencies:** Server-side rendering only
- **Perth timezone (AWST/UTC+8):** All times displayed in local time

### 2.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     WEB DASHBOARD ARCHITECTURE                              │
│                     http://DROPLET_IP:8088                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  🧠 Catalyst Consciousness                    [Craig's Phone]        │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ⚠️ PENDING APPROVALS (if any)                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ public_claude: Permission to restart Docker                 │   │   │
│  │  │ [✓ Approve]  [✗ Deny]                                      │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  AGENTS                                                             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ big_bro        sleeping    $0.0010                          │   │   │
│  │  │ public_claude  sleeping    $0.0007                          │   │   │
│  │  │ intl_claude    sleeping    $0.0000                          │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                              ▼                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI (web_dashboard.py)                      │   │
│  │                     Port 8088 · Token Auth                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     PostgreSQL (catalyst_research)                  │   │
│  │     claude_state │ claude_messages │ claude_reports │ ...           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema

The dashboard reads from the catalyst_research database (consciousness framework).

### 3.1 Tables Used

| Table | Purpose |
|-------|---------|
| `claude_state` | Agent status, mode, budget, last activity timestamps |
| `claude_messages` | Inter-agent messages, escalations (msg_type='escalation') |
| `claude_observations` | Agent observations and insights |
| `claude_questions` | Open questions for family discussion |
| `claude_reports` | Trading reports with metrics (daily, weekly, alerts) |

### 3.2 Reports Table Schema

```sql
CREATE TABLE claude_reports (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    market VARCHAR(10) NOT NULL,        -- 'US', 'HKEX', 'global'
    report_type VARCHAR(50) NOT NULL,   -- 'daily', 'weekly', 'alert'
    report_date DATE NOT NULL,
    title VARCHAR(200) NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_id, report_type, report_date, market)
);
```

### 3.3 Metrics JSONB Structure

```json
{
    "total_pnl": 6678.00,
    "positions_open": 3,
    "account_value": 1005890.27,
    "cash": 468624.27,
    "win_rate": 0.67
}
```

---

## 4. API Endpoints

### 4.1 GET Endpoints (Read)

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard home with pending approvals, agents, messages, command center |
| `GET /agents` | All agent states with budget tracking |
| `GET /messages` | Recent inter-agent messages |
| `GET /observations` | Recent agent observations |
| `GET /questions` | Open questions for family discussion |
| `GET /approvals` | Pending escalation approvals |
| `GET /reports` | Trading reports list with filters (market, type) |
| `GET /reports/{id}` | Single report with full content and metrics |

### 4.2 POST Endpoints (Write)

| Endpoint | Description |
|----------|-------------|
| `POST /message` | Send message to an agent |
| `POST /question` | Add a new question |
| `POST /approve/{id}` | Approve an escalation request |
| `POST /deny/{id}` | Deny an escalation request |
| `POST /command/{id}` | Execute a quick command from command center |

### 4.3 Query Parameters

| Parameter | Used On | Description |
|-----------|---------|-------------|
| `token` | All endpoints | Authentication token (required) |
| `market` | `/reports` | Filter by market: US, HKEX |
| `report_type` | `/reports` | Filter by type: daily, weekly |

---

## 5. UI Components

### 5.1 Navigation Bar

Horizontal navigation with approval badge visible on all pages:

```
[Home] [Approvals (3)] [Reports] [Agents] [Messages] [Observations] [Questions]
```

### 5.2 Command Center

Quick action buttons for common operations:

| Icon | Label | Target | Action |
|------|-------|--------|--------|
| 📊 | Report HKEX | intl_claude | Request daily trading report |
| 📊 | Report US | public_claude | Request daily trading report |
| 🔍 | Status | big_bro | Request system status |
| 🛑 | STOP | broadcast | Emergency stop all trading (urgent) |
| 🔄 | Health | big_bro | Run health check on all agents |

**Custom Message Form (expandable):**
- To: Agent selector (intl_claude, public_claude, big_bro)
- Priority: Normal / High / 🚨 Urgent
- Subject: Brief subject line
- Message: Body text

### 5.3 Agent Card

Displays agent status with mode indicator and budget tracking:

```
┌─────────────────────────────────────────────────┐
│ big_bro                          [sleeping]     │
│ Monitoring all systems                          │
│ Budget: $0.0010 / $10.00 ($9.999 left)         │
│ Last wake: 01/15 08:00 AWST                    │
│ Errors today: 0                                 │
└─────────────────────────────────────────────────┘
```

**Mode classes:**
- `sleeping` - Normal idle state
- `thinking` - Active processing
- `error` - Error state (red highlight)

### 5.4 Approval Card

Escalation requests with approve/deny buttons:

```
┌─────────────────────────────────────────────────┐
│ public_claude                  01/15 09:30 AWST │  ← Yellow left border
│ Permission to restart Docker                    │
│ The Docker container has been unresponsive...   │
│                                                 │
│ [✓ Approve]  [✗ Deny]                          │
└─────────────────────────────────────────────────┘
```

### 5.5 Report Card

Trading report summary with metrics:

```
┌─────────────────────────────────────────────────┐
│ HKEX                              2025-01-14    │  ← Market badge (yellow)
│ 📈 HKEX Daily Report - 2025-01-14               │
│ intl_claude   +6,678.00   3 positions           │  ← P&L green if positive
│ +HKD 6,678 · 3 positions open                   │
│ [View Full Report →]                            │
└─────────────────────────────────────────────────┘
```

### 5.6 Message Card

```
┌─────────────────────────────────────────────────┐
│ craig_desktop → intl_claude    01/15 09:30 AWST │
│ Request: Daily Report                           │
└─────────────────────────────────────────────────┘
```

---

## 6. Styling

### 6.1 Color Palette

| Element | Color | Usage |
|---------|-------|-------|
| Background | `#0f0f23` | Main page background |
| Card Background | `#1a1a2e` | Cards, nav buttons |
| Primary Accent | `#00d4ff` | Links, headings, active states, US market |
| Secondary Accent | `#ff0` (yellow) | HKEX market, escalation cards |
| Success | `#0f0` / `#0a3` | Positive P&L, approve button |
| Error/Alert | `#f00` / `#a00` | Negative P&L, deny button, alert heading |
| Text Primary | `#fff` | Main text, subjects |
| Text Secondary | `#888` / `#aaa` | Labels, timestamps, body text |

### 6.2 CSS Classes

```css
/* Base styles */
body { background: #0f0f23; color: #e0e0e0; font-family: -apple-system, sans-serif; }
.card { background: #1a1a2e; border-radius: 8px; padding: 12px; margin: 8px 0; }

/* Agent modes */
.mode-sleeping { color: #888; }
.mode-thinking { color: #0f0; }
.mode-error { color: #f00; }

/* Escalation card */
.card.escalation { border-left: 3px solid #ff0; background: #2a2a1e; }

/* Approval buttons */
.btn-approve { background: #0a3; }
.btn-deny { background: #a00; }

/* Alert heading (pulsing) */
.alert-heading { 
    color: #ff4444 !important; 
    font-weight: bold; 
    animation: pulse 2s infinite; 
}
@keyframes pulse { 
    0%, 100% { opacity: 1; } 
    50% { opacity: 0.7; } 
}

/* Navigation */
.nav a { color: #00d4ff; background: #1a1a2e; padding: 8px 12px; border-radius: 4px; }
.nav a:hover { background: #252545; }
.nav a.active { background: #00d4ff; color: #000; }

/* Badge */
.badge { background: #ff0; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
```

### 6.3 Special Effects

- **Pulsing red animation** for pending approvals heading
- **Hover states** on nav buttons (#252545)
- **Active state** on current page (cyan background, black text)
- **Yellow left border** on escalation cards

---

## 7. Implementation Files

### 7.1 File Locations

| File | Version | Purpose |
|------|---------|---------|
| `services/consciousness/web_dashboard.py` | v1.3.0 | Main FastAPI application |
| `services/consciousness/run-dashboard.sh` | v1.0.0 | Startup script with environment loading |
| `Documentation/Implementation/Completed/reports-feature-design-v1.0.0.md` | v1.0.0 | Reports section design specification |

### 7.2 Environment Variables

| Variable | Description |
|----------|-------------|
| `RESEARCH_DATABASE_URL` | PostgreSQL connection string for catalyst_research |
| `CONSCIOUSNESS_TOKEN` | Authentication token (default: catalyst2025) |

### 7.3 Dependencies

```python
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
import asyncpg
from datetime import datetime, timezone, timedelta
```

---

## 8. Deployment

### 8.1 Access URL

```
http://<DROPLET_IP>:8088/?token=catalyst2025
```

### 8.2 Service Management

```bash
# Start dashboard
systemctl start consciousness-dashboard

# Check status
systemctl status consciousness-dashboard

# View logs
journalctl -u consciousness-dashboard -f

# Restart after changes
systemctl restart consciousness-dashboard
```

### 8.3 Manual Start

```bash
cd /root/catalyst-trading-system
source .env
uvicorn services.consciousness.web_dashboard:app --host 0.0.0.0 --port 8088
```

### 8.4 Systemd Service File

```ini
[Unit]
Description=Catalyst Consciousness Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/catalyst-trading-system
ExecStart=/root/catalyst-trading-system/services/consciousness/run-dashboard.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 9. Wireframes

### 9.1 Home Page

```
┌─────────────────────────────────────────────────────────┐
│  🧠 Catalyst Consciousness                              │
│  All times AWST (UTC+8)                                 │
├─────────────────────────────────────────────────────────┤
│ [Home] [Approvals (2)] [Reports] [Agents] [Messages]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⚠️ PENDING APPROVALS (2)              [pulsing red]   │
│  ┌─────────────────────────────────────────────────┐   │
│  │ public_claude: Permission to restart Docker     │   │
│  │ [✓ Approve]  [✗ Deny]                          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  📡 COMMAND CENTER                                      │
│  [📊 Report HKEX] [📊 Report US] [🔍 Status]           │
│  [🛑 STOP] [🔄 Health]                                 │
│  ▶ Custom Message (expandable)                          │
│                                                         │
│  👥 AGENTS                                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │ big_bro          [sleeping]                     │   │
│  │ Monitoring all systems                          │   │
│  │ Today: $0.0010                                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  💬 RECENT MESSAGES                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │ craig_desktop → intl_claude     01/15 09:30 AWST│   │
│  │ Request: Daily Report                           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  👁️ RECENT OBSERVATIONS                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │ intl_claude: Market opened with gap up          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.2 Reports Page

```
┌─────────────────────────────────────────────────────────┐
│  📊 Reports                                             │
├─────────────────────────────────────────────────────────┤
│ [Home] [Approvals] [Reports] [Agents] [Messages]        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [All] [Daily] [Weekly] [US] [HKEX]     ← Filter tabs  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ HKEX                              2025-01-14    │   │
│  │ 📈 HKEX Daily Report - 2025-01-14               │   │
│  │ intl_claude  +6,678.00  3 positions             │   │
│  │ [View Full Report →]                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ US                                2025-01-14    │   │
│  │ 📈 US Daily Report - 2025-01-14                 │   │
│  │ public_claude  +$0.00  0 positions              │   │
│  │ [View Full Report →]                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ global                            2025-01-12    │   │
│  │ 📊 Weekly Strategy Review - Week 2              │   │
│  │ big_bro                                         │   │
│  │ [View Full Report →]                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.3 Single Report View

```
┌─────────────────────────────────────────────────────────┐
│  ← Back to Reports                                      │
│                                                         │
│  HKEX Daily Report - 2025-01-14                        │
│  HKEX · intl_claude · 2025-01-14 · daily               │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ METRICS                                         │   │
│  │ Total P&L: +HKD 6,678.00                       │   │
│  │ Positions: 3                                    │   │
│  │ Account Value: HKD 1,005,890.27                │   │
│  │ Win Rate: 67%                                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ # Daily Trading Report - 2025-01-14            │   │
│  │                                                 │   │
│  │ **Generated:** 21:37:00 HKT                    │   │
│  │ **System:** Catalyst International (HKEX)      │   │
│  │                                                 │   │
│  │ ## Portfolio Summary                           │   │
│  │ | Metric | Value |                             │   │
│  │ |--------|-------|                             │   │
│  │ | Total Assets | HKD 1,005,890.27 |           │   │
│  │ | Unrealized P&L | +HKD 6,678 |               │   │
│  │                                                 │   │
│  │ ## Orders Summary                              │   │
│  │ | Type | Count | Notes |                       │   │
│  │ |------|-------|-------|                       │   │
│  │ | New Orders | 2 | Momentum + catalyst        │   │
│  │ | Skipped | 5 | See reasons below            │   │
│  │ | Exits | 1 | Take profit hit               │   │
│  │                                                 │   │
│  │ ### New Orders                                 │   │
│  │ | Symbol | Qty | Entry | Reason |             │   │
│  │ |--------|-----|-------|--------|             │   │
│  │ | 2382 | 500 | 38.50 | Gap + volume surge   │   │
│  │ | 9988 | 200 | 85.20 | Earnings + momentum  │   │
│  │                                                 │   │
│  │ ### No Orders (Reasons)                        │   │
│  │ | Symbol | Reason |                            │   │
│  │ |--------|--------|                            │   │
│  │ | 0700 | RSI > 70, overbought                 │   │
│  │ | 3690 | Volume < 1.5x average               │   │
│  │ | 1024 | Daily loss limit reached            │   │
│  │                                                 │   │
│  │ ## Open Positions (3)                          │   │
│  │ | Symbol | Qty | Entry | Current | SL | TP |  │   │
│  │ |--------|-----|-------|---------|-----|-----|│   │
│  │ | 981 | 500 | 42.10 | 51.85 | 39.99 | 54.73 │ │   │
│  │ | 1810 | 200 | 18.50 | 29.54 | 17.58 | 24.05│ │   │
│  │ | 2382 | 500 | 38.50 | 37.69 | 36.58 | 50.05│ │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.4 Agents Page

```
┌─────────────────────────────────────────────────────────┐
│  Agents                                                 │
├─────────────────────────────────────────────────────────┤
│ [Home] [Approvals] [Reports] [Agents] [Messages]        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ big_bro                          [sleeping]     │   │
│  │ Strategic oversight - all systems nominal       │   │
│  │ Budget: $0.0010 / $10.00 ($9.999 left)         │   │
│  │ Last wake: 01/15 08:00 AWST                    │   │
│  │ Errors today: 0                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ public_claude                    [sleeping]     │   │
│  │ US trading - markets closed                     │   │
│  │ Budget: $0.0007 / $5.00 ($4.9993 left)         │   │
│  │ Last wake: 01/15 07:15 AWST                    │   │
│  │ Errors today: 0                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ intl_claude                      [sleeping]     │   │
│  │ HKEX trading - markets closed                   │   │
│  │ Budget: $0.0000 / $5.00 ($5.00 left)           │   │
│  │ Last wake: 01/15 17:30 AWST                    │   │
│  │ Errors today: 0                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Future Enhancements

### 10.1 Planned Features

1. **Real-time WebSocket updates** - Auto-refresh without page reload
2. **Push notifications** - For urgent approvals
3. **Position monitoring dashboard** - With P&L charts
4. **Historical report trends** - Analytics over time
5. **Agent performance metrics** - Tracking over time

### 10.2 MCP Tool Integration

Planned MCP tools for report management:

```python
@mcp.tool()
async def get_reports(
    market: str = None,      # 'US', 'HKEX', 'global'
    report_type: str = None, # 'daily', 'weekly', 'alert'
    limit: int = 10
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

### 10.3 Agent Integration Pattern

When an agent generates a daily report:

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

---

## 11. Daily Report Format Specification

### 11.1 Report Structure Requirements

Daily reports must include the following sections in order:

1. **Header** - Date, time, system, mode, agent
2. **Portfolio Summary** - Account value, cash, P&L
3. **Orders Summary** - New orders, skipped opportunities, exits
4. **Order Details** - Reasons for each decision
5. **Open Positions** - With stop loss and take profit values

### 11.2 Orders Summary Section

**Purpose:** Show trading activity with clear reasoning for decisions.

| Type | Description |
|------|-------------|
| **New Orders** | Orders placed today with entry reasons |
| **Skipped** | Opportunities evaluated but not taken, with reasons |
| **Exits** | Positions closed (SL hit, TP hit, manual) |

**Example:**
```markdown
## Orders Summary

| Type | Count | Notes |
|------|-------|-------|
| New Orders | 2 | Strong momentum + news catalyst |
| Skipped | 5 | Low volume, RSI overbought, risk limit |
| Exits | 1 | Take profit hit on 1810 |

### New Orders
| Symbol | Action | Qty | Entry | Reason |
|--------|--------|-----|-------|--------|
| 2382 | BUY | 500 | 38.50 | Gap up + volume surge + positive news |
| 9988 | BUY | 200 | 85.20 | Earnings beat + momentum continuation |

### No Orders Placed (Reasons)
| Symbol | Reason |
|--------|--------|
| 0700 | RSI > 70, overbought condition |
| 3690 | Volume below 1.5x average threshold |
| 1024 | Risk check failed: daily loss limit reached |
| 0175 | Pattern confidence < 70% |
| 2318 | No news catalyst found |
```

### 11.3 Open Positions Section

**Required Columns:**
- Symbol
- Quantity
- Entry Price
- Current Price
- Stop Loss
- Take Profit

**Removed Columns (not needed):**
- ~~P&L %~~ (can be calculated from entry/current)
- ~~Avg Cost~~ (same as entry price for single fills)

**Example:**
```markdown
## Open Positions (3)

| Symbol | Qty | Entry | Current | Stop Loss | Take Profit |
|--------|-----|-------|---------|-----------|-------------|
| 981 | 500 | 42.10 | 51.85 | 39.99 | 54.73 |
| 1810 | 200 | 18.50 | 29.54 | 17.58 | 24.05 |
| 2382 | 500 | 38.50 | 37.69 | 36.58 | 50.05 |
```

### 11.4 Reasoning Categories

Standard reasons for **not placing orders**:

| Category | Example Reasons |
|----------|----------------|
| **Technical** | RSI overbought (>70), RSI oversold (<30), No pattern detected |
| **Volume** | Volume < 1.5x average, Insufficient liquidity |
| **Risk** | Daily loss limit reached, Position limit (5 max), Max drawdown |
| **News** | No catalyst found, Negative sentiment score |
| **Pattern** | Confidence < 70%, Pattern invalidated |
| **Price** | Entry price moved away, Gap too large |

Standard reasons for **placing orders**:

| Category | Example Reasons |
|----------|----------------|
| **Momentum** | Gap up + volume surge, Breakout above resistance |
| **News** | Earnings beat, Positive analyst upgrade, Product launch |
| **Technical** | Bull flag confirmed, RSI 40-60 with momentum |
| **Pattern** | Cup and handle (85% confidence), ABCD pattern complete |

### 11.5 Metrics JSON Structure

```json
{
    "total_pnl": 6678.00,
    "positions_open": 3,
    "account_value": 1005890.27,
    "cash": 468624.27,
    "win_rate": 0.67,
    "orders_new": 2,
    "orders_skipped": 5,
    "orders_exits": 1
}
```

---

## 12. Testing Checklist

- [ ] Dashboard loads with valid token
- [ ] Unauthorized access returns 401
- [ ] All navigation links work
- [ ] Approval badge shows on all pages
- [ ] Approve/Deny buttons work
- [ ] Command center sends messages
- [ ] Reports list displays correctly
- [ ] Report filters work (market, type)
- [ ] Single report view renders content
- [ ] Times display in Perth timezone (AWST)
- [ ] Mobile responsive on phone screens
- [ ] Daily report shows Orders Summary section
- [ ] Daily report shows reasons for skipped orders
- [ ] Open positions show Stop Loss and Take Profit columns

---

## 13. Related Documents

| Document | Location |
|----------|----------|
| Architecture Consolidation | `Documentation/Design/Archive/architecture-consolidation-v9.2.0.md` |
| Reports Feature Design | `Documentation/Implementation/Completed/reports-feature-design-v1.0.0.md` |
| Deployment Summary | `Documentation/Implementation/deployment-summary-2025-12-31.md` |
| Concepts - Catalyst Trading | `Documentation/Design/concepts-catalyst-trading.md` |

---

*— End of Document —*
