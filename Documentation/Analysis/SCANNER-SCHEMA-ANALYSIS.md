# Scanner Service Database Schema Analysis

**Date**: 2025-11-22
**Service**: scanner-service.py (v6.0.0)
**Status**: CRITICAL SCHEMA MISMATCHES IDENTIFIED
**Severity**: HIGH - Service will fail on INSERT/UPDATE operations

---

## Executive Summary

The scanner service (`services/scanner/scanner-service.py`) contains multiple critical schema mismatches that will cause database errors during execution. The code attempts to INSERT and UPDATE using column names that do not exist in the actual database schema.

**Impact**:
- Scan operations will fail when persisting results
- Trading cycle creation will fail
- Schema verification checks for wrong columns

**Root Cause**: The scanner service code was written against a different schema version than what's deployed in the database.

---

## Table of Contents

1. [Schema Comparison Matrix](#schema-comparison-matrix)
2. [Critical Issues by Function](#critical-issues-by-function)
3. [Detailed Analysis](#detailed-analysis)
4. [Recommended Fixes](#recommended-fixes)
5. [Testing Checklist](#testing-checklist)

---

## Schema Comparison Matrix

### scan_results Table

| Source | Column Names Used | Status |
|--------|------------------|--------|
| **Actual Database** | `id`, `cycle_id`, `security_id`, `scan_timestamp`, `momentum_score`, `volume_score`, `catalyst_score`, `technical_score`, `composite_score`, `price`, `volume`, `rank`, `selected_for_trading`, `scan_metadata`, `created_at` | ✅ Ground Truth |
| **Scanner INSERT** (line 583-598) | Uses: `scan_type`❌, `price_at_scan`❌, `volume_at_scan`❌, `rank_in_scan`❌, `final_candidate`❌ | 🔴 BROKEN |
| **Scanner Verification** (line 218-220) | Checks: `scan_id`❌, `price_at_scan`❌, `volume_at_scan`❌, `rank_in_scan`❌ | 🔴 BROKEN |
| **Scanner SELECT** (line 671-692) | Uses: `rank`, `price`, `volume`, `composite_score`, `scan_metadata` | ✅ CORRECT |
| **Design Doc v6.0** | `scan_id` (UUID), `rank`, `final_score`, `price`, `volume`, `pattern`, `catalyst_type`, etc. | ⚠️ Different from actual |

### trading_cycles Table

| Source | Column Names Used | Status |
|--------|------------------|--------|
| **Actual Database** | `cycle_id`, `mode`, `status`, `max_positions`, `max_daily_loss`, `position_size_multiplier`, `risk_level`, `scan_frequency`, `started_at`, `stopped_at`, `total_risk_budget`, `used_risk_budget`, `current_positions`, `current_exposure`, `configuration`, `created_at`, `updated_at` | ✅ Ground Truth |
| **Scanner INSERT** (line 289-305) | Uses: `cycle_date`❌, `cycle_number`❌, `session_mode`❌, `triggered_by`❌ | 🔴 BROKEN |
| **Scanner UPDATE** (line 335-346) | Uses: `scan_completed_at`❌, `candidates_identified`❌ | 🔴 BROKEN |
| **Scanner SELECT** (line 752-767) | Uses: `mode`, `status`, `max_positions`, `scan_frequency`, `started_at`, `stopped_at`, etc. | ✅ CORRECT |
| **Design Doc v6.0** | `cycle_id` (UUID), `date`, `cycle_state`, `phase`, `session_mode`, `started_at`, `completed_at`, etc. | ⚠️ Different from actual |

---

## Critical Issues by Function

### 1. `persist_scan_results()` - Line 571-626

**Location**: `services/scanner/scanner-service.py:583-598`

**Issue**: INSERT statement uses non-existent columns

```python
# CURRENT CODE (BROKEN):
await state.db_pool.execute("""
    INSERT INTO scan_results (
        cycle_id,
        security_id,
        scan_timestamp,
        scan_type,              # ❌ DOES NOT EXIST
        momentum_score,
        volume_score,
        catalyst_score,
        technical_score,
        composite_score,
        price_at_scan,          # ❌ SHOULD BE: price
        volume_at_scan,         # ❌ SHOULD BE: volume
        rank_in_scan,           # ❌ SHOULD BE: rank
        final_candidate         # ❌ SHOULD BE: selected_for_trading
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
""", ...)
```

**Error Generated**:
```
ERROR: column "scan_type" of relation "scan_results" does not exist
```

**Required Fix**: Update column names to match actual schema:
- Remove `scan_type` entirely (not in schema)
- `price_at_scan` → `price`
- `volume_at_scan` → `volume`
- `rank_in_scan` → `rank`
- `final_candidate` → `selected_for_trading`

---

### 2. `scan_market()` - Cycle Creation - Line 288-305

**Location**: `services/scanner/scanner-service.py:289-305`

**Issue**: INSERT uses non-existent columns in trading_cycles

```python
# CURRENT CODE (BROKEN):
cycle_id = await conn.fetchval("""
    INSERT INTO trading_cycles (
        cycle_date,        # ❌ DOES NOT EXIST
        cycle_number,      # ❌ DOES NOT EXIST
        started_at,
        status,
        session_mode,      # ❌ SHOULD BE: mode
        triggered_by       # ❌ DOES NOT EXIST
    ) VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING cycle_id
""", ...)
```

**Error Generated**:
```
ERROR: column "cycle_date" of relation "trading_cycles" does not exist
```

**Required Fix**:
- Remove `cycle_date`, `cycle_number`, `triggered_by`
- `session_mode` → `mode`
- Must provide required columns: `max_positions`, `max_daily_loss`, `scan_frequency`, etc.
- Or rely on DEFAULT values for required columns

---

### 3. `scan_market()` - Cycle Update - Line 335-346

**Location**: `services/scanner/scanner-service.py:335-346`

**Issue**: UPDATE uses non-existent columns

```python
# CURRENT CODE (BROKEN):
await state.db_pool.execute("""
    UPDATE trading_cycles
    SET status = 'completed',
        scan_completed_at = $1,      # ❌ DOES NOT EXIST
        candidates_identified = $2   # ❌ DOES NOT EXIST
    WHERE cycle_id = $3
""", ...)
```

**Error Generated**:
```
ERROR: column "scan_completed_at" of relation "trading_cycles" does not exist
```

**Required Fix**:
- `scan_completed_at` → `stopped_at` (or store in `configuration` JSONB)
- `candidates_identified` → store in `configuration` JSONB
- Consider using `status = 'completed'` only

---

### 4. `verify_schema_compatibility()` - Line 190-236

**Location**: `services/scanner/scanner-service.py:218-220`

**Issue**: Checks for wrong column names in scan_results

```python
# CURRENT CODE (INCORRECT CHECK):
required_scan_cols = {
    'scan_id',           # ❌ ACTUAL: id
    'cycle_id',
    'security_id',
    'composite_score',
    'price_at_scan',     # ❌ ACTUAL: price
    'volume_at_scan',    # ❌ ACTUAL: volume
    'rank_in_scan'       # ❌ ACTUAL: rank
}
```

**Impact**: Schema verification will falsely report missing columns even though the database is correct.

**Required Fix**: Update to check for actual column names:
```python
required_scan_cols = {
    'id',              # Primary key
    'cycle_id',
    'security_id',
    'composite_score',
    'price',           # Not price_at_scan
    'volume',          # Not volume_at_scan
    'rank'             # Not rank_in_scan
}
```

---

## Detailed Analysis

### Issue #1: scan_results Column Mismatches

**Actual Database Schema**:
```sql
CREATE TABLE scan_results (
    id                   SERIAL PRIMARY KEY,
    cycle_id             VARCHAR(20) NOT NULL REFERENCES trading_cycles(cycle_id),
    security_id          INTEGER NOT NULL REFERENCES securities(security_id),
    scan_timestamp       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    momentum_score       NUMERIC(5,2) NOT NULL,
    volume_score         NUMERIC(5,2) NOT NULL,
    catalyst_score       NUMERIC(5,2) NOT NULL,
    technical_score      NUMERIC(5,2),
    composite_score      NUMERIC(5,2) NOT NULL,
    price                NUMERIC(10,2) NOT NULL,
    volume               BIGINT NOT NULL,
    rank                 INTEGER,
    selected_for_trading BOOLEAN DEFAULT FALSE,
    scan_metadata        JSONB DEFAULT '{}'::jsonb,
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

**Scanner Code Expectations** (from INSERT statement):
- Expects: `scan_type`, `price_at_scan`, `volume_at_scan`, `rank_in_scan`, `final_candidate`
- Missing from actual DB: All 5 columns don't exist
- Consequence: Every scan will fail when trying to persist results

**Scanner Code Expectations** (from verification):
- Expects: `scan_id` as column name
- Actual: `id` is the column name
- Consequence: Verification incorrectly reports schema mismatch

### Issue #2: trading_cycles Column Mismatches

**Actual Database Schema**:
```sql
CREATE TABLE trading_cycles (
    cycle_id                 VARCHAR(20) PRIMARY KEY,
    mode                     VARCHAR(20) NOT NULL,
    status                   VARCHAR(20) NOT NULL DEFAULT 'active',
    max_positions            INTEGER NOT NULL DEFAULT 5,
    max_daily_loss           NUMERIC(12,2) NOT NULL DEFAULT 2000.00,
    position_size_multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    risk_level               NUMERIC(3,2) NOT NULL DEFAULT 0.02,
    scan_frequency           INTEGER NOT NULL DEFAULT 300,
    started_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    stopped_at               TIMESTAMP WITH TIME ZONE,
    total_risk_budget        NUMERIC(12,2) NOT NULL DEFAULT 2000.00,
    used_risk_budget         NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    current_positions        INTEGER NOT NULL DEFAULT 0,
    current_exposure         NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    configuration            JSONB DEFAULT '{}'::jsonb,
    created_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

**Scanner Code Issues**:

1. **INSERT expects** (line 289-305):
   - `cycle_date` - doesn't exist
   - `cycle_number` - doesn't exist
   - `session_mode` - should be `mode`
   - `triggered_by` - doesn't exist
   - Missing required fields with no defaults

2. **UPDATE expects** (line 335-346):
   - `scan_completed_at` - doesn't exist (could use `stopped_at`)
   - `candidates_identified` - doesn't exist (could use `configuration` JSONB)

### Issue #3: Design Doc vs Actual Schema Divergence

The design document (`database-schema-mcp-v60.md`) describes a **different schema** than what's actually deployed:

**Design Doc says**:
- `trading_cycles.cycle_id` should be UUID
- `trading_cycles.date` (not in actual DB)
- `trading_cycles.cycle_state` (actual uses `status`)
- `trading_cycles.session_mode` (actual uses `mode`)
- `scan_results.scan_id` should be UUID (actual uses `id` SERIAL)
- `scan_results.final_score` (actual uses `composite_score`)
- `scan_results` should have `pattern`, `catalyst_type`, `news_headline`, `support_level`, etc. (not in actual DB)

**Root Cause**: The actual database schema evolved differently from the design document. The scanner service was written against yet another version.

---

## Recommended Fixes

### Priority 1: Fix persist_scan_results() - CRITICAL

**File**: `services/scanner/scanner-service.py`
**Lines**: 583-598

```python
# CORRECTED INSERT STATEMENT:
await state.db_pool.execute("""
    INSERT INTO scan_results (
        cycle_id,
        security_id,
        scan_timestamp,
        momentum_score,
        volume_score,
        catalyst_score,
        technical_score,
        composite_score,
        price,                    # FIXED: was price_at_scan
        volume,                   # FIXED: was volume_at_scan
        rank,                     # FIXED: was rank_in_scan
        selected_for_trading      # FIXED: was final_candidate
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
""",
    cycle_id,
    pick['security_id'],
    scan_timestamp,
    pick.get('momentum_score', 0),
    pick.get('volume_score', 0),
    pick.get('catalyst_score', 0),
    pick.get('technical_score', 0),
    pick.get('composite_score', 0),
    pick.get('price', 0),
    pick.get('volume', 0),
    i,                            # rank
    True                          # selected_for_trading
)
```

**Changes**:
- Removed `scan_type` column (not in schema)
- Renamed `price_at_scan` → `price`
- Renamed `volume_at_scan` → `volume`
- Renamed `rank_in_scan` → `rank`
- Renamed `final_candidate` → `selected_for_trading`
- Adjusted VALUES parameters from 13 to 12

### Priority 2: Fix trading_cycles INSERT - CRITICAL

**File**: `services/scanner/scanner-service.py`
**Lines**: 288-305

**Option A - Minimal Insert (rely on defaults)**:
```python
cycle_id = await conn.fetchval("""
    INSERT INTO trading_cycles (
        cycle_id,
        mode,              # FIXED: was session_mode
        status,
        started_at
    ) VALUES ($1, $2, $3, $4)
    RETURNING cycle_id
""",
    await generate_cycle_id(),  # Generate in format YYYYMMDD-NNN
    'normal',                   # mode (aggressive/normal/conservative)
    'scanning',                 # status
    datetime.utcnow()           # started_at
)
```

**Option B - Full Insert (explicit values)**:
```python
cycle_id = await conn.fetchval("""
    INSERT INTO trading_cycles (
        cycle_id,
        mode,
        status,
        max_positions,
        max_daily_loss,
        scan_frequency,
        started_at,
        configuration
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    RETURNING cycle_id
""",
    await generate_cycle_id(),
    'normal',                    # mode
    'scanning',                  # status
    5,                          # max_positions
    2000.00,                    # max_daily_loss
    300,                        # scan_frequency (5 minutes)
    datetime.utcnow(),          # started_at
    json.dumps({                # configuration (store metadata here)
        'triggered_by': 'scanner_service',
        'cycle_date': datetime.utcnow().date().isoformat()
    })
)
```

### Priority 3: Fix trading_cycles UPDATE - HIGH

**File**: `services/scanner/scanner-service.py`
**Lines**: 335-346

```python
# CORRECTED UPDATE STATEMENT:
await state.db_pool.execute("""
    UPDATE trading_cycles
    SET status = 'completed',
        stopped_at = $1,                           # FIXED: was scan_completed_at
        configuration = configuration || $2,       # Merge in candidates count
        updated_at = NOW()
    WHERE cycle_id = $3
""",
    datetime.utcnow(),                             # stopped_at
    json.dumps({                                   # Add to configuration JSONB
        'scan_completed_at': datetime.utcnow().isoformat(),
        'candidates_identified': candidates_found
    }),
    cycle_id
)
```

**Alternative - Status Only**:
```python
# Simpler approach if you don't need to track completion time
await state.db_pool.execute("""
    UPDATE trading_cycles
    SET status = 'completed',
        updated_at = NOW()
    WHERE cycle_id = $3
""", cycle_id)
```

### Priority 4: Fix Schema Verification - MEDIUM

**File**: `services/scanner/scanner-service.py`
**Lines**: 218-220

```python
# CORRECTED VERIFICATION:
scan_cols = {row['column_name'] for row in scan_results_cols}
required_scan_cols = {
    'id',              # FIXED: was scan_id
    'cycle_id',
    'security_id',
    'composite_score',
    'price',           # FIXED: was price_at_scan
    'volume',          # FIXED: was volume_at_scan
    'rank'             # FIXED: was rank_in_scan
}
```

### Priority 5: Update generate_cycle_id() - LOW

**File**: `services/scanner/scanner-service.py`
**Lines**: 261-271

The function is correct but note that `cycle_id` in the actual DB is VARCHAR(20), not auto-generated UUID. The format YYYYMMDD-NNN should work fine.

---

## Testing Checklist

After applying fixes, verify:

### Unit Tests
- [ ] `persist_scan_results()` successfully inserts data
- [ ] `scan_market()` creates trading_cycle without errors
- [ ] `scan_market()` updates trading_cycle status to 'completed'
- [ ] `verify_schema_compatibility()` passes without false positives

### Integration Tests
- [ ] Full scan completes end-to-end
- [ ] Scan results visible in database
- [ ] Trading cycle has correct status progression
- [ ] No database errors in logs

### Database Verification Queries

```sql
-- Check scan results were inserted
SELECT
    id, cycle_id,
    s.symbol,
    composite_score,
    price,
    volume,
    rank,
    selected_for_trading,
    scan_timestamp
FROM scan_results sr
JOIN securities s ON s.security_id = sr.security_id
ORDER BY scan_timestamp DESC
LIMIT 10;

-- Check trading cycle was created and updated
SELECT
    cycle_id,
    mode,
    status,
    started_at,
    stopped_at,
    configuration
FROM trading_cycles
ORDER BY started_at DESC
LIMIT 5;

-- Verify no orphaned data
SELECT COUNT(*)
FROM scan_results sr
LEFT JOIN trading_cycles tc ON tc.cycle_id = sr.cycle_id
WHERE tc.cycle_id IS NULL;
-- Should return 0
```

### Manual Testing Steps

1. **Start scanner service**:
   ```bash
   cd /root/catalyst-trading-system/services/scanner
   python3 scanner-service.py
   ```

2. **Trigger scan via API**:
   ```bash
   curl -X POST http://localhost:5001/api/v1/scan
   ```

3. **Check logs for errors**:
   ```bash
   # Should see no "column does not exist" errors
   ```

4. **Verify results**:
   ```bash
   curl http://localhost:5001/api/v1/candidates | jq
   ```

---

## Additional Considerations

### 1. Design Document Update Needed

The design document (`Documentation/Design/database-schema-mcp-v60.md`) should be updated to match the actual deployed schema, or vice versa. There's significant divergence.

**Recommendation**: Create a schema migration script to align actual DB with design doc, OR update design doc to reflect actual implementation.

### 2. Schema Version Control

**Problem**: No single source of truth for schema version.

**Recommendation**:
- Maintain actual DDL scripts in `database/migrations/` folder
- Use migration tool (Alembic, Flyway, or custom)
- Tag schema versions explicitly
- Include schema validation in CI/CD

### 3. Code Generation Opportunity

**Observation**: Many column name mismatches could be caught earlier with:
- ORM models (SQLAlchemy, etc.)
- Code-generated models from actual schema
- Type-safe database libraries

**Recommendation**: Consider using Pydantic models that match exact DB schema.

### 4. Missing Columns from Design

The design doc mentions many columns that would be useful but don't exist:

**scan_results**:
- `pattern` - chart pattern name
- `catalyst_type` - type of news catalyst
- `news_headline` - associated news
- `support_level`, `resistance_level` - key price levels
- `suggested_entry`, `suggested_stop`, `suggested_target` - trade levels

**Recommendation**: If these are needed, create migration to add them. Otherwise, use `scan_metadata` JSONB field.

---

## Summary

**Total Issues Found**: 4 critical areas
**Estimated Fix Time**: 1-2 hours
**Risk Level**: HIGH (service is non-functional without fixes)
**Testing Required**: Full integration testing after fixes

**Next Steps**:
1. Apply Priority 1-3 fixes immediately
2. Test with manual scan trigger
3. Verify database writes successful
4. Update design documentation
5. Implement schema version control

---

## Appendix: Full Column Comparison

### scan_results - Three-Way Comparison

| Actual DB | Scanner Code INSERT | Design Doc v6.0 | Notes |
|-----------|-------------------|-----------------|-------|
| `id` | - | `scan_id` (UUID) | Scanner doesn't specify PK |
| `cycle_id` | `cycle_id` ✅ | `cycle_id` (UUID) | Type mismatch: VARCHAR vs UUID |
| `security_id` | `security_id` ✅ | `security_id` ✅ | ✅ |
| `scan_timestamp` | `scan_timestamp` ✅ | `scan_timestamp` ✅ | ✅ |
| `momentum_score` | `momentum_score` ✅ | - | Not in design |
| `volume_score` | `volume_score` ✅ | - | Not in design |
| `catalyst_score` | `catalyst_score` ✅ | `catalyst_score` ✅ | ✅ |
| `technical_score` | `technical_score` ✅ | `technical_score` ✅ | ✅ |
| `composite_score` | `composite_score` ✅ | `final_score` | Name differs |
| `price` | `price_at_scan` ❌ | `price` ✅ | Scanner wrong |
| `volume` | `volume_at_scan` ❌ | `volume` ✅ | Scanner wrong |
| `rank` | `rank_in_scan` ❌ | `rank` ✅ | Scanner wrong |
| `selected_for_trading` | `final_candidate` ❌ | - | Scanner wrong name |
| `scan_metadata` | - | `metadata` | Scanner doesn't set |
| `created_at` | - | `created_at` ✅ | Auto-populated |
| - | `scan_type` ❌ | - | Scanner column doesn't exist |
| - | - | `pattern` | Design only |
| - | - | `catalyst_type` | Design only |
| - | - | `news_headline` | Design only |
| - | - | `support_level` | Design only |
| - | - | `resistance_level` | Design only |
| - | - | `suggested_entry` | Design only |
| - | - | `suggested_stop` | Design only |
| - | - | `suggested_target` | Design only |

### trading_cycles - Three-Way Comparison

| Actual DB | Scanner Code INSERT | Design Doc v6.0 | Notes |
|-----------|-------------------|-----------------|-------|
| `cycle_id` | - | `cycle_id` (UUID) | Scanner generates separately |
| `mode` | `session_mode` ❌ | `session_mode` | Scanner uses wrong name |
| `status` | `status` ✅ | `cycle_state` | Design uses different name |
| `max_positions` | - | - | Not in scanner or design |
| `max_daily_loss` | - | - | Not in scanner or design |
| `position_size_multiplier` | - | - | Not in scanner or design |
| `risk_level` | - | - | Not in scanner or design |
| `scan_frequency` | - | - | Not in scanner or design |
| `started_at` | `started_at` ✅ | `started_at` ✅ | ✅ |
| `stopped_at` | - | `completed_at` | Different names |
| `total_risk_budget` | - | - | Not in scanner or design |
| `used_risk_budget` | - | - | Not in scanner or design |
| `current_positions` | - | - | Not in scanner or design |
| `current_exposure` | - | - | Not in scanner or design |
| `configuration` | - | - | JSONB field for extras |
| `created_at` | - | `created_at` ✅ | Auto-populated |
| `updated_at` | - | `updated_at` ✅ | Auto-populated |
| - | `cycle_date` ❌ | `date` | Scanner column doesn't exist |
| - | `cycle_number` ❌ | - | Scanner column doesn't exist |
| - | `triggered_by` ❌ | - | Scanner column doesn't exist |
| - | - | `phase` | Design only |
| - | - | `daily_pnl` | Design only |
| - | - | `daily_pnl_pct` | Design only |
| - | - | `trades_executed` | Design only |
| - | - | `trades_won` | Design only |
| - | - | `trades_lost` | Design only |

---

**End of Analysis**

*Generated: 2025-11-22*
*Analyzer: Claude Code*
*Service Version: scanner-service.py v6.0.0*
*Database: PostgreSQL (production)*
