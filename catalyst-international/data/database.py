"""
PostgreSQL database client for the Catalyst Trading Agent.

Name of file: database.py
Version: 1.6.0
Last Updated: 2026-02-07

This module handles all database operations including:
- Agent cycle logging
- Decision audit trail
- Position tracking
- Trade history

REVISION HISTORY:
v1.6.0 (2026-02-07) - Position deduplication
- record_position() now checks for existing open position before INSERT (upsert)
- If position exists for symbol, updates quantity and recalculates avg price
- Added close_position_by_id() for targeted position closure
- Prevents duplicate open positions at application level
- Database also enforced via partial unique index on positions(symbol) WHERE status='open'

v1.5.0 (2026-02-05) - Symbol normalization
- Added normalize_symbol import from brokers.moomoo
- record_position() now normalizes symbol before storage
- record_order() now normalizes symbol before storage
- Ensures consistent symbol format in database (no leading zeros)

v1.4.0 (2026-01-31) - Add update_position_quantity
- Added update_position_quantity() for in-place quantity updates
- Used by sync_positions_with_broker to avoid close+create cycle
- Preserves position history and broker_order_id

v1.3.0 (2026-01-06) - Complete position recording
- Added symbol column to position INSERT
- Added entry_time to position INSERT
- Ensures all position fields are populated

v1.2.0 (2026-01-06) - Fix position recording bugs
- Fixed ON CONFLICT clause to match (symbol, exchange_id) constraint
- Changed broker_code from 'IBKR' to 'MOOMOO'

v1.1.0 (2025-12-30) - Fix exchange column name
- Changed 'exchange_code' to 'code' to match actual DB schema
- Fixed all SQL queries referencing the exchanges table

v1.0.0 (2025-12-20) - Initial implementation
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from brokers.moomoo import normalize_symbol

logger = logging.getLogger(__name__)

HK_TZ = ZoneInfo("Asia/Hong_Kong")


class DatabaseClient:
    """PostgreSQL client for Catalyst Trading System."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        pool_size: int = 5,
    ):
        """Initialize database connection pool.

        Args:
            host: Database host (or DB_HOST env var)
            port: Database port (or DB_PORT env var)
            database: Database name (or DB_NAME env var)
            user: Database user (or DB_USER env var)
            password: Database password (or DB_PASSWORD env var)
            pool_size: Connection pool size
        """
        self.host = host or os.environ.get("DB_HOST")
        self.port = port or int(os.environ.get("DB_PORT", "5432"))
        self.database = database or os.environ.get("DB_NAME", "catalyst_trading")
        self.user = user or os.environ.get("DB_USER")
        self.password = password or os.environ.get("DB_PASSWORD")

        if not all([self.host, self.user, self.password]):
            raise ValueError(
                "Database credentials required. Set DB_HOST, DB_USER, DB_PASSWORD"
            )

        self._pool: ThreadedConnectionPool | None = None
        self._pool_size = pool_size

    def _get_pool(self) -> ThreadedConnectionPool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=self._pool_size,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                sslmode="require",
            )
        return self._pool

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Get a connection from the pool."""
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    @contextmanager
    def get_cursor(self) -> Generator[RealDictCursor, None, None]:
        """Get a cursor with dict-like rows."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur

    def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None

    # =========================================================================
    # Exchange Operations
    # =========================================================================

    def get_exchange(self, exchange_code: str = "HKEX") -> dict | None:
        """Get exchange configuration."""
        with self.get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM exchanges WHERE code = %s AND is_active = TRUE
                """,
                (exchange_code,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_exchange_id(self, exchange_code: str = "HKEX") -> int | None:
        """Get exchange ID by code."""
        exchange = self.get_exchange(exchange_code)
        return exchange["exchange_id"] if exchange else None

    # =========================================================================
    # Agent Cycle Operations
    # =========================================================================

    def start_agent_cycle(self, cycle_id: str, exchange_code: str = "HKEX") -> str:
        """Record start of an agent cycle.

        Args:
            cycle_id: Unique cycle identifier
            exchange_code: Exchange code (default HKEX)

        Returns:
            The cycle_id
        """
        exchange_id = self.get_exchange_id(exchange_code)

        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_cycles (cycle_id, exchange_id, started_at)
                VALUES (%s, %s, %s)
                """,
                (cycle_id, exchange_id, datetime.now(HK_TZ)),
            )

        logger.info(f"Started agent cycle: {cycle_id}")
        return cycle_id

    def complete_agent_cycle(
        self,
        cycle_id: str,
        tools_called: list[dict],
        trades_executed: int,
        api_tokens_used: int,
        api_cost_usd: float,
        final_response: str,
        error: str | None = None,
    ):
        """Record completion of an agent cycle.

        Args:
            cycle_id: Cycle identifier
            tools_called: List of tool calls made
            trades_executed: Number of trades executed
            api_tokens_used: Total API tokens used
            api_cost_usd: Estimated API cost in USD
            final_response: Claude's final response
            error: Error message if cycle failed
        """
        with self.get_cursor() as cur:
            cur.execute(
                """
                UPDATE agent_cycles SET
                    completed_at = %s,
                    duration_seconds = EXTRACT(EPOCH FROM (%s - started_at)),
                    tools_called = %s,
                    trades_executed = %s,
                    api_tokens_used = %s,
                    api_cost_usd = %s,
                    final_response = %s,
                    error = %s
                WHERE cycle_id = %s
                """,
                (
                    datetime.now(HK_TZ),
                    datetime.now(HK_TZ),
                    json.dumps(tools_called),
                    trades_executed,
                    api_tokens_used,
                    api_cost_usd,
                    final_response,
                    error,
                    cycle_id,
                ),
            )

        status = "with error" if error else "successfully"
        logger.info(f"Completed agent cycle {cycle_id} {status}")

    def get_cycle_history(
        self, exchange_code: str = "HKEX", limit: int = 10
    ) -> list[dict]:
        """Get recent agent cycle history."""
        exchange_id = self.get_exchange_id(exchange_code)

        with self.get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM agent_cycles
                WHERE exchange_id = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (exchange_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    # =========================================================================
    # Decision Logging
    # =========================================================================

    def log_decision(
        self,
        cycle_id: str,
        decision_type: str,
        reasoning: str,
        symbol: str | None = None,
        tools_called: list[str] | None = None,
        exchange_code: str = "HKEX",
    ) -> int:
        """Log an agent decision for audit.

        Args:
            cycle_id: Current cycle identifier
            decision_type: Type of decision (trade, skip, close, emergency, observation)
            reasoning: Detailed reasoning for the decision
            symbol: Related symbol if applicable
            tools_called: List of tools called for this decision
            exchange_code: Exchange code

        Returns:
            The decision_id
        """
        exchange_id = self.get_exchange_id(exchange_code)

        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_decisions
                    (cycle_id, exchange_id, decision_type, symbol, reasoning, tools_called)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING decision_id
                """,
                (
                    cycle_id,
                    exchange_id,
                    decision_type,
                    symbol,
                    reasoning,
                    json.dumps(tools_called) if tools_called else None,
                ),
            )
            decision_id = cur.fetchone()["decision_id"]

        logger.info(f"Logged decision {decision_id}: {decision_type} for {symbol}")
        return decision_id

    def get_decisions(
        self, cycle_id: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Get decision history."""
        with self.get_cursor() as cur:
            if cycle_id:
                cur.execute(
                    """
                    SELECT * FROM agent_decisions
                    WHERE cycle_id = %s
                    ORDER BY created_at DESC
                    """,
                    (cycle_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM agent_decisions
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]

    # =========================================================================
    # Position Operations
    # =========================================================================

    def get_positions(self, exchange_code: str = "HKEX") -> list[dict]:
        """Get current open positions."""
        with self.get_cursor() as cur:
            cur.execute(
                """
                SELECT p.*, s.symbol, s.name as security_name
                FROM positions p
                JOIN securities s ON p.security_id = s.security_id
                WHERE p.broker_code = 'MOOMOO'
                    AND p.status = 'open'
                ORDER BY p.created_at DESC
                """,
            )
            return [dict(row) for row in cur.fetchall()]

    def record_position(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        broker_order_id: str,
        cycle_id: str,
        reason: str,
    ) -> int:
        """Record a position (upsert: updates existing open position if found).

        If an open position already exists for this symbol, the quantity is added
        and the average entry price is recalculated. Otherwise a new row is inserted.
        """
        # Normalize symbol and side to ensure consistent format
        symbol = normalize_symbol(symbol)
        side = side.lower()

        with self.get_cursor() as cur:
            # Get or create security
            cur.execute(
                """
                INSERT INTO securities (symbol, exchange_id)
                SELECT %s, exchange_id FROM exchanges WHERE code = 'HKEX'
                ON CONFLICT (symbol, exchange_id) DO UPDATE SET symbol = EXCLUDED.symbol
                RETURNING security_id
                """,
                (symbol,),
            )
            security_id = cur.fetchone()["security_id"]

            # Check for existing open position for this symbol
            cur.execute(
                """
                SELECT p.position_id, p.quantity, p.entry_price
                FROM positions p
                JOIN securities s ON p.security_id = s.security_id
                WHERE s.symbol = %s AND p.status = 'open'
                LIMIT 1
                """,
                (symbol,),
            )
            existing = cur.fetchone()

            if existing:
                # Update existing position (add quantity, recalculate avg price)
                old_qty = int(existing['quantity'])
                old_price = float(existing['entry_price'])
                new_qty = old_qty + quantity
                new_avg = ((old_qty * old_price) + (quantity * entry_price)) / new_qty
                cur.execute(
                    """
                    UPDATE positions SET quantity = %s, entry_price = %s,
                      updated_at = NOW(),
                      notes = COALESCE(notes, '') || %s
                    WHERE position_id = %s RETURNING position_id
                    """,
                    (
                        new_qty,
                        round(new_avg, 4),
                        f' | Added {quantity}@{entry_price} (order {broker_order_id})',
                        existing['position_id'],
                    ),
                )
                position_id = existing['position_id']
                logger.info(
                    f"Updated existing position {position_id}: {symbol} "
                    f"qty {old_qty}->{new_qty}, avg {old_price:.4f}->{new_avg:.4f}"
                )
                return position_id

            # No existing open position — INSERT new one
            cur.execute(
                """
                INSERT INTO positions (
                    security_id, symbol, side, quantity, entry_price, stop_loss, take_profit,
                    broker_order_id, broker_code, currency, status, notes, entry_time
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'MOOMOO', 'HKD', 'open', %s, NOW())
                RETURNING position_id
                """,
                (
                    security_id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    stop_loss,
                    take_profit,
                    broker_order_id,
                    f"Cycle: {cycle_id}. Reason: {reason}",
                ),
            )
            position_id = cur.fetchone()["position_id"]

        logger.info(f"Recorded position {position_id}: {side} {quantity} {symbol}")
        return position_id

    def record_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        limit_price: float | None,
        filled_quantity: int,
        filled_price: float | None,
        status: str,
        broker_order_id: str,
    ) -> int:
        """Record an order to the database.

        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell'
            order_type: 'MARKET' or 'LIMIT'
            quantity: Order quantity
            limit_price: Limit price (None for market orders)
            filled_quantity: Quantity filled
            filled_price: Average fill price
            status: Order status ('filled', 'cancelled', 'pending')
            broker_order_id: Broker's order ID

        Returns:
            Database order_id
        """
        # Normalize symbol to ensure consistent format (no leading zeros)
        symbol = normalize_symbol(symbol)
        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                    symbol, side, order_type, quantity, limit_price,
                    filled_quantity, filled_price, status, broker_order_id,
                    broker_code, submitted_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'MOOMOO', NOW())
                ON CONFLICT (broker_order_id) DO UPDATE SET
                    filled_quantity = EXCLUDED.filled_quantity,
                    filled_price = EXCLUDED.filled_price,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                RETURNING order_id
                """,
                (
                    symbol,
                    side,
                    order_type,
                    quantity,
                    limit_price,
                    filled_quantity,
                    filled_price,
                    status,
                    broker_order_id,
                ),
            )
            order_id = cur.fetchone()["order_id"]

        logger.info(f"Recorded order {order_id}: {side} {quantity} {symbol} ({status})")
        return order_id

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str,
    ) -> dict | None:
        """Close an existing position."""
        with self.get_cursor() as cur:
            cur.execute(
                """
                UPDATE positions p SET
                    status = 'closed',
                    exit_price = %s,
                    exit_time = %s,
                    realized_pnl = (CASE
                        WHEN side = 'buy' THEN (%s - entry_price) * quantity
                        ELSE (entry_price - %s) * quantity
                    END),
                    notes = COALESCE(notes, '') || ' | Closed: ' || %s
                FROM securities s
                WHERE p.security_id = s.security_id
                    AND s.symbol = %s
                    AND p.status = 'open'
                RETURNING p.*
                """,
                (exit_price, datetime.now(HK_TZ), exit_price, exit_price, reason, symbol),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def close_position_by_id(
        self,
        position_id: int,
        exit_price: float = 0,
        reason: str = "",
    ) -> dict | None:
        """Close a specific position by its ID."""
        with self.get_cursor() as cur:
            cur.execute(
                """
                UPDATE positions SET
                    status = 'closed',
                    exit_price = %s,
                    exit_time = %s,
                    exit_reason = %s,
                    notes = COALESCE(notes, '') || ' | Closed: ' || %s
                WHERE position_id = %s AND status = 'open'
                RETURNING *
                """,
                (exit_price, datetime.now(HK_TZ), reason, reason, position_id),
            )
            row = cur.fetchone()
            if row:
                logger.info(f"Closed position {position_id}: {reason}")
            return dict(row) if row else None

    def update_position_quantity(
        self,
        symbol: str,
        new_quantity: int,
        new_avg_price: float = None,
        reason: str = "",
    ) -> dict | None:
        """Update an existing position's quantity in-place.

        Used by sync_positions_with_broker to update quantities without
        closing and recreating positions (which loses history).

        Args:
            symbol: Stock symbol
            new_quantity: New quantity from broker
            new_avg_price: New average price (optional)
            reason: Reason for the update

        Returns:
            Updated position dict or None
        """
        with self.get_cursor() as cur:
            if new_avg_price:
                cur.execute(
                    """
                    UPDATE positions p SET
                        quantity = %s,
                        entry_price = %s,
                        updated_at = %s,
                        notes = COALESCE(notes, '') || ' | Updated: ' || %s
                    FROM securities s
                    WHERE p.security_id = s.security_id
                        AND s.symbol = %s
                        AND p.status = 'open'
                    RETURNING p.*
                    """,
                    (new_quantity, new_avg_price, datetime.now(HK_TZ), reason, symbol),
                )
            else:
                cur.execute(
                    """
                    UPDATE positions p SET
                        quantity = %s,
                        updated_at = %s,
                        notes = COALESCE(notes, '') || ' | Updated: ' || %s
                    FROM securities s
                    WHERE p.security_id = s.security_id
                        AND s.symbol = %s
                        AND p.status = 'open'
                    RETURNING p.*
                    """,
                    (new_quantity, datetime.now(HK_TZ), reason, symbol),
                )
            row = cur.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # Trading Cycle (shared with US system)
    # =========================================================================

    def create_trading_cycle(self, exchange_code: str = "HKEX") -> int:
        """Create a new trading cycle record."""
        exchange_id = self.get_exchange_id(exchange_code)

        with self.get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO trading_cycles (exchange_id, currency, status, started_at)
                VALUES (%s, 'HKD', 'running', %s)
                RETURNING cycle_id
                """,
                (exchange_id, datetime.now(HK_TZ)),
            )
            return cur.fetchone()["cycle_id"]

    def get_daily_stats(self, exchange_code: str = "HKEX") -> dict:
        """Get today's trading statistics."""
        exchange_id = self.get_exchange_id(exchange_code)
        today = datetime.now(HK_TZ).date()

        with self.get_cursor() as cur:
            # Get closed positions today
            cur.execute(
                """
                SELECT
                    COUNT(*) as trades_closed,
                    COALESCE(SUM(realized_pnl), 0) as realized_pnl
                FROM positions p
                JOIN securities s ON p.security_id = s.security_id
                WHERE p.broker_code = 'MOOMOO'
                    AND p.status = 'closed'
                    AND DATE(p.exit_time AT TIME ZONE 'Asia/Hong_Kong') = %s
                """,
                (today,),
            )
            closed = cur.fetchone()

            # Get open positions
            cur.execute(
                """
                SELECT COUNT(*) as open_positions
                FROM positions
                WHERE broker_code = 'MOOMOO' AND status = 'open'
                """,
            )
            open_count = cur.fetchone()["open_positions"]

            # Get cycle count today
            cur.execute(
                """
                SELECT COUNT(*) as cycles_today
                FROM agent_cycles
                WHERE exchange_id = %s
                    AND DATE(started_at AT TIME ZONE 'Asia/Hong_Kong') = %s
                """,
                (exchange_id, today),
            )
            cycles = cur.fetchone()["cycles_today"]

            return {
                "date": str(today),
                "trades_closed": closed["trades_closed"],
                "realized_pnl": float(closed["realized_pnl"]),
                "open_positions": open_count,
                "cycles_today": cycles,
            }


# Singleton instance
_database: DatabaseClient | None = None


def get_database() -> DatabaseClient:
    """Get or create database client singleton."""
    global _database
    if _database is None:
        _database = DatabaseClient()
    return _database


def init_database(
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> DatabaseClient:
    """Initialize database client with explicit credentials."""
    global _database
    _database = DatabaseClient(
        host=host, port=port, database=database, user=user, password=password
    )
    return _database
