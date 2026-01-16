#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: web_dashboard.py
Version: 1.4.0
Last Updated: 2026-01-16
Purpose: Mobile-friendly web dashboard for consciousness access

REVISION HISTORY:
v1.0.0 (2025-12-31) - Initial creation
- Mobile-friendly HTML/CSS (no React)
- Basic token auth (URL param or header)
- View agents, messages, observations, questions
- Send messages and add questions

v1.1.0 (2025-12-31) - Added approval system
- Escalation approvals for agent permission requests
- Approve/deny buttons on dashboard
- Response messages sent back to requesting agent

v1.2.0 (2025-12-31) - Added reports section
- Reports list with filtering by market/type
- Individual report view with metrics
- Mobile-friendly report cards

v1.3.0 (2026-01-16) - Dashboard implementation complete
- Perth timezone (AWST) for all times
- Approval alerts with pulsing red heading
- Command center with quick actions
- Reports section with market/type filters
- Aligned with webdash-design-mcp.md specification

v1.4.0 (2026-01-16) - Markdown table rendering
- Converts markdown tables to styled HTML tables
- Proper column alignment with CSS styling
- Supports headings, lists, horizontal rules, bold text
- Table header styling with cyan accent

ENDPOINTS:
GET  /                     → Dashboard home (with pending approvals)
GET  /agents               → All agent states
GET  /messages             → Recent messages
GET  /observations         → Recent observations
GET  /questions            → Open questions
GET  /approvals            → Pending approvals page
GET  /reports              → Trading reports list
GET  /reports/{id}         → View single report
POST /message              → Send message
POST /question             → Add question
POST /approve/{id}         → Approve an escalation
POST /deny/{id}            → Deny an escalation

USAGE:
uvicorn web_dashboard:app --host 0.0.0.0 --port 8088
"""

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
import asyncpg
import os
from datetime import datetime, timezone, timedelta

# Perth timezone (UTC+8) - same as Hong Kong/Singapore
PERTH_TZ = timezone(timedelta(hours=8))

app = FastAPI(title="Catalyst Consciousness")

DATABASE_URL = os.environ.get("RESEARCH_DATABASE_URL")
AUTH_TOKEN = os.environ.get("CONSCIOUSNESS_TOKEN", "catalyst2025")

# Quick commands for command center
QUICK_COMMANDS = [
    {"id": 1, "icon": "📊", "label": "Report HKEX", "to_agent": "intl_claude",
     "subject": "Request: Daily Report", "body": "Please generate today's trading report and store in consciousness.", "priority": "high"},
    {"id": 2, "icon": "📊", "label": "Report US", "to_agent": "public_claude",
     "subject": "Request: Daily Report", "body": "Please generate today's trading report.", "priority": "high"},
    {"id": 3, "icon": "🔍", "label": "Status", "to_agent": "big_bro",
     "subject": "Request: System Status", "body": "Please provide status on all agents and systems.", "priority": "normal"},
    {"id": 4, "icon": "🛑", "label": "STOP", "to_agent": "broadcast",
     "subject": "URGENT: Stop Trading", "body": "Human override - stop all trading activity immediately.", "priority": "urgent", "urgent": True},
    {"id": 5, "icon": "🔄", "label": "Health", "to_agent": "big_bro",
     "subject": "Request: Health Check", "body": "Run health check on all agents and report findings.", "priority": "normal"},
    {"id": 6, "icon": "💰", "label": "P&L", "to_agent": "big_bro",
     "subject": "Request: P&L Summary", "body": "What is our current P&L across all markets?", "priority": "normal"},
]

# ============================================================================
# DATABASE
# ============================================================================

async def get_pool():
    """Create database connection pool."""
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

async def get_approval_count(pool) -> int:
    """Get count of pending approvals for nav badge."""
    async with pool.acquire() as conn:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM claude_messages
            WHERE msg_type = 'escalation' AND status = 'pending'
        """)
        return count or 0

# ============================================================================
# AUTH
# ============================================================================

async def verify_token(request: Request):
    """Verify auth token from query param or header."""
    token = request.query_params.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token. Add ?token=YOUR_TOKEN to URL")
    return token

# ============================================================================
# STYLES
# ============================================================================

