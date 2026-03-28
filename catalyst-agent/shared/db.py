"""
Name of Application: Catalyst Trading System
Name of file: db.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Async SQLite wrapper for the agent nervous system

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- AgentDB class with communication table operations
- PFC state operations
- Principles operations

Description:
The core database access layer used by ALL agent body components.
Wraps aiosqlite with WAL mode, busy_timeout, and typed operations
for the communication table (the nervous system signal bus).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import aiosqlite

logger = logging.getLogger(__name__)


class AgentDB:
    """Async SQLite wrapper for the agent nervous system."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Open connection with WAL mode and busy_timeout."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        logger.info(f"Connected to {self.db_path}")

    async def close(self):
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info(f"Disconnected from {self.db_path}")

    def _now(self) -> str:
        """Current UTC timestamp as ISO string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # =========================================================================
    # COMMUNICATION TABLE — The nervous system signal bus
    # =========================================================================

    async def send_message(
        self,
        direction: str,
        source: str,
        target: Optional[str],
        msg_type: str,
        identifier: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> int:
        """
        Write a message to the communication table.
        Returns the message ID.
        """
        payload_str = json.dumps(payload) if payload else None
        cursor = await self._conn.execute(
            """INSERT INTO communication
               (direction, source, target, msg_type, identifier, payload, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (direction, source, target, msg_type, identifier, payload_str),
        )
        await self._conn.commit()
        msg_id = cursor.lastrowid
        logger.debug(
            f"Sent: {direction} {source}→{target or 'broadcast'} "
            f"type={msg_type} id={identifier} msg_id={msg_id}"
        )
        return msg_id

    async def receive_messages(
        self,
        target: str,
        msg_types: Optional[List[str]] = None,
        status: str = "pending",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Read messages for a target component, ordered by creation time.
        Also picks up broadcast messages (target IS NULL).
        """
        if msg_types:
            placeholders = ",".join("?" for _ in msg_types)
            query = f"""
                SELECT * FROM communication
                WHERE (target = ? OR target IS NULL)
                  AND msg_type IN ({placeholders})
                  AND status = ?
                ORDER BY created_at ASC
                LIMIT ?
            """
            params = [target] + msg_types + [status, limit]
        else:
            query = """
                SELECT * FROM communication
                WHERE (target = ? OR target IS NULL)
                  AND status = ?
                ORDER BY created_at ASC
                LIMIT ?
            """
            params = [target, status, limit]

        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def receive_by_identifier(
        self,
        target: str,
        identifier: str,
        msg_types: Optional[List[str]] = None,
        status: str = "pending",
    ) -> Optional[Dict[str, Any]]:
        """Read a specific message by identifier (for correlation)."""
        if msg_types:
            placeholders = ",".join("?" for _ in msg_types)
            query = f"""
                SELECT * FROM communication
                WHERE target = ? AND identifier = ?
                  AND msg_type IN ({placeholders})
                  AND status = ?
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = [target, identifier] + msg_types + [status]
        else:
            query = """
                SELECT * FROM communication
                WHERE target = ? AND identifier = ?
                  AND status = ?
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = [target, identifier, status]

        cursor = await self._conn.execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_message_status(
        self,
        msg_id: int,
        status: str,
        processed_by: Optional[str] = None,
    ):
        """Mark a message as processing/completed/failed/escalated."""
        processed_at = self._now() if status in ("completed", "failed") else None
        await self._conn.execute(
            """UPDATE communication
               SET status = ?, processed_at = ?, processed_by = ?
               WHERE id = ?""",
            (status, processed_at, processed_by, msg_id),
        )
        await self._conn.commit()

    async def get_recent_results(
        self,
        source: Optional[str] = None,
        limit: int = 20,
        minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get recent completed results (for hippocampus combined picture)."""
        query = """
            SELECT * FROM communication
            WHERE direction = 'ascending'
              AND msg_type = 'result'
              AND status = 'completed'
              AND created_at >= datetime('now', ?)
        """
        params = [f"-{minutes} minutes"]

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # =========================================================================
    # PFC STATE — Continuity across wake cycles
    # =========================================================================

    async def get_pfc_state(self, agent_id: str = "big_bro") -> Optional[Dict[str, Any]]:
        """Read the PFC state for continuity."""
        cursor = await self._conn.execute(
            "SELECT * FROM pfc_state WHERE agent_id = ?", (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_pfc_state(self, agent_id: str = "big_bro", **kwargs):
        """Update PFC state fields. Only updates provided kwargs."""
        if not kwargs:
            return
        kwargs["updated_at"] = self._now()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [agent_id]
        await self._conn.execute(
            f"UPDATE pfc_state SET {set_clause} WHERE agent_id = ?",
            values,
        )
        await self._conn.commit()

    # =========================================================================
    # PRINCIPLES — Permanent identity
    # =========================================================================

    async def get_principles(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read principles, optionally filtered by domain."""
        if domain:
            cursor = await self._conn.execute(
                "SELECT * FROM principles WHERE domain = ? ORDER BY established_at",
                (domain,),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM principles ORDER BY established_at"
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
