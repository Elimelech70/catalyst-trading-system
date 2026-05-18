"""
Market Scanner MCP Server

READ-ONLY market data agent. Provides quotes, technicals, patterns, and news
via MCP SSE protocol on port 8002.

Tools:
  - scan_market: Find candidates with volume spikes
  - get_quote: Current quote for a symbol
  - get_technicals: RSI, MACD, SMA, ATR for a symbol
  - detect_patterns: Chart patterns (breakout, bull_flag, etc.)
  - get_news: News + sentiment for a symbol

Version: 1.0.0
"""

import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("market-scanner-mcp")

HK_TZ = ZoneInfo("Asia/Hong_Kong")

# ---------------------------------------------------------------------------
# Lazy-init singletons
# ---------------------------------------------------------------------------

_broker = None
_market = None
_patterns = None
_news = None


def _get_broker():
    global _broker
    if _broker is None:
        from brokers.moomoo import init_moomoo_client, get_moomoo_client
        _broker = get_moomoo_client()
        if _broker is None:
            _broker = init_moomoo_client(paper_trading=True)
        if not _broker._connected:
            _broker.connect()
        logger.info("Broker connected (read-only)")
    return _broker


def _get_market():
    global _market
    if _market is None:
        from data.market import get_market_data
        _market = get_market_data(_get_broker())
    return _market


def _get_patterns():
    global _patterns
    if _patterns is None:
        from data.patterns import get_pattern_detector
        _patterns = get_pattern_detector(_get_market())
    return _patterns


def _get_news():
    global _news
    if _news is None:
        from data.news import get_news_client
        _news = get_news_client()
    return _news


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("market-scanner")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="scan_market",
            description=(
                "Scan the HKEX market for trading candidates with volume spikes. "
                "Returns candidates sorted by signal strength with volume ratio, "
                "price change, and momentum data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "index": {
                        "type": "string",
                        "description": "Index to scan: HSI, HSCEI, HSTECH, or ALL",
                        "default": "ALL",
                    },
                    "limit": {"type": "integer", "description": "Max candidates to return", "default": 10},
                    "min_volume_ratio": {"type": "number", "description": "Minimum volume ratio", "default": 1.5},
                    "max_price": {"type": "number", "description": "Max stock price in HKD", "default": 1000},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_quote",
            description="Get current quote for a symbol including last price, volume, bid/ask, and change.",
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "HKEX symbol (e.g. '700')"}},
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_technicals",
            description=(
                "Get technical indicators for a symbol: RSI, MACD, SMA (9/20/50/200), "
                "EMA (9/21), ATR, Bollinger Bands, volume ratio."
            ),
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        ),
        Tool(
            name="detect_patterns",
            description=(
                "Detect chart patterns for a symbol: breakout, near_breakout, bull_flag, "
                "ascending_triangle, momentum_continuation, etc. "
                "Returns entry, stop loss, take profit levels with confidence."
            ),
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_news",
            description="Get recent news and sentiment analysis for a symbol. Includes catalyst classification.",
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handlers = {
        "scan_market": _handle_scan_market,
        "get_quote": _handle_get_quote,
        "get_technicals": _handle_get_technicals,
        "detect_patterns": _handle_detect_patterns,
        "get_news": _handle_get_news,
    }
    handler = handlers.get(name)
    if not handler:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    try:
        result = handler(arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e), "success": False}))]


# ---------------------------------------------------------------------------
# Tool implementations (adapted from tool_executor.py)
# ---------------------------------------------------------------------------

def _handle_scan_market(args: dict) -> dict:
    market = _get_market()
    index = args.get("index", "ALL")
    limit = min(args.get("limit", 10), 20)
    min_volume_ratio = args.get("min_volume_ratio", 1.5)
    max_price = args.get("max_price", 1000.0)

    candidates = market.scan_market(
        index=index, limit=limit,
        min_volume_ratio=min_volume_ratio, max_price=max_price,
    )
    return {
        "index": index,
        "candidates_found": len(candidates),
        "candidates": candidates,
        "min_volume_ratio": min_volume_ratio,
        "max_price": max_price,
        "success": True,
        "timestamp": datetime.now(HK_TZ).isoformat(),
    }


def _handle_get_quote(args: dict) -> dict:
    market = _get_market()
    symbol = args["symbol"]
    quote = market.get_quote(symbol)
    return {
        "symbol": symbol, "quote": quote,
        "success": True, "timestamp": datetime.now(HK_TZ).isoformat(),
    }


def _handle_get_technicals(args: dict) -> dict:
    market = _get_market()
    symbol = args["symbol"]
    technicals = market.get_technicals(symbol)
    return {
        "symbol": symbol, "technicals": technicals,
        "success": True, "timestamp": datetime.now(HK_TZ).isoformat(),
    }


def _handle_detect_patterns(args: dict) -> dict:
    patterns = _get_patterns()
    symbol = args["symbol"]
    detected = patterns.detect_patterns(symbol)
    return {
        "symbol": symbol,
        "patterns_found": len(detected),
        "patterns": detected,
        "success": True,
        "timestamp": datetime.now(HK_TZ).isoformat(),
    }


def _handle_get_news(args: dict) -> dict:
    news = _get_news()
    symbol = args["symbol"]
    articles = news.get_news(symbol)
    return {
        "symbol": symbol, "news": articles,
        "success": True, "timestamp": datetime.now(HK_TZ).isoformat(),
    }


# ---------------------------------------------------------------------------
# Health + App
# ---------------------------------------------------------------------------

async def health(request):
    try:
        _get_broker()
        return JSONResponse({"status": "healthy", "service": "market-scanner"})
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)


sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    logger.info("Market Scanner MCP Server starting on port 8002")
    yield

app = Starlette(
    debug=False,
    routes=[
        Route("/health", health),
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