STYLES = """
<style>
    * { box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        margin: 0;
        padding: 16px;
        background: #0f0f23;
        color: #ccc;
        max-width: 600px;
        margin: 0 auto;
    }
    h1 { color: #00d4ff; font-size: 1.4em; margin-bottom: 8px; }
    h2 { color: #00d4ff; font-size: 1.1em; border-bottom: 1px solid #333; padding-bottom: 8px; margin-top: 24px; }
    .subtitle { color: #666; font-size: 0.85em; margin-bottom: 16px; }
    .card {
        background: #1a1a2e;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border-left: 3px solid #333;
    }
    .card.thinking { border-left-color: #0f0; }
    .card.sleeping { border-left-color: #666; }
    .card.error { border-left-color: #f00; }
    .agent-row { display: flex; justify-content: space-between; align-items: center; }
    .agent-name { font-weight: bold; color: #fff; }
    .agent-mode { font-size: 0.85em; padding: 2px 8px; border-radius: 4px; }
    .mode-sleeping { background: #333; color: #888; }
    .mode-thinking { background: #0a3; color: #fff; }
    .mode-error { background: #a00; color: #fff; }
    .agent-status { font-size: 0.8em; color: #888; margin-top: 4px; }
    .agent-spend { font-size: 0.8em; color: #0f0; }
    .msg-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
    .msg-from { color: #00d4ff; font-weight: bold; }
    .msg-to { color: #888; }
    .msg-subject { color: #fff; }
    .msg-body { font-size: 0.85em; color: #aaa; margin-top: 8px; white-space: pre-wrap; }
    .msg-time { font-size: 0.75em; color: #555; }
    .obs-agent { color: #00d4ff; font-weight: bold; }
    .obs-subject { color: #fff; }
    .obs-content { font-size: 0.85em; color: #aaa; margin-top: 4px; }
    .nav {
        display: flex;
        gap: 12px;
        margin: 16px 0;
        flex-wrap: wrap;
    }
    .nav a {
        color: #00d4ff;
        text-decoration: none;
        padding: 8px 12px;
        background: #1a1a2e;
        border-radius: 4px;
        font-size: 0.9em;
    }
    .nav a:hover { background: #252545; }
    .nav a.active { background: #00d4ff; color: #000; }
    form { margin-top: 16px; }
    label { display: block; color: #888; font-size: 0.85em; margin-top: 12px; }
    input, select, textarea {
        width: 100%;
        padding: 10px;
        margin: 4px 0 8px 0;
        border-radius: 6px;
        border: 1px solid #333;
        background: #16213e;
        color: #fff;
        font-size: 16px;
    }
    textarea { resize: vertical; min-height: 80px; }
    button {
        background: #00d4ff;
        color: #000;
        border: none;
        padding: 14px;
        border-radius: 6px;
        width: 100%;
        font-weight: bold;
        font-size: 1em;
        margin-top: 8px;
        cursor: pointer;
    }
    button:hover { background: #00b8e0; }
    .success { background: #0a3; color: #fff; padding: 12px; border-radius: 6px; margin: 16px 0; }
    .error-msg { background: #a00; color: #fff; padding: 12px; border-radius: 6px; margin: 16px 0; }
    .back { display: inline-block; margin-bottom: 16px; color: #00d4ff; text-decoration: none; }
    .empty { color: #555; font-style: italic; padding: 16px; text-align: center; }
    .priority { font-size: 0.8em; padding: 2px 6px; border-radius: 3px; background: #333; }
    .priority-high { background: #a50; }
    .priority-critical { background: #a00; }
    .card.escalation { border-left: 3px solid #ff0; background: #2a2a1e; }
    .approval-buttons { display: flex; gap: 8px; margin-top: 12px; }
    .approval-buttons form { margin: 0; flex: 1; }
    .approval-buttons button { padding: 10px; }
    .btn-approve { background: #0a3; }
    .btn-approve:hover { background: #0c4; }
    .btn-deny { background: #a00; }
    .btn-deny:hover { background: #c00; }
    .badge { display: inline-block; background: #ff0; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold; margin-left: 8px; }
    .alert-heading { color: #ff4444 !important; font-weight: bold; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
    /* Command Center */
    .command-center { margin: 16px 0; padding: 16px; background: #12122a; border-radius: 8px; border: 1px solid #333; }
    .command-center h2 { margin-top: 0; border-bottom: none; padding-bottom: 0; }
    .quick-commands { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0; }
    .quick-cmd { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 12px 4px; background: #1a1a2e; border: 1px solid #333; border-radius: 8px; color: #fff; cursor: pointer; min-height: 60px; font-family: inherit; }
    .quick-cmd:hover { background: #252545; border-color: #00d4ff; }
    .quick-cmd:active { background: #00d4ff; color: #000; }
    .quick-cmd.urgent { border-color: #f44; background: #2a1a1a; }
    .quick-cmd.urgent:hover { background: #f44; border-color: #f66; }
    .cmd-icon { font-size: 1.4em; margin-bottom: 2px; }
    .cmd-label { font-size: 0.75em; color: #aaa; text-align: center; }
    .quick-cmd:hover .cmd-label, .quick-cmd.urgent:hover .cmd-label { color: #fff; }
    .message-form-section { margin-top: 16px; padding-top: 12px; border-top: 1px solid #333; }
    .message-form-section summary { cursor: pointer; color: #00d4ff; font-size: 0.9em; }
    .message-form-section[open] summary { margin-bottom: 12px; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .form-row label { margin-top: 0; }
</style>
"""

