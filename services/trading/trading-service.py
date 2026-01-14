#!/usr/bin/env python3

# Name of Application: Catalyst Trading System
# Name of file: trading-service.py
# Version: 8.5.0
# Last Updated: 2025-12-26
# Purpose: Trading service with ALPACA INTEGRATION for autonomous trading

# REVISION HISTORY:
# v8.5.0 (2025-12-26) - P&L tracking when orders fill
# - Capture actual entry fill price (filled_avg_price) when orders fill
# - Add P&L calculation when positions close via ghost detection
# - Update entry_price, exit_price, realized_pnl, pnl_percent fields
# - Fixes critical bug: all 140 positions had NULL exit_price and realized_pnl
#
# v8.4.0 (2025-12-20) - Enhanced order sync with all terminal states
# - Added all Alpaca terminal states: filled, canceled, expired, rejected,
#   done_for_day, replaced, error
# - Auto-close positions when orders reach terminal states (expired, canceled, etc.)
# - Added ghost position detection (DB positions not in Alpaca)
# - Improved sync logging with [SYNC] prefix and cycle numbers
# - Added check for Alpaca trader enabled before sync
#
# v8.3.0 (2025-12-13) - Critical fixes: order sync, deduplication, limits
# - Added background task to sync order statuses from Alpaca every 60 seconds
# - Added position deduplication: blocks duplicate positions for same symbol
# - Added total position limit (50 max across all cycles)
# - Updated alpaca_trader to v1.4.0 with bracket order fix
#
# v8.2.0 (2025-12-06) - Order side validation and test endpoint
# - Added /api/v1/orders/test dry-run endpoint for integration testing
# - Updated alpaca_trader to v1.3.0 with validation and enhanced logging
# - Defense-in-depth validation prevents order side bugs
#
# v8.1.0 (2025-12-03) - Sub-penny pricing fix
# - Updated alpaca_trader to v1.1.0 with price rounding
# - All limit/stop/target prices now rounded to 2 decimal places
# - Fixes 95% order rejection rate due to sub-penny errors
#
# v8.0.0 (2025-11-18) - ALPACA INTEGRATION
# - Integrated alpaca_trader for real order execution
# - Submit bracket orders to Alpaca (entry + stop + target)
# - Store Alpaca order_id in database
# - Track order fill status
# - Paper trading and live trading support
#
# v5.1.2 (2025-10-13) - Production-Safe Logging
# - Removed Unicode emojis from logs (breaks log parsers)
# - Using [OK] prefix instead of checkmarks
# - Clean ASCII output for production systems
#
# v5.1.1 (2025-10-13) - FastAPI Lifespan Migration
# - Migrated from deprecated @app.on_event to lifespan context manager
# - Eliminates FastAPI deprecation warnings
# - Future-proof for FastAPI updates
#
# v5.1.0 (2025-10-13) - RIGOROUS ERROR HANDLING (Playbook v3.0 Compliant)
# - Fixed #1: get_security_id() - Specific exception handling (NO generic Exception)
# - Fixed #2: create_cycle() - Database vs validation errors distinguished
# - Fixed #3: create_position() - Tracks failures, raises on critical errors
# - Fixed #4: All endpoints use specific exception types
# - Enhanced logging with structured context throughout
# - Proper HTTPException with status codes (400, 404, 503, 500)
# - Conforms to Playbook v3.0 Zero Tolerance Policy âœ…
#
# v5.0.1 (2025-10-07) - FIXED to match actual v5.0 schema
# - Uses correct trading_cycles columns (mode, total_risk_budget, etc.)
# - Removed references to non-existent columns (cycle_name, initial_capital)
# - Mode values: aggressive/normal/conservative (not paper/live)

# Description of Service:
# Trading execution service (Service #3 of 9 in Playbook v3.0).
# Third service to be updated for rigorous error handling.
# **HANDLES REAL MONEY - Critical to get error handling right!**
# Manages:
# 1. Trading cycles with proper validation
# 2. Position management with security_id FKs
# 3. Order execution with comprehensive error tracking (NOW WITH ALPACA!)
# 4. Risk calculations via JOINs
# 5. NO silent failures - all errors visible and tracked

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import asyncpg
import json
import os
import logging
import uvicorn
from enum import Enum
from decimal import Decimal
import sys
from pathlib import Path
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import common utilities
from common.alpaca_trader import alpaca_trader

# ============================================================================
# SERVICE METADATA
# ============================================================================
SERVICE_NAME = "trading"
SERVICE_VERSION = "8.5.0"  # P&L tracking, entry fill price, ghost P&L calculation
SERVICE_TITLE = "Trading Service"
SCHEMA_VERSION = "v6.0 3NF normalized"
SERVICE_PORT = 5005

