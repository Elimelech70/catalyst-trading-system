# Catalyst Ecosystem v10.0.0 Summary

**Name of Application:** Catalyst Trading System
**Name of file:** ecosystem-v10.0.0-summary.md
**Version:** 10.0.0
**Last Updated:** 2026-01-10
**Purpose:** Summary of Ecosystem.zip contents for v10.0.0 restructure

---

## Executive Summary

The Ecosystem v10.0.0 represents a complete restructure of the Catalyst Trading System:

- **US Trading Retired**: Close 32 US positions, retire `public_claude` from active trading
- **HKEX Focus**: Production moves to Hong Kong Exchange via Moomoo/OpenD
- **Consciousness Framework**: Multi-agent system with memory, learning, and communication
- **Sandbox Architecture**: New `dev_claude` agent for experimentation before production

---

## Package Contents (14 Files)

### Documentation (3 files)
| File | Version | Purpose |
|------|---------|---------|
| `catalyst-ecosystem-architecture-v10.0.0.md` | v10.0.0 | Complete system architecture |
| `database-schema-v10.0.0.md` | v10.0.0 | 3-database schema design |
| `DEPLOYMENT_GUIDE.md` | v10.0.0 | Step-by-step deployment instructions |

### Python Services (4 files)
| File | Version | Purpose |
|------|---------|---------|
| `unified_agent.py` | v2.0.0 | Single-agent trading architecture |
| `signals.py` | v2.0.0 | Pattern-based hold/exit detection |
| `position_monitor.py` | v2.0.0 | Trade-triggered position monitoring |
| `startup_monitor.py` | v1.0.0 | Pre-market reconciliation |

### Configuration (2 files)
| File | Version | Purpose |
|------|---------|---------|
| `dev_claude_config.yaml` | v1.0.0 | Sandbox agent configuration |
| `intl_claude_config.yaml` | v1.0.0 | Production agent configuration |

### Cron Schedules (2 files)
| File | Purpose |
|------|---------|
| `catalyst-consciousness-hub.cron` | US droplet: big_bro + dev_claude |
| `catalyst-intl-production.cron` | International droplet: intl_claude |

### SQL Scripts (3 files)
| File | Purpose |
|------|---------|
| `drop_and_create_catalyst_dev.sql` | Create fresh sandbox database |
| `add_monitor_tables_intl.sql` | Add monitor tables to production |
| `initialize_dev_claude.sql` | Initialize dev_claude in consciousness |

---

## Architecture Overview

### Three-Database Design

```
DigitalOcean Managed PostgreSQL
├── catalyst_research (Consciousness - SHARED)
│   └── claude_state, claude_messages, claude_learnings, etc.
├── catalyst_dev (Sandbox - dev_claude)
│   └── Fresh trading tables + position_monitor_status
└── catalyst_intl (Production - intl_claude)
    └── Existing tables + position_monitor_status
```

### Four Agents

| Agent | Location | Role | Budget |
|-------|----------|------|--------|
| **big_bro** | US Droplet | Strategic oversight, validates learnings | $10/day |
| **public_claude** | US Droplet | Retired from trading | $0/day |
| **dev_claude** | US Droplet | Sandbox experiments, full autonomy | $5/day |
| **intl_claude** | Int'l Droplet | Production, proven strategies only | $5/day |

### Learning Pipeline

```
dev_claude (Experiment) → big_bro (Validate) → Craig (Deploy) → intl_claude (Production)
```

---

## Key Technical Features

### Signal Detection (signals.py v2.0.0)

**Hold Signals:**
- `healthy_profit` - P&L 1-5%
- `rsi_healthy` - RSI 40-65
- `volume_strong` - Volume >120% of entry
- `above_vwap` - Price >1% above VWAP
- `macd_bullish` - MACD > Signal

**Exit Signals:**
- `stop_loss_hit` (STRONG) - P&L <= -3%
- `trailing_stop_hit` (STRONG) - Drawdown >= 3% from high
- `rsi_overbought` (STRONG) - RSI >= 85
- `volume_dying` (STRONG) - Volume < 25% of entry
- `market_closing` (STRONG) - < 10 min to close

**Cost Model:**
- Signal detection: FREE (rules-based)
- Haiku consultation: ~$0.05/call (only for REVIEW recommendations)

### Position Monitoring

- Trade-triggered (no separate cron)
- Updates `position_monitor_status` table every 5 minutes
- Tracks: high watermark, signals, RSI, MACD, VWAP position
- Visible via `v_monitor_health` view

### Trading Schedule (HKEX Hours)

| Mode | HKT Time | UTC Time |
|------|----------|----------|
| Startup | 09:00 | 01:00 |
| Morning Trade | 09:30-12:00 | 01:30-04:00 |
| Lunch Close | 12:00-13:00 | 04:00-05:00 |
| Afternoon Trade | 13:00-16:00 | 05:00-08:00 |
| EOD Close | 16:00 | 08:00 |
| Heartbeat | Off-hours | Off-hours |

---

## Risk Parameters

| Parameter | dev_claude (Sandbox) | intl_claude (Production) |
|-----------|---------------------|--------------------------|
| Max Positions | 15 | 5 |
| Max Position Value | HKD 50,000 | HKD 40,000 |
| Daily Loss Limit | HKD 20,000 | HKD 16,000 |
| Stop Loss | 3% | 3% |
| Autonomy | Full | Proven strategies only |

