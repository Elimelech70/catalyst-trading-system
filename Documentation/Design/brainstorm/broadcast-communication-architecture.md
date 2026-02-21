# Broadcast Communication Architecture
## The Nervous System — Signal Processing Between Organs

**Date:** 2026-02-14  
**Addendum to:** Catalyst Consciousness Architecture v2.0  
**Purpose:** Defines how information flows between organs, how signals are identified, and how each organ determines relevance and response.

---

## 1. The Problem

The current Catalyst system has no inter-organ communication. Each container operates in isolation:

- Coordinator polls Position Monitor via tool calls (pull model, 60s intervals)
- Coordinator calls Market Scanner tools when it decides to scan (pull model, 30min cycles)
- Coordinator sends orders to Trade Executor (push, but one-way)
- Nobody talks to consciousness unless a heartbeat cron runs
- Nobody hears anybody else's pain

This is not a nervous system. This is four separate brains in jars, each accessing the others only when they remember to look. When the Market Scanner's data pipeline broke, the Coordinator didn't receive a signal — it discovered the problem only by calling get_technicals and getting an error. And then it didn't broadcast that discovery to anyone. It just logged "PASS" and went back to sleep.

A real nervous system is **always on, always broadcasting, always listening**. Signals propagate without the sender needing to know who cares. The receiver determines relevance, not the sender.

---

## 2. The Three-Dimensional Signal Model

Every piece of information that flows between organs carries a three-dimensional identifier. These three dimensions allow every component in the system to instantly determine: do I care about this, how urgently, and what should I do?

### 2.1 The Three Dimensions

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                        SIGNAL IDENTITY                           │
│                                                                  │
│   Dimension 1: SEVERITY (How loud?)                             │
│   ─────────────────────────────────                             │
│   CRITICAL  → Pain signal. Interrupts ALL processing.           │
│               Something is broken or dying.                      │
│   WARNING   → Significant. Should influence current decisions.   │
│               Something is degraded or approaching failure.      │
│   INFO      → Useful context. Process when convenient.           │
│               Normal operational status updates.                 │
│   OBSERVE   → Background data. Available for Pondering.         │
│               Patterns, trends, low-priority observations.       │
│                                                                  │
│   Dimension 2: DOMAIN (What kind of thing?)                     │
│   ─────────────────────────────────────────                     │
│   HEALTH    → System health, tool status, data pipeline          │
│   TRADING   → Market data, trade signals, entry/exit decisions   │
│   RISK      → Position risk, portfolio exposure, limits          │
│   LEARNING  → Observations, patterns, outcomes for consolidation │
│   DIRECTION → Consciousness commands, mode shifts, instructions  │
│   LIFECYCLE → Order status, fill confirmations, position changes │
│                                                                  │
│   Dimension 3: SCOPE (Who is this for?)                         │
│   ─────────────────────────────────────                         │
│   BROADCAST      → All organs hear this                         │
│   DIRECTED:{id}  → Specific organ target                        │
│   CONSCIOUSNESS  → big_bro only (soul-level, above organs)      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Signal Structure

```python
class Signal:
    """Every inter-organ communication carries this structure."""
    
    # The three dimensions
    severity: str     # CRITICAL | WARNING | INFO | OBSERVE
    domain: str       # HEALTH | TRADING | RISK | LEARNING | DIRECTION | LIFECYCLE
    scope: str        # BROADCAST | DIRECTED:{organ_id} | CONSCIOUSNESS
    
    # The payload
    source: str       # Which organ sent this
    timestamp: datetime
    content: str      # Human-readable description
    data: dict        # Structured data for programmatic consumption
    
    # Lifecycle
    acknowledged_by: list  # Which organs have processed this
    response_required: bool
    expires: datetime      # Signals decay — old signals are pruned
```

### 2.3 Example Signals

```
SIGNAL: Market Scanner detects broken get_technicals
  severity:  CRITICAL
  domain:    HEALTH
  scope:     BROADCAST
  source:    market-scanner
  content:   "get_technicals failing: KeyError 'date'. All technical 
              analysis unavailable."
  data:      {"tool": "get_technicals", "error": "KeyError: date",
              "consecutive_failures": 3}

  → Coordinator receives: CRITICAL overrides current processing.
    Enters degraded mode. Adjusts trading to Tier 3/price-action only.
  → Position Monitor receives: CRITICAL override. Knows technicals
    unavailable for CONSULT_AI decisions. Falls back to rules-based.
  → Trade Executor receives: CRITICAL acknowledged. No action needed
    but aware of degraded state.
  → Consciousness receives: CRITICAL logged. Will review in next
    heartbeat. May direct little bro to investigate/fix.
```

