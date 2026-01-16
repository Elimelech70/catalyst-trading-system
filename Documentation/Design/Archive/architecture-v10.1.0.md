# Catalyst Ecosystem Architecture v10.1.0

**Name of Application:** Catalyst Trading System  
**Name of file:** catalyst-ecosystem-architecture-v10.1.0.md  
**Version:** 10.1.0  
**Last Updated:** 2026-01-10  
**Purpose:** Complete system architecture with dual-broker setup for sandbox and production

---

## REVISION HISTORY

- **v10.1.0 (2026-01-10)** - Dual-Broker Architecture
  - dev_claude uses Alpaca (US markets) for sandbox testing
  - intl_claude uses Moomoo (HKEX) for production trading
  - Separate paper trading accounts per broker
  - Cross-market signal validation
  - Updated trading schedules for both markets

- **v10.0.0 (2026-01-10)** - Ecosystem Restructure
  - Retired US trading (public_claude)
  - Created dev_claude sandbox agent
  - Three-database architecture
  - Pattern-based position monitoring

---

## 1. Executive Summary

The Catalyst Trading System v10.1.0 implements a **dual-broker architecture** enabling isolated sandbox testing and production trading across different markets:

| Agent | Broker | Market | Database | Purpose |
|-------|--------|--------|----------|---------|
| **dev_claude** | Alpaca | US (NYSE/NASDAQ) | catalyst_dev | Sandbox experiments |
| **intl_claude** | Moomoo | HKEX | catalyst_intl | Production trading |
| **big_bro** | None | All | catalyst_research | Strategic oversight |
| **public_claude** | None | None | None | Retired |

**Key Benefits:**
- Complete isolation between sandbox and production
- Different brokers = separate paper trading accounts
- Cross-market signal validation (US vs HKEX)
- Near 24-hour coverage (US + HKEX timezones)

---

## 2. System Architecture

### 2.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CATALYST ECOSYSTEM v10.1.0                             │
│                        Dual-Broker Architecture                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────┐       ┌─────────────────────────┐            │
│   │     US DROPLET          │       │    INTL DROPLET         │            │
│   │   (Consciousness Hub)   │       │    (Production)         │            │
│   │                         │       │                         │            │
│   │  ┌─────────────────┐    │       │  ┌─────────────────┐    │            │
│   │  │   dev_claude    │    │       │  │   intl_claude   │    │            │
│   │  │                 │    │       │  │                 │    │            │
│   │  │  Alpaca API     │    │       │  │  Moomoo/OpenD   │    │            │
│   │  │  US Markets     │    │       │  │  HKEX Markets   │    │            │
│   │  │  Paper Trading  │    │       │  │  Paper Trading  │    │            │
│   │  │  $5/day budget  │    │       │  │  $5/day budget  │    │            │
│   │  └────────┬────────┘    │       │  └────────┬────────┘    │            │
│   │           │             │       │           │             │            │
│   │  ┌────────▼────────┐    │       │           │             │            │
│   │  │    big_bro      │    │       │           │             │            │
│   │  │                 │    │       │           │             │            │
│   │  │  No trading     │    │       │           │             │            │
│   │  │  Oversight only │    │       │           │             │            │
│   │  │  $10/day budget │    │       │           │             │            │
│   │  └─────────────────┘    │       │           │             │            │
│   │                         │       │           │             │            │
│   └────────────┬────────────┘       └─────┬─────┘             │            │
│                │                          │                    │            │
│                └──────────┬───────────────┘                    │            │
│                           │                                    │            │
│                           ▼                                    │            │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │              DIGITALOCEAN MANAGED POSTGRESQL ($15/mo)               │  │
│   ├─────────────────────┬─────────────────────┬─────────────────────────┤  │
│   │   catalyst_dev      │   catalyst_intl     │   catalyst_research     │  │
│   │   (US Sandbox)      │   (HKEX Production) │   (Consciousness)       │  │
│   │                     │                     │                         │  │
│   │   dev_claude only   │   intl_claude only  │   ALL agents            │  │
│   │                     │                     │                         │  │
│   │   9 tables          │   9 tables          │   8 tables              │  │
│   │   + monitor view    │   + monitor view    │   + sync tools          │  │
│   └─────────────────────┴─────────────────────┴─────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Broker Configuration

