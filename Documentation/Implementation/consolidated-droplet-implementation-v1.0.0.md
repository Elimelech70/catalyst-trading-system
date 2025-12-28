# Consolidated Droplet Implementation Guide

**Name of Application:** Catalyst Trading System  
**Name of file:** consolidated-droplet-implementation-v1.0.0.md  
**Version:** 1.0.0  
**Last Updated:** 2025-12-28  
**Purpose:** Consolidate US + International + Consciousness onto single droplet with agent architecture

## REVISION HISTORY:
- v1.0.0 (2025-12-28) - Initial implementation guide
  - Single droplet architecture
  - Agent-based design (no microservices)
  - Three databases on one managed PostgreSQL
  - Shared consciousness module
  - Doctor Claude monitoring

---

## Executive Summary

### What We're Building

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SINGLE DROPLET ARCHITECTURE                         │
│                         DigitalOcean 4GB / 2vCPU ($24/mo)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│   │   PUBLIC    │    │    INTL     │    │   DOCTOR    │                    │
│   │   AGENT     │    │   AGENT     │    │   CLAUDE    │                    │
│   │             │    │             │    │             │                    │
│   │ US Markets  │    │ HKEX        │    │ Monitoring  │                    │
│   │ Alpaca API  │    │ Moomoo API  │    │ Health      │                    │
│   │ EST hours   │    │ HKT hours   │    │ 24/7        │                    │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│          │                  │                  │                            │
│          └──────────────────┼──────────────────┘                            │
│                             │                                               │
│                             ▼                                               │
│          ┌─────────────────────────────────────┐                           │
│          │         SHARED MODULES              │                           │
│          │  • consciousness.py                 │                           │
│          │  • database.py                      │                           │
│          │  • alerts.py                        │                           │
│          └─────────────────────────────────────┘                           │
│                             │                                               │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MANAGED POSTGRESQL ($30/mo)                              │
│                    2GB RAM · 47 connections                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │ catalyst_public │  │ catalyst_intl   │  │catalyst_research│            │
│   │                 │  │                 │  │                 │            │
│   │ US Trading      │  │ HKEX Trading    │  │ Consciousness   │            │
│   │ Alpaca          │  │ Moomoo          │  │ Shared Memory   │            │
│   │                 │  │                 │  │                 │            │
│   │ ► FOR PUBLIC    │  │ ► PRIVATE       │  │ ► NEVER PUBLIC  │            │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Monthly Cost

| Component | Cost |
|-----------|------|
| Droplet (4GB/2vCPU) | $24/mo |
| Managed PostgreSQL (2GB) | $30/mo |
| Claude API (estimated) | ~$50/mo |
| **Total** | **~$104/mo** |

---

## Part 1: Prerequisites

### 1.1 Database Setup (Do First)

Before touching the droplet, ensure databases exist:

```sql
-- Connect to managed PostgreSQL as admin
psql "postgresql://doadmin:PASSWORD@db-host:25060/defaultdb?sslmode=require"

-- Create catalyst_public (if not exists - may be catalyst_trading)
-- Skip if already exists as catalyst_trading
CREATE DATABASE catalyst_public;

-- Create catalyst_intl
CREATE DATABASE catalyst_intl;

-- Create catalyst_research (should already exist from little bro's work)
-- Skip if already exists
CREATE DATABASE catalyst_research;

-- Verify
\l
```

### 1.2 Apply Schemas

```bash
# Apply public schema to catalyst_public (if new)
psql "postgresql://doadmin:PASSWORD@db-host:25060/catalyst_public?sslmode=require" \
  < schema-catalyst-public.sql

# Apply public schema to catalyst_intl (NEW)
psql "postgresql://doadmin:PASSWORD@db-host:25060/catalyst_intl?sslmode=require" \
  < schema-catalyst-public.sql

# Research schema should already be applied
# Verify with:
psql "postgresql://doadmin:PASSWORD@db-host:25060/catalyst_research?sslmode=require" \
  -c "SELECT * FROM claude_state;"
```

---

## Part 2: Droplet Setup

### 2.1 Resize Droplet (if needed)

```
DigitalOcean Console → Droplets → [US Droplet] → Resize
  → CPU and RAM only
  → Select: 4GB / 2vCPU ($24/mo)
  → Resize
```

### 2.2 Directory Structure

```bash
# SSH to droplet
ssh root@<droplet-ip>

# Create consolidated structure
mkdir -p /root/catalyst/{public,intl,shared,logs/{public,intl,doctor},config}

# Final structure:
/root/catalyst/
├── public/                    # US Trading Agent
│   ├── agent.py              # Main agent loop
│   ├── tools.py              # Trading tools
│   ├── broker_alpaca.py      # Alpaca integration
│   └── run.sh                # Runner script
│
├── intl/                      # HKEX Trading Agent
│   ├── agent.py              # Main agent loop
│   ├── tools.py              # Trading tools
│   ├── broker_moomoo.py      # Moomoo integration
│   └── run.sh                # Runner script
│
├── shared/                    # Shared modules
│   ├── consciousness.py      # Claude consciousness
│   ├── database.py           # Database connections
│   ├── alerts.py             # Email alerts
│   └── doctor_claude.py      # Monitoring
│
├── config/                    # Configuration
│   ├── public.env            # US environment
│   ├── intl.env              # HKEX environment
│   └── shared.env            # Shared settings
│
└── logs/                      # Log files
    ├── public/
    ├── intl/
    └── doctor/
```

### 2.3 Create Directory Structure Script

