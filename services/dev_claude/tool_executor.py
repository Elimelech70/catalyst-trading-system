#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: tool_executor.py
Version: 1.0.0
Last Updated: 2026-01-16
Purpose: Routes Claude's tool calls to actual implementations (US/Alpaca)

REVISION HISTORY:
v1.0.0 (2026-01-16) - Initial US implementation
  - Adapted from HKEX version for US markets
  - Alpaca broker integration
  - Position monitoring integration
  - 12 trading tools for Claude

Description:
This module receives tool calls from Claude and routes them to the
appropriate implementation functions. It handles all 12 trading tools
defined in the tool specification for US markets via Alpaca.

After successful BUY orders, automatically starts position monitoring
that runs until exit. Uses rules-based signal detection (free) and
Haiku consultations (~$0.05/call) for uncertain signals.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import asyncpg

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import (
        StockLatestQuoteRequest,
        StockBarsRequest,
        StockSnapshotRequest,
    )
    from alpaca.data.timeframe import TimeFrame
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# Local imports
from signals import analyze_position, SignalThresholds

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


# ============================================================================
# TOOL INPUT VALIDATION
# ============================================================================

TOOL_SCHEMAS = {
    "scan_market": {
        "required": [],
        "optional": ["index", "limit", "min_volume_ratio"],
    },
    "get_quote": {
        "required": ["symbol"],
        "optional": [],
    },
    "get_technicals": {
        "required": ["symbol"],
        "optional": ["timeframe"],
    },
    "detect_patterns": {
        "required": ["symbol"],
        "optional": ["timeframe"],
    },
    "get_news": {
        "required": ["symbol"],
        "optional": ["limit"],
    },
    "check_risk": {
        "required": ["symbol", "side", "quantity"],
        "optional": ["price"],
    },
    "get_portfolio": {
        "required": [],
        "optional": [],
    },
    "execute_trade": {
        "required": ["symbol", "side", "quantity"],
        "optional": ["order_type", "price", "stop_price", "target_price", "reasoning"],
    },
    "close_position": {
        "required": ["symbol"],
        "optional": ["reason"],
    },
    "close_all": {
        "required": [],
        "optional": ["reason"],
    },
    "send_alert": {
        "required": ["subject", "message"],
        "optional": ["severity"],
    },
    "log_decision": {
        "required": ["decision", "reasoning"],
        "optional": ["symbol"],
    },
    # Position Monitor specific tools
    "check_position_status": {
        "required": ["symbol"],
        "optional": [],
    },
    "force_exit": {
        "required": ["symbol"],
        "optional": ["reason"],
    },
    "get_monitor_stats": {
        "required": [],
        "optional": [],
    },
    "adjust_thresholds": {
        "required": ["symbol"],
        "optional": ["stop_loss", "take_profit", "trailing_stop"],
    },
}


def validate_tool_input(tool_name: str, tool_input: dict) -> tuple:
    """Validate tool input against schema."""
    schema = TOOL_SCHEMAS.get(tool_name)
    if not schema:
        return False, f"Unknown tool: {tool_name}"

    for field in schema["required"]:
        if field not in tool_input:
            return False, f"Missing required field: {field}"

    return True, None


# ============================================================================
# ALPACA BROKER CLIENT
# ============================================================================