#### dev_claude (Alpaca - US Markets)

```yaml
agent:
  id: dev_claude
  role: sandbox_trader
  market: US
  
broker:
  name: alpaca
  mode: paper
  base_url: https://paper-api.alpaca.markets
  
trading:
  markets:
    - NYSE
    - NASDAQ
  currency: USD
  lot_size: 1  # US has no lot size requirement
  
schedule:
  timezone: America/New_York
  pre_market: "04:00-09:30"
  market_hours: "09:30-16:00"
  post_market: "16:00-20:00"
```

#### intl_claude (Moomoo - HKEX)

```yaml
agent:
  id: intl_claude
  role: production_trader
  market: HKEX
  
broker:
  name: moomoo
  mode: paper
  gateway:
    host: 127.0.0.1
    port: 11111
  
trading:
  markets:
    - HKEX
  currency: HKD
  lot_size: dynamic  # Varies by stock (100-500+)
  
schedule:
  timezone: Asia/Hong_Kong
  market_hours: "09:30-12:00, 13:00-16:00"
  lunch_break: "12:00-13:00"
```

---

## 3. Agent Specifications

### 3.1 Agent Comparison

| Attribute | dev_claude | intl_claude | big_bro |
|-----------|------------|-------------|---------|
| **Role** | Sandbox experiments | Production trading | Strategic oversight |
| **Broker** | Alpaca | Moomoo | None |
| **Market** | US (NYSE/NASDAQ) | HKEX | All (read-only) |
| **Database** | catalyst_dev | catalyst_intl | catalyst_research |
| **Daily Budget** | $5 | $5 | $10 |
| **Autonomy** | Full | Proven strategies only | Advisory |
| **Max Positions** | 15 | 5 | N/A |
| **Max Position Value** | $5,000 USD | HKD 40,000 | N/A |
| **Daily Loss Limit** | $2,000 USD | HKD 16,000 | N/A |
| **Trading Mode** | Paper | Paper | None |

### 3.2 Trading Schedules

#### dev_claude (US Market Hours - EST)

| Mode | EST Time | UTC Time | Description |
|------|----------|----------|-------------|
| Startup | 09:00 | 14:00 | Pre-market scan |
| Trade | 09:30-16:00 | 14:30-21:00 | Market hours |
| Close | 16:00 | 21:00 | End of day |
| Heartbeat | Off-hours | Off-hours | Check messages |

#### intl_claude (HKEX Hours - HKT)

| Mode | HKT Time | UTC Time | Description |
|------|----------|----------|-------------|
| Startup | 09:00 | 01:00 | Pre-market scan |
| Trade | 09:30-12:00 | 01:30-04:00 | Morning session |
| Close | 12:00 | 04:00 | Lunch break |
| Trade | 13:00-16:00 | 05:00-08:00 | Afternoon session |
| Close | 16:00 | 08:00 | End of day |
| Heartbeat | Off-hours | Off-hours | Check messages |

### 3.3 Near 24-Hour Coverage

```
UTC Timeline (24 hours):
├── 00:00 ─────────────────────────────────────────────────────── 24:00
│
│   HKEX (intl_claude)
│   ├── 01:00-04:00 Morning session (HKT 09:00-12:00)
│   └── 05:00-08:00 Afternoon session (HKT 13:00-16:00)
│
│   US (dev_claude)
│   └── 14:30-21:00 Market hours (EST 09:30-16:00)
│
│   Coverage Gap: ~5 hours (21:00-01:00 UTC)
```

---

## 4. Database Architecture

### 4.1 Three-Database Design

