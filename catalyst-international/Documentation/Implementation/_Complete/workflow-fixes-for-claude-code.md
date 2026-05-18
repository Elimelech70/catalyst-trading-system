# Catalyst International - Workflow Fixes for Claude Code

## Instructions for Little Bro (Claude Code)

Execute these str_replace commands in order on the file:
`/root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py`

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

**Find the section that handles execute_trade results and add check_risk + VALIDATE/MONITOR handling:**

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

---

## FIX 4: Update version header

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
    Version: 3.0.0
    Last Updated: 2026-01-17
  new_str: |
    Version: 3.1.0
    Last Updated: 2026-01-20
```

---

## FIX 5: Update revision history

```
str_replace:
  path: /root/Catalyst-Trading-System-International/catalyst-international/unified_agent.py
  old_str: |
    v3.0.0 (2026-01-17) - MERGED AGENT.PY FUNCTIONALITY
  new_str: |
    v3.1.0 (2026-01-20) - CRITICAL WORKFLOW FIXES
    - Fixed missing DECIDE phase mapping (check_risk now triggers DECIDE)
    - Fixed missing MONITOR phase trigger (after successful execute_trade)
    - Added VALIDATE phase transition after check_risk result
    - Added debug logging for blocked backward phase transitions

    v3.0.0 (2026-01-17) - MERGED AGENT.PY FUNCTIONALITY
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

## Summary of Changes

| Change | Purpose |
|--------|---------|
| `check_risk` → DECIDE | Ensures DECIDE phase is entered when risk check is called |
| Add backward transition logging | Debug visibility when phase transitions are blocked |
| Handle DECIDE in `_complete_current_phase` | Proper metadata when DECIDE phase completes |
| Handle MONITOR in `_complete_current_phase` | Proper metadata when MONITOR phase completes |
| Add VALIDATE phase after check_risk | Workflow now shows DECIDE → VALIDATE → EXECUTE |
| Add MONITOR phase after execute_trade | Workflow now shows EXECUTE → MONITOR → LOG |
| Updated status check for trades | Added "submitted", "SUBMITTED" to success criteria |

---

## Rollback if Needed

If anything breaks, revert:
```bash
git checkout HEAD -- unified_agent.py
```
