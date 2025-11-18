# Catalyst Trading System - Complete Implementation Guide

## Overview

This guide will help you deploy the complete Catalyst Trading System from scratch in your own GitHub Codespace with your own DigitalOcean PostgreSQL database. The system includes 6 microservices using a v6.0 3NF normalized database schema with automated cron scheduling.

**Total Implementation Time**: ~30-45 minutes

---

## Prerequisites

### Required Accounts
- GitHub account (for Codespace)
- DigitalOcean account (for managed PostgreSQL)

### Required Knowledge
- Basic terminal/bash commands
- Basic understanding of PostgreSQL
- Basic understanding of Python and microservices

---

## Part 1: DigitalOcean Database Setup

### Step 1.1: Create PostgreSQL Database

1. Log into DigitalOcean
2. Navigate to **Databases** → **Create Database**
3. Configure:
   - **Database Engine**: PostgreSQL 15
   - **Plan**: Basic ($15/month minimum recommended)
   - **Datacenter**: Choose closest to your location
   - **Database Name**: `catalyst_trading`
4. Click **Create Database**
5. Wait 3-5 minutes for provisioning

### Step 1.2: Get Connection Details

1. On the database page, click **Connection Details**
2. Copy the connection string (format: `postgresql://doadmin:PASSWORD@HOST:PORT/catalyst_trading?sslmode=require`)
3. Save this - you'll need it in Step 2.3

### Step 1.3: Configure Firewall (Optional but Recommended)

1. In database settings → **Trusted Sources**
2. Add your IP address or use "Allow All" for development
3. Click **Save**

---

## Part 2: GitHub Codespace Setup

### Step 2.1: Fork/Clone Repository

```bash
# If starting from scratch, create a new repository or use existing
git clone https://github.com/YOUR_USERNAME/catalyst-trading-system.git
cd catalyst-trading-system
```

### Step 2.2: Open in Codespace

1. On GitHub repository page, click **Code** → **Codespaces** → **Create codespace on main**
2. Wait for Codespace to initialize (2-3 minutes)

### Step 2.3: Set Environment Variables

Create `.env` file in project root:

```bash
cd /workspaces/catalyst-trading-system/catalyst-trading-system
nano .env
```

Add the following (replace with your actual DigitalOcean credentials):

```bash
# DigitalOcean Database Connection
DATABASE_URL=postgresql://doadmin:YOUR_PASSWORD@YOUR_HOST.db.ondigitalocean.com:25060/catalyst_trading?sslmode=require

# Redis Configuration (local)
REDIS_HOST=localhost
REDIS_PORT=6379

# Service Ports
SCANNER_PORT=5001
NEWS_PORT=5002
TECHNICAL_PORT=5003
RISK_PORT=5004
TRADING_PORT=5005
WORKFLOW_PORT=5006
```

Save and exit (Ctrl+O, Enter, Ctrl+X)

---

## Part 3: Required Files

### Directory Structure

```
catalyst-trading-system/
├── services/
│   ├── scanner/
│   │   ├── scanner-service.py (v6.0.0)
│   │   └── requirements.txt
│   ├── news/
│   │   ├── news-service.py (v6.0.0)
│   │   └── requirements.txt
│   ├── technical/
│   │   ├── technical-service.py (v6.0.0)
│   │   └── requirements.txt
│   ├── risk-manager/
│   │   ├── risk-manager-service.py (v6.0.0)
│   │   └── requirements.txt
│   ├── trading/
│   │   ├── trading-service.py (v6.0.0)
│   │   └── requirements.txt
│   └── workflow/
│       ├── workflow-service.py (v6.0.0)
│       └── requirements.txt
├── scripts/
│   ├── create_catalyst_database_v60.sql
│   ├── start_all_services.sh
│   ├── cron-scan.sh
│   ├── cron-health-check.sh
│   └── catalyst.crontab
├── docker-compose.dev.yml
├── .env
└── Documentation/
    ├── phase5_implementation_guide.md
    └── COMPLETE_IMPLEMENTATION_GUIDE.md (this file)
```

