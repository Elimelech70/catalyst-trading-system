# OpenD Migration: Docker → Native

**Purpose:** Migrate OpenD from Docker container to native installation on droplet
**Target Server:** 209.38.87.27
**Created:** December 21, 2025

---

## Overview

**Current State:** Docker container at `/root/opend/` with 2FA/Device.dat persistence issues
**Target State:** Native OpenD at `/opt/opend/` with systemd service management

**Benefits of Native Installation:**
- Device.dat persists naturally (no volume mount issues)
- One-time 2FA authentication only
- Simpler debugging (direct process access)
- Lower memory footprint (no container overhead)
- Systemd service management (auto-restart, boot startup)

---

## Pre-Migration Checklist

- [ ] SSH access to droplet confirmed
- [ ] Current Docker container stopped
- [ ] Backup any existing Device.dat if present
- [ ] Moomoo credentials ready (craigjcolley@gmail.com / Thisissecure1234!)

---

## Phase 1: Stop Docker & Prepare

```bash
# Stop existing Docker container
cd /root/opend 2>/dev/null && docker compose down 2>/dev/null || echo "No Docker container running"

# Check for existing Device.dat (save if exists)
if [ -f /root/opend/opend-data/F3CNN/Device.dat ]; then
    mkdir -p /tmp/opend-backup
    cp /root/opend/opend-data/F3CNN/Device.dat /tmp/opend-backup/
    echo "✅ Backed up existing Device.dat"
fi

# Create directories
mkdir -p /opt/opend
mkdir -p /var/log/opend

echo "✅ Phase 1 complete"
```

---

## Phase 2: Download & Install OpenD

```bash
# Download OpenD
cd /tmp
wget -q https://softwaredownload.moomoo.com/softwares/OpenD/moomoo_OpenD_9.6.5618_Ubuntu18.04.tar.gz

# Extract
tar -xzf moomoo_OpenD_9.6.5618_Ubuntu18.04.tar.gz

# Move to installation directory
cp -r moomoo_OpenD_9.6.5618_Ubuntu18.04/* /opt/opend/

# Cleanup
rm -rf moomoo_OpenD_9.6.5618_Ubuntu18.04 moomoo_OpenD_9.6.5618_Ubuntu18.04.tar.gz

# Set permissions
chmod +x /opt/opend/OpenD
chmod +x /opt/opend/WebSocket 2>/dev/null || true
chmod +x /opt/opend/Update 2>/dev/null || true

# Verify installation
echo "Installed files:"
ls -la /opt/opend/

echo "✅ Phase 2 complete"
```

---

## Phase 3: Create Configuration

```bash
# Create OpenD.xml configuration
cat > /opt/opend/OpenD.xml << 'XMLEOF'
<?xml version="1.0" encoding="UTF-8"?>
<root>
    <!-- ========== AUTHENTICATION ========== -->
    <login_account>craigjcolley@gmail.com</login_account>
    <login_pwd>Thisissecure1234!</login_pwd>
    
    <!-- ========== NETWORK BINDING ========== -->
    <!-- localhost only for security - Python connects locally -->
    <ip>127.0.0.1</ip>
    <api_port>11111</api_port>
    
    <!-- ========== WEBSOCKET ========== -->
    <websocket_ip>127.0.0.1</websocket_ip>
    <websocket_port>33333</websocket_port>
    
    <!-- ========== TELNET (Required for 2FA) ========== -->
    <telnet_ip>127.0.0.1</telnet_ip>
    <telnet_port>22222</telnet_port>
    
    <!-- ========== PROTOCOL ========== -->
    <!-- 1 = JSON format for easier Python integration -->
    <push_proto_type>1</push_proto_type>
    <!-- 100ms quote push frequency -->
    <qot_push_frequency>100</qot_push_frequency>
    
    <!-- ========== MARKET PERMISSIONS ========== -->
    <auto_hold_quote_right>1</auto_hold_quote_right>
    <price_reminder_push>1</price_reminder_push>
    
    <!-- ========== LOGGING ========== -->
    <log_level>info</log_level>
    
    <!-- ========== REGIONAL ========== -->
    <lang>en</lang>
    <future_trade_api_time_zone>UTC+8</future_trade_api_time_zone>
</root>
XMLEOF

# Secure the config file (contains password)
chmod 600 /opt/opend/OpenD.xml

echo "✅ Configuration created"
cat /opt/opend/OpenD.xml
```

