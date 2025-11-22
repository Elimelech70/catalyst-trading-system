# Catalyst Trading System - Complete Deployment Guide

**Name of Application**: Catalyst Trading System  
**Name of file**: catalyst-deployment-guide.md  
**Version**: 1.0.0  
**Last Updated**: 2025-11-20  
**Purpose**: Complete deployment guide from fresh droplet to operational system

---

## REVISION HISTORY

**v1.0.0 (2025-11-20)** - Initial deployment guide
- Claude Code installation as Phase 1
- Complete system setup from wiped droplet
- All 9 services deployment
- Cron automation setup
- Security configuration

---

## Prerequisites Completed ✅
- Droplet wiped clean
- Critical information backed up (.env contents, API keys)
- Database connection string saved
- SSH access verified

---

## Phase 1: Install Claude Code (SSH Direct Access)

```bash
# 1. Install Claude Code on the droplet
curl -fsSL https://cdn.claude.ai/code/install.sh | sh

# 2. Verify installation
claude-code --version

# 3. Authenticate Claude Code
claude-code auth login

# 4. Configure Claude Code for direct SSH usage
# This allows Claude to work directly on the production server
claude-code config set remote.enabled true

# 5. Test Claude Code connection
claude-code status

# 6. Create Claude workspace directory
mkdir -p /root/claude-workspace
cd /root/claude-workspace

# 7. Initialize Claude Code in the workspace
claude-code init

# Note: Claude Code will now have direct SSH access to manage the system
```

---

## Phase 2: System Preparation

```bash
# 1. Update the system
apt-get update && apt-get upgrade -y

# 2. Install required tools
apt-get install -y \
    git \
    curl \
    jq \
    postgresql-client \
    python3-pip \
    cron \
    logrotate \
    net-tools \
    htop \
    vim \
    wget \
    unzip

# 3. Ensure Docker and Docker Compose are up to date
docker --version
docker-compose --version

# If Docker Compose version < 2.20, update it:
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 4. Set timezone to Perth
timedatectl set-timezone Australia/Perth

# 5. Verify timezone (should show Australia/Perth)
timedatectl

# 6. Setup Python environment (for utilities)
pip3 install --upgrade pip
pip3 install python-dotenv asyncpg aiohttp
```

---

## Phase 3: Clone and Setup Repository

```bash
# 1. Navigate to home directory
cd /root

# 2. Clone your GitHub repository
# IMPORTANT: Replace with your actual GitHub URL
git clone https://github.com/<your-username>/<your-repo-name>.git catalyst-trading-mcp

# Alternative if using SSH key:
# git clone git@github.com:<your-username>/<your-repo-name>.git catalyst-trading-mcp

# 3. Navigate to project directory
cd catalyst-trading-mcp

# 4. Create required directory structure
mkdir -p scripts
mkdir -p services
mkdir -p config
mkdir -p /var/log/catalyst
mkdir -p /backups/catalyst
mkdir -p /backups/catalyst/database
mkdir -p /backups/catalyst/configs

# 5. Set proper permissions
chmod 755 scripts
chmod 755 services
chmod 755 config
chmod 755 /var/log/catalyst
chmod 755 /backups/catalyst

# 6. Verify directory structure
tree -L 2 /root/catalyst-trading-mcp || ls -la /root/catalyst-trading-mcp
```

---

## Phase 4: Environment Configuration

