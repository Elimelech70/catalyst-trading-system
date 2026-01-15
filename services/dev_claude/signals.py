#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: signals.py
Version: 1.0.0
Last Updated: 2026-01-15
Purpose: Exit signal detection for position monitoring

REVISION HISTORY:
v1.0.0 (2026-01-15) - Initial implementation
  - Stop loss detection
  - Take profit detection
  - RSI overbought/oversold signals
  - Pattern breakdown detection

Description:
Analyzes positions and market data to detect exit signals.
Returns signal strength and recommended actions.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class SignalStrength(Enum):
    """Signal strength levels."""
    NONE = 0
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    CRITICAL = 4


@dataclass
class ExitSignal:
    """Exit signal for a position."""
    symbol: str
    signal_type: str
    strength: SignalStrength
    reason: str
    current_pnl_pct: float
    recommended_action: str
    urgency: str  # 'immediate', 'soon', 'monitor'
    metadata: Dict[str, Any]


class SignalDetector:
    """Detects exit signals for positions."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with signal configuration."""
        self.config = config.get('signals', {})

        # Default thresholds
        self.stop_loss_strong = self.config.get('stop_loss_strong', -0.05)
        self.stop_loss_moderate = self.config.get('stop_loss_moderate', -0.03)
        self.take_profit_strong = self.config.get('take_profit_strong', 0.10)
        self.take_profit_moderate = self.config.get('take_profit_moderate', 0.06)
        self.rsi_overbought_strong = self.config.get('rsi_overbought_strong', 80)
        self.rsi_overbought_moderate = self.config.get('rsi_overbought_moderate', 70)
        self.rsi_oversold_strong = self.config.get('rsi_oversold_strong', 20)
        self.rsi_oversold_moderate = self.config.get('rsi_oversold_moderate', 30)

    def detect_exit_signals(
        self,
        position: Dict[str, Any],
        technicals: Optional[Dict[str, Any]] = None,
        patterns: Optional[Dict[str, Any]] = None
    ) -> List[ExitSignal]:
        """
        Detect all exit signals for a position.

        Args:
            position: Position data with pnl_pct, entry_price, current_price
            technicals: Technical indicators (RSI, MAs, etc.)
            patterns: Detected chart patterns

        Returns:
            List of exit signals, sorted by strength
        """
        signals = []

        symbol = position.get('symbol', 'UNKNOWN')
        pnl_pct = position.get('pnl_pct', 0) / 100  # Convert from percentage
        side = position.get('side', 'long')

        # Check stop loss
        stop_signal = self._check_stop_loss(symbol, pnl_pct, side)
        if stop_signal:
            signals.append(stop_signal)

        # Check take profit
        tp_signal = self._check_take_profit(symbol, pnl_pct, side)
        if tp_signal:
            signals.append(tp_signal)

        # Check RSI signals
        if technicals:
            rsi_signal = self._check_rsi(symbol, pnl_pct, side, technicals)
            if rsi_signal:
                signals.append(rsi_signal)

            # Check MA breakdown
            ma_signal = self._check_ma_breakdown(symbol, pnl_pct, side, technicals)
            if ma_signal:
                signals.append(ma_signal)

        # Check pattern signals
        if patterns:
            pattern_signal = self._check_pattern_breakdown(symbol, pnl_pct, side, patterns)
            if pattern_signal:
                signals.append(pattern_signal)

        # Sort by strength (highest first)
        signals.sort(key=lambda x: x.strength.value, reverse=True)

        return signals

    def _check_stop_loss(self, symbol: str, pnl_pct: float, side: str) -> Optional[ExitSignal]:
        """Check stop loss conditions."""
        # For long positions, negative P&L triggers stop
        # For short positions, positive P&L triggers stop (price went up)
        effective_pnl = pnl_pct if side == 'long' else -pnl_pct

        if effective_pnl <= self.stop_loss_strong:
            return ExitSignal(
                symbol=symbol,
                signal_type='stop_loss',
                strength=SignalStrength.CRITICAL,
                reason=f'Stop loss triggered: {pnl_pct*100:.2f}% loss',
                current_pnl_pct=pnl_pct * 100,
                recommended_action='close_immediately',
                urgency='immediate',
                metadata={'threshold': self.stop_loss_strong}
            )
        elif effective_pnl <= self.stop_loss_moderate:
            return ExitSignal(
                symbol=symbol,
                signal_type='stop_loss_warning',
                strength=SignalStrength.STRONG,
                reason=f'Approaching stop loss: {pnl_pct*100:.2f}% loss',
                current_pnl_pct=pnl_pct * 100,
                recommended_action='tighten_stop',
                urgency='soon',
                metadata={'threshold': self.stop_loss_moderate}
            )
        return None

    def _check_take_profit(self, symbol: str, pnl_pct: float, side: str) -> Optional[ExitSignal]:
        """Check take profit conditions."""
        effective_pnl = pnl_pct if side == 'long' else -pnl_pct

        if effective_pnl >= self.take_profit_strong:
            return ExitSignal(
                symbol=symbol,
                signal_type='take_profit',
                strength=SignalStrength.STRONG,
                reason=f'Take profit target reached: {pnl_pct*100:.2f}% gain',
                current_pnl_pct=pnl_pct * 100,
                recommended_action='close_position',
                urgency='soon',
                metadata={'threshold': self.take_profit_strong}
            )
        elif effective_pnl >= self.take_profit_moderate:
            return ExitSignal(
                symbol=symbol,
                signal_type='take_profit_partial',
                strength=SignalStrength.MODERATE,
                reason=f'Moderate profit: {pnl_pct*100:.2f}% - consider partial exit',
                current_pnl_pct=pnl_pct * 100,
                recommended_action='trail_stop',
                urgency='monitor',
                metadata={'threshold': self.take_profit_moderate}
            )
        return None

    def _check_rsi(
        self,
        symbol: str,
        pnl_pct: float,
        side: str,
        technicals: Dict[str, Any]
    ) -> Optional[ExitSignal]:
        """Check RSI overbought/oversold conditions."""
        rsi = technicals.get('rsi_14')
        if rsi is None:
            return None

        # For long positions, overbought is exit signal
        # For short positions, oversold is exit signal
        if side == 'long':
            if rsi >= self.rsi_overbought_strong:
                return ExitSignal(
                    symbol=symbol,
                    signal_type='rsi_overbought',
                    strength=SignalStrength.STRONG,
                    reason=f'RSI strongly overbought at {rsi:.1f}',
                    current_pnl_pct=pnl_pct * 100,
                    recommended_action='close_position',
                    urgency='soon',
                    metadata={'rsi': rsi, 'threshold': self.rsi_overbought_strong}
                )
            elif rsi >= self.rsi_overbought_moderate:
                return ExitSignal(
                    symbol=symbol,
                    signal_type='rsi_overbought_warning',
                    strength=SignalStrength.MODERATE,
                    reason=f'RSI overbought at {rsi:.1f}',
                    current_pnl_pct=pnl_pct * 100,
                    recommended_action='tighten_stop',
                    urgency='monitor',
                    metadata={'rsi': rsi, 'threshold': self.rsi_overbought_moderate}
                )
        else:  # short position
            if rsi <= self.rsi_oversold_strong:
                return ExitSignal(
                    symbol=symbol,
                    signal_type='rsi_oversold',
                    strength=SignalStrength.STRONG,
                    reason=f'RSI strongly oversold at {rsi:.1f}',
                    current_pnl_pct=pnl_pct * 100,
                    recommended_action='close_position',
                    urgency='soon',
                    metadata={'rsi': rsi, 'threshold': self.rsi_oversold_strong}
                )
            elif rsi <= self.rsi_oversold_moderate:
                return ExitSignal(
                    symbol=symbol,
                    signal_type='rsi_oversold_warning',
                    strength=SignalStrength.MODERATE,
                    reason=f'RSI oversold at {rsi:.1f}',
                    current_pnl_pct=pnl_pct * 100,
                    recommended_action='tighten_stop',
                    urgency='monitor',
                    metadata={'rsi': rsi, 'threshold': self.rsi_oversold_moderate}
                )
        return None

    def _check_ma_breakdown(
        self,
        symbol: str,
        pnl_pct: float,
        side: str,
        technicals: Dict[str, Any]
    ) -> Optional[ExitSignal]:
        """Check moving average breakdown."""
        above_sma_10 = technicals.get('above_sma_10')
        above_sma_20 = technicals.get('above_sma_20')

        if above_sma_10 is None:
            return None

        # For long positions, breaking below MAs is bearish
        if side == 'long':
            if above_sma_10 is False and above_sma_20 is False:
                return ExitSignal(
                    symbol=symbol,
                    signal_type='ma_breakdown',
                    strength=SignalStrength.MODERATE,
                    reason='Price below both SMA 10 and SMA 20',
                    current_pnl_pct=pnl_pct * 100,
                    recommended_action='consider_exit',
                    urgency='monitor',
                    metadata={'above_sma_10': above_sma_10, 'above_sma_20': above_sma_20}
                )
            elif above_sma_10 is False:
                return ExitSignal(
                    symbol=symbol,
                    signal_type='ma_warning',
                    strength=SignalStrength.WEAK,
                    reason='Price below SMA 10',
                    current_pnl_pct=pnl_pct * 100,
                    recommended_action='tighten_stop',
                    urgency='monitor',
                    metadata={'above_sma_10': above_sma_10}
                )
        return None

    def _check_pattern_breakdown(
        self,
        symbol: str,
        pnl_pct: float,
        side: str,
        patterns: Dict[str, Any]
    ) -> Optional[ExitSignal]:
        """Check for pattern breakdown signals."""
        detected_patterns = patterns.get('patterns', [])

        for pattern in detected_patterns:
            pattern_type = pattern.get('type', '')

            # Bearish patterns for long positions
            if side == 'long':
                if pattern_type in ['double_top', 'head_shoulders', 'breakdown']:
                    return ExitSignal(
                        symbol=symbol,
                        signal_type='pattern_bearish',
                        strength=SignalStrength.MODERATE,
                        reason=f'Bearish pattern detected: {pattern_type}',
                        current_pnl_pct=pnl_pct * 100,
                        recommended_action='consider_exit',
                        urgency='soon',
                        metadata={'pattern': pattern}
                    )

            # Bullish patterns for short positions
            else:
                if pattern_type in ['double_bottom', 'inv_head_shoulders', 'breakout']:
                    return ExitSignal(
                        symbol=symbol,
                        signal_type='pattern_bullish',
                        strength=SignalStrength.MODERATE,
                        reason=f'Bullish pattern detected: {pattern_type}',
                        current_pnl_pct=pnl_pct * 100,
                        recommended_action='consider_exit',
                        urgency='soon',
                        metadata={'pattern': pattern}
                    )

        return None

    def get_strongest_signal(self, signals: List[ExitSignal]) -> Optional[ExitSignal]:
        """Get the strongest signal from a list."""
        if not signals:
            return None
        return max(signals, key=lambda x: x.strength.value)

    def should_exit(self, signals: List[ExitSignal]) -> bool:
        """Determine if position should be exited based on signals."""
        if not signals:
            return False

        strongest = self.get_strongest_signal(signals)
        return strongest.strength.value >= SignalStrength.STRONG.value

    def get_exit_reason(self, signals: List[ExitSignal]) -> str:
        """Get combined exit reason from signals."""
        if not signals:
            return "No exit signals"

        reasons = [s.reason for s in signals if s.strength.value >= SignalStrength.MODERATE.value]
        return "; ".join(reasons) if reasons else signals[0].reason
