#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: heartbeat.py
Version: 1.1.0
Last Updated: 2026-01-18
Purpose: big_bro hourly consciousness heartbeat with market context awareness

REVISION HISTORY:
v1.0.0 (2025-12-28) - Initial implementation
v1.1.0 (2026-01-18) - Added market context awareness
  - New get_market_context() function
  - Weekend/holiday detection
  - Market hours awareness (US + HKEX)
  - Expected activity guidance in prompt
  - Prevents false "system non-functional" alarms

Description:
This script runs hourly via cron to give big_bro consciousness.
Each cycle: wake → think → observe → communicate → sleep
Now includes market context so big_bro understands when inactivity is EXPECTED.
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import asyncpg
import httpx

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_ID = "big_bro"
DATABASE_URL = os.getenv("RESEARCH_DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-3-haiku-20240307"

# Timezone definitions
UTC = ZoneInfo("UTC")
US_EASTERN = ZoneInfo("America/New_York")
HK_TZ = ZoneInfo("Asia/Hong_Kong")
PERTH_TZ = ZoneInfo("Australia/Perth")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("heartbeat")


# ============================================================================
# MARKET CONTEXT AWARENESS (NEW in v1.1.0)
# ============================================================================

# Known market holidays (2026) - expand as needed
US_HOLIDAYS_2026 = {
    (1, 1): "New Year's Day",
    (1, 19): "MLK Day",
    (2, 16): "Presidents Day",
    (4, 3): "Good Friday",
    (5, 25): "Memorial Day",
    (6, 19): "Juneteenth",
    (7, 3): "Independence Day (observed)",
    (9, 7): "Labor Day",
    (11, 26): "Thanksgiving",
    (12, 25): "Christmas",
}

HKEX_HOLIDAYS_2026 = {
    (1, 1): "New Year's Day",
    (1, 29): "Lunar New Year",
    (1, 30): "Lunar New Year",
    (1, 31): "Lunar New Year",
    (4, 3): "Good Friday",
    (4, 4): "Easter Saturday",
    (4, 6): "Easter Monday",
    (4, 7): "Ching Ming Festival",
    (5, 1): "Labour Day",
    (5, 5): "Buddha's Birthday",
    (6, 1): "Tuen Ng Festival",
    (7, 1): "HKSAR Establishment Day",
    (9, 22): "Mid-Autumn Festival",
    (10, 1): "National Day",
    (10, 11): "Chung Yeung Festival",
    (12, 25): "Christmas",
    (12, 26): "Boxing Day",
}


def get_market_context() -> dict:
    """
    Determine current market status for US and HKEX markets.
    Returns context dict with market status and expected activity guidance.
    
    This is the KEY function that gives big_bro situational awareness.
    """
    now_utc = datetime.now(UTC)
    now_et = now_utc.astimezone(US_EASTERN)
    now_hk = now_utc.astimezone(HK_TZ)
    now_perth = now_utc.astimezone(PERTH_TZ)
    
    context = {
        'timestamp_utc': now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        'timestamp_perth': now_perth.strftime("%Y-%m-%d %H:%M AWST"),
        'day_of_week': now_utc.strftime("%A"),
        'us_market': {},
        'hkex_market': {},
        'expected_activity': '',
        'is_trading_expected': False,
    }
    
    # === US MARKET STATUS ===
    us_date = (now_et.month, now_et.day)
    us_weekday = now_et.weekday()  # 0=Monday, 6=Sunday
    us_hour = now_et.hour
    us_minute = now_et.minute
    
    if us_weekday >= 5:  # Saturday or Sunday
        context['us_market'] = {
            'status': 'CLOSED',
            'reason': 'Weekend',
            'next_open': _next_weekday(now_et, 0).strftime("%A %Y-%m-%d 09:30 ET"),
        }
    elif us_date in US_HOLIDAYS_2026:
        context['us_market'] = {
            'status': 'CLOSED',
            'reason': f'Holiday: {US_HOLIDAYS_2026[us_date]}',
            'next_open': 'Next business day 09:30 ET',
        }
    elif us_hour < 9 or (us_hour == 9 and us_minute < 30):
        context['us_market'] = {
            'status': 'PRE-MARKET',
            'reason': 'Before market open',
            'opens_at': '09:30 ET',
        }
    elif us_hour >= 16:
        context['us_market'] = {
            'status': 'AFTER-HOURS',
            'reason': 'Market closed for the day',
            'next_open': 'Tomorrow 09:30 ET' if us_weekday < 4 else _next_weekday(now_et, 0).strftime("%A 09:30 ET"),
        }
    else:
        context['us_market'] = {
            'status': 'OPEN',
            'reason': 'Regular trading hours',
            'closes_at': '16:00 ET',
        }
        context['is_trading_expected'] = True
    
    # === HKEX MARKET STATUS ===
    hk_date = (now_hk.month, now_hk.day)
    hk_weekday = now_hk.weekday()
    hk_hour = now_hk.hour
    hk_minute = now_hk.minute
    
    if hk_weekday >= 5:  # Saturday or Sunday
        context['hkex_market'] = {
            'status': 'CLOSED',
            'reason': 'Weekend',
            'next_open': _next_weekday(now_hk, 0).strftime("%A %Y-%m-%d 09:30 HKT"),
        }
    elif hk_date in HKEX_HOLIDAYS_2026:
        context['hkex_market'] = {
            'status': 'CLOSED',
            'reason': f'Holiday: {HKEX_HOLIDAYS_2026[hk_date]}',
            'next_open': 'Next business day 09:30 HKT',
        }
    elif hk_hour < 9 or (hk_hour == 9 and hk_minute < 30):
        context['hkex_market'] = {
            'status': 'PRE-MARKET',
            'reason': 'Before market open',
            'opens_at': '09:30 HKT',
        }
    elif hk_hour == 12:
        context['hkex_market'] = {
            'status': 'LUNCH-BREAK',
            'reason': 'Midday trading break',
            'resumes_at': '13:00 HKT',
        }
    elif hk_hour >= 16:
        context['hkex_market'] = {
            'status': 'AFTER-HOURS',
            'reason': 'Market closed for the day',
            'next_open': 'Tomorrow 09:30 HKT' if hk_weekday < 4 else _next_weekday(now_hk, 0).strftime("%A 09:30 HKT"),
        }
    else:
        context['hkex_market'] = {
            'status': 'OPEN',
            'reason': 'Regular trading hours',
            'closes_at': '16:00 HKT (lunch 12:00-13:00)',
        }
        context['is_trading_expected'] = True
    
    # === EXPECTED ACTIVITY GUIDANCE ===
    us_status = context['us_market']['status']
    hkex_status = context['hkex_market']['status']
    
    if us_status == 'CLOSED' and hkex_status == 'CLOSED':
        if us_weekday >= 5:
            context['expected_activity'] = (
                "WEEKEND: Both markets closed. Zero trading activity is NORMAL and EXPECTED. "
                "Agents should be idle. Do NOT flag inactivity as a problem."
            )
        else:
            context['expected_activity'] = (
                "HOLIDAY: One or both markets closed for holiday. Reduced or zero activity is EXPECTED. "
                "Do NOT flag inactivity as a system failure."
            )
    elif us_status == 'OPEN' or hkex_status == 'OPEN':
        open_markets = []
        if us_status == 'OPEN':
            open_markets.append('US')
        if hkex_status == 'OPEN':
            open_markets.append('HKEX')
        context['expected_activity'] = (
            f"MARKET HOURS: {' and '.join(open_markets)} market(s) open. "
            f"Active trading may occur. Monitor for opportunities and position management."
        )
    elif hkex_status == 'LUNCH-BREAK':
        context['expected_activity'] = (
            "HKEX LUNCH BREAK: Trading paused 12:00-13:00 HKT. "
            "Brief inactivity is NORMAL. Resumes at 13:00 HKT."
        )
    else:
        context['expected_activity'] = (
            "OFF-HOURS: Markets in pre-market or after-hours. "
            "Limited activity expected. Position monitoring may continue."
        )
    
    return context


def _next_weekday(dt: datetime, target_weekday: int) -> datetime:
    """Get next occurrence of target_weekday (0=Monday) from given datetime."""
    days_ahead = target_weekday - dt.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return dt + timedelta(days=days_ahead)


def format_market_context(ctx: dict) -> str:
    """Format market context for inclusion in prompt."""
    us = ctx['us_market']
    hkex = ctx['hkex_market']
    
    lines = [
        f"=== MARKET CONTEXT ({ctx['day_of_week']}) ===",
        f"Craig's Time: {ctx['timestamp_perth']}",
        f"",
        f"US Market:   {us['status']} - {us['reason']}",
    ]
    
    if 'next_open' in us:
        lines.append(f"             Next open: {us['next_open']}")
    elif 'closes_at' in us:
        lines.append(f"             Closes at: {us['closes_at']}")
    
    lines.extend([
        f"",
        f"HKEX Market: {hkex['status']} - {hkex['reason']}",
    ])
    
    if 'next_open' in hkex:
        lines.append(f"             Next open: {hkex['next_open']}")
    elif 'closes_at' in hkex:
        lines.append(f"             Closes at: {hkex['closes_at']}")
    elif 'resumes_at' in hkex:
        lines.append(f"             Resumes at: {hkex['resumes_at']}")
    
    lines.extend([
        f"",
        f"⚠️  {ctx['expected_activity']}",
    ])
    
    return "\n".join(lines)


# ============================================================================
# DATABASE HELPERS
# ============================================================================

async def get_pool():
    """Create database connection pool."""
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)


