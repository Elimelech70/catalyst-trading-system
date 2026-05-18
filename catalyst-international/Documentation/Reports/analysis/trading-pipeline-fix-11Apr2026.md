# Trading Pipeline Analysis & Fix — 11 April 2026

**Date:** 2026-04-11
**Author:** Craig + Claude
**System:** Catalyst Trading System International (HKEX)
**Architecture:** Multi-Agent MCP v2.3 (6-layer cycle + cerebellum)

---

## Executive Summary

Investigation into why daily trading reports showed "0 new orders" for multiple days revealed that the system **was actually trading successfully** — the reporting was broken, not the trading. However, several real issues were found that capped trading volume and forced premature position exits. Five fixes were applied and deployed.

---

## Investigation Findings

### Initial Symptom

Daily trading reports (April 8-10) all showed:
- New Orders: 0
- Skipped: 0
- Exits: 0

This suggested the system was completely idle despite running 12 brain cycles per day.

### Actual Reality (from Docker logs)

The coordinator was functioning well:

| Date | Brain Cycles | Trades Executed | Notes |
|------|-------------|-----------------|-------|
| Apr 8 | 3 | 3 | Architecture v2.3 just deployed (afternoon only) |
| Apr 9 | 11 | 0 | All candidates passed — market conditions weak |
| Apr 10 | 11 | **10** | Active morning, blocked afternoon |

**April 10 detail:**
- 09:31 cycle: 2 trades (9988, 1299)
- 10:01 cycle: 3 trades (3690, 1810, 1024)
- 10:31 cycle: 4+ trades (9988, 3690, 1024, 2382, 2015, 2333)
- 11:02 cycle: 0 trades (market scan, nothing qualifying)
- 11:32 cycle: 1 trade
- 13:00+ cycles: **ALL blocked** — "Daily trade limit reached (10/10)"

### What Was Working

- 6-layer brain cycle: all layers executing correctly
- MCP connections: all 3 servers healthy (market-scanner, trade-executor, position-monitor)
- Survival Pulse: scoring 3/3 every cycle
- Cerebellum: CandleModel loading from ONNX, neural signals integrated
- Discipline Gate: detecting idle days, firing ALARM/WARNING appropriately
- Market hours detection: correctly opening/closing with HKEX schedule + holidays
- Tool routing: all 15 tools available and working via MCP

---

## Issues Found

### Issue 1: Daily Trade Limit Too Low (CRITICAL)

**File:** `safety.py:43`
**Setting:** `max_daily_trades: int = 10`

**Impact:** After 10 morning trades, `check_risk` returned `approved=false` with reason "Daily trade limit reached (10/10)" for ALL afternoon candidates. The system runs 11 cycles per day across morning (09:30-12:00) and afternoon (13:00-16:00) sessions. With an aggressive morning, the entire afternoon was dead.

**Evidence from logs:**
```
2026-04-10 14:03:06 Tool: log_decision({"decision": "skip", "symbol": "1398",
  "reasoning": "Daily trade limit reached (10/10). Cannot execute..."})
```

### Issue 2: Minimum Risk/Reward Ratio Mismatch (HIGH)

**File:** `safety.py:44`
**Setting:** `min_risk_reward: float = 2.0`

**Impact:** The system prompt defines three tiers with different R:R requirements:
- Tier 1: R:R >= 2.0:1
- Tier 2: R:R >= 1.5:1
- Tier 3: R:R >= 1.2:1

But `safety.py` hard-coded a 2.0 minimum, silently rejecting valid Tier 2 and Tier 3 trades that Claude's decision engine had already approved. This created a contradiction where Claude would identify a Tier 3 learning trade, call `check_risk`, get rejected, and log "BLOCKED BY SYSTEM".

### Issue 3: Position Monitor Force-Closes All at 15:50 (HIGH)

**File:** `agents/position-monitor/monitor.py:136-139`
**Code:**
```python
if time(15, 50) <= ct < time(16, 0):
    signals.append("near_close:strong")
    immediate_exit = True  # <-- Forces EXIT for ALL positions
    strongest = strongest or "Market closing soon"
```

**Impact:** Every day between 15:50-16:00, the position monitor issued EXIT recommendations for ALL open positions regardless of conviction, P&L, or strategy. The coordinator dutifully closed everything:
```
2026-04-10 15:52:49 Processing 2 exit recommendations
  1299: EXIT - Market closing soon
  Closed 1299: quantity=200, fill_price=88.9
  9988: EXIT - Market closing soon
  Closed 9988: quantity=200, fill_price=125.5
```

This meant:
- No overnight positions possible
- Unrealized losses locked in daily
- Winners cut short regardless of momentum
- System bought positions in the morning, then closed them ALL 6 hours later

### Issue 4: log_decision FK Constraint Failure (HIGH)

**File:** `agents/trade-executor/mcp_server.py:626-638`

**Root cause chain:**
1. Coordinator calls `log_decision` tool via MCP
2. Trade-executor generates `cycle_id = f"mcp_{timestamp}"`
3. Inserts into `agent_decisions` table with this `cycle_id`
4. `agent_decisions.cycle_id` has FK constraint → `agent_cycles(cycle_id)`
5. No row exists in `agent_cycles` for this cycle_id
6. **FK violation → INSERT fails silently**
7. All decisions lost from database
8. Report generator queries `agent_decisions` → finds 0 rows → reports "0 orders"

This is why the reports showed zero activity despite 10+ real trades.

### Issue 5: SQL Syntax Error in UPDATE (MEDIUM)

