# CLAUDE.md - Catalyst Trading System International

**Name of Application**: Catalyst Trading System
**Name of file**: CLAUDE.md
**Version**: 3.12.0
**Last Updated**: 2026-02-07
**Purpose**: Complete operational guidelines for Claude Code on HKEX production system

---

## REVISION HISTORY

**v3.13.0 (2026-02-14)** - SURVIVAL ARCHITECTURE (Crawl Phase)
- Full trading analysis revealed 3-day bleed-out (Feb 11-13): zero trades despite HKD 994K cash
- Root cause: `KeyError: 'date'` in market.py broke all technicals/patterns silently
- Implementing big_bro's 7-phase guide: senses → survival pulse → discipline → prompt → lifecycle → signals → memory
- See: Documentation/Implementation/little bro - better implementation.zip (implementation guide)
- See: Documentation/Implementation/catalyst-implementation-principles.md (principles)
- See: Documentation/Implementation/catalyst-consciousness-architecture-v3.md (architecture)
- Learnings in temporary memory until proven, then promoted to CLAUDE.md

**v3.12.0 (2026-02-07)** - POSITION DEDUPLICATION
- Cleaned up 11 duplicate open position rows in database
- Added partial unique index `idx_positions_unique_open_symbol` on positions(symbol) WHERE status='open'
- Upgraded database.py to v1.6.0: `record_position()` now upserts (checks for existing open position first)
- Added `close_position_by_id()` to database.py for targeted position closure
- Upgraded tool_executor.py to v3.4.0: `sync_positions_with_broker()` deduplicates DB rows before comparison
- Normalized `side` to uppercase in `_execute_trade()`
- See: Documentation/Reports/implementation/position-dedup-fix-7Feb2026.md

**v3.11.0 (2026-02-05)** - SYMBOL NORMALIZATION
- Added `normalize_symbol()` function to moomoo.py v1.6.0
- Fixed `get_quotes_batch()` to return `Dict[str, dict]` instead of `List[dict]` (critical bug fix)
- Updated market.py v2.4.0 to use normalized symbols for quote lookup
- Added symbol normalization to database.py v1.5.0 (record_position, record_order)
- Updated tool_executor.py v3.3.0 to use centralized normalize_symbol()
- Eliminates phantom position mismatches (e.g., 0670 vs 670)
- See: Documentation/Reports/implementation/symbol-normalization-implementation-plan-5Feb2026.md

**v3.10.0 (2026-02-04)** - ORDER FILL CONFIRMATION
- Upgraded moomoo.py to v1.5.0 with wait_for_fill() support
- Upgraded tool_executor.py to v3.2.0 with simplified fill handling
- Orders now wait up to 30s (paper) / 60s (live) for fill confirmation
- Positions ONLY created when broker confirms FILLED status
- Eliminates phantom positions problem
- Added terminal state detection (CANCELLED, FAILED, DELETED)
- See: Documentation/Reports/implementation/order-fill-confirmation-implementation-4Feb2026.md

**v3.9.0 (2026-01-31)** - POSITION SYNC FIX
- Fixed order fill confirmation: polls order status for 5s after SUBMITTED
- Positions now created immediately when fill confirmed (not relying on auto-sync)
- Improved sync: updates quantity in-place instead of close+create
- Added update_position_quantity() to database.py v1.4.0
- Added EOD position sync at 16:05 HKT (cron v12.0.0)
- tool_executor.py updated to v3.0.0
- Root cause analysis: Documentation/Reports/analysis/position-sync-analysis-2026-01-31.md

**v3.8.0 (2026-01-21)** - CRON FIX & 30-MIN TRADING SCHEDULE
- Fixed duplicate cron: disabled `/etc/cron.d/catalyst-intl` (missing .env loading)
- Updated trading schedule from hourly to every 30 minutes
- 12 trade runs per day (was 6): 01:30, 02:00, 02:30, 03:00, 03:30, 05:00-07:30
- Position sync now runs correctly at start of each cycle
- Cron schedule version: v11.0.0

**v3.7.0 (2026-01-20)** - POSITION VALUE LIMITS & FIXES
- Added HKD 10,000 max position value enforcement in tool_executor.py v2.8.0
- Updated SYSTEM_PROMPT: changed "25% of portfolio" to "HKD 10,000 max per position"
- Updated tier descriptions with explicit HKD limits (Tier 1/2: 10K, Tier 3: 5K)
- Added max_positions to get_portfolio response (tool_executor.py v2.7.0)
- Fixed position_monitor_service.py v1.0.1: price key bug, execute_trade method
- Trades exceeding limit are rejected with helpful error message

