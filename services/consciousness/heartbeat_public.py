#!/usr/bin/env python3
"""
Catalyst Trading System - Public Claude Heartbeat with Task Execution
Name of file: heartbeat_public_v2.py
Version: 2.0.0
Last Updated: 2025-12-31
Purpose: Autonomous heartbeat with task execution capability

CHANGES from v1:
- Added task message processing
- Integrated TaskExecutor for safe command execution
- Reports task results back to big_bro
"""

import asyncio
import asyncpg
import os
import json
from datetime import datetime
from anthropic import Anthropic
from task_executor import TaskExecutor, parse_task_message, WHITELIST

# ============================================================================
# CONFIGURATION
# ============================================================================

AGENT_ID = "public_claude"
DATABASE_URL = os.environ.get("RESEARCH_DATABASE_URL")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DAILY_BUDGET = 5.00
MODEL = "claude-3-5-haiku-20241022"

# ============================================================================
# DATABASE HELPERS
# ============================================================================

async def get_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)

async def get_state(pool) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM claude_state WHERE agent_id = $1", AGENT_ID
        )
        return dict(row) if row else {}

async def update_state(pool, mode: str, status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state 
            SET current_mode = $2, status_message = $3, last_wake_at = NOW(), updated_at = NOW()
            WHERE agent_id = $1
        """, AGENT_ID, mode, status)

async def record_spend(pool, cost: float):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_state 
            SET api_spend_today = api_spend_today + $2
            WHERE agent_id = $1
        """, AGENT_ID, cost)

async def get_pending_messages(pool) -> list:
    """Get pending messages for this agent."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, from_agent, msg_type, subject, body, priority
            FROM claude_messages 
            WHERE to_agent = $1 AND status = 'pending'
            ORDER BY 
                CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                created_at
        """, AGENT_ID)
        return [dict(r) for r in rows]

async def mark_message_processed(pool, message_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE claude_messages SET status = 'processed', read_at = NOW()
            WHERE id = $1
        """, message_id)

async def send_message(pool, to_agent: str, subject: str, body: str, msg_type: str = "response"):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
        """, AGENT_ID, to_agent, msg_type, subject, body)