```bash
# 1. Create .env file from your backup
cd /root/catalyst-trading-mcp
nano .env

# Add all required environment variables:
# Copy and paste your backed-up environment variables
# Ensure these critical variables are set:

# === Database Configuration ===
DATABASE_URL=postgresql://username:password@your-db-host:port/catalyst_trading

# === Alpaca Trading API ===
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# === News APIs ===
NEWS_API_KEY=your_newsapi_key
BENZINGA_API_KEY=your_benzinga_key

# === Redis Configuration ===
REDIS_URL=redis://redis:6379

# === Service Ports ===
ORCHESTRATION_PORT=5000
SCANNER_PORT=5001
PATTERN_PORT=5002
TECHNICAL_PORT=5003
RISK_MANAGER_PORT=5004
TRADING_PORT=5005
WORKFLOW_PORT=5006
NEWS_PORT=5008
REPORTING_PORT=5009

# === System Configuration ===
TZ=Australia/Perth
ENVIRONMENT=production
LOG_LEVEL=INFO

# 2. Save and exit (Ctrl+X, Y, Enter)

# 3. Create .env.example for documentation
cp .env .env.example

# 4. Remove sensitive values from example
sed -i 's/=.*/=/' .env.example

# 5. Verify environment file exists and has content
wc -l .env
grep -c "=" .env

# 6. Test environment variable loading
source .env
echo "Database configured: ${DATABASE_URL:0:20}..."
```

---

## Phase 5: Database Setup and Verification

```bash
# 1. Install psql if not present
apt-get install -y postgresql-client

# 2. Test database connection
source /root/catalyst-trading-mcp/.env
psql "$DATABASE_URL" -c "SELECT version();"

# 3. Check if schema exists
psql "$DATABASE_URL" -c "\dt" > /tmp/tables.txt
cat /tmp/tables.txt

# 4. If tables don't exist, deploy schema
# (Only if you have the schema file in your repo)
if [ -f "normalized-database-schema-mcp-v60.sql" ]; then
    echo "Deploying database schema..."
    psql "$DATABASE_URL" -f normalized-database-schema-mcp-v60.sql
else
    echo "Schema file not found. Ensure database is already configured."
fi

# 5. Verify critical tables exist
psql "$DATABASE_URL" -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"

# 6. Test database write permission
psql "$DATABASE_URL" -c "CREATE TABLE IF NOT EXISTS health_check (id SERIAL PRIMARY KEY, check_time TIMESTAMP DEFAULT NOW());"
psql "$DATABASE_URL" -c "INSERT INTO health_check DEFAULT VALUES;"
psql "$DATABASE_URL" -c "SELECT * FROM health_check ORDER BY check_time DESC LIMIT 1;"
```

---

## Phase 6: Docker Services Deployment

```bash
# 1. Navigate to project directory
cd /root/catalyst-trading-mcp

# 2. Verify docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found!"
    echo "Please ensure it's in your repository"
    exit 1
fi

# 3. Validate docker-compose configuration
docker-compose config > /dev/null
if [ $? -eq 0 ]; then
    echo "Docker Compose configuration is valid"
else
    echo "ERROR: Invalid docker-compose.yml"
    exit 1
fi

# 4. Pull all required base images
docker-compose pull

# 5. Build all services with no cache
docker-compose build --no-cache

# 6. Start services in dependency order
# Start Redis first (required by all services)
docker-compose up -d redis
echo "Waiting for Redis to start..."
sleep 10

# Start News service (required by Scanner)
docker-compose up -d news-service
echo "Waiting for News service to start..."
sleep 10

# Start infrastructure services
docker-compose up -d pattern-service technical-service
sleep 5

# Start Scanner (depends on News)
docker-compose up -d scanner-service
sleep 5

# Start Risk Manager
docker-compose up -d risk-manager-service
sleep 5

# Start Trading service (depends on Risk Manager)
docker-compose up -d trading-service
sleep 5

# Start Reporting service
docker-compose up -d reporting-service
sleep 5

# Start Workflow service (coordinates everything)
docker-compose up -d workflow-service
sleep 5

# Start Orchestration (MCP interface)
docker-compose up -d orchestration-service
sleep 5

# 7. Verify all services are running
docker-compose ps

# 8. Check for any failed containers
docker ps -a --filter "status=exited"
```

---

## Phase 7: Health Verification Scripts

