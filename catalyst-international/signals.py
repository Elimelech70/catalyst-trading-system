"""
Name of Application: Catalyst Trading System
Name of file: signals.py
Version: 3.0.0
Last Updated: 2026-01-24
Purpose: Context-separated exit signal detection with pattern deterioration and hold signals

REVISION HISTORY:
v3.0.0 (2026-01-24) - Context-separated architecture
  - Loads thresholds from config/exit_context.yaml
  - Added pattern deterioration detection (lower highs, MACD divergence, EMA cross)
  - Added improved hold signal detection (higher lows, above MAs, volume)
  - Hot-reload capability for context changes
  - Added confidence scores to recommendations
  - Market-specific threshold overrides (HKEX/US)

v2.0.0 (2026-01-10) - Pattern-based trading
  - Added HOLD signals (not just exits)
  - Pattern continuation detection
  - Configurable thresholds
  - Signal strength classification

v1.0.0 (2025-01-01) - Initial implementation (exit signals only)

ARCHITECTURE:
  This tool (signals.py) contains LOGIC only.
  Context (thresholds, rules) lives in config/exit_context.yaml.

  Benefits:
  - Update thresholds without code changes
  - Hot-reload config without restart
  - Market-specific overrides
  - Easy A/B testing of different settings

Cost Model:
- All signal detection is FREE (rules-based)
- Haiku consultation only for MODERATE/CONSULT_AI signals (~$0.05/call)
"""

import logging
import yaml
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Hong Kong timezone for HKEX
HK_TZ = ZoneInfo("Asia/Hong_Kong")


# =============================================================================
# CONTEXT LOADER
# =============================================================================

_context_cache: Optional[dict] = None
_context_mtime: Optional[float] = None


def get_context_path() -> Path:
    """Get path to exit context file."""
    paths = [
        Path(__file__).parent / "config" / "exit_context.yaml",
        Path("/root/catalyst-international/config/exit_context.yaml"),
        Path("/root/Catalyst-Trading-System-International/catalyst-international/config/exit_context.yaml"),
        Path("./config/exit_context.yaml"),
    ]
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"exit_context.yaml not found. Searched: {[str(p) for p in paths]}")


def load_exit_context(force_reload: bool = False) -> dict:
    """
    Load exit context with automatic hot-reload.

    Checks file modification time and reloads if changed.
    """
    global _context_cache, _context_mtime

    try:
        context_path = get_context_path()
        current_mtime = context_path.stat().st_mtime

        if force_reload or _context_cache is None or current_mtime > _context_mtime:
            with open(context_path) as f:
                _context_cache = yaml.safe_load(f)
            _context_mtime = current_mtime
            logger.info(f"Loaded exit context v{_context_cache.get('version')} from {context_path}")

        return _context_cache
    except FileNotFoundError:
        logger.warning("exit_context.yaml not found, using defaults")
        return _get_default_context()


def reload_context() -> dict:
    """Force reload of exit context."""
    return load_exit_context(force_reload=True)


def _get_default_context() -> dict:
    """Get default context if config file not found."""
    return {
        "version": "default",
        "thresholds": {
            "stop_loss": {"strong": -0.03, "moderate": -0.02, "weak": -0.01},
            "take_profit": {"strong": 0.10, "moderate": 0.06, "weak": 0.03},
            "trailing_stop": {"activation_pct": 0.03, "drop_pct": 0.025},
            "time_stop": {"minutes_flat": 120},
        },
        "technical": {
            "rsi": {"overbought_strong": 85, "overbought_moderate": 75, "healthy_low": 40, "healthy_high": 65},
            "volume": {"collapse_strong": 0.25, "collapse_moderate": 0.40, "healthy_min": 0.80, "strong_min": 1.20},
        },
        "pattern_exit_rules": {
            "lower_high": {"enabled": True, "consecutive_required": 2, "min_drop_pct": 0.005, "signal_strength": "MODERATE"},
            "ema_cross_down": {"enabled": True, "fast_period": 9, "slow_period": 20, "signal_strength": "MODERATE"},
        },
        "hold_conditions": {
            "higher_lows": {"enabled": True, "consecutive_required": 2, "min_rise_pct": 0.005, "signal_strength": "STRONG"},
            "rsi_healthy": {"enabled": True, "min_rsi": 45, "max_rsi": 70, "signal_strength": "WEAK"},
        },
        "signal_weights": {
            "exit_signals": {"stop_loss_hit": 1.0, "trailing_stop_hit": 0.8, "rsi_overbought": 0.7, "volume_collapse": 0.6},
            "hold_signals": {"higher_lows": 0.8, "above_moving_averages": 0.6, "rsi_healthy": 0.3},
        },
    }


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
    weight: float = 0.5