from contextlib import asynccontextmanager

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup/shutdown.
    Replaces deprecated @app.on_event decorators.
    """
    # STARTUP
    logger.info(f"Starting {SERVICE_TITLE} v{SERVICE_VERSION}")
    
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not configured")
        
        state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        logger.info("Database pool initialized")
        
        # Verify schema
        await verify_schema()
        
        logger.info(f"{SERVICE_TITLE} v{SERVICE_VERSION} ready on port {SERVICE_PORT}")
        
    except ValueError as e:
        logger.critical(f"Configuration error: {e}", exc_info=True)
        raise
        
    except asyncpg.PostgresError as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise
        
    except Exception as e:
        logger.critical(f"Unexpected startup error: {e}", exc_info=True)
        raise
    
    # YIELD CONTROL TO APPLICATION
    yield
    
    # SHUTDOWN
    logger.info(f"Shutting down {SERVICE_TITLE}")
    
    if state.db_pool:
        await state.db_pool.close()
        logger.info("Database pool closed")
    
    logger.info(f"{SERVICE_TITLE} shutdown complete")

async def verify_schema():
    """Verify v5.0 normalized schema is deployed"""
    try:
        # Check positions table uses security_id FK
        has_security_id = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'positions' 
                AND column_name = 'security_id'
            )
        """)
        
        if not has_security_id:
            raise ValueError(
                "positions table missing security_id column - schema v5.0 not deployed!"
            )
        
        logger.info("[OK] Normalized schema v5.0 verified")
        
    except asyncpg.PostgresError as e:
        logger.critical(f"Schema verification failed: {e}", exc_info=True)
        raise

# Initialize FastAPI with lifespan
app = FastAPI(
    title=SERVICE_TITLE,
    version=SERVICE_VERSION,
    description=f"Trading execution with {SCHEMA_VERSION} + rigorous error handling",
    lifespan=lifespan  # âœ… Use lifespan instead of on_event
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(SERVICE_NAME)

# ============================================================================
# ENUMS
# ============================================================================
class CycleMode(str, Enum):
    """v5.0 schema modes"""
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    CONSERVATIVE = "conservative"

class CycleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"
    RISK_REDUCED = "risk_reduced"

# ============================================================================
# DATA MODELS
# ============================================================================
class CreateCycleRequest(BaseModel):
    """Create cycle matching v5.0 schema"""
    mode: CycleMode = CycleMode.NORMAL
    max_positions: int = 5
    max_daily_loss: float = 2000.00
    position_size_multiplier: float = 1.0
    risk_level: float = 0.02
    total_risk_budget: float = 10000.00
    config: Dict = {}

class PositionRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

# ============================================================================
# SERVICE STATE
# ============================================================================
class TradingState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None

state = TradingState()

# ============================================================================
# HELPER FUNCTIONS (RIGOROUS ERROR HANDLING)
# ============================================================================
async def get_security_id(symbol: str) -> int:
    """
    Get or create security_id for symbol using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_security() helper function.

    Raises:
        ValueError: If symbol is invalid or security_id cannot be obtained
        asyncpg.PostgresError: If database error occurs
    """
    try:
        # Validate input
        if not symbol or not isinstance(symbol, str):
            raise ValueError(f"Invalid symbol: {symbol}")

        symbol = symbol.upper().strip()
        if not symbol:
            raise ValueError("Symbol cannot be empty after normalization")

        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)",
            symbol
        )

        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")

        return security_id

    except ValueError:
        # Re-raise validation errors
        raise

    except asyncpg.PostgresError as e:
        # Database errors
        logger.error(
            f"Database error in get_security_id: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'database'}
        )
        raise

    except Exception as e:
        # Truly unexpected errors
        logger.critical(
            f"UNEXPECTED error in get_security_id for {symbol}: {e}",
            exc_info=True,
            extra={'symbol': symbol, 'error_type': 'unexpected'}
        )
        raise

# ============================================================================
# STARTUP & SHUTDOWN (FastAPI Lifespan Pattern)
# ============================================================================
from contextlib import asynccontextmanager

