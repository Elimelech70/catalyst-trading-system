#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: scanner-service.py
Version: 6.1.0
Last Updated: 2025-12-20
Purpose: Scanner service using actual deployed database schema

REVISION HISTORY:
v6.1.0 (2025-12-20) - IMPROVED SCORING LOGIC
- FIXED: Momentum scoring now PENALIZES overbought stocks (was rewarding them)
  * Old: momentum=1.0 (10%+ move) = max score = BUY = WRONG
  * New: momentum=1.0 triggers overbought penalty = avoid chasing
- ADDED: RSI calculation and overbought filter
  * RSI > 70 = overbought = reduce score by 50%
  * RSI 40-60 = pullback zone = bonus 20%
- ADDED: Optimal momentum zone (3-7% moves)
  * Stocks with 3-7% moves score highest
  * Stocks with >10% moves get penalized (already extended)
- ADDED: Volume spike warning
  * Volume 3x+ average WITH high momentum = climax top warning
- Based on analysis: High scores were correlating with LOSSES, not wins
  * See: Documentation/Analysis/trading-performance-analysis-2025-12-20.md

v6.0.1 (2025-11-22) - SCHEMA FIX - ALIGNED WITH ACTUAL DATABASE
- FIXED: scan_results INSERT - removed scan_type, renamed columns to actual schema
  * price_at_scan → price
  * volume_at_scan → volume
  * rank_in_scan → rank
  * final_candidate → selected_for_trading
- FIXED: trading_cycles INSERT - uses actual columns (mode, configuration)
  * Removed: cycle_date, cycle_number, session_mode, triggered_by
  * Added: mode, configuration (JSONB)
- FIXED: trading_cycles UPDATE - uses stopped_at and configuration
  * Removed: scan_completed_at, candidates_identified
  * Added: stopped_at, configuration merge
- FIXED: Schema verification checks actual column names
- All database operations now match deployed schema

v6.0.0 (2025-11-18) - SCHEMA v6.0 3NF COMPLIANCE (HAD BUGS)
- Attempted v6.0 3NF compliance but had column name mismatches
- Used non-existent columns that caused runtime failures

v5.5.0 (2025-10-16) - SCHEMA v5.0 COMPLIANCE FIX
- Earlier schema compliance attempt

Description of Service:
Market scanner that scans for trading candidates and persists results.
Fixed to match actual deployed database schema (not design doc).
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
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus
import ta  # Technical analysis library for RSI
import pandas as pd