```bash
# 1. Create comprehensive health check script
cat > /root/catalyst-trading-mcp/scripts/health-check.sh << 'HEALTH_SCRIPT'
#!/bin/bash

# Health Check Script for Catalyst Trading System
# Version: 1.0.0

echo "======================================"
echo "Catalyst Trading System Health Check"
echo "Time: $(date)"
echo "======================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check service
check_service() {
    local name=$1
    local port=$2
    
    if curl -f -s --max-time 5 "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name (port $port) - HEALTHY"
        return 0
    else
        echo -e "${RED}✗${NC} $name (port $port) - UNHEALTHY"
        return 1
    fi
}

# Check Docker daemon
echo ""
echo "Checking Docker Status:"
if systemctl is-active --quiet docker; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
else
    echo -e "${RED}✗${NC} Docker daemon is not running"
    exit 1
fi

# Check all services
echo ""
echo "Checking Microservices:"
failed_count=0

check_service "Orchestration (MCP)" 5000 || ((failed_count++))
check_service "Scanner" 5001 || ((failed_count++))
check_service "Pattern Detection" 5002 || ((failed_count++))
check_service "Technical Analysis" 5003 || ((failed_count++))
check_service "Risk Manager" 5004 || ((failed_count++))
check_service "Trading" 5005 || ((failed_count++))
check_service "Workflow" 5006 || ((failed_count++))
check_service "News Intelligence" 5008 || ((failed_count++))
check_service "Reporting" 5009 || ((failed_count++))

# Check Redis
echo ""
echo "Checking Redis:"
if docker exec $(docker ps -q -f name=redis) redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis is responding"
else
    echo -e "${RED}✗${NC} Redis is not responding"
    ((failed_count++))
fi

# Check Database
echo ""
echo "Checking Database:"
source /root/catalyst-trading-mcp/.env
if psql "$DATABASE_URL" -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Database connection successful"
else
    echo -e "${RED}✗${NC} Database connection failed"
    ((failed_count++))
fi

# Summary
echo ""
echo "======================================"
if [ $failed_count -eq 0 ]; then
    echo -e "${GREEN}All systems operational!${NC}"
    exit 0
else
    echo -e "${RED}$failed_count service(s) failed health check${NC}"
    exit 1
fi
HEALTH_SCRIPT

# 2. Make health check executable
chmod +x /root/catalyst-trading-mcp/scripts/health-check.sh

# 3. Run initial health check
/root/catalyst-trading-mcp/scripts/health-check.sh

# 4. Create service restart script
cat > /root/catalyst-trading-mcp/scripts/restart-unhealthy.sh << 'RESTART_SCRIPT'
#!/bin/bash

# Restart unhealthy services
cd /root/catalyst-trading-mcp

# Function to check and restart service
check_and_restart() {
    local service=$1
    local port=$2
    
    if ! curl -f -s --max-time 5 "http://localhost:$port/health" > /dev/null 2>&1; then
        echo "Restarting $service..."
        docker-compose restart $service
        sleep 10
    fi
}

# Check each service
check_and_restart "orchestration-service" 5000
check_and_restart "scanner-service" 5001
check_and_restart "pattern-service" 5002
check_and_restart "technical-service" 5003
check_and_restart "risk-manager-service" 5004
check_and_restart "trading-service" 5005
check_and_restart "workflow-service" 5006
check_and_restart "news-service" 5008
check_and_restart "reporting-service" 5009
RESTART_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/restart-unhealthy.sh
```

---

## Phase 8: Workflow and Testing Scripts

