#!/usr/bin/env python3
"""
Catalyst Trading System - Task Executor
Name of file: task_executor.py
Version: 1.0.0
Last Updated: 2025-12-31
Purpose: Safe command execution for autonomous agents

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
# SAFE COMMAND WHITELIST
# ============================================================================

WHITELIST = {
    # System Health
    "docker_ps": {
        "command": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
        "description": "List running Docker containers",
        "timeout": 30,
    },
    "docker_logs": {
        "command": "docker logs --tail 50 {service}",
        "description": "Get last 50 lines of service logs",
        "params": ["service"],
        "allowed_services": ["trading", "scanner", "workflow", "risk-manager", "orchestration", "pattern", "technical", "news", "reporting"],
        "timeout": 30,
    },
    "service_health": {
        "command": "curl -s http://localhost:{port}/health",
        "description": "Check service health endpoint",
        "params": ["port"],
        "allowed_ports": ["5000", "5001", "5002", "5003", "5004", "5005", "5006", "5008", "5009"],
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
    "catalyst_logs": {
        "command": "tail -100 /var/log/catalyst/{logfile}.log",
        "description": "Read catalyst log files",
        "params": ["logfile"],
        "allowed_logfiles": ["heartbeat", "heartbeat-public", "trading", "error"],
        "timeout": 10,
    },
    "system_logs": {
        "command": "journalctl -u {service} --no-pager -n 50",
        "description": "Read systemd service logs",
        "params": ["service"],
        "allowed_services": ["consciousness-dashboard", "docker"],
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
    
    # Service Control (RESTART ONLY - no stop)
    "restart_service": {
        "command": "docker restart {service}",
        "description": "Restart a Docker service",
        "params": ["service"],
        "allowed_services": ["trading", "scanner", "workflow", "risk-manager", "pattern", "technical", "news", "reporting"],
        "timeout": 60,
    },
    "restart_dashboard": {
        "command": "systemctl restart consciousness-dashboard",
        "description": "Restart consciousness dashboard",
        "timeout": 30,
    },
    "restart_all_services": {
        "command": "docker restart trading scanner workflow risk-manager pattern technical news reporting",
        "description": "Restart all trading services",
        "timeout": 120,
    },
    
    # File Operations (with automatic rollback)
    "write_file": {
        "command": "_internal_write_file",  # Handled by custom function
        "description": "Write a Python file with automatic backup/rollback",
        "params": ["filepath", "content", "reason"],
        "allowed_paths": [
            "/root/catalyst-trading-system/services/",
            "/root/catalyst-trading-system/scripts/",
            "/root/catalyst-intl/src/",
        ],
        "allowed_extensions": [".py", ".sh", ".md"],
        "timeout": 30,
    },
    "edit_file": {
        "command": "_internal_edit_file",  # Handled by custom function
        "description": "Edit a Python file (search/replace) with automatic backup/rollback",
        "params": ["filepath", "old_text", "new_text", "reason"],
        "allowed_paths": [
            "/root/catalyst-trading-system/services/",
            "/root/catalyst-trading-system/scripts/",
            "/root/catalyst-intl/src/",
        ],
        "allowed_extensions": [".py", ".sh"],
        "timeout": 30,
    },
    "rollback_file": {
        "command": "_internal_rollback",  # Handled by custom function
        "description": "Rollback a file to its backup",
        "params": ["filepath"],
        "timeout": 10,
    },
}

# Commands that need Craig's approval even if whitelisted
REQUIRES_APPROVAL = []  # Empty - big_bro has full restart authority


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
        
        backups.sort(reverse=True)  # Most recent first
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
        
        # Validate path
        valid, msg = cls.validate_path(filepath, WHITELIST["write_file"])
        if not valid:
            result["error"] = msg
            return result
        
        # Create backup if file exists
        result["backup_path"] = cls.create_backup(filepath)
        result["is_new_file"] = result["backup_path"] is None
        
        try:
            # Write new content
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)
            
            # Validate Python syntax
            valid, msg = cls.validate_python(filepath)
            if not valid:
                # Rollback!
                if result["backup_path"]:
                    cls.rollback(filepath, result["backup_path"])
                    result["rolled_back"] = True
                else:
                    os.remove(filepath)  # Remove invalid new file
                    result["rolled_back"] = True
                result["error"] = f"Validation failed, rolled back: {msg}"
                return result
            
            result["success"] = True
            result["requires_doc_update"] = True  # Flag for documentation
            result["message"] = f"File written successfully. Backup: {result['backup_path']}"
            result["summary"] = cls._generate_change_summary(filepath, None, content, reason)
            return result
            
        except Exception as e:
            # Rollback on any error
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
        
        # Validate path
        valid, msg = cls.validate_path(filepath, WHITELIST["edit_file"])
        if not valid:
            result["error"] = msg
            return result
        
        # File must exist
        if not os.path.exists(filepath):
            result["error"] = f"File not found: {filepath}"
            return result
        
        # Read current content
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Check old_text exists exactly once
        count = content.count(old_text)
        if count == 0:
            result["error"] = f"Text to replace not found in file"
            return result
        if count > 1:
            result["error"] = f"Text to replace found {count} times (must be unique)"
            return result
        
        # Create backup
        result["backup_path"] = cls.create_backup(filepath)
        
        try:
            # Make replacement
            new_content = content.replace(old_text, new_text, 1)
            
            with open(filepath, 'w') as f:
                f.write(new_content)
            
            # Validate Python syntax
            valid, msg = cls.validate_python(filepath)
            if not valid:
                # Rollback!
                cls.rollback(filepath, result["backup_path"])
                result["rolled_back"] = True
                result["error"] = f"Validation failed, rolled back: {msg}"
                return result
            
            result["success"] = True
            result["requires_doc_update"] = True  # Flag for documentation
            result["message"] = f"File edited successfully. Backup: {result['backup_path']}"
            result["old_text_preview"] = old_text[:100] + "..." if len(old_text) > 100 else old_text
            result["new_text_preview"] = new_text[:100] + "..." if len(new_text) > 100 else new_text
            result["summary"] = cls._generate_change_summary(filepath, old_text, new_text, reason)
            return result
            
        except Exception as e:
            # Rollback on any error
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
            # New file
            summary = f"""## File Created: {filename}