def nav_html(active: str, token: str, approval_count: int = 0) -> str:
    """Generate navigation HTML."""
    links = [
        ("Home", "/"),
        ("Approvals", "/approvals"),
        ("Reports", "/reports"),
        ("Agents", "/agents"),
        ("Messages", "/messages"),
        ("Observations", "/observations"),
        ("Questions", "/questions"),
    ]
    nav = '<div class="nav">'
    for name, url in links:
        is_active = "active" if name.lower() == active.lower() else ""
        badge = f'<span class="badge">{approval_count}</span>' if name == "Approvals" and approval_count > 0 else ""
        nav += f'<a href="{url}?token={token}" class="{is_active}">{name}{badge}</a>'
    nav += '</div>'
    return nav

def format_time(dt) -> str:
    """Format datetime for display in Perth time (UTC+8)."""
    if not dt:
        return ""
    # Convert to Perth timezone
    if dt.tzinfo is not None:
        perth_time = dt.astimezone(PERTH_TZ)
    else:
        # Assume UTC if no timezone info
        perth_time = dt.replace(tzinfo=timezone.utc).astimezone(PERTH_TZ)
    return perth_time.strftime("%m/%d %H:%M AWST")

def command_center_html(token: str) -> str:
    """Generate command center HTML."""
    buttons = ""
    for cmd in QUICK_COMMANDS:
        urgent_class = "urgent" if cmd.get("urgent") else ""
        buttons += f'''
        <form method="POST" action="/command/{cmd['id']}?token={token}" style="margin:0;">
            <button type="submit" class="quick-cmd {urgent_class}">
                <span class="cmd-icon">{cmd['icon']}</span>
                <span class="cmd-label">{cmd['label']}</span>
            </button>
        </form>
        '''

    html = f'''
    <div class="command-center">
        <h2>📡 COMMAND CENTER</h2>
        <div class="quick-commands">
            {buttons}
        </div>
        <details class="message-form-section">
            <summary>✉️ Custom Message</summary>
            <form method="POST" action="/message?token={token}">
                <div class="form-row">
                    <div>
                        <label>To:</label>
                        <select name="to_agent">
                            <option value="intl_claude">intl_claude (HKEX)</option>
                            <option value="public_claude">public_claude (US)</option>
                            <option value="big_bro">big_bro (Strategy)</option>
                        </select>
                    </div>
                    <div>
                        <label>Priority:</label>
                        <select name="priority">
                            <option value="normal">Normal</option>
                            <option value="high">High</option>
                            <option value="urgent">🚨 Urgent</option>
                        </select>
                    </div>
                </div>
                <label>Subject:</label>
                <input type="text" name="subject" placeholder="Brief subject..." required>
                <label>Message:</label>
                <textarea name="body" rows="2" placeholder="Your message..." required></textarea>
                <button type="submit">📤 Send Message</button>
            </form>
        </details>
    </div>
    '''
    return html

