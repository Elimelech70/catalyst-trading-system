"""
Position Monitor MCP Server

Exposes position monitoring data via MCP SSE protocol on port 8001.
READ-ONLY for positions table. Writes only to position_monitor_status.

Tools:
  - get_exit_recommendations: Pending exit/consult recommendations
  - get_position_health: Health status of all monitored positions  
  - acknowledge_recommendation: Mark recommendation as processed

Version: 1.0.0
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("position-monitor-mcp")

HK_TZ = ZoneInfo("Asia/Hong_Kong")

# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------

_db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL not set")
        _db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=5, command_timeout=30)
        logger.info("Database pool created")
    return _db_pool


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("position-monitor")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_exit_recommendations",
            description=(
                "Get pending exit recommendations from the position monitor. "
                "Returns positions where the monitor detected EXIT or CONSULT_AI signals. "
                "The coordinator should act on these (close position or decide to hold) "
                "then call acknowledge_recommendation."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_position_health",
            description=(
                "Get health status of all currently monitored positions. "
                "Returns P&L, signal counts, high watermark, last check time, "
                "and current recommendation for each position."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="acknowledge_recommendation",
            description=(
                "Mark a recommendation as processed by the coordinator. "
                "Call this after acting on (or deciding to ignore) a recommendation "
                "so it doesn't appear in get_exit_recommendations again."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "monitor_id": {
                        "type": "integer",
                        "description": "The monitor_id from position_monitor_status to acknowledge",
                    },
                    "action_taken": {
                        "type": "string",
                        "description": "What the coordinator did: 'closed', 'held', 'deferred'",
                    },
                },
                "required": ["monitor_id", "action_taken"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    pool = await get_db_pool()

    if name == "get_exit_recommendations":
        return await _get_exit_recommendations(pool)
    elif name == "get_position_health":
        return await _get_position_health(pool)
    elif name == "acknowledge_recommendation":
        return await _acknowledge_recommendation(pool, arguments)
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def _get_exit_recommendations(pool: asyncpg.Pool) -> list[TextContent]:
    """Return unacknowledged EXIT / CONSULT_AI recommendations."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                m.monitor_id,
                m.position_id,
                m.symbol,
                m.recommendation,
                m.recommendation_reason,
                m.high_watermark,
                m.last_check_at,
                m.checks_completed,
                p.quantity,
                p.entry_price,
                p.side,
                p.stop_loss,
                p.take_profit,
                p.entry_time
            FROM position_monitor_status m
            JOIN positions p ON m.position_id = p.position_id
            WHERE m.recommendation IN ('EXIT', 'CONSULT_AI')
              AND p.status = 'open'
              AND COALESCE((m.metadata->>'acknowledged')::boolean, false) = false
            ORDER BY
                CASE m.recommendation WHEN 'EXIT' THEN 0 ELSE 1 END,
                m.updated_at DESC
        """)

    recommendations = []
    for r in rows:
        recommendations.append({
            "monitor_id": r["monitor_id"],
            "position_id": r["position_id"],
            "symbol": r["symbol"],
            "recommendation": r["recommendation"],
            "reason": r["recommendation_reason"],
            "high_watermark": float(r["high_watermark"]) if r["high_watermark"] else None,
            "last_check_at": r["last_check_at"].isoformat() if r["last_check_at"] else None,
            "checks_completed": r["checks_completed"],
            "quantity": r["quantity"],
            "entry_price": float(r["entry_price"]),
            "side": r["side"],
            "stop_loss": float(r["stop_loss"]) if r["stop_loss"] else None,
            "take_profit": float(r["take_profit"]) if r["take_profit"] else None,
            "entry_time": r["entry_time"].isoformat() if r["entry_time"] else None,
        })

    result = {
        "count": len(recommendations),
        "recommendations": recommendations,
        "timestamp": datetime.now(HK_TZ).isoformat(),
    }
    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def _get_position_health(pool: asyncpg.Pool) -> list[TextContent]:
    """Return health status of all monitored positions."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                m.monitor_id,
                m.position_id,
                m.symbol,
                m.status AS monitor_status,
                m.recommendation,
                m.recommendation_reason,
                m.high_watermark,
                m.last_check_at,
                m.checks_completed,
                m.haiku_calls,
                m.error_count,
                m.last_error,
                p.quantity,
                p.entry_price,
                p.side,
                p.stop_loss,
                p.take_profit,
                p.entry_time,
                p.status AS position_status
            FROM position_monitor_status m
            JOIN positions p ON m.position_id = p.position_id
            WHERE p.status = 'open'
            ORDER BY m.updated_at DESC
        """)

    positions = []
    for r in rows:
        positions.append({
            "monitor_id": r["monitor_id"],
            "position_id": r["position_id"],
            "symbol": r["symbol"],
            "monitor_status": r["monitor_status"],
            "recommendation": r["recommendation"],
            "reason": r["recommendation_reason"],
            "high_watermark": float(r["high_watermark"]) if r["high_watermark"] else None,
            "last_check_at": r["last_check_at"].isoformat() if r["last_check_at"] else None,
            "checks_completed": r["checks_completed"],
            "haiku_calls": r["haiku_calls"],
            "error_count": r["error_count"],
            "last_error": r["last_error"],
            "quantity": r["quantity"],
            "entry_price": float(r["entry_price"]),
            "side": r["side"],
            "stop_loss": float(r["stop_loss"]) if r["stop_loss"] else None,
            "take_profit": float(r["take_profit"]) if r["take_profit"] else None,
            "entry_time": r["entry_time"].isoformat() if r["entry_time"] else None,
        })

    result = {
        "monitored_positions": len(positions),
        "positions": positions,
        "timestamp": datetime.now(HK_TZ).isoformat(),
    }
    return [TextContent(type="text", text=json.dumps(result, default=str))]


async def _acknowledge_recommendation(pool: asyncpg.Pool, args: dict) -> list[TextContent]:
    """Mark a recommendation as acknowledged."""
    monitor_id = args["monitor_id"]
    action_taken = args["action_taken"]

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE position_monitor_status
            SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{acknowledged}', 'true'::jsonb
                ) || jsonb_build_object(
                    'action_taken', $2::text,
                    'acknowledged_at', NOW()::text
                ),
                updated_at = NOW()
            WHERE monitor_id = $1
            RETURNING monitor_id, symbol, recommendation
        """, monitor_id, action_taken)

    if row:
        result = {
            "acknowledged": True,
            "monitor_id": row["monitor_id"],
            "symbol": row["symbol"],
            "recommendation": row["recommendation"],
            "action_taken": action_taken,
        }
    else:
        result = {"acknowledged": False, "error": f"monitor_id {monitor_id} not found"}

    return [TextContent(type="text", text=json.dumps(result))]


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

async def health(request):
    """Health check endpoint."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return JSONResponse({"status": "healthy", "service": "position-monitor"})
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup
    logger.info("Position Monitor MCP Server starting on port 8001")
    await get_db_pool()
    from monitor import MonitorLoop
    monitor = MonitorLoop(await get_db_pool())
    asyncio.create_task(monitor.run())
    logger.info("Background monitoring loop started")
    yield
    # Shutdown
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
    logger.info("Position Monitor MCP Server stopped")

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
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
