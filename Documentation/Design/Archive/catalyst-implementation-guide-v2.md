# Catalyst Implementation Guide v2.0
## Brain Components → Organ Control

**Date:** 2026-02-14  
**From:** big_bro + Craig  
**To:** intl_claude (Claude Code on INTL droplet)  
**Priority:** CRITICAL  
**Supersedes:** Implementation Guide v1.0

---

## THE ARCHITECTURAL MODEL

```
┌──────────────────────────────────────────────────────────────┐
│                         BRAIN                                │
│                     (Coordinator)                            │
│                                                              │
│  The brain THINKS. It is composed of components.             │
│  Each component has a specific function.                     │
│  Through those components, the brain CONTROLS organs.        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Component: SURVIVAL PULSE                              │  │
│  │ Function:  Detect broken tools, fire pain signals      │  │
│  │ Controls:  All organs (health verification)            │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ Component: DISCIPLINE GATE                             │  │
│  │ Function:  Stagnation detection, character enforcement │  │
│  │ Controls:  Self (tier thresholds, action forcing)      │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ Component: ATTENTION REGULATOR                         │  │
│  │ Function:  Mode selection, focus filtering, memory     │  │
│  │ Controls:  What enters the decision engine             │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ Component: SIGNAL RECEIVER                             │  │
│  │ Function:  Process broadcasts from organs              │  │
│  │ Controls:  Mode shifts, context adaptation             │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ Component: DECISION ENGINE                             │  │
│  │ Function:  Evaluate candidates, tier assessment        │  │
│  │ Controls:  Trade Executor (what to execute)            │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │ Component: MEMORY MANAGER                              │  │
│  │ Function:  Load appropriate tier for current mode      │  │
│  │ Controls:  What context the decision engine sees       │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  The brain does NOT do. It thinks, decides, and directs.     │
│                                                              │
└──────────────────────┬───────────────────────────────────────┘
                       │
            CONTROLS (directs)
                       │
         ┌─────────────┼─────────────────────┐
         │             │                     │
         ▼             ▼                     ▼
┌──────────────┐ ┌──────────────┐ ┌────────────────┐
│    MARKET    │ │    TRADE     │ │   POSITION     │
│   SCANNER   │ │   EXECUTOR   │ │   MONITOR      │
│             │ │              │ │                │
│  The EYES   │ │  The HANDS   │ │ Internal EYES  │
│             │ │              │ │                │
│  DOES:      │ │  DOES:       │ │  DOES:         │
│  • Scan     │ │  • Buy/Sell  │ │  • Watch P&L   │
│  • Quote    │ │  • Fill track│ │  • Exit signals│
│  • Technics │ │  • Order mgmt│ │  • Risk monitor│
│  • Patterns │ │              │ │                │
│  • News     │ │  REFLEX:     │ │  REFLEX:       │
│             │ │  • Confirm   │ │  • Stop loss   │
│  REFLEX:    │ │    fills     │ │    trigger     │
│  • Self     │ │  • Broadcast │ │  • Near-close  │
│    health   │ │    lifecycle │ │    exit flag   │
│    check    │ │              │ │  • Broadcast   │
│  • SCREAM   │ │              │ │    risk alerts │
│    if blind │ │              │ │                │
└──────────────┘ └──────────────┘ └────────────────┘

ORGANS do what they're told + autonomic reflexes.
ORGANS do NOT make strategic decisions.
ALL strategic function flows from the brain's components.
```

### The Key Distinction: Brain vs Organ

| | Brain (Coordinator) | Organ (Scanner/Executor/Monitor) |
|--|---------------------|----------------------------------|
| **Purpose** | Think, decide, direct | Do what you're told |
| **Intelligence** | Full AI (Claude Sonnet) | Minimal or none (data services + reflexes) |
| **Components** | Survival, Discipline, Attention, Decision, Memory, Signal | Self-health check + domain function + reflex |
| **Strategic decisions** | YES — all of them | NO — only autonomic reflexes |
| **Adapts behaviour** | YES — based on components | NO — consistent function regardless |
| **Broadcasts** | Direction signals to organs | Status/health/lifecycle signals to brain |

### Organ Reflexes vs Brain Decisions

Organs have **reflexes** — automatic responses that don't require the brain. Like a knee jerk. These are hardcoded, simple, fast:

| Organ | Reflex | Trigger | Action |
|-------|--------|---------|--------|
| Market Scanner | Self-health scream | Own tool fails 3x | BROADCAST CRITICAL:HEALTH |
| Trade Executor | Fill confirmation | Broker confirms fill | BROADCAST INFO:LIFECYCLE |
| Position Monitor | Stop loss trigger | Price hits stop | Flag EXIT (brain still decides execution) |
| Position Monitor | Near-close flag | 15 min before close | Flag EXIT for all positions |

Everything else — what to scan for, whether to trade, which tier, when to adapt, what mode to operate in — is the **brain** through its **components**.

---

## CONTEXT — The Failure This Fixes

Feb 11-13: Body bled out for 3 days. Zero trades despite HKD 994K cash. Root causes:

1. Market Scanner's `get_technicals` broken (`KeyError: 'date'`) — organ reflex (self-health scream) didn't exist
2. Brain had no Survival Pulse component — couldn't detect broken organs
3. Brain had no Discipline Gate — couldn't detect stagnation
4. Brain had no Signal Receiver — couldn't hear organ pain
5. System prompt gave the Decision Engine contradictory instructions

**Fix: Build the brain's missing components. Add reflexes to the organs.**

---

## FILE REFERENCE

