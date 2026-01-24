# Catalyst International - Workflow Fixes for Claude Code (UPDATED)

**Updated:** 2026-01-20
**Note:** Accounts for auto-sync changes in commit b0ccea1

## Instructions for Little Bro (Claude Code)

Execute these str_replace commands in order on the file:
`/root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py`

**IMPORTANT:** The file was just modified with auto-sync (v2.9.0). Line numbers have shifted. Use the exact string matching below - don't rely on line numbers.

---

## FIX 1: Update _tool_to_phase() method

**Find and replace the phase_map dictionary to map check_risk to DECIDE instead of VALIDATE:**

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
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
  new_str: |
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

        return new_phase if new_idx >= current_idx else current_phase
```

---

## FIX 2: Update _complete_current_phase() method

**Add handling for DECIDE and MONITOR phases:**

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
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
  new_str: |
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

## FIX 3: Update tool loop to add VALIDATE and MONITOR phase transitions

**IMPORTANT:** Look for the section in `_run_claude_loop()` that handles tool results. Find where `execute_trade` results are checked. The exact context may vary - search for "execute_trade" and "trades_executed += 1".

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
                    elif tool_name == "execute_trade" and isinstance(result, dict):
                        if result.get("status") in ["filled", "success", "FILLED"]:
                            trades_executed += 1

                    tool_results.append({
  new_str: |
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
```

**If FIX 3 fails to match**, try this alternative - the old_str might include "submitted" already:

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
                    elif tool_name == "execute_trade" and isinstance(result, dict):
                        if result.get("status") in ["filled", "success", "FILLED", "submitted", "SUBMITTED"]:
                            trades_executed += 1

                    tool_results.append({
  new_str: |
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
```

---

## FIX 4: Update version header

**Note:** Version may now be 3.1.0 or similar after auto-sync changes. Adjust accordingly:

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
    Version: 3.0.0
  new_str: |
    Version: 3.2.0
```

**OR if version is already 3.1.0:**

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
    Version: 3.1.0
  new_str: |
    Version: 3.2.0
```

---

## FIX 5: Update revision history

**Add new entry at the top of the revision history:**

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
    REVISION HISTORY:
  new_str: |
    REVISION HISTORY:
    v3.2.0 (2026-01-20) - CRITICAL WORKFLOW FIXES
    - Fixed missing DECIDE phase mapping (check_risk now triggers DECIDE)
    - Fixed missing MONITOR phase trigger (after successful execute_trade)
    - Added VALIDATE phase transition after check_risk result
    - Added debug logging for blocked backward phase transitions

```

---

## Verification After Fixes

Run this command to test:
```bash
cd /root/Catalyst-Trading-System-International/catalyst-international
./venv/bin/python3 unified_agent.py --mode trade --force
```

Expected output should show all 10 phases:
```
[✓ INIT][✓ PORTFOLIO][✓ SCAN][✓ ANALYZE][✓ DECIDE][✓ VALIDATE][✓ EXECUTE][✓ MONITOR][✓ LOG][✓ COMPLETE]
```

---

## What Changed with Auto-Sync

The auto-sync feature (lines 699-705) runs at the START of each trade cycle:
```
Trade cycle starts
        ↓
Auto-sync runs (reconciles DB with Moomoo)  ← NEW
        ↓
INIT phase starts
        ↓
... rest of workflow
```

This doesn't conflict with our fixes - we're modifying the MIDDLE of the workflow (DECIDE/VALIDATE/MONITOR transitions), not the start.

---

## Workflow After All Fixes

```
┌─────────────────────────────────────────────────────────────────┐
│  TRADE CYCLE START                                              │
│         ↓                                                       │
│  Auto-sync positions (NEW in v2.9.0)                           │
│         ↓                                                       │
│  INIT → PORTFOLIO → SCAN → ANALYZE                              │
│                              ↓                                  │
│                         check_risk called                       │
│                              ↓                                  │
│                         DECIDE phase (NEW FIX)                  │
│                              ↓                                  │
│                         VALIDATE phase (NEW FIX)                │
│                              ↓                                  │
│                         execute_trade called                    │
│                              ↓                                  │
│                         EXECUTE phase                           │
│                              ↓                                  │
│                         MONITOR phase (NEW FIX)                 │
│                              ↓                                  │
│                         LOG → COMPLETE                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Rollback if Needed

```bash
git checkout HEAD~1 -- unified_agent.py
```

Or to see what changed:
```bash
git diff unified_agent.py
```