```bash
# 1. Create workflow trigger script
cat > /root/catalyst-trading-mcp/scripts/trigger-workflow.sh << 'WORKFLOW_SCRIPT'
#!/bin/bash

# Trigger a trading workflow
echo "Triggering trading workflow at $(date)"

# Call workflow service to start a trading cycle
response=$(curl -s -X POST http://localhost:5006/workflow/start \
    -H "Content-Type: application/json" \
    -d '{"mode": "production", "max_trades": 5}')

if [ $? -eq 0 ]; then
    echo "Workflow triggered successfully"
    echo "Response: $response"
else
    echo "Failed to trigger workflow"
    exit 1
fi
WORKFLOW_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/trigger-workflow.sh

# 2. Create database backup script
cat > /root/catalyst-trading-mcp/scripts/backup-database.sh << 'BACKUP_SCRIPT'
#!/bin/bash

# Database backup script
source /root/catalyst-trading-mcp/.env

BACKUP_DIR="/backups/catalyst/database"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/catalyst_backup_$TIMESTAMP.sql"

echo "Starting database backup at $(date)"

# Perform backup
pg_dump "$DATABASE_URL" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    # Compress the backup
    gzip "$BACKUP_FILE"
    echo "Backup completed: ${BACKUP_FILE}.gz"
    
    # Remove backups older than 30 days
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
    echo "Old backups cleaned up"
else
    echo "Backup failed!"
    exit 1
fi
BACKUP_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/backup-database.sh

# 3. Create log viewer script
cat > /root/catalyst-trading-mcp/scripts/view-logs.sh << 'LOGS_SCRIPT'
#!/bin/bash

# Interactive log viewer
service=${1:-all}
lines=${2:-50}

if [ "$service" == "all" ]; then
    echo "Showing last $lines lines from all services:"
    docker-compose logs --tail=$lines
else
    echo "Showing last $lines lines from $service:"
    docker-compose logs --tail=$lines $service
fi
LOGS_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/view-logs.sh
```

---

## Phase 9: Cron Job Configuration

```bash
# 1. Create cron configuration script
cat > /root/catalyst-trading-mcp/scripts/setup-cron.sh << 'CRON_SCRIPT'
#!/bin/bash

# Setup cron jobs for Catalyst Trading System
echo "Setting up cron jobs..."

# Create cron job file
cat > /tmp/catalyst-cron << 'CRON_JOBS'
# Catalyst Trading System Cron Jobs
# All times in Perth timezone (AWST)

# === TRADING HOURS AUTOMATION ===
# US Pre-market (9:30 PM - 1:30 AM Perth)
30 21 * * 1-5 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 22 * * 1-5 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
30 22 * * 1-5 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 23 * * 1-5 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
30 23 * * 1-5 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1

# US Market hours (1:30 AM - 8:00 AM Perth)
30 1 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 2 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 3 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 4 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 5 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 6 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1
0 7 * * 2-6 /root/catalyst-trading-mcp/scripts/trigger-workflow.sh >> /var/log/catalyst/workflow.log 2>&1

# === MAINTENANCE TASKS ===
# Health check every 15 minutes
*/15 * * * * /root/catalyst-trading-mcp/scripts/health-check.sh >> /var/log/catalyst/health.log 2>&1

# Restart unhealthy services every hour
0 * * * * /root/catalyst-trading-mcp/scripts/restart-unhealthy.sh >> /var/log/catalyst/restart.log 2>&1

# Database backup daily at 2 AM Perth time
0 2 * * * /root/catalyst-trading-mcp/scripts/backup-database.sh >> /var/log/catalyst/backup.log 2>&1

# Clean up old logs weekly (Sunday 3 AM)
0 3 * * 0 find /var/log/catalyst -name "*.log" -mtime +30 -delete

# Generate daily report at 9 AM Perth (after US market close)
0 9 * * 2-6 curl -X POST http://localhost:5009/report/daily >> /var/log/catalyst/reports.log 2>&1

CRON_JOBS

# Install cron jobs
crontab /tmp/catalyst-cron
echo "Cron jobs installed successfully"

# Display installed cron jobs
echo ""
echo "Installed cron jobs:"
crontab -l
CRON_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/setup-cron.sh

# 2. Run cron setup
/root/catalyst-trading-mcp/scripts/setup-cron.sh

# 3. Verify cron is running
systemctl status cron
```

---

## Phase 10: Security Configuration

