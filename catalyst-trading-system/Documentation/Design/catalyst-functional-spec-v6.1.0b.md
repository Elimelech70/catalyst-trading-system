# Catalyst Trading System - Comprehensive Functional Specifications with Cron Automation

**Name of Application**: Catalyst Trading System  
**Name of file**: catalyst-functional-spec-with-cron-comprehensive.md  
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
- ⚠️ **BREAKING**: Research/ML moved to separate instance (future: research-functional-spec-v1.0.0)
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
9. **[WORKFLOW INITIATION & OPERATIONAL REQUIREMENTS](#9-workflow-initiation--operational-requirements)** ⭐ **NEW**
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

### 3.1 Read-Only Resources (Orchestration Service)

Claude Desktop accesses trading data through hierarchical MCP resources:

```yaml
trading-cycle://
├── trading-cycle://current
│   └── Current active cycle state, performance, positions
├── trading-cycle://history?limit=50
│   └── Historical cycle summaries
└── trading-cycle://performance
    └── Aggregate performance metrics

market-scan://
├── market-scan://latest
│   └── Most recent scan results
├── market-scan://candidates?status=active
│   └── Current trading candidates
└── market-scan://history?cycle_id=xxx
    └── Historical scan results for specific cycle

positions://
├── positions://active
│   └── All open positions with real-time P&L
├── positions://history?limit=100
│   └── Closed position history
└── positions://summary
    └── Position statistics and performance

news://
├── news://catalysts?hours=24
│   └── Recent catalyst events
├── news://sentiment?symbol=AAPL
│   └── News sentiment for specific security
└── news://trending
    └── Most mentioned securities in news

risk://
├── risk://limits
│   └── Current risk parameters and utilization
├── risk://violations
│   └── Risk limit violations history
└── risk://exposure
    └── Current portfolio exposure breakdown

reports://
├── reports://daily?date=2025-10-25
│   └── Daily performance report
├── reports://weekly
│   └── Weekly summary
└── reports://monthly
    └── Monthly performance review
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

## 9. WORKFLOW INITIATION & OPERATIONAL REQUIREMENTS

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
# Execute 100→35→20→10→5 candidate filtering
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
# Final conservative scan at market close
0 5 * * 2-6 curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "conservative", "max_positions": 3}' \
  >> /var/log/catalyst/trading.log 2>&1
```

##### After-Hours Shutdown
```bash
# 9:00 AM Perth = 8:00 PM EST
# Stop services after extended hours
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

#### 9.2.4 REST API Specification (Workflow Service)

**Endpoint**: `POST /api/v1/workflow/start`

**Request Body**:
```json
{
  "mode": "normal",
  "scan_frequency": 300,
  "max_positions": 5,
  "risk_per_trade": 0.01,
  "session_mode": "supervised"
}
```

**Response**:
```json
{
  "cycle_id": "20251025-093000-uuid",
  "status": "scanning",
  "mode": "normal",
  "started_at": "2025-10-25T09:30:00Z",
  "configuration": {
    "scan_frequency": 300,
    "max_positions": 5,
    "risk_per_trade": 0.01
  }
}
```

### 9.3 SECONDARY: Claude Desktop (Monitoring & ML)

#### 9.3.1 Architecture

```
┌──────────────────────────────────────────────────────┐
│           CLAUDE DESKTOP (Human-initiated)           │
│  - Manual analysis requests                          │
│  - ML training data queries                          │
│  - Manual trade overrides (rare)                     │
└───────────────────┬──────────────────────────────────┘
                    │
                    │ MCP Protocol
                    │ claude://localhost:5000
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│        ORCHESTRATION SERVICE (Port 5000)             │
│  - MCP resources (read-only data access)            │
│  - MCP tools (command execution)                    │
│  - Routes to Workflow via REST                      │
└───────────────────┬──────────────────────────────────┘
                    │
                    │ REST API
                    │ http://localhost:5006/api/v1/...
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│            WORKFLOW SERVICE (Port 5006)              │
│  (Same service that cron calls)                     │
└──────────────────────────────────────────────────────┘
```

#### 9.3.2 Five Primary Functions

**1. Performance Analysis**
```
Claude Query: "Why did our last 5 trades lose money?"

Process:
1. Read MCP resource: positions://history?limit=5&status=closed&pnl<0
2. Read MCP resource: news://catalysts (for each losing trade)
3. Analyze: Pattern quality, entry timing, risk:reward ratios
4. Generate: Human-readable insights with actionable recommendations
```

**2. ML Training Data Generation**
```
Claude Query: "Generate labeled dataset for bull flag pattern trades"

Process:
1. Read MCP resource: positions://history?pattern=bull_flag&limit=100
2. For each trade, compile:
   - Entry conditions (price, volume, indicators)
   - News sentiment at entry
   - Pattern confidence score
   - Outcome (win/loss, R:R achieved)
3. Export: CSV file for ML training
```

**3. Manual Trade Intervention**
```
Claude Query: "Close position X immediately - news changed"

Process:
1. Human identifies critical news not caught by system
2. Claude calls: emergency_stop(reason="FDA rejection news")
3. Workflow closes all positions
4. System logs decision for future improvement
```

**4. Strategy Parameter Optimization**
```
Claude Query: "What's the optimal risk_per_trade for bull flags?"

Process:
1. Read MCP resource: positions://history?pattern=bull_flag
2. Analyze: Win rate by risk_per_trade setting
3. Calculate: Kelly Criterion optimal position size
4. Recommend: Parameter updates with expected value improvement
```

**5. System Health Monitoring**
```
Claude Query: "Show me system health over last 24 hours"

Process:
1. Read MCP resources: 
   - trading-cycle://history?hours=24
   - risk://violations
   - reports://daily
2. Identify: Service failures, risk breaches, performance degradation
3. Report: Human-readable dashboard with alerts
```

#### 9.3.3 MCP Tool Specifications

See Section 4 for complete MCP tool definitions. Key tools:
- `start_trading_cycle()` - Manual workflow initiation
- `stop_trading_cycle()` - Manual workflow termination
- `emergency_stop()` - Immediate position closure
- `execute_trade()` - Manual trade entry (rare, supervised)
- `update_position()` - Stop loss / take profit adjustments

#### 9.3.4 MCP Resource Specifications

See Section 3 for complete MCP resource hierarchy. Key resources:
- `trading-cycle://current` - Active cycle state
- `positions://active` - Open positions with P&L
- `market-scan://latest` - Recent scan results
- `news://catalysts` - Catalyst events
- `reports://daily` - Performance metrics

### 9.4 Workflow Initiation Hierarchy

**Decision tree for workflow execution:**

```
1. SCHEDULED PRODUCTION TRADING (Highest Priority)
   - Trigger: Cron job fires at scheduled time
   - Target: POST /api/v1/workflow/start (port 5006)
   - Human Required: No
   - Example: 10:30 PM Perth cron initiates market open scan

2. MANUAL OVERSIGHT COMMAND (Medium Priority)
   - Trigger: Human asks Claude to start/stop cycle
   - Target: Claude calls MCP tool → Orchestration → Workflow
   - Human Required: Yes
   - Example: "Claude, stop trading - major news event"

3. EVENT-DRIVEN TRIGGER (Low Priority, Future)
   - Trigger: Critical news catalyst detected
   - Target: Workflow self-initiates emergency scan
   - Human Required: No
   - Example: FDA approval headline triggers immediate scan
   - Status: Not yet implemented
```

### 9.5 System Maintenance Automation

#### 9.5.1 Health Monitoring

```bash
# Health check every 15 minutes (24/7)
*/15 * * * * cd /root/catalyst-trading-mcp && \
  /root/catalyst-trading-mcp/scripts/health-check.sh \
  >> /var/log/catalyst/health.log 2>&1
```

**Health Check Script**:
- Verify all 9 services responding on their ports
- Check database connectivity
- Validate Redis pub/sub operational
- Test API response times
- Alert if any service down > 5 minutes

#### 9.5.2 Data Management

```bash
# Daily database backup (2:00 AM Perth)
0 2 * * * cd /root/catalyst-trading-mcp && \
  docker-compose exec -T postgres pg_dump -U catalyst_user \
  -d catalyst_trading | gzip > /backups/catalyst_$(date +\%Y\%m\%d).sql.gz \
  2>&1

# Log rotation (weekly, Sunday 3:00 AM)
0 3 * * 0 find /var/log/catalyst -name "*.log" -mtime +7 -delete

# Backup retention (keep 30 days)
0 3 * * 0 find /backups/catalyst -name "*.sql.gz" -mtime +30 -delete
```

#### 9.5.3 Reporting

```bash
# Daily performance report (6:00 AM Perth)
0 6 * * * cd /root/catalyst-trading-mcp && \
  docker-compose exec -T workflow \
  curl http://localhost:5006/api/v1/workflow/history?limit=50 | \
  python3 -m json.tool > /var/log/catalyst/daily_report_$(date +\%Y\%m\%d).json \
  2>&1
```

### 9.6 Operational Requirements

#### 9.6.1 Production Environment

**Required Infrastructure**:
- DigitalOcean Droplet (minimum 4GB RAM, 2 vCPUs)
- Docker & Docker Compose installed
- Cron daemon running
- PostgreSQL managed database (DigitalOcean managed)
- Persistent storage for backups (minimum 50GB)

**System Access**:
- SSH access for cron configuration
- Docker permissions for service management
- Database credentials in `.env` file (not version-controlled)

#### 9.6.2 Deployment Checklist

```bash
# 1. Install cron configuration
crontab -e  # Paste from catalyst-cron-setup.txt

# 2. Verify cron installation
crontab -l

# 3. Create required directories
mkdir -p /var/log/catalyst /backups/catalyst

# 4. Set permissions
chmod +x /root/catalyst-trading-mcp/scripts/*.sh

# 5. Test manual workflow trigger
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}'

# 6. Monitor first automated trigger
tail -f /var/log/catalyst/trading.log
```

#### 9.6.3 Monitoring Requirements

**Critical Metrics** (monitored via cron health checks):
- Workflow service availability (port 5006) - Response time < 500ms
- Database connectivity - Query time < 100ms
- Docker container status - All 9 services "healthy"
- Disk space - > 10% free space required
- API response times - < 2s for workflow execution

**Alerting Thresholds**:
- Service down > 5 minutes → Auto-restart via cron
- Database connection failure → Email alert immediately
- Disk space < 10% → Cleanup old logs
- Workflow failure rate > 20% → Manual review required

### 9.7 Integration: Cron ↔ Claude Desktop

#### 9.7.1 Data Flow for ML Improvement

```
1. CRON EXECUTES WORKFLOW (Primary)
   ├─ Scanner finds 100 candidates
   ├─ Filters to 35 → 20 → 10 → 5
   ├─ Executes trades on top 5
   ├─ Stores results in PostgreSQL database
   └─ Logs every decision (for ML training)
   
2. CLAUDE DESKTOP ANALYZES (Secondary)
   ├─ Reads workflow history via MCP resources
   ├─ Analyzes win/loss patterns
   ├─ Identifies optimal parameters
   ├─ Generates labeled training datasets
   └─ Recommends strategy improvements
   
3. SYSTEM IMPROVEMENT CYCLE
   ├─ Human reviews Claude's analysis
   ├─ Updates strategy parameters in Workflow config
   ├─ Deploys improved configuration
   └─ Cron continues with new parameters
```

#### 9.7.2 Claude Desktop Analysis Query Examples

**Example 1: Pattern Performance Analysis**
```
User: "Claude, analyze the performance of bull flag patterns over the last month"

Claude Process:
1. Read MCP resource: positions://history?pattern=bull_flag&days=30
2. Calculate:
   - Win rate: 12 wins / 18 trades = 66.7%
   - Average R:R: 2.3
   - Profit factor: $5,400 wins / $2,100 losses = 2.57
3. Read MCP resource: news://catalysts for each bull flag trade
4. Correlation analysis: News sentiment vs trade outcome
5. Generate report:
   "Bull flags with positive catalyst score >0.7 have 85% win rate.
    Recommend: Increase catalyst_score_threshold to 0.7 for this pattern."
```

**Example 2: Risk Parameter Optimization**
```
User: "What's our optimal position size for day trading?"

Claude Process:
1. Read MCP resource: positions://history?limit=100
2. Calculate Kelly Criterion:
   - Win rate: 62%
   - Avg win/loss ratio: 1.8
   - Kelly = W - [(1-W)/R] = 0.62 - (0.38/1.8) = 0.41
3. Current risk_per_trade: 1.0%
4. Recommendation: "Kelly suggests 41% but conservative is 20% Kelly = 8.2% per trade.
   Current 1% is ultra-conservative. Recommend increasing to 2-3% for optimal growth."
```

#### 9.7.3 ML Training Dataset Generation

**Process**:
```python
# Claude generates this programmatically via MCP
async def generate_training_dataset():
    # 1. Fetch all completed trades
    trades = await mcp.read_resource("positions://history?limit=1000")
    
    # 2. For each trade, compile features
    dataset = []
    for trade in trades:
        features = {
            # Entry conditions
            "entry_price": trade.entry_price,
            "volume_20d_avg": trade.volume_avg,
            "rsi_14": trade.rsi_at_entry,
            "macd_signal": trade.macd_signal,
            
            # News context
            "catalyst_score": trade.catalyst_score,
            "sentiment_score": trade.sentiment,
            "news_volume": trade.news_count,
            
            # Pattern
            "pattern_type": trade.pattern,
            "pattern_confidence": trade.confidence,
            
            # Outcome (label)
            "outcome": "win" if trade.realized_pnl > 0 else "loss",
            "r_multiple": trade.realized_pnl / trade.risk_amount
        }
        dataset.append(features)
    
    # 3. Export to CSV
    df = pd.DataFrame(dataset)
    df.to_csv("training_data_20251025.csv")
    
    return f"Generated {len(dataset)} training examples"
```

### 9.8 Configuration Management

#### 9.8.1 Cron Configuration File

**Location**: `/root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt`

**Installation**:
```bash
# Method 1: Edit crontab directly
crontab -e
# Paste contents from catalyst-cron-setup.txt

# Method 2: Install from file
crontab /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt

# Verify installation
crontab -l
```

#### 9.8.2 Environment Variables

**File**: `.env` (NOT version-controlled)

```bash
# Workflow Service
WORKFLOW_PORT=5006
WORKFLOW_LOG_LEVEL=INFO

# Trading Configuration
DEFAULT_MODE=normal
DEFAULT_SCAN_FREQUENCY=300
DEFAULT_MAX_POSITIONS=5
DEFAULT_RISK_PER_TRADE=0.01

# Market Hours (Perth AWST for US EST markets)
MARKET_OPEN_CRON="30 22 * * 1-5"
MARKET_CLOSE_CRON="0 5 * * 2-6"

# Database
DATABASE_URL=postgresql://catalyst_user:password@hostname:25060/catalyst_trading
DATABASE_POOL_SIZE=20

# External APIs
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # or live

BENZINGA_API_KEY=xxx
NEWSAPI_KEY=xxx
```

### 9.9 Failover & Redundancy

#### 9.9.1 Failure Scenarios

| Failure Type | Detection | Response | Recovery Time |
|--------------|-----------|----------|---------------|
| Single service down | Health check (15 min) | Auto-restart via Docker | < 2 minutes |
| Database connection lost | Query failure | Reconnect with backoff | < 30 seconds |
| Workflow service unresponsive | Cron HTTP timeout | Alert + manual review | < 5 minutes |
| Complete droplet failure | External monitoring | Manual intervention | 15-30 minutes |
| Claude Desktop offline | N/A (non-critical) | System continues via cron | N/A |

#### 9.9.2 Manual Override Procedures

**Emergency Stop via SSH**:
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

**Re-enable After Issue Resolved**:
```bash
# 1. Restore cron configuration
crontab /root/catalyst-trading-mcp/scripts/catalyst-cron-setup.txt

# 2. Verify services healthy
curl http://localhost:5006/health

# 3. Test workflow manually
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -d '{"mode": "conservative", "max_positions": 1}'

# 4. Monitor logs
tail -f /var/log/catalyst/trading.log
```

### 9.10 Summary: Workflow Initiation Architecture

**Key Takeaways:**

1. **Cron automation is PRIMARY** - Runs production trading 10+ times/day automatically
2. **Claude Desktop is SECONDARY** - Provides monitoring, analysis, and ML improvement
3. **Both target same Workflow service** - Different protocols (REST vs MCP) but same backend
4. **Human intervention is optional** - System operates autonomously, humans improve it
5. **ML improvement is continuous** - Every trade generates training data Claude analyzes

**Analogy:**
```
Cron Automation = Factory floor workers (run production)
Claude Desktop = Factory engineers (improve production)

Both are essential, but the factory runs without engineers.
Engineers make the factory better over time.
```

This architecture ensures:
- ✅ **Autonomous operation** - Trades happen automatically
- ✅ **Intelligent oversight** - Claude monitors for issues
- ✅ **Continuous improvement** - ML training data constantly generated
- ✅ **Human control** - Manual override always available
- ✅ **Reliability** - No single point of failure (cron + monitoring)

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

### 12.1 Complete Cron File

**File**: `catalyst-cron-setup.txt`

```bash
# ============================================================================
# Catalyst Trading System - Production Cron Configuration
# ============================================================================
# Install: crontab -e (paste this content)
# View: crontab -l
# Logs: tail -f /var/log/catalyst/*.log
#
# Server Timezone: Perth (AWST = UTC+8)
# Market Hours: US Markets 9:30 AM - 4:00 PM EST
# Perth Equivalent: 10:30 PM - 5:00 AM AWST (next day)
# ============================================================================

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
SHELL=/bin/bash
HOME=/root
CATALYST_HOME=/root/catalyst-trading-mcp

# ============================================================================
# MARKET HOURS AUTOMATION
# ============================================================================

# Pre-market startup (9:00 PM Perth = 4:00 AM EST)
0 21 * * 1-5 cd $CATALYST_HOME && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1

# Market open (10:30 PM Perth = 9:30 AM EST)
30 22 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode": "normal"}' >> /var/log/catalyst/trading.log 2>&1

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

**END OF COMPREHENSIVE FUNCTIONAL SPECIFICATION**

🎩 **DevGenius Status**: Complete functional spec with cron automation documented! 🚀
