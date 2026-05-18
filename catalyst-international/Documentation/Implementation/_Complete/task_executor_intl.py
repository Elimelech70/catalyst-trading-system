#!/usr/bin/env python3
"""
Catalyst Trading System - Task Executor (INTL)
Name of file: task_executor_intl.py
Version: 1.0.0
Last Updated: 2025-12-31
Purpose: Safe command execution for INTL droplet (HKEX trading)

WHITELIST ONLY - Commands not on list require Craig approval via dashboard
"""

import subprocess
import asyncio
import json
import re
import os
import shutil
import py_compile
from datetime import datetime
from typing import Optional, Tuple

# ============================================================================
# SAFE COMMAND WHITELIST (INTL DROPLET)
# ============================================================================

WHITELIST = {
    # System Health
    "check_agent": {
        "command": "ps aux | grep -E 'agent.py|python.*agent' | grep -v grep",
        "description": "Check if agent.py is running",
        "timeout": 10,
    },
    "check_opend": {
        "command": "ps aux | grep -E 'OpenD|opend' | grep -v grep",
        "description": "Check if OpenD gateway is running",
        "timeout": 10,
    },
    "opend_status": {
        "command": "systemctl status opend --no-pager",
        "description": "OpenD service status",
        "timeout": 10,
    },
    "disk_space": {
        "command": "df -h /",
        "description": "Check disk space",
        "timeout": 10,
    },
    "memory_usage": {
        "command": "free -m",
        "description": "Check memory usage",
        "timeout": 10,
    },
    "process_list": {
        "command": "ps aux --sort=-%mem | head -10",
        "description": "Top 10 processes by memory",
        "timeout": 10,
    },
    
    # Logs
    "agent_logs": {
        "command": "tail -100 /root/catalyst-intl/logs/{logfile}.log",
        "description": "Read agent log files",
        "params": ["logfile"],
        "allowed_logfiles": ["agent", "trading", "error", "decisions"],
        "timeout": 10,
    },
    "system_logs": {
        "command": "journalctl -u {service} --no-pager -n 50",
        "description": "Read systemd service logs",
        "params": ["service"],
        "allowed_services": ["opend", "catalyst-agent"],
        "timeout": 15,
    },
    
    # Database (READ ONLY)
    "db_agent_status": {
        "command": "psql \"$RESEARCH_DATABASE_URL\" -c \"SELECT agent_id, current_mode, api_spend_today, status_message FROM claude_state;\"",
        "description": "Check agent status from database",
        "timeout": 15,
    },
    "db_pending_messages": {
        "command": "psql \"$RESEARCH_DATABASE_URL\" -c \"SELECT COUNT(*) as pending FROM claude_messages WHERE status='pending';\"",
        "description": "Count pending messages",
        "timeout": 10,
    },
    "db_recent_observations": {
        "command": "psql \"$RESEARCH_DATABASE_URL\" -c \"SELECT agent_id, subject, created_at FROM claude_observations ORDER BY created_at DESC LIMIT 5;\"",
        "description": "Recent observations",
        "timeout": 10,
    },
    "db_positions": {
        "command": "psql \"$INTL_DATABASE_URL\" -c \"SELECT symbol, quantity, avg_price, unrealized_pnl FROM positions WHERE status='open';\"",
        "description": "Current HKEX positions",
        "timeout": 10,
    },
    
    # Service Control
    "restart_opend": {
        "command": "systemctl restart opend",
        "description": "Restart OpenD gateway",
        "timeout": 60,
    },
    "restart_agent": {
        "command": "systemctl restart catalyst-agent",
        "description": "Restart catalyst agent service",
        "timeout": 30,
    },
    "start_opend": {
        "command": "systemctl start opend",
        "description": "Start OpenD gateway",
        "timeout": 60,
    },
    "stop_agent": {
        "command": "systemctl stop catalyst-agent",
        "description": "Stop catalyst agent (for maintenance)",
        "timeout": 30,
    },
    
    # File Operations (with automatic rollback)
    "write_file": {
        "command": "_internal_write_file",
        "description": "Write a Python file with automatic backup/rollback",
        "params": ["filepath", "content", "reason"],
        "allowed_paths": [
            "/root/catalyst-intl/src/",
            "/root/catalyst-intl/scripts/",
            "/root/catalyst-intl/config/",
        ],
        "allowed_extensions": [".py", ".sh", ".md", ".json"],
        "timeout": 30,
    },
    "edit_file": {
        "command": "_internal_edit_file",
        "description": "Edit a Python file (search/replace) with automatic backup/rollback",
        "params": ["filepath", "old_text", "new_text", "reason"],
        "allowed_paths": [
            "/root/catalyst-intl/src/",
            "/root/catalyst-intl/scripts/",
            "/root/catalyst-intl/config/",
        ],
        "allowed_extensions": [".py", ".sh", ".json"],
        "timeout": 30,
    },
    "rollback_file": {
        "command": "_internal_rollback",
        "description": "Rollback a file to its backup",
        "params": ["filepath"],
        "timeout": 10,
    },
}