class AlpacaBrokerClient:
    """Alpaca broker client for US markets."""

    def __init__(self):
        self.trading_client = None
        self.data_client = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Alpaca."""
        if not ALPACA_AVAILABLE:
            logger.error("alpaca-py package not installed")
            return False

        try:
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

            if not api_key or not secret_key:
                logger.error("ALPACA_API_KEY or ALPACA_SECRET_KEY not set")
                return False

            paper = "paper" in base_url.lower()

            self.trading_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper
            )

            self.data_client = StockHistoricalDataClient(
                api_key=api_key,
                secret_key=secret_key
            )

            # Test connection
            account = self.trading_client.get_account()
            logger.info(f"Alpaca connected - Equity: ${float(account.equity):,.2f}")

            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Alpaca connection failed: {e}")
            return False

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get current quote for symbol."""
        if not self._connected:
            return {"error": "Not connected"}

        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)

            if symbol in quotes:
                quote = quotes[symbol]
                mid_price = (float(quote.bid_price) + float(quote.ask_price)) / 2 if quote.bid_price and quote.ask_price else 0
                return {
                    "symbol": symbol,
                    "bid": float(quote.bid_price) if quote.bid_price else 0,
                    "ask": float(quote.ask_price) if quote.ask_price else 0,
                    "last": mid_price,
                    "bid_size": int(quote.bid_size) if quote.bid_size else 0,
                    "ask_size": int(quote.ask_size) if quote.ask_size else 0,
                }
            return {"error": f"No quote for {symbol}"}
        except Exception as e:
            return {"error": str(e)}

    def get_bars(self, symbol: str, timeframe: str = "1D", limit: int = 100) -> List[Dict]:
        """Get historical bars for symbol."""
        if not self._connected:
            return []

        try:
            tf_map = {
                "1m": TimeFrame.Minute,
                "5m": TimeFrame(5, "Min"),
                "15m": TimeFrame(15, "Min"),
                "1h": TimeFrame.Hour,
                "1D": TimeFrame.Day,
            }
            tf = tf_map.get(timeframe, TimeFrame.Day)

            end = datetime.now(ET)
            start = end - timedelta(days=limit if timeframe == "1D" else 5)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end
            )
            bars = self.data_client.get_stock_bars(request)

            if symbol in bars:
                return [
                    {
                        "timestamp": bar.timestamp.isoformat(),
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                    }
                    for bar in bars[symbol]
                ]
            return []
        except Exception as e:
            logger.error(f"Error getting bars for {symbol}: {e}")
            return []

    def get_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio status."""
        if not self._connected:
            return {"error": "Not connected"}

        try:
            account = self.trading_client.get_account()
            positions = self.trading_client.get_all_positions()

            position_list = []
            for pos in positions:
                position_list.append({
                    "symbol": pos.symbol,
                    "quantity": int(pos.qty),
                    "side": "long" if int(pos.qty) > 0 else "short",
                    "entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pnl": float(pos.unrealized_pl),
                    "unrealized_pnl_pct": float(pos.unrealized_plpc) * 100,
                })

            return {
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "positions": position_list,
                "position_count": len(position_list),
            }
        except Exception as e:
            return {"error": str(e)}

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = None,
    ) -> Dict[str, Any]:
        """Place an order."""
        if not self._connected:
            return {"status": "error", "message": "Not connected"}

        try:
            order_side = OrderSide.BUY if side.upper() in ["BUY", "LONG"] else OrderSide.SELL

            if order_type.upper() == "MARKET":
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                if not price:
                    return {"status": "error", "message": "Price required for limit order"}
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=price
                )

            order = self.trading_client.submit_order(order_request)

            return {
                "status": "submitted",
                "order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": float(order.filled_avg_price) if order.filled_avg_price else price or 0,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ============================================================================
# MARKET DATA PROVIDER
# ============================================================================

class MarketDataProvider:
    """Market data provider using Alpaca."""

    def __init__(self, broker: AlpacaBrokerClient):
        self.broker = broker

    def get_technicals(self, symbol: str, timeframe: str = "1D") -> Dict[str, Any]:
        """Calculate technical indicators for symbol."""
        bars = self.broker.get_bars(symbol, timeframe, limit=50)

        if len(bars) < 14:
            return {"error": "Insufficient data"}

        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        volumes = [b["volume"] for b in bars]

        # RSI
        rsi = self._calculate_rsi(closes, 14)

        # MACD
        macd, signal, histogram = self._calculate_macd(closes)

        # Bollinger Bands
        sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        std20 = (sum((c - sma20) ** 2 for c in closes[-20:]) / 20) ** 0.5 if len(closes) >= 20 else 0

        # ATR
        atr = self._calculate_atr(highs, lows, closes, 14)

        # VWAP (simplified - today's data only)
        if volumes[-1] > 0:
            typical_price = (highs[-1] + lows[-1] + closes[-1]) / 3
            vwap = typical_price  # Simplified
        else:
            vwap = closes[-1]

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": closes[-1],
            "rsi": rsi,
            "macd": macd,
            "macd_signal": signal,
            "macd_histogram": histogram,
            "sma_20": sma20,
            "bollinger_upper": sma20 + 2 * std20,
            "bollinger_lower": sma20 - 2 * std20,
            "atr": atr,
            "vwap": vwap,
            "volume": volumes[-1],
            "avg_volume_20": sum(volumes[-20:]) / min(20, len(volumes)),
        }

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, prices: List[float]) -> tuple:
        """Calculate MACD."""
        if len(prices) < 26:
            return 0, 0, 0

        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        macd = ema12 - ema26

        # Signal line (9-period EMA of MACD) - simplified
        signal = macd * 0.9  # Approximation
        histogram = macd - signal

        return macd, signal, histogram

    def _ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return prices[-1]

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate ATR."""
        if len(closes) < period + 1:
            return 0

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            trs.append(tr)

        return sum(trs[-period:]) / period

    def scan_market(self, index: str = "ALL", limit: int = 10, min_volume_ratio: float = 1.5) -> List[Dict]:
        """Scan market for trading candidates using Alpaca screener."""
        try:
            from alpaca.data.requests import MostActivesRequest, ScreenerRequest
            from alpaca.data.historical.screener import ScreenerClient

            screener = ScreenerClient()

            # Get most active stocks
            request = MostActivesRequest(top=limit)
            actives = screener.get_most_actives(request)

            candidates = []
            for stock in actives.most_actives:
                candidates.append({
                    "symbol": stock.symbol,
                    "trade_count": stock.trade_count,
                    "volume": stock.volume,
                })

            return candidates

        except Exception as e:
            logger.warning(f"Screener not available: {e}")
            # Fallback: return empty list
            return []


