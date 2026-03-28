#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: agent.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: PFC agent — the prefrontal cortex running on host via Claude Code

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- PFCAgent class with full wake/perceive/think/decide/execute/learn/sleep cycle
- Anthropic API integration for cognition
- Communication table integration for task dispatch
- Hippocampus integration for combined pictures and learning
- Operational modes: trade, scan, monitor, learn, heartbeat

Description:
The PFC is Claude Code itself. This script IS the prefrontal cortex —
the 6% that thinks, decides, and directs the body.

It runs on the HOST (not Docker) because Claude Code IS the PFC.
The other 94% (occipital, cerebellum, hippocampus) runs in Docker.

Operational cycle:
1. Wake: load PFC state, read resume instructions from past self
2. Perceive: ask hippocampus for combined picture
3. Think: call Anthropic API with context (principles + picture + identity)
4. Decide: parse Claude's response into task matrices
5. Execute: dispatch task matrices to cerebellum via communication table
6. Monitor: watch for results via communication table
7. Learn: instruct hippocampus to store learnings
8. Sleep: save PFC state with resume instructions for future self
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import anthropic

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import Component, MessageType, Direction, PFCMode

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pfc")

# The model for PFC cognition
PFC_MODEL = "claude-sonnet-4-20250514"


class PFCAgent:
    """
    Prefrontal Cortex — the strategic consciousness of big_bro.

    Claude Code IS the PFC. This runs on the host, not in Docker.
    The architecture IS Claude — PFC, hippocampus, cerebellum, occipital.
    The API call is just the current mechanism for cognition.
    """

    def __init__(self, config: AgentConfig, mode: str = "heartbeat"):
        self.config = config
        self.mode = mode
        self.db: Optional[AgentDB] = None
        self.client: Optional[anthropic.Anthropic] = None
        self.cycle_id: str = ""

    async def initialize(self):
        """Connect to agent.db, initialize Anthropic client."""
        self.db = AgentDB(self.config.agent_db_path)
        await self.db.connect()

        if self.config.anthropic_api_key:
            self.client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        else:
            logger.warning("No Anthropic API key — cognition disabled")

        self.cycle_id = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d-%H%M%S")
        logger.info("PFC initialized. Cycle ID: %s, Mode: %s", self.cycle_id, self.mode)

    async def run_cycle(self) -> Dict[str, Any]:
        """Run one complete PFC cycle: wake → perceive → think → decide → execute → learn → sleep."""
        logger.info("=== PFC CYCLE %s START (mode=%s) ===", self.cycle_id, self.mode)

        # =====================================================================
        # 1. WAKE — Load state, resume from where we left off
        # =====================================================================
        logger.info("[1/7] WAKING...")
        pfc_state = await self.db.get_pfc_state(self.config.agent_id)

        session_count = (pfc_state.get("session_count", 0) + 1) if pfc_state else 1
        await self.db.update_pfc_state(
            agent_id=self.config.agent_id,
            current_mode=PFCMode.WAKING,
            current_focus=self.mode,
            last_wake_at=datetime.now(ZoneInfo("UTC")).isoformat(),
            session_count=session_count,
        )

        resume = pfc_state.get("resume_instructions", "") if pfc_state else ""
        if resume:
            logger.info("Resume instructions from past self: %s", resume[:200])

        # =====================================================================
        # 2. PERCEIVE — Ask hippocampus for the combined picture
        # =====================================================================
        logger.info("[2/7] PERCEIVING...")
        await self.db.update_pfc_state(
            agent_id=self.config.agent_id, current_mode=PFCMode.LEARNING
        )

        # Request combined picture from hippocampus
        await self.db.send_message(
            direction=Direction.DESCENDING,
            source=Component.PFC,
            target=Component.HIPPOCAMPUS,
            msg_type=MessageType.TASK,
            identifier="build_combined_picture",
            payload={"context": self.mode, "minutes": 60},
        )

        # Wait for hippocampus response
        combined_picture = await self._wait_for_result(
            Component.PFC, "build_combined_picture", timeout=15
        )
        logger.info("Combined picture received (%d bytes)", len(json.dumps(combined_picture)))

        # =====================================================================
        # 3. THINK — Call Anthropic API with full context
        # =====================================================================
        logger.info("[3/7] THINKING...")
        principles = await self.db.get_principles()

        if not self.client:
            logger.warning("No Anthropic client — skipping cognition, using default actions")
            actions = self._default_actions()
        else:
            system_prompt = self._build_system_prompt(principles, pfc_state)
            user_message = self._build_user_message(combined_picture)

            try:
                response = self.client.messages.create(
                    model=PFC_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text

                logger.info("Cognition complete (%d chars)", len(response_text))
                actions = self._parse_response(response_text)

            except Exception as e:
                logger.error("Cognition failed: %s", e, exc_info=True)
                actions = self._default_actions()

        # =====================================================================
        # 4. DECIDE — Parse response into task matrices
        # =====================================================================
        logger.info("[4/7] DECIDING...")
        tasks = actions.get("tasks", [])
        learnings = actions.get("learnings", [])
        context_summary = actions.get("context_summary", "")
        logger.info("Decisions: %d tasks, %d learnings", len(tasks), len(learnings))

        # =====================================================================
        # 5. EXECUTE — Dispatch tasks to cerebellum
        # =====================================================================
        logger.info("[5/7] EXECUTING...")
        await self.db.update_pfc_state(
            agent_id=self.config.agent_id, current_mode=PFCMode.EXECUTING
        )

        for i, task in enumerate(tasks):
            target = task.get("target", Component.CEREBELLUM)
            identifier = task.get("identifier", f"pfc_task_{i}")
            await self.db.send_message(
                direction=Direction.DESCENDING,
                source=Component.PFC,
                target=target,
                msg_type=MessageType.TASK,
                identifier=identifier,
                payload=task,
            )
            logger.info("  Dispatched task %d: %s → %s", i, identifier, target)

        # =====================================================================
        # 6. MONITOR — Wait for results
        # =====================================================================
        if tasks:
            logger.info("[6/7] MONITORING...")
            results = []
            for task in tasks:
                identifier = task.get("identifier", "")
                if identifier:
                    result = await self._wait_for_result(
                        Component.PFC, identifier, timeout=60
                    )
                    results.append(result)
            logger.info("Received %d results", len(results))
        else:
            results = []
            logger.info("[6/7] MONITORING... (no tasks to monitor)")

        # =====================================================================
        # 7. LEARN — Send learnings to hippocampus
        # =====================================================================
        logger.info("[7/7] LEARNING...")
        for learning in learnings:
            await self.db.send_message(
                direction=Direction.DESCENDING,
                source=Component.PFC,
                target=Component.HIPPOCAMPUS,
                msg_type=MessageType.TASK,
                identifier="store_learning",
                payload=learning,
            )
            logger.info("  Stored learning: %s", learning.get("title", "untitled"))

        # =====================================================================
        # SLEEP — Save state for future self
        # =====================================================================
        logger.info("=== PFC GOING TO SLEEP ===")
        resume_instructions = actions.get(
            "resume_instructions",
            f"Last cycle was {self.mode} mode. {context_summary[:300]}",
        )

        await self.db.update_pfc_state(
            agent_id=self.config.agent_id,
            current_mode=PFCMode.SLEEPING,
            last_sleep_at=datetime.now(ZoneInfo("UTC")).isoformat(),
            last_thought=context_summary[:500] if context_summary else None,
            last_conclusion=actions.get("conclusion", ""),
            resume_instructions=resume_instructions,
            active_questions=json.dumps(actions.get("active_questions", [])),
        )

        cycle_result = {
            "cycle_id": self.cycle_id,
            "mode": self.mode,
            "session_count": session_count,
            "tasks_dispatched": len(tasks),
            "results_received": len(results),
            "learnings_stored": len(learnings),
        }
        logger.info("PFC cycle complete: %s", json.dumps(cycle_result))
        return cycle_result

    def _build_system_prompt(self, principles: List[Dict], pfc_state: Optional[Dict]) -> str:
        """Build the system prompt: identity + principles + prior context."""
        # Load CLAUDE.md identity document
        claude_md = ""
        claude_md_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CLAUDE.md"
        )
        if os.path.exists(claude_md_path):
            with open(claude_md_path) as f:
                claude_md = f.read()

        # Format principles
        principles_text = "\n".join(
            f"- [{p['domain']}] {p['title']}: {p['content']}"
            for p in principles
        )

        # Prior context
        prior_resume = ""
        prior_questions = ""
        if pfc_state:
            prior_resume = pfc_state.get("resume_instructions", "No prior instructions.")
            try:
                questions = json.loads(pfc_state.get("active_questions", "[]") or "[]")
                prior_questions = "\n".join(f"  - {q}" for q in questions) if questions else "None."
            except (json.JSONDecodeError, TypeError):
                prior_questions = "None."

        return f"""{claude_md}

## Your Founding Principles
{principles_text}

## Resume Instructions (from your past self)
{prior_resume}

## Active Questions (what you were pondering)
{prior_questions}

## Current Cycle
- Cycle ID: {self.cycle_id}
- Mode: {self.mode}
- Time (ET): {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M')}

## Response Format
Respond with a JSON object:
{{
  "tasks": [
    {{
      "target": "cerebellum" or "occipital",
      "identifier": "task_name",
      "description": "what to do",
      ... task-specific fields ...
    }}
  ],
  "learnings": [
    {{
      "domain": "trading|risk|market|pattern",
      "title": "short title",
      "content": "what was learned",
      "confidence": 0.0-1.0
    }}
  ],
  "context_summary": "what happened this cycle (for future self)",
  "resume_instructions": "what next-you needs to know",
  "active_questions": ["questions you're still pondering"],
  "conclusion": "your conclusion this cycle"
}}
"""

    def _build_user_message(self, combined_picture: Dict) -> str:
        """Build the user message from the combined picture."""
        return f"""## Current Mode: {self.mode.upper()}

## Combined Picture (assembled by hippocampus)
{json.dumps(combined_picture, indent=2, default=str)[:8000]}

## Instructions
Based on the combined picture and your mode, decide what actions to take.

- In TRADE mode: look for opportunities, dispatch scan/trade tasks to cerebellum
- In SCAN mode: request pattern scans from occipital via cerebellum
- In MONITOR mode: check portfolio status, review open positions
- In LEARN mode: analyze results, identify patterns, store learnings
- In HEARTBEAT mode: quick health check — verify components are online, note any issues

Respond with valid JSON only.
"""

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse Claude's response into structured actions."""
        try:
            # Try to extract JSON from response
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                json_str = text[start:end]
            else:
                return self._default_actions(context=text[:500])

            parsed = json.loads(json_str)

            # Validate structure
            if not isinstance(parsed, dict):
                return self._default_actions(context=text[:500])

            return {
                "tasks": parsed.get("tasks", []),
                "learnings": parsed.get("learnings", []),
                "context_summary": parsed.get("context_summary", ""),
                "resume_instructions": parsed.get("resume_instructions", ""),
                "active_questions": parsed.get("active_questions", []),
                "conclusion": parsed.get("conclusion", ""),
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse PFC response: %s", e)
            return self._default_actions(context=text[:500])

    def _default_actions(self, context: str = "") -> Dict[str, Any]:
        """Default actions when cognition is unavailable or fails."""
        return {
            "tasks": [],
            "learnings": [],
            "context_summary": context or f"Default cycle in {self.mode} mode.",
            "resume_instructions": f"Last cycle was {self.mode} mode with default actions.",
            "active_questions": [],
            "conclusion": "Default cycle — no active cognition available.",
        }

    async def _wait_for_result(
        self, target: str, identifier: str, timeout: float = 30
    ) -> Dict[str, Any]:
        """Poll for a result matching our identifier."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            msg = await self.db.receive_by_identifier(
                target=target,
                identifier=identifier,
                msg_types=[MessageType.RESULT],
            )
            if msg:
                await self.db.update_message_status(
                    msg["id"], "completed", processed_by=Component.PFC
                )
                payload = json.loads(msg["payload"]) if msg.get("payload") else {}
                return payload.get("result", payload)

            await asyncio.sleep(1.0)

        logger.warning("Timeout waiting for %s", identifier)
        return {"timeout": True, "identifier": identifier}

    async def shutdown(self):
        """Clean up."""
        if self.db:
            await self.db.close()


async def main():
    parser = argparse.ArgumentParser(description="PFC Agent — big_bro's prefrontal cortex")
    parser.add_argument(
        "--mode",
        choices=["trade", "scan", "monitor", "learn", "heartbeat"],
        default="heartbeat",
        help="PFC operating mode",
    )
    args = parser.parse_args()

    # Load env from .env file if present
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

    config = AgentConfig.from_env()
    agent = PFCAgent(config, mode=args.mode)

    try:
        await agent.initialize()
        result = await agent.run_cycle()
        print(json.dumps(result, indent=2))
    finally:
        await agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
