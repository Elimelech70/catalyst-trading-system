# Trade Pipeline Analysis Report

**Name of Application**: Catalyst Trading System
**Name of file**: trade-pipeline-analysis-2025-11-29.md
**Version**: 1.0.0
**Date**: 2025-11-29
**Purpose**: Analysis of trade pipeline test results and root cause identification

---

## Executive Summary

**STATUS: PIPELINE BROKEN - TRADES NOT EXECUTING**

The trade pipeline investigation identified **three critical issues** preventing trade execution:

| # | Issue | Severity | Impact |
|---|-------|----------|--------|
| 1 | Scanner missing Alpaca credentials | **CRITICAL** | No stock universe, no scans |
| 2 | Technical service Redis authentication | HIGH | Service crash loop |
| 3 | Database schema mismatch | MEDIUM | Error logging fails |

**Root Cause**: The scanner service in `docker-compose.yml` does not have `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` environment variables configured, causing it to fail when attempting to fetch the stock universe.

---

## Test Results Summary

### Service Health Status (2025-11-29 06:42 UTC)

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| Scanner | 5001 | HEALTHY | But cannot fetch universe |
| Pattern | 5002 | HEALTHY | |
| Technical | 5003 | **FAILING** | Redis auth error, restart loop |
| Risk Manager | 5004 | HEALTHY | |
| Trading | 5005 | HEALTHY | Has Alpaca creds |
| Workflow | 5006 | HEALTHY | |
| News | 5008 | HEALTHY | |
| Reporting | 5009 | HEALTHY | |
| Redis | 6379 | HEALTHY | |

### Pipeline Test Results

#### Stage 1: Scanner Service
```
Test 1.1 Health Check: PASS
  Response: {"status": "healthy", "version": "6.0.1"}

Test 1.2 Scan Execution: FAIL
  Error: {"detail": "No active stocks found in universe"}

Test 1.3 Database Persistence: FAIL
  No new scan_results created
  Last scan: 2025-11-19 03:00:03 UTC (10 days ago)

Test 1.4 Cycle Update: PARTIAL
  Cycles created but stay in "scanning" status forever
```

**Scanner Log Evidence:**
```
2025-11-28 01:00:21 - WARNING - Alpaca credentials not found - limited universe mode
2025-11-28 01:30:01 - ERROR - Alpaca not configured - cannot fetch universe
2025-11-28 01:30:01 - ERROR - Scanner requires Alpaca credentials
2025-11-28 01:30:01 - ERROR - No active stocks found in universe
```

#### Stage 2: Workflow Coordinator
```
Test 2.1 Health Check: PASS
  Response: {"status": "healthy", "version": "2.0.0"}

Test 2.2 Config Loading: PASS
  Mode: autonomous (correctly loaded from trading_config.yaml)

Test 2.3 Workflow Start: PASS
  Response: {"success": true, "cycle_id": "cycle_20251129_064329"}

Test 2.4 Pipeline Progression: FAIL
  Status: "failed" after 0.024 seconds
  Error: "Scanner failed: HTTP 500"
```

**Workflow Log Evidence:**
```
2025-11-29 06:43:29 - INFO - [cycle_20251129_064329] Stage 1: Scanning market...
2025-11-29 06:43:29 - ERROR - [cycle_20251129_064329] Workflow failed: Scanner failed: HTTP 500
```

#### Stage 3: Trading Service & Alpaca
```
Test 3.1 Health Check: PASS
  Response: {"status": "healthy", "version": "8.0.0", "database": "connected"}

Test 3.2 Alpaca Connection: PASS
  Account: PA3BQ6U2T8ZV
  Status: ACTIVE
  Cash: $98,611.55
  Portfolio Value: $100,153.27
  Buying Power: $198,764.82

Test 3.3 Current Positions:
  - AAPL: 2 shares @ $201.52 (P/L: +$154.66)
  - MSFT: 2 shares @ $492.70 (P/L: -$1.38)

Test 3.4 Trading Container Credentials: PASS
  ALPACA_API_KEY=PK8ZTV60LQ83FALFQ2G4
  ALPACA_SECRET_KEY=<configured>
  ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

#### Stage 4: End-to-End Trade Execution
```
Test 4.1 Full Pipeline: FAIL
  Pipeline fails at Stage 1 (Scanner)
  No candidates reach trading stage

