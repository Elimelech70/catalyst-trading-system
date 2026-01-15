# dev_claude Implementation Summary

**Name of Application:** Catalyst Trading System
**Name of file:** dev_claude_implementation_summary.md
**Version:** 1.0.0
**Last Updated:** 2026-01-15
**Purpose:** Summary of dev_claude unified agent implementation for US markets

---

## Overview

`dev_claude_us_implementation.md` provides the complete implementation package for **dev_claude**, the US sandbox trading agent using a **unified agent architecture** (single-process) instead of the previous microservices approach.

## Architecture Transition

| Component | Old (Microservices) | New (Unified Agent) |
|-----------|---------------------|---------------------|
| Code size | ~5,000+ lines across 10 services | ~1,200 lines single file |
| Decision making | Fixed workflow | Claude API dynamic |
| Broker | Alpaca via HTTP services | Alpaca SDK direct |
| Containers | 10 Docker containers | 1 Python process |
| Complexity | High | Low |

The new architecture follows the proven pattern from `intl_claude` on HKEX markets.

## Key Components

### 1. File Structure
```
/root/catalyst-dev/
├── unified_agent.py          # Main agent (~1,200 lines)
├── config/dev_claude_config.yaml
├── .env                      # Environment variables
├── venv/                     # Python virtual environment
└── logs/                     # Agent logs
```

### 2. Trading Configuration
- **Max positions:** 8
- **Max position value:** $5,000 USD
- **Stop loss:** 5%
- **Take profit:** 10%
- **Daily loss limit:** $2,500
- **Min volume:** 500,000
- **Price range:** $5-$500

### 3. Agent Tools (12 Total)
| Tool | Purpose |
|------|---------|
| `scan_market` | Find trading candidates based on momentum/volume |
| `get_quote` | Get current bid/ask quote |
| `get_technicals` | RSI, MACD, moving averages, ATR |
| `detect_patterns` | Bull/bear flags, breakouts, support/resistance |
| `get_news` | News headlines and sentiment |
| `get_portfolio` | Current cash, equity, positions |
| `check_risk` | Validate trade against risk limits |
| `execute_trade` | Submit market order to Alpaca |
| `close_position` | Close single position |
| `close_all` | Emergency close all positions |
| `send_alert` | Alert big_bro or Craig |
| `log_decision` | Record trading decisions for learning |

### 4. Operating Modes
| Mode | Purpose | When |
|------|---------|------|
| `scan` | Find candidates, analyze, NO trading | Pre-market (08:00 EST) |
| `trade` | Full trading cycle | Market hours (09:30-16:00 EST) |
| `close` | Review positions, close weak setups, EOD report | Market close (16:00 EST) |
| `heartbeat` | Check messages, update status | Off-hours |

### 5. Cron Schedule (EST times, stored as UTC)
- **Pre-market scan:** 08:00 EST (13:00 UTC)
- **Market open trade:** 09:30 EST (14:30 UTC)
- **Hourly trades:** 10:00-15:00 EST
- **EOD close:** 16:00 EST (21:00 UTC)
- **Off-hours heartbeat:** Every 3 hours weekdays, every 6 hours weekends

## Integration Points

### Broker: Alpaca
- Paper trading mode for sandbox
- Direct SDK integration (alpaca-py)
- Market orders with DAY time-in-force

### Database
- **Trading DB:** catalyst_dev (orders, positions, decisions)
- **Research DB:** catalyst_research (consciousness framework)

### Consciousness Framework
- Inter-agent messaging (big_bro, craig)
- Observations and learnings storage
- Budget tracking ($5/day API budget)

## Decision Framework

**Entry Criteria:**
- RSI between 30-70 (not overbought/oversold)
- Price above SMA 10
- Clear pattern (breakout, support bounce)
- Risk check passes

**Exit Criteria:**
- Stop loss hit (-5%)
- Take profit hit (+10%)
- Pattern breakdown
- RSI > 80 (overbought)

## Key Differences from intl_claude (HKEX)

| Aspect | intl_claude (HKEX) | dev_claude (US) |
|--------|-------------------|-----------------|
| Broker | Moomoo/OpenD | Alpaca |
| Market | HKEX (HKT) | NYSE/NASDAQ (EST) |
| Currency | HKD | USD |
| Lot size | 100+ (varies) | 1 (no minimum) |
| Market hours | 09:30-12:00, 13:00-16:00 HKT | 09:30-16:00 EST |
| Lunch break | Yes (12:00-13:00) | No |

## Deployment Checklist

- [ ] Create `/root/catalyst-dev/` directory structure
- [ ] Set up Python virtual environment
- [ ] Install dependencies: `anthropic asyncpg pyyaml alpaca-py`
- [ ] Configure `.env` with API keys and database URLs
- [ ] Create `config/dev_claude_config.yaml`
- [ ] Deploy `unified_agent.py`
- [ ] Test with `--mode heartbeat`
- [ ] Install cron schedule in `/etc/cron.d/catalyst-dev`
- [ ] Verify logs directory is writable

## Next Steps

1. **Deploy to US droplet** - Follow deployment instructions
2. **Test paper trading** - Verify Alpaca connectivity
3. **Monitor initial cycles** - Check logs for issues
4. **Tune parameters** - Adjust based on performance
5. **Enable consciousness** - Connect to research database

---

*Summary generated: 2026-01-15*
*Source document: dev_claude_us_implementation.md v1.0.0*
