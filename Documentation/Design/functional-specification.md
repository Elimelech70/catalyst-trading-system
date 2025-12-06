# Catalyst Trading System - Functional Specification

**Name of Application**: Catalyst Trading System  
**Name of file**: functional-specification.md  
**Version**: 6.1.0  
**Last Updated**: 2025-10-25  
**Purpose**: Complete functional specifications including cron job automation and operational workflows  
**Scope**: PRODUCTION TRADING SYSTEM - 9 Services, US Markets, Stage 1

---

## REVISION HISTORY

**v6.1.0 (2025-10-25)** - CRON AUTOMATION & OPERATIONAL REQUIREMENTS
- ✅ **MAJOR ADDITION**: Section 9 - Workflow Initiation & Operational Requirements
- ✅ **CRITICAL CLARIFICATION**: Cron automation as PRIMARY workflow initiator
- ✅ **ROLE DEFINITION**: Claude Desktop as SECONDARY monitoring/ML tool
- ✅ Complete market hours cron schedule (Perth AWST → US EST)
- ✅ System maintenance automation specifications
- ✅ Production deployment requirements
- ✅ Failover and redundancy procedures
- ✅ ML improvement workflow integration

**v6.0.0 (2025-10-25)** - PRODUCTION SYSTEM CLEAN SEPARATION
- ✅ **MAJOR CHANGE**: Research features removed entirely from Production spec
- ✅ Production focus: 9 services, US markets only, Stage 1 trading
- ✅ Clean specification for immediate implementation
- ✅ Single instance deployment (DigitalOcean droplet)
- ✅ No ML training services, no multi-agent AI, no Chinese/Japanese markets
- ⚠️ **BREAKING**: Research/ML moved to separate instance (future)
- Strategy documents reference economic indicators but implementation is separate system

