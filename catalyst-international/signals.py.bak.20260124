"""
Name of Application: Catalyst Trading System
Name of file: signals.py
Version: 2.0.0
Last Updated: 2026-01-10
Purpose: Pattern-based hold and exit signal detection

REVISION HISTORY:
v2.0.0 (2026-01-10) - Complete rewrite for pattern-based trading
- Added HOLD signals (not just exits)
- Pattern continuation detection
- Configurable thresholds
- Signal strength classification
- SignalAnalysis dataclass with recommendation

v1.0.0 (2025-01-01) - Initial implementation (exit signals only)

Description:
Detects signals that indicate whether to HOLD or EXIT a position
based on technical patterns, momentum, and market conditions.
Positions stay open as long as patterns remain bullish.
Exit on pattern failure, not time-based rules.

Cost Model:
- All signal detection is FREE (rules-based)
- Haiku consultation only for MODERATE signals (~$0.05/call)
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

# Hong Kong timezone for HKEX
HK_TZ = ZoneInfo("Asia/Hong_Kong")


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class SignalStrength(Enum):
    """Signal strength levels."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class SignalType(Enum):
    """Type of signal."""
    HOLD = "hold"
    EXIT = "exit"


@dataclass
class Signal:
    """Individual signal with metadata."""
    name: str
    signal_type: SignalType
    strength: SignalStrength
    reason: str
    value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass 
class SignalAnalysis:
    """Complete signal analysis for a position."""
    hold_signals: List[Signal] = field(default_factory=list)
    exit_signals: List[Signal] = field(default_factory=list)
    
    @property
    def recommendation(self) -> str:
        """Overall recommendation: HOLD, EXIT, or REVIEW."""
        strong_exits = [s for s in self.exit_signals if s.strength == SignalStrength.STRONG]
        strong_holds = [s for s in self.hold_signals if s.strength == SignalStrength.STRONG]
        moderate_exits = [s for s in self.exit_signals if s.strength == SignalStrength.MODERATE]
        
        # Strong exit signals = immediate exit
        if strong_exits:
            return "EXIT"
        
        # Multiple moderate exits = review (consult Haiku)
        if len(moderate_exits) >= 2:
            return "REVIEW"
        
        # Strong holds with no concerning exits = hold
        if strong_holds and not moderate_exits:
            return "HOLD"
        
        # Mixed signals = review
        if moderate_exits and strong_holds:
            return "REVIEW"
        
        # Default to hold if no exit signals
        if not self.exit_signals:
            return "HOLD"
        
        return "REVIEW"
    
    @property
    def signal_strength(self) -> str:
        """Overall signal strength description."""
        rec = self.recommendation
        if rec == "EXIT":
            return "strong_exit"
        elif rec == "HOLD" and any(s.strength == SignalStrength.STRONG for s in self.hold_signals):
            return "strong_hold"
        elif rec == "HOLD":
            return "hold"
        else:
            return "review"
    
    @property
    def reason(self) -> str:
        """Human-readable reason for recommendation."""
        rec = self.recommendation
        if rec == "EXIT":
            signals = [s.name for s in self.exit_signals if s.strength == SignalStrength.STRONG]
            return f"Strong exit: {', '.join(signals)}"
        elif rec == "REVIEW":
            exits = [s.name for s in self.exit_signals if s.strength == SignalStrength.MODERATE]
            return f"Review needed: {', '.join(exits)}"
        else:
            signals = [s.name for s in self.hold_signals if s.strength in (SignalStrength.STRONG, SignalStrength.MODERATE)]
            return f"Holding: {', '.join(signals[:3])}" if signals else "No exit signals"
    
    @property
    def hold_signal_names(self) -> List[str]:
        """List of hold signal names for database storage."""
        return [s.name for s in self.hold_signals]
    
    @property
    def exit_signal_names(self) -> List[str]:
        """List of exit signal names for database storage."""
        return [s.name for s in self.exit_signals]
    
    def summary(self) -> str:
        """Summary string for logging."""
        return (
            f"Recommendation: {self.recommendation} | "
            f"Holds: {len(self.hold_signals)} | "
            f"Exits: {len(self.exit_signals)} | "
            f"Reason: {self.reason}"
        )


# =============================================================================
# THRESHOLD CONFIGURATION
# =============================================================================