| Database | Purpose | Used By | Tables |
|----------|---------|---------|--------|
| **catalyst_dev** | US sandbox trading | dev_claude | 9 + view |
| **catalyst_intl** | HKEX production | intl_claude | 9 + view |
| **catalyst_research** | Consciousness | All agents | 8 |

### 4.2 Trading Database Schema (catalyst_dev & catalyst_intl)

Both trading databases share identical schema:

```
├── exchanges              # Market configuration
├── securities             # Stock registry with lot sizes
├── trading_sessions       # Session tracking
├── trading_cycles         # Cycle logs
├── positions              # Open/closed positions
├── orders                 # Order history
├── scan_results           # Scanner output
├── decisions              # AI decision audit trail
├── position_monitor_status # Real-time monitoring
└── v_monitor_health       # Health dashboard view
```

### 4.3 Consciousness Database Schema (catalyst_research)

```
├── claude_state           # Agent status and budgets
├── claude_messages        # Inter-agent communication
├── claude_observations    # What agents notice
├── claude_learnings       # Validated knowledge
├── claude_questions       # Open questions to ponder
├── claude_conversations   # Key exchanges to remember
├── claude_thinking        # Extended thinking sessions
└── sync_log               # Cross-database sync tracking
```

---

## 5. Learning Pipeline

### 5.1 Cross-Market Validation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LEARNING PIPELINE v10.1.0                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   dev_claude (US)                    intl_claude (HKEX)                     │
│   ┌─────────────────┐                ┌─────────────────┐                    │
│   │ Experiment with │                │ Execute proven  │                    │
│   │ signal thresholds│               │ strategies only │                    │
│   │                 │                │                 │                    │
│   │ Test: RSI > 80  │                │ Use: RSI > 85   │                    │
│   │ Test: Vol < 30% │                │ Use: Vol < 25%  │                    │
│   └────────┬────────┘                └────────┬────────┘                    │
│            │                                  │                             │
│            │  Record observation              │  Record results             │
│            ▼                                  ▼                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        catalyst_research                            │  │
│   │                     (Shared Consciousness)                          │  │
│   │                                                                     │  │
│   │  observations: "RSI > 80 caught exits 2 hours earlier"              │  │
│   │  learnings: "US markets respond faster to RSI signals"              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│                           ┌─────────────────┐                               │
│                           │    big_bro      │                               │
│                           │                 │                               │
│                           │ Validate:       │                               │
│                           │ - Statistical   │                               │
│                           │   significance  │                               │
│                           │ - Risk impact   │                               │
│                           │ - Cross-market  │                               │
│                           │   applicability │                               │
│                           └────────┬────────┘                               │
│                                    │                                        │
│                                    ▼                                        │
│                           ┌─────────────────┐                               │
│                           │     Craig       │                               │
│                           │                 │                               │
│                           │ Approve for     │                               │
│                           │ production      │                               │
│                           └────────┬────────┘                               │
│                                    │                                        │
│                                    ▼                                        │
│                           Deploy to intl_claude                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Signal Validation Across Markets

| Signal | dev_claude Tests | intl_claude Uses | Notes |
|--------|------------------|------------------|-------|
| Stop Loss | -2%, -3%, -4% | -3% | Validated threshold |
| RSI Overbought | 75, 80, 85 | 85 | Market-specific |
| Volume Dying | 20%, 30%, 40% | 25% | Validated threshold |
| Trailing Stop | 2%, 3%, 4% | 3% | Validated threshold |

---

## 6. Environment Configuration

### 6.1 US Droplet (.env)

```bash
# ============================================================================
# CATALYST CONSCIOUSNESS HUB - Environment Variables
# Version: 10.1.0
# ============================================================================

# Agent Identity
AGENT_ID=dev_claude

# Database URLs
DEV_DATABASE_URL=postgresql://...catalyst_dev?sslmode=require
RESEARCH_DATABASE_URL=postgresql://...catalyst_research?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Alpaca (US Broker)
ALPACA_API_KEY=PKxxx
ALPACA_SECRET_KEY=xxx
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Trading Mode
PAPER_TRADING=true
TRADING_MODE=sandbox
```