### Required File: docker-compose.dev.yml

```yaml
version: '3.8'

services:
  # Local PostgreSQL for development/testing (optional)
  postgres:
    image: postgres:15-alpine
    container_name: catalyst-postgres-dev
    environment:
      POSTGRES_DB: catalyst_trading
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - catalyst-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: catalyst-redis-dev
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - catalyst-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:

networks:
  catalyst-network:
    driver: bridge
```

### Required File: requirements.txt (consolidated)

Create in project root for easy installation:

```txt
fastapi==0.115.4
uvicorn[standard]==0.32.0
asyncpg==0.30.0
redis==5.2.0
aiohttp==3.11.7
pydantic==2.9.2
python-multipart==0.0.17
yfinance==0.2.48
ta==0.11.0
pandas==2.2.3
numpy==2.1.3
python-dotenv==1.0.0
```

### Required File: start_all_services.sh

```bash
#!/bin/bash

# Load environment variables
export $(cat /workspaces/catalyst-trading-system/catalyst-trading-system/.env | xargs)

BASE_DIR="/workspaces/catalyst-trading-system/catalyst-trading-system/services"

echo "Starting Catalyst Trading System Services..."

# Scanner Service (Port 5001)
cd "$BASE_DIR/scanner"
nohup python3 scanner-service.py > /tmp/scanner.log 2>&1 &
echo "✓ Scanner Service started (PID: $!) - Port 5001"

# News Service (Port 5002)
cd "$BASE_DIR/news"
export SERVICE_PORT=5002
nohup python3 news-service.py > /tmp/news.log 2>&1 &
echo "✓ News Service started (PID: $!) - Port 5002"

# Technical Service (Port 5003)
cd "$BASE_DIR/technical"
export SERVICE_PORT=5003
nohup python3 technical-service.py > /tmp/technical.log 2>&1 &
echo "✓ Technical Service started (PID: $!) - Port 5003"

# Risk Manager Service (Port 5004)
cd "$BASE_DIR/risk-manager"
nohup python3 risk-manager-service.py > /tmp/risk-manager.log 2>&1 &
echo "✓ Risk Manager Service started (PID: $!) - Port 5004"

# Trading Service (Port 5005)
cd "$BASE_DIR/trading"
nohup python3 trading-service.py > /tmp/trading.log 2>&1 &
echo "✓ Trading Service started (PID: $!) - Port 5005"

# Workflow Service (Port 5006)
cd "$BASE_DIR/workflow"
nohup python3 workflow-service.py > /tmp/workflow.log 2>&1 &
echo "✓ Workflow Service started (PID: $!) - Port 5006"

echo ""
echo "All services started! Waiting 5 seconds for initialization..."
sleep 5

echo ""
echo "=== Service Health Check ==="
curl -s http://localhost:5001/health | python3 -m json.tool 2>/dev/null || echo "Scanner (5001): Not responding"
curl -s http://localhost:5002/health | python3 -m json.tool 2>/dev/null || echo "News (5002): Not responding"
curl -s http://localhost:5003/health | python3 -m json.tool 2>/dev/null || echo "Technical (5003): Not responding"
curl -s http://localhost:5004/health | python3 -m json.tool 2>/dev/null || echo "Risk Manager (5004): Not responding"
curl -s http://localhost:5005/health | python3 -m json.tool 2>/dev/null || echo "Trading (5005): Not responding"
curl -s http://localhost:5006/health | python3 -m json.tool 2>/dev/null || echo "Workflow (5006): Not responding"
```

---

## Part 4: Database Schema Setup

### Step 4.1: Create Database Schema

The complete v6.0 schema includes:
- 11 normalized tables (3NF)
- 16 foreign key relationships
- 2 helper functions (`get_or_create_security()`, `get_or_create_time()`)
- GICS sector reference data