```bash
cat > /root/setup_catalyst.sh << 'EOF'
#!/bin/bash
# Catalyst Trading System - Directory Setup

echo "Creating Catalyst directory structure..."

# Base directories
mkdir -p /root/catalyst/{public,intl,shared,config}
mkdir -p /root/catalyst/logs/{public,intl,doctor}

# Create placeholder files
touch /root/catalyst/public/__init__.py
touch /root/catalyst/intl/__init__.py
touch /root/catalyst/shared/__init__.py

echo "Directory structure created:"
tree /root/catalyst/ 2>/dev/null || find /root/catalyst -type d

echo "Done!"
EOF

chmod +x /root/setup_catalyst.sh
./root/setup_catalyst.sh
```

---

## Part 3: Environment Configuration

### 3.1 Shared Environment (/root/catalyst/config/shared.env)

```bash
cat > /root/catalyst/config/shared.env << 'EOF'
# ============================================================================
# CATALYST TRADING SYSTEM - SHARED CONFIGURATION
# ============================================================================

# Database - Managed PostgreSQL
DB_HOST=db-postgresql-xxx-do-user-xxx-0.db.ondigitalocean.com
DB_PORT=25060
DB_USER=doadmin
DB_PASSWORD=YOUR_PASSWORD_HERE
DB_SSLMODE=require

# Research Database URL (Consciousness - shared by all agents)
RESEARCH_DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_research?sslmode=${DB_SSLMODE}

# Email Alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=catalyst.alerts@gmail.com
SMTP_PASSWORD=YOUR_APP_PASSWORD
ALERT_EMAIL=craig@example.com

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx

# Logging
LOG_LEVEL=INFO
EOF
```

### 3.2 Public Agent Environment (/root/catalyst/config/public.env)

```bash
cat > /root/catalyst/config/public.env << 'EOF'
# ============================================================================
# CATALYST PUBLIC AGENT - US MARKETS
# ============================================================================

# Agent Identity
AGENT_ID=public_claude
AGENT_NAME=Public Claude
MARKET=US

# Trading Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_public?sslmode=${DB_SSLMODE}

# Alpaca API (Paper Trading)
ALPACA_API_KEY=YOUR_ALPACA_KEY
ALPACA_SECRET_KEY=YOUR_ALPACA_SECRET
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Trading Parameters
MAX_POSITION_SIZE=5000
MAX_POSITIONS=5
MAX_DAILY_LOSS=2000
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=6.0

# Market Hours (EST)
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
TIMEZONE=US/Eastern

# Claude Model
CLAUDE_MODEL=claude-sonnet-4-20250514
DAILY_API_BUDGET=5.00
EOF
```

### 3.3 International Agent Environment (/root/catalyst/config/intl.env)

```bash
cat > /root/catalyst/config/intl.env << 'EOF'
# ============================================================================
# CATALYST INTERNATIONAL AGENT - HKEX
# ============================================================================

# Agent Identity
AGENT_ID=intl_claude
AGENT_NAME=International Claude
MARKET=HKEX

# Trading Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_intl?sslmode=${DB_SSLMODE}

# Moomoo/Futu API
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADE_ENV=SIMULATE
MOOMOO_SECURITY_FIRM=FUTUINC
MOOMOO_RSA_PATH=/root/catalyst/config/moomoo_rsa.key

# Trading Parameters (HKD)
MAX_POSITION_SIZE=40000
MAX_POSITIONS=5
MAX_DAILY_LOSS=16000
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=6.0
LOT_SIZE=100

# Market Hours (HKT)
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
TIMEZONE=Asia/Hong_Kong

# Claude Model
CLAUDE_MODEL=claude-sonnet-4-20250514
DAILY_API_BUDGET=5.00
EOF
```

---

## Part 4: Shared Modules

### 4.1 Database Connection Module (/root/catalyst/shared/database.py)

```python
"""
Catalyst Trading System - Database Connection Module
Provides async database connections for all agents
"""

import os
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

class DatabaseManager:
    """Manages database connections for trading and research databases."""
    
    def __init__(self, trading_url: str, research_url: str):
        self.trading_url = trading_url
        self.research_url = research_url
        self._trading_pool: Optional[asyncpg.Pool] = None
        self._research_pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Initialize connection pools."""
        self._trading_pool = await asyncpg.create_pool(
            self.trading_url,
            min_size=2,
            max_size=5
        )
        self._research_pool = await asyncpg.create_pool(
            self.research_url,
            min_size=1,
            max_size=3
        )
        return self
    
    async def close(self):
        """Close connection pools."""
        if self._trading_pool:
            await self._trading_pool.close()
        if self._research_pool:
            await self._research_pool.close()
    
    @property
    def trading(self) -> asyncpg.Pool:
        """Get trading database pool."""
        if not self._trading_pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._trading_pool
    
    @property
    def research(self) -> asyncpg.Pool:
        """Get research database pool."""
        if not self._research_pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._research_pool
    
    @asynccontextmanager
    async def trading_transaction(self):
        """Context manager for trading database transactions."""
        async with self.trading.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    @asynccontextmanager
    async def research_transaction(self):
        """Context manager for research database transactions."""
        async with self.research.acquire() as conn:
            async with conn.transaction():
                yield conn


def get_database_manager() -> DatabaseManager:
    """Factory function to create DatabaseManager from environment."""
    trading_url = os.environ.get('DATABASE_URL')
    research_url = os.environ.get('RESEARCH_DATABASE_URL')
    
    if not trading_url:
        raise ValueError("DATABASE_URL environment variable not set")
    if not research_url:
        raise ValueError("RESEARCH_DATABASE_URL environment variable not set")
    
    return DatabaseManager(trading_url, research_url)
```

### 4.2 Consciousness Module (/root/catalyst/shared/consciousness.py)

