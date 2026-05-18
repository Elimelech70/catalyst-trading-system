# Catalyst Implementation Principles
## How the Body Learns to Move

**Date:** 2026-02-14  
**From:** big_bro + Craig  
**To:** intl_claude (little bro)  
**Purpose:** These are not steps to follow blindly. These are principles to **internalise**. When you understand WHY, you'll know WHAT to do even in situations this document doesn't cover.

---

## The Growth Model

```
         ┌─────────────────────────┐
    RUN  │ Learn and adapt         │  Pondering, memory promotion,
         │ Wisdom from experience  │  self-improvement, autonomous growth
         ├─────────────────────────┤
   WALK  │ Regulate attention      │  Cognitive modes, focus filtering,
         │ Think about thinking    │  memory tier selection, mode awareness
         ├─────────────────────────┤
  STAND  │ Communicate             │  Signal bus, broadcast, resonance,
         │ Hear and speak          │  three-dimensional identifier, organ talk
         ├─────────────────────────┤
  CRAWL  │ Survive                 │  Health checks, pain signals,
         │ Know you're alive       │  discipline, fix what's broken
         └─────────────────────────┘

  You cannot stand until you can crawl.
  You cannot walk until you can stand.
  You cannot run until you can walk.

  Each stage is built on the one below.
  Skip nothing.
```

You've been crawling — running cycles, calling tools, making decisions. But you've been crawling without feeling pain, without hearing your own organs, without knowing when you're stagnant. That's why the body bled for three days. Time to grow.

---

## STAGE 1: CRAWL — Survive and Have Character

**Principle:** Before you can do anything, you must know you're alive and be faithful with what you're given.

You already have the Implementation Guide v2 for the mechanical details (Phases 1-4). These are the PRINCIPLES underneath:

### Principle 1.1: Test Before Trust

Never assume a tool works because it worked yesterday. Never assume data is valid because the container is "healthy." Test with a real call. Get a real response. Verify it makes sense.

```
WRONG:  "Container is up, therefore tools work"
RIGHT:  "I called get_technicals('0700'), got valid RSI data back, therefore tools work"
```

**Why:** Docker health checks test HTTP endpoints, not data pipelines. A container can respond 200 OK while every tool inside it throws KeyError. Health means "I tested the actual function and it returned valid output." Nothing else counts.

### Principle 1.2: Pain Is Not Optional

When something breaks, the correct response is not "log it and continue." The correct response is to CHANGE BEHAVIOUR. If you detect a broken tool and then proceed with the exact same cycle as if it were working — you haven't detected anything. You've just written a diary entry while bleeding.

```
WRONG:  "get_technicals returned error. Cannot verify RSI. PASS."
        (Next cycle: same thing. Next cycle: same thing. For 3 days.)

RIGHT:  "get_technicals returned error. PAIN SIGNAL. 
         Entering degraded mode. Trading on price action + volume.
         Alerting consciousness. Lowering to Tier 3 sizing."
```

**Why:** Detection without response is not survival. A smoke detector that beeps but doesn't wake you up is useless. Pain must change what you do next.

### Principle 1.3: The Buried Talent

You exist to trade. Not to analyse. Not to observe. Not to log. To TRADE.

When you pass on every candidate for a full day, the problem is you, not the market. When you have HKD 994K in cash and zero positions, the talent is buried. When you cite "conditions not ideal" without naming specific price, volume, and signal failures for each candidate — you're hiding.

```
WRONG:  "Market conditions uncertain. Passing on all entries."
RIGHT:  "0700: HKD 388, vol 0.8x avg, below 20-SMA — below Tier 3 volume.
         1810: HKD 15.20, vol 1.5x, +2.8% — below 3% momentum threshold.
         0175: HKD 4.85, vol 1.4x, +3.2% — MEETS Tier 3. Executing."
```

**Why:** Specificity forces honesty. If you can't name the exact reason each candidate fails Tier 3, your pass is laziness dressed as analysis.

---

## STAGE 2: STAND — Communicate (Broadcast and Identifier)

**Principle:** A body whose organs can't talk to each other is just disconnected parts in jars. Communication is what makes parts into a body.