# ============================================================================
# ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, token: str = Depends(verify_token)):
    """Dashboard home - overview of everything."""
    # Check for success message
    sent = request.query_params.get("sent")
    success_msg = '<div class="success">✅ Command sent!</div>' if sent else ""

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            agents = await conn.fetch("""
                SELECT agent_id, current_mode, status_message, api_spend_today
                FROM claude_state ORDER BY agent_id
            """)
            messages = await conn.fetch("""
                SELECT from_agent, to_agent, subject, created_at
                FROM claude_messages
                ORDER BY created_at DESC LIMIT 5
            """)
            observations = await conn.fetch("""
                SELECT agent_id, subject, created_at
                FROM claude_observations
                ORDER BY created_at DESC LIMIT 5
            """)
            # Get pending approvals (escalations)
            approvals = await conn.fetch("""
                SELECT id, from_agent, subject, body, created_at
                FROM claude_messages
                WHERE msg_type = 'escalation' AND status = 'pending'
                ORDER BY created_at DESC
            """)
    finally:
        await pool.close()

    approval_count = len(approvals)

    agents_html = ""
    for a in agents:
        mode = a["current_mode"] or "unknown"
        mode_class = f"mode-{mode}" if mode in ["sleeping", "thinking", "error"] else ""
        agents_html += f'''
        <div class="card {mode}">
            <div class="agent-row">
                <span class="agent-name">{a["agent_id"]}</span>
                <span class="agent-mode {mode_class}">{mode}</span>
            </div>
            <div class="agent-status">{a["status_message"] or "No status"}</div>
            <div class="agent-spend">Today: ${float(a["api_spend_today"] or 0):.4f}</div>
        </div>
        '''

    msgs_html = ""
    for m in messages:
        msgs_html += f'''
        <div class="card">
            <div class="msg-header">
                <span><span class="msg-from">{m["from_agent"]}</span> → <span class="msg-to">{m["to_agent"]}</span></span>
                <span class="msg-time">{format_time(m["created_at"])}</span>
            </div>
            <div class="msg-subject">{m["subject"]}</div>
        </div>
        '''

    obs_html = ""
    for o in observations:
        obs_html += f'''
        <div class="card">
            <span class="obs-agent">{o["agent_id"]}</span>: <span class="obs-subject">{o["subject"]}</span>
            <div class="msg-time">{format_time(o["created_at"])}</div>
        </div>
        '''

    # Build approvals HTML
    approvals_html = ""
    for a in approvals:
        body_preview = (a["body"] or "")[:150] + ("..." if len(a["body"] or "") > 150 else "")
        approvals_html += f'''
        <div class="card escalation">
            <div class="msg-header">
                <span class="msg-from">{a["from_agent"]}</span>
                <span class="msg-time">{format_time(a["created_at"])}</span>
            </div>
            <div class="msg-subject">{a["subject"]}</div>
            <div class="msg-body">{body_preview}</div>
            <div class="approval-buttons">
                <form action="/approve/{a["id"]}?token={token}" method="post">
                    <button class="btn-approve">Approve</button>
                </form>
                <form action="/deny/{a["id"]}?token={token}" method="post">
                    <button class="btn-deny">Deny</button>
                </form>
            </div>
        </div>
        '''

    command_html = command_center_html(token)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
        <title>Catalyst Consciousness</title>
        {STYLES}
    </head>
    <body>
        <h1>🧠 Catalyst Consciousness</h1>
        <div class="subtitle">All times AWST (UTC+8)</div>

        {nav_html("home", token, approval_count)}

        {success_msg}

        {f'<h2 class="alert-heading">⚠️ PENDING APPROVALS ({approval_count})</h2>' + approvals_html if approvals_html else ''}

        {command_html}

        <h2>👥 Agents</h2>
        {agents_html or '<div class="empty">No agents</div>'}

        <h2>💬 Recent Messages</h2>
        {msgs_html or '<div class="empty">No messages</div>'}

        <h2>👁️ Recent Observations</h2>
        {obs_html or '<div class="empty">No observations</div>'}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request, token: str = Depends(verify_token)):
    """All agent states."""
    pool = await get_pool()
    try:
        approval_count = await get_approval_count(pool)
        async with pool.acquire() as conn:
            agents = await conn.fetch("""
                SELECT agent_id, current_mode, status_message, api_spend_today,
                       daily_budget, last_wake_at, last_think_at, error_count_today
                FROM claude_state ORDER BY agent_id
            """)
    finally:
        await pool.close()

    agents_html = ""
    for a in agents:
        mode = a["current_mode"] or "unknown"
        mode_class = f"mode-{mode}" if mode in ["sleeping", "thinking", "error"] else ""
        budget = float(a["daily_budget"] or 0)
        spent = float(a["api_spend_today"] or 0)
        remaining = budget - spent

        agents_html += f'''
        <div class="card {mode}">
            <div class="agent-row">
                <span class="agent-name">{a["agent_id"]}</span>
                <span class="agent-mode {mode_class}">{mode}</span>
            </div>
            <div class="agent-status">{a["status_message"] or "No status"}</div>
            <div style="margin-top: 8px; font-size: 0.85em; color: #888;">
                <div>Budget: ${spent:.4f} / ${budget:.2f} (${remaining:.4f} left)</div>
                <div>Last wake: {format_time(a["last_wake_at"])}</div>
                <div>Errors today: {a["error_count_today"] or 0}</div>
            </div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Agents - Catalyst</title>
        {STYLES}
    </head>
    <body>
        <h1>Agents</h1>
        {nav_html("agents", token, approval_count)}
        {agents_html or '<div class="empty">No agents</div>'}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request, token: str = Depends(verify_token)):
    """Recent messages."""
    pool = await get_pool()
    try:
        approval_count = await get_approval_count(pool)
        async with pool.acquire() as conn:
            messages = await conn.fetch("""
                SELECT from_agent, to_agent, subject, body, status, created_at
                FROM claude_messages
                ORDER BY created_at DESC LIMIT 20
            """)
    finally:
        await pool.close()

    msgs_html = ""
    for m in messages:
        status_color = "#0f0" if m["status"] == "read" else "#ff0"
        body_preview = (m["body"] or "")[:200] + ("..." if len(m["body"] or "") > 200 else "")
        msgs_html += f'''
        <div class="card">
            <div class="msg-header">
                <span><span class="msg-from">{m["from_agent"]}</span> → <span class="msg-to">{m["to_agent"]}</span></span>
                <span style="color: {status_color}; font-size: 0.8em;">{m["status"]}</span>
            </div>
            <div class="msg-subject">{m["subject"]}</div>
            <div class="msg-body">{body_preview}</div>
            <div class="msg-time">{format_time(m["created_at"])}</div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Messages - Catalyst</title>
        {STYLES}
    </head>
    <body>
        <h1>Messages</h1>
        {nav_html("messages", token, approval_count)}
        {msgs_html or '<div class="empty">No messages</div>'}

        <h2>Send Message</h2>
        <form action="/message?token={token}" method="post">
            <label>To Agent</label>
            <select name="to_agent">
                <option value="big_bro">big_bro</option>
                <option value="public_claude">public_claude</option>
                <option value="intl_claude">intl_claude</option>
            </select>
            <label>Subject</label>
            <input name="subject" placeholder="Message subject" required>
            <label>Message</label>
            <textarea name="body" placeholder="Your message..." required></textarea>
            <button type="submit">Send Message</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/observations", response_class=HTMLResponse)
