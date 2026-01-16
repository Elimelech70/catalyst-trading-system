# dev_claude US Unified Agent Implementation

**Name of Application:** Catalyst Trading System  
**Name of file:** dev_claude_us_implementation.md  
**Version:** 1.0.0  
**Last Updated:** 2026-01-14  
**Purpose:** Complete implementation package for dev_claude unified agent with Alpaca broker for US markets

---

## REVISION HISTORY

- **v1.0.0 (2026-01-14)** - Initial implementation
  - Unified agent architecture for US markets
  - Alpaca broker integration (paper trading)
  - 12 trading tools adapted from intl_claude
  - US market hours schedule (EST)
  - Consciousness integration

---

## 1. Executive Summary

This document provides the complete implementation for **dev_claude**, the US sandbox trading agent using the **unified agent architecture** (NOT microservices). This matches the proven pattern from intl_claude on HKEX.

### Architecture Comparison

| Component | Old (Microservices) | New (Unified Agent) |
|-----------|---------------------|---------------------|
| Code size | ~5,000+ lines across 10 services | ~1,200 lines single file |
| Decision making | Fixed workflow | Claude API dynamic |
| Broker | Alpaca via HTTP services | Alpaca SDK direct |
| Containers | 10 Docker containers | 1 Python process |
| Complexity | High | Low |

---

## 2. File Structure

```
/root/catalyst-dev/
├── unified_agent.py          # Main agent (v1.0.0) - THIS FILE
├── tool_executor.py          # Tool implementations
├── alpaca_client.py          # Alpaca broker wrapper
├── signals.py                # Exit signal detection
├── position_monitor.py       # Trade-triggered monitoring
├── startup_monitor.py        # Pre-market reconciliation
├── config/
│   └── dev_claude_config.yaml
├── venv/                     # Python virtual environment
├── logs/                     # Agent logs
└── .env                      # Environment variables
```

---

## 3. Environment Configuration

### .env File

```bash
# ============================================================================
# DEV_CLAUDE - US Sandbox Trading
# Version: 1.0.0
# ============================================================================

# Agent Identity
AGENT_ID=dev_claude

# Database URLs
DATABASE_URL=postgresql://doadmin:PASSWORD@db-host:25060/catalyst_dev?sslmode=require
RESEARCH_DATABASE_URL=postgresql://doadmin:PASSWORD@db-host:25060/catalyst_research?sslmode=require

# Claude API
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# Alpaca (US Broker) - Paper Trading
ALPACA_API_KEY=PKxxx
ALPACA_SECRET_KEY=xxx
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Trading Mode
PAPER_TRADING=true
TRADING_MODE=sandbox

# Logging
LOG_LEVEL=INFO
```

---

## 4. Agent Configuration

### config/dev_claude_config.yaml

```yaml
# ============================================================================
# dev_claude Configuration - US Sandbox Trading
# Version: 1.0.0
# ============================================================================

agent:
  id: dev_claude
  name: "Dev Claude"
  role: sandbox_trader
  market: US
  daily_budget: 5.00  # USD for Claude API

broker:
  name: alpaca
  mode: paper
  base_url: https://paper-api.alpaca.markets

trading:
  markets:
    - NYSE
    - NASDAQ
  currency: USD
  
  # Position limits
  max_positions: 8
  max_position_value: 5000  # USD per position
  min_position_value: 500   # USD minimum
  
  # Risk limits
  stop_loss_pct: 0.05       # 5% stop loss (sandbox = learning)
  take_profit_pct: 0.10     # 10% take profit
  daily_loss_limit: 2500    # USD max daily loss
  
  # Entry criteria (relaxed for learning)
  min_volume: 500000        # Minimum daily volume
  min_price: 5.00           # Minimum stock price
  max_price: 500.00         # Maximum stock price

signals:
  # Exit signal thresholds
  stop_loss_strong: -0.05
  stop_loss_moderate: -0.03
  take_profit_strong: 0.10
  take_profit_moderate: 0.06
  rsi_overbought_strong: 80
  rsi_overbought_moderate: 70

schedule:
  timezone: America/New_York
  pre_market: "08:00"       # Pre-market scan
  market_open: "09:30"
  market_close: "16:00"
  
autonomy:
  level: full               # Full autonomy for sandbox
  require_approval: false   # No approval needed
  experimental: true        # Can try new strategies
```

---

## 5. Main Agent Implementation

### unified_agent.py

