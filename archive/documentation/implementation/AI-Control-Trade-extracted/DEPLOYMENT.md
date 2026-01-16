# Trade-Triggered Position Monitoring - Deployment Guide

**Name of Application:** Catalyst Trading System International  
**Name of File:** DEPLOYMENT.md  
**Version:** 1.0.0  
**Last Updated:** 2025-01-01  
**Purpose:** Deploy trade-triggered position monitoring for intl_claude

---

## Overview

This deploys continuous AI position monitoring that runs **only when a position is open**. No separate cron or service needed - monitoring starts automatically after each trade.

### Cost Model

| Component | Cost |
|-----------|------|
| Signal detection (rules) | FREE |
| Haiku consultation (~2-3/trade) | ~$0.10-0.15 |
| Big Bro notifications | FREE (DB writes) |
| **Per-trade monitoring cost** | **~$0.10-0.15** |

---

## Files to Deploy

| File | Purpose | Lines |
|------|---------|-------|
| `signals.py` | Exit signal detection rules | ~320 |
| `consciousness_notify.py` | Big Bro notifications via DB | ~300 |
| `position_monitor.py` | Main monitoring loop | ~400 |
| `tool_executor.py` | UPDATE existing file | +20 lines |
| `agent.py` | UPDATE existing file | +1 line |

---

## Deployment Steps

### Step 1: SSH to International Droplet

```bash
ssh root@<international-droplet-ip>
cd /root/Catalyst-Trading-System-International/catalyst-international
```

### Step 2: Activate Virtual Environment

```bash
source venv/bin/activate
```

### Step 3: Verify asyncpg is Installed

```bash
pip list | grep asyncpg
# If not installed:
pip install asyncpg
```

### Step 4: Copy New Files

Copy these files to the catalyst-international directory:

```bash
# signals.py
# consciousness_notify.py  
# position_monitor.py
```

### Step 5: Update tool_executor.py

Add these changes to `tool_executor.py`:

#### 5a. Add import at top:

```python
# Add after existing imports
import asyncio
from position_monitor import start_position_monitor
```

#### 5b. Update ToolExecutor.__init__:

```python
def __init__(
    self,
    cycle_id: str,
    alert_callback: Any = None,
    agent: Any = None,  # ADD THIS PARAMETER
):
    self.cycle_id = cycle_id
    self.alert_callback = alert_callback
    self.agent = agent  # ADD THIS LINE
    # ... rest unchanged ...
```

#### 5c. Update _execute_trade method (after successful BUY):

Add this block after the trade is logged, inside the success branch for BUY orders:

```python
# After: self.db.log_trade(...)
# Add:

if side == "BUY" and self.agent:
    logger.info(f"Starting position monitor for {symbol}")
    
    # Get current volume for baseline
    try:
        quote = self.broker.get_quote(symbol)
        entry_volume = float(quote.get('volume', 0) or 0)
    except Exception:
        entry_volume = 0
    
    # Calculate wide bracket stops (5% stop, 10% target)
    wide_stop = fill_price * 0.95 if not stop_price else stop_price
    wide_target = fill_price * 1.10 if not target_price else target_price
    
    # Start monitoring
    try:
        monitor_result = await start_position_monitor(
            broker=self.broker,
            market_data=self.market,
            anthropic_client=self.agent.client,
            safety_validator=self.safety,
            symbol=symbol,
            entry_price=fill_price,
            quantity=quantity,
            entry_volume=entry_volume,
            entry_reason=reasoning,
            stop_price=wide_stop,
            target_price=wide_target,
        )
        result['monitor_result'] = monitor_result
    except Exception as e:
        logger.error(f"Position monitor failed: {e}")
        result['monitor_error'] = str(e)
```

### Step 6: Update agent.py

Find where ToolExecutor is initialized in `run_cycle()` and add `agent=self`:

```python
# BEFORE:
self.executor = ToolExecutor(
    cycle_id=self.cycle_id,
    alert_callback=self._send_alert,
)

# AFTER:
self.executor = ToolExecutor(
    cycle_id=self.cycle_id,
    alert_callback=self._send_alert,
    agent=self,
)
```

### Step 7: Test Signal Detection

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
python signals.py
```

Expected output:
```
Testing Exit Signal Detection
==================================================

Test 1: Position down 3%
  Signals: ['stop_loss_near:STRONG']
  Immediate exit: True
  ...
