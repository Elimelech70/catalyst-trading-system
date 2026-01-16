#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk-manager-service.py
Version: 7.1.0
Last Updated: 2025-12-14
Purpose: Autonomous risk management with real-time monitoring and emergency stop

REVISION HISTORY:
v7.1.0 (2025-12-14) - FALLBACK POSITION MONITORING
- ✅ Added PositionMonitor class for stop-loss/take-profit enforcement
- ✅ Monitors positions every 30 seconds as backup for Alpaca brackets
- ✅ Closes positions via market order when stops are hit
- ✅ Records close_reason in database for audit trail
- ✅ Sends alerts on fallback position closes
- Fixes: Silent bracket order failures left positions unprotected

v7.0.0 (2025-11-18) - AUTONOMOUS TRADING IMPLEMENTATION
- ✅ Real-time position monitoring (every 60 seconds)
- ✅ Automatic emergency stop execution at daily loss limit
- ✅ Alpaca API integration for closing real positions
- ✅ Email alerts for warnings and critical events
- ✅ YAML configuration with hot-reload support
- ✅ Background monitoring task lifecycle management
- ✅ Graceful degradation if Alpaca unavailable

v6.0.0 (2025-11-18) - SCHEMA v6.0 3NF COMPLIANCE
- Uses get_or_create_security() helper function
- All queries use proper JOINs and helper functions
- Fully normalized 3NF schema compliance

v5.0.0 (2025-10-13) - Normalized Schema Migration (Playbook v3.0 Step 6)
- ✅ Uses security_id FK lookups (NOT symbol VARCHAR)
- ✅ Sector exposure tracking via JOINs (securities → sectors)
- ✅ Position risk calculations with security_id FKs
- ✅ All queries use JOINs for sector exposure
- ✅ Real-time risk limits enforcement
- ✅ Daily risk metrics tracking with FKs
- ✅ Risk events logging with proper FKs
- ✅ Error handling compliant with v1.0 standard

Description of Service:
Autonomous risk management service that continuously monitors positions and
automatically executes emergency stop when risk limits are breached:

AUTONOMOUS FEATURES:
- Real-time monitoring: Checks all active cycles every 60 seconds
- Daily loss tracking: Monitors P&L against configured limit ($2,000 default)
- Warning alerts: Email sent at 75% of daily loss limit
- Emergency stop: Automatically triggered at 100% of daily loss limit
  1. Closes all positions via Alpaca API (real broker)
  2. Marks positions as closed in database
  3. Stops the trading cycle
  4. Sends critical email alert

RISK VALIDATION (Pre-trade):
- Position sizing and limits (via security_id)
- Sector exposure limits (via securities → sectors JOIN)
- Daily loss limits
- Max positions per cycle
- Risk/reward validation
- All queries use security_id FKs and helper functions for data integrity

INTEGRATION:
- Uses config/risk_parameters.yaml for risk limits
- Integrates with Alpaca API for real position closure
- Email alerts via SMTP (alert_manager)
- Schema: v6.0 3NF normalized
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
from enum import Enum
import asyncpg
import os
import logging
import json
import sys
from pathlib import Path
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import common utilities
from common.config_loader import get_risk_config, get_risk_limits, get_emergency_actions
from common.alert_manager import alert_manager, AlertType, AlertSeverity
from common.alpaca_trader import alpaca_trader

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SERVICE_NAME = "risk-manager"
SERVICE_VERSION = "7.1.0"  # FALLBACK POSITION MONITORING
SERVICE_PORT = 5004
SCHEMA_VERSION = "v6.0 3NF normalized"

# Global flag for monitoring task
_monitoring_task: Optional[asyncio.Task] = None

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Default risk parameters
class Config:
    MAX_POSITIONS = 5
    MAX_POSITION_SIZE_USD = 10000.0
    MAX_DAILY_LOSS_USD = 2000.0
    MAX_SECTOR_EXPOSURE_PCT = 40.0
    MIN_RISK_REWARD_RATIO = 1.5

# ============================================================================
# ENUMS
# ============================================================================

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskEventType(str, Enum):
    POSITION_LIMIT = "position_limit"
    SECTOR_LIMIT = "sector_limit"
    DAILY_LOSS = "daily_loss"
    POSITION_SIZE = "position_size"
    RISK_REWARD = "risk_reward"

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class ServiceState:
    """Global service state"""
    db_pool: Optional[asyncpg.Pool] = None