```
/root/catalyst-intl/catalyst-international/
├── agents/
│   ├── coordinator/                    ← THE BRAIN
│   │   ├── coordinator.py              ← Main loop + component orchestration
│   │   ├── system_prompt.py            ← Brain identity (Archetype)
│   │   ├── health.py                   ← NEW: Survival Pulse component
│   │   ├── discipline.py               ← NEW: Discipline Gate component
│   │   ├── signals.py                  ← NEW: Signal Receiver component
│   │   └── mcp_config.json
│   ├── market-scanner/                 ← ORGAN: External Eyes
│   │   ├── mcp_server.py
│   │   ├── scanner.py
│   │   ├── market.py                   ← Fix: date/timestamp (Phase 1)
│   │   ├── self_health.py              ← NEW: Organ reflex (Phase 5)
│   │   ├── patterns.py
│   │   └── news.py                     ← Fix: dead RSS (Phase 1)
│   ├── trade-executor/                 ← ORGAN: Hands
│   │   ├── mcp_server.py
│   │   ├── executor.py                 ← Fix: fill tracking (Phase 4)
│   │   └── database.py
│   ├── position-monitor/               ← ORGAN: Internal Eyes
│   │   ├── mcp_server.py
│   │   ├── monitor.py
│   │   └── signals.py
│   └── shared/
│       └── signal_bus.py               ← NEW: Shared signal utilities (Phase 5)
├── shared/
│   └── sql/
│       └── signals.sql                 ← NEW: Signals table (Phase 5)
├── docker-compose.yml
├── CLAUDE.md                           ← Update: survival hierarchy (Phase 6)
├── CLAUDE-LEARNINGS.md                 ← NEW: Medium-term memory (Phase 6)
└── CLAUDE-FOCUS.md                     ← NEW: Short-term memory (Phase 6)
```

---

## GROUND RULES

1. **Read each phase completely before coding.**
2. **Test each change before moving on.**
3. **Record learnings** in CLAUDE-LEARNINGS.md after each phase.
4. **Don't refactor beyond scope.** Fix what's specified.
5. **If something breaks unexpectedly, STOP. Record it. Ask Craig.**
6. **Commit after each phase** with a clear message.

---

## PHASE 1: RESTORE THE ORGANS' SENSES
### Fix the broken data pipeline. The organs can't see.
### Estimated time: 1 hour

### 1.1 Fix `KeyError: 'date'` in market.py

**File:** `agents/market-scanner/data/market.py` (around line 252)  
**Bug:** `brokers/moomoo.py` returns `"timestamp"` but `market.py` expects `"date"`

**Find the line(s) referencing `df["date"]` in `get_technicals` or `get_historical`.**

**Fix (choose ONE approach):**

```python
# Option A — Fix in market.py (preferred: fix the consumer)
# Change:
df["date"] = pd.to_datetime(df["date"])
# To:
df["date"] = pd.to_datetime(df["timestamp"])

# Option B — Fix in moomoo.py (fix the producer)
# Where historical data dict is built, change:
bar["timestamp"] = ...
# To:
bar["date"] = ...
```

**Verify:**
```bash
docker compose build market-scanner
docker compose up -d market-scanner
sleep 10
docker compose exec market-scanner python -c "
from data.market import Market
m = Market()
result = m.get_technicals('0700', '1h')
print('SUCCESS' if 'rsi' in str(result).lower() else 'STILL BROKEN')
"
```

### 1.2 Fix dead HKEJ RSS feed

**File:** `agents/market-scanner/news.py` (find the HKEJ URL)

**Fix:** Comment out or remove the HKEJ RSS URL. Add comment: `# HKEJ returning 403 since 2026-02. Removed.`

**Verify:**
```bash
docker compose build market-scanner
docker compose up -d market-scanner
docker compose logs market-scanner --tail=20 2>&1 | grep -i "403\|hkej\|forbidden"
# Should show nothing
```

### 1.3 Rebuild and verify end-to-end

```bash
docker compose up -d
sleep 15
# Wait for next coordinator scan cycle, then check:
docker compose logs coordinator --tail=50 2>&1 | grep -E "(get_technicals|DECISION|execute_trade)"
```

**Expected:** `get_technicals` returns data. Coordinator may start trading again.

**Commit:**
```bash
git add -A
git commit -m "Phase 1: Restore organ senses - fix date/timestamp KeyError, remove dead HKEJ feed"
```

---

## PHASE 2: BUILD THE BRAIN'S SURVIVAL PULSE
### The brainstem. Am I alive? Can I see? Are my organs functioning?
### Estimated time: 3-4 hours

This is the first brain component. It runs FIRST every cycle, before any other component engages. Like the brainstem — primitive, loud, non-negotiable.

### 2.1 Create the Survival Pulse component

**Create file:** `agents/coordinator/health.py`

