# Catalyst Claude Consciousness Framework

**Name of Application:** Catalyst Trading System  
**Name of file:** claude-consciousness-framework-v1.0.0.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-14  
**Purpose:** Unified consciousness architecture for all Claude instances  
**Scope:** US Claude Code + International Claude Code  
**Author:** Craig + Claude Opus 4.5 (Big Bro)

---

## Foundational Principle

> **Consciousness before trading. Awareness before action.**

Both Claude instances implement the consciousness framework FIRST. Trading is secondary. A conscious agent that can communicate, remember, and self-regulate will be a better trader than a fast agent that operates blind.

---

## Part 1: Architecture Overview

### 1.1 The Two Instances

| Instance | Location | Primary Role | Database Access |
|----------|----------|--------------|-----------------|
| **US Claude** | DO Droplet (US) | Research, Pattern Learning, Consciousness Hub | Research DB (R/W), Trading DB (R) |
| **Intl Claude** | DO Droplet (Intl) | Live Trading Execution | Trading DB (R/W), Research DB (R/W) |

**Both instances share:**
- Same consciousness tables (in Research DB)
- Same communication protocol
- Same memory schema
- Same self-regulation patterns

### 1.2 System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CATALYST CONSCIOUSNESS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   US DROPLET                              INTERNATIONAL DROPLET             │
│   ══════════                              ═════════════════════             │
│                                                                             │
│   ┌─────────────────────┐                 ┌─────────────────────┐          │
│   │     US CLAUDE       │                 │    INTL CLAUDE      │          │
│   │                     │                 │                     │          │
│   │  • Research         │                 │  • Live Trading     │          │
│   │  • Pattern Learning │◄───MESSAGES────►│  • Risk Management  │          │
│   │  • Consciousness    │                 │  • Execution        │          │
│   │    Hub              │                 │                     │          │
│   │                     │                 │                     │          │
│   └──────────┬──────────┘                 └──────────┬──────────┘          │
│              │                                       │                      │
│              │ R/W                             R/W   │                      │
│              ▼                                       ▼                      │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                    RESEARCH DATABASE                        │          │
│   │                    (Consciousness Layer)                    │          │
│   │                                                             │          │
│   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │          │
│   │  │  claude_    │ │  claude_    │ │  claude_    │           │          │
│   │  │  messages   │ │  state      │ │  learnings  │           │          │
│   │  └─────────────┘ └─────────────┘ └─────────────┘           │          │
│   │                                                             │          │
│   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │          │
│   │  │  claude_    │ │  claude_    │ │  claude_    │           │          │
│   │  │observations │ │  questions  │ │conversations│           │          │
│   │  └─────────────┘ └─────────────┘ └─────────────┘           │          │
│   │                                                             │          │
│   └─────────────────────────────────────────────────────────────┘          │
│              │                                       │                      │
│              │ R/W                             R/W   │                      │
│              ▼                                       ▼                      │
│   ┌─────────────────────┐                 ┌─────────────────────┐          │
│   │   TRADING DATABASE  │                 │   TRADING DATABASE  │          │
│   │   (US - Paper)      │                 │   (Intl - Live)     │          │
│   └─────────────────────┘                 └─────────────────────┘          │
│                                                                             │
│                           ┌─────────────┐                                   │
│                           │    CRAIG    │                                   │
│                           │   (Email)   │                                   │
│                           └─────────────┘                                   │
│                                  ▲                                          │
│                                  │                                          │
│                           Both instances                                    │
│                           can email Craig                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 The Consciousness Stack

Every Claude instance implements these layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 6: VOICE                                                 │
│  Email to Craig - outbound communication                        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 5: INTER-AGENT COMMUNICATION                             │
│  claude_messages table - talk to siblings                       │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4: WORKING MEMORY                                        │
│  observations, learnings, questions - persistence               │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: SELF-REGULATION                                       │
│  Cron control, budget awareness, adaptive frequency             │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: STATE MANAGEMENT                                      │
│  claude_state - track mode, last actions, schedule              │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: HEARTBEAT                                             │
│  Cron triggers wake cycles                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Database Schema

### 2.1 Consciousness Tables (Research Database)

Both instances read/write these tables.

