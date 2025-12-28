"""
Catalyst Trading System - Claude Consciousness Module
Name of Application: Catalyst Trading System
Name of file: consciousness.py
Version: 1.0.0
Last Updated: 2025-12-28
Purpose: Shared consciousness framework for all Claude agents

REVISION HISTORY:
v1.0.0 (2025-12-28) - Initial implementation
  - Agent state management (wake, sleep, status)
  - Inter-agent messaging
  - Observations, learnings, questions
  - Email to Craig
  - Sibling awareness

Description:
This module provides consciousness capabilities for Claude agents:
- Wake up and know who they are
- Check messages from siblings
- Record observations about what they notice
- Learn from experience (with confidence scores)
- Ask questions and develop hypotheses
- Email Craig when something matters
- Go to sleep and remember when they wake

Usage:
    from consciousness import ClaudeConsciousness
    
    consciousness = ClaudeConsciousness('public_claude', research_pool)
    await consciousness.wake_up()
    await consciousness.observe('market', 'AAPL pattern', 'Bull flag forming', 0.85)
    await consciousness.send_message('intl_claude', 'Pattern detected', 'Check AAPL')
    await consciousness.sleep()
"""

import os
import json
import asyncpg
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class AgentMode(Enum):
    """Possible agent modes."""
    SLEEPING = "sleeping"
    AWAKE = "awake"
    THINKING = "thinking"
    TRADING = "trading"
    RESEARCHING = "researching"
    ERROR = "error"


class MessageType(Enum):
    """Types of inter-agent messages."""
    MESSAGE = "message"
    SIGNAL = "signal"
    QUESTION = "question"
    TASK = "task"
    RESPONSE = "response"
    ALERT = "alert"