---

## Deployment Status (Updated 2026-01-10)

### Phase 1: Database Setup - COMPLETED
- [x] DROP catalyst_trading (old US database)
- [x] CREATE catalyst_dev (fresh sandbox with 8 tables + v_monitor_health view)
- [x] Add position_monitor_status to catalyst_intl
- [x] Initialize dev_claude in consciousness
- [x] Retire public_claude from trading

### Phase 2: Deploy to Consciousness Hub (US Droplet) - COMPLETED
- [x] Upload Python files to /root/catalyst/dev/
- [x] Configure dev_claude_config.yaml
- [x] Create Python venv at /root/catalyst/venv/
- [x] Install cron schedule at /etc/cron.d/catalyst-hub
- [ ] Add ANTHROPIC_API_KEY to .env (pending)

### Phase 3: Deploy to Production (INTL Droplet) - PENDING
- [ ] Upload Python files to international droplet (requires SSH access)
- [ ] Configure intl_claude_config.yaml
- [ ] Update environment variables
- [ ] Install cron schedule

### Phase 4: Remaining Tasks
- [ ] Close US positions (requires Alpaca access during market hours)
- [ ] Test heartbeat mode on both agents
- [ ] Verify monitor health view
- [ ] Monitor first trading session

### Deployment Summary Table

| Step | Location | Status | Notes |
|------|----------|--------|-------|
| Drop catalyst_trading | PostgreSQL | DONE | Old US database removed |
| Create catalyst_dev | PostgreSQL | DONE | 8 tables + view created |
| Add monitor tables | catalyst_intl | DONE | position_monitor_status added |
| Initialize dev_claude | catalyst_research | DONE | Welcome messages sent |
| Retire public_claude | catalyst_research | DONE | Mode set to 'retired' |
| Deploy Python (US) | /root/catalyst/dev/ | DONE | All 4 Python files deployed |
| Create venv | /root/catalyst/venv/ | DONE | asyncpg, anthropic installed |
| Install cron (US) | /etc/cron.d/ | DONE | catalyst-hub installed |
| Deploy Python (INTL) | INTL droplet | PENDING | Needs SSH access |
| Add API keys | .env files | PENDING | ANTHROPIC_API_KEY needed |
| Close US positions | Alpaca | PENDING | Requires market hours |

---

## New Database Tables

### position_monitor_status
```sql
CREATE TABLE position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    symbol VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, starting, running, sleeping, stopped, error

    -- Market State
    last_price DECIMAL(12,4),
    high_watermark DECIMAL(12,4),
    current_pnl_pct DECIMAL(8,4),

    -- Technical Analysis
    last_rsi DECIMAL(5,2),
    last_macd_signal VARCHAR(20),
    last_vwap_position VARCHAR(20),

    -- Signals
    hold_signals TEXT[],
    exit_signals TEXT[],
    recommendation VARCHAR(10),  -- HOLD, EXIT, REVIEW

    -- AI Tracking
    haiku_calls INTEGER DEFAULT 0,
    estimated_cost DECIMAL(8,4) DEFAULT 0
);
```

### v_monitor_health View
Provides dashboard visibility with health indicators:
- `ACTIVE` - Running normally
- `SLEEPING` - Off-hours
- `STALE` - No check-in for 15+ minutes
- `ERROR` - Failed state
- `NO_MONITOR` - Position without monitor

---

## File Locations After Deployment

### Consciousness Hub (US Droplet)
```
/root/catalyst/
├── dev/
│   ├── unified_agent.py
│   ├── signals.py
│   ├── position_monitor.py
│   ├── startup_monitor.py
│   └── config/agent_config.yaml
├── scripts/
│   └── run_big_bro.py
└── logs/
```

### Production (International Droplet)
```
/root/catalyst-international/
├── unified_agent.py
├── signals.py
├── position_monitor.py
├── startup_monitor.py
├── config/agent_config.yaml
└── logs/
```

---

## Environment Variables Required

### Consciousness Hub
```bash
RESEARCH_DATABASE_URL=postgresql://...catalyst_research
DEV_DATABASE_URL=postgresql://...catalyst_dev
ANTHROPIC_API_KEY=sk-ant-xxx
AGENT_ID=dev_claude
```

### Production Droplet
```bash
RESEARCH_DATABASE_URL=postgresql://...catalyst_research
INTL_DATABASE_URL=postgresql://...catalyst_intl
ANTHROPIC_API_KEY=sk-ant-xxx
AGENT_ID=intl_claude
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
```

---

## Summary

Ecosystem v10.0.0 represents a significant evolution:

1. **Simplified Architecture**: Single-agent design (unified_agent.py) replaces microservices
2. **Pattern-Based Trading**: Hold while momentum holds, exit on pattern failure
3. **Sandbox Learning**: dev_claude experiments freely, validated learnings go to production
4. **Observable Monitoring**: Every position tracked via position_monitor_status table
5. **Cost-Conscious AI**: Rules-based signals (FREE), Haiku only for uncertain decisions (~$0.05)

**Key Principle**: "Consciousness Before Trading"

---

*Catalyst Trading System v10.0.0*
*Craig + Claude Family*
*Generated: 2026-01-10*