@dataclass
class SignalThresholds:
    """Configurable thresholds for signal detection."""
    
    # P&L Thresholds
    stop_loss_strong: float = -0.03      # -3%
    stop_loss_moderate: float = -0.02    # -2%
    stop_loss_weak: float = -0.01        # -1%
    
    take_profit_strong: float = 0.08     # +8%
    take_profit_moderate: float = 0.05   # +5%
    take_profit_weak: float = 0.03       # +3%
    
    trailing_stop_pct: float = 0.03      # 3% from high watermark
    
    # RSI Thresholds
    rsi_overbought_strong: float = 85
    rsi_overbought_moderate: float = 75
    rsi_overbought_weak: float = 70
    rsi_oversold: float = 30
    rsi_healthy_low: float = 40
    rsi_healthy_high: float = 65
    
    # Volume Thresholds (relative to entry)
    volume_dying_strong: float = 0.25    # <25% of entry
    volume_dying_moderate: float = 0.40  # <40% of entry
    volume_dying_weak: float = 0.60      # <60% of entry
    volume_healthy: float = 0.80         # >80% of entry
    volume_strong: float = 1.20          # >120% of entry
    
    # Time Thresholds (minutes)
    time_stop_strong: int = 180          # 3 hours flat
    time_stop_moderate: int = 120        # 2 hours flat
    market_close_strong: int = 10        # 10 min to close
    market_close_moderate: int = 30      # 30 min to close


# Default thresholds
DEFAULT_THRESHOLDS = SignalThresholds()


# =============================================================================
# SIGNAL DETECTION FUNCTIONS
# =============================================================================

def detect_pnl_signals(
    pnl_pct: float,
    high_watermark_pnl_pct: float,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS
) -> List[Signal]:
    """
    Detect P&L-based signals.
    
    Args:
        pnl_pct: Current P&L percentage (e.g., -0.02 for -2%)
        high_watermark_pnl_pct: Highest P&L since entry
        thresholds: Signal thresholds configuration
        
    Returns:
        List of Signal objects
    """
    signals = []
    
    # === EXIT SIGNALS ===
    
    # Stop loss
    if pnl_pct <= thresholds.stop_loss_strong:
        signals.append(Signal(
            name="stop_loss_hit",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"P&L {pnl_pct*100:.1f}% <= {thresholds.stop_loss_strong*100}%",
            value=pnl_pct,
            threshold=thresholds.stop_loss_strong
        ))
    elif pnl_pct <= thresholds.stop_loss_moderate:
        signals.append(Signal(
            name="stop_loss_near",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"P&L {pnl_pct*100:.1f}% approaching stop",
            value=pnl_pct,
            threshold=thresholds.stop_loss_moderate
        ))
    
    # Trailing stop (from high watermark)
    drawdown_from_high = high_watermark_pnl_pct - pnl_pct
    if high_watermark_pnl_pct > 0.02 and drawdown_from_high >= thresholds.trailing_stop_pct:
        signals.append(Signal(
            name="trailing_stop_hit",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"Drawdown {drawdown_from_high*100:.1f}% from high of {high_watermark_pnl_pct*100:.1f}%",
            value=drawdown_from_high,
            threshold=thresholds.trailing_stop_pct
        ))
    
    # === HOLD SIGNALS ===
    
    # Healthy profit, not overextended
    if 0.01 <= pnl_pct <= thresholds.take_profit_moderate:
        signals.append(Signal(
            name="healthy_profit",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.MODERATE,
            reason=f"Profitable at {pnl_pct*100:.1f}%, room to run",
            value=pnl_pct
        ))
    
    # Strong profit - consider taking some
    if pnl_pct >= thresholds.take_profit_strong:
        signals.append(Signal(
            name="profit_target_reached",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,  # Not STRONG - let patterns decide
            reason=f"Target reached at {pnl_pct*100:.1f}%",
            value=pnl_pct,
            threshold=thresholds.take_profit_strong
        ))
    
    return signals


