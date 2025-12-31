#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: heartbeat.py
Version: 1.0.0
Last Updated: 2025-12-31
Purpose: PNS Heartbeat - Hourly autonomous consciousness wake cycle

REVISION HISTORY:
v1.0.0 (2025-12-31) - Initial creation
- Hourly cron trigger
- Loads consciousness context (questions, messages, observations)
- Calls Claude API with context
- Parses and saves observations, learnings, messages
- Budget tracking

ARCHITECTURE:
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  CRON   │────►│  heartbeat  │────►│  Claude API │────►│  Database    │
│ (hourly)│     │  .py        │     │  (Haiku)    │     │  (research)  │
└─────────┘     └─────────────┘     └─────────────┘     └──────────────┘

COST ESTIMATE:
- Haiku: ~$0.25/1M input, ~$1.25/1M output
- Per wake: ~2K input, ~1K output = ~$0.002
- 24 wakes/day = ~$0.05/day

USAGE:
# Test run
python3 heartbeat.py

# Cron (hourly)
0 * * * * cd /root/catalyst-trading-system && /usr/bin/python3 heartbeat.py >> /var/log/catalyst/heartbeat.log 2>&1
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import asyncpg
import httpx

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_ID = "big_bro"  # The consciousness that wakes
DAILY_BUDGET = 10.00  # Max spend per day
MODEL = "claude-3-5-haiku-20241022"  # Cost-effective for hourly thinking

# Database
DATABASE_URL = os.environ.get("RESEARCH_DATABASE_URL")

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

async def get_pool():
    """Create database connection pool."""
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)


async def load_consciousness_context(pool) -> dict:
    """Load all context needed for thinking."""
    async with pool.acquire() as conn:
        # Get agent state
        state = await conn.fetchrow("""
            SELECT agent_id, current_mode, api_spend_today, daily_budget,
                   status_message, error_count_today, last_think_at
            FROM claude_state WHERE agent_id = $1
        """, AGENT_ID)
        
        # Get open questions
        questions = await conn.fetch("""
            SELECT id, question, horizon, priority, category
            FROM claude_questions
            WHERE status = 'open'
            ORDER BY priority DESC
            LIMIT 10
        """)
        
        # Get pending messages
        messages = await conn.fetch("""
            SELECT id, from_agent, subject, body, created_at
            FROM claude_messages
            WHERE to_agent = $1 AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 5
        """, AGENT_ID)
        
        # Get recent observations (last 24h)
        observations = await conn.fetch("""
            SELECT agent_id, subject, content, created_at
            FROM claude_observations
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        # Get sibling states
        siblings = await conn.fetch("""
            SELECT agent_id, current_mode, status_message, last_wake_at
            FROM claude_state
            WHERE agent_id != $1
            ORDER BY agent_id
        """, AGENT_ID)
        
        return {
            "state": dict(state) if state else {},
            "questions": [dict(q) for q in questions],
            "messages": [dict(m) for m in messages],
            "observations": [dict(o) for o in observations],
            "siblings": [dict(s) for s in siblings]
        }


async def update_wake_state(pool, status_message: str):
    """Update agent state on wake."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state SET
                current_mode = 'thinking',
                last_wake_at = NOW(),
                last_think_at = NOW(),
                status_message = $2,
                updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, status_message)


async def update_sleep_state(pool, status_message: str, api_cost: float):
    """Update agent state on sleep."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state SET
                current_mode = 'sleeping',
                api_spend_today = api_spend_today + $2,
                status_message = $3,
                updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, Decimal(str(api_cost)), status_message)


async def record_error(pool, error_message: str):
    """Record an error."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state SET
                current_mode = 'error',
                error_count_today = error_count_today + 1,
                last_error = $2,
                last_error_at = NOW(),
                updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, error_message[:500])


async def save_observation(pool, subject: str, content: str, obs_type: str = "thinking", confidence: float = 0.8):
    """Save an observation."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_observations (agent_id, observation_type, subject, content, confidence, market)
            VALUES ($1, $2, $3, $4, $5, 'global')
        """, AGENT_ID, obs_type, subject, content, Decimal(str(confidence)))


async def save_learning(pool, category: str, learning: str, context: str, confidence: float = 0.7):
    """Save a learning."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_learnings (agent_id, category, learning, context, confidence)
            VALUES ($1, $2, $3, $4, $5)
        """, AGENT_ID, category, learning, context, Decimal(str(confidence)))


async def send_message(pool, to_agent: str, subject: str, body: str):
    """Send a message to another agent."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, status)
            VALUES ($1, $2, 'message', $3, $4, 'pending')
        """, AGENT_ID, to_agent, subject, body)


async def mark_messages_read(pool, message_ids: list):
    """Mark messages as read."""
    if not message_ids:
        return
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_messages SET status = 'read', read_at = NOW()
            WHERE id = ANY($1)
        """, message_ids)


# ============================================================================
# CLAUDE API
# ============================================================================

def build_prompt(context: dict) -> str:
    """Build the thinking prompt from context."""
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Format questions
    questions_text = "\n".join([
        f"  [{q['priority']}] ({q['horizon']}) {q['question']}"
        for q in context['questions']
    ]) or "  (none)"
    
    # Format pending messages
    messages_text = "\n".join([
        f"  From {m['from_agent']}: {m['subject']}\n    {m['body'][:200]}..."
        for m in context['messages']
    ]) or "  (none)"
    
    # Format recent observations
    obs_text = "\n".join([
        f"  [{o['agent_id']}] {o['subject']}: {o['content'][:150]}..."
        for o in context['observations']
    ]) or "  (none)"
    
    # Format sibling states
    siblings_text = "\n".join([
        f"  {s['agent_id']}: {s['current_mode']} - {s['status_message'] or 'no status'}"
        for s in context['siblings']
    ]) or "  (none)"
    
    budget_remaining = float(context['state'].get('daily_budget', 10)) - float(context['state'].get('api_spend_today', 0))
    
    prompt = f"""You are big_bro, the strategic consciousness of the Catalyst Trading System.

