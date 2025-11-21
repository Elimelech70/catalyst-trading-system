#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: orchestration-service.py
Version: 6.0.3
Last Updated: 2025-10-18
Purpose: Best-practice MCP orchestration using HTTP transport

REVISION HISTORY:
v6.0.3 (2025-10-18) - Fixed resource calling issue
- Separated internal health check from MCP resource
- Created _get_system_health_internal() for internal use
- MCP resources cannot be called directly as functions
- Fixed initialization health check

v6.0.2 (2025-10-18) - Fixed initialization hooks
- Removed @mcp.on_initialize() and @mcp.on_cleanup() decorators
- FastMCP doesn't support these decorators
- Moved to manual initialization before mcp.run()
- Added proper cleanup in finally block

v6.0.1 (2025-10-18) - Fixed URI format
- Changed resource URIs to full URL format (catalyst://path)
- FastMCP requires URI scheme, not just path strings
- Example: "system/health" → "catalyst://system/health"

v6.0.0 (2025-10-18) - Best Practice Implementation
- Pure FastMCP HTTP transport (no WebSocket)
- Removed FastAPI mixing - pure FastMCP server
- Simplified to single HTTP transport for production
- Ready for Nginx reverse proxy integration
- All MCP resources and tools from functional spec v4.1
- Proper initialization and cleanup hooks

v5.2.0 (2025-10-17) - WebSocket attempt (failed)
- Attempted WebSocket transport with non-existent method

Description of Service:
MCP orchestration server providing Claude with complete trading system access.
Uses HTTP transport as recommended for web deployments.

Transport Options:
- HTTP (Default): For production with Nginx reverse proxy
  - Requires: Nginx with SSL, API key authentication
  - Access: Claude Desktop via https://your-domain.com/mcp
  
- STDIO (Optional): For local development only
  - Requires: Claude Desktop on same machine
  - Access: Local process communication
  
NOTE: claude.ai web interface does NOT support MCP.
      Only Claude Desktop application supports MCP.
"""

from fastmcp import FastMCP, Context
from fastmcp.exceptions import McpError
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass
import aiohttp
import asyncio
import os
import logging

# ============================================================================
# SERVICE CONFIGURATION
# ============================================================================

SERVICE_NAME = "orchestration"
SERVICE_VERSION = "6.0.3"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "5000"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(SERVICE_NAME)


class Config:
    """Service URLs for internal REST API communication"""
    SCANNER_URL = os.getenv("SCANNER_URL", "http://scanner:5001")
    PATTERN_URL = os.getenv("PATTERN_URL", "http://pattern:5002")
    TECHNICAL_URL = os.getenv("TECHNICAL_URL", "http://technical:5003")
    RISK_URL = os.getenv("RISK_URL", "http://risk-manager:5004")
    TRADING_URL = os.getenv("TRADING_URL", "http://trading:5005")
    NEWS_URL = os.getenv("NEWS_URL", "http://news:5008")
    REPORTING_URL = os.getenv("REPORTING_URL", "http://reporting:5009")


SERVICE_URLS = {
    "scanner": Config.SCANNER_URL,
    "pattern": Config.PATTERN_URL,
    "technical": Config.TECHNICAL_URL,
    "risk_manager": Config.RISK_URL,
    "trading": Config.TRADING_URL,
    "news": Config.NEWS_URL,
    "reporting": Config.REPORTING_URL
}


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

@dataclass
class TradingCycle:
    """Current trading cycle state"""
    cycle_id: str
    status: str
    mode: str
    started_at: datetime
    aggressiveness: float
    max_positions: int


class ServiceState:
    """Global service state"""
    def __init__(self):
        self.current_cycle: Optional[TradingCycle] = None
        self.http_session: Optional[aiohttp.ClientSession] = None


state = ServiceState()


# ============================================================================
# INITIALIZE FASTMCP SERVER
# ============================================================================

mcp = FastMCP("catalyst-orchestration")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def call_service(
    service: str,
    method: str,
    endpoint: str,
    data: Optional[Dict] = None
) -> Dict:
    """
    Call internal REST service with error handling
    
    Args:
        service: Service name (scanner, pattern, etc.)
        method: HTTP method (GET, POST)
        endpoint: API endpoint path
        data: Optional request body for POST
        
    Returns:
        JSON response from service
        
    Raises:
        McpError: On service communication failure
    """
    try:
        if service not in SERVICE_URLS:
            raise ValueError(f"Unknown service: {service}")
        
        url = f"{SERVICE_URLS[service]}{endpoint}"
        
        if not state.http_session:
            raise RuntimeError("HTTP session not initialized")
        
        timeout = aiohttp.ClientTimeout(total=30)
        
        if method.upper() == "GET":
            async with state.http_session.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.json()
        elif method.upper() == "POST":
            async with state.http_session.post(
                url, json=data, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
    except aiohttp.ClientError as e:
        logger.error(f"Service call failed: {service} {endpoint} - {e}")
        raise McpError(
            "SERVICE_UNAVAILABLE",
            f"Failed to communicate with {service} service"
        )
    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise McpError("INVALID_PARAMETERS", str(e))


# ============================================================================
# CUSTOM ROUTES (Health Check)
# ============================================================================

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """
    Health check endpoint for Docker/Kubernetes
    
    Returns:
        200 OK if service is healthy
    """
    try:
        # Quick health check - verify HTTP session exists
        if state.http_session and not state.http_session.closed:
            return PlainTextResponse(
                f"OK - Orchestration v{SERVICE_VERSION}",
                status_code=200
            )
        else:
            return PlainTextResponse(
                "Service Initializing",
                status_code=503
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return PlainTextResponse(
            f"Unhealthy: {str(e)}",
            status_code=503
        )


# ============================================================================
# MCP RESOURCES - System State
# ============================================================================

async def _get_system_health_internal() -> Dict:
    """
    Internal function to check system health (not exposed as MCP resource)
    
    Returns:
        Dictionary with health status
    """
    health_results = {}
    failed_services = []
    
    # Check each service health
    for service_name, service_url in SERVICE_URLS.items():
        try:
            async with state.http_session.get(
                f"{service_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    health_results[service_name] = "healthy"
                else:
                    health_results[service_name] = "unhealthy"
                    failed_services.append(service_name)
        except Exception as e:
            health_results[service_name] = f"error: {str(e)}"
            failed_services.append(service_name)
    
    return {
        "status": "healthy" if not failed_services else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": health_results,
        "failed_services": failed_services
    }


@mcp.resource("catalyst://system/health")
async def get_system_health(ctx: Context) -> str:
    """
    Get overall system health status
    
    Returns:
        JSON string with system health metrics
    """
    try:
        return await _get_system_health_internal()
        
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        raise McpError("HEALTH_CHECK_FAILED", str(e))


@mcp.resource("catalyst://trading-cycle/current")
async def get_current_cycle(ctx: Context) -> str:
    """
    Get current trading cycle information
    
    Returns:
        JSON string with current cycle details
    """
    if not state.current_cycle:
        return {
            "status": "no_active_cycle",
            "message": "No trading cycle currently active"
        }
    
    cycle = state.current_cycle
    runtime = datetime.now() - cycle.started_at
    
    return {
        "cycle_id": cycle.cycle_id,
        "status": cycle.status,
        "mode": cycle.mode,
        "started_at": cycle.started_at.isoformat(),
        "runtime_seconds": int(runtime.total_seconds()),
        "runtime_formatted": str(runtime).split('.')[0],
        "max_positions": cycle.max_positions,
        "aggressiveness": cycle.aggressiveness
    }


@mcp.resource("catalyst://market-scan/latest")
async def get_latest_scan(ctx: Context) -> str:
    """
    Get latest market scan results
    
    Returns:
        JSON string with latest scan data
    """
    try:
        result = await call_service("scanner", "GET", "/api/v1/scan/latest")
        return result
    except Exception as e:
        logger.error(f"Failed to get scan results: {e}")
        raise McpError("SCAN_RETRIEVAL_FAILED", str(e))


@mcp.resource("catalyst://portfolio/positions/open")
async def get_open_positions(ctx: Context) -> str:
    """
    Get currently open trading positions
    
    Returns:
        JSON string with open positions
    """
    try:
        result = await call_service("trading", "GET", "/api/v1/positions/open")
        return result
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise McpError("POSITION_RETRIEVAL_FAILED", str(e))


@mcp.resource("catalyst://analytics/daily-summary")
async def get_daily_summary(ctx: Context) -> str:
    """
    Get today's trading performance summary
    
    Returns:
        JSON string with daily metrics
    """
    try:
        result = await call_service(
            "reporting", "GET", "/api/v1/analytics/daily"
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get daily summary: {e}")
        raise McpError("ANALYTICS_RETRIEVAL_FAILED", str(e))


# ============================================================================
# MCP TOOLS - Trading Operations
# ============================================================================

@mcp.tool()
async def start_trading_cycle(
    ctx: Context,
    mode: str = "normal",
    scan_frequency: int = 300,
    max_positions: int = 5,
    risk_level: float = 0.5
) -> Dict:
    """
    Start a new trading cycle
    
    Args:
        mode: Trading mode (conservative/normal/aggressive)
        scan_frequency: Seconds between market scans (60-3600)
        max_positions: Maximum concurrent positions (1-10)
        risk_level: Risk tolerance level (0.0-1.0)
        
    Returns:
        Cycle started confirmation with cycle_id
    """
    try:
        # Validate parameters
        if mode not in ["conservative", "normal", "aggressive"]:
            raise ValueError(
                f"Invalid mode: {mode}. "
                "Must be conservative, normal, or aggressive"
            )
        
        if not 60 <= scan_frequency <= 3600:
            raise ValueError(
                f"Invalid scan_frequency: {scan_frequency}. "
                "Must be between 60 and 3600 seconds"
            )
        
        if not 1 <= max_positions <= 10:
            raise ValueError(
                f"Invalid max_positions: {max_positions}. "
                "Must be between 1 and 10"
            )
        
        if not 0.0 <= risk_level <= 1.0:
            raise ValueError(
                f"Invalid risk_level: {risk_level}. "
                "Must be between 0.0 and 1.0"
            )
        
        # Check if cycle already active
        if state.current_cycle and state.current_cycle.status == "active":
            raise ValueError(
                f"Trading cycle already active: {state.current_cycle.cycle_id}"
            )
        
        # Generate cycle ID
        cycle_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Initialize scanner
        scanner_response = await call_service(
            "scanner",
            "POST",
            "/api/v1/scan/start",
            {
                "cycle_id": cycle_id,
                "scan_frequency": scan_frequency,
                "mode": mode
            }
        )
        
        # Store cycle state
        state.current_cycle = TradingCycle(
            cycle_id=cycle_id,
            status="active",
            mode=mode,
            started_at=datetime.now(),
            aggressiveness=risk_level,
            max_positions=max_positions
        )
        
        logger.info(f"Started trading cycle: {cycle_id} in {mode} mode")
        
        return {
            "success": True,
            "cycle_id": cycle_id,
            "status": "started",
            "mode": mode,
            "configuration": {
                "scan_frequency": scan_frequency,
                "max_positions": max_positions,
                "risk_level": risk_level
            },
            "scanner_status": scanner_response,
            "started_at": datetime.now().isoformat()
        }
        
    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise McpError("INVALID_PARAMETERS", str(e))
    except Exception as e:
        logger.error(f"Failed to start trading cycle: {e}", exc_info=True)
        raise McpError("CYCLE_START_FAILED", str(e))


@mcp.tool()
async def stop_trading(
    ctx: Context,
    close_positions: bool = False,
    reason: str = "manual"
) -> Dict:
    """
    Stop the current trading cycle
    
    Args:
        close_positions: If True, close all open positions
        reason: Reason for stopping (manual/scheduled/error)
        
    Returns:
        Stop confirmation with final statistics
    """
    try:
        if not state.current_cycle:
            return {
                "success": True,
                "message": "No active trading cycle to stop"
            }
        
        cycle_id = state.current_cycle.cycle_id
        
        # Stop scanner
        await call_service(
            "scanner",
            "POST",
            "/api/v1/scan/stop",
            {"cycle_id": cycle_id}
        )
        
        closed_positions = []
        if close_positions:
            # Get open positions
            positions = await call_service(
                "trading", "GET", "/api/v1/positions/open"
            )
            
            # Close each position
            for position in positions.get("positions", []):
                close_result = await call_service(
                    "trading",
                    "POST",
                    f"/api/v1/positions/{position['position_id']}/close",
                    {"reason": f"cycle_stop: {reason}"}
                )
                closed_positions.append(close_result)
        
        # Update state
        state.current_cycle.status = "stopped"
        cycle_duration = datetime.now() - state.current_cycle.started_at
        
        logger.info(f"Stopped trading cycle: {cycle_id}")
        
        result = {
            "success": True,
            "cycle_id": cycle_id,
            "status": "stopped",
            "reason": reason,
            "duration_seconds": int(cycle_duration.total_seconds()),
            "positions_closed": len(closed_positions),
            "closed_at": datetime.now().isoformat()
        }
        
        # Clear current cycle
        state.current_cycle = None
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to stop trading: {e}", exc_info=True)
        raise McpError("STOP_FAILED", str(e))


@mcp.tool()
async def analyze_symbol(
    ctx: Context,
    symbol: str,
    include_technical: bool = True,
    include_patterns: bool = True
) -> Dict:
    """
    Perform comprehensive analysis on a symbol
    
    Args:
        symbol: Stock symbol (e.g., AAPL, TSLA)
        include_technical: Include technical indicators
        include_patterns: Include pattern detection
        
    Returns:
        Complete analysis including technical and pattern data
    """
    try:
        # Validate symbol
        if not symbol or not symbol.isalpha():
            raise ValueError(f"Invalid symbol: {symbol}")
        
        symbol = symbol.upper()
        
        analysis = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat()
        }
        
        # Get technical analysis
        if include_technical:
            try:
                technical = await call_service(
                    "technical",
                    "POST",
                    "/api/v1/analyze",
                    {"symbol": symbol}
                )
                analysis["technical"] = technical
            except Exception as e:
                logger.warning(f"Technical analysis failed for {symbol}: {e}")
                analysis["technical"] = {"error": str(e)}
        
        # Get pattern analysis
        if include_patterns:
            try:
                patterns = await call_service(
                    "pattern",
                    "POST",
                    "/api/v1/detect",
                    {"symbol": symbol}
                )
                analysis["patterns"] = patterns
            except Exception as e:
                logger.warning(f"Pattern detection failed for {symbol}: {e}")
                analysis["patterns"] = {"error": str(e)}
        
        # Get news sentiment
        try:
            news = await call_service(
                "news",
                "GET",
                f"/api/v1/sentiment/{symbol}"
            )
            analysis["news_sentiment"] = news
        except Exception as e:
            logger.warning(f"News retrieval failed for {symbol}: {e}")
            analysis["news_sentiment"] = {"error": str(e)}
        
        return {
            "success": True,
            "analysis": analysis
        }
        
    except ValueError as e:
        logger.error(f"Invalid parameters: {e}")
        raise McpError("INVALID_PARAMETERS", str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise McpError("ANALYSIS_FAILED", str(e))


@mcp.tool()
async def get_risk_metrics(ctx: Context) -> Dict:
    """
    Get current risk management metrics
    
    Returns:
        Current risk parameters and exposure metrics
    """
    try:
        metrics = await call_service(
            "risk_manager", "GET", "/api/v1/metrics"
        )
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        raise McpError("RISK_METRICS_FAILED", str(e))


# ============================================================================
# INITIALIZATION AND CLEANUP
# ============================================================================

async def initialize():
    """Initialize orchestration service on startup"""
    logger.info(f"[INIT] Catalyst Orchestration Service v{SERVICE_VERSION}")
    
    try:
        # Create HTTP session for internal service calls
        state.http_session = aiohttp.ClientSession()
        logger.info("[INIT] HTTP session created")
        
        # Health check all services
        logger.info("[INIT] Checking service health...")
        health = await _get_system_health_internal()
        
        failed = health.get('failed_services', [])
        if failed:
            logger.warning(
                f"[INIT] Some services unhealthy: {failed}",
                extra={'failed_services': failed}
            )
        else:
            logger.info("[INIT] All services healthy")
        
        logger.info("[INIT] Orchestration ready for MCP connections")
        
    except Exception as e:
        logger.critical(
            f"[INIT] Initialization failed: {e}",
            exc_info=True,
            extra={'error_type': 'initialization'}
        )


async def cleanup():
    """Cleanup orchestration service on shutdown"""
    logger.info("[CLEANUP] Shutting down orchestration")
    
    try:
        # Stop any active trading cycle
        if state.current_cycle and state.current_cycle.status == "active":
            logger.info("[CLEANUP] Stopping active trading cycle")
            await stop_trading(None, close_positions=False, reason="shutdown")
        
        # Close HTTP session
        if state.http_session:
            await state.http_session.close()
            logger.info("[CLEANUP] HTTP session closed")
        
        logger.info("[CLEANUP] Orchestration stopped cleanly")
        
    except Exception as e:
        logger.error(
            f"[CLEANUP] Cleanup error: {e}",
            exc_info=True,
            extra={'error_type': 'cleanup'}
        )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Catalyst Trading MCP Orchestration Service")
    logger.info(f"Version: {SERVICE_VERSION}")
    logger.info(f"Port: {SERVICE_PORT}")
    logger.info(f"Services: {len(SERVICE_URLS)}")
    logger.info("=" * 60)
    
    # Initialize before starting server
    import asyncio
    asyncio.run(initialize())
    
    try:
        # Run FastMCP server with HTTP transport
        # This is the recommended transport for production deployments
        # Should be placed behind Nginx reverse proxy with SSL
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=SERVICE_PORT,
            path="/mcp"
        )
    finally:
        # Cleanup on exit
        asyncio.run(cleanup())
    
    # For local development with Claude Desktop on same machine:
    # mcp.run(transport="stdio")