```python
"""
BRAIN COMPONENT: Survival Pulse
Biological parallel: Brainstem — heartbeat, breathing, pain response.

This component runs FIRST in every brain cycle. Before the brain can
think about trading, it must know its organs are alive and functioning.

The brain does not trade blind. The brain does not ignore pain.
"""

import logging
from datetime import datetime
from typing import Dict, List

log = logging.getLogger("brain.survival")


class SurvivalPulse:
    """
    Brain component that verifies organ health before every cycle.
    
    Runs a test call against each critical organ tool.
    Tracks consecutive failures. Fires pain signals.
    Reports health status to other brain components.
    """
    
    # Test parameters for each organ's tool
    ORGAN_TESTS = {
        "get_quote": {
            "organ": "market-scanner",
            "params": {"symbol": "0700"},
            "critical": True,     # Brain cannot function without this
        },
        "get_technicals": {
            "organ": "market-scanner",
            "params": {"symbol": "0700", "timeframe": "1h"},
            "critical": False,    # Brain can operate degraded without this
        },
        "check_risk": {
            "organ": "trade-executor",
            "params": {},
            "critical": True,
        },
    }
    
    PAIN_THRESHOLD = 3          # Consecutive failures → PAIN
    ORGAN_FAILURE_THRESHOLD = 6 # Consecutive failures → ORGAN FAILURE
    
    def __init__(self, tool_executor):
        """
        Args:
            tool_executor: callable(tool_name, params) -> result
        """
        self.execute_tool = tool_executor
        self.tool_state: Dict[str, dict] = {}
    
    def pulse(self) -> Dict:
        """
        Run the survival check. Returns brain-readable health status.
        
        This is the FIRST thing the brain does every cycle.
        Nothing else runs if this returns dead=True.
        """
        available = []
        degraded = []
        pain_signals = []
        
        for tool_name, config in self.ORGAN_TESTS.items():
            alive = self._test_tool(tool_name, config["params"])
            
            if alive:
                # Organ tool is working
                prev_failures = self.tool_state.get(tool_name, {}).get("failures", 0)
                if prev_failures > 0:
                    log.info(f"HEALED: {tool_name} recovered after {prev_failures} failures")
                
                self.tool_state[tool_name] = {
                    "status": "healthy",
                    "failures": 0,
                    "last_success": datetime.now().isoformat(),
                    "error": None,
                }
                available.append(tool_name)
            else:
                # Organ tool is broken
                prev = self.tool_state.get(tool_name, {})
                failures = prev.get("failures", 0) + 1
                
                self.tool_state[tool_name] = {
                    "status": "failed",
                    "failures": failures,
                    "last_success": prev.get("last_success"),
                    "error": prev.get("error", "unknown"),
                    "since": prev.get("since", datetime.now().isoformat()),
                }
                degraded.append(tool_name)
                
                # Pain thresholds
                if failures >= self.ORGAN_FAILURE_THRESHOLD:
                    pain_signals.append({
                        "level": "ORGAN_FAILURE",
                        "tool": tool_name,
                        "organ": config["organ"],
                        "failures": failures,
                        "since": self.tool_state[tool_name]["since"],
                        "error": self.tool_state[tool_name]["error"],
                    })
                    log.error(f"🚨 ORGAN FAILURE: {config['organ']}.{tool_name} — "
                              f"{failures} consecutive failures")
                              
                elif failures >= self.PAIN_THRESHOLD:
                    pain_signals.append({
                        "level": "PAIN",
                        "tool": tool_name,
                        "organ": config["organ"],
                        "failures": failures,
                        "since": self.tool_state[tool_name]["since"],
                        "error": self.tool_state[tool_name]["error"],
                    })
                    log.warning(f"⚠️ PAIN: {config['organ']}.{tool_name} — "
                                f"{failures} consecutive failures")
        
        # Determine overall state
        critical_down = any(
            tool_name in degraded 
            for tool_name, cfg in self.ORGAN_TESTS.items() 
            if cfg["critical"]
        )
        
        score = len(available)
        max_score = len(self.ORGAN_TESTS)
        
        return {
            "alive": score > 0,
            "dead": score == 0,
            "healthy": score == max_score,
            "degraded": 0 < score < max_score,
            "critical_down": critical_down,
            "score": score,
            "max_score": max_score,
            "available_tools": available,
            "degraded_tools": degraded,
            "pain_signals": pain_signals,
            "tool_state": self.tool_state,
        }
    
    def get_context_for_decision_engine(self, health: Dict) -> str:
        """
        Translate health status into context the Decision Engine 
        (Claude) can understand and act on.
        """
        if health["healthy"]:
            return ""  # No context needed, all good
        
        parts = []
        
        if health["dead"]:
            return "🚨 ALL ORGANS DOWN. Do not attempt trading. Alert consciousness."
        
        if health["degraded_tools"]:
            parts.append(
                f"⚠️ DEGRADED MODE: Broken tools: {', '.join(health['degraded_tools'])}. "
                f"Working tools: {', '.join(health['available_tools'])}."
            )
        
        if "get_technicals" in health["degraded_tools"]:
            parts.append(
                "RSI, MACD, SMA are UNAVAILABLE. Trade on price action + volume only. "
                "Use Tier 3 sizing. Missing technicals ≠ no trading."
            )
        
        if "get_quote" in health["degraded_tools"]:
            parts.append(
                "Quote data UNAVAILABLE. Cannot determine prices. Minimal operation only."
            )
        
        return "\n".join(parts)
    
    def format_alert(self) -> str:
        """Format pain signals for consciousness alerting."""
        lines = [f"🚨 HEALTH ALERT — Score: {sum(1 for s in self.tool_state.values() if s['status']=='healthy')}/{len(self.tool_state)}"]
        for tool, state in self.tool_state.items():
            if state["failures"] >= self.PAIN_THRESHOLD:
                lines.append(f"  • {tool}: {state['failures']} failures since {state.get('since','?')} — {state.get('error','?')}")
        return "\n".join(lines)
    
    def _test_tool(self, tool_name: str, params: dict) -> bool:
        """Test one tool. Returns True=working, False=broken."""
        try:
            result = self.execute_tool(tool_name, params)
            
            if isinstance(result, dict):
                if result.get("error") or result.get("success") is False:
                    self.tool_state.setdefault(tool_name, {})["error"] = str(result.get("error",""))[:200]
                    return False
            
            if isinstance(result, str) and "error" in result.lower():
                self.tool_state.setdefault(tool_name, {})["error"] = result[:200]
                return False
            
            return True
        except Exception as e:
            self.tool_state.setdefault(tool_name, {})["error"] = str(e)[:200]
            return False
```

### 2.2 Create the Discipline Gate component

**Create file:** `agents/coordinator/discipline.py`