def detect_rsi_signals(
    rsi: float,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS
) -> List[Signal]:
    """
    Detect RSI-based signals.
    
    Args:
        rsi: Current RSI value (0-100)
        thresholds: Signal thresholds configuration
        
    Returns:
        List of Signal objects
    """
    signals = []
    
    if rsi is None:
        return signals
    
    # === EXIT SIGNALS ===
    
    if rsi >= thresholds.rsi_overbought_strong:
        signals.append(Signal(
            name="rsi_overbought",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"RSI {rsi:.1f} >= {thresholds.rsi_overbought_strong} (exhaustion)",
            value=rsi,
            threshold=thresholds.rsi_overbought_strong
        ))
    elif rsi >= thresholds.rsi_overbought_moderate:
        signals.append(Signal(
            name="rsi_high",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"RSI {rsi:.1f} getting extended",
            value=rsi,
            threshold=thresholds.rsi_overbought_moderate
        ))
    
    # Momentum dead
    if rsi <= thresholds.rsi_oversold:
        signals.append(Signal(
            name="rsi_momentum_dead",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"RSI {rsi:.1f} - momentum collapsed",
            value=rsi,
            threshold=thresholds.rsi_oversold
        ))
    
    # === HOLD SIGNALS ===
    
    if thresholds.rsi_healthy_low <= rsi <= thresholds.rsi_healthy_high:
        signals.append(Signal(
            name="rsi_healthy",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.STRONG,
            reason=f"RSI {rsi:.1f} in healthy range",
            value=rsi
        ))
    
    return signals


def detect_volume_signals(
    current_volume: float,
    entry_volume: float,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS
) -> List[Signal]:
    """
    Detect volume-based signals.
    
    Args:
        current_volume: Current trading volume
        entry_volume: Volume at time of entry
        thresholds: Signal thresholds configuration
        
    Returns:
        List of Signal objects
    """
    signals = []
    
    if not entry_volume or entry_volume == 0:
        return signals
    
    volume_ratio = current_volume / entry_volume
    
    # === EXIT SIGNALS ===
    
    if volume_ratio <= thresholds.volume_dying_strong:
        signals.append(Signal(
            name="volume_dying",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"Volume collapsed to {volume_ratio*100:.0f}% of entry",
            value=volume_ratio,
            threshold=thresholds.volume_dying_strong
        ))
    elif volume_ratio <= thresholds.volume_dying_moderate:
        signals.append(Signal(
            name="volume_weak",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"Volume weak at {volume_ratio*100:.0f}% of entry",
            value=volume_ratio,
            threshold=thresholds.volume_dying_moderate
        ))
    
    # === HOLD SIGNALS ===
    
    if volume_ratio >= thresholds.volume_strong:
        signals.append(Signal(
            name="volume_strong",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.STRONG,
            reason=f"Volume strong at {volume_ratio*100:.0f}% of entry",
            value=volume_ratio
        ))
    elif volume_ratio >= thresholds.volume_healthy:
        signals.append(Signal(
            name="volume_healthy",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.MODERATE,
            reason=f"Volume healthy at {volume_ratio*100:.0f}% of entry",
            value=volume_ratio
        ))
    
    return signals


def detect_trend_signals(
    current_price: float,
    vwap: Optional[float],
    ema20: Optional[float],
    macd_histogram: Optional[float] = None,
    macd_signal: Optional[str] = None
) -> List[Signal]:
    """
    Detect trend-based signals.
    
    Args:
        current_price: Current price
        vwap: Volume Weighted Average Price
        ema20: 20-period EMA
        macd_histogram: MACD histogram value
        macd_signal: MACD signal ('bullish', 'bearish', 'neutral')
        
    Returns:
        List of Signal objects
    """
    signals = []
    
    # === VWAP Position ===
    if vwap and current_price:
        vwap_distance_pct = (current_price - vwap) / vwap
        
        if vwap_distance_pct >= 0.01:  # >1% above VWAP
            signals.append(Signal(
                name="above_vwap",
                signal_type=SignalType.HOLD,
                strength=SignalStrength.STRONG,
                reason=f"Price {vwap_distance_pct*100:.1f}% above VWAP",
                value=vwap_distance_pct
            ))
        elif vwap_distance_pct <= -0.02:  # >2% below VWAP
            signals.append(Signal(
                name="below_vwap",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason=f"Price {abs(vwap_distance_pct)*100:.1f}% below VWAP",
                value=vwap_distance_pct
            ))
    
    # === EMA20 Position ===
    if ema20 and current_price:
        ema_distance_pct = (current_price - ema20) / ema20
        
        if ema_distance_pct >= 0.005:  # Above EMA20
            signals.append(Signal(
                name="above_ema20",
                signal_type=SignalType.HOLD,
                strength=SignalStrength.MODERATE,
                reason=f"Price above EMA20",
                value=ema_distance_pct
            ))
        elif ema_distance_pct <= -0.01:  # Below EMA20
            signals.append(Signal(
                name="below_ema20",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason=f"Price {abs(ema_distance_pct)*100:.1f}% below EMA20",
                value=ema_distance_pct
            ))
    
    # === MACD ===
    if macd_signal == 'bearish':
        signals.append(Signal(
            name="macd_bearish",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason="MACD bearish crossover",
            value=macd_histogram
        ))
    elif macd_signal == 'bullish':
        signals.append(Signal(
            name="macd_bullish",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.STRONG,
            reason="MACD bullish",
            value=macd_histogram
        ))
    
    return signals


