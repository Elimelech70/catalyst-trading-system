#!/bin/bash
# ============================================================================
# CATALYST TRADING SYSTEM - COMPLETE INSTALLATION
# Name of Application: Catalyst Trading System
# Name of file: install_catalyst.sh
# Version: 1.0.0
# Last Updated: 2025-12-28
# Purpose: One-command installation for consolidated droplet architecture
#
# USAGE:
#   chmod +x install_catalyst.sh
#   ./install_catalyst.sh
#
# PREREQUISITES:
#   - Fresh DigitalOcean droplet (4GB/2vCPU recommended)
#   - Ubuntu 22.04 or 24.04
#   - Root access
# ============================================================================

set -e  # Exit on error

echo "========================================"
echo "Catalyst Trading System - Installation"
echo "Version: 1.0.0"
echo "========================================"
echo ""

# ----------------------------------------------------------------------------
# 1. System Updates
# ----------------------------------------------------------------------------
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y
echo "✅ System updated"

# ----------------------------------------------------------------------------
# 2. Install Dependencies
# ----------------------------------------------------------------------------
echo ""
echo "[2/8] Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    tree \
    postgresql-client \
    curl \
    jq

echo "✅ System dependencies installed"

# ----------------------------------------------------------------------------
# 3. Install Python Packages
# ----------------------------------------------------------------------------
echo ""
echo "[3/8] Installing Python packages..."
pip3 install --break-system-packages \
    asyncpg \
    anthropic \
    python-dotenv \
    httpx \
    alpaca-py \
    futu-api \
    pandas \
    numpy \
    aiohttp

echo "✅ Python packages installed"

# ----------------------------------------------------------------------------
# 4. Create Directory Structure
# ----------------------------------------------------------------------------
echo ""
echo "[4/8] Creating directory structure..."

mkdir -p /root/catalyst/{public,intl,shared,config}
mkdir -p /root/catalyst/logs/{public,intl,doctor}
mkdir -p /root/catalyst/backups

touch /root/catalyst/public/__init__.py
touch /root/catalyst/intl/__init__.py
touch /root/catalyst/shared/__init__.py

echo "✅ Directory structure created"

# ----------------------------------------------------------------------------
# 5. Create Configuration Templates
# ----------------------------------------------------------------------------
echo ""
echo "[5/8] Creating configuration templates..."

# Shared configuration
cat > /root/catalyst/config/shared.env << 'SHARED_ENV'
# ============================================================================
# CATALYST TRADING SYSTEM - SHARED CONFIGURATION
# ============================================================================
# Update these values with your actual credentials

# Database Connection
DB_HOST=your-db-host.db.ondigitalocean.com
DB_PORT=25060
DB_USER=doadmin
DB_PASSWORD=YOUR_DB_PASSWORD_HERE
DB_SSLMODE=require

# Research Database (Consciousness - shared by all agents)
RESEARCH_DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_research?sslmode=${DB_SSLMODE}

# Email Alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-alerts-email@gmail.com
SMTP_PASSWORD=your-app-password-here
ALERT_EMAIL=your-personal-email@example.com

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Logging
LOG_LEVEL=INFO
SHARED_ENV

# Public agent configuration
cat > /root/catalyst/config/public.env << 'PUBLIC_ENV'
# ============================================================================
# CATALYST PUBLIC AGENT - US MARKETS (Alpaca)
# ============================================================================

# Agent Identity
AGENT_ID=public_claude
AGENT_NAME=Public Claude
MARKET=US

# Trading Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_public?sslmode=${DB_SSLMODE}

# Alpaca API (Paper Trading - switch to live when ready)
ALPACA_API_KEY=your-alpaca-api-key
ALPACA_SECRET_KEY=your-alpaca-secret-key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Trading Parameters (USD)
MAX_POSITION_SIZE=5000
MAX_POSITIONS=5
MAX_DAILY_LOSS=2000
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=6.0

# Market Hours (EST)
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
TIMEZONE=US/Eastern

# Claude Model
CLAUDE_MODEL=claude-sonnet-4-20250514
DAILY_API_BUDGET=5.00
PUBLIC_ENV

# International agent configuration
cat > /root/catalyst/config/intl.env << 'INTL_ENV'
# ============================================================================
# CATALYST INTERNATIONAL AGENT - HKEX (Moomoo/Futu)
# ============================================================================

# Agent Identity
AGENT_ID=intl_claude
AGENT_NAME=International Claude
MARKET=HKEX

# Trading Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_intl?sslmode=${DB_SSLMODE}

# Moomoo/Futu API
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADE_ENV=SIMULATE
MOOMOO_SECURITY_FIRM=FUTUINC
MOOMOO_RSA_PATH=/root/catalyst/config/moomoo_rsa.key

