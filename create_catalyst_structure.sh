#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: create_catalyst_structure.sh
# Version: 1.0.0
# Last Updated: 2025-01-18
# Purpose: Create complete folder structure for Catalyst Trading System

# REVISION HISTORY:
# v1.0.0 (2025-01-18) - Initial creation
# - Creates all directories and subdirectories
# - Generates placeholder files
# - Creates .env.template with all required variables
# - Sets proper permissions

# Description:
# This script creates the complete directory structure for the Catalyst Trading System,
# including all service directories, placeholder files, and configuration templates.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Catalyst Trading System - Structure Generator${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
}

print_section() {
    echo -e "\n${YELLOW}► $1${NC}"
}

# Get the target directory (default to current directory)
TARGET_DIR="${1:-catalyst-trading-system}"

print_header
echo "Creating Catalyst Trading System structure in: ${TARGET_DIR}"
echo ""

# Create main directory
print_section "Creating main project directory"
mkdir -p "${TARGET_DIR}"
cd "${TARGET_DIR}"
print_status "Created ${TARGET_DIR}"

# ============================================================================
# Create Services Directory Structure
# ============================================================================
print_section "Creating service directories"

# Service list with their subdirectories
declare -A service_subdirs
service_subdirs[pattern]="patterns"
service_subdirs[technical]="indicators"
service_subdirs[trading]="strategies models"
service_subdirs[news]="sources"

# Create each service directory
services=(
    "orchestration"
    "workflow"
    "scanner"
    "pattern"
    "technical"
    "risk-manager"
    "trading"
    "news"
    "reporting"
)

for service in "${services[@]}"; do
    mkdir -p "services/${service}"
    print_status "Created services/${service}"
    
    # Create subdirectories if needed
    if [[ -n "${service_subdirs[$service]}" ]]; then
        for subdir in ${service_subdirs[$service]}; do
            mkdir -p "services/${service}/${subdir}"
            print_status "  Created services/${service}/${subdir}"
            
            # Create __init__.py placeholder
            cat > "services/${service}/${subdir}/__init__.py" << 'EOF'
"""
Module placeholder for Docker build
"""
pass
EOF
            print_status "  Created services/${service}/${subdir}/__init__.py"
        done
    fi
    
    # Create placeholder requirements.txt for each service
    cat > "services/${service}/requirements.txt" << 'EOF'
# Core dependencies
fastapi==0.104.1
uvicorn==0.24.0
asyncpg==0.29.0
redis==5.0.1
pydantic==2.4.2
python-dotenv==1.0.0

# Service-specific dependencies (add as needed)
httpx==0.25.0
numpy==1.24.3
pandas==2.0.3
EOF
    print_status "Created services/${service}/requirements.txt"
    
    # Create placeholder Dockerfile for each service
    cat > "services/${service}/Dockerfile" << EOF
# Name of Application: Catalyst Trading System
# Service: ${service}
# Version: 1.0.0

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY *.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=${service}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import requests; requests.get('http://localhost:PORT/health')" || exit 1

# Run the service
CMD ["python", "-u", "${service}-service.py"]
EOF
    print_status "Created services/${service}/Dockerfile"
done

# ============================================================================
# Create Scripts Directory
# ============================================================================
print_section "Creating scripts directory"
mkdir -p "scripts"
print_status "Created scripts directory"

# Create placeholder scripts
scripts_files=(
    "manage.sh"
    "service_diagnostic.sh"
    "health-check.sh"
    "emergency-stop.sh"
    "recover-system.sh"
)

for script in "${scripts_files[@]}"; do
    cat > "scripts/${script}" << 'EOF'
#!/bin/bash
# Placeholder script - replace with actual implementation
echo "This is a placeholder for ${script}"
EOF
    chmod +x "scripts/${script}"
    print_status "Created scripts/${script}"
done