```

### Step 8: Test Notifications (Optional)

```bash
# Requires RESEARCH_DATABASE_URL
export RESEARCH_DATABASE_URL="postgresql://..."
python consciousness_notify.py
```

### Step 9: Test Full System (Paper Mode)

```bash
# During HKEX hours or with --force
python agent.py --force
```

Watch logs for:
- "Starting position monitor for ..."
- "Check N complete for ..."
- "Haiku decision: ..."
- "Exit notification sent: ..."

---

## Verification Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Files exist | `ls -la signals.py consciousness_notify.py position_monitor.py` | All present |
| Python syntax OK | `python -m py_compile signals.py` | No errors |
| Signal tests pass | `python signals.py` | All tests complete |
| Agent starts | `python agent.py --force` | No import errors |
| Big Bro sees notifications | Check dashboard | Notifications appear |

---

## How It Works

### Trade Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  1. CRON triggers agent.py                                      │
│        │                                                        │
│        ▼                                                        │
│  2. Claude decides: BUY 0700 @ HKD 380                         │
│        │                                                        │
│        ▼                                                        │
│  3. tool_executor._execute_trade()                              │
│        │                                                        │
│        ├── Place order with Moomoo                              │
│        ├── Log trade to DB                                      │
│        │                                                        │
│        ▼                                                        │
│  4. start_position_monitor()  ← NEW                             │
│        │                                                        │
│        │  ┌─────────────────────────────────────────────────┐  │
│        │  │           MONITORING LOOP                       │  │
│        │  │                                                 │  │
│        │  │  while position_open AND market_open:           │  │
│        │  │      signals = detect_signals()    ← FREE       │  │
│        │  │                                                 │  │
│        │  │      if STRONG signal:                          │  │
│        │  │          exit()                    ← NO COST    │  │
│        │  │      elif MODERATE signal:                      │  │
│        │  │          decision = ask_haiku()   ← ~$0.05      │  │
│        │  │          if exit: exit()                        │  │
│        │  │                                                 │  │
│        │  │      notify_big_bro()             ← FREE (DB)   │  │
│        │  │      sleep(5 min)                               │  │
│        │  │                                                 │  │
│        │  └─────────────────────────────────────────────────┘  │
│        │                                                        │
│        ▼                                                        │
│  5. Position closed → Monitor ends → Agent exits               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Signal Decision Logic

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIGNAL STRENGTH LEVELS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STRONG (exit immediately, no Claude cost):                     │
│  • P&L <= -3%                                                   │
│  • RSI > 85                                                     │
│  • Volume collapsed (< 25% of entry)                            │
│  • < 10 min to market close                                     │
│  • < 15 min to lunch break                                      │
│                                                                 │
│  MODERATE (ask Haiku, ~$0.05):                                  │
│  • P&L between -2% and -3%                                      │
│  • RSI between 75-85                                            │
│  • Volume fading (25-40% of entry)                              │
│  • MACD bearish crossover                                       │
│  • Below VWAP by 2%+                                            │
│  • Multiple weak signals                                        │
│                                                                 │
│  WEAK (note but don't act):                                     │
│  • P&L between -1% and -2%                                      │
│  • Minor technical weakness                                     │
│                                                                 │
│  NONE (all clear):                                              │
│  • Continue holding                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'position_monitor'"

Files not in the right location. Ensure all .py files are in the catalyst-international directory.

### "RESEARCH_DATABASE_URL not set"

Add to environment:
```bash
export RESEARCH_DATABASE_URL="postgresql://user:pass@host:port/catalyst_research?sslmode=require"
```

Or add to `.env` file.

### Monitor not starting

Check that `agent=self` was added to ToolExecutor initialization in agent.py.

### Notifications not appearing on dashboard

1. Check RESEARCH_DATABASE_URL is correct
2. Verify claude_messages table exists
3. Check big_bro heartbeat is running

### Haiku calls failing

1. Check ANTHROPIC_API_KEY is set
2. Verify API key has Haiku access
3. Check rate limits

---

## Rollback

If issues occur, comment out the monitoring code:

```python
# In tool_executor.py _execute_trade method:

# COMMENT OUT THIS BLOCK:
# if side == "BUY" and self.agent:
#     ...
#     monitor_result = await start_position_monitor(...)
#     ...
```

Wide bracket orders remain in place as backup protection.

---

## Configuration

### Adjust Check Interval

In `position_monitor.py`:
```python
CHECK_INTERVAL_SECONDS = 300  # Change to 180 for 3-minute checks
```

### Adjust Signal Thresholds

In `signals.py`, modify the threshold values in `detect_exit_signals()`:
```python
# Example: Make stop loss more aggressive
if pnl_pct <= -0.025:  # Change from -0.03 to -0.025
    signals.stop_loss_near = SignalStrength.STRONG
```

### Adjust Haiku Limit

In `position_monitor.py`:
```python
MAX_HAIKU_CALLS_PER_POSITION = 10  # Increase/decrease as needed
```

---

## Success Metrics

After 1 week of live trading, measure:

| Metric | Baseline | Target |
|--------|----------|--------|
| Avg exit loss | -3% | < -1.5% |
| Avg exit win | +5% | > +6% |
| Haiku calls/trade | - | < 3 |
| Monitor errors | - | 0 |

---

**END OF DEPLOYMENT GUIDE**

*Catalyst Trading System - January 1, 2025*