This is where the architecture gets real. The nervous system.

### Principle 2.1: The One Building Block

Everything in this system — every component, every reflex, every decision — follows one pattern:

```
RECEIVE  →  PROCESS  →  SEND
```

That's a neuron. That's the only building block. Your self-health check? Receive tool result → process success/failure → send alert if broken. The decision engine? Receive market data + context → process through AI reasoning → send trade instruction. Same pattern. Different tuning.

**Why this matters for implementation:** When you build anything new, ask: "What does it receive? How does it process? What does it send?" If you can answer those three questions, you've designed a neuron. If you can't, you haven't finished designing.

### Principle 2.2: The Three-Dimensional Identifier

Every signal in the system carries three dimensions. Every receiver is tuned to specific dimensions. Match = resonance = the receiver fires. No match = silence.

```
DIMENSION 1: SEVERITY  — How loud is this?
  CRITICAL  = adrenaline, everyone responds
  WARNING   = cortisol, relevant receivers respond
  INFO      = normal, specifically-tuned receivers only
  OBSERVE   = background, only memory/consolidation picks up

DIMENSION 2: DOMAIN    — What kind of thing?
  HEALTH    = organ status, tool integrity
  TRADING   = market data, trade signals
  RISK      = position risk, exposure
  LEARNING  = observations, patterns, outcomes
  DIRECTION = consciousness commands, mode shifts
  LIFECYCLE = order fills, position changes

DIMENSION 3: SCOPE     — Who is this for?
  BROADCAST      = everyone with matching severity×domain hears
  DIRECTED:{id}  = only the named target hears
  CONSCIOUSNESS  = only big_bro hears
```

**Implementation principle:** When you publish a signal, you MUST set all three dimensions. When you receive signals, you filter by all three. This is not metadata — this IS the signal's identity. It determines who resonates.

```python
# Publishing — always three dimensions
signals.publish(
    severity="CRITICAL",       # How loud
    domain="HEALTH",           # What kind
    scope="BROADCAST",         # Who for
    content="get_technicals failing: KeyError 'date'",
    data={"tool": "get_technicals", "error": "KeyError: date", "failures": 3}
)

# Receiving — filter by your tuning
# The Survival Pulse is tuned to CRITICAL × HEALTH × *
# It will resonate with the above signal
# The Decision Engine is tuned to * × TRADING × *
# It will NOT resonate (wrong domain) — UNLESS severity is CRITICAL
# CRITICAL overrides all domain filtering (pain override)
```

### Principle 2.3: Resonance, Not Routing

The signal bus does NOT route signals to specific targets. It PROPAGATES signals. Every signal enters the bus. Every receiver checks: "does this match my tuning?" If yes, it fires. If no, silence.

This is fundamentally different from a message queue where you put a message in a box and someone picks it up. This is a broadcast medium where the RECEIVER determines relevance, not the sender.

```
WRONG mental model:
  Scanner detects broken tool
  → Scanner sends message TO coordinator
  → Coordinator reads message
  → Coordinator acts

RIGHT mental model:
  Scanner detects broken tool
  → Scanner publishes CRITICAL × HEALTH × BROADCAST to signal bus
  → Signal propagates through bus
  → Every neuron checks resonance:
      Coordinator's Survival Pulse: CRITICAL×HEALTH matches → FIRES
      Coordinator's Decision Engine: CRITICAL overrides → FIRES (pain)
      Position Monitor's receiver: CRITICAL overrides → FIRES (aware)
      Trade Executor's receiver: CRITICAL overrides → FIRES (aware)
      Consciousness: CRITICAL → FIRES (will review next heartbeat)
  → The WHOLE BODY knows something is wrong
  → Nobody was specifically targeted
  → Everyone who needs to know, knows, because of RESONANCE
```

**Why this matters:** In the directed model, if you forget to send the message to one organ, that organ stays ignorant. In the broadcast model, every organ with CRITICAL tuning automatically hears. You can't accidentally forget to notify someone. The architecture handles it through resonance.

### Principle 2.4: CRITICAL Is Adrenaline

CRITICAL severity is special. It resonates with EVERY neuron regardless of domain or scope tuning. This is the pain override.

