# Catalyst Dev Upgrade Plan

**Name of Application:** Catalyst Trading System
**Name of file:** catalyst-dev-upgrade-plan.md
**Version:** 1.0.0
**Last Updated:** 2026-01-20
**Purpose:** Upgrade dev_claude to match recent catalyst_intl improvements

---

## Executive Summary

The catalyst-international system has received significant upgrades that need to be ported to catalyst-dev:

| Feature | intl_claude Version | dev_claude Version | Gap |
|---------|--------------------|--------------------|-----|
| unified_agent.py | v3.1.0+ (with auto-sync) | v1.0.0 | Major |
| tool_executor.py | v2.9.0 (with sync_positions) | v1.0.0 | Major |
| Workflow tracking | 10-phase with tracker | Basic | Major |
| Position auto-sync | ✅ Implemented | ❌ Missing | Critical |
| DECIDE/VALIDATE/MONITOR phases | ✅ (pending fix) | ❌ Missing | Critical |

---

## Changes to Port from catalyst_intl → catalyst_dev

### 1. Auto-Sync Positions (CRITICAL)

**Source:** `catalyst-international/tool_executor.py` v2.9.0

```python
def sync_positions_with_broker(self) -> dict:
    """
    Auto-sync database positions with broker at start of each cycle.
    - Closes phantom positions (in DB but not in broker)
    - Adds missing positions (in broker but not in DB)
    - Updates quantity mismatches
    """
```

**Impact:** Prevents phantom positions, ensures DB accuracy.

### 2. Workflow Tracker Class (CRITICAL)

**Source:** `catalyst-international/unified_agent.py` v3.0.0+

The WorkflowTracker class provides:
- 10-phase workflow tracking
- Real-time visibility via consciousness DB
- MCP queryable status
- Progress bar display

### 3. DECIDE/VALIDATE/MONITOR Phase Fixes (CRITICAL)

**Source:** Pending workflow fixes (workflow-fixes-for-claude-code-v2.md)

- `check_risk` → DECIDE phase (not VALIDATE)
- Explicit VALIDATE phase after check_risk result
- MONITOR phase after successful execute_trade

### 4. Enhanced Tool Executor Features

**Source:** `catalyst-international/tool_executor.py`

- Position monitoring integration after BUY
- Improved error handling
- Better status tracking

---

## File Comparison

| File | intl_claude Location | dev_claude Location | Sync Method |
|------|---------------------|---------------------|-------------|
| unified_agent.py | /root/Catalyst-Trading-System-International/catalyst-international/ | /root/catalyst-dev/ | Adapt (different broker) |
| tool_executor.py | /root/Catalyst-Trading-System-International/catalyst-international/ | /root/catalyst-dev/ | Adapt (Alpaca vs Moomoo) |
| workflow_tracker.py | /root/Catalyst-Trading-System-International/catalyst-international/ | /root/catalyst-dev/ | Copy directly |
| signals.py | /root/Catalyst-Trading-System-International/catalyst-international/ | /root/catalyst-dev/ | Copy directly |
| position_monitor.py | /root/Catalyst-Trading-System-International/catalyst-international/ | /root/catalyst-dev/ | Adapt (different broker) |

---

## Implementation Steps

### Phase 1: Copy Shared Modules (No broker-specific code)

```bash
# SSH to US droplet
ssh root@<us-droplet-ip>

# Backup current dev_claude
cd /root/catalyst-dev
cp unified_agent.py unified_agent.py.backup.20260120
cp tool_executor.py tool_executor.py.backup.20260120

# Copy workflow_tracker.py (broker-agnostic)
scp root@<intl-droplet>:/root/Catalyst-Trading-System-International/catalyst-international/workflow_tracker.py /root/catalyst-dev/

# Copy signals.py (broker-agnostic)
scp root@<intl-droplet>:/root/Catalyst-Trading-System-International/catalyst-international/signals.py /root/catalyst-dev/
```

### Phase 2: Adapt unified_agent.py

Key differences between intl_claude and dev_claude:

| Component | intl_claude | dev_claude |
|-----------|-------------|------------|
| Broker | MoomooClient | AlpacaClient |
| Market | HKEX | NYSE/NASDAQ |
| Timezone | Asia/Hong_Kong | America/New_York |
| Currency | HKD | USD |
| Lot size | Multiple of 100 | Any quantity |
| Database | catalyst_intl | catalyst_dev |