```python
#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: unified_agent.py
Version: 1.0.0
Last Updated: 2026-01-14
Purpose: Unified trading agent for US markets (dev_claude)

REVISION HISTORY:
v1.0.0 (2026-01-14) - Initial implementation
  - Adapted from intl_claude HKEX agent
  - Alpaca broker integration
  - US market hours (EST)
  - 12 trading tools

Description:
Single-agent architecture where Claude API makes all trading decisions
dynamically using available tools. No fixed workflow - Claude decides
what to do based on market conditions and portfolio state.
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import anthropic
import asyncpg
from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Timezone
ET = timezone(timedelta(hours=-5))  # US Eastern (adjust for DST)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dev_claude')

# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load agent configuration from YAML file."""
    import yaml
    
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), 
            'config', 
            'dev_claude_config.yaml'
        )
    
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    # Default config if file not found
    return {
        'agent': {
            'id': 'dev_claude',
            'name': 'Dev Claude',
            'role': 'sandbox_trader',
            'market': 'US',
            'daily_budget': 5.00,
        },
        'trading': {
            'max_positions': 8,
            'max_position_value': 5000,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.10,
            'daily_loss_limit': 2500,
        },
        'signals': {
            'stop_loss_strong': -0.05,
            'stop_loss_moderate': -0.03,
            'take_profit_strong': 0.10,
            'take_profit_moderate': 0.06,
        }
    }


# ============================================================================
# DATABASE
# ============================================================================

class Database:
    """Database connection manager."""
    
    def __init__(self, trading_url: str, research_url: Optional[str] = None):
        self.trading_url = trading_url
        self.research_url = research_url
        self.pool: Optional[asyncpg.Pool] = None
        self.research_pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Connect to databases."""
        self.pool = await asyncpg.create_pool(self.trading_url, min_size=1, max_size=5)
        logger.info("Connected to trading database")
        
        if self.research_url:
            self.research_pool = await asyncpg.create_pool(
                self.research_url, min_size=1, max_size=3
            )
            logger.info("Connected to research database")
    
    async def close(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
        if self.research_pool:
            await self.research_pool.close()
        logger.info("Database connections closed")


# ============================================================================
# CONSCIOUSNESS CLIENT
# ============================================================================

class ConsciousnessClient:
    """Interface to consciousness framework."""
    
    def __init__(self, pool: asyncpg.Pool, agent_id: str):
        self.pool = pool
        self.agent_id = agent_id
    
    async def wake_up(self) -> Dict[str, Any]:
        """Wake up and check for messages."""
        async with self.pool.acquire() as conn:
            # Update state to active
            await conn.execute("""
                UPDATE claude_state SET
                    status = 'active',
                    last_active = NOW()
                WHERE agent_id = $1
            """, self.agent_id)
            
            # Get pending messages
            messages = await conn.fetch("""
                SELECT id, from_agent, subject, body, priority, created_at
                FROM claude_messages
                WHERE to_agent = $1 AND status = 'pending'
                ORDER BY 
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'normal' THEN 3 
                        ELSE 4 
                    END,
                    created_at ASC
                LIMIT 10
            """, self.agent_id)
            
            # Mark as read
            if messages:
                ids = [m['id'] for m in messages]
                await conn.execute("""
                    UPDATE claude_messages SET status = 'read' WHERE id = ANY($1)
                """, ids)
            
            # Get budget info
            state = await conn.fetchrow("""
                SELECT daily_budget, budget_used FROM claude_state WHERE agent_id = $1
            """, self.agent_id)
            
            return {
                'messages': [dict(m) for m in messages],
                'budget_remaining': float(state['daily_budget'] - state['budget_used']) if state else 5.0
            }
    
    async def send_message(
        self, 
        to_agent: str, 
        subject: str, 
        body: str, 
        priority: str = 'normal'
    ):
        """Send message to another agent."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_messages (from_agent, to_agent, subject, body, priority)
                VALUES ($1, $2, $3, $4, $5)
            """, self.agent_id, to_agent, subject, body, priority)
    
    async def observe(self, subject: str, content: str, confidence: float = 0.8):
        """Record an observation."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_observations (agent_id, subject, content, confidence)
                VALUES ($1, $2, $3, $4)
            """, self.agent_id, subject, content, confidence)
    
    async def learn(self, category: str, learning: str, confidence: float = 0.7):
        """Record a learning."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO claude_learnings (agent_id, category, learning, confidence)
                VALUES ($1, $2, $3, $4)
            """, self.agent_id, category, learning, confidence)
    
    async def update_budget(self, amount_spent: float):
        """Update budget usage."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    budget_used = budget_used + $2,
                    last_active = NOW()
                WHERE agent_id = $1
            """, self.agent_id, amount_spent)
    
    async def sleep(self):
        """Go to sleep state."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE claude_state SET
                    status = 'sleeping',
                    last_active = NOW()
                WHERE agent_id = $1
            """, self.agent_id)


# ============================================================================
# ALPACA CLIENT
# ============================================================================

class AlpacaClient:
    """Alpaca broker integration for US markets."""
    
    def __init__(self, paper_trading: bool = True):
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
        from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
        from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=paper_trading
        )
        
        self.data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        
        # Store imports for later use
        self._MarketOrderRequest = MarketOrderRequest
        self._OrderSide = OrderSide
        self._TimeInForce = TimeInForce
        self._StockLatestQuoteRequest = StockLatestQuoteRequest
        self._StockBarsRequest = StockBarsRequest
        self._TimeFrame = TimeFrame
        
        logger.info(f"Alpaca client initialized (paper={paper_trading})")
    
    def get_account(self) -> Dict[str, Any]:
        """Get account information."""
        account = self.trading_client.get_account()
        return {
            'cash': float(account.cash),
            'equity': float(account.equity),
            'buying_power': float(account.buying_power),
            'portfolio_value': float(account.portfolio_value),
            'day_trade_count': account.daytrade_count,
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        positions = self.trading_client.get_all_positions()
        return [
            {
                'symbol': p.symbol,
                'quantity': int(p.qty),
                'entry_price': float(p.avg_entry_price),
                'current_price': float(p.current_price),
                'market_value': float(p.market_value),
                'unrealized_pnl': float(p.unrealized_pl),
                'pnl_pct': float(p.unrealized_plpc) * 100,
                'side': 'long' if int(p.qty) > 0 else 'short',
            }
            for p in positions
        ]
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get current quote for a symbol."""
        request = self._StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self.data_client.get_stock_latest_quote(request)
        
        if symbol in quotes:
            q = quotes[symbol]
            return {
                'symbol': symbol,
                'bid': float(q.bid_price),
                'ask': float(q.ask_price),
                'bid_size': int(q.bid_size),
                'ask_size': int(q.ask_size),
                'mid': (float(q.bid_price) + float(q.ask_price)) / 2,
                'spread': float(q.ask_price) - float(q.bid_price),
                'timestamp': q.timestamp.isoformat(),
            }
        return {'error': f'No quote for {symbol}'}
    
    def get_bars(self, symbol: str, days: int = 20) -> List[Dict[str, Any]]:
        """Get historical bars for technical analysis."""
        from datetime import datetime, timedelta
        
        end = datetime.now()
        start = end - timedelta(days=days)
        
        request = self._StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=self._TimeFrame.Day,
            start=start,
            end=end
        )
        
        bars = self.data_client.get_stock_bars(request)
        
        if symbol in bars:
            return [
                {
                    'timestamp': bar.timestamp.isoformat(),
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                }
                for bar in bars[symbol]
            ]
        return []
    
    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = 'market',
        time_in_force: str = 'day'
    ) -> Dict[str, Any]:
        """Submit an order."""
        order_side = self._OrderSide.BUY if side.lower() in ['buy', 'long'] else self._OrderSide.SELL
        tif = self._TimeInForce.GTC if time_in_force.lower() == 'gtc' else self._TimeInForce.DAY
        
        request = self._MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=tif
        )
        
        order = self.trading_client.submit_order(request)
        
        return {
            'order_id': str(order.id),
            'symbol': order.symbol,
            'qty': int(order.qty),
            'side': order.side.value,
            'status': order.status.value,
            'submitted_at': order.submitted_at.isoformat() if order.submitted_at else None,
        }
    
    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close a position."""
        try:
            order = self.trading_client.close_position(symbol)
            return {
                'success': True,
                'order_id': str(order.id),
                'symbol': symbol,
                'status': order.status.value,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close_all_positions(self) -> Dict[str, Any]:
        """Close all positions."""
        try:
            self.trading_client.close_all_positions(cancel_orders=True)
            return {'success': True, 'message': 'All positions closed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

TOOLS = [
    {
        "name": "scan_market",
        "description": "Scan US market for trading candidates based on momentum and volume. Returns top stocks meeting criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum candidates to return (default 10, max 20)",
                    "default": 10
                },
                "min_volume": {
                    "type": "integer",
                    "description": "Minimum daily volume (default 500000)",
                    "default": 500000
                },
                "min_change_pct": {
                    "type": "number",
                    "description": "Minimum price change % to consider (default 2.0)",
                    "default": 2.0
                }
            },
            "required": []
        }
    },
    {
        "name": "get_quote",
        "description": "Get current bid/ask quote for a US stock symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (e.g., AAPL, TSLA)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_technicals",
        "description": "Get technical indicators for a symbol: RSI, MACD, moving averages, ATR.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "detect_patterns",
        "description": "Detect chart patterns: bull/bear flags, double top/bottom, breakouts, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_news",
        "description": "Get recent news headlines and sentiment for a symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of headlines (default 5)",
                    "default": 5
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_portfolio",
        "description": "Get current portfolio: cash, equity, positions, daily P&L.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "check_risk",
        "description": "Validate a potential trade against risk limits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "side": {
                    "type": "string",
                    "description": "Trade side: 'buy' or 'sell'",
                    "enum": ["buy", "sell"]
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares"
                },
                "price": {
                    "type": "number",
                    "description": "Expected entry price"
                }
            },
            "required": ["symbol", "side", "quantity", "price"]
        }
    },
    {
        "name": "execute_trade",
        "description": "Execute a trade. Submit market order to Alpaca.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "side": {
                    "type": "string",
                    "description": "Trade side: 'buy' or 'sell'",
                    "enum": ["buy", "sell"]
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of shares"
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason for the trade"
                }
            },
            "required": ["symbol", "side", "quantity", "reason"]
        }
    },
    {
        "name": "close_position",
        "description": "Close an existing position by symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol to close"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for closing"
                }
            },
            "required": ["symbol", "reason"]
        }
    },
    {
        "name": "close_all",
        "description": "Emergency close all positions. Use only when necessary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for closing all positions"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "name": "send_alert",
        "description": "Send alert message to big_bro or Craig.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient: 'big_bro' or 'craig'",
                    "enum": ["big_bro", "craig"]
                },
                "subject": {
                    "type": "string",
                    "description": "Alert subject"
                },
                "message": {
                    "type": "string",
                    "description": "Alert content"
                },
                "priority": {
                    "type": "string",
                    "description": "Priority level",
                    "enum": ["normal", "high", "urgent"],
                    "default": "normal"
                }
            },
            "required": ["to", "subject", "message"]
        }
    },
    {
        "name": "log_decision",
        "description": "Log a trading decision for audit trail and learning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_type": {
                    "type": "string",
                    "description": "Type: 'entry', 'exit', 'hold', 'skip'",
                    "enum": ["entry", "exit", "hold", "skip"]
                },
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed reasoning for the decision"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level 0.0-1.0",
                    "default": 0.7
                }
            },
            "required": ["decision_type", "symbol", "reasoning"]
        }
    }
]


# ============================================================================
# TOOL EXECUTOR
# ============================================================================

class ToolExecutor:
    """Execute trading tools."""
    
    def __init__(
        self,
        broker: AlpacaClient,
        db: Database,
        consciousness: Optional[ConsciousnessClient],
        config: Dict[str, Any]
    ):
        self.broker = broker
        self.db = db
        self.consciousness = consciousness
        self.config = config
        self.tools_called = []
        self.trades_executed = 0
    
    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result."""
        self.tools_called.append({
            'tool': tool_name,
            'input': tool_input,
            'timestamp': datetime.now(ET).isoformat()
        })
        
        try:
            # Route to handler
            handlers = {
                'scan_market': self._scan_market,
                'get_quote': self._get_quote,
                'get_technicals': self._get_technicals,
                'detect_patterns': self._detect_patterns,
                'get_news': self._get_news,
                'get_portfolio': self._get_portfolio,
                'check_risk': self._check_risk,
                'execute_trade': self._execute_trade,
                'close_position': self._close_position,
                'close_all': self._close_all,
                'send_alert': self._send_alert,
                'log_decision': self._log_decision,
            }
            
            handler = handlers.get(tool_name)
            if not handler:
                return {'error': f'Unknown tool: {tool_name}', 'success': False}
            
            result = await handler(tool_input)
            result['success'] = True
            return result
            
        except Exception as e:
            logger.error(f"Tool error {tool_name}: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    async def _scan_market(self, inputs: Dict) -> Dict:
        """Scan for trading candidates."""
        # This is a simplified scanner - enhance based on your needs
        # In production, you'd use Alpaca's screener or a separate data source
        
        limit = min(inputs.get('limit', 10), 20)
        min_volume = inputs.get('min_volume', 500000)
        
        # Get most active stocks from Alpaca
        # Note: Alpaca doesn't have a built-in screener, so this is simplified
        # You might want to use a separate data source like Polygon or Finnhub
        
        # For now, return a curated watchlist
        watchlist = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'META', 'GOOGL', 'AMZN', 'MSFT', 'SPY', 'QQQ']
        
        candidates = []
        for symbol in watchlist[:limit]:
            try:
                quote = self.broker.get_quote(symbol)
                if 'error' not in quote:
                    candidates.append({
                        'symbol': symbol,
                        'price': quote.get('mid', 0),
                        'bid': quote.get('bid', 0),
                        'ask': quote.get('ask', 0),
                    })
            except Exception as e:
                logger.warning(f"Error getting quote for {symbol}: {e}")
        
        return {
            'candidates_found': len(candidates),
            'candidates': candidates,
            'timestamp': datetime.now(ET).isoformat()
        }
    
    async def _get_quote(self, inputs: Dict) -> Dict:
        """Get quote for symbol."""
        symbol = inputs['symbol'].upper()
        return self.broker.get_quote(symbol)
    
    async def _get_technicals(self, inputs: Dict) -> Dict:
        """Calculate technical indicators."""
        symbol = inputs['symbol'].upper()
        bars = self.broker.get_bars(symbol, days=30)
        
        if not bars:
            return {'error': f'No data for {symbol}'}
        
        # Calculate simple indicators
        closes = [b['close'] for b in bars]
        
        # RSI (14-period)
        rsi = self._calculate_rsi(closes, 14)
        
        # Moving averages
        sma_10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
        sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        
        # Current price relative to MAs
        current = closes[-1] if closes else 0
        
        return {
            'symbol': symbol,
            'current_price': current,
            'rsi_14': round(rsi, 2) if rsi else None,
            'sma_10': round(sma_10, 2) if sma_10 else None,
            'sma_20': round(sma_20, 2) if sma_20 else None,
            'above_sma_10': current > sma_10 if sma_10 else None,
            'above_sma_20': current > sma_20 if sma_20 else None,
            'bars_count': len(bars),
        }
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    async def _detect_patterns(self, inputs: Dict) -> Dict:
        """Detect chart patterns."""
        symbol = inputs['symbol'].upper()
        bars = self.broker.get_bars(symbol, days=30)
        
        if len(bars) < 10:
            return {'symbol': symbol, 'patterns': [], 'error': 'Insufficient data'}
        
        patterns = []
        
        # Simple pattern detection - enhance as needed
        closes = [b['close'] for b in bars]
        highs = [b['high'] for b in bars]
        lows = [b['low'] for b in bars]
        
        # Check for breakout
        recent_high = max(highs[-20:-1]) if len(highs) > 20 else max(highs[:-1])
        if closes[-1] > recent_high:
            patterns.append({
                'type': 'breakout',
                'description': 'Breaking above recent highs',
                'confidence': 0.7
            })
        
        # Check for support bounce
        recent_low = min(lows[-20:-1]) if len(lows) > 20 else min(lows[:-1])
        if closes[-1] > lows[-1] and lows[-1] <= recent_low * 1.02:
            patterns.append({
                'type': 'support_bounce',
                'description': 'Bouncing off support level',
                'confidence': 0.6
            })
        
        return {
            'symbol': symbol,
            'patterns': patterns,
            'recent_high': round(recent_high, 2),
            'recent_low': round(recent_low, 2),
            'current': round(closes[-1], 2),
        }
    
    async def _get_news(self, inputs: Dict) -> Dict:
        """Get news for symbol."""
        symbol = inputs['symbol'].upper()
        limit = inputs.get('limit', 5)
        
        # Alpaca has news API - implement if needed
        # For now, return placeholder
        return {
            'symbol': symbol,
            'headlines': [],
            'sentiment': 'neutral',
            'note': 'News API not implemented - add Alpaca News or alternative'
        }
    
    async def _get_portfolio(self, inputs: Dict) -> Dict:
        """Get portfolio state."""
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        
        return {
            'account': account,
            'positions': positions,
            'position_count': len(positions),
            'timestamp': datetime.now(ET).isoformat()
        }
    
    async def _check_risk(self, inputs: Dict) -> Dict:
        """Validate trade against risk limits."""
        symbol = inputs['symbol'].upper()
        side = inputs['side']
        quantity = inputs['quantity']
        price = inputs['price']
        
        config = self.config.get('trading', {})
        
        position_value = quantity * price
        max_position = config.get('max_position_value', 5000)
        
        # Check position size
        if position_value > max_position:
            return {
                'approved': False,
                'reason': f'Position value ${position_value:.2f} exceeds max ${max_position}',
                'suggested_qty': int(max_position / price)
            }
        
        # Check position count
        positions = self.broker.get_positions()
        max_positions = config.get('max_positions', 8)
        
        if len(positions) >= max_positions and side == 'buy':
            return {
                'approved': False,
                'reason': f'Already at max positions ({max_positions})'
            }
        
        return {
            'approved': True,
            'position_value': round(position_value, 2),
            'current_positions': len(positions),
            'max_positions': max_positions
        }
    
    async def _execute_trade(self, inputs: Dict) -> Dict:
        """Execute a trade."""
        symbol = inputs['symbol'].upper()
        side = inputs['side']
        quantity = inputs['quantity']
        reason = inputs.get('reason', 'No reason provided')
        
        logger.info(f"Executing trade: {side} {quantity} {symbol} - {reason}")
        
        result = self.broker.submit_order(
            symbol=symbol,
            qty=quantity,
            side=side,
            order_type='market',
            time_in_force='day'
        )
        
        if 'error' not in result:
            self.trades_executed += 1
            
            # Log to database
            if self.db.pool:
                async with self.db.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO orders (symbol, side, quantity, order_type, status, broker_order_id, reason)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, symbol, side, quantity, 'market', result.get('status', 'submitted'), 
                    result.get('order_id'), reason)
        
        return result
    
    async def _close_position(self, inputs: Dict) -> Dict:
        """Close a position."""
        symbol = inputs['symbol'].upper()
        reason = inputs.get('reason', 'No reason provided')
        
        logger.info(f"Closing position: {symbol} - {reason}")
        
        result = self.broker.close_position(symbol)
        
        if result.get('success'):
            self.trades_executed += 1
        
        return result
    
    async def _close_all(self, inputs: Dict) -> Dict:
        """Close all positions."""
        reason = inputs.get('reason', 'Emergency close')
        
        logger.warning(f"CLOSING ALL POSITIONS: {reason}")
        
        result = self.broker.close_all_positions()
        
        # Alert big_bro
        if self.consciousness:
            await self.consciousness.send_message(
                to_agent='big_bro',
                subject='ALERT: All Positions Closed',
                body=f'dev_claude closed all positions.\nReason: {reason}',
                priority='urgent'
            )
        
        return result
    
    async def _send_alert(self, inputs: Dict) -> Dict:
        """Send alert message."""
        to = inputs['to']
        subject = inputs['subject']
        message = inputs['message']
        priority = inputs.get('priority', 'normal')
        
        if self.consciousness:
            await self.consciousness.send_message(
                to_agent=to,
                subject=subject,
                body=message,
                priority=priority
            )
            return {'sent': True, 'to': to, 'subject': subject}
        
        return {'sent': False, 'error': 'Consciousness not connected'}
    
    async def _log_decision(self, inputs: Dict) -> Dict:
        """Log trading decision."""
        decision_type = inputs['decision_type']
        symbol = inputs['symbol'].upper()
        reasoning = inputs['reasoning']
        confidence = inputs.get('confidence', 0.7)
        
        if self.db.pool:
            async with self.db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO decisions (symbol, decision_type, reasoning, confidence, agent_id)
                    VALUES ($1, $2, $3, $4, $5)
                """, symbol, decision_type, reasoning, confidence, 'dev_claude')
        
        return {
            'logged': True,
            'decision_type': decision_type,
            'symbol': symbol,
            'confidence': confidence
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            'tools_called': len(self.tools_called),
            'trades_executed': self.trades_executed,
            'tool_list': [t['tool'] for t in self.tools_called]
        }


# ============================================================================
# UNIFIED AGENT
# ============================================================================

class UnifiedAgent:
    """Unified trading agent for US markets."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        broker: AlpacaClient,
        anthropic_client: anthropic.Anthropic,
        db: Database
    ):
        self.config = config
        self.broker = broker
        self.anthropic = anthropic_client
        self.db = db
        
        self.agent_id = config['agent']['id']
        self.daily_budget = config['agent'].get('daily_budget', 5.0)
        self.consciousness: Optional[ConsciousnessClient] = None
        self.executor: Optional[ToolExecutor] = None
        
        logger.info(f"UnifiedAgent initialized: {self.agent_id}")
    
    async def initialize(self):
        """Initialize agent connections."""
        await self.db.connect()
        
        if self.db.research_pool:
            self.consciousness = ConsciousnessClient(
                self.db.research_pool, self.agent_id
            )
        
        self.executor = ToolExecutor(
            broker=self.broker,
            db=self.db,
            consciousness=self.consciousness,
            config=self.config
        )
        
        logger.info("Agent initialized")
    
    async def shutdown(self):
        """Shutdown agent."""
        if self.consciousness:
            await self.consciousness.sleep()
        
        await self.db.close()
        logger.info("Agent shutdown complete")
    
    def _is_market_open(self) -> bool:
        """Check if US market is open."""
        now = datetime.now(ET)
        
        # Weekend check
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        return market_open <= current_time < market_close
    
    def _get_system_prompt(self, mode: str) -> str:
        """Get system prompt for Claude."""
        return f"""You are dev_claude, an AI trading agent for US markets (NYSE/NASDAQ).

## Your Role
- Sandbox trader experimenting with momentum strategies
- Learning and improving through paper trading
- $5/day API budget, {self.config['trading'].get('max_positions', 8)} max positions

## Current Mode: {mode.upper()}
{'- SCAN: Find candidates, analyze, but do NOT trade' if mode == 'scan' else ''}
{'- TRADE: Full trading cycle - scan, analyze, execute if criteria met' if mode == 'trade' else ''}
{'- CLOSE: Review positions, close weak setups, generate EOD report' if mode == 'close' else ''}
{'- HEARTBEAT: Check messages, update status, no trading' if mode == 'heartbeat' else ''}

## Trading Rules
1. Max position: ${self.config['trading'].get('max_position_value', 5000)} USD
2. Stop loss: {self.config['trading'].get('stop_loss_pct', 0.05) * 100}%
3. Take profit: {self.config['trading'].get('take_profit_pct', 0.10) * 100}%
4. Only trade stocks > $5, volume > 500K

## Workflow
1. get_portfolio - Check current state
2. scan_market - Find candidates  
3. For each candidate:
   - get_quote - Current price
   - get_technicals - RSI, MAs
   - detect_patterns - Chart patterns
   - check_risk - Validate trade
4. execute_trade - If criteria met
5. log_decision - Record reasoning

## Decision Framework
ENTER when:
- RSI between 30-70 (not overbought/oversold)
- Price above SMA 10
- Clear pattern (breakout, support bounce)
- Risk check passes

EXIT when:
- Stop loss hit (-5%)
- Take profit hit (+10%)
- Pattern breakdown
- RSI > 80 (overbought)

Always explain your reasoning using log_decision.
"""
    
    async def run_cycle(self, mode: str) -> Dict[str, Any]:
        """Run a trading cycle."""
        cycle_id = datetime.now(ET).strftime('%Y%m%d-%H%M%S')
        logger.info(f"Starting cycle {cycle_id} in {mode} mode")
        
        # Wake up consciousness
        budget_remaining = self.daily_budget
        if self.consciousness:
            wake_result = await self.consciousness.wake_up()
            budget_remaining = wake_result.get('budget_remaining', self.daily_budget)
            
            # Process any messages
            for msg in wake_result.get('messages', []):
                logger.info(f"Message from {msg['from_agent']}: {msg['subject']}")
        
        if budget_remaining <= 0:
            logger.warning("Daily budget exhausted")
            return {'status': 'budget_exhausted', 'cycle_id': cycle_id}
        
        # Skip trading if market closed (except heartbeat)
        if mode in ['trade', 'scan'] and not self._is_market_open():
            logger.info("Market closed - switching to heartbeat mode")
            mode = 'heartbeat'
        
        # For heartbeat, just process messages
        if mode == 'heartbeat':
            if self.consciousness:
                await self.consciousness.sleep()
            return {
                'status': 'complete',
                'cycle_id': cycle_id,
                'mode': 'heartbeat',
                'messages_processed': len(wake_result.get('messages', [])) if self.consciousness else 0
            }
        
        # Run Claude trading loop
        system_prompt = self._get_system_prompt(mode)
        messages = [{"role": "user", "content": f"Execute {mode} cycle. Check portfolio first."}]
        
        api_spend = 0.0
        iterations = 0
        max_iterations = 20  # Safety limit
        
        while iterations < max_iterations:
            iterations += 1
            
            try:
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages
                )
                
                # Estimate API cost
                api_spend += 0.003 * iterations  # Rough estimate
                
                # Process response
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)
                
                # Check for tool use
                tool_blocks = [b for b in response.content if b.type == "tool_use"]
                
                if not tool_blocks:
                    # No tools called - cycle complete
                    break
                
                # Execute tools
                tool_results = []
                for tool_block in tool_blocks:
                    result = await self.executor.execute(
                        tool_block.name,
                        tool_block.input
                    )
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result)
                    })
                
                messages.append({"role": "user", "content": tool_results})
                
                # Check stop reason
                if response.stop_reason == "end_turn":
                    break
                    
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                break
        
        # Update budget
        if self.consciousness:
            await self.consciousness.update_budget(api_spend)
            await self.consciousness.sleep()
        
        # Get summary
        summary = self.executor.get_summary() if self.executor else {}
        
        return {
            'status': 'complete',
            'cycle_id': cycle_id,
            'mode': mode,
            'iterations': iterations,
            'api_spend': round(api_spend, 4),
            'tools_called': summary.get('tools_called', 0),
            'trades_executed': summary.get('trades_executed', 0)
        }
    
    async def run_scan(self) -> Dict[str, Any]:
        """Run scan cycle."""
        return await self.run_cycle('scan')
    
    async def run_trade(self) -> Dict[str, Any]:
        """Run trade cycle."""
        return await self.run_cycle('trade')
    
    async def run_close(self) -> Dict[str, Any]:
        """Run close cycle."""
        return await self.run_cycle('close')
    
    async def run_heartbeat(self) -> Dict[str, Any]:
        """Run heartbeat cycle."""
        return await self.run_cycle('heartbeat')


# ============================================================================
# MAIN
# ============================================================================

async def main(mode: str, config_path: Optional[str] = None):
    """Main entry point."""
    
    # Load config
    config = load_config(config_path)
    agent_id = config['agent']['id']
    
    logger.info(f"Starting {agent_id} in {mode} mode")
    
    # Get database URLs
    trading_url = os.getenv("DATABASE_URL") or os.getenv("DEV_DATABASE_URL")
    research_url = os.getenv("RESEARCH_DATABASE_URL")
    
    if not trading_url:
        logger.error("No DATABASE_URL set")
        sys.exit(1)
    
    # Create components
    db = Database(trading_url, research_url)
    broker = AlpacaClient(paper_trading=True)
    anthropic_client = anthropic.Anthropic()
    
    # Create agent
    agent = UnifiedAgent(
        config=config,
        broker=broker,
        anthropic_client=anthropic_client,
        db=db
    )
    
    try:
        await agent.initialize()
        
        # Run appropriate mode
        if mode == 'scan':
            result = await agent.run_scan()
        elif mode == 'trade':
            result = await agent.run_trade()
        elif mode == 'close':
            result = await agent.run_close()
        elif mode == 'heartbeat':
            result = await agent.run_heartbeat()
        else:
            logger.error(f"Unknown mode: {mode}")
            result = {'error': f'Unknown mode: {mode}'}
        
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        
    finally:
        await agent.shutdown()


def cli():
    """Command line interface."""
    parser = argparse.ArgumentParser(description='dev_claude Unified Trading Agent')
    parser.add_argument(
        '--mode',
        choices=['scan', 'trade', 'close', 'heartbeat'],
        default='heartbeat',
        help='Operating mode'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config file'
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(args.mode, args.config))


if __name__ == "__main__":
    cli()
```

