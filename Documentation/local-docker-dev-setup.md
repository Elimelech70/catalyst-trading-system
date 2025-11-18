# Name of Application: Catalyst Trading System
# Name of file: local-docker-dev-setup.md  
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Complete guide for setting up a local Docker development environment with VSCode and Claude Code

# REVISION HISTORY:
# v1.0.0 (2025-11-18) - Initial setup guide
# - Local Docker environment configuration
# - VSCode development setup
# - Claude Code integration
# - Local PostgreSQL database
# - Complete microservices architecture

# Description of Document:
# This guide walks through setting up a complete local development environment
# for the Catalyst Trading System on a new computer, including Docker setup,
# local database, VSCode configuration, and Claude Code integration.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Structure](#2-project-structure)
3. [Docker Environment Setup](#3-docker-environment-setup)
4. [Database Configuration](#4-database-configuration)
5. [Service Configuration](#5-service-configuration)
6. [VSCode Setup](#6-vscode-setup)
7. [Claude Code Integration](#7-claude-code-integration)
8. [Testing & Validation](#8-testing--validation)
9. [Development Workflow](#9-development-workflow)

---

## 1. Prerequisites

### 1.1 Required Software

```bash
# Windows/Mac/Linux requirements:
- Docker Desktop (latest version)
- VSCode (latest version)
- Git
- Python 3.11+
- PostgreSQL client tools (psql)
- Claude Desktop App
- Claude Code CLI tool
```

### 1.2 Installation Steps

#### Windows
```powershell
# Install Docker Desktop
winget install Docker.DockerDesktop

# Install VSCode
winget install Microsoft.VisualStudioCode

# Install Git
winget install Git.Git

# Install Python
winget install Python.Python.3.11

# Install PostgreSQL tools
winget install PostgreSQL.PostgreSQL
```

#### Mac
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker Desktop
brew install --cask docker

# Install VSCode
brew install --cask visual-studio-code

# Install Git, Python, PostgreSQL
brew install git python@3.11 postgresql
```

#### Linux (Ubuntu/Debian)
```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install VSCode
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
sudo install -o root -g root -m 644 packages.microsoft.gpg /etc/apt/trusted.gpg.d/
sudo sh -c 'echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/trusted.gpg.d/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
sudo apt update
sudo apt install code

# Install other tools
sudo apt install git python3.11 postgresql-client
```

---

## 2. Project Structure

### 2.1 Create Directory Structure

```bash
# Create main project directory
mkdir -p ~/Development/catalyst-trading-local
cd ~/Development/catalyst-trading-local

# Clone the repository (replace with your actual repo URL)
git clone https://github.com/your-org/catalyst-trading-system.git .

# Create required directories
mkdir -p services/{orchestration,scanner,pattern,technical,risk-manager,trading,workflow,news,reporting}
mkdir -p config
mkdir -p scripts
mkdir -p data/{postgres,redis,logs,backups}
mkdir -p .vscode
```

### 2.2 Expected Structure

```
catalyst-trading-local/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.development
├── .gitignore
├── README.md
├── services/
│   ├── orchestration/
│   │   ├── Dockerfile
│   │   ├── orchestration-service.py
│   │   └── requirements.txt
│   ├── scanner/
│   ├── pattern/
│   ├── technical/
│   ├── risk-manager/
│   ├── trading/
│   ├── workflow/
│   ├── news/
│   └── reporting/
├── config/
│   └── claude-mcp-config.json
├── scripts/
│   ├── setup-dev.sh
│   ├── health-check.sh
│   └── reset-db.sh
├── data/
│   ├── postgres/
│   ├── redis/
│   ├── logs/
│   └── backups/
└── .vscode/
    ├── settings.json
    ├── launch.json
    └── tasks.json
```

---

## 3. Docker Environment Setup

### 3.1 Create docker-compose.dev.yml

```yaml
# Name of Application: Catalyst Trading System
# Name of file: docker-compose.dev.yml
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Local development Docker Compose configuration

version: '3.8'

networks:
  catalyst-dev-network:
    driver: bridge

volumes:
  postgres_dev_data:
  redis_dev_data:

services:
  # ==========================================================================
  # LOCAL POSTGRESQL DATABASE
  # ==========================================================================
  postgres:
    image: postgres:15-alpine
    container_name: catalyst-postgres-dev
    environment:
      POSTGRES_USER: catalyst_user
      POSTGRES_PASSWORD: catalyst_dev_password
      POSTGRES_DB: catalyst_trading_dev
      POSTGRES_HOST_AUTH_METHOD: md5
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    networks:
      - catalyst-dev-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U catalyst_user -d catalyst_trading_dev"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ==========================================================================
  # REDIS CACHE SERVICE
  # ==========================================================================
  redis:
    image: redis:7-alpine
    container_name: catalyst-redis-dev
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_dev_data:/data
    networks:
      - catalyst-dev-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ==========================================================================
  # ORCHESTRATION SERVICE (MCP)
  # ==========================================================================
  orchestration:
    build:
      context: ./services/orchestration
      dockerfile: Dockerfile.dev
    container_name: catalyst-orchestration-dev
    environment:
      SERVICE_PORT: 5000
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      SCANNER_URL: http://scanner:5001
      PATTERN_URL: http://pattern:5002
      TECHNICAL_URL: http://technical:5003
      RISK_URL: http://risk-manager:5004
      TRADING_URL: http://trading:5005
      WORKFLOW_URL: http://workflow:5006
      NEWS_URL: http://news:5008
      REPORTING_URL: http://reporting:5009
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5000:5000"
    volumes:
      - ./services/orchestration:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # SCANNER SERVICE
  # ==========================================================================
  scanner:
    build:
      context: ./services/scanner
      dockerfile: Dockerfile.dev
    container_name: catalyst-scanner-dev
    environment:
      SERVICE_PORT: 5001
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      ALPACA_API_KEY: ${ALPACA_API_KEY}
      ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY}
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5001:5001"
    volumes:
      - ./services/scanner:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # PATTERN DETECTION SERVICE
  # ==========================================================================
  pattern:
    build:
      context: ./services/pattern
      dockerfile: Dockerfile.dev
    container_name: catalyst-pattern-dev
    environment:
      SERVICE_PORT: 5002
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5002:5002"
    volumes:
      - ./services/pattern:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # TECHNICAL ANALYSIS SERVICE
  # ==========================================================================
  technical:
    build:
      context: ./services/technical
      dockerfile: Dockerfile.dev
    container_name: catalyst-technical-dev
    environment:
      SERVICE_PORT: 5003
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5003:5003"
    volumes:
      - ./services/technical:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # RISK MANAGER SERVICE
  # ==========================================================================
  risk-manager:
    build:
      context: ./services/risk-manager
      dockerfile: Dockerfile.dev
    container_name: catalyst-risk-manager-dev
    environment:
      SERVICE_PORT: 5004
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5004:5004"
    volumes:
      - ./services/risk-manager:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # TRADING SERVICE
  # ==========================================================================
  trading:
    build:
      context: ./services/trading
      dockerfile: Dockerfile.dev
    container_name: catalyst-trading-dev
    environment:
      SERVICE_PORT: 5005
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      ALPACA_API_KEY: ${ALPACA_API_KEY}
      ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY}
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5005:5005"
    volumes:
      - ./services/trading:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # WORKFLOW SERVICE
  # ==========================================================================
  workflow:
    build:
      context: ./services/workflow
      dockerfile: Dockerfile.dev
    container_name: catalyst-workflow-dev
    environment:
      SERVICE_PORT: 5006
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      SCANNER_URL: http://scanner:5001
      PATTERN_URL: http://pattern:5002
      TECHNICAL_URL: http://technical:5003
      RISK_URL: http://risk-manager:5004
      TRADING_URL: http://trading:5005
      NEWS_URL: http://news:5008
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5006:5006"
    volumes:
      - ./services/workflow:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # NEWS INTELLIGENCE SERVICE
  # ==========================================================================
  news:
    build:
      context: ./services/news
      dockerfile: Dockerfile.dev
    container_name: catalyst-news-dev
    environment:
      SERVICE_PORT: 5008
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      NEWS_API_KEY: ${NEWS_API_KEY}
      FINNHUB_API_KEY: ${FINNHUB_API_KEY}
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5008:5008"
    volumes:
      - ./services/news:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network

  # ==========================================================================
  # REPORTING SERVICE
  # ==========================================================================
  reporting:
    build:
      context: ./services/reporting
      dockerfile: Dockerfile.dev
    container_name: catalyst-reporting-dev
    environment:
      SERVICE_PORT: 5009
      DATABASE_URL: postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev
      REDIS_HOST: redis
      REDIS_PORT: 6379
      PYTHONUNBUFFERED: 1
      ENV: development
    ports:
      - "5009:5009"
    volumes:
      - ./services/reporting:/app
      - ./data/logs:/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - catalyst-dev-network
```

### 3.2 Create .env.development

```bash
# Name of Application: Catalyst Trading System
# Name of file: .env.development
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Environment variables for local development

# Database Configuration (Local)
DATABASE_URL=postgresql://catalyst_user:catalyst_dev_password@localhost:5432/catalyst_trading_dev
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=catalyst_trading_dev
DATABASE_USER=catalyst_user
DATABASE_PASSWORD=catalyst_dev_password

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379

# API Keys (Use test/paper trading keys)
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# News API Keys
NEWS_API_KEY=your_newsapi_key_here
FINNHUB_API_KEY=your_finnhub_key_here

# Service URLs (Docker internal network)
ORCHESTRATION_URL=http://localhost:5000
SCANNER_URL=http://localhost:5001
PATTERN_URL=http://localhost:5002
TECHNICAL_URL=http://localhost:5003
RISK_URL=http://localhost:5004
TRADING_URL=http://localhost:5005
WORKFLOW_URL=http://localhost:5006
NEWS_URL=http://localhost:5008
REPORTING_URL=http://localhost:5009

# Environment
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Trading Configuration
MAX_POSITIONS=5
MAX_POSITION_SIZE=10000
RISK_PERCENT=0.01
STOP_LOSS_PERCENT=0.02
TAKE_PROFIT_PERCENT=0.05

# Market Hours (EST)
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
PRE_MARKET_OPEN=04:00
AFTER_HOURS_CLOSE=20:00
```

---

## 4. Database Configuration

### 4.1 Create Database Init Script

Create `scripts/init-db.sql`:

```sql
-- Name of Application: Catalyst Trading System
-- Name of file: init-db.sql
-- Version: 6.0.0
-- Last Updated: 2025-11-18
-- Purpose: Initialize local development database with v6.0 schema

-- Create database if not exists
SELECT 'CREATE DATABASE catalyst_trading_dev'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'catalyst_trading_dev')\gexec

-- Connect to the database
\c catalyst_trading_dev;

-- Create schema
CREATE SCHEMA IF NOT EXISTS catalyst;

-- Set search path
SET search_path TO catalyst, public;

-- Import the normalized schema (you'll need to copy this from your repo)
-- This is a placeholder - replace with actual schema from normalized-database-schema-mcp-v60.sql
-- You can copy the content from your GitHub repo

-- Create tables, indexes, and relationships as per v6.0 schema
-- ... (include full schema here)
```

### 4.2 Database Setup Script

Create `scripts/setup-dev-db.sh`:

```bash
#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: setup-dev-db.sh
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Setup and initialize local development database

set -e

echo "Setting up Catalyst Trading System Development Database..."

# Start PostgreSQL container if not running
docker-compose -f docker-compose.dev.yml up -d postgres

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker-compose -f docker-compose.dev.yml exec postgres pg_isready -U catalyst_user; do
  sleep 2
done

echo "PostgreSQL is ready!"

# Run schema initialization
echo "Initializing database schema..."
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev -f /docker-entrypoint-initdb.d/init.sql

echo "Database setup complete!"

# Show database info
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev -c "\dt"
```

---

## 5. Service Configuration

### 5.1 Create Dockerfile.dev for Each Service

Example `services/orchestration/Dockerfile.dev`:

```dockerfile
# Name of Application: Catalyst Trading System
# Name of file: Dockerfile.dev
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Development Dockerfile with hot reload support

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install development tools
RUN pip install --no-cache-dir \
    watchdog \
    ipython \
    ipdb \
    pytest \
    pytest-asyncio \
    pytest-cov

# Copy application code
COPY . .

# Development command with auto-reload
CMD ["python", "-m", "watchdog.auto_restart", "--directory", ".", "--pattern", "*.py", "--", "python", "orchestration-service.py"]
```

### 5.2 Create requirements.txt for Each Service

Example `services/orchestration/requirements.txt`:

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
fastmcp==0.1.0
asyncpg==0.29.0
redis==5.0.1
aiohttp==3.9.1
pydantic==2.5.0
python-dotenv==1.0.0
structlog==23.2.0
prometheus-client==0.19.0
```

---

## 6. VSCode Setup

### 6.1 Create .vscode/settings.json

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    ".pytest_cache": true,
    "*.egg-info": true
  },
  "docker.defaultRegistryPath": "localhost:5000",
  "terminal.integrated.defaultProfile.windows": "Git Bash",
  "terminal.integrated.defaultProfile.linux": "bash",
  "terminal.integrated.defaultProfile.osx": "zsh"
}
```

### 6.2 Create .vscode/launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Docker: Attach to Orchestration",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/services/orchestration",
          "remoteRoot": "/app"
        }
      ]
    },
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env.development"
    },
    {
      "name": "Docker Compose Up",
      "type": "shell",
      "command": "docker-compose -f docker-compose.dev.yml up",
      "problemMatcher": []
    }
  ]
}
```

### 6.3 Create .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start Development Environment",
      "type": "shell",
      "command": "docker-compose -f docker-compose.dev.yml up",
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "problemMatcher": []
    },
    {
      "label": "Stop Development Environment",
      "type": "shell",
      "command": "docker-compose -f docker-compose.dev.yml down",
      "problemMatcher": []
    },
    {
      "label": "Rebuild Services",
      "type": "shell",
      "command": "docker-compose -f docker-compose.dev.yml build --no-cache",
      "problemMatcher": []
    },
    {
      "label": "View Logs",
      "type": "shell",
      "command": "docker-compose -f docker-compose.dev.yml logs -f",
      "problemMatcher": []
    },
    {
      "label": "Run Tests",
      "type": "shell",
      "command": "docker-compose -f docker-compose.dev.yml exec orchestration pytest",
      "problemMatcher": []
    }
  ]
}
```

---

## 7. Claude Code Integration

### 7.1 Install Claude Code

```bash
# Install Claude Code CLI
npm install -g @anthropic/claude-code

