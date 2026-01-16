#!/bin/bash
# ============================================================================
# Name of Application: Catalyst Trading System
# Name of file: install-doctor-claude-service.sh
# Version: 1.0.0
# Last Updated: 2025-12-27
# Purpose: Install Doctor Claude as a systemd service
#
# USAGE:
#   chmod +x install-doctor-claude-service.sh
#   sudo ./install-doctor-claude-service.sh
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  Doctor Claude Service Installer"
echo "=============================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root (sudo)${NC}"
    exit 1
fi

# Configuration
INSTALL_DIR="/root/catalyst-trading-system"
SCRIPTS_DIR="$INSTALL_DIR/scripts"
LOG_DIR="/var/log/catalyst"
SERVICE_FILE="/etc/systemd/system/doctor-claude.service"
ENV_FILE="$INSTALL_DIR/.env"

# Check if catalyst directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Error: Catalyst directory not found: $INSTALL_DIR${NC}"
    echo "Please ensure the trading system is installed first."
    exit 1
fi

# Step 1: Create log directory
echo -n "Creating log directory... "
mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR"
echo -e "${GREEN}OK${NC}"

# Step 2: Copy service script
echo -n "Installing service script... "
cp doctor_claude_service.py "$SCRIPTS_DIR/"
chmod +x "$SCRIPTS_DIR/doctor_claude_service.py"
echo -e "${GREEN}OK${NC}"

# Step 3: Verify trade_watchdog.py exists
echo -n "Verifying watchdog script... "
if [ -f "$SCRIPTS_DIR/trade_watchdog.py" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING: trade_watchdog.py not found${NC}"
    echo "  Please ensure trade_watchdog.py is in $SCRIPTS_DIR"
fi

# Step 4: Check/create environment file
echo -n "Checking environment file... "
if [ -f "$ENV_FILE" ]; then
    echo -e "${GREEN}OK${NC}"
    
    # Verify required variables
    source "$ENV_FILE"
    MISSING=""
    
    if [ -z "$DATABASE_URL" ]; then
        MISSING="$MISSING DATABASE_URL"
    fi
    if [ -z "$ALPACA_API_KEY" ]; then
        MISSING="$MISSING ALPACA_API_KEY"
    fi
    if [ -z "$ALPACA_SECRET_KEY" ]; then
        MISSING="$MISSING ALPACA_SECRET_KEY"
    fi
    
    if [ -n "$MISSING" ]; then
        echo -e "${YELLOW}WARNING: Missing environment variables:${NC}$MISSING"
        echo "  Please update $ENV_FILE"
    fi
else
    echo -e "${YELLOW}WARNING: .env file not found${NC}"
    echo "Creating template .env file..."
    cat > "$ENV_FILE" << 'EOF'
# Catalyst Trading System Environment Variables
# Doctor Claude Service Configuration

# Database (required)
DATABASE_URL="postgresql://user:password@host:port/dbname?sslmode=require"

# Alpaca API (required)
ALPACA_API_KEY="your-api-key"
ALPACA_SECRET_KEY="your-secret-key"
TRADING_MODE="paper"

# Doctor Claude Settings (optional)
DOCTOR_CLAUDE_INTERVAL="300"
DOCTOR_CLAUDE_VERBOSE="false"
EOF
    chmod 600 "$ENV_FILE"
    echo -e "${YELLOW}Please edit $ENV_FILE with your credentials${NC}"
fi

# Step 5: Install systemd service
echo -n "Installing systemd service... "
cp doctor-claude.service "$SERVICE_FILE"
echo -e "${GREEN}OK${NC}"

# Step 6: Reload systemd
echo -n "Reloading systemd... "
systemctl daemon-reload
echo -e "${GREEN}OK${NC}"

# Step 7: Enable service (optional)
echo ""
read -p "Enable Doctor Claude to start on boot? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl enable doctor-claude
    echo -e "${GREEN}Service enabled for auto-start${NC}"
fi

# Step 8: Start service (optional)
echo ""
read -p "Start Doctor Claude service now? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl start doctor-claude
    sleep 2
    
    if systemctl is-active --quiet doctor-claude; then
        echo -e "${GREEN}Service started successfully!${NC}"
    else
        echo -e "${RED}Service failed to start. Check logs:${NC}"
        echo "  journalctl -u doctor-claude -n 20"
    fi
fi

# Summary
echo ""
echo "=============================================="
echo "  Installation Complete"
echo "=============================================="
echo ""
echo "Files installed:"
echo "  - $SCRIPTS_DIR/doctor_claude_service.py"
echo "  - $SERVICE_FILE"
echo "  - $LOG_DIR (log directory)"
echo ""
echo "Management commands:"
echo "  systemctl start doctor-claude    # Start service"
echo "  systemctl stop doctor-claude     # Stop service"
echo "  systemctl restart doctor-claude  # Restart service"
echo "  systemctl status doctor-claude   # Check status"
echo "  journalctl -u doctor-claude -f   # View live logs"
echo ""
echo "Configuration:"
echo "  Edit $ENV_FILE to change settings"
echo "  Set DOCTOR_CLAUDE_INTERVAL for check frequency (seconds)"
echo "  Set DOCTOR_CLAUDE_VERBOSE=true for debug logging"
echo ""