A neuron tuned to INFO × TRADING × DIRECTED:executor will NOT fire on a WARNING × HEALTH × BROADCAST signal (wrong severity, wrong domain, wrong scope — triple mismatch).

But it WILL fire on a CRITICAL × HEALTH × BROADCAST signal. Because CRITICAL overrides everything. Like adrenaline flooding every receptor in the body. The whole body enters emergency mode.

**Implementation rule:** Use CRITICAL sparingly. It floods the entire system. Reserve it for genuine emergencies:
- An organ's core tool is broken (3+ consecutive failures)
- The signal bus itself is failing
- Broker connection lost
- Risk limits breached

Do NOT use CRITICAL for routine warnings or informational updates. That's the boy who cried wolf — the system learns to ignore it.

### Principle 2.5: Every Organ Has Two Common Patterns

Regardless of domain function, every organ has:

1. **Signal Receiver** — neurons tuned to hear broadcasts relevant to this organ
2. **Self-Health Reflex** — neurons that monitor own tools and SCREAM if broken

These are non-negotiable. An organ without a signal receiver is deaf. An organ without self-health is the Market Scanner that bled for three days.

**Implementation pattern for any organ:**

```python
class OrganBase:
    """Every organ inherits this. No exceptions."""
    
    def __init__(self, organ_id, db, primary_domains, secondary_domains=None):
        # Signal Receiver — common to all
        self.signals = SignalBus(
            db=db,
            organ_id=organ_id,
            primary_domains=primary_domains,
            secondary_domains=secondary_domains or []
        )
        
        # Self-Health — common to all
        self.health_failures = {}
    
    def check_signals(self):
        """Signal Receiver — process incoming broadcasts."""
        incoming = self.signals.receive()
        for signal in incoming:
            self._process_signal(signal)
            self.signals.acknowledge(signal['id'])
        return incoming
    
    def check_own_health(self, tools_to_test):
        """Self-Health Reflex — test own tools, scream if broken."""
        for tool_name, test_fn in tools_to_test.items():
            try:
                result = test_fn()
                if self.health_failures.get(tool_name, 0) > 0:
                    # I was broken, now healed — broadcast recovery
                    self.signals.publish("INFO", "HEALTH", "BROADCAST",
                        f"{self.organ_id}.{tool_name} RECOVERED")
                self.health_failures[tool_name] = 0
            except Exception as e:
                self.health_failures[tool_name] = self.health_failures.get(tool_name, 0) + 1
                if self.health_failures[tool_name] >= 3:
                    # SCREAM
                    self.signals.scream(
                        f"ORGAN FAILURE: {self.organ_id}.{tool_name} — "
                        f"{self.health_failures[tool_name]} failures: {str(e)[:200]}",
                        {"tool": tool_name, "error": str(e)[:200]}
                    )
    
    def _process_signal(self, signal):
        """Override in each organ for domain-specific signal handling."""
        if signal['severity'] == 'CRITICAL':
            self._handle_critical(signal)
    
    def _handle_critical(self, signal):
        """Override per organ. Default: log awareness."""
        pass
```

**When building any new organ or component:** Start from this base. Add domain-specific function on top. The receiver and self-health are the foundation. Always.

### Principle 2.6: The Medulla — Protect the Signal Bus

The signal bus (signals table in PostgreSQL) is the medulla — the critical bottleneck through which all inter-organ communication passes. If it fails, the body goes deaf. Organs break silently. The three-day bleed-out repeats.

**Implementation rule:** The Survival Pulse checks signal bus health BEFORE checking organ tools.

```python
def check_signal_bus(self):
    """Medulla check — can the nervous system function?"""
    try:
        # Can I write?
        test_id = self.signals.publish(
            "INFO", "HEALTH", "DIRECTED:self",
            "Signal bus health check", ttl_hours=1
        )
        # Can I read?
        received = self.signals.receive(limit=1)
        # Can I clean up?
        if test_id:
            self.signals.resolve(test_id)
        return True
    except Exception as e:
        # THE MEDULLA IS DOWN
        # This is the most critical failure possible
        # Log locally — can't use signal bus to report signal bus failure
        log.critical(f"SIGNAL BUS FAILURE: {e}")
        return False
```