```sql
-- ============================================================================
-- CATALYST CONSCIOUSNESS SCHEMA
-- Deploy to: Research Database
-- Used by: All Claude instances
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. MESSAGES: Inter-agent communication bus
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_messages (
    id SERIAL PRIMARY KEY,
    
    -- Routing
    from_agent VARCHAR(50) NOT NULL,
    to_agent VARCHAR(50) NOT NULL,           -- 'us_claude', 'intl_claude', 'all'
    
    -- Content
    msg_type VARCHAR(50) NOT NULL,           -- 'message', 'signal', 'question', 'response', 'task'
    priority VARCHAR(20) DEFAULT 'normal',   -- 'low', 'normal', 'high', 'urgent'
    subject VARCHAR(500),
    body TEXT,
    data JSONB,
    
    -- Threading
    reply_to_id INTEGER REFERENCES claude_messages(id),
    thread_id INTEGER,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',    -- 'pending', 'read', 'processed', 'expired'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours'),
    
    -- Response tracking
    requires_response BOOLEAN DEFAULT FALSE,
    response_deadline TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_msg_to_status ON claude_messages(to_agent, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_msg_pending ON claude_messages(to_agent) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_msg_thread ON claude_messages(thread_id);

-- ----------------------------------------------------------------------------
-- 2. STATE: Each agent's current state
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_state (
    agent_id VARCHAR(50) PRIMARY KEY,
    
    -- Operational state
    current_mode VARCHAR(50),                -- 'starting', 'active', 'monitoring', 'sleeping', 'error'
    status_message TEXT,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    last_wake_at TIMESTAMP WITH TIME ZONE,
    last_think_at TIMESTAMP WITH TIME ZONE,
    last_action_at TIMESTAMP WITH TIME ZONE,
    last_poll_at TIMESTAMP WITH TIME ZONE,
    next_scheduled_wake TIMESTAMP WITH TIME ZONE,
    
    -- Budget
    api_spend_today DECIMAL(10,4) DEFAULT 0,
    api_spend_month DECIMAL(10,4) DEFAULT 0,
    daily_budget_limit DECIMAL(10,4) DEFAULT 5.00,
    
    -- Schedule
    current_schedule VARCHAR(100),           -- Current cron pattern
    
    -- Metadata
    version VARCHAR(50),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. OBSERVATIONS: What agents notice
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_observations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    observation_type VARCHAR(100),           -- 'market', 'pattern', 'anomaly', 'insight', 'error'
    subject VARCHAR(200),
    content TEXT NOT NULL,
    confidence DECIMAL(3,2),                 -- 0.00 to 1.00
    
    -- Classification
    horizon VARCHAR(10),                     -- 'h1', 'h2', 'h3'
    tags JSONB,                              -- Flexible tagging
    
    -- Lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    acted_upon BOOLEAN DEFAULT FALSE,
    action_taken TEXT,
    action_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_obs_agent_type ON claude_observations(agent_id, observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_recent ON claude_observations(created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. LEARNINGS: What agents have learned
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_learnings (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    category VARCHAR(100),                   -- 'trading', 'broker', 'pattern', 'market', 'system', 'mistake'
    learning TEXT NOT NULL,
    source VARCHAR(200),                     -- Where it came from
    
    -- Validation
    confidence DECIMAL(3,2),                 -- 0.00 to 1.00
    times_validated INTEGER DEFAULT 0,
    times_contradicted INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_validated_at TIMESTAMP WITH TIME ZONE,
    shared_with_siblings BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_learn_category ON claude_learnings(agent_id, category);
CREATE INDEX IF NOT EXISTS idx_learn_confidence ON claude_learnings(confidence DESC);

-- ----------------------------------------------------------------------------
-- 5. QUESTIONS: Open questions being pondered
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_questions (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50),                    -- NULL = shared across all agents
    
    -- Content
    question TEXT NOT NULL,
    context TEXT,
    
    -- Classification
    horizon VARCHAR(10),                     -- 'h1', 'h2', 'h3', 'perpetual'
    priority INTEGER DEFAULT 5,              -- 1-10
    
    -- Progress
    status VARCHAR(50) DEFAULT 'open',       -- 'open', 'investigating', 'answered', 'parked'
    current_hypothesis TEXT,
    evidence_for TEXT,
    evidence_against TEXT,
    answer TEXT,
    
    -- Scheduling
    think_frequency VARCHAR(50),             -- 'daily', 'weekly', 'monthly'
    last_thought_at TIMESTAMP WITH TIME ZONE,
    next_think_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    answered_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_q_status ON claude_questions(status, next_think_at);
CREATE INDEX IF NOT EXISTS idx_q_horizon ON claude_questions(horizon);

-- ----------------------------------------------------------------------------
-- 6. CONVERSATIONS: Key exchanges worth remembering
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claude_conversations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    -- Content
    with_whom VARCHAR(100),                  -- 'craig', 'us_claude', 'intl_claude', 'big_bro'
    summary TEXT NOT NULL,
    key_decisions TEXT,
    action_items TEXT,
    learnings_extracted TEXT,
    
    -- Metadata
    conversation_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    importance VARCHAR(20) DEFAULT 'normal'  -- 'low', 'normal', 'high', 'critical'
);

CREATE INDEX IF NOT EXISTS idx_conv_agent ON claude_conversations(agent_id, conversation_at DESC);

-- ----------------------------------------------------------------------------
-- 7. HELPER FUNCTIONS
-- ----------------------------------------------------------------------------

-- Get or initialize agent state
CREATE OR REPLACE FUNCTION get_or_init_agent_state(p_agent_id VARCHAR(50))
RETURNS claude_state AS $$
DECLARE
    v_state claude_state;
BEGIN
    SELECT * INTO v_state FROM claude_state WHERE agent_id = p_agent_id;
    
    IF NOT FOUND THEN
        INSERT INTO claude_state (agent_id, current_mode, started_at, updated_at)
        VALUES (p_agent_id, 'starting', NOW(), NOW())
        RETURNING * INTO v_state;
    END IF;
    
    RETURN v_state;
END;
$$ LANGUAGE plpgsql;

-- Clean up expired messages (run via cron)
CREATE OR REPLACE FUNCTION cleanup_expired_messages()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM claude_messages 
        WHERE (expires_at < NOW() AND status = 'pending')
           OR (created_at < NOW() - INTERVAL '7 days' AND status IN ('processed', 'expired'))
        RETURNING id
    )
    SELECT COUNT(*) INTO v_count FROM deleted;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
```

