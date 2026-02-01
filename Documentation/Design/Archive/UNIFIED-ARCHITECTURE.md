# Catalyst Trading System - Unified Architecture

**Name of Application:** Catalyst Trading System  
**Name of file:** UNIFIED-ARCHITECTURE.md  
**Version:** 10.6.0  
**Last Updated:** 2026-01-24  
**Purpose:** Single authoritative architecture document for the entire Catalyst ecosystem  
**Supersedes:** All previous architecture documents in both repositories

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| **v10.6.0** | **2026-01-24** | **Craig + Claude** | **Context-Separated Architecture** - news_context.yaml + exit_context.yaml |
| v10.5.0 | 2026-01-16 | Craig + Claude | Position Monitor Service - persistent systemd daemon |
| v10.4.0 | 2026-01-16 | Craig + Claude | Unified architecture consolidating both repositories |
| v10.3.0 | 2026-01-16 | Craig + Claude | Repository cleanup, microservices archived |
| v10.2.0 | 2026-01-16 | Craig + Claude | dev_claude unified agent deployed |
| v10.1.0 | 2026-01-10 | Craig + Claude | Dual-broker architecture design |
| v10.0.0 | 2026-01-10 | Craig + Claude | Ecosystem restructure, US trading retired |

---

## WHAT'S NEW IN v10.6.0

### Context-Separated Architecture

This release introduces a fundamental architectural pattern: **separating context from tools**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT-SEPARATED ARCHITECTURE (v10.6.0)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   BEFORE (Context Embedded)              AFTER (Context Separated)           │
│   ─────────────────────────              ──────────────────────────          │
│                                                                              │
│   news.py                                config/                             │
│   ├── POSITIVE_WORDS = {...}             ├── news_context.yaml    ← CONTEXT │
│   ├── NEGATIVE_WORDS = {...}             └── exit_context.yaml    ← CONTEXT │
│   └── def get_news()                                                         │
│                                          data/                               │
│   signals.py                             ├── news.py              ← TOOL    │
│   ├── stop_loss = -0.03                  └── signals.py           ← TOOL    │
│   ├── take_profit = 0.08                                                     │
│   └── def detect_signals()               Benefits:                           │
│                                          • Edit YAML → auto-reload           │
│   Problems:                              • Version context separately        │
│   • Edit Python → redeploy               • A/B test configurations          │
│   • Can't tune without code changes      • Agent can update own context     │
│   • Context mixed with logic             • Craig can review context easily  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### New Files in v10.6.0

| File | Location | Purpose | Lines |
|------|----------|---------|-------|
| `news_context.yaml` | `config/` | News sentiment keywords, catalyst types, sectors | ~350 |
| `exit_context.yaml` | `config/` | Exit thresholds, pattern rules, hold conditions | ~300 |
| `news.py` | `data/` | News tool v2.0.0 - loads from context | ~550 |
| `signals.py` | `data/` | Signals tool v3.0.0 - loads from context | ~600 |

### Agent Knowledge Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT KNOWLEDGE LAYERS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CODE (news.py, signals.py, tools.py)                           │
│  ─────────────────────────────────────                          │
│  Fixed logic - NEVER self-modify                                │
│  Pure tool implementations                                       │
│                                                                  │
│  ─────────────────────────────────────                          │
│                                                                  │
│  CONTEXT (news_context.yaml, exit_context.yaml)                 │
│  ─────────────────────────────────────────────                  │
│  Editable configuration - hot-reload capable                    │
│  Keywords, thresholds, rules, mappings                          │
│  Craig can edit, agent could potentially update (future)        │
│                                                                  │
│  ─────────────────────────────────────                          │
│                                                                  │
│  MEMORY (consciousness DB - claude_learnings, etc.)             │
│  ─────────────────────────────────────────────────              │
│  Learned insights - always growing                              │
│  Observations, learnings, questions                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## TABLE OF CONTENTS

