#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: tool_executor.py
Version: 2.2.0
Last Updated: 2025-01-01
Purpose: Routes Claude's tool calls to actual implementations

REVISION HISTORY:
v2.2.0 (2025-01-01) - Added position monitoring integration
- Call position monitor after BUY orders
- Pass agent reference to executor
- Wide bracket orders as backup

v2.1.0 (2025-12-30) - Updated to use MoomooClient
- Changed imports from futu to moomoo
- Using moomoo-api SDK

v2.0.0 (2025-12-20) - Migrated to Moomoo/Futu
- Replaced IBKR with Futu broker client
- Updated all broker references

v1.0.0 (2025-12-06) - Initial implementation
- Tool call routing and execution
- Result formatting for Claude
- Error handling and logging

Description:
This module receives tool calls from Claude and routes them to the
appropriate implementation functions. It handles all 12 trading tools
defined in the CLAUDE.md specification.

NEW in v2.2.0: After successful BUY orders, automatically starts
position monitoring that runs until exit. Uses rules-based signal
detection (free) and Haiku consultations (~$0.05/call) for uncertain
signals.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from brokers.moomoo import get_moomoo_client
from data.database import get_database
from data.market import get_market_data
from data.news import get_news_client
from data.patterns import get_pattern_detector
from safety import get_safety_validator, validate_trade_request
from tools import validate_tool_input

# NEW: Position monitoring imports
from position_monitor import start_position_monitor

logger = logging.getLogger(__name__)

HK_TZ = ZoneInfo("Asia/Hong_Kong")


