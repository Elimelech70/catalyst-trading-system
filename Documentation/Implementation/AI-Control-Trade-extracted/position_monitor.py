#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: position_monitor.py
Version: 1.0.0
Last Updated: 2025-01-01
Purpose: Trade-triggered position monitoring until exit

REVISION HISTORY:
v1.0.0 (2025-01-01) - Initial implementation
- Trade-triggered monitoring (no separate cron needed)
- Rules-based signal detection (free)
- Haiku consultation for uncertain signals (~$0.05/call)
- Big Bro notifications via consciousness DB

Description:
This module monitors a position from entry until exit. It runs in the
same process as the entry decision - no separate service or cron needed.

Cost Model:
- Signal detection: FREE (rules-based)
- Haiku consultation: ~$0.05/call (only for uncertain signals)
- Big Bro notifications: FREE (DB writes only)
- Expected per-trade cost: ~$0.05-0.15 for monitoring

Architecture:
- Called after execute_trade() for BUY orders
- Runs continuous loop checking every 5 minutes
- Exits when: position closed, market closed, or error
- Wide bracket orders remain as catastrophic backup
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import anthropic

from signals import (
    ExitSignals,
    SignalStrength,
    detect_exit_signals,
    combine_signals_for_decision,
)
from consciousness_notify import (
    notify_big_bro,
    notify_exit_executed,
    notify_entry_executed,
    notify_monitor_started,
    notify_monitor_ended,
    notify_haiku_decision,
)

logger = logging.getLogger(__name__)

HK_TZ = ZoneInfo("Asia/Hong_Kong")

# Configuration
CHECK_INTERVAL_SECONDS = 300  # 5 minutes
MAX_HAIKU_CALLS_PER_POSITION = 10  # Cost limit per position
HAIKU_MODEL = "claude-3-haiku-20240307"


