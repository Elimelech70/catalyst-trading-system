#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: tool_executor.py
Version: 1.0.0
Last Updated: 2026-01-17
Purpose: Routes Claude's tool calls to actual implementations for US markets

REVISION HISTORY:
v1.0.0 (2026-01-17) - Initial implementation
  - Aligned with intl_claude tool_executor.py v2.6.0 pattern
  - 12 trading tools for US markets
  - Alpaca broker integration
  - Order vs Position separation
  - Position monitoring via systemd service (not inline)

Description:
This module receives tool calls from Claude and routes them to the
appropriate implementation functions. It handles all 12 trading tools
defined in the TOOLS list.

Position monitoring is handled by position_monitor_service.py (systemd)
- No inline monitor calls after trades
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from zoneinfo import ZoneInfo

# Timezone
try:
    import pytz
    ET = pytz.timezone('America/New_York')
except ImportError:
    ET = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tool calls from Claude."""
    
    def __init__(
        self,
        cycle_id: str,
        broker: Any = None,
        db: Any = None,
        alert_callback: Callable = None,
        agent: Any = None,
        config: Dict[str, Any] = None,
    ):
        """Initialize tool executor.
        
        Args:
            cycle_id: Current trading cycle ID
            broker: AlpacaClient instance
            db: Database connection
            alert_callback: Function to send alerts
            agent: Reference to UnifiedAgent (for position monitor)
            config: Configuration dict
        """
        self.cycle_id = cycle_id
        self.broker = broker
        self.db = db
        self.alert_callback = alert_callback
        self.agent = agent
        self.config = config or {}
        
        self.tools_called: list[dict] = []
        self.trades_executed = 0
        
        logger.info(f"ToolExecutor initialized for cycle {cycle_id}")
    
    def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result.
        
        Args:
            tool_name: Name of tool to execute
            tool_input: Input parameters for tool
            
        Returns:
            Tool execution result
        """
        self.tools_called.append({
            "tool": tool_name,
            "input": tool_input,
            "timestamp": datetime.now(ET).isoformat(),
        })
        
        try:
            # Route to appropriate handler
            if tool_name == "scan_market":
                return self._scan_market(tool_input)
            elif tool_name == "get_quote":
                return self._get_quote(tool_input)
            elif tool_name == "get_portfolio":
                return self._get_portfolio(tool_input)
            elif tool_name == "get_technicals":
                return self._get_technicals(tool_input)
            elif tool_name == "detect_patterns":
                return self._detect_patterns(tool_input)
            elif tool_name == "get_news":
                return self._get_news(tool_input)
            elif tool_name == "check_risk":
                return self._check_risk(tool_input)
            elif tool_name == "execute_trade":
                return self._execute_trade(tool_input)
            elif tool_name == "close_position":
                return self._close_position(tool_input)
            elif tool_name == "close_all_positions":
                return self._close_all_positions(tool_input)
            elif tool_name == "send_alert":
                return self._send_alert(tool_input)
            elif tool_name == "log_decision":
                return self._log_decision(tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return {"error": str(e)}
    
    # =========================================================================
    # MARKET DATA TOOLS
    # =========================================================================
    
    def _scan_market(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scan for trading candidates."""
        if not self.broker:
            return {"error": "Broker not connected", "candidates": []}
        
        min_price = params.get("min_price", 5.0)
        max_price = params.get("max_price", 500.0)
        min_volume_ratio = params.get("min_volume_ratio", 1.3)
        min_change_pct = params.get("min_change_pct", 1.0)
        max_change_pct = params.get("max_change_pct", 15.0)
        top_n = params.get("top_n", 20)
        
        # For US markets, we need to get active stocks from a data source
        # This is a simplified implementation - in production you'd use
        # a screening API or pre-built universe
        
        try:
            # Get a list of active symbols to scan
            # In production, this would come from a scanner API
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import GetAssetsRequest
            from alpaca.trading.enums import AssetClass, AssetStatus
            
            # Get tradeable assets
            request = GetAssetsRequest(
                asset_class=AssetClass.US_EQUITY,
                status=AssetStatus.ACTIVE,
            )
            assets = self.broker.trading_client.get_all_assets(request)
            
            # Filter to tradeable, fractionable stocks
            symbols = [
                a.symbol for a in assets[:200]  # Limit for API rate
                if a.tradable and a.easy_to_borrow
            ]
            
            # Get quotes for top movers
            # This is simplified - real scanner would use market data feed
            candidates = []
            
            # Batch quotes to avoid rate limiting
            batch_size = 50
            for i in range(0, min(len(symbols), 100), batch_size):
                batch = symbols[i:i+batch_size]
                try:
                    quotes = self.broker.get_quotes_batch(batch)
                    for q in quotes:
                        if q.get("last"):
                            price = q["last"]
                            if min_price <= price <= max_price:
                                candidates.append({
                                    "symbol": q["symbol"],
                                    "price": price,
                                    "bid": q.get("bid"),
                                    "ask": q.get("ask"),
                                })
                except Exception as e:
                    logger.warning(f"Batch quote failed: {e}")
            
            # Sort by some metric (in production, use change %)
            candidates = candidates[:top_n]
            
            return {
                "candidates": candidates,
                "count": len(candidates),
                "scan_time": datetime.now(ET).isoformat(),
                "filters": {
                    "min_price": min_price,
                    "max_price": max_price,
                    "min_volume_ratio": min_volume_ratio,
                }
            }
            
        except Exception as e:
            logger.error(f"Market scan failed: {e}")
            return {"error": str(e), "candidates": []}
    
    def _get_quote(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get real-time quote for a symbol."""
        symbol = params.get("symbol")
        if not symbol:
            return {"error": "Symbol required"}
        
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            quote = self.broker.get_quote(symbol)
            return quote
        except Exception as e:
            logger.error(f"Quote failed for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    def _get_portfolio(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get account portfolio."""
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            portfolio = self.broker.get_portfolio()
            return portfolio
        except Exception as e:
            logger.error(f"Portfolio failed: {e}")
            return {"error": str(e)}
    
    def _get_technicals(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get technical indicators for a symbol."""
        symbol = params.get("symbol")
        if not symbol:
            return {"error": "Symbol required"}
        
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            # Get historical data
            bars = self.broker.get_historical_data(symbol, timeframe="1D", limit=50)
            
            if not bars:
                return {"error": f"No historical data for {symbol}"}
            
            # Calculate basic technicals
            closes = [b["close"] for b in bars]
            highs = [b["high"] for b in bars]
            lows = [b["low"] for b in bars]
            volumes = [b["volume"] for b in bars]
            
            # Simple calculations (in production, use ta-lib)
            current = closes[-1] if closes else 0
            
            # SMA
            sma_20 = sum(closes[-20:]) / min(20, len(closes)) if closes else 0
            sma_50 = sum(closes[-50:]) / min(50, len(closes)) if closes else 0
            
            # RSI (simplified)
            gains = []
            losses = []
            for i in range(1, min(15, len(closes))):
                diff = closes[i] - closes[i-1]
                if diff > 0:
                    gains.append(diff)
                else:
                    losses.append(abs(diff))
            avg_gain = sum(gains) / 14 if gains else 0
            avg_loss = sum(losses) / 14 if losses else 0.001
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # VWAP (simplified - today's)
            if bars:
                last_bar = bars[-1]
                vwap = last_bar.get("vwap", current)
            else:
                vwap = current
            
            # Volume ratio
            avg_volume = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else 1
            current_volume = volumes[-1] if volumes else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            return {
                "symbol": symbol,
                "current_price": current,
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "rsi": round(rsi, 1),
                "vwap": round(vwap, 2),
                "volume_ratio": round(volume_ratio, 2),
                "above_vwap": current > vwap,
                "above_sma_20": current > sma_20,
                "trend": "bullish" if current > sma_20 > sma_50 else "bearish" if current < sma_20 < sma_50 else "neutral",
            }
            
        except Exception as e:
            logger.error(f"Technicals failed for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    def _detect_patterns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detect chart patterns for a symbol."""
        symbol = params.get("symbol")
        if not symbol:
            return {"error": "Symbol required"}
        
        # Simplified pattern detection
        # In production, use proper pattern recognition library
        return {
            "symbol": symbol,
            "patterns": [],
            "message": "Pattern detection not fully implemented for US markets",
        }
    
    def _get_news(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get news for a symbol."""
        symbol = params.get("symbol")
        if not symbol:
            return {"error": "Symbol required"}
        
        # Simplified news - in production, use news API
        return {
            "symbol": symbol,
            "news": [],
            "message": "News integration not fully implemented",
        }
    
    # =========================================================================
    # RISK & EXECUTION TOOLS
    # =========================================================================
    
    def _check_risk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check risk before trade execution."""
        symbol = params.get("symbol")
        quantity = params.get("quantity", 0)
        side = params.get("side", "buy")
        entry_price = params.get("entry_price", 0)
        stop_loss = params.get("stop_loss")
        
        if not symbol:
            return {"error": "Symbol required"}
        
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            portfolio = self.broker.get_portfolio()
            buying_power = portfolio.get("buying_power", 0)
            position_count = portfolio.get("position_count", 0)
            
            # Calculate trade value
            trade_value = quantity * entry_price if entry_price else 0
            
            # Risk checks
            max_positions = self.config.get("trading", {}).get("max_positions", 8)
            max_position_value = self.config.get("trading", {}).get("max_position_value_usd", 5000)
            
            approved = True
            warnings = []
            errors = []
            
            # Check buying power
            if trade_value > buying_power:
                approved = False
                errors.append(f"Insufficient buying power: ${buying_power:,.2f} < ${trade_value:,.2f}")
            
            # Check position count
            if position_count >= max_positions:
                approved = False
                errors.append(f"Max positions reached: {position_count}/{max_positions}")
            
            # Check position size
            if trade_value > max_position_value:
                warnings.append(f"Position exceeds max: ${trade_value:,.2f} > ${max_position_value:,.2f}")
            
            # Check stop loss
            if not stop_loss:
                warnings.append("No stop loss specified")
            elif entry_price and stop_loss:
                risk_pct = abs(entry_price - stop_loss) / entry_price * 100
                if risk_pct > 5:
                    warnings.append(f"Stop loss risk high: {risk_pct:.1f}%")
            
            return {
                "approved": approved,
                "symbol": symbol,
                "quantity": quantity,
                "trade_value": trade_value,
                "buying_power": buying_power,
                "position_count": position_count,
                "max_positions": max_positions,
                "warnings": warnings,
                "errors": errors,
            }
            
        except Exception as e:
            logger.error(f"Risk check failed: {e}")
            return {"error": str(e), "approved": False}
    
    def _execute_trade(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade."""
        symbol = params.get("symbol")
        side = params.get("side", "buy")
        quantity = params.get("quantity", 0)
        order_type = params.get("order_type", "market")
        limit_price = params.get("limit_price")
        stop_loss = params.get("stop_loss")
        take_profit = params.get("take_profit")
        reason = params.get("reason", "")
        
        if not symbol:
            return {"error": "Symbol required"}
        if not quantity or quantity <= 0:
            return {"error": "Quantity must be positive"}
        
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            result = self.broker.execute_trade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=reason,
            )
            
            # Check if filled
            filled_statuses = ["filled", "partially_filled"]
            submitted_statuses = ["submitted", "accepted", "pending_new", "new"]
            
            if result.status.lower() in filled_statuses:
                self.trades_executed += 1
                
                # Record to database if available
                if self.db and hasattr(self.db, 'record_trade'):
                    try:
                        self.db.record_trade({
                            "cycle_id": self.cycle_id,
                            "symbol": symbol,
                            "side": side,
                            "quantity": result.filled_quantity,
                            "price": result.filled_price,
                            "order_id": result.order_id,
                            "reason": reason,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to record trade: {e}")
                
                logger.info(f"Trade FILLED: {side} {result.filled_quantity} {symbol} @ {result.filled_price}")
                
            elif result.status.lower() in submitted_statuses:
                logger.info(f"Trade SUBMITTED (not yet filled): {side} {quantity} {symbol}")
                
            else:
                logger.warning(f"Trade status unknown: {result.status}")
            
            return {
                "order_id": result.order_id,
                "status": result.status,
                "symbol": result.symbol,
                "side": result.side,
                "quantity": result.quantity,
                "filled_quantity": result.filled_quantity,
                "filled_price": result.filled_price,
                "message": result.message,
            }
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {"error": str(e), "status": "error"}
    
    def _close_position(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Close a position."""
        symbol = params.get("symbol")
        reason = params.get("reason", "")
        
        if not symbol:
            return {"error": "Symbol required"}
        
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            result = self.broker.close_position(symbol, reason)
            
            if result.status.lower() in ["filled", "submitted", "accepted"]:
                self.trades_executed += 1
                logger.info(f"Position closed: {symbol} - {reason}")
            
            return {
                "order_id": result.order_id,
                "status": result.status,
                "symbol": result.symbol,
                "message": result.message,
            }
            
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return {"error": str(e)}
    
    def _close_all_positions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Emergency close all positions."""
        reason = params.get("reason", "Emergency close")
        
        if not self.broker:
            return {"error": "Broker not connected"}
        
        try:
            results = self.broker.close_all_positions(reason)
            
            return {
                "closed": len(results),
                "results": [
                    {"symbol": r.symbol, "status": r.status}
                    for r in results
                ],
                "reason": reason,
            }
            
        except Exception as e:
            logger.error(f"Close all failed: {e}")
            return {"error": str(e)}
    
    # =========================================================================
    # COMMUNICATION TOOLS
    # =========================================================================
    
    def _send_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an alert to big_bro or Craig."""
        to = params.get("to", "big_bro")
        subject = params.get("subject", "Alert")
        body = params.get("body", "")
        urgency = params.get("urgency", "normal")
        
        if self.alert_callback:
            try:
                self.alert_callback(to, subject, body, urgency)
                return {"sent": True, "to": to, "subject": subject}
            except Exception as e:
                logger.error(f"Alert send failed: {e}")
                return {"error": str(e), "sent": False}
        
        # Log if no callback
        logger.info(f"ALERT [{urgency}] to {to}: {subject}")
        return {"sent": True, "to": to, "subject": subject, "note": "Logged only"}
    
    def _log_decision(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Log a trading decision."""
        decision_type = params.get("decision_type", "analysis")
        symbol = params.get("symbol")
        reasoning = params.get("reasoning", "")
        confidence = params.get("confidence", "medium")
        tier = params.get("tier")
        
        log_entry = {
            "cycle_id": self.cycle_id,
            "timestamp": datetime.now(ET).isoformat(),
            "decision_type": decision_type,
            "symbol": symbol,
            "reasoning": reasoning,
            "confidence": confidence,
            "tier": tier,
        }
        
        logger.info(f"DECISION [{decision_type}] {symbol}: {reasoning[:100]}...")
        
        # Record to database if available
        if self.db and hasattr(self.db, 'log_decision'):
            try:
                self.db.log_decision(log_entry)
            except Exception as e:
                logger.warning(f"Failed to log decision: {e}")
        
        return {"logged": True, **log_entry}


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_tool_executor(
    cycle_id: str,
    broker: Any = None,
    db: Any = None,
    alert_callback: Callable = None,
    agent: Any = None,
    config: Dict[str, Any] = None,
) -> ToolExecutor:
    """Create a ToolExecutor instance.
    
    Args:
        cycle_id: Trading cycle ID
        broker: Broker client
        db: Database connection
        alert_callback: Alert sending function
        agent: Reference to agent
        config: Configuration dict
        
    Returns:
        Configured ToolExecutor
    """
    return ToolExecutor(
        cycle_id=cycle_id,
        broker=broker,
        db=db,
        alert_callback=alert_callback,
        agent=agent,
        config=config,
    )
