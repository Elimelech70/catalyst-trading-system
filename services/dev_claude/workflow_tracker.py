#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: workflow_tracker.py
Version: 1.0.0
Last Updated: 2026-01-20
Purpose: 10-phase workflow tracking for trading cycles

REVISION HISTORY:
v1.0.0 (2026-01-20) - Initial implementation
  - Ported from catalyst_intl for dev_claude
  - 10-phase workflow: INIT → PORTFOLIO → SCAN → ANALYZE → DECIDE → VALIDATE → EXECUTE → MONITOR → LOG → COMPLETE
  - Real-time progress tracking
  - Consciousness DB integration

Description:
Tracks the progress of trading cycles through 10 distinct phases.
Provides visibility into current workflow state for monitoring and debugging.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Workflow phases in order
WORKFLOW_PHASES = [
    "INIT",       # Cycle initialization
    "PORTFOLIO",  # Get portfolio state
    "SCAN",       # Scan market for candidates
    "ANALYZE",    # Analyze candidates (quotes, technicals, patterns)
    "DECIDE",     # Make trading decision (check_risk)
    "VALIDATE",   # Validate the decision
    "EXECUTE",    # Execute trades
    "MONITOR",    # Monitor positions after trade
    "LOG",        # Log decisions and send alerts
    "COMPLETE",   # Cycle complete
]


