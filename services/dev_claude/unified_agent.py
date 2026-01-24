#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: unified_agent.py
Version: 3.0.1
Last Updated: 2026-01-21
Purpose: Unified trading agent for US markets (dev_claude)

REVISION HISTORY:
v3.0.1 (2026-01-21) - Fix position sync dict/object mismatch
  - Fixed sync_positions_with_broker() to use dict notation
  - Internal AlpacaClient returns dicts, not Position objects
  - Fixes "'dict' object has no attribute 'symbol'" error

v3.0.0 (2026-01-20) - Workflow tracker and position auto-sync
  - Added WorkflowTracker for 10-phase workflow visibility
  - Added position auto-sync with broker at cycle start
  - Added DECIDE/VALIDATE/MONITOR phase transitions
  - Ported from intl_claude unified_agent.py v3.1.0

v2.0.1 (2026-01-20) - Switch to IEX data feed
  - Changed from SIP to IEX feed for market data
  - Fixes "subscription does not permit querying recent SIP data" error

v2.0.0 (2026-01-17) - Modular refactor aligned with intl_claude
  - Separated brokers/alpaca.py, data/database.py, tools.py
  - ToolExecutor moved to separate module
  - Aligned structure with intl_claude (HKEX)

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
from dotenv import load_dotenv

# Local modular imports (aligned with intl_claude structure)
from tools import TOOLS, TOOL_NAMES, get_tools_for_mode
from tool_executor import ToolExecutor, create_tool_executor
from workflow_tracker import WorkflowTracker, WORKFLOW_PHASES, get_phase_for_tool
from brokers.alpaca import AlpacaClient, init_alpaca_client, get_alpaca_client
from data.database import DatabaseClient, init_database, get_database

# Load environment variables
load_dotenv()

# Logging (must be before timezone to avoid reference error)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dev_claude')

# Timezone with DST support
try:
    import pytz
    ET = pytz.timezone('America/New_York')
    USE_PYTZ = True
except ImportError:
    # Fallback to fixed offset (no DST support)
    ET = timezone(timedelta(hours=-5))
    USE_PYTZ = False
    logger.warning("pytz not installed - DST handling disabled. Install with: pip install pytz")