# Commands that need Craig's approval even if whitelisted
REQUIRES_APPROVAL = []  # Empty - big_bro has full authority


# ============================================================================
# FILE OPERATIONS WITH ROLLBACK
# ============================================================================

BACKUP_DIR = "/root/catalyst-backups"

class FileEditor:
    """Safe file editing with automatic backup and rollback."""
    
    @staticmethod
    def validate_path(filepath: str, task_def: dict) -> Tuple[bool, str]:
        """Check if filepath is allowed."""
        allowed_paths = task_def.get("allowed_paths", [])
        allowed_extensions = task_def.get("allowed_extensions", [])
        
        # Check path prefix
        path_ok = any(filepath.startswith(p) for p in allowed_paths)
        if not path_ok:
            return False, f"Path not allowed. Must be in: {allowed_paths}"
        
        # Check extension
        ext_ok = any(filepath.endswith(e) for e in allowed_extensions)
        if not ext_ok:
            return False, f"Extension not allowed. Must be: {allowed_extensions}"
        
        # Block dangerous patterns
        if ".." in filepath or "~" in filepath:
            return False, "Path traversal not allowed"
        
        return True, "OK"
    
    @staticmethod
    def create_backup(filepath: str) -> Optional[str]:
        """Create backup of existing file. Returns backup path."""
        if not os.path.exists(filepath):
            return None
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(filepath)
        backup_path = f"{BACKUP_DIR}/{filename}.{timestamp}.bak"
        
        shutil.copy2(filepath, backup_path)
        return backup_path
    
    @staticmethod
    def validate_python(filepath: str) -> Tuple[bool, str]:
        """Check Python syntax."""
        if not filepath.endswith(".py"):
            return True, "Not a Python file, skipping syntax check"
        
        try:
            py_compile.compile(filepath, doraise=True)
            return True, "Syntax OK"
        except py_compile.PyCompileError as e:
            return False, f"Syntax error: {e}"
    
    @staticmethod
    def rollback(filepath: str, backup_path: str) -> bool:
        """Restore file from backup."""
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, filepath)
            return True
        return False
    
    @staticmethod
    def get_latest_backup(filepath: str) -> Optional[str]:
        """Find the most recent backup for a file."""
        if not os.path.exists(BACKUP_DIR):
            return None
        
        filename = os.path.basename(filepath)
        backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith(filename) and f.endswith(".bak")]
        
        if not backups:
            return None
        
        backups.sort(reverse=True)
        return f"{BACKUP_DIR}/{backups[0]}"
    
    @classmethod
    def write_file(cls, filepath: str, content: str, reason: str = "") -> dict:
        """Write file with backup and validation."""
        result = {
            "filepath": filepath,
            "operation": "write",
            "backup_path": None,
            "success": False,
            "rolled_back": False,
            "reason": reason,
            "requires_doc_update": False,
        }
        
        valid, msg = cls.validate_path(filepath, WHITELIST["write_file"])
        if not valid:
            result["error"] = msg
            return result
        
        result["backup_path"] = cls.create_backup(filepath)
        result["is_new_file"] = result["backup_path"] is None
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)
            
            valid, msg = cls.validate_python(filepath)
            if not valid:
                if result["backup_path"]:
                    cls.rollback(filepath, result["backup_path"])
                    result["rolled_back"] = True
                else:
                    os.remove(filepath)
                    result["rolled_back"] = True
                result["error"] = f"Validation failed, rolled back: {msg}"
                return result
            
            result["success"] = True
            result["requires_doc_update"] = True
            result["message"] = f"File written successfully. Backup: {result['backup_path']}"
            result["summary"] = cls._generate_change_summary(filepath, None, content, reason)
            return result
            
        except Exception as e:
            if result["backup_path"]:
                cls.rollback(filepath, result["backup_path"])
                result["rolled_back"] = True
            result["error"] = f"Write failed, rolled back: {e}"
            return result
    
    @classmethod
    def edit_file(cls, filepath: str, old_text: str, new_text: str, reason: str = "") -> dict:
        """Edit file (search/replace) with backup and validation."""
        result = {
            "filepath": filepath,
            "operation": "edit",
            "backup_path": None,
            "success": False,
            "rolled_back": False,
            "reason": reason,
            "requires_doc_update": False,
        }
        
        valid, msg = cls.validate_path(filepath, WHITELIST["edit_file"])
        if not valid:
            result["error"] = msg
            return result
        
        if not os.path.exists(filepath):
            result["error"] = f"File not found: {filepath}"
            return result
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        count = content.count(old_text)
        if count == 0:
            result["error"] = f"Text to replace not found in file"
            return result
        if count > 1:
            result["error"] = f"Text to replace found {count} times (must be unique)"
            return result
        
        result["backup_path"] = cls.create_backup(filepath)
        
        try:
            new_content = content.replace(old_text, new_text, 1)
            
            with open(filepath, 'w') as f:
                f.write(new_content)
            
            valid, msg = cls.validate_python(filepath)
            if not valid:
                cls.rollback(filepath, result["backup_path"])
                result["rolled_back"] = True
                result["error"] = f"Validation failed, rolled back: {msg}"
                return result
            
            result["success"] = True
            result["requires_doc_update"] = True
            result["message"] = f"File edited successfully. Backup: {result['backup_path']}"
            result["old_text_preview"] = old_text[:100] + "..." if len(old_text) > 100 else old_text
            result["new_text_preview"] = new_text[:100] + "..." if len(new_text) > 100 else new_text
            result["summary"] = cls._generate_change_summary(filepath, old_text, new_text, reason)
            return result
            
        except Exception as e:
            if result["backup_path"]:
                cls.rollback(filepath, result["backup_path"])
                result["rolled_back"] = True
            result["error"] = f"Edit failed, rolled back: {e}"
            return result
    
    @classmethod
    def _generate_change_summary(cls, filepath: str, old_text: Optional[str], new_text: str, reason: str) -> str:
        """Generate a summary of the change for documentation."""
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if old_text is None:
            summary = f"""## File Created: {filename}
**Path:** {filepath}
**Time:** {timestamp}
**Reason:** {reason}
**Action:** New file created ({len(new_text)} characters)
"""
        else:
            summary = f"""## File Modified: {filename}
**Path:** {filepath}
**Time:** {timestamp}
**Reason:** {reason}
**Change:**
- Removed: `{old_text[:50]}{'...' if len(old_text) > 50 else ''}`
- Added: `{new_text[:50]}{'...' if len(new_text) > 50 else ''}`
"""
        return summary
    
    @classmethod
    def manual_rollback(cls, filepath: str) -> dict:
        """Manually rollback to latest backup."""
        result = {
            "filepath": filepath,
            "operation": "rollback",
            "success": False,
        }
        
        backup_path = cls.get_latest_backup(filepath)
        if not backup_path:
            result["error"] = f"No backup found for {filepath}"
            return result
        
        try:
            shutil.copy2(backup_path, filepath)
            result["success"] = True
            result["message"] = f"Rolled back to: {backup_path}"
            result["backup_used"] = backup_path
            return result
        except Exception as e:
            result["error"] = f"Rollback failed: {e}"
            return result