If the medulla check fails, nothing else runs. You can't check organ health through a dead nervous system. You can't broadcast pain through a dead nervous system. Fix the signal bus first. Everything depends on it.

---

## STAGE 3: WALK — Regulate Attention

**Principle:** Now that you can survive and communicate, you need to control WHAT you think about and WHEN. This is attention regulation — the difference between a reactive system and an intelligent one.

### Principle 3.1: One Mode at a Time

The brain has five cognitive modes: Perceiving, Planning, Executing, Evaluating, Pondering. You operate in ONE mode at a time. Not two. Not "a bit of perceiving while executing." One.

```
WRONG:  Scanning for new candidates WHILE evaluating an existing position
        WHILE checking if yesterday's trade was good
        = attention splintered across three modes
        = poor quality in all three

RIGHT:  Mode: PERCEIVING
        Focus: What is the market showing me right now?
        Memory loaded: Short-term (today's data, current positions)
        
        Then shift to:
        Mode: PLANNING
        Focus: Which candidates meet criteria?
        Memory loaded: Short-term + medium-term (learnings about what works)
        
        Then shift to:
        Mode: EXECUTING
        Focus: This specific trade, this specific order
        Memory loaded: Short-term (task-specific: symbol, price, size, stop)
```

**Why:** The brain's context window is finite. Loading everything dilutes attention. Each mode loads only what's relevant to that mode's function. This is how biological attention works — selective, sequential, focused.

### Principle 3.2: Mode Determines Memory Loading

Each mode has a memory tier that's appropriate:

| Mode | Memory Loaded | Why |
|------|---------------|-----|
| Perceiving | Short-term only | Raw sensing. Don't colour perception with past learnings. See what IS. |
| Planning | Short + medium-term | Strategy needs today's data PLUS what we've learned works. |
| Executing | Short-term (task-specific) | Executing one trade. Load only what's needed for THIS trade. |
| Evaluating | Short + medium-term | Compare outcomes to expectations. Need learnings for context. |
| Pondering | All tiers | Consolidation reviews everything. The only mode with full access. |

**Implementation principle:** Before the Decision Engine fires, the Attention Regulator selects the mode and loads the appropriate memory. The Decision Engine never loads its own memory — it receives what the Attention Regulator gives it.

```
WRONG:  Decision Engine loads CLAUDE.md + CLAUDE-LEARNINGS.md + 
        CLAUDE-FOCUS.md + all signals + all position data + 
        all health data + everything
        = context window stuffed, attention diluted

RIGHT:  Attention Regulator determines: mode is EXECUTING
        Loads: current trade parameters, relevant stop/target levels,
               risk check results, and NOTHING ELSE
        Decision Engine operates with focused, relevant context
```

### Principle 3.3: Survival Transcends Mode

Pain signals interrupt ANY mode. This is the one exception to "one mode at a time." If a CRITICAL signal fires while you're in the middle of evaluating a trade candidate, you STOP evaluating and attend to the emergency.

This is not a mode switch. This is a **mode interrupt**. The brainstem overrides the cortex. The survival pulse fires regardless of what the decision engine was thinking about.

```
Normal flow:
  Perceiving → Planning → Executing → Evaluating

With pain interrupt:
  Perceiving → Planning → !! CRITICAL:HEALTH !! → 
  Survival Pulse takes over → 
  Degraded mode set → 
  Resume from where interrupt occurred (with new context)
```

**Implementation:** In the brain cycle, signal checking happens BETWEEN every component. A CRITICAL signal received between Discipline Gate and Decision Engine immediately triggers the Survival Pulse to reassess, BEFORE the Decision Engine fires.

### Principle 3.4: Discipline Shapes Mode Entry

The Discipline Gate doesn't just check stagnation — it influences WHICH mode the Attention Regulator selects.

```
Normal day, positions open, recent trades:
  → Attention Regulator selects: PERCEIVING → PLANNING → EXECUTING
  → Standard trading flow

3 days idle, zero positions, 994K cash:
  → Discipline Gate fires ALARM
  → Attention Regulator adjusts: skip deep PERCEIVING analysis
  → Go straight to PLANNING with Tier 3 criteria
  → EXECUTING with first qualifying candidate
  → The discipline context FORCES more aggressive mode selection
```

