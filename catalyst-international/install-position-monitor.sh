#!/bin/bash
# ============================================================================
# Name of Application: Catalyst Trading System
# Name of file: install-position-monitor.sh
# Version: 1.0.0
# Last Updated: 2026-01-16
# Purpose: Install HKEX Position Monitor Service
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================="
echo "Installing HKEX Position Monitor Service"
echo -e "==========================================${NC}"
echo ""

# Variables
INTL_DIR="/root/Catalyst-Trading-System-International/catalyst-international"
SERVICE_NAME="position-monitor"
SERVICE_FILE="${SERVICE_NAME}.service"
PYTHON_FILE="position_monitor_service.py"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root${NC}"
    exit 1
fi

# Check if international directory exists
if [ ! -d "$INTL_DIR" ]; then
    echo -e "${RED}Error: Directory not found: $INTL_DIR${NC}"
    exit 1
fi

# Step 1: Copy Python service file
echo -e "${YELLOW}Step 1: Copying service script...${NC}"
if [ -f "$PYTHON_FILE" ]; then
    cp "$PYTHON_FILE" "$INTL_DIR/"
    chmod +x "$INTL_DIR/$PYTHON_FILE"
    echo -e "${GREEN}✓ Copied $PYTHON_FILE to $INTL_DIR/${NC}"
else
    echo -e "${RED}Error: $PYTHON_FILE not found in current directory${NC}"
    exit 1
fi

# Step 2: Install systemd service
echo -e "${YELLOW}Step 2: Installing systemd service...${NC}"
if [ -f "$SERVICE_FILE" ]; then
    cp "$SERVICE_FILE" /etc/systemd/system/
    chmod 644 /etc/systemd/system/$SERVICE_FILE
    echo -e "${GREEN}✓ Installed $SERVICE_FILE${NC}"
else
    echo -e "${RED}Error: $SERVICE_FILE not found in current directory${NC}"
    exit 1
fi

# Step 3: Create logs directory
echo -e "${YELLOW}Step 3: Creating logs directory...${NC}"
mkdir -p "$INTL_DIR/logs"
echo -e "${GREEN}✓ Logs directory ready${NC}"

# Step 4: Check environment file
echo -e "${YELLOW}Step 4: Checking environment...${NC}"
if [ -f "$INTL_DIR/.env" ]; then
    if grep -q "DATABASE_URL\|INTL_DATABASE_URL" "$INTL_DIR/.env"; then
        echo -e "${GREEN}✓ Environment file found with database URL${NC}"
    else
        echo -e "${YELLOW}⚠ Warning: DATABASE_URL not found in .env${NC}"
    fi
else
    echo -e "${RED}Error: .env file not found at $INTL_DIR/.env${NC}"
    echo "Create .env with at minimum:"
    echo "  DATABASE_URL=postgresql://..."
    echo "  ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
fi

# Step 5: Reload systemd
echo -e "${YELLOW}Step 5: Reloading systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"

# Step 6: Enable service
echo -e "${YELLOW}Step 6: Enabling service for auto-start...${NC}"
systemctl enable $SERVICE_NAME
echo -e "${GREEN}✓ Service enabled${NC}"

# Step 7: Start service
echo -e "${YELLOW}Step 7: Starting service...${NC}"
systemctl start $SERVICE_NAME
sleep 2

# Step 8: Verify
echo -e "${YELLOW}Step 8: Verifying installation...${NC}"
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Service is running${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo "Check logs: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Installation Complete!"
echo -e "==========================================${NC}"
echo ""
echo "Service Status:"
systemctl status $SERVICE_NAME --no-pager | head -10
echo ""
echo "Commands:"
echo "  View logs:      journalctl -u $SERVICE_NAME -f"
echo "  Stop service:   systemctl stop $SERVICE_NAME"
echo "  Restart:        systemctl restart $SERVICE_NAME"
echo "  Status:         systemctl status $SERVICE_NAME"
echo ""
echo "The service will:"
echo "  • Check ALL open positions every 5 minutes"
echo "  • Execute exits when signals indicate"
echo "  • Sleep during market closed hours"
echo "  • Auto-restart on failure"
echo ""