```bash
# 1. Configure UFW firewall
echo "Configuring firewall..."

# Reset UFW to defaults
ufw --force reset

# Set default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (critical - do not lock yourself out!)
ufw allow 22/tcp comment 'SSH'

# Allow MCP Orchestration service (if needed externally)
ufw allow 5000/tcp comment 'MCP Orchestration'

# Allow Workflow service (if needed externally)
# ufw allow 5006/tcp comment 'Workflow Service'

# Internal services (5001-5005, 5008-5009) should NOT be exposed
# They communicate internally via Docker network

# Enable UFW
ufw --force enable

# Show status
ufw status verbose

# 2. Setup fail2ban for SSH protection
apt-get install -y fail2ban

# Create jail.local configuration
cat > /etc/fail2ban/jail.local << 'F2B_CONFIG'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
F2B_CONFIG

# Restart fail2ban
systemctl restart fail2ban
systemctl enable fail2ban

# 3. Configure log rotation
cat > /etc/logrotate.d/catalyst << 'LOGROTATE_CONFIG'
/var/log/catalyst/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        # Signal any services that need to reopen log files
        docker-compose -f /root/catalyst-trading-mcp/docker-compose.yml kill -s USR1
    endscript
}
LOGROTATE_CONFIG

# Test logrotate configuration
logrotate -d /etc/logrotate.d/catalyst
```

---

## Phase 11: Git Configuration for Updates

```bash
# 1. Configure git for the repository
cd /root/catalyst-trading-mcp

# Set git configuration
git config user.name "Catalyst Deployment"
git config user.email "admin@catalyst-trading.local"
git config pull.rebase false

# 2. Create update script
cat > /root/catalyst-trading-mcp/scripts/update-system.sh << 'UPDATE_SCRIPT'
#!/bin/bash

# System update script with rollback capability
set -e

echo "================================"
echo "Catalyst System Update"
echo "Time: $(date)"
echo "================================"

cd /root/catalyst-trading-mcp

# Backup current state
echo "Creating backup before update..."
cp docker-compose.yml docker-compose.yml.backup
cp .env .env.backup

# Create git tag for rollback
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
git tag -a "pre-update-$TIMESTAMP" -m "Backup before update $TIMESTAMP"

# Pull latest changes
echo "Pulling latest changes from repository..."
git pull origin main

# Check if docker-compose.yml changed
if ! diff -q docker-compose.yml docker-compose.yml.backup > /dev/null; then
    echo "Docker compose configuration changed, rebuilding services..."
    docker-compose build --no-cache
fi

# Apply database migrations if any
if [ -f "migrations/pending.sql" ]; then
    echo "Applying database migrations..."
    source .env
    psql "$DATABASE_URL" -f migrations/pending.sql
    mv migrations/pending.sql migrations/applied_$TIMESTAMP.sql
fi

# Restart services with zero downtime
echo "Performing rolling restart..."
for service in $(docker-compose config --services); do
    echo "Restarting $service..."
    docker-compose up -d --no-deps --build $service
    sleep 5
done

# Health check
echo "Running health check..."
./scripts/health-check.sh

if [ $? -eq 0 ]; then
    echo "Update completed successfully!"
    rm -f docker-compose.yml.backup .env.backup
else
    echo "Health check failed! Rolling back..."
    mv docker-compose.yml.backup docker-compose.yml
    mv .env.backup .env
    git reset --hard "pre-update-$TIMESTAMP"
    docker-compose up -d
    echo "Rollback completed"
    exit 1
fi
UPDATE_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/update-system.sh

# 3. Create rollback script
cat > /root/catalyst-trading-mcp/scripts/rollback.sh << 'ROLLBACK_SCRIPT'
#!/bin/bash

# Emergency rollback script
echo "Emergency rollback initiated..."

cd /root/catalyst-trading-mcp

# List available backup tags
echo "Available rollback points:"
git tag -l "pre-update-*" | tail -10

echo ""
echo "Enter tag name to rollback to (or 'cancel'):"
read tag_name

if [ "$tag_name" == "cancel" ]; then
    echo "Rollback cancelled"
    exit 0
fi

# Perform rollback
git reset --hard "$tag_name"
docker-compose down
docker-compose up -d

echo "Rollback to $tag_name completed"
./scripts/health-check.sh
ROLLBACK_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/rollback.sh
```

---

## Phase 12: Monitoring and Alerting Setup