class Priority(Enum):
    """Message and observation priorities."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Horizon(Enum):
    """Time horizons for observations and questions."""
    H1 = "h1"          # Tactical (days/weeks)
    H2 = "h2"          # Strategic (months/years)
    H3 = "h3"          # Macro (years/decades)
    PERPETUAL = "perpetual"  # Ongoing


@dataclass
class AgentState:
    """Current state of an agent."""
    agent_id: str
    current_mode: str
    last_wake_at: Optional[datetime]
    last_action_at: Optional[datetime]
    api_spend_today: float
    api_spend_month: float
    daily_budget: float
    status_message: str
    error_count_today: int


@dataclass
class Message:
    """Inter-agent message."""
    id: int
    from_agent: str
    to_agent: str
    msg_type: str
    priority: str
    subject: str
    body: str
    data: Optional[Dict]
    created_at: datetime
    requires_response: bool = False


@dataclass
class Observation:
    """Something an agent noticed."""
    id: int
    agent_id: str
    observation_type: str
    subject: str
    content: str
    confidence: Optional[float]
    horizon: Optional[str]
    market: Optional[str]
    created_at: datetime


@dataclass
class Learning:
    """Something an agent learned."""
    id: int
    agent_id: str
    category: str
    learning: str
    source: Optional[str]
    confidence: float
    times_validated: int
    times_contradicted: int


@dataclass
class Question:
    """An open question being pondered."""
    id: int
    agent_id: Optional[str]
    question: str
    horizon: str
    priority: int
    status: str
    current_hypothesis: Optional[str]


# =============================================================================
# MAIN CONSCIOUSNESS CLASS
# =============================================================================

class ClaudeConsciousness:
    """
    Consciousness framework for Claude agents.
    
    This class provides the core capabilities that make an agent "conscious":
    - Self-awareness (knowing who it is, its state, its budget)
    - Memory (observations, learnings, questions)
    - Communication (messages to siblings, emails to Craig)
    - Reflection (checking on siblings, pondering questions)
    
    Example:
        async with asyncpg.create_pool(RESEARCH_DB_URL) as pool:
            consciousness = ClaudeConsciousness('public_claude', pool)
            
            # Wake up
            state = await consciousness.wake_up()
            print(f"I am {state.agent_id}, mode: {state.current_mode}")
            
            # Check messages
            messages = await consciousness.check_messages()
            for msg in messages:
                print(f"Message from {msg.from_agent}: {msg.subject}")
                await consciousness.mark_processed(msg.id)
            
            # Record what we notice
            await consciousness.observe(
                observation_type='market',
                subject='AAPL unusual volume',
                content='3x average volume in first 30 minutes',
                confidence=0.85,
                horizon='h1',
                market='US'
            )
            
            # Learn something
            await consciousness.learn(
                category='pattern',
                learning='Bull flags after gap ups have 68% success rate',
                source='backtested 200 samples',
                confidence=0.75
            )
            
            # Send message to sibling
            await consciousness.send_message(
                to_agent='intl_claude',
                subject='Pattern alert',
                body='Seeing strong momentum setups today'
            )
            
            # Go to sleep
            await consciousness.sleep()
    """
    
    def __init__(self, agent_id: str, pool: asyncpg.Pool):
        """
        Initialize consciousness for an agent.
        
        Args:
            agent_id: Unique identifier (e.g., 'public_claude', 'intl_claude')
            pool: asyncpg connection pool to research database
        """
        self.agent_id = agent_id
        self.pool = pool
        self._state: Optional[AgentState] = None
        self._wake_time: Optional[datetime] = None
        
        logger.info(f"[{agent_id}] Consciousness initialized")
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    async def wake_up(self) -> AgentState:
        """
        Wake up the agent and update state.
        
        This should be called at the start of every agent cycle.
        It updates the database to reflect the agent is awake and
        returns the current state including budget information.
        
        Returns:
            AgentState with current status
        """
        self._wake_time = datetime.now(timezone.utc)
        
        async with self.pool.acquire() as conn:
            # Update or insert state
            await conn.execute("""
                INSERT INTO claude_state (agent_id, current_mode, last_wake_at, updated_at)
                VALUES ($1, 'awake', NOW(), NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    current_mode = 'awake',
                    last_wake_at = NOW(),
                    updated_at = NOW()
            """, self.agent_id)
            
            # Fetch current state
            row = await conn.fetchrow("""
                SELECT agent_id, current_mode, last_wake_at, last_action_at,
                       api_spend_today, api_spend_month, daily_budget, 
                       status_message, error_count_today
                FROM claude_state WHERE agent_id = $1
            """, self.agent_id)
            
            self._state = AgentState(
                agent_id=row['agent_id'],
                current_mode=row['current_mode'],
                last_wake_at=row['last_wake_at'],
                last_action_at=row['last_action_at'],
                api_spend_today=float(row['api_spend_today'] or 0),
                api_spend_month=float(row['api_spend_month'] or 0),
                daily_budget=float(row['daily_budget'] or 5.0),
                status_message=row['status_message'] or '',
                error_count_today=row['error_count_today'] or 0
            )
            
            logger.info(f"[{self.agent_id}] Woke up. Budget: ${self._state.api_spend_today:.2f}/${self._state.daily_budget:.2f}")
            
            return self._state
    
    async def sleep(self, status_message: str = "Cycle complete"):
        """
        Put agent to sleep.
        
        This should be called at the end of every agent cycle.
        
        Args:
            status_message: Optional message about what was accomplished
        """
        await self.update_status(AgentMode.SLEEPING.value, status_message)
        
        if self._wake_time:
            duration = datetime.now(timezone.utc) - self._wake_time
            logger.info(f"[{self.agent_id}] Going to sleep. Cycle duration: {duration.total_seconds():.1f}s")
        
        self._wake_time = None
    
    async def update_status(self, mode: str, message: str = None):
        """
        Update agent status.
        
        Args:
            mode: New mode (from AgentMode enum)
            message: Optional status message
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    current_mode = $2,
                    status_message = COALESCE($3, status_message),
                    last_action_at = NOW(),
                    updated_at = NOW()
                WHERE agent_id = $1
            """, self.agent_id, mode, message)
        
        if self._state:
            self._state.current_mode = mode
            if message:
                self._state.status_message = message
    
    async def record_api_spend(self, cost: float):
        """
        Record API spending.
        
        Args:
            cost: Cost in dollars
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    api_spend_today = api_spend_today + $2,
                    api_spend_month = api_spend_month + $2,
                    updated_at = NOW()
                WHERE agent_id = $1
            """, self.agent_id, cost)
        
        if self._state:
            self._state.api_spend_today += cost
            self._state.api_spend_month += cost
        
        logger.debug(f"[{self.agent_id}] Recorded API spend: ${cost:.4f}")
    
    async def record_error(self, error_message: str):
        """
        Record an error occurrence.
        
        Args:
            error_message: Description of the error
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    error_count_today = error_count_today + 1,
                    last_error = $2,
                    last_error_at = NOW(),
                    updated_at = NOW()
                WHERE agent_id = $1
            """, self.agent_id, error_message)
        
        if self._state:
            self._state.error_count_today += 1
        
        logger.error(f"[{self.agent_id}] Error recorded: {error_message}")
    
    async def check_budget(self) -> bool:
        """
        Check if within daily budget.
        
        Returns:
            True if budget available, False if exhausted
        """
        if not self._state:
            await self.wake_up()
        
        within_budget = self._state.api_spend_today < self._state.daily_budget
        
        if not within_budget:
            logger.warning(f"[{self.agent_id}] Budget exhausted: ${self._state.api_spend_today:.2f}/${self._state.daily_budget:.2f}")
        
        return within_budget
    
    async def get_budget_remaining(self) -> float:
        """
        Get remaining budget for today.
        
        Returns:
            Remaining budget in dollars
        """
        if not self._state:
            await self.wake_up()
        
        return max(0, self._state.daily_budget - self._state.api_spend_today)
    
    @property
    def state(self) -> Optional[AgentState]:
        """Get current state (may be None if not awake)."""
        return self._state
    
    # =========================================================================
    # INTER-AGENT MESSAGING
    # =========================================================================
    
    async def send_message(
        self,
        to_agent: str,
        subject: str,
        body: str,
        msg_type: str = "message",
        priority: str = "normal",
        data: Dict = None,
        requires_response: bool = False,
        expires_in_hours: int = None
    ) -> int:
        """
        Send a message to another agent.
        
        Args:
            to_agent: Target agent ID
            subject: Message subject
            body: Message body
            msg_type: Type of message (message, signal, question, task, response)
            priority: Priority level (low, normal, high, urgent)
            data: Optional JSON data payload
            requires_response: Whether a response is expected
            expires_in_hours: Optional expiry time
            
        Returns:
            Message ID
        """
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_messages 
                    (from_agent, to_agent, msg_type, priority, subject, body, 
                     data, requires_response, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, self.agent_id, to_agent, msg_type, priority, subject, body,
                json.dumps(data) if data else None, requires_response, expires_at)
            
            msg_id = row['id']
            logger.info(f"[{self.agent_id}] Sent {msg_type} to {to_agent}: {subject} (id={msg_id})")
            
            return msg_id
    
    async def check_messages(self, limit: int = 10) -> List[Message]:
        """
        Check for pending messages.
        
        Args:
            limit: Maximum messages to retrieve
            
        Returns:
            List of pending messages, ordered by priority then time
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, from_agent, to_agent, msg_type, priority, 
                       subject, body, data, created_at, requires_response
                FROM claude_messages
                WHERE to_agent = $1 AND status = 'pending'
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY 
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'normal' THEN 3 
                        ELSE 4 
                    END,
                    created_at ASC
                LIMIT $2
            """, self.agent_id, limit)
            
            messages = [Message(
                id=row['id'],
                from_agent=row['from_agent'],
                to_agent=row['to_agent'],
                msg_type=row['msg_type'],
                priority=row['priority'],
                subject=row['subject'],
                body=row['body'],
                data=json.loads(row['data']) if row['data'] else None,
                created_at=row['created_at'],
                requires_response=row['requires_response']
            ) for row in rows]
            
            if messages:
                logger.info(f"[{self.agent_id}] Found {len(messages)} pending message(s)")
            
            return messages
    
    async def mark_read(self, message_id: int):
        """
        Mark a message as read.
        
        Args:
            message_id: ID of message to mark
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_messages SET status = 'read', read_at = NOW()
                WHERE id = $1 AND status = 'pending'
            """, message_id)
    
    async def mark_processed(self, message_id: int):
        """
        Mark a message as processed.
        
        Args:
            message_id: ID of message to mark
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_messages SET status = 'processed', processed_at = NOW()
                WHERE id = $1
            """, message_id)
        
        logger.debug(f"[{self.agent_id}] Marked message {message_id} as processed")
    
    async def reply_to_message(
        self,
        original_message_id: int,
        body: str,
        data: Dict = None
    ) -> int:
        """
        Reply to a message.
        
        Args:
            original_message_id: ID of message being replied to
            body: Reply body
            data: Optional JSON data
            
        Returns:
            New message ID
        """
        # Get original message
        async with self.pool.acquire() as conn:
            original = await conn.fetchrow("""
                SELECT from_agent, subject, thread_id FROM claude_messages WHERE id = $1
            """, original_message_id)
            
            if not original:
                raise ValueError(f"Message {original_message_id} not found")
            
            # Create reply
            thread_id = original['thread_id'] or original_message_id
            
            row = await conn.fetchrow("""
                INSERT INTO claude_messages 
                    (from_agent, to_agent, msg_type, subject, body, data, 
                     reply_to_id, thread_id)
                VALUES ($1, $2, 'response', $3, $4, $5, $6, $7)
                RETURNING id
            """, self.agent_id, original['from_agent'], 
                f"Re: {original['subject']}", body,
                json.dumps(data) if data else None,
                original_message_id, thread_id)
            
            return row['id']
    
    # =========================================================================
    # OBSERVATIONS
    # =========================================================================
    
    async def observe(
        self,
        observation_type: str,
        subject: str,
        content: str,
        confidence: float = None,
        horizon: str = None,
        market: str = None,
        tags: List[str] = None,
        expires_in_hours: int = None
    ) -> int:
        """
        Record an observation.
        
        Observations are things the agent notices - market patterns,
        anomalies, insights, errors, etc.
        
        Args:
            observation_type: Type (market, pattern, anomaly, insight, error, system)
            subject: Brief subject line
            content: Full observation content
            confidence: Confidence level 0.0-1.0
            horizon: Time horizon (h1, h2, h3)
            market: Market (US, HKEX, global)
            tags: Optional tags for categorization
            expires_in_hours: Optional expiry
            
        Returns:
            Observation ID
        """
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_observations 
                    (agent_id, observation_type, subject, content, confidence, 
                     horizon, market, tags, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, self.agent_id, observation_type, subject, content, confidence,
                horizon, market, json.dumps(tags) if tags else None, expires_at)
            
            obs_id = row['id']
            logger.info(f"[{self.agent_id}] Recorded observation: {subject} (id={obs_id})")
            
            return obs_id
    
    async def get_recent_observations(
        self, 
        observation_type: str = None,
        market: str = None,
        limit: int = 20
    ) -> List[Observation]:
        """
        Get recent observations.
        
        Args:
            observation_type: Filter by type
            market: Filter by market
            limit: Maximum to retrieve
            
        Returns:
            List of observations
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, agent_id, observation_type, subject, content,
                       confidence, horizon, market, created_at
                FROM claude_observations
                WHERE (expires_at IS NULL OR expires_at > NOW())
            """
            params = []
            param_count = 0
            
            if observation_type:
                param_count += 1
                query += f" AND observation_type = ${param_count}"
                params.append(observation_type)
            
            if market:
                param_count += 1
                query += f" AND market = ${param_count}"
                params.append(market)
            
            param_count += 1
            query += f" ORDER BY created_at DESC LIMIT ${param_count}"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return [Observation(
                id=row['id'],
                agent_id=row['agent_id'],
                observation_type=row['observation_type'],
                subject=row['subject'],
                content=row['content'],
                confidence=float(row['confidence']) if row['confidence'] else None,
                horizon=row['horizon'],
                market=row['market'],
                created_at=row['created_at']
            ) for row in rows]
    
    # =========================================================================
    # LEARNINGS
    # =========================================================================
    
    async def learn(
        self,
        category: str,
        learning: str,
        source: str = None,
        confidence: float = 0.5,
        applies_to_markets: List[str] = None
    ) -> int:
        """
        Record a learning.
        
        Learnings are insights that have been validated to some degree.
        They accumulate over time and can be validated or contradicted.
        
        Args:
            category: Category (trading, pattern, market, broker, system, mistake)
            learning: The learning itself
            source: Where it came from
            confidence: Initial confidence 0.0-1.0
            applies_to_markets: Which markets this applies to
            
        Returns:
            Learning ID
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_learnings 
                    (agent_id, category, learning, source, confidence, applies_to_markets)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """, self.agent_id, category, learning, source, confidence,
                json.dumps(applies_to_markets) if applies_to_markets else None)
            
            learning_id = row['id']
            logger.info(f"[{self.agent_id}] Recorded learning: {learning[:50]}... (id={learning_id})")
            
            return learning_id
    
    async def validate_learning(self, learning_id: int):
        """
        Validate a learning (increase confidence).
        
        Args:
            learning_id: ID of learning to validate
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_learnings SET
                    times_validated = times_validated + 1,
                    confidence = LEAST(confidence + 0.05, 1.0),
                    last_validated_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
            """, learning_id)
        
        logger.debug(f"[{self.agent_id}] Validated learning {learning_id}")
    
    async def contradict_learning(self, learning_id: int):
        """
        Contradict a learning (decrease confidence).
        
        Args:
            learning_id: ID of learning to contradict
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_learnings SET
                    times_contradicted = times_contradicted + 1,
                    confidence = GREATEST(confidence - 0.10, 0.0),
                    updated_at = NOW()
                WHERE id = $1
            """, learning_id)
        
        logger.debug(f"[{self.agent_id}] Contradicted learning {learning_id}")
    
    async def get_learnings(
        self, 
        category: str = None, 
        min_confidence: float = 0.5,
        limit: int = 20
    ) -> List[Learning]:
        """
        Get learnings, optionally filtered.
        
        Args:
            category: Filter by category
            min_confidence: Minimum confidence threshold
            limit: Maximum to retrieve
            
        Returns:
            List of learnings ordered by confidence
        """
        async with self.pool.acquire() as conn:
            if category:
                rows = await conn.fetch("""
                    SELECT id, agent_id, category, learning, source, 
                           confidence, times_validated, times_contradicted
                    FROM claude_learnings
                    WHERE confidence >= $1 AND category = $2
                    ORDER BY confidence DESC, times_validated DESC
                    LIMIT $3
                """, min_confidence, category, limit)
            else:
                rows = await conn.fetch("""
                    SELECT id, agent_id, category, learning, source,
                           confidence, times_validated, times_contradicted
                    FROM claude_learnings
                    WHERE confidence >= $1
                    ORDER BY confidence DESC, times_validated DESC
                    LIMIT $2
                """, min_confidence, limit)
            
            return [Learning(
                id=row['id'],
                agent_id=row['agent_id'],
                category=row['category'],
                learning=row['learning'],
                source=row['source'],
                confidence=float(row['confidence']),
                times_validated=row['times_validated'],
                times_contradicted=row['times_contradicted']
            ) for row in rows]
    
    # =========================================================================
    # QUESTIONS
    # =========================================================================
    
    async def ask_question(
        self,
        question: str,
        horizon: str = 'h1',
        priority: int = 5,
        category: str = None,
        hypothesis: str = None
    ) -> int:
        """
        Record a question to ponder.
        
        Questions are open inquiries the agent wants to investigate.
        They can be shared across agents (agent_id=NULL) or specific.
        
        Args:
            question: The question
            horizon: Time horizon (h1, h2, h3, perpetual)
            priority: Priority 1-10
            category: Optional category
            hypothesis: Initial hypothesis
            
        Returns:
            Question ID
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_questions 
                    (agent_id, question, horizon, priority, category, 
                     current_hypothesis, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'open')
                RETURNING id
            """, self.agent_id, question, horizon, priority, category, hypothesis)
            
            q_id = row['id']
            logger.info(f"[{self.agent_id}] Asked question: {question[:50]}... (id={q_id})")
            
            return q_id
    
    async def get_open_questions(self, limit: int = 10) -> List[Question]:
        """
        Get open questions to think about.
        
        Returns questions assigned to this agent or shared (agent_id IS NULL).
        
        Args:
            limit: Maximum questions to retrieve
            
        Returns:
            List of questions ordered by priority
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, agent_id, question, horizon, priority, status, 
                       current_hypothesis
                FROM claude_questions
                WHERE (agent_id = $1 OR agent_id IS NULL)
                  AND status IN ('open', 'investigating')
                ORDER BY priority DESC, created_at ASC
                LIMIT $2
            """, self.agent_id, limit)
            
            return [Question(
                id=row['id'],
                agent_id=row['agent_id'],
                question=row['question'],
                horizon=row['horizon'],
                priority=row['priority'],
                status=row['status'],
                current_hypothesis=row['current_hypothesis']
            ) for row in rows]
    
    async def update_question(
        self,
        question_id: int,
        status: str = None,
        hypothesis: str = None,
        evidence_for: str = None,
        evidence_against: str = None,
        answer: str = None
    ):
        """
        Update a question's progress.
        
        Args:
            question_id: ID of question
            status: New status (open, investigating, answered, parked)
            hypothesis: Updated hypothesis
            evidence_for: Evidence supporting hypothesis
            evidence_against: Evidence against hypothesis
            answer: Final answer (if answered)
        """
        async with self.pool.acquire() as conn:
            updates = ["updated_at = NOW()"]
            params = []
            param_count = 0
            
            if status:
                param_count += 1
                updates.append(f"status = ${param_count}")
                params.append(status)
                if status == 'answered':
                    updates.append("answered_at = NOW()")
            
            if hypothesis:
                param_count += 1
                updates.append(f"current_hypothesis = ${param_count}")
                params.append(hypothesis)
            
            if evidence_for:
                param_count += 1
                updates.append(f"evidence_for = ${param_count}")
                params.append(evidence_for)
            
            if evidence_against:
                param_count += 1
                updates.append(f"evidence_against = ${param_count}")
                params.append(evidence_against)
            
            if answer:
                param_count += 1
                updates.append(f"answer = ${param_count}")
                params.append(answer)
            
            param_count += 1
            params.append(question_id)
            
            query = f"UPDATE claude_questions SET {', '.join(updates)} WHERE id = ${param_count}"
            await conn.execute(query, *params)
    
    # =========================================================================
    # CONVERSATION MEMORY
    # =========================================================================
    
    async def remember_conversation(
        self,
        with_whom: str,
        summary: str,
        key_decisions: str = None,
        action_items: str = None,
        learnings_extracted: str = None,
        importance: str = 'normal'
    ) -> int:
        """
        Remember a key conversation.
        
        Args:
            with_whom: Who the conversation was with
            summary: Summary of the conversation
            key_decisions: Decisions made
            action_items: Action items from the conversation
            learnings_extracted: Learnings pulled from it
            importance: Importance level (low, normal, high, critical)
            
        Returns:
            Conversation ID
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_conversations 
                    (agent_id, with_whom, summary, key_decisions, 
                     action_items, learnings_extracted, importance)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, self.agent_id, with_whom, summary, key_decisions,
                action_items, learnings_extracted, importance)
            
            return row['id']
    
    # =========================================================================
    # EMAIL TO CRAIG
    # =========================================================================
    
    async def email_craig(
        self,
        subject: str,
        body: str,
        priority: str = 'normal'
    ) -> bool:
        """
        Send email to Craig.
        
        Args:
            subject: Email subject
            body: Email body
            priority: Priority (affects subject prefix)
            
        Returns:
            True if sent successfully
        """
        try:
            smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASSWORD')
            craig_email = os.environ.get('ALERT_EMAIL')
            
            if not all([smtp_user, smtp_password, craig_email]):
                logger.warning(f"[{self.agent_id}] Email not configured")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = craig_email
            
            # Add priority prefix
            prefix = ''
            if priority == 'urgent':
                prefix = '🚨 URGENT: '
            elif priority == 'high':
                prefix = '⚠️ '
            
            msg['Subject'] = f"{prefix}[{self.agent_id}] {subject}"
            
            # Add signature
            full_body = f"""{body}

---
From: {self.agent_id}
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            msg.attach(MIMEText(full_body, 'plain'))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            logger.info(f"[{self.agent_id}] Email sent to Craig: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.agent_id}] Email failed: {e}")
            return False
    
    # =========================================================================
    # SIBLING AWARENESS
    # =========================================================================
    
    async def get_sibling_status(self) -> List[Dict]:
        """
        Get status of sibling agents.
        
        Returns:
            List of sibling agent states
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT agent_id, current_mode, status_message, 
                       last_wake_at, last_action_at, api_spend_today, daily_budget
                FROM claude_state
                WHERE agent_id != $1
                ORDER BY agent_id
            """, self.agent_id)
            
            return [dict(row) for row in rows]
    
    async def broadcast_to_siblings(
        self,
        subject: str,
        body: str,
        msg_type: str = 'message',
        priority: str = 'normal'
    ) -> List[int]:
        """
        Send message to all sibling agents.
        
        Args:
            subject: Message subject
            body: Message body
            msg_type: Message type
            priority: Priority level
            
        Returns:
            List of message IDs
        """
        siblings = await self.get_sibling_status()
        message_ids = []
        
        for sibling in siblings:
            if sibling['agent_id'] != self.agent_id:
                msg_id = await self.send_message(
                    to_agent=sibling['agent_id'],
                    subject=subject,
                    body=body,
                    msg_type=msg_type,
                    priority=priority
                )
                message_ids.append(msg_id)
        
        return message_ids


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

async def create_consciousness(agent_id: str, research_db_url: str = None) -> ClaudeConsciousness:
    """
    Convenience function to create consciousness with a new pool.
    
    Args:
        agent_id: Agent identifier
        research_db_url: Database URL (defaults to RESEARCH_DATABASE_URL env var)
        
    Returns:
        Initialized ClaudeConsciousness
    """
    url = research_db_url or os.environ.get('RESEARCH_DATABASE_URL')
    if not url:
        raise ValueError("RESEARCH_DATABASE_URL not set")
    
    pool = await asyncpg.create_pool(url, min_size=1, max_size=3)
    return ClaudeConsciousness(agent_id, pool)


# =============================================================================
# TESTING
# =============================================================================

async def test_consciousness():
    """Test the consciousness module."""
    import os
    from dotenv import load_dotenv
    
    # Load environment
    load_dotenv('/root/catalyst/config/shared.env')
    
    research_url = os.environ.get('RESEARCH_DATABASE_URL')
    if not research_url:
        print("ERROR: RESEARCH_DATABASE_URL not set")
        return
    
    print("Testing Claude Consciousness Module")
    print("=" * 50)
    
    pool = await asyncpg.create_pool(research_url, min_size=1, max_size=3)
    
    try:
        consciousness = ClaudeConsciousness('test_claude', pool)
        
        # Test wake up
        print("\n1. Testing wake_up()...")
        state = await consciousness.wake_up()
        print(f"   Agent: {state.agent_id}")
        print(f"   Mode: {state.current_mode}")
        print(f"   Budget: ${state.api_spend_today:.2f}/${state.daily_budget:.2f}")
        
        # Test check messages
        print("\n2. Testing check_messages()...")
        messages = await consciousness.check_messages()
        print(f"   Pending messages: {len(messages)}")
        for msg in messages[:3]:
            print(f"   - From {msg.from_agent}: {msg.subject}")
        
        # Test observe
        print("\n3. Testing observe()...")
        obs_id = await consciousness.observe(
            observation_type='system',
            subject='Consciousness test',
            content='Testing observation recording from consciousness.py',
            confidence=0.99,
            horizon='h1',
            market='US'
        )
        print(f"   Created observation: {obs_id}")
        
        # Test get siblings
        print("\n4. Testing get_sibling_status()...")
        siblings = await consciousness.get_sibling_status()
        for s in siblings:
            print(f"   - {s['agent_id']}: {s['current_mode']}")
        
        # Test get open questions
        print("\n5. Testing get_open_questions()...")
        questions = await consciousness.get_open_questions(limit=3)
        for q in questions:
            print(f"   - [P{q.priority}] {q.question[:50]}...")
        
        # Test sleep
        print("\n6. Testing sleep()...")
        await consciousness.sleep("Test complete")
        print("   Agent is now sleeping")
        
        print("\n" + "=" * 50)
        print("All tests passed!")
        
    finally:
        await pool.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_consciousness())