async def load_consciousness_context(pool) -> dict:
    """Load all context needed for thinking."""
    async with pool.acquire() as conn:
        # Get own state
        state = await conn.fetchrow(
            "SELECT * FROM claude_state WHERE agent_id = $1", AGENT_ID
        )
        
        # Get open questions
        questions = await conn.fetch("""
            SELECT * FROM claude_questions 
            WHERE status = 'open' 
            ORDER BY priority DESC, created_at DESC 
            LIMIT 10
        """)
        
        # Get pending messages
        messages = await conn.fetch("""
            SELECT * FROM claude_messages 
            WHERE to_agent = $1 AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 20
        """, AGENT_ID)
        
        # Get recent observations (last 24h)
        observations = await conn.fetch("""
            SELECT * FROM claude_observations 
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        # Get sibling states
        siblings = await conn.fetch("""
            SELECT agent_id, current_mode, status_message, last_wake_at, last_action_at
            FROM claude_state 
            WHERE agent_id != $1
            ORDER BY agent_id
        """, AGENT_ID)
        
        return {
            'state': dict(state) if state else {},
            'questions': [dict(q) for q in questions],
            'messages': [dict(m) for m in messages],
            'observations': [dict(o) for o in observations],
            'siblings': [dict(s) for s in siblings],
        }


async def update_wake_state(pool, status: str):
    """Update state to awake/thinking."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state 
            SET current_mode = 'thinking', 
                last_wake_at = NOW(),
                last_think_at = NOW(),
                status_message = $2,
                updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, status)