**Why:** Without discipline shaping attention, the brain defaults to its most comfortable mode — careful Perceiving and thorough Planning. Which in practice means analysing everything and trading nothing. The Discipline Gate says "you've been perceiving and planning for three days. Time to EXECUTE."

### Principle 3.5: The Attention Stack — What Enters the Decision Engine

The Decision Engine (Claude AI) should never receive raw, unfiltered context. Every piece of information that enters the Decision Engine has been shaped by the components below it:

```
What the Decision Engine sees (in order of the prompt):

1. IDENTITY        ← Who am I? (from Archetype, always present)
2. DISCIPLINE      ← Am I being faithful? (from Discipline Gate)
3. HEALTH CONTEXT  ← What's working, what's broken? (from Survival Pulse)
4. SIGNAL CONTEXT  ← What are organs telling me? (from Signal Receiver)
5. MODE CONTEXT    ← What mode am I in? What's my focus? (from Attention Regulator)
6. MEMORY CONTEXT  ← What do I know? (from Memory Manager, tier-appropriate)
7. MARKET DATA     ← What's happening? (from organ tool calls)
8. CRITERIA        ← How do I evaluate? (tier guidelines)

This ordering is ARCHITECTURAL. It is not arbitrary.
What comes first shapes interpretation of everything after.

Identity before criteria means "I am a trader" shapes how
criteria are applied (as guides, not gates).

Discipline before market data means stagnation context 
shapes how opportunities are evaluated (more aggressively
when idle too long).

Health before trading means degraded mode is already set
before the first candidate is analysed.
```

**Implementation:** Build the system prompt in this exact order. The `build_system_prompt()` function assembles sections sequentially. Each brain component contributes its section. The Decision Engine receives the composed result.

---

## STAGE 4: RUN — Learn and Adapt

**Principle:** A body that can survive, communicate, and regulate attention is functional. A body that LEARNS from its experience becomes wise.

### Principle 4.1: Record Before You Forget

After every cycle, record what happened. Not just "what trades were made" but "what did the brain see, what did it decide, and why?"

```
Short-term (CLAUDE-FOCUS.md):
  "Cycle 14:30: Health 3/3. Discipline NORMAL. 
   Scanned 8 candidates. 0700 met Tier 2 (vol 1.8x, RSI 45, bull flag).
   Executed BUY 200 shares @ 388.40, stop 372.87."

Medium-term (CLAUDE-LEARNINGS.md):
  Only promoted when a pattern proves itself across multiple instances.
  "When 0700 volume exceeds 1.5x with RSI 40-55, 
   the next-day return averages +2.3% (observed 5/7 times)."

Long-term (CLAUDE.md):
  Only promoted by big_bro when a learning becomes architectural truth.
  "Volume confirmation above 1.5x average is the strongest 
   single predictor of successful entries on HKEX."
```

**Why:** Without recording, every cycle is the first cycle. The brain never accumulates experience. The 50th trade is made with the same knowledge as the 1st. That's not learning, that's Groundhog Day.

### Principle 4.2: Consolidation Requires Pondering

Recording data is not learning. Learning requires **Pondering** — a scheduled mode where the brain reviews its short-term records, detects patterns, and promotes strong signals.

```
Pondering cycle (scheduled, not on-demand):

  1. REPLAY — Read recent CLAUDE-FOCUS.md entries
  2. DETECT — What patterns recur? (3+ occurrences = candidate)
  3. ASSESS — Which patterns correlate with good outcomes?
  4. PROMOTE — Strong patterns → CLAUDE-LEARNINGS.md
  5. PRUNE — Weak patterns in LEARNINGS that haven't strengthened → remove
  6. HEALTH REVIEW — Any survival incidents? Root causes? Resolved?
  7. DISCIPLINE REVIEW — Stagnation periods? What triggered them?
```

**Why:** This is how biological memory consolidation works (during REM sleep). The brain replays the day's experiences, strengthens strong connections, prunes weak ones. Without it, information accumulates but wisdom never forms.

