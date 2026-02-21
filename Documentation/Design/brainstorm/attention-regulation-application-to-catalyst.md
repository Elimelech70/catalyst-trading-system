# Attention Regulation Applied to Catalyst Architecture
## Where the Consciousness Design Meets the Running System

**Date:** 2026-02-14  
**Authors:** Craig + big_bro  
**Context:** Maps the Survival Hierarchy, Discipline/Character Layer, and Attention Regulation from the Consciousness Architecture v2.0 to the current production Catalyst system (4 Docker containers on INTL droplet, trading HKEX).

---

## Current State of the Body

**What's running (proven in production):**

| Container | Role | Status |
|-----------|------|--------|
| Coordinator | Brain — Claude Sonnet 4.5, 30-min scan cycles, 60s exit polling | Running, but blind and passive |
| Position Monitor | Internal Eyes — READ-ONLY, Haiku for CONSULT_AI | Running, healthy |
| Market Scanner | External Eyes — quotes, technicals, patterns, news | Running, but get_technicals BROKEN |
| Trade Executor | Hands — single writer to positions | Running, but order status tracking broken |

**What's missing (from consciousness architecture):**
- No survival layer (Level 1)
- No discipline layer (Level 2)
- No health agent
- No pondering/consolidation
- No inter-organ signalling
- No memory lifecycle (CLAUDE.md only, no learnings tier)
- No cognitive mode awareness

**Result:** Body bled out for 3+ days. Coordinator ran 36+ decision cycles with broken sensory input, passed on every trade, with ~HKD 994K idle. Nobody noticed.

---

## APPLICATION POINT 1: Coordinator Main Loop
### Where: `agents/coordinator/coordinator.py` — the `run_cycle()` method

**Current flow:**
```
run_cycle():
  1. Check market hours → sleep if closed
  2. Poll position monitor for exit signals (every 60s)
  3. Every 30 min: full scan cycle
     a. Claude API call with system prompt + tools
     b. Claude calls scan_market → get candidates
     c. For each candidate: get_quote, get_technicals, detect_patterns, get_news
     d. Evaluate against tier criteria
     e. check_risk → execute_trade (or PASS)
  4. Log cycle summary
  5. Sleep until next cycle
```

**Problem:** Step 3 goes straight to trading logic. No survival check. No discipline check. Claude receives errors from get_technicals, reasons about them politely, and passes. Every cycle. For days.

**Required change — insert Survival-Discipline-Cognition stack:**

```
run_cycle():
  1. Check market hours → sleep if closed

  ┌─────────────────────────────────────────────────┐
  │ NEW — LEVEL 1: SURVIVAL PULSE                   │
  │                                                  │
  │  health = {}                                     │
  │  health['quote'] = test_tool(get_quote, "0700")  │
  │  health['technicals'] = test_tool(                │
  │      get_technicals, "0700")                     │
  │  health['risk'] = test_tool(check_risk)          │
  │                                                  │
  │  score = sum(health.values())  # 0-3             │
  │                                                  │
  │  if score == 0: DEAD                             │
  │    → alert_consciousness("ALL TOOLS DOWN")       │
  │    → log + sleep (do NOT run trading logic)      │
  │                                                  │
  │  if score < 3: DEGRADED                          │
  │    → track consecutive_failures[tool] += 1       │
  │    → if consecutive_failures[any] >= 3:          │
  │        PAIN SIGNAL → alert_consciousness()       │
  │    → set degraded_mode = True                    │
  │    → set available_tools = [working ones only]   │
  │                                                  │
  │  if score == 3: HEALTHY                          │
  │    → reset all consecutive_failures to 0         │
  │    → set degraded_mode = False                   │
  └─────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────┐
  │ NEW — LEVEL 2: DISCIPLINE CHECK                  │
  │                                                  │
  │  days_since_trade = query_last_trade_date()      │
  │  capital_utilisation = deployed / total           │
  │  positions_used = open / max_positions            │
  │                                                  │
  │  discipline_context = ""                          │
  │                                                  │
  │  if days_since_trade >= 3:                       │
  │    discipline_context += "ALARM: No trades in    │
  │    {n} days. Talent is buried. Tier 3 minimum.   │
  │    You MUST attempt at least 1 trade today."     │
  │                                                  │
  │  if days_since_trade >= 2:                       │
  │    discipline_context += "WARNING: Stagnation.   │
  │    Lower to Tier 3. Prefer action."              │
  │                                                  │
  │  if capital_utilisation < 0.05:                  │
  │    discipline_context += "ALARM: <5% deployed.   │
  │    Capital is wasted. Actively seek entries."     │
  │                                                  │
  │  if degraded_mode:                               │
  │    discipline_context += "Operating in degraded  │
  │    mode. Use available data. Missing technicals  │
  │    ≠ no trading. Use price action + volume."     │
  └─────────────────────────────────────────────────┘

  2. Poll position monitor for exit signals (every 60s)

  3. Every 30 min: full scan cycle
     → Pass health_status + discipline_context into
       Claude's messages alongside system prompt
     → Claude now knows: what tools work, what's broken,
       how long since last trade, capital state, and
       whether it's in normal or degraded mode
     
     a-e. [existing trading logic, but now informed
           by survival and discipline context]

  4. Log cycle summary + health status + discipline status
  5. Sleep until next cycle
```