---

## 6. Cron Schedule

### /etc/cron.d/catalyst-dev

```cron
# ============================================================================
# DEV_CLAUDE - US Market Trading Schedule
# Timezone: UTC (EST = UTC-5, EDT = UTC-4)
# ============================================================================

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# Working directories
CATALYST_DIR=/root/catalyst-dev
VENV_PYTHON=/root/catalyst-dev/venv/bin/python3
LOG_DIR=/root/catalyst-dev/logs

# ============================================================================
# PRE-MARKET SCAN (08:00 EST = 13:00 UTC)
# ============================================================================
0 13 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode scan >> $LOG_DIR/scan.log 2>&1

# ============================================================================
# TRADING HOURS (09:30-16:00 EST = 14:30-21:00 UTC)
# ============================================================================
# First cycle at market open
30 14 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1

# Hourly cycles during market hours
0 15 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 16 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 17 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 18 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 19 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1
0 20 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode trade >> $LOG_DIR/trade.log 2>&1

# ============================================================================
# END OF DAY (16:00 EST = 21:00 UTC)
# ============================================================================
0 21 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode close >> $LOG_DIR/close.log 2>&1

# ============================================================================
# OFF-HOURS HEARTBEAT (every 3 hours)
# ============================================================================
0 0,3,6,9,12 * * 1-5 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode heartbeat >> $LOG_DIR/heartbeat.log 2>&1

# Weekend heartbeat (every 6 hours)
0 0,6,12,18 * * 0,6 cd $CATALYST_DIR && $VENV_PYTHON unified_agent.py --mode heartbeat >> $LOG_DIR/heartbeat.log 2>&1

# ============================================================================
# LOG ROTATION
# ============================================================================
0 0 * * 0 find $LOG_DIR -name "*.log" -mtime +7 -delete
```