class ToolExecutor:
    """Executes tool calls from Claude."""

    def __init__(
        self,
        cycle_id: str,
        alert_callback: Any = None,
        agent: Any = None,  # NEW: Reference to TradingAgent
    ):
        """Initialize tool executor.

        Args:
            cycle_id: Current agent cycle ID
            alert_callback: Function to send alerts (severity, subject, message)
            agent: Reference to TradingAgent (for Claude client access)
        """
        self.cycle_id = cycle_id
        self.alert_callback = alert_callback
        self.agent = agent  # NEW: Store agent reference
        self.tools_called: list[dict] = []
        self.trades_executed = 0

        # Initialize services
        self.broker = get_moomoo_client()
        self.db = get_database()
        self.market = get_market_data(self.broker)
        self.patterns = get_pattern_detector(self.market)
        self.news = get_news_client()
        self.safety = get_safety_validator()

    def execute(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Tool result as dictionary
        """
        # Validate input
        is_valid, error = validate_tool_input(tool_name, tool_input)
        if not is_valid:
            return {"error": error, "success": False}

        # Log tool call
        self.tools_called.append(
            {
                "tool": tool_name,
                "input": tool_input,
                "timestamp": datetime.now(HK_TZ).isoformat(),
            }
        )

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
            "scan_market": self._scan_market,
            "get_quote": self._get_quote,
            "get_technicals": self._get_technicals,
            "detect_patterns": self._detect_patterns,
            "get_news": self._get_news,
            "check_risk": self._check_risk,
            "get_portfolio": self._get_portfolio,
            "execute_trade": self._execute_trade,
            "close_position": self._close_position,
            "close_all": self._close_all,
            "send_alert": self._send_alert,
            "log_decision": self._log_decision,
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
            "min_volume_ratio": min_volume_ratio,
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    def _get_quote(self, inputs: dict) -> dict:
        """Get current quote for a symbol."""
        symbol = inputs["symbol"]
        quote = self.broker.get_quote(symbol)

        return {
            "symbol": symbol,
            "quote": quote,
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    def _get_technicals(self, inputs: dict) -> dict:
        """Get technical indicators for a symbol."""
        symbol = inputs["symbol"]
        timeframe = inputs.get("timeframe", "15m")

        technicals = self.market.get_technicals(symbol, timeframe)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "technicals": technicals,
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    def _detect_patterns(self, inputs: dict) -> dict:
        """Detect chart patterns for a symbol."""
        symbol = inputs["symbol"]
        timeframe = inputs.get("timeframe", "15m")

        patterns = self.patterns.detect_patterns(symbol, timeframe)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "patterns_found": len(patterns),
            "patterns": patterns,
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    def _get_news(self, inputs: dict) -> dict:
        """Get news and sentiment for a symbol."""
        symbol = inputs["symbol"]
        limit = min(inputs.get("limit", 5), 10)

        news = self.news.get_news(symbol, limit)

        return {
            "symbol": symbol,
            "articles_found": len(news),
            "articles": news,
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    # =========================================================================
    # Risk Management Tools
    # =========================================================================

    def _check_risk(self, inputs: dict) -> dict:
        """Check if a trade passes risk validation."""
        symbol = inputs["symbol"]
        side = inputs["side"]
        quantity = inputs["quantity"]
        price = inputs.get("price", 0)

        result = validate_trade_request(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )

        return {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "approved": result.get("approved", False),
            "reason": result.get("reason", ""),
            "checks": result.get("checks", {}),
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    def _get_portfolio(self, inputs: dict) -> dict:
        """Get current portfolio status."""
        portfolio = self.broker.get_portfolio()

        return {
            "portfolio": portfolio,
            "timestamp": datetime.now(HK_TZ).isoformat(),
        }

    # =========================================================================
    # Trading Execution Tools
    # =========================================================================

    def _execute_trade(self, inputs: dict) -> dict:
        """
        Execute a trade and start position monitoring for BUY orders.
        
        NEW in v2.2.0: After successful BUY, starts continuous monitoring
        that runs until exit. Uses rules-based signal detection (free)
        and Haiku consultations (~$0.05/call) for uncertain signals.
        """
        symbol = inputs.get("symbol")
        side = inputs.get("side", "BUY").upper()
        quantity = inputs.get("quantity")
        order_type = inputs.get("order_type", "LIMIT").upper()
        price = inputs.get("price")
        stop_price = inputs.get("stop_price")
        target_price = inputs.get("target_price")
        reasoning = inputs.get("reasoning", "")

        logger.info(f"Executing trade: {side} {quantity} {symbol}")

        # Validate trade first
        risk_check = validate_trade_request(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price or 0,
        )

        if not risk_check.get("approved"):
            return {
                "status": "rejected",
                "reason": risk_check.get("reason", "Risk check failed"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }

        try:
            # Place the order
            result = self.broker.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
            )

            if result.get("status") in ["filled", "FILLED", "submitted", "SUBMITTED"]:
                self.trades_executed += 1

                fill_price = float(result.get("fill_price", price or 0))

                # Log the trade
                try:
                    self.db.log_trade(
                        cycle_id=self.cycle_id,
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=fill_price,
                        order_type=order_type,
                        reasoning=reasoning,
                    )
                except Exception as e:
                    logger.error(f"Failed to log trade: {e}")

                # ==============================================================
                # NEW: START POSITION MONITORING FOR BUY ORDERS
                # ==============================================================
                monitor_result = None
                monitor_error = None
                
                if side == "BUY" and self.agent:
                    logger.info(f"Starting position monitor for {symbol}")

                    # Get current volume for baseline
                    try:
                        quote = self.broker.get_quote(symbol)
                        entry_volume = float(quote.get('volume', 0) or 0)
                    except Exception as e:
                        logger.warning(f"Failed to get entry volume: {e}")
                        entry_volume = 0

                    # Calculate wide bracket stops (5% stop, 10% target)
                    # These are BACKUP only - AI monitor should exit before these
                    wide_stop = fill_price * 0.95 if not stop_price else stop_price
                    wide_target = fill_price * 1.10 if not target_price else target_price

                    # Start monitoring (this will run until position exit)
                    try:
                        monitor_result = asyncio.get_event_loop().run_until_complete(
                            start_position_monitor(
                                broker=self.broker,
                                market_data=self.market,
                                anthropic_client=self.agent.client,
                                safety_validator=self.safety,
                                symbol=symbol,
                                entry_price=fill_price,
                                quantity=quantity,
                                entry_volume=entry_volume,
                                entry_reason=reasoning,
                                stop_price=wide_stop,
                                target_price=wide_target,
                            )
                        )
                        logger.info(f"Position monitor completed: {monitor_result}")

                    except Exception as e:
                        logger.error(f"Position monitor failed: {e}", exc_info=True)
                        monitor_error = str(e)
                        # Trade still succeeded, just monitoring failed
                        # Wide bracket orders are in place as backup
                # ==============================================================
                # END NEW CODE
                # ==============================================================

                return {
                    "status": "success",
                    "order_id": result.get("order_id"),
                    "fill_price": fill_price,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "timestamp": datetime.now(HK_TZ).isoformat(),
                    # NEW: Include monitoring results
                    "monitor_result": monitor_result,
                    "monitor_error": monitor_error,
                }
            else:
                return {
                    "status": "failed",
                    "reason": result.get("message", "Order rejected"),
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                }

        except Exception as e:
            logger.error(f"Trade execution error: {e}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }

    def _close_position(self, inputs: dict) -> dict:
        """Close a specific position."""
        symbol = inputs["symbol"]
        reason = inputs.get("reason", "Manual close")

        logger.info(f"Closing position: {symbol} - {reason}")

        try:
            # Get current position
            portfolio = self.broker.get_portfolio()
            position = None

            for pos in portfolio.get("positions", []):
                pos_symbol = pos.get("symbol", "").replace(".HK", "")
                if pos_symbol == symbol or pos_symbol == symbol.replace(".HK", ""):
                    position = pos
                    break

            if not position:
                return {
                    "status": "error",
                    "reason": f"No position found for {symbol}",
                }

            quantity = abs(int(position.get("quantity", 0)))

            # Place market sell
            result = self.broker.place_order(
                symbol=symbol,
                side="SELL",
                quantity=quantity,
                order_type="MARKET",
            )

            if result.get("status") in ["filled", "FILLED", "submitted", "SUBMITTED"]:
                self.trades_executed += 1
                return {
                    "status": "success",
                    "symbol": symbol,
                    "quantity": quantity,
                    "reason": reason,
                    "order_id": result.get("order_id"),
                    "timestamp": datetime.now(HK_TZ).isoformat(),
                }
            else:
                return {
                    "status": "failed",
                    "reason": result.get("message", "Close order rejected"),
                }

        except Exception as e:
            logger.error(f"Close position error: {e}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e),
            }

    def _close_all(self, inputs: dict) -> dict:
        """Close all positions (emergency)."""
        reason = inputs.get("reason", "Emergency close all")

        logger.warning(f"CLOSING ALL POSITIONS: {reason}")

        # Send alert
        if self.alert_callback:
            self.alert_callback(
                "critical",
                "Emergency Close All",
                f"Closing all positions: {reason}",
            )

        try:
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
                symbol = pos.get("symbol", "").replace(".HK", "")
                quantity = abs(int(pos.get("quantity", 0)))

                if quantity > 0:
                    try:
                        result = self.broker.place_order(
                            symbol=symbol,
                            side="SELL",
                            quantity=quantity,
                            order_type="MARKET",
                        )

                        if result.get("status") in ["filled", "FILLED", "submitted", "SUBMITTED"]:
                            closed.append(symbol)
                            self.trades_executed += 1
                        else:
                            failed.append(f"{symbol}: {result.get('message')}")

                    except Exception as e:
                        failed.append(f"{symbol}: {str(e)}")

            return {
                "status": "success" if not failed else "partial",
                "closed_count": len(closed),
                "closed_symbols": closed,
                "failed_count": len(failed),
                "failed_details": failed,
                "reason": reason,
                "timestamp": datetime.now(HK_TZ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Close all error: {e}", exc_info=True)
            return {
                "status": "error",
                "reason": str(e),
            }

    # =========================================================================
    # Utility Tools
    # =========================================================================

    def _send_alert(self, inputs: dict) -> dict:
        """Send an alert notification."""
        severity = inputs.get("severity", "info")
        subject = inputs["subject"]
        message = inputs["message"]

        if self.alert_callback:
            self.alert_callback(severity, subject, message)
            logger.info(f"Alert sent: [{severity}] {subject}")
            return {
                "sent": True,
                "severity": severity,
                "subject": subject,
            }
        else:
            logger.warning("No alert callback configured")
            return {
                "sent": False,
                "reason": "No alert callback configured",
            }

    def _log_decision(self, inputs: dict) -> dict:
        """Log a trading decision with reasoning."""
        decision_type = inputs["decision"]
        symbol = inputs.get("symbol")
        reasoning = inputs["reasoning"]

        # Log to database
        try:
            decision_id = self.db.log_decision(
                cycle_id=self.cycle_id,
                decision_type=decision_type,
                reasoning=reasoning,
                symbol=symbol,
                tools_called=[t["tool"] for t in self.tools_called],
            )

            return {
                "logged": True,
                "decision_id": decision_id,
                "decision_type": decision_type,
                "symbol": symbol,
                "timestamp": datetime.now(HK_TZ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
            return {
                "logged": False,
                "error": str(e),
            }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_summary(self) -> dict:
        """Get execution summary for this cycle."""
        return {
            "cycle_id": self.cycle_id,
            "tools_called": len(self.tools_called),
            "trades_executed": self.trades_executed,
            "tool_history": self.tools_called,
        }


def create_tool_executor(
    cycle_id: str,
    alert_callback: Any = None,
    agent: Any = None,
) -> ToolExecutor:
    """Create a new tool executor for a cycle."""
    return ToolExecutor(
        cycle_id=cycle_id,
        alert_callback=alert_callback,
        agent=agent,
    )