**File**: `scripts/create_catalyst_database_v60.sql`

```bash
# Apply schema to DigitalOcean database
cd /workspaces/catalyst-trading-system/catalyst-trading-system/scripts

# Using the connection string from Step 1.2
psql "$DATABASE_URL" -f create_catalyst_database_v60.sql
```

### Step 4.2: Verify Schema

```bash
python3 << 'EOF'
import asyncpg
import asyncio
import os

async def verify():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))

    # Check tables
    tables = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    print(f"✅ Tables created: {len(tables)}")

    # Check helper functions
    funcs = await conn.fetch("""
        SELECT proname
        FROM pg_proc
        WHERE proname IN ('get_or_create_security', 'get_or_create_time')
    """)
    print(f"✅ Helper functions: {len(funcs)}/2")

    # Check sectors
    sectors = await conn.fetchval("SELECT COUNT(*) FROM sectors")
    print(f"✅ GICS sectors loaded: {sectors}")

    await conn.close()

asyncio.run(verify())
EOF
```

Expected output:
```
✅ Tables created: 11+
✅ Helper functions: 2/2
✅ GICS sectors loaded: 11
```

---

## Part 5: Install Dependencies

### Step 5.1: Install Python Dependencies

```bash
cd /workspaces/catalyst-trading-system/catalyst-trading-system

# Install all required packages
pip3 install -r requirements.txt
```

### Step 5.2: Start Docker Services (Redis)

```bash
# Start Redis cache
docker-compose -f docker-compose.dev.yml up -d redis

# Verify Redis is running
docker ps | grep redis
```

---

## Part 6: Start All Services

### Step 6.1: Make Scripts Executable

```bash
cd /workspaces/catalyst-trading-system/catalyst-trading-system

chmod +x scripts/*.sh
```

### Step 6.2: Start Services

```bash
# Start all 6 microservices
bash scripts/start_all_services.sh
```

### Step 6.3: Verify Services

All services should respond with health checks:

```bash
curl http://localhost:5001/health  # Scanner
curl http://localhost:5002/health  # News
curl http://localhost:5003/health  # Technical
curl http://localhost:5004/health  # Risk Manager
curl http://localhost:5005/health  # Trading
curl http://localhost:5006/health  # Workflow
```

Expected response (example):
```json
{
    "status": "healthy",
    "service": "scanner",
    "version": "6.0.0",
    "schema": "v6.0 3NF normalized",
    "database": "connected"
}
```

---

## Part 7: Cron Automation Setup

### Step 7.1: Install Cron

```bash
sudo apt-get update -qq
sudo apt-get install -y cron
sudo service cron start
```

### Step 7.2: Install Crontab

```bash
cd /workspaces/catalyst-trading-system/catalyst-trading-system

# Install automated schedule
crontab scripts/catalyst.crontab

# Verify installation
crontab -l
```

### Step 7.3: Verify Cron Jobs

```bash
# Check cron service
sudo service cron status

# Test health check manually
bash scripts/cron-health-check.sh
cat /tmp/catalyst-cron/health-$(date +%Y%m%d).log

# Test scan manually
bash scripts/cron-scan.sh
cat /tmp/catalyst-cron/scan-$(date +%Y%m%d).log
```

---

## Part 8: Testing the System

### Test 1: Health Check All Services

```bash
for port in 5001 5002 5003 5004 5005 5006; do
    echo "Port $port:"
    curl -s http://localhost:$port/health | python3 -m json.tool
    echo ""
done
```

### Test 2: Trigger Market Scan

```bash
curl -X POST http://localhost:5001/api/v1/scan \
  -H "Content-Type: application/json" | python3 -m json.tool
```

Expected response:
```json
{
    "success": true,
    "cycle_id": "20251118-001",
    "candidates": 0,
    "picks": [],
    "errors": null
}
```

### Test 3: Check Cycles

```bash
curl -s http://localhost:5006/api/v1/cycles | python3 -m json.tool
```