@dataclass
class SignalAnalysis:
    """Complete signal analysis for a position."""
    hold_signals: List[Signal] = field(default_factory=list)
    exit_signals: List[Signal] = field(default_factory=list)
    pattern_health: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5

    @property
    def recommendation(self) -> str:
        """Overall recommendation: HOLD, EXIT, or CONSULT_AI."""
        strong_exits = [s for s in self.exit_signals if s.strength == SignalStrength.STRONG]
        strong_holds = [s for s in self.hold_signals if s.strength == SignalStrength.STRONG]
        moderate_exits = [s for s in self.exit_signals if s.strength == SignalStrength.MODERATE]

        # Strong exit signals = immediate exit
        if strong_exits:
            return "EXIT"

        # Multiple moderate exits with no strong holds = consult AI
        if len(moderate_exits) >= 2 and not strong_holds:
            return "CONSULT_AI"

        # Strong holds with no concerning exits = hold
        if strong_holds and not moderate_exits:
            return "HOLD"

        # Mixed signals = consult AI
        if moderate_exits and strong_holds:
            return "CONSULT_AI"

        # Single moderate exit = consult AI
        if moderate_exits:
            return "CONSULT_AI"

        # Default to hold if no exit signals
        if not self.exit_signals:
            return "HOLD"

        return "CONSULT_AI"

    @property
    def immediate_exit(self) -> bool:
        """Check if any STRONG exit signal."""
        return any(s.strength == SignalStrength.STRONG for s in self.exit_signals)

    @property
    def consult_ai(self) -> bool:
        """Check if AI consultation needed."""
        return self.recommendation == "CONSULT_AI"

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
        elif rec == "CONSULT_AI":
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
            f"Confidence: {self.confidence:.0%} | "
            f"Reason: {self.reason}"
        )


# =============================================================================
# THRESHOLD HELPER
# =============================================================================

def _get_thresholds(context: dict, market: str = "hkex") -> dict:
    """Get thresholds with market-specific overrides applied."""
    base = {}
    for key, value in context.get('thresholds', {}).items():
        if isinstance(value, dict):
            base[key] = value.copy()
        else:
            base[key] = value

    overrides = context.get('market_overrides', {}).get(market, {}).get('thresholds', {})

    # Deep merge overrides
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value

    return base


# =============================================================================
# P&L SIGNAL DETECTION
# =============================================================================

def detect_pnl_signals(
    pnl_pct: float,
    high_watermark_pnl_pct: float,
    entry_price: float,
    context: dict,
    market: str = "hkex"
) -> List[Signal]:
    """Detect P&L-based exit signals using context configuration."""
    signals = []
    thresholds = _get_thresholds(context, market)
    weights = context.get('signal_weights', {}).get('exit_signals', {})

    sl = thresholds.get('stop_loss', {})
    tp = thresholds.get('take_profit', {})
    ts = thresholds.get('trailing_stop', {})

    # Stop Loss
    if pnl_pct <= sl.get('strong', -0.03):
        signals.append(Signal(
            name="stop_loss_hit",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"Stop loss hit: {pnl_pct*100:.1f}% <= {sl.get('strong', -0.03)*100:.1f}%",
            value=pnl_pct,
            threshold=sl.get('strong', -0.03),
            weight=weights.get('stop_loss_hit', 1.0)
        ))
    elif pnl_pct <= sl.get('moderate', -0.02):
        signals.append(Signal(
            name="stop_loss_near",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"Near stop loss: {pnl_pct*100:.1f}%",
            value=pnl_pct,
            threshold=sl.get('moderate', -0.02),
            weight=weights.get('stop_loss_hit', 1.0) * 0.7
        ))

    # Take Profit (MODERATE - check pattern before exiting)
    if pnl_pct >= tp.get('strong', 0.10):
        signals.append(Signal(
            name="take_profit_target",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,  # Not STRONG - let pattern decide
            reason=f"Take profit target: {pnl_pct*100:.1f}% >= {tp.get('strong', 0.10)*100:.1f}%",
            value=pnl_pct,
            threshold=tp.get('strong', 0.10),
            weight=weights.get('take_profit', 0.6)
        ))

    # Trailing Stop
    if entry_price and high_watermark_pnl_pct > 0:
        activation = ts.get('activation_pct', 0.03)
        drop_pct = ts.get('drop_pct', 0.025)

        if high_watermark_pnl_pct >= activation:
            drawdown = high_watermark_pnl_pct - pnl_pct
            if drawdown >= drop_pct:
                signals.append(Signal(
                    name="trailing_stop_hit",
                    signal_type=SignalType.EXIT,
                    strength=SignalStrength.STRONG,
                    reason=f"Trailing stop: {drawdown*100:.1f}% drop from {high_watermark_pnl_pct*100:.1f}% high",
                    value=drawdown,
                    threshold=drop_pct,
                    weight=weights.get('trailing_stop_hit', 0.8)
                ))

    # Healthy profit - HOLD signal
    if 0.01 <= pnl_pct <= tp.get('moderate', 0.06):
        signals.append(Signal(
            name="healthy_profit",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.MODERATE,
            reason=f"Profitable at {pnl_pct*100:.1f}%, room to run",
            value=pnl_pct,
            weight=0.4
        ))

    return signals


