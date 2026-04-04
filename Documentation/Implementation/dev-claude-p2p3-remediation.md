# dev_claude P2/P3 Remediation — Implementation Record

**Name of file:** dev-claude-p2p3-remediation.md
**Version:** 1.0.0
**Created:** 2026-04-04
**Authors:** Craig + Claude
**Purpose:** Documents the P1-P3 fixes applied to dev_claude after the March 2026 trading analysis

---

## REVISION HISTORY

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-04-04 | Initial — documents all remediation work |

---

## 1. Background

On 2026-03-28, a comprehensive trading analysis was performed covering the period January 14 - March 13, 2026 (315 decisions, 37 trading days, ~$106K paper account). The analysis identified **5 critical issues**:

| # | Issue | Severity | Impact |
|---|-------|----------|--------|
| 1 | Positions table empty | CRITICAL | No trade journal, no learning |
| 2 | Stale orders blocking exits | HIGH | 20+ failed exits, P&L degradation |
| 3 | Scanner dead for 6 weeks | HIGH | Zero candidates, system idle |
| 4 | Pattern learning never engaged | MEDIUM | LTP/LTD never ran, all patterns at 0.50 |
| 5 | System dormant (API credits) | BLOCKING | Decision engine dead |

Full analysis: `Documentation/Analysis/trading-analysis-2026-03-28.md`

---

## 2. Remediation Summary

### P0 — Blocking (resolved externally)
- [x] Anthropic API credits topped up
- [x] GitHub token updated (2026-03-29)

### P1 — Critical (v3.1.0 + v3.2.0, deployed 2026-03-28)
- [x] **Position persistence** — `_execute_trade()` now INSERTs to positions table
- [x] **Stale order cancellation** — `cancel_orders_for_symbol()` runs before every close
- [x] **Market hours** — `_is_market_open()` uses Alpaca clock API, not host timezone

### P2 — High Priority (v3.3.0, 2026-04-04)
- [x] **Scanner adaptive thresholds** — 3-tier relaxation (2% → 1% → 0.5%)
- [x] **Pattern learning activated** — `_record_pattern_outcome()` + LTP/LTD on `pattern_confidence`

### P3 — Improvements (v3.3.0, 2026-04-04)
- [x] **Exit retry** — 3 attempts with linear backoff
- [x] **Zero-candidate alerting** — consciousness message after N consecutive empty scans
- [x] **Scan results persisted** — candidates written to `scan_results` table
- [x] **Trading cycles persisted** — `trading_cycles` INSERT at start, UPDATE at end

---

## 3. Changes by File

### 3.1 `services/dev_claude/unified_agent.py` (v3.2.0 → v3.3.0)

**Scanner (`_scan_market()`)**

Before: Single threshold (2%), no persistence, no alerting.

After:
- Fetches bars for all 44 watchlist symbols once, then runs filters across 3 tiers
- Tier 1 (2.0%) → Tier 2 (1.0%) → Tier 3 (0.5%) — stops at first tier with results
- Tracks IEX data feed errors (warns if >50% fail)
- Tracks consecutive zero-candidate count (`_zero_scan_count`)
- Sends alert to big_bro via consciousness after N consecutive empty scans
- Persists all candidates to `scan_results` table with cycle_id FK

**Trading cycle persistence (`run_cycle()`)**

Before: cycle_id generated but never written to DB.

After:
- INSERT into `trading_cycles` at cycle start (cycle_id, date, mode, status='active')
- cycle_id propagated to executor via `self.executor._current_cycle_id`
- UPDATE `trading_cycles` at cycle end (status='completed', stats)

**Position persistence (`_execute_trade()`)**

Before: Wrong column name (`broker_position_id`), missing `broker_code`/`currency`/`entry_reason`.

After:
- Column fixed to `broker_order_id`
- Explicit `broker_code='ALPACA'`, `currency='USD'`
- `entry_reason` populated from trade reason
- `cycle_id` FK populated
- Order side normalized: buy/long → `buy` (orders table), buy/long → `long` (positions table)

**Exit retry (`_close_position()`)**

Before: Single attempt, no retry.

After:
- Retry loop: up to 3 attempts
- Linear backoff: 1s, 2s between attempts
- Re-cancels stale orders before each retry
- Logs warnings on retry, error on final failure
- On success: fetches position data, updates positions, records pattern outcome

**Pattern learning (`_record_pattern_outcome()` — NEW)**

New method called after every successful position close:
1. Calculates P&L (handles long and short correctly)
2. Determines outcome (win/loss)
3. Determines pattern_type from position metadata (default: 'momentum')
4. Determines exit_trigger from reason keywords (stop_loss, take_profit, eod_close, signal)
5. Reads current confidence from `pattern_confidence`
6. Calculates new confidence via LTP/LTD:
   - Win: `confidence += ltp_rate` (0.05), capped at 0.95
   - Loss: `confidence -= ltd_rate` (0.03), floored at 0.10