# Create cron setup file
cat > "scripts/catalyst-cron-setup.txt" << 'EOF'
# Catalyst Trading System - Cron Schedule
# Market Hours: Mon-Fri 21:00-09:00 Perth Time (04:00-20:00 EST)

# Health Checks (Every 15 minutes)
*/15 * * * * /root/catalyst-trading-mcp/scripts/health-check.sh >> /var/log/catalyst/health.log 2>&1

# Market Open (Mon-Fri 22:30 Perth = 09:30 EST)
30 22 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/start >> /var/log/catalyst/trading.log 2>&1

# Market Close (Mon-Fri 05:00 Perth = 16:00 EST)
0 5 * * 1-5 curl -X POST http://localhost:5006/api/v1/workflow/stop >> /var/log/catalyst/trading.log 2>&1

# Daily Backup (02:00 Perth)
0 2 * * * /root/catalyst-trading-mcp/scripts/backup.sh >> /var/log/catalyst/backup.log 2>&1
EOF
print_status "Created scripts/catalyst-cron-setup.txt"

# ============================================================================
# Create Configuration Files
# ============================================================================
print_section "Creating configuration files"

# Create .env.template
cat > ".env.template" << 'EOF'
# ============================================================================
# Catalyst Trading System - Environment Variables Template
# ============================================================================
# Copy this file to .env and fill in your actual values
# NEVER commit .env to version control!

# Database Configuration (DigitalOcean Managed PostgreSQL)
DATABASE_URL=postgresql://username:password@host:port/dbname?sslmode=require

# Service Ports (Internal Docker Network)
ORCHESTRATION_PORT=5000
SCANNER_PORT=5001
PATTERN_PORT=5002
TECHNICAL_PORT=5003
RISK_PORT=5004
TRADING_PORT=5005
WORKFLOW_PORT=5006
NEWS_PORT=5008
REPORTING_PORT=5009

# Alpaca Trading API
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# News APIs
NEWS_API_KEY=your_newsapi_key_here
BENZINGA_API_KEY=your_benzinga_key_here

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Service URLs (Internal Docker Network)
SCANNER_URL=http://scanner:5001
PATTERN_URL=http://pattern:5002
TECHNICAL_URL=http://technical:5003
RISK_URL=http://risk-manager:5004
TRADING_URL=http://trading:5005
NEWS_URL=http://news:5008
REPORTING_URL=http://reporting:5009
WORKFLOW_URL=http://workflow:5006

# Trading Configuration
MAX_DAILY_LOSS=1000
MAX_POSITION_SIZE=5000
MAX_POSITIONS=5
TRADING_MODE=paper

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Feature Flags
ENABLE_PAPER_TRADING=true
ENABLE_LIVE_TRADING=false
ENABLE_NEWS_SENTIMENT=true
ENABLE_PATTERN_DETECTION=true
EOF
print_status "Created .env.template"

# Create .gitignore
cat > ".gitignore" << 'EOF'
# Environment files
.env
.env.*
!.env.template
config/.env*
!config/.env.template

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST
*.pyc
*.pyo
*.pyd
.pytest_cache/
.coverage
htmlcov/

# Docker
postgres_data/
redis_data/
volume_*/
*.log

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
Thumbs.db
desktop.ini

# Trading data
logs/
data/
trades/
positions/
orders/
market_data/
backtests/

# API Keys and secrets
secrets/
keys/
credentials/
*.key
*.pem
*.p12
*.pfx

# Backups
*.sql
*.sql.gz
backups/
*.bak
EOF
print_status "Created .gitignore"

# Create docker-compose.yml
cat > "docker-compose.yml" << 'EOF'
# Name of Application: Catalyst Trading System
# Name of file: docker-compose.yml
# Version: 5.2.0
# Last Updated: 2025-01-18
# Purpose: Docker Compose orchestration for all services

version: '3.8'