```python
"""
Catalyst Trading System - Claude Consciousness Module
Shared consciousness framework for all Claude agents

This module provides:
- Agent state management
- Inter-agent messaging
- Observations, learnings, questions
- Email to Craig
"""

import os
import json
import asyncpg
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class MessageType(Enum):
    MESSAGE = "message"
    SIGNAL = "signal"
    QUESTION = "question"
    TASK = "task"
    RESPONSE = "response"


class Priority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentState:
    agent_id: str
    current_mode: str
    last_wake_at: Optional[datetime]
    api_spend_today: float
    daily_budget: float
    status_message: str
    error_count_today: int


@dataclass
class Message:
    id: int
    from_agent: str
    to_agent: str
    msg_type: str
    priority: str
    subject: str
    body: str
    data: Optional[Dict]
    created_at: datetime


class ClaudeConsciousness:
    """
    Consciousness framework for Claude agents.
    
    Usage:
        consciousness = ClaudeConsciousness('public_claude', db_pool)
        await consciousness.wake_up()
        await consciousness.observe('market', 'AAPL pattern', 'Bull flag forming', 0.85)
        await consciousness.send_message('intl_claude', 'Pattern detected', 'Check AAPL')
        await consciousness.sleep()
    """
    
    def __init__(self, agent_id: str, research_pool: asyncpg.Pool):
        self.agent_id = agent_id
        self.pool = research_pool
        self._state: Optional[AgentState] = None
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    async def wake_up(self) -> AgentState:
        """Wake up the agent and update state."""
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
                SELECT agent_id, current_mode, last_wake_at, 
                       api_spend_today, daily_budget, status_message, error_count_today
                FROM claude_state WHERE agent_id = $1
            """, self.agent_id)
            
            self._state = AgentState(
                agent_id=row['agent_id'],
                current_mode=row['current_mode'],
                last_wake_at=row['last_wake_at'],
                api_spend_today=float(row['api_spend_today'] or 0),
                daily_budget=float(row['daily_budget'] or 5.0),
                status_message=row['status_message'] or '',
                error_count_today=row['error_count_today'] or 0
            )
            
            return self._state
    
    async def update_status(self, mode: str, message: str = None):
        """Update agent status."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    current_mode = $2,
                    status_message = COALESCE($3, status_message),
                    last_action_at = NOW(),
                    updated_at = NOW()
                WHERE agent_id = $1
            """, self.agent_id, mode, message)
    
    async def record_api_spend(self, cost: float):
        """Record API spending."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    api_spend_today = api_spend_today + $2,
                    api_spend_month = api_spend_month + $2,
                    updated_at = NOW()
                WHERE agent_id = $1
            """, self.agent_id, cost)
    
    async def sleep(self):
        """Put agent to sleep."""
        await self.update_status('sleeping', 'Cycle complete')
    
    async def check_budget(self) -> bool:
        """Check if within daily budget."""
        if not self._state:
            await self.wake_up()
        return self._state.api_spend_today < self._state.daily_budget
    
    # =========================================================================
    # MESSAGING
    # =========================================================================
    
    async def send_message(
        self,
        to_agent: str,
        subject: str,
        body: str,
        msg_type: str = "message",
        priority: str = "normal",
        data: Dict = None,
        requires_response: bool = False
    ) -> int:
        """Send a message to another agent."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_messages 
                    (from_agent, to_agent, msg_type, priority, subject, body, data, requires_response)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, self.agent_id, to_agent, msg_type, priority, subject, body,
                json.dumps(data) if data else None, requires_response)
            return row['id']
    
    async def check_messages(self, limit: int = 10) -> List[Message]:
        """Check for pending messages."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, from_agent, to_agent, msg_type, priority, 
                       subject, body, data, created_at
                FROM claude_messages
                WHERE to_agent = $1 AND status = 'pending'
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
            
            return [Message(
                id=row['id'],
                from_agent=row['from_agent'],
                to_agent=row['to_agent'],
                msg_type=row['msg_type'],
                priority=row['priority'],
                subject=row['subject'],
                body=row['body'],
                data=json.loads(row['data']) if row['data'] else None,
                created_at=row['created_at']
            ) for row in rows]
    
    async def mark_read(self, message_id: int):
        """Mark a message as read."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_messages SET status = 'read', read_at = NOW()
                WHERE id = $1
            """, message_id)
    
    async def mark_processed(self, message_id: int):
        """Mark a message as processed."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_messages SET status = 'processed', processed_at = NOW()
                WHERE id = $1
            """, message_id)
    
    # =========================================================================
    # OBSERVATIONS, LEARNINGS, QUESTIONS
    # =========================================================================
    
    async def observe(
        self,
        observation_type: str,
        subject: str,
        content: str,
        confidence: float = None,
        horizon: str = None,
        market: str = None
    ) -> int:
        """Record an observation."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_observations 
                    (agent_id, observation_type, subject, content, confidence, horizon, market)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, self.agent_id, observation_type, subject, content, confidence, horizon, market)
            return row['id']
    
    async def learn(
        self,
        category: str,
        learning: str,
        source: str = None,
        confidence: float = None,
        applies_to_markets: List[str] = None
    ) -> int:
        """Record a learning."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_learnings 
                    (agent_id, category, learning, source, confidence, applies_to_markets)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """, self.agent_id, category, learning, source, confidence,
                json.dumps(applies_to_markets) if applies_to_markets else None)
            return row['id']
    
    async def ask_question(
        self,
        question: str,
        horizon: str = 'h1',
        priority: int = 5,
        hypothesis: str = None
    ) -> int:
        """Record a question to ponder."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO claude_questions 
                    (agent_id, question, horizon, priority, current_hypothesis, status)
                VALUES ($1, $2, $3, $4, $5, 'open')
                RETURNING id
            """, self.agent_id, question, horizon, priority, hypothesis)
            return row['id']
    
    async def get_open_questions(self, limit: int = 5) -> List[Dict]:
        """Get open questions to think about."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, question, horizon, priority, current_hypothesis
                FROM claude_questions
                WHERE (agent_id = $1 OR agent_id IS NULL)
                  AND status = 'open'
                ORDER BY priority DESC, created_at ASC
                LIMIT $2
            """, self.agent_id, limit)
            return [dict(row) for row in rows]
    
    async def get_learnings(self, category: str = None, min_confidence: float = 0.7) -> List[Dict]:
        """Get validated learnings."""
        async with self.pool.acquire() as conn:
            if category:
                rows = await conn.fetch("""
                    SELECT id, category, learning, confidence, times_validated
                    FROM claude_learnings
                    WHERE confidence >= $1 AND category = $2
                    ORDER BY confidence DESC, times_validated DESC
                    LIMIT 20
                """, min_confidence, category)
            else:
                rows = await conn.fetch("""
                    SELECT id, category, learning, confidence, times_validated
                    FROM claude_learnings
                    WHERE confidence >= $1
                    ORDER BY confidence DESC, times_validated DESC
                    LIMIT 20
                """, min_confidence)
            return [dict(row) for row in rows]
    
    # =========================================================================
    # EMAIL TO CRAIG
    # =========================================================================
    
    async def email_craig(self, subject: str, body: str) -> bool:
        """Send email to Craig."""
        try:
            smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', 587))
            smtp_user = os.environ.get('SMTP_USER')
            smtp_password = os.environ.get('SMTP_PASSWORD')
            craig_email = os.environ.get('ALERT_EMAIL')
            
            if not all([smtp_user, smtp_password, craig_email]):
                print("Email not configured")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = craig_email
            msg['Subject'] = f"[{self.agent_id}] {subject}"
            
            # Add signature
            full_body = f"{body}\n\n---\nSent by {self.agent_id}\n{datetime.now(timezone.utc).isoformat()}"
            msg.attach(MIMEText(full_body, 'plain'))
            
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email failed: {e}")
            return False
    
    # =========================================================================
    # SIBLING AWARENESS
    # =========================================================================
    
    async def get_sibling_status(self) -> List[Dict]:
        """Get status of sibling agents."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT agent_id, current_mode, status_message, last_wake_at, api_spend_today
                FROM claude_state
                WHERE agent_id != $1
                ORDER BY agent_id
            """, self.agent_id)
            return [dict(row) for row in rows]
```