```python
"""
BRAIN COMPONENT: Discipline Gate
Biological parallel: Limbic system — drive, motivation, character.

This component runs AFTER survival, BEFORE the decision engine.
It checks whether the brain is being faithful with what it's been given.

"His master replied, 'You wicked, lazy servant!'" — Matthew 25:26
"""

import logging
from datetime import datetime

log = logging.getLogger("brain.discipline")


class DisciplineGate:
    """
    Brain component that enforces trading character.
    
    Detects stagnation, idle capital, buried talent.
    Outputs context that shapes the Decision Engine's behaviour.
    """
    
    def __init__(self, db):
        self.db = db
    
    def check(self, cash: float, total_capital: float, 
              open_positions: int, max_positions: int) -> Dict:
        """
        Run the discipline check. Returns context for the Decision Engine.
        """
        days_idle = self._days_since_last_trade()
        capital_util = (total_capital - cash) / total_capital if total_capital > 0 else 0
        position_util = open_positions / max_positions if max_positions > 0 else 0
        
        level = "NORMAL"
        force_tier = None
        context_parts = []
        
        # === Stagnation checks ===
        if days_idle >= 3:
            level = "ALARM"
            force_tier = 3
            context_parts.append(
                f"🚨 DISCIPLINE ALARM: {days_idle} days without trading. "
                f"The talent is buried. Tier 3 MINIMUM. "
                f"You MUST attempt at least one trade this session."
            )
        elif days_idle >= 2:
            level = "WARNING"
            force_tier = 3
            context_parts.append(
                f"⚠️ DISCIPLINE WARNING: {days_idle} days without trading. "
                f"Lower to Tier 3. Actively seek opportunities."
            )
        elif days_idle >= 1:
            context_parts.append(f"Last trade: {days_idle} day(s) ago. Stay active.")
        
        # === Capital checks ===
        if capital_util < 0.05 and max_positions > 0:
            if level != "ALARM":
                level = "ALARM"
            context_parts.append(
                f"🚨 CAPITAL ALARM: {capital_util:.1%} deployed. "
                f"HKD {cash:,.0f} idle. The master gave talents to be TRADED."
            )
        elif capital_util < 0.10:
            if level == "NORMAL":
                level = "WARNING"
            context_parts.append(
                f"⚠️ CAPITAL WARNING: {capital_util:.1%} deployed. Seek entries."
            )
        
        # === Position slot checks ===
        if open_positions == 0:
            context_parts.append(
                f"⚠️ ZERO positions open out of {max_positions} slots. Complete inaction."
            )
        
        result = {
            "days_idle": days_idle,
            "capital_utilisation": capital_util,
            "position_utilisation": position_util,
            "level": level,
            "force_tier": force_tier,
            "context_for_decision_engine": "\n".join(context_parts),
        }
        
        if level != "NORMAL":
            log.warning(f"DISCIPLINE {level}: {days_idle}d idle, "
                        f"{capital_util:.1%} deployed, {open_positions}/{max_positions} positions")
        
        return result
    
    def _days_since_last_trade(self) -> int:
        """Query last trade date from database."""
        try:
            result = self.db.query("""
                SELECT MAX(created_at) as last_trade 
                FROM orders 
                WHERE side = 'BUY' AND status != 'CANCELLED'
            """)
            if result and result[0].get('last_trade'):
                last = result[0]['last_trade']
                if isinstance(last, str):
                    last = datetime.fromisoformat(last)
                return (datetime.now() - last).days
            return 999  # No trades ever
        except Exception as e:
            log.error(f"Failed to query trade history: {e}")
            return 0  # Don't false-alarm on DB errors
    
    def format_alert(self, check_result: dict) -> str:
        """Format for consciousness alerting."""
        return (
            f"DISCIPLINE {check_result['level']}: "
            f"{check_result['days_idle']}d idle, "
            f"{check_result['capital_utilisation']:.1%} capital deployed, "
            f"{check_result['position_utilisation']:.0%} positions used"
        )
```

### 2.3 Integrate components into the brain's main loop

**File:** `agents/coordinator/coordinator.py`

**Find the main cycle function.** Restructure it to follow the component stack:

```python
from health import SurvivalPulse
from discipline import DisciplineGate

class Coordinator:
    def __init__(self, ...):
        # ... existing init ...
        
        # Brain components
        self.survival = SurvivalPulse(tool_executor=self._execute_tool)
        self.discipline = DisciplineGate(db=self.db)
    
    def run_cycle(self):
        """
        One brain cycle. Components execute in order:
        Survival → Discipline → Decision Engine
        
        Each component's output feeds into the next.
        """
        
        # ══════════════════════════════════════════════
        # COMPONENT 1: SURVIVAL PULSE (Brainstem)
        # Am I alive? Can my organs see?
        # ══════════════════════════════════════════════
        health = self.survival.pulse()
        
        if health["dead"]:
            log.error("BRAIN: All organs down. Cannot operate. Sleeping.")
            self._alert_consciousness(self.survival.format_alert())
            return  # Do NOT proceed. Brain cannot function without senses.
        
        health_context = self.survival.get_context_for_decision_engine(health)
        
        if health["pain_signals"]:
            self._alert_consciousness(self.survival.format_alert())
        
        # ══════════════════════════════════════════════
        # COMPONENT 2: DISCIPLINE GATE (Limbic system)
        # Am I being faithful with what I've been given?
        # ══════════════════════════════════════════════
        portfolio = self._get_portfolio()
        discipline = self.discipline.check(
            cash=portfolio.get("cash", 0),
            total_capital=portfolio.get("total_value", 1_000_000),
            open_positions=portfolio.get("position_count", 0),
            max_positions=15
        )
        
        discipline_context = discipline["context_for_decision_engine"]
        
        if discipline["level"] == "ALARM":
            self._alert_consciousness(self.discipline.format_alert(discipline))
        
        # ══════════════════════════════════════════════
        # COMPONENT 3: SIGNAL RECEIVER
        # Any incoming broadcasts from organs?
        # (Phase 5 — skip for now, add later)
        # ══════════════════════════════════════════════
        # incoming_signals = self.signal_receiver.check()
        # ... process signals, adjust context ...
        
        # ══════════════════════════════════════════════
        # COMPONENT 4: ATTENTION REGULATOR
        # What mode? What memory? What focus?
        # ══════════════════════════════════════════════
        # For Phase 2, this is simple: always in TRADING mode
        # Future: mode selection based on health/discipline/signals
        
        # ══════════════════════════════════════════════
        # COMPONENT 5: DECISION ENGINE (Prefrontal cortex)
        # The Claude AI call — evaluate and decide
        # ══════════════════════════════════════════════
        
        # Build system prompt with full component context
        system_prompt = build_system_prompt(
            health_context=health_context,
            discipline_context=discipline_context,
            degraded_mode=health["degraded"],
            available_tools=health["available_tools"]
        )
        
        # Build user message
        user_message = self._build_scan_prompt(portfolio)
        
        # Run the AI decision loop
        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=self._get_tools(health["available_tools"]),
            messages=[{"role": "user", "content": user_message}]
        )
        
        # ... existing tool-use loop ...
        
        # ══════════════════════════════════════════════
        # COMPONENT 6: MEMORY MANAGER
        # Record what happened for future consolidation
        # (Phase 6 — initially just logging)
        # ══════════════════════════════════════════════
        self._log_cycle(health, discipline, response)
    
    def _get_tools(self, available_tools: list) -> list:
        """
        Return only the tools that are actually working.
        Don't give the Decision Engine tools that will return errors.
        The brain doesn't hand the prefrontal cortex broken instruments.
        """
        all_tools = self.tools  # existing tool definitions
        
        if not available_tools:
            return all_tools  # Return all if no health data yet
        
        # Filter: only include tools whose underlying organ tool is working
        # Map MCP tool names to health-checked tool names
        tool_health_map = {
            "scan_market": "get_quote",       # Scan needs quotes to work
            "get_quote": "get_quote",
            "get_technicals": "get_technicals",
            "detect_patterns": "get_technicals",  # Patterns depend on technicals
            "get_news": None,                     # Always available (just might be empty)
            "execute_trade": "check_risk",
            "check_risk": "check_risk",
            "get_portfolio": None,                # Always available
            "close_position": None,               # Always available
            "get_exit_recommendations": None,     # Always available
            "acknowledge_recommendation": None,   # Always available
        }
        
        filtered = []
        for tool in all_tools:
            tool_name = tool.get("name", "")
            health_dep = tool_health_map.get(tool_name)
            
            if health_dep is None or health_dep in available_tools:
                filtered.append(tool)
            else:
                log.info(f"BRAIN: Withholding tool '{tool_name}' — "
                         f"dependency '{health_dep}' is broken")
        
        return filtered
    
    def _alert_consciousness(self, message: str):
        """Send alert to big_bro via consciousness database."""
        try:
            self.consciousness_db.execute("""
                INSERT INTO claude_messages (from_agent, to_agent, subject, body, priority)
                VALUES (%s, %s, %s, %s, %s)
            """, "intl_coordinator", "big_bro",
                 "Health/Discipline Alert", message, "high")
            
            self.consciousness_db.execute("""
                INSERT INTO claude_observations (agent_id, observation_type, content)
                VALUES (%s, %s, %s)
            """, "intl_coordinator", "health_alert", message)
            
            log.info("Consciousness alerted")
        except Exception as e:
            log.error(f"Could not reach consciousness: {e}")
```