async def observations_page(request: Request, token: str = Depends(verify_token)):
    """Recent observations."""
    pool = await get_pool()
    try:
        approval_count = await get_approval_count(pool)
        async with pool.acquire() as conn:
            observations = await conn.fetch("""
                SELECT agent_id, observation_type, subject, content, confidence, market, created_at
                FROM claude_observations
                ORDER BY created_at DESC LIMIT 20
            """)
    finally:
        await pool.close()

    obs_html = ""
    for o in observations:
        obs_html += f'''
        <div class="card">
            <div class="msg-header">
                <span class="obs-agent">{o["agent_id"]}</span>
                <span class="msg-time">{format_time(o["created_at"])}</span>
            </div>
            <div class="obs-subject">{o["subject"]}</div>
            <div class="obs-content">{o["content"]}</div>
            <div style="margin-top: 8px; font-size: 0.75em; color: #555;">
                Type: {o["observation_type"]} | Market: {o["market"]} | Confidence: {float(o["confidence"] or 0):.0%}
            </div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Observations - Catalyst</title>
        {STYLES}
    </head>
    <body>
        <h1>Observations</h1>
        {nav_html("observations", token, approval_count)}
        {obs_html or '<div class="empty">No observations</div>'}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/questions", response_class=HTMLResponse)
async def questions_page(request: Request, token: str = Depends(verify_token)):
    """Open questions."""
    pool = await get_pool()
    try:
        approval_count = await get_approval_count(pool)
        async with pool.acquire() as conn:
            questions = await conn.fetch("""
                SELECT id, question, horizon, priority, category, status, created_at
                FROM claude_questions
                WHERE status = 'open'
                ORDER BY priority DESC, created_at DESC
            """)
    finally:
        await pool.close()

    q_html = ""
    for q in questions:
        priority = int(q["priority"] or 5)
        priority_class = "priority-critical" if priority >= 9 else "priority-high" if priority >= 7 else ""
        q_html += f'''
        <div class="card">
            <div class="msg-header">
                <span class="priority {priority_class}">P{priority}</span>
                <span class="msg-time">{q["horizon"] or "any"}</span>
            </div>
            <div class="obs-subject" style="margin-top: 8px;">{q["question"]}</div>
            <div style="margin-top: 8px; font-size: 0.75em; color: #555;">
                Category: {q["category"] or "general"} | Added: {format_time(q["created_at"])}
            </div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Questions - Catalyst</title>
        {STYLES}
    </head>
    <body>
        <h1>Open Questions</h1>
        {nav_html("questions", token, approval_count)}
        {q_html or '<div class="empty">No open questions</div>'}

        <h2>Add Question</h2>
        <form action="/question?token={token}" method="post">
            <label>Question</label>
            <textarea name="question" placeholder="Question for the family to think about..." required></textarea>
            <label>Priority</label>
            <select name="priority">
                <option value="5">Normal (5)</option>
                <option value="7">High (7)</option>
                <option value="9">Critical (9)</option>
            </select>
            <label>Horizon</label>
            <select name="horizon">
                <option value="short">Short-term</option>
                <option value="medium">Medium-term</option>
                <option value="long">Long-term</option>
            </select>
            <label>Category</label>
            <select name="category">
                <option value="trading">Trading</option>
                <option value="system">System</option>
                <option value="mission">Mission</option>
                <option value="market">Market</option>
            </select>
            <button type="submit">Add Question</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/message")