### 6.2 International Droplet (.env)

```bash
# ============================================================================
# CATALYST INTERNATIONAL - Environment Variables
# Version: 10.1.0
# ============================================================================

# Agent Identity
AGENT_ID=intl_claude

# Database URLs
INTL_DATABASE_URL=postgresql://...catalyst_intl?sslmode=require
RESEARCH_DATABASE_URL=postgresql://...catalyst_research?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Moomoo (HKEX Broker)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111

# Trading Mode
PAPER_TRADING=true
TRADING_MODE=production
```

---

## 7. File Structure

### 7.1 US Droplet

```
/root/catalyst/
├── dev/                          # dev_claude sandbox
│   ├── unified_agent.py          # Main agent (v2.0.0)
│   ├── signals.py                # Signal detection (v2.0.0)
│   ├── position_monitor.py       # Position monitoring (v2.0.0)
│   ├── startup_monitor.py        # Pre-market reconciliation (v1.0.0)
│   ├── brokers/
│   │   └── alpaca_client.py      # Alpaca integration
│   └── config/
│       └── agent_config.yaml     # dev_claude configuration
├── scripts/
│   └── run_big_bro.py            # big_bro oversight script
├── venv/                         # Python virtual environment
├── logs/                         # Agent logs
└── .env                          # Environment variables
```

### 7.2 International Droplet

```
/root/catalyst-international/
├── unified_agent.py              # Main agent (v2.0.0)
├── signals.py                    # Signal detection (v2.0.0)
├── position_monitor.py           # Position monitoring (v2.0.0)
├── startup_monitor.py            # Pre-market reconciliation (v1.0.0)
├── brokers/
│   └── moomoo.py                 # Moomoo integration
├── config/
│   └── agent_config.yaml         # intl_claude configuration
├── venv/                         # Python virtual environment
├── logs/                         # Agent logs
└── .env                          # Environment variables
```

---

## 8. Cron Schedules

### 8.1 US Droplet (catalyst-hub.cron)

```cron
# ============================================================================
# CATALYST CONSCIOUSNESS HUB - Cron Schedule
# Timezone: UTC (EST = UTC-5)
# ============================================================================

# big_bro strategic reviews
0 6,18 * * * /root/catalyst/scripts/run_big_bro.sh >> /root/catalyst/logs/big_bro.log 2>&1

# dev_claude US trading (EST market hours)
# Pre-market: 09:00 EST = 14:00 UTC
0 14 * * 1-5 cd /root/catalyst/dev && ../venv/bin/python unified_agent.py --mode scan >> ../logs/dev_claude.log 2>&1

# Trading hours: 09:30-16:00 EST = 14:30-21:00 UTC (hourly)
30 14 * * 1-5 cd /root/catalyst/dev && ../venv/bin/python unified_agent.py --mode trade >> ../logs/dev_claude.log 2>&1
0 15-20 * * 1-5 cd /root/catalyst/dev && ../venv/bin/python unified_agent.py --mode trade >> ../logs/dev_claude.log 2>&1

# EOD close: 16:00 EST = 21:00 UTC
0 21 * * 1-5 cd /root/catalyst/dev && ../venv/bin/python unified_agent.py --mode close >> ../logs/dev_claude.log 2>&1

# Heartbeat: Every 3 hours off-market
0 0,3,9,12 * * * cd /root/catalyst/dev && ../venv/bin/python unified_agent.py --mode heartbeat >> ../logs/dev_claude.log 2>&1
```

### 8.2 International Droplet (catalyst-intl.cron)