# ============================================================================
# SERVICE METADATA
# ============================================================================
SERVICE_NAME = "scanner"
SERVICE_VERSION = "6.1.0"
SERVICE_TITLE = "Scanner Service"
SCHEMA_VERSION = "actual deployed schema"
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
        self.alpaca_client: Optional[StockHistoricalDataClient] = None
        self.alpaca_trading_client: Optional[TradingClient] = None
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

    # Alpaca clients (optional - for market data and asset info)
    try:
        alpaca_api_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY")

        if alpaca_api_key and alpaca_secret_key:
            # Data client for historical/realtime market data
            state.alpaca_client = StockHistoricalDataClient(
                api_key=alpaca_api_key,
                secret_key=alpaca_secret_key
            )
            # Trading client for asset queries and trading (future)
            state.alpaca_trading_client = TradingClient(
                api_key=alpaca_api_key,
                secret_key=alpaca_secret_key,
                paper=True  # Use paper trading endpoint
            )
            logger.info("Alpaca clients initialized (market data + assets API enabled)")
        else:
            logger.warning("Alpaca credentials not found - limited universe mode")
    except Exception as e:
        logger.warning(f"Alpaca initialization failed: {e}")

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
    """Verify the database has the expected actual schema"""
    try:
        # Check trading_cycles has correct columns
        trading_cycles_cols = await state.db_pool.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'trading_cycles'
        """)

        cols = {row['column_name'] for row in trading_cycles_cols}
        # Actual schema columns
        required_cols = {'cycle_id', 'mode', 'status', 'started_at', 'configuration'}

        missing = required_cols - cols
        if missing:
            error_msg = f"Schema mismatch: Missing columns in trading_cycles: {missing}"
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

        # Check scan_results has correct columns
        scan_results_cols = await state.db_pool.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'scan_results'
        """)

        scan_cols = {row['column_name'] for row in scan_results_cols}
        # Actual schema - uses scan_id, price, volume, rank
        required_scan_cols = {'scan_id', 'cycle_id', 'security_id', 'composite_score',
                             'price', 'volume', 'rank', 'selected_for_trading'}

        missing_scan = required_scan_cols - scan_cols
        if missing_scan:
            error_msg = f"Schema mismatch: Missing columns in scan_results: {missing_scan}"
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

        logger.info("✅ Schema compatibility check completed")

    except RuntimeError:
        # Re-raise schema mismatch errors - these are critical
        raise
    except Exception as e:
        logger.critical(f"Schema verification failed unexpectedly: {e}", exc_info=True)
        raise RuntimeError(f"Schema verification failed: {e}") from e

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
async def get_security_id(symbol: str) -> int:
    """
    Get or create security_id for symbol using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_security() helper function.
    """
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)",
            symbol
        )

        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")

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
        # Create trading cycle with actual schema
        async with state.db_pool.acquire() as conn:
            # Generate cycle_id first
            generated_cycle_id = await generate_cycle_id()

            # Insert trading cycle
            cycle_id = await conn.fetchval("""
                INSERT INTO trading_cycles (
                    cycle_id,
                    mode,
                    status,
                    started_at,
                    configuration
                ) VALUES ($1, $2, $3, $4, $5)
                RETURNING cycle_id
            """,
                generated_cycle_id,
                'normal',
                'scanning',
                datetime.utcnow(),
                json.dumps({
                    'triggered_by': 'scanner_service',
                    'cycle_date': datetime.utcnow().date().isoformat()
                })
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
        
        # Update cycle status with actual schema columns
        await state.db_pool.execute(
            """
            UPDATE trading_cycles
            SET status = 'completed',
                stopped_at = $1,
                configuration = configuration || $2,
                updated_at = NOW()
            WHERE cycle_id = $3
            """,
            datetime.utcnow(),
            json.dumps({
                'scan_completed_at': datetime.utcnow().isoformat(),
                'candidates_identified': candidates_found
            }),
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
                        error_message = $1
                    WHERE cycle_id = $2
                    """,
                    str(e),      # error_message
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
    """
    Get most active stocks dynamically from Alpaca Assets API.

    Returns up to initial_universe_size stocks sorted by recent trading volume.
    Uses Alpaca's Assets API to get all tradable US equities, then fetches
    recent bar data to sort by volume.

    Fallback: Returns empty list if Alpaca not configured (will cause scan to fail safely).
    """
    try:
        if not state.alpaca_trading_client or not state.alpaca_client:
            logger.error("Alpaca not configured - cannot fetch universe")
            logger.error("Scanner requires Alpaca credentials. Set ALPACA_API_KEY and ALPACA_SECRET_KEY")
            return []

        logger.info("Fetching tradable assets from Alpaca Assets API...")

        # Get all active, tradable US stocks from Alpaca
        assets_request = GetAssetsRequest(
            asset_class=AssetClass.US_EQUITY,
            status=AssetStatus.ACTIVE
        )

        assets = state.alpaca_trading_client.get_all_assets(assets_request)

        # Filter for tradable stocks only (exclude crypto, etc)
        tradable_symbols = [
            asset.symbol for asset in assets
            if asset.tradable and asset.fractionable and asset.shortable
        ]

        logger.info(f"Found {len(tradable_symbols)} tradable US equities from Alpaca")

        # Sample a subset for volume checking (to avoid rate limits)
        # Take up to 500 symbols to check volume
        import random
        sample_size = min(500, len(tradable_symbols))
        sampled_symbols = random.sample(tradable_symbols, sample_size)

        logger.info(f"Sampling {sample_size} symbols to check volume...")

        # Get latest bar data for volume sorting
        # Split into batches to respect API limits
        symbols_with_volume = []
        batch_size = 100  # Alpaca allows ~200 symbols per request, use 100 to be safe

        for i in range(0, len(sampled_symbols), batch_size):
            batch = sampled_symbols[i:i + batch_size]

            try:
                # Get latest bars for volume data
                bars_request = StockLatestBarRequest(symbol_or_symbols=batch)
                latest_bars = state.alpaca_client.get_stock_latest_bar(bars_request)

                for symbol, bar in latest_bars.items():
                    if bar and bar.volume:
                        symbols_with_volume.append({
                            'symbol': symbol,
                            'volume': bar.volume,
                            'price': bar.close
                        })

            except Exception as e:
                logger.warning(f"Failed to get bars for batch {i//batch_size + 1}: {e}")
                continue

        # Sort by volume (descending) and filter by price range
        symbols_with_volume.sort(key=lambda x: x['volume'], reverse=True)

        # Filter by configured price range
        filtered_symbols = [
            s['symbol'] for s in symbols_with_volume
            if state.config.min_price <= s['price'] <= state.config.max_price
        ]

        # Return top N symbols
        universe = filtered_symbols[:state.config.initial_universe_size]

        logger.info(f"Selected top {len(universe)} most active stocks from Alpaca")
        logger.info(f"Top 10: {universe[:10]}")

        return universe

    except Exception as e:
        logger.error(f"Failed to get universe from Alpaca: {e}", exc_info=True)
        logger.error("Scanner cannot proceed without valid universe")
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
            
            # Get price data - need 14+ days for RSI calculation
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")  # Extended for RSI

            if hist.empty or len(hist) < 14:
                logger.warning(f"Insufficient price data for {symbol}")
                continue

            # Calculate base metrics
            current_price = float(hist['Close'].iloc[-1])
            avg_volume = int(hist['Volume'].mean())
            current_volume = int(hist['Volume'].iloc[-1])
            price_change = float((hist['Close'].iloc[-1] / hist['Close'].iloc[-5] - 1) * 100)  # 5-day change

            # ================================================================
            # IMPROVED SCORING LOGIC v6.1.0
            # Based on analysis: old scoring was CHASING momentum, not TRADING it
            # See: Documentation/Analysis/trading-performance-analysis-2025-12-20.md
            # ================================================================

            # --- RSI Calculation ---
            try:
                close_series = pd.Series(hist['Close'].values)
                rsi_indicator = ta.momentum.RSIIndicator(close_series, window=14)
                rsi = float(rsi_indicator.rsi().iloc[-1])
            except Exception:
                rsi = 50.0  # Neutral if calculation fails

            # --- MOMENTUM SCORE (Improved) ---
            # Old logic: Higher momentum = higher score (WRONG - chasing)
            # New logic: Optimal momentum is 3-7%, penalize extremes
            abs_change = abs(price_change)
            if abs_change < 2.0:
                # Too weak - not enough momentum
                momentum_score = abs_change / 2.0 * 0.5  # Max 0.5
            elif abs_change <= 7.0:
                # OPTIMAL ZONE (3-7% moves)
                momentum_score = 0.7 + (abs_change - 2.0) / 5.0 * 0.3  # 0.7 to 1.0
            else:
                # EXTENDED - penalize chasing (was the main problem!)
                # 10%+ moves get progressively worse scores
                momentum_score = max(0.3, 1.0 - (abs_change - 7.0) / 10.0)

            # --- VOLUME SCORE ---
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            volume_score = min(1.0, avg_volume / 10_000_000)

            # --- RSI ADJUSTMENT ---
            rsi_multiplier = 1.0
            if rsi > 70:
                # OVERBOUGHT - reduce score significantly
                rsi_multiplier = 0.5
                logger.debug(f"{symbol}: RSI={rsi:.1f} OVERBOUGHT, applying 0.5x penalty")
            elif rsi > 60:
                # Getting extended
                rsi_multiplier = 0.8
            elif 40 <= rsi <= 60:
                # PULLBACK ZONE - bonus
                rsi_multiplier = 1.2
                logger.debug(f"{symbol}: RSI={rsi:.1f} in pullback zone, 1.2x bonus")
            elif rsi < 30:
                # Oversold - could bounce
                rsi_multiplier = 1.1

            # --- VOLUME SPIKE WARNING ---
            # High volume + high momentum = likely climax top
            climax_penalty = 1.0
            if volume_ratio > 3.0 and momentum_score > 0.8:
                climax_penalty = 0.6
                logger.debug(f"{symbol}: Volume spike ({volume_ratio:.1f}x) with high momentum - climax warning")

            # --- TECHNICAL SCORE (RSI-adjusted) ---
            technical_score = ((momentum_score + volume_score) / 2) * rsi_multiplier

            # Add data to stock dict
            stock['momentum_score'] = round(momentum_score, 2)
            stock['volume_score'] = round(volume_score, 2)
            stock['technical_score'] = round(min(1.0, technical_score), 2)
            stock['price'] = current_price
            stock['volume'] = avg_volume
            stock['change_percent'] = price_change
            stock['rsi'] = round(rsi, 1)
            stock['volume_ratio'] = round(volume_ratio, 2)

            # --- COMPOSITE SCORE (with penalties applied) ---
            raw_composite = (
                stock['catalyst_score'] * 0.3 +
                stock['momentum_score'] * 0.2 +
                stock['volume_score'] * 0.2 +
                stock['technical_score'] * 0.3
            )
            stock['composite_score'] = round(raw_composite * climax_penalty, 2)
            
            # Only keep if meets criteria
            if (avg_volume >= state.config.min_volume and
                state.config.min_price <= current_price <= state.config.max_price):
                results.append(stock)
                logger.info(
                    f"[SCORE] {symbol}: composite={stock['composite_score']:.2f}, "
                    f"mom={stock['momentum_score']:.2f}, vol={stock['volume_score']:.2f}, "
                    f"tech={stock['technical_score']:.2f}, RSI={rsi:.1f}, chg={price_change:.1f}%"
                )

        except Exception as e:
            logger.error(f"Failed technical analysis for {stock.get('symbol')}: {e}")
            continue
    
    # Sort by composite score
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return results[:state.config.technical_filter_size]

async def persist_scan_results(cycle_id: str, picks: List[Dict]) -> bool:
    """
    Persist scan results using actual database schema columns
    """
    success_count = 0
    failure_count = 0
    
    try:
        scan_timestamp = datetime.utcnow()
        
        for i, pick in enumerate(picks, 1):
            try:
                # Store additional metrics in scan_metadata (RSI, volume_ratio, etc.)
                scan_metadata = json.dumps({
                    'rsi': pick.get('rsi', 50.0),
                    'volume_ratio': pick.get('volume_ratio', 1.0),
                    'change_percent': pick.get('change_percent', 0),
                    'scoring_version': '6.1.0'
                })

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
                        scan_metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                    cycle_id,
                    pick['security_id'],
                    scan_timestamp,
                    pick.get('momentum_score', 0),
                    pick.get('volume_score', 0),
                    pick.get('catalyst_score', 0),
                    pick.get('technical_score', 0),
                    pick.get('composite_score', 0),
                    pick.get('price', 0),
                    pick.get('volume', 0),
                    i,
                    True,
                    scan_metadata
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