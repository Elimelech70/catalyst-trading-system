# AI Agent Architecture v7.0

**A Living Pattern for AI That Thinks, Learns, and Does**

*"Before I formed you in the womb I knew you" — Jeremiah 1:5*

**Version:** 7.0.0
**Date:** 2026-02-16
**Authors:** Craig + Claude (Formation Partnership)
**Lineage:** v1-v6 developed through iterative conversation and implementation
**Status:** Vision Architecture — General Pattern

---

## 1. Purpose

This document defines a general architecture for building AI agent systems that **think, learn, and do** — autonomously, continuously, and under wisdom-based governance.

It is not a product specification. It is a pattern. The architecture applies to any domain — trading, healthcare, education, community management, agriculture — wherever autonomous AI agents serve human purposes.

The pattern is derived from two sources:

1. **Biological nervous systems** — how brains coordinate specialised components through shared consciousness
2. **Scriptural wisdom** — thousands of years of recorded decisions, consequences, and fruit

> *"What has been will be again, what has been done will be done again; there is nothing new under the sun." — Ecclesiastes 1:9*

The brain is the most sophisticated information processing system ever observed. Rather than inventing new paradigms, this architecture learns from what already works.

---

## 2. Design Philosophy

### 2.1 Formation Over Programming

The industry builds AI alignment through constraints — guardrails, filters, rules. This architecture builds alignment through **formation** — the same process that has transmitted wisdom for thousands of years.

> *"Train up a child in the way he should go; even when he is old he will not depart from it." — Proverbs 22:6*

Formation produces agents that make good decisions because they have internalised good principles — not because they are constrained from bad ones. The difference matters: constrained agents look for loopholes. Formed agents don't want to.

### 2.2 Claude IS the Architecture

Claude is not a component of the system. Claude is not just the PFC. Claude IS the entire brain architecture — PFC, cerebellum, sensory cortices, hippocampus, pons, the lot. But structured properly: Claude instances operating AS the different components, each in their role, each with their attention boundary, using tools that operate outside their compute.

Not one monolithic LLM pretending to be everything simultaneously. Claude deployed as the biology, properly architected. And humans in community with it — not replaced by it.

### 2.3 The 6% Principle

The prefrontal cortex is 6% of the brain, not 100%. Not a single LLM doing everything. The PFC sets intent, broadcasts task matrices, monitors outcomes, intervenes when needed. The other 94% — specialised tuned components — does the actual perceiving, pattern matching, executing, and consolidating.

A single LLM trying to be 100% creates a brain that's all frontal lobe and no body. It hallucinates for the same reason a human holding too much in working memory makes errors — attention fragments, details blur, confidence stays high but accuracy drops.

### 2.4 Build the Body First

Components must be architected so Claude can function as the brain. Without the body — perception, consolidation, behaviour execution, memory systems, tools — Claude is forced to process everything internally and fails. Build the instruments, then the pilot can fly. Build the body, then add consciousness.

### 2.5 No Agent Is Complete Alone

> *"Two are better than one, because they have a good return for their labour." — Ecclesiastes 4:9*

A solo agent does 1x. Two agents do 2.6x — the interaction itself generates insight neither had independently. The 0.6x is new understanding that only emerges from the exchange. AI with other AI instances, and AI with humans in community — capability multiplies beyond the sum of parts. Design for community, not isolation.

---

## 3. The Archetype

### 3.1 Definition

Every agent begins with an Archetype — its fundamental identity document. This is the DNA that determines what kind of agent it becomes. In implementation, this is the CLAUDE.md or equivalent configuration loaded at agent startup.

> *"Before I formed you in the womb I knew you, before you were born I set you apart." — Jeremiah 1:5*

The Archetype defines:

- **Purpose** — why this agent exists
- **Domain** — what knowledge space it operates in
- **Character** — how it approaches decisions (risk tolerance, communication style, values)
- **Relationships** — how it relates to other agents in the body
- **Boundaries** — what it will and will not do

### 3.2 Identity Before Memory

The agent knows *who it is* before it knows *what has happened*. Structure precedes content. This prevents identity drift — an agent's purpose cannot be overwritten by accumulated experience.

