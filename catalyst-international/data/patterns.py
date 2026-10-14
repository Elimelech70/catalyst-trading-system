"""
Name of Application: Catalyst Trading System
Name of file: patterns.py
Version: 1.2.0
Last Updated: 2026-01-08
Purpose: Chart pattern detection with relaxed breakout criteria

REVISION HISTORY:
v1.2.0 (2026-01-08) - Fix broken pattern detection
- CRITICAL FIX: Changed get_ohlcv() to get_historical() 
- MarketData class only has get_historical() method, not get_ohlcv()
- This fix restores all pattern detection functionality

v1.1.0 (2026-01-06) - Relaxed breakout detection for paper trading
- Allow continuation breakouts (prev_close can be up to 2% above resistance)
- Add "near_breakout" pattern for stocks within 1% of resistance
- Add "momentum_continuation" pattern for strong trending stocks
- Log near-miss patterns for learning
- Reduced volume requirement from 1.5x to 1.3x for Tier 3 patterns

v1.0.0 (2025-12-06) - Initial implementation
- 8 pattern types: bull_flag, bear_flag, cup_handle, triangles, ABCD, breakout, breakdown

Description:
This module detects chart patterns in price data for trading signals.
Patterns are detected using technical analysis of OHLCV data.

BUG FIX APPLIED:
Line 66 changed from:
    df = self.market_data.get_ohlcv(symbol, days=days)
To:
    df = self.market_data.get_historical(symbol, timeframe="1d", bars=days)
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

logger = logging.getLogger(__name__)


class PatternDetector:
    """Chart pattern detection for HKEX stocks."""

    def __init__(self, market_data: Any = None):
        """Initialize pattern detector.

        Args:
            market_data: MarketDataClient instance for fetching OHLCV data
        """
        self.market_data = market_data

    def set_market_data(self, market_data: Any):
        """Set market data client."""
        self.market_data = market_data

    def detect_patterns(self, symbol: str, days: int = 30) -> list[dict]:
        """Detect all patterns for a symbol.

        Args:
            symbol: Stock symbol (e.g., "0700" for Tencent)
            days: Number of days of data to analyze

        Returns:
            List of detected patterns with entry/exit levels
        """
        if not self.market_data:
            logger.warning("No market data client set")
            return []

        # Get historical data
        # FIX: Changed from get_ohlcv() to get_historical()
        # MarketData class only has get_historical() method
        try:
            df = self.market_data.get_historical(symbol, timeframe="1d", bars=days)
            if df is None or len(df) < 20:
                return []
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {e}")
            return []

        patterns = []

        # Run all pattern detectors
        detectors = [
            self._detect_bull_flag,
            self._detect_bear_flag,
            self._detect_cup_handle,
            self._detect_ascending_triangle,
            self._detect_descending_triangle,
            self._detect_ABCD,
            self._detect_breakout,
            self._detect_breakdown,
            self._detect_near_breakout,           # NEW: Within 1% of breakout
            self._detect_momentum_continuation,   # NEW: Strong trend continuation
        ]

        for detector in detectors:
            try:
                pattern = detector(df)
                if pattern:
                    pattern["symbol"] = symbol
                    patterns.append(pattern)
            except Exception as e:
                logger.error(f"Pattern detection error ({detector.__name__}): {e}")

        return patterns

    # =========================================================================
    # NOTE: The rest of the file (all _detect_* methods) remains unchanged.
    # Only the get_ohlcv -> get_historical fix is needed.
    # =========================================================================

    def _detect_bull_flag(self, df: pd.DataFrame) -> dict | None:
        """Detect bull flag pattern.
        
        Bull flag: Strong uptrend (pole) followed by consolidation (flag).
        """
        if len(df) < 20:
            return None
            
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        
        # Look for pole (strong uptrend in first half)
        mid = len(df) // 2
        pole_return = (close[mid] - close[0]) / close[0]
        
        if pole_return < 0.05:  # Need at least 5% gain for pole
            return None
            
        # Look for consolidation (flag) in second half
        flag_high = high[mid:].max()
        flag_low = low[mid:].min()
        flag_range = (flag_high - flag_low) / flag_low
        
        if flag_range > 0.05:  # Flag should be tight (<5% range)
            return None
            
        # Check for downward slope in flag
        flag_slope = (close[-1] - close[mid]) / close[mid]
        if flag_slope > 0.02:  # Flag should slope down or flat
            return None
            
        entry = close[-1]
        stop = flag_low * 0.98
        target = entry + (entry - stop) * 2.5
        
        return {
            "pattern": "bull_flag",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "confidence": 0.7,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_bear_flag(self, df: pd.DataFrame) -> dict | None:
        """Detect bear flag pattern."""
        if len(df) < 20:
            return None
            
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        
        mid = len(df) // 2
        pole_return = (close[mid] - close[0]) / close[0]
        
        if pole_return > -0.05:
            return None
            
        flag_high = high[mid:].max()
        flag_low = low[mid:].min()
        flag_range = (flag_high - flag_low) / flag_low
        
        if flag_range > 0.05:
            return None
            
        flag_slope = (close[-1] - close[mid]) / close[mid]
        if flag_slope < -0.02:
            return None
            
        entry = close[-1]
        stop = flag_high * 1.02
        target = entry - (stop - entry) * 2.5
        
        return {
            "pattern": "bear_flag",
            "direction": "short",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "confidence": 0.7,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_cup_handle(self, df: pd.DataFrame) -> dict | None:
        """Detect cup and handle pattern."""
        if len(df) < 30:
            return None
            
        close = df["close"].values
        
        # Find local minima for cup bottom
        order = min(5, len(close) // 4)
        local_min_idx = argrelextrema(close, np.less, order=order)[0]
        
        if len(local_min_idx) == 0:
            return None
            
        # Cup should be in middle third
        cup_bottom_idx = local_min_idx[len(local_min_idx) // 2]
        if cup_bottom_idx < len(close) // 4 or cup_bottom_idx > 3 * len(close) // 4:
            return None
            
        # Left rim and right rim should be similar
        left_rim = close[:cup_bottom_idx].max()
        right_rim = close[cup_bottom_idx:].max()
        
        if abs(left_rim - right_rim) / left_rim > 0.05:
            return None
            
        # Handle should be small pullback
        handle_low = close[-5:].min()
        if (right_rim - handle_low) / right_rim > 0.05:
            return None
            
        entry = right_rim
        stop = handle_low * 0.98
        target = entry + (entry - stop) * 2.5
        
        return {
            "pattern": "cup_handle",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "confidence": 0.75,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_ascending_triangle(self, df: pd.DataFrame) -> dict | None:
        """Detect ascending triangle pattern."""
        if len(df) < 20:
            return None
            
        high = df["high"].values
        low = df["low"].values
        
        # Flat resistance (highs should be similar)
        recent_highs = high[-10:]
        resistance = recent_highs.max()
        if (resistance - recent_highs.min()) / resistance > 0.02:
            return None
            
        # Rising support (lows should be increasing)
        recent_lows = low[-10:]
        support_slope = np.polyfit(range(len(recent_lows)), recent_lows, 1)[0]
        if support_slope <= 0:
            return None
            
        entry = resistance * 1.01
        stop = recent_lows[-1] * 0.98
        target = entry + (entry - stop) * 2.0
        
        return {
            "pattern": "ascending_triangle",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "confidence": 0.7,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_descending_triangle(self, df: pd.DataFrame) -> dict | None:
        """Detect descending triangle pattern."""
        if len(df) < 20:
            return None
            
        high = df["high"].values
        low = df["low"].values
        
        # Flat support
        recent_lows = low[-10:]
        support = recent_lows.min()
        if (recent_lows.max() - support) / support > 0.02:
            return None
            
        # Falling resistance
        recent_highs = high[-10:]
        resistance_slope = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
        if resistance_slope >= 0:
            return None
            
        entry = support * 0.99
        stop = recent_highs[-1] * 1.02
        target = entry - (stop - entry) * 2.0
        
        return {
            "pattern": "descending_triangle",
            "direction": "short",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "confidence": 0.7,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_ABCD(self, df: pd.DataFrame) -> dict | None:
        """Detect ABCD pattern."""
        if len(df) < 20:
            return None
            
        close = df["close"].values
        
        # Find local extrema
        order = min(3, len(close) // 6)
        local_max_idx = argrelextrema(close, np.greater, order=order)[0]
        local_min_idx = argrelextrema(close, np.less, order=order)[0]
        
        if len(local_max_idx) < 2 or len(local_min_idx) < 2:
            return None
            
        # ABCD pattern: A (high) -> B (low) -> C (high) -> D (low)
        # CD leg should be similar to AB leg (Fibonacci retracement)
        a_idx = local_max_idx[-2]
        b_idx = local_min_idx[-2]
        c_idx = local_max_idx[-1]
        d_idx = local_min_idx[-1]
        
        if not (a_idx < b_idx < c_idx < d_idx):
            return None
            
        ab_move = close[a_idx] - close[b_idx]
        cd_move = close[c_idx] - close[d_idx]
        
        # CD should be 0.618-1.618 of AB
        ratio = cd_move / ab_move if ab_move != 0 else 0
        if ratio < 0.5 or ratio > 2.0:
            return None
            
        entry = close[-1]
        stop = close[d_idx] * 0.98
        target = entry + ab_move * 0.618
        
        return {
            "pattern": "ABCD",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "confidence": 0.65,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_breakout(self, df: pd.DataFrame) -> dict | None:
        """Detect breakout pattern (price breaking above resistance)."""
        if len(df) < 20:
            return None
            
        close = df["close"].values
        high = df["high"].values
        volume = df["volume"].values if "volume" in df.columns else None
        
        # Calculate resistance from recent highs (excluding last bar)
        lookback = min(20, len(df) - 1)
        resistance = high[-lookback:-1].max()
        
        # Current price must be above resistance
        current_price = close[-1]
        prev_close = close[-2]
        
        # v1.1.0: Allow continuation breakouts
        # Previous close can be up to 2% above resistance (not just below)
        if prev_close > resistance * 1.02:
            return None  # Too far above - not a fresh breakout
            
        # Current price must be at least 0.5% above resistance
        if current_price < resistance * 1.005:
            return None
            
        # Volume confirmation (relaxed from 1.5x to 1.3x for Tier 3)
        if volume is not None:
            avg_volume = volume[-20:-1].mean()
            current_volume = volume[-1]
            if current_volume < avg_volume * 1.3:
                return None
                
        entry = current_price
        stop = resistance * 0.98
        target = entry + (entry - stop) * 2.5
        
        return {
            "pattern": "breakout",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "resistance": round(resistance, 4),
            "confidence": 0.8,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_breakdown(self, df: pd.DataFrame) -> dict | None:
        """Detect breakdown pattern (price breaking below support)."""
        if len(df) < 20:
            return None
            
        close = df["close"].values
        low = df["low"].values
        volume = df["volume"].values if "volume" in df.columns else None
        
        lookback = min(20, len(df) - 1)
        support = low[-lookback:-1].min()
        
        current_price = close[-1]
        if current_price > support * 0.995:
            return None
            
        if volume is not None:
            avg_volume = volume[-20:-1].mean()
            current_volume = volume[-1]
            if current_volume < avg_volume * 1.5:
                return None
                
        entry = current_price
        stop = support * 1.02
        target = entry - (stop - entry) * 2.5
        
        return {
            "pattern": "breakdown",
            "direction": "short",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "support": round(support, 4),
            "confidence": 0.8,
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_near_breakout(self, df: pd.DataFrame) -> dict | None:
        """Detect stocks within 1% of breakout level (v1.1.0 addition)."""
        if len(df) < 20:
            return None
            
        close = df["close"].values
        high = df["high"].values
        
        lookback = min(20, len(df) - 1)
        resistance = high[-lookback:-1].max()
        
        current_price = close[-1]
        distance_pct = (resistance - current_price) / resistance
        
        # Within 1% of resistance but not yet broken out
        if distance_pct < 0 or distance_pct > 0.01:
            return None
            
        logger.info(f"Near breakout detected: {distance_pct*100:.2f}% from resistance {resistance}")
        
        entry = resistance * 1.005
        stop = resistance * 0.97
        target = entry + (entry - stop) * 2.0
        
        return {
            "pattern": "near_breakout",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "resistance": round(resistance, 4),
            "distance_pct": round(distance_pct * 100, 2),
            "confidence": 0.6,  # Lower confidence - watchlist candidate
            "detected_at": datetime.now().isoformat(),
        }

    def _detect_momentum_continuation(self, df: pd.DataFrame) -> dict | None:
        """Detect strong trending stocks for momentum continuation (v1.1.0 addition)."""
        if len(df) < 20:
            return None
            
        close = df["close"].values
        
        # Calculate short-term and medium-term trends
        sma_5 = close[-5:].mean()
        sma_10 = close[-10:].mean()
        sma_20 = close[-20:].mean()
        
        current_price = close[-1]
        
        # Strong uptrend: price > SMA5 > SMA10 > SMA20
        if not (current_price > sma_5 > sma_10 > sma_20):
            return None
            
        # Price should be at least 3% above SMA20
        if (current_price - sma_20) / sma_20 < 0.03:
            return None
            
        # Calculate ATR for stop placement
        high = df["high"].values
        low = df["low"].values
        tr = np.maximum(high - low, np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1)))
        atr = tr[-14:].mean()
        
        entry = current_price
        stop = entry - (atr * 1.5)
        target = entry + (atr * 3.0)
        
        return {
            "pattern": "momentum_continuation",
            "direction": "long",
            "entry": round(entry, 4),
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "trend_strength": round((current_price - sma_20) / sma_20 * 100, 2),
            "confidence": 0.65,
            "detected_at": datetime.now().isoformat(),
        }


# Singleton instance
_pattern_detector: PatternDetector | None = None


def get_pattern_detector(market_data: Any = None) -> PatternDetector:
    """Get or create pattern detector singleton."""
    global _pattern_detector
    if _pattern_detector is None:
        _pattern_detector = PatternDetector(market_data)
    elif market_data and _pattern_detector.market_data is None:
        _pattern_detector.set_market_data(market_data)
    return _pattern_detector
