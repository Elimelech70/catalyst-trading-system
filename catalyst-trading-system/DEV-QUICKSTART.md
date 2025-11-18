# Catalyst Trading System - Local Development Quick Start

## Overview
This guide helps you quickly get started with local development using Docker.

## Prerequisites
- Docker & Docker Compose installed
- Git
- Your favorite code editor (VSCode recommended)

## Quick Start (3 Steps)

### 1. Configure Environment Variables

Edit `.env.development` and add your API keys:

```bash
# Required for trading (use paper trading keys!)
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here

# Optional: Market data APIs
ALPHAVANTAGE_API_KEY=your_key_here
POLYGON_API_KEY=your_key_here

# Optional: News APIs
NEWS_API_KEY=your_key_here
FINNHUB_API_KEY=your_key_here
```

### 2. Start the Development Environment

```bash
# Start all services with local PostgreSQL
docker-compose -f docker-compose.dev.yml up -d

# Or start only infrastructure first
docker-compose -f docker-compose.dev.yml up -d postgres redis
```

### 3. Initialize the Database

```bash
./scripts/setup-dev-db.sh
```

## Verify Everything is Running

```bash
./scripts/health-check.sh
```

You should see all services showing ✅ HEALTHY.

## Daily Development Workflow

### Morning Startup
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Check health
./scripts/health-check.sh
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f orchestration
docker-compose -f docker-compose.dev.yml logs -f scanner
```

### Make Code Changes
Your code changes will auto-reload thanks to the `--reload` flag in the dev Dockerfiles!

Just edit files in `services/*/` and the containers will automatically restart.

### Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| Orchestration (MCP) | http://localhost:5000 | Main coordination service |
| Scanner | http://localhost:5001 | Market scanning |
| Pattern | http://localhost:5002 | Pattern detection |
| Technical | http://localhost:5003 | Technical indicators |
| Risk Manager | http://localhost:5004 | Risk management |
| Trading | http://localhost:5005 | Order execution |
| Workflow | http://localhost:5006 | Trade coordination |
| News | http://localhost:5008 | News intelligence |
| Reporting | http://localhost:5009 | Performance reports |

### Database Access

```bash
# Connect to PostgreSQL
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev

# Connect to Redis
docker-compose -f docker-compose.dev.yml exec redis redis-cli
```

### Restart Services

```bash
# Restart specific service
docker-compose -f docker-compose.dev.yml restart scanner

# Restart all services
docker-compose -f docker-compose.dev.yml restart
```

### Rebuild After Dependency Changes

```bash
# Rebuild specific service
docker-compose -f docker-compose.dev.yml build --no-cache scanner
docker-compose -f docker-compose.dev.yml up -d scanner

# Rebuild all services
docker-compose -f docker-compose.dev.yml build --no-cache
docker-compose -f docker-compose.dev.yml up -d
```

### Shutdown

```bash
# Stop services (keep data)
docker-compose -f docker-compose.dev.yml down

# Stop and remove volumes (CAUTION: deletes database!)
docker-compose -f docker-compose.dev.yml down -v
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose -f docker-compose.dev.yml logs [service-name]

# Rebuild the service
docker-compose -f docker-compose.dev.yml build --no-cache [service-name]
docker-compose -f docker-compose.dev.yml up -d [service-name]
```

### Database issues
```bash
# Reset database
docker-compose -f docker-compose.dev.yml down
docker volume rm catalyst_trading_dev_postgres_dev_data
./scripts/setup-dev-db.sh
```

### Port conflicts
If you see port conflicts, another service may be using the ports. Check:
```bash
# Check what's using port 5432 (PostgreSQL)
lsof -i :5432

# Check what's using port 6379 (Redis)
lsof -i :6379
```

### Hot reload not working
Make sure you're using the dev compose file:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

## Key Differences: Dev vs Production

| Feature | Development | Production |
|---------|------------|------------|
| Database | Local PostgreSQL | DigitalOcean Managed |
| Compose File | `docker-compose.dev.yml` | `docker-compose.yml` |
| Dockerfiles | `Dockerfile.dev` | `Dockerfile` |
| Hot Reload | ✅ Enabled | ❌ Disabled |
| Debug Mode | ✅ Enabled | ❌ Disabled |
| Container Names | `*-dev` suffix | No suffix |
| Volumes | Mounted for editing | Copied at build |

## What's Next?

1. **Add Database Schema**: Update `scripts/init-db.sql` with your v6.0 schema
2. **VSCode Integration**: See `Documentation/local-docker-dev-setup.md` for VSCode setup
3. **MCP Integration**: Configure Claude Desktop integration
4. **Write Tests**: Add tests to each service

## Helpful Commands Cheat Sheet

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View all logs
docker-compose -f docker-compose.dev.yml logs -f

# Check health
./scripts/health-check.sh

# Setup database
./scripts/setup-dev-db.sh

# Connect to database
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev

# Restart service
docker-compose -f docker-compose.dev.yml restart [service]

# Rebuild service
docker-compose -f docker-compose.dev.yml build --no-cache [service]

# Stop everything
docker-compose -f docker-compose.dev.yml down

# Nuclear option (reset everything)
docker-compose -f docker-compose.dev.yml down -v
```

## Support

For detailed setup instructions, see `Documentation/local-docker-dev-setup.md`.