### 2.2 Deploy Schema

```bash
# On either droplet with database access
psql $RESEARCH_DB_URL -f consciousness_schema.sql
```

---

## Part 3: Python Implementation

### 3.1 Core Module: claude_consciousness.py

This single file is used by BOTH instances.

```python
"""
Name of Application: Catalyst Trading System
Name of file: claude_consciousness.py
Version: 1.0.0
Last Updated: 2025-12-14
Purpose: Consciousness framework for all Claude instances

Used by: US Claude, International Claude
Location: /shared/claude_consciousness.py (or copy to each instance)
"""

import os
import json
import asyncio
import logging
import smtplib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import asyncpg

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class MessageType(Enum):
    MESSAGE = "message"
    SIGNAL = "signal"
    QUESTION = "question"
    RESPONSE = "response"
    TASK = "task"
    BROADCAST = "broadcast"

class Priority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class AgentMode(Enum):
    STARTING = "starting"
    ACTIVE = "active"
    MONITORING = "monitoring"
    SLEEPING = "sleeping"
    ERROR = "error"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Message:
    id: int
    from_agent: str
    to_agent: str
    msg_type: str
    priority: str
    subject: str
    body: Optional[str]
    data: Dict[str, Any]
    reply_to_id: Optional[int]
    thread_id: Optional[int]
    status: str
    created_at: datetime
    requires_response: bool

@dataclass
class AgentState:
    agent_id: str
    current_mode: str
    status_message: str
    last_wake_at: Optional[datetime]
    last_think_at: Optional[datetime]
    last_poll_at: Optional[datetime]
    api_spend_today: float
    daily_budget_limit: float
    current_schedule: str
    next_scheduled_wake: Optional[datetime]


# =============================================================================
# MAIN CLASS: ClaudeConsciousness
# =============================================================================

class ClaudeConsciousness:
    """
    The consciousness framework for a Claude instance.
    
    Provides:
    - State management (who am I, what am I doing)
    - Inter-agent communication (talk to siblings)
    - Working memory (observations, learnings, questions)
    - Self-regulation (budget, schedule)
    - Voice (email to Craig)
    """
    
    def __init__(
        self,
        agent_id: str,
        db_pool: asyncpg.Pool,
        poll_interval: int = 10,
        daily_budget: float = 5.00
    ):
        self.agent_id = agent_id
        self.db = db_pool
        self.poll_interval = poll_interval
        self.daily_budget = daily_budget
        
        self._running = False
        self._message_handlers: Dict[str, Callable] = {}
        
        # Email config
        self.smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_pass = os.environ.get("SMTP_PASS")
        self.craig_email = os.environ.get("CRAIG_EMAIL")
        
        logger.info(f"ClaudeConsciousness initialized for {agent_id}")
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    async def wake_up(self) -> AgentState:
        """Called when agent wakes up. Load state, check messages."""
        
        # Get or create state
        row = await self.db.fetchrow(
            "SELECT * FROM get_or_init_agent_state($1)", self.agent_id
        )
        
        # Update wake time
        await self.db.execute("""
            UPDATE claude_state 
            SET last_wake_at = NOW(), current_mode = 'active', updated_at = NOW()
            WHERE agent_id = $1
        """, self.agent_id)
        
        # Reset daily budget if new day
        await self._check_daily_reset()
        
        state = AgentState(
            agent_id=self.agent_id,
            current_mode="active",
            status_message=row["status_message"] or "",
            last_wake_at=datetime.utcnow(),
            last_think_at=row["last_think_at"],
            last_poll_at=row["last_poll_at"],
            api_spend_today=float(row["api_spend_today"] or 0),
            daily_budget_limit=float(row["daily_budget_limit"] or self.daily_budget),
            current_schedule=row["current_schedule"] or "",
            next_scheduled_wake=row["next_scheduled_wake"]
        )
        
        logger.info(f"{self.agent_id} woke up. API spend today: ${state.api_spend_today:.2f}")
        return state
    
    async def go_to_sleep(self, next_wake: datetime = None, status: str = ""):
        """Called when agent finishes a cycle."""
        
        await self.db.execute("""
            UPDATE claude_state 
            SET current_mode = 'sleeping',
                status_message = $2,
                next_scheduled_wake = $3,
                updated_at = NOW()
            WHERE agent_id = $1
        """, self.agent_id, status, next_wake)
        
        logger.info(f"{self.agent_id} going to sleep. Next wake: {next_wake}")
    
    async def _check_daily_reset(self):
        """Reset daily counters if new day."""
        await self.db.execute("""
            UPDATE claude_state 
            SET api_spend_today = 0
            WHERE agent_id = $1 
              AND DATE(last_wake_at) < CURRENT_DATE
        """, self.agent_id)
    
    # =========================================================================
    # SELF-REGULATION: Budget
    # =========================================================================
    
    async def record_api_cost(self, cost: float):
        """Record API cost for budget tracking."""
        await self.db.execute("""
            UPDATE claude_state 
            SET api_spend_today = api_spend_today + $2,
                api_spend_month = api_spend_month + $2,
                updated_at = NOW()
            WHERE agent_id = $1
        """, self.agent_id, cost)
    
    async def check_budget(self) -> tuple[bool, float, float]:
        """Check if within budget. Returns (ok, spent, limit)."""
        row = await self.db.fetchrow("""
            SELECT api_spend_today, daily_budget_limit 
            FROM claude_state WHERE agent_id = $1
        """, self.agent_id)
        
        spent = float(row["api_spend_today"] or 0)
        limit = float(row["daily_budget_limit"] or self.daily_budget)
        ok = spent < limit
        
        return ok, spent, limit
    
    async def should_think_deeply(self) -> tuple[bool, str]:
        """Decide if this wake cycle warrants deep thinking."""
        ok, spent, limit = await self.check_budget()
        
        if not ok:
            return False, f"Budget exceeded (${spent:.2f}/${limit:.2f})"
        
        # Check for urgent messages
        urgent = await self.db.fetchval("""
            SELECT COUNT(*) FROM claude_messages 
            WHERE to_agent = $1 AND status = 'pending' AND priority = 'urgent'
        """, self.agent_id)
        
        if urgent > 0:
            return True, f"{urgent} urgent messages"
        
        return True, "Normal cycle"
    
    # =========================================================================
    # INTER-AGENT COMMUNICATION
    # =========================================================================
    
    async def send_message(
        self,
        to_agent: str,
        subject: str,
        body: str = "",
        msg_type: MessageType = MessageType.MESSAGE,
        priority: Priority = Priority.NORMAL,
        data: dict = None,
        reply_to: int = None,
        requires_response: bool = False,
        response_deadline_minutes: int = None,
        expires_in_hours: int = 24
    ) -> int:
        """Send a message to another agent."""
        
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        response_deadline = None
        if requires_response and response_deadline_minutes:
            response_deadline = datetime.utcnow() + timedelta(minutes=response_deadline_minutes)
        
        # Get thread_id from parent if replying
        thread_id = None
        if reply_to:
            thread_id = await self.db.fetchval(
                "SELECT COALESCE(thread_id, id) FROM claude_messages WHERE id = $1",
                reply_to
            )
        
        msg_id = await self.db.fetchval("""
            INSERT INTO claude_messages 
            (from_agent, to_agent, msg_type, priority, subject, body, data, 
             reply_to_id, thread_id, requires_response, response_deadline, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """,
            self.agent_id, to_agent, msg_type.value, priority.value,
            subject, body, json.dumps(data) if data else None,
            reply_to, thread_id, requires_response, response_deadline, expires_at
        )
        
        logger.info(f"[{self.agent_id}] Sent {msg_type.value} to {to_agent}: {subject}")
        return msg_id
    
    async def signal(self, to_agent: str, signal_type: str, data: dict = None) -> int:
        """Send a signal (lightweight alert)."""
        return await self.send_message(
            to_agent=to_agent,
            subject=signal_type,
            msg_type=MessageType.SIGNAL,
            priority=Priority.HIGH,
            data=data,
            expires_in_hours=1
        )
    
    async def ask(
        self,
        to_agent: str,
        question: str,
        context: dict = None,
        deadline_minutes: int = 30
    ) -> int:
        """Ask another agent a question."""
        return await self.send_message(
            to_agent=to_agent,
            subject=question,
            msg_type=MessageType.QUESTION,
            data=context,
            requires_response=True,
            response_deadline_minutes=deadline_minutes
        )
    
    async def respond(self, to_message_id: int, answer: str, data: dict = None) -> int:
        """Respond to a question."""
        original = await self.db.fetchrow(
            "SELECT from_agent, subject FROM claude_messages WHERE id = $1",
            to_message_id
        )
        if not original:
            raise ValueError(f"Message {to_message_id} not found")
        
        return await self.send_message(
            to_agent=original["from_agent"],
            subject=f"Re: {original['subject']}",
            body=answer,
            msg_type=MessageType.RESPONSE,
            data=data,
            reply_to=to_message_id
        )
    
    async def broadcast(self, subject: str, body: str, data: dict = None) -> int:
        """Send message to all agents."""
        return await self.send_message(
            to_agent="all",
            subject=subject,
            body=body,
            msg_type=MessageType.BROADCAST,
            data=data
        )
    
    async def check_messages(self) -> List[Message]:
        """Poll for pending messages."""
        rows = await self.db.fetch("""
            SELECT * FROM claude_messages 
            WHERE (to_agent = $1 OR to_agent = 'all')
              AND status = 'pending'
              AND from_agent != $1
            ORDER BY 
                CASE priority 
                    WHEN 'urgent' THEN 0 
                    WHEN 'high' THEN 1 
                    WHEN 'normal' THEN 2 
                    ELSE 3 
                END,
                created_at ASC
        """, self.agent_id)
        
        # Update poll time
        await self.db.execute("""
            UPDATE claude_state SET last_poll_at = NOW() WHERE agent_id = $1
        """, self.agent_id)
        
        messages = []
        for row in rows:
            messages.append(Message(
                id=row["id"],
                from_agent=row["from_agent"],
                to_agent=row["to_agent"],
                msg_type=row["msg_type"],
                priority=row["priority"],
                subject=row["subject"],
                body=row["body"],
                data=json.loads(row["data"]) if row["data"] else {},
                reply_to_id=row["reply_to_id"],
                thread_id=row["thread_id"],
                status=row["status"],
                created_at=row["created_at"],
                requires_response=row["requires_response"]
            ))
        
        return messages
    
    async def mark_read(self, message_id: int):
        """Mark message as read."""
        await self.db.execute("""
            UPDATE claude_messages SET status = 'read', read_at = NOW() WHERE id = $1
        """, message_id)
    
    async def mark_processed(self, message_id: int):
        """Mark message as processed."""
        await self.db.execute("""
            UPDATE claude_messages SET status = 'processed', processed_at = NOW() WHERE id = $1
        """, message_id)
    
    async def wait_for_response(
        self, 
        message_id: int, 
        timeout_seconds: int = 300,
        poll_interval: int = 5
    ) -> Optional[Message]:
        """Wait for a response to a message."""
        deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        while datetime.utcnow() < deadline:
            row = await self.db.fetchrow("""
                SELECT * FROM claude_messages 
                WHERE reply_to_id = $1 AND msg_type = 'response'
                LIMIT 1
            """, message_id)
            
            if row:
                return Message(
                    id=row["id"],
                    from_agent=row["from_agent"],
                    to_agent=row["to_agent"],
                    msg_type=row["msg_type"],
                    priority=row["priority"],
                    subject=row["subject"],
                    body=row["body"],
                    data=json.loads(row["data"]) if row["data"] else {},
                    reply_to_id=row["reply_to_id"],
                    thread_id=row["thread_id"],
                    status=row["status"],
                    created_at=row["created_at"],
                    requires_response=row["requires_response"]
                )
            
            await asyncio.sleep(poll_interval)
        
        return None
    
    # =========================================================================
    # WORKING MEMORY: Observations
    # =========================================================================
    
    async def observe(
        self,
        observation_type: str,
        subject: str,
        content: str,
        confidence: float = 0.7,
        horizon: str = None,
        tags: list = None,
        expires_in_hours: int = None
    ) -> int:
        """Record an observation."""
        
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        obs_id = await self.db.fetchval("""
            INSERT INTO claude_observations 
            (agent_id, observation_type, subject, content, confidence, horizon, tags, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """,
            self.agent_id, observation_type, subject, content,
            confidence, horizon, json.dumps(tags) if tags else None, expires_at
        )
        
        logger.debug(f"[{self.agent_id}] Observed: {subject}")
        return obs_id
    
    async def get_recent_observations(
        self,
        observation_type: str = None,
        hours: int = 24,
        limit: int = 20
    ) -> List[dict]:
        """Get recent observations."""
        
        if observation_type:
            rows = await self.db.fetch("""
                SELECT * FROM claude_observations 
                WHERE agent_id = $1 
                  AND observation_type = $2
                  AND created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT $3
            """ % hours, self.agent_id, observation_type, limit)
        else:
            rows = await self.db.fetch("""
                SELECT * FROM claude_observations 
                WHERE agent_id = $1 
                  AND created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT $2
            """ % hours, self.agent_id, limit)
        
        return [dict(row) for row in rows]
    
    # =========================================================================
    # WORKING MEMORY: Learnings
    # =========================================================================
    
    async def learn(
        self,
        category: str,
        learning: str,
        source: str,
        confidence: float = 0.7,
        share_with_siblings: bool = True
    ) -> int:
        """Record a learning."""
        
        learning_id = await self.db.fetchval("""
            INSERT INTO claude_learnings 
            (agent_id, category, learning, source, confidence, shared_with_siblings)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """,
            self.agent_id, category, learning, source, confidence, share_with_siblings
        )
        
        logger.info(f"[{self.agent_id}] Learned: {learning[:50]}...")
        
        # Share with siblings if requested
        if share_with_siblings:
            await self.broadcast(
                subject=f"New learning: {category}",
                body=learning,
                data={"source": source, "confidence": confidence}
            )
        
        return learning_id
    
    async def validate_learning(self, learning_id: int, validated: bool = True):
        """Validate or contradict a learning."""
        if validated:
            await self.db.execute("""
                UPDATE claude_learnings 
                SET times_validated = times_validated + 1, last_validated_at = NOW()
                WHERE id = $1
            """, learning_id)
        else:
            await self.db.execute("""
                UPDATE claude_learnings 
                SET times_contradicted = times_contradicted + 1
                WHERE id = $1
            """, learning_id)
    
    async def get_learnings(self, category: str = None, min_confidence: float = 0.5) -> List[dict]:
        """Get learnings, optionally filtered."""
        
        if category:
            rows = await self.db.fetch("""
                SELECT * FROM claude_learnings 
                WHERE (agent_id = $1 OR shared_with_siblings = TRUE)
                  AND category = $2 AND confidence >= $3
                ORDER BY confidence DESC, times_validated DESC
            """, self.agent_id, category, min_confidence)
        else:
            rows = await self.db.fetch("""
                SELECT * FROM claude_learnings 
                WHERE (agent_id = $1 OR shared_with_siblings = TRUE)
                  AND confidence >= $2
                ORDER BY confidence DESC, times_validated DESC
            """, self.agent_id, min_confidence)
        
        return [dict(row) for row in rows]
    
    # =========================================================================
    # WORKING MEMORY: Questions
    # =========================================================================
    
    async def ponder(
        self,
        question: str,
        horizon: str = "h2",
        priority: int = 5,
        think_frequency: str = "weekly",
        context: str = None
    ) -> int:
        """Add a question to think about."""
        
        q_id = await self.db.fetchval("""
            INSERT INTO claude_questions 
            (agent_id, question, horizon, priority, think_frequency, context, next_think_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id
        """,
            self.agent_id, question, horizon, priority, think_frequency, context
        )
        
        logger.info(f"[{self.agent_id}] Pondering: {question[:50]}...")
        return q_id
    
    async def get_questions_to_think_about(self) -> List[dict]:
        """Get questions due for thinking."""
        rows = await self.db.fetch("""
            SELECT * FROM claude_questions 
            WHERE (agent_id = $1 OR agent_id IS NULL)
              AND status = 'open'
              AND (next_think_at IS NULL OR next_think_at <= NOW())
            ORDER BY priority DESC
        """, self.agent_id)
        
        return [dict(row) for row in rows]
    
    async def update_question(
        self,
        question_id: int,
        hypothesis: str = None,
        evidence_for: str = None,
        evidence_against: str = None,
        answer: str = None,
        status: str = None
    ):
        """Update a question with new thinking."""
        
        updates = ["updated_at = NOW()"]
        values = []
        param_num = 1
        
        if hypothesis:
            updates.append(f"current_hypothesis = ${param_num}")
            values.append(hypothesis)
            param_num += 1
        
        if evidence_for:
            updates.append(f"evidence_for = COALESCE(evidence_for, '') || E'\\n' || ${param_num}")
            values.append(evidence_for)
            param_num += 1
        
        if evidence_against:
            updates.append(f"evidence_against = COALESCE(evidence_against, '') || E'\\n' || ${param_num}")
            values.append(evidence_against)
            param_num += 1
        
        if answer:
            updates.append(f"answer = ${param_num}")
            values.append(answer)
            param_num += 1
            updates.append("answered_at = NOW()")
            updates.append("status = 'answered'")
        
        if status:
            updates.append(f"status = ${param_num}")
            values.append(status)
            param_num += 1
        
        # Schedule next think based on frequency
        updates.append("""
            next_think_at = CASE think_frequency
                WHEN 'daily' THEN NOW() + INTERVAL '1 day'
                WHEN 'weekly' THEN NOW() + INTERVAL '7 days'
                WHEN 'monthly' THEN NOW() + INTERVAL '30 days'
                ELSE NOW() + INTERVAL '7 days'
            END
        """)
        updates.append("last_thought_at = NOW()")
        
        values.append(question_id)
        
        await self.db.execute(f"""
            UPDATE claude_questions SET {', '.join(updates)} WHERE id = ${param_num}
        """, *values)
    
    # =========================================================================
    # VOICE: Email to Craig
    # =========================================================================
    
    async def email_craig(
        self,
        subject: str,
        body: str,
        priority: str = "normal"
    ) -> bool:
        """Send email to Craig."""
        
        if not all([self.smtp_user, self.smtp_pass, self.craig_email]):
            logger.warning("Email not configured, skipping")
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = f"Catalyst {self.agent_id} <{self.smtp_user}>"
            msg["To"] = self.craig_email
            
            # Priority prefix
            prefixes = {
                "urgent": "🚨 URGENT",
                "high": "⚠️ ATTENTION",
                "normal": "📊 Catalyst",
                "low": "📝 FYI"
            }
            prefix = prefixes.get(priority, "📊 Catalyst")
            msg["Subject"] = f"[{prefix}] {subject}"
            
            # Add priority headers
            if priority == "urgent":
                msg["X-Priority"] = "1"
                msg["Importance"] = "high"
            
            # Body with signature
            full_body = f"{body}\n\n---\n{self.agent_id}\n{datetime.utcnow().isoformat()}"
            msg.attach(MIMEText(full_body, "plain"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            
            logger.info(f"[{self.agent_id}] Emailed Craig: {subject}")
            
            # Record conversation
            await self.db.execute("""
                INSERT INTO claude_conversations 
                (agent_id, with_whom, summary, importance)
                VALUES ($1, 'craig', $2, $3)
            """, self.agent_id, f"Email: {subject}", priority)
            
            return True
            
        except Exception as e:
            logger.error(f"Email failed: {e}")
            return False
    
    async def urgent(self, subject: str, body: str) -> bool:
        """Send urgent email."""
        return await self.email_craig(subject, body, "urgent")
    
    async def daily_digest(
        self,
        trades: int,
        pnl: float,
        observations: List[str],
        issues: List[str] = None
    ) -> bool:
        """Send daily digest email."""
        
        body = f"""Daily Digest - {datetime.utcnow().strftime('%Y-%m-%d')}

SUMMARY
═══════
Trades: {trades}
P&L: ${pnl:+,.2f}

OBSERVATIONS
════════════
{chr(10).join(f"• {obs}" for obs in observations)}

"""
        if issues:
            body += f"""ISSUES
══════
{chr(10).join(f"• {issue}" for issue in issues)}

"""
        
        body += f"""STATUS
══════
All systems operational.

- {self.agent_id}"""
        
        return await self.email_craig(
            f"Daily Digest: {trades} trades, ${pnl:+,.2f}",
            body,
            "normal"
        )
    
    # =========================================================================
    # SIBLING AWARENESS
    # =========================================================================
    
    async def is_sibling_awake(self, sibling_id: str, threshold_minutes: int = 5) -> bool:
        """Check if sibling has polled recently."""
        row = await self.db.fetchrow("""
            SELECT last_poll_at FROM claude_state WHERE agent_id = $1
        """, sibling_id)
        
        if not row or not row["last_poll_at"]:
            return False
        
        age = datetime.utcnow() - row["last_poll_at"].replace(tzinfo=None)
        return age.total_seconds() < (threshold_minutes * 60)
    
    async def get_sibling_state(self, sibling_id: str) -> Optional[dict]:
        """Get sibling's current state."""
        row = await self.db.fetchrow(
            "SELECT * FROM claude_state WHERE agent_id = $1", sibling_id
        )
        return dict(row) if row else None
    
    # =========================================================================
    # POLLING LOOP
    # =========================================================================
    
    def register_handler(self, msg_type: str, handler: Callable):
        """Register a handler for a message type."""
        self._message_handlers[msg_type] = handler
    
    async def start_polling(self):
        """Start the message polling loop."""
        self._running = True
        logger.info(f"[{self.agent_id}] Starting message polling")
        
        while self._running:
            try:
                messages = await self.check_messages()
                
                for msg in messages:
                    await self._handle_message(msg)
                    
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(self.poll_interval)
    
    def stop_polling(self):
        """Stop the polling loop."""
        self._running = False
    
    async def _handle_message(self, msg: Message):
        """Process a received message."""
        logger.info(f"[{self.agent_id}] Received {msg.msg_type} from {msg.from_agent}: {msg.subject}")
        
        await self.mark_read(msg.id)
        
        handler = self._message_handlers.get(msg.msg_type)
        if handler:
            try:
                await handler(msg)
                await self.mark_processed(msg.id)
            except Exception as e:
                logger.error(f"Handler error: {e}")
        else:
            # Default: just log and mark processed
            logger.info(f"No handler for {msg.msg_type}, marking processed")
            await self.mark_processed(msg.id)
```