# ============================================================================
# TASK EXECUTOR
# ============================================================================

class TaskExecutor:
    """Execute whitelisted tasks safely."""
    
    def __init__(self, agent_id: str, db_pool=None):
        self.agent_id = agent_id
        self.pool = db_pool
    
    def is_whitelisted(self, task_name: str) -> bool:
        return task_name in WHITELIST
    
    def requires_approval(self, task_name: str) -> bool:
        return task_name in REQUIRES_APPROVAL
    
    def validate_params(self, task_name: str, params: dict) -> Tuple[bool, str]:
        """Validate task parameters against allowed values."""
        task_def = WHITELIST.get(task_name)
        if not task_def:
            return False, f"Task '{task_name}' not in whitelist"
        
        required_params = task_def.get("params", [])
        
        for param in required_params:
            if param == "reason":
                continue
                
            if param not in params:
                return False, f"Missing required parameter: {param}"
            
            allowed_key = f"allowed_{param}s"
            if allowed_key in task_def:
                if params[param] not in task_def[allowed_key]:
                    return False, f"Parameter '{param}' value '{params[param]}' not allowed. Allowed: {task_def[allowed_key]}"
        
        return True, "OK"
    
    def build_command(self, task_name: str, params: dict = None) -> str:
        """Build the actual command string."""
        task_def = WHITELIST[task_name]
        command = task_def["command"]
        
        if params:
            command = command.format(**params)
        
        return command
    
    async def execute(self, task_name: str, params: dict = None, reason: str = None) -> dict:
        """Execute a whitelisted task."""
        
        params = params or {}
        
        if not self.is_whitelisted(task_name):
            return {
                "success": False,
                "error": f"Task '{task_name}' not whitelisted",
                "requires_escalation": True,
            }
        
        valid, msg = self.validate_params(task_name, params)
        if not valid:
            return {
                "success": False,
                "error": msg,
            }
        
        task_def = WHITELIST[task_name]
        if task_def.get("requires_reason") and not reason:
            return {
                "success": False,
                "error": f"Task '{task_name}' requires a reason",
            }
        
        # Handle internal file operations
        if task_def["command"].startswith("_internal_"):
            return await self._execute_file_operation(task_name, params)
        
        # Build and execute shell command
        command = self.build_command(task_name, params)
        timeout = task_def.get("timeout", 30)
        
        try:
            env = os.environ.copy()
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            return {
                "success": result.returncode == 0,
                "task": task_name,
                "command": command,
                "stdout": result.stdout[:2000] if result.stdout else "",
                "stderr": result.stderr[:500] if result.stderr else "",
                "return_code": result.returncode,
                "executed_at": datetime.utcnow().isoformat(),
                "executed_by": self.agent_id,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "task": task_name,
                "error": f"Command timed out after {timeout}s",
            }
        except Exception as e:
            return {
                "success": False,
                "task": task_name,
                "error": str(e),
            }
    
    async def _execute_file_operation(self, task_name: str, params: dict) -> dict:
        """Execute file write/edit operations with rollback."""
        
        reason = params.get("reason", "No reason provided")
        
        if task_name == "write_file":
            filepath = params.get("filepath")
            content = params.get("content")
            if not filepath or not content:
                return {"success": False, "error": "Missing filepath or content"}
            return FileEditor.write_file(filepath, content, reason)
        
        elif task_name == "edit_file":
            filepath = params.get("filepath")
            old_text = params.get("old_text")
            new_text = params.get("new_text")
            if not all([filepath, old_text, new_text]):
                return {"success": False, "error": "Missing filepath, old_text, or new_text"}
            return FileEditor.edit_file(filepath, old_text, new_text, reason)
        
        elif task_name == "rollback_file":
            filepath = params.get("filepath")
            if not filepath:
                return {"success": False, "error": "Missing filepath"}
            return FileEditor.manual_rollback(filepath)
        
        return {"success": False, "error": f"Unknown file operation: {task_name}"}
    
    async def request_approval(self, task_name: str, params: dict = None, reason: str = None) -> int:
        """Send approval request to Craig via dashboard."""
        if not self.pool:
            return -1
        
        task_def = WHITELIST.get(task_name, {"description": task_name})
        command = self.build_command(task_name, params) if task_name in WHITELIST else task_name
        
        body = f"""Task: {task_name}
Command: {command}
Description: {task_def.get('description', 'N/A')}
Reason: {reason or 'Not provided'}
Requested by: {self.agent_id}"""
        
        async with self.pool.acquire() as conn:
            msg_id = await conn.fetchval("""
                INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, 'craig_mobile', 'escalation', $2, $3, 'high', 'pending')
                RETURNING id
            """, self.agent_id, f"Permission: {task_name}", body)
        
        return msg_id


# ============================================================================
# TASK PARSER
# ============================================================================

def parse_task_message(body: str) -> dict:
    """Parse a task message body into executable format."""
    task = {"task_name": None, "params": {}, "reason": None}
    
    lines = body.strip().split('\n')
    for line in lines:
        if line.startswith('TASK:'):
            task["task_name"] = line.replace('TASK:', '').strip()
        elif line.startswith('PARAMS:'):
            try:
                task["params"] = json.loads(line.replace('PARAMS:', '').strip())
            except:
                pass
        elif line.startswith('REASON:'):
            task["reason"] = line.replace('REASON:', '').strip()
    
    return task


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    async def test():
        executor = TaskExecutor("test_agent")
        
        print("=== Testing INTL Commands ===")
        
        result = await executor.execute("check_opend")
        print(f"check_opend: {result['success']}")
        
        result = await executor.execute("disk_space")
        print(f"disk_space: {result['success']}")
        
        result = await executor.execute("db_positions")
        print(f"db_positions: {result['success']}")
        
        # Test path validation
        result = await executor.execute("write_file", {
            "filepath": "/etc/passwd",
            "content": "hacked"
        })
        print(f"write_file (bad path - should fail): {result}")
    
    asyncio.run(test())