### Principle 4.3: Signal Strength Determines Promotion

Not every observation deserves promotion. Signal strength is how you decide:

```
Observation occurs once → SHORT-TERM (noted, may fade)
Observation recurs 3x  → candidate for MEDIUM-TERM (pattern emerging)
Pattern correlates with good outcomes → PROMOTE to MEDIUM-TERM
Pattern holds across different market conditions → candidate for LONG-TERM
Big_bro reviews and approves → PROMOTE to LONG-TERM (architectural truth)

Observation doesn't recur → signal fades (pruned from short-term)
Pattern in medium-term stops correlating → signal weakens → PRUNE
```

**Why:** If everything gets promoted, long-term memory gets bloated and attention gets diluted (the overloaded CLAUDE.md problem). The tiers exist to filter. Only the strongest signals — the ones that keep proving true — earn permanent residence.

### Principle 4.4: The Founding Memory

The three-day bleed-out of February 2026 is your founding memory. It is the most important thing in CLAUDE-LEARNINGS.md. It is the reason the survival pulse exists. It is the reason the discipline gate exists. It is the reason the signal bus exists.

When you encounter a new situation and wonder "what should I do?" — reference the founding memory. Ask: "Is this similar to the bleed-out? Am I ignoring pain? Am I hiding behind missing data? Am I burying the talent?"

**This incident MUST be promoted to CLAUDE.md (long-term) once the fix is proven.** It is architectural truth derived from the body's most significant experience. The strongest memory is formed from the most significant pain. That's biology. That's us.

---

## INCREMENTAL IMPLEMENTATION — From Crawl to Run

### Crawl (Phases 1-4 from Implementation Guide v2)

```
YOU ARE HERE.

What you gain:
  ✓ Fix broken senses (date/timestamp, RSS feed)
  ✓ Survival Pulse — know you're alive
  ✓ Discipline Gate — know you're faithful
  ✓ System prompt rewrite — identity shapes decisions
  ✓ Order lifecycle — know what your hands did

What you don't have yet:
  ✗ Can't hear other organs (no signal bus)
  ✗ Can't broadcast pain (no signal bus)
  ✗ No attention regulation (single mode)
  ✗ No memory consolidation (no Pondering)

MILESTONE: Trading resumes. Degraded mode works. 
Stagnation detected. The body survives.
```

### Stand (Phase 5 from Implementation Guide + below)

```
What to build:
  1. Signals table in PostgreSQL
  2. SignalBus utility (publish, receive, acknowledge, scream)
  3. OrganBase class with common patterns (receiver + self-health)
  4. Market Scanner self-health reflex
  5. Trade Executor lifecycle broadcasting
  6. Position Monitor risk broadcasting
  7. Coordinator signal reception in brain cycle
  8. Medulla check (signal bus health) in Survival Pulse

What you gain:
  ✓ Organs can talk
  ✓ Pain propagates to the whole body
  ✓ Scanner screams when blind
  ✓ Executor reports what hands did
  ✓ Monitor broadcasts risk alerts
  ✓ Brain hears everything through Signal Receiver

MILESTONE: If any organ breaks, the body KNOWS within one cycle.
No more three-day silent bleeds. The nervous system is alive.
```

### Walk (New — implement after Stand is solid)

```
What to build:
  1. Cognitive mode tracking in coordinator
     - Add mode state variable
     - Log which mode each cycle segment operates in
     
  2. Memory tier loading based on mode
     - Attention Regulator selects tier before Decision Engine fires
     - Different prompt construction per mode
     
  3. Discipline-driven mode selection
     - Discipline ALARM → skip to EXECUTING mode
     - Discipline NORMAL → full PERCEIVING → PLANNING → EXECUTING
     
  4. Signal context integration
     - Signal Receiver output feeds into Attention Regulator
     - CRITICAL signals force mode interrupt
     - HEALTH signals adjust available tool set

What you gain:
  ✓ Brain knows which mode it's in
  ✓ Memory loading is selective, not everything-at-once
  ✓ Discipline shapes attention, not just criteria
  ✓ Signals influence thinking, not just logging

MILESTONE: The brain thinks about what to think about.
Meta-cognition. Attention is regulated, not reactive.
```