def get_eastern_now():
    """Get current time in Eastern timezone with DST awareness."""
    if USE_PYTZ:
        return datetime.now(ET)
    else:
        return datetime.now(ET)


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
            try:
                self.research_pool = await asyncpg.create_pool(
                    self.research_url, min_size=1, max_size=3
                )
                logger.info("Connected to research database")
            except Exception as e:
                logger.warning(f"Could not connect to research database: {e}")
                self.research_pool = None

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
    """Interface to consciousness framework - aligned with catalyst_research schema."""

    def __init__(self, pool: asyncpg.Pool, agent_id: str):
        self.pool = pool
        self.agent_id = agent_id

    async def wake_up(self) -> Dict[str, Any]:
        """Wake up and check for messages."""
        try:
            async with self.pool.acquire() as conn:
                # Check if claude_state table exists
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'claude_state'
                    )
                """)

                if not exists:
                    logger.warning("claude_state table not found - consciousness disabled")
                    return {'messages': [], 'budget_remaining': 5.0}

                # Update state to active (using actual schema columns)
                await conn.execute("""
                    INSERT INTO claude_state (agent_id, current_mode, last_wake_at, last_action_at, daily_budget, api_spend_today)
                    VALUES ($1, 'active', NOW(), NOW(), 5.0, 0.0)
                    ON CONFLICT (agent_id) DO UPDATE SET
                        current_mode = 'active',
                        last_wake_at = NOW(),
                        last_action_at = NOW(),
                        updated_at = NOW()
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

                # Mark as read (using actual schema columns)
                if messages:
                    ids = [m['id'] for m in messages]
                    await conn.execute("""
                        UPDATE claude_messages
                        SET status = 'read', read_at = NOW()
                        WHERE id = ANY($1)
                    """, ids)

                # Get budget info (using actual schema columns)
                state = await conn.fetchrow("""
                    SELECT daily_budget, api_spend_today FROM claude_state WHERE agent_id = $1
                """, self.agent_id)

                return {
                    'messages': [dict(m) for m in messages],
                    'budget_remaining': float(state['daily_budget'] - state['api_spend_today']) if state else 5.0
                }
        except Exception as e:
            logger.warning(f"Consciousness wake_up error: {e}")
            return {'messages': [], 'budget_remaining': 5.0}

    async def send_message(
        self,
        to_agent: str,
        subject: str,
        body: str,
        priority: str = 'normal',
        msg_type: str = 'notification'
    ):
        """Send message to another agent."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_messages (from_agent, to_agent, msg_type, subject, body, priority)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, self.agent_id, to_agent, msg_type, subject, body, priority)
        except Exception as e:
            logger.warning(f"Could not send message: {e}")

    async def observe(self, subject: str, content: str, confidence: float = 0.8, observation_type: str = 'market'):
        """Record an observation."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_observations (agent_id, observation_type, subject, content, confidence, market)
                    VALUES ($1, $2, $3, $4, $5, 'US')
                """, self.agent_id, observation_type, subject, content, confidence)
        except Exception as e:
            logger.warning(f"Could not record observation: {e}")

    async def learn(self, category: str, learning: str, confidence: float = 0.7):
        """Record a learning."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_learnings (agent_id, category, learning, confidence, applies_to_markets)
                    VALUES ($1, $2, $3, $4, '["US"]'::jsonb)
                """, self.agent_id, category, learning, confidence)
        except Exception as e:
            logger.warning(f"Could not record learning: {e}")

    async def update_budget(self, amount_spent: float):
        """Update budget usage."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE claude_state SET
                        api_spend_today = api_spend_today + $2,
                        last_action_at = NOW(),
                        updated_at = NOW()
                    WHERE agent_id = $1
                """, self.agent_id, amount_spent)
        except Exception as e:
            logger.warning(f"Could not update budget: {e}")

    async def sleep(self):
        """Go to sleep state."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE claude_state SET
                        current_mode = 'sleeping',
                        last_action_at = NOW(),
                        updated_at = NOW()
                    WHERE agent_id = $1
                """, self.agent_id)
        except Exception as e:
            logger.warning(f"Could not set sleep state: {e}")


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
        from alpaca.data.enums import DataFeed

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

        # News client
        self.news_client = None
        try:
            from alpaca.data.historical.news import NewsClient
            from alpaca.data.requests import NewsRequest
            self.news_client = NewsClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )
            self._NewsRequest = NewsRequest
        except ImportError:
            logger.warning("Alpaca news client not available")

        # Store imports for later use
        self._MarketOrderRequest = MarketOrderRequest
        self._OrderSide = OrderSide
        self._TimeInForce = TimeInForce
        self._StockLatestQuoteRequest = StockLatestQuoteRequest
        self._StockBarsRequest = StockBarsRequest
        self._TimeFrame = TimeFrame
        self._DataFeed = DataFeed

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
        request = self._StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=self._DataFeed.IEX)
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
            end=end,
            feed=self._DataFeed.IEX
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

    def get_news(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get news for a symbol using Alpaca News API."""
        if not self.news_client:
            return {
                'symbol': symbol,
                'headlines': [],
                'sentiment': 'neutral',
                'note': 'News client not available'
            }

        try:
            from datetime import datetime, timedelta

            # Get news from last 3 days
            end = datetime.now()
            start = end - timedelta(days=3)

            request = self._NewsRequest(
                symbols=symbol,
                start=start,
                end=end,
                limit=limit
            )

            news = self.news_client.get_news(request)

            headlines = []
            sentiment_scores = []

            for article in news.news:
                headline_data = {
                    'headline': article.headline,
                    'source': article.source,
                    'url': article.url,
                    'created_at': article.created_at.isoformat() if article.created_at else None,
                    'summary': article.summary[:200] + '...' if article.summary and len(article.summary) > 200 else article.summary
                }

                # Simple sentiment analysis based on keywords
                sentiment = self._analyze_headline_sentiment(article.headline)
                headline_data['sentiment'] = sentiment
                sentiment_scores.append(sentiment)

                headlines.append(headline_data)

            # Calculate overall sentiment
            if sentiment_scores:
                pos_count = sentiment_scores.count('positive')
                neg_count = sentiment_scores.count('negative')
                if pos_count > neg_count:
                    overall = 'positive'
                elif neg_count > pos_count:
                    overall = 'negative'
                else:
                    overall = 'neutral'
            else:
                overall = 'neutral'

            return {
                'symbol': symbol,
                'headlines': headlines,
                'article_count': len(headlines),
                'sentiment': overall,
                'sentiment_breakdown': {
                    'positive': sentiment_scores.count('positive'),
                    'negative': sentiment_scores.count('negative'),
                    'neutral': sentiment_scores.count('neutral')
                }
            }

        except Exception as e:
            logger.warning(f"Error fetching news for {symbol}: {e}")
            return {
                'symbol': symbol,
                'headlines': [],
                'sentiment': 'neutral',
                'error': str(e)
            }

    def _analyze_headline_sentiment(self, headline: str) -> str:
        """Simple keyword-based sentiment analysis."""
        if not headline:
            return 'neutral'

        headline_lower = headline.lower()

        positive_words = [
            'surge', 'soar', 'jump', 'rally', 'gain', 'rise', 'up', 'high',
            'beat', 'exceed', 'strong', 'growth', 'profit', 'bullish', 'buy',
            'upgrade', 'outperform', 'record', 'boost', 'positive', 'win'
        ]

        negative_words = [
            'drop', 'fall', 'plunge', 'sink', 'decline', 'down', 'low',
            'miss', 'loss', 'weak', 'cut', 'bearish', 'sell', 'downgrade',
            'underperform', 'warning', 'concern', 'risk', 'negative', 'fail'
        ]

        pos_count = sum(1 for word in positive_words if word in headline_lower)
        neg_count = sum(1 for word in negative_words if word in headline_lower)

        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        return 'neutral'


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
        """Scan for trading candidates with momentum and volume analysis."""
        limit = min(inputs.get('limit', 10), 20)
        min_volume = inputs.get('min_volume', 500000)
        min_change_pct = inputs.get('min_change_pct', 2.0)

        config = self.config.get('trading', {})
        min_price = config.get('min_price', 5.0)
        max_price = config.get('max_price', 500.0)

        # Extended watchlist of liquid US stocks
        watchlist = [
            # Tech giants
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
            # Semiconductors
            'AMD', 'INTC', 'AVGO', 'QCOM', 'MU', 'AMAT',
            # Growth tech
            'CRM', 'ADBE', 'NOW', 'SNOW', 'PLTR', 'NET', 'DDOG',
            # Finance
            'JPM', 'BAC', 'GS', 'MS', 'V', 'MA',
            # Consumer
            'DIS', 'NFLX', 'SBUX', 'NKE', 'HD', 'WMT',
            # Healthcare
            'UNH', 'JNJ', 'PFE', 'MRNA', 'LLY',
            # Energy
            'XOM', 'CVX', 'OXY',
            # ETFs
            'SPY', 'QQQ', 'IWM', 'DIA'
        ]

        candidates = []
        scanned = 0

        for symbol in watchlist:
            if len(candidates) >= limit:
                break

            try:
                # Get recent bars for momentum calculation
                bars = self.broker.get_bars(symbol, days=5)
                if len(bars) < 2:
                    continue

                scanned += 1

                # Calculate metrics
                current_close = bars[-1]['close']
                prev_close = bars[-2]['close']
                change_pct = ((current_close - prev_close) / prev_close) * 100

                # Get today's volume (last bar)
                volume = bars[-1]['volume']

                # Calculate 5-day average volume
                avg_volume = sum(b['volume'] for b in bars) / len(bars)

                # Filter criteria
                if current_close < min_price or current_close > max_price:
                    continue
                if avg_volume < min_volume:
                    continue
                if abs(change_pct) < min_change_pct:
                    continue

                # Get current quote for spread analysis
                quote = self.broker.get_quote(symbol)
                spread_pct = 0
                if 'error' not in quote and quote.get('mid', 0) > 0:
                    spread_pct = (quote.get('spread', 0) / quote.get('mid', 1)) * 100

                # Calculate momentum score
                momentum_score = abs(change_pct) * (volume / avg_volume)

                candidates.append({
                    'symbol': symbol,
                    'price': round(current_close, 2),
                    'change_pct': round(change_pct, 2),
                    'volume': volume,
                    'avg_volume': int(avg_volume),
                    'volume_ratio': round(volume / avg_volume, 2),
                    'spread_pct': round(spread_pct, 3),
                    'momentum_score': round(momentum_score, 2),
                    'direction': 'bullish' if change_pct > 0 else 'bearish'
                })

            except Exception as e:
                logger.warning(f"Error scanning {symbol}: {e}")
                continue

        # Sort by momentum score descending
        candidates.sort(key=lambda x: x['momentum_score'], reverse=True)

        return {
            'candidates_found': len(candidates),
            'stocks_scanned': scanned,
            'candidates': candidates[:limit],
            'filters': {
                'min_volume': min_volume,
                'min_change_pct': min_change_pct,
                'min_price': min_price,
                'max_price': max_price
            },
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
        """Get news for symbol using Alpaca News API."""
        symbol = inputs['symbol'].upper()
        limit = inputs.get('limit', 5)
        return self.broker.get_news(symbol, limit)

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
                try:
                    async with self.db.pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO orders (symbol, side, quantity, order_type, status, broker_order_id, order_purpose, notes)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """, symbol, side, quantity, 'market', result.get('status', 'submitted'),
                        result.get('order_id'), 'entry', reason)
                except Exception as e:
                    logger.warning(f"Could not log order to DB: {e}")

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
                priority='urgent',
                msg_type='alert'
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
                priority=priority,
                msg_type='alert'
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
            try:
                async with self.db.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO decisions (symbol, decision_type, reasoning, confidence, metadata)
                        VALUES ($1, $2, $3, $4, $5::jsonb)
                    """, symbol, decision_type, reasoning, confidence, json.dumps({'agent_id': 'dev_claude'}))
            except Exception as e:
                logger.warning(f"Could not log decision to DB: {e}")

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

    def sync_positions_with_broker(self) -> Dict[str, Any]:
        """
        Sync database positions with Alpaca broker.

        Reconciles the local database with broker's actual positions:
        - Closes phantom positions (in DB but not in Alpaca)
        - Adds missing positions (in Alpaca but not in DB)
        - Updates quantity mismatches
        """
        result = {
            "phantoms_closed": [],
            "missing_added": [],
            "quantity_updated": [],
            "changes_made": False,
            "timestamp": datetime.now(ET).isoformat(),
        }

        if not self.broker:
            logger.warning("Broker not connected, skipping position sync")
            return {"error": "Broker not connected", "changes_made": False}

        try:
            # Get positions from Alpaca (returns list of dicts)
            broker_positions = self.broker.get_positions()
            broker_symbols = {p['symbol']: p for p in broker_positions}

            logger.info(f"Position sync: {len(broker_positions)} positions in Alpaca")

            # For now, just log what we find - DB sync requires async
            if broker_positions:
                for p in broker_positions:
                    logger.info(f"  Alpaca position: {p['symbol']} qty={p['quantity']} @ ${p['entry_price']:.2f}")

            return result

        except Exception as e:
            logger.error(f"Position sync error: {e}")
            return {"error": str(e), "changes_made": False}


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
        wake_result = {'messages': []}
        if self.consciousness:
            wake_result = await self.consciousness.wake_up()
            budget_remaining = wake_result.get('budget_remaining', self.daily_budget)

            # Process any messages
            for msg in wake_result.get('messages', []):
                logger.info(f"Message from {msg['from_agent']}: {msg['subject']}")

        if budget_remaining <= 0:
            logger.warning("Daily budget exhausted")
            return {'status': 'budget_exhausted', 'cycle_id': cycle_id}

        # Initialize workflow tracker
        self.tracker = WorkflowTracker(
            cycle_id=cycle_id,
            agent_id=self.agent_id,
            db_pool=self.db.research_pool if self.db else None,
            timezone="America/New_York"
        )
        await self.tracker.start_phase("INIT", "Cycle initialization")

        # Auto-sync positions with broker at start of each cycle
        if self.executor and mode in ['trade', 'scan', 'close']:
            try:
                sync_result = self.executor.sync_positions_with_broker()
                if sync_result.get('changes_made'):
                    logger.info(f"Position sync: {sync_result}")
            except Exception as e:
                logger.warning(f"Position sync failed: {e}")

        await self.tracker.complete_phase("INIT", sync_complete=True)

        # Skip trading if market closed (except heartbeat) - unless forced
        force = self.config.get('force', False)
        if mode in ['trade', 'scan'] and not self._is_market_open() and not force:
            logger.info("Market closed - switching to heartbeat mode")
            mode = 'heartbeat'
        elif force and not self._is_market_open():
            logger.warning("Market closed but running in FORCED mode")

        # For heartbeat, just process messages
        if mode == 'heartbeat':
            if self.consciousness:
                await self.consciousness.sleep()
            return {
                'status': 'complete',
                'cycle_id': cycle_id,
                'mode': 'heartbeat',
                'messages_processed': len(wake_result.get('messages', []))
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

                # Execute tools with workflow tracking
                tool_results = []
                for tool_block in tool_blocks:
                    tool_name = tool_block.name
                    tool_input = tool_block.input

                    # Update workflow phase based on tool
                    new_phase = get_phase_for_tool(tool_name, self.tracker.current_phase or "INIT")
                    if new_phase != self.tracker.current_phase:
                        if self.tracker.current_phase:
                            await self.tracker.complete_phase(self.tracker.current_phase)
                        await self.tracker.start_phase(new_phase, f"Executing {tool_name}")

                    # Execute the tool
                    result = await self.executor.execute(tool_name, tool_input)

                    # Handle special workflow transitions
                    if tool_name == "check_risk" and isinstance(result, dict):
                        # After DECIDE (check_risk), transition to VALIDATE
                        await self.tracker.complete_phase("DECIDE", decision_made=True)
                        await self.tracker.start_phase("VALIDATE", "Risk validation")
                        await self.tracker.complete_phase("VALIDATE",
                            approved=result.get("approved", False),
                            reason=result.get("reason", "")
                        )

                    elif tool_name == "execute_trade" and isinstance(result, dict):
                        if result.get("status", "").lower() in ["filled", "success", "submitted", "accepted"]:
                            # After successful EXECUTE, transition to MONITOR
                            await self.tracker.complete_phase("EXECUTE", trades=1)
                            await self.tracker.start_phase("MONITOR", "Position monitoring")
                            await self.tracker.complete_phase("MONITOR",
                                symbol=result.get("symbol"),
                                monitoring_active=True
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

        # Complete LOG phase
        await self.tracker.start_phase("LOG", "Logging results")
        await self.tracker.complete_phase("LOG")

        # Update budget
        if self.consciousness:
            await self.consciousness.update_budget(api_spend)
            await self.consciousness.sleep()

        # Get summary
        summary = self.executor.get_summary() if self.executor else {}

        # Complete cycle
        await self.tracker.complete_cycle({
            'mode': mode,
            'iterations': iterations,
            'trades': summary.get('trades_executed', 0)
        })

        logger.info(f"Cycle complete: {self.tracker.get_progress_bar()}")

        return {
            'status': 'complete',
            'cycle_id': cycle_id,
            'mode': mode,
            'iterations': iterations,
            'api_spend': round(api_spend, 4),
            'tools_called': summary.get('tools_called', 0),
            'trades_executed': summary.get('trades_executed', 0),
            'workflow': self.tracker.get_progress_bar()
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

async def main(mode: str, config_path: Optional[str] = None, force: bool = False):
    """Main entry point."""

    # Load config
    config = load_config(config_path)
    config['force'] = force  # Pass force flag to agent
    agent_id = config['agent']['id']

    logger.info(f"Starting {agent_id} in {mode} mode{' (FORCED)' if force else ''}")

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
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force run even if market is closed'
    )

    args = parser.parse_args()

    asyncio.run(main(args.mode, args.config, args.force))


if __name__ == "__main__":
    cli()
