"""
Tool definitions for the Catalyst Trading Agent.

These are the tools that Claude can use to interact with the trading system.
Each tool has a name, description, and input schema that Claude uses to
understand how to call the tool.
"""

TOOLS = [
    {
        "name": "scan_market",
        "description": """Scan HKEX for trading candidates.

Returns top stocks by momentum and volume from the specified index.
Results include symbol, name, price, volume, change%, and relative volume.
Use this at the start of each cycle to find potential opportunities.

Note: Position size limit (HKD 10K) is enforced at trade execution, not here.
You can buy as few as 10 shares, so most stocks are tradeable.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "string",
                    "enum": ["HSI", "HSCEI", "HSTECH", "ALL"],
                    "description": "Index to scan. HSI=Hang Seng, HSCEI=China Enterprises, HSTECH=Tech Index, ALL=All indices"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of candidates to return (default 10, max 20)"
                },
                "min_volume_ratio": {
                    "type": "number",
                    "description": "Minimum volume ratio vs average (default 1.5)"
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum stock price in HKD (default 1000). Most stocks tradeable with 10+ share minimum."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_quote",
        "description": """Get current price and volume for a symbol.

Returns: symbol, name, price, bid, ask, volume, avg_volume, volume_ratio,
change, change_pct, day_high, day_low, open, prev_close, market_cap, lot_size.
Use this to check current price before analyzing a stock.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code (e.g., '0700' for Tencent, '9988' for Alibaba)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_technicals",
        "description": """Get technical indicators for a symbol.

Returns RSI, MACD (value, signal, histogram), moving averages (SMA9, SMA20,
SMA50, SMA200, EMA9, EMA21), ATR, Bollinger Bands, and support/resistance levels.
Use this to assess the technical setup before entering a trade.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code (e.g., '0700')"
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["5m", "15m", "1h", "1d"],
                    "description": "Timeframe for analysis (default '15m')"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "detect_patterns",
        "description": """Detect chart patterns for a symbol.

Scans for: bull_flag, bear_flag, cup_handle, ascending_triangle,
descending_triangle, ABCD, breakout, breakdown.

Returns list of detected patterns with confidence score (0-1),
pattern type, entry price, stop loss, and target price.
Use this to confirm a setup before entering.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code (e.g., '0700')"
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["5m", "15m", "1h", "1d"],
                    "description": "Timeframe for pattern detection (default '15m')"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_news",
        "description": """Get recent news and sentiment for a symbol.

Returns list of news items with headline, source, timestamp, url, and
sentiment score (-1 to 1). Also returns overall_sentiment average.
Use this to check for catalysts before entering a trade.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code (e.g., '0700')"
                },
                "hours": {
                    "type": "integer",
                    "description": "Hours to look back for news (default 24, max 72)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "check_risk",
        "description": """Validate trade against risk limits. MUST call before execute_trade.

Checks:
- Position size limits (max 20% of portfolio)
- Number of positions (max 5)
- Daily loss limit (2%)
- Stop loss percentage (max 5%)
- Risk/reward ratio (min 2:1)

Returns approved (bool), reason, position_value, portfolio_pct, risk_amount.
If approved=false, DO NOT proceed with the trade.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code"
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Trade direction"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares (must be multiple of lot size 100)"
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
            "required": ["symbol", "side", "quantity", "entry_price", "stop_loss", "take_profit"]
        }
    },
    {
        "name": "get_portfolio",
        "description": """Get current portfolio status.

Returns:
- cash: Available cash in HKD
- equity: Total portfolio value
- positions: List of current positions with symbol, quantity, avg_cost,
  current_price, unrealized_pnl, unrealized_pnl_pct
- daily_pnl: Today's realized + unrealized P&L
- daily_pnl_pct: Today's P&L as percentage
- position_count: Number of open positions
- max_positions: Maximum allowed positions from config

Use position_count and max_positions to determine if you can open more positions.
Use this to check available capital and monitor positions.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "execute_trade",
        "description": """Execute trade via broker. Only call after check_risk approves.

Submits order to broker with stop loss and take profit levels
and take profit. Returns order_id, status, filled_price, filled_quantity.

IMPORTANT: Always call check_risk first. Include a clear reason for audit.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code"
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Trade direction"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares (must be multiple of 100)"
                },
                "order_type": {
                    "type": "string",
                    "enum": ["market", "limit"],
                    "description": "Order type"
                },
                "limit_price": {
                    "type": "number",
                    "description": "Limit price (required if order_type is 'limit')"
                },
                "stop_loss": {
                    "type": "number",
                    "description": "Stop loss price"
                },
                "take_profit": {
                    "type": "number",
                    "description": "Take profit price"
                },
                "reason": {
                    "type": "string",
                    "description": "Why this trade? (for audit trail)"
                }
            },
            "required": ["symbol", "side", "quantity", "order_type", "stop_loss", "take_profit", "reason"]
        }
    },
    {
        "name": "close_position",
        "description": """Close an existing position.

Submits market order to close the entire position for the given symbol.
Returns order_id, status, filled_price, realized_pnl.

Use this for planned exits or when stop/target is reached.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock code to close"
                },
                "reason": {
                    "type": "string",
                    "description": "Why closing? (for audit trail)"
                }
            },
            "required": ["symbol", "reason"]
        }
    },
    {
        "name": "close_all",
        "description": """EMERGENCY: Close all positions immediately.

Use when:
- Daily loss limit (2%) is breached
- Market emergency/crash
- End of day position cleanup
- System issues detected

Returns list of closed positions with realized P&L.
Also sends critical alert to operator.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why emergency close? (for audit trail)"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "name": "send_alert",
        "description": """Send email alert to operator.

Use for:
- info: Trade executed, position closed, session summary
- warning: Approaching loss limit, unusual market conditions
- critical: Emergency close triggered, system errors

Alerts are queued and sent immediately.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "critical"],
                    "description": "Alert severity level"
                },
                "subject": {
                    "type": "string",
                    "description": "Alert subject line"
                },
                "message": {
                    "type": "string",
                    "description": "Alert body with details"
                }
            },
            "required": ["severity", "subject", "message"]
        }
    },
    {
        "name": "log_decision",
        "description": """Log decision to database for audit trail.

Record every significant decision:
- trade: Entered a position (include symbol)
- skip: Decided not to trade an opportunity (include symbol)
- close: Exited a position (include symbol)
- emergency: Emergency action taken
- observation: Market observation or note

This creates a complete audit trail for review and strategy improvement.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["trade", "skip", "close", "emergency", "observation"],
                    "description": "Type of decision"
                },
                "symbol": {
                    "type": "string",
                    "description": "Related symbol (if applicable)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed reasoning for the decision"
                }
            },
            "required": ["decision", "reasoning"]
        }
    }
]


def get_tool_by_name(name: str) -> dict | None:
    """Get a tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tool_names() -> list[str]:
    """Get list of all tool names."""
    return [tool["name"] for tool in TOOLS]


def validate_tool_input(tool_name: str, inputs: dict) -> tuple[bool, str]:
    """Validate tool inputs against schema.

    Returns (is_valid, error_message)
    """
    tool = get_tool_by_name(tool_name)
    if not tool:
        return False, f"Unknown tool: {tool_name}"

    schema = tool["input_schema"]
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # Check required fields
    for field in required:
        if field not in inputs:
            return False, f"Missing required field: {field}"

    # Check field types
    for field, value in inputs.items():
        if field not in properties:
            continue  # Allow extra fields

        prop = properties[field]
        expected_type = prop.get("type")

        if expected_type == "string" and not isinstance(value, str):
            return False, f"Field {field} must be a string"
        elif expected_type == "integer" and not isinstance(value, int):
            return False, f"Field {field} must be an integer"
        elif expected_type == "number" and not isinstance(value, (int, float)):
            return False, f"Field {field} must be a number"

        # Check enum values
        if "enum" in prop and value not in prop["enum"]:
            return False, f"Field {field} must be one of: {prop['enum']}"

    return True, ""