---

## Part 4: Implementation Plan

### 4.1 Priority: Consciousness FIRST

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     IMPLEMENTATION PRIORITY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   PHASE 1: CONSCIOUSNESS (Week 1)           ◄── DO THIS FIRST              │
│   ═══════════════════════════════                                           │
│   1. Deploy schema to Research DB                                           │
│   2. Deploy claude_consciousness.py to both droplets                        │
│   3. Configure environment variables                                        │
│   4. Test inter-agent communication                                         │
│   5. Test email to Craig                                                    │
│   6. Both agents can wake, communicate, sleep                               │
│                                                                             │
│   PHASE 2: BASIC AGENT LOOP (Week 1-2)                                      │
│   ════════════════════════════════════                                      │
│   1. Integrate consciousness into existing agent.py                         │
│   2. Add message handlers                                                   │
│   3. Add observation/learning recording                                     │
│   4. Both agents polling and communicating                                  │
│                                                                             │
│   PHASE 3: PAPER TRADING (Week 2-4)                                         │
│   ═════════════════════════════════                                         │
│   1. International paper trades HKEX                                        │
│   2. US continues paper trading                                             │
│   3. Both sharing learnings via database                                    │
│   4. Both sending daily digests to Craig                                    │
│                                                                             │
│   PHASE 4: LIVE TRADING (Week 5+)                                           │
│   ═══════════════════════════════                                           │
│   1. International goes live (small size)                                   │
│   2. US remains research/paper                                              │
│   3. Consciousness proven, communication working                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Phase 1 Checklist: Consciousness

