# Doctor Claude Systemd Service

**Name of Application:** Catalyst Trading System  
**Name of file:** README.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-27  
**Purpose:** Installation guide for Doctor Claude as a systemd service

---

## Overview

This package installs Doctor Claude as a systemd service that:
- Starts automatically on boot
- Runs trade watchdog every 5 minutes during market hours
- Sleeps efficiently outside market hours
- Handles graceful shutdown
- Logs to systemd journal

---

## Quick Install

```bash
# 1. Upload package to droplet
scp -r doctor-claude-service root@your-droplet:/tmp/

# 2. SSH to droplet
ssh root@your-droplet

# 3. Navigate to package
cd /tmp/doctor-claude-service

# 4. Run installer
chmod +x install-doctor-claude-service.sh
sudo ./install-doctor-claude-service.sh

# 5. Check status
systemctl status doctor-claude
```

---

## Manual Installation

### Step 1: Copy Files

```bash
# Copy service script
cp doctor_claude_service.py /root/catalyst-trading-system/scripts/
chmod +x /root/catalyst-trading-system/scripts/doctor_claude_service.py

# Copy systemd service file
cp doctor-claude.service /etc/systemd/system/
```

### Step 2: Configure Environment

Ensure `/root/catalyst-trading-system/.env` contains:

```bash
# Required
DATABASE_URL="postgresql://user:pass@host:port/dbname?sslmode=require"
ALPACA_API_KEY="your-api-key"
ALPACA_SECRET_KEY="your-secret-key"
TRADING_MODE="paper"

# Optional
DOCTOR_CLAUDE_INTERVAL="300"      # Check interval in seconds (default: 300)
DOCTOR_CLAUDE_VERBOSE="false"     # Enable debug logging
```

### Step 3: Enable and Start

```bash
# Reload systemd
systemctl daemon-reload

# Enable auto-start on boot
systemctl enable doctor-claude

# Start the service
systemctl start doctor-claude

# Check status
systemctl status doctor-claude
```

---

## Management Commands

| Command | Description |
|---------|-------------|
| `systemctl start doctor-claude` | Start the service |
| `systemctl stop doctor-claude` | Stop the service |
| `systemctl restart doctor-claude` | Restart the service |
| `systemctl status doctor-claude` | Check service status |
| `systemctl enable doctor-claude` | Enable auto-start on boot |
| `systemctl disable doctor-claude` | Disable auto-start |

---

## Viewing Logs

```bash
# View live logs
journalctl -u doctor-claude -f

# View last 50 lines
journalctl -u doctor-claude -n 50

# View today's logs
journalctl -u doctor-claude --since today

# View logs with timestamps
journalctl -u doctor-claude -o short-precise

# View only errors
journalctl -u doctor-claude -p err
```

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `ALPACA_API_KEY` | (required) | Alpaca API key |
| `ALPACA_SECRET_KEY` | (required) | Alpaca secret key |
| `TRADING_MODE` | `paper` | Trading mode: `paper` or `live` |
| `DOCTOR_CLAUDE_INTERVAL` | `300` | Check interval in seconds |
| `DOCTOR_CLAUDE_VERBOSE` | `false` | Enable verbose debug logging |

### Service Parameters

Edit `/etc/systemd/system/doctor-claude.service` to modify:

```ini
# Memory limit
MemoryMax=512M

# CPU limit
CPUQuota=50%

# Restart delay
RestartSec=30
```

After editing, reload systemd:
```bash
systemctl daemon-reload
systemctl restart doctor-claude
```

---

## Market Hours

The service automatically detects US market hours:

- **Market Open:** 9:30 AM ET
- **Market Close:** 4:00 PM ET
- **Monitoring Window:** 9:15 AM - 4:15 PM ET (with 15-min buffer)
- **Weekends:** Service sleeps, wakes for Monday

Outside market hours, the service sleeps efficiently and wakes up when markets open.

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
journalctl -u doctor-claude -n 50

# Common issues:
# 1. Missing environment variables
cat /root/catalyst-trading-system/.env

# 2. Missing watchdog script
ls -la /root/catalyst-trading-system/scripts/trade_watchdog.py

# 3. Python not found
which python3
```

### Service Keeps Restarting

```bash
# Check restart count
systemctl show doctor-claude | grep RestartCount

# View failure reason
journalctl -u doctor-claude -p err --since "1 hour ago"
```

### Can't Connect to Database

```bash
# Test database connection
source /root/catalyst-trading-system/.env
psql "$DATABASE_URL" -c "SELECT 1;"
```

### Can't Connect to Alpaca

```bash
# Test Alpaca connection
source /root/catalyst-trading-system/.env
python3 -c "
from alpaca.trading.client import TradingClient
import os
client = TradingClient(os.environ['ALPACA_API_KEY'], os.environ['ALPACA_SECRET_KEY'], paper=True)
print(client.get_account())
"
```

---

## Uninstallation

```bash
# Stop and disable service
systemctl stop doctor-claude
systemctl disable doctor-claude

# Remove service file
rm /etc/systemd/system/doctor-claude.service
systemctl daemon-reload

# Optionally remove script
rm /root/catalyst-trading-system/scripts/doctor_claude_service.py
```

---

## Files

| File | Location | Purpose |
|------|----------|---------|
| `doctor-claude.service` | `/etc/systemd/system/` | Systemd service definition |
| `doctor_claude_service.py` | `/root/catalyst-trading-system/scripts/` | Service daemon script |
| `trade_watchdog.py` | `/root/catalyst-trading-system/scripts/` | Watchdog diagnostic (existing) |
| `.env` | `/root/catalyst-trading-system/` | Environment configuration |

---

## Log Output Examples

### Healthy System
```
INFO: === Check #42 at 10:30:00 ===
INFO: ✅ HEALTHY | Orders: 83 | Positions: 2 open | Issues: 0
```

### Warning
```
INFO: === Check #43 at 10:35:00 ===
WARNING: ⚠️  WARNING | Issues: 1 | Types: ['ORDER_STATUS_MISMATCH']
WARNING:    - ORDER_STATUS_MISMATCH: Order AAPL status: DB=submitted, Alpaca=filled
```

### Outside Market Hours
```
INFO: Outside market hours. Next check in 60 minutes. Market opens at 09:30:00 ET
```

---

*Doctor Claude Service v1.0.0*  
*Catalyst Trading System*  
*December 27, 2025*