def detect_time_signals(
    entry_time: datetime,
    current_time: Optional[datetime] = None,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS
) -> List[Signal]:
    """
    Detect time-based signals (HKEX specific).
    
    Args:
        entry_time: When position was opened
        current_time: Current time (defaults to now in HK timezone)
        thresholds: Signal thresholds configuration
        
    Returns:
        List of Signal objects
    """
    signals = []
    
    if current_time is None:
        current_time = datetime.now(HK_TZ)
    
    # Ensure timezone aware
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=HK_TZ)
    
    current_time_only = current_time.time()
    
    # Market close proximity (16:00 HKT)
    if current_time_only >= time(15, 50):  # After 15:50
        signals.append(Signal(
            name="market_closing",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason="Market closing in <10 minutes",
        ))
    elif current_time_only >= time(15, 30):  # After 15:30
        signals.append(Signal(
            name="market_closing_soon",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason="Market closing in <30 minutes",
        ))
    
    # Lunch break proximity (12:00-13:00 HKT)
    if time(11, 50) <= current_time_only < time(12, 0):
        signals.append(Signal(
            name="lunch_break_soon",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason="Lunch break starting soon",
        ))
    
    # Time in position (not necessarily bad for swing trades)
    if entry_time:
        # Ensure entry_time is timezone aware
        if entry_time.tzinfo is None:
            entry_time = entry_time.replace(tzinfo=HK_TZ)
        
        hours_held = (current_time - entry_time).total_seconds() / 3600
        if hours_held >= 24:  # Held overnight - that's fine for swing trades
            signals.append(Signal(
                name="overnight_hold",
                signal_type=SignalType.HOLD,
                strength=SignalStrength.WEAK,
                reason=f"Position held {hours_held:.1f} hours (overnight OK)",
            ))
    
    return signals


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def analyze_position(
    position: Dict[str, Any],
    quote: Dict[str, Any],
    technicals: Dict[str, Any],
    entry_volume: Optional[float] = None,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS
) -> SignalAnalysis:
    """
    Complete signal analysis for a position.
    
    Args:
        position: Position data dict with keys:
            - symbol, entry_price, current_price, pnl_pct
            - high_watermark (optional), entry_time (optional)
        quote: Quote data dict with keys:
            - price (or last_price), volume, bid, ask
        technicals: Technical indicators dict with keys:
            - rsi, macd_histogram, macd_signal, vwap, ema20
        entry_volume: Volume at time of entry (optional)
        thresholds: Signal thresholds configuration
        
    Returns:
        SignalAnalysis with hold_signals, exit_signals, and recommendation
    """
    analysis = SignalAnalysis()
    
    # Extract values safely
    pnl_pct = position.get('pnl_pct', 0) or 0
    entry_price = position.get('entry_price', 0) or 0
    high_watermark = position.get('high_watermark') or position.get('entry_price') or 0
    current_price = position.get('current_price') or quote.get('price') or quote.get('last_price') or 0
    
    # Calculate high watermark P&L
    if entry_price and high_watermark:
        high_watermark_pnl_pct = (high_watermark - entry_price) / entry_price
    else:
        high_watermark_pnl_pct = pnl_pct
    
    # Collect all signals
    all_signals = []
    
    # P&L signals
    all_signals.extend(detect_pnl_signals(pnl_pct, high_watermark_pnl_pct, thresholds))
    
    # RSI signals
    rsi = technicals.get('rsi')
    if rsi is not None:
        all_signals.extend(detect_rsi_signals(rsi, thresholds))
    
    # Volume signals
    current_volume = quote.get('volume', 0)
    if entry_volume and current_volume:
        all_signals.extend(detect_volume_signals(current_volume, entry_volume, thresholds))
    
    # Trend signals
    all_signals.extend(detect_trend_signals(
        current_price=current_price,
        vwap=technicals.get('vwap'),
        ema20=technicals.get('ema20'),
        macd_histogram=technicals.get('macd_histogram'),
        macd_signal=technicals.get('macd_signal')
    ))
    
    # Time signals
    entry_time = position.get('entry_time')
    if entry_time:
        all_signals.extend(detect_time_signals(entry_time, thresholds=thresholds))
    
    # Categorize signals
    for signal in all_signals:
        if signal.signal_type == SignalType.HOLD:
            analysis.hold_signals.append(signal)
        else:
            analysis.exit_signals.append(signal)
    
    return analysis


