#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: alpaca_trader.py
Version: 2.1.0
Last Updated: 2026-01-01
Purpose: Consolidated Alpaca trading client - SINGLE SOURCE OF TRUTH

REVISION HISTORY:
v2.1.0 (2026-01-01) - FIX: Bracket orders now use GTC instead of DAY
  - Changed TimeInForce.DAY to TimeInForce.GTC for bracket orders
  - Stop-loss and take-profit orders now persist across trading days
  - Fixes issue where all brackets expired at market close

v2.0.0 (2025-12-27) - C2 Fix: Consolidated from 5 duplicate files
  - services/trading/common/alpaca_trader.py
  - services/risk-manager/common/alpaca_trader.py
  - services/workflow/common/alpaca_trader.py
  - services/shared/common/alpaca_trader.py
  - services/common/alpaca_trader.py
  - Added order_class=OrderClass.BRACKET for bracket orders
  - Sub-penny price rounding enforced
  - Critical side mapping validation

v1.5.0 - Order side mapping bug fix
v1.4.0 - Sub-penny price handling
v1.3.0 - Bracket order support

LOCATION:
  This file should be at: services/shared/common/alpaca_trader.py
  All other locations should be symlinks to this file.

USAGE:
    from services.shared.common.alpaca_trader import AlpacaTrader
    
    trader = AlpacaTrader()
    order = await trader.submit_bracket_order(
        symbol="AAPL",
        quantity=10,
        side="buy",
        entry_price=150.00,
        stop_loss=145.00,
        take_profit=160.00
    )
