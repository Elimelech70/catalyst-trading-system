#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: alpaca_trader.py
Version: 1.0.0
Last Updated: 2025-11-18
Purpose: Alpaca trading integration for autonomous order execution

Description:
Handles all Alpaca API interactions for trading execution.
Supports:
- Market orders
- Limit orders
- Bracket orders (entry + stop + target)
- Position tracking
- Order status updates
"""

import os
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest
)
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

logger = logging.getLogger(__name__)


class AlpacaTrader:
    """
    Alpaca trading client for autonomous order execution.

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
        # Get credentials from environment
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.paper = os.getenv("TRADING_MODE", "paper").lower() == "paper"

        if not self.api_key or not self.secret_key:
            logger.warning("Alpaca credentials not configured")
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
            logger.info(f"Alpaca trader initialized ({mode} mode)")

        except Exception as e:
            logger.error(f"Alpaca initialization failed: {e}")
            self.enabled = False

    def is_enabled(self) -> bool:
        """Check if Alpaca trading is enabled"""
        return self.enabled

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for symbol"""
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
        Submit market order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            side: "buy" or "sell"

        Returns:
            Order result dictionary
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY
            )

            order = self.trading_client.submit_order(request)

            logger.info(f"Market order submitted: {symbol} {side} {quantity} shares")

            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "market",
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "filled_qty": order.filled_qty or 0,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None
            }

        except Exception as e:
            logger.error(f"Market order failed for {symbol}: {e}")
            raise

    async def submit_limit_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        limit_price: float
    ) -> Dict[str, Any]:
        """
        Submit limit order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            side: "buy" or "sell"
            limit_price: Limit price

        Returns:
            Order result dictionary
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            request = LimitOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price
            )

            order = self.trading_client.submit_order(request)

            logger.info(f"Limit order submitted: {symbol} {side} {quantity} @ ${limit_price}")

            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": "limit",
                "limit_price": limit_price,
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
            }

        except Exception as e:
            logger.error(f"Limit order failed for {symbol}: {e}")
            raise

    async def submit_bracket_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Submit bracket order (entry + stop loss + take profit).

        This is the RECOMMENDED order type for autonomous trading.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            side: "buy" or "sell"
            entry_price: Entry limit price (None = market order)
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Order result dictionary
        """
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            # Build stop loss and take profit requests
            stop_loss_req = None
            take_profit_req = None

            if stop_loss:
                stop_loss_req = StopLossRequest(stop_price=stop_loss)

            if take_profit:
                take_profit_req = TakeProfitRequest(limit_price=take_profit)

            # Create order request (market or limit)
            if entry_price:
                # Limit order entry
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=entry_price,
                    stop_loss=stop_loss_req,
                    take_profit=take_profit_req
                )
                order_type = "limit_bracket"
            else:
                # Market order entry
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    stop_loss=stop_loss_req,
                    take_profit=take_profit_req
                )
                order_type = "market_bracket"

            order = self.trading_client.submit_order(request)

            logger.info(
                f"Bracket order submitted: {symbol} {side} {quantity} shares "
                f"(entry: ${entry_price or 'market'}, stop: ${stop_loss}, target: ${take_profit})"
            )

            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "status": order.status.value,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
            }

        except Exception as e:
            logger.error(f"Bracket order failed for {symbol}: {e}")
            raise

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of an order"""
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
            logger.error(f"Failed to get order status: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an open position"""
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            order = self.trading_client.close_position(symbol)

            logger.info(f"Position closed: {symbol}")

            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "status": order.status.value,
                "filled_qty": order.filled_qty or 0
            }

        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            raise

    async def close_all_positions(self) -> List[Dict[str, Any]]:
        """Close all open positions (emergency stop)"""
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            orders = self.trading_client.close_all_positions(cancel_orders=True)

            logger.critical(f"All positions closed: {len(orders)} positions")

            return [
                {
                    "order_id": str(order.id),
                    "symbol": order.symbol,
                    "status": order.status.value
                }
                for order in orders
            ]

        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            raise

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.enabled:
            raise RuntimeError("Alpaca trading not enabled")

        try:
            account = self.trading_client.get_account()

            return {
                "account_number": account.account_number,
                "status": account.status.value,
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked
            }

        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise


# Global singleton instance
alpaca_trader = AlpacaTrader()


if __name__ == '__main__':
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test_alpaca():
        print("Testing Alpaca Trader...")
        print("=" * 70)

        if not alpaca_trader.is_enabled():
            print("❌ Alpaca not configured (missing credentials)")
            return

        try:
            # Get account info
            account = await alpaca_trader.get_account_info()
            print(f"✅ Account: {account['account_number']}")
            print(f"   Cash: ${account['cash']:,.2f}")
            print(f"   Portfolio: ${account['portfolio_value']:,.2f}")

            # Get current price
            price = await alpaca_trader.get_current_price("AAPL")
            if price:
                print(f"✅ AAPL price: ${price:.2f}")

            print("\n" + "=" * 70)
            print("Alpaca Trader Test: PASSED")

        except Exception as e:
            print(f"❌ Test failed: {e}")

    asyncio.run(test_alpaca())