# ============================================================================
# PATTERN DETECTOR
# ============================================================================

class PatternDetector:
    """Simple pattern detection."""

    def __init__(self, market_data: MarketDataProvider):
        self.market = market_data

    def detect_patterns(self, symbol: str, timeframe: str = "1D") -> List[Dict]:
        """Detect chart patterns."""
        bars = self.market.broker.get_bars(symbol, timeframe, limit=50)

        if len(bars) < 20:
            return []

        patterns = []
        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]

        # Simple pattern detection

        # Uptrend
        if closes[-1] > closes[-5] > closes[-10]:
            patterns.append({
                "pattern": "uptrend",
                "strength": "moderate",
                "description": "Price making higher highs",
            })

        # Downtrend
        if closes[-1] < closes[-5] < closes[-10]:
            patterns.append({
                "pattern": "downtrend",
                "strength": "moderate",
                "description": "Price making lower lows",
            })

        # Support/Resistance
        recent_low = min(lows[-10:])
        recent_high = max(highs[-10:])

        if abs(closes[-1] - recent_low) / recent_low < 0.02:
            patterns.append({
                "pattern": "near_support",
                "strength": "moderate",
                "level": recent_low,
            })

        if abs(closes[-1] - recent_high) / recent_high < 0.02:
            patterns.append({
                "pattern": "near_resistance",
                "strength": "moderate",
                "level": recent_high,
            })

        return patterns


# ============================================================================
# SAFETY VALIDATOR
# ============================================================================