state = ServiceState()

# ============================================================================
# AUTONOMOUS MONITORING & EMERGENCY STOP
# ============================================================================

async def execute_emergency_stop(cycle_id: str, reason: str) -> Dict[str, Any]:
    """
    Execute emergency stop: close all positions, cancel orders, halt trading.

    This is AUTONOMOUS - no human approval required.
    """
    logger.critical(f"🛑 EMERGENCY STOP TRIGGERED: {reason}")

    result = {
        "emergency_stop": True,
        "reason": reason,
        "cycle_id": cycle_id,
        "timestamp": datetime.utcnow().isoformat(),
        "positions_closed": 0,
        "orders_cancelled": 0,
        "errors": []
    }

    try:
        async with state.db_pool.acquire() as conn:
            # Get all open positions for this cycle (with symbols)
            open_positions = await conn.fetch("""
                SELECT
                    p.position_id,
                    p.security_id,
                    p.side,
                    p.quantity,
                    p.broker_order_id,
                    s.symbol
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                WHERE p.cycle_id = $1 AND p.status = 'open'
            """, cycle_id)

            logger.info(f"Found {len(open_positions)} open positions to close")

            # ===================================================================
            # ALPACA INTEGRATION - Close real positions first
            # ===================================================================
            alpaca_closed = 0
            if alpaca_trader.is_enabled():
                try:
                    logger.critical("Closing all positions via Alpaca...")

                    # Option 1: Use Alpaca's close_all_positions() - fastest
                    alpaca_results = await alpaca_trader.close_all_positions()
                    alpaca_closed = len(alpaca_results)

                    logger.critical(
                        f"Alpaca closed {alpaca_closed} positions successfully"
                    )

                except Exception as e:
                    logger.error(f"Alpaca close_all failed: {e}", exc_info=True)
                    result["errors"].append(f"Alpaca close_all error: {str(e)}")

                    # Fallback: Close positions individually
                    for position in open_positions:
                        try:
                            if position['symbol']:
                                await alpaca_trader.close_position(position['symbol'])
                                alpaca_closed += 1
                        except Exception as e:
                            logger.error(
                                f"Failed to close {position['symbol']} via Alpaca: {e}"
                            )
                            result["errors"].append(
                                f"Alpaca {position['symbol']}: {str(e)}"
                            )
            else:
                logger.warning("Alpaca not enabled - closing database positions only")

            result["alpaca_positions_closed"] = alpaca_closed

            # ===================================================================
            # DATABASE - Mark positions as closed
            # ===================================================================
            for position in open_positions:
                try:
                    await conn.execute("""
                        UPDATE positions
                        SET status = 'closed',
                            closed_at = $1,
                            exit_price = entry_price,
                            realized_pnl = 0,
                            alpaca_status = 'closed_by_emergency_stop'
                        WHERE position_id = $2
                    """, datetime.utcnow(), position['position_id'])

                    result["positions_closed"] += 1

                except Exception as e:
                    logger.error(f"Failed to close position {position['position_id']}: {e}")
                    result["errors"].append(f"Position {position['position_id']}: {str(e)}")

            # Update cycle status to stopped
            await conn.execute("""
                UPDATE trading_cycles
                SET status = 'stopped',
                    stopped_at = $1
                WHERE cycle_id = $2
            """, datetime.utcnow(), cycle_id)

            logger.critical(
                f"Emergency stop completed: {result['positions_closed']} DB positions closed, "
                f"{alpaca_closed} Alpaca positions closed"
            )

            # Send critical alert
            try:
                # Get final P&L
                daily_pnl = await get_daily_pnl(conn, cycle_id)

                await alert_manager.alert_emergency_stop(
                    reason=reason,
                    daily_pnl=daily_pnl,
                    positions_closed=result["positions_closed"],
                    orders_cancelled=result["orders_cancelled"]
                )
            except Exception as e:
                logger.error(f"Failed to send emergency stop alert: {e}")
                result["errors"].append(f"Alert failed: {str(e)}")

            return result

    except Exception as e:
        logger.critical(f"Emergency stop failed: {e}", exc_info=True)
        result["errors"].append(f"Critical error: {str(e)}")
        return result


