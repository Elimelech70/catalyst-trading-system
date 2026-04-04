# dev_claude Architecture — v3.3

**Name of file:** dev-claude-architecture-v3.3.md
**Version:** 1.0.0
**Created:** 2026-04-04
**Authors:** Craig + Claude
**Purpose:** Architecture document for dev_claude US sandbox trading agent after P1-P3 remediation
**Status:** Current
**Supersedes:** catalyst-us-v8-implementation.md v1.0.0 (2026-03-21)

---

## REVISION HISTORY

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-04-04 | Initial — documents v3.3.0 architecture after trading analysis remediation |

---

## 1. Purpose

This document describes the architecture of **dev_claude**, the US sandbox trading agent running on the Catalyst droplet. It reflects the state of the system after the March 2026 trading analysis identified 5 critical issues and the subsequent P1-P3 remediation that fixed them.

dev_claude is a single-agent architecture where Claude API (Sonnet) makes all trading decisions using tools. It trades US stocks on Alpaca paper and learns from outcomes via the synaptic learning loop.

---

## 2. Architecture Overview

```
dev_claude (unified_agent.py v3.3.0)
│
├── CYCLE LOOP (Anthropic Claude API)
│     Claude decides → tool calls → results → Claude decides again
│     Max 20 iterations per cycle
│
├── TOOLS (12 available)
│     scan_market       ← Adaptive tiered scanning
│     get_quote         ← Current price/spread
│     get_technicals    ← RSI, SMA-10, SMA-20
│     detect_patterns   ← Chart pattern recognition
│     get_news          ← Alpaca news API
│     get_portfolio     ← Account + positions
│     check_risk        ← Position sizing validation
│     execute_trade     ← Buy/sell → Alpaca → positions DB
│     close_position    ← Cancel stale orders → close → P&L → LTP/LTD
│     close_all         ← Emergency full liquidation
│     send_alert        ← Consciousness message bus
│     log_decision      ← Decision audit trail
│
├── BROKER (AlpacaClient v1.2.0)
│     Paper trading, IEX data feed
│     Market clock API for hours detection
│     Stale order cancellation before exits
│
├── DATABASE (PostgreSQL — catalyst_dev)
│     trading_cycles    ← Cycle lifecycle (new)
│     scan_results      ← Scan candidates persisted (new)
│     positions         ← Entry + exit + P&L (fixed)
│     orders            ← Order audit trail
│     decisions         ← Decision reasoning
│     pattern_outcomes  ← Trade outcome per pattern (new)
│     pattern_confidence← Synaptic weights, LTP/LTD (now active)
│
├── CONSCIOUSNESS (PostgreSQL — catalyst_research)
│     claude_state      ← Budget, mode, wake status
│     claude_messages   ← Inter-agent messaging
│     claude_learnings  ← Validated learnings
│
└── CRON (TZ=America/New_York)
      08:00 ET  Pre-market scan
      09:30 ET  Market open trade
      10-15 ET  Hourly trade cycles
      16:00 ET  End-of-day close
      Off-hours  Heartbeat (every 3h weekday, 6h weekend)
```

---

## 3. Data Flow — Trade Lifecycle

```
CRON triggers unified_agent.py --mode trade
    │
    ├── 1. INSERT trading_cycles (cycle_id, date, mode)
    ├── 2. Wake consciousness, check budget
    ├── 3. Sync positions with Alpaca broker
    │
    ├── 4. Claude API loop begins
    │     ├── scan_market (adaptive: 2% → 1% → 0.5%)
    │     │     └── Persist to scan_results
    │     ├── get_portfolio, get_quote, get_technicals
    │     ├── detect_patterns
    │     ├── check_risk
    │     ├── execute_trade
    │     │     ├── Submit order to Alpaca
    │     │     ├── INSERT orders (side=buy/sell, cycle_id)
    │     │     └── INSERT positions (side=long/short, broker_code=ALPACA, currency=USD)
    │     ├── close_position (with retry × 3)
    │     │     ├── Cancel stale orders
    │     │     ├── Close via Alpaca
    │     │     ├── UPDATE positions (exit_price, P&L)
    │     │     ├── INSERT pattern_outcomes
    │     │     └── UPDATE pattern_confidence (LTP/LTD)
    │     └── log_decision
    │
    ├── 5. UPDATE trading_cycles (status=completed, stats)
    └── 6. Sleep consciousness
```

