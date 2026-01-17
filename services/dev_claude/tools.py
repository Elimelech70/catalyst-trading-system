#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: tools.py
Version: 1.0.0
Last Updated: 2026-01-17
Purpose: Trading tool definitions for Claude AI agent (US markets)

REVISION HISTORY:
v1.0.0 (2026-01-17) - Initial implementation
  - Aligned with intl_claude tools.py
  - 12 trading tools for US markets
  - JSON schema definitions for Claude
  - Input validation helpers

Description:
This module defines the trading tools available to Claude during trading
cycles. Tools are defined using Anthropic's tool-use JSON schema format.
"""

from typing import Dict, Any, List

# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS: List[Dict[str, Any]] = [
    # =========================================================================
    # MARKET DATA TOOLS
    # =========================================================================
    {
        "name": "scan_market",
        "description": """Scan for trading candidates with momentum and volume.
Returns top stocks showing unusual activity based on filters.
Use this first to find potential opportunities.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_price": {
                    "type": "number",
                    "description": "Minimum stock price filter",
                    "default": 5.0
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum stock price filter",
                    "default": 500.0
                },
                "min_volume_ratio": {
                    "type": "number",
                    "description": "Minimum volume vs 20-day average (e.g., 1.5 = 150%)",
                    "default": 1.3
                },
                "min_change_pct": {
                    "type": "number",
                    "description": "Minimum price change percentage",
                    "default": 1.0
                },
                "max_change_pct": {
                    "type": "number",
                    "description": "Maximum price change percentage (avoid overextended)",
                    "default": 15.0
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top candidates to return",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "get_quote",
        "description": """Get real-time quote for a stock symbol.
Returns last price, bid/ask, volume, and intraday OHLC.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (e.g., 'AAPL', 'TSLA')"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_portfolio",
        "description": """Get current account portfolio status.
Returns cash balance, equity, buying power, open positions, and P&L.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_technicals",
        "description": """Get technical indicators for a symbol.
Returns RSI, MACD, moving averages, VWAP, volume ratio, and trend assessment.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "period": {
                    "type": "string",
                    "description": "Analysis period: 'intraday', 'daily', 'weekly'",
                    "default": "intraday"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "detect_patterns",
        "description": """Detect chart patterns for a symbol.
Identifies consolidation, breakout, ABCD, bull/bear flags, etc.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "timeframe": {
                    "type": "string",
                    "description": "Chart timeframe: '1min', '5min', '15min', '1h', '1d'",
                    "default": "5min"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_news",
        "description": """Get recent news and sentiment for a symbol.
Returns headlines, sentiment score, and catalyst identification.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "hours": {
                    "type": "integer",
                    "description": "How many hours back to search",
                    "default": 24
                }
            },
            "required": ["symbol"]
        }
    },
    
    # =========================================================================
    # RISK & EXECUTION TOOLS
    # =========================================================================
    {
        "name": "check_risk",
        "description": """Check risk parameters before executing a trade.
Validates against position limits, buying power, and risk rules.
ALWAYS call this before execute_trade.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares"
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Order side"
                },
                "entry_price": {
                    "type": "number",
                    "description": "Expected entry price"
                },
                "stop_loss": {
                    "type": "number",
                    "description": "Stop loss price"
                },
                "take_profit": {
                    "type": "number",
                    "description": "Take profit price"
                }
            },
            "required": ["symbol", "quantity", "side"]
        }
    },
    {
        "name": "execute_trade",
        "description": """Execute a trade order.
Submits order to Alpaca with optional bracket orders (stop loss + take profit).
Only call after check_risk returns approved=true.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Order side"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares"
                },
                "order_type": {
                    "type": "string",
                    "enum": ["market", "limit"],
                    "description": "Order type",
                    "default": "market"
                },
                "limit_price": {
                    "type": "number",
                    "description": "Limit price (required for limit orders)"
                },
                "stop_loss": {
                    "type": "number",
                    "description": "Stop loss price (creates bracket order)"
                },
                "take_profit": {
                    "type": "number",
                    "description": "Take profit price (creates bracket order)"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for trade (logged)"
                }
            },
            "required": ["symbol", "side", "quantity"]
        }
    },
    {
        "name": "close_position",
        "description": """Close an existing position.
Submits a market order to close the entire position.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol to close"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for closing (logged)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "close_all_positions",
        "description": """EMERGENCY: Close all open positions immediately.
Use only in emergency situations or end-of-day liquidation.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for emergency close"
                }
            },
            "required": ["reason"]
        }
    },
    
    # =========================================================================
    # COMMUNICATION TOOLS
    # =========================================================================
    {
        "name": "send_alert",
        "description": """Send an alert message to big_bro or Craig.
Use for important updates, questions, or end-of-cycle summaries.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "enum": ["big_bro", "craig"],
                    "description": "Recipient",
                    "default": "big_bro"
                },
                "subject": {
                    "type": "string",
                    "description": "Alert subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Alert body content"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "critical"],
                    "description": "Alert urgency level",
                    "default": "normal"
                }
            },
            "required": ["subject", "body"]
        }
    },
    {
        "name": "log_decision",
        "description": """Log a trading decision with reasoning.
Use to document analysis, entry/exit decisions, and learning.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_type": {
                    "type": "string",
                    "enum": ["analysis", "entry", "exit", "skip", "hold", "learning"],
                    "description": "Type of decision"
                },
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (if applicable)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed reasoning for the decision"
                },
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Confidence level",
                    "default": "medium"
                },
                "tier": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": "Entry tier (1=highest conviction)"
                }
            },
            "required": ["decision_type", "reasoning"]
        }
    },
]


# =============================================================================
# TOOL NAME LIST
# =============================================================================

TOOL_NAMES = [tool["name"] for tool in TOOLS]


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_tool_input(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Validate tool input against schema.
    
    Args:
        tool_name: Name of tool
        tool_input: Input parameters
        
    Returns:
        Dict with 'valid' bool and optional 'errors' list
    """
    # Find tool definition
    tool_def = None
    for tool in TOOLS:
        if tool["name"] == tool_name:
            tool_def = tool
            break
    
    if not tool_def:
        return {"valid": False, "errors": [f"Unknown tool: {tool_name}"]}
    
    schema = tool_def.get("input_schema", {})
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    errors = []
    
    # Check required fields
    for field in required:
        if field not in tool_input or tool_input[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Check field types (basic validation)
    for field, value in tool_input.items():
        if field in properties:
            expected_type = properties[field].get("type")
            enum_values = properties[field].get("enum")
            
            # Check enum
            if enum_values and value not in enum_values:
                errors.append(f"Invalid value for {field}: {value}. Must be one of: {enum_values}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors if errors else None
    }


# =============================================================================
# TOOL HELPERS
# =============================================================================

def get_tool_by_name(name: str) -> Dict[str, Any]:
    """Get tool definition by name.
    
    Args:
        name: Tool name
        
    Returns:
        Tool definition dict or None
    """
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tools_for_mode(mode: str) -> List[Dict[str, Any]]:
    """Get relevant tools for a trading mode.
    
    Args:
        mode: Trading mode ('scan', 'trade', 'close', 'heartbeat')
        
    Returns:
        List of relevant tool definitions
    """
    if mode == "scan":
        # Limited tools for scanning
        return [t for t in TOOLS if t["name"] in [
            "scan_market", "get_quote", "get_technicals", 
            "get_portfolio", "log_decision"
        ]]
    elif mode == "close":
        # Tools for closing positions
        return [t for t in TOOLS if t["name"] in [
            "get_portfolio", "get_quote", "close_position",
            "close_all_positions", "send_alert", "log_decision"
        ]]
    elif mode == "heartbeat":
        # Minimal tools for heartbeat
        return [t for t in TOOLS if t["name"] in [
            "get_portfolio", "send_alert", "log_decision"
        ]]
    else:
        # Full tools for trading
        return TOOLS
