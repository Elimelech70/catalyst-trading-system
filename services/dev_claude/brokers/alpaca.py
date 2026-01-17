#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: alpaca.py
Version: 1.0.0
Last Updated: 2026-01-17
Purpose: Alpaca broker client for US markets via Alpaca API

REVISION HISTORY:
v1.0.0 (2026-01-17) - Initial implementation
  - Aligned with intl_claude's brokers/moomoo.py pattern
  - Module-level client singleton pattern
  - get_alpaca_client() / init_alpaca_client() functions
  - OrderResult and Position dataclasses
  - Sub-penny price rounding (2 decimal places)
  - Bracket order support via OrderClass.BRACKET
  - Paper trading by default

Description:
This module provides the AlpacaClient class for trading US equities via
Alpaca Markets API. It mirrors the interface of brokers/moomoo.py for
consistency across the Catalyst ecosystem.

Official Documentation:
- API Docs: https://docs.alpaca.markets/
- Python SDK: https://pypi.org/project/alpaca-py/

Environment Variables:
    ALPACA_API_KEY: API key ID
    ALPACA_SECRET_KEY: API secret key
    ALPACA_PAPER: 'true' for paper trading (default), 'false' for live
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

# Alpaca SDK imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
        GetOrdersRequest,
        ClosePositionRequest,
    )
    from alpaca.trading.enums import (
        OrderSide,
        OrderClass,
        TimeInForce,
        QueryOrderStatus,
        OrderStatus,
    )
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.live import StockDataStream
    from alpaca.data.requests import (
        StockLatestQuoteRequest,
        StockBarsRequest,
        StockLatestBarRequest,
    )
    from alpaca.data.timeframe import TimeFrame
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class OrderResult:
    """Result of an order submission."""
    order_id: str
    status: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    filled_price: Optional[float]
    filled_quantity: int
    message: str