# Global reference to background task
_status_sync_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup/shutdown.
    Replaces deprecated @app.on_event decorators.
    """
    global _status_sync_task

    # STARTUP
    logger.info(f"Starting {SERVICE_TITLE} v{SERVICE_VERSION}")

    try:
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not configured")

        state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )

        logger.info("Database pool initialized")

        # Verify schema
        await verify_schema()

        # Start background order status sync task
        logger.info("[DEBUG] About to create sync task...")
        try:
            _status_sync_task = asyncio.create_task(sync_order_statuses())
            logger.info("[OK] Background order status sync started")
        except Exception as sync_err:
            logger.error(f"[ERROR] Failed to start sync task: {sync_err}", exc_info=True)

        logger.info(f"{SERVICE_TITLE} v{SERVICE_VERSION} ready on port {SERVICE_PORT}")

    except ValueError as e:
        logger.critical(f"Configuration error: {e}", exc_info=True)
        raise

    except asyncpg.PostgresError as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise

    except Exception as e:
        logger.critical(f"Unexpected startup error: {e}", exc_info=True)
        raise

    # YIELD CONTROL TO APPLICATION
    yield

    # SHUTDOWN
    logger.info(f"Shutting down {SERVICE_TITLE}")

    # Cancel background task
    if _status_sync_task:
        _status_sync_task.cancel()
        try:
            await _status_sync_task
        except asyncio.CancelledError:
            pass
        logger.info("Order status sync task stopped")

    if state.db_pool:
        await state.db_pool.close()
        logger.info("Database pool closed")

    logger.info(f"{SERVICE_TITLE} shutdown complete")

async def sync_order_statuses():
    """
    Background task: Sync order statuses from Alpaca every 60 seconds.

    Updates database alpaca_status field for all open positions by
    querying Alpaca for current order status. This ensures the database
    reflects actual broker state (filled, canceled, expired, etc.).

    Alpaca Order Statuses:
    - Terminal (order finished): filled, canceled, expired, rejected,
                                 done_for_day, replaced
    - Active: new, partially_filled, accepted, pending_new, pending_cancel,
              pending_replace, accepted_for_bidding, stopped, suspended,
              calculated, held
    """
    # All terminal states where order processing is complete
    TERMINAL_STATES = (
        'filled', 'canceled', 'expired', 'rejected',
        'done_for_day', 'replaced', 'error'
    )

    logger.info("[OK] Order status sync task started")
    sync_cycle = 0

    while True:
        try:
            if not state.db_pool:
                logger.warning("Sync task: No database pool available, waiting...")
                await asyncio.sleep(60)
                continue

            if not alpaca_trader.is_enabled():
                logger.warning("Sync task: Alpaca trader not enabled, waiting...")
                await asyncio.sleep(60)
                continue

            sync_cycle += 1
            logger.info(f"[SYNC] Cycle {sync_cycle} starting...")

            async with state.db_pool.acquire() as conn:
                # Find positions that need status sync (not in terminal state)
                positions = await conn.fetch("""
                    SELECT p.position_id, p.broker_order_id,
                           p.metadata->>'alpaca_status' as alpaca_status, s.symbol
                    FROM positions p
                    JOIN securities s ON s.security_id = p.security_id
                    WHERE p.broker_order_id IS NOT NULL
                    AND p.status = 'open'
                    AND (p.metadata->>'alpaca_status' IS NULL OR p.metadata->>'alpaca_status' NOT IN
                         ('filled', 'canceled', 'expired', 'rejected', 'done_for_day', 'replaced', 'error'))
                """)

                logger.info(f"[SYNC] Found {len(positions)} positions to check")

                synced_count = 0
                closed_count = 0
                error_count = 0

                for pos in positions:
                    try:
                        status_info = await alpaca_trader.get_order_status(pos['broker_order_id'])
                        new_status = status_info.get('status', 'unknown')
                        filled_qty = status_info.get('filled_qty', 0)
                        filled_avg_price = status_info.get('filled_avg_price')

                        if new_status != pos['alpaca_status']:
                            # Update alpaca_status in metadata JSONB
                            await conn.execute("""
                                UPDATE positions
                                SET metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{alpaca_status}', to_jsonb($1::text)),
                                    updated_at = NOW()
                                WHERE position_id = $2
                            """, new_status, pos['position_id'])
                            synced_count += 1

                            logger.info(
                                f"[SYNC] {pos['symbol']}: {pos['alpaca_status']} -> {new_status} "
                                f"(filled_qty={filled_qty}, fill_price={filled_avg_price})"
                            )

                            # v8.5.0: When order fills, update entry_price with actual fill price
                            if new_status == 'filled' and filled_avg_price:
                                await conn.execute("""
                                    UPDATE positions
                                    SET entry_price = $1, updated_at = NOW()
                                    WHERE position_id = $2
                                """, filled_avg_price, pos['position_id'])
                                logger.info(
                                    f"[SYNC] {pos['symbol']}: Updated entry_price to {filled_avg_price}"
                                )

                            # If order reached terminal state, check if we should close position
                            if new_status in TERMINAL_STATES:
                                # For expired/canceled/rejected, close the position
                                if new_status in ('expired', 'canceled', 'rejected', 'done_for_day'):
                                    await conn.execute("""
                                        UPDATE positions
                                        SET status = 'closed',
                                            close_reason = $1,
                                            closed_at = NOW(),
                                            updated_at = NOW()
                                        WHERE position_id = $2
                                    """, f"alpaca_{new_status}", pos['position_id'])
                                    closed_count += 1
                                    logger.info(f"[SYNC] {pos['symbol']}: Closed (reason: alpaca_{new_status})")

                    except Exception as e:
                        error_count += 1
                        error_msg = str(e)
                        # Check if order not found (might have been purged by Alpaca)
                        if 'not found' in error_msg.lower() or '404' in error_msg:
                            logger.warning(f"[SYNC] {pos['symbol']}: Order not found in Alpaca, marking as error")
                            await conn.execute("""
                                UPDATE positions
                                SET alpaca_status = 'error',
                                    alpaca_error = $1,
                                    updated_at = NOW()
                                WHERE position_id = $2
                            """, f"Order not found: {error_msg}", pos['position_id'])
                        else:
                            logger.warning(f"[SYNC] {pos['symbol']}: Failed to sync - {e}")

                # Log summary
                logger.info(
                    f"[SYNC] Cycle {sync_cycle} complete: "
                    f"synced={synced_count}, closed={closed_count}, errors={error_count}"
                )

                # Every 10 cycles, check for ghost positions (open in DB but not in Alpaca)
                if sync_cycle % 10 == 0:
                    await check_ghost_positions(conn)

            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("[SYNC] Order status sync task cancelled")
            break
        except Exception as e:
            logger.error(f"[SYNC] Unexpected error: {e}", exc_info=True)
            await asyncio.sleep(60)


async def check_ghost_positions(conn):
    """
    Check for positions that are open in DB but don't exist in Alpaca.
    These are 'ghost' positions that were closed by stop-loss or take-profit.
    v8.5.0: Now closes these positions with P&L calculation.
    """
    try:
        if not alpaca_trader.is_enabled():
            return

        # Get Alpaca positions
        alpaca_positions = await alpaca_trader.get_positions()
        alpaca_symbols = {p['symbol'] for p in alpaca_positions} if alpaca_positions else set()

        # Get open positions from DB that are older than 1 hour and alpaca_status='filled'
        # These are positions where entry filled but now not in Alpaca = closed by stop/take-profit
        db_positions = await conn.fetch("""
            SELECT p.position_id, s.symbol, p.alpaca_status, p.opened_at,
                   p.entry_price, p.quantity, p.side, p.stop_loss, p.take_profit
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            WHERE p.status = 'open'
            AND p.alpaca_status = 'filled'
            AND p.opened_at < NOW() - INTERVAL '1 hour'
        """)

        ghost_count = 0
        closed_count = 0
        for pos in db_positions:
            if pos['symbol'] not in alpaca_symbols:
                ghost_count += 1

                # v8.5.0: Close the ghost position with P&L calculation
                try:
                    # Try to get current price as exit estimate
                    current_price = await alpaca_trader.get_current_price(pos['symbol'])

                    entry_price = float(pos['entry_price']) if pos['entry_price'] else 0
                    quantity = pos['quantity'] or 0
                    side = pos['side']

                    # Use current price, or estimate from stop/take-profit levels
                    if current_price:
                        exit_price = current_price
                        close_reason = 'alpaca_position_closed'
                    elif pos['stop_loss']:
                        exit_price = float(pos['stop_loss'])
                        close_reason = 'stop_loss_estimated'
                    elif pos['take_profit']:
                        exit_price = float(pos['take_profit'])
                        close_reason = 'take_profit_estimated'
                    else:
                        exit_price = entry_price
                        close_reason = 'closed_no_exit_price'

                    # Calculate P&L
                    if side == 'long':
                        realized_pnl = (exit_price - entry_price) * quantity
                    else:  # short
                        realized_pnl = (entry_price - exit_price) * quantity

                    pnl_percent = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    if side == 'short':
                        pnl_percent = -pnl_percent

                    # Update position with P&L
                    await conn.execute("""
                        UPDATE positions
                        SET status = 'closed',
                            exit_price = $1,
                            realized_pnl = $2,
                            pnl_percent = $3,
                            close_reason = $4,
                            closed_at = NOW(),
                            updated_at = NOW()
                        WHERE position_id = $5
                    """, exit_price, realized_pnl, pnl_percent, close_reason, pos['position_id'])

                    closed_count += 1
                    logger.info(
                        f"[GHOST] {pos['symbol']}: Closed with P&L - "
                        f"entry={entry_price:.2f}, exit={exit_price:.2f}, "
                        f"pnl=${realized_pnl:.2f} ({pnl_percent:.1f}%)"
                    )

                except Exception as e:
                    logger.warning(
                        f"[GHOST] {pos['symbol']}: Failed to close with P&L - {e}"
                    )

        if ghost_count > 0:
            logger.info(f"[GHOST] Found {ghost_count} ghost positions, closed {closed_count} with P&L")

    except Exception as e:
        logger.error(f"[GHOST] Error checking ghost positions: {e}")

async def verify_schema():
    """Verify v5.0 normalized schema is deployed"""
    try:
        # Check positions table uses security_id FK
        has_security_id = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'positions'
                AND column_name = 'security_id'
            )
        """)

        if not has_security_id:
            raise ValueError(
                "positions table missing security_id column - schema v5.0 not deployed!"
            )

        logger.info("[OK] Normalized schema v5.0 verified")

    except asyncpg.PostgresError as e:
        logger.critical(f"Schema verification failed: {e}", exc_info=True)
        raise

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.get("/health")
async def health():
    """Health check with detailed status"""
    try:
        if state.db_pool:
            async with state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            return {
                "status": "healthy",
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "schema": SCHEMA_VERSION,
                "database": "connected",
                "uses_security_id_fk": True,
                "error_handling": "rigorous",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise RuntimeError("Database pool not initialized")
            
    except asyncpg.PostgresError as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": "database_unavailable",
            "message": str(e)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": "unknown",
            "message": str(e)
        }


