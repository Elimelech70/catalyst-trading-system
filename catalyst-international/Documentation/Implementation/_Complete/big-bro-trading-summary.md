# Big Bro Trading - Unified Agent Summary

**Generated**: 2026-01-05
**Source**: big bro trading.zip
**Purpose**: Summary of the unified agent implementation for HKEX trading

---

## Overview

The "Big Bro Trading" package contains a **unified agent implementation** that merges the existing `heartbeat_intl.py` (consciousness) and `agent.py` (trading) into a single file with automatic mode detection.

### Package Contents

| File | Lines | Purpose |
|------|-------|---------|
| `unified_agent.py` | 940 | Main unified agent (consciousness + trading) |
| `unified-agent-implementation.md` | 1081 | Design document and implementation guide |
| `catalyst-intl.cron` | 77 | Cron schedule for HKEX market hours |
| `deploy_unified_agent.sh` | 226 | Deployment script with backup/rollback |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      UNIFIED AGENT                               │
├─────────────────────────────────────────────────────────────────┤
│  CRON TRIGGER (based on HKEX market hours)                      │
│       │                                                          │
│       ▼                                                          │
│  unified_agent.py                                                │
│       │                                                          │
│       ├── 1. WAKE UP (update state, check budget)               │
│       ├── 2. PROCESS MESSAGES (from claude_messages)            │
│       ├── 3. TRADING (if market hours - Claude API loop)        │
│       ├── 4. REFLECT (learnings, observations)                  │
│       └── 5. SLEEP (update state, record spend)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Auto Mode Detection
The agent automatically determines its mode based on HKEX market hours:

| Time (HKT) | Mode | Actions |
|------------|------|---------|
| 08:00-09:30 | `scan` | Pre-market scanning, no trades |
| 09:30-12:00 | `trade` | Full trading session |
| 12:00-13:00 | `close` | Mandatory lunch break close |
| 13:00-16:00 | `trade` | Afternoon trading session |
| 16:00-16:30 | `close` | EOD close and report |
| Other times | `heartbeat` | Messages only |

### 2. Consciousness Integration
- Reads/writes to `claude_state` table
- Processes messages from `claude_messages`
- Records observations and learnings
- Tracks API spend against daily budget ($5.00)

### 3. Trading Tools
12 trading tools available via Claude API:
- `scan_market`, `get_quote`, `get_technicals`
- `detect_patterns`, `get_news`
- `check_risk`, `get_portfolio`
- `execute_trade`, `close_position`, `close_all`
- `send_alert`, `log_decision`

### 4. Risk Management
- Max 5 positions at once
- Max HKD 40,000 per position
- Max HKD 16,000 daily loss limit
- Mandatory stop losses
- No holding through lunch break

---

## Cron Schedule (UTC Times)

```
# Pre-market scan (09:00 HKT = 01:00 UTC)
0 1 * * 1-5   --mode scan

# Morning session (09:30-11:30 HKT = 01:30-03:30 UTC)
30 1,2,3 * * 1-5   --mode trade
0 2,3 * * 1-5      --mode trade

# Lunch close (12:00 HKT = 04:00 UTC)
0 4 * * 1-5   --mode close

# Afternoon session (13:00-15:30 HKT = 05:00-07:30 UTC)
0,30 5,6,7 * * 1-5   --mode trade

# EOD close (16:00 HKT = 08:00 UTC)
0 8 * * 1-5   --mode close

# Off-hours heartbeat (hourly)
0 0,9-23 * * 1-5   --mode heartbeat
0 * * * 0,6        --mode heartbeat (weekends)
```

---

## Deployment

### Quick Deploy
```bash
cd /tmp/big_bro_trading
chmod +x deploy_unified_agent.sh
./deploy_unified_agent.sh
```

### Manual Deploy
```bash
# 1. Backup
mkdir -p backups/$(date +%Y%m%d)
cp agent.py backups/$(date +%Y%m%d)/
cp scripts/heartbeat_intl.py backups/$(date +%Y%m%d)/

# 2. Deploy
cp unified_agent.py /root/Catalyst-Trading-System-International/catalyst-international/
chmod +x unified_agent.py

# 3. Install cron
cp catalyst-intl.cron /etc/cron.d/catalyst-intl
chmod 644 /etc/cron.d/catalyst-intl
systemctl restart cron

# 4. Test
python3 unified_agent.py --mode heartbeat
```

---

## Testing

```bash
# Heartbeat (no broker required)
python3 unified_agent.py --mode heartbeat

# Scan mode
python3 unified_agent.py --mode scan

# Trade mode (requires broker)
python3 unified_agent.py --mode trade

# Close mode
python3 unified_agent.py --mode close
```

---

## Rollback

If issues occur:
```bash
# Stop cron
rm /etc/cron.d/catalyst-intl

# Restore old files
cp backups/YYYYMMDD/agent.py .
cp backups/YYYYMMDD/heartbeat_intl.py scripts/
```

---

## Key Differences from Previous Implementation

| Aspect | Before (Split) | After (Unified) |
|--------|----------------|-----------------|
| Entry points | 2 files | 1 file |
| Trading trigger | Never called | Auto by market hours |
| Message processing | Every heartbeat | Every cycle |
| Mode detection | Manual | Automatic by time |
| Budget tracking | Separate | Combined |
| Logging | Split logs | Unified logging |

---

## Dependencies

- Python 3.9+
- `anthropic` - Claude API client
- `asyncpg` - PostgreSQL async driver
- `pyyaml` - Configuration
- `python-dotenv` - Environment variables
- Moomoo/Futu OpenD gateway (for trading)

---

## Environment Variables Required

```bash
ANTHROPIC_API_KEY=       # Claude API key
DATABASE_URL=            # Trading database (catalyst_intl)
RESEARCH_DATABASE_URL=   # Consciousness database (catalyst_research)
```

---

## Files Location After Deployment

```
/root/Catalyst-Trading-System-International/catalyst-international/
├── unified_agent.py          # Main agent
├── logs/
│   ├── unified_agent.log     # Agent logs
│   └── cron.log              # Cron output
└── backups/
    └── YYYYMMDD_HHMMSS/      # Backup of old files

/etc/cron.d/
└── catalyst-intl             # Cron schedule
```

---

**Status**: Ready for deployment
**Next Action**: Run `deploy_unified_agent.sh` on production server
