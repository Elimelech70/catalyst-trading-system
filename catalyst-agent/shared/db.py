"""
Name of Application: Catalyst Trading System
Name of file: db.py
Version: 3.0.0
Last Updated: 2026-04-08
Purpose: Async SQLite wrapper for the agent nervous system

REVISION HISTORY:
v3.0.0 (2026-04-08) - v2.4 architecture alignment
- Added coordinator_state table operations
- Added trade_feedback table operations (exit type tracking)
- Auto-creates coordinator_state and trade_feedback tables on connect
- Added ATTENTION and EXECUTION signal domains
v2.0.0 (2026-04-06) - v8 architecture alignment
- Added signals table operations (3D signal bus)
v1.0.0 (2026-03-03) - Initial creation
- AgentDB class with communication table operations

Description:
The core database access layer used by ALL agent body components.
Wraps aiosqlite with WAL mode, busy_timeout, and typed operations
for the communication table, signals table, coordinator state,
and trade feedback (the nervous system).
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
        await self._ensure_signals_table()
        await self._ensure_coordinator_tables()
        logger.info(f"Connected to {self.db_path}")

    async def _ensure_signals_table(self):
        """Create the signals table if it doesn't exist (v8 signal bus)."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING', 'INFO', 'OBSERVE')),
                domain TEXT NOT NULL CHECK (domain IN (
                    'HEALTH', 'TRADING', 'RISK', 'LEARNING', 'DIRECTION', 'LIFECYCLE',
                    'ATTENTION', 'EXECUTION'
                )),
                scope TEXT NOT NULL,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                acknowledged_by TEXT DEFAULT '[]',
                resolved INTEGER DEFAULT 0
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_severity ON signals(severity)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_resolved ON signals(resolved)"
        )
        await self._conn.commit()

    async def _ensure_coordinator_tables(self):
        """Create v2.4 coordinator state and trade feedback tables."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS coordinator_state (
                agent_id TEXT PRIMARY KEY DEFAULT 'big_bro',
                current_layer TEXT DEFAULT 'heartbeat',
                cycle_id TEXT,
                cycle_count INTEGER DEFAULT 0,
                last_cycle_at TIMESTAMP,
                attention_mode TEXT DEFAULT 'security_selection',
                attention_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                watch_list TEXT DEFAULT '[]',
                active_securities TEXT DEFAULT '{}',
                body_health TEXT DEFAULT '{}',
                candle_model_loaded INTEGER DEFAULT 0,
                news_model_loaded INTEGER DEFAULT 0,
                fused_model_loaded INTEGER DEFAULT 0,
                market_open INTEGER DEFAULT 0,
                trading_enabled INTEGER DEFAULT 1,
                daily_pnl REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._conn.execute(
            "INSERT OR IGNORE INTO coordinator_state (agent_id) VALUES ('big_bro')"
        )
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL DEFAULT 'US',
                broker TEXT NOT NULL DEFAULT 'alpaca',
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                return_pct REAL NOT NULL,
                qty INTEGER,
                side TEXT,
                exit_type TEXT NOT NULL CHECK (exit_type IN ('AI_PATTERN', 'STOP_LOSS', 'MANUAL', 'ADVERSARIAL_EVENT')),
                pattern_type TEXT,
                holding_minutes INTEGER,
                neural_prediction TEXT,
                neural_confidence REAL,
                candle_model_version TEXT,
                candles_at_exit TEXT,
                exit_source TEXT,
                entry_at TIMESTAMP,
                exit_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_exit_type ON trade_feedback(exit_type)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_symbol ON trade_feedback(symbol)"
        )
        await self._conn.commit()

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
    # COMMUNICATION TABLE -- The nervous system signal bus
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
            f"Sent: {direction} {source}->{target or 'broadcast'} "
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
    # PFC STATE -- Continuity across wake cycles
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
    # PRINCIPLES -- Permanent identity
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

    # =========================================================================
    # SIGNALS TABLE -- v8 Architecture 3D Signal Bus
    # =========================================================================

    async def publish_signal(
        self,
        severity: str,
        domain: str,
        scope: str,
        source: str,
        content: str,
        data: Optional[dict] = None,
        expires_at: Optional[str] = None,
    ) -> int:
        """
        Publish a signal to the signal bus.
        Three-dimensional identifier: severity x domain x scope.
        """
        data_str = json.dumps(data) if data else None
        cursor = await self._conn.execute(
            """INSERT INTO signals
               (severity, domain, scope, source, content, data, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (severity, domain, scope, source, content, data_str, expires_at),
        )
        await self._conn.commit()
        sig_id = cursor.lastrowid
        logger.debug(
            "Signal published: %s:%s:%s from %s (id=%d)",
            severity, domain, scope, source, sig_id,
        )
        return sig_id

    async def read_signals(
        self,
        component: str,
        severity: Optional[str] = None,
        domain: Optional[str] = None,
        resolved: bool = False,
        limit: int = 20,
        minutes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read signals relevant to a component.
        Matches BROADCAST scope and DIRECTED:{component} scope.
        CRITICAL signals sort first (adrenaline flood).
        """
        query = """
            SELECT * FROM signals
            WHERE resolved = ?
              AND (scope = 'BROADCAST' OR scope = ?)
        """
        params: list = [1 if resolved else 0, f"DIRECTED:{component}"]

        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if minutes:
            query += " AND created_at >= datetime('now', ?)"
            params.append(f"-{minutes} minutes")

        query += " AND (expires_at IS NULL OR expires_at > datetime('now'))"

        # CRITICAL first, then by recency
        query += """
            ORDER BY
                CASE severity
                    WHEN 'CRITICAL' THEN 0
                    WHEN 'WARNING' THEN 1
                    WHEN 'INFO' THEN 2
                    WHEN 'OBSERVE' THEN 3
                END,
                created_at DESC
            LIMIT ?
        """
        params.append(limit)

        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def acknowledge_signal(self, signal_id: int, component: str):
        """Add component to acknowledged_by list."""
        cursor = await self._conn.execute(
            "SELECT acknowledged_by FROM signals WHERE id = ?", (signal_id,)
        )
        row = await cursor.fetchone()
        if row:
            try:
                ack_list = json.loads(row["acknowledged_by"] or "[]")
            except (json.JSONDecodeError, TypeError):
                ack_list = []
            if component not in ack_list:
                ack_list.append(component)
                await self._conn.execute(
                    "UPDATE signals SET acknowledged_by = ? WHERE id = ?",
                    (json.dumps(ack_list), signal_id),
                )
                await self._conn.commit()

    async def resolve_signal(self, signal_id: int):
        """Mark a signal as resolved."""
        await self._conn.execute(
            "UPDATE signals SET resolved = 1 WHERE id = ?", (signal_id,)
        )
        await self._conn.commit()

    # =========================================================================
    # COORDINATOR STATE -- v2.4 Architecture
    # =========================================================================

    async def get_coordinator_state(self, agent_id: str = "big_bro") -> Optional[Dict[str, Any]]:
        """Read the coordinator state (6-layer cycle + attention mode)."""
        cursor = await self._conn.execute(
            "SELECT * FROM coordinator_state WHERE agent_id = ?", (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_coordinator_state(self, agent_id: str = "big_bro", **kwargs):
        """Update coordinator state fields."""
        if not kwargs:
            return
        kwargs["updated_at"] = self._now()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [agent_id]
        await self._conn.execute(
            f"UPDATE coordinator_state SET {set_clause} WHERE agent_id = ?",
            values,
        )
        await self._conn.commit()

    async def set_attention_mode(self, mode: str, agent_id: str = "big_bro"):
        """Switch the attention state machine mode."""
        await self.update_coordinator_state(
            agent_id,
            attention_mode=mode,
            attention_changed_at=self._now(),
        )

    async def update_watch_list(self, symbols: list, agent_id: str = "big_bro"):
        """Update the Mode 2 watch list."""
        await self.update_coordinator_state(
            agent_id,
            watch_list=json.dumps(symbols),
        )

    async def update_active_securities(self, securities: dict, agent_id: str = "big_bro"):
        """Update active securities with direction and confidence."""
        await self.update_coordinator_state(
            agent_id,
            active_securities=json.dumps(securities),
        )

    # =========================================================================
    # TRADE FEEDBACK -- v2.4 Architecture Feedback Loop
    # =========================================================================

    async def record_trade_feedback(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        return_pct: float,
        exit_type: str,
        market: str = "US",
        broker: str = "alpaca",
        qty: Optional[int] = None,
        side: Optional[str] = None,
        pattern_type: Optional[str] = None,
        holding_minutes: Optional[int] = None,
        neural_prediction: Optional[str] = None,
        neural_confidence: Optional[float] = None,
        candle_model_version: Optional[str] = None,
        candles_at_exit: Optional[str] = None,
        exit_source: Optional[str] = None,
        entry_at: Optional[str] = None,
    ) -> int:
        """
        Record a trade exit for the feedback loop.
        This is the most important data for model improvement.
        """
        cursor = await self._conn.execute(
            """INSERT INTO trade_feedback
               (symbol, market, broker, entry_price, exit_price, return_pct,
                qty, side, exit_type, pattern_type, holding_minutes,
                neural_prediction, neural_confidence, candle_model_version,
                candles_at_exit, exit_source, entry_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, market, broker, entry_price, exit_price, return_pct,
             qty, side, exit_type, pattern_type, holding_minutes,
             neural_prediction, neural_confidence, candle_model_version,
             candles_at_exit, exit_source, entry_at),
        )
        await self._conn.commit()
        feedback_id = cursor.lastrowid
        logger.info(
            "Trade feedback recorded: %s exit_type=%s return=%.2f%% (id=%d)",
            symbol, exit_type, return_pct * 100, feedback_id,
        )
        return feedback_id

    async def get_trade_feedback(
        self,
        exit_type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get trade feedback records for analysis."""
        query = """
            SELECT * FROM trade_feedback
            WHERE created_at >= datetime('now', ?)
        """
        params: list = [f"-{days} days"]

        if exit_type:
            query += " AND exit_type = ?"
            params.append(exit_type)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self._conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_feedback_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get aggregate feedback statistics for the coordinator."""
        cursor = await self._conn.execute("""
            SELECT
                exit_type,
                COUNT(*) as count,
                AVG(return_pct) as avg_return,
                SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN return_pct <= 0 THEN 1 ELSE 0 END) as losses
            FROM trade_feedback
            WHERE created_at >= datetime('now', ?)
            GROUP BY exit_type
        """, (f"-{days} days",))
        rows = await cursor.fetchall()
        return {row["exit_type"]: dict(row) for row in rows}
