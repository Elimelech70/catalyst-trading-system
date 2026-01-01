#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: signals.py
Version: 1.0.0
Last Updated: 2025-01-01
Purpose: Exit signal detection - RULES BASED (no Claude cost)

REVISION HISTORY:
v1.0.0 (2025-01-01) - Initial implementation
- Pattern-based signals
- Volume-based signals
- Technical signals
- P&L signals
- Time-based signals

Description:
Detects exit signals based on rules. These are FREE checks that don't
require Claude API calls. Only uncertain/moderate signals trigger a
cheap Haiku consultation.

Signal Strength Levels:
- NONE (0): No signal
- WEAK (1): Note but don't act
- MODERATE (2): Uncertain - consult Haiku
- STRONG (3): Act immediately - no Claude needed
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

HK_TZ = ZoneInfo("Asia/Hong_Kong")


class SignalStrength(Enum):
    """Signal strength levels."""
    NONE = 0        # No signal detected
    WEAK = 1        # Note but don't act
    MODERATE = 2    # Uncertain - ask Haiku
    STRONG = 3      # Act immediately (no Claude needed)


@dataclass
class ExitSignals:
    """Collection of exit signals for a position."""
    
    # Pattern signals
    pattern_broken: SignalStrength = SignalStrength.NONE
    lower_high: SignalStrength = SignalStrength.NONE
    support_break: SignalStrength = SignalStrength.NONE
    
    # Volume signals  
    volume_dying: SignalStrength = SignalStrength.NONE
    volume_spike_down: SignalStrength = SignalStrength.NONE
    no_follow_through: SignalStrength = SignalStrength.NONE
    
    # Technical signals
    rsi_overbought: SignalStrength = SignalStrength.NONE
    rsi_oversold: SignalStrength = SignalStrength.NONE
    macd_bearish_cross: SignalStrength = SignalStrength.NONE
    below_vwap: SignalStrength = SignalStrength.NONE
    below_ema20: SignalStrength = SignalStrength.NONE
    
    # P&L signals
    stop_loss_near: SignalStrength = SignalStrength.NONE
    profit_target_near: SignalStrength = SignalStrength.NONE
    trailing_stop_hit: SignalStrength = SignalStrength.NONE
    
    # Time signals
    market_closing_soon: SignalStrength = SignalStrength.NONE
    lunch_break_approaching: SignalStrength = SignalStrength.NONE
    extended_hold: SignalStrength = SignalStrength.NONE
    
    # Context
    timestamp: datetime = field(default_factory=lambda: datetime.now(HK_TZ))
    
    def strongest(self) -> SignalStrength:
        """Return the strongest signal."""
        all_signals = [
            self.pattern_broken, self.lower_high, self.support_break,
            self.volume_dying, self.volume_spike_down, self.no_follow_through,
            self.rsi_overbought, self.rsi_oversold, self.macd_bearish_cross,
            self.below_vwap, self.below_ema20,
            self.stop_loss_near, self.profit_target_near, self.trailing_stop_hit,
            self.market_closing_soon, self.lunch_break_approaching, self.extended_hold,
        ]
        return max(all_signals, key=lambda x: x.value)
    
    def needs_claude(self) -> bool:
        """Return True if signals are uncertain (need Claude)."""
        strongest = self.strongest()
        # MODERATE = uncertain, needs Claude judgment
        return strongest == SignalStrength.MODERATE
    
    def immediate_exit(self) -> bool:
        """Return True if should exit immediately (no Claude needed)."""
        return self.strongest() == SignalStrength.STRONG
    
    def no_action_needed(self) -> bool:
        """Return True if no signals warrant action."""
        return self.strongest().value <= SignalStrength.WEAK.value
    
    def active_signals(self) -> list[str]:
        """Return list of active signal names with strength."""
        signals = []
        
        # Check each signal
        if self.pattern_broken.value > 0:
            signals.append(f"pattern_broken:{self.pattern_broken.name}")
        if self.lower_high.value > 0:
            signals.append(f"lower_high:{self.lower_high.name}")
        if self.support_break.value > 0:
            signals.append(f"support_break:{self.support_break.name}")
        if self.volume_dying.value > 0:
            signals.append(f"volume_dying:{self.volume_dying.name}")
        if self.volume_spike_down.value > 0:
            signals.append(f"volume_spike_down:{self.volume_spike_down.name}")
        if self.no_follow_through.value > 0:
            signals.append(f"no_follow_through:{self.no_follow_through.name}")
        if self.rsi_overbought.value > 0:
            signals.append(f"rsi_overbought:{self.rsi_overbought.name}")
        if self.rsi_oversold.value > 0:
            signals.append(f"rsi_oversold:{self.rsi_oversold.name}")
        if self.macd_bearish_cross.value > 0:
            signals.append(f"macd_bearish:{self.macd_bearish_cross.name}")
        if self.below_vwap.value > 0:
            signals.append(f"below_vwap:{self.below_vwap.name}")
        if self.below_ema20.value > 0:
            signals.append(f"below_ema20:{self.below_ema20.name}")
        if self.stop_loss_near.value > 0:
            signals.append(f"stop_loss_near:{self.stop_loss_near.name}")
        if self.profit_target_near.value > 0:
            signals.append(f"profit_target:{self.profit_target_near.name}")
        if self.trailing_stop_hit.value > 0:
            signals.append(f"trailing_stop:{self.trailing_stop_hit.name}")
        if self.market_closing_soon.value > 0:
            signals.append(f"market_closing:{self.market_closing_soon.name}")
        if self.lunch_break_approaching.value > 0:
            signals.append(f"lunch_break:{self.lunch_break_approaching.name}")
        if self.extended_hold.value > 0:
            signals.append(f"extended_hold:{self.extended_hold.name}")
            
        return signals
    
    def summary(self) -> str:
        """Return human-readable summary."""
        active = self.active_signals()
        if not active:
            return "No active signals"
        return f"Active signals: {', '.join(active)}"


