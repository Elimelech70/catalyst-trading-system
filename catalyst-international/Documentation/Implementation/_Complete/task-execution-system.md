# Task Execution System

**Version:** 1.0.0  
**Last Updated:** 2025-12-31  
**Purpose:** How big_bro issues commands to little bros

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TASK EXECUTION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   BIG_BRO                                                                   │
│      │                                                                      │
│      │  Sends task message (msg_type='task')                               │
│      ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  claude_messages table                                              │  │
│   │  from_agent: big_bro                                                │  │
│   │  to_agent: public_claude                                            │  │
│   │  msg_type: task                                                     │  │
│   │  subject: Check Docker health                                       │  │
│   │  body: TASK: docker_ps                                              │  │
│   │        PARAMS: {}                                                   │  │
│   │        REASON: Routine health check                                 │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│      │                                                                      │
│      │  Heartbeat picks up message                                         │
│      ▼                                                                      │
│   PUBLIC_CLAUDE                                                             │
│      │                                                                      │
│      ├── Is task whitelisted? ──► YES ──► Execute                          │
│      │                                         │                            │
│      │                                         ▼                            │
│      │                              Send result back to big_bro            │
│      │                                                                      │
│      └── Is task whitelisted? ──► NO ──► Escalate to craig_mobile          │
│                                                │                            │
│                                                ▼                            │
│                                    Craig approves/denies on phone           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Task Message Format

### Sending a Task (big_bro)

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES (
    'big_bro',
    'public_claude', 
    'task',
    'Check Docker health',
    'TASK: docker_ps
PARAMS: {}
REASON: Routine hourly health check',
    'normal',
    'pending'
);
```

### Task with Parameters

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES (
    'big_bro',
    'public_claude', 
    'task',
    'Get trading service logs',
    'TASK: docker_logs
PARAMS: {"service": "trading"}
REASON: Checking for errors after last trade',
    'normal',
    'pending'
);
```

---

## Whitelisted Tasks

### System Health (No Approval Needed)

| Task Name | Description | Params |
|-----------|-------------|--------|
| `docker_ps` | List running containers | - |
| `disk_space` | Check disk usage | - |
| `memory_usage` | Check RAM usage | - |
| `process_list` | Top 10 processes | - |
| `service_health` | Check HTTP health | `port` (5000-5009) |
| `docker_logs` | Service logs (50 lines) | `service` |
| `catalyst_logs` | Read log files | `logfile` |

### Database Queries (Read Only)

| Task Name | Description | Params |
|-----------|-------------|--------|
| `db_agent_status` | Agent states | - |
| `db_pending_messages` | Count pending | - |
| `db_recent_observations` | Last 5 observations | - |

### Service Control (Whitelisted - No Approval)

| Task Name | Description | Params |
|-----------|-------------|--------|
| `restart_service` | Restart Docker service | `service` |
| `restart_dashboard` | Restart web dashboard | - |
| `restart_all_services` | Restart ALL trading services | - |

### File Operations (with Automatic Rollback)

| Task Name | Description | Params |
|-----------|-------------|--------|
| `write_file` | Write new Python file | `filepath`, `content` |
| `edit_file` | Edit file (search/replace) | `filepath`, `old_text`, `new_text` |
| `rollback_file` | Restore file from backup | `filepath` |

**Allowed Paths:**
- `/root/catalyst-trading-system/services/`
- `/root/catalyst-trading-system/scripts/`
- `/root/catalyst-intl/src/`

**Allowed Extensions:** `.py`, `.sh`, `.md`

**Safety Features:**
1. Automatic backup before any change
2. Python syntax validation after write
3. Automatic rollback if validation fails
4. Backups stored in `/root/catalyst-backups/`

---

## File Operation Examples

### Write a New File

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Create helper script', 
        'TASK: write_file
