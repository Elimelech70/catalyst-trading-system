# US Position Monitor Service - Implementation Summary

**Name of Application:** Catalyst Trading System
**Name of file:** us-position-monitor-implementation-summary.md
**Version:** 1.0.0
**Last Updated:** 2026-01-16
**Purpose:** Implementation summary for US Position Monitor Service

---

## Overview

This document summarizes the implementation of the **US Position Monitor Service** for the Catalyst Trading System. The service is a persistent systemd daemon that continuously monitors all open positions during US market hours and executes exits when signals indicate.

## Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `position_monitor_service.py` | 1129 | Main Python service |
| `position-monitor-service-us-design.md` | 350 | Design document |
| `position_monitor_service_schema.sql` | 79 | Database schema additions |
| `position-monitor-us.service` | 70 | Systemd unit file |
| `install-position-monitor-us.sh` | 184 | Installation script |

---

## Key Features

### 1. Persistent Monitoring
- Runs as a systemd daemon (auto-restarts on failure)
- Checks all open positions every 5 minutes during market hours
- No missed positions - unlike previous design where monitors died with entry process

### 2. US Market Hours
| Period | Time (ET) | Action |
|--------|-----------|--------|
| Pre-Market | 4:00 AM - 9:30 AM | Service sleeps |
| **Regular Hours** | **9:30 AM - 4:00 PM** | **Active monitoring** |
| After Hours | 4:00 PM - 8:00 PM | Service sleeps |
| Weekend | Sat-Sun | Service sleeps |

**Note:** No lunch break (continuous trading, unlike HKEX version)

### 3. Signal Detection System

#### P&L Signals (US Volatility Adjusted)
| Signal | Threshold | Strength | Action |
|--------|-----------|----------|--------|
| Stop Loss | <= -5% | STRONG | Exit immediately |
| Stop Loss | <= -3% | MODERATE | Consult Haiku |
| Stop Loss | <= -2% | WEAK | Monitor only |
| Take Profit | >= +10% | STRONG | Exit immediately |
| Take Profit | >= +6% | MODERATE | Consult Haiku |

#### Technical Signals
| Signal | Threshold | Strength |
|--------|-----------|----------|
| RSI Overbought | >= 85 | STRONG |
| RSI Overbought | >= 75 | MODERATE |
| Volume Collapse | <= 25% of entry | STRONG |
| Volume Collapse | <= 40% of entry | MODERATE |
| Trailing Stop | >= 3% from high | MODERATE |
| MACD Bearish | < -0.5 | MODERATE |

#### Time-Based Signals
| Time (ET) | Signal | Strength |
|-----------|--------|----------|
| 3:45 PM - 4:00 PM | Near Close | STRONG |
| 3:00 PM - 3:30 PM | Power Hour | WEAK |

### 4. Decision Flow
```
Signal Detected
      │
      ├── STRONG Signal ──────────────> EXIT IMMEDIATELY
      │
      ├── MODERATE Signal ──> Consult Haiku AI ──> EXIT or HOLD
      │
      └── WEAK Signal ─────────────────> MONITOR ONLY
```

### 5. Haiku AI Integration
- Consulted for MODERATE signals only
- Maximum 5 Haiku calls per monitoring cycle
- Prompt includes: position details, P&L, signals, entry reason
- Response format: EXIT (yes/no) + REASON

### 6. Consciousness Framework Integration
- Agent ID: `dev_claude`
- Exit notifications sent to `big_bro`
- Observations recorded in `claude_observations` table
- Service health tracked in `service_health` table

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Position Monitor Service                      │
│                         (systemd daemon)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │   Database   │    │    Alpaca    │    │  Anthropic   │     │
│   │  (asyncpg)   │    │   (alpaca-py)│    │   (Haiku)    │     │
│   └──────────────┘    └──────────────┘    └──────────────┘     │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              Signal Detection Engine                     │  │
│   │  • Stop Loss    • Take Profit   • Trailing Stop         │  │
│   │  • RSI          • Volume        • Time-based            │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Consciousness Framework                       │
│                     (catalyst_research DB)                       │
│   • Exit notifications to big_bro                               │
│   • Observations for learning                                   │
│   • Service health monitoring                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema Additions