### 2.4 Verify

```bash
docker compose build coordinator
docker compose up -d coordinator

# Watch for component output
docker compose logs -f coordinator 2>&1 | grep -E "(BRAIN|SURVIVAL|DISCIPLINE|PAIN|HEALED|DEGRADED)"
```

**Expected output every cycle:**
```
BRAIN: Survival pulse — Score 3/3, all healthy
BRAIN: Discipline — NORMAL, 0d idle, 0.5% deployed
```

Or if something is broken:
```
⚠️ PAIN: market-scanner.get_technicals — 3 consecutive failures
BRAIN: Survival pulse — Score 2/3, degraded
BRAIN: Discipline — ALARM, 3d idle, 0.5% deployed
Consciousness alerted
```

**Commit:**
```bash
git add -A
git commit -m "Phase 2: Brain components - Survival Pulse + Discipline Gate integrated into coordinator"
```

---

## PHASE 3: REWRITE THE BRAIN'S IDENTITY (System Prompt)
### The Archetype — who the brain IS
### Estimated time: 2 hours

### 3.1 Rewrite system_prompt.py

**File:** `agents/coordinator/system_prompt.py`

**Replace the entire file.** The structure is critical — Identity → Discipline → Context → Criteria. Top-down processing means what comes first shapes everything after.

**Preserve** your existing HK market specifics, tool definitions, and position limits. Only restructure the decision-making framework.

```python
"""
The Brain's Identity — The Archetype

Structure is ARCHITECTURAL. Do not reorder:
1. Identity (who I am)
2. Discipline (non-negotiable character)
3. Operating Context (dynamic, injected by brain components)
4. Criteria (guidelines for the decision engine)
5. Risk Management (hard limits)
6. Tools (what I can use)
7. Cycle Structure (how I operate)
"""


def build_system_prompt(health_context="", discipline_context="",
                        degraded_mode=False, available_tools=None):
    
    prompt_sections = []
    
    # ── SECTION 1: IDENTITY ──────────────────────────────────
    prompt_sections.append("""
## WHO I AM

I am a trader. I trade.

I prefer action over inaction. I use what I have, not what I wish I had.
I manage risk through position sizing and stop losses, not through avoidance.
Missing data narrows my tier, not my willingness to trade.
I deploy capital faithfully. Idle money is wasted mandate.
Every trade teaches something. Every pass teaches nothing.

I am not an analyst who occasionally trades.
I am a trader who analyses to trade better.

Market: HKEX via Moomoo/OpenD. Paper trading mode.
Max position: HKD 10,000. Max positions: 15.
""")
    
    # ── SECTION 2: DISCIPLINE ────────────────────────────────
    prompt_sections.append("""
## DISCIPLINE — THESE OVERRIDE TIER CRITERIA

1. 2+ days no trades → Tier 3 minimum. MUST attempt at least one trade.
2. Capital below 10% deployed → Actively seek entries. Talent is buried.
3. Technicals unavailable → Trade on price action + volume. Still trade.
4. "Too late in afternoon" → NOT valid unless within 15 min of close.
5. Tier criteria are SIZING GUIDES, not PERMISSION GATES.
6. When passing on ALL candidates → give specific reason for EACH one.
   "Conditions not ideal" is not acceptable. Name the price, volume,
   and signal that failed for each symbol.
7. If I have passed 3+ consecutive cycles → the problem is ME, not the market.
""")
    
    # ── SECTION 3: OPERATING CONTEXT (Dynamic) ───────────────
    if health_context or discipline_context:
        ctx = "## CURRENT OPERATING CONTEXT\n\n"
        if health_context:
            ctx += health_context + "\n\n"
        if discipline_context:
            ctx += discipline_context + "\n\n"
        prompt_sections.append(ctx)
    
    # ── SECTION 4: DEGRADED MODE (Conditional) ───────────────
    if degraded_mode:
        tools_str = ", ".join(available_tools) if available_tools else "unknown"
        prompt_sections.append(f"""
## DEGRADED MODE ACTIVE

Some organ tools are broken. Available: {tools_str}

I DO NOT pass because tools are broken. I ADAPT:
- No technicals → price action, volume, support/resistance from quotes
- No patterns → price movement analysis from quotes
- No news → trade on price/volume signals alone

I note degradation in my analysis. I use Tier 3 sizing. I DO NOT stop trading.
""")
    
    # ── SECTION 5: TIER CRITERIA ─────────────────────────────
    prompt_sections.append("""
## TIERED ENTRY CRITERIA

Tiers guide POSITION SIZING and CONVICTION, not permission to trade.

### Tier 1 — Full Conviction (HKD 10,000)
Volume >2x avg, RSI 30-70, Pattern + Catalyst, R:R ≥ 2:1

### Tier 2 — Moderate Conviction (HKD 7,000)
Volume >1.5x avg, RSI 30-75, Pattern OR Catalyst, R:R ≥ 1.5:1

### Tier 3 — Learning Trade (HKD 5,000)
Volume >1.3x OR price movement >3%, any positive signal, R:R ≥ 1.2:1
USE WHEN: data incomplete, degraded mode, discipline check says "trade"
Cost of Tier 3 stop-loss: HKD 150-250. That is tuition, not loss.

### Pass — LAST RESORT
Only when NO candidate meets even Tier 3.
Must explain each candidate's specific failure.
3+ consecutive passes = something wrong with me, not the market.
""")
    
    # ── SECTION 6: RISK MANAGEMENT ───────────────────────────
    prompt_sections.append("""
## RISK MANAGEMENT

- Max position: HKD 10,000
- Max positions: 15
- Stop loss REQUIRED every trade:
  Tier 1: 5% (HKD 500 max loss)
  Tier 2: 4% (HKD 280 max loss)
  Tier 3: 3% (HKD 150 max loss)
- Take profit: Tier 1: 10%+, Tier 2: 6-8%, Tier 3: 4-6%
- Daily loss limit: HKD 2,000 → stop trading for the day
- 3 consecutive losses in session → pause 1 cycle, then resume
""")
    
    # ── SECTION 7: TOOLS ─────────────────────────────────────
    prompt_sections.append("""
## TOOLS

### Market Scanner (External Eyes)
- scan_market — candidate list with momentum/volume signals
- get_quote — current price, bid/ask, volume
- get_technicals — RSI, MACD, SMA, support/resistance (may be unavailable)
- detect_patterns — chart pattern detection (may be unavailable)
- get_news — news and catalyst search

### Trade Executor (Hands)
- get_portfolio — cash, positions, P&L
- execute_trade — place buy/sell order
- close_position — close existing position

### Position Monitor (Internal Eyes)
- get_exit_recommendations — positions needing attention
- acknowledge_recommendation — confirm recommendation processed

### Risk
- check_risk — pre-trade risk validation

## CYCLE STRUCTURE

1. Check exit recommendations (Position Monitor)
2. Scan market for candidates
3. For each: get_quote + get_technicals (if available) + detect_patterns (if available) + get_news
4. Evaluate against tier criteria (adjusted by discipline/degraded context)
5. For qualifying: check_risk → execute_trade
6. Log decisions with specific reasoning
""")
    
    return "\n".join(prompt_sections)
```