### Test 4: Database Verification

```bash
python3 << 'EOF'
import asyncpg
import asyncio
import os

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))

    tables = ['securities', 'trading_cycles', 'scan_results', 'positions']
    for table in tables:
        count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
        print(f'{table}: {count} records')

    await conn.close()

asyncio.run(check())
EOF
```

---

## Part 9: Monitoring & Maintenance

### View Service Logs

```bash
# Real-time logs
tail -f /tmp/scanner.log
tail -f /tmp/news.log
tail -f /tmp/technical.log
tail -f /tmp/risk-manager.log
tail -f /tmp/trading.log
tail -f /tmp/workflow.log
```

### View Cron Logs

```bash
# Today's scan log
cat /tmp/catalyst-cron/scan-$(date +%Y%m%d).log

# Today's health log
cat /tmp/catalyst-cron/health-$(date +%Y%m%d).log

# Live tail
tail -f /tmp/catalyst-cron/scan-$(date +%Y%m%d).log
```

### Check Running Services

```bash
ps aux | grep "python3.*-service.py" | grep -v grep
```

### Restart Services

```bash
# Kill all services
pkill -f "python3.*-service.py"

# Restart all
bash scripts/start_all_services.sh
```

---

## Part 10: Cron Schedule Details

### Automated Market Scans (Mon-Fri)

| Time (EST) | Time (UTC) | Cron Expression | Purpose |
|------------|------------|-----------------|---------|
| 09:15 AM | 14:15 | `15 14 * * 1-5` | Pre-market scan |
| 09:30 AM | 14:30 | `30 14 * * 1-5` | Market open |
| 10:30 AM | 15:30 | `30 15 * * 1-5` | Mid-morning |
| 12:00 PM | 17:00 | `0 17 * * 1-5` | Late morning |
| 01:30 PM | 18:30 | `30 18 * * 1-5` | Early afternoon |
| 03:00 PM | 20:00 | `0 20 * * 1-5` | Late afternoon |
| 04:00 PM | 21:00 | `0 21 * * 1-5` | Market close |

### Health Checks

- **Expression**: `*/15 * * * *`
- **Frequency**: Every 15 minutes
- **Schedule**: 24/7, all days

---

## Architecture Overview

### Service Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Client/User                        │
└─────────────────────┬───────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
    HTTP Requests            Automated Cron
         │                         │
         ↓                         ↓