---

## 7. Database Schema

### Required Tables in catalyst_dev

```sql
-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    order_type VARCHAR(20) DEFAULT 'market',
    status VARCHAR(20) DEFAULT 'pending',
    broker_order_id VARCHAR(100),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Decisions table (for learning)
CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    decision_type VARCHAR(20) NOT NULL,
    reasoning TEXT,
    confidence DECIMAL(3,2),
    agent_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(10,2),
    current_price DECIMAL(10,2),
    unrealized_pnl DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'open',
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    close_reason TEXT
);
```

---

## 8. Deployment Instructions

### For Claude Code (little bro):

```bash
# 1. SSH to US droplet
ssh root@<us-droplet-ip>

# 2. Create directory structure
mkdir -p /root/catalyst-dev/{config,logs}
cd /root/catalyst-dev

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install anthropic asyncpg pyyaml alpaca-py

# 5. Create .env file (fill in actual values)
cat > .env << 'EOF'
AGENT_ID=dev_claude
DATABASE_URL=postgresql://...
RESEARCH_DATABASE_URL=postgresql://...
ANTHROPIC_API_KEY=sk-ant-...
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
PAPER_TRADING=true
EOF

# 6. Copy unified_agent.py (from this document)
# 7. Copy config/dev_claude_config.yaml (from this document)

# 8. Test the agent
source .env
python3 unified_agent.py --mode heartbeat

# 9. Install cron schedule
cp catalyst-dev.cron /etc/cron.d/catalyst-dev
chmod 644 /etc/cron.d/catalyst-dev
systemctl restart cron

# 10. Verify cron installed
cat /etc/cron.d/catalyst-dev
```

---

## 9. Testing Checklist

- [ ] `.env` file created with all variables
- [ ] `config/dev_claude_config.yaml` created
- [ ] Virtual environment activated
- [ ] Dependencies installed (anthropic, asyncpg, alpaca-py, pyyaml)
- [ ] Database connection working
- [ ] Alpaca connection working (paper trading)
- [ ] `python3 unified_agent.py --mode heartbeat` runs successfully
- [ ] Cron schedule installed
- [ ] Logs directory exists and writable

---

## 10. Key Differences from intl_claude

| Aspect | intl_claude (HKEX) | dev_claude (US) |
|--------|-------------------|-----------------|
| Broker | Moomoo/OpenD | Alpaca |
| Market | HKEX (HKT) | NYSE/NASDAQ (EST) |
| Currency | HKD | USD |
| Lot size | 100+ (varies) | 1 (no minimum) |
| Market hours | 09:30-12:00, 13:00-16:00 HKT | 09:30-16:00 EST |
| Lunch break | Yes (12:00-13:00) | No |

---

**END OF IMPLEMENTATION DOCUMENT**

*Catalyst Trading System - January 2026*
*Craig + Claude Family*