# =============================================================================
# TECHNICAL SIGNAL DETECTION
# =============================================================================

def detect_rsi_signals(rsi: Optional[float], context: dict) -> List[Signal]:
    """Detect RSI-based signals using context configuration."""
    signals = []

    if rsi is None:
        return signals

    rsi_th = context.get('technical', {}).get('rsi', {})
    weights = context.get('signal_weights', {}).get('exit_signals', {})
    hold_conditions = context.get('hold_conditions', {})

    # EXIT signals - overbought
    if rsi >= rsi_th.get('overbought_strong', 85):
        signals.append(Signal(
            name="rsi_overbought",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"RSI overbought: {rsi:.0f} >= {rsi_th.get('overbought_strong', 85)}",
            value=rsi,
            threshold=rsi_th.get('overbought_strong', 85),
            weight=weights.get('rsi_overbought', 0.7)
        ))
    elif rsi >= rsi_th.get('overbought_moderate', 75):
        signals.append(Signal(
            name="rsi_elevated",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"RSI elevated: {rsi:.0f}",
            value=rsi,
            threshold=rsi_th.get('overbought_moderate', 75),
            weight=weights.get('rsi_overbought', 0.7) * 0.7
        ))

    # HOLD signals - healthy RSI
    rsi_healthy = hold_conditions.get('rsi_healthy', {})
    if rsi_healthy.get('enabled', True):
        min_rsi = rsi_healthy.get('min_rsi', 45)
        max_rsi = rsi_healthy.get('max_rsi', 70)
        if min_rsi <= rsi <= max_rsi:
            signals.append(Signal(
                name="rsi_healthy",
                signal_type=SignalType.HOLD,
                strength=SignalStrength[rsi_healthy.get('signal_strength', 'WEAK')],
                reason=f"RSI {rsi:.0f} in healthy range ({min_rsi}-{max_rsi})",
                value=rsi,
                weight=context.get('signal_weights', {}).get('hold_signals', {}).get('rsi_healthy', 0.3)
            ))

    return signals


def detect_volume_signals(
    current_volume: float,
    entry_volume: float,
    context: dict
) -> List[Signal]:
    """Detect volume-based signals using context configuration."""
    signals = []

    if not entry_volume or entry_volume == 0:
        return signals

    ratio = current_volume / entry_volume
    vol_th = context.get('technical', {}).get('volume', {})
    exit_weights = context.get('signal_weights', {}).get('exit_signals', {})
    hold_weights = context.get('signal_weights', {}).get('hold_signals', {})

    # EXIT signals - volume collapse
    if ratio <= vol_th.get('collapse_strong', 0.25):
        signals.append(Signal(
            name="volume_collapse",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            reason=f"Volume collapsed: {ratio*100:.0f}% of entry",
            value=ratio,
            threshold=vol_th.get('collapse_strong', 0.25),
            weight=exit_weights.get('volume_collapse', 0.6)
        ))
    elif ratio <= vol_th.get('collapse_moderate', 0.40):
        signals.append(Signal(
            name="volume_weak",
            signal_type=SignalType.EXIT,
            strength=SignalStrength.MODERATE,
            reason=f"Volume weak: {ratio*100:.0f}% of entry",
            value=ratio,
            threshold=vol_th.get('collapse_moderate', 0.40),
            weight=exit_weights.get('volume_collapse', 0.6) * 0.7
        ))

    # HOLD signals - strong/healthy volume
    if ratio >= vol_th.get('strong_min', 1.20):
        signals.append(Signal(
            name="volume_strong",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.STRONG,
            reason=f"Strong volume: {ratio*100:.0f}% of entry",
            value=ratio,
            weight=hold_weights.get('volume_confirmation', 0.6)
        ))
    elif ratio >= vol_th.get('healthy_min', 0.80):
        signals.append(Signal(
            name="volume_healthy",
            signal_type=SignalType.HOLD,
            strength=SignalStrength.MODERATE,
            reason=f"Healthy volume: {ratio*100:.0f}% of entry",
            value=ratio,
            weight=hold_weights.get('volume_confirmation', 0.6) * 0.7
        ))

    return signals