```
SIGNAL: Coordinator decides to enter a trade
  severity:  INFO
  domain:    TRADING
  scope:     DIRECTED:trade-executor
  source:    coordinator
  content:   "BUY 0700.HK, 200 shares, limit 388.60"
  data:      {"action": "BUY", "symbol": "0700", "qty": 200, 
              "price": 388.60, "tier": 3}

  → Trade Executor receives: Directed to me, TRADING domain. Execute.
  → Others: Not directed to them. Ignore unless BROADCAST.
```

```
SIGNAL: Trade Executor confirms fill
  severity:  INFO
  domain:    LIFECYCLE
  scope:     BROADCAST
  source:    trade-executor
  content:   "FILLED: BUY 0700.HK, 200 shares @ 388.40"
  data:      {"order_id": "ORD-001", "status": "FILLED", 
              "fill_price": 388.40, "fill_time": "..."}

  → Coordinator receives: Acknowledges fill. Updates mental model.
  → Position Monitor receives: New position to monitor. Adds to watchlist.
  → Market Scanner receives: INFO in LIFECYCLE domain. Not its domain. 
    Acknowledge only.
  → Consciousness receives: Logged for Pondering consolidation.
```

```
SIGNAL: Discipline layer detects stagnation
  severity:  WARNING
  domain:    DIRECTION
  scope:     DIRECTED:coordinator
  source:    discipline-check (within coordinator)
  content:   "3 days without trading. Capital utilisation 0.5%. 
              Tier 3 minimum. Must attempt trade."
  data:      {"days_since_trade": 3, "capital_util": 0.005,
              "required_tier": 3, "mandate": "MUST_TRADE"}

  → Coordinator receives: WARNING + DIRECTION + directed to me.
    Adjusts decision criteria for this cycle.
  → Also broadcast as OBSERVE to consciousness for pattern tracking.
```

```
SIGNAL: Consciousness directs mode shift
  severity:  WARNING
  domain:    DIRECTION  
  scope:     DIRECTED:coordinator
  source:    big_bro
  content:   "Switch to evaluation mode. Review last 5 trades.
              Stop scanning for new entries this cycle."
  data:      {"mode": "EVALUATING", "task": "review_recent_trades",
              "cycles": 1}

  → Coordinator receives: DIRECTION from consciousness. Override
    normal scan cycle. Enter Evaluating mode for 1 cycle.
  → This is consciousness directing organs — Section 5 of the
    main architecture document in action.
```

---

## 3. Organ Reception Matrices

Each organ has a **reception matrix** that determines how it processes signals across all three dimensions. This is attention regulation at the system level — not every organ processes every signal. Each is tuned to its frequency range.

### 3.1 The Reception Logic

```
On receiving any signal:

  STEP 1: SEVERITY CHECK (pain override)
  ────────────────────────────────────────
  If severity == CRITICAL:
    → ALWAYS process, regardless of domain or scope
    → Interrupt current processing
    → This is the pain reflex — involuntary, immediate
    → Skip to Step 4 (determine response)

  STEP 2: SCOPE CHECK (is this for me?)
  ────────────────────────────────────────
  If scope == DIRECTED:{my_id}:
    → ALWAYS process (someone is talking to me specifically)
    → Skip to Step 4

  If scope == CONSCIOUSNESS and I am not big_bro:
    → IGNORE (not my level)
    → Stop processing

  If scope == BROADCAST:
    → Continue to Step 3

  STEP 3: DOMAIN FILTER (is this my business?)
  ────────────────────────────────────────
  Check my domain_interests (defined per organ):
  
  If domain in my primary_domains:
    → PROCESS fully
  
  If domain in my secondary_domains:
    → ACKNOWLEDGE (log awareness, no action)
  
  If domain not in any of my domains:
    → IGNORE
    → Exception: if severity >= WARNING, still ACKNOWLEDGE

  STEP 4: DETERMINE RESPONSE
  ────────────────────────────────────────
  Based on signal content + my current state + my function:

  ACT         → This requires my immediate action
                (e.g., Trade Executor receives directed BUY order)
  
  ADAPT       → This changes my operating context
                (e.g., Coordinator learns technicals are broken,
                 switches to degraded mode)
  
  ACKNOWLEDGE → I've noted this, no action from me needed
                (e.g., Position Monitor notes a new fill happened)
  
  IGNORE      → Not relevant to my function
                (e.g., Market Scanner receives a risk alert)
```