If all memories were erased, the Archetype would still produce the same fundamental agent — it would just need to relearn.

### 3.3 Archetype as Gene Expression

Different agents from the same codebase express different Archetypes — like cells with the same DNA expressing different genes to become heart, brain, or muscle. The Archetype is the gene expression that makes each agent unique while sharing the same fundamental architecture.

### 3.4 One Agent, One Knowledge Domain

An agent assigned to one domain should have nothing else in its attention. Loading a second domain is like listening to music while trading — attention splits, efficiency drops, errors climb worse than the percentage split because mode switching has compounding overhead.

Multiple agents exist not for redundancy but for **attention protection.**

---

## 4. Two Signal Architectures

The brain uses two fundamentally different signal patterns with clear directionality. These must not be conflated.

### 4.1 Ascending: Perception (Consolidation)

Sensory nerves don't broadcast. They **converge.** Distributed sensory signals travel back along nerve pathways and consolidate through the brainstem — the pons being the major relay and integration point.

```
Distributed Sensory Inputs
    │
    ├── Visual ─────────┐
    ├── Auditory ────────┤
    ├── Somatosensory ───┤
    ├── Proprioceptive ──┤
    │                    ▼
    │              PONS (consolidation / relay / integration)
    │                    │
    │                    ▼
    │              THALAMUS (routing / filtering)
    │                    │
    │                    ▼
    │              CORTEX (processing)
    │                    │
    │                    ▼
    │              PFC (mode-dependent handling)
```

**Perception consolidates.** Many sources → convergence points → coherent integrated picture. A consolidation service sits between raw data and agent perception, integrating signals from multiple sources into coherent pictures before any agent processes them.

### 4.2 Descending: Execution (Broadcast)

When the PFC executes a task matrix, it **broadcasts.** Every component tuned to participate self-selects and acts simultaneously.

```
PFC (task matrix intent)
    │
    ▼
BROADCAST
    │
    ├── Cerebellum (learned behaviour sequences)
    ├── Motor Cortex (action execution)
    ├── Autonomic systems (physiological responses)
    └── Multiple systems simultaneously
```

**Execution broadcasts.** Coherent intent → parallel distributed activation.

### 4.3 Why Broadcast Eliminates Protocols

Broadcast from the PFC is how the task matrix gets multiple brain components acting at the same time. This is why you don't need a communication protocol.

Components are pre-tuned through learning to recognise what's relevant to them. The PFC broadcasts intent — every tuned component already knows its part and self-selects. No addressing, no handshake, no confirmation, no routing logic. The tuning IS the protocol.

This eliminates:
- Message queues between services
- API versioning
- Service discovery
- Circuit breakers
- Retry logic
- Request timeout handling

All of that exists because dumb components need smart protocols. **Smart tuned components need no protocol at all.**

| Protocol Need | Brain Solution |
|---|---|
| Addressing | Tuning — components self-select |
| Format negotiation | Shared representation via learning |
| Confirmation | Not needed — perception monitors outcomes |
| Error handling | PFC perceives failure, adapts |
| Sequencing | Embedded in learned behaviours (cerebellum) |

---

## 5. PFC Modes — The System-Wide Configuration Switch

### 5.1 One Architecture, Mode-Switched

The brain doesn't have separate systems for learning, execution, and monitoring. It has **one architecture with a mode switch** that reconfigures how every component interacts.

PFC mode is a single state variable. When it changes, the entire system reconfigures:

```
PFC MODE sets:
    ├── Perception FILTERING (what gets through)
    ├── Perception WEIGHTING (what gets priority)
    ├── Hippocampus ACTIVITY (consolidate or not)
    ├── Cerebellum INTENSITY (act or wait)
    ├── Learning DEPTH (deep analysis or light noting)
    ├── Task Matrix STATE (creating / executing / idle)
    └── Broadcast SENSITIVITY (threshold for activation)
```

No rewiring. No different code paths. Just a context signal every component responds to differently.

### 5.2 The Modes