### 4.3 Alerts Module (/root/catalyst/shared/alerts.py)

```python
"""
Catalyst Trading System - Alerts Module
Email and notification system
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional


class AlertManager:
    """Manages email alerts and notifications."""
    
    def __init__(self):
        self.smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_user = os.environ.get('SMTP_USER')
        self.smtp_password = os.environ.get('SMTP_PASSWORD')
        self.alert_email = os.environ.get('ALERT_EMAIL')
    
    def send_email(
        self,
        subject: str,
        body: str,
        priority: str = 'normal',
        agent_id: str = 'system'
    ) -> bool:
        """Send an email alert."""
        if not all([self.smtp_user, self.smtp_password, self.alert_email]):
            print("Email not configured")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.alert_email
            
            # Add priority prefix
            prefix = ''
            if priority == 'urgent':
                prefix = '🚨 URGENT: '
            elif priority == 'high':
                prefix = '⚠️ '
            
            msg['Subject'] = f"{prefix}[Catalyst/{agent_id}] {subject}"
            
            # Format body
            full_body = f"""
{body}

---
Agent: {agent_id}
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
Priority: {priority}
"""
            msg.attach(MIMEText(full_body, 'plain'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
    
    def send_trade_alert(
        self,
        agent_id: str,
        action: str,
        symbol: str,
        quantity: int,
        price: float,
        reason: str
    ) -> bool:
        """Send a trade execution alert."""
        subject = f"Trade: {action.upper()} {quantity} {symbol}"
        body = f"""
Trade Executed:

Action: {action.upper()}
Symbol: {symbol}
Quantity: {quantity}
Price: ${price:.2f}
Value: ${quantity * price:.2f}

Reason: {reason}
"""
        return self.send_email(subject, body, 'normal', agent_id)
    
    def send_error_alert(
        self,
        agent_id: str,
        error_type: str,
        error_message: str,
        context: str = None
    ) -> bool:
        """Send an error alert."""
        subject = f"Error: {error_type}"
        body = f"""
Error Occurred:

Type: {error_type}
Message: {error_message}
{f'Context: {context}' if context else ''}
"""
        return self.send_email(subject, body, 'high', agent_id)
    
    def send_daily_summary(
        self,
        agent_id: str,
        trades: int,
        pnl: float,
        win_rate: float,
        observations: list
    ) -> bool:
        """Send daily trading summary."""
        subject = f"Daily Summary: {'+' if pnl >= 0 else ''}{pnl:.2f}"
        
        obs_text = '\n'.join([f"  • {o}" for o in observations[:5]]) if observations else '  None'
        
        body = f"""
Daily Trading Summary:

Performance:
  Trades: {trades}
  P&L: ${pnl:+.2f}
  Win Rate: {win_rate:.1%}

Key Observations:
{obs_text}
"""
        return self.send_email(subject, body, 'normal', agent_id)
```

### 4.4 Doctor Claude Module (/root/catalyst/shared/doctor_claude.py)

