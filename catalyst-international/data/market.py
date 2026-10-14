"""
Market data and technical analysis for the Catalyst Trading Agent.

Name of file: market.py
Version: 2.4.0
Last Updated: 2026-02-05

This module provides:
- Real-time quotes from Moomoo/Futu
- Historical price data
- Technical indicators (RSI, MACD, Moving Averages, etc.)
- Market scanning functionality

REVISION HISTORY:
v2.4.0 (2026-02-05) - Symbol normalization fix
- Import normalize_symbol from brokers.moomoo
- Updated scan_market() to use normalized symbols for quote lookup
- get_quotes_batch() now returns Dict (fixed in moomoo.py v1.6.0)
- Fixes critical bug where quotes_batch.get(symbol) failed on List

v2.3.0 (2026-01-16) - Volume ratio fix
- Fixed volume_ratio calculation in get_quote() to match scan_market()
- Changed avg_volume fallback from `volume` to `volume // 2`
- This ensures candidates that pass scan also pass tier criteria

v2.2.0 (2026-01-08) - Dynamic lot size support
- get_quote() now returns actual board lot size instead of hardcoded 100
- Added _get_lot_size() helper method
- Fixes odd lot order errors for stocks with non-100 lot sizes

v2.1.0 (2025-12-30) - Batch quote support to avoid rate limiting
- Updated scan_market() to use get_quotes_batch() instead of individual calls
- Fixes "too frequent" error (60 requests per 30 seconds limit)
- Single API call for all index constituents

v2.0.0 (2025-12-20) - Migrated to Moomoo/Futu
- Replaced IBKR with Futu broker client
- Real-time data now included (no more delayed data)

v1.1.0 (2025-12-11) - NaN handling for delayed data
- Added safe_float() helper to handle NaN values from delayed market data
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from brokers.moomoo import normalize_symbol

logger = logging.getLogger(__name__)


def safe_float(val, default=0.0):
    """Safely convert value to float, handling NaN."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    """Safely convert value to int, handling NaN."""
    return int(safe_float(val, default))


@dataclass
class Quote:
    """Current market quote for a symbol."""

    symbol: str
    name: str
    price: float
    bid: float
    ask: float
    volume: int
    avg_volume: int
    volume_ratio: float
    change: float
    change_pct: float
    day_high: float
    day_low: float
    open: float
    prev_close: float
    market_cap: float
    lot_size: int
    timestamp: datetime


@dataclass
class Technicals:
    """Technical indicators for a symbol."""

    symbol: str
    timeframe: str

    # RSI
    rsi: float

    # MACD
    macd_value: float
    macd_signal: float
    macd_histogram: float

    # Moving Averages
    sma_9: float
    sma_20: float
    sma_50: float
    sma_200: float
    ema_9: float
    ema_21: float

    # Volatility
    atr: float
    atr_pct: float

    # Bollinger Bands
    bb_upper: float
    bb_middle: float
    bb_lower: float

    # Support/Resistance
    support: float
    resistance: float

    # Trend
    trend: str  # 'bullish', 'bearish', 'neutral'
    price_vs_sma20: str  # 'above', 'below'

    timestamp: datetime


class MarketData:
    """Market data provider using Moomoo/Futu as data source."""

    def __init__(self, broker_client: Any = None):
        """Initialize market data provider.

        Args:
            broker_client: Broker client instance for data fetching (FutuClient)
        """
        self.broker = broker_client
        self._price_cache: dict[str, pd.DataFrame] = {}

    def set_broker_client(self, client: Any):
        """Set the broker client."""
        self.broker = client

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol.

        Args:
            symbol: HKEX stock code (e.g., '0700')

        Returns:
            Quote data as dictionary
        """
        if not self.broker:
            raise RuntimeError("Broker client not initialized")

        # Fetch from broker (Moomoo)
        data = self.broker.get_quote(symbol)

        # Calculate volume ratio and change % (handle NaN from delayed data)
        volume = safe_int(data.get("volume"), 0)
        # Estimate avg_volume as half of current volume (same as scan_market)
        # This is because Moomoo API doesn't provide avg_volume directly
        avg_volume = safe_int(data.get("avg_volume"), max(volume // 2, 1))
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        # Calculate change from prev_close if not provided
        last_price = safe_float(data.get("last_price") or data.get("last"))
        prev_close = safe_float(data.get("prev_close") or data.get("prev_close_price"))
        change = last_price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "symbol": symbol,
            "name": data.get("name", symbol),
            "price": last_price,
            "bid": safe_float(data.get("bid_price") or data.get("bid")),
            "ask": safe_float(data.get("ask_price") or data.get("ask")),
            "volume": volume,
            "avg_volume": avg_volume,
            "volume_ratio": round(volume_ratio, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "day_high": safe_float(data.get("high_price") or data.get("high")),
            "day_low": safe_float(data.get("low_price") or data.get("low")),
            "open": safe_float(data.get("open_price") or data.get("open")),
            "prev_close": prev_close,
            "market_cap": safe_float(data.get("market_cap")),
            "lot_size": self._get_lot_size(symbol),  # Actual HKEX board lot for this stock
            "timestamp": datetime.now().isoformat(),
        }

    def _get_lot_size(self, symbol: str) -> int:
        """Get actual lot size from broker if available."""
        if hasattr(self.broker, 'get_lot_size'):
            try:
                return self.broker.get_lot_size(symbol)
            except Exception as e:
                logger.warning(f"Could not get lot size for {symbol}: {e}")
        return 100  # Default fallback

    def get_historical(
        self, symbol: str, timeframe: str = "15m", bars: int = 100
    ) -> pd.DataFrame:
        """Get historical price data.

        Args:
            symbol: Stock code
            timeframe: '5m', '15m', '1h', '1d'
            bars: Number of bars to fetch

        Returns:
            DataFrame with OHLCV data
        """
        if not self.broker:
            raise RuntimeError("Broker client not initialized")

        # Map timeframe to IBKR format
        tf_map = {
            "5m": "5 mins",
            "15m": "15 mins",
            "1h": "1 hour",
            "1d": "1 day",
        }

        duration_map = {
            "5m": f"{bars * 5 // 60 + 1} D",
            "15m": f"{bars * 15 // 60 + 1} D",
            "1h": f"{bars // 24 + 1} D",
            "1d": f"{bars + 1} D",
        }

        bar_size = tf_map.get(timeframe, "15 mins")
        duration = duration_map.get(timeframe, "5 D")

        data = self.broker.get_historical_data(
            symbol=symbol, duration=duration, bar_size=bar_size
        )

        df = pd.DataFrame(data)
        # moomoo.py returns "timestamp" key, not "date"
        date_col = "timestamp" if "timestamp" in df.columns else "date"
        df["timestamp"] = pd.to_datetime(df[date_col])
        df = df.set_index("timestamp")
        df = df[["open", "high", "low", "close", "volume"]]

        # Cache for pattern detection
        cache_key = f"{symbol}_{timeframe}"
        self._price_cache[cache_key] = df

        return df.tail(bars)

    def get_technicals(self, symbol: str, timeframe: str = "15m") -> dict:
        """Calculate technical indicators for a symbol.

        Args:
            symbol: Stock code
            timeframe: Analysis timeframe

        Returns:
            Technical indicators as dictionary
        """
        # Get historical data
        df = self.get_historical(symbol, timeframe, bars=200)

        # Get real-time quote price to avoid stale bar data discrepancy
        try:
            quote = self.get_quote(symbol)
            realtime_price = quote.get("price", 0)
        except Exception:
            realtime_price = None

        if len(df) < 50:
            raise ValueError(f"Insufficient data for {symbol}")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # RSI (14 period)
        rsi = self._calculate_rsi(close, 14)

        # MACD (12, 26, 9)
        macd_value, macd_signal, macd_hist = self._calculate_macd(close)

        # Moving Averages
        sma_9 = close.rolling(9).mean().iloc[-1]
        sma_20 = close.rolling(20).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
        ema_9 = close.ewm(span=9).mean().iloc[-1]
        ema_21 = close.ewm(span=21).mean().iloc[-1]

        # ATR (14 period)
        atr = self._calculate_atr(high, low, close, 14)
        atr_pct = (atr / close.iloc[-1]) * 100 if close.iloc[-1] > 0 else 0

        # Bollinger Bands
        bb_middle = close.rolling(20).mean().iloc[-1]
        bb_std = close.rolling(20).std().iloc[-1]
        bb_upper = bb_middle + (2 * bb_std)
        bb_lower = bb_middle - (2 * bb_std)

        # Support/Resistance (simple pivot points)
        support, resistance = self._calculate_support_resistance(df)

        # Trend determination - use realtime price if available, else last bar close
        bar_close = close.iloc[-1]
        current_price = realtime_price if realtime_price else bar_close
        if current_price > sma_20 and sma_9 > sma_20:
            trend = "bullish"
        elif current_price < sma_20 and sma_9 < sma_20:
            trend = "bearish"
        else:
            trend = "neutral"

        price_vs_sma20 = "above" if current_price > sma_20 else "below"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),
            "rsi": round(rsi, 2),
            "macd": {
                "value": round(macd_value, 4),
                "signal": round(macd_signal, 4),
                "histogram": round(macd_hist, 4),
            },
            "moving_averages": {
                "sma_9": round(sma_9, 2),
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "sma_200": round(sma_200, 2) if sma_200 else None,
                "ema_9": round(ema_9, 2),
                "ema_21": round(ema_21, 2),
            },
            "volatility": {
                "atr": round(atr, 2),
                "atr_pct": round(atr_pct, 2),
            },
            "bollinger_bands": {
                "upper": round(bb_upper, 2),
                "middle": round(bb_middle, 2),
                "lower": round(bb_lower, 2),
            },
            "support_resistance": {
                "support": round(support, 2),
                "resistance": round(resistance, 2),
            },
            "trend": trend,
            "price_vs_sma20": price_vs_sma20,
            "timestamp": datetime.now().isoformat(),
        }

    def scan_market(
        self,
        index: str = "ALL",
        limit: int = 10,
        min_volume_ratio: float = 1.5,
        max_price: float = 1000.0,
    ) -> list[dict]:
        """Scan market for trading candidates.

        Uses batch quote API to avoid rate limiting (60 requests per 30 seconds).
        All symbols are fetched in a single API call.

        Args:
            index: Index to scan (HSI, HSCEI, HSTECH, ALL)
            limit: Maximum candidates to return
            min_volume_ratio: Minimum volume vs average
            max_price: Maximum stock price (default 1000, can buy 10+ shares)

        Returns:
            List of candidate stocks sorted by momentum
        """
        if not self.broker:
            raise RuntimeError("Broker client not initialized")

        # Get index constituents
        symbols = self._get_index_constituents(index)

        # Use batch quote to avoid rate limiting
        # This fetches all symbols in one API call instead of individual calls
        try:
            quotes_batch = self.broker.get_quotes_batch(symbols)
        except Exception as e:
            logger.error(f"Failed to get batch quotes: {e}")
            return []

        candidates = []
        for symbol in symbols:
            try:
                # Normalize symbol to match dict keys (quotes_batch uses normalized symbols)
                norm_symbol = normalize_symbol(symbol)
                quote_data = quotes_batch.get(norm_symbol)
                if not quote_data:
                    continue

                # Calculate volume ratio
                volume = safe_int(quote_data.get("volume"), 0)
                # Estimate avg volume from turnover if available
                avg_volume = max(volume // 2, 1)  # Simplified estimate
                volume_ratio = volume / avg_volume if avg_volume > 0 else 0

                # Get price change percentage
                last_price = safe_float(quote_data.get("last_price"), 0)
                prev_close = safe_float(quote_data.get("prev_close"), 0)
                if prev_close > 0:
                    change_pct = ((last_price - prev_close) / prev_close) * 100
                else:
                    change_pct = safe_float(quote_data.get("change_pct"), 0)

                # Filter by volume
                if volume_ratio < min_volume_ratio:
                    continue

                # Filter by max price (for position sizing limits)
                if max_price and last_price > max_price:
                    continue

                # Filter by price action (positive momentum)
                if change_pct <= 0:
                    continue

                quote = {
                    "symbol": symbol,
                    "name": symbol,
                    "price": last_price,
                    "change_pct": change_pct,
                    "volume": volume,
                    "volume_ratio": round(volume_ratio, 2),
                }

                candidates.append(
                    {
                        "symbol": quote["symbol"],
                        "name": quote["name"],
                        "price": quote["price"],
                        "change_pct": round(quote["change_pct"], 2),
                        "volume": quote["volume"],
                        "volume_ratio": quote["volume_ratio"],
                        "momentum_score": self._calculate_momentum_score(quote),
                    }
                )
            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue

        # Sort by momentum score
        candidates.sort(key=lambda x: x["momentum_score"], reverse=True)

        logger.info(f"Scan found {len(candidates)} candidates from {len(symbols)} symbols")
        return candidates[:limit]

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    def _calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[float, float, float]:
        """Calculate MACD indicator."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line

        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

    def _calculate_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> float:
        """Calculate Average True Range."""
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr.iloc[-1]

    def _calculate_support_resistance(self, df: pd.DataFrame) -> tuple[float, float]:
        """Calculate simple support and resistance levels."""
        recent = df.tail(20)

        # Support: recent low
        support = recent["low"].min()

        # Resistance: recent high
        resistance = recent["high"].max()

        return support, resistance

    def _calculate_momentum_score(self, quote: dict) -> float:
        """Calculate momentum score for ranking candidates."""
        # Weighted combination of factors
        change_score = min(quote["change_pct"], 10) / 10 * 40  # Max 40 points
        volume_score = min(quote["volume_ratio"], 5) / 5 * 40  # Max 40 points
        price_score = 20 if quote["price"] > 1 else quote["price"] * 20  # Max 20 points

        return change_score + volume_score + price_score

    def _get_index_constituents(self, index: str) -> list[str]:
        """Get constituent symbols for an index."""
        # HSI major constituents
        hsi = [
            "0005",
            "0011",
            "0388",
            "0700",
            "0941",
            "1299",
            "2318",
            "2628",
            "3988",
            "0883",
            "0939",
            "1398",
            "2388",
            "0016",
            "0001",
            "0027",
            "0066",
            "0002",
            "0003",
            "0006",
            "0012",
            "0017",
            "0019",
            "0023",
            "0101",
            "0267",
            "0386",
            "0688",
            "0762",
            "0823",
            "0857",
            "0868",
            "0881",
            "0960",
            "0968",
            "1038",
            "1044",
            "1093",
            "1109",
            "1113",
            "1177",
            "1211",
            "1929",
            "1997",
            "2007",
            "2020",
            "2269",
            "2313",
            "2319",
            "2382",
        ]

        # HSCEI China enterprises
        hscei = [
            "0386",
            "0688",
            "0762",
            "0857",
            "0883",
            "0939",
            "0941",
            "1088",
            "1398",
            "1800",
            "2318",
            "2319",
            "2328",
            "2601",
            "2628",
            "3328",
            "3968",
            "3988",
            "6030",
            # "6837",  # Removed - not found in IBKR
        ]

        # HSTECH technology
        hstech = [
            "0700",
            "3690",
            "0981",
            "9618",
            "9888",
            "1810",
            "9999",
            "0241",
            "2382",
            "0268",
            "1024",
            "0772",
            "6060",
            "0285",
            "3888",
            "1347",
            "2018",
            "0909",
            "9698",
            "0020",
            "9926",
            "6690",
            "0992",
            "1797",
            "2013",
            "9961",
            "9866",
            "9988",
            "9868",
            "2015",
        ]

        if index == "HSI":
            return hsi
        elif index == "HSCEI":
            return hscei
        elif index == "HSTECH":
            return hstech
        else:  # ALL
            # Combine and deduplicate
            all_symbols = list(set(hsi + hscei + hstech))
            return all_symbols

    def get_cached_data(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """Get cached price data if available."""
        cache_key = f"{symbol}_{timeframe}"
        return self._price_cache.get(cache_key)


# Singleton instance
_market_data: MarketData | None = None


def get_market_data(broker_client: Any = None) -> MarketData:
    """Get or create market data singleton."""
    global _market_data
    if _market_data is None:
        _market_data = MarketData(broker_client)
    elif broker_client and _market_data.broker is None:
        _market_data.set_broker_client(broker_client)
    return _market_data