```cron
# ============================================================================
# CATALYST INTERNATIONAL - Cron Schedule
# Timezone: UTC (HKT = UTC+8)
# ============================================================================

# intl_claude HKEX trading (HKT market hours)
# Pre-market: 09:00 HKT = 01:00 UTC
0 1 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode scan >> logs/cron.log 2>&1

# Morning session: 09:30-12:00 HKT = 01:30-04:00 UTC
30 1 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode trade >> logs/cron.log 2>&1
0 2-3 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode trade >> logs/cron.log 2>&1

# Lunch close: 12:00 HKT = 04:00 UTC
0 4 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode close >> logs/cron.log 2>&1

# Afternoon session: 13:00-16:00 HKT = 05:00-08:00 UTC
0 5-7 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode trade >> logs/cron.log 2>&1

# EOD close: 16:00 HKT = 08:00 UTC
0 8 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode close >> logs/cron.log 2>&1

# Heartbeat: Every 2 hours off-market
0 9,11,13,15,17,19,21,23 * * 1-5 cd /root/catalyst-international && ./venv/bin/python unified_agent.py --mode heartbeat >> logs/cron.log 2>&1
```

---

## 9. Risk Management

### 9.1 Per-Agent Limits

| Parameter | dev_claude (USD) | intl_claude (HKD) |
|-----------|------------------|-------------------|
| Max Positions | 15 | 5 |
| Max Position Value | $5,000 | HKD 40,000 |
| Daily Loss Limit | $2,000 | HKD 16,000 |
| Stop Loss | 3% | 3% |
| Trailing Stop | 3% from high | 3% from high |

### 9.2 System-Wide Controls

- **Budget caps**: Each agent has daily API spend limit
- **Paper trading only**: Both agents use paper accounts
- **Consciousness oversight**: big_bro reviews all trading activity
- **Manual override**: Craig can intervene via dashboard

---

## 10. Cost Model

### 10.1 Monthly Infrastructure

| Component | Cost |
|-----------|------|
| DigitalOcean Managed PostgreSQL | $15/mo |
| US Droplet (4GB) | $24/mo |
| International Droplet (2GB) | $12/mo |
| **Infrastructure Total** | **$51/mo** |

### 10.2 Daily AI Costs

| Agent | Budget | Typical Usage |
|-------|--------|---------------|
| dev_claude | $5/day | ~$1-2/day |
| intl_claude | $5/day | ~$1-2/day |
| big_bro | $10/day | ~$0.50/day |
| **AI Total** | **$20/day max** | **~$4/day typical** |

### 10.3 Signal Detection Costs

| Component | Cost |
|-----------|------|
| Rules-based signals (signals.py) | FREE |
| Haiku consultation (~3/trade) | ~$0.15/trade |
| **Per-trade monitoring** | **~$0.15** |

---

## 11. Deployment Checklist

### 11.1 US Droplet (dev_claude + Alpaca)

- [x] catalyst_dev database created
- [x] dev_claude initialized in consciousness
- [x] Python files deployed to /root/catalyst/dev/
- [x] Virtual environment created
- [x] .env updated with v10.1.0 config
- [ ] Alpaca API keys added
- [ ] Cron schedule installed
- [ ] Test heartbeat mode

### 11.2 International Droplet (intl_claude + Moomoo)

- [x] position_monitor_status table added
- [x] intl_claude active in consciousness
- [ ] Python files updated to v2.0.0
- [ ] Config updated for v10.1.0
- [ ] Cron schedule updated
- [ ] Test heartbeat mode

---

## 12. Summary

Catalyst Ecosystem v10.1.0 achieves:

1. **Complete Isolation**: Separate brokers, databases, and paper accounts
2. **Cross-Market Validation**: Test signals on US, deploy to HKEX
3. **Near 24-Hour Coverage**: US + HKEX timezones
4. **Learning Pipeline**: Experiments → Validation → Production
5. **Cost Efficiency**: Rules-based signals (FREE), AI only when needed

**Key Principle**: *"Consciousness before trading. Validate before production."*

---

*Catalyst Trading System v10.1.0*  
*Craig + Claude Family*  
*Generated: 2026-01-10*