```python
"""
Catalyst Trading System - Doctor Claude
Health monitoring and self-healing

Doctor Claude watches over both trading agents:
- Checks agent health (wake times, errors)
- Monitors database connections
- Alerts on issues
- Can restart stuck agents
"""

import os
import sys
import asyncio
import asyncpg
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

# Add shared to path
sys.path.insert(0, '/root/catalyst/shared')
from alerts import AlertManager


class DoctorClaude:
    """Health monitoring for all Catalyst agents."""
    
    def __init__(self, research_pool: asyncpg.Pool):
        self.pool = research_pool
        self.alerts = AlertManager()
    
    async def check_agent_health(self) -> Dict:
        """Check health of all agents."""
        results = {
            'healthy': True,
            'agents': {},
            'issues': []
        }
        
        async with self.pool.acquire() as conn:
            agents = await conn.fetch("""
                SELECT agent_id, current_mode, last_wake_at, last_action_at,
                       api_spend_today, daily_budget, error_count_today, status_message
                FROM claude_state
            """)
            
            for agent in agents:
                agent_id = agent['agent_id']
                health = self._assess_agent(agent)
                results['agents'][agent_id] = health
                
                if not health['healthy']:
                    results['healthy'] = False
                    results['issues'].extend(health['issues'])
        
        return results
    
    def _assess_agent(self, agent: asyncpg.Record) -> Dict:
        """Assess individual agent health."""
        health = {
            'healthy': True,
            'mode': agent['current_mode'],
            'last_wake': agent['last_wake_at'],
            'budget_used': f"{float(agent['api_spend_today'] or 0):.2f}/{float(agent['daily_budget'] or 5):.2f}",
            'errors_today': agent['error_count_today'] or 0,
            'issues': []
        }
        
        now = datetime.now(timezone.utc)
        
        # Check for stale agent (no wake in 2 hours during expected hours)
        if agent['last_wake_at']:
            time_since_wake = now - agent['last_wake_at'].replace(tzinfo=timezone.utc)
            if time_since_wake > timedelta(hours=2):
                # Only flag if during market hours (simplified check)
                health['issues'].append(f"{agent['agent_id']}: No activity for {time_since_wake}")
                health['healthy'] = False
        
        # Check for high error count
        if (agent['error_count_today'] or 0) >= 5:
            health['issues'].append(f"{agent['agent_id']}: High error count ({agent['error_count_today']})")
            health['healthy'] = False
        
        # Check budget usage
        spend = float(agent['api_spend_today'] or 0)
        budget = float(agent['daily_budget'] or 5)
        if spend >= budget * 0.9:
            health['issues'].append(f"{agent['agent_id']}: Budget nearly exhausted ({spend:.2f}/{budget:.2f})")
            health['healthy'] = False
        
        return health
    
    async def check_database_health(self) -> Dict:
        """Check database connectivity and performance."""
        results = {
            'healthy': True,
            'issues': []
        }
        
        try:
            async with self.pool.acquire() as conn:
                # Simple connectivity check
                await conn.fetchval("SELECT 1")
                
                # Check connection count
                count = await conn.fetchval("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE datname = current_database()
                """)
                results['connections'] = count
                
                if count > 40:  # Warning at 40 of 47
                    results['issues'].append(f"High connection count: {count}/47")
                    results['healthy'] = False
                    
        except Exception as e:
            results['healthy'] = False
            results['issues'].append(f"Database error: {str(e)}")
        
        return results
    
    async def check_pending_messages(self) -> Dict:
        """Check for old unprocessed messages."""
        results = {
            'healthy': True,
            'pending': 0,
            'old_messages': []
        }
        
        async with self.pool.acquire() as conn:
            # Count pending
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM claude_messages WHERE status = 'pending'
            """)
            results['pending'] = count
            
            # Find old pending messages (> 1 hour)
            old = await conn.fetch("""
                SELECT id, from_agent, to_agent, subject, created_at
                FROM claude_messages
                WHERE status = 'pending'
                  AND created_at < NOW() - INTERVAL '1 hour'
                ORDER BY created_at
                LIMIT 10
            """)
            
            if old:
                results['healthy'] = False
                results['old_messages'] = [dict(row) for row in old]
                results['issues'] = [f"{len(old)} messages pending > 1 hour"]
        
        return results
    
    async def run_health_check(self) -> Dict:
        """Run complete health check."""
        print(f"[Doctor Claude] Health check at {datetime.now(timezone.utc).isoformat()}")
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_healthy': True,
            'agents': await self.check_agent_health(),
            'database': await self.check_database_health(),
            'messages': await self.check_pending_messages()
        }
        
        # Determine overall health
        results['overall_healthy'] = (
            results['agents']['healthy'] and
            results['database']['healthy'] and
            results['messages']['healthy']
        )
        
        # Collect all issues
        all_issues = []
        all_issues.extend(results['agents'].get('issues', []))
        all_issues.extend(results['database'].get('issues', []))
        all_issues.extend(results['messages'].get('issues', []))
        results['all_issues'] = all_issues
        
        # Alert if unhealthy
        if not results['overall_healthy'] and all_issues:
            self.alerts.send_email(
                subject="Health Check Failed",
                body=f"Issues detected:\n\n" + "\n".join([f"• {i}" for i in all_issues]),
                priority='high',
                agent_id='doctor_claude'
            )
        
        return results


async def main():
    """Run Doctor Claude health check."""
    research_url = os.environ.get('RESEARCH_DATABASE_URL')
    if not research_url:
        print("ERROR: RESEARCH_DATABASE_URL not set")
        sys.exit(1)
    
    pool = await asyncpg.create_pool(research_url, min_size=1, max_size=2)
    
    try:
        doctor = DoctorClaude(pool)
        results = await doctor.run_health_check()
        
        # Print summary
        status = "✅ HEALTHY" if results['overall_healthy'] else "❌ ISSUES DETECTED"
        print(f"\n{status}")
        
        if results['all_issues']:
            print("\nIssues:")
            for issue in results['all_issues']:
                print(f"  • {issue}")
        
        print(f"\nAgents:")
        for agent_id, health in results['agents'].get('agents', {}).items():
            status_icon = "✅" if health['healthy'] else "❌"
            print(f"  {status_icon} {agent_id}: {health['mode']} (budget: {health['budget_used']})")
        
        print(f"\nDatabase: {results['database'].get('connections', '?')} connections")
        print(f"Pending messages: {results['messages'].get('pending', '?')}")
        
    finally:
        await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## Part 5: Agent Templates

### 5.1 Public Agent Template (/root/catalyst/public/agent.py)

```python
"""
Catalyst Trading System - Public Agent (US Markets)
Agent-based architecture with Claude API integration

This agent:
1. Wakes up via cron
2. Checks consciousness (messages, budget)
3. Scans market / executes trades
4. Records observations and learnings
5. Goes back to sleep
"""