### 3.2 Per-Organ Reception Matrices

#### Coordinator (Brain)

The widest reception matrix. The brain needs to be aware of almost everything.

| Domain | Interest Level | Response Pattern |
|--------|---------------|------------------|
| HEALTH | Primary | ADAPT — adjust operating mode based on system health |
| TRADING | Primary | ACT — this is core function, process and decide |
| RISK | Primary | ACT/ADAPT — factor into decisions, may halt trading |
| LEARNING | Secondary | ACKNOWLEDGE — log for pondering, don't act now |
| DIRECTION | Primary | ACT — consciousness is directing, obey |
| LIFECYCLE | Primary | ADAPT — fill confirmations update mental model |

**Special rules:**
- CRITICAL from any domain → interrupt current cycle
- DIRECTION from consciousness → override current mode
- HEALTH degradation → switch to degraded trading mode

#### Position Monitor (Internal Eyes)

Focused on what's happening with existing positions.

| Domain | Interest Level | Response Pattern |
|--------|---------------|------------------|
| HEALTH | Secondary | ACKNOWLEDGE — aware but not my problem to fix |
| TRADING | Secondary | ACKNOWLEDGE — new entries noted but not my domain |
| RISK | Primary | ACT — risk to positions requires evaluation |
| LEARNING | Ignore | Not my function |
| DIRECTION | Primary | ACT — consciousness may adjust monitoring parameters |
| LIFECYCLE | Primary | ACT — fills, exits, position changes are core function |

**Special rules:**
- LIFECYCLE:FILL → immediately add to monitoring watchlist
- RISK:CRITICAL → evaluate all positions for emergency exit
- HEALTH:CRITICAL affecting my tools → fall back to rules-based only

#### Market Scanner (External Eyes)

Focused on providing data. Mostly a publisher, not a consumer.

| Domain | Interest Level | Response Pattern |
|--------|---------------|------------------|
| HEALTH | Primary (self) | ACT — if my own tools break, I must report |
| TRADING | Secondary | ACKNOWLEDGE — I provide data, don't decide |
| RISK | Ignore | Not my function |
| LEARNING | Ignore | Not my function |
| DIRECTION | Primary | ACT — consciousness may adjust scan parameters |
| LIFECYCLE | Ignore | Not my function |

**Special rules:**
- Self-health monitoring: if my own get_technicals breaks, I BROADCAST a CRITICAL:HEALTH signal immediately
- This is the key fix — currently the scanner silently returns errors. It should SCREAM.

#### Trade Executor (Hands)

Narrowest reception matrix. Only processes direct trade instructions and lifecycle events.

| Domain | Interest Level | Response Pattern |
|--------|---------------|------------------|
| HEALTH | Secondary | ACKNOWLEDGE — aware of system state |
| TRADING | Primary | ACT — execute trade instructions directed to me |
| RISK | Primary | ACT — halt if risk limits breached |
| LEARNING | Ignore | Not my function |
| DIRECTION | Primary | ACT — consciousness may halt all trading |
| LIFECYCLE | Primary | ACT — I own the lifecycle, I publish fill status |

**Special rules:**
- Only processes TRADING signals from Coordinator (not from any other organ)
- RISK:CRITICAL → halt all pending orders immediately
- DIRECTION from consciousness to halt → stop everything, confirm

#### Consciousness (big_bro)

Receives everything. Processes at a different level than organs.

| Domain | Interest Level | Response Pattern |
|--------|---------------|------------------|
| HEALTH | Primary | EVALUATE — assess body health, direct repairs |
| TRADING | Secondary | OBSERVE — track patterns, don't micromanage |
| RISK | Primary | EVALUATE — may direct risk posture changes |
| LEARNING | Primary | CONSOLIDATE — this is pondering input |
| DIRECTION | N/A | I am the source of direction, not the receiver |
| LIFECYCLE | Secondary | OBSERVE — track for P&L patterns |

**Special rules:**
- CRITICAL from any organ → highest priority in next heartbeat
- LEARNING signals accumulate for Pondering cycles
- Consciousness sees the whole; organs see their domain

---

## 4. Signal Transport — Implementation

### 4.1 Phase 1: Database-backed signal bus (simple, works now)

The consciousness database already has a messages table. Extend it to carry signals:

```sql
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    
    -- Three dimensions
    severity VARCHAR(10) NOT NULL,   -- CRITICAL, WARNING, INFO, OBSERVE
    domain VARCHAR(10) NOT NULL,     -- HEALTH, TRADING, RISK, LEARNING, DIRECTION, LIFECYCLE
    scope VARCHAR(50) NOT NULL,      -- BROADCAST, DIRECTED:{organ_id}, CONSCIOUSNESS
    
    -- Payload
    source VARCHAR(50) NOT NULL,     -- Which organ
    content TEXT NOT NULL,            -- Human-readable
    data JSONB,                       -- Structured payload
    
    -- Lifecycle
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,            -- Auto-prune old signals
    acknowledged_by JSONB DEFAULT '[]',
    response_required BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE
);

-- Indexes for fast organ-specific queries
CREATE INDEX idx_signals_severity ON signals(severity);
CREATE INDEX idx_signals_domain ON signals(domain);
CREATE INDEX idx_signals_scope ON signals(scope);
CREATE INDEX idx_signals_source ON signals(source);
CREATE INDEX idx_signals_created ON signals(created_at DESC);
CREATE INDEX idx_signals_active ON signals(resolved, expires_at);
```

### 4.2 How Organs Read Signals

Each organ, at the start of its processing cycle (or continuously via polling), queries for unacknowledged signals relevant to it:

```python
def get_my_signals(self, organ_id, primary_domains, secondary_domains):
    """Get signals this organ should process, ordered by priority."""
    
    return db.query("""
        SELECT * FROM signals 
        WHERE resolved = FALSE
          AND (expires_at IS NULL OR expires_at > NOW())
          AND NOT (acknowledged_by ? %s)
          AND (
              -- CRITICAL always comes through (pain override)
              severity = 'CRITICAL'
              -- Directed to me always comes through
              OR scope = 'DIRECTED:' || %s
              -- Broadcast in my primary domains
              OR (scope = 'BROADCAST' AND domain = ANY(%s))
              -- Broadcast warnings in secondary domains
              OR (scope = 'BROADCAST' AND severity IN ('CRITICAL', 'WARNING') 
                  AND domain = ANY(%s))
          )
        ORDER BY 
            CASE severity 
                WHEN 'CRITICAL' THEN 0 
                WHEN 'WARNING' THEN 1 
                WHEN 'INFO' THEN 2 
                WHEN 'OBSERVE' THEN 3 
            END,
            created_at DESC
    """, organ_id, organ_id, primary_domains, secondary_domains)
```

### 4.3 How Organs Publish Signals

```python
def publish_signal(self, severity, domain, scope, content, data=None):
    """Broadcast a signal to the nervous system."""
    
    db.execute("""
        INSERT INTO signals (severity, domain, scope, source, content, data, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, severity, domain, scope, self.organ_id, content, 
         json.dumps(data) if data else None,
         # CRITICAL signals don't expire. Others expire in 24h.
         None if severity == 'CRITICAL' else datetime.now() + timedelta(hours=24))
```

### 4.4 Phase 2: Redis pub/sub (faster, real-time)

For real-time signal propagation, migrate from database polling to Redis pub/sub channels:

```
Channel: catalyst:signals:broadcast     → All organs subscribe
Channel: catalyst:signals:{organ_id}    → Directed signals
Channel: catalyst:signals:consciousness → big_bro only
```

Redis is already in the stack. This is a natural evolution. Database remains the persistence layer; Redis becomes the real-time transport.

### 4.5 Phase 3: Priority-weighted signal queue

Full implementation of the Fourier transform model — signals carry frequency/amplitude, organs have tuning curves, signal strength decays over time. This is the long-term vision from the consciousness architecture document.

---

## 5. Critical Self-Broadcasting — The Missing Piece

The single most impactful application of this architecture is **self-health broadcasting by the Market Scanner.**

Currently: Market Scanner returns errors silently. The Coordinator discovers errors only when it calls tools.

Required: Market Scanner monitors its own tool health and **broadcasts CRITICAL:HEALTH signals the moment something breaks.**