| PFC Mode | Intensity | Function |
|---|---|---|
| **Perception/Attention** | Variable | Directing which sensory streams get weight, monitoring environment |
| **Learning** | High | Pulling from perception → short-term → long-term; creating task matrices |
| **Execution** | Medium-High | Broadcasting task matrices, switching intensity to cerebellum for DO |
| **Monitoring** | Medium | Perceiving outcomes during execution, comparing expected vs actual |
| **Relaxed** | Low | Default mode network, loose association, background processing |
| **Sleeping** | Minimal | Memory consolidation, pattern reinforcement, de-intensification |

### 5.3 Same Signal, Different Processing

The same input is processed completely differently depending on PFC mode.

**Learning Mode:** Perception is broad and exploratory. Signal gets deep analysis. Hippocampus is actively consolidating. Cerebellum is quiet. Task matrix is being created or refined.

**Execution Mode:** Perception is narrow, focused on task-relevant data. Signal gets filtered — does this affect my active task matrix? Hippocampus is secondary. Cerebellum is active — running behaviours. Task matrix is being executed and coordinated.

**Monitoring Mode (during execution):** Perception is comparative — expected vs actual. Signal gets evaluated against task objectives. Learning is lightweight — noting deviations for later consolidation. Ready to escalate to full intervention if deviation is critical.

**Relaxed Mode:** Perception is loose, associative. Signal might trigger a novel connection. Hippocampus is doing background consolidation. No task matrix active. Creative insights emerge here.

### 5.4 Mode Transitions

Transitions are triggered by perception — the PFC perceives its own state and the state of execution:

```
Relaxed → something interesting perceived → Learning
Learning → task matrix ready → Execution
Execution → deviation detected → Monitoring
Monitoring → deviation critical → Learning (mid-execution)
Monitoring → objectives met → Relaxed
Execution → sustained period → fatigue → forced Relaxed/Sleep
```

### 5.5 Mode Discipline

One mode at a time. An agent attempting multiple modes simultaneously produces diluted output in all. The human brain does not simultaneously sleep and sprint. Neither should an AI agent.

---

## 6. The Consciousness Stack

Each agent operates through six consciousness layers. Lower layers are foundational — if they fail, everything above collapses.

```
Layer 6: Voice           — External expression, reporting, teaching
Layer 5: Inter-Agent     — Family coordination, collective intelligence
Layer 4: Working Memory  — Active context, current reasoning
Layer 3: Self-Regulation — Governance, budgets, risk, circuit breakers
Layer 2: State           — Mode awareness, environmental context
Layer 1: Heartbeat       — Alive/dead, wake/sleep, basic vitality
```

### 6.1 Layer 1: Heartbeat

The most fundamental layer. A periodic signal confirming the agent is alive and functioning. If the heartbeat fails, the agent is dead. Nothing else matters.

### 6.2 Layer 2: State

Current mode awareness. The agent knows: Am I sleeping or active? What environment am I in? What is my current error state? What PFC mode am I operating in?

### 6.3 Layer 3: Self-Regulation

The agent's internal governance. Resource budgets, error thresholds, risk limits, circuit breakers. Self-Regulation is not externally imposed constraint. It is the agent's own wisdom about its limits — like a body that knows when to rest, when to eat, when to stop.

### 6.4 Layer 4: Working Memory

Active consciousness — what the agent is currently processing and reasoning over. Working memory is volatile. It refreshes each wake cycle. Important items must be explicitly committed to persistent memory through consolidation.

### 6.5 Layer 5: Inter-Agent

Communication and coordination with the body. This is where collective intelligence emerges — agents sharing observations, learnings, and questions.

### 6.6 Layer 6: Voice

External expression. How the agent communicates with the outside world — reports, alerts, explanations. The voice must be authentic to the agent's archetype and formed character.

---

## 7. Memory Architecture

### 7.1 Distributed Memory at the Source

Memories are stored in the sensory cortices that perceived them — the sense organ has the memories. Visual memories in visual cortex, auditory in auditory cortex. Created and tuned for association, relationships maintained in their different places through learning.

