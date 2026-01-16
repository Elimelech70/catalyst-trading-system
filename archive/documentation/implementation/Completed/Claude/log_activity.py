#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: log_activity.py
Version: 1.0.0
Last Updated: 2025-12-27
Purpose: Log Claude Code (Doctor Claude) activities to database

REVISION HISTORY:
v1.0.0 (2025-12-27) - Initial implementation
- Insert activity logs to claude_activity_log table
- Support all observation, decision, and action fields
- Auto-generate session ID if not provided
- JSON support for complex fields

Usage:
    # Log a simple observation
    python3 log_activity.py --type watchdog_run --decision no_action
    
    # Log with full details
    python3 log_activity.py \\
        --type watchdog_run \\
        --summary '{"status":"OK","issues":0}' \\
        --decision auto_fix \\
        --reasoning "ORDER_STATUS_MISMATCH is safe to auto-fix" \\
        --action-type sql_update \\
        --action "UPDATE orders SET status = 'filled' WHERE order_id = 'xyz'" \\
        --target orders \\
        --result success \\
        --issue-type ORDER_STATUS_MISMATCH \\
        --severity WARNING
    
    # Log session start
    python3 log_activity.py --type startup --decision no_action --reasoning "Beginning monitoring"
    
    # Log session end
    python3 log_activity.py --type shutdown --decision no_action

Exit Codes:
    0 = Success
    1 = Failure

Dependencies:
    pip install asyncpg

Environment Variables:
    DATABASE_URL - PostgreSQL connection string
"""

import asyncio
import asyncpg
import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional


DATABASE_URL = os.environ.get('DATABASE_URL')


async def log_activity(
    observation_type: str,
    observation_summary: Optional[dict] = None,
    issues_found: int = 0,
    critical_count: int = 0,
    warning_count: int = 0,
    decision: Optional[str] = None,
    decision_reasoning: Optional[str] = None,
    action_type: Optional[str] = None,
    action_detail: Optional[str] = None,
    action_target: Optional[str] = None,
    action_result: Optional[str] = None,
    error_message: Optional[str] = None,
    issue_type: Optional[str] = None,
    issue_severity: Optional[str] = None,
    fix_duration_ms: Optional[int] = None,
    watchdog_duration_ms: Optional[int] = None,
    cycle_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> bool:
    """
    Insert activity log entry into database.
    
    Args:
        observation_type: Type of observation (watchdog_run, manual_check, startup, shutdown, etc.)
        observation_summary: JSON dict with observation details
        issues_found: Total count of issues found
        critical_count: Count of critical severity issues
        warning_count: Count of warning severity issues
        decision: Decision made (auto_fix, escalate, monitor, no_action, defer)
        decision_reasoning: Explanation of why this decision was made
        action_type: Type of action taken (sql_update, api_call, alert_sent, none)
        action_detail: The actual command/query executed
        action_target: What was acted upon (table name, service, etc.)
        action_result: Result of action (success, failed, partial, pending, skipped)
        error_message: Error details if action failed
        issue_type: Issue taxonomy classification
        issue_severity: Issue severity (CRITICAL, WARNING, INFO)
        fix_duration_ms: How long the fix took in milliseconds
        watchdog_duration_ms: How long the watchdog diagnostic took
        cycle_id: Trading cycle UUID if applicable
        session_id: Claude session identifier (auto-generated if not provided)
        metadata: Additional context as JSON
    
    Returns:
        bool: True if logged successfully, False otherwise
    """
    
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set", file=sys.stderr)
        return False
    
    # Generate session_id if not provided (date-based)
    if not session_id:
        session_id = f"claude-{datetime.now().strftime('%Y%m%d')}"
    
    conn = None
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Check if table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'claude_activity_log'
            )
        """)
        
        if not table_exists:
            print("ERROR: claude_activity_log table does not exist. Run doctor-claude-schema.sql first.", file=sys.stderr)
            return False
        
        await conn.execute("""
            INSERT INTO claude_activity_log (
                session_id, cycle_id,
                observation_type, observation_summary, 
                issues_found, critical_count, warning_count,
                decision, decision_reasoning,
                action_type, action_detail, action_target, action_result,
                error_message, issue_type, issue_severity,
                fix_duration_ms, watchdog_duration_ms, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
            )
        """,
            session_id,
            cycle_id,
            observation_type,
            json.dumps(observation_summary) if observation_summary else None,
            issues_found,
            critical_count,
            warning_count,
            decision,
            decision_reasoning,
            action_type,
            action_detail,
            action_target,
            action_result,
            error_message,
            issue_type,
            issue_severity,
            fix_duration_ms,
            watchdog_duration_ms,
            json.dumps(metadata) if metadata else None
        )
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to log activity: {str(e)}", file=sys.stderr)
        return False
        
    finally:
        if conn:
            await conn.close()