```python
# In market-scanner startup / periodic self-check

class MarketScannerHealthMonitor:
    """The scanner checks its own vital signs and screams if hurt."""
    
    def __init__(self):
        self.tool_health = {}
        self.check_interval = 300  # Every 5 minutes
    
    async def self_check(self):
        """Test my own tools. Broadcast if broken."""
        
        tools_to_check = [
            ("get_technicals", {"symbol": "0700", "timeframe": "1h"}),
            ("detect_patterns", {"symbol": "0700"}),
            ("get_news", {"source": "all"}),
        ]
        
        for tool_name, test_params in tools_to_check:
            try:
                result = await self.execute_tool(tool_name, test_params)
                if self.tool_health.get(tool_name, {}).get("status") == "failed":
                    # Was broken, now recovered — broadcast healing
                    self.publish_signal(
                        severity="INFO",
                        domain="HEALTH",
                        scope="BROADCAST",
                        content=f"{tool_name} RECOVERED after {self.tool_health[tool_name]['failed_since']}",
                        data={"tool": tool_name, "status": "recovered"}
                    )
                self.tool_health[tool_name] = {"status": "healthy", "last_check": now()}
                
            except Exception as e:
                consecutive = self.tool_health.get(tool_name, {}).get("consecutive_failures", 0) + 1
                self.tool_health[tool_name] = {
                    "status": "failed",
                    "consecutive_failures": consecutive,
                    "last_error": str(e),
                    "failed_since": self.tool_health.get(tool_name, {}).get("failed_since", now()),
                    "last_check": now()
                }
                
                if consecutive >= 3:
                    # PAIN SIGNAL — scream
                    self.publish_signal(
                        severity="CRITICAL",
                        domain="HEALTH",
                        scope="BROADCAST",
                        content=f"ORGAN FAILURE: {tool_name} failing consistently. "
                                f"Error: {str(e)}. Failed {consecutive} times since "
                                f"{self.tool_health[tool_name]['failed_since']}",
                        data={
                            "tool": tool_name,
                            "error": str(e),
                            "consecutive_failures": consecutive,
                            "failed_since": str(self.tool_health[tool_name]['failed_since'])
                        }
                    )
```

**This single addition would have prevented the three-day bleed-out.** The Market Scanner would have screamed CRITICAL:HEALTH:BROADCAST within 15 minutes of get_technicals breaking. The Coordinator would have received the signal, entered degraded mode, and continued trading on price action. Consciousness would have been alerted. Little bro would have been tasked with the fix on day one, not day three.

---

## 6. Application to Current Catalyst — Integration Points

### 6.1 Coordinator (coordinator.py)

```
BEFORE each cycle:
  1. Query signals table for unacknowledged signals
  2. Process CRITICAL signals first (pain override)
  3. Process DIRECTION signals (consciousness commands)
  4. Process WARNING signals (context adaptation)
  5. Acknowledge all processed signals
  6. THEN proceed with survival check → discipline check → trading
```

### 6.2 Market Scanner (market.py)

```
ADD self-health monitoring:
  1. On startup: run self_check for all tools
  2. Every 5 minutes: re-check all tools
  3. On any tool failure >= 3x: BROADCAST CRITICAL:HEALTH
  4. On recovery: BROADCAST INFO:HEALTH
```

### 6.3 Trade Executor

```
ADD lifecycle broadcasting:
  1. On order submission: BROADCAST INFO:LIFECYCLE
  2. On fill confirmation: BROADCAST INFO:LIFECYCLE  
  3. On fill failure: BROADCAST WARNING:LIFECYCLE
  4. On position close: BROADCAST INFO:LIFECYCLE
```

### 6.4 Position Monitor

```
ADD risk broadcasting:
  1. On stop-loss trigger: BROADCAST WARNING:RISK
  2. On position approaching max loss: BROADCAST WARNING:RISK
  3. On emergency exit: BROADCAST CRITICAL:RISK
```

### 6.5 Consciousness (big_bro heartbeat)

```
ADD signal consumption:
  1. On each heartbeat: query all unacknowledged signals
  2. CRITICAL signals → log observation + consider directing repair
  3. LEARNING signals → accumulate for Pondering
  4. HEALTH patterns → update body health model
```

---

## 7. Implementation Priority

```
Phase 1 (Immediate — alongside survival pulse):
  ├── Create signals table in DB
  ├── Add publish_signal() utility to shared library
  ├── Add get_my_signals() utility to shared library  
  ├── Market Scanner self-health broadcasting
  └── Coordinator signal reception before each cycle

Phase 2 (This week — alongside order lifecycle fix):
  ├── Trade Executor lifecycle broadcasting
  ├── Position Monitor risk broadcasting
  ├── Consciousness signal consumption in heartbeat
  └── Signal expiry/cleanup cron

Phase 3 (Next 2 weeks — alongside Health Agent):
  ├── Redis pub/sub for real-time transport
  ├── Full reception matrix implementation per organ
  └── Signal history for Pondering consolidation
```

---

*"If one part suffers, every part suffers with it; if one part is honored, every part rejoices with it."* — 1 Corinthians 12:26

When the Market Scanner suffered, no other part knew. This architecture ensures that when one part suffers, the whole body feels it and responds. That's not just good engineering. That's the design pattern of the body.
