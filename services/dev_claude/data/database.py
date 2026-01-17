#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: database.py
Version: 1.0.0
Last Updated: 2026-01-17
Purpose: Database connection manager for US markets (dev_claude)

REVISION HISTORY:
v1.0.0 (2026-01-17) - Initial implementation
  - Aligned with intl_claude data/database.py pattern
  - Module-level singleton pattern
  - get_database() / init_database() functions
  - Support for trading DB and consciousness DB

Description:
This module provides database connectivity for the Catalyst trading system.
It manages connections to both the trading database (catalyst_dev) and
the consciousness database (catalyst_research).

Environment Variables:
    DATABASE_URL: Trading database connection string
    DEV_DATABASE_URL: Alternative trading database URL
    RESEARCH_DATABASE_URL: Consciousness database connection string
"""

import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

try:
    import pytz
    ET = pytz.timezone('America/New_York')
except ImportError:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Database client for Catalyst trading system.
    
    Manages connections to:
    - Trading database (positions, orders, cycles)
    - Consciousness database (state, messages, observations)
    """
    
    def __init__(
        self,
        trading_url: str = None,
        research_url: str = None,
    ):
        """Initialize database client.
        
        Args:
            trading_url: Trading database connection string
            research_url: Consciousness database connection string
        """
        self.trading_url = trading_url or os.environ.get("DATABASE_URL") or os.environ.get("DEV_DATABASE_URL")
        self.research_url = research_url or os.environ.get("RESEARCH_DATABASE_URL")
        
        self.trading_pool: Optional[asyncpg.Pool] = None
        self.research_pool: Optional[asyncpg.Pool] = None
        self._connected = False
        
        logger.info("DatabaseClient initialized")
    
    async def connect(self) -> bool:
        """Connect to databases.
        
        Returns:
            True if at least trading DB connected
        """
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg not installed")
            return False
        
        try:
            # Connect to trading database
            if self.trading_url:
                self.trading_pool = await asyncpg.create_pool(
                    self.trading_url,
                    min_size=1,
                    max_size=5,
                    command_timeout=30,
                )
                logger.info("Connected to trading database")
            else:
                logger.warning("No trading database URL configured")
            
            # Connect to consciousness database
            if self.research_url:
                self.research_pool = await asyncpg.create_pool(
                    self.research_url,
                    min_size=1,
                    max_size=3,
                    command_timeout=30,
                )
                logger.info("Connected to consciousness database")
            else:
                logger.warning("No consciousness database URL configured")
            
            self._connected = self.trading_pool is not None
            return self._connected
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Close database connections."""
        if self.trading_pool:
            await self.trading_pool.close()
            self.trading_pool = None
        if self.research_pool:
            await self.research_pool.close()
            self.research_pool = None
        self._connected = False
        logger.info("Database connections closed")
    
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected
    
    # =========================================================================
    # TRADING DATABASE OPERATIONS
    # =========================================================================
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions from database.
        
        Returns:
            List of position dicts
        """
        if not self.trading_pool:
            return []
        
        try:
            async with self.trading_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        position_id,
                        symbol,
                        side,
                        quantity,
                        entry_price,
                        stop_loss,
                        take_profit,
                        entry_time,
                        notes as entry_reason,
                        max_favorable as high_watermark
                    FROM positions
                    WHERE status = 'open'
                    ORDER BY entry_time
                """)
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def record_trade(self, trade: Dict[str, Any]) -> Optional[int]:
        """Record a trade to the database.
        
        Args:
            trade: Trade data dict
            
        Returns:
            Trade ID if successful
        """
        if not self.trading_pool:
            return None
        
        try:
            async with self.trading_pool.acquire() as conn:
                # Record to orders table
                order_id = await conn.fetchval("""
                    INSERT INTO orders (
                        symbol, side, quantity, order_type,
                        limit_price, stop_price, broker_order_id,
                        status, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    RETURNING order_id
                """,
                    trade.get("symbol"),
                    trade.get("side"),
                    trade.get("quantity"),
                    trade.get("order_type", "market"),
                    trade.get("limit_price"),
                    trade.get("stop_loss"),
                    trade.get("order_id"),
                    trade.get("status", "filled"),
                )
                
                logger.info(f"Recorded order {order_id}: {trade.get('side')} {trade.get('symbol')}")
                return order_id
                
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            return None
    
    async def log_decision(self, decision: Dict[str, Any]) -> bool:
        """Log a trading decision.
        
        Args:
            decision: Decision data dict
            
        Returns:
            True if logged successfully
        """
        if not self.trading_pool:
            return False
        
        try:
            async with self.trading_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO decision_log (
                        cycle_id, decision_type, symbol,
                        reasoning, confidence, tier, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                    decision.get("cycle_id"),
                    decision.get("decision_type"),
                    decision.get("symbol"),
                    decision.get("reasoning"),
                    decision.get("confidence"),
                    decision.get("tier"),
                )
                return True
        except Exception as e:
            logger.warning(f"Failed to log decision: {e}")
            return False
    
    async def start_cycle(self, cycle_id: str, mode: str, agent_id: str) -> bool:
        """Record start of a trading cycle.
        
        Args:
            cycle_id: Unique cycle identifier
            mode: Trading mode
            agent_id: Agent identifier
            
        Returns:
            True if recorded
        """
        if not self.trading_pool:
            return False
        
        try:
            async with self.trading_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trading_cycles (
                        cycle_id, mode, agent_id, status, started_at
                    ) VALUES ($1, $2, $3, 'running', NOW())
                    ON CONFLICT (cycle_id) DO UPDATE SET
                        status = 'running',
                        started_at = NOW()
                """, cycle_id, mode, agent_id)
                return True
        except Exception as e:
            logger.warning(f"Failed to start cycle: {e}")
            return False
    
    async def end_cycle(
        self, 
        cycle_id: str, 
        result: Dict[str, Any]
    ) -> bool:
        """Record end of a trading cycle.
        
        Args:
            cycle_id: Cycle identifier
            result: Cycle result dict
            
        Returns:
            True if recorded
        """
        if not self.trading_pool:
            return False
        
        try:
            async with self.trading_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE trading_cycles SET
                        status = 'complete',
                        ended_at = NOW(),
                        trades_executed = $2,
                        api_cost = $3,
                        notes = $4
                    WHERE cycle_id = $1
                """,
                    cycle_id,
                    result.get("trades_executed", 0),
                    result.get("api_cost", 0),
                    str(result),
                )
                return True
        except Exception as e:
            logger.warning(f"Failed to end cycle: {e}")
            return False
    
    # =========================================================================
    # CONSCIOUSNESS DATABASE OPERATIONS
    # =========================================================================
    
    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent state from consciousness database.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            State dict or None
        """
        if not self.research_pool:
            return None
        
        try:
            async with self.research_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM claude_state
                    WHERE agent_id = $1
                """, agent_id)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get agent state: {e}")
            return None
    
    async def update_agent_state(
        self,
        agent_id: str,
        mode: str = None,
        api_spend: float = 0,
    ) -> bool:
        """Update agent state in consciousness database.
        
        Args:
            agent_id: Agent identifier
            mode: Current mode
            api_spend: API spend to add
            
        Returns:
            True if updated
        """
        if not self.research_pool:
            return False
        
        try:
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE claude_state SET
                        current_mode = COALESCE($2, current_mode),
                        api_spend_today = api_spend_today + $3,
                        last_active = NOW(),
                        updated_at = NOW()
                    WHERE agent_id = $1
                """, agent_id, mode, api_spend)
                return True
        except Exception as e:
            logger.warning(f"Failed to update state: {e}")
            return False
    
    async def get_pending_messages(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get unread messages for agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            List of message dicts
        """
        if not self.research_pool:
            return []
        
        try:
            async with self.research_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM claude_messages
                    WHERE to_agent = $1
                      AND read_at IS NULL
                    ORDER BY created_at
                """, agent_id)
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    async def mark_message_read(self, message_id: int) -> bool:
        """Mark a message as read.
        
        Args:
            message_id: Message ID
            
        Returns:
            True if marked
        """
        if not self.research_pool:
            return False
        
        try:
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE claude_messages
                    SET read_at = NOW()
                    WHERE message_id = $1
                """, message_id)
                return True
        except Exception as e:
            logger.warning(f"Failed to mark message: {e}")
            return False
    
    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        subject: str,
        body: str,
        priority: str = "normal",
    ) -> Optional[int]:
        """Send a message to another agent.
        
        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            subject: Message subject
            body: Message body
            priority: Message priority
            
        Returns:
            Message ID if sent
        """
        if not self.research_pool:
            return None
        
        try:
            async with self.research_pool.acquire() as conn:
                message_id = await conn.fetchval("""
                    INSERT INTO claude_messages (
                        from_agent, to_agent, subject, body,
                        priority, created_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                    RETURNING message_id
                """, from_agent, to_agent, subject, body, priority)
                return message_id
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    async def log_observation(
        self,
        agent_id: str,
        observation_type: str,
        content: str,
        tags: Dict[str, Any] = None,
    ) -> bool:
        """Log an observation to consciousness database.
        
        Args:
            agent_id: Agent identifier
            observation_type: Type of observation
            content: Observation content
            tags: Additional metadata
            
        Returns:
            True if logged
        """
        if not self.research_pool:
            return False
        
        try:
            import json
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_observations (
                        agent_id, observation_type, content,
                        tags, market, created_at
                    ) VALUES ($1, $2, $3, $4, 'US', NOW())
                """,
                    agent_id,
                    observation_type,
                    content,
                    json.dumps(tags) if tags else None,
                )
                return True
        except Exception as e:
            logger.warning(f"Failed to log observation: {e}")
            return False


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_database: Optional[DatabaseClient] = None


def get_database() -> DatabaseClient:
    """Get the global DatabaseClient instance.
    
    Returns:
        DatabaseClient instance
        
    Raises:
        RuntimeError: If not initialized
    """
    global _database
    if _database is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _database


async def init_database(
    trading_url: str = None,
    research_url: str = None,
) -> DatabaseClient:
    """Initialize and connect the global DatabaseClient.
    
    Args:
        trading_url: Trading database URL
        research_url: Consciousness database URL
        
    Returns:
        Connected DatabaseClient instance
    """
    global _database
    _database = DatabaseClient(
        trading_url=trading_url,
        research_url=research_url,
    )
    await _database.connect()
    return _database
