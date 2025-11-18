# Catalyst Trading System - Architecture v6.0

**Name of Application**: Catalyst Trading System  
**Name of file**: architecture-mcp-v60.md  
**Version**: 6.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: System architecture for Production trading system
**Scope**: PRODUCTION ARCHITECTURE ONLY

---

## REVISION HISTORY

**v6.0.0 (2025-10-25)** - PRODUCTION ARCHITECTURE CLEAN SEPARATION
- ✅ **MAJOR CHANGE**: Research services removed entirely
- ✅ 9-service microservices (no ML/Research services)
- ✅ Single DigitalOcean droplet deployment
- ✅ MCP protocol for Claude Desktop integration
- ✅ REST APIs for inter-service communication
- ⚠️ **BREAKING**: Research architecture → research-architecture-v10.md (future)

**v5.0.0 (2025-10-22)** - 9-Service Split (superseded)
- Mixed Production + future Research services

**v4.1.0 (2025-08-31)** - 7-Service Architecture (superseded)
- Combined Orchestration + Workflow

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

### **OUT OF SCOPE (Future Research Architecture)**
❌ ML Training Service (research-architecture-v10.md)  
❌ Pattern Discovery Service (research-architecture-v10.md)  
❌ Backtest Engine (research-architecture-v10.md)  
❌ Multi-Agent Coordinator (research-architecture-v10.md)  
❌ Separate Research droplet (research-architecture-v10.md)  
❌ Multi-agent AI APIs (Claude + GPT-4 + Perplexity + Gemini)  