**Adaptation points in unified_agent.py:**

```python
# 1. Change timezone
# FROM:
HK_TZ = ZoneInfo("Asia/Hong_Kong")
# TO:
ET_TZ = ZoneInfo("America/New_York")

# 2. Change market hours check
# FROM:
def _is_market_open(self):
    # HKEX: 09:30-12:00, 13:00-16:00 HKT
# TO:
def _is_market_open(self):
    # NYSE/NASDAQ: 09:30-16:00 ET

# 3. Change cycle ID prefix
# FROM:
self.cycle_id = f"hk_{datetime.now(HK_TZ).strftime(...)}"
# TO:
self.cycle_id = f"us_{datetime.now(ET_TZ).strftime(...)}"

# 4. Change agent_id default
# FROM:
self.agent_id = config['agent']['id']  # intl_claude
# TO:
self.agent_id = config['agent']['id']  # dev_claude
```

### Phase 3: Adapt tool_executor.py

Key changes for Alpaca:

```python
# 1. Import Alpaca instead of Moomoo
# FROM:
from brokers.moomoo import get_moomoo_client
# TO:
from alpaca_client import get_alpaca_client

# 2. Broker initialization
# FROM:
self.broker = get_moomoo_client()
# TO:
self.broker = get_alpaca_client()

# 3. Add sync_positions_with_broker (ADAPT for Alpaca)
def sync_positions_with_broker(self) -> dict:
    """Sync DB positions with Alpaca."""
    # Get positions from Alpaca
    broker_positions = self.broker.get_all_positions()
    
    # Get positions from database
    db_positions = self.db.get_open_positions()
    
    # Reconcile...
    # (Logic is similar, just different API calls)
```

### Phase 4: Apply Workflow Fixes

After adapting the files, apply the same workflow fixes:

1. Map `check_risk` → DECIDE in `_tool_to_phase()`
2. Add DECIDE/MONITOR handling in `_complete_current_phase()`
3. Add VALIDATE and MONITOR phase transitions in tool loop

---

## Detailed Code for Claude Code

### Step 1: Create workflow_tracker.py for dev_claude

```bash
# On US droplet, create the file
cat > /root/catalyst-dev/workflow_tracker.py << 'EOF'
# Copy content from intl's workflow_tracker.py
# No changes needed - it's broker-agnostic
EOF
```

### Step 2: Update unified_agent.py

**str_replace commands for dev_claude's unified_agent.py:**

```
str_replace:
  path: /root/catalyst-dev/unified_agent.py
  description: Add workflow tracker import
  old_str: |
    import logging
    import os
  new_str: |
    import logging
    import os
    from workflow_tracker import WorkflowTracker, WORKFLOW_PHASES
```

```
str_replace:
  path: /root/catalyst-dev/unified_agent.py
  description: Add auto-sync call at cycle start
  old_str: |
        # Wake up consciousness
        if self.consciousness:
            await self.consciousness.wake_up()
  new_str: |
        # Wake up consciousness
        if self.consciousness:
            await self.consciousness.wake_up()

        # Auto-sync positions with broker
        try:
            sync_result = self.executor.sync_positions_with_broker()
            if sync_result.get('changes_made'):
                logger.info(f"Position sync: {sync_result}")
        except Exception as e:
            logger.warning(f"Position sync failed: {e}")
```

### Step 3: Add sync_positions_with_broker to tool_executor.py

