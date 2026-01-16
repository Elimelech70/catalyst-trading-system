# Trade-Triggered Position Monitoring - Delivered Files

## Summary

This package implements continuous AI position monitoring for intl_claude that:
- Runs **only when a position is open** (no separate cron needed)
- Uses **rules-based signal detection** (free)
- Consults **Haiku only for uncertain signals** (~$0.05/call)
- Notifies **big_bro via dashboard** (free DB writes)

**Estimated monthly cost:** $10-25 (vs $120-270 original design)

---

## Files Delivered

### New Files (copy to catalyst-international/)

| File | Purpose | Lines |
|------|---------|-------|
| `signals.py` | Exit signal detection rules (free) | 320 |
| `consciousness_notify.py` | Big Bro notifications via DB (free) | 300 |
| `position_monitor.py` | Main monitoring loop | 400 |

### Updated Files (replace existing)

| File | Purpose | Changes |
|------|---------|---------|
| `tool_executor.py` | Trade execution with monitoring | Added ~50 lines |

### Patch Files (for reference)

| File | Purpose |
|------|---------|
| `agent_patch.py` | Shows the ONE line change for agent.py |
| `tool_executor_additions.py` | Documents all tool_executor changes |

### Documentation

| File | Purpose |
|------|---------|
| `DEPLOYMENT.md` | Complete deployment guide |
| `implementation-plan-trade-triggered-monitoring-v1.0.0.md` | Full implementation plan |
| `ai-pattern-exit-strategy-v1.0.0.md` | Original design document |

---

## Quick Deployment

### 1. Copy files to droplet

```bash
scp signals.py consciousness_notify.py position_monitor.py tool_executor.py root@<intl-droplet>:/root/Catalyst-Trading-System-International/catalyst-international/
```

### 2. Update agent.py (ONE LINE)

```bash
ssh root@<intl-droplet>

# Find and edit this line in agent.py:
# OLD: alert_callback=self._send_alert,
# NEW: alert_callback=self._send_alert,
#      agent=self,
```

### 3. Test

```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate
python signals.py  # Test signal detection
python agent.py --force  # Test full flow
```

---

## How It Works

```
Trade Entry
    │
    ▼
execute_trade() fills order
    │
    ▼
start_position_monitor() begins
    │
    ▼
┌─────────────────────────────────────────┐
│  Every 5 minutes:                       │
│                                         │
│  1. Check market open      (free)       │
│  2. Get quote & technicals (free)       │
│  3. Detect exit signals    (free)       │
│                                         │
│  If STRONG signal → Exit immediately    │
│  If MODERATE signal → Ask Haiku ($0.05) │
│  If WEAK/NONE → Continue holding        │
│                                         │
│  Notify big_bro via dashboard (free)    │
└─────────────────────────────────────────┘
    │
    ▼
Position closed → Monitor ends
```

---

## Cost Model

| Component | Per-Trade Cost |
|-----------|----------------|
| Signal detection | FREE |
| Haiku calls (1-3 avg) | ~$0.05-0.15 |
| Big Bro notifications | FREE |
| **Total per trade** | **~$0.10-0.15** |

Monthly (20 trades): **~$2-3**

---

## Files Summary

```
DELIVERED/
├── signals.py              ← NEW: Signal detection rules
├── consciousness_notify.py ← NEW: Dashboard notifications
├── position_monitor.py     ← NEW: Monitoring loop
├── tool_executor.py        ← UPDATED: With monitoring call
├── agent_patch.py          ← PATCH: One-line agent.py change
├── DEPLOYMENT.md           ← GUIDE: Full deployment steps
└── README.md               ← THIS FILE
```

---

*Catalyst Trading System - January 1, 2025*
