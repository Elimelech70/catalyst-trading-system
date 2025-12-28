# Catalyst Trading System - C1 & C2 Fix Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** IMPLEMENTATION-GUIDE.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-27  
**Purpose:** Implementation guide for C1 (Orders in Positions) and C2 (alpaca_trader.py duplication) fixes

---

## Executive Summary

This implementation package contains all files needed to fix:

| ID | Issue | Solution |
|----|-------|----------|
| **C1** | Orders stored in positions table (violates ARCHITECTURE-RULES.md Rule 1) | Create proper orders table, migrate data, update services |
| **C2** | alpaca_trader.py duplicated in 4+ locations | Consolidate to single authoritative module in shared/common/ |

---

## Implementation Order

### Phase 1: Pre-deployment Checks (5 min)
1. Verify database connection
2. Backup database
3. Verify no active trading cycle

### Phase 2: Database Migration (10 min)
1. Run orders table migration
2. Verify migration success
3. DO NOT drop old columns yet

### Phase 3: Code Deployment (15 min)
1. Deploy consolidated alpaca_trader.py
2. Update trading-service.py
3. Update trade_watchdog.py
4. Restart services

### Phase 4: Verification (10 min)
1. Run Doctor Claude diagnostic
2. Verify orders table populated
3. Test order submission (paper mode)

### Phase 5: Cleanup (After 1 trading day)
1. Run Phase 2 migration to drop old columns
2. Final verification

---

## File Manifest

```
c1-c2-implementation/
├── IMPLEMENTATION-GUIDE.md          # This file
├── sql/
│   ├── 01-orders-table-create.sql   # Phase 1: Create orders table
│   ├── 02-migrate-data.sql          # Phase 1: Migrate from positions
│   └── 03-cleanup-positions.sql     # Phase 5: Drop old columns (AFTER verification)
├── services/
│   └── shared/
│       └── common/
│           └── alpaca_trader.py     # Consolidated Alpaca client (C2 fix)
├── trading/
│   └── trading-service-orders.py    # Updated trading service (C1 fix)
├── scripts/
│   ├── trade_watchdog_v2.py         # Doctor Claude uses orders table
│   └── verify-c1-c2-fixes.py        # Verification script
└── tests/
    └── test_orders_integration.py   # Integration tests
```

---

## Deployment Commands

### Step 1: Backup Database

```bash
# SSH to droplet
ssh root@catalyst-droplet

# Create backup
pg_dump $DATABASE_URL > /backups/catalyst/pre-c1-c2-$(date +%Y%m%d_%H%M%S).sql
echo "Backup created: $(ls -la /backups/catalyst/ | tail -1)"
```

### Step 2: Upload Implementation Files

```bash
# From local machine
scp -r c1-c2-implementation root@catalyst-droplet:/root/catalyst-trading-system/
```

### Step 3: Run Database Migration

```bash
# On droplet
cd /root/catalyst-trading-system

# Create orders table
psql $DATABASE_URL -f c1-c2-implementation/sql/01-orders-table-create.sql

# Migrate existing data
psql $DATABASE_URL -f c1-c2-implementation/sql/02-migrate-data.sql

# Verify
psql $DATABASE_URL -c "SELECT COUNT(*) as orders_migrated FROM orders;"
```

### Step 4: Deploy Code Changes

```bash
# Backup existing files
cp services/shared/common/alpaca_trader.py services/shared/common/alpaca_trader.py.backup
cp services/trading/trading-service.py services/trading/trading-service.py.backup
cp scripts/trade_watchdog.py scripts/trade_watchdog.py.backup

# Deploy new files
cp c1-c2-implementation/services/shared/common/alpaca_trader.py services/shared/common/
cp c1-c2-implementation/trading/trading-service-orders.py services/trading/trading-service.py
cp c1-c2-implementation/scripts/trade_watchdog_v2.py scripts/trade_watchdog.py

# Remove duplicates (create symlinks instead)
rm -f services/trading/common/alpaca_trader.py
rm -f services/risk-manager/common/alpaca_trader.py
rm -f services/workflow/common/alpaca_trader.py

# Create symlinks
ln -sf /root/catalyst-trading-system/services/shared/common/alpaca_trader.py services/trading/common/alpaca_trader.py
ln -sf /root/catalyst-trading-system/services/shared/common/alpaca_trader.py services/risk-manager/common/alpaca_trader.py
ln -sf /root/catalyst-trading-system/services/shared/common/alpaca_trader.py services/workflow/common/alpaca_trader.py
```

### Step 5: Restart Services

```bash
# Restart Docker containers
docker-compose restart trading-service risk-manager workflow-service

# Verify services are running
docker-compose ps
```

### Step 6: Run Verification

```bash
# Run Doctor Claude diagnostic
python3 scripts/trade_watchdog.py --pretty

# Run verification script
python3 c1-c2-implementation/scripts/verify-c1-c2-fixes.py
```

---

## Doctor Claude Testing

After deployment, Doctor Claude will automatically test the fixes during its next 5-minute monitoring cycle. The updated trade_watchdog.py will:

1. **Query orders table** (not positions.alpaca_* columns)
2. **Detect stuck orders** from orders table
3. **Reconcile orders** with Alpaca API
4. **Report issues** in structured JSON format

### Manual Doctor Claude Test

```bash
# Run diagnostic manually
python3 scripts/trade_watchdog.py --pretty

# Expected output (no errors):
{
  "timestamp": "2025-12-27T...",
  "status": "HEALTHY",
  "orders": {
    "total": 83,
    "submitted": 0,
    "filled": 83,
    "stuck": 0
  },
  "positions": {
    "open": 16,
    "closed": 67
  },
  "issues": []
}
```

---

## Rollback Procedure

If something goes wrong:

```bash
# Restore database backup
psql $DATABASE_URL < /backups/catalyst/pre-c1-c2-YYYYMMDD_HHMMSS.sql

# Restore code files
cp services/shared/common/alpaca_trader.py.backup services/shared/common/alpaca_trader.py
cp services/trading/trading-service.py.backup services/trading/trading-service.py
cp scripts/trade_watchdog.py.backup scripts/trade_watchdog.py

# Remove symlinks, restore duplicates
rm -f services/trading/common/alpaca_trader.py
rm -f services/risk-manager/common/alpaca_trader.py
rm -f services/workflow/common/alpaca_trader.py
cp services/shared/common/alpaca_trader.py.backup services/trading/common/alpaca_trader.py
cp services/shared/common/alpaca_trader.py.backup services/risk-manager/common/alpaca_trader.py
cp services/shared/common/alpaca_trader.py.backup services/workflow/common/alpaca_trader.py

# Restart services
docker-compose restart
```

---

## Post-Deployment Checklist

- [ ] Database backup created
- [ ] Orders table created
- [ ] Data migrated (verify count matches)
- [ ] alpaca_trader.py consolidated
- [ ] Symlinks created for duplicates
- [ ] trading-service.py updated
- [ ] trade_watchdog.py updated
- [ ] Services restarted
- [ ] Doctor Claude diagnostic passes
- [ ] Paper trade test successful
- [ ] (After 1 day) Old columns dropped

---

## References

- `Documentation/Implementation/Claude/ORDERS-POSITIONS-IMPLEMENTATION.md` - Authority document
- `Documentation/Implementation/Claude/ARCHITECTURE-RULES.md` - Rules being fixed
- `catalyst-workflows-and-audit.md` - Audit findings

---

*Implementation Package by Claude Opus 4.5*  
*Catalyst Trading System*  
*December 27, 2025*