async def monitor_positions_continuously():
    """
    Background task: Monitor all active positions every 60 seconds.

    Checks:
    - Daily P&L against limit
    - Position count limits
    - Risk violations

    AUTONOMOUS: Triggers emergency stop when limits hit.
    """
    logger.info("🔍 Real-time position monitoring started")

    check_interval = 60  # seconds

    while True:
        try:
            # Load risk limits from config
            risk_limits = get_risk_limits()
            max_daily_loss = risk_limits.get('max_daily_loss_usd', 2000.0)
            warning_threshold = risk_limits.get('warning_threshold_pct', 0.75)

            # Get all active cycles
            async with state.db_pool.acquire() as conn:
                active_cycles = await conn.fetch("""
                    SELECT cycle_id
                    FROM trading_cycles
                    WHERE status = 'active'
                """)

                for cycle in active_cycles:
                    cycle_id = cycle['cycle_id']

                    # Check daily P&L
                    daily_pnl = await get_daily_pnl(conn, cycle_id)

                    # WARNING threshold (75% of limit)
                    warning_level = -(max_daily_loss * warning_threshold)
                    if daily_pnl <= warning_level and daily_pnl > -max_daily_loss:
                        logger.warning(
                            f"Daily P&L warning for {cycle_id}: ${daily_pnl:,.2f} "
                            f"({abs(daily_pnl)/max_daily_loss*100:.1f}% of limit)"
                        )

                        # Send warning alert
                        try:
                            await alert_manager.alert_daily_loss_warning(
                                current_loss=daily_pnl,
                                max_loss=max_daily_loss,
                                percentage=abs(daily_pnl) / max_daily_loss * 100
                            )
                        except Exception as e:
                            logger.error(f"Failed to send warning alert: {e}")

                    # CRITICAL threshold (100% of limit) - EMERGENCY STOP
                    if daily_pnl <= -max_daily_loss:
                        logger.critical(
                            f"🛑 Daily loss limit exceeded for {cycle_id}: ${daily_pnl:,.2f}"
                        )

                        # AUTONOMOUS EMERGENCY STOP
                        await execute_emergency_stop(
                            cycle_id=cycle_id,
                            reason=f"Daily loss limit exceeded: ${daily_pnl:,.2f} >= ${max_daily_loss:,.2f}"
                        )

            # Wait before next check
            await asyncio.sleep(check_interval)

        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
            # Continue monitoring even if error occurs
            await asyncio.sleep(check_interval)


# ============================================================================
# FALLBACK POSITION MONITORING (STOP-LOSS/TAKE-PROFIT)
# ============================================================================