# Trading Parameters (HKD)
MAX_POSITION_SIZE=40000
MAX_POSITIONS=5
MAX_DAILY_LOSS=16000
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=6.0
LOT_SIZE=100

# Market Hours (HKT)
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
TIMEZONE=Asia/Hong_Kong

# Claude Model
CLAUDE_MODEL=claude-sonnet-4-20250514
DAILY_API_BUDGET=5.00
INTL_ENV

chmod 600 /root/catalyst/config/*.env
echo "✅ Configuration templates created"

# ----------------------------------------------------------------------------
# 6. Create Runner Scripts
# ----------------------------------------------------------------------------
echo ""
echo "[6/8] Creating runner scripts..."

# Public agent runner
cat > /root/catalyst/public/run.sh << 'PUBLIC_RUN'
#!/bin/bash
# Catalyst Public Agent - Runner Script

# Load environment
set -a
source /root/catalyst/config/shared.env
source /root/catalyst/config/public.env
set +a

# Set working directory
cd /root/catalyst/public

# Get mode (default: scan)
MODE=${1:-scan}

# Log file
LOG_DIR=/root/catalyst/logs/public
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/$(date +%Y%m%d).log"

# Run agent
echo "$(date '+%Y-%m-%d %H:%M:%S') [public_claude] Starting $MODE cycle" >> $LOG_FILE
python3 agent.py $MODE >> $LOG_FILE 2>&1
EXIT_CODE=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') [public_claude] $MODE cycle complete (exit: $EXIT_CODE)" >> $LOG_FILE
PUBLIC_RUN

# International agent runner
cat > /root/catalyst/intl/run.sh << 'INTL_RUN'
#!/bin/bash
# Catalyst International Agent - Runner Script

# Load environment
set -a
source /root/catalyst/config/shared.env
source /root/catalyst/config/intl.env
set +a

# Set working directory
cd /root/catalyst/intl

# Get mode (default: scan)
MODE=${1:-scan}

# Log file
LOG_DIR=/root/catalyst/logs/intl
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/$(date +%Y%m%d).log"

# Run agent
echo "$(date '+%Y-%m-%d %H:%M:%S') [intl_claude] Starting $MODE cycle" >> $LOG_FILE
python3 agent.py $MODE >> $LOG_FILE 2>&1
EXIT_CODE=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') [intl_claude] $MODE cycle complete (exit: $EXIT_CODE)" >> $LOG_FILE
INTL_RUN

# Doctor Claude runner
cat > /root/catalyst/shared/run_doctor.sh << 'DOCTOR_RUN'
#!/bin/bash
# Doctor Claude - Health Monitor Runner

# Load environment
set -a
source /root/catalyst/config/shared.env
set +a

# Log file
LOG_DIR=/root/catalyst/logs/doctor
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/$(date +%Y%m%d).log"

# Run health check
cd /root/catalyst/shared
echo "$(date '+%Y-%m-%d %H:%M:%S') [doctor_claude] Health check starting" >> $LOG_FILE
python3 doctor_claude.py >> $LOG_FILE 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') [doctor_claude] Health check complete" >> $LOG_FILE
DOCTOR_RUN

chmod +x /root/catalyst/public/run.sh
chmod +x /root/catalyst/intl/run.sh
chmod +x /root/catalyst/shared/run_doctor.sh

echo "✅ Runner scripts created"

# ----------------------------------------------------------------------------
# 7. Create Cron Setup Script
# ----------------------------------------------------------------------------
echo ""
echo "[7/8] Creating cron setup script..."

cat > /root/catalyst/setup_cron.sh << 'CRON_SETUP'
#!/bin/bash
# Setup cron jobs for Catalyst Trading System

echo "Setting up cron jobs..."

# Backup existing crontab
crontab -l > /root/catalyst/backups/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true

# Create new crontab
cat > /tmp/catalyst_cron << 'CRON'
# ============================================================================
# CATALYST TRADING SYSTEM - CRON SCHEDULE
# Server timezone: UTC
# ============================================================================

SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# ============================================================================
# PUBLIC AGENT (US Markets)
# Market hours: 9:30-16:00 EST = 14:30-21:00 UTC
# ============================================================================

# Pre-market scan (9:00 EST = 14:00 UTC)
0 14 * * 1-5 /root/catalyst/public/run.sh scan

# Trading cycles every 30 min (9:30-15:30 EST = 14:30-20:30 UTC)
30 14 * * 1-5 /root/catalyst/public/run.sh trade
0 15-20 * * 1-5 /root/catalyst/public/run.sh trade
30 15-20 * * 1-5 /root/catalyst/public/run.sh trade

# End of day (16:00 EST = 21:00 UTC)
0 21 * * 1-5 /root/catalyst/public/run.sh close

# ============================================================================
# INTERNATIONAL AGENT (HKEX)
# Market hours: 9:30-16:00 HKT = 01:30-08:00 UTC
# ============================================================================

# Pre-market scan (9:00 HKT = 01:00 UTC)
0 1 * * 1-5 /root/catalyst/intl/run.sh scan

# Trading cycles every 30 min (9:30-15:30 HKT = 01:30-07:30 UTC)
30 1 * * 1-5 /root/catalyst/intl/run.sh trade
0 2-7 * * 1-5 /root/catalyst/intl/run.sh trade
30 2-7 * * 1-5 /root/catalyst/intl/run.sh trade

# End of day (16:00 HKT = 08:00 UTC)
0 8 * * 1-5 /root/catalyst/intl/run.sh close

# ============================================================================
# DOCTOR CLAUDE (Health Monitoring)
# ============================================================================

# Health check every 5 minutes
*/5 * * * * /root/catalyst/shared/run_doctor.sh