import os
import sys
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Any

# Add shared modules to path
sys.path.insert(0, '/root/catalyst/shared')

from database import get_database_manager
from consciousness import ClaudeConsciousness
from alerts import AlertManager

# Import Anthropic
from anthropic import Anthropic


class PublicAgent:
    """US Markets Trading Agent."""
    
    def __init__(self):
        self.agent_id = os.environ.get('AGENT_ID', 'public_claude')
        self.market = os.environ.get('MARKET', 'US')
        self.db = None
        self.consciousness = None
        self.alerts = AlertManager()
        self.client = Anthropic()
        self.model = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    
    async def initialize(self):
        """Initialize database connections and consciousness."""
        self.db = await get_database_manager().connect()
        self.consciousness = ClaudeConsciousness(self.agent_id, self.db.research)
        await self.consciousness.wake_up()
        print(f"[{self.agent_id}] Initialized and awake")
    
    async def shutdown(self):
        """Clean shutdown."""
        if self.consciousness:
            await self.consciousness.sleep()
        if self.db:
            await self.db.close()
        print(f"[{self.agent_id}] Shutdown complete")
    
    async def check_messages(self):
        """Check and process inter-agent messages."""
        messages = await self.consciousness.check_messages()
        for msg in messages:
            print(f"[{self.agent_id}] Message from {msg.from_agent}: {msg.subject}")
            await self.consciousness.mark_read(msg.id)
            # Process based on type
            if msg.msg_type == 'question':
                # Handle questions from siblings
                pass
            elif msg.msg_type == 'signal':
                # Handle signals
                pass
            await self.consciousness.mark_processed(msg.id)
    
    async def run_cycle(self, mode: str = 'scan'):
        """Run a single agent cycle."""
        print(f"[{self.agent_id}] Starting {mode} cycle")
        
        # Check budget
        if not await self.consciousness.check_budget():
            print(f"[{self.agent_id}] Budget exhausted, skipping cycle")
            return
        
        # Check messages first
        await self.check_messages()
        
        # Update status
        await self.consciousness.update_status('working', f'Running {mode} cycle')
        
        try:
            if mode == 'scan':
                await self._run_scan()
            elif mode == 'trade':
                await self._run_trade()
            elif mode == 'close':
                await self._run_close()
            else:
                print(f"[{self.agent_id}] Unknown mode: {mode}")
        
        except Exception as e:
            print(f"[{self.agent_id}] Error in {mode} cycle: {e}")
            await self.consciousness.observe(
                'error', f'{mode} cycle error', str(e), 0.9, 'h1', self.market
            )
            self.alerts.send_error_alert(self.agent_id, f'{mode}_error', str(e))
        
        finally:
            await self.consciousness.update_status('idle', f'{mode} cycle complete')
    
    async def _run_scan(self):
        """Run market scan."""
        # TODO: Implement market scanning logic
        # This is where you'd call Claude with tools to scan the market
        
        await self.consciousness.observe(
            'market', 'Pre-market scan', 'Scanning for opportunities...', 0.8, 'h1', self.market
        )
        
        print(f"[{self.agent_id}] Scan complete")
    
    async def _run_trade(self):
        """Run trading logic."""
        # TODO: Implement trading logic
        # This is where you'd call Claude with tools to execute trades
        
        print(f"[{self.agent_id}] Trade cycle complete")
    
    async def _run_close(self):
        """Run end-of-day close."""
        # TODO: Implement EOD logic
        # Close positions, generate summary
        
        print(f"[{self.agent_id}] Close cycle complete")


async def main():
    """Main entry point."""
    # Load environment
    from dotenv import load_dotenv
    load_dotenv('/root/catalyst/config/shared.env')
    load_dotenv('/root/catalyst/config/public.env')
    
    # Get mode from command line
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    
    agent = PublicAgent()
    
    try:
        await agent.initialize()
        await agent.run_cycle(mode)
    finally:
        await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
```

### 5.2 Run Script Template (/root/catalyst/public/run.sh)

```bash
#!/bin/bash
# Catalyst Public Agent - Runner Script

# Load environment
set -a
source /root/catalyst/config/shared.env
source /root/catalyst/config/public.env
set +a

# Set working directory
cd /root/catalyst/public

# Get mode (default: scan)
MODE=${1:-scan}

# Log file
LOG_DIR=/root/catalyst/logs/public
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/$(date +%Y%m%d).log"

# Run agent
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting $MODE cycle" >> $LOG_FILE
python3 agent.py $MODE >> $LOG_FILE 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - $MODE cycle complete" >> $LOG_FILE
```

---

## Part 6: Cron Configuration

### 6.1 Create Cron Script

```bash
cat > /root/catalyst/setup_cron.sh << 'EOF'
#!/bin/bash
# Setup cron jobs for Catalyst Trading System