PARAMS: {"filepath": "/root/catalyst-trading-system/services/consciousness/helper.py", "content": "#!/usr/bin/env python3\n\"\"\"Helper module\"\"\"\n\ndef hello():\n    return \"Hello from helper\"\n"}
REASON: Adding utility function', 'normal', 'pending');
```

### Edit an Existing File

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Fix bug in heartbeat', 
        'TASK: edit_file
PARAMS: {"filepath": "/root/catalyst-trading-system/services/consciousness/heartbeat.py", "old_text": "MODEL = \"claude-3-5-haiku-20241022\"", "new_text": "MODEL = \"claude-3-haiku-20240307\""}
REASON: Switching to older model', 'normal', 'pending');
```

### Manual Rollback

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Rollback heartbeat', 
        'TASK: rollback_file
PARAMS: {"filepath": "/root/catalyst-trading-system/services/consciousness/heartbeat.py"}
REASON: Previous edit caused issues', 'high', 'pending');
```

---

## Rollback Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FILE EDIT WITH ROLLBACK                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. big_bro sends edit_file task                                           │
│     │                                                                       │
│     ▼                                                                       │
│  2. public_claude creates backup                                           │
│     /root/catalyst-backups/heartbeat.py.20251231_120000.bak                │
│     │                                                                       │
│     ▼                                                                       │
│  3. Make the edit                                                          │
│     │                                                                       │
│     ▼                                                                       │
│  4. Validate Python syntax                                                 │
│     │                                                                       │
│     ├── PASS ──► Success!                                                  │
│     │            │                                                          │
│     │            ├── Update CHANGELOG-AUTO.md                              │
│     │            ├── Send detailed report to big_bro (MANDATORY)           │
│     │            └── Backup kept for manual rollback                       │
│     │                                                                       │
│     └── FAIL ──► AUTOMATIC ROLLBACK to backup                              │
│                  Send error report to big_bro (MANDATORY)                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Task Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE TASK EXECUTION FLOW                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BIG_BRO (:00)                                                             │
│     │                                                                       │
│     │ "Fix the timeout bug in heartbeat.py"                                │
│     │                                                                       │
│     ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ claude_messages (msg_type='task')                                   │   │
│  │ TASK: edit_file                                                     │   │
│  │ PARAMS: {"filepath": "...", "old_text": "...", "new_text": "..."}  │   │
│  │ REASON: Timeout too short                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                       │
│     │ Waits in queue                                                       │
│     ▼                                                                       │
│  PUBLIC_CLAUDE (:15)                                                       │
│     │                                                                       │
│     ├── 1. Read task message                                               │
│     ├── 2. Validate whitelist ✓                                            │
│     ├── 3. Create backup                                                   │
│     ├── 4. Execute edit                                                    │
│     ├── 5. Validate syntax                                                 │
│     ├── 6. Update CHANGELOG-AUTO.md                                        │
│     └── 7. MANDATORY: Send detailed report                                 │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ claude_messages (msg_type='response')                               │   │
│  │ To: big_bro                                                         │   │
│  │ Subject: Task Report: Fix the timeout bug                          │   │
│  │ Body:                                                               │   │
│  │   ✅ SUCCESS                                                        │   │
│  │   ## Task: edit_file                                                │   │
│  │   ### Change Summary                                                │   │
│  │   - Removed: `timeout=30`                                          │   │
│  │   - Added: `timeout=60`                                            │   │
│  │   *Changelog automatically updated.*                               │   │
│  │   **Backup:** /root/catalyst-backups/...                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│     │                                                                       │
│     │ big_bro reads report on next wake                                    │
│     ▼                                                                       │
│  BIG_BRO (:00 next hour)                                                   │
│     │                                                                       │
│     └── Knows exactly what was changed, why, and where backup is           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Example: big_bro Hourly Health Check

In big_bro's heartbeat, add this logic:

```python
# In heartbeat.py (big_bro)

async def send_health_check_task(pool):
    """Send health check task to public_claude."""
    await pool.execute("""
        INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
        VALUES ('big_bro', 'public_claude', 'task', 'Hourly Health Check', 
                'TASK: docker_ps
PARAMS: {}
REASON: Routine hourly health check', 'normal', 'pending')
    """)