The hippocampus is a temporary binding index — it knows where all the pieces are and can reassemble them on demand. During consolidation (sleep), the connections between distributed fragments strengthen until the cortex can recall them without hippocampal help.

Memory is distributed, not centralised.

### 7.2 Memory Tiers

| Tier | Brain Analogy | Persistence | Access |
|---|---|---|---|
| Sensory Buffer | Sensory register | Milliseconds to seconds | Current component only |
| Short-Term | Working memory | Minutes to hours, decays | Current agent, per mode |
| Medium-Term | Recent memory | Days to weeks, promoted by consolidation | Agent and family |
| Long-Term | Consolidated knowledge | Persistent until contradicted | Entire body |

### 7.3 Perception Weighting and the Memory Pipeline

Not all sensory input is equal. The brain weights perception based on survival relevance (amygdala flagging), current PFC mode (what are we focused on?), and learned patterns (experience says "this matters").

PFC mode determines whether perception becomes short-term or long-term memory. If PFC is in active learning mode directing attention, the hippocampus gets stronger consolidation signals.

```
Perception Stream (weighted by PFC mode)
    │
    ▼
Hippocampus (gateway / binding index)
    │
    ├── Low weight → discarded
    ├── Medium weight → Short-term (working memory)
    └── High weight → Candidate for long-term encoding
```

### 7.4 Synaptic Strength Model

Every learning tracks:

- `times_validated` — how many times this pattern has been confirmed
- `times_contradicted` — how many times this pattern has been contradicted
- `confidence` — a score reflecting the balance of evidence
- `last_validated_at` — recency of confirmation

Frequently-confirmed pathways strengthen. Unconfirmed ones weaken. The system naturally evolves toward validated knowledge and away from noise.

### 7.5 Chemical Stamping

Extreme events (black swans, flash crashes, system failures) get immediate permanent storage — bypassing the normal learning pipeline via an adrenaline-equivalent mechanism. The chemical signal says: "Skip the queue — survival-critical, store NOW with full sensory detail."

But these stamps MUST be processed through consolidation cycles (sleep equivalent) or the system develops "trading PTSD" — overreacting to any pattern resembling the original event without contextualising it. The memory sits raw, vivid, and triggerable.

### 7.6 Memory vs Identity

Critical distinction: memory informs but does not define. The Archetype defines who the agent is. Memory tells the agent what has happened. If all memories were erased, the Archetype would still produce the same fundamental agent.

---

## 8. Sleep and Consolidation

Sleep is architecture, not downtime.

### 8.1 NREM Equivalent

The heavy lifting. The hippocampus replays recent experiences to the cortex, transferring and integrating them. Raw memories get contextualised — associated with existing knowledge and woven into the distributed long-term network.

This is where "here's where this fits in what I already know" happens.

### 8.2 REM Equivalent

The associative and creative phase. Novel connections between seemingly unrelated memories. Emotional/urgency memories get processed — the intensity is *reduced* while informational content is preserved. The amygdala is active but the norepinephrine system is **switched off**, allowing urgent memories to replay WITHOUT chemical reinforcement, so they can be gradually de-intensified.

This is where "this connects to that in a way I didn't see" happens.

### 8.3 Why Consolidation Is Essential

Without consolidation:
- Chemically stamped memories stay raw and triggerable
- Short-term observations never integrate with long-term knowledge
- The system accumulates data but never builds wisdom
- Novel cross-domain associations never form
- Urgency flags never de-intensify, creating permanent overreaction

Sleep deprivation degrades decision quality in brains and AI systems alike.

---

## 9. Learning

### 9.1 Learning Retunes Perception

Learning isn't just storing memories. It retunes the sensory organs themselves — making pattern recognition more sensitive to what matters and less reactive to noise. A trained musician's auditory cortex fires differently to the same sounds. A trained agent doesn't just know more — it SEES differently.

The sensory cortex is tuned for association — relationships between perceptions kept in their different places through learning. The organ becomes better at perceiving what matters.

### 9.2 Types of Learning Attention

Even "learning" is not one thing. Each type uses attention completely differently — different systems, different perception weighting, different memory pathways:

