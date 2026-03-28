#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: hippocampus.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Hippocampus — memory binding and combined picture engine

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- Hippocampus class with polling loop
- Combined picture assembly from communication + learnings + principles
- Learning storage and recall
- Memory binding between related learnings
- Synaptic strength decay for unused memories

Description:
The hippocampus is the pivotal memory component. It sits between
the sensory organs (occipital) and consciousness (PFC).

It does NOT determine what to learn — that's PFC's job.
It HOLDS what was learned and presents the combined picture.

Responsibilities:
1. Monitor communication table for ALL ascending results
2. When PFC requests: build combined picture (recent results + learnings + principles)
3. When PFC instructs: store new learnings
4. Maintain memory bindings between related knowledge
5. Decay unused memories (synaptic strength fading)

Has its own SQLite database (memory.db) for learnings and bindings.
Reads from agent.db (communication table) for current state.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import aiosqlite

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import Component, MessageType, Direction

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hippocampus")


class Hippocampus:
    """
    Memory binding engine — where memories live and bind into understanding.

    Has two databases:
    - agent.db (read): communication table, principles
    - memory.db (read/write): learnings, memory_bindings, combined_picture
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_db: Optional[AgentDB] = None
        self.memory_conn: Optional[aiosqlite.Connection] = None
        self._running = False
        self._cycle_count = 0

    async def initialize(self):
        """Connect to both databases."""
        # Agent nervous system (communication table, principles)
        self.agent_db = AgentDB(self.config.agent_db_path)
        await self.agent_db.connect()

        # Hippocampus memory (learnings, bindings)
        self.memory_conn = await aiosqlite.connect(self.config.hippocampus_db_path)
        self.memory_conn.row_factory = aiosqlite.Row
        await self.memory_conn.execute("PRAGMA journal_mode=WAL")
        await self.memory_conn.execute("PRAGMA busy_timeout=5000")

        # Announce presence
        await self.agent_db.send_message(
            direction=Direction.ASCENDING,
            source=Component.HIPPOCAMPUS,
            target=None,
            msg_type=MessageType.STATUS,
            identifier="hippocampus_online",
            payload={"status": "online"},
        )
        logger.info("Hippocampus online. Memory database connected.")

    async def run(self):
        """Main polling loop — process tasks, absorb results, maintain memory."""
        self._running = True
        logger.info("Hippocampus entering polling loop (interval=%.1fs)", self.config.poll_interval)

        while self._running:
            try:
                # 1. Process direct tasks (requests from PFC)
                tasks = await self.agent_db.receive_messages(
                    target=Component.HIPPOCAMPUS,
                    msg_types=[MessageType.TASK],
                    limit=5,
                )
                for task in tasks:
                    await self._process_task(task)

                # 2. Periodic maintenance (every 50 cycles ≈ every ~100s)
                self._cycle_count += 1
                if self._cycle_count % 50 == 0:
                    await self._maintenance()

            except Exception as e:
                logger.error("Hippocampus loop error: %s", e, exc_info=True)

            await asyncio.sleep(self.config.poll_interval)

    async def _process_task(self, msg: Dict[str, Any]):
        """Handle tasks from PFC or other components."""
        msg_id = msg["id"]
        identifier = msg.get("identifier", "")
        logger.info("Processing task msg_id=%d identifier=%s", msg_id, identifier)

        await self.agent_db.update_message_status(
            msg_id, "processing", processed_by=Component.HIPPOCAMPUS
        )

        try:
            payload = json.loads(msg["payload"]) if msg.get("payload") else {}
            result = {}

            if identifier == "build_combined_picture":
                result = await self._build_combined_picture(payload)
            elif identifier == "recall_learnings":
                result = await self._recall_learnings(payload)
            elif identifier == "store_learning":
                result = await self._store_learning(payload)
            elif identifier == "get_relevant_memories":
                result = await self._get_relevant_memories(payload)
            elif identifier == "bind_memories":
                result = await self._bind_memories(payload)
            else:
                result = {"error": f"Unknown task: {identifier}"}

            # Send result back
            await self.agent_db.send_message(
                direction=Direction.ASCENDING,
                source=Component.HIPPOCAMPUS,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "result": result},
            )
            await self.agent_db.update_message_status(
                msg_id, "completed", processed_by=Component.HIPPOCAMPUS
            )
            logger.info("Task msg_id=%d completed", msg_id)

        except Exception as e:
            logger.error("Task msg_id=%d failed: %s", msg_id, e, exc_info=True)
            await self.agent_db.send_message(
                direction=Direction.ASCENDING,
                source=Component.HIPPOCAMPUS,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "error": str(e)},
            )
            await self.agent_db.update_message_status(
                msg_id, "failed", processed_by=Component.HIPPOCAMPUS
            )

    async def _build_combined_picture(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the combined picture for PFC consumption.

        Assembles:
        1. Recent sensory results from communication table
        2. Relevant learnings from memory.db
        3. Active principles from agent.db
        4. Memory bindings that connect results to knowledge
        """
        context = payload.get("context", "full")
        minutes = payload.get("minutes", 30)
        now = datetime.now(ZoneInfo("UTC")).isoformat()

        # 1. Recent results from communication table
        recent_results = await self.agent_db.get_recent_results(minutes=minutes)
        sensory_data = []
        for r in recent_results:
            try:
                p = json.loads(r["payload"]) if r.get("payload") else {}
            except (json.JSONDecodeError, TypeError):
                p = {}
            sensory_data.append({
                "source": r["source"],
                "identifier": r.get("identifier"),
                "result": p.get("result", p),
                "created_at": r["created_at"],
            })

        # 2. Relevant learnings from memory.db
        learnings = await self._recall_learnings({
            "min_confidence": 0.3,
            "limit": 20,
        })

        # 3. Principles from agent.db
        principles = await self.agent_db.get_principles()

        # 4. PFC state for context
        pfc_state = await self.agent_db.get_pfc_state()

        # Assemble the combined picture
        picture = {
            "assembled_at": now,
            "context": context,
            "pfc_state": {
                "mode": pfc_state.get("current_mode", "unknown") if pfc_state else "unknown",
                "focus": pfc_state.get("current_focus") if pfc_state else None,
                "active_questions": pfc_state.get("active_questions") if pfc_state else None,
                "last_thought": pfc_state.get("last_thought") if pfc_state else None,
                "session_count": pfc_state.get("session_count", 0) if pfc_state else 0,
            },
            "sensory_results": sensory_data,
            "learnings": learnings.get("learnings", []),
            "principles": [
                {
                    "domain": p["domain"],
                    "title": p["title"],
                    "content": p["content"],
                }
                for p in principles
            ],
        }

        # Cache the combined picture
        await self.memory_conn.execute(
            """INSERT INTO combined_picture
               (requested_by, request_context, sensory_results,
                relevant_learnings, active_bindings)
               VALUES (?, ?, ?, ?, ?)""",
            (
                "pfc",
                context,
                json.dumps(sensory_data),
                json.dumps(learnings.get("learnings", [])),
                json.dumps([]),
            ),
        )
        await self.memory_conn.commit()

        logger.info(
            "Combined picture assembled: %d sensory, %d learnings, %d principles",
            len(sensory_data),
            len(learnings.get("learnings", [])),
            len(principles),
        )
        return picture

    async def _recall_learnings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Recall learnings, sorted by confidence and strength."""
        domain = payload.get("domain")
        min_confidence = payload.get("min_confidence", 0.3)
        limit = payload.get("limit", 20)

        query = "SELECT * FROM learnings WHERE confidence >= ?"
        params: list = [min_confidence]

        if domain:
            query += " AND domain = ?"
            params.append(domain)

        query += " ORDER BY confidence DESC, times_validated DESC LIMIT ?"
        params.append(limit)

        cursor = await self.memory_conn.execute(query, params)
        rows = await cursor.fetchall()

        # Update last_accessed for recalled learnings
        learning_ids = [row["learning_id"] for row in rows]
        if learning_ids:
            placeholders = ",".join("?" for _ in learning_ids)
            await self.memory_conn.execute(
                f"UPDATE learnings SET updated_at = CURRENT_TIMESTAMP WHERE learning_id IN ({placeholders})",
                learning_ids,
            )
            await self.memory_conn.commit()

        return {
            "learnings": [
                {
                    "learning_id": row["learning_id"],
                    "domain": row["domain"],
                    "title": row["title"],
                    "content": row["content"],
                    "confidence": row["confidence"],
                    "times_validated": row["times_validated"],
                    "times_contradicted": row["times_contradicted"],
                    "source_component": row["source_component"],
                }
                for row in rows
            ]
        }

    async def _store_learning(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Store a new learning or reinforce an existing one."""
        domain = payload.get("domain", "trading")
        title = payload.get("title", "")
        content = payload.get("content", "")
        source_component = payload.get("source_component", "pfc")
        confidence = payload.get("confidence", 0.6)

        if not title or not content:
            return {"error": "Learning requires title and content"}

        # Check for existing similar learning
        cursor = await self.memory_conn.execute(
            "SELECT * FROM learnings WHERE domain = ? AND title = ?",
            (domain, title),
        )
        existing = await cursor.fetchone()

        if existing:
            # Reinforce existing learning
            new_validated = existing["times_validated"] + 1
            new_confidence = min(1.0, existing["confidence"] + 0.05)
            await self.memory_conn.execute(
                """UPDATE learnings
                   SET times_validated = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE learning_id = ?""",
                (new_validated, new_confidence, existing["learning_id"]),
            )
            await self.memory_conn.commit()
            logger.info("Reinforced learning: %s (confidence=%.2f)", title, new_confidence)
            return {
                "action": "reinforced",
                "learning_id": existing["learning_id"],
                "new_confidence": new_confidence,
            }
        else:
            # Store new learning
            learning_id = f"L-{uuid.uuid4().hex[:8]}"
            await self.memory_conn.execute(
                """INSERT INTO learnings
                   (learning_id, domain, title, content, confidence,
                    source_component, source_observations)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    learning_id,
                    domain,
                    title,
                    content,
                    confidence,
                    source_component,
                    json.dumps(payload.get("observations", [])),
                ),
            )
            await self.memory_conn.commit()
            logger.info("Stored new learning: %s (id=%s)", title, learning_id)
            return {"action": "created", "learning_id": learning_id}

    async def _get_relevant_memories(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get memories relevant to a specific context via bindings."""
        source_ref = payload.get("source_ref", "")
        source_type = payload.get("source_type", "learning")

        cursor = await self.memory_conn.execute(
            """SELECT mb.*, l.title, l.content, l.confidence
               FROM memory_bindings mb
               JOIN learnings l ON l.learning_id = mb.target_ref
               WHERE mb.source_type = ? AND mb.source_ref = ?
                 AND mb.association_strength >= 0.3
               ORDER BY mb.association_strength DESC
               LIMIT 10""",
            (source_type, source_ref),
        )
        rows = await cursor.fetchall()

        return {
            "related_memories": [
                {
                    "binding_id": row["binding_id"],
                    "target_ref": row["target_ref"],
                    "title": row["title"],
                    "content": row["content"],
                    "confidence": row["confidence"],
                    "association_strength": row["association_strength"],
                    "relationship": row["relationship"],
                }
                for row in rows
            ]
        }

    async def _bind_memories(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or strengthen a memory binding."""
        source_type = payload.get("source_type", "learning")
        source_ref = payload.get("source_ref", "")
        target_type = payload.get("target_type", "learning")
        target_ref = payload.get("target_ref", "")
        relationship = payload.get("relationship", "")

        if not source_ref or not target_ref:
            return {"error": "Binding requires source_ref and target_ref"}

        # Check for existing binding
        cursor = await self.memory_conn.execute(
            """SELECT * FROM memory_bindings
               WHERE source_type = ? AND source_ref = ?
                 AND target_type = ? AND target_ref = ?""",
            (source_type, source_ref, target_type, target_ref),
        )
        existing = await cursor.fetchone()

        if existing:
            # Strengthen existing binding
            new_strength = min(1.0, existing["association_strength"] + 0.1)
            new_coactivated = existing["times_coactivated"] + 1
            await self.memory_conn.execute(
                """UPDATE memory_bindings
                   SET association_strength = ?, times_coactivated = ?,
                       last_coactivated_at = CURRENT_TIMESTAMP
                   WHERE binding_id = ?""",
                (new_strength, new_coactivated, existing["binding_id"]),
            )
            await self.memory_conn.commit()
            return {"action": "strengthened", "binding_id": existing["binding_id"], "new_strength": new_strength}
        else:
            binding_id = f"B-{uuid.uuid4().hex[:8]}"
            await self.memory_conn.execute(
                """INSERT INTO memory_bindings
                   (binding_id, source_type, source_ref, target_type, target_ref,
                    association_strength, relationship)
                   VALUES (?, ?, ?, ?, ?, 0.5, ?)""",
                (binding_id, source_type, source_ref, target_type, target_ref, relationship),
            )
            await self.memory_conn.commit()
            return {"action": "created", "binding_id": binding_id}

    async def _maintenance(self):
        """Periodic maintenance: decay unused memories, clean expired pictures."""
        try:
            # Decay synaptic strength for learnings not accessed recently
            await self.memory_conn.execute(
                """UPDATE learnings
                   SET confidence = MAX(0.1, confidence * 0.995)
                   WHERE updated_at < datetime('now', '-7 days')
                     AND confidence > 0.1""",
            )

            # Decay weak memory bindings
            await self.memory_conn.execute(
                """UPDATE memory_bindings
                   SET association_strength = MAX(0.0, association_strength - 0.01)
                   WHERE last_coactivated_at < datetime('now', '-14 days')
                     AND association_strength > 0.0""",
            )

            # Clean very weak bindings
            await self.memory_conn.execute(
                "DELETE FROM memory_bindings WHERE association_strength <= 0.05",
            )

            # Clean old combined pictures (keep last 20)
            await self.memory_conn.execute(
                """DELETE FROM combined_picture
                   WHERE picture_id NOT IN (
                       SELECT picture_id FROM combined_picture
                       ORDER BY assembled_at DESC LIMIT 20
                   )""",
            )

            await self.memory_conn.commit()
            logger.debug("Maintenance cycle complete")

        except Exception as e:
            logger.error("Maintenance error: %s", e, exc_info=True)

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self.agent_db:
            await self.agent_db.send_message(
                direction=Direction.ASCENDING,
                source=Component.HIPPOCAMPUS,
                target=None,
                msg_type=MessageType.STATUS,
                identifier="hippocampus_offline",
                payload={"status": "offline"},
            )
            await self.agent_db.close()
        if self.memory_conn:
            await self.memory_conn.close()
        logger.info("Hippocampus shutdown complete")


async def main():
    config = AgentConfig.from_env()
    hippo = Hippocampus(config)

    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s, shutting down...", sig)
        loop.create_task(hippo.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await hippo.initialize()
        await hippo.run()
    except asyncio.CancelledError:
        pass
    finally:
        await hippo.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