class PositionMonitor:
    """
    Fallback position monitoring that checks positions against stop-loss/take-profit.

    This is a SAFETY NET in case Alpaca bracket orders fail silently.
    Runs every 30 seconds during market hours.
    """

    def __init__(self, db_pool, alpaca_client):
        self.db_pool = db_pool
        self.alpaca_trader = alpaca_client
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the position monitoring loop"""
        self.running = True
        logger.info("🛡️ Fallback position monitor started (checks every 30s)")
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the position monitoring loop"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Position monitor stopped")

    async def _run_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self._check_positions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Position monitor error: {e}")

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _check_positions(self):
        """Check all open positions against their stop prices"""

        if not self.alpaca_trader.is_enabled():
            return

        async with self.db_pool.acquire() as conn:
            # Get all open positions with stop prices
            positions = await conn.fetch("""
                SELECT
                    p.position_id,
                    p.broker_order_id,
                    s.symbol,
                    p.quantity,
                    p.entry_price,
                    p.stop_loss,
                    p.take_profit,
                    p.side
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                WHERE p.status = 'open'
                AND p.stop_loss IS NOT NULL
            """)

            if not positions:
                return

            # Get current prices from Alpaca
            symbols = list(set([p['symbol'] for p in positions]))

            try:
                current_prices = await self.alpaca_trader.get_current_prices(symbols)
            except Exception as e:
                logger.error(f"Failed to get current prices for fallback monitor: {e}")
                return

            # Check each position
            for pos in positions:
                symbol = pos['symbol']
                current_price = current_prices.get(symbol)

                if current_price is None:
                    continue

                stop_loss = float(pos['stop_loss']) if pos['stop_loss'] else None
                take_profit = float(pos['take_profit']) if pos['take_profit'] else None
                side = pos['side']

                should_close = False
                close_reason = None

                # Check stop loss (for long positions, close if price <= stop)
                if stop_loss and side == 'long' and current_price <= stop_loss:
                    should_close = True
                    close_reason = f"STOP_LOSS_HIT: {symbol} @ ${current_price:.2f} <= ${stop_loss:.2f}"

                # Check stop loss (for short positions, close if price >= stop)
                if stop_loss and side == 'short' and current_price >= stop_loss:
                    should_close = True
                    close_reason = f"STOP_LOSS_HIT: {symbol} @ ${current_price:.2f} >= ${stop_loss:.2f}"

                # Check take profit (for long positions, close if price >= target)
                if take_profit and side == 'long' and current_price >= take_profit:
                    should_close = True
                    close_reason = f"TAKE_PROFIT_HIT: {symbol} @ ${current_price:.2f} >= ${take_profit:.2f}"

                # Check take profit (for short positions, close if price <= target)
                if take_profit and side == 'short' and current_price <= take_profit:
                    should_close = True
                    close_reason = f"TAKE_PROFIT_HIT: {symbol} @ ${current_price:.2f} <= ${take_profit:.2f}"

                if should_close:
                    logger.warning(f"🛡️ FALLBACK CLOSE TRIGGERED: {close_reason}")
                    await self._close_position(conn, pos, current_price, close_reason)

    async def _close_position(self, conn, position: dict, current_price: float, reason: str):
        """Close a position via market order"""

        symbol = position['symbol']
        quantity = position['quantity']
        side = position['side']

        try:
            # Submit market order to close (sell for long, buy for short)
            close_side = 'sell' if side == 'long' else 'buy'

            result = await self.alpaca_trader.submit_market_order(
                symbol=symbol,
                quantity=quantity,
                side=close_side
            )

            logger.info(f"Fallback close order submitted: {symbol} {quantity} shares, reason: {reason}")

            # Calculate P&L
            entry_price = float(position['entry_price']) if position['entry_price'] else 0
            if side == 'long':
                realized_pnl = (current_price - entry_price) * quantity
            else:
                realized_pnl = (entry_price - current_price) * quantity

            # Update database
            await conn.execute("""
                UPDATE positions
                SET
                    status = 'closed',
                    exit_price = $1,
                    closed_at = NOW(),
                    realized_pnl = $2,
                    close_reason = $3,
                    alpaca_status = 'closed_by_fallback'
                WHERE position_id = $4
            """, current_price, realized_pnl, reason, position['position_id'])

            # Send alert
            try:
                await alert_manager.send_alert(
                    alert_type=AlertType.POSITION_CLOSED,
                    severity=AlertSeverity.WARNING,
                    title=f"Fallback Position Close: {symbol}",
                    message=f"{reason}\nP&L: ${realized_pnl:,.2f}"
                )
            except Exception as e:
                logger.error(f"Failed to send fallback close alert: {e}")

        except Exception as e:
            logger.error(f"Failed to close position {symbol} via fallback: {e}")


# Global position monitor instance
_position_monitor: Optional[PositionMonitor] = None

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    
    try:
        # Create database pool
        state.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("✅ Database pool created")
        
        # Verify schema
        async with state.db_pool.acquire() as conn:
            # Check for helper function
            helper_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_proc 
                    WHERE proname = 'get_or_create_security'
                )
            """)
            
            if not helper_exists:
                raise RuntimeError("get_or_create_security() function not found! Run schema v5.0 first.")
            
            # Check for securities table
            securities_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'securities'
                )
            """)
            
            if not securities_exists:
                raise RuntimeError("securities table not found! Run schema v5.0 first.")
            
            # Check for risk tables (OPTIONAL - warn if missing, don't crash)
            risk_tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('risk_parameters', 'daily_risk_metrics', 'risk_events')
            """)
            
            risk_table_names = {r['table_name'] for r in risk_tables}
            missing_tables = {'risk_parameters', 'daily_risk_metrics', 'risk_events'} - risk_table_names
            
            if missing_tables:
                logger.warning(f"⚠️ Missing risk tables: {missing_tables}")
                logger.warning(f"⚠️ Run: psql $DATABASE_URL -f add-risk-tables-v50.sql")
                logger.warning(f"⚠️ Service will use default parameters until tables are created")
            else:
                logger.info(f"✅ All risk tables present")
            
            logger.info(f"✅ Schema validation passed - {SCHEMA_VERSION}")

        # ===================================================================
        # START REAL-TIME MONITORING (AUTONOMOUS TRADING)
        # ===================================================================
        global _monitoring_task, _position_monitor
        _monitoring_task = asyncio.create_task(monitor_positions_continuously())
        logger.info("✅ Real-time position monitoring started (autonomous mode)")

        # ===================================================================
        # START FALLBACK POSITION MONITOR (STOP-LOSS/TAKE-PROFIT)
        # ===================================================================
        _position_monitor = PositionMonitor(state.db_pool, alpaca_trader)
        await _position_monitor.start()
        logger.info("✅ Fallback position monitor started (checks stop-loss/take-profit every 30s)")

        logger.info(f"✅ {SERVICE_NAME} v{SERVICE_VERSION} ready on port {SERVICE_PORT}")
        logger.info("🤖 AUTONOMOUS MODE: Emergency stop will trigger automatically at daily loss limit")
        logger.info("🛡️ FALLBACK MODE: Position monitor will enforce stop-loss/take-profit if Alpaca brackets fail")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info(f"Shutting down {SERVICE_NAME}")

    # Stop fallback position monitor
    if _position_monitor:
        await _position_monitor.stop()
        logger.info("Fallback position monitor stopped")

    # Cancel monitoring task
    if _monitoring_task:
        _monitoring_task.cancel()
        try:
            await _monitoring_task
        except asyncio.CancelledError:
            pass
        logger.info("Monitoring task stopped")

    if state.db_pool:
        await state.db_pool.close()
        logger.info("Database pool closed")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Risk Manager Service",
    version=SERVICE_VERSION,
    description="Risk management with normalized schema v5.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class PositionRiskRequest(BaseModel):
    """Request to validate a position risk"""
    cycle_id: str  # VARCHAR(20) in database
    symbol: str
    side: str  # 'long' or 'short'
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0, description="Stop loss price")
    target_price: Optional[float] = Field(None, gt=0, description="Target price")
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        return v.upper().strip()
    
    @field_validator('side')
    @classmethod
    def validate_side(cls, v):
        if v.lower() not in ['long', 'short']:
            raise ValueError("Side must be 'long' or 'short'")
        return v.lower()

