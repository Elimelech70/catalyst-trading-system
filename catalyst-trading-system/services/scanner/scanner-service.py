#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: scanner-service.py
Version: 5.5.0
Last Updated: 2025-10-16
Purpose: Scanner service FIXED to match v5.0 normalized database schema

REVISION HISTORY:
v5.5.0 (2025-10-16) - SCHEMA v5.0 COMPLIANCE FIX
- Fixed ALL column name mismatches
- Removed non-existent columns
- Uses correct schema from design documents
- Stores scanner config in JSONB configuration field
- Proper column names: started_at, composite_score, price
- No more schema violations

Description of Service:
Market scanner that CORRECTLY uses the v5.0 normalized database schema.
All database operations now match the design documentation exactly.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
import asyncpg
import json
import os
import logging
from dataclasses import dataclass, asdict
import yfinance as yf
import redis.asyncio as redis
import uvicorn

# ============================================================================
# SERVICE METADATA
# ============================================================================
SERVICE_NAME = "scanner"
SERVICE_VERSION = "5.5.0"
SERVICE_TITLE = "Scanner Service"
SCHEMA_VERSION = "v5.0 normalized"
SERVICE_PORT = 5001

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(SERVICE_NAME)

# ============================================================================
# SERVICE STATE
# ============================================================================
@dataclass
class ScannerConfig:
    """Scanner-specific configuration (stored in trading_cycles.configuration)"""
    initial_universe_size: int = 200
    catalyst_filter_size: int = 50
    technical_filter_size: int = 20
    final_selection_size: int = 5
    min_volume: int = 1_000_000
    min_price: float = 5.0
    max_price: float = 500.0
    min_catalyst_score: float = 0.3

class ScannerState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.config: ScannerConfig = ScannerConfig()

state = ScannerState()