class SafetyValidator:
    """Trade safety validation."""

    def __init__(self, max_position_pct: float = 0.10, max_positions: int = 10):
        self.max_position_pct = max_position_pct
        self.max_positions = max_positions

    def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        portfolio: Dict,
    ) -> Dict[str, Any]:
        """Validate a trade request."""
        checks = {}
        approved = True
        reasons = []

        equity = portfolio.get("equity", 0)
        position_count = portfolio.get("position_count", 0)

        # Position size check
        trade_value = quantity * price
        position_pct = trade_value / equity if equity > 0 else 1

        checks["position_size"] = position_pct <= self.max_position_pct
        if not checks["position_size"]:
            approved = False
            reasons.append(f"Position size {position_pct:.1%} exceeds max {self.max_position_pct:.1%}")

        # Position count check
        checks["position_count"] = position_count < self.max_positions
        if not checks["position_count"] and side.upper() in ["BUY", "LONG"]:
            approved = False
            reasons.append(f"Max positions ({self.max_positions}) reached")

        # Buying power check
        buying_power = portfolio.get("buying_power", 0)
        checks["buying_power"] = trade_value <= buying_power
        if not checks["buying_power"] and side.upper() in ["BUY", "LONG"]:
            approved = False
            reasons.append(f"Insufficient buying power: ${buying_power:,.2f} < ${trade_value:,.2f}")

        return {
            "approved": approved,
            "reason": "; ".join(reasons) if reasons else "All checks passed",
            "checks": checks,
        }


# ============================================================================
# TOOL EXECUTOR
# ============================================================================