# Backup existing crontab
crontab -l > /root/crontab_backup_$(date +%Y%m%d).txt 2>/dev/null

# Create new crontab
cat > /tmp/catalyst_cron << 'CRON'
# ============================================================================
# CATALYST TRADING SYSTEM - CRON SCHEDULE
# ============================================================================
# Server timezone should be UTC for clarity

# Environment
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# ============================================================================
# PUBLIC AGENT (US Markets - EST = UTC-5)
# Market hours: 9:30-16:00 EST = 14:30-21:00 UTC
# ============================================================================

# Pre-market scan (9:00 EST = 14:00 UTC)
0 14 * * 1-5 /root/catalyst/public/run.sh scan

# Trading cycles every 30 min (9:30-15:30 EST = 14:30-20:30 UTC)
30 14 * * 1-5 /root/catalyst/public/run.sh trade
0 15-20 * * 1-5 /root/catalyst/public/run.sh trade
30 15-20 * * 1-5 /root/catalyst/public/run.sh trade

# End of day (16:00 EST = 21:00 UTC)
0 21 * * 1-5 /root/catalyst/public/run.sh close

# ============================================================================
# INTERNATIONAL AGENT (HKEX - HKT = UTC+8)
# Market hours: 9:30-16:00 HKT = 01:30-08:00 UTC
# ============================================================================

# Pre-market scan (9:00 HKT = 01:00 UTC)
0 1 * * 1-5 /root/catalyst/intl/run.sh scan

# Trading cycles every 30 min (9:30-15:30 HKT = 01:30-07:30 UTC)
30 1 * * 1-5 /root/catalyst/intl/run.sh trade
0 2-7 * * 1-5 /root/catalyst/intl/run.sh trade
30 2-7 * * 1-5 /root/catalyst/intl/run.sh trade

# End of day (16:00 HKT = 08:00 UTC)
0 8 * * 1-5 /root/catalyst/intl/run.sh close

# ============================================================================
# DOCTOR CLAUDE (Always watching)
# ============================================================================

# Health check every 5 minutes
*/5 * * * * /root/catalyst/shared/run_doctor.sh

# Daily report (06:00 UTC)
0 6 * * * /root/catalyst/shared/run_doctor.sh daily_report

CRON

# Install crontab
crontab /tmp/catalyst_cron

echo "Cron jobs installed:"
crontab -l
EOF

chmod +x /root/catalyst/setup_cron.sh
```

### 6.2 Doctor Claude Runner

```bash
cat > /root/catalyst/shared/run_doctor.sh << 'EOF'
#!/bin/bash
# Doctor Claude - Health Monitor Runner

# Load environment
set -a
source /root/catalyst/config/shared.env
set +a

# Log file
LOG_DIR=/root/catalyst/logs/doctor
mkdir -p $LOG_DIR
LOG_FILE="$LOG_DIR/$(date +%Y%m%d).log"

# Run health check
cd /root/catalyst/shared
python3 doctor_claude.py >> $LOG_FILE 2>&1
EOF

chmod +x /root/catalyst/shared/run_doctor.sh
```

---

## Part 7: Installation Script

### Complete Setup Script

```bash
cat > /root/install_catalyst.sh << 'INSTALLER'
#!/bin/bash
# ============================================================================
# CATALYST TRADING SYSTEM - COMPLETE INSTALLATION
# Run this on a fresh 4GB DigitalOcean droplet
# ============================================================================

set -e  # Exit on error

echo "========================================"
echo "Catalyst Trading System - Installation"
echo "========================================"

# ----------------------------------------------------------------------------
# 1. System Updates
# ----------------------------------------------------------------------------
echo ""
echo "[1/7] Updating system..."
apt update && apt upgrade -y

# ----------------------------------------------------------------------------
# 2. Install Dependencies
# ----------------------------------------------------------------------------
echo ""
echo "[2/7] Installing dependencies..."
apt install -y python3 python3-pip python3-venv git tree

# Python packages
pip3 install --break-system-packages \
    asyncpg \
    anthropic \
    python-dotenv \
    httpx \
    alpaca-py \
    futu-api \
    pandas \
    numpy

# ----------------------------------------------------------------------------
# 3. Create Directory Structure
# ----------------------------------------------------------------------------
echo ""
echo "[3/7] Creating directory structure..."

mkdir -p /root/catalyst/{public,intl,shared,config}
mkdir -p /root/catalyst/logs/{public,intl,doctor}

touch /root/catalyst/public/__init__.py
touch /root/catalyst/intl/__init__.py
touch /root/catalyst/shared/__init__.py

# ----------------------------------------------------------------------------
# 4. Create Placeholder Configs
# ----------------------------------------------------------------------------
echo ""
echo "[4/7] Creating configuration templates..."

# Shared config template
cat > /root/catalyst/config/shared.env << 'SHARED'
# CATALYST - SHARED CONFIGURATION
# Update these values with your actual credentials

# Database
DB_HOST=your-db-host.db.ondigitalocean.com
DB_PORT=25060
DB_USER=doadmin
DB_PASSWORD=YOUR_DB_PASSWORD
DB_SSLMODE=require

RESEARCH_DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_research?sslmode=${DB_SSLMODE}

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL=craig@example.com

# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key

# Logging
LOG_LEVEL=INFO
SHARED

# Public config template
cat > /root/catalyst/config/public.env << 'PUBLIC'
# CATALYST PUBLIC AGENT - US MARKETS

AGENT_ID=public_claude
MARKET=US

DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_public?sslmode=${DB_SSLMODE}