Test 4.2 Database Records: FAIL
  No new positions created
  Only 1 old position from 2025-10-11

Test 4.3 Alpaca Verification: N/A
  No new orders to verify
```

---

## Root Cause Analysis

### Issue #1: Scanner Missing Alpaca Credentials (CRITICAL)

**Location**: `/root/catalyst-trading-system/docker-compose.yml` lines 88-121

**Problem**: The scanner service environment section does NOT include:
```yaml
ALPACA_API_KEY: ${ALPACA_API_KEY:-}
ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY:-}
ALPACA_BASE_URL: ${ALPACA_BASE_URL:-https://paper-api.alpaca.markets}
```

**Evidence**: Container environment check:
```bash
$ docker exec catalyst-scanner env | grep ALPACA
# (no output - credentials missing)

$ docker exec catalyst-trading env | grep ALPACA
ALPACA_API_KEY=PK8ZTV60LQ83FALFQ2G4
ALPACA_SECRET_KEY=6VvdVlR9h5KcH9BXxLIa4XqHlX8VS0AKbWQcZood
# (trading service has credentials)
```

**Impact**: Scanner cannot call Alpaca API to get tradeable assets, so returns empty universe.

**Fix Required**:
```yaml
# In docker-compose.yml, scanner service section, add:
scanner:
  environment:
    # ... existing vars ...
    ALPACA_API_KEY: ${ALPACA_API_KEY:-}
    ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY:-}
    ALPACA_BASE_URL: ${ALPACA_BASE_URL:-https://paper-api.alpaca.markets}
```

### Issue #2: Technical Service Redis Authentication (HIGH)

**Location**: Technical service container

**Problem**: Technical service fails to authenticate with Redis:
```
redis.exceptions.AuthenticationError: Authentication required.
ERROR: Application startup failed. Exiting.
```

**Evidence**: Container status shows continuous restart:
```
catalyst-technical       Restarting (3) 1 second ago
```

**Root Cause**: Technical service connects to Redis without password, but Redis requires `REDIS_PASSWORD`.

**Fix Required**: Add to technical service environment:
```yaml
REDIS_PASSWORD: ${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}
REDIS_URL: redis://:${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}@redis:6379/0
```

### Issue #3: Database Schema Mismatch (MEDIUM)

**Location**: Scanner service error handling

**Problem**: Scanner tries to update non-existent column:
```
Failed to update cycle status: column "error_message" of relation "trading_cycles" does not exist
```

**Impact**: Error logging fails, but doesn't break core functionality.

**Fix**: Either add `error_message` column to `trading_cycles` table or update scanner error handling.

---

## Timeline of Failure

| Date | Event |
|------|-------|
| Before 2025-11-19 | System working - scans successful |
| ~2025-11-19 | Last successful scan recorded |
| 2025-11-20 onwards | Scanner fails silently, cycles created but no scans |
| 2025-11-29 | Issue diagnosed - missing Alpaca credentials |

**Note**: The exact date when Alpaca credentials were removed from scanner config is unknown. This may have occurred during a docker-compose.yml update or service refactoring.

---

## Service Dependency Map

```
                    ┌─────────────────────────────────────────────┐
                    │              CRON (triggers)                │
                    └─────────────────────────────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────────┐
                    │      WORKFLOW COORDINATOR (5006)            │
                    │      Status: HEALTHY                        │
                    └─────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │ SCANNER (5001)│   │ PATTERN (5002)│   │ NEWS (5008)   │
            │ ❌ NO ALPACA  │   │ HEALTHY       │   │ HEALTHY       │
            │   CREDENTIALS │   │               │   │               │
            └───────────────┘   └───────────────┘   └───────────────┘
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌───────────────┐   ┌───────────────┐
            │TECHNICAL(5003)│   │RISK MGR (5004)│
            │ ❌ REDIS AUTH │   │ HEALTHY       │
            │   FAILURE     │   │               │
            └───────────────┘   └───────────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   TRADING (5005)      │
                            │   ✅ HEALTHY          │
                            │   ✅ HAS ALPACA CREDS │
                            └───────────────────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   ALPACA PAPER API    │
                            │   ✅ ACCESSIBLE       │
                            │   Account: PA3BQ6U2T8ZV│
                            └───────────────────────┘
```

---

## Recommendations

### Immediate Fixes (Priority 1)

1. **Add Alpaca credentials to scanner service in docker-compose.yml**
   - File: `/root/catalyst-trading-system/docker-compose.yml`
   - Add ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL to scanner environment

2. **Add Redis password to technical service in docker-compose.yml**
   - File: `/root/catalyst-trading-system/docker-compose.yml`
   - Add REDIS_PASSWORD and/or REDIS_URL to technical environment

3. **Restart services after fix**
   ```bash
   cd /root/catalyst-trading-system
   docker-compose down
   docker-compose up -d --build
   ```

### Verification After Fix

1. Check scanner can fetch universe:
   ```bash
   curl -X POST http://localhost:5001/api/v1/scan
   # Should return picks array with candidates
   ```

2. Verify new scan_results in database:
   ```sql
   SELECT COUNT(*) FROM scan_results WHERE scan_timestamp > NOW() - INTERVAL '5 minutes';
   ```

3. Run full workflow:
   ```bash
   curl -X POST http://localhost:5006/api/v1/workflow/start \
     -H "Content-Type: application/json" \
     -d '{"mode":"autonomous","max_positions":1}'
   ```

4. Verify trade execution:
   ```bash
   curl https://paper-api.alpaca.markets/v2/orders?status=all&limit=5
   ```

---

## Appendix: Environment Variable Comparison

### Scanner Service (BROKEN)
```yaml
environment:
  SERVICE_PORT: 5001
  DATABASE_URL: ${DATABASE_URL}
  REDIS_HOST: redis
  REDIS_PORT: 6379
  ALPHAVANTAGE_API_KEY: ${ALPHAVANTAGE_API_KEY:-}  # Not used for universe
  POLYGON_API_KEY: ${POLYGON_API_KEY:-}            # Not used for universe
  # MISSING: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL
```

### Trading Service (WORKING)
```yaml
environment:
  SERVICE_PORT: 5005
  DATABASE_URL: ${DATABASE_URL}
  REDIS_HOST: redis
  REDIS_PORT: 6379
  ALPACA_API_KEY: ${ALPACA_API_KEY:-}          # ✅ Present
  ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY:-}    # ✅ Present
  ALPACA_BASE_URL: ${ALPACA_BASE_URL:-...}     # ✅ Present
```

### Risk Manager Service (WORKING)
```yaml
environment:
  # ... other vars ...
  ALPACA_API_KEY: ${ALPACA_API_KEY:-}          # ✅ Present
  ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY:-}    # ✅ Present
  ALPACA_BASE_URL: ${ALPACA_BASE_URL:-...}     # ✅ Present
```

---

## Conclusion

The trade pipeline is broken due to a **configuration oversight** where Alpaca credentials were not added to the scanner service in docker-compose.yml. This is a simple fix requiring 3 lines of YAML configuration.

Once fixed, the pipeline should resume normal operation:
1. Scanner fetches stock universe from Alpaca
2. Candidates flow through pattern/technical/risk analysis
3. Approved trades execute via trading service
4. Orders appear in Alpaca paper account

**Estimated Time to Fix**: 5-10 minutes (config change + restart)

---

*Report generated by Claude Code pipeline analysis*
*Test execution date: 2025-11-29 06:42 UTC*