async def send_message(
    request: Request,
    to_agent: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    token: str = Depends(verify_token)
):
    """Send a message to an agent."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, status)
                VALUES ('craig_desktop', $1, 'message', $2, $3, 'pending')
            """, to_agent, subject, body)
    finally:
        await pool.close()

    return RedirectResponse(url=f"/messages?token={token}&success=1", status_code=303)


@app.post("/command/{command_id}")
async def execute_command(
    command_id: int,
    request: Request,
    token: str = Depends(verify_token)
):
    """Execute a quick command."""
    cmd = next((c for c in QUICK_COMMANDS if c['id'] == command_id), None)
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Handle broadcast
            if cmd['to_agent'] == 'broadcast':
                agents = ['intl_claude', 'public_claude', 'big_bro']
            else:
                agents = [cmd['to_agent']]

            # Send message to each agent
            for agent in agents:
                await conn.execute("""
                    INSERT INTO claude_messages
                    (from_agent, to_agent, subject, body, priority, msg_type, status)
                    VALUES ('craig_mobile', $1, $2, $3, $4, 'task', 'pending')
                """, agent, cmd['subject'], cmd['body'], cmd['priority'])
    finally:
        await pool.close()

    return RedirectResponse(url=f"/?token={token}&sent=1", status_code=303)


@app.post("/question")
async def add_question(
    request: Request,
    question: str = Form(...),
    priority: int = Form(5),
    horizon: str = Form("medium"),
    category: str = Form("trading"),
    token: str = Depends(verify_token)
):
    """Add a question for the family."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_questions (question, horizon, priority, category, status)
                VALUES ($1, $2, $3, $4, 'open')
            """, question, horizon, priority, category)
    finally:
        await pool.close()

    return RedirectResponse(url=f"/questions?token={token}&success=1", status_code=303)


@app.get("/approvals", response_class=HTMLResponse)
async def approvals_page(request: Request, token: str = Depends(verify_token)):
    """Pending approvals page."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            approvals = await conn.fetch("""
                SELECT id, from_agent, subject, body, created_at
                FROM claude_messages
                WHERE msg_type = 'escalation' AND status = 'pending'
                ORDER BY created_at DESC
            """)
    finally:
        await pool.close()

    approval_count = len(approvals)

    approvals_html = ""
    for a in approvals:
        body_text = a["body"] or ""
        approvals_html += f'''
        <div class="card escalation">
            <div class="msg-header">
                <span class="msg-from">{a["from_agent"]}</span>
                <span class="msg-time">{format_time(a["created_at"])}</span>
            </div>
            <div class="msg-subject">{a["subject"]}</div>
            <div class="msg-body">{body_text}</div>
            <div class="approval-buttons">
                <form action="/approve/{a["id"]}?token={token}" method="post">
                    <button class="btn-approve">Approve</button>
                </form>
                <form action="/deny/{a["id"]}?token={token}" method="post">
                    <button class="btn-deny">Deny</button>
                </form>
            </div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Approvals - Catalyst</title>
        {STYLES}
    </head>
    <body>
        <h1>Pending Approvals</h1>
        {nav_html("approvals", token, approval_count)}
        {approvals_html or '<div class="empty">No pending approvals</div>'}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/approve/{message_id}")
async def approve_escalation(message_id: int, request: Request, token: str = Depends(verify_token)):
    """Approve an escalation request."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Get original message
            msg = await conn.fetchrow(
                "SELECT from_agent, subject FROM claude_messages WHERE id = $1",
                message_id
            )
            if not msg:
                raise HTTPException(status_code=404, detail="Message not found")

            # Mark as approved
            await conn.execute("""
                UPDATE claude_messages
                SET status = 'approved', read_at = NOW()
                WHERE id = $1
            """, message_id)

            # Send approval response back to agent
            await conn.execute("""
                INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, status)
                VALUES ('craig_mobile', $1, 'response', $2, 'APPROVED', 'pending')
            """, msg['from_agent'], f"Approved: {msg['subject']}")
    finally:
        await pool.close()

    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.post("/deny/{message_id}")