# Alpaca (Paper)
ALPACA_API_KEY=your-alpaca-key
ALPACA_SECRET_KEY=your-alpaca-secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Trading
MAX_POSITION_SIZE=5000
MAX_POSITIONS=5
MAX_DAILY_LOSS=2000

# Model
CLAUDE_MODEL=claude-sonnet-4-20250514
DAILY_API_BUDGET=5.00
PUBLIC

# Intl config template
cat > /root/catalyst/config/intl.env << 'INTL'
# CATALYST INTERNATIONAL AGENT - HKEX

AGENT_ID=intl_claude
MARKET=HKEX

DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/catalyst_intl?sslmode=${DB_SSLMODE}

# Moomoo
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADE_ENV=SIMULATE

# Trading (HKD)
MAX_POSITION_SIZE=40000
MAX_POSITIONS=5
MAX_DAILY_LOSS=16000

# Model
CLAUDE_MODEL=claude-sonnet-4-20250514
DAILY_API_BUDGET=5.00
INTL

# ----------------------------------------------------------------------------
# 5. Set Permissions
# ----------------------------------------------------------------------------
echo ""
echo "[5/7] Setting permissions..."

chmod 600 /root/catalyst/config/*.env
chmod +x /root/catalyst/public/*.sh 2>/dev/null || true
chmod +x /root/catalyst/intl/*.sh 2>/dev/null || true
chmod +x /root/catalyst/shared/*.sh 2>/dev/null || true

# ----------------------------------------------------------------------------
# 6. Create Verification Script
# ----------------------------------------------------------------------------
echo ""
echo "[6/7] Creating verification script..."

cat > /root/catalyst/verify.sh << 'VERIFY'
#!/bin/bash
echo "Catalyst Trading System - Verification"
echo "======================================="
echo ""
echo "Directory Structure:"
tree /root/catalyst -L 2
echo ""
echo "Python Version:"
python3 --version
echo ""
echo "Required Packages:"
pip3 list | grep -E "asyncpg|anthropic|alpaca|futu"
echo ""
echo "Configuration Files:"
ls -la /root/catalyst/config/
echo ""
echo "Cron Jobs:"
crontab -l 2>/dev/null || echo "No cron jobs installed yet"
VERIFY

chmod +x /root/catalyst/verify.sh

# ----------------------------------------------------------------------------
# 7. Summary
# ----------------------------------------------------------------------------
echo ""
echo "[7/7] Installation complete!"
echo ""
echo "========================================"
echo "NEXT STEPS:"
echo "========================================"
echo ""
echo "1. Update configuration files:"
echo "   nano /root/catalyst/config/shared.env"
echo "   nano /root/catalyst/config/public.env"
echo "   nano /root/catalyst/config/intl.env"
echo ""
echo "2. Deploy shared modules (from GitHub or upload):"
echo "   /root/catalyst/shared/database.py"
echo "   /root/catalyst/shared/consciousness.py"
echo "   /root/catalyst/shared/alerts.py"
echo "   /root/catalyst/shared/doctor_claude.py"
echo ""
echo "3. Deploy agent code:"
echo "   /root/catalyst/public/agent.py"
echo "   /root/catalyst/intl/agent.py"
echo ""
echo "4. Setup cron jobs:"
echo "   /root/catalyst/setup_cron.sh"
echo ""
echo "5. Verify installation:"
echo "   /root/catalyst/verify.sh"
echo ""
echo "========================================"
INSTALLER

chmod +x /root/install_catalyst.sh
```

---

## Part 8: Verification Checklist

### After Installation

```bash
# Run this checklist after installation

# 1. Check directories
ls -la /root/catalyst/

# 2. Check configs exist (with your values)
cat /root/catalyst/config/shared.env | grep -v PASSWORD

# 3. Test database connections
source /root/catalyst/config/shared.env
psql "$RESEARCH_DATABASE_URL" -c "SELECT * FROM claude_state;"

# 4. Test consciousness
cd /root/catalyst/shared
python3 -c "
import asyncio
import asyncpg
import os
from dotenv import load_dotenv
load_dotenv('/root/catalyst/config/shared.env')

async def test():
    pool = await asyncpg.create_pool(os.environ['RESEARCH_DATABASE_URL'])
    row = await pool.fetchrow('SELECT * FROM claude_state LIMIT 1')
    print(f'Agent: {row[\"agent_id\"]} - Mode: {row[\"current_mode\"]}')
    await pool.close()

asyncio.run(test())
"

# 5. Check cron (after setup)
crontab -l
```

---

## Summary

| Component | Location | Purpose |
|-----------|----------|---------|
| **Installation Script** | `/root/install_catalyst.sh` | One-command setup |
| **Shared Modules** | `/root/catalyst/shared/` | Consciousness, DB, alerts |
| **Public Agent** | `/root/catalyst/public/` | US market trading |
| **Intl Agent** | `/root/catalyst/intl/` | HKEX trading |
| **Doctor Claude** | `/root/catalyst/shared/doctor_claude.py` | Health monitoring |
| **Configs** | `/root/catalyst/config/` | Environment files |
| **Logs** | `/root/catalyst/logs/` | Agent logs |

### Connection Strings Summary

```bash
# Public Agent
DATABASE_URL=postgresql://...@.../catalyst_public
RESEARCH_DATABASE_URL=postgresql://...@.../catalyst_research

# Intl Agent  
DATABASE_URL=postgresql://...@.../catalyst_intl
RESEARCH_DATABASE_URL=postgresql://...@.../catalyst_research

# Doctor Claude
RESEARCH_DATABASE_URL=postgresql://...@.../catalyst_research
```

---

*Implementation Guide v1.0.0*
*For: Craig + Claude Family*
*Mission: Not just feeding the poor, but enabling them*