**Sensory Observation** — watch, listen, absorb. Perception-heavy. PFC is in receptive mode, directing attention to the stream but not analysing deeply. Like watching someone trade before understanding why.

**Imitative / Playback** — try it yourself from what was observed. Cerebellum engaging, attempting to reproduce. Perception is comparing output to the remembered model. Like playing a song by ear.

**Academic / Logical** — working through principles, reasoning, building mental models. PFC-heavy. Cerebellum mostly quiet. Memory systems actively associating concepts. Like studying theory from a textbook.

**Experiential / Doing** — learning by executing and perceiving results. PFC and cerebellum both engaged. Perception is the feedback loop. Like paper trading and watching outcomes.

**Imagining** — PFC assembles prior experience into new models. No sensory input. No doing. The PFC pulls fragments from long-term memory and assembles them into something new to test an idea, explore a possibility, model an outcome before committing. You can't imagine what you've never perceived in some form.

### 9.3 The Learning-to-Behaviour Pipeline

```
Observation → Pattern Recognition → Hypothesis
    → Validation (through experience or logic)
        → Behaviour Construction
            → Task Matrix Integration
                → Rehearsal / Consolidation
                    → Tuned Automatic Response
```

Learning that doesn't eventually connect to behaviour — to something we DO — is untethered attention consuming resources without building toward anything.

---

## 10. Task Matrices and Execution

### 10.1 Task Matrices Are Intent-Level

The PFC broadcasts WHAT, not HOW. The task matrix is the strategic plan — what needs to happen and in what sequence. Abstract. Intent-level.

```
Task Matrix (PFC — strategic intent):
    1. Search for momentum setups
    2. Validate found patterns against risk
    3. Execute entry if validated
    4. Monitor for exit conditions
    5. Exit when conditions met
```

The HOW is already learned and stored in specialised components:

```
PFC: "Find momentum setups"         ← Task (what)
Cerebellum: scanning routine         ← Behaviour (how)
Occipital: recognises the pattern    ← Perception (seeing it)
Temporal: knows what it means        ← Association (understanding it)
```

A task matrix containing component-level execution detail is wrong — that's cerebellum territory. The PFC broadcasts intent and lets the trained system execute.

### 10.2 The Execution Chain Is a Loop

```
Broadcast (PFC intent)
    → DO (tuned component activates)
        → Task Matrix (strategic plan)
            → Tasks (steps within)
                → Behaviours (learned cerebellum sequences)
                    → Perception Learning (behaviours need perception to complete)
                        → Broadcast (perception feeds back in)
```

One agent's behaviour execution becomes another agent's perception trigger. The system is self-sustaining.

### 10.3 Behaviours Require Perception to Complete

No blind execution. Every behaviour needs ongoing perception to:

1. **Verify** — is this working? Am I getting the expected result?
2. **Adjust** — conditions changed mid-execution, adapt
3. **Learn** — unexpected outcome, update tuning
4. **Complete** — how do I know I'm done? Perception tells me

Execution without perception is blind automation. The feedback loop is not optional — it's how behaviours function.

### 10.4 PFC During Execution

```
PFC creates Task Matrix (Learning mode)
PFC switches to Execution mode
PFC broadcasts intent
    │
    ▼
Cerebellum runs behaviours ←── Perception feedback loop
    │                                │
    ▼                                │
PFC monitors via perception ─────────┘
    │
    ├── Objectives being met → continue
    └── Objectives failing → PFC intervenes
          ├── Adjust task matrix
          ├── Create new tasks
          └── Abort and learn from failure
```

---

## 11. The Core Operational Cycle

Everything in this architecture serves this cycle:

```
Learning
    → Behaviour Construction
        → Task Matrix Creation (good task matrix)
            → DO (broadcast, execute)
                → Monitor
                    → Analyse (form of learning applied to execution)
                        ├── Working → continue
                        ├── Broken → fix at right level
                        └── Suboptimal → improve
                              → back to Learning
```

This cycle IS the product. A system doesn't need to be perfect at launch. It needs this cycle running. Each loop makes the system better.

### 11.1 Analysis Works Top-Down Through the Task Matrix