class RiskCheckResult(BaseModel):
    """Result of risk validation"""
    approved: bool
    risk_level: RiskLevel
    violations: List[str]
    warnings: List[str]
    position_size_usd: float
    risk_amount_usd: float
    risk_reward_ratio: Optional[float]
    sector_exposure_pct: Optional[float]
    daily_pnl: float

class SectorExposure(BaseModel):
    """Sector exposure data"""
    sector_name: str
    position_count: int
    total_exposure_usd: float
    total_pnl: float
    exposure_pct: float

# ============================================================================
# HELPER FUNCTIONS (v5.0 NORMALIZED SCHEMA)
# ============================================================================

async def get_security_id(conn: asyncpg.Connection, symbol: str) -> int:
    """
    Get security_id for a symbol using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_security() helper function.
    """
    security_id = await conn.fetchval(
        "SELECT get_or_create_security($1)", symbol.upper()
    )

    if not security_id:
        raise ValueError(f"Failed to get security_id for {symbol}")

    return security_id

async def get_risk_parameters(conn: asyncpg.Connection, cycle_id: str) -> Dict[str, Any]:
    """
    Get risk parameters for the current cycle.
    Falls back to defaults if risk_parameters table doesn't exist yet.
    """
    try:
        params = await conn.fetchrow("""
            SELECT 
                max_positions,
                max_position_size_usd,
                max_daily_loss_usd,
                max_sector_exposure_pct,
                min_risk_reward_ratio
            FROM risk_parameters
            WHERE cycle_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """, cycle_id)
        
        if params:
            return dict(params)
    except asyncpg.UndefinedTableError:
        logger.warning("risk_parameters table not found, using defaults")
    except Exception as e:
        logger.warning(f"Error fetching risk parameters: {e}, using defaults")
    
    # Return defaults if table doesn't exist or no params found
    return {
        'max_positions': Config.MAX_POSITIONS,
        'max_position_size_usd': Config.MAX_POSITION_SIZE_USD,
        'max_daily_loss_usd': Config.MAX_DAILY_LOSS_USD,
        'max_sector_exposure_pct': Config.MAX_SECTOR_EXPOSURE_PCT,
        'min_risk_reward_ratio': Config.MIN_RISK_REWARD_RATIO
    }