# ============================================================================
# LIFESPAN CONTEXT MANAGER
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle"""
    # === STARTUP ===
    logger.info(f"Starting {SERVICE_TITLE} v{SERVICE_VERSION} ({SCHEMA_VERSION})")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable required")
        
        state.db_pool = await asyncpg.create_pool(
            database_url, 
            min_size=5, 
            max_size=20
        )
        logger.info("Database pool initialized")
        
        # Verify schema compatibility
        await verify_schema_compatibility()
        
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise
    
    # Redis (optional)
    try:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        state.redis_client = await redis.from_url(redis_url)
        logger.info("Redis client initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed (non-critical): {e}")
    
    # HTTP session
    state.http_session = aiohttp.ClientSession()
    logger.info(f"{SERVICE_TITLE} ready on port {SERVICE_PORT}")
    
    yield
    
    # === SHUTDOWN ===
    logger.info(f"Shutting down {SERVICE_TITLE}")
    if state.http_session:
        await state.http_session.close()
    if state.db_pool:
        await state.db_pool.close()
    if state.redis_client:
        await state.redis_client.close()
    logger.info(f"{SERVICE_TITLE} shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title=SERVICE_TITLE,
    version=SERVICE_VERSION,
    description=f"Market scanner with {SCHEMA_VERSION} schema compliance",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# SCHEMA VERIFICATION
# ============================================================================
async def verify_schema_compatibility():
    """Verify the database has the expected v5.0 schema"""
    try:
        # Check trading_cycles has correct columns
        trading_cycles_cols = await state.db_pool.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trading_cycles'
        """)
        
        cols = {row['column_name'] for row in trading_cycles_cols}
        required_cols = {'cycle_id', 'mode', 'status', 'started_at', 'stopped_at', 
                        'max_positions', 'scan_frequency', 'configuration'}
        
        missing = required_cols - cols
        if missing:
            logger.warning(f"Missing columns in trading_cycles: {missing}")
        
        # Check scan_results has correct columns
        scan_results_cols = await state.db_pool.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'scan_results'
        """)
        
        scan_cols = {row['column_name'] for row in scan_results_cols}
        required_scan_cols = {'id', 'cycle_id', 'security_id', 'composite_score', 
                             'price', 'volume', 'rank'}
        
        missing_scan = required_scan_cols - scan_cols
        if missing_scan:
            logger.warning(f"Missing columns in scan_results: {missing_scan}")
        
        logger.info("✅ Schema compatibility check completed")
        
    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        # Continue anyway, errors will surface during operations

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
async def get_security_id(symbol: str) -> int:
    """Get or create security_id for symbol"""
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT security_id FROM securities WHERE symbol = $1",
            symbol
        )
        
        if security_id:
            return security_id
        
        # Create new security
        security_id = await state.db_pool.fetchval(
            """
            INSERT INTO securities (symbol, company_name, sector_id, active)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (symbol) DO UPDATE SET symbol = EXCLUDED.symbol
            RETURNING security_id
            """,
            symbol, f"{symbol} Corp", 1
        )
        
        return security_id
        
    except Exception as e:
        logger.error(f"Failed to get/create security_id for {symbol}: {e}")
        raise

async def generate_cycle_id() -> str:
    """Generate cycle_id in format YYYYMMDD-NNN"""
    today = datetime.now().strftime('%Y%m%d')
    
    # Get count of cycles today
    count = await state.db_pool.fetchval(
        "SELECT COUNT(*) FROM trading_cycles WHERE cycle_id LIKE $1",
        f"{today}-%"
    )
    
    return f"{today}-{(count + 1):03d}"

# ============================================================================
# CORE SCANNING LOGIC (FIXED FOR v5.0 SCHEMA)
# ============================================================================
async def scan_market() -> Dict:
    """
    Main scanning orchestration - FIXED to match v5.0 schema exactly
    """
    cycle_id = None
    candidates_found = 0
    errors = []
    
    try:
        # Generate proper cycle_id
        cycle_id = await generate_cycle_id()
        
        # Create trading cycle with CORRECT schema columns
        async with state.db_pool.acquire() as conn:
            # Store scanner config in the JSONB configuration field
            scanner_config = asdict(state.config)
            
            await conn.execute("""
                INSERT INTO trading_cycles (
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    scan_frequency,
                    started_at,
                    configuration,
                    created_at,
                    updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
                cycle_id,                    # cycle_id (VARCHAR)
                'normal',                    # mode
                'scanning',                  # status
                state.config.final_selection_size,  # max_positions
                300,                         # scan_frequency (seconds)
                datetime.utcnow(),          # started_at (NOT cycle_start!)
                json.dumps(scanner_config), # configuration (JSONB for scanner settings)
                datetime.utcnow(),          # created_at
                datetime.utcnow()           # updated_at
            )
        
        logger.info(f"Started scan cycle {cycle_id}")
        
        # Get initial universe
        universe = await get_active_universe()
        if not universe:
            raise ValueError("No active stocks found in universe")
        
        logger.info(f"Initial universe: {len(universe)} stocks")
        
        # Filter by catalysts
        catalyst_stocks = await filter_by_catalyst(universe)
        logger.info(f"After catalyst filter: {len(catalyst_stocks)} stocks")
        
        # Filter by technical setup
        technical_stocks = await filter_by_technical(catalyst_stocks)
        logger.info(f"After technical filter: {len(technical_stocks)} stocks")
        
        # Final selection
        final_picks = technical_stocks[:state.config.final_selection_size]
        candidates_found = len(final_picks)
        logger.info(f"Final selection: {candidates_found} stocks")
        
        # Persist results with CORRECT schema
        success = await persist_scan_results(cycle_id, final_picks)
        if not success:
            errors.append("Failed to persist some scan results")
        
        # Update cycle status with CORRECT columns
        await state.db_pool.execute(
            """
            UPDATE trading_cycles 
            SET status = 'completed',
                stopped_at = $1,
                current_positions = $2,
                updated_at = $3
            WHERE cycle_id = $4
            """,
            datetime.utcnow(),  # stopped_at (NOT cycle_end!)
            candidates_found,   # current_positions
            datetime.utcnow(),  # updated_at
            cycle_id
        )
        
        return {
            "success": True,
            "cycle_id": cycle_id,
            "candidates": candidates_found,
            "picks": final_picks,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        logger.error(f"Error in scan_market: {e}", exc_info=True)
        
        if cycle_id:
            try:
                await state.db_pool.execute(
                    """
                    UPDATE trading_cycles 
                    SET status = 'error', 
                        stopped_at = $1,
                        updated_at = $2
                    WHERE cycle_id = $3
                    """,
                    datetime.utcnow(),
                    datetime.utcnow(),
                    cycle_id
                )
            except Exception as update_error:
                logger.error(f"Failed to update cycle status: {update_error}")
        
        return {
            "success": False,
            "error": str(e),
            "cycle_id": cycle_id
        }

async def get_active_universe() -> List[str]:
    """Get most active stocks"""
    try:
        # This would normally query market data API
        # For testing, return common active stocks
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "META", 
                "TSLA", "NVDA", "JPM", "V", "JNJ"]
    except Exception as e:
        logger.error(f"Failed to get active universe: {e}")
        return []

