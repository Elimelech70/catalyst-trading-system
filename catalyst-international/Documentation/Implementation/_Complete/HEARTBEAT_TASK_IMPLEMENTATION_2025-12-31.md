# Heartbeat & Task Executor Implementation - 2025-12-31

**Version:** 1.0.0
**Status:** IMPLEMENTED & TESTED

---

## Overview

Implemented the autonomous heartbeat and task execution system for `intl_claude` on the INTL droplet.

## Files Deployed

| File | Location | Lines | Purpose |
|------|----------|-------|---------|
| `heartbeat_intl.py` | `scripts/` | 321 | Autonomous heartbeat with task processing |
| `task_executor_intl.py` | `scripts/` | 619 | Whitelisted safe command execution |

## Path Updates

Updated all paths from `/root/catalyst-intl/` to actual project path:
```
/root/Catalyst-Trading-System-International/catalyst-international/
```

### Specific Changes

1. **CHANGELOG_PATH** (heartbeat_intl.py:29)
   - From: `/root/catalyst-intl/CHANGELOG-AUTO.md`
   - To: `/root/Catalyst-Trading-System-International/catalyst-international/CHANGELOG-AUTO.md`

2. **agent_logs command** (task_executor_intl.py:61)
   - Updated log path to actual location
   - Added `cron` and `report` to allowed logfiles

3. **allowed_paths for file operations** (task_executor_intl.py:124-140)
   - Updated to actual project directories:
     - `scripts/`
     - `config/`
     - `brokers/`

## Test Results

### Task Executor
```
=== Testing INTL Commands ===
check_opend: True ✓
disk_space: True ✓
db_positions: False (INTL_DATABASE_URL not set - expected)
write_file (bad path): Properly rejected ✓
```

### Heartbeat
```
[2025-12-31 13:08:56] intl_claude waking up...
Processing message #14 from craig_desktop: Direction: Trading first
Processing message #34 from craig_desktop: Request: Today's HKEX Trading Report
Processing message #43 from craig_mobile: Request: Daily Report
Processing message #18 from craig_desktop: Task: Repository cleanup
Processing message #52 from craig_desktop: Cron schedule
[2025-12-31 13:09:02] Cycle complete. Cost: $0.0001
```

## Whitelisted Tasks

### System Health
- `check_agent` - Agent process status
- `check_opend` - OpenD gateway status
- `opend_status` - Systemd service status
- `disk_space` - Disk usage
- `memory_usage` - RAM usage
- `process_list` - Top processes

### Logs
- `agent_logs` - Agent log files (cron, report, trading, etc.)
- `system_logs` - Journalctl service logs

### Database (Read Only)
- `db_agent_status` - Agent states
- `db_pending_messages` - Message queue
- `db_recent_observations` - Observations
- `db_positions` - HKEX positions

### Service Control
- `restart_opend` - Restart OpenD
- `restart_agent` - Restart agent
- `start_opend` / `stop_agent` - Service management

### File Operations (Auto-Rollback)
- `write_file` - Create file with backup
- `edit_file` - Search/replace with backup
- `rollback_file` - Restore from backup

## Architecture

```
big_bro (US) ──► claude_messages ──► intl_claude heartbeat
                     │                      │
                     │ msg_type='task'      │ Process tasks
                     │ TASK: disk_space     │ Execute whitelisted
                     │ PARAMS: {}           │ Report results
                     │                      │
                     ◄──────────────────────┘
```

## Cron Integration

To enable scheduled heartbeat, add to crontab:
```bash
# intl_claude heartbeat - every 15 mins
*/15 * * * * cd /root/Catalyst-Trading-System-International/catalyst-international && source venv/bin/activate && source .env && python3 scripts/heartbeat_intl.py >> logs/heartbeat.log 2>&1
```

## Security Features

1. **Whitelist only** - No arbitrary commands
2. **Parameter validation** - Only allowed values
3. **Path restrictions** - Only project directories
4. **Automatic backup** - Before file changes
5. **Python syntax check** - Validates .py files
6. **Auto-rollback** - Reverts invalid changes
7. **Escalation** - Non-whitelisted → craig_mobile

---

**Implementation Complete**