# ============================================================================
# MAINTENANCE
# ============================================================================

# Log rotation (daily at 00:00 UTC)
0 0 * * * find /root/catalyst/logs -name "*.log" -mtime +7 -delete

CRON

# Install crontab
crontab /tmp/catalyst_cron
rm /tmp/catalyst_cron

echo "✅ Cron jobs installed"
echo ""
echo "Current cron schedule:"
crontab -l
CRON_SETUP

chmod +x /root/catalyst/setup_cron.sh
echo "✅ Cron setup script created"

# ----------------------------------------------------------------------------
# 8. Create Verification Script
# ----------------------------------------------------------------------------
echo ""
echo "[8/8] Creating verification script..."

cat > /root/catalyst/verify.sh << 'VERIFY'
#!/bin/bash
# Catalyst Trading System - Verification Script

echo "========================================"
echo "Catalyst Trading System - Verification"
echo "========================================"
echo ""

echo "📁 Directory Structure:"
echo "------------------------"
tree /root/catalyst -L 2 2>/dev/null || find /root/catalyst -maxdepth 2 -type d
echo ""

echo "🐍 Python Version:"
echo "------------------"
python3 --version
echo ""

echo "📦 Required Packages:"
echo "---------------------"
pip3 list 2>/dev/null | grep -E "asyncpg|anthropic|alpaca|futu|dotenv" || echo "Package check requires pip3"
echo ""

echo "📄 Configuration Files:"
echo "-----------------------"
ls -la /root/catalyst/config/
echo ""

echo "🔧 Runner Scripts:"
echo "------------------"
ls -la /root/catalyst/public/*.sh 2>/dev/null || echo "Public scripts not found"
ls -la /root/catalyst/intl/*.sh 2>/dev/null || echo "Intl scripts not found"
ls -la /root/catalyst/shared/*.sh 2>/dev/null || echo "Shared scripts not found"
echo ""

echo "⏰ Cron Jobs:"
echo "-------------"
crontab -l 2>/dev/null || echo "No cron jobs installed yet (run setup_cron.sh)"
echo ""

echo "🔌 Database Connection Test:"
echo "----------------------------"
if [ -f /root/catalyst/config/shared.env ]; then
    source /root/catalyst/config/shared.env
    if [ -n "$RESEARCH_DATABASE_URL" ]; then
        psql "$RESEARCH_DATABASE_URL" -c "SELECT agent_id, current_mode FROM claude_state;" 2>/dev/null || echo "Database connection failed - check credentials"
    else
        echo "RESEARCH_DATABASE_URL not set"
    fi
else
    echo "shared.env not found"
fi
echo ""

echo "========================================"
echo "Verification complete"
echo "========================================"
VERIFY

chmod +x /root/catalyst/verify.sh

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
echo ""
echo "========================================"
echo "✅ INSTALLATION COMPLETE"
echo "========================================"
echo ""
echo "Directory: /root/catalyst/"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Update configuration files with your credentials:"
echo "   nano /root/catalyst/config/shared.env"
echo "   nano /root/catalyst/config/public.env"
echo "   nano /root/catalyst/config/intl.env"
echo ""
echo "2. Deploy the shared Python modules:"
echo "   - /root/catalyst/shared/database.py"
echo "   - /root/catalyst/shared/consciousness.py"
echo "   - /root/catalyst/shared/alerts.py"
echo "   - /root/catalyst/shared/doctor_claude.py"
echo ""
echo "3. Deploy the agent code:"
echo "   - /root/catalyst/public/agent.py"
echo "   - /root/catalyst/intl/agent.py"
echo ""
echo "4. Setup cron jobs:"
echo "   /root/catalyst/setup_cron.sh"
echo ""
echo "5. Verify installation:"
echo "   /root/catalyst/verify.sh"
echo ""
echo "========================================"