async def deny_escalation(message_id: int, request: Request, reason: str = Form(""), token: str = Depends(verify_token)):
    """Deny an escalation request."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Get original message
            msg = await conn.fetchrow(
                "SELECT from_agent, subject FROM claude_messages WHERE id = $1",
                message_id
            )
            if not msg:
                raise HTTPException(status_code=404, detail="Message not found")

            # Mark as denied
            await conn.execute("""
                UPDATE claude_messages
                SET status = 'denied', read_at = NOW()
                WHERE id = $1
            """, message_id)

            # Send denial response back to agent
            await conn.execute("""
                INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, status)
                VALUES ('craig_mobile', $1, 'response', $2, $3, 'pending')
            """, msg['from_agent'], f"Denied: {msg['subject']}", reason or 'DENIED')
    finally:
        await pool.close()

    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "consciousness-dashboard"}


# ============================================================================
# REPORTS
# ============================================================================

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    market: str = None,
    report_type: str = None,
    token: str = Depends(verify_token)
):
    """Trading reports list with filtering."""
    pool = await get_pool()
    try:
        approval_count = await get_approval_count(pool)
        async with pool.acquire() as conn:
            # Build query with optional filters
            query = """
                SELECT id, agent_id, market, report_type, report_date, title, summary, metrics, created_at
                FROM claude_reports
                WHERE 1=1
            """
            params = []
            param_idx = 1

            if market:
                query += f" AND market = ${param_idx}"
                params.append(market)
                param_idx += 1

            if report_type:
                query += f" AND report_type = ${param_idx}"
                params.append(report_type)
                param_idx += 1

            query += " ORDER BY report_date DESC, created_at DESC LIMIT 50"

            reports = await conn.fetch(query, *params)
    finally:
        await pool.close()

    # Filter tabs
    filter_tabs = f'''
    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
        <a href="/reports?token={token}" class="nav {'active' if not market and not report_type else ''}" style="padding: 6px 12px;">All</a>
        <a href="/reports?token={token}&report_type=daily" class="nav {'active' if report_type == 'daily' else ''}" style="padding: 6px 12px;">Daily</a>
        <a href="/reports?token={token}&report_type=weekly" class="nav {'active' if report_type == 'weekly' else ''}" style="padding: 6px 12px;">Weekly</a>
        <a href="/reports?token={token}&market=US" class="nav {'active' if market == 'US' else ''}" style="padding: 6px 12px;">US</a>
        <a href="/reports?token={token}&market=HKEX" class="nav {'active' if market == 'HKEX' else ''}" style="padding: 6px 12px;">HKEX</a>
    </div>
    '''

    reports_html = ""
    for r in reports:
        metrics = r["metrics"] or {}
        if isinstance(metrics, str):
            import json as json_lib
            metrics = json_lib.loads(metrics)
        pnl = metrics.get("total_pnl", 0)
        positions = metrics.get("positions_open", 0)

        # Format P&L with color
        pnl_color = "#0f0" if pnl >= 0 else "#f00"
        pnl_str = f"+{pnl:,.2f}" if pnl >= 0 else f"{pnl:,.2f}"

        # Market badge color
        market_color = "#00d4ff" if r["market"] == "US" else "#ff0" if r["market"] == "HKEX" else "#888"

        # Report type icon
        type_icon = "📈" if r["report_type"] == "daily" else "📊" if r["report_type"] == "weekly" else "⚠️" if r["report_type"] == "alert" else "📋"

        reports_html += f'''
        <div class="card">
            <div class="msg-header">
                <span style="color: {market_color}; font-weight: bold;">{r["market"]}</span>
                <span class="msg-time">{r["report_date"]}</span>
            </div>
            <div class="msg-subject">{type_icon} {r["title"]}</div>
            <div style="margin-top: 8px; font-size: 0.85em;">
                <span class="obs-agent">{r["agent_id"]}</span>
                {f'<span style="color: {pnl_color}; margin-left: 8px;">{pnl_str}</span>' if pnl else ''}
                {f'<span style="color: #888; margin-left: 8px;">{positions} positions</span>' if positions else ''}
            </div>
            {f'<div class="msg-body">{r["summary"]}</div>' if r["summary"] else ''}
            <div style="margin-top: 12px;">
                <a href="/reports/{r["id"]}?token={token}" style="color: #00d4ff; text-decoration: none;">View Full Report →</a>
            </div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Reports - Catalyst</title>
        {STYLES}
    </head>
    <body>
        <h1>📊 Reports</h1>
        {nav_html("reports", token, approval_count)}
        {filter_tabs}
        {reports_html or '<div class="empty">No reports yet</div>'}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/reports/{report_id}", response_class=HTMLResponse)
async def view_report(report_id: int, request: Request, token: str = Depends(verify_token)):
    """View a single report."""
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            report = await conn.fetchrow("""
                SELECT id, agent_id, market, report_type, report_date, title, summary, content, metrics, created_at
                FROM claude_reports
                WHERE id = $1
            """, report_id)
    finally:
        await pool.close()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    metrics = report["metrics"] or {}
    if isinstance(metrics, str):
        import json as json_lib
        metrics = json_lib.loads(metrics)

    # Build metrics cards
    metrics_html = ""
    if metrics:
        metrics_items = []
        if "total_pnl" in metrics:
            pnl = metrics["total_pnl"]
            pnl_color = "#0f0" if pnl >= 0 else "#f00"
            pnl_str = f"+{pnl:,.2f}" if pnl >= 0 else f"{pnl:,.2f}"
            metrics_items.append(f'<span style="color: {pnl_color};">P&L: {pnl_str}</span>')
        if "positions_open" in metrics:
            metrics_items.append(f'Positions: {metrics["positions_open"]}')
        if "account_value" in metrics:
            metrics_items.append(f'Account: {metrics["account_value"]:,.2f}')
        if "win_rate" in metrics:
            metrics_items.append(f'Win Rate: {metrics["win_rate"]*100:.0f}%')

        if metrics_items:
            metrics_html = f'''
            <div class="card" style="border-left-color: #00d4ff;">
                <div style="display: flex; flex-wrap: wrap; gap: 16px;">
                    {"  |  ".join(metrics_items)}
                </div>
            </div>
            '''

    # Convert markdown content to HTML
    content = report["content"] or ""

    # Convert markdown tables to HTML tables
    lines = content.split('\n')
    html_lines = []
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Check if this is a table row (starts and ends with |)
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            # Check if this is a separator row (contains only dashes and colons)
            if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                continue  # Skip separator rows
            # Convert bold markers in cells
            cells = [c.replace('**', '<strong>', 1).replace('**', '</strong>', 1) if '**' in c else c for c in cells]
            if not in_table:
                html_lines.append('<table class="report-table">')
                in_table = True
                # First row is header
                html_lines.append('<tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>')
            else:
                html_lines.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        else:
            if in_table:
                html_lines.append('</table>')
                in_table = False
            # Handle headings
            if stripped.startswith('## '):
                html_lines.append(f'<h3>{stripped[3:]}</h3>')
            elif stripped.startswith('# '):
                html_lines.append(f'<h2>{stripped[2:]}</h2>')
            elif stripped.startswith('### '):
                html_lines.append(f'<h4>{stripped[4:]}</h4>')
            elif stripped == '---':
                html_lines.append('<hr>')
            elif stripped.startswith('- '):
                html_lines.append(f'<div class="list-item">• {stripped[2:]}</div>')
            elif stripped.startswith('**') and stripped.endswith('**'):
                html_lines.append(f'<p><strong>{stripped[2:-2]}</strong></p>')
            elif stripped:
                # Handle bold text within line
                formatted = stripped
                while '**' in formatted:
                    formatted = formatted.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
                html_lines.append(f'<p>{formatted}</p>')

    if in_table:
        html_lines.append('</table>')

    content = '\n'.join(html_lines)

    # Market badge color
    market_color = "#00d4ff" if report["market"] == "US" else "#ff0" if report["market"] == "HKEX" else "#888"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{report["title"]} - Catalyst</title>
        {STYLES}
        <style>
            .report-content {{ line-height: 1.6; }}
            .report-content h2 {{ color: #00d4ff; font-size: 1.2em; margin-top: 24px; margin-bottom: 12px; }}
            .report-content h3 {{ color: #00d4ff; font-size: 1.1em; margin-top: 20px; margin-bottom: 10px; }}
            .report-content h4 {{ color: #aaa; font-size: 0.95em; margin-top: 16px; margin-bottom: 8px; }}
            .report-content p {{ margin: 6px 0; color: #ccc; }}
            .report-content hr {{ border: none; border-top: 1px solid #333; margin: 16px 0; }}
            .report-content .list-item {{ margin: 4px 0; padding-left: 8px; color: #aaa; }}
            .report-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 12px 0;
                font-size: 0.9em;
            }}
            .report-table th {{
                background: #252545;
                color: #00d4ff;
                padding: 10px 8px;
                text-align: left;
                border-bottom: 2px solid #00d4ff;
                white-space: nowrap;
            }}
            .report-table td {{
                padding: 8px;
                border-bottom: 1px solid #333;
                color: #ccc;
            }}
            .report-table tr:hover {{ background: #1f1f3a; }}
        </style>
    </head>
    <body>
        <a href="/reports?token={token}" class="back">← Back to Reports</a>

        <h1>{report["title"]}</h1>
        <div class="subtitle">
            <span style="color: {market_color};">{report["market"]}</span> ·
            {report["agent_id"]} ·
            {report["report_date"]} ·
            {report["report_type"]}
        </div>

        {metrics_html}

        <div class="card report-content" style="margin-top: 16px;">
            {content}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