---

## Phase 4: Create Systemd Service

```bash
# Create systemd service file
cat > /etc/systemd/system/opend.service << 'SERVICEEOF'
[Unit]
Description=Moomoo OpenD Trading Gateway
Documentation=https://openapi.moomoo.com/moomoo-api-doc/en/opend/opend-intro.html
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/opend
ExecStart=/opt/opend/OpenD
Restart=on-failure
RestartSec=10
TimeoutStartSec=60
TimeoutStopSec=30

# Environment
Environment=HOME=/root
Environment=LANG=en_US.UTF-8

# Logging
StandardOutput=append:/var/log/opend/opend.log
StandardError=append:/var/log/opend/opend.log

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/opend /var/log/opend /root/.com.moomoo.OpenD
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Reload systemd to recognize new service
systemctl daemon-reload

echo "✅ Systemd service created"
systemctl cat opend.service
```

---

## Phase 5: Create Helper Scripts

### 5.1 Telnet Verification Script

```bash
cat > /opt/opend/telnet_verify.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""
OpenD Telnet Verification Script
Handles 2FA/Device Lock verification via Telnet commands

Usage:
    python3 telnet_verify.py status              - Check OpenD status
    python3 telnet_verify.py request_sms         - Request SMS verification code
    python3 telnet_verify.py submit_sms CODE     - Submit SMS verification code
    python3 telnet_verify.py request_captcha     - Request CAPTCHA image
    python3 telnet_verify.py submit_captcha CODE - Submit CAPTCHA code
    python3 telnet_verify.py relogin [PASSWORD]  - Re-login to OpenD
"""

from telnetlib import Telnet
import sys
import time

TELNET_HOST = '127.0.0.1'
TELNET_PORT = 22222

def send_command(command: str) -> str:
    """Send command to OpenD via Telnet and return response."""
    try:
        with Telnet(TELNET_HOST, TELNET_PORT, timeout=10) as tn:
            tn.write(f'{command}\r\n'.encode())
            time.sleep(0.5)
            reply = b''
            while True:
                msg = tn.read_until(b'\r\n', timeout=0.5)
                reply += msg
                if msg == b'':
                    break
            decoded = reply.decode('gb2312', errors='ignore')
            return decoded if decoded.strip() else "Command sent (no response)"
    except ConnectionRefusedError:
        return "ERROR: Connection refused - OpenD not running or Telnet not enabled"
    except Exception as e:
        return f"ERROR: {e}"

def request_phone_verification():
    """Request SMS verification code (max 1 per 60 seconds)."""
    print("📱 Requesting phone verification code...")
    print("   (Rate limit: 1 request per 60 seconds)")
    response = send_command('req_phone_verify_code')
    print(f"Response: {response}")
    return response

def submit_phone_verification(code: str):
    """Submit SMS verification code (max 10 per 60 seconds)."""
    print(f"📱 Submitting phone verification code: {code}")
    response = send_command(f'input_phone_verify_code -code={code}')
    print(f"Response: {response}")
    return response

def request_captcha():
    """Request graphic verification code (max 10 per 60 seconds)."""
    print("🖼️  Requesting graphic verification code...")
    response = send_command('req_pic_verify_code')
    print(f"Response: {response}")
    print("\nNote: Check /var/log/opend/opend.log for CAPTCHA image path")
    return response

def submit_captcha(code: str):
    """Submit graphic verification code (max 10 per 60 seconds)."""
    print(f"🖼️  Submitting graphic verification code: {code}")
    response = send_command(f'input_pic_verify_code -code={code}')
    print(f"Response: {response}")
    return response

def relogin(password: str = None):
    """Re-login to OpenD (max 10 per hour)."""
    if password:
        cmd = f'relogin -login_pwd={password}'
        print("🔄 Attempting re-login with password...")
    else:
        cmd = 'relogin'
        print("🔄 Attempting re-login...")
    response = send_command(cmd)
    print(f"Response: {response}")
    return response

def check_status():
    """Check OpenD status via ping."""
    print("🔍 Checking OpenD status...")
    response = send_command('ping')
    print(f"Response: {response}")
    return response

def show_help():
    """Show help information."""
    print(__doc__)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action in ['status', 'ping']:
        check_status()
    elif action == 'request_sms':
        request_phone_verification()
    elif action == 'submit_sms':
        if len(sys.argv) < 3:
            print("ERROR: Missing SMS code. Usage: submit_sms CODE")
            sys.exit(1)
        submit_phone_verification(sys.argv[2])
    elif action == 'request_captcha':
        request_captcha()
    elif action == 'submit_captcha':
        if len(sys.argv) < 3:
            print("ERROR: Missing CAPTCHA code. Usage: submit_captcha CODE")
            sys.exit(1)
        submit_captcha(sys.argv[2])
    elif action == 'relogin':
        password = sys.argv[2] if len(sys.argv) >= 3 else None
        relogin(password)
    elif action in ['help', '-h', '--help']:
        show_help()
    else:
        print(f"ERROR: Unknown action '{action}'")
        show_help()
        sys.exit(1)
PYTHONEOF

chmod +x /opt/opend/telnet_verify.py
echo "✅ telnet_verify.py created"
```