def detect_trend_signals(
    current_price: float,
    technicals: Dict[str, Any],
    context: dict
) -> List[Signal]:
    """Detect trend-based signals (VWAP, EMA positions)."""
    signals = []
    hold_conditions = context.get('hold_conditions', {})
    hold_weights = context.get('signal_weights', {}).get('hold_signals', {})

    vwap = technicals.get('vwap')
    ema9 = technicals.get('ema_9') or technicals.get('ema9')
    sma20 = technicals.get('sma_20') or technicals.get('sma20') or technicals.get('ema20')

    # Above VWAP - HOLD
    if vwap and current_price:
        vwap_rule = hold_conditions.get('above_vwap', {})
        if vwap_rule.get('enabled', True):
            min_above = vwap_rule.get('min_above_pct', 0.01)
            if current_price > vwap * (1 + min_above):
                signals.append(Signal(
                    name="above_vwap",
                    signal_type=SignalType.HOLD,
                    strength=SignalStrength[vwap_rule.get('signal_strength', 'MODERATE')],
                    reason=f"Price {((current_price/vwap)-1)*100:.1f}% above VWAP",
                    value=(current_price - vwap) / vwap,
                    weight=hold_weights.get('above_vwap', 0.4)
                ))

        # Below VWAP - EXIT (moderate)
        if current_price < vwap * 0.98:  # 2% below VWAP
            signals.append(Signal(
                name="below_vwap",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason=f"Price {((vwap/current_price)-1)*100:.1f}% below VWAP",
                value=(current_price - vwap) / vwap,
                weight=0.4
            ))

    # Above key moving averages - HOLD
    ma_rule = hold_conditions.get('above_moving_averages', {})
    if ma_rule.get('enabled', True):
        above_ema9 = ema9 and current_price > ema9
        above_sma20 = sma20 and current_price > sma20

        if above_ema9 and above_sma20:
            signals.append(Signal(
                name="above_key_mas",
                signal_type=SignalType.HOLD,
                strength=SignalStrength[ma_rule.get('signal_strength', 'MODERATE')],
                reason="Price above EMA9 and SMA20 - trend intact",
                weight=hold_weights.get('above_moving_averages', 0.6)
            ))

    # MACD
    macd = technicals.get('macd')
    macd_signal = technicals.get('macd_signal')
    macd_histogram = technicals.get('macd_histogram')

    if macd is not None and macd_signal is not None:
        if macd < macd_signal:  # Bearish
            signals.append(Signal(
                name="macd_bearish",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason="MACD bearish crossover",
                value=macd_histogram,
                weight=0.5
            ))
        elif macd > macd_signal:  # Bullish
            signals.append(Signal(
                name="macd_bullish",
                signal_type=SignalType.HOLD,
                strength=SignalStrength.MODERATE,
                reason="MACD bullish",
                value=macd_histogram,
                weight=0.5
            ))

    return signals


# =============================================================================
# PATTERN DETERIORATION DETECTION
# =============================================================================