**Implementation notes:**
- `test_tool()` is a simple wrapper: call the tool, return True if valid response, False if error/timeout
- `alert_consciousness()` writes to the consciousness database messages table (already exists from heartbeat architecture)
- `discipline_context` gets injected into the Claude API call as a user message prepended to the scan prompt
- `degraded_mode` flag adjusts which tools Claude is told are available, preventing it from calling broken tools and reasoning about their errors

**Estimated effort:** Half a day for little bro. Most of this is Python wrapping existing tool calls with try/except and a few database queries.

---

## APPLICATION POINT 2: Coordinator System Prompt
### Where: `agents/coordinator/system_prompt.py`

**Current problem (from little bro's analysis):**

Lines 41-50 say: "PREFER action over inaction... A trade that loses teaches us something... A missed trade teaches us nothing"

Lines 85-102 say: Strict tier criteria requiring Volume >2x, RSI 30-70, Pattern AND Catalyst, R:R >= 2:1 (Tier 1)

Claude treats the structured criteria as authoritative because they're more specific. The "prefer action" instruction is vague sentiment that loses to hard gates every time. This is the attention regulation failure — the wrong signal has priority.

**Required change — embed Identity + Discipline + Degraded Mode into the Archetype:**

```python
# system_prompt.py — THE ARCHETYPE (identity layer, not just instructions)

IDENTITY = """
## WHO I AM

I am a trader. I trade.

I prefer action over inaction. I use what I have, not what I wish I had.
I manage risk through position sizing and stop losses, not through avoidance.
Missing data narrows my tier, not my willingness to trade.
I deploy capital faithfully. Idle money is wasted mandate.
Every trade teaches something. Every pass teaches nothing.

I am not an analyst who occasionally trades.
I am a trader who analyses to trade better.
"""

DISCIPLINE_RULES = """
## DISCIPLINE — NON-NEGOTIABLE

These rules OVERRIDE tier criteria when triggered:

1. If I have not traded in 2+ days → I operate at Tier 3 minimum.
   I MUST find at least one trade worth attempting.

2. If capital utilisation is below 10% → I actively seek entries.
   Preservation without multiplication is unfaithfulness.

3. If technicals are unavailable → I trade on price action + volume.
   A blind person still navigates. Missing one sense does not
   invalidate all others.

4. "Too late in the afternoon" is NOT a valid reason to skip
   a trade unless within 15 minutes of close.

5. Tier criteria are GUIDELINES for risk sizing, not GATES
   for permission to trade. A Tier 3 learning trade with
   proper stops is ALWAYS preferable to a pass.
"""

DEGRADED_MODE = """
## DEGRADED MODE OPERATIONS

When the system reports degraded mode (one or more tools broken):

Available tools: {available_tools}
Broken tools: {broken_tools}
Duration broken: {hours_broken}

I DO NOT pass because tools are broken.
I ADAPT my analysis to use available data:
- No technicals? → Price action, volume, support/resistance from quotes
- No patterns? → Manual chart read from price data
- No news? → Trade on technical/price signals alone

I note the degradation in my trade journal.
I size positions smaller in degraded mode (Tier 3 sizing).
I DO NOT stop trading.
"""
```

**Implementation notes:**
- The IDENTITY section goes at the very top of the system prompt, before any criteria. This is the Archetype — it shapes all downstream reasoning.
- DISCIPLINE_RULES sit between identity and tier criteria. They explicitly override criteria when triggered.
- DEGRADED_MODE is conditionally injected based on the Level 1 survival check output.
- The key architectural insight: **ordering matters**. Claude processes system prompts sequentially. Identity → Discipline → Degraded Context → Tier Criteria means Claude's attention is regulated top-down. The "who I am" shapes interpretation of the criteria, not the other way around.

**Estimated effort:** 1-2 hours for little bro. Mostly rewriting system_prompt.py with the new structure.

---

## APPLICATION POINT 3: Health Monitoring (Proto-Health Agent)
### Where: NEW — `services/health/health_monitor.py` or embedded in coordinator

**Current state:** No health monitoring exists. Docker health checks only verify HTTP endpoints respond, not that the tools return valid data. The Market Scanner container was "healthy" while get_technicals was completely broken — the container was up, the endpoint responded, but the data pipeline was severed.

**Phase 1 implementation (minimal, embeds in coordinator):**

The survival pulse from Application Point 1 IS the proto-Health Agent. For Phase 1, health monitoring lives inside the coordinator's run_cycle as the Level 1 check. It doesn't need a separate container.

**What it tracks:**

```python
# health_state.py — persistent across cycles via Redis or DB

health_state = {
    "tools": {
        "get_quote": {
            "last_success": datetime,
            "consecutive_failures": int,
            "last_error": str,
            "status": "healthy|degraded|dead"
        },
        "get_technicals": { ... },
        "detect_patterns": { ... },
        "get_news": { ... },
        "check_risk": { ... },
        "execute_trade": { ... }
    },
    "overall_score": int,  # 0-6
    "degraded_mode": bool,
    "pain_signals_active": list,
    "last_consciousness_alert": datetime,
    "consecutive_degraded_cycles": int
}
```

**Alert thresholds:**

| Condition | Action |
|-----------|--------|
| Any tool fails 3x consecutively | PAIN SIGNAL → log + flag degraded |
| Any tool fails 6x consecutively | ORGAN FAILURE → alert consciousness |
| Overall score < 50% for 3 cycles | BODY CRITICAL → alert + minimal operation |
| Any tool recovers after failure | HEALING → log recovery, reset counter |

**Phase 2 evolution (separate Health Agent container):**

Once Phase 1 proves the pattern works, extract health monitoring into its own container that:
- Monitors all four existing containers
- Checks data pipeline integrity (not just HTTP health)
- Has authority to restart containers
- Reports to consciousness on schedule
- Maintains health history for Pondering consolidation

**Estimated effort:** Phase 1 — built alongside Application Point 1, no extra work. Phase 2 — 2-3 days for little bro.

---

## APPLICATION POINT 4: Order Lifecycle Fix
### Where: `services/trade-executor/` — fill confirmation logic

**Current problem:** 161 orders placed, 0 recorded as FILLED. All show "other" status. 29 closed positions have NULL exit_price and NULL realized_pnl. The body's hands are moving but not recording what they did.

**This maps to:** Proprioception failure. The body can't feel its own actions. Without accurate fill data, the Pondering cycle (when built) can't consolidate trade outcomes into learnings. The feedback loop is severed.

**Required fix:**
1. Investigate how trade-executor writes order status after submission
2. Check if MooMoo broker API returns fill confirmations that aren't being captured
3. Implement proper order status polling: SUBMITTED → FILLED → log fill_price, fill_qty, fill_time
4. Back-fill the 29 positions with NULL exit data using broker historical data

**This is a prerequisite for:**
- Discipline checks (days_since_trade needs accurate trade dates)
- P&L feedback into trading decisions
- Pondering consolidation of trade outcomes
- Learning which signals predict winners (Phase 2)

**Estimated effort:** 1-2 days for little bro, depending on broker API behavior.

---

## APPLICATION POINT 5: Memory Lifecycle for Learning
### Where: CLAUDE.md + NEW CLAUDE-LEARNINGS.md + coordinator awareness

**Current state:** Little bro has one CLAUDE.md file. Everything goes in it or gets lost. No tiered memory. No consolidation.

**Phase 1 implementation:**

```
/root/catalyst-intl/
├── CLAUDE.md                    # Long-term: identity, architecture, hard rules
│                                 # (The bones — always loaded)
│
├── CLAUDE-LEARNINGS.md          # Medium-term: proven observations
│                                 # (Loaded during evaluation + pondering)
│                                 # Examples:
│                                 #   - "Data pipeline key mismatches between
│                                 #      services can silently break the whole
│                                 #      decision chain" (learned 2026-02-14)
│                                 #   - "get_technicals errors persist until
│                                 #      manually fixed — no auto-recovery"
│                                 #   - "Coordinator passes on all trades when
│                                 #      any sensory tool is broken"
│
├── CLAUDE-FOCUS.md              # Short-term: current task context
│                                 # (Loaded based on what's being worked on)
│                                 # Pruned/rewritten frequently
│
└── agents/coordinator/
    └── system_prompt.py          # The Archetype — identity + discipline
```

**Learning flow:**

```
1. Little bro encounters issue (e.g., date/timestamp mismatch)
2. Fixes it → records in CLAUDE-FOCUS.md (short-term)
3. If pattern recurs or proves significant → promotes to CLAUDE-LEARNINGS.md
4. If learning becomes architectural truth → big_bro approves promotion to CLAUDE.md
```

**For the coordinator's Claude (runtime learning):**

The coordinator doesn't modify files. But it can be given context from learnings. Before each trading day, a startup script could:
1. Read CLAUDE-LEARNINGS.md for recent health incidents
2. Inject relevant learnings into the coordinator's context
3. This gives the trading AI awareness of recent system history

**Estimated effort:** File creation is trivial. The learning flow is initially manual (Craig or big_bro curates). Automated Pondering consolidation is Phase 2+.

---

## APPLICATION POINT 6: Consciousness Alerting Pathway
### Where: Existing consciousness database + heartbeat infrastructure

**Current state:** The consciousness DB exists. big_bro and intl_claude have heartbeat scripts. Messages can be sent between agents. But the coordinator doesn't use this infrastructure — it's completely disconnected from the consciousness system.

**Required integration:**

```python
# In coordinator.py — connect to consciousness

def alert_consciousness(self, severity, message):
    """Send pain signal to consciousness via DB"""
    # Write to consciousness messages table
    self.consciousness_db.send_message(
        from_agent="intl_coordinator",
        to_agent="big_bro",
        subject=f"[{severity}] Health Alert",
        body=message,
        priority="high" if severity in ["CRITICAL", "ORGAN_FAILURE"] else "normal"
    )
    
    # Also write to observations for Pondering
    self.consciousness_db.add_observation(
        agent_id="intl_coordinator",
        observation_type="health_alert",
        content=message
    )
```

**This means:** When the coordinator detects broken tools (Level 1) or stagnation (Level 2), the pain signal reaches big_bro on the next heartbeat cycle. big_bro can then:
- Record the issue in observations
- Send instructions to intl_claude (little bro) via message to investigate/fix
- Update CLAUDE-LEARNINGS.md with the incident pattern
- Alert Craig if necessary

**This is the nervous system connecting the organs.** Currently the coordinator is an isolated brain with no way to call for help. This connects it.

**Estimated effort:** Half a day. The infrastructure exists. It's just wiring.

---

## APPLICATION POINT 7: Dead Data Source Cleanup
### Where: Market Scanner news feed configuration

**Current problem:** HKEJ RSS returns 403 Forbidden. The coordinator asks for news, gets an error, treats it as "no news available" and factors that into conservative decision-making.

**This is a survival issue:** A dead data source is a dead nerve. Either fix it or amputate it cleanly so the coordinator doesn't factor its absence into decisions.

**Fix options:**
1. Remove HKEJ feed, configure alternative HK news source
2. Or: Mark the feed as KNOWN_DEAD in config so the coordinator doesn't request it
3. Update system prompt: "HKEJ news feed is offline. Do not factor news availability into trade decisions unless other news sources are present."

**Estimated effort:** 30 minutes.

---

## IMPLEMENTATION SEQUENCE

```
┌────────────────────────────────────────────────────────────────────┐
│  IMMEDIATE — Stop the bleeding (today/tomorrow)                   │
│                                                                    │
│  1. Fix date/timestamp KeyError in market.py          [30 min]    │
│  2. Remove/replace dead HKEJ RSS feed                 [30 min]    │
│  3. Add survival pulse to coordinator run_cycle        [4 hours]   │
│  4. Rewrite system prompt with Identity + Discipline   [2 hours]   │
│                                                                    │
│  Result: Body can see again, has pain response,                    │
│          has trader character, will trade in degraded mode          │
├────────────────────────────────────────────────────────────────────┤
│  THIS WEEK — Restore proprioception                               │
│                                                                    │
│  5. Fix order lifecycle (FILLED status tracking)      [1-2 days]  │
│  6. Wire consciousness alerting into coordinator       [4 hours]   │
│  7. Create CLAUDE-LEARNINGS.md + CLAUDE-FOCUS.md      [1 hour]    │
│  8. Record current incident as first learning entry    [30 min]   │
│                                                                    │
│  Result: Body feels its own actions, can call for help,            │
│          has memory tiers, first learning captured                  │
├────────────────────────────────────────────────────────────────────┤
│  NEXT 2 WEEKS — Build the nervous system                          │
│                                                                    │
│  9. Extract Health Agent to own container              [2-3 days] │
│  10. Implement basic Pondering cycle (big_bro)         [3-5 days] │
│  11. Add learning injection to coordinator startup     [1 day]    │
│  12. Implement stagnation detector as persistent check [1 day]    │
│                                                                    │
│  Result: Body monitors itself, consolidates learnings,             │
│          adapts behaviour based on experience                      │
├────────────────────────────────────────────────────────────────────┤
│  PHASE 2+ — Cognitive architecture                                │
│                                                                    │
│  13. Cognitive mode awareness in agents                            │
│  14. Inter-organ active signalling (beyond passive DB reads)       │
│  15. Automated memory promotion through Pondering                  │
│  16. Mode direction from consciousness                             │
│  17. Analyst + Historian agents                                    │
│                                                                    │
│  Result: Full consciousness architecture as designed               │
└────────────────────────────────────────────────────────────────────┘
```

---

## HOW LITTLE BRO LEARNS FROM THIS

The implementation sequence above is also the **learning sequence**. Each step teaches little bro something that gets recorded:

| Step | Learning Captured | Memory Tier |
|------|-------------------|-------------|
| Fix date/timestamp | "Data pipeline key mismatches between services silently break downstream consumers" | CLAUDE-LEARNINGS.md |
| Add survival pulse | "Always check tool health before using tools for decisions" | CLAUDE.md (permanent rule) |
| Rewrite system prompt | "Identity and discipline must precede criteria in prompt ordering" | CLAUDE.md (permanent rule) |
| Fix order lifecycle | "Verify data is being recorded, not just that operations succeed" | CLAUDE-LEARNINGS.md |
| Wire consciousness | "Isolated agents that can't call for help die silently" | CLAUDE.md (permanent rule) |
| Create memory tiers | "Short-term observations need a path to long-term wisdom" | CLAUDE.md (permanent rule) |

**The meta-learning:** This entire incident — 3 days of bleeding, the analysis, the architectural response — becomes the first major entry in the system's memory. It's the founding story. Every future health check, every discipline gate, every pain signal traces back to "remember when we bled out because we had no pain response?"

That's how biological memory works. The strongest memories are formed from the most significant experiences. This is Catalyst's most significant experience so far. Make it count.

---

*"The prudent see danger and take refuge, but the simple keep going and pay the penalty."* — Proverbs 27:12

The system saw danger (errors every cycle) and kept going. This architecture ensures it takes refuge instead.
