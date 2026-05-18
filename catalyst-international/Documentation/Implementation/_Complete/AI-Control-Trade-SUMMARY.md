# AI-Control-Trade Package Summary

**Name of Application:** Catalyst Trading System International
**Name of File:** AI-Control-Trade-SUMMARY.md
**Version:** 1.0.0
**Last Updated:** 2026-01-01
**Purpose:** Summary of trade-triggered position monitoring package

---

## Overview

This package implements **continuous AI position monitoring** for intl_claude that:
- Runs **only when a position is open** (no separate cron needed)
- Uses **rules-based signal detection** (FREE)
- Consults **Haiku only for uncertain signals** (~$0.05/call)
- Notifies **big_bro via dashboard** (FREE DB writes)

**Estimated monthly cost:** $10-25 (vs $120-270 original design)

---

## Package Contents

| File | Purpose | Lines | Cost |
|------|---------|-------|------|
| `signals.py` | Exit signal detection rules | ~445 | FREE |
| `consciousness_notify.py` | Big Bro notifications via DB | ~479 | FREE |
| `position_monitor.py` | Main monitoring loop | ~594 | ~$0.05/Haiku call |
| `tool_executor.py` | Trade execution with monitoring | Updated | - |
| `agent_patch.py` | One-line change for agent.py | ~42 | - |
| `README.md` | Quick start guide | ~139 | - |
| `DEPLOYMENT.md` | Full deployment steps | ~385 | - |

---

## Architecture

```
Trade Entry
    |
    v
execute_trade() fills order
    |
    v
start_position_monitor() begins
    |
    v
+---------------------------------------------+
|  Every 5 minutes:                           |
|                                             |
|  1. Check market open      (FREE)           |
|  2. Get quote & technicals (FREE)           |
|  3. Detect exit signals    (FREE)           |
|                                             |
|  If STRONG signal --> Exit immediately      |
|  If MODERATE signal --> Ask Haiku (~$0.05)  |
|  If WEAK/NONE --> Continue holding          |
|                                             |
|  Notify big_bro via dashboard (FREE)        |
+---------------------------------------------+
    |
    v
Position closed --> Monitor ends
```

---

## Signal Detection (FREE - No Claude Cost)

### Signal Strength Levels

| Level | Action | Cost |
|-------|--------|------|
| **STRONG** | Exit immediately | FREE |
| **MODERATE** | Consult Haiku | ~$0.05 |
| **WEAK** | Note but don't act | FREE |
| **NONE** | Continue holding | FREE |

### STRONG Signals (Immediate Exit)
- P&L <= -3% (stop loss)
- RSI > 85 (overbought)
- Volume collapsed (< 25% of entry)
- < 10 min to market close
- < 15 min to lunch break (HKEX)

### MODERATE Signals (Ask Haiku)
- P&L between -2% and -3%
- RSI between 75-85
- Volume fading (25-40% of entry)
- MACD bearish crossover
- Below VWAP by 2%+
- Multiple weak signals combined

### WEAK Signals (Note Only)
- P&L between -1% and -2%
- Minor technical weakness
- Extended hold time

---

## Big Bro Notifications

All notifications are FREE (DB writes to `claude_messages` table):

| Event | Priority | When |
|-------|----------|------|
| ENTRY | Normal | Position opened |
| MONITOR_STARTED | Low | Monitoring begins |
| HIGH_SEVERITY_SIGNAL | Normal | MODERATE+ signals detected |
| HAIKU_DECISION | Normal | Haiku consultation result |
| EXIT | High | Position closed |
| MONITOR_ENDED | Low | Monitoring stops |
| MONITOR_ERROR | High | Error occurred |

---

## Cost Model

| Component | Per-Trade Cost |
|-----------|----------------|
| Signal detection | FREE |
| Haiku calls (1-3 avg) | ~$0.05-0.15 |
| Big Bro notifications | FREE |
| **Total per trade** | **~$0.10-0.15** |

### Monthly Estimate (20 trades)
- Original design: $120-270/month
- This implementation: **$2-10/month**
- **Savings: 90%+**

---

## Deployment Requirements

1. Copy 3 new files to catalyst-international/:
   - `signals.py`
   - `consciousness_notify.py`
   - `position_monitor.py`

2. Update `tool_executor.py` (replace existing)

3. Add ONE line to `agent.py`:
   ```python
   self.executor = ToolExecutor(
       cycle_id=self.cycle_id,
       alert_callback=self._send_alert,
       agent=self,  # <-- ADD THIS LINE
   )
   ```

4. Ensure `asyncpg` is installed

5. Set `RESEARCH_DATABASE_URL` environment variable

---

## Testing

```bash
# Test signal detection
python signals.py

# Test notifications (requires RESEARCH_DATABASE_URL)
python consciousness_notify.py

# Test full flow (paper mode)
python agent.py --force
```

---

## Key Benefits

1. **Zero infrastructure** - No separate service or cron
2. **Cost-effective** - 90%+ cheaper than original design
3. **Intelligent exits** - Rules + AI for uncertain decisions
4. **Full visibility** - All events to big_bro dashboard
5. **Safe fallback** - Wide bracket orders remain as backup

---

## Files Location

Extracted to: `Documentation/Implementation/AI-Control-Trade/`

Original zip: `Documentation/Implementation/AI-Control-Trade.zip`

---

*Catalyst Trading System - January 2026*