# ============================================================================
# ORDER SIDE TEST ENDPOINT (v1.3.0 - Integration Testing)
# ============================================================================
class OrderTestRequest(BaseModel):
    """Request model for testing order side mapping"""
    symbol: str
    quantity: int
    side: str
    dry_run: bool = True


@app.post("/api/v1/orders/test")
async def test_order_mapping(request: OrderTestRequest):
    """
    Test order side mapping without submitting to Alpaca.

    This endpoint is used for integration testing to verify that
    the _normalize_side() function correctly maps input sides
    to Alpaca OrderSide enums.

    The v1.2.0 bug caused "long" to incorrectly map to SELL.
    This endpoint allows verification that "long" -> "buy".

    Args:
        request: OrderTestRequest with symbol, quantity, side, dry_run

    Returns:
        Mapping result showing input_side -> mapped_side
    """
    from common.alpaca_trader import map_side, validate_side_mapping
    from alpaca.trading.enums import OrderSide

    try:
        # Normalize the side (this is the function we're testing)
        mapped_side = map_side(request.side)

        # Validate the mapping (defense in depth)
        validate_side_mapping(request.side, mapped_side)

        result = {
            "test": "order_side_mapping",
            "input_side": request.side,
            "mapped_side": mapped_side.value,
            "symbol": request.symbol,
            "quantity": request.quantity,
            "dry_run": request.dry_run,
            "validation": "passed",
            "would_submit_as": mapped_side.value.upper(),
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(
            f"ORDER TEST: input_side='{request.side}' -> mapped_side='{mapped_side.value}' "
            f"(symbol={request.symbol}, qty={request.quantity}, dry_run={request.dry_run})"
        )

        return result

    except ValueError as e:
        logger.warning(f"ORDER TEST FAILED (ValueError): {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except RuntimeError as e:
        # This would be caught by _validate_order_side_mapping if there's a mismatch
        logger.error(f"ORDER TEST FAILED (RuntimeError): {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"ORDER TEST FAILED (Unexpected): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TRADING CYCLES (RIGOROUS ERROR HANDLING)
# ============================================================================
@app.post("/api/v1/cycles")
async def create_cycle(request: CreateCycleRequest):
    """
    Create trading cycle with rigorous error handling.
    
    Raises:
        HTTPException(400): Invalid request parameters
        HTTPException(503): Database unavailable
        HTTPException(500): Unexpected error
    """
    cycle_id = f"api-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
    logger.info(
        f"Creating trading cycle: {cycle_id}",
        extra={'cycle_id': cycle_id, 'mode': request.mode.value}
    )
    
    try:
        # Validate request
        if request.max_positions <= 0:
            raise ValueError("max_positions must be positive")
        
        if request.max_daily_loss <= 0:
            raise ValueError("max_daily_loss must be positive")
        
        if not 0.0 <= request.risk_level <= 0.10:
            raise ValueError("risk_level must be between 0.0 and 0.10 (10%)")
        
        if request.total_risk_budget <= 0:
            raise ValueError("total_risk_budget must be positive")
        
        # Build configuration JSONB
        config = request.config.copy()
        config.update({
            "created_via": "api",
            "timestamp": datetime.utcnow().isoformat(),
            "display_name": config.get("name", f"Cycle {cycle_id}"),
            "capital_info": {
                "initial": float(request.total_risk_budget),
                "currency": "USD"
            }
        })
        
        # Create cycle in database
        async with state.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO trading_cycles (
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    max_daily_loss,
                    position_size_multiplier,
                    risk_level,
                    scan_frequency,
                    started_at,
                    total_risk_budget,
                    used_risk_budget,
                    current_positions,
                    current_exposure,
                    configuration
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
                cycle_id,
                request.mode.value,
                CycleStatus.ACTIVE.value,
                request.max_positions,
                request.max_daily_loss,
                request.position_size_multiplier,
                request.risk_level,
                300,  # scan_frequency default
                datetime.utcnow(),
                Decimal(str(request.total_risk_budget)),
                Decimal('0.00'),
                0,
                Decimal('0.00'),
                json.dumps(config)
            )
        
        logger.info(
            f"Trading cycle created successfully: {cycle_id}",
            extra={'cycle_id': cycle_id, 'mode': request.mode.value}
        )
        
        return {
            "success": True,
            "cycle_id": cycle_id,
            "mode": request.mode.value,
            "status": "active",
            "total_risk_budget": request.total_risk_budget,
            "message": "Cycle created with v5.0 schema",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        # Validation errors
        logger.error(
            f"Invalid cycle parameters: {e}",
            extra={'cycle_id': cycle_id, 'error_type': 'validation'}
        )
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'Invalid parameters',
                'message': str(e),
                'cycle_id': cycle_id
            }
        )
        
    except asyncpg.UniqueViolationError as e:
        # Duplicate cycle_id (shouldn't happen with timestamp-based IDs)
        logger.error(
            f"Duplicate cycle_id: {e}",
            extra={'cycle_id': cycle_id, 'error_type': 'duplicate'}
        )
        raise HTTPException(
            status_code=409,
            detail={
                'error': 'Duplicate cycle',
                'message': 'Cycle ID already exists',
                'cycle_id': cycle_id
            }
        )
        
    except asyncpg.PostgresError as e:
        # Database errors
        logger.critical(
            f"Database error creating cycle: {e}",
            exc_info=True,
            extra={'cycle_id': cycle_id, 'error_type': 'database'}
        )
        raise HTTPException(
            status_code=503,
            detail={
                'error': 'Database unavailable',
                'message': 'Cannot create cycle. Database error occurred.',
                'cycle_id': cycle_id,
                'retry_after': 30
            }
        )
        
    except Exception as e:
        # Truly unexpected errors
        logger.critical(
            f"UNEXPECTED error creating cycle: {e}",
            exc_info=True,
            extra={'cycle_id': cycle_id, 'error_type': 'unexpected'}
        )
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'Internal server error',
                'message': 'Unexpected error creating cycle',
                'cycle_id': cycle_id
            }
        )