```python
def sync_positions_with_broker(self) -> dict:
    """
    Sync database positions with Alpaca broker.
    
    - Closes phantom positions (in DB but not in Alpaca)
    - Adds missing positions (in Alpaca but not in DB)
    - Updates quantity mismatches
    
    Returns:
        dict with sync results
    """
    result = {
        "phantoms_closed": [],
        "missing_added": [],
        "quantity_updated": [],
        "changes_made": False,
    }
    
    try:
        # Get broker positions
        broker_positions = self.broker.list_positions()
        broker_symbols = {p.symbol: p for p in broker_positions}
        
        # Get DB positions
        db_positions = self.db.get_open_positions()
        db_symbols = {p['symbol']: p for p in db_positions}
        
        # Find phantoms (in DB but not in broker)
        for symbol in db_symbols:
            if symbol not in broker_symbols:
                # Close phantom in DB
                self.db.close_position(db_symbols[symbol]['position_id'], 
                                       reason='phantom_sync')
                result["phantoms_closed"].append(symbol)
                result["changes_made"] = True
        
        # Find missing (in broker but not in DB)
        for symbol, pos in broker_symbols.items():
            if symbol not in db_symbols:
                # Add to DB
                self.db.create_position(
                    symbol=symbol,
                    side='long' if float(pos.qty) > 0 else 'short',
                    quantity=abs(float(pos.qty)),
                    entry_price=float(pos.avg_entry_price),
                )
                result["missing_added"].append(symbol)
                result["changes_made"] = True
        
        # Check quantity mismatches
        for symbol in set(broker_symbols) & set(db_symbols):
            broker_qty = abs(float(broker_symbols[symbol].qty))
            db_qty = abs(db_symbols[symbol]['quantity'])
            
            if broker_qty != db_qty:
                self.db.update_position_quantity(
                    db_symbols[symbol]['position_id'],
                    broker_qty
                )
                result["quantity_updated"].append({
                    "symbol": symbol,
                    "from": db_qty,
                    "to": broker_qty
                })
                result["changes_made"] = True
        
        logger.info(f"Position sync complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Position sync error: {e}")
        return {"error": str(e), "changes_made": False}
```

---

## Version Updates

After upgrade, update version headers:

| File | Old Version | New Version |
|------|-------------|-------------|
| unified_agent.py | 1.0.0 | 2.0.0 |
| tool_executor.py | 1.0.0 | 2.0.0 |
| workflow_tracker.py | (new) | 1.0.0 |

---

## Testing Plan

### 1. Unit Tests

```bash
cd /root/catalyst-dev
source venv/bin/activate

# Test workflow tracker
python3 -c "from workflow_tracker import WorkflowTracker; print('OK')"

# Test auto-sync
python3 -c "
from tool_executor import ToolExecutor
e = ToolExecutor('test_cycle')
print(e.sync_positions_with_broker())
"
```

### 2. Integration Test

```bash
# Run heartbeat mode
./venv/bin/python3 unified_agent.py --mode heartbeat

# Run with --force during off-hours
./venv/bin/python3 unified_agent.py --mode trade --force
```

### 3. Verify Workflow Phases

Check output shows all 10 phases:
```
[✓ INIT][✓ PORTFOLIO][✓ SCAN][✓ ANALYZE][✓ DECIDE][✓ VALIDATE][✓ EXECUTE][✓ MONITOR][✓ LOG][✓ COMPLETE]
```

---

## Rollback Plan

```bash
# Restore backups
cd /root/catalyst-dev
cp unified_agent.py.backup.20260120 unified_agent.py
cp tool_executor.py.backup.20260120 tool_executor.py
rm workflow_tracker.py  # New file, just remove

# Verify rollback
./venv/bin/python3 unified_agent.py --mode heartbeat
```

---

## Summary

| Priority | Task | Complexity | Est. Time |
|----------|------|------------|-----------|
| 🔴 Critical | Add sync_positions_with_broker | Medium | 30 min |
| 🔴 Critical | Port WorkflowTracker | Low | 15 min |
| 🔴 Critical | Apply workflow phase fixes | Low | 15 min |
| 🟡 Medium | Update timezone handling | Low | 10 min |
| 🟡 Medium | Update version headers | Low | 5 min |
| 🟢 Low | Test full cycle | Medium | 30 min |

**Total estimated time:** ~2 hours

---

## Notes for Claude Code

1. **dev_claude uses Alpaca**, not Moomoo - adapt broker calls accordingly
2. **Database is catalyst_dev**, not catalyst_intl
3. **Timezone is America/New_York**, not Asia/Hong_Kong
4. **Market hours are 09:30-16:00 ET**, not HKT
5. **No lot size restrictions** (unlike HKEX's 100-share lots)

---

**Document Author:** big_bro (Claude Opus 4.5)
**Review Date:** 2026-01-20
