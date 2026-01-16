#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: consciousness_notify.py
Version: 1.0.0
Last Updated: 2025-01-01
Purpose: Notify big_bro via consciousness database (no Claude cost)

REVISION HISTORY:
v1.0.0 (2025-01-01) - Initial implementation
- Notification to big_bro via claude_messages table
- Exit notifications with full trade details
- Signal notifications for visibility
- Dashboard integration

Description:
This module handles notifications from intl_claude to big_bro via the
consciousness database. These are DB writes only - NO Claude API cost.
Big_bro picks up notifications on the next hourly heartbeat.

Notifications appear on the web dashboard for Craig to see.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

import asyncpg

if TYPE_CHECKING:
    from signals import ExitSignals

logger = logging.getLogger(__name__)

HK_TZ = ZoneInfo("Asia/Hong_Kong")

# Connection pool singleton
_pool: Optional[asyncpg.Pool] = None


async def get_research_pool() -> asyncpg.Pool:
    """Get or create connection pool to research database."""
    global _pool
    
    if _pool is None:
        database_url = os.environ.get("RESEARCH_DATABASE_URL")
        if not database_url:
            raise ValueError("RESEARCH_DATABASE_URL not set")
        
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=3,
            command_timeout=30,
        )
        logger.info("Created research database pool")
    
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Closed research database pool")


async def notify_big_bro(
    event_type: str,
    position: dict,
    signals: "ExitSignals",
    details: str = "",
    priority: str = "normal",
) -> bool:
    """
    Write notification to consciousness DB for big_bro to see.
    
    This is a DB write only - NO Claude API cost.
    Big_bro picks up on next hourly heartbeat.
    Dashboard shows notifications to Craig.
    
    Args:
        event_type: Type of event (HIGH_SIGNAL, EXIT_EXECUTED, etc.)
        position: Position details dict
        signals: Current exit signals object
        details: Additional details text
        priority: Message priority (low, normal, high, urgent)
        
    Returns:
        True if notification sent successfully
    """
    try:
        pool = await get_research_pool()
        now = datetime.now(HK_TZ)
        
        symbol = position.get('symbol', 'UNKNOWN')
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price', entry_price)
        pnl_pct = position.get('pnl_pct', 0)
        
        subject = f"[{event_type}] {symbol}"
        
        body = f"""Event: {event_type}
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT
Symbol: {symbol}
Entry: HKD {entry_price:.2f}
Current: HKD {current_price:.2f}
P&L: {pnl_pct:.2%}

Active Signals: {', '.join(signals.active_signals()) if signals.active_signals() else 'None'}
Strongest: {signals.strongest().name}

{details}""".strip()
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages 
                (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'pending')
            """, 'intl_claude', 'big_bro', 'notification', subject, body, priority)
        
        logger.info(f"Notified big_bro: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to notify big_bro: {e}")
        return False


async def notify_exit_executed(
    position: dict,
    exit_reason: str,
    exit_price: float,
    pnl: float,
    pnl_pct: float,
) -> bool:
    """
    Notify big_bro that a position was exited.
    
    Args:
        position: Position details dict
        exit_reason: Why we exited
        exit_price: Price at exit
        pnl: Absolute P&L in HKD
        pnl_pct: P&L as percentage
        
    Returns:
        True if notification sent successfully
    """
    try:
        pool = await get_research_pool()
        now = datetime.now(HK_TZ)
        
        symbol = position.get('symbol', 'UNKNOWN')
        entry_price = position.get('entry_price', 0)
        quantity = position.get('quantity', 0)
        entry_reason = position.get('entry_reason', 'N/A')
        entry_time = position.get('entry_time')
        
        # Calculate hold time
        hold_time = "N/A"
        if entry_time:
            if isinstance(entry_time, datetime):
                duration = now - entry_time
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                hold_time = f"{hours}h {minutes}m"
        
        subject = f"[EXIT] {symbol} - {exit_reason[:30]}"
        
        # Emoji based on P&L
        pnl_emoji = "✅" if pnl >= 0 else "❌"
        
        body = f"""{pnl_emoji} EXIT EXECUTED

Symbol: {symbol}
Quantity: {quantity} shares
Entry: HKD {entry_price:.2f}
Exit: HKD {exit_price:.2f}
P&L: HKD {pnl:+,.2f} ({pnl_pct:+.2%})

Reason: {exit_reason}
Hold Time: {hold_time}

Entry Reason: {entry_reason}

---
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT"""
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages 
                (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, $2, $3, $4, $5, 'high', 'pending')
            """, 'intl_claude', 'big_bro', 'notification', subject, body)
        
        logger.info(f"Exit notification sent: {symbol} P&L: HKD {pnl:+,.2f}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send exit notification: {e}")
        return False


