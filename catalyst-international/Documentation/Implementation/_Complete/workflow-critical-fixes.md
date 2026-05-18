# Catalyst International - Critical Workflow Fixes

**Name of Application:** Catalyst Trading System
**Name of file:** workflow-critical-fixes.md
**Version:** 1.0.0
**Last Updated:** 2026-01-20
**Purpose:** Implementation guide for fixing critical workflow logic errors

---

## Overview

Two critical logic errors were identified in the Catalyst International workflow:

1. **Missing DECIDE phase** - The DECIDE phase exists in WORKFLOW_PHASES but no tool triggers it
2. **Missing MONITOR phase** - The MONITOR phase exists but is never entered in workflow tracking

Both issues cause incomplete workflow visibility and broken audit trails.

---

## Fix #1: DECIDE and MONITOR Phase Mapping

### File: `unified_agent.py`

### Location: Find the `_tool_to_phase()` method (around line 350-380)

### Current Code (BROKEN):
```python
def _tool_to_phase(self, tool_name: str, current_phase: str) -> str:
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

    return new_phase if new_idx >= current_idx else current_phase
```

### Replace With (FIXED):
```python
def _tool_to_phase(self, tool_name: str, current_phase: str) -> str:
    """Map tool name to workflow phase.
    
    Phase order: INIT → PORTFOLIO → SCAN → ANALYZE → DECIDE → VALIDATE → EXECUTE → MONITOR → LOG → COMPLETE
    
    Note: DECIDE phase is triggered when check_risk is called (decision has been made).
    MONITOR phase is triggered after successful trade execution.
    """
    phase_map = {
        "get_portfolio": "PORTFOLIO",
        "scan_market": "SCAN",
        "get_quote": "ANALYZE",
        "get_technicals": "ANALYZE",
        "detect_patterns": "ANALYZE",
        "get_news": "ANALYZE",
        "check_risk": "DECIDE",      # CHANGED: check_risk means a decision has been made
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

    return new_phase if new_idx >= current_idx else current_phase
```

---

## Fix #2: Add VALIDATE Phase After DECIDE

### File: `unified_agent.py`

### Location: Find the tool execution loop in `_run_claude_loop()` (around line 280-340)

### Current Code (BROKEN):
```python
for tool_block in tool_use_blocks:
    tool_name = tool_block.name
    tool_input = tool_block.input

    # Update workflow phase based on tool
    new_phase = self._tool_to_phase(tool_name, current_phase)
    if new_phase != current_phase:
        if phase_started:
            await self._complete_current_phase(
                current_phase, candidates_count, analyzed_count, trades_executed
            )
        current_phase = new_phase
        await self.tracker.start_phase(new_phase, f"Running {tool_name}")
        phase_started = True

    logger.info(f"Tool call: {tool_name}")
    tools_called.append({"tool": tool_name, "input": tool_input})

    # Execute tool
    result = executor.execute(tool_name, tool_input)

    # Update counts for phase metadata
    if tool_name == "scan_market" and isinstance(result, dict):
        candidates_count = len(result.get("candidates", []))
    elif tool_name in ["get_quote", "get_technicals", "detect_patterns", "get_news"]:
        analyzed_count += 1
    elif tool_name == "execute_trade" and isinstance(result, dict):
        if result.get("status") in ["filled", "success", "FILLED"]:
            trades_executed += 1

    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tool_block.id,
        "content": json.dumps(result),
    })
```

### Replace With (FIXED):
```python
for tool_block in tool_use_blocks:
    tool_name = tool_block.name
    tool_input = tool_block.input

    # Update workflow phase based on tool
    new_phase = self._tool_to_phase(tool_name, current_phase)
    if new_phase != current_phase:
        if phase_started:
            await self._complete_current_phase(
                current_phase, candidates_count, analyzed_count, trades_executed
            )
        current_phase = new_phase
        await self.tracker.start_phase(new_phase, f"Running {tool_name}")
        phase_started = True

    logger.info(f"Tool call: {tool_name}")
    tools_called.append({"tool": tool_name, "input": tool_input})

    # Execute tool
    result = executor.execute(tool_name, tool_input)

    # Update counts for phase metadata
    if tool_name == "scan_market" and isinstance(result, dict):
        candidates_count = len(result.get("candidates", []))
    elif tool_name in ["get_quote", "get_technicals", "detect_patterns", "get_news"]:
        analyzed_count += 1
    
    # === CRITICAL FIX: Handle DECIDE → VALIDATE → EXECUTE → MONITOR transitions ===
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
    # === END CRITICAL FIX ===

    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tool_block.id,
        "content": json.dumps(result),
    })
```

---

## Fix #3: Update `_complete_current_phase()` to Handle New Phases

### File: `unified_agent.py`

### Location: Find the `_complete_current_phase()` method (around line 390-400)

### Current Code:
```python
async def _complete_current_phase(self, phase: str, candidates: int, analyzed: int, trades: int):
    """Complete current workflow phase with appropriate metadata."""
    if phase == "SCAN":
        await self.tracker.complete_phase(phase, candidates=candidates)
    elif phase == "ANALYZE":
        await self.tracker.complete_phase(phase, analyzed=analyzed)
    elif phase == "EXECUTE":
        await self.tracker.complete_phase(phase, trades=trades)
    else:
        await self.tracker.complete_phase(phase)
```

### Replace With (FIXED):
```python
async def _complete_current_phase(self, phase: str, candidates: int, analyzed: int, trades: int):
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
        await self.tracker.complete_phase(phase)
```

---

## Verification Steps

After applying fixes, verify with:

### 1. Run a test trade cycle:
```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
./venv/bin/python3 unified_agent.py --mode trade --force
```

### 2. Check workflow summary output shows all 10 phases:
```
[✓ INIT][✓ PORTFOLIO][✓ SCAN][✓ ANALYZE][✓ DECIDE][✓ VALIDATE][✓ EXECUTE][✓ MONITOR][✓ LOG][✓ COMPLETE]
```

### 3. Query consciousness database for workflow observations:
```sql
SELECT content, tags 
FROM claude_observations 
WHERE observation_type = 'workflow' 
ORDER BY created_at DESC 
LIMIT 1;
```

The `tags` JSON should show all phases completed.

---

## Summary of Changes

| File | Method | Change |
|------|--------|--------|
| unified_agent.py | `_tool_to_phase()` | Map `check_risk` to DECIDE instead of VALIDATE |
| unified_agent.py | `_tool_to_phase()` | Add debug logging for blocked backward transitions |
| unified_agent.py | `_run_claude_loop()` | Add explicit VALIDATE phase after check_risk result |
| unified_agent.py | `_run_claude_loop()` | Add MONITOR phase after successful execute_trade |
| unified_agent.py | `_complete_current_phase()` | Handle DECIDE and MONITOR phases |

---

## Rollback Plan

If issues occur, revert unified_agent.py to previous version:
```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
git checkout HEAD~1 -- unified_agent.py
```

---

**Document Author:** big_bro (Claude Opus 4.5)
**Review Date:** 2026-01-20
