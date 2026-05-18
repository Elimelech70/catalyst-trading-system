# Hard-Coded Trading Decisions Audit

**Date**: 2026-03-10
**Purpose**: Identify all trading DECISIONS baked into Python code that should be in learnable markdown config files
**Finding**: 27 hard-coded decisions found across 7 files
**Action**: Move decisions to `.md` learning files the brain can read, update, and grow

---

## The Problem

Every trading decision is baked into `.py` files. The brain can't learn, adapt, or grow without a code deploy. Yesterday (March 9), the position monitor hard-closed all 4 profitable positions at 15:53 simply because it was near market close — no evaluation of candles, momentum, or overnight potential.

---

## Hard-Coded Decisions by Category

### 1. EXIT RULES (agents/position-monitor/monitor.py) — 10 decisions

| Line | Rule | Current Value | Problem |
|------|------|--------------|---------|
| 50 | Stop loss (strong) | -3% | Same for all tiers. Tier 1 should be 5% |
| 50 | Stop loss (moderate) | -2% | No per-tier adjustment |
| 51 | Take profit (strong) | +8% | Breakouts might target 10%+ |
| 51 | Take profit (moderate) | +5% | Mean-reversion might exit at 3% |
| 52 | RSI overbought (strong) | 85 | Market-dependent, should be learned |
| 52 | RSI overbought (moderate) | 75 | Same |
| 53 | Volume collapse (strong/moderate) | 25% / 40% | Varies by stock liquidity |
| 54 | Trailing stop | 2% from high | Volatile stocks need wider trail |
| 129 | MACD bearish | < -0.5 | Not normalized to price scale |
| **136** | **Flatten at 15:50** | **immediate_exit=True** | **Kills overnight holds entirely** |
| 140 | Lunch break close | consult at 11:50 | Brain should decide |

### 2. DISCIPLINE RULES (agents/coordinator/discipline.py) — 4 decisions

| Line | Rule | Current Value | Problem |
|------|------|--------------|---------|
| 66 | Days idle ALARM | 3 days | Arbitrary |
| 74 | Days idle WARNING | 2 days | Arbitrary |
| 85 | Capital utilization ALARM | < 5% | Strategy-dependent |
| 106 | Consecutive passes | 3 cycles | Some strategies have dry spells |

### 3. SYSTEM PROMPT (agents/coordinator/system_prompt.py) — 7 decisions

| Line | Rule | Current Value | Problem |
|------|------|--------------|---------|
| 37 | Max position | HKD 10,000 | Should scale with portfolio |
| 106-108 | Stop loss per tier | 5%/4%/3% | Should be learned from outcomes |
| 109 | Take profit per tier | 10%/8%/6% | Should be learned from outcomes |
| 110 | Daily loss limit | HKD 2,000 | Should be percentage-based |
| 111 | Consecutive loss pause | 3 losses, 1 cycle | Arbitrary |
| 47 | "Too late" cutoff | 15 min before close | Brain should decide |
| 154 | Close before lunch | Default yes | Brain should decide |

### 4. PATTERN DETECTION (data/patterns.py) — 5 decisions

| Line | Rule | Current Value | Problem |
|------|------|--------------|---------|
| 394 | Breakout volume req | 1.3x avg | Varies by stock |
| 134 | Bull flag min gain | 5% | Timeframe-dependent |
| 142 | Flag consolidation range | < 5% | Should be learned |
| 504 | Momentum min above SMA20 | 3% | Market-regime dependent |
| 464 | Near-breakout distance | 1% of resistance | Should scale with price |

### 5. TIMING (agents/coordinator/coordinator.py + monitor.py) — 2 decisions

| Line | Rule | Current Value | Problem |
|------|------|--------------|---------|
| coordinator.py:44 | Scan interval | 30 min | Should adapt to volatility |
| monitor.py:34 | Max Haiku calls | 5/cycle | Cost vs quality tradeoff |

---

## Proposed Solution: Learnable Markdown Files

Move all 27 decisions into **markdown learning files** that the brain reads, updates, and grows:

| File | Contains | Who Updates |
|------|----------|-------------|
| `CLAUDE-STRATEGY.md` | Tier sizing, stop/take-profit, position limits | Brain after reviewing outcomes |
| `CLAUDE-SIGNALS.md` | RSI, volume, MACD thresholds, trailing stops | Brain after win/loss analysis |
| `CLAUDE-DISCIPLINE.md` | Idle thresholds, capital targets, pass limits | Brain after stagnation review |
| `CLAUDE-PATTERNS.md` | Pattern parameters, breakout/flag/momentum rules | Brain after pattern success rates |

### How It Works

1. Python code reads thresholds from `.md` files at startup and each cycle
2. Brain evaluates performance after each trade closes
3. Brain updates `.md` files with adjusted thresholds based on outcomes
4. No code deploys needed to improve trading decisions
5. Full audit trail of what changed and why

### Priority Order

1. **EXIT RULES** — Most impactful. The forced close at 15:50 cost real P&L yesterday
2. **SYSTEM PROMPT rules** — Stop/take-profit percentages affect every trade
3. **PATTERN parameters** — Affect which trades are taken
4. **DISCIPLINE thresholds** — Affect trading frequency

---

## Key Insight

The code should be **mechanical** (how to place orders, connect to broker, calculate RSI).
The markdown should be **decisional** (when to exit, what RSI means, how much to risk).

The brain THINKS. The code DOES. Right now the code is thinking too.
