# dev_claude - US Unified Trading Agent

**Version:** 1.0.0
**Last Updated:** 2026-01-16
**Market:** US (NYSE/NASDAQ)
**Broker:** Alpaca (Paper Trading)

## Overview

dev_claude is a unified trading agent for US markets using the single-process architecture (not microservices). It uses the Claude API to make dynamic trading decisions based on market conditions.

## Architecture

```
unified_agent.py          # Main agent with Claude API integration
├── AlpacaClient          # Broker integration (alpaca-py SDK)
├── ToolExecutor          # 12 trading tools
├── ConsciousnessClient   # Inter-agent messaging
└── Database              # Position/order tracking
```

## Files

| File | Purpose |
|------|---------|
| `unified_agent.py` | Main agent (~1,200 lines) |
| `position_monitor.py` | Trade-triggered monitoring |
| `signals.py` | Exit signal detection |
| `startup_monitor.py` | Pre-market reconciliation |
| `config/dev_claude_config.yaml` | Trading parameters |
| `cron.d` | Cron schedule for autonomous trading |
| `.env.example` | Environment template |

## Deployment

```bash
# 1. Create directory and venv
mkdir -p /root/catalyst-dev/{config,logs}
python3 -m venv /root/catalyst-dev/venv
source /root/catalyst-dev/venv/bin/activate

# 2. Install dependencies
pip install anthropic asyncpg pyyaml alpaca-py

# 3. Configure environment
cp .env.example /root/catalyst-dev/.env
# Edit .env with actual credentials

# 4. Copy files
cp unified_agent.py position_monitor.py signals.py startup_monitor.py /root/catalyst-dev/
cp config/dev_claude_config.yaml /root/catalyst-dev/config/

# 5. Test
cd /root/catalyst-dev && source .env
./venv/bin/python3 unified_agent.py --mode heartbeat

# 6. Install cron
cp cron.d /etc/cron.d/catalyst-dev
chmod 644 /etc/cron.d/catalyst-dev
```

## Operating Modes

| Mode | Command | Purpose |
|------|---------|---------|
| scan | `--mode scan` | Pre-market candidate search |
| trade | `--mode trade` | Full trading cycle |
| close | `--mode close` | EOD position review |
| heartbeat | `--mode heartbeat` | Check messages, update status |

## Trading Tools (12)

- `scan_market` - Find trading candidates
- `get_quote` - Current bid/ask
- `get_technicals` - RSI, MACD, MAs
- `detect_patterns` - Chart patterns
- `get_news` - News headlines
- `get_portfolio` - Account status
- `check_risk` - Validate trades
- `execute_trade` - Submit orders
- `close_position` - Close single position
- `close_all` - Emergency close
- `send_alert` - Alert big_bro/Craig
- `log_decision` - Record reasoning

## Schedule (US Eastern Time)

| Time | Mode |
|------|------|
| 08:00 | scan |
| 09:30 | trade (market open) |
| 10:00-15:00 | trade (hourly) |
| 16:00 | close |
| Off-hours | heartbeat (every 3h) |

## Configuration

Key settings in `config/dev_claude_config.yaml`:

```yaml
trading:
  max_positions: 8
  max_position_value: 5000
  stop_loss_pct: 0.05
  take_profit_pct: 0.10
  daily_loss_limit: 2500
```

## Monitoring

```bash
# View logs
tail -f /root/catalyst-dev/logs/trade.log

# Check agent status
cd /root/catalyst-dev && source .env
./venv/bin/python3 unified_agent.py --mode heartbeat

# Check cron
cat /etc/cron.d/catalyst-dev
```