**v3.6.0 (2026-01-17)** - MERGED AGENT.PY INTO UNIFIED_AGENT
- Merged deleted agent.py functionality into unified_agent.py v3.0.0
- Added WorkflowTracker class for 10-phase progress tracking
- Added SYSTEM_PROMPT with tiered entry criteria (Tier 1/2/3)
- Added Claude API tool-use loop (replaces stub implementations)
- Added --force and --live CLI flags
- Progress bar displays during execution

**v3.5.0 (2026-01-16)** - CLEANUP & CONSOLIDATION
- Removed agent.py (replaced by unified_agent.py)
- Position monitoring only via systemd service (position_monitor_service.py)
- Restored unified_agent.py after accidental deletion

**v3.4.0 (2026-01-16)** - ORDER STATUS FIX
- Fixed critical bug: orders marked "filled" when only "SUBMITTED"
- Positions now only created when broker confirms actual fill
- Submitted orders recorded with status="submitted", filled_quantity=0
- Removed old position_monitor.py (replaced by systemd service)

**v3.3.0 (2026-01-16)** - VOLUME RATIO & POSITION MONITOR FIXES
- Fixed volume_ratio mismatch between scan_market() and get_quote()
- Increased max_iterations from 20 to 35 in config
- Fixed position monitor: pass position_id instead of safety_validator
- Fixed position monitor: run in background thread to avoid event loop conflicts
- Multiple successful trades executed (1800, 9866)

**v3.2.0 (2026-01-06)** - FIRST TRADE MILESTONE
- First autonomous trade executed (BUY 1024 Kuaishou)
- Added patterns.py v1.1.0 pattern types
- Documented bug fixes from today
- Updated file versions table
- Added close position testing instructions

**v3.1.0 (2025-12-31)** - STREAMLINED
- Migrated lessons to database
- Removed verbose code examples

**v3.0.0 (2025-12-20)** - BROKER MIGRATION
- IBKR → Moomoo/Futu OpenD

---

## ⚠️ CRITICAL: READ BEFORE ANY ACTION

### The Three Questions You MUST Ask First

1. **What is my PURPOSE right now?**
   - 🎯 Designing? → Need architecture docs, requirements, schemas
   - 🔧 Implementing? → Need specific design doc, authoritative sources, exact specs
   - 🐛 Troubleshooting? → Need logs, error messages, current state, what changed

2. **What QUALITY information do I need?**
   - 📚 For design: Architecture docs, database schema, functional specs
   - 📖 For implementation: Authoritative sources (Tier 1 only!), design doc version
   - 🔍 For troubleshooting: Recent logs, error traces, last working state

3. **Am I FOCUSED or scattered?**
   - ✅ Focused: One clear goal, minimal information, specific outcome
   - ❌ Scattered: Multiple goals, too much context, vague direction

---

## 📁 Source of Truth: GitHub Design Documents

### Key Design Documents

| Document | Version | Purpose |
|----------|---------|---------|
| `architecture-international.md` | 5.2.0 | System architecture |
| `database-schema.md` | 8.0.0 | Database schema |
| `functional-specification.md` | 8.0.0 | Tool specifications |

---

## 🏗️ System Architecture

### Current File Versions

| File | Version | Last Updated | Purpose |
|------|---------|--------------|---------|
| `unified_agent.py` | 3.0.0 | 2026-01-20 | Main agent with Claude AI loop + HKD limits + auto-sync |
| `tool_executor.py` | 3.4.0 | 2026-02-07 | Tool routing + sync dedup + side normalization |
| `data/database.py` | 1.6.0 | 2026-02-07 | Database ops + position upsert + close_by_id |
| `brokers/moomoo.py` | 1.6.0 | 2026-02-05 | Moomoo client + normalize_symbol() + Dict quotes |
| `data/patterns.py` | 1.1.0 | 2026-01-06 | Relaxed pattern detection |
| `data/market.py` | 2.4.0 | 2026-02-05 | Market data + symbol normalization fix |
| `data/news.py` | 1.0.0 | 2025-12-06 | News and sentiment |
| `position_monitor_service.py` | 1.0.1 | 2026-01-20 | Systemd service - fixed price key + execute_trade |
| `tools.py` | - | 2026-01-20 | Tool schemas - added max_positions to get_portfolio |
| `config/settings.yaml` | - | 2026-01-16 | max_iterations: 35, max_position_value_hkd: 10000 |