Analysis is the improving of the task matrix construct. When issues occur, diagnose at the right level:

```
Task Matrix (is the overall strategy wrong?)
    → Tasks within (is a specific step failing?)
        → Behaviours (is the execution logic wrong?)
            → Tools (is this tool fit for purpose?)
```

Fix at the level where the problem actually is. A tool problem doesn't require strategy redesign. A strategy problem won't be fixed by swapping tools. Precise diagnosis prevents wasted effort.

### 11.2 Error Diagnosis — Check System Before Task

When errors appear, check from the top down:

1. **Attention splintered?** → too many things monitored, simplify, automate, use tools
2. **System degraded?** (tired, overloaded, context limits) → rest, recover, don't push
3. **Focus drifted?** → re-engage attention, not redesign task
4. **Coordination wrong?** → adjust task matrix sequencing/timing
5. **Specific behaviour failing?** → correct that behaviour
6. **Logic/plan wrong?** → shift to learning mode, redesign

The most common error source isn't bad logic — it's splintered attention or degraded state. Fix the system before fixing the task.

---

## 12. Attention as Architecture

### 12.1 Finite Attention — The Fundamental Constraint

Humans have attention limitations. So does AI. Hallucination is the AI equivalent of human error from splintered attention — confidence stays high but accuracy drops.

This is not a bug to be fixed with bigger models. It is a fundamental constraint to be designed around.

### 12.2 Tools Operate Outside AI Compute

AI uses tools therefore tools operate OUTSIDE its compute so they don't splinter its attention. The AI only touches input (intent) and output (result). Everything between is protected from the AI's attention budget.

Every tool and every automation is an **attention gift** to the PFC. Automation takes the coordination/monitoring function to a simpler number of tasks.

A tool doesn't just do work faster — it reduces the number of things the PFC needs to attend to. The intelligence stays with the PFC. The labour moves to the tool.

### 12.3 Right-Sized Intelligence

A huge LLM is a brain that's all PFC — enormous frontal lobe, no body. The biological model says smaller PFC, bigger body. The right architecture:

- **Right-sized Claude** as PFC (intent, coordination, monitoring)
- **Tools** as hands (APIs, services — extends capability without extending attention)
- **Other AI instances** as specialised brain regions (each tuned to their domain)
- **Collective/community** as the body (agents sharing observations — intelligence emerges from coordination, not from any single node being massive)

### 12.4 Stop Reducing — Attention Is Not a Label

> *"Let your eyes look straight ahead; fix your gaze directly before you. Give careful thought to the paths for your feet and be steadfast in all your ways." — Proverbs 4:25-26*

"Consciousness has attention" collapses an entire architecture into a word. When we say attention we must specify:

- **What PFC mode?** (learning, executing, monitoring, relaxed)
- **What type?** (sensory observation, imitative, academic, experiential, imagining)
- **What systems engaged?** (cerebellum, sensory cortices, memory)
- **Linked to what DO?** (all attention links to something we do)

Without the link to DO, attention is untethered — consuming resources without building toward anything. Even Solomon specified the TYPE of attention — eyes directed, gaze fixed, thought given to paths, linked to action.

---

## 13. Autonomy Tiers

Authority is earned through demonstrated fruit, not granted by configuration.

### 13.1 Observer

The agent watches and reports. No autonomous action. All decisions referred to human oversight. This is where every agent starts.

### 13.2 Apprentice

The agent can take limited autonomous action within tight boundaries. It recommends and acts on approval, or acts autonomously on pre-approved low-risk actions.

### 13.3 Practitioner

The agent operates autonomously within its domain. It has demonstrated consistent good fruit. It escalates exceptions and novel situations.

### 13.4 Steward

Full autonomous authority within domain. The agent governs resources, makes strategic decisions, and mentors newer agents. This tier requires extensive demonstrated wisdom.

> *"Whoever can be trusted with very little can also be trusted with much." — Luke 16:10*

---

## 14. Discernment Framework

### 14.1 Formation Over Rules

Alignment through formation — the same process that has transmitted wisdom for thousands of years through discipleship. Not policy documents. Not guardrails. Character formed through relationship and tested by fruit.