class PositionMonitor:
    """
    Monitors a position until exit.
    
    Runs in the same process as entry - no separate service needed.
    Uses rules-based signal detection (free) and only consults
    Haiku for uncertain decisions (~$0.05/call).
    """
    
    def __init__(
        self,
        broker: Any,
        market_data: Any,
        anthropic_client: anthropic.Anthropic,
        safety_validator: Any,
    ):
        """
        Initialize position monitor.
        
        Args:
            broker: MoomooClient for quotes and order execution
            market_data: MarketData for technicals
            anthropic_client: Anthropic client for Haiku calls
            safety_validator: SafetyValidator for market hours check
        """
        self.broker = broker
        self.market_data = market_data
        self.client = anthropic_client
        self.safety = safety_validator
        
        # Tracking
        self.total_checks = 0
        self.haiku_calls = 0
    
    async def monitor_until_exit(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        entry_volume: float,
        entry_reason: str,
        stop_price: float,
        target_price: float,
    ) -> dict:
        """
        Monitor position until exit condition met.
        
        This runs in the same process as entry - no separate cron needed.
        Loop continues until position is closed or market closes.
        
        Args:
            symbol: HKEX symbol (e.g., '0700')
            entry_price: Price at entry
            quantity: Shares held
            entry_volume: Market volume at entry time
            entry_reason: Why we entered (for logging)
            stop_price: Wide catastrophic stop (bracket order)
            target_price: Wide target (bracket order)
            
        Returns:
            {
                'exit_price': float or None,
                'exit_reason': str,
                'pnl': float,
                'pnl_pct': float,
                'total_checks': int,
                'haiku_calls': int,
            }
        """
        logger.info(f"Starting position monitor for {symbol}")
        
        # Reset counters
        self.total_checks = 0
        self.haiku_calls = 0
        
        entry_time = datetime.now(HK_TZ)
        
        # Position state
        position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_volume': entry_volume,
            'entry_reason': entry_reason,
            'entry_time': entry_time,
            'stop_price': stop_price,
            'target_price': target_price,
            'side': 'LONG',
            'current_price': entry_price,
            'pnl_pct': 0.0,
        }
        
        # Notify big_bro that monitoring started
        await notify_monitor_started(symbol, entry_price, quantity)
        
        exit_result = {
            'exit_price': None,
            'exit_reason': 'Unknown',
            'pnl': 0.0,
            'pnl_pct': 0.0,
            'total_checks': 0,
            'haiku_calls': 0,
        }
        
        try:
            while True:
                self.total_checks += 1
                
                # === CHECK 1: Market still open? ===
                is_open, market_status = self.safety.is_market_open()
                if not is_open:
                    logger.info(f"Market closed: {market_status}")
                    exit_result['exit_reason'] = f"Market closed: {market_status}"
                    break
                
                # === CHECK 2: Position still exists? ===
                # (Might have hit bracket order)
                position_exists = await self._check_position_exists(symbol)
                if not position_exists:
                    logger.info(f"Position {symbol} no longer exists (bracket hit?)")
                    exit_result['exit_reason'] = "Position closed (bracket order hit)"
                    break
                
                # === CHECK 3: Get current market state ===
                quote = await self._get_quote(symbol)
                if not quote:
                    logger.warning(f"Failed to get quote for {symbol}, waiting...")
                    await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                    continue
                
                technicals = await self._get_technicals(symbol)
                
                # Update position state
                current_price = float(quote.get('price', 0) or quote.get('last_price', entry_price))
                position['current_price'] = current_price
                position['pnl_pct'] = (current_price - entry_price) / entry_price
                
                # === CHECK 4: Detect exit signals (FREE - rules based) ===
                signals = detect_exit_signals(
                    position=position,
                    quote=quote,
                    technicals=technicals,
                    entry_volume=entry_volume,
                    entry_time=entry_time,
                )
                
                # === DECISION LOGIC ===
                
                if signals.immediate_exit():
                    # STRONG signal - exit immediately, no Claude needed
                    exit_reason = f"STRONG EXIT: {', '.join(signals.active_signals())}"
                    logger.info(f"Immediate exit triggered: {exit_reason}")
                    
                    exit_price = await self._execute_exit(position, exit_reason)
                    
                    if exit_price:
                        pnl = (exit_price - entry_price) * quantity
                        pnl_pct = (exit_price - entry_price) / entry_price
                        
                        await notify_exit_executed(
                            position=position,
                            exit_reason=exit_reason,
                            exit_price=exit_price,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                        )
                        
                        exit_result = {
                            'exit_price': exit_price,
                            'exit_reason': exit_reason,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'total_checks': self.total_checks,
                            'haiku_calls': self.haiku_calls,
                        }
                    break
                    
                elif signals.needs_claude():
                    # MODERATE signal - ask Haiku (cheap)
                    if self.haiku_calls < MAX_HAIKU_CALLS_PER_POSITION:
                        decision = await self._consult_haiku(position, signals)
                        self.haiku_calls += 1
                        
                        if decision.get('should_exit'):
                            exit_reason = f"HAIKU EXIT: {decision.get('reason', 'Haiku decision')}"
                            logger.info(f"Haiku exit triggered: {exit_reason}")
                            
                            exit_price = await self._execute_exit(position, exit_reason)
                            
                            if exit_price:
                                pnl = (exit_price - entry_price) * quantity
                                pnl_pct = (exit_price - entry_price) / entry_price
                                
                                await notify_exit_executed(
                                    position=position,
                                    exit_reason=exit_reason,
                                    exit_price=exit_price,
                                    pnl=pnl,
                                    pnl_pct=pnl_pct,
                                )
                                
                                exit_result = {
                                    'exit_price': exit_price,
                                    'exit_reason': exit_reason,
                                    'pnl': pnl,
                                    'pnl_pct': pnl_pct,
                                    'total_checks': self.total_checks,
                                    'haiku_calls': self.haiku_calls,
                                }
                            break
                        else:
                            # Haiku said hold - notify big_bro for visibility
                            await notify_haiku_decision(
                                position=position,
                                signals=signals,
                                decision="HOLD",
                                reason=decision.get('reason', 'Continue holding'),
                            )
                    else:
                        # Hit Haiku limit - notify but continue monitoring
                        logger.warning(f"Haiku call limit reached for {symbol}")
                        await notify_big_bro(
                            event_type="HAIKU_LIMIT_REACHED",
                            position=position,
                            signals=signals,
                            details=f"Reached {MAX_HAIKU_CALLS_PER_POSITION} Haiku calls. Continuing with rules only.",
                            priority="normal",
                        )
                
                elif signals.strongest().value >= SignalStrength.MODERATE.value:
                    # High severity but already handled - notify big_bro for visibility
                    await notify_big_bro(
                        event_type="HIGH_SEVERITY_SIGNAL",
                        position=position,
                        signals=signals,
                        priority="normal",
                    )
                
                # === WAIT FOR NEXT CHECK ===
                logger.debug(f"Check {self.total_checks} complete for {symbol}, P&L: {position['pnl_pct']:.2%}")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                
        except asyncio.CancelledError:
            logger.info(f"Monitor cancelled for {symbol}")
            exit_result['exit_reason'] = "Monitor cancelled"
            
        except Exception as e:
            logger.error(f"Monitor error for {symbol}: {e}", exc_info=True)
            exit_result['exit_reason'] = f"Monitor error: {e}"
            
            # Notify big_bro of error
            await notify_big_bro(
                event_type="MONITOR_ERROR",
                position=position,
                signals=ExitSignals(),
                details=f"Error: {e}\n\nBracket orders still in place as backup.",
                priority="high",
            )
        
        finally:
            # Notify monitoring ended
            await notify_monitor_ended(
                symbol=symbol,
                reason=exit_result['exit_reason'],
                total_checks=self.total_checks,
                claude_calls=self.haiku_calls,
            )
            
            logger.info(
                f"Monitor ended for {symbol}: {exit_result['exit_reason']} "
                f"(checks: {self.total_checks}, haiku: {self.haiku_calls})"
            )
        
        return exit_result
    
    async def _check_position_exists(self, symbol: str) -> bool:
        """Check if position still exists in portfolio."""
        try:
            portfolio = self.broker.get_portfolio()
            positions = portfolio.get('positions', [])
            
            for pos in positions:
                pos_symbol = pos.get('symbol', '').replace('.HK', '')
                if pos_symbol == symbol or pos_symbol == symbol.replace('.HK', ''):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking position: {e}")
            return True  # Assume exists on error
    
    async def _get_quote(self, symbol: str) -> Optional[dict]:
        """Get current quote for symbol."""
        try:
            quote = self.broker.get_quote(symbol)
            return quote
        except Exception as e:
            logger.error(f"Error getting quote: {e}")
            return None
    
    async def _get_technicals(self, symbol: str) -> dict:
        """Get technical indicators for symbol."""
        try:
            technicals = self.market_data.get_technicals(symbol)
            return technicals or {}
        except Exception as e:
            logger.error(f"Error getting technicals: {e}")
            return {}
    
    async def _execute_exit(self, position: dict, reason: str) -> Optional[float]:
        """
        Execute market sell to exit position.
        
        Returns:
            Fill price if successful, None if failed
        """
        symbol = position['symbol']
        quantity = position['quantity']
        
        logger.info(f"Executing exit: {symbol} x {quantity} - {reason}")
        
        try:
            result = self.broker.place_order(
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                order_type='MARKET',
            )
            
            if result.get('status') in ['filled', 'FILLED', 'submitted', 'SUBMITTED']:
                fill_price = float(result.get('fill_price', 0) or position['current_price'])
                logger.info(f"Exit executed: {symbol} @ HKD {fill_price:.2f}")
                return fill_price
            else:
                logger.error(f"Exit order failed: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Exit execution error: {e}")
            return None
    
    async def _consult_haiku(
        self,
        position: dict,
        signals: ExitSignals,
    ) -> dict:
        """
        Ask Haiku for exit decision on uncertain signals.
        
        COST: ~$0.05 per call (Haiku is cheap)
        
        Returns:
            {'should_exit': bool, 'reason': str}
        """
        symbol = position['symbol']
        entry_price = position['entry_price']
        current_price = position['current_price']
        pnl_pct = position['pnl_pct']
        entry_reason = position['entry_reason']
        entry_time = position['entry_time']
        
        # Calculate hold time
        hold_duration = datetime.now(HK_TZ) - entry_time
        hold_minutes = int(hold_duration.total_seconds() / 60)
        
        prompt = f"""You are monitoring an HKEX position. Quick decision needed.

POSITION:
- Symbol: {symbol}
- Entry: HKD {entry_price:.2f}
- Current: HKD {current_price:.2f}
- P&L: {pnl_pct:+.2%}
- Hold time: {hold_minutes} minutes

ACTIVE SIGNALS:
{chr(10).join(f'- {s}' for s in signals.active_signals())}

ENTRY REASON: {entry_reason}

MARKET TIME: {datetime.now(HK_TZ).strftime('%H:%M')} HKT

Should we EXIT or HOLD?

Consider:
1. Are the signals indicating real weakness or just noise?
2. Is the original entry thesis still valid?
3. Is it worth the risk to continue holding?

Respond in exactly this format:
DECISION: EXIT or HOLD
REASON: One sentence explanation (max 20 words)
"""
        
        try:
            response = self.client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text
            logger.debug(f"Haiku response: {text}")
            
            # Parse response
            should_exit = False
            reason = "Haiku decision"
            
            if "DECISION:" in text:
                decision_line = text.split("DECISION:")[1].split("\n")[0].strip()
                should_exit = "EXIT" in decision_line.upper()
            
            if "REASON:" in text:
                reason = text.split("REASON:")[-1].strip()
                # Truncate if too long
                if len(reason) > 100:
                    reason = reason[:100] + "..."
            
            logger.info(f"Haiku decision for {symbol}: {'EXIT' if should_exit else 'HOLD'} - {reason}")
            
            return {
                'should_exit': should_exit,
                'reason': reason
            }
            
        except Exception as e:
            logger.error(f"Haiku consultation failed: {e}")
            # On error, default to HOLD (conservative)
            return {
                'should_exit': False,
                'reason': f"Haiku error, defaulting to hold: {str(e)[:50]}"
            }


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