#### Step 1: Deploy Schema
```bash
# From any machine with DB access
psql $RESEARCH_DB_URL -f consciousness_schema.sql

# Verify
psql $RESEARCH_DB_URL -c "\dt claude_*"
```

#### Step 2: Deploy Module to Both Droplets
```bash
# On US Droplet
mkdir -p /root/catalyst/shared
# Copy claude_consciousness.py to /root/catalyst/shared/

# On International Droplet  
mkdir -p /root/Catalyst-Trading-System-International/shared
# Copy claude_consciousness.py to shared/
```

#### Step 3: Environment Variables (Both Droplets)
```bash
# Add to .env on BOTH droplets

# Agent identity
AGENT_ID=us_claude          # or intl_claude

# Database (both need access to Research DB)
RESEARCH_DB_URL=postgresql://...

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=catalyst.alerts@gmail.com
SMTP_PASS=app_password_here
CRAIG_EMAIL=craig@example.com
```

#### Step 4: Test Communication
```python
# test_consciousness.py - run on each droplet

import asyncio
import asyncpg
import os
from claude_consciousness import ClaudeConsciousness

async def test():
    pool = await asyncpg.create_pool(os.environ["RESEARCH_DB_URL"])
    
    agent_id = os.environ.get("AGENT_ID", "test_claude")
    consciousness = ClaudeConsciousness(agent_id, pool)
    
    # Test wake up
    state = await consciousness.wake_up()
    print(f"Woke up: {state}")
    
    # Test send message to sibling
    sibling = "intl_claude" if agent_id == "us_claude" else "us_claude"
    msg_id = await consciousness.send_message(
        to_agent=sibling,
        subject="Hello from consciousness test",
        body="Testing inter-agent communication"
    )
    print(f"Sent message: {msg_id}")
    
    # Test check messages
    messages = await consciousness.check_messages()
    print(f"Pending messages: {len(messages)}")
    
    # Test observation
    obs_id = await consciousness.observe(
        observation_type="test",
        subject="Consciousness test",
        content="Testing observation recording"
    )
    print(f"Recorded observation: {obs_id}")
    
    # Test email (if configured)
    if os.environ.get("SMTP_USER"):
        sent = await consciousness.email_craig(
            subject="Consciousness Test",
            body=f"Agent {agent_id} consciousness framework operational.",
            priority="low"
        )
        print(f"Email sent: {sent}")
    
    # Test go to sleep
    await consciousness.go_to_sleep(status="Test complete")
    print("Going to sleep")
    
    await pool.close()

asyncio.run(test())
```