**v5.0.0 (2025-10-22)** - 9-Service Architecture (superseded)
- Mixed Production + Research features (caused implementation confusion)
- Reason for v6.0: Clean separation required for faster Production completion

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Service Matrix - 9 Microservices](#2-service-matrix---9-microservices)
3. [MCP Resource Hierarchy](#3-mcp-resource-hierarchy)
4. [MCP Tools Specification](#4-mcp-tools-specification)
5. [REST API Specifications](#5-rest-api-specifications)
6. [Data Flow Specifications](#6-data-flow-specifications)
7. [Claude Interaction Patterns](#7-claude-interaction-patterns)
8. [Error Handling](#8-error-handling)
9. [Workflow Initiation & Operational Requirements](#9-workflow-initiation--operational-requirements)
10. [Performance Requirements](#10-performance-requirements)
11. [Security Requirements](#11-security-requirements)
12. [Cron Configuration Reference](#12-cron-configuration-reference)

---

## 1. System Overview

### 1.1 Executive Summary

The Catalyst Trading System is a sophisticated day trading platform implementing **Ross Cameron momentum trading methodology** with AI-assisted decision-making through Claude Desktop. The system operates on a **9-service microservices architecture** deployed on DigitalOcean infrastructure.

**Key Characteristics:**
- **Automated Trading**: Cron-driven workflows execute 10+ times daily during market hours
- **AI Monitoring**: Claude Desktop provides intelligent oversight and continuous ML improvement
- **Risk-First Design**: Multi-layer risk validation before every trade
- **News-Catalyst Driven**: Primary filter based on market-moving news events
- **Multi-Stage Filtering**: Progressive refinement from 100 → 35 → 20 → 10 → 5 candidates

### 1.2 Dual Initiation Architecture

**CRITICAL UNDERSTANDING:**

```
PRIMARY INITIATION: Cron Automation (Production Trading)
    └─> Automated workflows 10+ times/day
    └─> REST API calls to Workflow service (port 5006)
    └─> No human intervention required
    └─> Runs business operations

SECONDARY INITIATION: Claude Desktop (Monitoring & ML)
    └─> Manual oversight and analysis
    └─> MCP protocol to Orchestration service (port 5000)
    └─> ML training data generation
    └─> Improves business operations
```

**This is NOT a Claude-driven trading system. This IS a cron-automated trading system with Claude providing intelligent analysis.**

---

## 2. Service Matrix - 9 Microservices

### 2.1 Complete Service Inventory

| # | Service | Type | Port | Primary Function | Protocol |
|---|---------|------|------|------------------|----------|
| 1 | **Orchestration** | MCP | 5000 | Claude Desktop interface | MCP (FastMCP) |
| 2 | **Workflow** | REST | 5006 | Trade coordination | REST (FastAPI) |
| 3 | **Scanner** | REST | 5001 | Market scanning | REST (FastAPI) |
| 4 | **Pattern** | REST | 5002 | Chart pattern recognition | REST (FastAPI) |
| 5 | **Technical** | REST | 5003 | Technical analysis | REST (FastAPI) |
| 6 | **Risk Manager** | REST | 5004 | Risk validation | REST (FastAPI) |
| 7 | **Trading** | REST | 5005 | Order execution (Alpaca) | REST (FastAPI) |
| 8 | **News** | REST | 5008 | News catalyst detection | REST (FastAPI) |
| 9 | **Reporting** | REST | 5009 | Performance analytics | REST (FastAPI) |

### 2.2 Service Dependency Flow

```
AUTOMATED WORKFLOWS (Cron-initiated):
┌─────────────┐
│  Cron Job   │ (10+ times/day during market hours)
└──────┬──────┘
       │ HTTP POST
       ▼
┌─────────────┐
│  Workflow   │ (Port 5006 - Coordination Logic)
│  Service    │
└──────┬──────┘
       │
       ├──> Scanner (5001) ──> News (5008)
       │        └──> Pattern (5002)
       │             └──> Technical (5003)
       │
       ├──> Risk Manager (5004)
       │
       ├──> Trading (5005) ──> Alpaca Markets
       │
       └──> Reporting (5009)

MONITORING & ANALYSIS (Claude Desktop):
┌─────────────┐
│Claude Desktop│ (Human-initiated)
└──────┬──────┘
       │ MCP Protocol
       ▼
┌─────────────┐
│Orchestration│ (Port 5000 - MCP Interface)
└──────┬──────┘
       │ REST API Calls
       ▼
┌─────────────┐
│  Workflow   │ (Can also receive manual commands)
│  Service    │
└─────────────┘
```

---

## 3. MCP Resource Hierarchy

### 3.1 Resource URIs

```
trading-cycle://
├── current                    # Active cycle state
├── {cycle_id}/
│   ├── status                 # Cycle status
│   ├── timeline               # Execution timeline
│   └── positions              # Cycle positions

market-scan://
├── latest                     # Most recent scan
├── candidates/
│   └── {symbol}               # Candidate details

positions://
├── current                    # Open positions
├── history                    # Closed positions
└── {position_id}/
    └── status                 # Position details

performance://
├── daily                      # Daily metrics
├── weekly                     # Weekly metrics
└── monthly                    # Monthly metrics

alerts://
├── active                     # Current alerts
└── history                    # Alert history

news://
└── catalysts                  # Active catalysts

risk://
├── status                     # Current risk state
└── violations                 # Risk violations
```

---

## 4. MCP Tools Specification

### 4.1 Trading Cycle Management

Claude Desktop can initiate workflows manually (though cron handles this automatically in production):

```python
@mcp.tool()
async def start_trading_cycle(
    ctx: Context,
    mode: str = "normal",  # "normal", "aggressive", "conservative"
    scan_frequency: int = 300,  # seconds between scans
    max_positions: int = 5,
    risk_per_trade: float = 0.01
) -> Dict:
    """
    Start a new trading cycle (usually triggered by cron, not manually)
    
    Returns:
        {
            "cycle_id": "uuid",
            "mode": "normal",
            "status": "scanning",
            "started_at": "2025-10-25T09:30:00Z"
        }
    """
```

```python
@mcp.tool()
async def stop_trading_cycle(
    ctx: Context,
    cycle_id: str
) -> Dict:
    """
    Stop an active trading cycle
    
    Returns:
        {
            "cycle_id": "uuid",
            "stopped_at": "2025-10-25T16:00:00Z",
            "final_pnl": 523.45,
            "trades_executed": 3
        }
    """
```

```python
@mcp.tool()
async def emergency_stop(
    ctx: Context,
    reason: str
) -> Dict:
    """
    Emergency halt - close all positions immediately
    
    Returns:
        {
            "positions_closed": 5,
            "total_realized_pnl": -123.45,
            "stopped_at": "2025-10-25T14:23:11Z"
        }
    """
```

### 4.2 Trade Execution

```python
@mcp.tool()
async def execute_trade(
    ctx: Context,
    symbol: str,
    side: str,  # "long" or "short"
    quantity: int,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    pattern: str,  # e.g., "bull_flag"
    confidence: float
) -> Dict:
    """
    Execute a trade (after risk validation)
    
    Returns:
        {
            "position_id": "uuid",
            "order_id": "alpaca_order_id",
            "status": "filled",
            "filled_price": 123.45
        }
    """
```

---

## 5. REST API Specifications

### 5.1 Workflow Service (Port 5006)

**Start Workflow:**
```
POST /api/v1/workflow/start

Request:
{
    "mode": "normal",
    "scan_frequency": 300,
    "max_positions": 5,
    "risk_per_trade": 0.01
}

Response:
{
    "cycle_id": "uuid",
    "status": "started",
    "mode": "normal"
}
```

**Workflow History:**
```
GET /api/v1/workflow/history?limit=50

Response:
{
    "cycles": [
        {
            "cycle_id": "uuid",
            "started_at": "...",
            "ended_at": "...",
            "trades": 3,
            "pnl": 523.45
        }
    ]
}
```

### 5.2 Scanner Service (Port 5001)

**Start Scan:**
```
POST /api/v1/scan/start

Request:
{
    "cycle_id": "uuid",
    "universe_size": 100
}

Response:
{
    "scan_id": "uuid",
    "status": "started",
    "estimated_completion": "2025-10-25T08:05:00Z"
}
```

---

## 6. Data Flow Specifications

### 6.1 Multi-Stage Filtering Pipeline

```
Stage 1: Universe Selection (100 stocks)
├── Volume > 1M shares/day
├── Price > $5
└── News in last 24 hours

Stage 2: Catalyst Filter (35 stocks)
├── catalyst_strength > 0.7
└── sentiment_score > 0.5

Stage 3: Technical Filter (20 stocks)
├── Price above SMA 20
├── RSI between 40-70
└── Volume > 1.5x average

Stage 4: Pattern Filter (10 stocks)
├── Recognized chart pattern
└── Pattern confidence > 0.7

Stage 5: Final Ranking (5 stocks)
├── Composite score calculation
└── Risk/reward assessment
```

---

## 7. Claude Interaction Patterns

### 7.1 Example Queries

**Performance Analysis:**
```
Claude Query: "How did we do today?"

Process:
1. Read MCP resource: performance://daily
2. Analyze: Win rate, P&L, best/worst trades
3. Present: Human-readable summary with insights
```

**Pattern Analysis:**
```
Claude Query: "Which patterns performed best this week?"

Process:
1. Read MCP resource: positions://history?days=7
2. Group by: Pattern type
3. Calculate: Win rate, average R:R, profit factor
4. Export: CSV file for ML training
```

**Manual Trade Intervention:**
```
Claude Query: "Close position X immediately - news changed"

Process:
1. Human identifies critical news not caught by system
2. Claude calls: emergency_stop(reason="FDA rejection news")
3. Workflow closes all positions
4. System logs decision for future improvement
```

---

## 8. Error Handling

### 8.1 Error Response Format

```json
{
  "error": {
    "code": "INVALID_UNIVERSE_SIZE",
    "message": "Universe size must be between 50 and 200",
    "details": {"provided": 10, "min": 50, "max": 200}
  }
}
```

### 8.2 Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `CYCLE_NOT_FOUND` | 404 | Trading cycle doesn't exist |
| `CYCLE_ALREADY_ACTIVE` | 409 | Cannot start new cycle |
| `RISK_VALIDATION_FAILED` | 400 | Trade rejected by risk manager |
| `ORDER_EXECUTION_FAILED` | 500 | Alpaca API error |
| `DATABASE_ERROR` | 500 | PostgreSQL connection issue |

---

## 9. Workflow Initiation & Operational Requirements

### 9.1 Overview: Primary vs Secondary Initiation

**CRITICAL ARCHITECTURAL PRINCIPLE:**

This system is **automated-first** with **intelligent monitoring**. Cron automation handles production trading; Claude Desktop provides analysis and continuous improvement.

| Aspect | PRIMARY: Cron Automation | SECONDARY: Claude Desktop |
|--------|--------------------------|---------------------------|
| **Purpose** | Execute trading workflows | Monitor & improve system |
| **Frequency** | 10+ times/day (market hours) | On-demand (human-initiated) |
| **Protocol** | REST API (port 5006) | MCP (port 5000) |
| **Target Service** | Workflow directly | Orchestration → Workflow |
| **Human Required** | No | Yes |
| **Production Role** | Runs the business | Improves the business |
| **Examples** | Market open scan, periodic scans | "Why did trade X lose?", "Analyze patterns" |

### 9.2 PRIMARY: Cron Automation

#### 9.2.1 Architecture

```
┌──────────────────────────────────────────────────────┐
│              CRON SCHEDULER                          │
│  (Linux crontab on DigitalOcean droplet)            │
└───────────────────┬──────────────────────────────────┘
                    │
                    │ HTTP POST
                    │ http://localhost:5006/api/v1/workflow/start
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│            WORKFLOW SERVICE (Port 5006)              │
│  - Receives workflow commands                        │
│  - Orchestrates Scanner → Pattern → Technical       │
│  - Coordinates Risk Manager validation              │
│  - Routes signals to Trading service                │
│  - Logs decisions for ML training                   │
└──────────────────────────────────────────────────────┘
```

#### 9.2.2 Complete Cron Schedule (Perth AWST → US EST)

**Server Timezone**: Perth, Western Australia (AWST = UTC+8)  
**US Market Hours**: 9:30 AM - 4:00 PM EST  
**Perth Equivalent**: 10:30 PM - 5:00 AM AWST (next day)

##### Pre-Market Startup
```bash
# 9:00 PM Perth = 4:00 AM EST
# Start all Docker services before market opens
0 21 * * 1-5 cd /root/catalyst-trading-mcp && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1
```

##### Market Open Trigger
```bash
# 10:30 PM Perth = 9:30 AM EST
# Initiate first trading workflow at market open
30 22 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal", "scan_frequency": 300, "max_positions": 5}' \
  >> /var/log/catalyst/trading.log 2>&1
```

##### Periodic Workflow Triggers During Market Hours
```bash
# Every 30 minutes from 11:00 PM - 4:30 AM Perth (10:00 AM - 3:30 PM EST)
0,30 23 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}' \
  >> /var/log/catalyst/trading.log 2>&1

0,30 0-4 * * 2-6 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}' \
  >> /var/log/catalyst/trading.log 2>&1
```

##### Market Close Operations
```bash
# 5:00 AM Perth = 4:00 PM EST
0 5 * * 2-6 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "conservative", "max_positions": 3}' \
  >> /var/log/catalyst/trading.log 2>&1
```

##### After-Hours Shutdown
```bash
# 9:00 AM Perth = 8:00 PM EST
0 9 * * 2-6 cd /root/catalyst-trading-mcp && docker-compose stop \
  >> /var/log/catalyst/shutdown.log 2>&1
```

#### 9.2.3 Workflow Parameters by Time Period

| Time Period (EST) | Mode | Max Positions | Scan Frequency | Risk per Trade |
|-------------------|------|---------------|----------------|----------------|
| Pre-market (4:00-9:25 AM) | aggressive | 3 | 5 minutes | 0.5% |
| Opening range (9:30-9:45 AM) | normal | 5 | Real-time | 1.0% |
| Morning session (9:45-11:30 AM) | normal | 5 | 15 minutes | 1.0% |
| Midday (11:30-2:00 PM) | conservative | 3 | 30 minutes | 0.75% |
| Power hour (2:00-3:30 PM) | normal | 5 | 15 minutes | 1.0% |
| Close (3:30-4:00 PM) | conservative | 3 | Real-time | 0.5% |

### 9.3 SECONDARY: Claude Desktop (MCP)

#### 9.3.1 Use Cases

1. **Performance Review** - "How did we do today?"
2. **Pattern Analysis** - "Which patterns performed best?"
3. **Trade Intervention** - "Close position X immediately"
4. **Strategy Optimization** - "What's the optimal risk_per_trade?"
5. **System Monitoring** - "Show me system health"

### 9.4 Failover & Redundancy

| Failure Type | Detection | Response | Recovery Time |
|--------------|-----------|----------|---------------|
| Single service down | Health check (15 min) | Auto-restart via Docker | < 2 minutes |
| Database connection lost | Query failure | Reconnect with backoff | < 30 seconds |
| Workflow service unresponsive | Cron HTTP timeout | Alert + manual review | < 5 minutes |
| Complete droplet failure | External monitoring | Manual intervention | 15-30 minutes |
| Claude Desktop offline | N/A (non-critical) | System continues via cron | N/A |

### 9.5 Manual Override Procedures

**Emergency Stop via SSH:**
```bash
# 1. SSH into droplet
ssh root@catalyst-droplet-ip

# 2. Stop trading immediately
curl -X POST http://localhost:5006/api/v1/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manual intervention - critical news"}'

# 3. Disable cron temporarily
crontab -r

# 4. Verify all positions closed
curl http://localhost:5006/api/v1/positions/active
```

---

## 10. Performance Requirements

### 10.1 Response Time Targets

| Operation | Target | Maximum | Notes |
|-----------|--------|---------|-------|
| MCP resource queries | 50ms | 200ms | Read-only data access |
| MCP tool executions | 100ms | 500ms | Command initiation |
| Workflow REST APIs | 200ms | 2s | Full workflow coordination |
| Market scans (100 candidates) | 5s | 10s | Scanner service |
| Pattern recognition | 500ms | 2s | Per symbol |
| Technical analysis | 300ms | 1s | Per symbol |
| News sentiment analysis | 200ms | 1s | Per article |
| Order execution (Alpaca) | 100ms | 1s | Market orders |

### 10.2 Throughput Requirements

| Metric | Requirement |
|--------|-------------|
| Cron workflow triggers per day | 10-15 (market hours) |
| Concurrent positions | 1-5 |
| Market scans per hour | 4-6 |
| Orders per day | 20 maximum |
| Claude MCP queries | Unlimited (read-only) |
| Database connections (pool) | 20 concurrent |

---

## 11. Security Requirements

### 11.1 API Security

- ✅ Environment variables for all credentials (never in code)
- ✅ HTTPS for external API calls (Alpaca, Benzinga)
- ✅ Local HTTP for internal services (Docker network)
- ✅ MCP authentication via Claude Desktop (local trust)
- ✅ Database credentials in `.env` (not version-controlled)

### 11.2 Data Security

- ✅ Encrypted backups (gzip compression)
- ✅ Secure credential storage (DigitalOcean secrets)
- ✅ Audit logging (all trade decisions logged)
- ✅ No PII collected (only trading data)

---

## 12. Cron Configuration Reference

### 12.1 Complete Crontab

```bash
# ============================================================================
# CATALYST TRADING SYSTEM - CRON CONFIGURATION
# ============================================================================
# Server timezone: Perth, Western Australia (AWST = UTC+8)
# US Market Hours: 9:30 AM - 4:00 PM EST
# Perth Equivalent: 10:30 PM - 5:00 AM AWST (next day)
# ============================================================================

CATALYST_HOME=/root/catalyst-trading-mcp

# ============================================================================
# TRADING OPERATIONS
# ============================================================================

# Pre-market startup (9:00 PM Perth = 4:00 AM EST)
0 21 * * 1-5 cd $CATALYST_HOME && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1

# Market open (10:30 PM Perth = 9:30 AM EST)
30 22 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -d '{"mode": "normal", "scan_frequency": 300, "max_positions": 5}' >> /var/log/catalyst/trading.log 2>&1

# Periodic scans (every 30 minutes during market hours)
0,30 23 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -d '{"mode": "normal"}' >> /var/log/catalyst/trading.log 2>&1
0,30 0-4 * * 2-6 curl -X POST http://localhost:5006/api/v1/workflow/start -d '{"mode": "normal"}' >> /var/log/catalyst/trading.log 2>&1

# Market close (5:00 AM Perth = 4:00 PM EST)
0 5 * * 2-6 curl -X POST http://localhost:5006/api/v1/workflow/start -d '{"mode": "conservative", "max_positions": 3}' >> /var/log/catalyst/trading.log 2>&1

# After-hours shutdown (9:00 AM Perth = 8:00 PM EST)
0 9 * * 2-6 cd $CATALYST_HOME && docker-compose stop >> /var/log/catalyst/shutdown.log 2>&1

# ============================================================================
# SYSTEM MAINTENANCE
# ============================================================================

# Health check (every 15 minutes, 24/7)
*/15 * * * * cd $CATALYST_HOME && /root/catalyst-trading-mcp/scripts/health-check.sh >> /var/log/catalyst/health.log 2>&1

# Database backup (daily 2:00 AM Perth)
0 2 * * * cd $CATALYST_HOME && docker-compose exec -T postgres pg_dump -U catalyst_user -d catalyst_trading | gzip > /backups/catalyst/catalyst_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz 2>&1

# Log rotation (weekly Sunday 3:00 AM)
0 3 * * 0 find /var/log/catalyst -name "*.log" -mtime +7 -delete
0 3 * * 0 find /backups/catalyst -name "*.sql.gz" -mtime +30 -delete

# Daily report (6:00 AM Perth)
0 6 * * * cd $CATALYST_HOME && docker-compose exec -T workflow curl http://localhost:5006/api/v1/workflow/history?limit=50 | python3 -m json.tool > /var/log/catalyst/daily_report_$(date +\%Y\%m\%d).json 2>&1

# ============================================================================
# MONITORING & ALERTS
# ============================================================================

# Auto-restart failed services (every 5 minutes)
*/5 * * * * cd $CATALYST_HOME && docker-compose ps | grep -q "Exit" && docker-compose up -d >> /var/log/catalyst/auto-restart.log 2>&1
```

### 12.2 Cron Schedule Summary

| Time (Perth) | Time (EST) | Action | Frequency |
|--------------|-----------|--------|-----------|
| 9:00 PM | 4:00 AM | Start services | Mon-Fri |
| 10:30 PM | 9:30 AM | Market open workflow | Mon-Fri |
| 11:00 PM - 4:30 AM | 10:00 AM - 3:30 PM | Periodic scans | Every 30 min |
| 5:00 AM | 4:00 PM | Market close workflow | Tue-Sat |
| 9:00 AM | 8:00 PM | Stop services | Tue-Sat |
| Every 15 min | Every 15 min | Health checks | 24/7 |
| 2:00 AM | 1:00 PM | Database backup | Daily |
| 3:00 AM Sun | 2:00 PM Sat | Log cleanup | Weekly |

---

## Conclusion

This comprehensive functional specification defines a **dual-initiation architecture** where:

1. **Cron automation** executes production trading workflows automatically (PRIMARY)
2. **Claude Desktop** provides intelligent monitoring and ML improvement (SECONDARY)

Both systems target the same backend services but serve different purposes:
- Cron **runs the business** (automated trading)
- Claude **improves the business** (pattern analysis, optimization)

This architecture ensures:
- ✅ Autonomous operation without human intervention
- ✅ Intelligent oversight for continuous improvement
- ✅ ML training data generation from every trade
- ✅ Manual override capability when needed
- ✅ Reliable production trading with monitoring

**The system is production-ready with both automation and intelligence working together.**

---

## Related Documents

- **architecture.md** - System architecture and deployment
- **database-schema.md** - 3NF normalized schema
- **deployment-guide.md** - Step-by-step deployment

---

**END OF FUNCTIONAL SPECIFICATION**

🎩 *Catalyst Trading System - Production Ready*
