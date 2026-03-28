#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: broker.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Alpaca broker integration for the cerebellum

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- AlpacaBroker class with connect/disconnect lifecycle
- _normalize_side() — CRITICAL (Lesson 6 from CLAUDE.md)
- Order submission, position management, market data

Description:
Broker integration for the cerebellum to execute trades via Alpaca.
Follows the same patterns as the existing AlpacaClient but focused
on the cerebellum's specific needs.

CRITICAL: Uses _normalize_side() to prevent the order side bug
(v1.2.0 Lesson 6). 'long' → 'buy', 'short' → 'sell'.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger("cerebellum.broker")


class AlpacaBroker:
    """
    Alpaca broker client for the cerebellum.

    Handles order execution, position management, and market data.
    CRITICAL: Always uses _normalize_side() before order submission.
    """

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.trading_client: Optional[TradingClient] = None
        self.data_client: Optional[StockHistoricalDataClient] = None

    def connect(self) -> bool:
        """Initialize Alpaca clients."""
        try:
            self.trading_client = TradingClient(
                self.api_key, self.secret_key, paper=self.paper
            )
            self.data_client = StockHistoricalDataClient(
                self.api_key, self.secret_key
            )
            logger.info("Alpaca broker connected (paper=%s)", self.paper)
            return True
        except Exception as e:
            logger.error("Alpaca connection failed: %s", e, exc_info=True)
            return False

    def disconnect(self):
        """Clean up clients."""
        self.trading_client = None
        self.data_client = None
        logger.info("Alpaca broker disconnected")

    @staticmethod
    def _normalize_side(side: str) -> OrderSide:
        """
        CRITICAL: Normalize order side input.
        Lesson 6 from CLAUDE.md — the order side bug that affected 81 positions.
        'long' → buy, 'short' → sell, 'buy' → buy, 'sell' → sell.
        """
        mapping = {
            "long": OrderSide.BUY,
            "buy": OrderSide.BUY,
            "short": OrderSide.SELL,
            "sell": OrderSide.SELL,
        }
        normalized = mapping.get(side.lower())
        if normalized is None:
            raise ValueError(
                f"Invalid order side: '{side}'. "
                f"Valid values: {list(mapping.keys())}"
            )
        logger.info("Side normalized: '%s' → %s", side, normalized.value)
        return normalized

    @staticmethod
    def round_price(price: float) -> float:
        """Round to 2 decimal places to prevent sub-penny violations."""
        return round(price, 2)

    def get_account(self) -> Dict[str, Any]:
        """Get current account info."""
        account = self.trading_client.get_account()
        return {
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "equity": float(account.equity),
            "portfolio_value": float(account.portfolio_value),
            "status": account.status,
            "pattern_day_trader": account.pattern_day_trader,
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        positions = self.trading_client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": p.side,
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "market_value": float(p.market_value),
            }
            for p in positions
        ]

    def get_bars(
        self,
        symbol: str,
        days: int = 20,
        timeframe: str = "1Day",
    ) -> List[Dict[str, Any]]:
        """Get historical bars for a symbol."""
        tf = TimeFrame.Day if timeframe == "1Day" else TimeFrame.Hour
        end = datetime.now(ZoneInfo("America/New_York"))
        start = end - timedelta(days=days)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
        )
        bars_set = self.data_client.get_stock_bars(request)
        bars = bars_set.get(symbol, []) if hasattr(bars_set, 'get') else bars_set.data.get(symbol, [])

        return [
            {
                "timestamp": str(bar.timestamp),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
            for bar in bars
        ]

    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Dict[str, Any]:
        """
        Submit an order to Alpaca.
        CRITICAL: Uses _normalize_side() first.
        """
        # Normalize side — LESSON 6
        order_side = self._normalize_side(side)

        tif = TimeInForce.DAY if time_in_force == "day" else TimeInForce.GTC

        if order_type == "limit" and limit_price:
            request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=tif,
                limit_price=self.round_price(limit_price),
            )
        else:
            request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=tif,
            )

        # Add stop loss if provided
        if stop_loss_price:
            request.stop_loss = StopLossRequest(stop_price=self.round_price(stop_loss_price))
        if take_profit_price:
            request.take_profit = TakeProfitRequest(limit_price=self.round_price(take_profit_price))

        try:
            order = self.trading_client.submit_order(request)
            result = {
                "order_id": str(order.id),
                "symbol": order.symbol,
                "qty": str(order.qty),
                "side": order.side.value,
                "type": order.type.value,
                "status": order.status.value,
                "submitted_at": str(order.submitted_at),
            }
            logger.info(
                "Order submitted: %s %s %s @ %s — status=%s",
                order.side.value, order.qty, order.symbol,
                limit_price or "market", order.status.value,
            )
            return result
        except Exception as e:
            logger.error("Order submission failed: %s", e, exc_info=True)
            return {"error": str(e), "symbol": symbol, "side": side, "qty": qty}

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close a specific position."""
        try:
            order = self.trading_client.close_position(symbol)
            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "status": "closing",
            }
        except Exception as e:
            logger.error("Failed to close position %s: %s", symbol, e)
            return {"error": str(e), "symbol": symbol}

    def close_all_positions(self) -> Dict[str, Any]:
        """Emergency: close all positions."""
        try:
            responses = self.trading_client.close_all_positions(cancel_orders=True)
            return {
                "closed": len(responses) if responses else 0,
                "status": "all_closed",
            }
        except Exception as e:
            logger.error("Failed to close all positions: %s", e)
            return {"error": str(e)}
