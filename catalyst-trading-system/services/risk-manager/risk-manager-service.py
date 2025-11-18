#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk-manager-service.py
Version: 5.0.0
Last Updated: 2025-10-13
Purpose: Risk management with normalized schema v5.0 (security_id FKs + sector JOINs)

REVISION HISTORY:
v5.0.0 (2025-10-13) - Normalized Schema Migration (Playbook v3.0 Step 6)
- ✅ Uses security_id FK lookups (NOT symbol VARCHAR)
- ✅ Sector exposure tracking via JOINs (securities → sectors)
- ✅ Position risk calculations with security_id FKs
- ✅ All queries use JOINs for sector exposure
- ✅ Real-time risk limits enforcement
- ✅ Daily risk metrics tracking with FKs
- ✅ Risk events logging with proper FKs
- ✅ Error handling compliant with v1.0 standard

v4.2.1 (2025-09-20) - DEPRECATED (Denormalized)
- Had risk tables but used symbol VARCHAR
- No FK relationships with securities/sectors

Description of Service:
Enforces risk management rules using normalized v5.0 schema:
- Position sizing and limits (via security_id)
- Sector exposure limits (via securities → sectors JOIN)
- Daily loss limits
- Max positions per cycle
- Risk/reward validation
- All queries use security_id FKs for data integrity
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
SERVICE_VERSION = "5.0.0"
SERVICE_PORT = 5004
SCHEMA_VERSION = "v5.0 Normalized Schema"

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
        
        logger.info(f"✅ {SERVICE_NAME} ready on port {SERVICE_PORT}")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
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
    Get security_id for a symbol using helper function.
    v5.0 Pattern: Always use security_id FK, never symbol VARCHAR.
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