def detect_pattern_deterioration(
    price_history: List[Dict],
    technicals: Dict[str, Any],
    entry_pattern: Optional[Dict],
    context: dict
) -> List[Signal]:
    """Detect pattern breakdown signals."""
    signals = []
    rules = context.get('pattern_exit_rules', {})
    weights = context.get('signal_weights', {}).get('exit_signals', {})

    if not price_history or len(price_history) < 5:
        return signals

    # === LOWER HIGH DETECTION ===
    lh_rule = rules.get('lower_high', {})
    if lh_rule.get('enabled', True):
        lower_highs = _count_lower_highs(price_history, lh_rule.get('min_drop_pct', 0.005))
        if lower_highs >= lh_rule.get('consecutive_required', 2):
            signals.append(Signal(
                name="lower_high",
                signal_type=SignalType.EXIT,
                strength=SignalStrength[lh_rule.get('signal_strength', 'MODERATE')],
                reason=f"{lower_highs} consecutive lower highs - momentum weakening",
                value=lower_highs,
                weight=weights.get('lower_high', 0.4)
            ))

    # === MACD DIVERGENCE ===
    div_rule = rules.get('macd_divergence', {})
    if div_rule.get('enabled', True):
        divergence = _detect_macd_divergence(price_history, technicals, div_rule.get('lookback_periods', 5))
        if divergence:
            signals.append(Signal(
                name="macd_divergence",
                signal_type=SignalType.EXIT,
                strength=SignalStrength[div_rule.get('signal_strength', 'MODERATE')],
                reason="Bearish divergence: price up but MACD down",
                weight=weights.get('macd_divergence', 0.5)
            ))

    # === EMA CROSS DOWN ===
    ema_rule = rules.get('ema_cross_down', {})
    if ema_rule.get('enabled', True):
        fast_key = f"ema_{ema_rule.get('fast_period', 9)}"
        slow_key = f"ema_{ema_rule.get('slow_period', 20)}"
        ema_fast = technicals.get(fast_key) or technicals.get('ema9') or technicals.get('ema_9')
        ema_slow = technicals.get(slow_key) or technicals.get('sma_20') or technicals.get('sma20') or technicals.get('ema20')

        if ema_fast and ema_slow and ema_fast < ema_slow:
            signals.append(Signal(
                name="ema_cross_down",
                signal_type=SignalType.EXIT,
                strength=SignalStrength[ema_rule.get('signal_strength', 'MODERATE')],
                reason=f"EMA{ema_rule.get('fast_period', 9)} crossed below SMA{ema_rule.get('slow_period', 20)}",
                value=ema_fast - ema_slow,
                weight=weights.get('ema_cross_down', 0.4)
            ))

    # === PATTERN SUPPORT BREAKDOWN ===
    if entry_pattern:
        bd_rule = rules.get('pattern_breakdown', {})
        if bd_rule.get('enabled', True):
            support = entry_pattern.get('support') or entry_pattern.get('stop_loss')
            if support:
                current_price = price_history[-1].get('close', 0)
                if current_price and support:
                    break_pct = (support - current_price) / support
                    if break_pct >= bd_rule.get('support_break_pct', 0.02):
                        signals.append(Signal(
                            name="pattern_breakdown",
                            signal_type=SignalType.EXIT,
                            strength=SignalStrength.STRONG,
                            reason=f"Pattern support broken: {break_pct*100:.1f}% below support",
                            value=break_pct,
                            threshold=bd_rule.get('support_break_pct', 0.02),
                            weight=weights.get('pattern_breakdown', 0.9)
                        ))

    # === CONSOLIDATION STALL ===
    stall_rule = rules.get('consolidation_stall', {})
    if stall_rule.get('enabled', True) and len(price_history) >= stall_rule.get('max_periods', 10):
        recent = price_history[-stall_rule.get('max_periods', 10):]
        highs = [bar.get('high', 0) for bar in recent]
        lows = [bar.get('low', 0) for bar in recent]
        if highs and lows and min(lows) > 0:
            range_pct = (max(highs) - min(lows)) / min(lows)
            if range_pct < stall_rule.get('max_range_pct', 0.02):
                signals.append(Signal(
                    name="consolidation_stall",
                    signal_type=SignalType.EXIT,
                    strength=SignalStrength[stall_rule.get('signal_strength', 'WEAK')],
                    reason=f"Momentum stalled - {range_pct*100:.1f}% range for {len(recent)} periods",
                    value=range_pct,
                    weight=weights.get('consolidation_stall', 0.2)
                ))

    return signals


def _count_lower_highs(price_history: List[Dict], min_drop_pct: float) -> int:
    """Count consecutive lower highs in price data."""
    if len(price_history) < 3:
        return 0

    count = 0
    highs = [bar.get('high', 0) for bar in price_history[-5:]]

    for i in range(len(highs) - 1, 0, -1):
        if highs[i-1] > 0 and highs[i] < highs[i-1] * (1 - min_drop_pct):
            count += 1
        else:
            break

    return count


def _detect_macd_divergence(
    price_history: List[Dict],
    technicals: Dict[str, Any],
    lookback: int
) -> bool:
    """Detect bearish MACD divergence (price up, MACD down)."""
    if len(price_history) < lookback:
        return False

    recent_highs = [bar.get('high', 0) for bar in price_history[-lookback:]]
    if not recent_highs or max(recent_highs[:-1]) == 0:
        return False

    # Check if price making higher highs
    price_higher_high = recent_highs[-1] > max(recent_highs[:-1])

    # Check MACD
    macd = technicals.get('macd', 0)
    macd_signal = technicals.get('macd_signal', 0)

    # Bearish if MACD below signal while price at highs
    macd_bearish = macd is not None and macd_signal is not None and macd < macd_signal

    return price_higher_high and macd_bearish


# =============================================================================
# HOLD SIGNAL DETECTION (PATTERN HEALTH)
# =============================================================================