async def get_recent_activity(limit: int = 10) -> list:
    """Get recent activity log entries for verification."""
    if not DATABASE_URL:
        return []
    
    conn = None
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT 
                logged_at,
                observation_type,
                decision,
                action_type,
                action_result,
                issue_type
            FROM claude_activity_log
            ORDER BY logged_at DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        return []
    finally:
        if conn:
            await conn.close()


async def main():
    parser = argparse.ArgumentParser(
        description='Log Doctor Claude activities to database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Log watchdog run with no issues
  python3 log_activity.py --type watchdog_run --decision no_action
  
  # Log an auto-fix action
  python3 log_activity.py --type watchdog_run --decision auto_fix \\
      --action-type sql_update --action "UPDATE orders SET..." --result success
  
  # Log session start
  python3 log_activity.py --type startup --decision no_action
  
  # View recent activity
  python3 log_activity.py --view
        """
    )
    
    # View mode
    parser.add_argument('--view', action='store_true', help='View recent activity logs')
    parser.add_argument('--limit', type=int, default=10, help='Number of records to view (with --view)')
    
    # Required for logging
    parser.add_argument('--type', dest='obs_type', help='Observation type (watchdog_run, startup, shutdown, manual_check)')
    
    # Observation details
    parser.add_argument('--summary', help='Observation summary as JSON string')
    parser.add_argument('--issues', type=int, default=0, help='Total issues found')
    parser.add_argument('--critical', type=int, default=0, help='Critical issue count')
    parser.add_argument('--warnings', type=int, default=0, help='Warning count')
    
    # Decision
    parser.add_argument('--decision', help='Decision made (auto_fix, escalate, monitor, no_action, defer)')
    parser.add_argument('--reasoning', help='Decision reasoning')
    
    # Action
    parser.add_argument('--action-type', help='Action type (sql_update, api_call, alert_sent, none)')
    parser.add_argument('--action', help='Action detail/command')
    parser.add_argument('--target', help='Action target (table, service)')
    parser.add_argument('--result', help='Action result (success, failed, partial, pending, skipped)')
    parser.add_argument('--error', help='Error message if failed')
    
    # Issue classification
    parser.add_argument('--issue-type', help='Issue type (ORDER_STATUS_MISMATCH, PHANTOM_POSITION, etc.)')
    parser.add_argument('--severity', help='Issue severity (CRITICAL, WARNING, INFO)')
    
    # Timing
    parser.add_argument('--fix-ms', type=int, help='Fix duration in milliseconds')
    parser.add_argument('--watchdog-ms', type=int, help='Watchdog run duration in milliseconds')
    
    # Context
    parser.add_argument('--cycle-id', help='Trading cycle UUID')
    parser.add_argument('--session-id', help='Claude session ID (auto-generated if not provided)')
    parser.add_argument('--metadata', help='Additional metadata as JSON string')
    
    args = parser.parse_args()
    
    # View mode
    if args.view:
        activity = await get_recent_activity(args.limit)
        if activity:
            print(json.dumps(activity, indent=2, default=str))
        else:
            print("No activity logs found or error occurred.")
        sys.exit(0)
    
    # Logging mode - require observation type
    if not args.obs_type:
        parser.error("--type is required when logging activity")
    
    # Parse JSON arguments
    summary = None
    if args.summary:
        try:
            summary = json.loads(args.summary)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in --summary: {e}", file=sys.stderr)
            sys.exit(1)
    
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in --metadata: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Log the activity
    success = await log_activity(
        observation_type=args.obs_type,
        observation_summary=summary,
        issues_found=args.issues,
        critical_count=args.critical,
        warning_count=args.warnings,
        decision=args.decision,
        decision_reasoning=args.reasoning,
        action_type=args.action_type,
        action_detail=args.action,
        action_target=args.target,
        action_result=args.result,
        error_message=args.error,
        issue_type=args.issue_type,
        issue_severity=args.severity,
        fix_duration_ms=args.fix_ms,
        watchdog_duration_ms=args.watchdog_ms,
        cycle_id=args.cycle_id,
        session_id=args.session_id,
        metadata=metadata
    )
    
    if success:
        print(json.dumps({
            "status": "success",
            "message": "Activity logged successfully",
            "timestamp": datetime.now().isoformat(),
            "observation_type": args.obs_type,
            "decision": args.decision
        }))
        sys.exit(0)
    else:
        print(json.dumps({
            "status": "failed",
            "message": "Failed to log activity"
        }))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