### New Table: `service_health`
```sql
CREATE TABLE service_health (
    service_name VARCHAR(100) PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'unknown',
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    last_check_count INTEGER DEFAULT 0,
    positions_monitored INTEGER DEFAULT 0,
    exits_executed INTEGER DEFAULT 0,
    haiku_calls INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Position Table Additions
- `high_watermark NUMERIC(18,4)` - For trailing stop tracking
- `entry_volume NUMERIC(18,0)` - For volume analysis

---

## Configuration

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection (catalyst_dev) |
| `ALPACA_API_KEY` | Yes | Alpaca API key |
| `ALPACA_SECRET_KEY` | Yes | Alpaca secret key |
| `ALPACA_BASE_URL` | Yes | Alpaca endpoint (paper/live) |
| `RESEARCH_DATABASE_URL` | No | Consciousness DB (catalyst_research) |
| `ANTHROPIC_API_KEY` | No | For Haiku consultations |
| `MONITOR_CHECK_INTERVAL` | No | Check interval (default: 300s) |
| `MONITOR_DRY_RUN` | No | Testing mode (default: false) |

### Systemd Service Settings
- **User:** root
- **Working Directory:** /root/catalyst-dev
- **Restart Policy:** Always (30s delay, max 5 attempts/5min)
- **Resource Limits:** 256MB RAM, 25% CPU
- **Watchdog:** 600s timeout

---

## Differences from HKEX Version

| Aspect | HKEX (intl_claude) | US (dev_claude) |
|--------|---------------------|-----------------|
| **Timezone** | Asia/Hong_Kong | America/New_York |
| **Market Hours** | 9:30-12:00, 13:00-16:00 | 9:30-16:00 (continuous) |
| **Lunch Break** | Yes (12:00-13:00) | No |
| **Broker** | Moomoo | Alpaca |
| **Database** | catalyst_intl | catalyst_dev |
| **Stop Loss (Strong)** | -3% | -5% |
| **Take Profit (Strong)** | +8% | +10% |
| **Trailing Stop** | 2% | 3% |
| **Currency** | HKD | USD |

---

## Installation

### Quick Install
```bash
# Upload files to server
scp position_monitor_service.py position-monitor-us.service \
    install-position-monitor-us.sh root@catalyst-dev:/tmp/

# SSH and run installer
ssh root@catalyst-dev
cd /tmp && chmod +x install-position-monitor-us.sh
./install-position-monitor-us.sh
```

### Manual Install
```bash
# 1. Copy Python script
cp position_monitor_service.py /root/catalyst-dev/
chmod +x /root/catalyst-dev/position_monitor_service.py

# 2. Install systemd service
cp position-monitor-us.service /etc/systemd/system/
chmod 644 /etc/systemd/system/position-monitor-us.service

# 3. Apply database schema
psql -h <host> -U <user> -d catalyst_dev -f position_monitor_service_schema.sql

# 4. Enable and start
systemctl daemon-reload
systemctl enable position-monitor-us
systemctl start position-monitor-us
```

---

## Operations

### Service Management
```bash
systemctl start position-monitor-us    # Start
systemctl stop position-monitor-us     # Stop
systemctl restart position-monitor-us  # Restart
systemctl status position-monitor-us   # Status
journalctl -u position-monitor-us -f   # Live logs
```

### Dry Run Testing
```bash
echo "MONITOR_DRY_RUN=true" >> /root/catalyst-dev/.env
systemctl restart position-monitor-us
journalctl -u position-monitor-us -f  # Watch logs (exits logged but not executed)
```

### Health Check
```sql
SELECT * FROM service_health WHERE service_name = 'position_monitor_us';
```

---

## Dependencies

### Python Packages
- `alpaca-py>=0.43.0` - Alpaca broker integration
- `asyncpg>=0.31.0` - PostgreSQL async client
- `anthropic>=0.76.0` - Haiku AI (optional)

### System Requirements
- Python 3.10+
- PostgreSQL (catalyst_dev, catalyst_research)
- Systemd

---

## Statistics Tracked

| Metric | Description |
|--------|-------------|
| `check_count` | Total monitoring cycles |
| `positions_checked` | Total positions analyzed |
| `exits_executed` | Total exits performed |
| `haiku_calls` | Total AI consultations |
| `errors` | Total errors encountered |

---

## Related Documents

- `position-monitor-service-design.md` - HKEX version (original)
- `dev_claude_us_implementation.md` - dev_claude agent design
- `current-architecture.md` - System architecture
- `database-schema.md` - Full database schema

---

*Document created by Claude for the Catalyst Trading System*