def analyze_pattern_health(
    price_history: List[Dict],
    technicals: Dict[str, Any],
    context: dict
) -> Dict[str, Any]:
    """Analyze overall pattern health for hold decisions."""
    hold_rules = context.get('hold_conditions', {})

    health = {
        'higher_lows': False,
        'higher_lows_count': 0,
        'above_ema9': False,
        'above_sma20': False,
        'above_vwap': False,
        'volume_confirming': False,
        'macd_expanding': False,
        'rsi_healthy': False,
    }

    if not price_history or len(price_history) < 3:
        return health

    current_price = price_history[-1].get('close', 0)

    # Higher Lows
    hl_rule = hold_rules.get('higher_lows', {})
    if hl_rule.get('enabled', True):
        lows = [bar.get('low', 0) for bar in price_history[-5:]]
        higher_low_count = 0
        for i in range(1, len(lows)):
            if lows[i-1] > 0 and lows[i] > lows[i-1] * (1 + hl_rule.get('min_rise_pct', 0.005)):
                higher_low_count += 1
        health['higher_lows_count'] = higher_low_count
        health['higher_lows'] = higher_low_count >= hl_rule.get('consecutive_required', 2)

    # Above MAs
    ema9 = technicals.get('ema_9') or technicals.get('ema9')
    sma20 = technicals.get('sma_20') or technicals.get('sma20') or technicals.get('ema20')
    vwap = technicals.get('vwap')

    if ema9 and current_price:
        health['above_ema9'] = current_price > ema9
    if sma20 and current_price:
        health['above_sma20'] = current_price > sma20
    if vwap and current_price:
        vwap_rule = hold_rules.get('above_vwap', {})
        min_above = vwap_rule.get('min_above_pct', 0.01)
        health['above_vwap'] = current_price > vwap * (1 + min_above)

    # RSI Healthy
    rsi = technicals.get('rsi', 50)
    rsi_rule = hold_rules.get('rsi_healthy', {})
    if rsi is not None:
        health['rsi_healthy'] = rsi_rule.get('min_rsi', 45) <= rsi <= rsi_rule.get('max_rsi', 70)

    # MACD Expanding
    macd_hist = technicals.get('macd_histogram', 0)
    health['macd_expanding'] = macd_hist is not None and macd_hist > 0

    return health


def pattern_health_to_signals(pattern_health: Dict[str, Any], context: dict) -> List[Signal]:
    """Convert pattern health analysis to hold signals."""
    signals = []
    hold_rules = context.get('hold_conditions', {})
    weights = context.get('signal_weights', {}).get('hold_signals', {})

    if pattern_health.get('higher_lows'):
        rule = hold_rules.get('higher_lows', {})
        signals.append(Signal(
            name="higher_lows",
            signal_type=SignalType.HOLD,
            strength=SignalStrength[rule.get('signal_strength', 'STRONG')],
            reason=f"Higher lows pattern ({pattern_health.get('higher_lows_count', 2)}x) - healthy uptrend",
            weight=weights.get('higher_lows', 0.8)
        ))

    if pattern_health.get('above_ema9') and pattern_health.get('above_sma20'):
        rule = hold_rules.get('above_moving_averages', {})
        signals.append(Signal(
            name="above_key_mas",
            signal_type=SignalType.HOLD,
            strength=SignalStrength[rule.get('signal_strength', 'MODERATE')],
            reason="Price above EMA9 and SMA20 - trend intact",
            weight=weights.get('above_moving_averages', 0.6)
        ))

    if pattern_health.get('macd_expanding'):
        rule = hold_rules.get('macd_expansion', {})
        if rule.get('enabled', True):
            signals.append(Signal(
                name="macd_expanding",
                signal_type=SignalType.HOLD,
                strength=SignalStrength[rule.get('signal_strength', 'MODERATE')],
                reason="MACD histogram positive - momentum accelerating",
                weight=weights.get('macd_expansion', 0.5)
            ))

    return signals


# =============================================================================
# TIME SIGNAL DETECTION
# =============================================================================

def detect_time_signals(
    entry_time: Optional[datetime],
    pnl_pct: float,
    context: dict,
    market: str = "hkex"
) -> List[Signal]:
    """Detect time-based exit signals."""
    signals = []
    time_th = context.get('thresholds', {}).get('time_stop', {})
    market_times = context.get('market_overrides', {}).get(market, {}).get('time_rules', {})

    now = datetime.now(HK_TZ)
    current_time_only = now.time()

    # Market close proximity
    if market == "hkex":
        if current_time_only >= time(15, 50):
            signals.append(Signal(
                name="market_closing",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.STRONG,
                reason="Market closing in <10 minutes",
                weight=0.9
            ))
        elif current_time_only >= time(15, 30):
            signals.append(Signal(
                name="market_closing_soon",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason="Market closing in <30 minutes",
                weight=0.6
            ))

        # Lunch break
        if time(11, 50) <= current_time_only < time(12, 0):
            signals.append(Signal(
                name="lunch_break_soon",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason="Lunch break starting soon",
                weight=0.5
            ))

    # Time stop for flat positions
    if entry_time:
        if isinstance(entry_time, str):
            try:
                entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            except:
                return signals

        if entry_time.tzinfo is None:
            entry_time = entry_time.replace(tzinfo=HK_TZ)

        minutes_held = (now - entry_time).total_seconds() / 60

        # Flat position too long
        if abs(pnl_pct) < 0.01 and minutes_held >= time_th.get('minutes_flat', 120):
            signals.append(Signal(
                name="time_stop_flat",
                signal_type=SignalType.EXIT,
                strength=SignalStrength.MODERATE,
                reason=f"Position flat for {minutes_held:.0f} minutes",
                value=minutes_held,
                threshold=time_th.get('minutes_flat', 120),
                weight=0.4
            ))

    return signals


# =============================================================================
# RECOMMENDATION LOGIC
# =============================================================================