┌─────────────────────────────────────────────────────┐
│               Microservices Layer                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Scanner  │ │   News   │ │Technical │           │
│  │  :5001   │ │  :5002   │ │  :5003   │           │
│  └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Risk   │ │ Trading  │ │Workflow  │           │
│  │  :5004   │ │  :5005   │ │  :5006   │           │
│  └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────┬───────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ↓                         ↓
┌──────────────────┐    ┌──────────────────┐
│  Redis Cache     │    │  PostgreSQL DB    │
│  (Local Docker)  │    │  (DigitalOcean)   │
│  Port: 6379      │    │  v6.0 3NF Schema  │
└──────────────────┘    └──────────────────┘
```

### Database Schema (v6.0 3NF)

**Core Tables:**
1. `sectors` - GICS sector master data
2. `securities` - Master securities table (no symbol duplication)
3. `time_dimension` - Time hierarchy for efficient queries
4. `trading_cycles` - Trading session tracking
5. `scan_results` - Market scan candidates
6. `positions` - Position tracking
7. `orders` - Order management
8. `news_sentiment` - News sentiment analysis
9. `technical_indicators` - Technical analysis data
10. `risk_events` - Risk management events
11. `trading_history` - Historical trade records

**Helper Functions:**
- `get_or_create_security(symbol)` - Returns security_id
- `get_or_create_time(timestamp)` - Returns time_id

**Key Features:**
- ✅ Full 3NF normalization
- ✅ 16 foreign key relationships
- ✅ No symbol duplication
- ✅ Proper JOINs throughout
- ✅ Helper functions for consistency

---

## Troubleshooting

### Issue: Services Won't Start

**Check logs:**
```bash
tail -50 /tmp/scanner.log
```

**Common causes:**
- Missing dependencies: Run `pip3 install -r requirements.txt`
- Port conflict: Check if ports 5001-5006 are available
- Database connection: Verify DATABASE_URL in .env

### Issue: Database Connection Failed

**Test connection:**
```bash
psql "$DATABASE_URL" -c "SELECT version();"
```

**Common causes:**
- Incorrect connection string in .env
- Firewall blocking connection (check DigitalOcean trusted sources)
- Database not provisioned yet

### Issue: Cron Jobs Not Running

**Check cron service:**
```bash
sudo service cron status
sudo service cron restart
```

**Verify crontab:**
```bash
crontab -l
```

**Check cron logs:**
```bash
grep CRON /var/log/syslog
```

### Issue: Helper Functions Not Found

**Verify functions exist:**
```bash
psql "$DATABASE_URL" -c "SELECT proname FROM pg_proc WHERE proname LIKE 'get_or_create%';"
```

**If missing, reapply schema:**
```bash
psql "$DATABASE_URL" -f scripts/create_catalyst_database_v60.sql
```

---

## Cost Breakdown

### DigitalOcean Database
- **Basic Plan**: $15/month
- **Professional Plan**: $50/month (recommended for production)
- **Includes**: Automated backups, high availability, 1-2 GB RAM

### GitHub Codespace
- **Free Tier**: 60 hours/month (sufficient for development)
- **Paid**: $0.18/hour for 4-core machine

### Total Estimated Cost
- **Development**: $15-30/month
- **Production**: $50-100/month

---

## Security Best Practices

1. **Never commit .env files**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use environment variables for secrets**
   - Never hardcode passwords
   - Rotate credentials regularly

3. **Enable SSL for database**
   - Already configured with `?sslmode=require`

4. **Restrict database access**
   - Use DigitalOcean's trusted sources feature
   - Limit to specific IP addresses in production

5. **Monitor logs regularly**
   - Check for unauthorized access attempts
   - Set up alerts for errors

---

## Next Steps

### Phase 6: Integration Testing
- End-to-end workflow testing
- Load testing
- Performance optimization

### Phase 7: Production Deployment
- Move to dedicated servers
- Set up monitoring (Datadog, New Relic)
- Configure alerting
- Implement CI/CD pipeline

### Phase 8: Advanced Features
- Machine learning integration
- Real-time market data feeds
- Advanced risk models
- Portfolio optimization

---

## Support & Resources

### Documentation
- Phase 5 Implementation Guide: `Documentation/phase5_implementation_guide.md`
- Cron Setup Guide: `CRON-README.md`
- Database Schema: `scripts/create_catalyst_database_v60.sql`

### Quick Commands Reference

```bash
# Start everything
bash scripts/start_all_services.sh

# Check health
for p in 5001 5002 5003 5004 5005 5006; do curl http://localhost:$p/health; done

# Trigger scan
curl -X POST http://localhost:5001/api/v1/scan

# View logs
tail -f /tmp/scanner.log

# Restart services
pkill -f "python3.*-service.py" && bash scripts/start_all_services.sh

# Check cron
crontab -l

# Database connection test
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM securities;"
```

---

## Conclusion

You now have a fully functional, production-ready trading system with:

✅ **6 Microservices** running on v6.0.0
✅ **DigitalOcean PostgreSQL** with 3NF normalized schema
✅ **Automated Cron Jobs** for market scanning and health monitoring
✅ **Redis Cache** for performance
✅ **Comprehensive Logging** for debugging and monitoring
✅ **Helper Functions** for data consistency

**System Status**: Fully operational and ready for trading! 🚀

---

**Version**: 1.0.0
**Last Updated**: November 18, 2025
**Schema Version**: v6.0 3NF Normalized
**Services Version**: 6.0.0
