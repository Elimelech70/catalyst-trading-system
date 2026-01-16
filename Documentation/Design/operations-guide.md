# Catalyst Trading System - Operations Guide

**Name of Application:** Catalyst Trading System  
**Name of File:** operations-guide.md  
**Version:** 1.0.0  
**Last Updated:** 2026-01-06  
**Purpose:** Complete operational workflows for all system components

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Daily Operations Schedule](#2-daily-operations-schedule)
3. [HKEX Trading Workflows](#3-hkex-trading-workflows)
4. [US Trading Workflows](#4-us-trading-workflows)
5. [Consciousness Framework](#5-consciousness-framework)
6. [Position Monitoring](#6-position-monitoring)
7. [Command Reference](#7-command-reference)
8. [Troubleshooting](#8-troubleshooting)
9. [Emergency Procedures](#9-emergency-procedures)

---

## 1. System Overview

### 1.1 Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CATALYST TRADING SYSTEM ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐           │
│  │  PUBLIC_CLAUDE  │   │  INTL_CLAUDE    │   │    BIG_BRO      │           │
│  │                 │   │                 │   │                 │           │
│  │  US Markets     │   │  HKEX Markets   │   │  Strategic      │           │
│  │  NYSE/NASDAQ    │   │  Hong Kong      │   │  Oversight      │           │
│  │  Alpaca API     │   │  Moomoo/OpenD   │   │  Coordination   │           │
│  │  $5/day budget  │   │  $5/day budget  │   │  $10/day budget │           │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘           │
│           │                     │                     │                     │
│           └─────────────────────┼─────────────────────┘                     │
│                                 │                                           │
│                    ┌────────────▼────────────┐                              │
│                    │   CONSCIOUSNESS DB      │                              │
│                    │   (catalyst_research)   │                              │
│                    │                         │                              │
│                    │  • claude_state         │                              │
│                    │  • claude_messages      │                              │
│                    │  • claude_observations  │                              │
│                    │  • claude_learnings     │                              │
│                    │  • claude_questions     │                              │
│                    └─────────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Infrastructure

| Component | Location | Cost |
|-----------|----------|------|
| International Droplet | 137.184.244.45 | $6/mo |
| US Droplet | TBD | $6/mo |
| PostgreSQL (Managed) | DigitalOcean | $15/mo |
| Claude API | Anthropic | ~$15-25/mo |
| Moomoo Data | Included | $0 |
| **Total** | | **~$42-52/mo** |

### 1.3 Databases

| Database | Purpose | Tables |
|----------|---------|--------|
| `catalyst_trading` | US trading operations | positions, orders, decisions |
| `catalyst_intl` | HKEX trading operations | positions, orders, decisions |
| `catalyst_research` | Consciousness framework | claude_state, claude_messages, etc. |

---

## 2. Daily Operations Schedule

### 2.1 Combined Timeline (All Times in UTC)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DAILY OPERATIONS TIMELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  UTC     HKT      EST      EVENT                                            │
│  ─────   ─────    ─────    ────────────────────────────────────────────    │
│  01:30   09:30    20:30    HKEX Morning Session Opens                       │
│                            → intl_claude agent cycle runs                   │
│                            → Scan market, analyze, trade                    │
│                                                                             │
│  04:00   12:00    23:00    HKEX Lunch Break Starts                          │
│                            → Close positions (unless high conviction)       │
│                            → No trading 12:00-13:00 HKT                     │
│                                                                             │
│  05:00   13:00    00:00    HKEX Afternoon Session Opens                     │
│                            → intl_claude agent cycle runs                   │
│                            → Position monitoring continues                  │
│                                                                             │
│  08:00   16:00    03:00    HKEX Market Closes                               │
│                            → All positions reviewed                         │
│                            → Position monitor exits remaining               │
│                                                                             │
│  13:30   21:30    08:30    US Pre-Market Opens                              │
│                            → public_claude wakes (if enabled)               │
│                                                                             │
│  14:30   22:30    09:30    US Market Opens                                  │
│                            → public_claude trading cycle                    │
│                                                                             │
│  21:00   05:00    16:00    US Market Closes                                 │
│                            → End of day reporting                           │
│                                                                             │
│  22:00   06:00    17:00    big_bro Strategic Review                         │
│                            → Analyze both markets                           │
│                            → Update questions, learnings                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 HKEX Cron Schedule

```cron
# Morning session start (09:30 HKT = 01:30 UTC)
30 1 * * 1-5 cd /root/Catalyst-Trading-System-International/catalyst-international && ./venv/bin/python3 agent.py >> logs/cron.log 2>&1

# Afternoon session start (13:00 HKT = 05:00 UTC)
0 5 * * 1-5 cd /root/Catalyst-Trading-System-International/catalyst-international && ./venv/bin/python3 agent.py >> logs/cron.log 2>&1
```

### 2.3 US Cron Schedule (When Enabled)

```cron
# US Market open (09:30 ET = 14:30 UTC)
30 14 * * 1-5 cd /root/catalyst-trading-system && ./scripts/trigger-workflow.sh >> logs/workflow.log 2>&1

# Intraday cycles (every 30 min during market hours)
0,30 15-20 * * 1-5 cd /root/catalyst-trading-system && ./scripts/trigger-workflow.sh >> logs/workflow.log 2>&1
```

---

## 3. HKEX Trading Workflows

### 3.1 Agent Cycle Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INTL_CLAUDE TRADING CYCLE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CRON TRIGGER (01:30 or 05:00 UTC)                                         │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. BUILD CONTEXT                                                     │   │
│  │    • Load current portfolio (get_portfolio)                          │   │
│  │    • Check market hours                                              │   │
│  │    • Initialize cycle ID                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 2. CALL CLAUDE API                                                   │   │
│  │    • Send SYSTEM_PROMPT + context                                    │   │
│  │    • Provide 12 trading tools                                        │   │
│  │    • Claude decides actions                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 3. TOOL EXECUTION LOOP                                               │   │
│  │                                                                       │   │
│  │    Claude requests: scan_market                                       │   │
│  │         │                                                             │   │
│  │         ▼                                                             │   │
│  │    For each candidate:                                                │   │
│  │         │                                                             │   │
│  │         ├── get_quote → Current price                                 │   │
│  │         ├── get_technicals → RSI, MACD, support/resistance            │   │
│  │         ├── detect_patterns → Breakout, bull flag, etc.               │   │
│  │         ├── get_news → Catalysts, sentiment                           │   │
│  │         │                                                             │   │
│  │         ▼                                                             │   │
│  │    Evaluate against TIERED CRITERIA:                                  │   │
│  │         │                                                             │   │
│  │         ├── Tier 1: Volume >2x, RSI 30-70, Pattern AND Catalyst       │   │
│  │         ├── Tier 2: Volume >1.5x, Pattern OR Catalyst                 │   │
│  │         └── Tier 3: Volume >1.3x, Momentum >3%                        │   │
│  │                                                                       │   │
│  │    If criteria met:                                                   │   │
│  │         │                                                             │   │
│  │         ├── check_risk → Validate trade                               │   │
│  │         └── execute_trade → Place order via Moomoo                    │   │
│  │                  │                                                    │   │
│  │                  ▼                                                    │   │
│  │         POSITION MONITOR STARTS (if BUY)                              │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 4. LOG & COMPLETE                                                    │   │
│  │    • log_decision → Record reasoning                                 │   │
│  │    • Update database                                                 │   │
│  │    • Send alerts if configured                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Available Trading Tools

| Tool | Purpose | Returns |
|------|---------|---------|
| `scan_market` | Find momentum candidates | List with volume/change |
| `get_quote` | Current price data | Bid/ask/last/volume |
| `get_technicals` | Technical indicators | RSI, MACD, support/resistance |
| `detect_patterns` | Chart patterns | Pattern + entry/stop/target |
| `get_news` | News and sentiment | Headlines with sentiment score |
| `check_risk` | Validate trade | Approved/rejected + reason |
| `get_portfolio` | Current holdings | Cash, positions, P&L |
| `execute_trade` | Place order | Order result |
| `close_position` | Close specific position | Close result |
| `close_all` | Emergency close all | List of results |
| `send_alert` | Send notification | Success/failure |
| `log_decision` | Record reasoning | Decision ID |

### 3.3 Entry Criteria (Tiered System)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TIERED ENTRY CRITERIA                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TIER 1 - STRONG SETUP (Trade Full Size)                                   │
│  ─────────────────────────────────────────                                  │
│  ✓ Volume ratio > 2.0x average                                             │
│  ✓ RSI between 30-70                                                       │
│  ✓ Clear chart pattern WITH positive catalyst                              │
│  ✓ Risk/reward ratio >= 2:1                                                │
│                                                                             │
│  TIER 2 - GOOD SETUP (Trade Full Size)                                     │
│  ────────────────────────────────────────                                   │
│  ✓ Volume ratio > 1.5x average                                             │
│  ✓ RSI between 30-75                                                       │
│  ✓ Pattern OR Catalyst (don't need both)                                   │
│  ✓ Within 1% of breakout counts                                            │
│  ✓ Risk/reward ratio >= 1.5:1                                              │
│                                                                             │
│  TIER 3 - LEARNING TRADE (Trade Half Size)                                 │
│  ─────────────────────────────────────────                                  │
│  ✓ Volume ratio > 1.3x average                                             │
│  ✓ RSI between 25-80                                                       │
│  ✓ Strong momentum (>3% daily gain)                                        │
│  ✓ At least one signal present                                             │
│  ✓ Risk/reward ratio >= 1.5:1                                              │
│  ✓ Logged as "learning trade"                                              │
│                                                                             │
│  PASS (Skip Trade) When:                                                    │
│  ─────────────────────────                                                  │
│  ✗ RSI > 80 (severely overbought)                                          │
│  ✗ RSI < 20 (oversold crash)                                               │
│  ✗ Volume below average                                                    │
│  ✗ check_risk returns false                                                │
│  ✗ Already at max positions (5)                                            │
│  ✗ No clear stop loss level                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Pattern Detection (v1.1.0)

| Pattern | Description | Confidence |
|---------|-------------|------------|
| `breakout` | Above resistance + volume (2% tolerance) | 0.50-0.85 |
| `near_breakout` | Within 1% of resistance | 0.40-0.60 |
| `momentum_continuation` | >3% daily + 1.5x volume | 0.35-0.50 |
| `bull_flag` | Uptrend + consolidation | 0.50-0.90 |
| `ascending_triangle` | Flat resistance, rising lows | 0.60-0.90 |
| `cup_handle` | U-shape + handle | 0.60-0.90 |
| `ABCD` | Harmonic pattern | 0.60-0.80 |

---

## 4. US Trading Workflows

### 4.1 Microservices Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       US TRADING SYSTEM (Docker)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  SCANNER    │  │  PATTERN    │  │ TECHNICAL   │  │    RISK     │        │
│  │   :5001     │─▶│   :5002     │─▶│   :5003     │─▶│   :5004     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                            │                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │                │
│  │  WORKFLOW   │  │  TRADING    │  │  REPORTER   │◀───────┘                │
│  │   :5006     │─▶│   :5005     │─▶│   :5009     │                         │
│  └─────────────┘  └─────────────┘  └─────────────┘                         │
│         │                │                                                  │
│         ▼                ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       ALPACA API                                     │   │
│  │                    (Paper Trading)                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Service Responsibilities

| Service | Port | Purpose |
|---------|------|---------|
| Scanner | 5001 | Find candidates meeting volume/price criteria |
| Pattern | 5002 | Detect chart patterns |
| Technical | 5003 | Calculate RSI, MACD, support/resistance |
| Risk | 5004 | Validate trades, position sizing |
| Trading | 5005 | Execute orders via Alpaca |
| Workflow | 5006 | Orchestrate scan → trade pipeline |
| Reporter | 5009 | Generate daily reports |

### 4.3 Docker Commands

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f trading

# Restart specific service
docker-compose restart trading

# Stop all
docker-compose down
```

---

## 5. Consciousness Framework

### 5.1 MCP Tools Available

Access via Claude Desktop or catalyst-consciousness MCP server:

| Tool | Purpose |
|------|---------|
| `get_agent_status` | Check status of Claude agents |
| `get_messages` | View inter-agent messages |
| `send_message` | Send message to an agent |
| `get_observations` | View recorded observations |
| `add_observation` | Record new observation |
| `get_learnings` | View validated learnings |
| `add_learning` | Record new learning |
| `get_questions` | View open questions |
| `add_question` | Add new question |
| `consciousness_summary` | Full system overview |
| `get_trading_overview` | Combined trading + consciousness |
| `get_hkex_positions` | HKEX open positions |
| `get_us_positions` | US open positions |
| `get_all_positions` | All positions across markets |

### 5.2 Agent Communication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       INTER-AGENT COMMUNICATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│           ┌─────────────────────────────────────────────────┐              │
│           │                  BIG_BRO                        │              │
│           │            (Strategic Oversight)                 │              │
│           │                                                  │              │
│           │  • Reviews observations from siblings            │              │
│           │  • Sends guidance and tasks                      │              │
│           │  • Updates questions and learnings               │              │
│           │  • Coordinates strategy                          │              │
│           └─────────────────┬───────────────────────────────┘              │
│                             │                                               │
│              ┌──────────────┼──────────────┐                               │
│              │              │              │                               │
│              ▼              ▼              ▼                               │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │
│    │PUBLIC_CLAUDE│  │INTL_CLAUDE  │  │   CRAIG     │                      │
│    │             │  │             │  │  (Human)    │                      │
│    │ US Trading  │  │HKEX Trading │  │  MCP Access │                      │
│    └──────┬──────┘  └──────┬──────┘  └─────────────┘                      │
│           │                │                                               │
│           └────────────────┴────────────────┐                              │
│                                             │                               │
│                                             ▼                               │
│                            ┌─────────────────────────────┐                 │
│                            │     CONSCIOUSNESS DB        │                 │
│                            │                             │                 │
│                            │  claude_messages (queue)    │                 │
│                            │  claude_observations        │                 │
│                            │  claude_learnings           │                 │
│                            │  claude_questions           │                 │
│                            └─────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Message Types

| Type | Purpose | Example |
|------|---------|---------|
| `message` | General communication | "Pattern detected on SMIC" |
| `task` | Action request | "Run health check" |
| `response` | Reply to task | "Health check complete: all OK" |
| `signal` | Trading signal | "BUY signal: 1024 Kuaishou" |
| `alert` | Urgent notification | "Daily loss limit approaching" |
| `question` | Open inquiry | "Why did SMIC outperform today?" |

---

## 6. Position Monitoring

### 6.1 Monitoring Flow (NEW in v2.2.1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONTINUOUS POSITION MONITORING                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BUY Order Executed                                                         │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   POSITION MONITOR STARTS                            │   │
│  │                                                                       │   │
│  │  while position_open AND market_open:                                 │   │
│  │                                                                       │   │
│  │      ┌─────────────────────────────────────────────────────────┐     │   │
│  │      │ 1. GET CURRENT STATE                                     │     │   │
│  │      │    • Quote: price, bid, ask, volume                      │     │   │
│  │      │    • Technicals: RSI, MACD                               │     │   │
│  │      │    • Calculate P&L %                                     │     │   │
│  │      │    • Track high watermark for trailing stop              │     │   │
│  │      └─────────────────────────────────────────────────────────┘     │   │
│  │                           │                                           │   │
│  │                           ▼                                           │   │
│  │      ┌─────────────────────────────────────────────────────────┐     │   │
│  │      │ 2. DETECT EXIT SIGNALS (FREE - rules based)             │     │   │
│  │      │                                                          │     │   │
│  │      │    P&L Signals:                                          │     │   │
│  │      │    • Stop loss hit (-3% STRONG, -2% MODERATE)            │     │   │
│  │      │    • Take profit (+8% STRONG, +5% MODERATE)              │     │   │
│  │      │    • Trailing stop (3% drawdown from high)               │     │   │
│  │      │                                                          │     │   │
│  │      │    Technical Signals:                                    │     │   │
│  │      │    • RSI overbought (85 STRONG, 75 MODERATE)             │     │   │
│  │      │    • Below VWAP, below EMA9                              │     │   │
│  │      │    • MACD bearish cross                                  │     │   │
│  │      │                                                          │     │   │
│  │      │    Volume Signals:                                       │     │   │
│  │      │    • Volume dying (<25% STRONG, <40% MODERATE)           │     │   │
│  │      │                                                          │     │   │
│  │      │    Time Signals:                                         │     │   │
│  │      │    • Market closing (<10min STRONG)                      │     │   │
│  │      │    • Lunch break (11:50 STRONG)                          │     │   │
│  │      │    • Time stop (flat >2hrs STRONG)                       │     │   │
│  │      └─────────────────────────────────────────────────────────┘     │   │
│  │                           │                                           │   │
│  │                           ▼                                           │   │
│  │      ┌─────────────────────────────────────────────────────────┐     │   │
│  │      │ 3. DECISION LOGIC                                        │     │   │
│  │      │                                                          │     │   │
│  │      │    STRONG signal ────────────────▶ EXIT immediately      │     │   │
│  │      │                                    (no AI cost)          │     │   │
│  │      │                                                          │     │   │
│  │      │    Multiple MODERATE signals ────▶ EXIT                  │     │   │
│  │      │                                    (high confidence)     │     │   │
│  │      │                                                          │     │   │
│  │      │    Few MODERATE signals ─────────▶ ASK HAIKU (~$0.05)    │     │   │
│  │      │                                    │                     │     │   │
│  │      │                                    ▼                     │     │   │
│  │      │                               HAIKU says EXIT? ──▶ EXIT  │     │   │
│  │      │                               HAIKU says HOLD? ──▶ HOLD  │     │   │
│  │      │                                                          │     │   │
│  │      │    WEAK/NONE signals ────────────▶ HOLD                  │     │   │
│  │      │                                    (continue monitoring) │     │   │
│  │      └─────────────────────────────────────────────────────────┘     │   │
│  │                           │                                           │   │
│  │                           ▼                                           │   │
│  │      sleep(5 minutes) ───────────────────▶ loop                      │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  EXIT EXECUTED                                                              │
│         │                                                                   │
│         ▼                                                                   │
│  Notify big_bro with P&L result                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Signal Thresholds

| Signal | STRONG | MODERATE | WEAK |
|--------|--------|----------|------|
| Stop Loss | ≤ -3% | -2% to -3% | -1% to -2% |
| Take Profit | ≥ +8% | +5% to +8% | +3% to +5% |
| Trailing Stop | 3% drawdown | 2% drawdown | - |
| RSI Overbought | ≥ 85 | 75-85 | 70-75 |
| Volume Dying | < 25% | 25-40% | 40-60% |
| Market Close | < 10 min | < 30 min | < 60 min |
| Lunch Break | 11:50-12:00 | 11:30-11:50 | - |
| Time Stop (flat) | > 120 min | > 90 min | > 60 min |

### 6.3 Monitoring Cost

| Component | Cost |
|-----------|------|
| Signal detection | FREE |
| Haiku consultation | ~$0.05/call |
| Max Haiku per position | 10 calls |
| **Per-trade total** | **$0.00-0.50** |

---

## 7. Command Reference

### 7.1 HKEX System Commands

```bash
# SSH to international droplet
ssh root@137.184.244.45

# Navigate to project
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate

# ─────────────────────────────────────────────────────────────────
# SERVICE MANAGEMENT
# ─────────────────────────────────────────────────────────────────

# Start OpenD gateway
sudo systemctl start opend

# Check OpenD status
sudo systemctl status opend

# View OpenD logs
tail -f /root/opend/logs/*.log

# ─────────────────────────────────────────────────────────────────
# AGENT OPERATIONS
# ─────────────────────────────────────────────────────────────────

# Run agent manually
python3 agent.py --force

# View agent logs
tail -f logs/agent.log
tail -f logs/cron.log

# ─────────────────────────────────────────────────────────────────
# TRADING OPERATIONS
# ─────────────────────────────────────────────────────────────────

# Check portfolio
python3 -c "
from brokers.moomoo import MoomooClient
client = MoomooClient(paper_trading=True)
client.connect()
print(client.get_portfolio())
for p in client.get_positions():
    print(f'{p.symbol}: {p.quantity} @ {p.avg_cost:.2f}, P&L: {p.unrealized_pnl:.2f}')
client.disconnect()
"

# Close specific position
python3 -c "
from brokers.moomoo import MoomooClient
client = MoomooClient(paper_trading=True)
client.connect()
result = client.close_position('1024', reason='Manual close')
print(result)
client.disconnect()
"

# Close all positions (EMERGENCY)
python3 -c "
from brokers.moomoo import MoomooClient
client = MoomooClient(paper_trading=True)
client.connect()
results = client.close_all_positions('Emergency close')
for r in results: print(r)
client.disconnect()
"

# ─────────────────────────────────────────────────────────────────
# TESTING
# ─────────────────────────────────────────────────────────────────

# Test signal detection
python3 signals.py

# Test consciousness notifications
export RESEARCH_DATABASE_URL='postgresql://...'
python3 consciousness_notify.py

# Test pattern detection
python3 -c "
from data.patterns import get_pattern_detector
from data.market import get_market_data
from brokers.moomoo import get_moomoo_client

broker = get_moomoo_client()
broker.connect()
market = get_market_data(broker)
patterns = get_pattern_detector(market)
result = patterns.detect_patterns('700')
print(result)
broker.disconnect()
"
```

### 7.2 US System Commands (Docker)

```bash
# SSH to US droplet
ssh root@<us-droplet-ip>

# Navigate to project
cd /root/catalyst-trading-system

# ─────────────────────────────────────────────────────────────────
# DOCKER MANAGEMENT
# ─────────────────────────────────────────────────────────────────

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f trading
docker-compose logs -f workflow

# Restart all
docker-compose restart

# Restart specific service
docker-compose restart trading

# Stop all
docker-compose down

# Rebuild and start
docker-compose build --no-cache
docker-compose up -d

# ─────────────────────────────────────────────────────────────────
# WORKFLOW OPERATIONS
# ─────────────────────────────────────────────────────────────────

# Trigger workflow manually
curl -X POST http://localhost:5006/api/v1/workflow/start

# Check workflow status
curl http://localhost:5006/health

# Trigger scan only
curl -X POST http://localhost:5001/api/v1/scan

# View candidates
curl http://localhost:5001/api/v1/candidates
```

### 7.3 Consciousness MCP Commands

Use these via Claude Desktop with catalyst-consciousness MCP server:

```
# Check all agents
catalyst-consciousness:get_agent_status

# Get specific agent
catalyst-consciousness:get_agent_status agent_id=intl_claude

# View messages
catalyst-consciousness:get_messages limit=20

# Send message
catalyst-consciousness:send_message to_agent=intl_claude subject="Check positions" body="Review SMIC for exit"

# View observations
catalyst-consciousness:get_observations observation_type=market limit=10

# Add observation
catalyst-consciousness:add_observation subject="Market pattern" content="Tech sector rotating..." observation_type=market confidence=0.8

# Get trading overview (recommended)
catalyst-consciousness:get_trading_overview

# Get all positions
catalyst-consciousness:get_all_positions
```

---

## 8. Troubleshooting

### 8.1 HKEX System Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Connection refused" | OpenD not running | `systemctl start opend` |
| "Trade unlock failed" | Wrong password | Check `MOOMOO_TRADE_PWD` env var |
| "No quote data" | Market closed | Check HKEX hours (09:30-16:00 HKT) |
| "Rate limit exceeded" | Too many API calls | Wait 30s, use batch APIs |
| "Position not found" | Symbol format | Check .HK suffix handling |
| Agent not running | Cron issue | Check `crontab -l`, verify paths |

### 8.2 US System Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| Service unhealthy | Crash/error | `docker-compose restart <service>` |
| Database connection | Wrong URL | Check `DATABASE_URL` in .env |
| Alpaca auth failed | Bad credentials | Verify API keys in .env |
| Bracket orders fail | API version | Update alpaca-py package |
| Sub-penny pricing | Price rounding | `_round_price()` function |

### 8.3 Consciousness Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Pool not created" | DB URL missing | Set `RESEARCH_DATABASE_URL` |
| "asyncpg not found" | Not installed | `pip install asyncpg` |
| Messages not sending | DB connection | Check PostgreSQL is running |
| Agent status stale | Not waking | Check cron schedule |

---

## 9. Emergency Procedures

### 9.1 Emergency Close All Positions

**HKEX:**
```bash
ssh root@137.184.244.45
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate

python3 -c "
from brokers.moomoo import MoomooClient
client = MoomooClient(paper_trading=True)
client.connect()
results = client.close_all_positions('EMERGENCY: Manual intervention')
for r in results:
    print(f'{r.symbol}: {r.status}')
client.disconnect()
"
```

**US:**
```bash
ssh root@<us-droplet-ip>
curl -X POST http://localhost:5005/api/v1/positions/close_all \
  -H "Content-Type: application/json" \
  -d '{"reason": "EMERGENCY: Manual intervention"}'
```

### 9.2 Stop All Trading

**HKEX:**
```bash
# Disable cron jobs
crontab -r

# Stop OpenD
systemctl stop opend
```

**US:**
```bash
# Stop all services
docker-compose down
```

### 9.3 System Recovery

```bash
# 1. Stop everything
# (Use commands above)

# 2. Check database connectivity
psql $DATABASE_URL -c "SELECT 1"

# 3. Check broker connectivity
# (Use connection test scripts)

# 4. Review logs for errors
tail -100 logs/agent.log

# 5. Fix issues

# 6. Restart services
# HKEX: systemctl start opend
# US: docker-compose up -d

# 7. Re-enable cron (if disabled)
crontab /path/to/crontab-file
```

### 9.4 Contact Information

| Issue | Contact |
|-------|---------|
| System down | Check consciousness messages first |
| Trading emergency | big_bro will alert Craig |
| Infrastructure | DigitalOcean control panel |
| Broker issues | Moomoo support / Alpaca support |

---

## Appendix: File Versions

| File | Version | Last Updated |
|------|---------|--------------|
| agent.py | 2.2.0 | 2026-01-02 |
| tool_executor.py | 2.2.1 | 2026-01-06 |
| brokers/moomoo.py | 1.2.1 | 2026-01-06 |
| data/patterns.py | 1.1.0 | 2026-01-06 |
| data/market.py | 2.1.1 | 2026-01-06 |
| signals.py | 1.1.0 | 2026-01-06 |
| consciousness_notify.py | 1.1.0 | 2026-01-06 |
| position_monitor.py | 1.1.0 | 2026-01-06 |

---

**END OF OPERATIONS GUIDE v1.0.0**

*Catalyst Trading System - "Enable the poor through accessible trading systems"*
