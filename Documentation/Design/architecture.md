# Catalyst Trading System - Architecture

**Name of Application**: Catalyst Trading System  
**Name of file**: architecture.md  
**Version**: 7.0.0  
**Last Updated**: 2025-12-27  
**Purpose**: System architecture for Production trading system  
**Scope**: PRODUCTION ARCHITECTURE + DOCTOR CLAUDE MONITORING

---

## REVISION HISTORY

**v7.0.0 (2025-12-27)** - DOCTOR CLAUDE MONITORING INTEGRATION
- ✅ **NEW**: Doctor Claude trade lifecycle monitoring system
- ✅ **NEW**: `claude_activity_log` table for audit trail
- ✅ **NEW**: `doctor_claude_rules` table for auto-fix configuration
- ✅ **NEW**: `trade_watchdog.py` diagnostic script
- ✅ **NEW**: `log_activity.py` activity logger
- ✅ **NEW**: Pipeline status views for real-time monitoring
- ✅ Claude Code as active watchdog during market hours

**v6.0.0 (2025-10-25)** - PRODUCTION ARCHITECTURE CLEAN SEPARATION
- ✅ Research services removed entirely
- ✅ 9-service microservices (no ML/Research services)
- ✅ Single DigitalOcean droplet deployment
- ✅ MCP protocol for Claude Desktop integration

**v5.0.0 (2025-10-22)** - 9-Service Split (superseded)

---

## ⚠️ CRITICAL: SCOPE DEFINITION

### **IN SCOPE (Production Architecture)**
✅ 9 microservices for day trading  
✅ MCP protocol (Claude Desktop interface)  
✅ REST APIs (internal service communication)  
✅ PostgreSQL (normalized production database)  
✅ Redis (pub/sub + caching)  
✅ Docker Compose (service orchestration)  
✅ Single DigitalOcean droplet  
✅ Nginx (SSL termination + reverse proxy)  
✅ **Doctor Claude monitoring system**  