class WorkflowTracker:
    """Tracks workflow progress through trading cycle phases."""

    def __init__(
        self,
        cycle_id: str,
        agent_id: str = "dev_claude",
        db_pool: Any = None,
        timezone: str = "America/New_York"
    ):
        """Initialize workflow tracker.

        Args:
            cycle_id: Current trading cycle ID
            agent_id: Agent identifier (dev_claude, intl_claude, etc.)
            db_pool: Database connection pool for consciousness DB
            timezone: Timezone for timestamps
        """
        self.cycle_id = cycle_id
        self.agent_id = agent_id
        self.db_pool = db_pool
        self.tz = ZoneInfo(timezone)

        # Phase tracking
        self.phases: Dict[str, Dict[str, Any]] = {}
        self.current_phase: Optional[str] = None
        self.started_at = datetime.now(self.tz)

        # Initialize all phases as pending
        for phase in WORKFLOW_PHASES:
            self.phases[phase] = {
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "metadata": {},
            }

        logger.info(f"WorkflowTracker initialized for cycle {cycle_id}")

    async def start_phase(self, phase: str, description: str = "") -> bool:
        """Start a workflow phase.

        Args:
            phase: Phase name (must be in WORKFLOW_PHASES)
            description: Optional description of what's happening

        Returns:
            True if phase started successfully
        """
        if phase not in WORKFLOW_PHASES:
            logger.warning(f"Unknown phase: {phase}")
            return False

        # Complete current phase if different
        if self.current_phase and self.current_phase != phase:
            await self.complete_phase(self.current_phase)

        self.current_phase = phase
        now = datetime.now(self.tz)

        self.phases[phase] = {
            "status": "in_progress",
            "started_at": now,
            "completed_at": None,
            "description": description,
            "metadata": {},
        }

        logger.info(f"[{self.cycle_id}] Phase started: {phase} - {description}")

        # Update consciousness DB if available
        await self._update_consciousness_db(phase, "in_progress")

        return True

    async def complete_phase(self, phase: str, **metadata) -> bool:
        """Complete a workflow phase.

        Args:
            phase: Phase name to complete
            **metadata: Additional metadata for the phase

        Returns:
            True if phase completed successfully
        """
        if phase not in WORKFLOW_PHASES:
            logger.warning(f"Unknown phase: {phase}")
            return False

        now = datetime.now(self.tz)

        self.phases[phase]["status"] = "completed"
        self.phases[phase]["completed_at"] = now
        self.phases[phase]["metadata"].update(metadata)

        # Calculate duration
        if self.phases[phase]["started_at"]:
            duration = (now - self.phases[phase]["started_at"]).total_seconds()
            self.phases[phase]["duration_seconds"] = duration

        logger.info(f"[{self.cycle_id}] Phase completed: {phase} ({metadata})")

        # Update consciousness DB if available
        await self._update_consciousness_db(phase, "completed", metadata)

        return True

    async def fail_phase(self, phase: str, error: str) -> bool:
        """Mark a phase as failed.

        Args:
            phase: Phase name that failed
            error: Error message

        Returns:
            True if recorded successfully
        """
        if phase not in WORKFLOW_PHASES:
            return False

        now = datetime.now(self.tz)

        self.phases[phase]["status"] = "failed"
        self.phases[phase]["completed_at"] = now
        self.phases[phase]["error"] = error

        logger.error(f"[{self.cycle_id}] Phase failed: {phase} - {error}")

        # Update consciousness DB
        await self._update_consciousness_db(phase, "failed", {"error": error})

        return True

    def get_progress_bar(self) -> str:
        """Get ASCII progress bar showing workflow status.

        Returns:
            Progress bar string like: [✓ INIT][✓ PORTFOLIO][→ SCAN][ ANALYZE]...
        """
        bar = ""
        for phase in WORKFLOW_PHASES:
            status = self.phases[phase]["status"]
            if status == "completed":
                bar += f"[✓ {phase}]"
            elif status == "in_progress":
                bar += f"[→ {phase}]"
            elif status == "failed":
                bar += f"[✗ {phase}]"
            else:
                bar += f"[ {phase}]"
        return bar

    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status.

        Returns:
            Dict with cycle_id, current_phase, phases, progress
        """
        completed = sum(1 for p in self.phases.values() if p["status"] == "completed")
        total = len(WORKFLOW_PHASES)

        return {
            "cycle_id": self.cycle_id,
            "agent_id": self.agent_id,
            "current_phase": self.current_phase,
            "progress": f"{completed}/{total}",
            "progress_pct": round(completed / total * 100, 1),
            "progress_bar": self.get_progress_bar(),
            "started_at": self.started_at.isoformat(),
            "phases": self.phases,
        }

    async def _update_consciousness_db(
        self,
        phase: str,
        status: str,
        metadata: Dict[str, Any] = None
    ):
        """Update consciousness database with workflow status.

        Args:
            phase: Phase name
            status: Phase status
            metadata: Additional metadata
        """
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                # Upsert workflow status
                await conn.execute("""
                    INSERT INTO workflow_status (
                        cycle_id, agent_id, phase, status, metadata, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (cycle_id, phase)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """,
                    self.cycle_id,
                    self.agent_id,
                    phase,
                    status,
                    metadata or {}
                )
        except Exception as e:
            # Don't fail the workflow if DB update fails
            logger.debug(f"Failed to update consciousness DB: {e}")

    async def complete_cycle(self, summary: Dict[str, Any] = None):
        """Mark the entire cycle as complete.

        Args:
            summary: Summary of cycle results
        """
        await self.start_phase("COMPLETE", "Cycle completed")
        await self.complete_phase("COMPLETE", **(summary or {}))

        logger.info(f"[{self.cycle_id}] Workflow complete: {self.get_progress_bar()}")


def get_phase_for_tool(tool_name: str, current_phase: str) -> str:
    """Map a tool name to its workflow phase.

    Args:
        tool_name: Name of tool being called
        current_phase: Current workflow phase

    Returns:
        Phase that this tool belongs to
    """
    phase_map = {
        "get_portfolio": "PORTFOLIO",
        "scan_market": "SCAN",
        "get_quote": "ANALYZE",
        "get_technicals": "ANALYZE",
        "detect_patterns": "ANALYZE",
        "get_news": "ANALYZE",
        "check_risk": "DECIDE",  # check_risk means decision is being made
        "execute_trade": "EXECUTE",
        "close_position": "EXECUTE",
        "close_all": "EXECUTE",
        "send_alert": "LOG",
        "log_decision": "LOG",
    }

    new_phase = phase_map.get(tool_name, current_phase)

    # Don't go backwards in phases
    if current_phase in WORKFLOW_PHASES and new_phase in WORKFLOW_PHASES:
        current_idx = WORKFLOW_PHASES.index(current_phase)
        new_idx = WORKFLOW_PHASES.index(new_phase)

        if new_idx < current_idx:
            logger.debug(f"Blocked backward phase transition: {current_phase} → {new_phase} (tool: {tool_name})")
            return current_phase

    return new_phase