# =============================================================================
# CONVENIENCE FUNCTIONS FOR DATABASE
# =============================================================================

def get_vwap_position(current_price: float, vwap: Optional[float]) -> str:
    """Get VWAP position as string for database storage."""
    if not vwap or not current_price:
        return "unknown"
    diff_pct = (current_price - vwap) / vwap
    if diff_pct > 0.005:
        return "above"
    elif diff_pct < -0.005:
        return "below"
    return "at"


def get_ema_position(current_price: float, ema: Optional[float]) -> str:
    """Get EMA position as string for database storage."""
    if not ema or not current_price:
        return "unknown"
    diff_pct = (current_price - ema) / ema
    if diff_pct > 0.005:
        return "above"
    elif diff_pct < -0.005:
        return "below"
    return "at"


def get_macd_signal_str(macd: Optional[float], macd_signal_line: Optional[float]) -> str:
    """Get MACD signal as string for database storage."""
    if macd is None or macd_signal_line is None:
        return "unknown"
    if macd > macd_signal_line:
        return "bullish"
    elif macd < macd_signal_line:
        return "bearish"
    return "neutral"


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    """Test signal detection."""
    
    print("=" * 60)
    print("Signal Detection Module v2.0.0")
    print("=" * 60)
    
    # Test position - slightly losing
    test_position = {
        'symbol': '01024',
        'entry_price': 75.00,
        'current_price': 74.00,
        'pnl_pct': -0.0133,  # -1.33%
        'high_watermark': 76.50,
        'entry_time': datetime.now(HK_TZ),
    }
    
    test_quote = {
        'price': 74.00,
        'volume': 500000,
    }
    
    test_technicals = {
        'rsi': 55.0,
        'macd_signal': 'neutral',
        'vwap': 74.50,
        'ema20': 74.20,
    }
    
    print(f"\nTest Position: {test_position['symbol']}")
    print(f"Entry: HKD {test_position['entry_price']:.2f}")
    print(f"Current: HKD {test_position['current_price']:.2f}")
    print(f"P&L: {test_position['pnl_pct']*100:.2f}%")
    print(f"High Watermark: HKD {test_position['high_watermark']:.2f}")
    
    analysis = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        entry_volume=600000
    )
    
    print(f"\n{analysis.summary()}")
    
    print(f"\nHold Signals ({len(analysis.hold_signals)}):")
    for s in analysis.hold_signals:
        print(f"  • {s.name} ({s.strength.value}): {s.reason}")
    
    print(f"\nExit Signals ({len(analysis.exit_signals)}):")
    for s in analysis.exit_signals:
        print(f"  • {s.name} ({s.strength.value}): {s.reason}")
    
    print("\n" + "=" * 60)
    
    # Test strong exit scenario
    print("\nTest: Strong Exit Scenario (RSI 90)")
    test_technicals['rsi'] = 90.0
    analysis2 = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        entry_volume=600000
    )
    print(f"{analysis2.summary()}")
    
    # Test stop loss scenario
    print("\nTest: Stop Loss Scenario (-3.5%)")
    test_position['pnl_pct'] = -0.035
    test_technicals['rsi'] = 45.0
    analysis3 = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        entry_volume=600000
    )
    print(f"{analysis3.summary()}")
    
    print("\n" + "=" * 60)
    print("Signal detection tests complete!")