---

## 4. Key Subsystems

### 4.1 Adaptive Scanner

The scanner failed for 6 weeks (Feb-Mar 2026) because the 2% minimum daily change filter was too strict during a low-volatility market. Fixed with tiered adaptive thresholds:

| Tier | min_change_pct | When Used |
|------|---------------|-----------|
| 1 | 2.0% | Default — strong movers |
| 2 | 1.0% | Tier 1 found zero candidates |
| 3 | 0.5% | Tier 2 found zero candidates |

Additional safeguards:
- **IEX error tracking**: Logs degraded data feed (>50% symbol failures)
- **Zero-candidate alerting**: After N consecutive empty scans (configurable, default 3), sends alert to big_bro via consciousness
- **Scan persistence**: All candidates persisted to `scan_results` table with cycle_id FK

Configuration in `config/dev_claude_config.yaml`:
```yaml
scanner:
  min_change_pct_tiers: [2.0, 1.0, 0.5]
  zero_candidate_alert_threshold: 3
  persist_results: true
```

### 4.2 Position Persistence

Positions are the trade journal. Every entry and exit is recorded.

**On entry** (`execute_trade`):
- INSERT into `positions` with explicit `broker_code='ALPACA'`, `currency='USD'`
- Entry price from live quote (ask or last)
- Side normalized: buy/long → `long`, sell/short → `short`
- FK to `trading_cycles` via `cycle_id`

**On exit** (`close_position`):
- UPDATE positions: exit_price, exit_time, exit_reason
- Realized P&L calculated in SQL (handles long/short correctly)
- Also records `closed_at` timestamp

**Schema note**: The `positions.broker_code` defaults to `'MOOMOO'` and `currency` to `'HKD'` (HKEX legacy). US agent must always set these explicitly.

### 4.3 Synaptic Learning (LTP/LTD)

The learning loop connects trade outcomes to pattern confidence. This is what allows the system to improve over time.

```
Position closed with P&L
    │
    ├── Determine pattern_type (from metadata or default 'momentum')
    ├── Determine exit_trigger (stop_loss, take_profit, eod_close, signal, manual)
    ├── Calculate outcome (win if pnl_pct > 0)
    │
    ├── INSERT pattern_outcomes
    │     pattern_type, symbol, position_id, pnl_pct, pnl_usd,
    │     outcome, exit_trigger, confidence_before, confidence_after
    │
    └── UPDATE pattern_confidence
          Win  → LTP: confidence += 0.05 (capped at 0.95)
          Loss → LTD: confidence -= 0.03 (floored at 0.10)
          Also updates: sample_count, win_count, loss_count,
          avg_win_pct, avg_loss_pct (running averages)
```

Configuration:
```yaml
learning:
  ltp_rate: 0.05
  ltd_rate: 0.03
  min_confidence: 0.10
  max_confidence: 0.95
```

The asymmetric rates (LTP > LTD) mean the system learns faster from wins than it unlearns from losses, encouraging cautious growth.

### 4.4 Exit Retry Logic

The #1 operational failure (20+ failed exits due to "shares held for orders") is now handled with:

1. `cancel_orders_for_symbol()` runs automatically before every close attempt
2. If close fails, retry up to 3 times with linear backoff (1s, 2s)
3. Before each retry, re-cancel stale orders (catches race conditions)
4. After 3 failures, log error and return failure to Claude

### 4.5 Trading Cycle Persistence

Every cycle (scan, trade, close, heartbeat) is now recorded:

- **Start**: INSERT into `trading_cycles` with cycle_id, date, mode, status='active'
- **End**: UPDATE with status='completed', positions_opened, api_calls, api_cost, notes
- **cycle_id** is FK parent for: positions, orders, scan_results, decisions

### 4.6 Market Hours Detection

Uses Alpaca clock API (authoritative) instead of timezone calculation:

```python
clock = broker.get_clock()  # {'is_open': True, 'next_close': '...'}
```

Falls back to ET timezone calculation only if API fails. This handles weekends, holidays, and early closes correctly regardless of host timezone (AWST).

---

## 5. Database Schema (Active Tables)

| Table | Purpose | Populated By |
|-------|---------|-------------|
| `trading_cycles` | Cycle lifecycle | run_cycle() start/end |
| `scan_results` | Scan candidates | _scan_market() |
| `positions` | Trade journal | _execute_trade() / _close_position() |
| `orders` | Order audit | _execute_trade() |
| `decisions` | Decision reasoning | _log_decision() |
| `pattern_outcomes` | Trade outcomes per pattern | _close_position() → _record_pattern_outcome() |
| `pattern_confidence` | Synaptic weights | _record_pattern_outcome() LTP/LTD |
| `signals` | Signal bus | (future — not yet wired to scanner) |
| `securities` | Symbol registry | (manual — needs population) |

---

## 6. Configuration

All configuration in `config/dev_claude_config.yaml`. Key sections:

| Section | Controls |
|---------|----------|
| `agent` | Identity, budget ($5/day) |
| `trading` | Position limits, risk thresholds, price/volume filters |
| `scanner` | Adaptive tiers, zero-candidate alerting |
| `learning` | LTP/LTD rates, confidence bounds |
| `signals` | Exit signal thresholds |
| `schedule` | Market hours |
| `autonomy` | Full autonomy for sandbox |

---

## 7. File Map

```
services/dev_claude/
├── unified_agent.py          ← Main agent (v3.3.0) — cycle orchestration + all tools
├── tools.py                  ← Tool definitions for Claude API
├── tool_executor.py          ← Tool routing (legacy, being absorbed into unified_agent)
├── workflow_tracker.py       ← 10-phase workflow progress tracking
├── signals.py                ← Exit signal detection (RSI, stop-loss, patterns)
├── brokers/
│   └── alpaca.py             ← Alpaca client (v1.2.0) — orders, data, clock
├── data/
│   └── database.py           ← DB connection management
├── config/
│   ├── dev_claude_config.yaml← Agent configuration
│   └── exit_context.yaml     ← Hot-reloadable exit thresholds
├── cron.d                    ← Cron schedule (TZ=America/New_York)
└── logs/                     ← Log output directory
```

---

## 8. Known Limitations

1. **Pattern detection is basic** — only breakout and support_bounce detected. Need richer pattern library.
2. **Securities table sparse** — only AAPL registered. Scanned symbols not auto-registered.
3. **No dynamic watchlist** — fixed 44-symbol list. No screening from universe.
4. **Single-threaded scanning** — scans symbols sequentially. Could be slow for larger watchlists.
5. **Pattern type assignment** — defaults to 'momentum' if no pattern metadata on position. Needs better association between detected patterns and trade entries.

---

## 9. Cron Schedule

```
TZ=America/New_York

08:00 ET  Mon-Fri  Pre-market scan
09:30 ET  Mon-Fri  Market open trade
10-15 ET  Mon-Fri  Hourly trade cycles
16:00 ET  Mon-Fri  End-of-day close
00,03,06,09,12 ET  Mon-Fri  Off-hours heartbeat (3h)
00,06,12,18 ET  Sat-Sun  Weekend heartbeat (6h)
00:00 ET  Sunday   Log rotation (>7 days)
```

---

*Architecture document for dev_claude v3.3.0*
*Craig + The Claude Family*
*2026-04-04*