```bash
# 1. Create monitoring script
cat > /root/catalyst-trading-mcp/scripts/monitor-system.sh << 'MONITOR_SCRIPT'
#!/bin/bash

# System monitoring script
source /root/catalyst-trading-mcp/.env

# Function to send alert (customize as needed)
send_alert() {
    local level=$1
    local message=$2
    
    # Log the alert
    echo "[$(date)] [$level] $message" >> /var/log/catalyst/alerts.log
    
    # TODO: Add email/Slack/Discord notification here
    # Example for email (requires mail setup):
    # echo "$message" | mail -s "Catalyst Alert: $level" admin@example.com
}

# Check disk space
disk_usage=$(df /root | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $disk_usage -gt 80 ]; then
    send_alert "WARNING" "Disk usage is ${disk_usage}%"
fi

# Check memory usage
mem_usage=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
if [ $mem_usage -gt 80 ]; then
    send_alert "WARNING" "Memory usage is ${mem_usage}%"
fi

# Check Docker containers
stopped_containers=$(docker ps -a --filter "status=exited" --format "{{.Names}}" | wc -l)
if [ $stopped_containers -gt 0 ]; then
    send_alert "ERROR" "$stopped_containers containers have stopped"
fi

# Check service response times
for port in 5000 5001 5002 5003 5004 5005 5006 5008 5009; do
    response_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:$port/health)
    if (( $(echo "$response_time > 2" | bc -l) )); then
        send_alert "WARNING" "Service on port $port slow response: ${response_time}s"
    fi
done

# Check database connection
if ! psql "$DATABASE_URL" -c "SELECT 1" > /dev/null 2>&1; then
    send_alert "CRITICAL" "Database connection failed!"
fi

# Check Redis
if ! docker exec $(docker ps -q -f name=redis) redis-cli ping > /dev/null 2>&1; then
    send_alert "CRITICAL" "Redis is not responding!"
fi

echo "Monitoring check completed at $(date)"
MONITOR_SCRIPT

chmod +x /root/catalyst-trading-mcp/scripts/monitor-system.sh

# 2. Add monitoring to cron (every 5 minutes)
(crontab -l ; echo "*/5 * * * * /root/catalyst-trading-mcp/scripts/monitor-system.sh > /dev/null 2>&1") | crontab -
```

---

## Phase 13: Final System Verification

```bash
# 1. Complete system check
echo "Running complete system verification..."

# Check all services are running
docker-compose ps

# Run health check
/root/catalyst-trading-mcp/scripts/health-check.sh

# Check logs for errors
echo ""
echo "Checking for errors in logs..."
docker-compose logs --tail=100 | grep -i error || echo "No errors found in recent logs"

# Test workflow trigger
echo ""
echo "Testing workflow trigger..."
/root/catalyst-trading-mcp/scripts/trigger-workflow.sh

# Check resource usage
echo ""
echo "System resource usage:"
docker stats --no-stream

# Check disk space
echo ""
echo "Disk usage:"
df -h

# Network connectivity test
echo ""
echo "Testing external API connectivity:"
curl -s https://api.alpaca.markets/v2/clock | jq '.' || echo "Alpaca API test failed"

# Display service endpoints
echo ""
echo "Service Endpoints:"
echo "==================="
echo "MCP Orchestration:    http://localhost:5000"
echo "Scanner Service:      http://localhost:5001"
echo "Pattern Detection:    http://localhost:5002"
echo "Technical Analysis:   http://localhost:5003"
echo "Risk Manager:         http://localhost:5004"
echo "Trading Service:      http://localhost:5005"
echo "Workflow Service:     http://localhost:5006"
echo "News Intelligence:    http://localhost:5008"
echo "Reporting Service:    http://localhost:5009"
echo ""

# Display useful commands
echo "Useful Commands:"
echo "================"
echo "View logs:            ./scripts/view-logs.sh [service-name] [lines]"
echo "Health check:         ./scripts/health-check.sh"
echo "Trigger workflow:     ./scripts/trigger-workflow.sh"
echo "Update system:        ./scripts/update-system.sh"
echo "Monitor system:       ./scripts/monitor-system.sh"
echo "Backup database:      ./scripts/backup-database.sh"
echo ""

# Create quick reference card
cat > /root/CATALYST_QUICK_REFERENCE.txt << 'REFERENCE'
CATALYST TRADING SYSTEM - QUICK REFERENCE
=========================================

PROJECT LOCATION: /root/catalyst-trading-mcp

COMMON COMMANDS:
- Start all services:    cd ~/catalyst-trading-mcp && docker-compose up -d
- Stop all services:     cd ~/catalyst-trading-mcp && docker-compose down
- View logs:            docker-compose logs --tail=50 [service-name]
- Restart service:      docker-compose restart [service-name]
- Health check:         ./scripts/health-check.sh

SERVICE NAMES:
- orchestration-service (port 5000)
- scanner-service (port 5001)
- pattern-service (port 5002)
- technical-service (port 5003)
- risk-manager-service (port 5004)
- trading-service (port 5005)
- workflow-service (port 5006)
- news-service (port 5008)
- reporting-service (port 5009)

TROUBLESHOOTING:
- Check service status:  docker-compose ps
- View service logs:     docker-compose logs [service-name]
- Restart unhealthy:     ./scripts/restart-unhealthy.sh
- System update:         ./scripts/update-system.sh
- Emergency rollback:    ./scripts/rollback.sh

LOG LOCATIONS:
- Application logs:      /var/log/catalyst/
- Docker logs:          docker-compose logs

DATABASE:
- Connection:           Source from .env file
- Backup:              ./scripts/backup-database.sh
- Backups location:    /backups/catalyst/database/

CRON JOBS:
- View:                crontab -l
- Edit:                crontab -e
- Logs:                /var/log/catalyst/workflow.log

CLAUDE CODE:
- Status:              claude-code status
- Workspace:           /root/claude-workspace
REFERENCE

echo ""
echo "Quick reference saved to: /root/CATALYST_QUICK_REFERENCE.txt"
```