### 5.2 Connection Test Script

```bash
cat > /opt/opend/test_connection.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""
OpenD Connection Test Script
Tests connectivity to OpenD API, WebSocket, and Telnet ports
"""

import socket
import sys

def test_port(host: str, port: int, name: str) -> bool:
    """Test if a port is open and accepting connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"✅ {name:12} (port {port}): OPEN")
            return True
        else:
            print(f"❌ {name:12} (port {port}): CLOSED")
            return False
    except Exception as e:
        print(f"❌ {name:12} (port {port}): ERROR - {e}")
        return False

def main():
    print("=" * 50)
    print("OpenD Connection Test")
    print("=" * 50)
    print()
    
    host = '127.0.0.1'
    
    api_ok = test_port(host, 11111, "API")
    ws_ok = test_port(host, 33333, "WebSocket")
    telnet_ok = test_port(host, 22222, "Telnet")
    
    print()
    print("-" * 50)
    
    if api_ok and ws_ok and telnet_ok:
        print("✅ All ports accessible - OpenD is fully operational")
        return 0
    elif api_ok:
        print("⚠️  API accessible - OpenD running (some ports closed)")
        return 0
    else:
        print("❌ OpenD not accessible - service may not be running")
        print()
        print("Troubleshooting:")
        print("  1. Check service status: systemctl status opend")
        print("  2. Check logs: tail -50 /var/log/opend/opend.log")
        print("  3. Start service: systemctl start opend")
        return 1

if __name__ == "__main__":
    sys.exit(main())
PYTHONEOF

chmod +x /opt/opend/test_connection.py
echo "✅ test_connection.py created"
```

### 5.3 Service Management Script