**File:** `agents/trade-executor/mcp_server.py:452-455`
**Code:**
```sql
UPDATE positions SET exit_type = %s
WHERE symbol = %s AND status = 'closed' AND exit_type IS NULL
ORDER BY exit_time DESC LIMIT 1
```

**Impact:** PostgreSQL does not support `ORDER BY` in `UPDATE` statements. Every position close logged:
```
WARNING: Failed to record exit_type for 1299: syntax error at or near "ORDER"
```

This broke the cerebellum's feedback loop — exit types (AI_PATTERN, STOP_LOSS, etc.) were never recorded, preventing the neural model from learning which exit strategies work.

---

## Fixes Applied

### Fix 1: Increase Daily Trade Limit

**File:** `safety.py:43`
```python
# Before
max_daily_trades: int = 10

# After
max_daily_trades: int = 25
```

**Rationale:** 25 allows full activity across both sessions (morning + afternoon) while still providing a safety cap against runaway trading.

### Fix 2: Lower Minimum Risk/Reward Ratio

**File:** `safety.py:44`
```python
# Before
min_risk_reward: float = 2.0

# After
min_risk_reward: float = 1.2
```

**Rationale:** Aligns safety.py with the system prompt's Tier 3 criteria (R:R >= 1.2:1). The decision engine already filters by tier-appropriate R:R; the safety layer should be a floor, not override Claude's tier selection.

### Fix 3: Position Monitor — Consult Instead of Force-Close

**File:** `agents/position-monitor/monitor.py:136-139`
```python
# Before
if time(15, 50) <= ct < time(16, 0):
    signals.append("near_close:strong")
    immediate_exit = True
    strongest = strongest or "Market closing soon"

# After
if time(15, 50) <= ct < time(16, 0):
    signals.append("near_close:moderate")
    consult_ai = True
    strongest = strongest or "Market closing soon — coordinator decides"
```

**Rationale:** The coordinator (brain) should decide which positions to close at EOD based on conviction, P&L, and strategy — not have the position monitor (reflex) force-close everything. Positions with strong momentum or overnight catalysts can now be held.

### Fix 4: Create Agent Cycle Before Logging Decision

**File:** `agents/trade-executor/mcp_server.py:626-641`
```python
# Before
def _handle_log_decision(args: dict) -> dict:
    db = _get_db()
    cycle_id = f"mcp_{...}"
    decision_id = db.log_decision(cycle_id=cycle_id, ...)  # FK violation!

# After
def _handle_log_decision(args: dict) -> dict:
    db = _get_db()
    cycle_id = f"mcp_{...}"
    try:
        db.start_agent_cycle(cycle_id=cycle_id)  # Create cycle first
    except Exception:
        pass  # May already exist from same second
    decision_id = db.log_decision(cycle_id=cycle_id, ...)  # FK satisfied
```

**Rationale:** The FK constraint exists for data integrity. Rather than dropping it, we ensure the parent row exists before inserting the child.

### Fix 5: Fix SQL UPDATE Syntax

**File:** `agents/trade-executor/mcp_server.py:452-457`
```sql
-- Before (invalid PostgreSQL)
UPDATE positions SET exit_type = %s
WHERE symbol = %s AND status = 'closed' AND exit_type IS NULL
ORDER BY exit_time DESC LIMIT 1

-- After (valid PostgreSQL)
UPDATE positions SET exit_type = %s
WHERE position_id = (
  SELECT position_id FROM positions
  WHERE symbol = %s AND status = 'closed' AND exit_type IS NULL
  ORDER BY exit_time DESC LIMIT 1
)
```

### Fix 6: Report Generator — Orders Table Fallback

**File:** `scripts/generate_daily_report.py:248-280`

Added fallback logic: when `agent_decisions` returns no rows, query the `orders` table directly to count buys (new orders) and sells (exits). This ensures reports reflect reality even if decision logging has issues.

---

## Deployment

All three Docker services were rebuilt and restarted:
```bash
docker compose build --no-cache trade-executor position-monitor coordinator
docker compose up -d trade-executor position-monitor coordinator
```

Post-deployment verification:
- All MCP connections established
- All 15 tools registered
- Initial position sync successful
- Safety validator confirms: `max_daily_trades=25, min_risk_reward=1.2`

---

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Max trades per day | 10 (morning only) | 25 (full day) |
| Afternoon trading | Blocked after morning | Active |
| Min R:R for approval | 2.0:1 (Tier 1 only) | 1.2:1 (all tiers) |
| EOD position handling | Force-close ALL at 15:50 | Coordinator decides per-position |
| Decision logging | FK failure, 0 recorded | Working, all decisions saved |
| Exit type feedback | SQL error, never recorded | Working, cerebellum learns |
| Daily report accuracy | Shows 0 orders always | Shows actual trade count |

---

## Files Modified

| File | Change |
|------|--------|
| `safety.py` | max_daily_trades 10→25, min_risk_reward 2.0→1.2 |
| `agents/position-monitor/monitor.py` | near_close: immediate_exit → consult_ai |
| `agents/trade-executor/mcp_server.py` | FK fix in log_decision, SQL fix in exit_type UPDATE |
| `scripts/generate_daily_report.py` | Added orders table fallback for report counting |

---

## Next Trading Session

Monday 2026-04-14, 09:30 HKT. Monitor:
- `docker logs catalyst-coordinator` — verify full-day trading
- Afternoon cycles should now execute trades (not "Daily trade limit reached")
- EOD positions should get CONSULT_AI not forced EXIT
- `agent_decisions` table should have records
- Daily report should show accurate order counts
