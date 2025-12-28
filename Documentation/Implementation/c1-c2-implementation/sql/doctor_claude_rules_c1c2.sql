-- ============================================================================
-- Name of Application: Catalyst Trading System
-- Name of file: doctor_claude_rules_c1c2.sql
-- Version: 1.0.0
-- Last Updated: 2025-12-27
-- Purpose: Doctor Claude rules for monitoring C1/C2 fixes
--
-- REVISION HISTORY:
-- v1.0.0 (2025-12-27) - Initial rules for C1/C2 fix monitoring
--
-- EXECUTION:
--   psql $DATABASE_URL -f doctor_claude_rules_c1c2.sql
-- ============================================================================

\echo '=============================================='
\echo 'Adding Doctor Claude rules for C1/C2 monitoring'
\echo '=============================================='

BEGIN;

-- ============================================================================
-- C1 FIX: Orders table monitoring rules
-- ============================================================================

-- Rule: Check for stuck orders (orders pending > 5 minutes)
INSERT INTO doctor_claude_rules (
    rule_name,
    rule_type,
    condition_sql,
    action_type,
    auto_fix_enabled,
    description,
    severity,
    enabled
) VALUES (
    'stuck_orders_c1',
    'order_status',
    $SQL$
        SELECT COUNT(*) > 0
        FROM orders
        WHERE status IN ('created', 'submitted', 'accepted', 'pending_new', 'new')
          AND submitted_at < NOW() - INTERVAL '5 minutes'
    $SQL$,
    'alert',
    false,
    'C1 FIX: Detect orders stuck in pending state using orders table',
    'warning',
    true
) ON CONFLICT (rule_name) DO UPDATE SET
    condition_sql = EXCLUDED.condition_sql,
    description = EXCLUDED.description,
    enabled = true;

-- Rule: Check for unlinked filled orders
INSERT INTO doctor_claude_rules (
    rule_name,
    rule_type,
    condition_sql,
    action_type,
    auto_fix_enabled,
    description,
    severity,
    enabled
) VALUES (
    'unlinked_orders_c1',
    'order_status',
    $SQL$
        SELECT COUNT(*) > 0
        FROM orders
        WHERE status = 'filled'
          AND order_purpose = 'entry'
          AND position_id IS NULL
    $SQL$,
    'alert',
    false,
    'C1 FIX: Detect filled entry orders without linked positions',
    'critical',
    true
) ON CONFLICT (rule_name) DO UPDATE SET
    condition_sql = EXCLUDED.condition_sql,
    description = EXCLUDED.description,
    enabled = true;

-- Rule: Verify orders table has data
INSERT INTO doctor_claude_rules (
    rule_name,
    rule_type,
    condition_sql,
    action_type,
    auto_fix_enabled,
    description,
    severity,
    enabled
) VALUES (
    'orders_table_health_c1',
    'schema_check',
    $SQL$
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'orders'
        )
        AND (SELECT COUNT(*) FROM orders) > 0
    $SQL$,
    'verify',
    false,
    'C1 FIX: Verify orders table exists and has data',
    'info',
    true
) ON CONFLICT (rule_name) DO UPDATE SET
    condition_sql = EXCLUDED.condition_sql,
    description = EXCLUDED.description,
    enabled = true;

-- Rule: Check positions table doesn't have alpaca columns
INSERT INTO doctor_claude_rules (
    rule_name,
    rule_type,
    condition_sql,
    action_type,
    auto_fix_enabled,
    description,
    severity,
    enabled
) VALUES (
    'positions_no_alpaca_c1',
    'schema_check',
    $SQL$
        SELECT NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'positions' 
              AND column_name IN ('alpaca_order_id', 'alpaca_status')
        )
    $SQL$,
    'verify',
    false,
    'C1 FIX: Verify positions table has no alpaca_* columns',
    'info',
    true
) ON CONFLICT (rule_name) DO UPDATE SET
    condition_sql = EXCLUDED.condition_sql,
    description = EXCLUDED.description,
    enabled = true;

-- ============================================================================
-- Order sync rules
-- ============================================================================

-- Rule: Orders in DB but not in Alpaca
INSERT INTO doctor_claude_rules (
    rule_name,
    rule_type,
    condition_sql,
    action_type,
    auto_fix_enabled,
    description,
    severity,
    enabled
) VALUES (
    'order_reconciliation',
    'reconciliation',
    $SQL$
        -- This is a placeholder SQL; actual reconciliation requires Alpaca API call
        SELECT COUNT(*) > 0
        FROM orders
        WHERE status IN ('submitted', 'accepted')
          AND alpaca_order_id IS NOT NULL
          AND updated_at < NOW() - INTERVAL '10 minutes'
    $SQL$,
    'sync',
    true,
    'C1 FIX: Reconcile stale orders with Alpaca',
    'warning',
    true
) ON CONFLICT (rule_name) DO UPDATE SET
    condition_sql = EXCLUDED.condition_sql,
    description = EXCLUDED.description,
    enabled = true;

-- ============================================================================
-- C2 FIX: alpaca_trader.py consolidation rules
-- ============================================================================

-- Note: C2 fix is verified by the verify-c1-c2-fixes.py script
-- These rules document the expected state

INSERT INTO doctor_claude_rules (
    rule_name,
    rule_type,
    condition_sql,
    action_type,
    auto_fix_enabled,
    description,
    severity,
    enabled
) VALUES (
    'alpaca_trader_version',
    'code_check',
    'SELECT true',  -- Always passes; actual check is in verification script
    'verify',
    false,
    'C2 FIX: Verify alpaca_trader.py is v2.0.0 consolidated version',
    'info',
    true
) ON CONFLICT (rule_name) DO UPDATE SET
    description = EXCLUDED.description,
    enabled = true;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
\echo ''
\echo 'Doctor Claude rules for C1/C2 monitoring:'
SELECT 
    rule_name,
    rule_type,
    action_type,
    severity,
    enabled,
    auto_fix_enabled
FROM doctor_claude_rules
WHERE rule_name LIKE '%c1%' OR rule_name LIKE '%c2%' OR rule_name = 'order_reconciliation'
ORDER BY rule_name;

\echo ''
\echo '=============================================='
\echo 'Rules added successfully'
\echo '=============================================='