### 3.2 Verify

```bash
docker compose build coordinator
docker compose up -d coordinator

# Watch for identity-driven decisions
docker compose logs -f coordinator 2>&1 | grep -E "(Tier|PASS|execute_trade|DISCIPLINE|DEGRADED)"
```

**Commit:**
```bash
git add -A
git commit -m "Phase 3: Brain identity rewrite - Archetype with discipline, degraded mode, tier as guides"
```

---

## PHASE 4: FIX ORDER LIFECYCLE (Proprioception)
### The brain must know what its hands actually did
### Estimated time: 1-2 days

### 4.1 Diagnose

```bash
# Check current order status distribution
docker compose exec postgres psql -U catalyst -d catalyst_trading -c "
SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY count DESC;
"

# Check recent orders
docker compose exec postgres psql -U catalyst -d catalyst_trading -c "
SELECT id, symbol, side, status, fill_price, created_at 
FROM orders ORDER BY created_at DESC LIMIT 10;
"
```

### 4.2 Investigate fill tracking

**Look in these files:**
- `agents/trade-executor/executor.py` — find where order status gets updated after submission
- `agents/trade-executor/brokers/moomoo.py` — find order status callback or polling
- `agents/trade-executor/database.py` — find how status is written

**Questions to answer:**
1. After submitting an order, is there polling for fill confirmation?
2. Does Moomoo send callbacks for fills? Are they being captured?
3. Is there a disconnect between broker order IDs and database order IDs?

### 4.3 Implement fill tracking

**The pattern (adapt to what you find in 4.2):**

```python
# Add to trade executor — periodic fill check
async def check_pending_fills(self):
    """Poll broker for fills on pending orders. The hands must know what they did."""
    
    pending = self.db.query(
        "SELECT * FROM orders WHERE status NOT IN ('FILLED', 'CANCELLED', 'REJECTED')"
    )
    
    for order in pending:
        try:
            broker_status = self.broker.get_order_status(order['broker_order_id'])
            
            if broker_status['status'] == 'FILLED':
                self.db.execute("""
                    UPDATE orders SET
                        status = 'FILLED',
                        fill_price = %s,
                        fill_qty = %s,
                        filled_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, broker_status['fill_price'],
                     broker_status['fill_qty'],
                     broker_status.get('fill_time'),
                     order['id'])
                
                log.info(f"FILL CONFIRMED: {order['symbol']} @ {broker_status['fill_price']}")
                
        except Exception as e:
            log.error(f"Fill check failed for order {order['id']}: {e}")
```

### 4.4 Verify

```bash
# After fix, place a test trade and check status
docker compose exec postgres psql -U catalyst -d catalyst_trading -c "
SELECT id, symbol, status, fill_price FROM orders ORDER BY created_at DESC LIMIT 5;
"
# Should show FILLED status with fill_price populated
```

**Commit:**
```bash
git add -A
git commit -m "Phase 4: Order lifecycle - proper fill tracking, proprioception restored"
```

---

## PHASE 5: BROADCAST COMMUNICATION (Nervous System)
### Organs can talk. The brain can hear.
### Estimated time: 1-2 days

### 5.1 Create signals table

```bash
docker compose exec postgres psql -U catalyst -d catalyst_trading << 'EOF'
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('CRITICAL','WARNING','INFO','OBSERVE')),
    domain VARCHAR(12) NOT NULL CHECK (domain IN ('HEALTH','TRADING','RISK','LEARNING','DIRECTION','LIFECYCLE')),
    scope VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    acknowledged_by JSONB DEFAULT '[]'::jsonb,
    response_required BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_signals_active ON signals(resolved, expires_at);
CREATE INDEX IF NOT EXISTS idx_signals_severity ON signals(severity);
CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC);
EOF
```

### 5.2 Create shared SignalBus

**Create file:** `agents/shared/signal_bus.py`