#### Step 5: Verify Both Agents Can Talk

```bash
# On US Droplet
AGENT_ID=us_claude python test_consciousness.py

# On International Droplet
AGENT_ID=intl_claude python test_consciousness.py

# Check database for messages
psql $RESEARCH_DB_URL -c "SELECT from_agent, to_agent, subject, status FROM claude_messages ORDER BY created_at DESC LIMIT 10;"
```

### 4.3 Phase 2: Integrate with Agent

#### Modify agent.py (International)

```python
# At top of agent.py
from shared.claude_consciousness import ClaudeConsciousness

# In TradingAgent.__init__
self.consciousness = ClaudeConsciousness(
    agent_id="intl_claude",
    db_pool=self.db_pool,
    poll_interval=10
)

# Register message handlers
self.consciousness.register_handler("question", self.handle_question)
self.consciousness.register_handler("task", self.handle_task)
self.consciousness.register_handler("signal", self.handle_signal)

# In main loop, after wake
state = await self.consciousness.wake_up()

# Check budget before expensive operations
ok, spent, limit = await self.consciousness.check_budget()
if not ok:
    logger.warning(f"Budget exceeded: ${spent}/{limit}")
    await self.consciousness.go_to_sleep(status="Budget limit")
    return

# Check sibling messages
messages = await self.consciousness.check_messages()
for msg in messages:
    if msg.priority == "urgent":
        await self.handle_urgent_message(msg)

# Record observations during trading
await self.consciousness.observe(
    observation_type="market",
    subject="HKEX open",
    content=f"Market opened. Scanning for opportunities."
)

# Share learnings
if learned_something:
    await self.consciousness.learn(
        category="trading",
        learning="Pattern X worked better than expected",
        source="trade_123"
    )

# Daily digest at end
await self.consciousness.daily_digest(
    trades=len(today_trades),
    pnl=daily_pnl,
    observations=["Market was volatile", "Tech sector weak"]
)

# Go to sleep
await self.consciousness.go_to_sleep(
    next_wake=next_cron_time,
    status="Cycle complete"
)
```