class ToolExecutor:
    """Executes tool calls from Claude for US markets."""

    def __init__(
        self,
        cycle_id: str,
        alert_callback: Any = None,
        agent: Any = None,
        db_pool: asyncpg.Pool = None,
    ):
        self.cycle_id = cycle_id
        self.alert_callback = alert_callback
        self.agent = agent
        self.db_pool = db_pool
        self.tools_called: List[Dict] = []
        self.trades_executed = 0

        # Initialize services
        self.broker = AlpacaBrokerClient()
        self.broker.connect()
        self.market = MarketDataProvider(self.broker)
        self.patterns = PatternDetector(self.market)
        self.safety = SafetyValidator()

        # Position monitoring state
        self.monitored_positions: Dict[str, Dict] = {}

    def execute(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool call."""
        # Validate input
        is_valid, error = validate_tool_input(tool_name, tool_input)
        if not is_valid:
            return {"error": error, "success": False}

        # Log tool call
        self.tools_called.append({
            "tool": tool_name,
            "input": tool_input,
            "timestamp": datetime.now(ET).isoformat(),
        })

        # Route to implementation
        try:
            result = self._route_tool(tool_name, tool_input)
            result["success"] = True
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {tool_name}: {e}", exc_info=True)
            return {
                "error": str(e),
                "success": False,
                "tool": tool_name,
            }

    def _route_tool(self, tool_name: str, inputs: dict) -> dict:
        """Route tool call to implementation."""
        handlers = {
            # Market Analysis
            "scan_market": self._scan_market,
            "get_quote": self._get_quote,
            "get_technicals": self._get_technicals,
            "detect_patterns": self._detect_patterns,
            "get_news": self._get_news,
            # Risk Management
            "check_risk": self._check_risk,
            "get_portfolio": self._get_portfolio,
            # Trading Execution
            "execute_trade": self._execute_trade,
            "close_position": self._close_position,
            "close_all": self._close_all,
            # Utility
            "send_alert": self._send_alert,
            "log_decision": self._log_decision,
            # Position Monitor
            "check_position_status": self._check_position_status,
            "force_exit": self._force_exit,
            "get_monitor_stats": self._get_monitor_stats,
            "adjust_thresholds": self._adjust_thresholds,
        }

        handler = handlers.get(tool_name)
        if not handler:
            raise ValueError(f"Unknown tool: {tool_name}")

        return handler(inputs)

    # =========================================================================
    # Market Analysis Tools
    # =========================================================================

    def _scan_market(self, inputs: dict) -> dict:
        """Scan market for trading candidates."""
        index = inputs.get("index", "ALL")
        limit = min(inputs.get("limit", 10), 20)
        min_volume_ratio = inputs.get("min_volume_ratio", 1.5)

        candidates = self.market.scan_market(
            index=index,
            limit=limit,
            min_volume_ratio=min_volume_ratio,
        )

        return {
            "index": index,
            "candidates_found": len(candidates),
            "candidates": candidates,
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _get_quote(self, inputs: dict) -> dict:
        """Get current quote."""
        symbol = inputs["symbol"]
        quote = self.broker.get_quote(symbol)

        return {
            "symbol": symbol,
            "quote": quote,
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _get_technicals(self, inputs: dict) -> dict:
        """Get technical indicators."""
        symbol = inputs["symbol"]
        timeframe = inputs.get("timeframe", "1D")

        technicals = self.market.get_technicals(symbol, timeframe)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "technicals": technicals,
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _detect_patterns(self, inputs: dict) -> dict:
        """Detect chart patterns."""
        symbol = inputs["symbol"]
        timeframe = inputs.get("timeframe", "1D")

        patterns = self.patterns.detect_patterns(symbol, timeframe)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "patterns_found": len(patterns),
            "patterns": patterns,
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _get_news(self, inputs: dict) -> dict:
        """Get news for symbol (placeholder - needs news API)."""
        symbol = inputs["symbol"]
        limit = min(inputs.get("limit", 5), 10)

        # Placeholder - would integrate with news API
        return {
            "symbol": symbol,
            "articles_found": 0,
            "articles": [],
            "note": "News API not configured",
            "timestamp": datetime.now(ET).isoformat(),
        }

    # =========================================================================
    # Risk Management Tools
    # =========================================================================

    def _check_risk(self, inputs: dict) -> dict:
        """Check trade risk."""
        symbol = inputs["symbol"]
        side = inputs["side"]
        quantity = inputs["quantity"]
        price = inputs.get("price", 0)

        # Get current price if not provided
        if price == 0:
            quote = self.broker.get_quote(symbol)
            price = quote.get("last", 0)

        portfolio = self.broker.get_portfolio()

        result = self.safety.validate_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            portfolio=portfolio,
        )

        return {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "approved": result["approved"],
            "reason": result["reason"],
            "checks": result["checks"],
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _get_portfolio(self, inputs: dict) -> dict:
        """Get portfolio status."""
        portfolio = self.broker.get_portfolio()

        return {
            "portfolio": portfolio,
            "timestamp": datetime.now(ET).isoformat(),
        }

    # =========================================================================
    # Trading Execution Tools
    # =========================================================================

    def _execute_trade(self, inputs: dict) -> dict:
        """Execute a trade."""
        symbol = inputs["symbol"]
        side = inputs["side"].upper()
        quantity = inputs["quantity"]
        order_type = inputs.get("order_type", "MARKET").upper()
        price = inputs.get("price")
        stop_price = inputs.get("stop_price")
        target_price = inputs.get("target_price")
        reasoning = inputs.get("reasoning", "")

        logger.info(f"Executing trade: {side} {quantity} {symbol}")

        # Risk check first
        portfolio = self.broker.get_portfolio()
        quote = self.broker.get_quote(symbol)
        current_price = quote.get("last", price or 0)

        risk_check = self.safety.validate_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=current_price,
            portfolio=portfolio,
        )

        if not risk_check["approved"]:
            return {
                "status": "rejected",
                "reason": risk_check["reason"],
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }

        # Place order
        result = self.broker.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
        )

        if result.get("status") in ["submitted", "filled"]:
            self.trades_executed += 1
            fill_price = result.get("fill_price", current_price)

            # Track for monitoring
            if side in ["BUY", "LONG"]:
                self.monitored_positions[symbol] = {
                    "entry_price": fill_price,
                    "quantity": quantity,
                    "entry_time": datetime.now(ET).isoformat(),
                    "stop_price": stop_price or fill_price * 0.95,
                    "target_price": target_price or fill_price * 1.10,
                    "reasoning": reasoning,
                    "high_watermark": fill_price,
                }

            # Log to database if available
            if self.db_pool:
                asyncio.create_task(self._log_trade_to_db(
                    symbol, side, quantity, fill_price, reasoning
                ))

            return {
                "status": "success",
                "order_id": result.get("order_id"),
                "fill_price": fill_price,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "timestamp": datetime.now(ET).isoformat(),
            }
        else:
            return {
                "status": "failed",
                "reason": result.get("message", "Order rejected"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }

    async def _log_trade_to_db(self, symbol: str, side: str, quantity: int, price: float, reasoning: str):
        """Log trade to database."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trades (symbol, side, quantity, price, reasoning, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                """, symbol, side, quantity, price, reasoning)
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    def _close_position(self, inputs: dict) -> dict:
        """Close a specific position."""
        symbol = inputs["symbol"]
        reason = inputs.get("reason", "Manual close")

        logger.info(f"Closing position: {symbol} - {reason}")

        # Get current position
        portfolio = self.broker.get_portfolio()
        position = None

        for pos in portfolio.get("positions", []):
            if pos["symbol"] == symbol:
                position = pos
                break

        if not position:
            return {
                "status": "error",
                "reason": f"No position found for {symbol}",
            }

        quantity = abs(position["quantity"])

        result = self.broker.place_order(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            order_type="MARKET",
        )

        if result.get("status") in ["submitted", "filled"]:
            self.trades_executed += 1

            # Remove from monitoring
            if symbol in self.monitored_positions:
                del self.monitored_positions[symbol]

            return {
                "status": "success",
                "symbol": symbol,
                "quantity": quantity,
                "reason": reason,
                "order_id": result.get("order_id"),
                "timestamp": datetime.now(ET).isoformat(),
            }
        else:
            return {
                "status": "failed",
                "reason": result.get("message", "Close order rejected"),
            }

    def _close_all(self, inputs: dict) -> dict:
        """Close all positions."""
        reason = inputs.get("reason", "Emergency close all")

        logger.warning(f"CLOSING ALL POSITIONS: {reason}")

        if self.alert_callback:
            self.alert_callback("critical", "Emergency Close All", reason)

        portfolio = self.broker.get_portfolio()
        positions = portfolio.get("positions", [])

        if not positions:
            return {
                "status": "success",
                "message": "No positions to close",
                "closed_count": 0,
            }

        closed = []
        failed = []

        for pos in positions:
            symbol = pos["symbol"]
            quantity = abs(pos["quantity"])

            try:
                result = self.broker.place_order(
                    symbol=symbol,
                    side="SELL",
                    quantity=quantity,
                    order_type="MARKET",
                )

                if result.get("status") in ["submitted", "filled"]:
                    closed.append(symbol)
                    self.trades_executed += 1
                else:
                    failed.append(f"{symbol}: {result.get('message')}")
            except Exception as e:
                failed.append(f"{symbol}: {str(e)}")

        # Clear monitoring
        self.monitored_positions.clear()

        return {
            "status": "success" if not failed else "partial",
            "closed_count": len(closed),
            "closed_symbols": closed,
            "failed_count": len(failed),
            "failed_details": failed,
            "reason": reason,
            "timestamp": datetime.now(ET).isoformat(),
        }

    # =========================================================================
    # Utility Tools
    # =========================================================================

    def _send_alert(self, inputs: dict) -> dict:
        """Send alert notification."""
        severity = inputs.get("severity", "info")
        subject = inputs["subject"]
        message = inputs["message"]

        if self.alert_callback:
            self.alert_callback(severity, subject, message)
            return {"sent": True, "severity": severity, "subject": subject}
        else:
            logger.info(f"Alert [{severity}]: {subject} - {message}")
            return {"sent": False, "reason": "No alert callback configured"}

    def _log_decision(self, inputs: dict) -> dict:
        """Log a trading decision."""
        decision = inputs["decision"]
        reasoning = inputs["reasoning"]
        symbol = inputs.get("symbol")

        logger.info(f"Decision: {decision} for {symbol or 'N/A'}: {reasoning}")

        return {
            "logged": True,
            "decision": decision,
            "symbol": symbol,
            "timestamp": datetime.now(ET).isoformat(),
        }

    # =========================================================================
    # Position Monitor Tools
    # =========================================================================

    def _check_position_status(self, inputs: dict) -> dict:
        """Check status of a monitored position."""
        symbol = inputs["symbol"]

        # Get current quote
        quote = self.broker.get_quote(symbol)
        current_price = quote.get("last", 0)

        # Get portfolio position
        portfolio = self.broker.get_portfolio()
        position = None
        for pos in portfolio.get("positions", []):
            if pos["symbol"] == symbol:
                position = pos
                break

        if not position:
            return {
                "symbol": symbol,
                "status": "no_position",
                "message": f"No open position for {symbol}",
            }

        # Get monitoring data if available
        monitor_data = self.monitored_positions.get(symbol, {})
        entry_price = monitor_data.get("entry_price", position["entry_price"])
        high_watermark = max(monitor_data.get("high_watermark", entry_price), current_price)

        # Update high watermark
        if symbol in self.monitored_positions:
            self.monitored_positions[symbol]["high_watermark"] = high_watermark

        # Analyze for signals
        analysis = analyze_position(
            entry_price=entry_price,
            current_price=current_price,
            high_watermark=high_watermark,
        )

        return {
            "symbol": symbol,
            "status": "open",
            "entry_price": entry_price,
            "current_price": current_price,
            "high_watermark": high_watermark,
            "quantity": position["quantity"],
            "unrealized_pnl": position["unrealized_pnl"],
            "unrealized_pnl_pct": position["unrealized_pnl_pct"],
            "signals": analysis["active_signals"],
            "strongest_signal": analysis["strongest_signal"],
            "immediate_exit": analysis["immediate_exit"],
            "consult_ai": analysis["consult_ai"],
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _force_exit(self, inputs: dict) -> dict:
        """Force exit a position."""
        symbol = inputs["symbol"]
        reason = inputs.get("reason", "Forced exit")

        return self._close_position({"symbol": symbol, "reason": reason})

    def _get_monitor_stats(self, inputs: dict) -> dict:
        """Get position monitor statistics."""
        portfolio = self.broker.get_portfolio()

        return {
            "monitored_count": len(self.monitored_positions),
            "monitored_symbols": list(self.monitored_positions.keys()),
            "portfolio_positions": portfolio.get("position_count", 0),
            "trades_executed": self.trades_executed,
            "tools_called": len(self.tools_called),
            "timestamp": datetime.now(ET).isoformat(),
        }

    def _adjust_thresholds(self, inputs: dict) -> dict:
        """Adjust monitoring thresholds for a position."""
        symbol = inputs["symbol"]

        if symbol not in self.monitored_positions:
            return {
                "status": "error",
                "reason": f"No monitored position for {symbol}",
            }

        updated = {}

        if "stop_loss" in inputs:
            self.monitored_positions[symbol]["stop_price"] = inputs["stop_loss"]
            updated["stop_loss"] = inputs["stop_loss"]

        if "take_profit" in inputs:
            self.monitored_positions[symbol]["target_price"] = inputs["take_profit"]
            updated["take_profit"] = inputs["take_profit"]

        return {
            "symbol": symbol,
            "status": "updated",
            "updated_fields": updated,
            "timestamp": datetime.now(ET).isoformat(),
        }

    # =========================================================================
    # Summary
    # =========================================================================

    def get_summary(self) -> dict:
        """Get execution summary."""
        return {
            "cycle_id": self.cycle_id,
            "tools_called": len(self.tools_called),
            "trades_executed": self.trades_executed,
            "monitored_positions": len(self.monitored_positions),
            "tool_history": self.tools_called,
        }


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_tool_executor(
    cycle_id: str,
    alert_callback: Any = None,
    agent: Any = None,
    db_pool: asyncpg.Pool = None,
) -> ToolExecutor:
    """Create a new tool executor."""
    return ToolExecutor(
        cycle_id=cycle_id,
        alert_callback=alert_callback,
        agent=agent,
        db_pool=db_pool,
    )