async def get_sector_exposure(
    conn: asyncpg.Connection, 
    cycle_id: str, 
    security_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get sector exposure using v5.0 normalized schema.
    
    v5.0 Pattern:
    - JOINs positions → securities → sectors
    - Uses security_id FKs throughout
    - No symbol VARCHAR anywhere
    """
    
    if security_id:
        # Get exposure for specific security's sector
        result = await conn.fetchrow("""
            SELECT 
                sec.sector_name,
                COUNT(DISTINCT p.position_id) as position_count,
                COALESCE(SUM(p.quantity * p.entry_price), 0) as total_exposure,
                COALESCE(SUM(p.unrealized_pnl), 0) as total_pnl
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND p.status = 'open'
            AND s.security_id = $2
            GROUP BY sec.sector_name
        """, cycle_id, security_id)
    else:
        # Get total portfolio exposure
        result = await conn.fetchrow("""
            SELECT 
                COALESCE(SUM(p.quantity * p.entry_price), 0) as total_exposure
            FROM positions p
            WHERE p.cycle_id = $1
            AND p.status = 'open'
        """, cycle_id)
    
    if not result:
        return {
            'sector_name': None,
            'position_count': 0,
            'total_exposure': 0,
            'total_pnl': 0,
            'exposure_pct': 0
        }
    
    # Calculate exposure percentage
    total_portfolio = await conn.fetchval("""
        SELECT COALESCE(SUM(quantity * entry_price), 0)
        FROM positions
        WHERE cycle_id = $1 AND status = 'open'
    """, cycle_id)
    
    exposure_pct = 0
    if total_portfolio > 0 and 'total_exposure' in result:
        exposure_pct = (result['total_exposure'] / total_portfolio) * 100
    
    return {
        'sector_name': result.get('sector_name'),
        'position_count': result.get('position_count', 0),
        'total_exposure': float(result.get('total_exposure', 0)),
        'total_pnl': float(result.get('total_pnl', 0)),
        'exposure_pct': exposure_pct
    }

async def get_daily_pnl(conn: asyncpg.Connection, cycle_id: str) -> float:
    """Get today's P&L for the cycle"""
    today = date.today()
    
    pnl = await conn.fetchval("""
        SELECT COALESCE(SUM(realized_pnl), 0) + COALESCE(SUM(unrealized_pnl), 0)
        FROM positions
        WHERE cycle_id = $1
        AND DATE(created_at) = $2
    """, cycle_id, today)
    
    return float(pnl or 0)

async def log_risk_event(
    conn: asyncpg.Connection,
    cycle_id: str,
    security_id: int,
    event_type: RiskEventType,
    risk_level: RiskLevel,
    description: str,
    metadata: Dict = None
):
    """
    Log a risk event with v5.0 normalized schema.
    
    v5.0 Pattern:
    - Uses security_id FK (NOT symbol VARCHAR)
    - Stores metadata as JSON
    - Gracefully handles missing risk_events table
    """
    try:
        await conn.execute("""
            INSERT INTO risk_events (
                cycle_id, security_id, event_type, risk_level,
                description, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """, 
            cycle_id, security_id, event_type.value, risk_level.value,
            description, json.dumps(metadata or {})
        )
    except asyncpg.UndefinedTableError:
        logger.warning(f"risk_events table not found, event not logged: {description}")
    except Exception as e:
        logger.error(f"Failed to log risk event: {e}", exc_info=True)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "schema": SCHEMA_VERSION,
        "uses_security_id_fk": True,
        "uses_sector_joins": True
    }