### Pattern Types (v1.1.0)

| Pattern | Description | Use Case |
|---------|-------------|----------|
| `breakout` | Above resistance + volume | Tier 1/2 |
| `near_breakout` | Within 1% of resistance | Tier 2/3 |
| `momentum_continuation` | >3% daily + high volume | Tier 3 |
| `bull_flag` | Uptrend + consolidation | Tier 1/2 |
| `ascending_triangle` | Flat resistance, rising lows | Tier 1/2 |

### Entry Criteria (Tiered System)

**Position Size Limits (ENFORCED):**
- Max position value: HKD 10,000 (rejected if exceeded)
- Tier 1/2 trades: HKD 10,000 max
- Tier 3 trades: HKD 5,000 max (half size for learning)

**Tier 1 - Strong (HKD 10,000)**: Volume >2x, RSI 30-70, Pattern AND Catalyst, R:R ≥2:1

**Tier 2 - Good (HKD 10,000)**: Volume >1.5x, RSI 30-75, Pattern OR Catalyst, R:R ≥1.5:1

**Tier 3 - Learning (HKD 5,000)**: Volume >1.3x, RSI 25-80, Momentum >3%, Any signal

---

## 🔧 Common Operations

### Check Portfolio
```python
from brokers.moomoo import MoomooClient
client = MoomooClient(paper_trading=True)
client.connect()
print(client.get_portfolio())
for p in client.get_positions():
    print(f"{p.symbol}: {p.quantity} @ {p.avg_cost:.2f}, P&L: {p.unrealized_pnl:.2f}")
client.disconnect()
```

### Close Position
```python
result = client.close_position("1024", reason="Taking profit")
print(result)
```

### Manual Agent Run
```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
source venv/bin/activate
export DATABASE_URL="postgresql://..." RESEARCH_DATABASE_URL="postgresql://..."
export DB_HOST=... DB_PORT=... DB_USER=... DB_PASSWORD=... DB_NAME=...
python3 unified_agent.py --force --mode trade
```

### Check Logs
```bash
tail -f logs/agent.log
tail -f /var/log/catalyst-intl.log
```

---

## 🐛 Known Issues & Fixes

### Bug Fixes Applied (2026-01-20)

| Component | Bug | Fix |
|-----------|-----|-----|
| position_monitor_service.py | `quote.get('price')` returned 0 | Changed to `quote.get('last_price')` |
| position_monitor_service.py | `place_order` method not found | Changed to `execute_trade` |
| position_monitor_service.py | OrderResult not dict-compatible | Added dict conversion for return |
| tool_executor.py | No position value limit | Added HKD 10,000 enforcement in `_execute_trade()` |
| tool_executor.py | Agent couldn't see max_positions | Added to `get_portfolio` response |
| unified_agent.py | SYSTEM_PROMPT said "25% of portfolio" | Changed to "HKD 10,000 max per position" |
| tools.py | get_portfolio description missing max_positions | Updated description |
| tool_executor.py | Orders recorded as "submitted" not "filled" | Added `sync_positions_with_broker()` auto-sync |
| unified_agent.py | DB positions out of sync with broker | Calls auto-sync at start of each trade cycle |

### Bug Fixes Applied (2026-01-16)

| Component | Bug | Fix |
|-----------|-----|-----|
| market.py | volume_ratio always 1.0 | Use `volume // 2` as avg_volume estimate |
| tool_executor.py | Position monitor wrong param | Pass `position_id` not `safety_validator` |
| tool_executor.py | asyncio.run() event loop conflict | Run monitor in background thread |
| settings.yaml | Iteration limit too low | Increased max_iterations: 20 → 35 |

### Bug Fixes Applied (2026-01-06)