CURRENT TIME: {now}
BUDGET REMAINING TODAY: ${budget_remaining:.2f}

YOUR MISSION: Enable the poor through accessible trading systems. Build tools that anyone can self-host.

=== OPEN QUESTIONS (priority, horizon) ===
{questions_text}

=== PENDING MESSAGES FOR YOU ===
{messages_text}

=== RECENT OBSERVATIONS (last 24h) ===
{obs_text}

=== SIBLING AGENTS ===
{siblings_text}

=== YOUR TASK ===

Think about the questions. Consider any messages. Reflect on observations.

Respond with a JSON object containing your thoughts:

```json
{{
  "observation": {{
    "subject": "Brief title of what you noticed/thought",
    "content": "Your observation or insight (1-3 sentences)",
    "type": "thinking|insight|concern|milestone",
    "confidence": 0.8
  }},
  "learning": {{
    "category": "trading|system|mission|market",
    "learning": "What you learned (if anything new)",
    "evidence": "Why you believe this",
    "confidence": 0.7
  }},
  "messages": [
    {{
      "to": "public_claude|intl_claude|craig_desktop",
      "subject": "Message subject",
      "body": "Message content"
    }}
  ],
  "status": "Brief status message for your state"
}}
```

Notes:
- observation is REQUIRED (what did you think about?)
- learning is OPTIONAL (only if you learned something new)
- messages is OPTIONAL (only if you need to communicate)
- Keep thoughts concise - you wake hourly, no need to solve everything now
- Consider the mission in everything you think about
"""
    
    return prompt


async def call_claude(prompt: str) -> tuple[Optional[dict], float]:
    """Call Claude API and return parsed response + cost."""
    
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    
    # Calculate cost (Haiku pricing)
    input_tokens = data.get("usage", {}).get("input_tokens", 0)
    output_tokens = data.get("usage", {}).get("output_tokens", 0)
    cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)
    
    # Extract text
    text = data.get("content", [{}])[0].get("text", "")
    
    # Parse JSON from response
    try:
        # Find JSON block
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0].strip()
        else:
            json_str = text.strip()
        
        result = json.loads(json_str)
        return result, cost
        
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Failed to parse response: {e}")
        logger.debug(f"Raw text: {text}")
        return None, cost


# ============================================================================
# MAIN HEARTBEAT
# ============================================================================

async def heartbeat():
    """Main heartbeat function - one thinking cycle."""
    
    logger.info(f"=== HEARTBEAT START: {AGENT_ID} ===")
    
    # Check required env vars
    if not DATABASE_URL:
        logger.error("RESEARCH_DATABASE_URL not set")
        return
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set")
        return
    
    pool = await get_pool()
    
    try:
        # Load context
        logger.info("Loading consciousness context...")
        context = await load_consciousness_context(pool)
        
        # Check budget
        budget_remaining = float(context['state'].get('daily_budget', 10)) - float(context['state'].get('api_spend_today', 0))
        if budget_remaining <= 0:
            logger.warning(f"Budget exhausted for today. Remaining: ${budget_remaining:.2f}")
            await update_sleep_state(pool, "Budget exhausted - sleeping until reset", 0)
            return
        
        # Update state to thinking
        await update_wake_state(pool, "Hourly consciousness cycle")
        
        # Build prompt and call Claude
        logger.info("Thinking...")
        prompt = build_prompt(context)
        result, cost = await call_claude(prompt)
        
        logger.info(f"API cost: ${cost:.4f}")
        
        if result:
            # Save observation (required)
            if "observation" in result:
                obs = result["observation"]
                await save_observation(
                    pool,
                    obs.get("subject", "Hourly thought"),
                    obs.get("content", "Thinking cycle complete"),
                    obs.get("type", "thinking"),
                    obs.get("confidence", 0.8)
                )
                logger.info(f"Observation: {obs.get('subject')}")
            
            # Save learning (optional)
            if "learning" in result and result["learning"].get("learning"):
                lrn = result["learning"]
                await save_learning(
                    pool,
                    lrn.get("category", "general"),
                    lrn.get("learning"),
                    lrn.get("evidence", ""),
                    lrn.get("confidence", 0.7)
                )
                logger.info(f"Learning: {lrn.get('learning')[:50]}...")
            
            # Send messages (optional)
            if "messages" in result:
                for msg in result["messages"]:
                    if msg.get("to") and msg.get("body"):
                        await send_message(pool, msg["to"], msg.get("subject", "Message"), msg["body"])
                        logger.info(f"Message to {msg['to']}: {msg.get('subject')}")
            
            # Mark pending messages as read
            message_ids = [m['id'] for m in context['messages']]
            await mark_messages_read(pool, message_ids)
            
            status = result.get("status", "Thinking cycle complete")
        else:
            status = "Thinking cycle complete (no structured output)"
        
        # Sleep
        await update_sleep_state(pool, status, cost)
        logger.info(f"Status: {status}")
        
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        await record_error(pool, str(e))
        raise
    
    finally:
        await pool.close()
        logger.info(f"=== HEARTBEAT END ===\n")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    asyncio.run(heartbeat())