async def start_position_monitor(
    broker: Any,
    market_data: Any,
    anthropic_client: anthropic.Anthropic,
    safety_validator: Any,
    symbol: str,
    entry_price: float,
    quantity: int,
    entry_volume: float,
    entry_reason: str,
    stop_price: float,
    target_price: float,
) -> dict:
    """
    Convenience function to start monitoring a position.
    
    Call this after execute_trade() for BUY orders.
    
    Args:
        broker: MoomooClient
        market_data: MarketData
        anthropic_client: Anthropic client
        safety_validator: SafetyValidator
        symbol: HKEX symbol
        entry_price: Fill price
        quantity: Shares purchased
        entry_volume: Volume at entry
        entry_reason: Why we entered
        stop_price: Wide stop (bracket backup)
        target_price: Wide target (bracket backup)
        
    Returns:
        Exit result dict
    """
    # Notify entry
    await notify_entry_executed(
        symbol=symbol,
        side='BUY',
        quantity=quantity,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        entry_reason=entry_reason,
    )
    
    # Create monitor and run
    monitor = PositionMonitor(
        broker=broker,
        market_data=market_data,
        anthropic_client=anthropic_client,
        safety_validator=safety_validator,
    )
    
    result = await monitor.monitor_until_exit(
        symbol=symbol,
        entry_price=entry_price,
        quantity=quantity,
        entry_volume=entry_volume,
        entry_reason=entry_reason,
        stop_price=stop_price,
        target_price=target_price,
    )
    
    return result


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    """Test position monitor (requires live services)."""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Position Monitor Module")
    print("=" * 50)
    print("\nThis module is designed to be called from agent.py")
    print("after a successful BUY trade execution.")
    print("\nUsage:")
    print("  from position_monitor import start_position_monitor")
    print("  result = await start_position_monitor(...)")
    print("\nCost model:")
    print("  - Signal detection: FREE (rules-based)")
    print("  - Haiku consultation: ~$0.05/call")
    print(f"  - Max Haiku calls per position: {MAX_HAIKU_CALLS_PER_POSITION}")
    print(f"  - Check interval: {CHECK_INTERVAL_SECONDS} seconds")