**REASON**: Production-first, complete working system fast, Research built later.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Service Architecture](#2-service-architecture)
3. [Communication Patterns](#3-communication-patterns)
4. [Data Architecture](#4-data-architecture)
5. [Deployment Architecture](#5-deployment-architecture)
6. [Security Architecture](#6-security-architecture)
7. [Performance Architecture](#7-performance-architecture)
8. [Reliability Architecture](#8-reliability-architecture)

---

## 1. Architecture Overview

### 1.1 Architecture Philosophy

```yaml
Design Principles:
  - Production-first: Complete working system in 8 weeks
  - Single instance: No premature scaling complexity
  - Proven tech: Docker Compose, PostgreSQL, Redis
  - Clean separation: MCP vs REST, concerns isolated
  - Fail-safe: Risk management enforced at multiple layers
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
│  │                                                       │ │
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
│                       │ Database Queries + Redis Pub/Sub    │
│                       ▼                                     │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ INFRASTRUCTURE SERVICES                                │ │
│  │                                                       │ │
│  │  ┌─────────────────────┐  ┌──────────────────────┐  │ │
│  │  │ Redis (6379)        │  │ Health Monitor       │  │ │
│  │  │ - Pub/sub           │  │ - Service checks     │  │ │
│  │  │ - Caching           │  │ - Metrics            │  │ │
│  │  └─────────────────────┘  └──────────────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────┘
                           │ Private Network
                           │ (Connection String)
┌──────────────────────────▼───────────────────────────────────┐
│             DATA LAYER                                        │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ DigitalOcean Managed PostgreSQL                       │  │
│  │ - Database: catalyst_trading_production               │  │
│  │ - Schema: v6.0 (normalized 3NF)                       │  │
│  │ - Size: 1vCPU, 1GB RAM, 10GB storage                 │  │
│  │ - Backups: Automated daily                            │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
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
                      │  Trading  │
                      └─────┬─────┘
                            │
                      ┌─────▼─────┐
                      │ Reporting │
                      └───────────┘
```

### 2.3 Service Responsibilities

#### **1. Orchestration Service (Port 5000)**

**Role**: MCP protocol interface for Claude Desktop

**Responsibilities**:
- Expose MCP resources (hierarchical URIs)
- Expose MCP tools (trading actions)
- Route requests to Workflow service
- Return structured responses to Claude
- Handle MCP protocol lifecycle

**Does NOT**:
- Execute business logic (delegates to Workflow)
- Access database directly (calls REST services)
- Make trading decisions (presents options)

**Technology Stack**:
```yaml
Framework: FastMCP (Anthropic)
HTTP: FastAPI
Protocol: MCP (Model Context Protocol)
Communication: REST client (httpx)
```

**Key Endpoints**:
```
MCP Resources:
  - trading-cycle/current
  - trading-cycle/{cycle_id}/timeline
  - market-scan/latest
  - market-scan/candidates/{symbol}
  - positions/current
  - positions/{position_id}/status
  - performance/daily
  - performance/weekly
  - alerts/active

MCP Tools:
  - start_trading_session()
  - stop_trading_session()
  - get_scan_results()
  - get_candidate_analysis()
  - execute_trade()
  - close_position()
  - update_risk_parameter()
  - get_risk_status()
  - get_performance_report()
  - get_trade_journal()
```

#### **2. Scanner Service (Port 5001)**

**Role**: Multi-stage market filtering (100 → 5 candidates)

**Responsibilities**:
- Universe selection (50-100 active stocks)
- News catalyst filtering (35 stocks with catalysts)
- Technical filtering (20 stocks meeting criteria)
- Pattern confirmation (10 stocks with setups)
- Final ranking (5 top candidates)

**Filtering Pipeline**:
```
Stage 1: Universe (100 stocks)
  - Volume > 1M shares/day
  - Price > $5
  - News in last 24 hours
  ↓
Stage 2: Catalyst Filter (35 stocks)
  - catalyst_strength > 0.7
  - sentiment_score > 0.5
  ↓
Stage 3: Technical Filter (20 stocks)
  - Price above SMA 20
  - RSI between 40-70
  - Volume > 1.5x average
  ↓
Stage 4: Pattern Filter (10 stocks)
  - Recognized chart pattern
  - Pattern confidence > 0.7
  ↓
Stage 5: Final Ranking (5 stocks)
  - Composite score calculation
  - Risk/reward assessment
```

**Technology Stack**:
```yaml
Framework: FastAPI
Database: asyncpg (PostgreSQL)
Cache: Redis
External APIs: None (uses News/Technical/Pattern services)
```

#### **3. Pattern Service (Port 5002)**

**Role**: Technical chart pattern detection

**Responsibilities**:
- Identify chart patterns (bull flag, cup & handle, etc.)
- Calculate pattern confidence scores
- Determine support/resistance levels
- Provide entry/exit recommendations
- Detect breakout signals

**Patterns Detected**:
- Bull flag (momentum continuation)
- Cup and handle (accumulation)
- Ascending triangle (bullish breakout)
- ABCD pattern (measured move)
- Opening range breakout (ORB)

**Technology Stack**:
```yaml
Framework: FastAPI
Analysis: NumPy, SciPy
Database: asyncpg (PostgreSQL)
Cache: Redis (pattern results cached 5 min)
```

#### **4. Technical Service (Port 5003)**

**Role**: Technical indicator calculation

**Responsibilities**:
- Calculate moving averages (SMA, EMA)
- Calculate momentum indicators (RSI, MACD)
- Calculate volatility (ATR, Bollinger Bands)
- Analyze volume (OBV, volume ratio)
- Identify support/resistance levels

**Indicators Calculated**:
```yaml
Moving Averages: SMA 20, 50, 200 | EMA 9, 21
Momentum: RSI 14, MACD (12,26,9)
Volatility: ATR 14, Bollinger Bands (20,2)
Volume: OBV, Volume Ratio (vs 20-day avg)
Levels: Dynamic support/resistance
```

**Technology Stack**:
```yaml
Framework: FastAPI
Analysis: TA-Lib (technical analysis library)
Database: asyncpg (PostgreSQL)
Cache: Redis (indicators cached 5 min)
Storage: technical_indicators table
```

#### **5. Risk Manager Service (Port 5004)**

**Role**: Risk validation and enforcement

**Responsibilities**:
- Pre-trade risk validation
- Position size calculation (Kelly criterion)
- Daily loss limit monitoring
- Correlation checks
- Emergency stop execution

**Risk Checks**:
```yaml
Pre-Trade:
  - Daily loss limit (default: $2,000)
  - Position size limit (max 20% capital)
  - Max positions (default: 5)
  - Correlation check (max 0.7 between positions)
  - Stop loss validation (2x ATR or support)

Real-Time:
  - Continuous P&L monitoring
  - Position exposure tracking
  - Warning threshold alerts (75% of limits)
  - Critical threshold enforcement (100% of limits)
```

**Configuration**:
```yaml
Source: config/risk_parameters.yaml
Hot-reload: Yes (no restart required)
Validation: Pydantic models
Override: Via MCP tool or config file edit
```

**Technology Stack**:
```yaml
Framework: FastAPI
Database: asyncpg (PostgreSQL)
Cache: Redis (risk state cached)
Config: PyYAML + Pydantic
```

#### **6. Trading Service (Port 5005)**

**Role**: Order execution via Alpaca Markets

**Responsibilities**:
- Submit orders to Alpaca API
- Track order status (WebSocket)
- Confirm fills
- Manage positions
- Handle order errors

**Alpaca Integration**:
```yaml
Live Trading: api.alpaca.markets
Paper Trading: paper-api.alpaca.markets
WebSocket: wss://stream.data.alpaca.markets
Authentication: API Key + Secret

Order Types:
  - Market (immediate execution)
  - Limit (price protection)
  - Stop (stop loss)
  - Bracket (entry + stop + target combined)
```

**Technology Stack**:
```yaml
Framework: FastAPI
Alpaca SDK: alpaca-trade-api
Database: asyncpg (PostgreSQL)
WebSocket: asyncio (real-time updates)
```

#### **7. Workflow Service (Port 5006)**

**Role**: Trade workflow coordination

**Responsibilities**:
- Orchestrate daily trading cycle
- Coordinate service calls (Scanner → Pattern → Technical → Trading)
- Manage workflow state machine
- Log decisions (for ML training)
- Trigger scheduled workflows

**Workflow Phases**:
```yaml
08:00 ET - Pre-market scan:
  1. Call News service (get catalysts)
  2. Call Scanner service (filter candidates)
  3. Store results in database
  4. Notify Orchestration (Redis pub/sub)

09:30 ET - Market open:
  1. Monitor for Claude Desktop requests
  2. Coordinate trade execution via Trading service
  3. Log decisions to decision_logs table

Trading Hours - Position monitoring:
  1. Update position P&L every 1 minute
  2. Check risk limits via Risk Manager
  3. Send alerts if needed

15:30 ET - Market close:
  1. Close all open positions
  2. Reconcile with Alpaca
  3. Call Reporting service
  4. Send daily summary email
```

**Technology Stack**:
```yaml
Framework: FastAPI
Scheduler: APScheduler (cron triggers)
Database: asyncpg (PostgreSQL)
Pub/Sub: Redis
State Machine: Python Enum (cycle_state)
```

#### **8. News Service (Port 5008)**

**Role**: News catalyst intelligence

**Responsibilities**:
- Aggregate news from multiple sources
- Sentiment analysis (positive/negative/neutral)
- Catalyst classification (earnings, FDA, merger, etc.)
- Source reliability scoring
- Real-time monitoring

**News Sources**:
```yaml
Primary: Benzinga News API (paid)
Backup: NewsAPI (free tier)
Real-time: Alpaca News API
Filings: SEC EDGAR (free)
```

**Sentiment Analysis**:
```yaml
Model: FinBERT (Hugging Face transformer)
Scoring: -1.0 (negative) to +1.0 (positive)
Labels: positive, negative, neutral
Catalyst Detection: Keyword + regex patterns
```

**Technology Stack**:
```yaml
Framework: FastAPI
NLP: transformers (FinBERT)
Database: asyncpg (PostgreSQL)
Cache: Redis
External APIs: Benzinga, NewsAPI, Alpaca
```

#### **9. Reporting Service (Port 5009)**

**Role**: Performance analytics and reporting

**Responsibilities**:
- Calculate daily/weekly/monthly P&L
- Compute performance metrics (Sharpe, win rate, etc.)
- Generate trade journal
- Create PDF reports (future)
- Send email summaries

**Metrics Calculated**:
```yaml
Performance:
  - Daily P&L (absolute + percentage)
  - Win rate (wins / total trades)
  - Profit factor (gross profit / gross loss)
  - Sharpe ratio (risk-adjusted return)
  - Max drawdown (peak to trough)

Trade Analysis:
  - Average win size
  - Average loss size
  - Largest win/loss
  - Average hold time
  - Best/worst patterns
```

**Technology Stack**:
```yaml
Framework: FastAPI
Analysis: Pandas, NumPy
Database: asyncpg (PostgreSQL)
Email: SMTP (DigitalOcean Email)
Reports: Future (ReportLab PDF generation)
```

---

## 3. Communication Patterns

### 3.1 MCP Protocol (Claude Desktop ↔ Orchestration)

**Protocol**: Model Context Protocol (MCP)  
**Transport**: HTTPS (443)  
**Format**: JSON-RPC 2.0  
**Authentication**: API Key (custom header)

**Request Flow**:
```
1. Claude Desktop → Nginx (HTTPS, port 443)
2. Nginx → Orchestration (HTTP, port 5000)
3. Orchestration → Workflow (REST, port 5006)
4. Workflow → Other services (REST)
5. Response bubbles back up
```

**Example MCP Tool Call**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_trade",
    "arguments": {
      "symbol": "TSLA",
      "side": "buy",
      "quantity": 50
    }
  },
  "id": 1
}
```

### 3.2 REST APIs (Internal Service Communication)

**Protocol**: HTTP REST  
**Format**: JSON  
**Authentication**: API Key (X-API-Key header)  
**Network**: Docker bridge network (internal)

**Standard Request/Response**:
```python
# Request
POST http://scanner:5001/api/v1/scan/start
Headers:
  X-API-Key: <service-api-key>
  Content-Type: application/json
Body:
  {
    "cycle_id": "uuid",
    "universe_size": 100
  }

# Response (200 OK)
{
  "scan_id": "uuid",
  "status": "started",
  "estimated_completion": "2025-10-25T08:05:00Z"
}

# Error Response (400 Bad Request)
{
  "error": {
    "code": "INVALID_UNIVERSE_SIZE",
    "message": "Universe size must be between 50 and 200",
    "details": {"provided": 10, "min": 50, "max": 200}
  }
}
```

### 3.3 Database Access Pattern

**All services use connection pooling:**

```python
# Database pool configuration
db_pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=5,  # Per service (9 services = 45 connections max)
    command_timeout=10.0
)

# Usage pattern
async with db_pool.acquire() as conn:
    result = await conn.fetchrow(query, *params)
```

**Query Pattern (Always use FKs)**:
```python
# ✅ CORRECT: Use helper function + FK
security_id = await conn.fetchval(
    "SELECT get_or_create_security($1)", symbol
)
await conn.execute("""
    INSERT INTO positions (cycle_id, security_id, ...)
    VALUES ($1, $2, ...)
""", cycle_id, security_id, ...)

# ❌ WRONG: Store symbol directly
await conn.execute("""
    INSERT INTO positions (cycle_id, symbol, ...)
    VALUES ($1, $2, ...)
""", cycle_id, symbol, ...)  # NO! Use security_id FK!
```

### 3.4 Redis Pub/Sub Pattern

**Used for real-time event notifications:**

```python
# Publisher (e.g., Scanner Service)
await redis.publish(
    "catalyst:scan_complete",
    json.dumps({
        "cycle_id": cycle_id,
        "candidates_count": 5,
        "timestamp": datetime.now().isoformat()
    })
)

# Subscriber (e.g., Orchestration Service)
pubsub = redis.pubsub()
await pubsub.subscribe("catalyst:scan_complete")

async for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        # Notify Claude Desktop via MCP
```

**Redis Channels**:
```yaml
catalyst:scan_complete - Scanner finished
catalyst:position_update - Position P&L changed
catalyst:risk_alert - Risk threshold reached
catalyst:order_filled - Order execution confirmed
catalyst:news_catalyst - High-strength catalyst detected
```

---

## 4. Data Architecture

### 4.1 Database Design Philosophy

**Normalization Level**: 3NF (Third Normal Form)  
**Key Principle**: Security_id FK everywhere, NO symbol VARCHAR duplication  
**Query Strategy**: Always JOIN to get human-readable data

**Master Tables**:
- `securities` - Single source of truth for symbols
- `sectors` - GICS sector master data
- `time_dimension` - Time as its own entity

**Fact Tables (Time-Series)**:
- `trading_history` - OHLCV bars (security_id + time_id FKs)
- `news_sentiment` - News events (security_id + time_id FKs)
- `technical_indicators` - Indicators (security_id + time_id FKs)

**Trading Tables**:
- `trading_cycles` - Daily workflow state
- `positions` - Trading positions (security_id FK)
- `orders` - Order execution (security_id FK)
- `scan_results` - Candidates (security_id FK)
- `risk_events` - Risk management log

### 4.2 Data Flow

```
External APIs → Services → Database
                   ↓
         Helper Functions
    (get_or_create_security)
    (get_or_create_time)
                   ↓
         Normalized Storage
      (security_id FK everywhere)
                   ↓
         Query with JOINs
      (get symbol from securities table)
```

### 4.3 Caching Strategy

**Redis Cache Layers**:

```yaml
Layer 1 - Hot Data (TTL: 1 min):
  - Latest prices (v_securities_latest)
  - Open positions
  - Current risk status

Layer 2 - Warm Data (TTL: 5 min):
  - Technical indicators
  - Scan results
  - News sentiment scores

Layer 3 - Cold Data (TTL: 1 hour):
  - Performance metrics
  - Historical patterns
  - Sector correlations
```

**Cache Invalidation**:
- On database write: Invalidate related keys
- On time boundary: Refresh materialized views
- On demand: Manual refresh via API

---

## 5. Deployment Architecture

### 5.1 Single Droplet Architecture

```
┌─────────────────────────────────────────────────────┐
│ DigitalOcean Droplet                                │
│ sfo3 region                                         │
│ 4vCPU, 8GB RAM, 160GB SSD                           │
│ Ubuntu 22.04 LTS                                    │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │ Docker Compose Orchestration                  │ │
│  │                                               │ │
│  │  [Nginx] [Redis] [9 Services]                │ │
│  │                                               │ │
│  │  Network: catalyst-network (172.18.0.0/16)   │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │ System Services                               │ │
│  │ - Docker Engine                               │ │
│  │ - UFW Firewall                                │ │
│  │ - Systemd (service management)                │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                        ↓
         Private Network (Connection String)
                        ↓
┌─────────────────────────────────────────────────────┐
│ DigitalOcean Managed PostgreSQL                     │
│ 1vCPU, 1GB RAM, 10GB Storage                        │
│ PostgreSQL 15                                       │
│ Automated daily backups                             │
└─────────────────────────────────────────────────────┘
```

### 5.2 Docker Compose Configuration

**File**: `docker-compose.yml`

```yaml
version: '3.8'

networks:
  catalyst-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.18.0.0/16

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - catalyst-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  orchestration:
    build: ./services/orchestration
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    networks:
      - catalyst-network

  scanner:
    build: ./services/scanner
    ports:
      - "5001:5001"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - news
    networks:
      - catalyst-network

  # ... other 7 services ...

volumes:
  redis-data:
```

### 5.3 Service Startup Sequence

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
```

---

## 6. Security Architecture

### 6.1 Network Security

**Firewall Configuration** (UFW):
```bash
# Only SSH and HTTPS allowed from outside
ufw allow 22/tcp   # SSH
ufw allow 443/tcp  # HTTPS
ufw default deny incoming
ufw default allow outgoing
ufw enable
```

**Docker Network Isolation**:
- Internal bridge network (172.18.0.0/16)
- Services cannot be accessed from outside except via Nginx
- PostgreSQL connection via private network (DigitalOcean)

### 6.2 Authentication & Authorization

**External (Claude Desktop)**:
```yaml
Transport: HTTPS (TLS 1.3)
Auth: API Key in custom header
Validation: Nginx → checks key before routing
Rotation: Quarterly
```

**Internal (Service-to-Service)**:
```yaml
Transport: HTTP (Docker network, isolated)
Auth: API Key (X-API-Key header)
Validation: Each service validates keys
Keys: Unique per service
```

**Database**:
```yaml
Transport: SSL/TLS (enforced)
Auth: Username + Password
Credentials: Environment variables only
Access: Firewall (only droplet IP allowed)
```

### 6.3 Secrets Management

**Environment Variables**:
```bash
# .env.prod (NEVER commit to Git!)
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
ALPACA_API_KEY=<encrypted>
ALPACA_SECRET_KEY=<encrypted>
NEWS_API_KEY=<encrypted>
BENZINGA_API_KEY=<encrypted>
ORCHESTRATION_API_KEY=<encrypted>
```

**Secret Injection**:
```yaml
Development: .env file
Production: DigitalOcean environment variables
Deployment: Injected at container startup
Storage: Never in code, never in Git
```

### 6.4 Audit Logging

**All critical actions logged**:
```python
logger.info(
    "Trade executed",
    extra={
        "user": "claude_desktop",
        "symbol": "TSLA",
        "side": "buy",
        "quantity": 50,
        "order_id": order_id,
        "risk_validated": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
)
```

**Log Retention**:
- Application logs: 90 days (rotating)
- Audit logs: 7 years (regulatory)
- Database logs: Via PostgreSQL (managed by DigitalOcean)

---

## 7. Performance Architecture

### 7.1 Response Time Budget

**End-to-end latency (Claude Desktop → Response)**:
```
User request (MCP)
  → Nginx (10ms SSL termination)
  → Orchestration (50ms)
  → Workflow (100ms coordination)
  → Services (200ms business logic)
  → Database (50ms query)
Total: ~410ms (target <500ms)
```

### 7.2 Concurrency Model

**Per Service**:
```yaml
Workers: 4 (Gunicorn/Uvicorn)
Async: asyncio (Python)
Database Pool: 2-5 connections per service
Redis Pool: 10 connections per service
```

**System Total**:
```yaml
Services: 9
Total Workers: 36
Total DB Connections: 45 (out of 100 available)
CPU Usage: 50-70% during market hours
Memory Usage: 6GB out of 8GB
```

### 7.3 Caching Strategy

**Three-tier cache**:
```
1. In-memory (service local): 1-min TTL
2. Redis (shared): 5-min TTL
3. Materialized views (PostgreSQL): Refresh every 5 min
```

**Cache Hit Ratios (Target)**:
- Latest prices: >95%
- Technical indicators: >90%
- Scan results: >85%

### 7.4 Database Optimization

**Query Optimization**:
- All tables have appropriate indexes
- Composite indexes for common join patterns
- Partial indexes for filtered queries (e.g., WHERE status='open')
- Materialized views for expensive aggregations

**Connection Pooling**:
```python
# Per service
Pool Size: 2-5 connections
Timeout: 10 seconds
Max Overflow: 0 (no burst)

# System total
45 connections / 100 available = 45% utilization (safe)
```

---

## 8. Reliability Architecture

### 8.1 Health Checks

**Every service exposes**:
```
GET /health

Response:
{
  "status": "healthy",
  "service": "scanner",
  "version": "6.0.0",
  "timestamp": "2025-10-25T14:30:00Z",
  "database": "connected",
  "redis": "connected",
  "dependencies": {
    "news": "healthy",
    "technical": "healthy",
    "pattern": "healthy"
  }
}
```

**Health Check Schedule**:
- Docker: Every 30 seconds
- Nginx: Every 10 seconds (upstream checks)
- Monitoring script: Every 60 seconds (full system)

### 8.2 Error Handling

**Graceful Degradation**:
```yaml
News API down:
  → Use cached news
  → Log warning
  → Reduce universe size
  → Continue trading

Database slow query:
  → Timeout after 10s
  → Return cached data
  → Log slow query warning
  → Alert if persistent

Alpaca API error:
  → Retry with exponential backoff (3 attempts)
  → Log error with context
  → Reject trade if all retries fail
  → Alert trader via email
```

### 8.3 Circuit Breakers

**External API Protection**:
```python
# Circuit breaker for Alpaca API
circuit_breaker = CircuitBreaker(
    failure_threshold=5,    # Open after 5 failures
    recovery_timeout=60,    # Try again after 60s
    expected_exception=AlpacaAPIError
)

@circuit_breaker
async def submit_order(...):
    # If circuit open, raises CircuitBreakerOpen immediately
    # If closed, attempts order submission
    pass
```

### 8.4 Failover Strategy

**Single Point of Failure**: DigitalOcean Droplet

**Mitigation**:
```yaml
Backups:
  - Daily database backups (DigitalOcean managed)
  - Weekly droplet snapshots
  - Configuration backed up to Git

Recovery:
  - Provision new droplet from snapshot (5 min)
  - Restore database from backup if needed (10 min)
  - Update DNS if using domain (5 min)
  - Total RTO: ~20 minutes

Acceptable: Single-user system, trading hours only (6.5h/day)
```

---

## 9. Monitoring Architecture

### 9.1 Metrics Collection

**System Metrics**:
```yaml
CPU: Per container (docker stats)
Memory: Per container
Network: Bytes in/out
Disk: I/O operations

Target:
  CPU: <70% average
  Memory: <75% average
  Disk I/O: <50% capacity
```

**Application Metrics**:
```yaml
Response Times: p50, p95, p99
Error Rates: Errors per minute
Request Rates: Requests per second
Database: Query times, connection pool utilization
```

### 9.2 Logging Architecture

**Structured Logging**:
```python
# All services use structured JSON logging
import structlog

logger = structlog.get_logger()

logger.info(
    "order_executed",
    symbol="TSLA",
    quantity=50,
    order_id=order_id,
    execution_time_ms=125
)

# Output (JSON)
{
  "event": "order_executed",
  "symbol": "TSLA",
  "quantity": 50,
  "order_id": "...",
  "execution_time_ms": 125,
  "timestamp": "2025-10-25T14:30:15Z",
  "service": "trading",
  "level": "info"
}
```

**Log Aggregation**:
```
Docker containers → stdout/stderr
  → Docker logging driver
  → DigitalOcean Logs (future)
  → Local files (90-day retention)
```

### 9.3 Alerting

**Alert Channels**:
- Email: Critical alerts (DigitalOcean Email Service)
- Logs: All events (for later analysis)

**Alert Types**:
```yaml
Critical:
  - Service down (>1 min)
  - Database connection failed
  - Daily loss limit hit
  - Emergency stop triggered
  - Order execution failed

Warning:
  - High error rate (>5% of requests)
  - Slow response times (p95 >2s)
  - Memory usage >80%
  - Approaching loss limit (>75%)

Info:
  - Daily trading summary
  - Weekly performance report
  - System maintenance completed
```

---

## Appendix A: Technology Stack

### A.1 Core Technologies

```yaml
Programming Language: Python 3.11+
Web Framework: FastAPI
MCP Framework: FastMCP (Anthropic)
Database: PostgreSQL 15
Cache: Redis 7
Container: Docker + Docker Compose
Web Server: Nginx
Operating System: Ubuntu 22.04 LTS
```

### A.2 Python Libraries

```yaml
HTTP/API:
  - fastapi: Web framework
  - uvicorn: ASGI server
  - httpx: Async HTTP client
  - pydantic: Data validation

Database:
  - asyncpg: PostgreSQL async driver
  - sqlalchemy: ORM (optional)

Data Processing:
  - pandas: Data analysis
  - numpy: Numerical computing
  - ta-lib: Technical analysis

Machine Learning (Future):
  - scikit-learn: ML algorithms
  - transformers: FinBERT sentiment

External APIs:
  - alpaca-trade-api: Alpaca Markets
  - benzinga-api: News intelligence

Utilities:
  - redis: Redis client
  - pyyaml: Configuration
  - python-dotenv: Environment variables
  - structlog: Structured logging
```

---

## Appendix B: Deployment Commands

### B.1 Initial Deployment

```bash
# 1. SSH to droplet
ssh root@catalyst-droplet

# 2. Clone repository
git clone https://github.com/your-org/catalyst-trading.git
cd catalyst-trading

# 3. Configure environment
cp .env.example .env.prod
nano .env.prod  # Add DATABASE_URL, API keys

# 4. Deploy schema
psql $DATABASE_URL -f normalized-database-schema-mcp-v60.sql

# 5. Start services
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify health
./scripts/health-check.sh
```

### B.2 Update Deployment

```bash
# Rolling update (zero downtime)
./scripts/deploy-update.sh

# Or manual update per service
docker-compose up -d --no-deps --build orchestration
docker-compose up -d --no-deps --build scanner
# ... etc
```

---

**END OF ARCHITECTURE v6.0**

*Production architecture ONLY. 9 services. Single droplet. Clean and focused.* 🎩
