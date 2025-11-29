# Catalyst Trading System - Architecture

**Name of Application**: Catalyst Trading System  
**Name of file**: architecture.md  
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
- ⚠️ **BREAKING**: Research architecture → separate document (future)

**v5.0.0 (2025-10-22)** - 9-Service Split (superseded)

**v4.1.0 (2025-08-31)** - 7-Service Architecture (superseded)

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
❌ ML Training Service  
❌ Pattern Discovery Service  
❌ Backtest Engine  
❌ Multi-Agent Coordinator  
❌ Separate Research droplet  
❌ Multi-agent AI APIs  

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
│  │  │ Redis (6379)        │  │ Health Monitor       │  │ │
│  │  │ - Pub/sub           │  │ - Service checks     │  │ │
│  │  │ - Caching           │  │ - Metrics            │  │ │
│  │  └─────────────────────┘  └──────────────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│             DATA LAYER                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ DigitalOcean Managed PostgreSQL                       │  │
│  │ - Database: catalyst_trading_production               │  │
│  │ - Schema: 3NF normalized (see database-schema.md)     │  │
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

### 3.2 REST APIs (Internal Service Communication)

**Protocol**: HTTP REST  
**Format**: JSON  
**Authentication**: API Key (X-API-Key header)  
**Network**: Docker bridge network (internal)

### 3.3 Database Access Pattern

**All services use connection pooling:**

```python
db_pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=5,
    command_timeout=10.0
)
```

**Query Pattern (Always use FKs)** - See database-schema.md for details.

### 3.4 Redis Pub/Sub Pattern

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

See **database-schema.md** for complete schema details.

### 4.2 Caching Strategy

**Redis Cache Layers**:
```yaml
Layer 1 - Hot Data (TTL: 1 min):
  - Latest prices
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

---

## 5. Deployment Architecture

### 5.1 Single Droplet Design

**DigitalOcean Droplet**:
```yaml
Size: 4GB RAM, 2vCPU, 80GB SSD
OS: Ubuntu 22.04 LTS
Location: SFO3 (US West - closest to markets)
```

### 5.2 Service Startup Order

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
ufw allow 22/tcp   # SSH
ufw allow 443/tcp  # HTTPS
ufw default deny incoming
ufw default allow outgoing
ufw enable
```

### 6.2 Authentication & Authorization

**External (Claude Desktop)**: HTTPS + API Key  
**Internal (Service-to-Service)**: API Key (X-API-Key header)  
**Database**: SSL/TLS + Username/Password

### 6.3 Secrets Management

All secrets via environment variables (`.env`), never in Git.

---

## 7. Performance Architecture

### 7.1 Response Time Budget

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

```yaml
Workers: 4 per service (Uvicorn)
Async: asyncio (Python)
Database Pool: 2-5 connections per service
Redis Pool: 10 connections per service
```

---

## 8. Reliability Architecture

### 8.1 Health Checks

Every service exposes `GET /health` endpoint.

### 8.2 Error Handling

**Graceful Degradation**:
- News API down → Use cached news
- Database slow → Return cached data
- Alpaca API error → Retry with exponential backoff

### 8.3 Failover Strategy

**Recovery**:
- Provision new droplet from snapshot (5 min)
- Restore database from backup if needed (10 min)
- Total RTO: ~20 minutes

---

## Appendix A: Technology Stack

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

---

## Appendix B: Deployment Commands

### B.1 Initial Deployment

```bash
# 1. SSH to droplet
ssh root@catalyst-droplet

# 2. Clone repository
git clone https://github.com/Elimelech70/catalyst-trading-system.git
cd catalyst-trading-system

# 3. Configure environment
cp .env.example .env.prod
nano .env.prod  # Add DATABASE_URL, API keys

# 4. Deploy schema
psql $DATABASE_URL -f database-schema.sql

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
```

---

## Related Documents

- **database-schema.md** - Complete 3NF normalized schema
- **functional-specification.md** - MCP tools, REST APIs, workflows
- **deployment-guide.md** - Step-by-step deployment instructions

---

**END OF ARCHITECTURE DOCUMENT**

*Production architecture ONLY. 9 services. Single droplet. Clean and focused.* 🎩