@dataclass
class Position:
    """A portfolio position."""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def round_price(price: Optional[float]) -> Optional[float]:
    """
    Round price to 2 decimal places to avoid sub-penny rejection.
    
    Alpaca rejects orders with sub-penny prices (e.g., 9.050000190734863).
    This helper ensures all prices are properly rounded to cents.
    
    Args:
        price: Price to round
        
    Returns:
        Rounded price or None if input was None
    """
    if price is None:
        return None
    return float(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


# =============================================================================
# ALPACA CLIENT
# =============================================================================

class AlpacaClient:
    """Alpaca client for US market trading.
    
    This client connects to Alpaca's API to execute trades on US equities.
    It provides a similar interface to MoomooClient for consistency.
    
    Example:
        client = AlpacaClient(paper=True)
        client.connect()
        quote = client.get_quote("AAPL")
        print(f"Apple last price: {quote['last']}")
        client.disconnect()
    """
    
    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        paper: bool = True,
    ):
        """Initialize Alpaca client.
        
        Args:
            api_key: Alpaca API key (default: ALPACA_API_KEY env)
            secret_key: Alpaca secret key (default: ALPACA_SECRET_KEY env)
            paper: Use paper trading environment (default: True)
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        
        # Check for paper trading env var override
        paper_env = os.environ.get("ALPACA_PAPER", "true").lower()
        self.paper = paper if paper_env == "true" else False
        
        self.trading_client = None
        self.data_client = None
        self._connected = False
        
        if not self.api_key or not self.secret_key:
            logger.warning("Alpaca API keys not found in environment")
        
        logger.info(
            f"AlpacaClient initialized: paper={self.paper}"
        )
    
    def connect(self) -> bool:
        """Connect to Alpaca API.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not ALPACA_AVAILABLE:
            logger.error("alpaca-py not installed. Run: pip install alpaca-py")
            return False
        
        if not self.api_key or not self.secret_key:
            logger.error("Alpaca API keys not configured")
            return False
        
        try:
            # Trading client
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
            )
            
            # Data client
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )
            
            # Verify connection by getting account
            account = self.trading_client.get_account()
            logger.info(f"Connected to Alpaca: equity=${float(account.equity):,.2f}, "
                       f"buying_power=${float(account.buying_power):,.2f}")
            
            self._connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Alpaca (no-op, stateless API)."""
        self._connected = False
        logger.info("Disconnected from Alpaca")
    
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected
    
    # =========================================================================
    # MARKET DATA
    # =========================================================================
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            
        Returns:
            Quote dict with last, bid, ask, volume, etc.
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)
            
            if symbol not in quotes:
                raise ValueError(f"No quote data for {symbol}")
            
            quote = quotes[symbol]
            
            # Get latest bar for OHLC
            bar_request = StockLatestBarRequest(symbol_or_symbols=symbol)
            bars = self.data_client.get_stock_latest_bar(bar_request)
            bar = bars.get(symbol)
            
            result = {
                "symbol": symbol,
                "last": float(quote.ask_price) if quote.ask_price else None,  # Approximate
                "bid": float(quote.bid_price) if quote.bid_price else None,
                "ask": float(quote.ask_price) if quote.ask_price else None,
                "bid_size": int(quote.bid_size) if quote.bid_size else 0,
                "ask_size": int(quote.ask_size) if quote.ask_size else 0,
                "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
            }
            
            # Add bar data if available
            if bar:
                result.update({
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": int(bar.volume),
                    "vwap": float(bar.vwap) if bar.vwap else None,
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            raise
    
    def get_quotes_batch(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Get quotes for multiple symbols in one request.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            List of quote dicts
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self.data_client.get_stock_latest_quote(request)
            
            results = []
            for symbol in symbols:
                if symbol in quotes:
                    quote = quotes[symbol]
                    results.append({
                        "symbol": symbol,
                        "last": float(quote.ask_price) if quote.ask_price else None,
                        "bid": float(quote.bid_price) if quote.bid_price else None,
                        "ask": float(quote.ask_price) if quote.ask_price else None,
                        "bid_size": int(quote.bid_size) if quote.bid_size else 0,
                        "ask_size": int(quote.ask_size) if quote.ask_size else 0,
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get batch quotes: {e}")
            return []
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1D",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get historical OHLCV data.
        
        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe ('1Min', '5Min', '1H', '1D')
            limit: Number of bars to fetch
            
        Returns:
            List of bar dicts with date, open, high, low, close, volume
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        # Map timeframe string to TimeFrame object
        tf_map = {
            "1Min": TimeFrame.Minute,
            "5Min": TimeFrame(5, "Min"),
            "15Min": TimeFrame(15, "Min"),
            "1H": TimeFrame.Hour,
            "1D": TimeFrame.Day,
        }
        tf = tf_map.get(timeframe, TimeFrame.Day)
        
        try:
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=limit * 2)  # Buffer for weekends
            
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                limit=limit,
            )
            bars = self.data_client.get_stock_bars(request)
            
            if symbol not in bars:
                return []
            
            result = []
            for bar in bars[symbol][-limit:]:  # Take last N bars
                result.append({
                    "date": bar.timestamp.isoformat(),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": int(bar.volume),
                    "vwap": float(bar.vwap) if bar.vwap else None,
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {e}")
            return []
    
    # =========================================================================
    # ACCOUNT & POSITIONS
    # =========================================================================
    
    def get_portfolio(self) -> Dict[str, Any]:
        """Get account portfolio summary.
        
        Returns:
            Dict with cash, equity, positions, P&L
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            account = self.trading_client.get_account()
            positions = self.get_positions()
            
            # Calculate position market value
            market_value = sum(p.current_price * p.quantity for p in positions)
            unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            
            return {
                "cash": float(account.cash),
                "total_assets": float(account.equity),
                "equity": float(account.equity),
                "buying_power": float(account.buying_power),
                "market_value": market_value,
                "positions": [
                    {
                        "symbol": p.symbol,
                        "quantity": p.quantity,
                        "avg_cost": p.avg_cost,
                        "current_price": p.current_price,
                        "unrealized_pnl": p.unrealized_pnl,
                        "unrealized_pnl_pct": p.unrealized_pnl_pct,
                    }
                    for p in positions
                ],
                "position_count": len(positions),
                "unrealized_pnl": unrealized_pnl,
                "daily_pnl": float(account.equity) - float(account.last_equity),
                "daily_pnl_pct": (float(account.equity) - float(account.last_equity)) / float(account.last_equity) * 100 if float(account.last_equity) > 0 else 0,
                "currency": "USD",
            }
            
        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            raise
    
    def get_positions(self) -> List[Position]:
        """Get all open positions.
        
        Returns:
            List of Position objects
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            raw_positions = self.trading_client.get_all_positions()
            
            positions = []
            for p in raw_positions:
                positions.append(Position(
                    symbol=p.symbol,
                    quantity=int(p.qty),
                    avg_cost=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    unrealized_pnl=float(p.unrealized_pl),
                    unrealized_pnl_pct=float(p.unrealized_plpc) * 100,
                ))
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have an open position in a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if position exists
        """
        positions = self.get_positions()
        return any(p.symbol == symbol for p in positions)
    
    # =========================================================================
    # ORDER EXECUTION
    # =========================================================================
    
    def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        limit_price: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        reason: str = "",
    ) -> OrderResult:
        """Execute a trade with optional bracket orders.
        
        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell'
            quantity: Number of shares
            order_type: 'market' or 'limit'
            limit_price: Limit price (required for limit orders)
            stop_loss: Stop loss price (creates bracket order)
            take_profit: Take profit price (creates bracket order)
            reason: Reason for trade (logged)
            
        Returns:
            OrderResult with status and details
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        # Map side string to enum
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        
        # Round prices to avoid sub-penny rejection
        limit_price = round_price(limit_price)
        stop_loss = round_price(stop_loss)
        take_profit = round_price(take_profit)
        
        logger.info(f"Executing {side} {quantity} {symbol} @ {order_type}"
                   f" (SL={stop_loss}, TP={take_profit})")
        
        try:
            # Determine order class
            if stop_loss and take_profit:
                order_class = OrderClass.BRACKET
            elif stop_loss or take_profit:
                order_class = OrderClass.OTO  # One-Triggers-Other
            else:
                order_class = OrderClass.SIMPLE
            
            # Build order request
            if order_type.lower() == "limit" and limit_price:
                # Limit order with bracket
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                    order_class=order_class,
                )
            else:
                # Market order with bracket
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    order_class=order_class,
                )
            
            # Add stop loss leg
            if stop_loss:
                order_request.stop_loss = StopLossRequest(stop_price=stop_loss)
            
            # Add take profit leg
            if take_profit:
                order_request.take_profit = TakeProfitRequest(limit_price=take_profit)
            
            # Submit order
            order = self.trading_client.submit_order(order_request)
            
            # Determine status
            status = str(order.status).lower()
            if order.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                filled_qty = int(order.filled_qty) if order.filled_qty else 0
                filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
            else:
                filled_qty = 0
                filled_price = None
            
            return OrderResult(
                order_id=str(order.id),
                status=status,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=filled_price,
                filled_quantity=filled_qty,
                message=f"Order {order.id} {status}",
            )
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            return OrderResult(
                order_id="",
                status="error",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                filled_price=None,
                filled_quantity=0,
                message=str(e),
            )
    
    def close_position(self, symbol: str, reason: str = "") -> OrderResult:
        """Close a specific position.
        
        Args:
            symbol: Stock symbol to close
            reason: Reason for closing (logged)
            
        Returns:
            OrderResult with status
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        logger.info(f"Closing position: {symbol} - {reason}")
        
        try:
            # Close position via API
            order = self.trading_client.close_position(symbol)
            
            status = str(order.status).lower() if hasattr(order, 'status') else 'submitted'
            
            return OrderResult(
                order_id=str(order.id) if hasattr(order, 'id') else "",
                status=status,
                symbol=symbol,
                side="sell",
                quantity=int(order.qty) if hasattr(order, 'qty') else 0,
                order_type="market",
                filled_price=float(order.filled_avg_price) if hasattr(order, 'filled_avg_price') and order.filled_avg_price else None,
                filled_quantity=int(order.filled_qty) if hasattr(order, 'filled_qty') and order.filled_qty else 0,
                message=f"Position closed: {reason}",
            )
            
        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            return OrderResult(
                order_id="",
                status="error",
                symbol=symbol,
                side="sell",
                quantity=0,
                order_type="market",
                filled_price=None,
                filled_quantity=0,
                message=str(e),
            )
    
    def close_all_positions(self, reason: str = "") -> List[OrderResult]:
        """Emergency close all positions.
        
        Args:
            reason: Reason for closing (logged)
            
        Returns:
            List of OrderResults
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        logger.warning(f"CLOSING ALL POSITIONS: {reason}")
        
        try:
            # Use Alpaca's close all positions API
            orders = self.trading_client.close_all_positions(cancel_orders=True)
            
            results = []
            for order in orders:
                results.append(OrderResult(
                    order_id=str(order.id) if hasattr(order, 'id') else "",
                    status=str(order.status).lower() if hasattr(order, 'status') else 'submitted',
                    symbol=order.symbol if hasattr(order, 'symbol') else "",
                    side="sell",
                    quantity=int(order.qty) if hasattr(order, 'qty') else 0,
                    order_type="market",
                    filled_price=None,
                    filled_quantity=0,
                    message=f"Emergency close: {reason}",
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            return []
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    def get_orders(self, status: str = "open") -> List[Dict[str, Any]]:
        """Get orders by status.
        
        Args:
            status: 'open', 'closed', 'all'
            
        Returns:
            List of order dicts
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            if status == "open":
                query_status = QueryOrderStatus.OPEN
            elif status == "closed":
                query_status = QueryOrderStatus.CLOSED
            else:
                query_status = QueryOrderStatus.ALL
            
            request = GetOrdersRequest(status=query_status)
            orders = self.trading_client.get_orders(request)
            
            return [
                {
                    "order_id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side).lower(),
                    "quantity": int(o.qty),
                    "filled_quantity": int(o.filled_qty) if o.filled_qty else 0,
                    "status": str(o.status).lower(),
                    "order_type": str(o.order_type).lower(),
                    "limit_price": float(o.limit_price) if o.limit_price else None,
                    "stop_price": float(o.stop_price) if o.stop_price else None,
                    "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if not self._connected:
            raise RuntimeError("Not connected to Alpaca")
        
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Cancelled order: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_client: Optional[AlpacaClient] = None


def get_alpaca_client() -> AlpacaClient:
    """Get the global AlpacaClient instance.
    
    Returns:
        Connected AlpacaClient instance
        
    Raises:
        RuntimeError: If client not initialized
    """
    global _client
    if _client is None:
        raise RuntimeError("AlpacaClient not initialized. Call init_alpaca_client() first.")
    return _client


def init_alpaca_client(
    api_key: str = None,
    secret_key: str = None,
    paper: bool = True,
) -> AlpacaClient:
    """Initialize and connect the global AlpacaClient.
    
    Args:
        api_key: Alpaca API key
        secret_key: Alpaca secret key
        paper: Use paper trading environment
        
    Returns:
        Connected AlpacaClient instance
    """
    global _client
    _client = AlpacaClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=paper,
    )
    _client.connect()
    return _client
