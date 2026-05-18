#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: apply_workflow_fixes.py
Version: 1.0.0
Last Updated: 2026-01-20
Purpose: Apply critical workflow fixes to unified_agent.py

REVISION HISTORY:
v1.0.0 (2026-01-20) - Initial implementation
  - Fix missing DECIDE phase mapping
  - Fix missing MONITOR phase trigger
  - Add VALIDATE phase after check_risk

Usage:
    cd /root/Catalyst-Trading-System-International/catalyst-international
    python3 apply_workflow_fixes.py

Or manually apply the str_replace operations below.
"""

import re
import shutil
from pathlib import Path
from datetime import datetime

UNIFIED_AGENT_PATH = Path("unified_agent.py")
BACKUP_SUFFIX = f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def backup_file(filepath: Path) -> Path:
    """Create a backup of the file."""
    backup_path = filepath.with_suffix(filepath.suffix + BACKUP_SUFFIX)
    shutil.copy2(filepath, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def apply_fix_1_tool_to_phase(content: str) -> str:
    """Fix #1: Update _tool_to_phase() to map check_risk to DECIDE."""
    
    old_phase_map = '''    def _tool_to_phase(self, tool_name: str, current_phase: str) -> str:
        """Map tool name to workflow phase."""
        phase_map = {
            "get_portfolio": "PORTFOLIO",
            "scan_market": "SCAN",
            "get_quote": "ANALYZE",
            "get_technicals": "ANALYZE",
            "detect_patterns": "ANALYZE",
            "get_news": "ANALYZE",
            "check_risk": "VALIDATE",
            "execute_trade": "EXECUTE",
            "close_position": "EXECUTE",
            "close_all": "EXECUTE",
            "send_alert": "LOG",
            "log_decision": "LOG",
        }

        new_phase = phase_map.get(tool_name, current_phase)

        # Don't go backwards in phases
        current_idx = WORKFLOW_PHASES.index(current_phase) if current_phase in WORKFLOW_PHASES else 0
        new_idx = WORKFLOW_PHASES.index(new_phase) if new_phase in WORKFLOW_PHASES else current_idx

        return new_phase if new_idx >= current_idx else current_phase'''

    new_phase_map = '''    def _tool_to_phase(self, tool_name: str, current_phase: str) -> str:
        """Map tool name to workflow phase.
        
        Phase order: INIT → PORTFOLIO → SCAN → ANALYZE → DECIDE → VALIDATE → EXECUTE → MONITOR → LOG → COMPLETE
        
        Note: DECIDE phase is triggered when check_risk is called (decision has been made).
        MONITOR phase is triggered after successful trade execution in the tool loop.
        """
        phase_map = {
            "get_portfolio": "PORTFOLIO",
            "scan_market": "SCAN",
            "get_quote": "ANALYZE",
            "get_technicals": "ANALYZE",
            "detect_patterns": "ANALYZE",
            "get_news": "ANALYZE",
            "check_risk": "DECIDE",      # FIXED: check_risk means a decision has been made
            "execute_trade": "EXECUTE",
            "close_position": "EXECUTE",
            "close_all": "EXECUTE",
            "send_alert": "LOG",
            "log_decision": "LOG",
        }

        new_phase = phase_map.get(tool_name, current_phase)

        # Don't go backwards in phases
        current_idx = WORKFLOW_PHASES.index(current_phase) if current_phase in WORKFLOW_PHASES else 0
        new_idx = WORKFLOW_PHASES.index(new_phase) if new_phase in WORKFLOW_PHASES else current_idx

        # Log blocked backward transitions for debugging
        if new_idx < current_idx:
            logger.debug(f"Blocked backward phase transition: {current_phase} → {new_phase} (tool: {tool_name})")

        return new_phase if new_idx >= current_idx else current_phase'''

    if old_phase_map in content:
        content = content.replace(old_phase_map, new_phase_map)
        print("✓ Fix #1 applied: _tool_to_phase() updated (check_risk → DECIDE)")
    else:
        print("⚠ Fix #1: Could not find exact match for _tool_to_phase(). Manual review needed.")
    
    return content


def apply_fix_2_complete_current_phase(content: str) -> str:
    """Fix #2: Update _complete_current_phase() to handle DECIDE and MONITOR."""
    
    old_complete = '''    async def _complete_current_phase(self, phase: str, candidates: int, analyzed: int, trades: int):
        """Complete current workflow phase with appropriate metadata."""
        if phase == "SCAN":
            await self.tracker.complete_phase(phase, candidates=candidates)
        elif phase == "ANALYZE":
            await self.tracker.complete_phase(phase, analyzed=analyzed)
        elif phase == "EXECUTE":
            await self.tracker.complete_phase(phase, trades=trades)
        else:
            await self.tracker.complete_phase(phase)'''

    new_complete = '''    async def _complete_current_phase(self, phase: str, candidates: int, analyzed: int, trades: int):
        """Complete current workflow phase with appropriate metadata."""
        if phase == "SCAN":
            await self.tracker.complete_phase(phase, candidates=candidates)
        elif phase == "ANALYZE":
            await self.tracker.complete_phase(phase, analyzed=analyzed)
        elif phase == "DECIDE":
            await self.tracker.complete_phase(phase, decision_made=True)
        elif phase == "EXECUTE":
            await self.tracker.complete_phase(phase, trades=trades)
        elif phase == "MONITOR":
            await self.tracker.complete_phase(phase, monitoring_active=True)
        else:
            await self.tracker.complete_phase(phase)'''

    if old_complete in content:
        content = content.replace(old_complete, new_complete)
        print("✓ Fix #2 applied: _complete_current_phase() updated (DECIDE, MONITOR handling)")
    else:
        print("⚠ Fix #2: Could not find exact match for _complete_current_phase(). Manual review needed.")
    
    return content