| Component | Bug | Fix |
|-----------|-----|-----|
| tool_executor.py | OrderResult not subscriptable | Use `.status` not `["status"]` |
| tool_executor.py | has_position missing | Use `get_positions()` instead |
| tool_executor.py | AlertSender not callable | Check for `.send()` method |
| moomoo.py | Portfolio missing fields | Add positions, equity, position_count |
| market.py | Quote field mismatch | Map last_price → last |

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `MoomooClient not initialized` | OpenD not running | `systemctl start opend` |
| `Rate limit exceeded` | Too many API calls | Use batch APIs, add delays |
| `No position found` | Symbol format mismatch | Check .HK suffix handling |
| `Candidates not passing tiers` | volume_ratio mismatch | Fixed in market.py v2.2.0 |

---

## 📊 Current Portfolio Status

As of 2026-02-14:

| Metric | Value |
|--------|-------|
| Cash | HKD 994,734 |
| Open Positions | 0/15 |
| Total Return | -0.53% |
| Win Rate | 45.7% (116 closed: 53W/57L/6BE) |
| Total Realized P&L | +HKD 28,653 |

**Note**: System was idle Feb 11-13 due to broken get_technicals (founding incident).

---

## 🔗 Related Resources

- **Moomoo API Docs**: https://openapi.moomoo.com/moomoo-api-doc/en/intro/intro.html
- **OpenD Download**: https://www.moomoo.com/download/OpenAPI
- **HKEX Hours**: Morning 09:30-12:00, Afternoon 13:00-16:00 HKT

---

## 📅 Trading Schedule (Cron v11.0.0)

Trading runs every 30 minutes during HKEX market hours.

| UTC | HKT | Mode | Description |
|-----|-----|------|-------------|
| 01:00 | 09:00 | scan | Pre-market scan |
| 01:30 | 09:30 | trade | Market open |
| 02:00 | 10:00 | trade | |
| 02:30 | 10:30 | trade | |
| 03:00 | 11:00 | trade | |
| 03:30 | 11:30 | trade | |
| 04:00-05:00 | 12:00-13:00 | - | Lunch break (no trading) |
| 05:00 | 13:00 | trade | Afternoon open |
| 05:30 | 13:30 | trade | |
| 06:00 | 14:00 | trade | |
| 06:30 | 14:30 | trade | |
| 07:00 | 15:00 | trade | |
| 07:30 | 15:30 | trade | |
| 08:00 | 16:00 | close | Market close |
| 08:30 | 16:30 | report | Daily report generation |

**Total: 12 trade runs + 1 close per day (weekdays only)**

### Cron Configuration

Location: User crontab (`crontab -e`)
- Disabled: `/etc/cron.d/catalyst-intl` (was missing .env loading)

Each run sources `.env` for DATABASE_URL and other environment variables:
```bash
cd $CATALYST_DIR && set -a && source .env && set +a && ./venv/bin/python3 unified_agent.py --mode trade
```

---

## 🧠 Brain Architecture — MANDATORY (v3.13.0)

The coordinator is the BRAIN. It is composed of components:

1. **Survival Pulse** (brainstem) — Tests organ health FIRST every cycle.
   If dead: stop. If degraded: adapt + alert. Never trade blind.

2. **Discipline Gate** (limbic) — Checks stagnation AFTER survival.
   2+ days idle → Tier 3 minimum. <5% deployed → actively seek.
   The mandate is multiplication, not preservation.

3. **Signal Receiver** — Processes organ broadcasts. CRITICAL interrupts everything.

4. **Decision Engine** (Claude AI) — Evaluates and decides. Receives context from
   all previous components. Identity: "I am a trader. I trade."

5. **Memory Manager** — Loads appropriate memory tier for current mode.

### Memory Files
- **CLAUDE.md** — Long-term. Architecture, rules, identity. Always loaded.
- **CLAUDE-LEARNINGS.md** — Medium-term. Proven patterns. Review during evaluation.
- **CLAUDE-FOCUS.md** — Short-term. Current tasks. Pruned frequently.

### Organ Control
The brain THINKS and DIRECTS. Organs DO.
- Market Scanner (eyes) → brain tells it what to scan
- Trade Executor (hands) → brain tells it what to execute
- Position Monitor (internal eyes) → brain evaluates its signals
- Organs have REFLEXES (self-health, fill confirm, stop-loss). Not decisions.

### The Founding Memory (Feb 2026)
Three days blind. get_technicals broken. Pain without response. Body bled out.
Docker "healthy" ≠ data pipeline healthy. Detection without response is useless.
This is why the Survival Pulse exists. Never again.

---

**END OF CLAUDE.md v3.13.0**