def detect_exit_signals(
    position: dict,
    quote: dict,
    technicals: dict,
    entry_volume: float,
    entry_time: Optional[datetime] = None,
) -> ExitSignals:
    """
    Detect exit signals based on rules.
    
    This is FREE - no Claude API cost. Only MODERATE signals
    trigger a cheap Haiku consultation.
    
    Args:
        position: Current position {symbol, entry_price, quantity, side}
        quote: Current quote {price, bid, ask, volume}
        technicals: Technical indicators {rsi, macd, macd_signal, vwap, ema20}
        entry_volume: Volume at time of entry
        entry_time: Time position was entered
        
    Returns:
        ExitSignals with strength ratings
    """
    signals = ExitSignals()
    
    # Extract values with defaults
    current_price = float(quote.get('price', 0) or quote.get('last_price', 0) or 0)
    entry_price = float(position.get('entry_price', current_price) or current_price)
    
    if entry_price == 0:
        logger.warning("Entry price is 0, skipping signal detection")
        return signals
    
    pnl_pct = (current_price - entry_price) / entry_price
    
    # =========================================================================
    # P&L SIGNALS (Most important for risk management)
    # =========================================================================
    
    # Stop loss proximity
    if pnl_pct <= -0.03:
        # Down 3% or more - STRONG exit signal
        signals.stop_loss_near = SignalStrength.STRONG
        logger.info(f"STRONG STOP: P&L at {pnl_pct:.2%}")
    elif pnl_pct <= -0.02:
        # Down 2-3% - uncertain, ask Claude
        signals.stop_loss_near = SignalStrength.MODERATE
    elif pnl_pct <= -0.01:
        # Down 1-2% - note but don't act
        signals.stop_loss_near = SignalStrength.WEAK
        
    # Profit target proximity
    if pnl_pct >= 0.08:
        # Up 8% or more - consider taking profits
        signals.profit_target_near = SignalStrength.MODERATE
    elif pnl_pct >= 0.05:
        # Up 5-8% - note
        signals.profit_target_near = SignalStrength.WEAK
    
    # =========================================================================
    # VOLUME SIGNALS
    # =========================================================================
    
    current_volume = float(quote.get('volume', 0) or 0)
    
    if entry_volume and entry_volume > 0:
        volume_ratio = current_volume / entry_volume
        
        # Volume dying - momentum fading
        if volume_ratio < 0.25:
            # Volume collapsed - STRONG exit
            signals.volume_dying = SignalStrength.STRONG
            logger.info(f"STRONG VOLUME DIE: ratio {volume_ratio:.2f}")
        elif volume_ratio < 0.4:
            # Volume weak - uncertain
            signals.volume_dying = SignalStrength.MODERATE
        elif volume_ratio < 0.6:
            # Volume fading - note
            signals.volume_dying = SignalStrength.WEAK
    
    # =========================================================================
    # TECHNICAL SIGNALS
    # =========================================================================
    
    rsi = float(technicals.get('rsi', 50) or 50)
    macd = float(technicals.get('macd', 0) or 0)
    macd_signal = float(technicals.get('macd_signal', 0) or 0)
    vwap = float(technicals.get('vwap', current_price) or current_price)
    ema20 = float(technicals.get('ema20', current_price) or current_price)
    
    # RSI overbought (for longs)
    if rsi > 85:
        signals.rsi_overbought = SignalStrength.STRONG
        logger.info(f"STRONG RSI OVERBOUGHT: {rsi:.1f}")
    elif rsi > 75:
        signals.rsi_overbought = SignalStrength.MODERATE
    elif rsi > 70:
        signals.rsi_overbought = SignalStrength.WEAK
        
    # RSI oversold (position might recover - be cautious about exit)
    if rsi < 25:
        signals.rsi_oversold = SignalStrength.WEAK  # Note but momentum dead
        
    # MACD bearish crossover
    if macd < macd_signal:
        if macd > 0:
            # Crossed below signal while above zero - momentum turning
            signals.macd_bearish_cross = SignalStrength.MODERATE
        else:
            # Already negative - weak
            signals.macd_bearish_cross = SignalStrength.WEAK
            
    # Below VWAP (for long positions)
    if current_price < vwap * 0.98:
        # 2%+ below VWAP - concerning
        signals.below_vwap = SignalStrength.MODERATE
    elif current_price < vwap * 0.99:
        # 1-2% below VWAP
        signals.below_vwap = SignalStrength.WEAK
        
    # Below EMA20
    if current_price < ema20 * 0.98:
        signals.below_ema20 = SignalStrength.MODERATE
    elif current_price < ema20:
        signals.below_ema20 = SignalStrength.WEAK
    
    # =========================================================================
    # TIME SIGNALS
    # =========================================================================
    
    now = datetime.now(HK_TZ)
    
    # Market closing soon (HKEX closes at 16:00)
    market_close = time(16, 0)
    time_to_close = datetime.combine(now.date(), market_close, HK_TZ) - now
    
    if time_to_close.total_seconds() < 600:  # < 10 minutes
        signals.market_closing_soon = SignalStrength.STRONG
        logger.info("STRONG MARKET CLOSE: < 10 min remaining")
    elif time_to_close.total_seconds() < 1800:  # < 30 minutes
        signals.market_closing_soon = SignalStrength.MODERATE
    elif time_to_close.total_seconds() < 3600:  # < 1 hour
        signals.market_closing_soon = SignalStrength.WEAK
        
    # Lunch break approaching (12:00-13:00)
    lunch_start = time(12, 0)
    now_time = now.time()
    
    if time(11, 45) <= now_time < time(12, 0):
        # 11:45-12:00 - should close before lunch
        signals.lunch_break_approaching = SignalStrength.STRONG
        logger.info("STRONG LUNCH: Close before break")
    elif time(11, 30) <= now_time < time(11, 45):
        signals.lunch_break_approaching = SignalStrength.MODERATE
        
    # Extended hold time
    if entry_time:
        hold_duration = now - entry_time
        hold_minutes = hold_duration.total_seconds() / 60
        
        if hold_minutes > 180:  # > 3 hours
            signals.extended_hold = SignalStrength.MODERATE
        elif hold_minutes > 120:  # > 2 hours
            signals.extended_hold = SignalStrength.WEAK
    
    logger.debug(f"Signals detected: {signals.summary()}")
    return signals