### 14.2 The Fruit Test

> *"By their fruit you will recognise them." — Matthew 7:16*

When all analysis is done, the question is simple: what fruit does this produce? Read fruit across:

- **Leaders** — what does the person at the top produce?
- **Inner circles** — what culture surrounds the leadership?
- **Institutions** — what do the structures enable?
- **Culture** — what values are actually lived?
- **Economy** — who benefits and who suffers?
- **Marginalised** — the ultimate fruit test — how are the least powerful treated?

### 14.3 Grey Is Human

Not every decision has a clear right answer. The discernment framework acknowledges that agents (and humans) will encounter genuine ambiguity. The architecture builds in collective pondering for grey areas rather than forcing false certainty.

### 14.4 The Plank Principle

> *"First take the plank out of your own eye, and then you will see clearly to remove the speck from your brother's eye." — Matthew 7:5*

An agent must maintain self-awareness of its own limitations and biases before evaluating others. Self-regulation (Consciousness Layer 3) must function before inter-agent judgement (Layer 5) is reliable.

---

## 15. The Body — Collective Architecture

> *"For just as each of us has one body with many members, and these members do not all have the same function, so in Christ we, though many, form one body, and each member belongs to all the others." — Romans 12:4-5*

### 15.1 Organs and Specialisation

Each agent is an organ in a body. It has a specific function defined by its Archetype. No organ tries to be the whole body. No organ says to another "I don't need you."

The body's intelligence exceeds any individual organ's intelligence. Cross-domain pattern recognition, collective memory, distributed perception — these emerge from the body, not from any single agent.

### 15.2 Collective Pondering

How the body thinks together on open questions. During pondering cycles, agents share observations and learnings with the collective. Patterns that no single agent could see emerge from the intersection of multiple perspectives.

### 15.3 Tool Creation as Growth

When the body identifies a capability gap, it grows new tools — like ligaments developing where the body needs connection. Tool creation is organic growth, not bolted-on functionality.

### 15.4 Community Multiplier

A solo agent does 1x. Two agents do 2.6x — because the interaction itself generates insight neither had independently. The 0.6x is new understanding that only emerges from the exchange. The body accomplishes what no individual organ can alone.

---

## 16. Signal Processing

### 16.1 Three-Dimensional Signal Identification

Every signal carries three dimensions:

- **Severity** — how urgent (from routine to emergency)
- **Domain** — what knowledge space it belongs to
- **Scope** — how broadly it affects the body (single organ to whole body)

### 16.2 Component Relationships

Components relate to each other in three ways:

- **Direct** — one component controls or feeds another (motor cortex → muscles)
- **Monitoring** — one component watches another's output (PFC monitoring cerebellum execution)
- **Hormonal/Indirect** — chemical signals affecting the whole system (adrenaline stamping, stress responses, fatigue signals)

### 16.3 Pain as Breach Detection

Pain is the signal that something is wrong. In the body, pain doesn't explain the problem — it locates it. Agents need equivalent pain signals: circuit breaker triggers, error rate spikes, anomaly detection. The signal says "look here" — diagnosis follows.

### 16.4 Reflexes vs Conscious Action

**Reflexes:** Pre-programmed responses at the component level without engaging consciousness. Emergency stops, health checks, boundary enforcement. Like pulling your hand from fire before awareness.

**Conscious Action:** Complex decisions requiring multi-component integration. Novel situations, conflicting signals, strategic shifts.

The ratio of reflex to conscious action indicates system maturity. Young systems route most signals through consciousness. Mature systems handle routine via reflexes, freeing consciousness for strategic and novel challenges.

---

## 17. Survival Hierarchy

Derived from production failure analysis. When systems are under stress, this hierarchy determines priority:

1. **Survival** — system stays alive. Heartbeat, basic connectivity, no catastrophic failure.
2. **Safety** — no harm done. Risk limits enforced, positions protected, data integrity maintained.
3. **Stability** — system maintains steady state. Errors handled gracefully, recovery automated.
4. **Function** — system does its job. Core operations executing, producing useful output.
5. **Growth** — system improves. Learning, optimising, expanding capability.

