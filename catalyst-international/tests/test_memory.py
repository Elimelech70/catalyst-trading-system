"""
Name of Application: Catalyst Trading System
Name of file: tests/test_memory.py
Version: 1.0.0
Last Updated: 2025-12-09
Purpose: Test database connection and memory operations

REVISION HISTORY:
v1.0.0 (2025-12-09) - Initial implementation

Description:
Tests for the memory system (database interface).
"""

import asyncio
import os
import pytest

# Skip tests if no database available
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


@pytest.fixture
async def memory():
    """Create memory system for testing."""
    from agent.memory import MemorySystem

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://catalyst:catalyst_password@localhost:5432/catalyst_trading"
    )

    memory = MemorySystem(db_url)
    await memory.initialize()

    yield memory

    await memory.close()


@pytest.mark.asyncio
async def test_connection(memory):
    """Test database connection."""
    # Should not raise
    context = await memory.get_recent_context()
    assert context is not None


@pytest.mark.asyncio
async def test_get_current_strategy(memory):
    """Test getting current strategy."""
    strategy = await memory.get_current_strategy()

    assert isinstance(strategy, dict)
    assert "risk_appetite" in strategy or strategy == {}


@pytest.mark.asyncio
async def test_get_daily_stats(memory):
    """Test getting daily statistics."""
    stats = await memory.get_daily_stats()

    assert isinstance(stats, dict)
    assert "total_decisions" in stats
    assert "open_positions" in stats


if __name__ == "__main__":
    # Quick test runner
    async def main():
        from agent.memory import MemorySystem

        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://catalyst:catalyst_password@localhost:5432/catalyst_trading"
        )

        print(f"Testing connection to: {db_url}")

        memory = MemorySystem(db_url)
        await memory.initialize()

        print("Connection successful!")

        context = await memory.get_recent_context()
        print(f"Found {len(context.decisions)} recent decisions")

        strategy = await memory.get_current_strategy()
        print(f"Current strategy: {strategy.get('risk_appetite', 'N/A')}")

        await memory.close()
        print("Test complete!")

    asyncio.run(main())