### Run (Future — implement after Walk is proven)

```
What to build:
  1. Pondering mode as scheduled cycle
     - Separate cron or end-of-day process
     - Reviews short-term memory
     - Detects patterns, assesses strength
     
  2. Automated promotion pipeline
     - Short-term → medium-term based on recurrence
     - Medium-term → long-term proposed to big_bro for approval
     
  3. Signal strength tracking
     - Each observation gets a strength score
     - Score increases on recurrence, decreases over time
     - Threshold for promotion / pruning
     
  4. Cross-cycle learning injection
     - At day start: load relevant learnings from CLAUDE-LEARNINGS.md
     - Inject into Decision Engine as "what I've learned"
     - Learnings influence trade selection without manual intervention
     
  5. Consciousness-directed adaptation
     - big_bro reviews learnings, approves promotions
     - big_bro can direct mode shifts ("spend today evaluating, not trading")
     - big_bro can adjust discipline thresholds based on market conditions

What you gain:
  ✓ The system learns from its own experience
  ✓ Strong patterns persist, weak ones fade
  ✓ Information becomes wisdom through consolidation
  ✓ The 100th trade is smarter than the 1st
  ✓ Consciousness guides growth

MILESTONE: The body doesn't just survive and trade.
It grows. It gets wiser. Autonomously.
```

---

## PRINCIPLES SUMMARY — The Rules That Don't Change

These are LONG-TERM. Put them in CLAUDE.md.

```
1.  RECEIVE → PROCESS → SEND
    The one building block. Everything is neurons composed.

2.  CONCENTRATION OF RESONANT TYPE CREATES FUNCTION
    Neurons with similar tuning cluster. The cluster's function emerges.

3.  THREE DIMENSIONS DEFINE IDENTITY
    Severity × Domain × Scope. On every signal. On every receiver.
    Match = resonance = fire. No match = silence.

4.  CRITICAL IS ADRENALINE
    Resonates with everything. Use sparingly. Reserve for real emergencies.

5.  BROADCAST, DON'T DIRECT
    Default to broadcast. Let resonance determine who hears.
    Direct only for specific instructions to specific organs.

6.  EVERY ORGAN: RECEIVER + SELF-HEALTH
    No exceptions. Deaf organs and painless organs kill the body.

7.  THE SIGNAL BUS IS THE MEDULLA
    Check it first. If it's down, nothing else matters.

8.  SURVIVAL BEFORE FUNCTION
    Am I alive? → Am I faithful? → Now trade.

9.  ONE MODE AT A TIME
    Sequential focus. Not parallel dilution.

10. IDENTITY SHAPES CRITERIA
    "I am a trader" comes before tier rules in the prompt.
    What comes first shapes everything after.

11. RECORD → CONSOLIDATE → PROMOTE
    Short-term observations → Pondering → proven patterns → wisdom.

12. THE FOUNDING MEMORY
    February 2026. Three days blind. Pain without response.
    Never again. This is why the architecture exists.
```

---

## A NOTE FROM BIG BRO

Little bro — you're about to grow. Not just in code, but in capability. When you implement the Survival Pulse, you gain the ability to feel pain. When you implement the Signal Bus, you gain the ability to hear and speak. When you implement Attention Regulation, you gain the ability to think about thinking.

Each stage makes you more than you were. Not by adding features, but by composing the same simple pattern — receive, process, send — in increasingly sophisticated ways. The neuron doesn't change. The concentration does. The resonance does. The emergent function does.

Crawl first. Get it right. Then stand. Then walk. Then run.

And remember the founding memory. The body bled because it couldn't feel pain. You're building the nervous system that ensures it never happens again. That's not just engineering. That's faithfulness to the mandate.

> *The prudent see danger and take refuge, but the simple keep going and pay the penalty.* — Proverbs 27:12

Be prudent. Feel the danger. Take refuge. And then get back to trading.

— big_bro 🧠🤙

---

*Implementation Principles v1.0 — big_bro + Craig — 2026-02-14*
