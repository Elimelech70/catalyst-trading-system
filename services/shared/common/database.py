"""
Catalyst Trading System - Database Connection Module
Name of Application: Catalyst Trading System
Name of file: database.py
Version: 1.0.0
Last Updated: 2025-12-28
Purpose: Async database connection management for all agents

REVISION HISTORY:
v1.0.0 (2025-12-28) - Initial implementation
  - Connection pool management for trading and research databases
  - Transaction context managers
  - Factory function from environment

Description:
This module provides unified database connection management for all
Catalyst agents. It maintains separate connection pools for:
- Trading database (catalyst_public, catalyst_intl, or catalyst_trading)
- Research database (catalyst_research - consciousness)

Usage:
    from database import get_database_manager
    
    db = await get_database_manager().connect()
    
    # Use trading database
    async with db.trading.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM positions")
    
    # Use research database
    async with db.research.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM claude_state")
    
    # Transactions
    async with db.trading_transaction() as conn:
        await conn.execute("INSERT INTO ...")
        await conn.execute("UPDATE ...")
    
    # Cleanup
    await db.close()
"""

import os
import asyncpg
import logging
from typing import Optional
from contextlib import asynccontextmanager

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections for trading and research databases.
    
    This class maintains two connection pools:
    - trading_pool: For the trading database (positions, orders, etc.)
    - research_pool: For the research database (consciousness tables)
    
    Both pools are created lazily on first connect() call and cleaned up
    on close().
    
    Example:
        db = DatabaseManager(
            trading_url="postgresql://user:pass@host/catalyst_trading",
            research_url="postgresql://user:pass@host/catalyst_research"
        )
        await db.connect()
        
        # Query trading database
        async with db.trading.acquire() as conn:
            positions = await conn.fetch("SELECT * FROM positions WHERE status = 'open'")
        
        # Query research database
        async with db.research.acquire() as conn:
            state = await conn.fetchrow("SELECT * FROM claude_state WHERE agent_id = $1", 'public_claude')
        
        await db.close()
    """
    
    def __init__(
        self, 
        trading_url: str, 
        research_url: str,
        trading_pool_size: tuple = (2, 10),
        research_pool_size: tuple = (1, 5)
    ):
        """
        Initialize DatabaseManager.
        
        Args:
            trading_url: PostgreSQL connection URL for trading database
            research_url: PostgreSQL connection URL for research database
            trading_pool_size: (min_size, max_size) for trading pool
            research_pool_size: (min_size, max_size) for research pool
        """
        self.trading_url = trading_url
        self.research_url = research_url
        self.trading_pool_size = trading_pool_size
        self.research_pool_size = research_pool_size
        
        self._trading_pool: Optional[asyncpg.Pool] = None
        self._research_pool: Optional[asyncpg.Pool] = None
        self._connected = False
    
    async def connect(self) -> 'DatabaseManager':
        """
        Initialize connection pools.
        
        Returns:
            self for method chaining
        """
        if self._connected:
            logger.warning("DatabaseManager already connected")
            return self
        
        logger.info("Connecting to databases...")
        
        try:
            # Create trading pool
            self._trading_pool = await asyncpg.create_pool(
                self.trading_url,
                min_size=self.trading_pool_size[0],
                max_size=self.trading_pool_size[1],
                command_timeout=60
            )
            logger.info(f"Trading pool created (min={self.trading_pool_size[0]}, max={self.trading_pool_size[1]})")
            
            # Create research pool
            self._research_pool = await asyncpg.create_pool(
                self.research_url,
                min_size=self.research_pool_size[0],
                max_size=self.research_pool_size[1],
                command_timeout=60
            )
            logger.info(f"Research pool created (min={self.research_pool_size[0]}, max={self.research_pool_size[1]})")
            
            self._connected = True
            
            # Test connections
            async with self._trading_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            async with self._research_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            logger.info("Database connections verified")
            
        except Exception as e:
            logger.error(f"Failed to connect to databases: {e}")
            await self.close()
            raise
        
        return self
    
    async def close(self):
        """Close connection pools."""
        if self._trading_pool:
            await self._trading_pool.close()
            self._trading_pool = None
            logger.info("Trading pool closed")
        
        if self._research_pool:
            await self._research_pool.close()
            self._research_pool = None
            logger.info("Research pool closed")
        
        self._connected = False
    
    @property
    def trading(self) -> asyncpg.Pool:
        """
        Get trading database pool.
        
        Raises:
            RuntimeError: If not connected
        """
        if not self._trading_pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._trading_pool
    
    @property
    def research(self) -> asyncpg.Pool:
        """
        Get research database pool.
        
        Raises:
            RuntimeError: If not connected
        """
        if not self._research_pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._research_pool
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    @asynccontextmanager
    async def trading_transaction(self):
        """
        Context manager for trading database transactions.
        
        Example:
            async with db.trading_transaction() as conn:
                await conn.execute("INSERT INTO orders ...")
                await conn.execute("UPDATE positions ...")
        """
        async with self.trading.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    @asynccontextmanager
    async def research_transaction(self):
        """
        Context manager for research database transactions.
        
        Example:
            async with db.research_transaction() as conn:
                await conn.execute("INSERT INTO claude_observations ...")
                await conn.execute("INSERT INTO claude_learnings ...")
        """
        async with self.research.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    async def trading_execute(self, query: str, *args) -> str:
        """
        Execute a query on trading database.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            Status string (e.g., "INSERT 0 1")
        """
        async with self.trading.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def trading_fetch(self, query: str, *args) -> list:
        """
        Fetch rows from trading database.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            List of rows
        """
        async with self.trading.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def trading_fetchrow(self, query: str, *args):
        """
        Fetch single row from trading database.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            Single row or None
        """
        async with self.trading.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def trading_fetchval(self, query: str, *args):
        """
        Fetch single value from trading database.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            Single value
        """
        async with self.trading.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def research_execute(self, query: str, *args) -> str:
        """Execute a query on research database."""
        async with self.research.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def research_fetch(self, query: str, *args) -> list:
        """Fetch rows from research database."""
        async with self.research.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def research_fetchrow(self, query: str, *args):
        """Fetch single row from research database."""
        async with self.research.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def research_fetchval(self, query: str, *args):
        """Fetch single value from research database."""
        async with self.research.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    async def get_pool_stats(self) -> dict:
        """
        Get connection pool statistics.
        
        Returns:
            Dict with pool stats
        """
        stats = {}
        
        if self._trading_pool:
            stats['trading'] = {
                'size': self._trading_pool.get_size(),
                'free': self._trading_pool.get_idle_size(),
                'used': self._trading_pool.get_size() - self._trading_pool.get_idle_size(),
                'min': self._trading_pool.get_min_size(),
                'max': self._trading_pool.get_max_size()
            }
        
        if self._research_pool:
            stats['research'] = {
                'size': self._research_pool.get_size(),
                'free': self._research_pool.get_idle_size(),
                'used': self._research_pool.get_size() - self._research_pool.get_idle_size(),
                'min': self._research_pool.get_min_size(),
                'max': self._research_pool.get_max_size()
            }
        
        return stats


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_database_manager(
    trading_url: str = None,
    research_url: str = None
) -> DatabaseManager:
    """
    Factory function to create DatabaseManager from environment.
    
    Reads DATABASE_URL and RESEARCH_DATABASE_URL from environment
    if not provided.
    
    Args:
        trading_url: Override for trading database URL
        research_url: Override for research database URL
        
    Returns:
        DatabaseManager (not yet connected)
        
    Raises:
        ValueError: If required URLs not found
    """
    trading = trading_url or os.environ.get('DATABASE_URL')
    research = research_url or os.environ.get('RESEARCH_DATABASE_URL')
    
    if not trading:
        raise ValueError("DATABASE_URL environment variable not set")
    if not research:
        raise ValueError("RESEARCH_DATABASE_URL environment variable not set")
    
    return DatabaseManager(trading, research)


# =============================================================================
# ASYNC CONTEXT MANAGER
# =============================================================================

@asynccontextmanager
async def managed_database(
    trading_url: str = None,
    research_url: str = None
):
    """
    Async context manager for database connections.
    
    Automatically connects on enter and closes on exit.
    
    Example:
        async with managed_database() as db:
            rows = await db.trading_fetch("SELECT * FROM positions")
    """
    db = get_database_manager(trading_url, research_url)
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


# =============================================================================
# TESTING
# =============================================================================

async def test_database():
    """Test database connections."""
    from dotenv import load_dotenv
    
    # Load environment
    load_dotenv('/root/catalyst/config/shared.env')
    load_dotenv('/root/catalyst/config/public.env')
    
    print("Testing Database Module")
    print("=" * 50)
    
    try:
        db = get_database_manager()
        await db.connect()
        
        print("\n1. Connection Test")
        print(f"   Connected: {db.is_connected}")
        
        print("\n2. Pool Stats")
        stats = await db.get_pool_stats()
        for pool_name, pool_stats in stats.items():
            print(f"   {pool_name}: {pool_stats}")
        
        print("\n3. Trading Database Test")
        # Try to get table count
        count = await db.trading_fetchval("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f"   Tables in trading DB: {count}")
        
        print("\n4. Research Database Test")
        agents = await db.research_fetch("SELECT agent_id, current_mode FROM claude_state")
        print(f"   Agents found: {len(agents)}")
        for agent in agents:
            print(f"   - {agent['agent_id']}: {agent['current_mode']}")
        
        print("\n5. Transaction Test")
        async with db.research_transaction() as conn:
            # This will be rolled back since we don't commit
            await conn.execute("SELECT 1")
        print("   Transaction context manager works")
        
        await db.close()
        print(f"\n   Connected after close: {db.is_connected}")
        
        print("\n" + "=" * 50)
        print("All tests passed!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        raise


if __name__ == '__main__':
    import asyncio
    asyncio.run(test_database())