```bash
cat > /opt/opend/opend.sh << 'BASHEOF'
#!/bin/bash
# OpenD Service Management Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/opend/opend.log"
DEVICE_DAT="/root/.com.moomoo.OpenD/F3CNN/Device.dat"

case "$1" in
    start)
        echo "Starting OpenD..."
        systemctl start opend
        sleep 3
        systemctl status opend --no-pager
        ;;
    stop)
        echo "Stopping OpenD..."
        systemctl stop opend
        systemctl status opend --no-pager
        ;;
    restart)
        echo "Restarting OpenD..."
        systemctl restart opend
        sleep 3
        systemctl status opend --no-pager
        ;;
    status)
        systemctl status opend --no-pager
        echo ""
        python3 "$SCRIPT_DIR/test_connection.py"
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    logs-recent)
        tail -100 "$LOG_FILE"
        ;;
    device)
        if [ -f "$DEVICE_DAT" ]; then
            echo "✅ Device.dat exists:"
            ls -la "$DEVICE_DAT"
        else
            echo "❌ Device.dat not found"
            echo "   Location: $DEVICE_DAT"
            echo "   OpenD needs to complete authentication first"
        fi
        ;;
    verify)
        python3 "$SCRIPT_DIR/telnet_verify.py" "$2" "$3"
        ;;
    test)
        python3 "$SCRIPT_DIR/test_connection.py"
        ;;
    *)
        echo "OpenD Service Management"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  start        - Start OpenD service"
        echo "  stop         - Stop OpenD service"
        echo "  restart      - Restart OpenD service"
        echo "  status       - Show service status and port connectivity"
        echo "  logs         - Follow log file (Ctrl+C to exit)"
        echo "  logs-recent  - Show last 100 log lines"
        echo "  device       - Check Device.dat status"
        echo "  test         - Test port connectivity"
        echo "  verify CMD   - Run verification command (status/request_sms/submit_sms/etc)"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 verify request_sms"
        echo "  $0 verify submit_sms 123456"
        ;;
esac
BASHEOF

chmod +x /opt/opend/opend.sh
echo "✅ opend.sh management script created"
```

---

## Phase 6: Restore Device.dat (If Backup Exists)

```bash
# If we backed up Device.dat earlier, restore it
if [ -f /tmp/opend-backup/Device.dat ]; then
    mkdir -p /root/.com.moomoo.OpenD/F3CNN
    cp /tmp/opend-backup/Device.dat /root/.com.moomoo.OpenD/F3CNN/
    echo "✅ Restored Device.dat from backup (may skip 2FA)"
else
    echo "ℹ️  No Device.dat backup found - will need 2FA on first login"
fi
```

---

## Phase 7: Start OpenD & Authenticate

```bash
# Start the service
systemctl start opend

# Wait for startup
echo "Waiting for OpenD to start..."
sleep 15

# Check status
systemctl status opend --no-pager

# Test connectivity
python3 /opt/opend/test_connection.py

# Check logs for any verification requirements
echo ""
echo "=== Recent Logs ==="
tail -30 /var/log/opend/opend.log
```

### If Phone Verification Required:

```bash
# Request SMS code
python3 /opt/opend/telnet_verify.py request_sms

# Wait for SMS on your phone, then submit
python3 /opt/opend/telnet_verify.py submit_sms YOUR_CODE_HERE
```

### If CAPTCHA Required:

```bash
# Request CAPTCHA
python3 /opt/opend/telnet_verify.py request_captcha

# Check logs for CAPTCHA info, then submit
python3 /opt/opend/telnet_verify.py submit_captcha YOUR_CODE_HERE
```

---

## Phase 8: Verify Device.dat Created

```bash
# Check Device.dat exists (proves successful authentication)
ls -la /root/.com.moomoo.OpenD/F3CNN/

# Expected output:
# -rw-r--r-- 1 root root XXX Dec 21 XX:XX Device.dat

# If Device.dat exists, future restarts will NOT require 2FA
```

---

## Phase 9: Enable Auto-Start

```bash
# Enable service to start on boot
systemctl enable opend

# Verify enabled
systemctl is-enabled opend

# Final verification
echo ""
echo "=== Final Status ==="
systemctl status opend --no-pager
python3 /opt/opend/test_connection.py
```

---

## Phase 10: Cleanup (Optional)

**Only run after confirming native OpenD works correctly!**

```bash
# Remove old Docker setup
# rm -rf /root/opend

# Remove Docker images (optional)
# docker system prune -a

# Remove backup
rm -rf /tmp/opend-backup
```