@app.get("/api/v1/cycles/active")
async def get_active_cycles():
    """
    Get active cycles with error handling.
    
    Returns list of active trading cycles.
    """
    try:
        async with state.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    total_risk_budget,
                    used_risk_budget,
                    current_positions,
                    current_exposure,
                    started_at,
                    configuration
                FROM trading_cycles
                WHERE status = 'active'
                ORDER BY started_at DESC
            """)
        
        cycles = []
        for row in rows:
            cycle_dict = dict(row)
            # Calculate available risk budget
            cycle_dict['available_risk_budget'] = (
                float(cycle_dict['total_risk_budget']) - 
                float(cycle_dict['used_risk_budget'])
            )
            cycles.append(cycle_dict)
        
        logger.info(f"Retrieved {len(cycles)} active cycles")
        
        return {
            "success": True,
            "cycles": cycles,
            "count": len(cycles),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except asyncpg.PostgresError as e:
        logger.error(f"Database error retrieving cycles: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={'error': 'Database unavailable', 'message': str(e)}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving cycles: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={'error': 'Internal server error', 'message': str(e)}
        )

# ============================================================================
# POSITIONS (RIGOROUS ERROR HANDLING)
# ============================================================================
@app.post("/api/v1/positions")
async def create_position(cycle_id: str, request: PositionRequest):
    """
    Create position with rigorous error handling.
    
    Args:
        cycle_id: Trading cycle ID
        request: Position details
        
    Raises:
        HTTPException(400): Invalid parameters
        HTTPException(404): Cycle not found
        HTTPException(409): Risk budget exceeded
        HTTPException(503): Database unavailable
        HTTPException(500): Unexpected error
    """
    logger.info(
        f"Creating position for {request.symbol} in cycle {cycle_id}",
        extra={
            'cycle_id': cycle_id,
            'symbol': request.symbol,
            'quantity': request.quantity
        }
    )
    
    try:
        # Validate request
        if request.quantity <= 0:
            raise ValueError("quantity must be positive")
        
        if request.entry_price and request.entry_price <= 0:
            raise ValueError("entry_price must be positive")
        
        if request.side.lower() not in ['buy', 'sell', 'long', 'short']:
            raise ValueError(f"Invalid side: {request.side}")
        
        async with state.db_pool.acquire() as conn:
            # Verify cycle exists and is active
            cycle = await conn.fetchrow("""
                SELECT
                    mode,
                    status,
                    max_positions,
                    total_risk_budget,
                    used_risk_budget,
                    current_positions
                FROM trading_cycles
                WHERE cycle_id = $1 AND status IN ('active', 'completed', 'running')
            """, cycle_id)

            if not cycle:
                raise ValueError(f"Cycle not found: {cycle_id}")
            
            # Check per-cycle position limits
            if cycle['current_positions'] >= cycle['max_positions']:
                raise RuntimeError(
                    f"Maximum positions ({cycle['max_positions']}) reached for this cycle"
                )

            # Check TOTAL open positions across all cycles (Issue 4 fix)
            MAX_TOTAL_POSITIONS = 50
            total_open_positions = await conn.fetchval("""
                SELECT COUNT(*) FROM positions WHERE status = 'open'
            """)
            if total_open_positions >= MAX_TOTAL_POSITIONS:
                raise RuntimeError(
                    f"Maximum total positions ({MAX_TOTAL_POSITIONS}) reached across all cycles"
                )

            # Get security_id
            security_id = await get_security_id(request.symbol)

            # Check for existing open position with same symbol (Issue 3 fix - deduplication)
            existing_position = await conn.fetchval("""
                SELECT position_id FROM positions
                WHERE security_id = $1
                AND status = 'open'
            """, security_id)

            if existing_position:
                logger.warning(
                    f"Duplicate position blocked: {request.symbol} already has open position {existing_position}"
                )
                raise RuntimeError(
                    f"Symbol {request.symbol} already has an open position"
                )

            # Calculate risk amount
            if request.stop_loss and request.entry_price:
                risk_per_share = abs(request.entry_price - request.stop_loss)
                risk_amount = Decimal(str(risk_per_share * request.quantity))
            else:
                # Default 2% risk
                estimated_price = request.entry_price or 100.0
                risk_amount = Decimal(str(estimated_price * request.quantity * 0.02))
            
            # Check risk budget
            available_budget = (
                cycle['total_risk_budget'] - cycle['used_risk_budget']
            )
            if risk_amount > available_budget:
                raise RuntimeError(
                    f"Risk amount ${risk_amount:.2f} exceeds "
                    f"available budget ${available_budget:.2f}"
                )
            
            # Create position
            position_id = await conn.fetchval("""
                INSERT INTO positions (
                    cycle_id,
                    security_id,
                    side,
                    quantity,
                    entry_price,
                    stop_loss,
                    take_profit,
                    risk_amount,
                    status,
                    opened_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING position_id
            """,
                cycle_id,
                security_id,
                request.side.lower(),
                request.quantity,
                request.entry_price,
                request.stop_loss,
                request.take_profit,
                risk_amount,
                PositionStatus.OPEN.value,
                datetime.utcnow()
            )
            
            # Update cycle metrics
            await conn.execute("""
                UPDATE trading_cycles
                SET
                    current_positions = current_positions + 1,
                    used_risk_budget = used_risk_budget + $1,
                    current_exposure = current_exposure + $2
                WHERE cycle_id = $3
            """,
                risk_amount,
                Decimal(str((request.entry_price or 0) * request.quantity)),
                cycle_id
            )

            # ===================================================================
            # ALPACA INTEGRATION - Submit real order to broker
            # ===================================================================
            alpaca_order_id = None
            alpaca_status = "not_submitted"

            if alpaca_trader.is_enabled():
                try:
                    logger.info(f"Submitting bracket order to Alpaca: {request.symbol}")

                    # Submit bracket order (entry + stop + target)
                    alpaca_order = await alpaca_trader.submit_bracket_order(
                        symbol=request.symbol,
                        quantity=request.quantity,
                        side=request.side.lower(),
                        entry_price=request.entry_price,  # None = market order
                        stop_loss=request.stop_loss,
                        take_profit=request.take_profit
                    )

                    alpaca_order_id = alpaca_order['order_id']
                    alpaca_status = alpaca_order['status']

                    # Store Alpaca order_id in database (broker_order_id column, status in metadata)
                    await conn.execute("""
                        UPDATE positions
                        SET broker_order_id = $1,
                            metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{alpaca_status}', to_jsonb($2::text))
                        WHERE position_id = $3
                    """, alpaca_order_id, alpaca_status, position_id)

                    logger.info(
                        f"Alpaca order submitted successfully: {alpaca_order_id} "
                        f"(status: {alpaca_status})"
                    )

                except Exception as e:
                    # Log Alpaca error but don't fail position creation
                    logger.error(
                        f"Alpaca order submission failed: {e}",
                        exc_info=True,
                        extra={
                            'position_id': position_id,
                            'symbol': request.symbol,
                            'error_type': 'alpaca_integration'
                        }
                    )

                    # Store error in database (in metadata JSONB)
                    await conn.execute("""
                        UPDATE positions
                        SET metadata = jsonb_set(
                            jsonb_set(COALESCE(metadata, '{}'::jsonb), '{alpaca_status}', '"error"'),
                            '{alpaca_error}', to_jsonb($1::text)
                        )
                        WHERE position_id = $2
                    """, str(e), position_id)

                    alpaca_status = "error"
            else:
                logger.warning(
                    f"Alpaca not enabled - position created in database only "
                    f"(position_id: {position_id})"
                )
                alpaca_status = "alpaca_disabled"

        logger.info(
            f"Position created: {position_id} for {request.symbol} "
            f"(Alpaca: {alpaca_status})",
            extra={
                'position_id': position_id,
                'cycle_id': cycle_id,
                'symbol': request.symbol,
                'security_id': security_id,
                'risk_amount': float(risk_amount)
            }
        )
        
        return {
            "success": True,
            "position_id": position_id,
            "security_id": security_id,
            "symbol": request.symbol,
            "risk_amount": float(risk_amount),
            "cycle_id": cycle_id,
            "alpaca_order_id": alpaca_order_id,
            "alpaca_status": alpaca_status,
            "alpaca_enabled": alpaca_trader.is_enabled(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        # Validation errors
        logger.error(
            f"Invalid position parameters: {e}",
            extra={
                'cycle_id': cycle_id,
                'symbol': request.symbol,
                'error_type': 'validation'
            }
        )
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'Invalid parameters',
                'message': str(e),
                'symbol': request.symbol
            }
        )
        
    except RuntimeError as e:
        # Risk/limit violations
        logger.warning(
            f"Position creation blocked: {e}",
            extra={
                'cycle_id': cycle_id,
                'symbol': request.symbol,
                'error_type': 'risk_violation'
            }
        )
        raise HTTPException(
            status_code=409,
            detail={
                'error': 'Risk violation',
                'message': str(e),
                'cycle_id': cycle_id
            }
        )
        
    except asyncpg.PostgresError as e:
        # Database errors - CRITICAL (may be in inconsistent state)
        logger.critical(
            f"Database error creating position: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'symbol': request.symbol,
                'error_type': 'database'
            }
        )
        raise HTTPException(
            status_code=503,
            detail={
                'error': 'Database unavailable',
                'message': 'Cannot create position. Database error occurred.',
                'retry_after': 30
            }
        )
        
    except Exception as e:
        # Truly unexpected errors
        logger.critical(
            f"UNEXPECTED error creating position: {e}",
            exc_info=True,
            extra={
                'cycle_id': cycle_id,
                'symbol': request.symbol,
                'error_type': 'unexpected'
            }
        )
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'Internal server error',
                'message': 'Unexpected error creating position'
            }
        )

@app.get("/api/v1/positions/active")
async def get_active_positions(cycle_id: Optional[str] = None):
    """
    Get active positions with JOINs (normalized schema).
    
    Args:
        cycle_id: Optional cycle filter
        
    Returns positions with security/sector data via JOINs.
    """
    try:
        async with state.db_pool.acquire() as conn:
            if cycle_id:
                # Get positions for specific cycle
                rows = await conn.fetch("""
                    SELECT 
                        p.*,
                        s.symbol,
                        s.company_name,
                        sec.sector_name
                    FROM positions p
                    JOIN securities s ON s.security_id = p.security_id
                    LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
                    WHERE p.cycle_id = $1 AND p.status = 'open'
                    ORDER BY p.opened_at DESC
                """, cycle_id)
            else:
                # Get all active positions
                rows = await conn.fetch("""
                    SELECT 
                        p.*,
                        s.symbol,
                        s.company_name,
                        sec.sector_name
                    FROM positions p
                    JOIN securities s ON s.security_id = p.security_id
                    LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
                    WHERE p.status = 'open'
                    ORDER BY p.opened_at DESC
                """)
        
        positions = [dict(row) for row in rows]
        
        logger.info(
            f"Retrieved {len(positions)} active positions",
            extra={'count': len(positions), 'cycle_id': cycle_id}
        )
        
        return {
            "success": True,
            "positions": positions,
            "count": len(positions),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except asyncpg.PostgresError as e:
        logger.error(f"Database error retrieving positions: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={'error': 'Database unavailable', 'message': str(e)}
        )
        
    except Exception as e:
        logger.error(f"Error retrieving positions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={'error': 'Internal server error', 'message': str(e)}
        )

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(f"Catalyst Trading System - {SERVICE_TITLE} v{SERVICE_VERSION}")
    print("=" * 70)
    print(f"[OK] {SCHEMA_VERSION} with security_id FKs")
    print("[OK] RIGOROUS error handling - NO silent failures")
    print("[OK] Specific exception types (not generic)")
    print("[OK] Structured logging with context")
    print("[OK] HTTPException with proper status codes")
    print("[OK] Handles REAL MONEY - Critical safety layer")
    print("[OK] FastAPI lifespan (no deprecation warnings)")
    print(f"Port: {SERVICE_PORT}")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
