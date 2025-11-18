# Catalyst Trading System - Cron Automation

## 🎯 Overview

The Catalyst Trading System now runs **fully automated** with scheduled market scans and health monitoring via cron.

## ✅ What's Automated

### 📊 Market Scans (Mon-Fri Only)

| Time (EST) | Time (UTC) | Purpose |
|------------|------------|---------|
| 09:15 AM | 14:15 | Pre-market scan |
| 09:30 AM | 14:30 | Market open scan |
| 10:30 AM | 15:30 | Mid-morning scan |
| 12:00 PM | 17:00 | Late morning scan |
| 01:30 PM | 18:30 | Early afternoon scan |
| 03:00 PM | 20:00 | Late afternoon scan |
| 04:00 PM | 21:00 | Market close scan |

**Total: 7 scans per trading day**

### 🏥 Health Checks

- **Frequency**: Every 15 minutes
- **Schedule**: 24/7, every day
- **Monitors**: All 6 services (Scanner, News, Technical, Risk Manager, Trading, Workflow)

## 📁 Files

### Scripts
- `scripts/cron-scan.sh` - Triggers market scans via API
- `scripts/cron-health-check.sh` - Monitors service health
- `scripts/catalyst.crontab` - Cron schedule configuration

### Logs
- `/tmp/catalyst-cron/scan-YYYYMMDD.log` - Scan execution logs
- `/tmp/catalyst-cron/health-YYYYMMDD.log` - Health check logs
- **Retention**: 7 days (auto-cleanup)

## 🔧 Management

### View Current Crontab
```bash
crontab -l
```

### Install/Update Crontab
```bash
crontab /workspaces/catalyst-trading-system/catalyst-trading-system/scripts/catalyst.crontab
```

### Remove Crontab
```bash
crontab -r
```

### Check Cron Service
```bash
sudo service cron status
```

### Start Cron Service
```bash
sudo service cron start
```

### View Logs
```bash
# Today's scan logs
cat /tmp/catalyst-cron/scan-$(date +%Y%m%d).log

# Today's health logs
cat /tmp/catalyst-cron/health-$(date +%Y%m%d).log

# Live tail
tail -f /tmp/catalyst-cron/scan-$(date +%Y%m%d).log
```

## 🧪 Testing

### Test Health Check Manually
```bash
bash /workspaces/catalyst-trading-system/catalyst-trading-system/scripts/cron-health-check.sh
cat /tmp/catalyst-cron/health-$(date +%Y%m%d).log
```

### Test Scan Manually
```bash
bash /workspaces/catalyst-trading-system/catalyst-trading-system/scripts/cron-scan.sh
cat /tmp/catalyst-cron/scan-$(date +%Y%m%d).log
```

### Trigger API Scan Directly
```bash
curl -X POST http://localhost:5001/api/v1/scan
```

## 📊 Expected Results

### Scan Log Example
```
========================================
Scan started: Tue Nov 18 09:02:51 UTC 2025
========================================
HTTP Status: 200
Response: {"success":true,"cycle_id":"20251118-005","candidates":0,"picks":[],"errors":null}
✓ Scan completed successfully
Cycle ID: 20251118-005
Candidates found: 0
Scan completed: Tue Nov 18 09:03:00 UTC 2025
```

### Health Log Example
```
[09:02:31] ✓ scanner (port 5001): healthy
[09:02:31] ✓ news (port 5002): healthy
[09:02:32] ✓ technical (port 5003): healthy
[09:02:32] ✓ risk-manager (port 5004): healthy
[09:02:33] ✓ trading (port 5005): healthy
[09:02:33] ✓ workflow (port 5006): healthy
[09:02:33] All services healthy
```

## ⚠️ Important Notes

1. **Services must be running** for cron jobs to work
2. **Market hours** are based on US Eastern Time
3. **Weekend scans** are automatically skipped (Mon-Fri only)
4. **Health checks** run 24/7 regardless of market hours
5. **Logs auto-delete** after 7 days to save disk space

## 🚀 Quick Start

After system boot:

1. Start services:
   ```bash
   bash /tmp/start_all_services.sh
   ```

2. Start cron:
   ```bash
   sudo service cron start
   ```

3. Verify cron is running:
   ```bash
   sudo service cron status
   crontab -l
   ```

4. Monitor logs:
   ```bash
   tail -f /tmp/catalyst-cron/health-$(date +%Y%m%d).log
   ```

## 🎊 System Status

- ✅ All 6 services running (v6.0.0)
- ✅ Database connected (v6.0 3NF normalized)
- ✅ Cron service active
- ✅ Automated scans configured
- ✅ Health monitoring enabled

**The system is now fully autonomous!** 🚀