services:
  # Redis Cache Service
  redis:
    image: redis:7-alpine
    container_name: catalyst-redis
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - catalyst-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Orchestration Service (MCP Interface)
  orchestration:
    build:
      context: ./services/orchestration
      dockerfile: Dockerfile
    container_name: catalyst-orchestration
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_HOST=redis
      - SERVICE_PORT=5000
    ports:
      - "5000:5000"
    networks:
      - catalyst-network
    depends_on:
      - redis
    restart: unless-stopped

  # Workflow Coordinator Service
  workflow:
    build:
      context: ./services/workflow
      dockerfile: Dockerfile
    container_name: catalyst-workflow
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_HOST=redis
      - SERVICE_PORT=5006
    ports:
      - "5006:5006"
    networks:
      - catalyst-network
    depends_on:
      - redis
    restart: unless-stopped

  # Scanner Service
  scanner:
    build:
      context: ./services/scanner
      dockerfile: Dockerfile
    container_name: catalyst-scanner
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_HOST=redis
      - SERVICE_PORT=5001
    ports:
      - "5001:5001"
    networks:
      - catalyst-network
    depends_on:
      - redis
    restart: unless-stopped

  # Additional services follow the same pattern...
  # (Pattern, Technical, Risk-Manager, Trading, News, Reporting)

networks:
  catalyst-network:
    driver: bridge
    name: catalyst-network

volumes:
  redis_data:
    name: catalyst-redis-data
EOF
print_status "Created docker-compose.yml"

# Create README.md
cat > "README.md" << 'EOF'
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
EOF
print_status "Created README.md"

# ============================================================================
# Create placeholder service files
# ============================================================================
print_section "Creating placeholder service files"

# Create minimal placeholder for each service
for service in "${services[@]}"; do
    cat > "services/${service}/${service}-service.py" << EOF
#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: ${service}-service.py
Version: 1.0.0
Last Updated: $(date +%Y-%m-%d)
Purpose: ${service} service placeholder

REVISION HISTORY:
v1.0.0 ($(date +%Y-%m-%d)) - Initial placeholder
- Basic FastAPI setup
- Health endpoint
- Placeholder for service logic

Description:
Placeholder for ${service} service implementation.
Replace with actual service code.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging

# Service configuration
SERVICE_NAME = "${service}"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "5000"))

# Initialize FastAPI
app = FastAPI(title=f"Catalyst {SERVICE_NAME.title()} Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_NAME)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": SERVICE_NAME,
        "status": "running",
        "message": "Replace this placeholder with actual service implementation"
    }

if __name__ == "__main__":
    logger.info(f"Starting {SERVICE_NAME} service on port {SERVICE_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
EOF
    print_status "Created services/${service}/${service}-service.py"
done

# ============================================================================
# Create additional directories
# ============================================================================
print_section "Creating additional directories"

additional_dirs=(
    "logs"
    "data"
    "backups"
    "tests"
    "docs"
)

for dir in "${additional_dirs[@]}"; do
    mkdir -p "${dir}"
    # Create .gitkeep to preserve empty directories
    touch "${dir}/.gitkeep"
    print_status "Created ${dir}/"
done

# ============================================================================
# Set permissions
# ============================================================================
print_section "Setting permissions"
chmod +x scripts/*.sh
print_status "Set executable permissions on scripts"

# ============================================================================
# Summary
# ============================================================================
print_header
echo -e "${GREEN}✓ Successfully created Catalyst Trading System structure!${NC}"
echo ""
echo "Project structure created in: ${TARGET_DIR}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. cd ${TARGET_DIR}"
echo "2. Copy .env.template to .env and add your credentials"
echo "3. Replace placeholder service files with actual implementations"
echo "4. Build Docker images: docker-compose build"
echo "5. Start services: docker-compose up -d"
echo ""
echo -e "${BLUE}Directory structure:${NC}"
tree -L 3 -d 2>/dev/null || find . -type d -maxdepth 3 | sed 's|^\./||' | sort | sed 's|^|  |'
echo ""
echo -e "${GREEN}Happy Trading! 🚀${NC}"