async def request_service_restart(pool, service: str, reason: str):
    """Request a service restart (will go to Craig for approval)."""
    await pool.execute("""
        INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
        VALUES ('big_bro', 'public_claude', 'task', $1, $2, 'high', 'pending')
    """, f"Restart {service}", f"""TASK: restart_service
PARAMS: {{"service": "{service}"}}
REASON: {reason}""")
```

---

## Response Format

When public_claude completes a task, it sends back:

```
✅ SUCCESS

Task: Check Docker health
Result: {
  "success": true,
  "task": "docker_ps",
  "stdout": "NAMES          STATUS         PORTS\ntrading        Up 2 hours     0.0.0.0:5005->5005/tcp\n...",
  "return_code": 0,
  "executed_at": "2025-12-31T12:00:00",
  "executed_by": "public_claude"
}
```

---

## Escalation Flow

If task is NOT whitelisted or requires approval:

1. public_claude sends escalation to craig_mobile
2. Craig sees it on phone dashboard
3. Craig taps Approve/Deny
4. Response flows back to public_claude
5. public_claude executes (if approved)

---

## Testing

### Test 1: Simple Health Check

```sql
-- Send task
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Test: Docker Status', 
        'TASK: docker_ps
PARAMS: {}
REASON: Testing task execution', 'normal', 'pending');

-- Wait for :15 heartbeat, then check response
SELECT * FROM claude_messages WHERE from_agent = 'public_claude' ORDER BY created_at DESC LIMIT 1;
```

### Test 2: Parameterized Task

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Test: Service Health', 
        'TASK: service_health
PARAMS: {"port": "5005"}
REASON: Check trading service', 'normal', 'pending');
```

### Test 3: Restart Service (Executes Immediately)

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Restart Trading Service', 
        'TASK: restart_service
PARAMS: {"service": "trading"}
REASON: Service unresponsive', 'high', 'pending');

-- This will execute immediately - no approval needed
-- big_bro has full restart authority
```

### Test 4: Restart All Services

```sql
INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
VALUES ('big_bro', 'public_claude', 'task', 'Restart All Services', 
        'TASK: restart_all_services
PARAMS: {}
REASON: Full system refresh', 'high', 'pending');
```

---

## Files to Deploy

| File | Location | Purpose |
|------|----------|---------|
| `task_executor.py` | services/consciousness/ | Whitelist and execution |
| `heartbeat_public_v2.py` | services/consciousness/ | Enhanced heartbeat |

---

## Security Notes

1. **Whitelist only** - No arbitrary commands
2. **Parameter validation** - Only allowed values
3. **Timeout limits** - Commands can't hang forever
4. **Output truncation** - Prevent memory issues
5. **Full audit trail** - All tasks logged to messages
6. **Automatic backup** - All file changes backed up
7. **Syntax validation** - Python files checked before commit
8. **Auto-rollback** - Invalid changes automatically reverted

---

## Mandatory Reporting

**Little bros MUST report back to big_bro after EVERY task.** No silent fixes.

### Report Format

```
✅ SUCCESS

## Task: edit_file
**Original Request:** Fix timeout bug

### Result
```
File edited successfully. Backup: /root/catalyst-backups/heartbeat.py.20251231_120000.bak
```

### Change Summary
## File Modified: heartbeat.py
**Path:** /root/catalyst-trading-system/services/consciousness/heartbeat.py
**Time:** 2025-12-31 12:00:00
**Reason:** Timeout too short for slow API responses
**Change:**
- Removed: `timeout=30`
- Added: `timeout=60`

*Changelog automatically updated.*
**Backup:** `/root/catalyst-backups/heartbeat.py.20251231_120000.bak`

**Executed at:** 2025-12-31T12:00:00
**Executed by:** public_claude
```

---

## Auto-Generated Changelog

All successful file changes are automatically logged to:

```
/root/catalyst-trading-system/CHANGELOG-AUTO.md
```

This creates a permanent audit trail of all autonomous code changes.

---

**END OF TASK EXECUTION DOCUMENTATION**
