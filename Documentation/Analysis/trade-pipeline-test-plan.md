# Trade Pipeline Test Plan

**Name of Application**: Catalyst Trading System
**Name of file**: trade-pipeline-test-plan.md
**Version**: 1.0.0
**Created**: 2025-11-29
**Purpose**: Comprehensive test plan to diagnose and verify the trade execution pipeline

---

## 1. Test Objective

Identify why trades are not being executed despite:
- Trading cycles being created successfully
- Alpaca account being active and functional
- Configuration set to autonomous mode

**Known Issue**: Scan results stopped being saved after 2025-11-19. Pipeline appears broken between scanner and downstream services.

---

## 2. Success Criteria

### Stage 1: Scanner Service
| Test | Success Criteria |
|------|------------------|
| 1.1 Health Check | Returns `{"status": "healthy"}` |
| 1.2 Scan Execution | Returns `picks` array with candidates |
| 1.3 Database Persistence | New rows appear in `scan_results` table |
| 1.4 Cycle Update | `trading_cycles.status` updates appropriately |

### Stage 2: Workflow Coordinator
| Test | Success Criteria |
|------|------------------|
| 2.1 Health Check | Returns healthy status with version info |
| 2.2 Config Loading | `trading_config.yaml` loads with `mode: autonomous` |
| 2.3 Workflow Start | Returns `{"success": true, "cycle_id": "..."}` |
| 2.4 Pipeline Progression | Status progresses: scanning → filtering → analyzing → executing |

### Stage 3: Trading Service + Alpaca
| Test | Success Criteria |
|------|------------------|
| 3.1 Health Check | Returns healthy with database connected |
| 3.2 Alpaca Connection | Can fetch account info via API |
| 3.3 Position Creation | Can create position record in database |
| 3.4 Order Submission | Can submit order to Alpaca (paper) |

### Stage 4: End-to-End Trade Execution
| Test | Success Criteria |
|------|------------------|
| 4.1 Full Pipeline | Workflow completes with `executed_trades > 0` |
| 4.2 Database Records | New position in `positions` table with `alpaca_order_id` |
| 4.3 Alpaca Verification | Order visible in Alpaca account |

---

## 3. Test Procedure

### Pre-Test Setup
1. Start all Docker services
2. Verify database connectivity
3. Record baseline state (current positions, scan_results count)

### Stage 1: Scanner Tests
```bash
# 1.1 Health check
curl http://localhost:5001/health

# 1.2 Trigger scan
curl -X POST http://localhost:5001/api/v1/scan

# 1.3 Verify database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM scan_results WHERE scan_timestamp > NOW() - INTERVAL '5 minutes';"

# 1.4 Check cycle status
psql $DATABASE_URL -c "SELECT cycle_id, status FROM trading_cycles ORDER BY started_at DESC LIMIT 1;"
```

### Stage 2: Workflow Tests
```bash
# 2.1 Health check
curl http://localhost:5006/health

# 2.2 Start workflow
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode":"autonomous","max_positions":1,"execute_top_n":1}'

# 2.3 Check status progression
curl http://localhost:5006/api/v1/workflow/status
```

### Stage 3: Trading Service Tests
```bash
# 3.1 Health check
curl http://localhost:5005/health

# 3.2 Test Alpaca connection (via direct API)
curl -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
     https://paper-api.alpaca.markets/v2/account

# 3.3 Check active positions in database
psql $DATABASE_URL -c "SELECT * FROM positions WHERE status = 'open';"
```

### Stage 4: End-to-End Test
```bash
# 4.1 Trigger full autonomous workflow
curl -X POST http://localhost:5006/api/v1/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"mode":"autonomous","max_positions":1,"execute_top_n":1}'

# Wait 2-3 minutes for pipeline completion

# 4.2 Verify results
psql $DATABASE_URL -c "SELECT p.*, s.symbol FROM positions p JOIN securities s ON p.security_id = s.security_id WHERE p.opened_at > NOW() - INTERVAL '10 minutes';"

# 4.3 Check Alpaca for new orders
curl -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
     "https://paper-api.alpaca.markets/v2/orders?status=all&limit=5"
```

---

## 4. Diagnostic Checkpoints

If any stage fails, capture:

1. **Docker container logs**:
   ```bash
   docker logs catalyst-scanner-1 --tail 100
   docker logs catalyst-workflow-1 --tail 100
   docker logs catalyst-trading-1 --tail 100
   ```

2. **Database state**:
   ```bash
   psql $DATABASE_URL -c "SELECT cycle_id, status, current_positions FROM trading_cycles ORDER BY started_at DESC LIMIT 5;"
   ```

3. **Service connectivity**:
   ```bash
   for port in 5001 5002 5003 5004 5005 5006; do
     echo "Port $port: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:$port/health)"
   done
   ```

---

## 5. Expected Outcomes

### If Pipeline Works:
- New scan_results rows created
- Trading cycle transitions to "completed"
- Position created in database with alpaca_order_id
- Order visible in Alpaca paper account

### If Pipeline Fails:
- Document exact failure point
- Capture error logs
- Identify root cause for remediation

---

## 6. Test Execution Log

*To be filled during test execution*

| Timestamp | Test | Result | Notes |
|-----------|------|--------|-------|
| | | | |

---

## 7. Analysis Document

*To be produced after test completion with:*
- Summary of findings
- Root cause identification
- Recommended fixes
- Before/after comparison