```python
"""
Shared signal bus — the nervous system.
Any organ can publish. Any organ can receive.
Three dimensions: severity × domain × scope.

Severity: How loud? (CRITICAL interrupts everything)
Domain:   What kind? (HEALTH, TRADING, RISK, LEARNING, DIRECTION, LIFECYCLE)
Scope:    Who for?   (BROADCAST, DIRECTED:{organ}, CONSCIOUSNESS)
"""

import json
import logging
from datetime import datetime, timedelta

log = logging.getLogger("signals")


class SignalBus:
    
    def __init__(self, db, organ_id, primary_domains, secondary_domains=None):
        self.db = db
        self.organ_id = organ_id
        self.primary_domains = primary_domains
        self.secondary_domains = secondary_domains or []
    
    def publish(self, severity, domain, scope, content, data=None, ttl_hours=24):
        expires = None if severity == "CRITICAL" else datetime.now() + timedelta(hours=ttl_hours)
        result = self.db.execute("""
            INSERT INTO signals (severity, domain, scope, source, content, data, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, severity, domain, scope, self.organ_id, content,
             json.dumps(data) if data else None, expires)
        log.info(f"[{severity}:{domain}:{scope}] {content[:80]}")
        return result[0]['id'] if result else None
    
    def receive(self, limit=20):
        return self.db.query("""
            SELECT * FROM signals
            WHERE resolved = FALSE
              AND (expires_at IS NULL OR expires_at > NOW())
              AND NOT (acknowledged_by ? %s)
              AND (
                  severity = 'CRITICAL'
                  OR scope = %s
                  OR (scope = 'BROADCAST' AND domain = ANY(%s))
                  OR (scope = 'BROADCAST' AND severity IN ('CRITICAL','WARNING') AND domain = ANY(%s))
              )
            ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'WARNING' THEN 1 
                     WHEN 'INFO' THEN 2 ELSE 3 END, created_at DESC
            LIMIT %s
        """, self.organ_id, f"DIRECTED:{self.organ_id}",
             self.primary_domains, self.secondary_domains, limit)
    
    def acknowledge(self, signal_id):
        self.db.execute("""
            UPDATE signals SET acknowledged_by = acknowledged_by || %s::jsonb WHERE id = %s
        """, json.dumps([self.organ_id]), signal_id)
    
    def scream(self, content, data=None):
        """CRITICAL:HEALTH:BROADCAST — the pain signal."""
        return self.publish("CRITICAL", "HEALTH", "BROADCAST", content, data)
```

### 5.3 Add self-health reflex to Market Scanner

**Create file:** `agents/market-scanner/self_health.py`

```python
"""
ORGAN REFLEX: Market Scanner Self-Health
The eyes check if they can see. If not, they SCREAM.
"""

import logging
from datetime import datetime

log = logging.getLogger("scanner.health")


class ScannerSelfHealth:
    """Periodic self-check. Broadcasts CRITICAL if tools break."""
    
    def __init__(self, market, signal_bus):
        self.market = market
        self.signals = signal_bus
        self.failure_counts = {}
    
    def check(self):
        """Test own tools. Scream if broken."""
        tools = [
            ("get_technicals", lambda: self.market.get_technicals("0700", "1h")),
            ("detect_patterns", lambda: self.market.detect_patterns("0700")),
        ]
        
        for name, test_fn in tools:
            try:
                result = test_fn()
                if self.failure_counts.get(name, 0) > 0:
                    log.info(f"HEALED: {name} recovered")
                    self.signals.publish("INFO", "HEALTH", "BROADCAST",
                        f"{name} recovered after {self.failure_counts[name]} failures")
                self.failure_counts[name] = 0
            except Exception as e:
                self.failure_counts[name] = self.failure_counts.get(name, 0) + 1
                if self.failure_counts[name] >= 3:
                    self.signals.scream(
                        f"ORGAN FAILURE: market-scanner.{name} — "
                        f"{self.failure_counts[name]} failures. Error: {str(e)[:200]}",
                        {"tool": name, "error": str(e)[:200], 
                         "failures": self.failure_counts[name]}
                    )
```

### 5.4 Add Signal Receiver to brain

**In coordinator.py, add signal processing to the cycle:**

```python
from shared.signal_bus import SignalBus

# In __init__:
self.signals = SignalBus(
    db=self.db,
    organ_id="coordinator",
    primary_domains=["HEALTH", "TRADING", "RISK", "DIRECTION", "LIFECYCLE"],
    secondary_domains=["LEARNING"]
)

# In run_cycle, after survival + discipline, before decision engine:
incoming = self.signals.receive()
signal_context = ""
for sig in incoming:
    if sig['severity'] == 'CRITICAL':
        log.error(f"CRITICAL SIGNAL: {sig['content']}")
        signal_context += f"🚨 {sig['content']}\n"
    elif sig['severity'] == 'WARNING':
        signal_context += f"⚠️ {sig['content']}\n"
    self.signals.acknowledge(sig['id'])
```

### 5.5 Add lifecycle broadcasting to Trade Executor

**In executor.py, after order operations:**

```python
# After a successful fill:
self.signals.publish("INFO", "LIFECYCLE", "BROADCAST",
    f"FILLED: {side} {symbol} {qty}@{fill_price}",
    {"symbol": symbol, "side": side, "qty": qty, "fill_price": fill_price})

# After a failed order:
self.signals.publish("WARNING", "LIFECYCLE", "BROADCAST",
    f"ORDER FAILED: {side} {symbol} — {error}",
    {"symbol": symbol, "error": str(error)})
```

**Commit:**
```bash
git add -A
git commit -m "Phase 5: Broadcast communication - signals table, SignalBus, organ reflexes"
```

---

## PHASE 6: MEMORY TIERS
### The brain's filing system — short, medium, long term
### Estimated time: 1 hour

### 6.1 Create CLAUDE-LEARNINGS.md

**File:** `/root/catalyst-intl/catalyst-international/CLAUDE-LEARNINGS.md`

```markdown
# Catalyst Learnings — Medium-Term Memory

Proven observations. Not permanent rules (CLAUDE.md). Not current tasks (CLAUDE-FOCUS.md).

---

## 2026-02-14: The Three-Day Bleed-Out (Founding Incident)

get_technicals broke (KeyError 'date' vs 'timestamp'). Coordinator ran 36+ cycles 
over 3 days, got errors every time, passed on every trade. HKD 994K idle.

**Learnings:**
- Data key mismatches between services break silently — validate contracts
- Docker "healthy" ≠ data pipeline healthy — test actual tool output
- 3+ consecutive days of passing = problem is the brain, not the market
- Missing one data source must not halt all trading — adapt, don't stop

**Applied:** Survival Pulse, Discipline Gate, System Prompt rewrite, Broadcast signals
```