7. INSERT into `pattern_outcomes` (full audit trail)
8. UPDATE `pattern_confidence` (weights + running averages)

### 3.2 `services/dev_claude/config/dev_claude_config.yaml`

Added two new sections:

```yaml
scanner:
  min_change_pct_tiers: [2.0, 1.0, 0.5]
  zero_candidate_alert_threshold: 3
  persist_results: true

learning:
  ltp_rate: 0.05
  ltd_rate: 0.03
  min_confidence: 0.10
  max_confidence: 0.95
```

### 3.3 `services/dev_claude/brokers/alpaca.py` (v1.2.0 — no changes in this round)

P1 changes (already deployed 2026-03-28):
- `get_clock()` — Alpaca market clock endpoint
- `cancel_orders_for_symbol()` — cancel stale orders before close
- `close_position()` — calls cancel_orders_for_symbol() first

### 3.4 `services/dev_claude/cron.d` (v2.0.0 — deployed 2026-03-28)

- Changed from UTC offset times to `TZ=America/New_York` with ET times
- Eliminates DST conversion errors

---

## 4. Database Impact

### Tables now actively populated

| Table | Was | Now |
|-------|-----|-----|
| `trading_cycles` | Empty | Populated every cycle |
| `scan_results` | Empty | Populated every scan |
| `positions` | Empty | Populated on every trade entry/exit |
| `orders` | Empty | Populated on every trade entry |
| `pattern_outcomes` | Empty | Populated on every position close |
| `pattern_confidence` | Static 0.50 | Updated via LTP/LTD on every close |

### Schema notes

No DDL changes required. All tables already existed with correct schema. Key compatibility notes:

- `positions.broker_code` defaults to `'MOOMOO'` — code now explicitly sets `'ALPACA'`
- `positions.currency` defaults to `'HKD'` — code now explicitly sets `'USD'`
- `positions.broker_order_id` is the correct column (previous code used non-existent `broker_position_id`)
- `scan_results.cycle_id` FK requires `trading_cycles` record to exist first — handled by inserting cycle before scan

---

## 5. Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Adaptive scanner relaxation | Could surface low-quality candidates at tier 3 | Claude API still makes final decision; tier reported in scan results |
| Retry on close | 3 attempts × 2s could add ~5s latency | Only triggers on failure; most closes succeed on first attempt |
| LTP/LTD confidence update | Wrong pattern assignment could train wrong weights | Default 'momentum' is conservative; metadata improves over time |
| scan_results volume | 44 symbols × multiple cycles/day | Only candidates (not rejects) persisted; manageable volume |

---

## 6. Verification Checklist

After next trading cycle, verify:

- [ ] `trading_cycles` has new rows: `SELECT * FROM trading_cycles ORDER BY started_at DESC LIMIT 5;`
- [ ] `scan_results` populated: `SELECT COUNT(*) FROM scan_results;`
- [ ] `positions` populated on entry: `SELECT * FROM positions ORDER BY created_at DESC LIMIT 5;`
- [ ] `positions` updated on exit: `SELECT exit_price, realized_pnl FROM positions WHERE status='closed' LIMIT 5;`
- [ ] `positions.broker_code` = 'ALPACA': `SELECT DISTINCT broker_code, currency FROM positions;`
- [ ] `orders` populated: `SELECT * FROM orders ORDER BY created_at DESC LIMIT 5;`
- [ ] `pattern_outcomes` populated after close: `SELECT * FROM pattern_outcomes ORDER BY created_at DESC LIMIT 5;`
- [ ] `pattern_confidence` updated: `SELECT * FROM pattern_confidence WHERE sample_count > 0;`
- [ ] Scanner adaptive tiers work: check scan.log for "Scanner relaxed to tier" messages
- [ ] Zero-candidate alerting: check `claude_messages` for scanner alerts after extended empty periods

---

## 7. What Remains

| Item | Priority | Notes |
|------|----------|-------|
| Richer pattern detection | P3 | Current detect_patterns only finds breakout + support_bounce |
| Dynamic watchlist | P3 | Screen from universe instead of fixed 44 symbols |
| Bootstrap pattern_outcomes from Alpaca history | P2 | Seed from past trades so learning starts with data |
| Securities table population | P3 | Auto-register symbols on first scan |
| Execution retry queue | P3 | Persist failed closes for retry next cycle |

---

*Implementation record for dev_claude v3.3.0 remediation*
*Craig + The Claude Family*
*2026-04-04*