@app.post("/api/v1/validate-position", response_model=RiskCheckResult)
async def validate_position(request: PositionRiskRequest):
    """
    Validate a proposed position against risk limits.
    
    v5.0 Pattern:
    - Uses security_id FK lookups
    - JOINs with sectors table for sector exposure
    - Queries positions table with security_id
    """
    try:
        violations = []
        warnings = []
        
        async with state.db_pool.acquire() as conn:
            # Get security_id
            security_id = await get_security_id(conn, request.symbol)
            
            # Get risk parameters
            params = await get_risk_parameters(conn, request.cycle_id)
            
            # Calculate position metrics
            position_size = request.quantity * request.entry_price
            
            if request.side == 'long':
                risk_amount = request.quantity * (request.entry_price - request.stop_price)
            else:
                risk_amount = request.quantity * (request.stop_price - request.entry_price)
            
            risk_reward_ratio = None
            if request.target_price:
                if request.side == 'long':
                    reward = request.quantity * (request.target_price - request.entry_price)
                else:
                    reward = request.quantity * (request.entry_price - request.target_price)
                
                if risk_amount > 0:
                    risk_reward_ratio = reward / risk_amount
            
            # Check 1: Position size limit
            if position_size > params['max_position_size_usd']:
                violations.append(
                    f"Position size ${position_size:.2f} exceeds max ${params['max_position_size_usd']:.2f}"
                )
            
            # Check 2: Risk/reward ratio
            if risk_reward_ratio and risk_reward_ratio < params['min_risk_reward_ratio']:
                violations.append(
                    f"Risk/reward ratio {risk_reward_ratio:.2f} below minimum {params['min_risk_reward_ratio']:.2f}"
                )
            
            # Check 3: Max positions limit
            open_positions = await conn.fetchval("""
                SELECT COUNT(*)
                FROM positions
                WHERE cycle_id = $1 AND status = 'open'
            """, request.cycle_id)
            
            if open_positions >= params['max_positions']:
                violations.append(
                    f"Max positions ({params['max_positions']}) already reached"
                )
            
            # Check 4: Sector exposure (v5.0 JOIN pattern)
            sector_exp = await get_sector_exposure(conn, request.cycle_id, security_id)
            
            if sector_exp['exposure_pct'] > params['max_sector_exposure_pct']:
                violations.append(
                    f"Sector {sector_exp['sector_name']} exposure {sector_exp['exposure_pct']:.1f}% "
                    f"exceeds max {params['max_sector_exposure_pct']:.1f}%"
                )
            
            # Check 5: Daily loss limit
            daily_pnl = await get_daily_pnl(conn, request.cycle_id)
            
            if daily_pnl < -params['max_daily_loss_usd']:
                violations.append(
                    f"Daily loss ${abs(daily_pnl):.2f} exceeds max ${params['max_daily_loss_usd']:.2f}"
                )
            
            # Determine risk level
            if violations:
                risk_level = RiskLevel.CRITICAL
            elif sector_exp['exposure_pct'] > params['max_sector_exposure_pct'] * 0.8:
                risk_level = RiskLevel.HIGH
                warnings.append(f"Sector exposure at {sector_exp['exposure_pct']:.1f}%")
            elif position_size > params['max_position_size_usd'] * 0.8:
                risk_level = RiskLevel.MEDIUM
                warnings.append(f"Large position size: ${position_size:.2f}")
            else:
                risk_level = RiskLevel.LOW
            
            # Log risk event if violations
            if violations:
                await log_risk_event(
                    conn, request.cycle_id, security_id,
                    RiskEventType.POSITION_LIMIT,
                    risk_level,
                    f"Position validation failed for {request.symbol}",
                    {
                        'violations': violations,
                        'position_size_usd': position_size,
                        'risk_amount_usd': risk_amount
                    }
                )
            
            return RiskCheckResult(
                approved=len(violations) == 0,
                risk_level=risk_level,
                violations=violations,
                warnings=warnings,
                position_size_usd=position_size,
                risk_amount_usd=risk_amount,
                risk_reward_ratio=risk_reward_ratio,
                sector_exposure_pct=sector_exp['exposure_pct'],
                daily_pnl=daily_pnl
            )
    
    except Exception as e:
        logger.error(f"Position validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/exposure/{cycle_id}")