async def add_observation(pool, subject: str, content: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO claude_observations (agent_id, observation_type, subject, content, confidence)
            VALUES ($1, 'system', $2, $3, 0.9)
        """, AGENT_ID, subject, content)

# ============================================================================
# TASK PROCESSING
# ============================================================================

CHANGELOG_PATH = "/root/catalyst-trading-system/CHANGELOG-AUTO.md"

async def append_to_changelog(summary: str):
    """Append change summary to auto-generated changelog."""
    try:
        # Create if doesn't exist
        if not os.path.exists(CHANGELOG_PATH):
            with open(CHANGELOG_PATH, 'w') as f:
                f.write("# Catalyst Auto-Generated Changelog\n\n")
                f.write("*Automatically updated by Claude agents when files are modified.*\n\n")
                f.write("---\n\n")
        
        # Append new entry
        with open(CHANGELOG_PATH, 'a') as f:
            f.write(summary)
            f.write("\n---\n\n")
        
        return True
    except Exception as e:
        print(f"Failed to update changelog: {e}")
        return False

async def process_task_message(pool, msg: dict, executor: TaskExecutor) -> dict:
    """Process a task message and execute if whitelisted."""
    
    task = parse_task_message(msg['body'])
    task_name = task.get('task_name')
    params = task.get('params', {})
    reason = task.get('reason', 'No reason provided')
    
    # Add reason to params for file operations
    params['reason'] = reason
    
    if not task_name:
        return {"success": False, "error": "No TASK: found in message body"}
    
    # Check whitelist
    if not executor.is_whitelisted(task_name):
        # Request approval from Craig
        approval_id = await executor.request_approval(task_name, params, reason)
        return {
            "success": False, 
            "error": f"Task '{task_name}' not whitelisted - escalated to Craig (approval #{approval_id})"
        }
    
    # Check if requires pre-approval
    if executor.requires_approval(task_name):
        approval_id = await executor.request_approval(task_name, params, reason)
        return {
            "success": False,
            "error": f"Task '{task_name}' requires Craig approval (approval #{approval_id})"
        }
    
    # Execute
    result = await executor.execute(task_name, params, reason)
    
    # If file operation was successful, update changelog
    if result.get("success") and result.get("requires_doc_update"):
        summary = result.get("summary", "")
        if summary:
            await append_to_changelog(summary)
            result["changelog_updated"] = True
    
    return result

async def send_task_report(pool, to_agent: str, task_name: str, msg_subject: str, result: dict):
    """Send detailed task report back to requesting agent. MANDATORY."""
    
    success = result.get("success", False)
    status = "✅ SUCCESS" if success else "❌ FAILED"
    
    # Build detailed report
    report_lines = [
        f"{status}",
        f"",
        f"## Task: {task_name}",
        f"**Original Request:** {msg_subject}",
        f"",
    ]
    
    if success:
        report_lines.extend([
            f"### Result",
            f"```",
            f"{result.get('stdout', result.get('message', 'Completed'))[:1000]}",
            f"```",
        ])
        
        # Include change summary for file operations
        if result.get("summary"):
            report_lines.extend([
                f"",
                f"### Change Summary",
                result.get("summary"),
            ])
        
        if result.get("changelog_updated"):
            report_lines.append(f"*Changelog automatically updated.*")
        
        if result.get("backup_path"):
            report_lines.append(f"**Backup:** `{result.get('backup_path')}`")
    else:
        report_lines.extend([
            f"### Error",
            f"```",
            f"{result.get('error', 'Unknown error')}",
            f"```",
        ])
        
        if result.get("rolled_back"):
            report_lines.append(f"**Action:** Automatically rolled back to backup")
    
    report_lines.extend([
        f"",
        f"**Executed at:** {result.get('executed_at', datetime.now().isoformat())}",
        f"**Executed by:** {result.get('executed_by', 'public_claude')}",
    ])
    
    report_body = "\n".join(report_lines)
    
    await send_message(pool, to_agent, f"Task Report: {msg_subject}", report_body, "response")

async def check_for_approval_responses(pool) -> list:
    """Check for approval responses from Craig."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, subject, body 
            FROM claude_messages 
            WHERE to_agent = $1 
              AND from_agent = 'craig_mobile'
              AND msg_type = 'response'
              AND status = 'pending'
        """, AGENT_ID)
        return [dict(r) for r in rows]

# ============================================================================
# MAIN HEARTBEAT
# ============================================================================

async def heartbeat():
    """Main heartbeat cycle with task execution."""
    
    print(f"[{datetime.now()}] {AGENT_ID} waking up...")
    
    pool = await get_pool()
    executor = TaskExecutor(AGENT_ID, pool)
    
    try:
        # 1. Check budget
        state = await get_state(pool)
        spent = float(state.get('api_spend_today', 0))
        if spent >= DAILY_BUDGET:
            print(f"Budget exhausted: ${spent:.4f} >= ${DAILY_BUDGET}")
            await update_state(pool, "sleeping", f"Budget exhausted: ${spent:.4f}")
            return
        
        await update_state(pool, "awake", "Processing messages")
        
        # 2. Process pending messages
        messages = await get_pending_messages(pool)
        task_results = []
        
        for msg in messages:
            print(f"Processing message #{msg['id']} from {msg['from_agent']}: {msg['subject']}")
            
            if msg['msg_type'] == 'task':
                # Parse task to get task_name for reporting
                task = parse_task_message(msg['body'])
                task_name = task.get('task_name', 'unknown')
                
                # Execute task
                result = await process_task_message(pool, msg, executor)
                task_results.append({
                    "message_id": msg['id'],
                    "task_name": task_name,
                    "subject": msg['subject'],
                    "result": result
                })
                
                # MANDATORY: Send detailed report back to sender
                await send_task_report(pool, msg['from_agent'], task_name, msg['subject'], result)
            
            # Mark processed
            await mark_message_processed(pool, msg['id'])
        
        # 3. Check for approval responses (execute approved tasks)
        approvals = await check_for_approval_responses(pool)
        for approval in approvals:
            if 'APPROVED' in approval['body'].upper():
                # Parse original task from subject
                # Subject format: "Approved: Permission: task_name"
                print(f"Executing approved task: {approval['subject']}")
                # TODO: Extract and execute approved task
            await mark_message_processed(pool, approval['id'])
        
        # 4. Quick think (minimal API call)
        await update_state(pool, "thinking", "Quick status check")
        
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        prompt = f"""You are public_claude, a trading assistant on the US droplet.
Current time: {datetime.now().isoformat()}
Messages processed this cycle: {len(messages)}
Task results: {len(task_results)}

If there were tasks, summarize what was done. Otherwise just note you're operational.
Keep response under 100 words."""
        
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        
        thought = response.content[0].text
        cost = (response.usage.input_tokens * 0.25 + response.usage.output_tokens * 1.25) / 1_000_000
        
        await record_spend(pool, cost)
        
        # 5. Record observation if tasks were executed
        if task_results:
            summary = "\n".join([f"- {r['subject']}: {'SUCCESS' if r['result'].get('success') else 'FAILED'}" 
                                for r in task_results])
            await add_observation(pool, f"Executed {len(task_results)} tasks", summary)
        
        # 6. Sleep
        await update_state(pool, "sleeping", f"Cycle complete. Processed {len(messages)} messages, {len(task_results)} tasks. ${cost:.4f}")
        
        print(f"[{datetime.now()}] Cycle complete. Cost: ${cost:.4f}")
        
    finally:
        await pool.close()

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    asyncio.run(heartbeat())