def apply_fix_3_tool_loop_phases(content: str) -> str:
    """Fix #3: Add VALIDATE and MONITOR phase transitions in tool loop."""
    
    # This is trickier - we need to find the execute_trade handling section
    # and add the VALIDATE/MONITOR phase transitions
    
    old_trade_check = '''    elif tool_name == "execute_trade" and isinstance(result, dict):
                        if result.get("status") in ["filled", "success", "FILLED"]:
                            trades_executed += 1'''

    new_trade_check = '''    # === CRITICAL FIX: Handle DECIDE → VALIDATE → EXECUTE → MONITOR transitions ===
                    elif tool_name == "check_risk" and isinstance(result, dict):
                        # After DECIDE (check_risk), transition to VALIDATE with the result
                        if phase_started:
                            await self._complete_current_phase(current_phase, candidates_count, analyzed_count, trades_executed)
                        current_phase = "VALIDATE"
                        await self.tracker.start_phase("VALIDATE", "Risk validation")
                        await self.tracker.complete_phase("VALIDATE", 
                            approved=result.get("approved", False),
                            reason=result.get("reason", "")
                        )
                        phase_started = False  # VALIDATE is immediately completed
                        
                    elif tool_name == "execute_trade" and isinstance(result, dict):
                        if result.get("status") in ["filled", "success", "FILLED", "submitted", "SUBMITTED"]:
                            trades_executed += 1
                            
                            # After successful EXECUTE, transition to MONITOR
                            if phase_started:
                                await self._complete_current_phase(current_phase, candidates_count, analyzed_count, trades_executed)
                            
                            # Start and complete MONITOR phase
                            await self.tracker.start_phase("MONITOR", "Position monitoring started")
                            await self.tracker.complete_phase("MONITOR",
                                symbol=result.get("symbol"),
                                side=tool_input.get("side"),
                                quantity=tool_input.get("quantity"),
                                monitor_started=result.get("monitor_result") is not None
                            )
                            current_phase = "MONITOR"
                            phase_started = False  # MONITOR is immediately completed
                    # === END CRITICAL FIX ==='''

    if old_trade_check in content:
        content = content.replace(old_trade_check, new_trade_check)
        print("✓ Fix #3 applied: Tool loop updated with VALIDATE and MONITOR transitions")
    else:
        # Try alternative pattern matching
        print("⚠ Fix #3: Could not find exact match. Attempting regex match...")
        
        # More flexible regex pattern
        pattern = r'(elif tool_name == "execute_trade" and isinstance\(result, dict\):[\s\n]+if result\.get\("status"\) in \["filled", "success", "FILLED"\]:[\s\n]+trades_executed \+= 1)'
        
        if re.search(pattern, content):
            content = re.sub(pattern, new_trade_check, content)
            print("✓ Fix #3 applied via regex: Tool loop updated")
        else:
            print("✗ Fix #3 FAILED: Manual intervention required for tool loop")
    
    return content


def update_version_header(content: str) -> str:
    """Update the version header to reflect changes."""
    
    old_version = 'Version: 3.0.0'
    new_version = 'Version: 3.1.0'
    
    if old_version in content:
        content = content.replace(old_version, new_version)
        print("✓ Version updated: 3.0.0 → 3.1.0")
    
    # Add revision history entry
    old_history_marker = 'v3.0.0 (2026-01-17) - MERGED AGENT.PY FUNCTIONALITY'
    new_history = '''v3.1.0 (2026-01-20) - CRITICAL WORKFLOW FIXES
- Fixed missing DECIDE phase mapping (check_risk now triggers DECIDE)
- Fixed missing MONITOR phase trigger (after successful execute_trade)
- Added VALIDATE phase transition after check_risk result
- Added debug logging for blocked backward phase transitions

v3.0.0 (2026-01-17) - MERGED AGENT.PY FUNCTIONALITY'''
    
    if old_history_marker in content:
        content = content.replace(old_history_marker, new_history)
        print("✓ Revision history updated")
    
    return content


def main():
    """Apply all fixes to unified_agent.py."""
    print("=" * 60)
    print("CATALYST INTERNATIONAL - CRITICAL WORKFLOW FIXES")
    print("=" * 60)
    print()
    
    if not UNIFIED_AGENT_PATH.exists():
        print(f"✗ Error: {UNIFIED_AGENT_PATH} not found")
        print("  Make sure you're running this from the catalyst-international directory")
        return 1
    
    # Create backup
    backup_path = backup_file(UNIFIED_AGENT_PATH)
    
    # Read current content
    content = UNIFIED_AGENT_PATH.read_text()
    original_content = content
    
    print()
    print("Applying fixes...")
    print("-" * 40)
    
    # Apply fixes in order
    content = apply_fix_1_tool_to_phase(content)
    content = apply_fix_2_complete_current_phase(content)
    content = apply_fix_3_tool_loop_phases(content)
    content = update_version_header(content)
    
    print("-" * 40)
    
    # Check if any changes were made
    if content == original_content:
        print()
        print("⚠ No changes were made. Fixes may have already been applied or code has changed.")
        return 0
    
    # Write updated content
    UNIFIED_AGENT_PATH.write_text(content)
    print()
    print(f"✓ Changes written to {UNIFIED_AGENT_PATH}")
    print(f"  Backup saved to {backup_path}")
    
    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Review the changes: git diff unified_agent.py")
    print("2. Test with: ./venv/bin/python3 unified_agent.py --mode trade --force")
    print("3. Verify workflow shows all 10 phases in output")
    print("4. If issues, rollback: cp {backup_path} unified_agent.py")
    print()
    
    return 0


if __name__ == "__main__":
    exit(main())