### **OUT OF SCOPE (Future Research Architecture)**
❌ ML Training Service  
❌ Pattern Discovery Service  
❌ Backtest Engine  
❌ Multi-Agent Coordinator  

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Service Architecture](#2-service-architecture)
3. [Doctor Claude Monitoring](#3-doctor-claude-monitoring)
4. [Communication Patterns](#4-communication-patterns)
5. [Data Architecture](#5-data-architecture)
6. [Deployment Architecture](#6-deployment-architecture)
7. [Security Architecture](#7-security-architecture)
8. [Reliability Architecture](#8-reliability-architecture)

---

## 1. Architecture Overview

### 1.1 Architecture Philosophy

```yaml
Design Principles:
  - Production-first: Complete working system
  - Single instance: No premature scaling complexity
  - Proven tech: Docker Compose, PostgreSQL, Redis
  - Clean separation: MCP vs REST, concerns isolated
  - Fail-safe: Risk management enforced at multiple layers
  - Observable: Doctor Claude monitors trade lifecycle
```

### 1.2 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  EXTERNAL LAYER                              │
│                                                              │
│  ┌────────────────────────┐      ┌──────────────────────┐  │
│  │ Claude Desktop         │      │ Alpaca Markets API   │  │
│  │ (Windows/Mac)          │      │ (Trading Execution)  │  │
│  │ MCP Client             │      │ REST API             │  │
│  └───────────┬────────────┘      └──────────┬───────────┘  │
│              │                               │              │
└──────────────┼───────────────────────────────┼──────────────┘
               │ HTTPS (443)                   │ HTTPS
               │ MCP Protocol                  │
┌──────────────▼───────────────────────────────▼──────────────┐
│              PRESENTATION LAYER                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Nginx Reverse Proxy                                  │  │
│  │ - SSL/TLS Termination                                │  │
│  │ - API Key Validation                                 │  │
│  │ - Request Routing                                    │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
└───────────────────────┼─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│            APPLICATION LAYER (Docker Network)                │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ MCP SERVICE                                           │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │ Orchestration Service (Port 5000)           │    │ │
│  │  │ - FastMCP framework                         │    │ │
│  │  │ - MCP resources (trading-cycle/*, etc.)     │    │ │
│  │  │ - MCP tools (execute_trade, etc.)           │    │ │
│  │  │ - Routes to Workflow via REST               │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────┘ │
│                       │                                     │
│                       │ REST API Calls                      │
│                       ▼                                     │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ REST SERVICES (Business Logic)                        │ │
│  │                                                       │ │
│  │  ┌─────────────────┐  ┌─────────────────┐           │ │
│  │  │ Workflow (5006) │  │ Scanner (5001)  │           │ │
│  │  │ - Coord logic   │  │ - Market filter │           │ │
│  │  └─────────────────┘  └─────────────────┘           │ │
│  │                                                       │ │
│  │  ┌─────────────────┐  ┌─────────────────┐           │ │
│  │  │ Pattern (5002)  │  │ Technical (5003)│           │ │
│  │  │ - Chart patterns│  │ - Indicators    │           │ │
│  │  └─────────────────┘  └─────────────────┘           │ │
│  │                                                       │ │
│  │  ┌─────────────────┐  ┌─────────────────┐           │ │
│  │  │ Risk Mgr (5004) │  │ Trading (5005)  │           │ │
│  │  │ - Risk checks   │  │ - Alpaca orders │           │ │
│  │  └─────────────────┘  └─────────────────┘           │ │
│  │                                                       │ │
│  │  ┌─────────────────┐  ┌─────────────────┐           │ │
│  │  │ News (5008)     │  │ Reporting (5009)│           │ │
│  │  │ - Catalysts     │  │ - Analytics     │           │ │
│  │  └─────────────────┘  └─────────────────┘           │ │
│  └───────────────────────────────────────────────────────┘ │
│                       │                                     │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ INFRASTRUCTURE SERVICES                                │ │
│  │  ┌─────────────────────┐  ┌──────────────────────┐  │ │
│  │  │ Redis (6379)        │  │ PostgreSQL           │  │ │
│  │  │ - Pub/Sub           │  │ - DigitalOcean       │  │ │
│  │  │ - Cache             │  │ - Managed DB         │  │ │
│  │  └─────────────────────┘  └──────────────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ DOCTOR CLAUDE MONITORING (NEW in v7.0)                │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │ Claude Code (Active Watchdog)               │    │ │
│  │  │ - trade_watchdog.py (diagnostics)           │    │ │
│  │  │ - log_activity.py (audit trail)             │    │ │
│  │  │ - Observe → Decide → Act → Log loop         │    │ │
│  │  │ - Auto-fix safe issues, escalate others     │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Service Architecture

### 2.1 Service Matrix

| # | Service | Type | Port | Technology | Dependencies |
|---|---------|------|------|------------|--------------|
| 1 | **Orchestration** | MCP | 5000 | FastMCP, FastAPI | Workflow, Redis |
| 2 | **Scanner** | REST | 5001 | FastAPI | News, Technical, Pattern, PostgreSQL |
| 3 | **Pattern** | REST | 5002 | FastAPI, NumPy | PostgreSQL, Redis |
| 4 | **Technical** | REST | 5003 | FastAPI, TA-Lib | PostgreSQL, Redis |
| 5 | **Risk Manager** | REST | 5004 | FastAPI | PostgreSQL, Redis |
| 6 | **Trading** | REST | 5005 | FastAPI, Alpaca SDK | Risk Manager, PostgreSQL |
| 7 | **Workflow** | REST | 5006 | FastAPI | All services, PostgreSQL, Redis |
| 8 | **News** | REST | 5008 | FastAPI, FinBERT | PostgreSQL, Redis |
| 9 | **Reporting** | REST | 5009 | FastAPI, Pandas | PostgreSQL |
| 10 | **Doctor Claude** | Script | N/A | Python, asyncpg | PostgreSQL, Alpaca API |

### 2.2 Service Dependency Graph

```
                    ┌─────────────────┐
                    │ Claude Desktop  │
                    └────────┬────────┘
                             │ MCP
                    ┌────────▼────────┐
                    │ Orchestration   │
                    └────────┬────────┘
                             │ REST
                    ┌────────▼────────┐
                    │   Workflow      │◄─────┐
                    └────────┬────────┘      │
                             │               │
          ┌──────────────────┼───────────────┼──────────────┐
          │                  │               │              │
    ┌─────▼─────┐     ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
    │   News    │     │  Scanner  │  │ Technical │  │  Pattern  │
    └───────────┘     └─────┬─────┘  └───────────┘  └───────────┘
                            │
                      ┌─────▼─────┐
                      │Risk Manager│
                      └─────┬─────┘
                            │
                      ┌─────▼─────┐
                      │  Trading  │◄────────────────┐
                      └─────┬─────┘                 │
                            │                       │
                      ┌─────▼─────┐          ┌─────┴─────┐
                      │ Reporting │          │  Doctor   │
                      └───────────┘          │  Claude   │
                                             └───────────┘
                                                   │
                                             Monitors All
                                             Services via
                                             DB + Alpaca
```

---

## 3. Doctor Claude Monitoring

### 3.1 Overview

Doctor Claude is an active monitoring system where Claude Code watches the trade pipeline during market hours, diagnoses issues, applies safe fixes, and logs all activities.

### 3.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DOCTOR CLAUDE                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐  │
│   │                 OBSERVE-DECIDE-ACT LOOP             │  │
│   │                                                     │  │
│   │   ┌──────────┐    ┌──────────┐    ┌──────────┐    │  │
│   │   │   RUN    │───▶│   READ   │───▶│  DECIDE  │    │  │
│   │   │ WATCHDOG │    │  OUTPUT  │    │          │    │  │
│   │   └──────────┘    └──────────┘    └────┬─────┘    │  │
│   │        ▲                               │          │  │
│   │        │                               ▼          │  │
│   │   ┌────┴─────┐    ┌──────────┐    ┌──────────┐   │  │
│   │   │   LOG    │◀───│   LOG    │◀───│   ACT    │   │  │
│   │   │  RESULT  │    │ DECISION │    │          │   │  │
│   │   └──────────┘    └──────────┘    └──────────┘   │  │
│   │        │                                          │  │
│   │        └──────────── WAIT 5 MIN ─────────────────┘  │
│   └─────────────────────────────────────────────────────┘  │
│                                                             │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  PostgreSQL  │ │    Alpaca    │ │    Email     │
    │   Database   │ │   Broker     │ │   Alerts     │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### 3.3 Components

| Component | File | Purpose |
|-----------|------|---------|
| **Trade Watchdog** | `trade_watchdog.py` | Diagnostic checks, JSON output |
| **Activity Logger** | `log_activity.py` | Audit trail to database |
| **Rules Table** | `doctor_claude_rules` | Auto-fix configuration |
| **Activity Log** | `claude_activity_log` | Decision/action history |
| **Pipeline View** | `v_trade_pipeline_status` | Real-time pipeline state |

### 3.4 Checks Performed

| Check | Description | Severity | Auto-Fixable |
|-------|-------------|----------|--------------|
| Pipeline Status | Current cycle state | INFO | N/A |
| Stuck Orders | Orders pending > 5 min | WARNING | No |
| Phantom Positions | DB position not in Alpaca | CRITICAL | Yes |
| Orphan Positions | Alpaca position not in DB | CRITICAL | No |
| Qty Mismatch | DB qty ≠ Alpaca qty | WARNING | Maybe |
| Order Status Mismatch | DB status ≠ Alpaca status | WARNING | Yes |
| Stale Cycle | No activity > 30 min | WARNING | No |

### 3.5 Safety Boundaries

**Doctor Claude will NEVER:**
- Close positions in Alpaca automatically
- Modify real money amounts
- Change risk parameters
- Override emergency stops

**Doctor Claude CAN:**
- Sync DB state to match Alpaca (read broker, write DB)
- Mark phantom positions as closed
- Update order statuses to match Alpaca
- Alert Craig to issues requiring human judgment

---

## 4. Communication Patterns

### 4.1 MCP Protocol (Claude Desktop ↔ Orchestration)

**Protocol**: Model Context Protocol (MCP)  
**Transport**: HTTPS (443)  
**Format**: JSON-RPC 2.0  
**Authentication**: API Key (custom header)

### 4.2 REST APIs (Internal Service Communication)

**Protocol**: HTTP REST  
**Format**: JSON  
**Authentication**: API Key (X-API-Key header)  
**Network**: Docker bridge network (internal)

### 4.3 Doctor Claude Communication

**Database**: Direct PostgreSQL connection via asyncpg  
**Broker**: Alpaca Trading Client API  
**Alerts**: Email via SMTP (escalations)  
**Output**: Structured JSON for Claude Code parsing

### 4.4 Redis Pub/Sub Pattern

**Redis Channels**:
```yaml
catalyst:scan_complete - Scanner finished
catalyst:position_update - Position P&L changed
catalyst:risk_alert - Risk threshold reached
catalyst:order_filled - Order execution confirmed
catalyst:news_catalyst - High-strength catalyst detected
```

---

## 5. Data Architecture

### 5.1 Database Design Philosophy

**Normalization Level**: 3NF (Third Normal Form)  
**Key Principle**: Security_id FK everywhere, NO symbol VARCHAR duplication  
**Query Strategy**: Always JOIN to get human-readable data

### 5.2 Core Tables

| Table | Type | Purpose |
|-------|------|---------|
| `securities` | Dimension | Master security data |
| `sectors` | Dimension | GICS sectors |
| `trading_cycles` | Operations | Daily workflows |
| `positions` | Operations | Trading positions |
| `orders` | Operations | Order execution |
| `scan_results` | Operations | Market scan candidates |

### 5.3 Doctor Claude Tables (NEW in v7.0)

| Table | Purpose |
|-------|---------|
| `claude_activity_log` | Audit trail of observations, decisions, actions |
| `doctor_claude_rules` | Auto-fix rules and escalation configuration |

### 5.4 Doctor Claude Views (NEW in v7.0)

| View | Purpose |
|------|---------|
| `v_trade_pipeline_status` | Real-time pipeline state |
| `v_claude_activity_summary` | Daily activity summary |
| `v_recurring_issues` | Issue frequency for learning |
| `v_recent_escalations` | Issues needing human review |
| `v_failed_actions` | Failed actions for investigation |

---

## 6. Deployment Architecture

### 6.1 Single Droplet Design

**DigitalOcean Droplet**:
```yaml
Size: 4GB RAM, 2vCPU, 80GB SSD
OS: Ubuntu 22.04 LTS
Location: SFO3 (US West - closest to markets)
```

### 6.2 Service Startup Order

```
1. Redis (10s startup)
   ↓
2. Infrastructure services in parallel:
   - News (15s)
   - Technical (15s)
   - Pattern (15s)
   ↓
3. Core trading services:
   - Scanner (depends on News)
   - Risk Manager
   ↓
4. Execution layer:
   - Trading (depends on Risk Manager)
   - Workflow (depends on all services)
   ↓
5. Interface layer:
   - Orchestration (depends on Workflow)
   - Reporting
   ↓
6. Monitoring layer:
   - Doctor Claude (runs after market open)
```

### 6.3 Doctor Claude Deployment

```yaml
Location: /root/catalyst-trading-mcp/scripts/
Files:
  - trade_watchdog.py
  - log_activity.py
  - doctor_claude_monitor.sh (wrapper script)

Execution:
  - During market hours only
  - Every 5 minutes via loop or cron
  - Can run as systemd service

Dependencies:
  - Python 3.10+
  - asyncpg
  - alpaca-py
```

---

## 7. Security Architecture

### 7.1 Authentication

| Component | Method |
|-----------|--------|
| MCP (Claude Desktop) | API Key in header |
| Internal REST APIs | API Key (X-API-Key) |
| PostgreSQL | Connection string with SSL |
| Alpaca | API Key + Secret |

### 7.2 Network Security

- All external traffic via Nginx with SSL
- Internal services on Docker bridge network
- No direct database exposure to internet
- Doctor Claude connects to managed DB via SSL

---

## 8. Reliability Architecture

### 8.1 Health Monitoring

| Component | Health Check |
|-----------|--------------|
| Docker Services | Container health checks |
| PostgreSQL | Connection pool validation |
| Redis | PING command |
| Alpaca | Account status check |
| Doctor Claude | Watchdog exit codes |

### 8.2 Error Recovery

| Failure | Recovery |
|---------|----------|
| Service crash | Docker auto-restart |
| Database connection | Connection pool retry |
| Alpaca unavailable | Graceful degradation |
| Doctor Claude issue | Log and continue |

### 8.3 Observability Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Traditional Monitoring:                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Docker Logs │ │ Health API  │ │ Redis Pub   │          │
│  │ /var/log    │ │ /health     │ │ /Sub        │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                             │
│  Doctor Claude (NEW):                                       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ • trade_watchdog.py - Pipeline diagnostics          │  │
│  │ • claude_activity_log - Decision audit trail        │  │
│  │ • v_trade_pipeline_status - Real-time view          │  │
│  │ • Auto-fix for safe issues                          │  │
│  │ • Escalation for critical issues                    │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Related Documents

- **database-schema.md** - Full database schema including Doctor Claude tables
- **functional-specification.md** - Service APIs and Doctor Claude operational specs
- **DOCTOR-CLAUDE-DESIGN.md** - Detailed Doctor Claude design
- **DOCTOR-CLAUDE-IMPLEMENTATION.md** - Deployment guide

---

**END OF ARCHITECTURE DOCUMENT v7.0.0**
