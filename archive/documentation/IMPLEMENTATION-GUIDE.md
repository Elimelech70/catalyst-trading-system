# Catalyst Trading System - Implementation Guide

**Version**: 6.0.1
**Last Updated**: 2025-11-22
**Target Audience**: DevOps Engineers, System Administrators, Developers
**Estimated Setup Time**: 2-4 hours

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [System Architecture](#3-system-architecture)
4. [Installation Steps](#4-installation-steps)
5. [Configuration](#5-configuration)
6. [Database Setup](#6-database-setup)
7. [Service Deployment](#7-service-deployment)
8. [Testing & Validation](#8-testing--validation)
9. [Production Deployment](#9-production-deployment)
10. [Monitoring & Maintenance](#10-monitoring--maintenance)
11. [Troubleshooting](#11-troubleshooting)
12. [Security Best Practices](#12-security-best-practices)

---

## 1. Overview

### What is Catalyst Trading System?

Catalyst is an **autonomous day trading system** that:
- Scans 4,000+ US equities daily
- Analyzes news sentiment, chart patterns, and technical indicators
- Validates risk before executing trades
- Automatically manages positions with stop-loss and take-profit
- Integrates with Alpaca for live/paper trading

### System Capabilities

- **Automated Scanning**: Filters 4,129 stocks → Top 5 candidates
- **Multi-Factor Analysis**: News (30%) + Technical (30%) + Momentum (20%) + Volume (20%)
- **Risk Management**: Daily loss limits, position limits, sector exposure controls
- **Autonomous Trading**: Execute trades without human intervention (optional)
- **Email Alerts**: Real-time notifications for critical events

### Technology Stack

- **Backend**: Python 3.11+ (FastAPI microservices)
- **Database**: PostgreSQL 15+ (3NF normalized schema)
- **Cache**: Redis 7.x
- **Deployment**: Docker + Docker Compose
- **Trading API**: Alpaca Markets
- **Market Data**: Alpaca, yfinance
- **News**: NewsAPI, Benzinga (optional)

---

## 2. Prerequisites

### 2.1 System Requirements

**Minimum Hardware**:
- CPU: 4 cores
- RAM: 8 GB
- Storage: 50 GB SSD
- Network: Stable internet connection (200+ Mbps recommended)

**Recommended Hardware** (Production):
- CPU: 8 cores
- RAM: 16 GB
- Storage: 100 GB SSD
- Network: Low-latency connection (< 50ms to Alpaca)

**Operating System**:
- Linux (Ubuntu 22.04 LTS recommended)
- macOS 12+ (for development)
- Windows 11 with WSL2 (for development)

### 2.2 Required Software

Install the following before proceeding:

```bash
# Docker & Docker Compose
docker --version          # Minimum: 24.0+
docker-compose --version  # Minimum: 2.20+

# Git
git --version            # Minimum: 2.30+

# PostgreSQL Client (for database management)
psql --version           # Minimum: 15+

# Python (for local development/testing)
python3 --version        # Minimum: 3.11+

# curl (for API testing)
curl --version

# jq (for JSON parsing)
jq --version
```

**Installation Commands** (Ubuntu/Debian):
```bash
# Update package list
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Install PostgreSQL client
sudo apt install postgresql-client

# Install utilities
sudo apt install git curl jq python3.11 python3-pip

# Verify installations
docker --version
docker compose version
psql --version
python3 --version
```

### 2.3 Required Accounts & API Keys

#### A. Alpaca Trading Account (REQUIRED)

1. **Sign up**: https://alpaca.markets/
2. **Choose**: Paper Trading (free, for testing) or Live Trading
3. **Get API Keys**:
   - Navigate to: Dashboard → API Keys
   - Generate keys (save securely!)
   - Note: `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`

**Important**: Start with **Paper Trading** until you've validated the system!

#### B. Database Service (REQUIRED)

**Option 1: DigitalOcean Managed PostgreSQL** (Recommended for Production)
1. Sign up: https://www.digitalocean.com/
2. Create → Databases → PostgreSQL 15
3. Choose: Basic plan ($15/month) or Pro
4. Get connection string from dashboard
5. Note: `DATABASE_URL` (format: `postgresql://user:pass@host:port/db?sslmode=require`)

**Option 2: Self-Hosted PostgreSQL** (Development/Testing)
```bash
# Using Docker
docker run -d \
  --name catalyst-postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_DB=catalyst_trading \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine

# Connection string
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/catalyst_trading
```

**Option 3: Cloud Providers**
- AWS RDS PostgreSQL
- Google Cloud SQL
- Azure Database for PostgreSQL

#### C. News APIs (OPTIONAL but Recommended)

**NewsAPI** (Free tier available):
1. Sign up: https://newsapi.org/
2. Get API key from dashboard
3. Free tier: 100 requests/day

**Benzinga** (Premium):
1. Sign up: https://www.benzinga.com/apis/
2. Paid plans start at $99/month
3. Provides high-quality financial news

#### D. Email Service (OPTIONAL - for alerts)

**Option 1: DigitalOcean SMTP** (Recommended)
- Professional email delivery
- Configuration included in system

**Option 2: Gmail** (Development/Testing)
- Free but has rate limits
- Requires app-specific password

**Option 3: SendGrid/Mailgun** (Production)
- Dedicated transactional email services
- Better deliverability

### 2.4 Knowledge Requirements

**Essential**:
- Basic Linux command line
- Docker and containerization concepts
- Environment variables and configuration
- Basic SQL queries

**Helpful**:
- Python programming
- FastAPI framework
- PostgreSQL administration
- Trading/financial markets knowledge
- System monitoring and logging

---

## 3. System Architecture

### 3.1 Microservices Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Catalyst Trading System                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Orchestration│───▶│   Workflow   │───▶│   Scanner    │
│   (MCP)      │    │ Coordinator  │    │   Service    │
│   Port 5000  │    │   Port 5007  │    │   Port 5001  │
└──────────────┘    └──────────────┘    └──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│     News     │    │   Pattern    │    │  Technical   │
│   Service    │    │   Analysis   │    │  Indicators  │
│   Port 5002  │    │   Port 5003  │    │   Port 5004  │
└──────────────┘    └──────────────┘    └──────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────┐                        ┌──────────────┐
│     Risk     │                        │   Trading    │
│   Manager    │───────────────────────▶│   Service    │
│   Port 5005  │                        │   Port 5006  │
└──────────────┘                        └──────────────┘
        │                                       │
        └───────────────────┬───────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   Alpaca     │
                    │Trading API   │
                    └──────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Database   │    │    Redis     │    │  Reporting   │
│  PostgreSQL  │    │    Cache     │    │   Service    │
│              │    │   Port 6379  │    │   Port 5009  │
└──────────────┘    └──────────────┘    └──────────────┘
```

### 3.2 Service Descriptions

| Service | Port | Purpose | Critical |
|---------|------|---------|----------|
| **Orchestration** | 5000 | MCP server, external integrations | No |
| **Scanner** | 5001 | Market scanning, candidate selection | Yes |
| **News** | 5002 | News sentiment analysis | Yes |
| **Pattern** | 5003 | Chart pattern detection | Yes |
| **Technical** | 5004 | Technical indicator calculation | Yes |
| **Risk Manager** | 5005 | Risk validation, emergency stops | Yes |
| **Trading** | 5006 | Position management, order execution | Yes |
| **Workflow** | 5007 | Cycle orchestration, pipeline control | Yes |
| **Reporting** | 5009 | Performance metrics, analytics | No |
| **Redis** | 6379 | Caching, session storage | Yes |

### 3.3 Data Flow

**Complete Trading Cycle**:
```
1. Cron Job (Market Open) → Workflow Coordinator
2. Workflow → Scanner: POST /api/v1/scan
3. Scanner → Alpaca: Fetch 4,129 tradable stocks
4. Scanner → Database: Insert scan_results (Top 200)
5. Workflow → News: Filter by sentiment (100 → 35)
6. Workflow → Pattern: Detect patterns (35 → 20)
7. Workflow → Technical: Validate indicators (20 → 10)
8. Workflow → Risk Manager: Validate risk (10 → 5)
9. Risk Manager → Trading: Approve top 3-5 trades
10. Trading → Alpaca: Submit bracket orders
11. Trading → Database: Insert positions
12. Risk Manager (every 60s): Monitor P&L, check stops
13. Trading (market close): Close all positions
14. Workflow → Database: Update cycle status = 'completed'
```

---

## 4. Installation Steps

### 4.1 Clone the Repository

```bash
# Clone from GitHub
git clone https://github.com/YOUR_USERNAME/catalyst-trading-system.git
cd catalyst-trading-system

# Verify directory structure
ls -la
# Expected output:
# - services/          (9 microservices)
# - config/            (YAML configuration files)
# - Documentation/     (Analysis and design docs)
# - docker-compose.yml
# - .env.template
# - README.md
```

### 4.2 Create Environment Configuration

```bash
# Copy environment template
cp .env.template .env

# Open .env in your editor
nano .env  # or vim, or code
```

**Fill in the following values** (see section 5 for detailed configuration):

```bash
# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/dbname?sslmode=require

# Alpaca (REQUIRED)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here

# News APIs (OPTIONAL)
NEWS_API_KEY=your_newsapi_key_here
BENZINGA_API_KEY=your_benzinga_key_here

# Email Alerts (OPTIONAL)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_CRITICAL=trader@yourdomain.com
```

**Save and close** the file.

### 4.3 Verify Docker Setup

```bash
# Check Docker is running
docker ps

# Check Docker Compose version
docker compose version

# Test Docker permissions (should not require sudo)
docker run hello-world

# If permission denied, add user to docker group:
sudo usermod -aG docker $USER
# Then log out and back in
```

---

## 5. Configuration

### 5.1 Environment Variables (.env)

**Critical Settings**:

```bash
# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
# Format: postgresql://username:password@host:port/database?sslmode=require
DATABASE_URL=postgresql://catalyst_user:STRONG_PASSWORD@db.example.com:25060/catalyst_trading?sslmode=require

# ============================================================================
# ALPACA TRADING API
# ============================================================================
# Get from: https://app.alpaca.markets/paper/dashboard/overview
ALPACA_API_KEY=PK1234567890ABCDEF
ALPACA_SECRET_KEY=abcdefghijklmnopqrstuvwxyz1234567890ABCD
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
# ALPACA_BASE_URL=https://api.alpaca.markets      # Live trading (BE CAREFUL!)

# ============================================================================
# TRADING CONFIGURATION
# ============================================================================
MAX_DAILY_LOSS=2000          # Emergency stop at -$2,000
MAX_POSITION_SIZE=5000       # Maximum per position
MAX_POSITIONS=5              # Maximum concurrent positions
TRADING_MODE=paper           # 'paper' or 'live'

# ============================================================================
# AUTONOMOUS TRADING
# ============================================================================
TRADING_SESSION_MODE=supervised    # Start with 'supervised', then 'autonomous'
WORKFLOW_AUTO_EXECUTE=false        # Start with false for safety
WORKFLOW_SCAN_FREQUENCY_MINUTES=30 # Scan every 30 minutes
WORKFLOW_EXECUTE_TOP_N=3           # Execute top 3 candidates

# ============================================================================
# EMAIL ALERTS (OPTIONAL)
# ============================================================================
ENABLE_EMAIL_ALERTS=true           # Set to false to disable

# Gmail Configuration (for testing)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password  # NOT your regular password!
SMTP_FROM=your-email@gmail.com
SMTP_TLS=true

# Alert Recipients
ALERT_EMAIL_CRITICAL=trader@yourdomain.com
ALERT_EMAIL_WARNING=trader@yourdomain.com
ALERT_EMAIL_INFO=trader@yourdomain.com

# ============================================================================
# NEWS APIS (OPTIONAL)
# ============================================================================
NEWS_API_KEY=your_newsapi_key_here          # Get from newsapi.org
BENZINGA_API_KEY=your_benzinga_key_here     # Premium (optional)

# ============================================================================
# REDIS CONFIGURATION
# ============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=RedisCatalyst2025!SecureCache  # Change this!

# ============================================================================
# FEATURE FLAGS
# ============================================================================
ENABLE_PAPER_TRADING=true
ENABLE_LIVE_TRADING=false      # ONLY enable after extensive testing!
ENABLE_NEWS_SENTIMENT=true
ENABLE_PATTERN_DETECTION=true
ENABLE_AUTONOMOUS_TRADING=false  # Start with false!

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json
```

### 5.2 Trading Configuration (config/trading_config.yaml)

This file is **hot-reloaded** (no restart required):

```yaml
# Catalyst Trading System - Trading Configuration
# Hot-reload enabled: Changes take effect within 60 seconds

# Session Settings
session:
  mode: supervised  # 'autonomous' or 'supervised'
  timezone: US/Eastern
  market_open: "09:30"
  market_close: "16:00"

# Risk Parameters
risk:
  max_daily_loss: 2000.00       # Hard stop
  max_position_size: 5000.00
  max_positions: 5
  max_sector_exposure_pct: 40   # Max 40% in one sector
  max_correlation: 0.7          # Prevent correlated positions

# Position Management
positions:
  default_stop_loss_pct: 2.0    # 2% stop loss
  default_take_profit_pct: 6.0  # 6% take profit (3:1 R:R)
  max_hold_time_minutes: 180    # 3 hours max
  close_all_at_market_close: true

# Workflow Automation
workflow:
  auto_execute: false           # Start with manual approval
  scan_frequency_minutes: 30
  execute_top_n: 3              # Execute top 3 candidates
```

### 5.3 Risk Parameters (config/risk_parameters.yaml)

**Hot-reloaded** configuration:

```yaml
# Catalyst Trading System - Risk Parameters
# Hot-reload enabled: Changes take effect within 60 seconds

# Daily Risk Limits
daily_limits:
  max_loss: 2000.00
  warning_threshold_pct: 75      # Alert at 75% ($1,500)
  emergency_stop_at_100: true    # Hard stop at 100% ($2,000)

# Position Limits
position_limits:
  max_positions: 5
  max_position_size: 5000.00
  min_position_size: 100.00

# Sector Exposure
sector_limits:
  max_exposure_pct: 40
  sectors_to_limit:
    - Technology
    - Financial
    - Healthcare

# Correlation Limits
correlation:
  max_correlation: 0.7
  check_enabled: true

# Emergency Actions
emergency_actions:
  close_all_positions_on_limit: true
  send_email_alert: true
  halt_new_trades: true
  cooldown_period_minutes: 60
```

---

## 6. Database Setup

### 6.1 Create Database

If using DigitalOcean or cloud provider, the database is already created. Skip to 6.2.

If self-hosting:

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres

# Create database
CREATE DATABASE catalyst_trading;

# Create user
CREATE USER catalyst_user WITH ENCRYPTED PASSWORD 'STRONG_PASSWORD_HERE';

# Grant permissions
GRANT ALL PRIVILEGES ON DATABASE catalyst_trading TO catalyst_user;

# Exit
\q
```

### 6.2 Deploy Database Schema

The system uses helper functions that **must be deployed to the database**:

**Option 1: Using psql** (Recommended)

```bash
# Connect to your database
export DATABASE_URL="your_connection_string_here"
psql $DATABASE_URL

# Create helper functions
CREATE OR REPLACE FUNCTION get_or_create_security(p_symbol VARCHAR(10))
RETURNS INTEGER AS $$
DECLARE
    v_security_id INTEGER;
BEGIN
    SELECT security_id INTO v_security_id
    FROM securities
    WHERE symbol = UPPER(p_symbol);

    IF v_security_id IS NULL THEN
        INSERT INTO securities (symbol, exchange, is_active)
        VALUES (UPPER(p_symbol), 'UNKNOWN', true)
        RETURNING security_id INTO v_security_id;
    END IF;

    RETURN v_security_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_or_create_time(p_timestamp TIMESTAMP WITH TIME ZONE)
RETURNS BIGINT AS $$
DECLARE
    v_time_id BIGINT;
    v_date DATE;
    v_hour INTEGER;
    v_is_market_hours BOOLEAN;
BEGIN
    SELECT time_id INTO v_time_id
    FROM time_dimension
    WHERE timestamp = p_timestamp;

    IF v_time_id IS NULL THEN
        v_date := DATE(p_timestamp);
        v_hour := EXTRACT(HOUR FROM p_timestamp);

        v_is_market_hours := (
            EXTRACT(DOW FROM p_timestamp) BETWEEN 1 AND 5
            AND v_hour >= 14 AND v_hour < 21
        );

        INSERT INTO time_dimension (
            timestamp, date, year, month, day, day_of_week,
            hour, minute, is_market_hours, is_trading_day
        ) VALUES (
            p_timestamp,
            v_date,
            EXTRACT(YEAR FROM p_timestamp),
            EXTRACT(MONTH FROM p_timestamp),
            EXTRACT(DAY FROM p_timestamp),
            EXTRACT(DOW FROM p_timestamp),
            v_hour,
            EXTRACT(MINUTE FROM p_timestamp),
            v_is_market_hours,
            EXTRACT(DOW FROM p_timestamp) BETWEEN 1 AND 5
        )
        RETURNING time_id INTO v_time_id;
    END IF;

    RETURN v_time_id;
END;
$$ LANGUAGE plpgsql;
```

**Option 2: Check if Functions Exist**

```sql
-- Verify helper functions
SELECT proname, prosrc
FROM pg_proc
WHERE proname IN ('get_or_create_security', 'get_or_create_time');

-- Should return 2 rows
```

### 6.3 Verify Schema

The services will create tables on first run, but you can verify:

```bash
# Connect to database
psql $DATABASE_URL

# List tables
\dt

# Expected tables:
# - trading_cycles
# - scan_results
# - securities
# - news_sentiment
# - technical_indicators
# - pattern_analysis
# - positions
# - orders
# - risk_events
# - time_dimension
# - sectors

# Check table structure
\d trading_cycles
\d scan_results

# Exit
\q
```

---

## 7. Service Deployment

### 7.1 Build Docker Images

```bash
# Build all services
docker compose build

# This will:
# 1. Download base images (Python 3.11)
# 2. Install dependencies from requirements.txt
# 3. Build 9 service images
#
# Expected duration: 10-15 minutes (first time)

# Verify images built
docker images | grep catalyst
```

### 7.2 Start Services

**Development Mode** (with hot reload):

```bash
# Start all services
docker compose up -d

# View logs (all services)
docker compose logs -f

# View specific service logs
docker compose logs -f scanner
docker compose logs -f workflow

# Stop following logs: Ctrl+C
```

**Production Mode**:

```bash
# Use production compose file (if you have one)
docker compose -f docker-compose.yml up -d

# Or use the default
docker compose up -d --build
```

### 7.3 Verify Services Are Running

```bash
# Check container status
docker compose ps

# Expected output (all should show "Up" and "healthy"):
# NAME                  STATUS
# catalyst-scanner      Up (healthy)
# catalyst-workflow     Up (healthy)
# catalyst-news         Up (healthy)
# catalyst-pattern      Up (healthy)
# catalyst-technical    Up (healthy)
# catalyst-risk-manager Up (healthy)
# catalyst-trading      Up (healthy)
# catalyst-orchestration Up (healthy)
# catalyst-reporting    Up (healthy)
# catalyst-redis        Up (healthy)

# If any service is "unhealthy", check logs:
docker compose logs [service-name]
```

### 7.4 Health Check All Services

```bash
# Test all health endpoints
for port in 5000 5001 5002 5003 5004 5005 5006 5009; do
    echo "=== Port $port ==="
    curl -s http://localhost:$port/health | jq '.'
done

# Expected: All should return {"status": "healthy", ...}
```

**Individual Service Tests**:

```bash
# Scanner
curl http://localhost:5001/health
# {"status":"healthy","service":"scanner","version":"6.0.1"}

# Workflow
curl http://localhost:5006/health
# {"status":"healthy","service":"workflow","version":"6.0.0"}

# Risk Manager
curl http://localhost:5005/health
# {"status":"healthy","service":"risk-manager","version":"6.0.0"}

# Trading
curl http://localhost:5006/health
# {"status":"healthy","service":"trading","version":"6.0.0"}
```

---

## 8. Testing & Validation

### 8.1 Database Connection Test

```bash
# Test from workflow service
docker exec catalyst-workflow python -c "
import asyncio
import asyncpg
import os

async def test():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    version = await conn.fetchval('SELECT version()')
    print(f'✅ Connected: {version[:50]}...')
    await conn.close()

asyncio.run(test())
"

# Expected: ✅ Connected: PostgreSQL 15.x...
```

### 8.2 Alpaca API Test

```bash
# Test Alpaca connectivity
docker exec catalyst-scanner python -c "
import os
from alpaca.trading.client import TradingClient

client = TradingClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    paper=True
)

account = client.get_account()
print(f'✅ Alpaca Connected')
print(f'   Account: {account.account_number}')
print(f'   Cash: \${account.cash}')
print(f'   Buying Power: \${account.buying_power}')
"

# Expected:
# ✅ Alpaca Connected
#    Account: PA...
#    Cash: $100000.00
#    Buying Power: $100000.00
```

### 8.3 Manual Workflow Test (Supervised Mode)

```bash
# Step 1: Create a trading cycle
curl -X POST http://localhost:5007/api/v1/cycles \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "normal",
    "max_positions": 5,
    "max_daily_loss": 2000.0,
    "scan_frequency": 300
  }' | jq '.'

# Save the cycle_id from response
CYCLE_ID="20251122-143022"

# Step 2: Trigger a scan
curl -X POST http://localhost:5001/api/v1/scan | jq '.'

# Expected:
# {
#   "success": true,
#   "cycle_id": "20251122-143022",
#   "candidates": 5,
#   "picks": [...]
# }

# Step 3: View scan results
curl "http://localhost:5001/api/v1/candidates?cycle_id=$CYCLE_ID" | jq '.'

# Step 4: View cycle details
curl "http://localhost:5007/api/v1/cycles/$CYCLE_ID" | jq '.'

# Step 5: Check database
psql $DATABASE_URL -c "
SELECT cycle_id, mode, status, started_at
FROM trading_cycles
WHERE cycle_id = '$CYCLE_ID';
"

# Step 6: Check scan results
psql $DATABASE_URL -c "
SELECT id, rank, price, volume, composite_score
FROM scan_results
WHERE cycle_id = '$CYCLE_ID'
ORDER BY rank LIMIT 5;
"
```

### 8.4 Risk Validation Test

```bash
# Test risk validation
curl -X POST http://localhost:5005/api/v1/risk/validate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "TSLA",
    "side": "long",
    "quantity": 10,
    "price": 250.00,
    "cycle_id": "'$CYCLE_ID'"
  }' | jq '.'

# Expected:
# {
#   "approved": true,
#   "risk_score": 0.15,
#   "risk_amount": 50.00,
#   "reason": "Risk within limits"
# }
```

### 8.5 Email Alert Test (If Configured)

```bash
# Trigger a test alert
curl -X POST http://localhost:5005/api/v1/risk/test-alert

# Check your email for test message
# Subject: "[TEST] Catalyst Alert System Test"
```

---

## 9. Production Deployment

### 9.1 Pre-Production Checklist

Before enabling autonomous trading:

- [ ] All services pass health checks
- [ ] Database schema deployed and verified
- [ ] Alpaca API connected (paper trading mode)
- [ ] Manual scan test completed successfully
- [ ] Risk validation tested
- [ ] Email alerts configured and tested
- [ ] Configuration files reviewed (trading_config.yaml, risk_parameters.yaml)
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] At least 1 week of supervised testing completed

### 9.2 Enable Autonomous Mode

**IMPORTANT**: Only enable after successful supervised testing!

**Step 1: Update Trading Configuration**

Edit `config/trading_config.yaml`:

```yaml
session:
  mode: autonomous  # Changed from 'supervised'

workflow:
  auto_execute: true  # Changed from false
  execute_top_n: 3    # Start conservative
```

**Step 2: Update Environment Variables**

Edit `.env`:

```bash
TRADING_SESSION_MODE=autonomous
WORKFLOW_AUTO_EXECUTE=true
ENABLE_AUTONOMOUS_TRADING=true
```

**Step 3: Restart Services**

```bash
# Restart to pick up new config
docker compose restart workflow risk-manager trading

# Verify autonomous mode enabled
docker compose logs workflow | grep "autonomous"
# Should see: "Trading session mode: autonomous"
```

### 9.3 Configure Cron Jobs (Market Hours Automation)

The system needs to be triggered during market hours.

**Edit crontab**:

```bash
crontab -e
```

**Add the following entries**:

```cron
# Catalyst Trading System - Autonomous Trading Schedule
# Market Hours: 9:30 AM - 4:00 PM ET
# Adjust times based on your timezone!

# Market Open - Full scan and execute
30 9 * * 1-5 curl -X POST http://localhost:5007/api/v1/workflow/start -H "Content-Type: application/json" -d '{"mode":"autonomous"}' >> /var/log/catalyst-cron.log 2>&1

# Mid-morning scan (10:30 AM ET)
30 10 * * 1-5 curl -X POST http://localhost:5001/api/v1/scan >> /var/log/catalyst-cron.log 2>&1

# Midday scan (12:00 PM ET)
0 12 * * 1-5 curl -X POST http://localhost:5001/api/v1/scan >> /var/log/catalyst-cron.log 2>&1

# Afternoon scan (2:00 PM ET)
0 14 * * 1-5 curl -X POST http://localhost:5001/api/v1/scan >> /var/log/catalyst-cron.log 2>&1

# Market close - Verify all positions closed (3:50 PM ET)
50 15 * * 1-5 curl http://localhost:5006/api/v1/positions?status=open >> /var/log/catalyst-cron.log 2>&1
```

**If in a different timezone** (e.g., Perth, Australia):

```cron
# Perth time = ET + 12-13 hours (depending on DST)
# Market open 9:30 AM ET = 9:30 PM or 10:30 PM Perth

# Example for Perth (AWST, no DST):
# Market open: 9:30 AM ET = 9:30 PM Perth
30 21 * * 1-5 curl -X POST http://localhost:5007/api/v1/workflow/start -d '{"mode":"autonomous"}'

# Or use Docker exec to run from inside container:
30 21 * * 1-5 docker exec catalyst-workflow curl -X POST http://localhost:5007/api/v1/workflow/start -d '{"mode":"autonomous"}'
```

**Verify cron jobs**:

```bash
# List cron jobs
crontab -l

# Test cron manually
curl -X POST http://localhost:5007/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode":"autonomous"}'

# Check logs
tail -f /var/log/catalyst-cron.log
```

### 9.4 Production Environment Variables

For production, ensure:

```bash
# Use strong passwords
REDIS_PASSWORD=GenerateAStrongRandomPassword123!

# Dedicated email for alerts
ALERT_EMAIL_CRITICAL=trading-critical@yourdomain.com

# Production logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Disable development features
ENABLE_PAPER_TRADING=false  # ONLY if going live!
ENABLE_LIVE_TRADING=true    # ONLY if going live!

# Keep safety features
RISK_HOT_RELOAD=true
TRADING_HOT_RELOAD=true
```

### 9.5 Backup Strategy

**Daily Database Backups**:

```bash
# Create backup script: /usr/local/bin/catalyst-backup.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/catalyst"
mkdir -p $BACKUP_DIR

# Backup database
pg_dump $DATABASE_URL > $BACKUP_DIR/catalyst_$DATE.sql

# Keep only last 7 days
find $BACKUP_DIR -name "catalyst_*.sql" -mtime +7 -delete

# Log backup
echo "$DATE - Backup completed" >> /var/log/catalyst-backup.log
```

**Make executable and add to cron**:

```bash
chmod +x /usr/local/bin/catalyst-backup.sh

# Add to crontab (daily at 6 AM)
0 6 * * * /usr/local/bin/catalyst-backup.sh
```

---

## 10. Monitoring & Maintenance

### 10.1 Log Monitoring

**View live logs**:

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f scanner
docker compose logs -f workflow
docker compose logs -f risk-manager

# Filter for errors
docker compose logs | grep ERROR
docker compose logs | grep CRITICAL

# Save logs to file
docker compose logs > catalyst-logs-$(date +%Y%m%d).log
```

**Log locations inside containers**:

```bash
# Scanner logs
docker exec catalyst-scanner ls -la /app/logs/

# View specific log
docker exec catalyst-scanner tail -f /app/logs/scanner.log
```

### 10.2 Health Monitoring Script

Create `/usr/local/bin/catalyst-monitor.sh`:

```bash
#!/bin/bash
# Catalyst Health Monitor

SERVICES="5000 5001 5002 5003 5004 5005 5006 5009"
ALL_HEALTHY=true

echo "=== Catalyst Trading System Health Check ==="
echo "$(date)"
echo ""

for port in $SERVICES; do
    response=$(curl -s http://localhost:$port/health)
    status=$(echo $response | jq -r '.status' 2>/dev/null)

    if [ "$status" = "healthy" ]; then
        service=$(echo $response | jq -r '.service')
        version=$(echo $response | jq -r '.version')
        echo "✅ Port $port - $service v$version"
    else
        echo "❌ Port $port - UNHEALTHY or DOWN"
        ALL_HEALTHY=false
    fi
done

echo ""
if [ "$ALL_HEALTHY" = true ]; then
    echo "Status: ALL SYSTEMS OPERATIONAL"
    exit 0
else
    echo "Status: SOME SERVICES DOWN - CHECK LOGS"
    exit 1
fi
```

**Make executable and run**:

```bash
chmod +x /usr/local/bin/catalyst-monitor.sh
/usr/local/bin/catalyst-monitor.sh

# Add to cron (every 5 minutes)
*/5 * * * * /usr/local/bin/catalyst-monitor.sh >> /var/log/catalyst-monitor.log
```

### 10.3 Database Monitoring

**Check database size**:

```bash
psql $DATABASE_URL -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

**Check active connections**:

```bash
psql $DATABASE_URL -c "
SELECT count(*) as connections
FROM pg_stat_activity
WHERE datname = current_database();
"
```

**Monitor query performance**:

```bash
psql $DATABASE_URL -c "
SELECT
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
"
```

### 10.4 Performance Metrics

**Trading Cycle Performance**:

```bash
psql $DATABASE_URL -c "
SELECT
    cycle_id,
    mode,
    status,
    started_at,
    stopped_at,
    (stopped_at - started_at) as duration
FROM trading_cycles
ORDER BY started_at DESC
LIMIT 10;
"
```

**Position Performance**:

```bash
psql $DATABASE_URL -c "
SELECT
    COUNT(*) as total_positions,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winners,
    SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losers,
    ROUND(AVG(realized_pnl), 2) as avg_pnl,
    ROUND(SUM(realized_pnl), 2) as total_pnl
FROM positions
WHERE status = 'closed'
AND DATE(entry_time) >= CURRENT_DATE - INTERVAL '7 days';
"
```

### 10.5 Disk Space Monitoring

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up old images/containers
docker system prune -a --volumes -f

# Keep only last 3 days of logs
docker logs catalyst-scanner 2>&1 | tail -n 10000 > /tmp/scanner.log
```

---

## 11. Troubleshooting

### 11.1 Common Issues

#### Issue: "column does not exist" errors

**Symptom**: Services crash with SQL errors
**Cause**: Database schema mismatch
**Fix**:

```bash
# Check scanner service version (should be 6.0.1)
curl http://localhost:5001/health | jq '.version'

# If older, rebuild scanner
docker compose build scanner
docker compose restart scanner

# Verify schema
psql $DATABASE_URL -c "\d scan_results"
psql $DATABASE_URL -c "\d trading_cycles"
```

#### Issue: Services unhealthy

**Symptom**: `docker compose ps` shows "unhealthy"
**Fix**:

```bash
# Check logs
docker compose logs [service-name]

# Common causes:
# 1. Database connection failed
curl http://localhost:5001/health | jq '.database'
# Should show: "connected"

# 2. Missing environment variables
docker exec catalyst-scanner env | grep DATABASE_URL
docker exec catalyst-scanner env | grep ALPACA

# 3. Port conflicts
netstat -tulpn | grep 5001

# Restart service
docker compose restart [service-name]
```

#### Issue: Alpaca API errors

**Symptom**: "Authentication failed" or "API key invalid"
**Fix**:

```bash
# Verify API keys in .env
cat .env | grep ALPACA

# Test keys manually
curl -u "$ALPACA_API_KEY:$ALPACA_SECRET_KEY" \
  https://paper-api.alpaca.markets/v2/account

# Regenerate keys at: https://app.alpaca.markets/paper/dashboard/overview
# Update .env and restart
docker compose restart scanner trading
```

#### Issue: No scans running

**Symptom**: No scan_results in database
**Cause**: Cron not configured or autonomous mode disabled
**Fix**:

```bash
# Check autonomous mode
curl http://localhost:5007/health | jq '.mode'

# Should show: "autonomous"

# Manual trigger
curl -X POST http://localhost:5001/api/v1/scan

# Check cron jobs
crontab -l

# Check cron logs
tail -f /var/log/catalyst-cron.log
```

#### Issue: Email alerts not sending

**Symptom**: No email received
**Fix**:

```bash
# Test SMTP settings
docker exec catalyst-workflow python -c "
import smtplib
import os

smtp = smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT')))
smtp.starttls()
smtp.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
print('✅ SMTP authentication successful')
smtp.quit()
"

# Check Gmail app password (if using Gmail)
# Must be "App Password", not regular password

# Trigger test alert
curl -X POST http://localhost:5005/api/v1/risk/test-alert
```

### 11.2 Emergency Procedures

#### Emergency Stop All Trading

```bash
# Stop workflow coordinator (prevents new trades)
docker compose stop workflow

# Close all open positions
curl -X POST http://localhost:5006/api/v1/positions/close-all

# Verify positions closed
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM positions WHERE status = 'open';
"
# Should return: 0

# Disable autonomous mode
# Edit .env: ENABLE_AUTONOMOUS_TRADING=false
docker compose restart risk-manager trading
```

#### Database Recovery

```bash
# Restore from backup
psql $DATABASE_URL < /backups/catalyst/catalyst_YYYYMMDD.sql

# Verify data
psql $DATABASE_URL -c "SELECT COUNT(*) FROM trading_cycles;"

# Restart services
docker compose restart
```

#### Reset System

```bash
# DANGER: This deletes all data!

# Stop all services
docker compose down

# Delete all volumes
docker volume rm $(docker volume ls -q | grep catalyst)

# Delete database (if self-hosted)
psql -U postgres -c "DROP DATABASE catalyst_trading;"
psql -U postgres -c "CREATE DATABASE catalyst_trading;"

# Redeploy
docker compose up -d
```

---

## 12. Security Best Practices

### 12.1 Environment Variables

```bash
# Never commit .env to Git
echo ".env" >> .gitignore

# Restrict file permissions
chmod 600 .env

# Use strong passwords
REDIS_PASSWORD=$(openssl rand -base64 32)
DATABASE_PASSWORD=$(openssl rand -base64 32)

# Rotate API keys regularly (every 90 days)
```

### 12.2 Network Security

```bash
# Restrict port access (use firewall)
sudo ufw allow 22/tcp      # SSH only
sudo ufw deny 5000:5009/tcp  # Block direct service access
sudo ufw enable

# Use reverse proxy (Nginx/Caddy) for external access
# Only expose orchestration service (5000) if needed

# Enable SSL/TLS
# Use Let's Encrypt for free certificates
```

### 12.3 Database Security

```bash
# Use SSL connections
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require

# Restrict database access by IP
# (DigitalOcean → Database → Settings → Trusted Sources)

# Regular security updates
sudo apt update && sudo apt upgrade -y

# Backup encryption
pg_dump $DATABASE_URL | gpg -c > backup_encrypted.sql.gpg
```

### 12.4 Access Control

```bash
# Create separate database users with limited permissions

# Read-only user for reporting
CREATE USER catalyst_readonly WITH PASSWORD 'strong_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO catalyst_readonly;

# Application user (limited)
CREATE USER catalyst_app WITH PASSWORD 'strong_password';
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO catalyst_app;
REVOKE DELETE ON ALL TABLES IN SCHEMA public FROM catalyst_app;
```

### 12.5 Audit Logging

```bash
# Enable PostgreSQL query logging
# Edit postgresql.conf:
log_statement = 'mod'  # Log all modifications
log_min_duration_statement = 1000  # Log slow queries

# Application-level audit trail
# All trades logged in positions table
# All risk events logged in risk_events table

# Review audit logs regularly
psql $DATABASE_URL -c "
SELECT event_type, severity, message, occurred_at
FROM risk_events
ORDER BY occurred_at DESC
LIMIT 20;
"
```

---

## 13. Support & Resources

### 13.1 Documentation

- **Design Documents**: `/Documentation/Design/`
- **Analysis Reports**: `/Documentation/Analysis/`
- **Implementation Guide**: `/Documentation/Implementation/`

### 13.2 Logs & Debugging

```bash
# Service logs
docker compose logs -f [service-name]

# Database logs (if self-hosted)
tail -f /var/log/postgresql/postgresql-15-main.log

# Cron logs
tail -f /var/log/catalyst-cron.log

# System logs
journalctl -u docker -f
```

### 13.3 Useful Commands Reference

```bash
# Service Management
docker compose up -d          # Start all services
docker compose down           # Stop all services
docker compose restart        # Restart all services
docker compose ps             # List running services
docker compose logs -f        # View logs

# Database
psql $DATABASE_URL            # Connect to database
pg_dump $DATABASE_URL > backup.sql  # Backup
psql $DATABASE_URL < backup.sql     # Restore

# Health Checks
curl http://localhost:5001/health  # Scanner
curl http://localhost:5006/health  # Workflow

# Manual Operations
curl -X POST http://localhost:5001/api/v1/scan  # Trigger scan
curl -X POST http://localhost:5007/api/v1/cycles  # Create cycle
curl http://localhost:5001/api/v1/candidates  # View candidates
```

---

## 14. Quick Start Checklist

Use this checklist for your first deployment:

### Prerequisites
- [ ] Linux server with Docker installed
- [ ] PostgreSQL database created (DigitalOcean or self-hosted)
- [ ] Alpaca paper trading account created
- [ ] API keys obtained (Alpaca, optional: NewsAPI)

### Installation
- [ ] Repository cloned: `git clone ...`
- [ ] Environment file created: `cp .env.template .env`
- [ ] `.env` file configured with all API keys
- [ ] Database helper functions deployed
- [ ] Docker images built: `docker compose build`

### Deployment
- [ ] Services started: `docker compose up -d`
- [ ] All services healthy: `docker compose ps`
- [ ] Health checks passing: `curl http://localhost:5001/health`
- [ ] Database connection verified
- [ ] Alpaca API connection verified

### Testing
- [ ] Manual scan test completed successfully
- [ ] Trading cycle created and completed
- [ ] Risk validation tested
- [ ] Email alerts tested (if configured)
- [ ] Logs reviewed for errors

### Production (ONLY after testing)
- [ ] Supervised mode tested for 1 week minimum
- [ ] Configuration reviewed (trading_config.yaml, risk_parameters.yaml)
- [ ] Autonomous mode enabled in config
- [ ] Cron jobs configured for market hours
- [ ] Backup strategy implemented
- [ ] Monitoring configured

---

## 15. Going Live Checklist

**CRITICAL: Only proceed after extensive paper trading!**

### Final Validation
- [ ] At least 2 weeks of successful paper trading
- [ ] Win rate > 50%
- [ ] Average trade profit > $50
- [ ] Max drawdown < $500 in any day
- [ ] Risk controls validated (emergency stop tested)
- [ ] All services stable (no crashes in 2 weeks)

### Live Trading Preparation
- [ ] Alpaca live trading account funded
- [ ] Live API keys generated
- [ ] `.env` updated with live credentials
- [ ] `ENABLE_LIVE_TRADING=true` set
- [ ] `ALPACA_BASE_URL=https://api.alpaca.markets` set
- [ ] Reduced position size for first week (50% of normal)
- [ ] Increased monitoring frequency

### First Live Day
- [ ] Start with supervised mode (human approval)
- [ ] Monitor every trade manually
- [ ] Review each position before entry
- [ ] Keep emergency stop button ready
- [ ] Watch for 30 minutes before enabling autonomous

**Remember: Trading involves risk. Never trade with money you can't afford to lose.**

---

**End of Implementation Guide**

For questions or issues, review:
- Analysis documents in `/Documentation/Analysis/`
- Service logs: `docker compose logs`
- Database schema: `/Documentation/Design/database-schema-mcp-v60.md`

**Good luck with your implementation!** 🚀