async def notify_entry_executed(
    symbol: str,
    side: str,
    quantity: int,
    entry_price: float,
    stop_price: float,
    target_price: float,
    entry_reason: str,
) -> bool:
    """
    Notify big_bro that a new position was entered.
    
    Args:
        symbol: HKEX symbol
        side: BUY or SELL
        quantity: Number of shares
        entry_price: Fill price
        stop_price: Stop loss level
        target_price: Target price
        entry_reason: Why we entered
        
    Returns:
        True if notification sent successfully
    """
    try:
        pool = await get_research_pool()
        now = datetime.now(HK_TZ)
        
        subject = f"[ENTRY] {symbol} - {side}"
        
        position_value = entry_price * quantity
        risk = abs(entry_price - stop_price) * quantity
        reward = abs(target_price - entry_price) * quantity
        rr_ratio = reward / risk if risk > 0 else 0
        
        body = f"""📈 NEW POSITION ENTERED

Symbol: {symbol}
Side: {side}
Quantity: {quantity} shares
Entry: HKD {entry_price:.2f}
Position Value: HKD {position_value:,.2f}

Risk Management:
- Stop Loss: HKD {stop_price:.2f} ({((stop_price - entry_price) / entry_price * 100):+.1f}%)
- Target: HKD {target_price:.2f} ({((target_price - entry_price) / entry_price * 100):+.1f}%)
- Risk: HKD {risk:,.2f}
- Reward: HKD {reward:,.2f}
- R:R Ratio: {rr_ratio:.1f}:1

Reason: {entry_reason}

---
Position will be monitored continuously until exit.
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT"""
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages 
                (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, $2, $3, $4, $5, 'normal', 'pending')
            """, 'intl_claude', 'big_bro', 'notification', subject, body)
        
        logger.info(f"Entry notification sent: {symbol} {side} {quantity} @ {entry_price}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send entry notification: {e}")
        return False


async def notify_monitor_started(
    symbol: str,
    entry_price: float,
    quantity: int,
) -> bool:
    """Notify that position monitoring has started."""
    try:
        pool = await get_research_pool()
        now = datetime.now(HK_TZ)
        
        subject = f"[MONITOR] Started: {symbol}"
        body = f"""Position monitoring started.

Symbol: {symbol}
Entry: HKD {entry_price:.2f}
Quantity: {quantity}

Checking every 5 minutes for exit signals.
Rules-based detection (no Claude cost).
Haiku consultation only for uncertain signals (~$0.05/call).

---
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT"""
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages 
                (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, $2, $3, $4, $5, 'low', 'pending')
            """, 'intl_claude', 'big_bro', 'notification', subject, body)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send monitor notification: {e}")
        return False


async def notify_monitor_ended(
    symbol: str,
    reason: str,
    total_checks: int,
    claude_calls: int,
) -> bool:
    """Notify that position monitoring has ended."""
    try:
        pool = await get_research_pool()
        now = datetime.now(HK_TZ)
        
        subject = f"[MONITOR] Ended: {symbol}"
        body = f"""Position monitoring ended.

Symbol: {symbol}
Reason: {reason}

Stats:
- Total signal checks: {total_checks}
- Haiku consultations: {claude_calls}
- Est. consultation cost: ${claude_calls * 0.05:.2f}

---
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT"""
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages 
                (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, $2, $3, $4, $5, 'low', 'pending')
            """, 'intl_claude', 'big_bro', 'notification', subject, body)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send monitor ended notification: {e}")
        return False


async def notify_haiku_decision(
    position: dict,
    signals: "ExitSignals",
    decision: str,
    reason: str,
) -> bool:
    """Notify about a Haiku consultation decision."""
    try:
        pool = await get_research_pool()
        now = datetime.now(HK_TZ)
        
        symbol = position.get('symbol', 'UNKNOWN')
        pnl_pct = position.get('pnl_pct', 0)
        
        subject = f"[HAIKU] {symbol}: {decision}"
        
        body = f"""🤖 HAIKU CONSULTATION

Symbol: {symbol}
Current P&L: {pnl_pct:.2%}

Signals presented:
{chr(10).join(f'- {s}' for s in signals.active_signals())}

Decision: {decision}
Reason: {reason}

Cost: ~$0.05

---
Time: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT"""
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages 
                (from_agent, to_agent, msg_type, subject, body, priority, status)
                VALUES ($1, $2, $3, $4, $5, 'normal', 'pending')
            """, 'intl_claude', 'big_bro', 'notification', subject, body)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Haiku decision notification: {e}")
        return False


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    """Test notifications (requires RESEARCH_DATABASE_URL)."""
    
    import asyncio
    from signals import ExitSignals, SignalStrength
    
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        print("Testing Consciousness Notifications")
        print("=" * 50)
        
        # Check for database URL
        if not os.environ.get("RESEARCH_DATABASE_URL"):
            print("RESEARCH_DATABASE_URL not set - skipping DB tests")
            print("Set it to test: export RESEARCH_DATABASE_URL='postgresql://...'")
            return
        
        # Create test signals
        signals = ExitSignals()
        signals.volume_dying = SignalStrength.MODERATE
        signals.rsi_overbought = SignalStrength.WEAK
        
        # Test position
        position = {
            'symbol': '0700',
            'entry_price': 380.0,
            'current_price': 385.0,
            'quantity': 100,
            'pnl_pct': 0.0132,
            'entry_reason': 'Test entry',
        }
        
        print("\nTest 1: High severity signal notification")
        result = await notify_big_bro(
            event_type="HIGH_SEVERITY_SIGNAL",
            position=position,
            signals=signals,
            details="Testing notification system",
            priority="normal",
        )
        print(f"  Result: {'✅ Success' if result else '❌ Failed'}")
        
        print("\nTest 2: Exit notification")
        result = await notify_exit_executed(
            position=position,
            exit_reason="Test exit - volume dying",
            exit_price=385.50,
            pnl=550.0,
            pnl_pct=0.0145,
        )
        print(f"  Result: {'✅ Success' if result else '❌ Failed'}")
        
        print("\nTest 3: Entry notification")
        result = await notify_entry_executed(
            symbol='0700',
            side='BUY',
            quantity=100,
            entry_price=380.0,
            stop_price=361.0,  # -5%
            target_price=418.0,  # +10%
            entry_reason='Bull flag breakout with volume',
        )
        print(f"  Result: {'✅ Success' if result else '❌ Failed'}")
        
        # Cleanup
        await close_pool()
        
        print("\n" + "=" * 50)
        print("Tests complete - check dashboard for notifications")
    
    asyncio.run(test())