async def filter_by_catalyst(symbols: List[str]) -> List[Dict]:
    """Filter by news catalysts using normalized schema"""
    results = []
    
    for symbol in symbols:
        try:
            security_id = await get_security_id(symbol)
            
            # Query news_sentiment with proper joins
            catalyst_data = await state.db_pool.fetchrow("""
                SELECT 
                    s.symbol,
                    s.security_id,
                    AVG(ns.sentiment_score) as avg_sentiment,
                    COUNT(*) as news_count
                FROM news_sentiment ns
                JOIN securities s ON s.security_id = ns.security_id
                WHERE ns.security_id = $1
                  AND ns.created_at > NOW() - INTERVAL '24 hours'
                  AND ns.sentiment_score > 0.3
                GROUP BY s.symbol, s.security_id
                HAVING COUNT(*) >= 1
            """, security_id)
            
            if catalyst_data:
                results.append({
                    "symbol": symbol,
                    "security_id": security_id,
                    "catalyst_score": float(catalyst_data['avg_sentiment'] or 0.5),
                    "news_count": catalyst_data['news_count']
                })
            else:
                # No catalyst data, add with low score
                results.append({
                    "symbol": symbol,
                    "security_id": security_id,
                    "catalyst_score": 0.3,
                    "news_count": 0
                })
                
        except Exception as e:
            logger.warning(f"Failed to check catalyst for {symbol}: {e}")
            continue
    
    # Sort by catalyst score
    results.sort(key=lambda x: x['catalyst_score'], reverse=True)
    return results[:state.config.catalyst_filter_size]