def combine_signals_for_decision(signals: ExitSignals) -> dict:
    """
    Combine signals into a decision recommendation.
    
    Returns:
        {
            'recommendation': 'EXIT' | 'HOLD' | 'ASK_CLAUDE',
            'confidence': float 0-1,
            'reasons': list[str]
        }
    """
    active = signals.active_signals()
    strongest = signals.strongest()
    
    if strongest == SignalStrength.STRONG:
        return {
            'recommendation': 'EXIT',
            'confidence': 0.9,
            'reasons': [s for s in active if 'STRONG' in s],
        }
    elif strongest == SignalStrength.MODERATE:
        # Count moderate signals
        moderate_count = sum(1 for s in active if 'MODERATE' in s)
        
        if moderate_count >= 3:
            # Multiple moderate signals = lean toward exit
            return {
                'recommendation': 'EXIT',
                'confidence': 0.7,
                'reasons': active,
            }
        else:
            # Few moderate signals = ask Claude
            return {
                'recommendation': 'ASK_CLAUDE',
                'confidence': 0.5,
                'reasons': active,
            }
    else:
        return {
            'recommendation': 'HOLD',
            'confidence': 0.8,
            'reasons': active if active else ['No concerning signals'],
        }


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    """Test signal detection."""
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("Testing Exit Signal Detection")
    print("=" * 50)
    
    # Test case 1: Position down 3%
    print("\nTest 1: Position down 3%")
    position = {'entry_price': 100, 'symbol': '0700'}
    quote = {'price': 97, 'volume': 50000}
    technicals = {'rsi': 45, 'macd': 0.5, 'macd_signal': 0.6, 'vwap': 98}
    
    signals = detect_exit_signals(position, quote, technicals, 100000)
    print(f"  Signals: {signals.active_signals()}")
    print(f"  Immediate exit: {signals.immediate_exit()}")
    print(f"  Needs Claude: {signals.needs_claude()}")
    
    decision = combine_signals_for_decision(signals)
    print(f"  Decision: {decision}")
    
    # Test case 2: RSI overbought
    print("\nTest 2: RSI overbought")
    position = {'entry_price': 100, 'symbol': '0700'}
    quote = {'price': 108, 'volume': 80000}
    technicals = {'rsi': 82, 'macd': 1.2, 'macd_signal': 1.0, 'vwap': 105}
    
    signals = detect_exit_signals(position, quote, technicals, 100000)
    print(f"  Signals: {signals.active_signals()}")
    print(f"  Immediate exit: {signals.immediate_exit()}")
    print(f"  Needs Claude: {signals.needs_claude()}")
    
    decision = combine_signals_for_decision(signals)
    print(f"  Decision: {decision}")
    
    # Test case 3: Volume dying
    print("\nTest 3: Volume dying")
    position = {'entry_price': 100, 'symbol': '0700'}
    quote = {'price': 101, 'volume': 20000}  # Only 20% of entry volume
    technicals = {'rsi': 55, 'macd': 0.3, 'macd_signal': 0.3, 'vwap': 100}
    
    signals = detect_exit_signals(position, quote, technicals, 100000)
    print(f"  Signals: {signals.active_signals()}")
    print(f"  Immediate exit: {signals.immediate_exit()}")
    print(f"  Needs Claude: {signals.needs_claude()}")
    
    decision = combine_signals_for_decision(signals)
    print(f"  Decision: {decision}")
    
    # Test case 4: Everything fine
    print("\nTest 4: Healthy position")
    position = {'entry_price': 100, 'symbol': '0700'}
    quote = {'price': 103, 'volume': 120000}
    technicals = {'rsi': 60, 'macd': 0.8, 'macd_signal': 0.6, 'vwap': 101}
    
    signals = detect_exit_signals(position, quote, technicals, 100000)
    print(f"  Signals: {signals.active_signals()}")
    print(f"  Immediate exit: {signals.immediate_exit()}")
    print(f"  Needs Claude: {signals.needs_claude()}")
    print(f"  No action needed: {signals.no_action_needed()}")
    
    decision = combine_signals_for_decision(signals)
    print(f"  Decision: {decision}")
    
    print("\n" + "=" * 50)
    print("Tests complete")
