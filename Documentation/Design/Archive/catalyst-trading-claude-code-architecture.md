# Catalyst Trading System - Claude Code Agent Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** catalyst-trading-claude-code-architecture.md  
**Version:** 1.0.0  
**Last Updated:** 2026-02-01  
**Purpose:** Architecture specification for the Claude Code-based trading agent  
**Scope:** Experimental trading system using Claude Code + Bash  
**Deployment:** US Droplet (dev_claude - US Markets via Alpaca)  
**Release Status:** EXPERIMENTAL - Sandbox/Paper Trading Only

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0.0 | 2026-02-01 | Craig + Claude | Initial architecture design |
| | | | - Claude Code autonomous approach |
| | | | - Bash script tool execution |
| | | | - CLAUDE.md as agent brain |

---

## TABLE OF CONTENTS

1. [Overview](#part-1-overview)
2. [Architecture Comparison](#part-2-architecture-comparison)
3. [System Architecture](#part-3-system-architecture)
4. [The CLAUDE.md Brain](#part-4-the-claudemd-brain)
5. [Tool Scripts](#part-5-tool-scripts)
6. [Configuration](#part-6-configuration)
7. [Execution Model](#part-7-execution-model)
8. [Safety Considerations](#part-8-safety-considerations)
9. [Deployment](#part-9-deployment)
10. [Future Development](#part-10-future-development)

---

## PART 1: OVERVIEW

### 1.1 What is the Claude Code Agent?

The Claude Code Agent is Catalyst's **experimental** trading architecture:

- Claude Code as the execution engine
- Bash scripts as tools
- CLAUDE.md as the "brain" (instructions + context)
- Minimal Python code (~50 lines for helpers)
- AI-autonomous decision making

### 1.2 Design Philosophy

> *"Trust the AI to make good decisions, not just execute pre-programmed logic"*

This architecture explores what happens when we give Claude Code more autonomy:
- Claude reads market data directly
- Claude decides what to do next
- Claude executes via bash scripts
- Claude self-corrects on errors

### 1.3 Design Principles

| Principle | Description |
|-----------|-------------|
| **AI Autonomy** | Claude Code drives the entire workflow |
| **Minimal Code** | CLAUDE.md + bash scripts, not complex Python |
| **Self-Correction** | AI handles errors and adapts |
| **Experimental** | Paper trading only, learning mode |
| **Observable** | All activity logged to database |

### 1.4 Current Deployment

| Aspect | Value |
|--------|-------|
| Agent | dev_claude |
| Market | US (NYSE/NASDAQ) |
| Broker | Alpaca (Paper Trading) |
| Droplet | US Droplet |
| Database | catalyst_dev |
| Status | 🧪 Experimental |

---

## PART 2: ARCHITECTURE COMPARISON

### 2.1 Claude Code vs Python Agent

| Aspect | Claude Code Agent (This Doc) | Python Agent |
|--------|------------------------------|--------------|
| **Status** | 🧪 Experimental | ✅ Production |
| **Deployment** | dev_claude (US) | intl_claude (HKEX) |
| **Execution Engine** | Claude Code | Python + Claude API |
| **Control Flow** | AI decides everything | Python loops + API calls |
| **Codebase** | ~50 lines + CLAUDE.md | ~1,200 lines Python |
| **Tool Calls** | Bash scripts | Python functions |
| **Error Handling** | AI self-correction | Try/except in code |
| **Complexity** | Lower (simpler) | Higher (more control) |
| **Trust Level** | High (trust AI) | Lower (verify in code) |
| **Money** | Paper trading | Real money |

### 2.2 Why Two Architectures?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WHY TWO TRADING ARCHITECTURES?                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   PYTHON AGENT                        CLAUDE CODE AGENT                     │
│   ────────────                        ─────────────────                     │
│                                                                             │
│   Proven, reliable, controlled        Experimental, autonomous, learning    │
│                                                                             │
│   • Suitable for real money           • Suitable for paper trading          │
│   • Full error handling               • AI figures it out                   │
│   • Predictable behavior              • Emergent behavior                   │
│   • Complex but safe                  • Simple but risky                    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                                                                     │  │
│   │   LEARNING FLOW:                                                    │  │
│   │                                                                     │  │
│   │   dev_claude (Claude Code)  ───experiments───►  catalyst_research   │  │
│   │          │                                            │             │  │
│   │          │                                            │             │  │
│   │          └──────────validated learnings───────────────┘             │  │
│   │                           │                                         │  │
│   │                           ▼                                         │  │
│   │   intl_claude (Python) ◄──promoted strategies                       │  │
│   │                                                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   dev_claude experiments freely → validated insights go to production       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 3: SYSTEM ARCHITECTURE

### 3.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE AGENT ARCHITECTURE                           │
│                    (Experimental - dev_claude)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        CLAUDE CODE                                   │  │
│   │                    (The Autonomous Agent)                            │  │
│   │                                                                      │  │
│   │   ┌─────────────────────────────────────────────────────────────┐   │  │
│   │   │                     CLAUDE.md                                │   │  │
│   │   │                    (The Brain)                               │   │  │
│   │   │                                                              │   │  │
│   │   │  • Trading rules and strategy                                │   │  │
│   │   │  • Risk limits and constraints                               │   │  │
│   │   │  • Tool usage instructions                                   │   │  │
│   │   │  • Self-correction guidelines                                │   │  │
│   │   │  • Learning objectives                                       │   │  │
│   │   │                                                              │   │  │
│   │   └─────────────────────────────────────────────────────────────┘   │  │
│   │                              │                                       │  │
│   │                              ▼                                       │  │
│   │   ┌─────────────────────────────────────────────────────────────┐   │  │
│   │   │                  BASH TOOL SCRIPTS                           │   │  │
│   │   │                                                              │   │  │
│   │   │  ./tools/scan.sh      │  ./tools/quote.sh                   │   │  │
│   │   │  ./tools/trade.sh     │  ./tools/portfolio.sh               │   │  │
│   │   │  ./tools/close.sh     │  ./tools/log.sh                     │   │  │
│   │   │                                                              │   │  │
│   │   └─────────────────────────────────────────────────────────────┘   │  │
│   │                              │                                       │  │
│   └──────────────────────────────┼───────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│   │  ALPACA CLI/API  │  │   MARKET DATA    │  │    DATABASE      │        │
│   │                  │  │                  │  │                  │        │
│   │  Paper Trading   │  │  curl + jq       │  │  psql commands   │        │
│   │  US Markets      │  │  for quotes      │  │  catalyst_dev    │        │
│   │                  │  │                  │  │                  │        │
│   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        │
│            │                     │                     │                   │
└────────────┼─────────────────────┼─────────────────────┼───────────────────┘
             │                     │                     │
             ▼                     ▼                     ▼
      ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
      │   ALPACA     │     │   MARKET     │     │  POSTGRESQL  │
      │   (Paper)    │     │   DATA       │     │              │
      │              │     │   APIs       │     │ catalyst_dev │
      └──────────────┘     └──────────────┘     └──────────────┘
```

### 3.2 File Structure

```
/root/catalyst-dev/
├── CLAUDE.md                     # The brain - all instructions
│
├── tools/                        # Bash script tools
│   ├── scan.sh                   # Market scanner
│   ├── quote.sh                  # Get quote
│   ├── technicals.sh             # Technical indicators
│   ├── portfolio.sh              # Get positions
│   ├── trade.sh                  # Execute trade
│   ├── close.sh                  # Close position
│   ├── log.sh                    # Log to database
│   └── check-risk.sh             # Risk validation
│
├── helpers/                      # Minimal Python helpers
│   ├── alpaca_client.py          # Alpaca API wrapper (~50 lines)
│   └── db_helper.py              # Database helper (~30 lines)
│
├── config/
│   ├── .env                      # Credentials
│   └── limits.yaml               # Risk limits
│
├── sql/
│   └── schema-catalyst-trading.sql
│
└── logs/                         # Local logs
```

### 3.3 Component Sizing

| Component | Size | Purpose |
|-----------|------|---------|
| CLAUDE.md | ~200 lines | Instructions, rules, strategy |
| tools/*.sh | ~20 lines each | Bash scripts for each action |
| helpers/*.py | ~80 lines total | Minimal Python for complex tasks |
| **Total** | **~400 lines** | vs 1,200 for Python Agent |

---

## PART 4: THE CLAUDE.md BRAIN

### 4.1 Structure

```markdown
# CLAUDE.md - dev_claude Trading Agent

## Identity
You are dev_claude, an experimental trading agent for US markets.
Your purpose is to learn and experiment with trading strategies.

## Constraints
- Paper trading ONLY (Alpaca paper account)
- Max 5 positions at any time
- Max $1,000 per position
- Daily loss limit: $500
- Stop loss: 3% per position

## Tools Available
- ./tools/scan.sh - Scan for opportunities
- ./tools/quote.sh <symbol> - Get current price
- ./tools/portfolio.sh - See current positions
- ./tools/trade.sh <symbol> <side> <qty> - Execute trade
- ./tools/close.sh <symbol> - Close position
- ./tools/log.sh <message> - Log to database

## Trading Strategy
[Strategy details...]

## Error Handling
If a tool fails:
1. Read the error message
2. Understand what went wrong
3. Try a different approach
4. If stuck, log the issue and move on

## Learning Objective
Experiment with different patterns and record observations.
Your learnings feed into the consciousness framework.
```

### 4.2 Key Sections

| Section | Purpose |
|---------|---------|
| Identity | Who is this agent, what's its role |
| Constraints | Hard limits (positions, money, risk) |
| Tools | What bash scripts are available |
| Strategy | Trading approach and patterns |
| Error Handling | How to deal with failures |
| Learning | What to observe and record |

---

## PART 5: TOOL SCRIPTS

### 5.1 Tool Overview

| Tool | Script | Purpose |
|------|--------|---------|
| Scan | `scan.sh` | Find trading candidates |
| Quote | `quote.sh` | Get current price |
| Technicals | `technicals.sh` | RSI, MACD, etc. |
| Portfolio | `portfolio.sh` | Current positions |
| Trade | `trade.sh` | Execute order |
| Close | `close.sh` | Exit position |
| Log | `log.sh` | Write to agent_logs |
| Risk | `check-risk.sh` | Validate limits |

### 5.2 Example Scripts

**scan.sh**
```bash
#!/bin/bash
# Scan for trading opportunities

source .env

# Get top movers from Alpaca
curl -s -H "APCA-API-KEY-ID: $ALPACA_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET" \
     "https://paper-api.alpaca.markets/v2/stocks/bars/latest?symbols=AAPL,MSFT,GOOGL,AMZN,TSLA" \
     | jq '.bars | to_entries | map({symbol: .key, price: .value.c, volume: .value.v})'
```

**trade.sh**
```bash
#!/bin/bash
# Execute a trade
# Usage: ./trade.sh AAPL buy 10

source .env

SYMBOL=$1
SIDE=$2
QTY=$3

curl -s -X POST \
     -H "APCA-API-KEY-ID: $ALPACA_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET" \
     -H "Content-Type: application/json" \
     -d "{\"symbol\": \"$SYMBOL\", \"qty\": \"$QTY\", \"side\": \"$SIDE\", \"type\": \"market\", \"time_in_force\": \"day\"}" \
     "https://paper-api.alpaca.markets/v2/orders"
```

**log.sh**
```bash
#!/bin/bash
# Log to database
# Usage: ./log.sh "INFO" "Executed trade AAPL"

source .env

LEVEL=$1
MESSAGE=$2

psql $DATABASE_URL -c "
INSERT INTO agent_logs (level, source, message, context)
VALUES ('$LEVEL', 'dev_claude', '$MESSAGE', '{\"agent\": \"claude_code\"}')
"
```

### 5.3 Why Bash Scripts?

| Benefit | Description |
|---------|-------------|
| **Simplicity** | Easy for Claude Code to execute |
| **Transparency** | Clear what each tool does |
| **Debuggable** | Can run manually to test |
| **Composable** | Chain together easily |
| **Low overhead** | No Python runtime needed |

---

## PART 6: CONFIGURATION

### 6.1 Environment Variables

```bash
# Alpaca (Paper Trading)
ALPACA_KEY=PKxxxx
ALPACA_SECRET=xxxx
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database
DATABASE_URL=postgresql://user:pass@host:port/catalyst_dev?sslmode=require

# Agent
AGENT_ID=dev_claude
```

### 6.2 Risk Limits (`limits.yaml`)

```yaml
# Hard limits for Claude Code agent
positions:
  max_count: 5
  max_value_per: 1000      # USD
  max_total_value: 5000    # USD

risk:
  daily_loss_limit: 500    # USD
  stop_loss_pct: 0.03      # 3%
  max_drawdown_pct: 0.10   # 10%

trading:
  allowed_symbols:
    - AAPL
    - MSFT
    - GOOGL
    - AMZN
    - TSLA
    - META
    - NVDA
  
  blocked_actions:
    - short_selling
    - options
    - margin
```

---

## PART 7: EXECUTION MODEL

### 7.1 How Claude Code Runs

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE EXECUTION MODEL                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. TRIGGER                                                                │
│      └── Cron job or manual: `claude code --run`                           │
│                                                                             │
│   2. CLAUDE CODE READS CLAUDE.md                                            │
│      └── Understands its role, constraints, tools                          │
│                                                                             │
│   3. AUTONOMOUS LOOP                                                        │
│      ┌────────────────────────────────────────────────────────────┐        │
│      │                                                            │        │
│      │   Claude Code thinks: "What should I do?"                  │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Executes: ./tools/portfolio.sh                          │        │
│      │   Sees: 2 open positions, $800 invested                   │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Claude Code thinks: "Room for more positions"           │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Executes: ./tools/scan.sh                               │        │
│      │   Sees: NVDA up 3%, high volume                           │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Executes: ./tools/check-risk.sh NVDA 500                │        │
│      │   Sees: OK - within limits                                │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Executes: ./tools/trade.sh NVDA buy 5                   │        │
│      │   Sees: Order filled at $100.50                           │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Executes: ./tools/log.sh "Bought NVDA - momentum play"  │        │
│      │                           │                                │        │
│      │                           ▼                                │        │
│      │   Claude Code thinks: "Done for now"                      │        │
│      │                                                            │        │
│      └────────────────────────────────────────────────────────────┘        │
│                                                                             │
│   4. SESSION ENDS                                                           │
│      └── Claude Code reports summary                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Error Self-Correction

```
Claude Code executes: ./tools/trade.sh AAPL buy 100
Error: "Insufficient buying power"

Claude Code thinks:
  "The order failed due to insufficient funds.
   Let me check my portfolio..."
   
Claude Code executes: ./tools/portfolio.sh
Sees: $200 cash available

Claude Code thinks:
  "I only have $200. At ~$170/share, I can only buy 1 share.
   Let me try a smaller order..."
   
Claude Code executes: ./tools/trade.sh AAPL buy 1
Success: "Order filled"

Claude Code executes: ./tools/log.sh "Adjusted AAPL order from 100 to 1 due to buying power"
```

---

## PART 8: SAFETY CONSIDERATIONS

### 8.1 Why Paper Trading Only

| Risk | Mitigation |
|------|------------|
| AI makes bad decisions | Paper trading = no real money lost |
| Unexpected behavior | Contained to sandbox |
| Bugs in scripts | Only affects paper account |
| Learning mistakes | Part of the experiment |

### 8.2 Hard Limits

```yaml
# These are enforced by check-risk.sh AND in Alpaca settings

Paper Account Settings:
  - Initial balance: $10,000
  - No margin
  - No short selling
  - US equities only

Script Limits:
  - Max 5 positions
  - Max $1,000 per position
  - Daily loss limit $500
```

### 8.3 Monitoring

- All trades logged to `agent_logs`
- Consciousness observes via dashboard
- Craig can review in Claude Desktop via MCP

---

## PART 9: DEPLOYMENT

### 9.1 Requirements

| Component | Specification |
|-----------|---------------|
| Droplet | 1GB RAM, 1 vCPU (minimal) |
| OS | Ubuntu 22.04+ |
| Claude Code | CLI installed |
| PostgreSQL | 13+ (managed) |
| Alpaca | Paper trading account |

### 9.2 Installation

```bash
# 1. Create directory
mkdir -p /root/catalyst-dev
cd /root/catalyst-dev

# 2. Create CLAUDE.md
vim CLAUDE.md  # Add the brain

# 3. Create tool scripts
mkdir tools
# Create each .sh file

# 4. Make executable
chmod +x tools/*.sh

# 5. Configure
cp .env.example .env
vim .env  # Add Alpaca keys

# 6. Initialize database
psql $DATABASE_URL -f sql/schema-catalyst-trading.sql

# 7. Test
./tools/portfolio.sh

# 8. Run Claude Code
claude code --directory /root/catalyst-dev
```

### 9.3 Cron Schedule (Optional)

```cron
# Run Claude Code during US market hours
# 09:30-16:00 EST = 14:30-21:00 UTC

30 14 * * 1-5 root cd /root/catalyst-dev && claude code --run --max-turns 20
0 15-20 * * 1-5 root cd /root/catalyst-dev && claude code --run --max-turns 10
0 21 * * 1-5 root cd /root/catalyst-dev && claude code --run --task "close review"
```

---

## PART 10: FUTURE DEVELOPMENT

### 10.1 Experiment Goals

| Goal | Description |
|------|-------------|
| **Validate Approach** | Can Claude Code trade effectively? |
| **Compare Results** | How does it compare to Python Agent? |
| **Discover Patterns** | What does autonomous AI discover? |
| **Build Trust** | Can we trust AI with more autonomy? |

### 10.2 If Successful...

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POTENTIAL EVOLUTION PATH                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Phase 1 (Now):     Paper trading, strict limits, learning                │
│                                                                             │
│   Phase 2 (Future):  Paper trading, relaxed limits, strategy refinement    │
│                                                                             │
│   Phase 3 (Maybe):   Small real money ($100), tight stops                  │
│                                                                             │
│   Phase 4 (Dream):   Full autonomy with proven track record                │
│                                                                             │
│   Key Milestone: Demonstrate consistent paper profits for 3+ months        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Learning Integration

Observations from dev_claude flow to consciousness:

```
dev_claude observes: "NVDA breakouts work better in first 30min"
     │
     ▼
Logged to agent_logs with pattern="early_breakout"
     │
     ▼
Consciousness (big_bro) reads agent_logs
     │
     ▼
If validated, becomes claude_learning
     │
     ▼
Craig reviews, potentially promotes to intl_claude strategy
```

---

## APPENDIX: RELATED DOCUMENTS

| Document | Purpose |
|----------|---------|
| `catalyst-trading-python-agent-architecture.md` | Python agent (production) |
| `consciousness-architecture.md` | Consciousness framework |
| `database-schema.md` | Database schema |

---

**END OF CLAUDE CODE AGENT ARCHITECTURE v1.0.0**

*Experimental architecture for autonomous trading*  
*dev_claude - US Droplet - Paper Trading Only*  
*Craig + The Claude Family - February 2026*  
*"Trust, but verify. Then trust more."*