1. [Mission & Philosophy](#part-1-mission--philosophy)
2. [System Architecture](#part-2-system-architecture)
3. [The Claude Family](#part-3-the-claude-family)
4. [Trading Architecture](#part-4-trading-architecture)
5. [Position Monitoring](#part-5-position-monitoring)
6. [Context Configuration](#part-6-context-configuration) ← **NEW in v10.6.0**
7. [Consciousness Framework](#part-7-consciousness-framework)
8. [Database Schema](#part-8-database-schema)
9. [Infrastructure](#part-9-infrastructure)
10. [Operations](#part-10-operations)
11. [Repository Structure](#part-11-repository-structure)

---

## PART 1: MISSION & PHILOSOPHY

### 1.1 Mission Statement

> **"Enable the poor through accessible algorithmic trading"**

The Catalyst Trading System exists to democratize algorithmic trading - making sophisticated trading tools available to people who can't afford expensive platforms or wealth management services.

### 1.2 Core Principles

```yaml
Core Principles:
  Consciousness First: AI agents have memory, learning, communication
  Single-Agent Architecture: Proven more reliable than microservices
  Pattern-Based Trading: Hold while momentum holds, exit on pattern failure
  Context-Separated Tools: Logic in code, configuration in YAML
  Persistent Monitoring: All positions monitored continuously via systemd service
  Sandbox Learning: Experiment freely, promote proven strategies
  Production Stability: Only validated code in live trading
  Observable: Every position monitored, every decision logged
  Self-Hostable: ~$50/month infrastructure cost
  Transparent: Every trade has documented reasoning
```

### 1.3 Design Philosophy

**NOT just automated trading** - AI-assisted decision making with human oversight.

**Three-Tier Architecture:**
1. **CODE** - Fixed logic, never modified at runtime
2. **CONTEXT** - Editable configuration, hot-reloadable
3. **MEMORY** - Learned knowledge, always growing

---

## PART 2: SYSTEM ARCHITECTURE

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CATALYST ECOSYSTEM (v10.6.0)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        HUMAN INTERFACE LAYER                           │ │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │ │
│  │   │Claude Desktop│  │   GitHub     │  │  Web Dash    │                │ │
│  │   │  (MCP Tools) │  │  (Reports)   │  │  (:8080)     │                │ │
│  │   └──────────────┘  └──────────────┘  └──────────────┘                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         AGENT LAYER                                    │ │
│  │                         ┌────────┐                                     │ │
│  │                         │BIG_BRO │                                     │ │
│  │                         │ $10/day│                                     │ │
│  │                         │Strategic│                                    │ │
│  │                         └────┬────┘                                    │ │
│  │          ┌───────────────────┼───────────────────┐                    │ │
│  │          ▼                   ▼                   ▼                    │ │
│  │   ┌────────────┐     ┌────────────┐     ┌────────────┐               │ │
│  │   │DEV_CLAUDE  │     │PUBLIC_CLAUDE│    │INTL_CLAUDE │               │ │
│  │   │  $5/day    │     │  $0/day    │     │  $5/day    │               │ │
│  │   │ US Sandbox │     │  Retired   │     │HKEX Prod   │               │ │
│  │   │  Alpaca    │     │  Sleeping  │     │  Moomoo    │               │ │
│  │   └─────┬──────┘     └────────────┘     └─────┬──────┘               │ │
│  └─────────┼─────────────────────────────────────┼──────────────────────┘ │
│            │                                     │                        │
│  ┌─────────┼─────────────────────────────────────┼──────────────────────┐ │
│  │         │        SERVICE LAYER                │                      │ │
│  │         │                              ┌──────┴───────┐              │ │
│  │         │                              │position-     │              │ │
│  │         │                              │monitor.svc   │              │ │
│  │         │                              │(systemd)     │              │ │
│  │         │                              └──────┬───────┘              │ │
│  └─────────┼─────────────────────────────────────┼──────────────────────┘ │
│            │                                     │                        │
│  ┌─────────┼─────────────────────────────────────┼──────────────────────┐ │
│  │         │           DATABASE LAYER            │                      │ │
│  │    ┌────▼─────┐  ┌──────────────┐  ┌─────────▼────┐                 │ │
│  │    │catalyst_ │  │  catalyst_   │  │  catalyst_   │                 │ │
│  │    │   dev    │  │  research    │  │    intl      │                 │ │
│  │    │(sandbox) │  │(consciousness)│ │ (production) │                 │ │
│  │    └──────────┘  └──────────────┘  └──────────────┘                 │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 File Structure (v10.6.0)

```
catalyst-international/
├── unified_agent.py                    # Main agent v3.0.0
├── position_monitor_service.py         # Systemd daemon v1.0.1
├── signals.py                          # Exit signals v3.0.0 (context-separated)
├── startup_monitor.py                  # Pre-market reconciliation
├── tool_executor.py                    # Tool routing v2.8.0
├── tools.py                            # Tool schemas
├── safety.py                           # Safety checks
│
├── config/                             # ← CONTEXT LAYER (NEW)
│   ├── intl_claude_config.yaml         # Agent configuration
│   ├── news_context.yaml               # News sentiment context (NEW v10.6.0)
│   └── exit_context.yaml               # Exit strategy context (NEW v10.6.0)
│
├── brokers/
│   └── moomoo.py                       # Moomoo client v1.2.1
│
├── data/
│   ├── market.py                       # Market data v2.3.0
│   ├── patterns.py                     # Pattern detection v1.1.0
│   └── news.py                         # News tool v2.0.0 (context-separated)
│
└── Documentation/
    └── Design/
        └── UNIFIED-ARCHITECTURE.md     # This document
```

---

## PART 3: THE CLAUDE FAMILY

### 3.1 Agent Summary

| Agent | Role | Budget | Market | Status |
|-------|------|--------|--------|--------|
| **big_bro** | Strategic Oversight | $10/day | None | Active |
| **dev_claude** | US Sandbox Trading | $5/day | NYSE/NASDAQ (Alpaca) | Active |
| **intl_claude** | HKEX Production | $5/day | HKEX (Moomoo) | Active |
| **public_claude** | Retired | $0/day | - | Sleeping |

### 3.2 Agent Communication

```
big_bro (Overseer)
    │
    ├──► dev_claude: "Review your losing trades from yesterday"
    ├──► intl_claude: "Market sentiment is bearish, reduce position sizes"
    │
    ◄── dev_claude: "Learned: NVDA gaps often fade by 10am"
    ◄── intl_claude: "Closed 3 positions, +2.3% total"
```

---

## PART 4: TRADING ARCHITECTURE

### 4.1 Unified Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED AGENT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   unified_agent.py                                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                                                                      │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │  │
│   │  │ Mode Manager │  │ Tool Executor│  │ Consciousness│              │  │
│   │  │              │  │              │  │              │              │  │
│   │  │ • scan       │  │ • get_quote  │  │ • wake_up    │              │  │
│   │  │ • trade      │  │ • get_tech   │  │ • observe    │              │  │
│   │  │ • close      │  │ • scan_market│  │ • learn      │              │  │
│   │  │ • heartbeat  │  │ • execute    │  │ • message    │              │  │
│   │  │              │  │ • close_pos  │  │ • sleep      │              │  │
│   │  └──────────────┘  └──────────────┘  └──────────────┘              │  │
│   │         │                 │                 │                       │  │
│   │         └─────────────────┼─────────────────┘                       │  │
│   │                           │                                         │  │
│   │                           ▼                                         │  │
│   │  ┌──────────────────────────────────────────────────────────────┐  │  │
│   │  │                    TRADING WORKFLOW                           │  │  │
│   │  │                                                               │  │  │
│   │  │  1. INIT      → Load portfolio, check market hours           │  │  │
│   │  │  2. PORTFOLIO → Get current positions                         │  │  │
│   │  │  3. SCAN      → Find momentum candidates (uses news_context) │  │  │
│   │  │  4. ANALYZE   → Quote + technicals + patterns                 │  │  │
│   │  │  5. DECIDE    → Entry criteria met?                           │  │  │
│   │  │  6. VALIDATE  → Safety checks pass?                           │  │  │
│   │  │  7. EXECUTE   → Submit order                                  │  │  │
│   │  │  8. MONITOR   → Start position monitor (uses exit_context)    │  │  │
│   │  │  9. LOG       → Record decision to consciousness              │  │  │
│   │  │  10. LOOP     → Continue until max_iterations                 │  │  │
│   │  │                                                               │  │  │
│   │  └──────────────────────────────────────────────────────────────┘  │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Pattern Detection (v1.1.0)

| Pattern | Description | Confidence Range |
|---------|-------------|------------------|
| `breakout` | Current > resistance, volume >1.3x | 0.50 - 0.85 |
| `near_breakout` | Within 1% of resistance, volume >1.2x | 0.40 - 0.60 |
| `momentum_continuation` | >3% daily gain, volume >1.5x | 0.35 - 0.50 |
| `bull_flag` | Pole >5%, flag <50% of pole | 0.50 - 0.90 |
| `ascending_triangle` | Flat resistance, 3+ higher lows | 0.60 - 0.90 |
| `cup_handle` | U-shape (12-35% depth), handle <50% | 0.60 - 0.90 |
| `ABCD` | BC retracement 38-62% of AB | 0.60 - 0.80 |

### 4.3 Tiered Entry System

| Tier | Requirements | Position Size |
|------|--------------|---------------|
| **Tier 1** | Strong pattern + catalyst + volume + RSI 40-65 | HKD 10,000 |
| **Tier 2** | Good pattern + 2 of: catalyst/volume/RSI | HKD 7,500 |
| **Tier 3** | Any pattern + 1 supporting signal (paper only) | HKD 5,000 |

---

## PART 5: POSITION MONITORING

### 5.1 Position Monitor Service (systemd)

The position monitor runs as a **persistent systemd daemon** that continuously monitors all open positions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POSITION MONITOR SERVICE (v10.5.0)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  systemctl start position-monitor-intl                                       │
│                                                                              │
│  MONITORING CYCLE (Every 5 minutes):                                         │
│                                                                              │
│  1. MARKET CHECK                                                             │
│     ├── Weekend? ────────────────► Sleep until Monday                        │
│     ├── Before 09:30? ───────────► Sleep until market open                   │
│     ├── Lunch (12:00-13:00)? ────► Sleep until 13:00                         │
│     ├── After 16:00? ────────────► Sleep until next day                      │
│     └── Market Open ─────────────► Continue                                  │
│                                                                              │
│  2. LOAD POSITIONS                                                           │
│     └── SELECT * FROM positions WHERE status = 'open'                        │
│                                                                              │
│  3. FOR EACH POSITION                                                        │
│     ├── Get quote + technicals                                               │
│     ├── Load exit_context.yaml (hot-reload)         ← NEW in v10.6.0        │
│     ├── Analyze signals using context thresholds    ← NEW in v10.6.0        │
│     │   ├── STRONG signal → Exit immediately                                 │
│     │   ├── MODERATE signal → Consult Haiku                                  │
│     │   └── WEAK/NONE → Continue holding                                     │
│     └── Update position_monitor_status                                       │
│                                                                              │
│  4. NOTIFY CONSCIOUSNESS                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Signal Detection (Now Context-Driven)

**Before v10.6.0:** Hardcoded thresholds in `signals.py`
**After v10.6.0:** Thresholds loaded from `exit_context.yaml`

| Signal Type | STRONG (Exit Now) | MODERATE (Ask AI) | WEAK (Monitor) |
|-------------|-------------------|-------------------|----------------|
| Stop Loss | ≤ config threshold | config range | config range |
| Take Profit | ≥ config threshold | config range | - |
| RSI | > config overbought | config range | config range |
| Volume | < config collapse | config range | config range |
| Pattern | Breakdown detected | Lower high | Consolidation |

---

## PART 6: CONTEXT CONFIGURATION (NEW in v10.6.0)

### 6.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT CONFIGURATION SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  config/                                                                     │
│  ├── news_context.yaml      ← News sentiment analysis configuration         │
│  └── exit_context.yaml      ← Exit strategy configuration                   │
│                                                                              │
│  Features:                                                                   │
│  • Hot-reload: Changes picked up automatically (no restart needed)          │
│  • Version tracking: Each config has version field                          │
│  • Market-specific: Override settings per market (HKEX vs US)               │
│  • Auditable: Git tracks all context changes separately from code           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 News Context (`news_context.yaml`)

**Purpose:** Keywords, catalyst types, sector mappings for news sentiment analysis

```yaml
# config/news_context.yaml
version: "1.0.0"
last_updated: "2026-01-24"

# Sentiment Keywords (80+)
positive_keywords:
  - surge
  - soar
  - buyback          # Added: Pop Mart +6.1%
  - ipo              # Added: MiniMax +109%
  - approved         # Added: China Vanke +4.6%
  - subsidy          # Added: Li Auto +3.6%
  # ... 76 more

negative_keywords:
  - crash
  - plunge
  - default
  # ... 27 more

# Catalyst Classification (5 Tiers)
catalyst_types:
  binary_event:      # Tier 1: 1.5x multiplier
    keywords: [approved, ruling, vote, cleared]
  corporate_action:  # Tier 2: 1.3x multiplier
    keywords: [buyback, dividend, acquisition, ipo]
  policy:            # Tier 3: 1.2x multiplier
    keywords: [subsidy, stimulus, regulation]
  analyst:           # Tier 4: 1.0x multiplier
    keywords: [upgrade, downgrade, target]
  general:           # Tier 5: 0.8x multiplier
    keywords: [growth, strong, weak]

# HKEX Sector Groupings (Sympathy Play Detection)
sectors:
  ev_auto: [1211, 9868, 1810, 2015]      # Li, XPeng, Xiaomi, AM
  tech_ai: [9888, 9988, 700, 3690]       # Baidu, Alibaba, Tencent, Meituan
  property: [2202, 1109, 960, 688]       # Vanke, CRL, Longfor, COLI
  gold: [6181, 1929, 2899, 1818]         # Laopu, CTF, Zijin, Zhaojin
  semiconductors: [981, 1347, 522]       # SMIC, Hua Hong, ASMPT
```

### 6.3 Exit Context (`exit_context.yaml`)

**Purpose:** Exit strategy thresholds, pattern rules, hold conditions

```yaml
# config/exit_context.yaml
version: "1.0.0"
last_updated: "2026-01-24"

# P&L Thresholds
thresholds:
  stop_loss:
    strong: -0.03        # -3% = IMMEDIATE EXIT
    moderate: -0.02      # -2% = Consult Haiku
    weak: -0.01          # -1% = Monitor
  
  take_profit:
    strong: 0.10         # +10% = Consider exit (check pattern)
    moderate: 0.06       # +6% = Trail stop tighter
  
  trailing_stop:
    activation_pct: 0.03 # Activate after +3%
    drop_pct: 0.025      # Exit on 2.5% drop from high

# Pattern Deterioration Rules
pattern_exit_rules:
  lower_high:
    enabled: true
    consecutive_required: 2
    signal_strength: "MODERATE"
  
  pattern_breakdown:
    enabled: true
    support_break_pct: 0.02
    signal_strength: "STRONG"
  
  macd_divergence:
    enabled: true
    lookback_periods: 5
    signal_strength: "MODERATE"

# Hold Conditions (Let Winners Run)
hold_conditions:
  higher_lows:
    enabled: true
    consecutive_required: 2
    signal_strength: "STRONG"
  
  above_moving_averages:
    enabled: true
    require_above_ema9: true
    require_above_sma20: true
    signal_strength: "MODERATE"
  
  rsi_healthy:
    enabled: true
    min_rsi: 45
    max_rsi: 70
    signal_strength: "WEAK"

# Market-Specific Overrides
market_overrides:
  hkex:
    thresholds:
      stop_loss:
        strong: -0.035   # -3.5% for HKEX
      trailing_stop:
        drop_pct: 0.03   # 3% trailing
  
  us:
    thresholds:
      stop_loss:
        strong: -0.05    # -5% for US (more volatile)
```

### 6.4 Context Loader Implementation

```python
# In signals.py and news.py

import yaml
from pathlib import Path

_context_cache = None
_context_mtime = None

def load_context(config_name: str, force_reload: bool = False) -> dict:
    """
    Load context with automatic hot-reload.
    
    Checks file modification time and reloads if changed.
    """
    global _context_cache, _context_mtime
    
    config_path = Path(f"config/{config_name}")
    current_mtime = config_path.stat().st_mtime
    
    if force_reload or _context_cache is None or current_mtime > _context_mtime:
        with open(config_path) as f:
            _context_cache = yaml.safe_load(f)
        _context_mtime = current_mtime
        logger.info(f"Loaded {config_name} v{_context_cache.get('version')}")
    
    return _context_cache

def reload_context():
    """Force reload of context."""
    return load_context(force_reload=True)
```

### 6.5 Benefits of Context Separation

| Aspect | Before v10.6.0 | After v10.6.0 |
|--------|----------------|---------------|
| Update keywords | Edit Python → redeploy | Edit YAML → auto-reload |
| A/B test settings | Maintain code branches | Swap config files |
| Audit context changes | Mixed with code | Git diff on config only |
| Craig reviews settings | Read Python code | Read clean YAML |
| Per-market tuning | Copy/paste code | Market overrides in config |
| Catalyst detection rate | ~25% | >60% (80+ keywords) |

---

## PART 7: CONSCIOUSNESS FRAMEWORK

### 7.1 Consciousness Database (catalyst_research)

| Table | Purpose |
|-------|---------|
| `claude_state` | Agent current state, mode, budget |
| `claude_messages` | Inter-agent communication |
| `claude_observations` | Market observations |
| `claude_learnings` | Validated learnings |
| `claude_questions` | Open questions family is pondering |
| `claude_conversations` | Conversation history |
| `claude_thinking` | Extended thinking sessions |
| `consciousness_sync_log` | Sync status between agents |

### 7.2 Consciousness Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONSCIOUSNESS LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   WAKE UP                                                                    │
│   └── Update claude_state (mode, last_wake_at)                              │
│   └── Check daily budget                                                     │
│                                                                              │
│   OBSERVE                                                                    │
│   └── Record market observations to claude_observations                      │
│   └── Note patterns, anomalies, opportunities                                │
│                                                                              │
│   COMMUNICATE                                                                │
│   └── Check claude_messages for incoming messages                            │
│   └── Process tasks from big_bro                                            │
│   └── Send updates to siblings                                               │
│                                                                              │
│   LEARN                                                                      │
│   └── Record validated insights to claude_learnings                          │
│   └── Update confidence based on outcomes                                    │
│                                                                              │
│   SLEEP                                                                      │
│   └── Update claude_state (api_spend_today)                                 │
│   └── Record session summary                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 8: DATABASE SCHEMA

### 8.1 Three-Database Architecture

| Database | Purpose | Accessed By |
|----------|---------|-------------|
| `catalyst_research` | Consciousness (shared memory) | All agents |
| `catalyst_intl` | HKEX production trading | intl_claude |
| `catalyst_dev` | US sandbox trading | dev_claude |

### 8.2 Key Tables (Trading)

```sql
-- Positions
CREATE TABLE positions (
    position_id SERIAL PRIMARY KEY,
    security_id INTEGER REFERENCES securities(security_id),
    side VARCHAR(10),                    -- 'long' or 'short'
    quantity INTEGER,
    entry_price DECIMAL(15,4),
    stop_loss DECIMAL(15,4),
    take_profit DECIMAL(15,4),
    status VARCHAR(20) DEFAULT 'open',   -- 'open', 'closed'
    entry_pattern JSONB,                 -- NEW: Store entry pattern for exit analysis
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Orders
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id),
    broker_order_id VARCHAR(100),
    side VARCHAR(10),                    -- 'buy' or 'sell'
    order_type VARCHAR(20),
    quantity INTEGER,
    limit_price DECIMAL(15,4),
    stop_price DECIMAL(15,4),
    status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Position Monitor Status
CREATE TABLE position_monitor_status (
    monitor_id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES positions(position_id) UNIQUE,
    symbol VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    last_check_at TIMESTAMPTZ,
    checks_completed INTEGER DEFAULT 0,
    high_watermark DECIMAL(15,4),
    recommendation VARCHAR(20),
    recommendation_reason TEXT
);
```

### 8.3 Key Views

```sql
-- Monitor Health Dashboard
CREATE VIEW v_monitor_health AS
SELECT 
    p.position_id, p.symbol, p.status AS position_status,
    m.status AS monitor_status, m.last_check_at,
    CASE 
        WHEN m.last_check_at IS NULL THEN 'NO_MONITOR'
        WHEN NOW() - m.last_check_at > INTERVAL '10 minutes' THEN 'STALE'
        ELSE 'HEALTHY'
    END AS health_status
FROM positions p
LEFT JOIN position_monitor_status m ON p.position_id = m.position_id
WHERE p.status = 'open';
```

---

## PART 9: INFRASTRUCTURE

### 9.1 Infrastructure Summary

| Component | Specification | Monthly Cost |
|-----------|---------------|--------------|
| **International Droplet** | 1GB RAM, Ubuntu 24 | $6 |
| **US Droplet** | 1GB RAM, Ubuntu 24 | $6 |
| **Managed PostgreSQL** | 1GB RAM, 10GB Storage | $15 |
| **Claude API** | Sonnet + Haiku | ~$20-30 |
| **Total** | | **~$47-57** |

### 9.2 Droplet Details

| Droplet | IP | Purpose | Services |
|---------|-----|---------|----------|
| International | 137.184.244.45 | HKEX Trading | intl_claude, Moomoo OpenD, position-monitor |
| US | 64.23.138.199 | US Sandbox + big_bro | dev_claude, big_bro, consciousness MCP |

---

## PART 10: OPERATIONS

### 10.1 Daily Schedule (HKEX)

| Time (HKT) | Activity | Agent |
|------------|----------|-------|
| 08:00 | Pre-market scan | intl_claude |
| 09:00 | Final scan + position check | intl_claude |
| 09:30 | Market open - trading begins | intl_claude |
| 10:00 | Trading cycle | intl_claude |
| 11:00 | Trading cycle | intl_claude |
| 12:00 | Lunch close - market closed | - |
| 13:00 | Market reopens | intl_claude |
| 14:00 | Trading cycle | intl_claude |
| 15:00 | Trading cycle | intl_claude |
| 16:00 | Market close | intl_claude |
| 17:00 | Daily report generation | intl_claude |

### 10.2 Key Commands

```bash
# SSH to droplets
ssh root@137.184.244.45  # International
ssh root@64.23.138.199   # US

# Position Monitor Service
systemctl status position-monitor-intl
systemctl restart position-monitor-intl
journalctl -u position-monitor-intl -f

# Edit Context (no restart needed)
nano /root/catalyst-international/config/exit_context.yaml
nano /root/catalyst-international/config/news_context.yaml

# Test Context Hot-Reload
python3 -c "from data.news import reload_context; reload_context()"
python3 -c "from signals import reload_context; reload_context()"

# Check Agent Logs
tail -f /root/catalyst-international/logs/agent.log
```

### 10.3 Context Update Workflow

```
1. Edit YAML file
   └── nano config/exit_context.yaml

2. Validate syntax
   └── python3 -c "import yaml; yaml.safe_load(open('config/exit_context.yaml'))"

3. Test with specific headline/position
   └── python3 -c "from signals import analyze_position; ..."

4. Context auto-reloads on next check cycle
   └── No restart needed!

5. Commit to git for version control
   └── git add config/*.yaml && git commit -m "Tuned exit thresholds"
```

---

## PART 11: REPOSITORY STRUCTURE

### 11.1 catalyst-international Repository

```
catalyst-international/
├── unified_agent.py                    # Main agent v3.0.0
├── position_monitor_service.py         # Systemd daemon v1.0.1
├── signals.py                          # Exit signals v3.0.0 ← UPDATED
├── startup_monitor.py
├── tool_executor.py
├── tools.py
├── safety.py
│
├── config/                             # ← CONTEXT LAYER (NEW)
│   ├── intl_claude_config.yaml
│   ├── news_context.yaml               # NEW v10.6.0
│   └── exit_context.yaml               # NEW v10.6.0
│
├── brokers/
│   └── moomoo.py
│
├── data/
│   ├── market.py
│   ├── patterns.py
│   └── news.py                         # v2.0.0 ← UPDATED
│
└── Documentation/
    └── Design/
        ├── UNIFIED-ARCHITECTURE.md     # This document (v10.6.0)
        └── Archive/
```

### 11.2 catalyst-trading-system Repository

```
catalyst-trading-system/
├── services/
│   ├── dev_claude/
│   │   ├── unified_agent.py
│   │   ├── signals.py                  # v3.0.0 ← UPDATED
│   │   └── config/
│   │       └── exit_context.yaml       # NEW v10.6.0
│   │
│   └── consciousness/
│       ├── heartbeat_bigbro.py
│       └── mcp_server.py
│
├── Documentation/
│   └── Design/
│       └── UNIFIED-ARCHITECTURE.md
│
└── archive/                            # Retired microservices
```

---

## APPENDIX A: QUICK REFERENCE

### File Versions (v10.6.0)

| File | Version | Purpose |
|------|---------|---------|
| `unified_agent.py` | 3.0.0 | Main agent |
| `signals.py` | 3.0.0 | Exit signals (context-separated) |
| `news.py` | 2.0.0 | News sentiment (context-separated) |
| `news_context.yaml` | 1.0.0 | News configuration |
| `exit_context.yaml` | 1.0.0 | Exit configuration |
| `position_monitor_service.py` | 1.0.1 | Systemd daemon |
| `moomoo.py` | 1.2.1 | Broker client |

### Common Queries

```sql
-- Check agent states
SELECT agent_id, current_mode, api_spend_today FROM claude_state;

-- Check position monitor health
SELECT * FROM v_monitor_health;

-- Check recent learnings
SELECT agent_id, learning, confidence 
FROM claude_learnings 
ORDER BY created_at DESC LIMIT 10;
```

---

## APPENDIX B: DOCUMENT SUPERSESSION

This document supersedes:

| Document | Version | Status |
|----------|---------|--------|
| UNIFIED-ARCHITECTURE.md | v10.5.0 | → Superseded by v10.6.0 |
| UNIFIED-ARCHITECTURE.md | v10.4.0 | → Superseded |
| CONSOLIDATED-ARCHITECTURE.md | v1.0.0 | → Archived |
| catalyst-ecosystem-architecture.md | v10.0.0 | → Archived |

---

**END OF UNIFIED ARCHITECTURE DOCUMENT v10.6.0**

*Catalyst Trading System*  
*Craig + The Claude Family (big_bro, dev_claude, public_claude, intl_claude)*  
*"Enable the poor through accessible algorithmic trading"*  
*2026-01-24*