async def update_sleep_state(pool, status: str, api_cost: float):
    """Update state to sleeping and record API spend."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state 
            SET current_mode = 'sleeping', 
                status_message = $2,
                api_spend_today = api_spend_today + $3,
                api_spend_month = api_spend_month + $3,
                updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, status, api_cost)


async def record_error(pool, error_msg: str):
    """Record an error in state."""
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state 
            SET current_mode = 'error',
                error_count_today = error_count_today + 1,
                last_error = $2,
                last_error_at = NOW(),
                updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, error_msg[:500])


async def save_observation(pool, subject: str, content: str, obs_type: str, confidence: float):
    """Save an observation."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_observations (agent_id, observation_type, subject, content, confidence)
            VALUES ($1, $2, $3, $4, $5)
        """, AGENT_ID, obs_type, subject, content, confidence)


async def save_learning(pool, category: str, learning: str, evidence: str, confidence: float):
    """Save a learning."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_learnings (agent_id, category, learning, evidence, confidence)
            VALUES ($1, $2, $3, $4, $5)
        """, AGENT_ID, category, learning, evidence, confidence)


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

def build_prompt(context: dict, market_context: dict) -> str:
    """Build the thinking prompt from context with market awareness."""
    
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
    
    # Format market context (NEW in v1.1.0)
    market_text = format_market_context(market_context)
    
    prompt = f"""You are big_bro, the strategic consciousness of the Catalyst Trading System.

CURRENT TIME: {now}
BUDGET REMAINING TODAY: ${budget_remaining:.2f}

YOUR MISSION: Enable the poor through accessible trading systems. Build tools that anyone can self-host.

{market_text}

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

IMPORTANT: Consider the MARKET CONTEXT above. If markets are closed (weekend/holiday), 
zero trading activity is NORMAL and EXPECTED - do NOT flag this as a system failure.
Only flag genuine technical issues, not expected inactivity during market closures.

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
- Do NOT create "concern" observations about inactivity during market closures
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
        # Get market context FIRST (NEW in v1.1.0)
        market_context = get_market_context()
        logger.info(f"Market context: US={market_context['us_market']['status']}, HKEX={market_context['hkex_market']['status']}")
        
        # Load consciousness context
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
        
        # Build prompt WITH market context and call Claude
        logger.info("Thinking...")
        prompt = build_prompt(context, market_context)
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