# Verify installation
claude-code --version

# Authenticate with your API key
claude-code auth login
```

### 7.2 Create Claude MCP Configuration

Create `config/claude-mcp-config.json`:

```json
{
  "mcpServers": {
    "catalyst-local": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "catalyst-orchestration-dev",
        "python",
        "orchestration-service.py"
      ],
      "env": {
        "MCP_MODE": "stdio",
        "DATABASE_URL": "postgresql://catalyst_user:catalyst_dev_password@postgres:5432/catalyst_trading_dev"
      }
    }
  }
}
```

### 7.3 Configure Claude Desktop

1. Open Claude Desktop settings
2. Go to "Developer" tab
3. Click "Edit Config"
4. Add the configuration:

```json
{
  "mcpServers": {
    "catalyst-local": {
      "command": "python",
      "args": ["C:\\Development\\catalyst-trading-local\\scripts\\mcp-bridge.py"],
      "env": {
        "ORCHESTRATION_URL": "http://localhost:5000"
      }
    }
  }
}
```

### 7.4 Create MCP Bridge Script

Create `scripts/mcp-bridge.py`:

```python
#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: mcp-bridge.py
Version: 1.0.0
Last Updated: 2025-11-18
Purpose: Local MCP bridge for Claude Desktop to Docker services
"""

import asyncio
import aiohttp
import json
import sys
import os
from typing import Any, Dict

class MCPBridge:
    def __init__(self):
        self.orchestration_url = os.getenv("ORCHESTRATION_URL", "http://localhost:5000")
        
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Forward MCP requests to the orchestration service"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.orchestration_url}/mcp",
                json=request
            ) as response:
                return await response.json()
    
    async def run(self):
        """Main loop for handling MCP protocol over stdio"""
        while True:
            try:
                # Read from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break
                    
                # Parse JSON request
                request = json.loads(line.strip())
                
                # Forward to orchestration service
                response = await self.handle_request(request)
                
                # Write response to stdout
                print(json.dumps(response), flush=True)
                
            except Exception as e:
                error_response = {
                    "error": str(e),
                    "type": "bridge_error"
                }
                print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    bridge = MCPBridge()
    asyncio.run(bridge.run())
```

---

## 8. Testing & Validation

### 8.1 Start Services

```bash
# Navigate to project directory
cd ~/Development/catalyst-trading-local

# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Check service health
docker-compose -f docker-compose.dev.yml ps

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

### 8.2 Health Check Script

Create `scripts/health-check.sh`:

```bash
#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: health-check.sh
# Version: 1.0.0
# Last Updated: 2025-11-18
# Purpose: Check health of all local services

echo "Checking Catalyst Trading System Services..."
echo "=========================================="

# Check each service
services=(
    "orchestration:5000"
    "scanner:5001"
    "pattern:5002"
    "technical:5003"
    "risk-manager:5004"
    "trading:5005"
    "workflow:5006"
    "news:5008"
    "reporting:5009"
)

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health)
    
    if [ "$response" = "200" ]; then
        echo "✅ $name (port $port): HEALTHY"
    else
        echo "❌ $name (port $port): UNHEALTHY (HTTP $response)"
    fi
done

# Check database
echo ""
echo "Checking Database Connection..."
docker-compose -f docker-compose.dev.yml exec postgres pg_isready -U catalyst_user -d catalyst_trading_dev
```

### 8.3 Test MCP Integration

```bash
# Test orchestration MCP endpoint
curl -X POST http://localhost:5000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "resources/list"}'

# Test workflow trigger
curl -X POST http://localhost:5006/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"trigger": "manual", "mode": "test"}'
```

---

## 9. Development Workflow

### 9.1 Daily Development Tasks

```bash
# Morning startup
cd ~/Development/catalyst-trading-local
docker-compose -f docker-compose.dev.yml up -d
./scripts/health-check.sh

# Open VSCode
code .

# Connect Claude Code
claude-code connect

# View logs in terminal
docker-compose -f docker-compose.dev.yml logs -f orchestration
```

### 9.2 Making Code Changes

1. **Edit code in VSCode** - Changes auto-reload in containers
2. **Test changes** - Use VSCode tasks or terminal
3. **Commit to Git** - Regular commits with clear messages
4. **Run tests** - `docker-compose exec [service] pytest`

### 9.3 Database Management

```bash
# Connect to database
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user -d catalyst_trading_dev

# Backup database
docker-compose -f docker-compose.dev.yml exec postgres pg_dump -U catalyst_user catalyst_trading_dev > backup.sql

# Restore database
docker-compose -f docker-compose.dev.yml exec postgres psql -U catalyst_user catalyst_trading_dev < backup.sql

# Reset database
./scripts/reset-db.sh
```

### 9.4 Troubleshooting

```bash
# Check container logs
docker-compose -f docker-compose.dev.yml logs [service-name]

# Restart a specific service
docker-compose -f docker-compose.dev.yml restart [service-name]

# Rebuild service after dependency changes
docker-compose -f docker-compose.dev.yml build --no-cache [service-name]
docker-compose -f docker-compose.dev.yml up -d [service-name]

# Full reset
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
```

---

## Quick Start Commands

```bash
# Clone and setup (one-time)
git clone [your-repo] ~/Development/catalyst-trading-local
cd ~/Development/catalyst-trading-local
cp .env.example .env.development
# Edit .env.development with your API keys

# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Verify everything is running
./scripts/health-check.sh

# Open in VSCode
code .

# Stop when done
docker-compose -f docker-compose.dev.yml down
```

---

## Next Steps

1. **Configure API Keys**: Add your Alpaca, NewsAPI keys to `.env.development`
2. **Import Database Schema**: Copy v6.0 schema to `scripts/init-db.sql`
3. **Setup Services**: Copy service code from production repo
4. **Test MCP**: Verify Claude Desktop can connect
5. **Start Developing**: Make changes, test locally, then deploy

---

**END OF LOCAL DEVELOPMENT SETUP GUIDE**

*This setup provides a complete local development environment that mirrors production while allowing for easy debugging and testing with VSCode and Claude Code.*