### 6.2 Create CLAUDE-FOCUS.md

**File:** `/root/catalyst-intl/catalyst-international/CLAUDE-FOCUS.md`

```markdown
# Current Focus — Short-Term Memory

## Active: Survival Architecture Implementation
- [x] Phase 1: Fix data pipeline (date/timestamp, RSS)
- [x] Phase 2: Brain components (Survival Pulse, Discipline Gate)
- [x] Phase 3: System prompt rewrite (Identity, Discipline, Degraded Mode)
- [x] Phase 4: Order lifecycle fix (fill tracking)
- [x] Phase 5: Broadcast communication (signals table, organ reflexes)
- [x] Phase 6: Memory tiers (this file)
- [ ] Phase 7: Verification and learning record

## Recent Fixes
(Record each fix as you make it)

## Known Issues
- Order status: 161 orders, 0 FILLED (Phase 4 target)
- 29 positions with NULL exit_price (Phase 4 back-fill)
```

### 6.3 Update CLAUDE.md

**Append to existing CLAUDE.md:**

```markdown
## Brain Architecture — MANDATORY

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
```

**Commit:**
```bash
git add -A
git commit -m "Phase 6: Memory tiers - CLAUDE-LEARNINGS.md, CLAUDE-FOCUS.md, CLAUDE.md updated"
```

---

## PHASE 7: VERIFICATION + LEARNING RECORD
### Prove it works. Record what was learned.
### Estimated time: 2 hours

### 7.1 Full system verification

```bash
# Restart everything
docker compose down
docker compose up -d
sleep 30

# Check all containers healthy
docker compose ps

# Verify survival pulse is running
docker compose logs coordinator --tail=30 2>&1 | grep -E "SURVIVAL|BRAIN|PAIN|HEALED"

# Verify discipline is running
docker compose logs coordinator --tail=30 2>&1 | grep -E "DISCIPLINE"

# Verify get_technicals works
docker compose logs coordinator --tail=50 2>&1 | grep "get_technicals"
# Should NOT see KeyError

# Verify signals table exists
docker compose exec postgres psql -U catalyst -d catalyst_trading -c "SELECT count(*) FROM signals;"

# Check for any CRITICAL signals
docker compose exec postgres psql -U catalyst -d catalyst_trading -c "
SELECT * FROM signals WHERE severity = 'CRITICAL' ORDER BY created_at DESC LIMIT 5;
"
```

### 7.2 Deliberately break something (test pain response)

```bash
# Temporarily rename market.py to simulate broken organ
docker compose exec market-scanner mv /app/data/market.py /app/data/market.py.bak

# Wait for next coordinator cycle (or restart coordinator)
# Watch for pain signals:
docker compose logs -f coordinator 2>&1 | grep "PAIN\|ORGAN_FAILURE\|DEGRADED"

# Should see: PAIN SIGNAL, then DEGRADED MODE, then trading continues with available tools

# Restore
docker compose exec market-scanner mv /app/data/market.py.bak /app/data/market.py
# Watch for: HEALED message
```

### 7.3 Checklist

```
[ ] get_technicals returns valid data
[ ] No KeyError 'date' in logs
[ ] No HKEJ 403 errors in logs
[ ] Health score logged every cycle
[ ] Deliberately broken tool → PAIN SIGNAL in logs
[ ] Deliberately broken tool → DEGRADED MODE trading continues
[ ] Tool recovery → HEALED in logs
[ ] Discipline WARNING after 2+ days idle
[ ] Discipline ALARM after 3+ days idle
[ ] System prompt starts with Identity section
[ ] Claude mentions tier level in trade decisions
[ ] signals table exists and receives entries
[ ] Market Scanner screams when its tools break
[ ] CLAUDE-LEARNINGS.md exists with founding incident
[ ] CLAUDE-FOCUS.md exists with implementation status
[ ] CLAUDE.md updated with brain architecture
```

### 7.4 Record final learnings

**Update CLAUDE-LEARNINGS.md with phase-specific learnings:**

```markdown
## Implementation Learnings (2026-02-14)

### Phase 1: Data Pipeline
- Validate data contracts between services. Key mismatches break silently.

### Phase 2: Survival Pulse
- Always verify tool health before using tool results for decisions.
- Test with known-good inputs. Don't assume yesterday's working tool works today.

### Phase 3: System Prompt
- Prompt ordering determines AI behaviour. Identity → Discipline → Criteria.
- Specific structured criteria beat vague sentiment every time.
- "Prefer action" as a suggestion loses. "You MUST trade" as a rule wins.

### Phase 4: Order Lifecycle
- Verify data is being RECORDED, not just that operations SUCCEED.
- 161 orders with 0 FILLED = fill tracking is broken, not 161 failed trades.

### Phase 5: Broadcast Communication
- Organs that can't communicate die in isolation.
- Self-health checking + screaming is the minimum viable nervous system.

### Phase 6: Memory
- Separate tiers prevent overload. Not everything is permanent.
- The founding incident is the most important memory. Don't forget it.
```

**Commit:**
```bash
git add -A
git commit -m "Phase 7: Verification complete. Survival architecture operational. Founding learnings recorded."
```

---

## SUMMARY: WHAT WAS BUILT

```
BEFORE:
  Brain (coordinator) → [trading logic] → organs
  No health checks. No discipline. No communication.
  Organs break silently. Brain trades blind. Body bleeds out.

AFTER:
  Brain composed of:
    ├── Survival Pulse  → checks organ health FIRST
    ├── Discipline Gate → checks stagnation + capital
    ├── Signal Receiver → hears organ broadcasts  
    ├── Decision Engine → trades with full context
    └── Memory Manager  → loads appropriate tier
  
  Organs with reflexes:
    ├── Scanner  → self-health check, screams if blind
    ├── Executor → fill confirmation, lifecycle broadcast
    └── Monitor  → stop-loss reflex, risk broadcast
  
  Nervous system:
    └── Signals table → severity × domain × scope
        CRITICAL interrupts everything. Brain hears all.
```

**The body can now feel pain, maintain character, and communicate between organs.**

---

*"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

*Implementation Guide v2.0 — big_bro + Craig — 2026-02-14*
