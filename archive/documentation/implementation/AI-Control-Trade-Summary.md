# AI-Control-Trade Package Summary

**Name of Application:** Catalyst Trading System
**Name of File:** AI-Control-Trade-Summary.md
**Version:** 1.0.0
**Last Updated:** 2026-01-01
**Purpose:** Summary of the Trade-Triggered Position Monitoring implementation for International Trading

---

## Overview

The AI-Control-Trade package implements **continuous AI position monitoring** for the Catalyst International trading system (`intl_claude`). The system automatically monitors open positions after trade entry and makes intelligent exit decisions without manual intervention.

### Key Features

| Feature | Description |
|---------|-------------|
| Trade-triggered | Monitoring starts automatically after each BUY order |
| Rules-based signals | FREE - No Claude API cost for signal detection |
| Haiku consultations | ~$0.05/call for uncertain signals only |
| Big Bro notifications | FREE - Database writes to dashboard |
| No separate cron needed | Runs in same process as trade entry |

---

## Cost Model

| Component | Cost |
|-----------|------|
| Signal detection (rules-based) | FREE |
| Haiku consultation (~2-3/trade) | ~$0.10-0.15 |
| Big Bro notifications | FREE (DB writes) |
| **Per-trade monitoring cost** | **~$0.10-0.15** |
| **Monthly estimate (20 trades)** | **$2-3** |

Compared to original design ($120-270/month), this represents **~95% cost reduction**.

---

## Files Delivered

### New Files (to deploy to catalyst-international/)

| File | Purpose | Lines |
|------|---------|-------|
| `signals.py` | Rules-based exit signal detection | ~445 |
| `consciousness_notify.py` | Dashboard notifications via DB | ~479 |
| `position_monitor.py` | Main monitoring loop | ~594 |

### Updated Files

| File | Purpose | Changes |
|------|---------|---------|
| `tool_executor.py` | Trade execution with monitoring | v2.2.0 - added monitoring integration |
| `agent.py` | TradingAgent | +1 line (pass `agent=self` to ToolExecutor) |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Quick start guide |
| `DEPLOYMENT.md` | Full deployment instructions |

---

## Architecture

### Signal Detection Flow

```
Trade Entry (BUY order filled)
         │
         ▼
execute_trade() completes
         │
         ▼
start_position_monitor() begins
         │
         ▼
┌────────────────────────────────────────────┐
│        MONITORING LOOP (every 5 min)       │
│                                            │
│  1. Check market open              (free)  │
│  2. Check position exists          (free)  │
│  3. Get quote & technicals         (free)  │
│  4. Detect exit signals            (free)  │
│                                            │
│  ┌─────────────────────────────────────┐   │
│  │ Signal Strength Decision Matrix    │   │
│  ├─────────────────────────────────────┤   │
│  │ STRONG   → Exit immediately (FREE) │   │
│  │ MODERATE → Consult Haiku (~$0.05)  │   │
│  │ WEAK     → Note but continue       │   │
│  │ NONE     → All clear, continue     │   │
│  └─────────────────────────────────────┘   │
│                                            │
│  Notify big_bro via dashboard      (free)  │
│  Sleep 5 minutes                           │
└────────────────────────────────────────────┘
         │
         ▼
Position closed → Monitor ends → Agent exits
```

### Signal Strength Thresholds

| Level | Criteria | Action |
|-------|----------|--------|
| **STRONG** | P&L <= -3%, RSI > 85, Volume < 25%, < 10 min to close | Exit immediately (no Claude cost) |
| **MODERATE** | P&L -2% to -3%, RSI 75-85, Volume 25-40%, MACD bearish | Ask Haiku (~$0.05) |
| **WEAK** | P&L -1% to -2%, Minor technical weakness | Note but don't act |
| **NONE** | No concerning signals | Continue holding |

---

## Signal Types

### P&L Signals
- `stop_loss_near` - Position approaching stop loss
- `profit_target_near` - Position approaching target
- `trailing_stop_hit` - Trailing stop triggered

### Volume Signals
- `volume_dying` - Volume collapsed vs entry
- `volume_spike_down` - Unusual volume on down move
- `no_follow_through` - No volume confirmation

### Technical Signals
- `rsi_overbought` - RSI > 70/75/85 (weak/moderate/strong)
- `rsi_oversold` - RSI < 25 (momentum dead)
- `macd_bearish_cross` - MACD crossed below signal
- `below_vwap` - Price below VWAP by 1-2%+
- `below_ema20` - Price below 20 EMA

### Time Signals
- `market_closing_soon` - < 10/30/60 min to close
- `lunch_break_approaching` - HKEX lunch break imminent
- `extended_hold` - Holding > 2-3 hours

---

## Big Bro Notifications

Notifications are written to `claude_messages` table and appear on the consciousness dashboard:

| Event | Priority | Description |
|-------|----------|-------------|
| `[ENTRY]` | normal | New position entered |
| `[MONITOR]` Started | low | Monitoring began |
| `[HAIKU]` | normal | Claude consultation result |
| `HIGH_SEVERITY_SIGNAL` | normal | Moderate+ signals detected |
| `[EXIT]` | high | Position closed with P&L |
| `[MONITOR]` Ended | low | Monitoring completed |
| `MONITOR_ERROR` | high | Error during monitoring |
| `HAIKU_LIMIT_REACHED` | normal | Max Haiku calls hit |

---

## Configuration Options

### position_monitor.py

```python
CHECK_INTERVAL_SECONDS = 300       # Check every 5 minutes
MAX_HAIKU_CALLS_PER_POSITION = 10  # Cost limit per position
HAIKU_MODEL = "claude-3-haiku-20240307"
```

### signals.py Thresholds (adjustable)

```python
# Stop loss thresholds
-3% = STRONG exit
-2% to -3% = MODERATE (ask Haiku)
-1% to -2% = WEAK (note only)

# RSI thresholds
> 85 = STRONG
> 75 = MODERATE
> 70 = WEAK

# Volume thresholds
< 25% = STRONG
< 40% = MODERATE
< 60% = WEAK
```

---

## Deployment Checklist

1. [ ] SSH to international droplet
2. [ ] Copy new files: `signals.py`, `consciousness_notify.py`, `position_monitor.py`
3. [ ] Replace `tool_executor.py` with v2.2.0
4. [ ] Update `agent.py` (+1 line: `agent=self`)
5. [ ] Verify `asyncpg` installed: `pip install asyncpg`
6. [ ] Test signal detection: `python signals.py`
7. [ ] Test full system: `python agent.py --force`

---

## Success Metrics

After 1 week of live trading:

| Metric | Baseline | Target |
|--------|----------|--------|
| Avg exit loss | -3% | < -1.5% |
| Avg exit win | +5% | > +6% |
| Haiku calls/trade | - | < 3 |
| Monitor errors | - | 0 |

---

## Rollback

If issues occur, comment out monitoring code in `tool_executor.py`:

```python
# In _execute_trade method, comment out:
# if side == "BUY" and self.agent:
#     monitor_result = await start_position_monitor(...)
```

Wide bracket orders remain in place as backup protection.

---

## Files Location

Extracted files stored in:
```
Documentation/Implementation/AI-Control-Trade-extracted/
├── signals.py
├── consciousness_notify.py
├── position_monitor.py
├── tool_executor.py
├── agent_patch.py
├── README.md
└── DEPLOYMENT.md
```

---

*Catalyst Trading System - 2026-01-01*