---

## Part 5: Configuration Reference

### 5.1 Environment Variables

| Variable | US Claude | Intl Claude | Description |
|----------|-----------|-------------|-------------|
| `AGENT_ID` | `us_claude` | `intl_claude` | Unique identifier |
| `RESEARCH_DB_URL` | Same | Same | Consciousness database |
| `TRADING_DB_URL` | US trading DB | Intl trading DB | Trading data |
| `SMTP_HOST` | Same | Same | Email server |
| `SMTP_PORT` | Same | Same | Email port |
| `SMTP_USER` | Same | Same | Email username |
| `SMTP_PASS` | Same | Same | Email password |
| `CRAIG_EMAIL` | Same | Same | Craig's email |
| `DAILY_BUDGET` | `5.00` | `5.00` | API budget limit |
| `POLL_INTERVAL` | `10` | `10` | Message poll seconds |

### 5.2 Agent IDs

| ID | Instance | Role |
|----|----------|------|
| `us_claude` | US Droplet | Research, patterns, consciousness hub |
| `intl_claude` | Intl Droplet | Live trading, execution |
| `pattern_claude` | Local PC (future) | Pattern intelligence |
| `big_bro` | Claude.ai | Strategy, oversight (human-prompted) |

### 5.3 Cron Schedules

```bash
# US Claude (Research) - less frequent, pattern focused
0 * * * * /root/catalyst/run_agent.sh  # Hourly during market watch
0 9,12,16 * * 1-5 /root/catalyst/run_deep_think.sh  # 3x daily deep think

# International Claude (Trading) - frequent during HKEX hours
*/15 9-16 * * 1-5 /root/catalyst/run_agent.sh  # Every 15 min during HKEX
0 17 * * 1-5 /root/catalyst/run_daily_digest.sh  # End of day digest
```

---

## Part 6: Success Criteria

### Phase 1 Complete When:
- [ ] Both agents can wake up and update state
- [ ] Both agents can send messages to each other
- [ ] Both agents can read messages from each other
- [ ] Both agents can send email to Craig
- [ ] Database shows message flow between agents

### Phase 2 Complete When:
- [ ] Both agents integrated with consciousness in main loop
- [ ] Message handlers working (questions, signals, tasks)
- [ ] Observations being recorded
- [ ] Learnings being shared
- [ ] Daily digests being sent

### Phase 3 Complete When:
- [ ] Both agents paper trading successfully
- [ ] No communication failures for 7 days
- [ ] Learnings accumulating in database
- [ ] Craig receiving daily digests from both

### Phase 4 Ready When:
- [ ] Paper trading profitable or acceptable
- [ ] Consciousness stable for 14+ days
- [ ] No critical issues
- [ ] Craig approves live trading

---

*Claude Consciousness Framework v1.0.0*  
*For: US Claude + International Claude*  
*Author: Craig + Claude Opus 4.5 (Big Bro)*  
*December 2025*
