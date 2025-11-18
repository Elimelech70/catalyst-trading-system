# Catalyst Trading System

## Overview
The Catalyst Trading System is a sophisticated automated trading platform implementing Ross Cameron's momentum trading methodology enhanced with AI-assisted decision-making.

## Architecture
- 9 Microservices architecture
- MCP (Model Context Protocol) integration via Orchestration service
- PostgreSQL database (DigitalOcean managed)
- Redis caching layer
- Docker Compose orchestration

## Services
1. **Orchestration** (Port 5000) - MCP interface for Claude Desktop
2. **Workflow** (Port 5006) - Trade coordination and pipeline management
3. **Scanner** (Port 5001) - Market scanning and opportunity detection
4. **Pattern** (Port 5002) - Pattern recognition and analysis
5. **Technical** (Port 5003) - Technical indicator calculations
6. **Risk Manager** (Port 5004) - Risk validation and position sizing
7. **Trading** (Port 5005) - Order execution via Alpaca
8. **News** (Port 5008) - News sentiment and catalyst detection
9. **Reporting** (Port 5009) - Performance analytics and reporting

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- PostgreSQL database (DigitalOcean managed recommended)
- Alpaca trading account
- News API keys

### 2. Configuration
```bash
# Copy environment template
cp .env.template .env

# Edit .env with your credentials
nano .env
```

### 3. Build and Deploy
```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# Check service health
docker-compose ps
```

### 4. Monitoring
```bash
# View logs
docker-compose logs -f

# Check specific service
docker-compose logs orchestration --tail=50

# Run health check
./scripts/health-check.sh
```

## Production Deployment
See `scripts/catalyst-cron-setup.txt` for production cron schedule configuration.

## License
Proprietary - All rights reserved