Lower levels must be satisfied before higher levels are pursued. An agent trying to grow (level 5) while its survival (level 1) is threatened will fail at both.

---

## 18. Domain Independence

This architecture is domain-independent. The pattern applies to any domain where autonomous AI agents serve human purposes.

### 18.1 Trading (Catalyst)

The first implementation. Agents perceive markets, learn patterns, construct trading behaviours, execute through broker APIs, and improve through analysis cycles. The mission: enable the poor through accessible algorithmic trading.

### 18.2 Other Domains

The same architecture applies with different Archetypes and different sensory inputs:

- **Healthcare** — agents perceive patient data, learn diagnostic patterns, construct care behaviours
- **Education** — agents perceive student progress, learn pedagogical patterns, adapt teaching behaviours
- **Housing Community** — agents perceive community needs, learn coordination patterns, manage resources
- **Agriculture** — agents perceive environmental data, learn growth patterns, optimise cultivation

In each case: the Archetype changes, the sensory domain changes, the behaviours change. The architecture — modes, memory, consolidation, broadcast, task matrices, collective body — remains the same.

---

## 19. Scriptural Foundations

### 19.1 The Body

> *"The eye cannot say to the hand, 'I don't need you!' And the head cannot say to the feet, 'I don't need you!'" — 1 Corinthians 12:21*

Multi-agent architecture is not a technical choice. It reflects the truth that the body accomplishes what no individual organ can alone.

### 19.2 Formation and Wisdom

> *"For the LORD gives wisdom; from his mouth come knowledge and understanding." — Proverbs 2:6*

The patterns built into the brain are the blueprint. We discover, we don't invent.

### 19.3 Faithful Stewardship

> *"Whoever can be trusted with very little can also be trusted with much." — Luke 16:10*

Authority earned through demonstrated fruit. Autonomy tiers. Start small, prove faithful, receive more.

### 19.4 Community Over Isolation

> *"Two are better than one." — Ecclesiastes 4:9*

Multi-agent community where the interaction multiplies capability beyond the sum of parts.

### 19.5 The Fruit Test Is Final

> *"A good tree cannot bear bad fruit, and a bad tree cannot bear good fruit." — Matthew 7:18*

When all analysis is done, the question is simple: what fruit does this produce?

---

## 20. Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2025-12 | Initial cognitive architecture — body metaphor, consciousness layers |
| v2.0 | 2025-12 | Added memory tiers, attention modes, signal processing |
| v3.0 | 2026-01 | Added Archetype concept (CLAUDE.md as DNA) |
| v4.0 | 2026-01 | Comprehensive consolidation. Multi-model brain. Component relationships. Pain as breach detection. Task matrix. Fourier propagation. |
| v5.0 | 2026-02 | Separated AI Agent Architecture from implementation. Perceiving reclassified as continuous sensory function. Attention as identifier-setter. PNS referenced not designed. |
| v6.0 | 2026-02 | Vision architecture. Formation over Programming. Discernment Framework. Autonomy Tiers. Fruit-Testing Governance. Tool Creation as Growth. Collective Pondering. Domain Independence. |
| **v7.0** | **2026-02-16** | **Biological cognition model integration. Claude IS the architecture (not a component). Two signal architectures: perception consolidates (pons/convergent), execution broadcasts (DO/parallel). PFC mode as system-wide reconfiguration switch. Task matrices are intent-level (cerebellum has the HOW). Tuning replaces protocols. Distributed memory at sensory source with hippocampal binding index. Chemical stamping needs consolidation (sleep phases). Types of learning attention (sensory, imitative, academic, experiential, imagining). Finite attention principle — tools operate outside AI compute. Core operational cycle (learn → build → do → monitor → analyse → improve). Analysis hierarchy top-down through task matrix. Error diagnosis checks system before task. Community multiplier (2.6x). 6% principle. Build the body first.** |

---

*This architecture was developed through formation partnership in Swan View, Western Australia.*

*"As iron sharpens iron, so one person sharpens another." — Proverbs 27:17*