**Path:** {filepath}
**Time:** {timestamp}
**Reason:** {reason}
**Action:** New file created ({len(new_text)} characters)
"""
        else:
            # Edit
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
        """Check if task is in whitelist."""
        return task_name in WHITELIST
    
    def requires_approval(self, task_name: str) -> bool:
        """Check if task requires Craig's approval."""
        return task_name in REQUIRES_APPROVAL
    
    def validate_params(self, task_name: str, params: dict) -> Tuple[bool, str]:
        """Validate task parameters against allowed values."""
        task_def = WHITELIST.get(task_name)
        if not task_def:
            return False, f"Task '{task_name}' not in whitelist"
        
        required_params = task_def.get("params", [])
        
        for param in required_params:
            # 'reason' is always optional (can come from REASON line in message)
            if param == "reason":
                continue
                
            if param not in params:
                return False, f"Missing required parameter: {param}"
            
            # Check against allowed values if specified
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
        
        # Validate
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
        
        # Check if requires approval
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
            # Build environment with required variables
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
                "stdout": result.stdout[:2000] if result.stdout else "",  # Limit output
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
    """Parse a task message body into executable format.
    
    Expected format in message body:
    TASK: task_name
    PARAMS: {"key": "value"}
    REASON: why this is needed
    """
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
    import asyncio
    
    async def test():
        executor = TaskExecutor("test_agent")
        
        # Test safe commands
        print("=== Testing Safe Commands ===")
        
        result = await executor.execute("docker_ps")
        print(f"docker_ps: {result['success']}")
        
        result = await executor.execute("disk_space")
        print(f"disk_space: {result['success']}")
        
        result = await executor.execute("memory_usage")
        print(f"memory_usage: {result['success']}")
        
        # Test parameterized command
        result = await executor.execute("service_health", {"port": "5000"})
        print(f"service_health: {result['success']}")
        
        # Test invalid param
        result = await executor.execute("service_health", {"port": "9999"})
        print(f"service_health (bad port): {result}")
        
        # Test non-whitelisted
        result = await executor.execute("rm_rf")
        print(f"rm_rf (should fail): {result}")
        
        # Test file operations
        print("\n=== Testing File Operations ===")
        
        # Test write (to allowed path simulation)
        test_content = '''#!/usr/bin/env python3
"""Test file"""
print("Hello")
'''
        # This would fail in test because path doesn't exist
        # result = await executor.execute("write_file", {
        #     "filepath": "/root/catalyst-trading-system/services/test_file.py",
        #     "content": test_content
        # })
        # print(f"write_file: {result}")
        
        # Test path validation
        result = await executor.execute("write_file", {
            "filepath": "/etc/passwd",
            "content": "hacked"
        })
        print(f"write_file (bad path - should fail): {result}")
        
        result = await executor.execute("write_file", {
            "filepath": "/root/catalyst-trading-system/services/../../../etc/passwd",
            "content": "hacked"
        })
        print(f"write_file (path traversal - should fail): {result}")
    
    asyncio.run(test())
