# Incident Report: Service Outage - December 29-30, 2025

**Incident ID**: INC-2025-12-30-001
**Severity**: High
**Status**: Resolved
**Date Detected**: December 30, 2025 09:43 AWST (December 29, 2025 20:43 ET)
**Date Resolved**: December 30, 2025 10:10 AWST (December 29, 2025 21:10 ET)

---

## Executive Summary

Trading services failed to restart after the scheduled daily shutdown, resulting in a complete missed trading day on Monday, December 29, 2025 (US). Two root causes were identified and fixed: a missing directory change in the cron startup command, and broken symlinks in Docker container builds.

---

## Timeline

| Time (ET) | Time (AWST) | Event |
|-----------|-------------|-------|
| Dec 28, 15:00 | Dec 29, 04:00 | Last successful trading cycle (20251228-004) |
| Dec 28, 17:00 | Dec 29, 06:00 | Scheduled service shutdown (cron) |
| Dec 29, 08:00 | Dec 29, 21:00 | Service restart FAILED - cron triggered but docker-compose couldn't find config |
| Dec 29, 09:30 | Dec 29, 22:30 | Market open trading cycle FAILED - connection refused |
| Dec 29, 11:00 | Dec 30, 00:00 | Mid-morning cycle FAILED - connection refused |
| Dec 29, 13:00 | Dec 30, 02:00 | Afternoon cycle FAILED - connection refused |
| Dec 29, 15:00 | Dec 30, 04:00 | Late afternoon cycle FAILED - connection refused |
| Dec 29, 20:43 | Dec 30, 09:43 | Issue detected during manual check |
| Dec 29, 21:10 | Dec 30, 10:10 | All services restored and healthy |

---

## Root Cause Analysis

### Primary Cause: Missing Directory Change in Cron

The cron job for starting services before market open was missing the `cd` command:

**Before (Broken):**
```bash
0 21 * * 0-4 docker-compose up -d >> /var/log/catalyst/startup.log 2>&1
```

**After (Fixed):**
```bash
0 21 * * 0-4 cd /root/catalyst-trading-system && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1
```

Without the directory change, `docker-compose` couldn't find `docker-compose.yml` and failed with:
```
no configuration file provided: not found
```

### Secondary Cause: Broken Symlinks in Docker Builds

Two services (workflow, risk-manager) had symlinks to shared files that don't work inside Docker containers:

```
services/workflow/common/alpaca_trader.py -> /root/catalyst-trading-system/services/shared/common/alpaca_trader.py
services/risk-manager/common/alpaca_trader.py -> /root/catalyst-trading-system/services/shared/common/alpaca_trader.py
```

Symlinks with absolute host paths resolve to nothing inside containers, causing:
```
ModuleNotFoundError: No module named 'common.alpaca_trader'
```

---

## Impact Assessment

### Trading Impact
- **Missed Trading Day**: Monday, December 29, 2025 (full US market session)
- **Missed Cycles**: 4 scheduled trading cycles
- **Potential Trades Missed**: Unknown (scanner did not run)

### Position Impact
14 positions opened on December 28 remained open without monitoring:

| Symbol | Side | Qty | Entry Price | Entry Time (ET) | Value |
|--------|------|-----|-------------|-----------------|-------|
| QBTS | long | 200 | $25.29 | 09:30 | $5,058 |
| MRNA | long | 200 | $31.20 | 09:30 | $6,240 |
| NVTS | long | 200 | $7.40 | 11:00 | $1,480 |
| CLSK | long | 200 | $10.91 | 11:00 | $2,182 |
| AAL | long | 200 | $15.44 | 11:00 | $3,088 |
| M | long | 200 | $22.47 | 11:00 | $4,494 |
| JOBY | long | 200 | $13.88 | 11:00 | $2,776 |
| ONDS | long | 200 | $8.48 | 13:00 | $1,696 |
| WULF | long | 200 | $11.75 | 13:00 | $2,350 |
| PSKY | long | 200 | $13.59 | 13:00 | $2,718 |
| TE | long | 200 | $6.80 | 13:00 | $1,360 |
| AEO | long | 200 | $26.36 | 13:00 | $5,272 |
| MARA | long | 200 | $9.59 | 15:00 | $1,918 |
| OPEN | long | 200 | $6.01 | 15:00 | $1,202 |

**Total Position Value at Entry**: $41,834

### Risk Exposure
- Positions held overnight and through full trading day without stop-loss monitoring
- No risk manager service running to execute emergency stops if needed

---

## Resolution Actions

### Immediate Fixes Applied

1. **Fixed Cron Startup Command**
   ```bash
   # Changed from:
   0 21 * * 0-4 docker-compose up -d >> /var/log/catalyst/startup.log 2>&1

   # To:
   0 21 * * 0-4 cd /root/catalyst-trading-system && docker-compose up -d >> /var/log/catalyst/startup.log 2>&1
   ```

2. **Replaced Symlinks with Actual Files**
   ```bash
   # Workflow service
   rm services/workflow/common/alpaca_trader.py
   cp services/shared/common/alpaca_trader.py services/workflow/common/

   # Risk-manager service
   rm services/risk-manager/common/alpaca_trader.py
   cp services/shared/common/alpaca_trader.py services/risk-manager/common/
   ```

3. **Rebuilt Affected Services**
   ```bash
   docker-compose up -d --no-deps --build workflow
   docker-compose up -d --no-deps --build risk-manager
   ```

### Verification
All 10 services confirmed healthy after fixes:
- catalyst-redis (healthy)
- catalyst-orchestration (healthy)
- catalyst-scanner (healthy)
- catalyst-pattern (healthy)
- catalyst-technical (healthy)
- catalyst-news (healthy)
- catalyst-reporting (healthy)
- catalyst-risk-manager (healthy)
- catalyst-trading (healthy)
- catalyst-workflow (healthy)

---

## Prevention Measures

### Short-term
1. Add startup verification to health check script
2. Monitor startup.log for "configuration file" errors
3. Audit all services for symlinks in common/ folders

### Long-term
1. **Standardize shared code distribution** - Use volume mounts consistently instead of copying/symlinking
2. **Add alerting** - Email/SMS alert if services fail to start within expected window
3. **Startup health check** - Add a cron job 15 minutes after startup to verify services are running
4. **Pre-market verification** - Automated check at 21:15 AWST to confirm all services healthy before trading

### Recommended Cron Addition
```bash
# Verify services started correctly (15 min after scheduled start)
15 21 * * 0-4 /root/catalyst-trading-system/scripts/verify-startup.sh >> /var/log/catalyst/startup-verify.log 2>&1
```

---

## Lessons Learned

1. **Test cron jobs in isolation** - Cron runs with different environment/directory than interactive shells
2. **Avoid symlinks in Docker builds** - Symlinks to absolute paths on host don't resolve inside containers
3. **Add redundant monitoring** - Service health checks during market hours weren't enough; need startup verification
4. **Centralize shared code properly** - Current approach of copying common/ to each service is fragile

---

## Appendix: Service Status at Detection

```
NAME                     STATUS
catalyst-news            Up (healthy)
catalyst-orchestration   Up (healthy)
catalyst-pattern         Up (healthy)
catalyst-redis           Up (healthy)
catalyst-reporting       Up (healthy)
catalyst-risk-manager    Restarting (crash loop)
catalyst-scanner         Up (healthy)
catalyst-technical       Up (healthy)
catalyst-trading         Up (healthy)
catalyst-workflow        Restarting (crash loop)
```

---

**Report Generated**: December 30, 2025 10:15 AWST
**Author**: Claude Code (Automated Analysis)