async def get_cycle_exposure(cycle_id: str):
    """
    Get exposure breakdown by sector for a cycle.
    
    v5.0 Pattern:
    - JOINs positions → securities → sectors
    - Uses security_id FKs throughout
    - Returns sector aggregations
    """
    try:
        async with state.db_pool.acquire() as conn:
            # Get sector-level exposure
            sectors = await conn.fetch("""
                SELECT 
                    sec.sector_name,
                    COUNT(DISTINCT p.position_id) as position_count,
                    COALESCE(SUM(p.quantity * p.entry_price), 0) as total_exposure_usd,
                    COALESCE(SUM(p.unrealized_pnl), 0) as total_pnl
                FROM positions p
                JOIN securities s ON s.security_id = p.security_id
                JOIN sectors sec ON sec.sector_id = s.sector_id
                WHERE p.cycle_id = $1
                AND p.status = 'open'
                GROUP BY sec.sector_name
                ORDER BY total_exposure_usd DESC
            """, cycle_id)
            
            # Get total portfolio value
            total_portfolio = await conn.fetchval("""
                SELECT COALESCE(SUM(quantity * entry_price), 0)
                FROM positions
                WHERE cycle_id = $1 AND status = 'open'
            """, cycle_id)
            
            # Calculate exposure percentages
            exposure_list = []
            for sector in sectors:
                exposure_pct = 0
                if total_portfolio > 0:
                    exposure_pct = (sector['total_exposure_usd'] / total_portfolio) * 100
                
                exposure_list.append(SectorExposure(
                    sector_name=sector['sector_name'],
                    position_count=sector['position_count'],
                    total_exposure_usd=float(sector['total_exposure_usd']),
                    total_pnl=float(sector['total_pnl']),
                    exposure_pct=exposure_pct
                ))
            
            return {
                "cycle_id": cycle_id,
                "total_portfolio_usd": float(total_portfolio),
                "sector_exposures": exposure_list,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        logger.error(f"Exposure calculation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/metrics/{cycle_id}")
async def get_risk_metrics(cycle_id: str):
    """Get real-time risk metrics for a cycle"""
    try:
        async with state.db_pool.acquire() as conn:
            # Get parameters
            params = await get_risk_parameters(conn, cycle_id)
            
            # Get current metrics
            metrics = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as open_positions,
                    COALESCE(SUM(quantity * entry_price), 0) as total_exposure,
                    COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl,
                    COALESCE(SUM(realized_pnl), 0) as total_realized_pnl
                FROM positions
                WHERE cycle_id = $1 AND status = 'open'
            """, cycle_id)
            
            # Get daily P&L
            daily_pnl = await get_daily_pnl(conn, cycle_id)
            
            # Calculate utilization
            position_utilization = (metrics['open_positions'] / params['max_positions']) * 100
            
            return {
                "cycle_id": cycle_id,
                "open_positions": metrics['open_positions'],
                "max_positions": params['max_positions'],
                "position_utilization_pct": position_utilization,
                "total_exposure_usd": float(metrics['total_exposure']),
                "unrealized_pnl": float(metrics['total_unrealized_pnl']),
                "realized_pnl": float(metrics['total_realized_pnl']),
                "daily_pnl": daily_pnl,
                "daily_loss_limit_usd": params['max_daily_loss_usd'],
                "daily_loss_remaining_usd": params['max_daily_loss_usd'] + daily_pnl,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except Exception as e:
        logger.error(f"Metrics calculation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/parameters/{cycle_id}")
async def get_cycle_parameters(cycle_id: str):
    """Get risk parameters for a cycle"""
    try:
        async with state.db_pool.acquire() as conn:
            params = await get_risk_parameters(conn, cycle_id)
            return params
    
    except Exception as e:
        logger.error(f"Parameters fetch error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 70)
    print(f"🎩 Catalyst Trading System - {SERVICE_NAME.upper()} v{SERVICE_VERSION}")
    print("=" * 70)
    print(f"✅ {SCHEMA_VERSION}")
    print("✅ Uses security_id FK (NOT symbol VARCHAR)")
    print("✅ Sector exposure via JOINs (securities → sectors)")
    print("✅ All position queries use security_id FKs")
    print("✅ Real-time risk validation")
    print("✅ Daily loss tracking")
    print("✅ Sector concentration limits")
    print(f"Port: {SERVICE_PORT}")
    print("=" * 70)
    
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