---

## Post-Migration Quick Reference

### File Locations

| Component | Location |
|-----------|----------|
| **Executable** | `/opt/opend/OpenD` |
| **Configuration** | `/opt/opend/OpenD.xml` |
| **Device Identity** | `/root/.com.moomoo.OpenD/F3CNN/Device.dat` |
| **Logs** | `/var/log/opend/opend.log` |
| **Helper Scripts** | `/opt/opend/*.py`, `/opt/opend/opend.sh` |
| **Systemd Service** | `/etc/systemd/system/opend.service` |

### Common Commands

```bash
# Service Management
systemctl start opend           # Start
systemctl stop opend            # Stop
systemctl restart opend         # Restart
systemctl status opend          # Status
systemctl enable opend          # Enable auto-start
systemctl disable opend         # Disable auto-start

# Using opend.sh helper
/opt/opend/opend.sh start       # Start
/opt/opend/opend.sh stop        # Stop
/opt/opend/opend.sh status      # Status + connectivity test
/opt/opend/opend.sh logs        # Follow logs
/opt/opend/opend.sh device      # Check Device.dat

# Logs
tail -f /var/log/opend/opend.log           # Follow logs
tail -100 /var/log/opend/opend.log         # Last 100 lines
journalctl -u opend -f                      # Systemd journal

# Testing
python3 /opt/opend/test_connection.py       # Port connectivity

# Verification (if needed)
python3 /opt/opend/telnet_verify.py status
python3 /opt/opend/telnet_verify.py request_sms
python3 /opt/opend/telnet_verify.py submit_sms CODE
```

### Connection Details (For Python/Catalyst)

```python
# OpenD connection settings (unchanged from Docker)
OPEND_HOST = '127.0.0.1'
OPEND_PORT = 11111

# Example connection
from moomoo import OpenQuoteContext
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
```

---

## Troubleshooting

### OpenD Won't Start

```bash
# Check logs
tail -50 /var/log/opend/opend.log
journalctl -u opend -n 50

# Check config syntax
cat /opt/opend/OpenD.xml

# Try running directly (for detailed errors)
cd /opt/opend && ./OpenD
```

### Ports Not Accessible

```bash
# Check if process is running
ps aux | grep OpenD

# Check what's using ports
ss -tlnp | grep -E '11111|33333|22222'

# Restart service
systemctl restart opend
```

### 2FA Required Again

```bash
# Check if Device.dat exists
ls -la /root/.com.moomoo.OpenD/F3CNN/Device.dat

# If missing, complete verification again
python3 /opt/opend/telnet_verify.py request_sms
python3 /opt/opend/telnet_verify.py submit_sms CODE
```

### Connection Refused from Python

```bash
# Verify OpenD is running
systemctl status opend

# Test ports
python3 /opt/opend/test_connection.py

# Check if binding to correct interface
grep -E '<ip>|<api_port>' /opt/opend/OpenD.xml
```

---

## Rollback to Docker (If Needed)

```bash
# Stop native OpenD
systemctl stop opend
systemctl disable opend

# Restart Docker version (if files still exist)
cd /root/opend
docker compose up -d
```

---

## Migration Checklist

- [ ] Phase 1: Docker stopped, directories created
- [ ] Phase 2: OpenD downloaded and installed
- [ ] Phase 3: OpenD.xml configured with credentials
- [ ] Phase 4: Systemd service created
- [ ] Phase 5: Helper scripts created
- [ ] Phase 6: Device.dat restored (if available)
- [ ] Phase 7: OpenD started and authenticated
- [ ] Phase 8: Device.dat verified (2FA complete)
- [ ] Phase 9: Auto-start enabled
- [ ] Phase 10: Old Docker setup cleaned up
- [ ] Catalyst trading system tested with native OpenD

---

**Document Version:** 1.0
**Created:** December 21, 2025
**Status:** Ready for Execution