---

## Success Checklist

After completing all phases, verify:

- [ ] Claude Code installed and authenticated
- [ ] All 9 services showing "Up" status in `docker-compose ps`
- [ ] Health check script reports all services healthy
- [ ] Database connection verified
- [ ] Redis operational
- [ ] Environment variables configured
- [ ] Cron jobs installed and running
- [ ] Firewall configured with UFW
- [ ] Log rotation configured
- [ ] Backup scripts tested
- [ ] Workflow trigger tested successfully
- [ ] Git repository connected for updates
- [ ] Monitoring script running
- [ ] All scripts in `/root/catalyst-trading-mcp/scripts/` executable
- [ ] No critical errors in logs

---

## Post-Deployment Tasks

1. **Monitor Initial Operation**
   ```bash
   # Watch logs for first hour
   docker-compose logs -f
   ```

2. **Test Market Hours Operation**
   - Wait for next market open
   - Verify cron triggers workflow
   - Check for successful trades

3. **Setup External Monitoring** (Optional)
   - Configure email alerts
   - Setup Slack/Discord notifications
   - Consider Grafana/Prometheus

4. **Document Custom Changes**
   - Keep notes in `/root/catalyst-trading-mcp/NOTES.md`
   - Document any API key changes
   - Record any custom configurations

5. **Regular Maintenance**
   - Weekly: Review logs for errors
   - Monthly: Check disk space and clean old logs
   - Quarterly: Review and update dependencies

---

## Troubleshooting Guide

### Service Won't Start
```bash
# Check specific service logs
docker-compose logs [service-name] --tail=100

# Rebuild specific service
docker-compose build --no-cache [service-name]
docker-compose up -d [service-name]
```

### Database Connection Issues
```bash
# Test connection
source .env
psql "$DATABASE_URL" -c "SELECT 1"

# Check firewall rules on DigitalOcean
```

### High Memory Usage
```bash
# Check memory per container
docker stats

# Restart memory-heavy services
docker-compose restart [service-name]

# Clear Docker cache
docker system prune -a
```

### Cron Jobs Not Running
```bash
# Check cron service
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog

# Verify timezone
timedatectl
```

---

**Deployment Complete!** Your Catalyst Trading System should now be fully operational.