def _determine_recommendation(
    exit_signals: List[Signal],
    hold_signals: List[Signal],
    context: dict
) -> Tuple[str, float]:
    """Determine overall recommendation based on signals."""

    # STRONG exit = immediate exit
    strong_exits = [s for s in exit_signals if s.strength == SignalStrength.STRONG]
    if strong_exits:
        return "EXIT", 0.95

    # Calculate weighted scores
    exit_score = sum(s.weight for s in exit_signals)
    hold_score = sum(s.weight for s in hold_signals)

    # No signals = HOLD (maintain position)
    if not exit_signals and not hold_signals:
        return "HOLD", 0.5

    # Only hold signals = HOLD with confidence
    if not exit_signals and hold_signals:
        return "HOLD", min(0.9, 0.5 + hold_score * 0.1)

    # Only exit signals (MODERATE) = CONSULT_AI
    if exit_signals and not hold_signals:
        moderate_exits = [s for s in exit_signals if s.strength == SignalStrength.MODERATE]
        if moderate_exits:
            return "CONSULT_AI", 0.6
        return "HOLD", 0.5  # Only WEAK exits

    # Conflicting signals = CONSULT_AI
    if exit_score > hold_score * 0.8:  # Exit signals winning
        return "CONSULT_AI", 0.5 + min(0.4, (exit_score - hold_score) * 0.1)
    else:  # Hold signals winning
        return "HOLD", 0.5 + min(0.4, (hold_score - exit_score) * 0.1)


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def analyze_position(
    position: Dict[str, Any],
    quote: Dict[str, Any],
    technicals: Dict[str, Any],
    price_history: Optional[List[Dict]] = None,
    entry_pattern: Optional[Dict] = None,
    entry_volume: Optional[float] = None,
    market: str = "hkex"
) -> SignalAnalysis:
    """
    Complete signal analysis for a position using context configuration.

    Args:
        position: Position data dict with keys:
            - symbol, entry_price, current_price, pnl_pct
            - high_watermark (optional), entry_time (optional)
        quote: Quote data dict with keys:
            - price (or last_price), volume, bid, ask
        technicals: Technical indicators dict with keys:
            - rsi, macd, macd_signal, macd_histogram, vwap, ema_9, sma_20
        price_history: Recent OHLCV bars for pattern analysis (optional)
        entry_pattern: Original entry pattern info (optional)
        entry_volume: Volume at time of entry (optional)
        market: "hkex" or "us" for market-specific rules

    Returns:
        SignalAnalysis with hold_signals, exit_signals, pattern_health, and recommendation
    """
    context = load_exit_context()

    exit_signals = []
    hold_signals = []
    pattern_health = {}

    # Extract position data
    pnl_pct = position.get('pnl_pct', 0) or 0
    entry_price = position.get('entry_price', 0) or 0
    current_price = position.get('current_price') or quote.get('price') or quote.get('last_price') or 0
    high_watermark = position.get('high_watermark', current_price) or current_price
    entry_time = position.get('entry_time')

    # Calculate high watermark P&L
    if entry_price and high_watermark:
        high_watermark_pnl_pct = (high_watermark - entry_price) / entry_price
    else:
        high_watermark_pnl_pct = pnl_pct

    # === P&L SIGNALS ===
    pnl_sigs = detect_pnl_signals(pnl_pct, high_watermark_pnl_pct, entry_price, context, market)
    for s in pnl_sigs:
        if s.signal_type == SignalType.EXIT:
            exit_signals.append(s)
        else:
            hold_signals.append(s)

    # === RSI SIGNALS ===
    rsi = technicals.get('rsi')
    rsi_sigs = detect_rsi_signals(rsi, context)
    for s in rsi_sigs:
        if s.signal_type == SignalType.EXIT:
            exit_signals.append(s)
        else:
            hold_signals.append(s)

    # === VOLUME SIGNALS ===
    current_volume = quote.get('volume', 0)
    if entry_volume and current_volume:
        vol_sigs = detect_volume_signals(current_volume, entry_volume, context)
        for s in vol_sigs:
            if s.signal_type == SignalType.EXIT:
                exit_signals.append(s)
            else:
                hold_signals.append(s)

    # === TREND SIGNALS ===
    trend_sigs = detect_trend_signals(current_price, technicals, context)
    for s in trend_sigs:
        if s.signal_type == SignalType.EXIT:
            exit_signals.append(s)
        else:
            hold_signals.append(s)

    # === PATTERN DETERIORATION ===
    if price_history:
        pattern_exits = detect_pattern_deterioration(price_history, technicals, entry_pattern, context)
        exit_signals.extend(pattern_exits)

    # === PATTERN HEALTH (HOLD SIGNALS) ===
    if price_history:
        pattern_health = analyze_pattern_health(price_history, technicals, context)
        health_holds = pattern_health_to_signals(pattern_health, context)
        hold_signals.extend(health_holds)

    # === TIME SIGNALS ===
    time_sigs = detect_time_signals(entry_time, pnl_pct, context, market)
    for s in time_sigs:
        if s.signal_type == SignalType.EXIT:
            exit_signals.append(s)
        else:
            hold_signals.append(s)

    # === DETERMINE RECOMMENDATION ===
    _, confidence = _determine_recommendation(exit_signals, hold_signals, context)

    return SignalAnalysis(
        exit_signals=exit_signals,
        hold_signals=hold_signals,
        pattern_health=pattern_health,
        confidence=confidence
    )


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
    """Test signal detection with context."""

    print("=" * 60)
    print("SIGNAL DETECTION MODULE v3.0.0")
    print("Context-Separated Architecture")
    print("=" * 60)

    # Load and display context
    context = load_exit_context()
    print(f"\nContext version: {context.get('version')}")
    print(f"Stop loss (strong): {context.get('thresholds', {}).get('stop_loss', {}).get('strong', 'N/A')}")
    print(f"Pattern rules enabled: {list(context.get('pattern_exit_rules', {}).keys())}")
    print(f"Hold conditions enabled: {list(context.get('hold_conditions', {}).keys())}")

    # Test position - slightly losing with pattern history
    test_position = {
        'symbol': '01024',
        'entry_price': 75.00,
        'current_price': 74.00,
        'pnl_pct': -0.0133,
        'high_watermark': 76.50,
        'entry_time': datetime.now(HK_TZ),
    }

    test_quote = {
        'price': 74.00,
        'volume': 500000,
    }

    test_technicals = {
        'rsi': 55.0,
        'macd': 0.5,
        'macd_signal': 0.3,
        'macd_histogram': 0.2,
        'vwap': 74.50,
        'ema_9': 74.30,
        'sma_20': 74.10,
    }

    # Simulate price history with higher lows
    test_price_history = [
        {'high': 75.00, 'low': 73.00, 'close': 74.50},
        {'high': 75.50, 'low': 73.50, 'close': 75.00},
        {'high': 76.00, 'low': 74.00, 'close': 75.50},
        {'high': 76.50, 'low': 74.20, 'close': 74.00},
        {'high': 75.00, 'low': 73.80, 'close': 74.00},
    ]

    print(f"\n--- Test 1: Healthy Position ---")
    print(f"Position: {test_position['symbol']}")
    print(f"P&L: {test_position['pnl_pct']*100:.2f}%")

    analysis = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        price_history=test_price_history,
        entry_volume=600000,
        market="hkex"
    )

    print(f"\n{analysis.summary()}")
    print(f"\nHold Signals ({len(analysis.hold_signals)}):")
    for s in analysis.hold_signals:
        print(f"  [{s.strength.value:8}] {s.name}: {s.reason}")
    print(f"\nExit Signals ({len(analysis.exit_signals)}):")
    for s in analysis.exit_signals:
        print(f"  [{s.strength.value:8}] {s.name}: {s.reason}")

    print(f"\nPattern Health: {analysis.pattern_health}")

    # Test stop loss scenario
    print(f"\n--- Test 2: Stop Loss Hit ---")
    test_position['pnl_pct'] = -0.04
    analysis2 = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        price_history=test_price_history,
        entry_volume=600000,
        market="hkex"
    )
    print(f"{analysis2.summary()}")
    print(f"Immediate Exit: {analysis2.immediate_exit}")

    # Test RSI overbought
    print(f"\n--- Test 3: RSI Overbought ---")
    test_position['pnl_pct'] = 0.05
    test_technicals['rsi'] = 88.0
    analysis3 = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        price_history=test_price_history,
        entry_volume=600000,
        market="hkex"
    )
    print(f"{analysis3.summary()}")
    print(f"Immediate Exit: {analysis3.immediate_exit}")

    # Test lower highs pattern
    print(f"\n--- Test 4: Lower Highs (Pattern Deterioration) ---")
    test_technicals['rsi'] = 55.0
    test_position['pnl_pct'] = 0.02
    # Simulate lower highs
    lower_highs_history = [
        {'high': 78.00, 'low': 75.00, 'close': 77.00},
        {'high': 77.50, 'low': 74.50, 'close': 76.50},
        {'high': 77.00, 'low': 74.00, 'close': 76.00},
        {'high': 76.00, 'low': 73.50, 'close': 75.00},
        {'high': 75.00, 'low': 73.00, 'close': 74.00},
    ]
    analysis4 = analyze_position(
        position=test_position,
        quote=test_quote,
        technicals=test_technicals,
        price_history=lower_highs_history,
        entry_volume=600000,
        market="hkex"
    )
    print(f"{analysis4.summary()}")

    print("\n" + "=" * 60)
    print("Signal detection tests complete!")
    print("=" * 60)