async def filter_by_technical(stocks: List[Dict]) -> List[Dict]:
    """Filter by technical indicators"""
    results = []
    
    for stock in stocks:
        try:
            symbol = stock['symbol']
            
            # Get price data (mock for now)
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                logger.warning(f"No price data for {symbol}")
                continue
            
            # Calculate scores
            current_price = float(hist['Close'].iloc[-1])
            avg_volume = int(hist['Volume'].mean())
            price_change = float((hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100)
            
            # Calculate technical metrics
            momentum_score = min(1.0, abs(price_change) / 10)
            volume_score = min(1.0, avg_volume / 10_000_000)
            
            # Add technical data
            stock['momentum_score'] = momentum_score
            stock['volume_score'] = volume_score
            stock['technical_score'] = (momentum_score + volume_score) / 2
            stock['price'] = current_price
            stock['volume'] = avg_volume
            stock['change_percent'] = price_change
            
            # Calculate composite score (matching schema)
            stock['composite_score'] = (
                stock['catalyst_score'] * 0.3 +
                stock['momentum_score'] * 0.2 +
                stock['volume_score'] * 0.2 +
                stock['technical_score'] * 0.3
            )
            
            # Only keep if meets criteria
            if (avg_volume >= state.config.min_volume and 
                state.config.min_price <= current_price <= state.config.max_price):
                results.append(stock)
                
        except Exception as e:
            logger.error(f"Failed technical analysis for {stock.get('symbol')}: {e}")
            continue
    
    # Sort by composite score
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return results[:state.config.technical_filter_size]

async def persist_scan_results(cycle_id: str, picks: List[Dict]) -> bool:
    """
    Persist results using CORRECT v5.0 schema columns
    """
    success_count = 0
    failure_count = 0
    
    try:
        scan_timestamp = datetime.utcnow()
        
        for i, pick in enumerate(picks, 1):
            try:
                await state.db_pool.execute("""
                    INSERT INTO scan_results (
                        cycle_id,
                        security_id,
                        scan_timestamp,
                        momentum_score,
                        volume_score,
                        catalyst_score,
                        technical_score,
                        composite_score,
                        price,
                        volume,
                        rank,
                        selected_for_trading,
                        scan_metadata,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                    cycle_id,
                    pick['security_id'],
                    scan_timestamp,
                    pick.get('momentum_score', 0),
                    pick.get('volume_score', 0),
                    pick.get('catalyst_score', 0),
                    pick.get('technical_score', 0),
                    pick.get('composite_score', 0),  # NOT combined_score!
                    pick.get('price', 0),            # NOT current_price!
                    pick.get('volume', 0),           # NOT avg_volume_5d!
                    i,  # rank
                    i <= 5,  # selected_for_trading (top 5)
                    json.dumps({
                        'change_percent': pick.get('change_percent', 0),
                        'news_count': pick.get('news_count', 0)
                    }),  # Extra data in JSONB field
                    datetime.utcnow()
                )
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to persist result for {pick.get('symbol')}: {e}")
                failure_count += 1
                continue
        
        logger.info(f"Persisted {success_count} results, {failure_count} failures")
        return failure_count == 0
        
    except Exception as e:
        logger.error(f"Critical error in persist_scan_results: {e}", exc_info=True)
        return False

# ============================================================================
# API ENDPOINTS (FIXED FOR v5.0 SCHEMA)
# ============================================================================
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "schema": SCHEMA_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected" if state.db_pool else "disconnected",
        "redis": "connected" if state.redis_client else "disconnected"
    }

@app.post("/api/v1/scan")
async def trigger_scan():
    """Trigger market scan"""
    try:
        result = await scan_market()
        
        if not result.get('success'):
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Scan failed')
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error in trigger_scan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/candidates")
async def get_candidates(cycle_id: Optional[str] = None, limit: int = 10):
    """
    Get scan candidates - FIXED to use correct column names
    """
    try:
        if cycle_id:
            candidates = await state.db_pool.fetch("""
                SELECT 
                    sr.rank,
                    s.symbol,
                    s.company_name,
                    sec.sector_name,
                    sr.catalyst_score,
                    sr.technical_score,
                    sr.composite_score,     -- NOT combined_score!
                    sr.price,               -- NOT current_price!
                    sr.volume,              -- NOT avg_volume_5d!
                    sr.momentum_score,
                    sr.volume_score,
                    sr.scan_timestamp,
                    sr.scan_metadata
                FROM scan_results sr
                JOIN securities s ON s.security_id = sr.security_id
                LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
                WHERE sr.cycle_id = $1
                ORDER BY sr.rank
                LIMIT $2
            """, cycle_id, limit)
        else:
            # Get latest cycle
            candidates = await state.db_pool.fetch("""
                WITH latest_cycle AS (
                    SELECT cycle_id 
                    FROM trading_cycles 
                    WHERE status = 'completed'
                    ORDER BY started_at DESC
                    LIMIT 1
                )
                SELECT 
                    sr.rank,
                    s.symbol,
                    s.company_name,
                    sec.sector_name,
                    sr.catalyst_score,
                    sr.technical_score,
                    sr.composite_score,
                    sr.price,
                    sr.volume,
                    sr.momentum_score,
                    sr.volume_score,
                    sr.scan_timestamp,
                    sr.scan_metadata
                FROM scan_results sr
                JOIN securities s ON s.security_id = sr.security_id
                LEFT JOIN sectors sec ON sec.sector_id = s.sector_id
                WHERE sr.cycle_id = (SELECT cycle_id FROM latest_cycle)
                ORDER BY sr.rank
                LIMIT $1
            """, limit)
        
        # Parse JSONB metadata and add to results
        results = []
        for row in candidates:
            result = dict(row)
            if result.get('scan_metadata'):
                metadata = result['scan_metadata']
                result['change_percent'] = metadata.get('change_percent', 0)
                result['news_count'] = metadata.get('news_count', 0)
            results.append(result)
        
        return {
            "success": True,
            "count": len(results),
            "candidates": results
        }
        
    except Exception as e:
        logger.error(f"Failed to get candidates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve candidates: {str(e)}"
        )

@app.get("/api/v1/cycles/{cycle_id}")
async def get_cycle_details(cycle_id: str):
    """Get detailed information about a scan cycle - FIXED columns"""
    try:
        cycle = await state.db_pool.fetchrow("""
            SELECT 
                cycle_id,
                mode,
                status,
                max_positions,
                scan_frequency,
                started_at,           -- NOT cycle_start!
                stopped_at,           -- NOT cycle_end!
                current_positions,
                configuration,
                created_at,
                updated_at
            FROM trading_cycles
            WHERE cycle_id = $1
        """, cycle_id)
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")
        
        # Parse configuration JSONB
        result = dict(cycle)
        if result.get('configuration'):
            config = result['configuration']
            result['scanner_config'] = config
        
        return {
            "success": True,
            "cycle": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cycle details: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve cycle: {str(e)}"
        )

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "scanner-service:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
        log_level="info"
    )