"""

import logging
import os
from typing import Any, Dict, List, Optional

# Alpaca SDK imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
        GetOrdersRequest,
    )
    from alpaca.trading.enums import (
        OrderSide,
        OrderClass,
        TimeInForce,
        QueryOrderStatus,
    )
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def round_price(price: Optional[float]) -> Optional[float]:
    """
    Round price to 2 decimal places to avoid sub-penny rejection.
    
    Alpaca rejects orders with sub-penny prices (e.g., 9.050000190734863).
    This helper ensures all prices are properly rounded to cents.
    
    Args:
        price: The price to round (can be None)
        
    Returns:
        Price rounded to 2 decimal places, or None if input was None
    """
    if price is None:
        return None
    return round(float(price), 2)


def map_side(side: str) -> OrderSide:
    """
    Map side string to Alpaca OrderSide enum.
    
    CRITICAL: This mapping has caused bugs before. Be very careful.
    
    Args:
        side: Input side string ('buy', 'sell', 'long', 'short')
        
    Returns:
        OrderSide enum value
        
    Raises:
        ValueError: If side string is not recognized
    """
    side_lower = side.lower().strip()
    
    if side_lower in ('buy', 'long'):
        return OrderSide.BUY
    elif side_lower in ('sell', 'short'):
        return OrderSide.SELL
    else:
        raise ValueError(f"Invalid order side: '{side}'. Must be 'buy', 'sell', 'long', or 'short'")


def validate_side_mapping(input_side: str, output_side: OrderSide) -> None:
    """
    Validate that side mapping is correct.
    
    This is a CRITICAL safety check. The order side bug has caused
    inverted positions in the past. This validation prevents that.
    
    Args:
        input_side: Original side string from caller
        output_side: Mapped OrderSide enum
        
    Raises:
        RuntimeError: If mapping is incorrect (would cause inverted position)
    """
    input_lower = input_side.lower().strip()
    
    if input_lower in ("long", "buy") and output_side != OrderSide.BUY:
        raise RuntimeError(
            f"CRITICAL: Order side mismatch! "
            f"Input '{input_side}' should map to BUY, "
            f"but got {output_side.value}. Aborting order to prevent inverted position."
        )
    
    if input_lower in ("short", "sell") and output_side != OrderSide.SELL:
        raise RuntimeError(
            f"CRITICAL: Order side mismatch! "
            f"Input '{input_side}' should map to SELL, "
            f"but got {output_side.value}. Aborting order to prevent inverted position."
        )


# ============================================================================
# ALPACA TRADER CLASS
# ============================================================================

class AlpacaTrader:
    """
    Alpaca trading client for autonomous order execution.
    
    This is the SINGLE SOURCE OF TRUTH for Alpaca integration.
    All services must use this class via import or symlink.
    
    Usage:
        trader = AlpacaTrader()
        order = await trader.submit_bracket_order(
            symbol="AAPL",
            quantity=10,
            side="buy",
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00
        )
    """

    def __init__(self):
        """Initialize Alpaca trader with credentials from environment."""
        if not ALPACA_AVAILABLE:
            logger.warning("Alpaca SDK not installed. Trading disabled.")
            self.enabled = False
            return
            
        # Get credentials from environment
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.paper = os.getenv("TRADING_MODE", "paper").lower() == "paper"

        if not self.api_key or not self.secret_key:
            logger.warning("Alpaca credentials not configured. Trading disabled.")
            self.enabled = False
            return

        try:
            # Trading client (for orders)
            self.trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper
            )

            # Data client (for quotes)
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )

            self.enabled = True
            mode = "PAPER" if self.paper else "LIVE"
            logger.info(f"AlpacaTrader v2.0.0 initialized ({mode} mode)")

        except Exception as e:
            logger.error(f"Alpaca initialization failed: {e}")
            self.enabled = False

    def is_enabled(self) -> bool:
        """Check if Alpaca trading is enabled."""
        return self.enabled

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current market price for symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Mid-price (average of bid and ask), or None if unavailable
        """
        if not self.enabled:
            return None

        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)

            if symbol in quotes:
                quote = quotes[symbol]
                # Use mid-price between bid and ask
                return (quote.bid_price + quote.ask_price) / 2

            return None

        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def submit_market_order(
        self,
        symbol: str,
        quantity: int,
        side: str
    ) -> Dict[str, Any]:
        """
        Submit simple market order.
        
        Args:
            symbol: Stock ticker
            quantity: Number of shares
            side: 'buy' or 'sell' (also accepts 'long' or 'short')
            
        Returns:
            Order details dict
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            # Map and validate side
            order_side = map_side(side)
            validate_side_mapping(side, order_side)

            request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY
            )

            order = self.trading_client.submit_order(request)

            logger.info(
                f"ORDER CONFIRMED [MARKET]: order_id={order.id}, "
                f"symbol={symbol}, side={order.side}, qty={quantity}"
            )

            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "market",
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
            }

        except Exception as e:
            logger.error(f"Market order failed for {symbol}: {e}")
            raise

    async def submit_bracket_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        entry_price: Optional[float] = None,
        stop_loss: float = None,
        take_profit: float = None
    ) -> Dict[str, Any]:
        """
        Submit bracket order with stop-loss and take-profit.
        
        CRITICAL: Uses OrderClass.BRACKET to ensure proper bracket order creation.
        
        Args:
            symbol: Stock ticker
            quantity: Number of shares
            side: 'buy' or 'sell' (also accepts 'long' or 'short')
            entry_price: Limit price for entry (None = market order)
            stop_loss: Stop-loss price (REQUIRED)
            take_profit: Take-profit price (REQUIRED)
            
        Returns:
            Order details dict with order_id, status, etc.
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        if stop_loss is None or take_profit is None:
            raise ValueError("stop_loss and take_profit are required for bracket orders")

        try:
            # Map and validate side
            order_side = map_side(side)
            validate_side_mapping(side, order_side)

            # Round all prices to avoid sub-penny rejection
            rounded_entry = round_price(entry_price)
            rounded_stop = round_price(stop_loss)
            rounded_target = round_price(take_profit)

            logger.info(
                f"SUBMITTING BRACKET ORDER: symbol={symbol}, side={side}, "
                f"qty={quantity}, entry={rounded_entry}, "
                f"stop={rounded_stop}, target={rounded_target}"
            )

            # Create stop-loss and take-profit requests
            stop_loss_req = StopLossRequest(stop_price=rounded_stop)
            take_profit_req = TakeProfitRequest(limit_price=rounded_target)

            if rounded_entry:
                # Limit order entry with bracket
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.GTC,  # GTC so stops/targets persist across days
                    limit_price=rounded_entry,
                    order_class=OrderClass.BRACKET,  # CRITICAL: Must be BRACKET
                    stop_loss=stop_loss_req,
                    take_profit=take_profit_req
                )
                order_type = "limit_bracket"
            else:
                # Market order entry with bracket
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.GTC,  # GTC so stops/targets persist across days
                    order_class=OrderClass.BRACKET,  # CRITICAL: Must be BRACKET
                    stop_loss=stop_loss_req,
                    take_profit=take_profit_req
                )
                order_type = "market_bracket"

            order = self.trading_client.submit_order(request)

            logger.info(
                f"ORDER CONFIRMED [BRACKET]: order_id={order.id}, "
                f"symbol={symbol}, alpaca_side={order.side}, "
                f"status={order.status.value}, qty={quantity}, "
                f"entry=${rounded_entry or 'market'}, "
                f"stop=${rounded_stop}, target=${rounded_target}"
            )

            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "entry_price": rounded_entry,
                "stop_loss": rounded_stop,
                "take_profit": rounded_target,
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
            }

        except Exception as e:
            logger.error(f"Bracket order failed for {symbol}: {e}")
            raise

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order.
        
        Args:
            order_id: Alpaca order ID
            
        Returns:
            Order status dict
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            order = self.trading_client.get_order_by_id(order_id)

            return {
                "order_id": str(order.id),
                "symbol": order.symbol,
                "status": order.status.value,
                "filled_qty": order.filled_qty or 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None
            }

        except Exception as e:
            logger.error(f"Failed to get order status for {order_id}: {e}")
            raise

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            order_id: Alpaca order ID
            
        Returns:
            Cancellation result dict
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            self.trading_client.cancel_order_by_id(order_id)
            
            logger.info(f"ORDER CANCELLED: order_id={order_id}")
            
            return {
                "order_id": order_id,
                "status": "cancelled",
                "message": "Order cancellation requested"
            }

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders, optionally filtered by symbol.
        
        Args:
            symbol: Filter by stock ticker (optional)
            
        Returns:
            List of order dicts
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            request = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[symbol] if symbol else None
            )
            
            orders = self.trading_client.get_orders(request)
            
            return [
                {
                    "order_id": str(order.id),
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.qty,
                    "filled_qty": order.filled_qty or 0,
                    "status": order.status.value,
                    "order_type": order.type.value if order.type else None,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
                }
                for order in orders
            ]

        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            raise

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions from Alpaca.
        
        Returns:
            List of position dicts
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            positions = self.trading_client.get_all_positions()
            
            return [
                {
                    "symbol": pos.symbol,
                    "quantity": int(pos.qty),
                    "side": "long" if float(pos.qty) > 0 else "short",
                    "entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pnl": float(pos.unrealized_pl),
                    "unrealized_pnl_pct": float(pos.unrealized_plpc) * 100
                }
                for pos in positions
            ]

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close a position by symbol.
        
        Args:
            symbol: Stock ticker to close
            
        Returns:
            Close result dict
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            order = self.trading_client.close_position(symbol)
            
            logger.info(f"POSITION CLOSED: symbol={symbol}, order_id={order.id}")
            
            return {
                "symbol": symbol,
                "order_id": str(order.id),
                "status": order.status.value,
                "message": f"Position close order submitted for {symbol}"
            }

        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            raise

    async def close_all_positions(self) -> Dict[str, Any]:
        """
        Emergency: Close ALL positions.
        
        Returns:
            Results dict with closed positions
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            logger.warning("EMERGENCY: Closing ALL positions!")
            
            result = self.trading_client.close_all_positions(cancel_orders=True)
            
            logger.warning(f"EMERGENCY COMPLETE: Closed {len(result)} positions")
            
            return {
                "action": "close_all_positions",
                "positions_closed": len(result),
                "details": [
                    {"symbol": pos.symbol, "order_id": str(pos.id)}
                    for pos in result
                ]
            }

        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            raise


# ============================================================================
# MODULE-LEVEL SINGLETON (for convenience)
# ============================================================================

# Create singleton instance
_alpaca_trader: Optional[AlpacaTrader] = None


def get_alpaca_trader() -> AlpacaTrader:
    """Get or create AlpacaTrader singleton."""
    global _alpaca_trader
    if _alpaca_trader is None:
        _alpaca_trader = AlpacaTrader()
    return _alpaca_trader


# Default instance for simple imports
alpaca_trader = get_alpaca_trader()
