#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: technical-service.py
Version: 6.0.0
Last Updated: 2025-11-18
Purpose: Technical analysis service using v6.0 3NF normalized schema

REVISION HISTORY:
v6.0.0 (2025-11-18) - SCHEMA v6.0 3NF COMPLIANCE
- Uses get_or_create_security() helper function
- Uses get_or_create_time() helper function
- Replaced security_dimension with securities table
- All queries use proper JOINs and helper functions
- Fully normalized 3NF schema compliance

v5.3.2 (2025-10-16) - Production-ready with 'ta' library
- Using 'ta' library (pure Python, no C dependencies)
- Matches industry-standard calculations
- Full indicator suite with proper error handling
- Redis caching for performance

v5.2.0 (2025-10-16) - Critical production fixes
- Added missing CORSMiddleware import

v5.0.0 (2025-10-11) - Normalized schema implementation

Description of Service:
Technical analysis service using the 'ta' library with v6.0 3NF normalized schema.
Provides comprehensive technical analysis with proper database helper functions.
"""

import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager

import asyncpg
import numpy as np
import pandas as pd
import ta  # Pure Python technical analysis library
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import aiohttp
import redis.asyncio as redis
import yfinance as yf

# ============================================================================
# SERVICE CONFIGURATION
# ============================================================================

SERVICE_NAME = "Technical Analysis Service"
SERVICE_VERSION = "6.0.0"
SCHEMA_VERSION = "v6.0 3NF normalized"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "5003"))

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")  # Gets "redis" from docker-compose
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
# Build Redis URL with optional password
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Global connections
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
http_session: Optional[aiohttp.ClientSession] = None

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TechnicalRequest(BaseModel):
    """Request for technical analysis"""
    symbol: str
    timeframe: str = Field(default="5m", description="1m, 5m, 15m, 1h, 1d")
    period: int = Field(default=100, ge=50, le=500)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        return v.upper().strip()

class TechnicalIndicators(BaseModel):
    """Technical indicators response"""
    symbol: str
    security_id: int
    timestamp: datetime
    price: float
    volume: int
    
    # Trend
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    
    # MACD
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # Momentum
    rsi: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    williams_r: Optional[float] = None
    cci: Optional[float] = None
    
    # Volatility
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    atr: Optional[float] = None
    
    # Volume
    obv: Optional[float] = None
    vwap: Optional[float] = None
    volume_ratio: Optional[float] = None
    
    # Signals
    signal: str  # BUY, SELL, HOLD
    signal_strength: float  # 0.0 to 1.0

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    timestamp: datetime
    database: str = "disconnected"
    redis: str = "disconnected"

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global db_pool, redis_client, http_session
    
    try:
        # Initialize database pool
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=10
        )
        logger.info("Database pool created successfully")
        
        # Initialize Redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected successfully")
        
        # Initialize HTTP session
        http_session = aiohttp.ClientSession()
        logger.info("HTTP session created")
        
        logger.info(f"{SERVICE_NAME} v{SERVICE_VERSION} started on port {SERVICE_PORT}")
        
        yield
        
    finally:
        # Cleanup
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")
        
        if redis_client:
            await redis_client.close()
            logger.info("Redis connection closed")
            
        if http_session:
            await http_session.close()
            logger.info("HTTP session closed")
        
        logger.info(f"{SERVICE_NAME} shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================================
# TECHNICAL INDICATORS CALCULATION USING 'ta' LIBRARY
# ============================================================================

def calculate_indicators(data: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate all technical indicators using 'ta' library
    This matches the approach from v4.1.0 which works correctly
    """
    indicators = {}
    
    try:
        # Ensure column names are lowercase
        data.columns = [col.lower() for col in data.columns]
        
        close = data['close']
        high = data['high']
        low = data['low']
        volume = data['volume']
        
        # Current values
        indicators['price'] = float(close.iloc[-1])
        indicators['volume'] = int(volume.iloc[-1])
        
        # ========== TREND INDICATORS ==========
        
        # Simple Moving Averages
        if len(close) >= 20:
            indicators['sma_20'] = float(ta.trend.sma_indicator(close, window=20).iloc[-1])
        else:
            indicators['sma_20'] = float(close.mean())
            
        if len(close) >= 50:
            indicators['sma_50'] = float(ta.trend.sma_indicator(close, window=50).iloc[-1])
        else:
            indicators['sma_50'] = indicators['sma_20']
        
        # Exponential Moving Averages
        indicators['ema_12'] = float(ta.trend.ema_indicator(close, window=12).iloc[-1])
        indicators['ema_26'] = float(ta.trend.ema_indicator(close, window=26).iloc[-1])
        
        # MACD
        macd = ta.trend.MACD(close)
        indicators['macd'] = float(macd.macd().iloc[-1])
        indicators['macd_signal'] = float(macd.macd_signal().iloc[-1])
        indicators['macd_histogram'] = float(macd.macd_diff().iloc[-1])
        
        # ========== MOMENTUM INDICATORS ==========
        
        # RSI
        rsi_indicator = ta.momentum.RSIIndicator(close, window=14)
        indicators['rsi'] = float(rsi_indicator.rsi().iloc[-1])
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
        indicators['stoch_k'] = float(stoch.stoch().iloc[-1])
        indicators['stoch_d'] = float(stoch.stoch_signal().iloc[-1])
        
        # Williams %R
        williams = ta.momentum.WilliamsRIndicator(high, low, close, lbp=14)
        indicators['williams_r'] = float(williams.williams_r().iloc[-1])
        
        # CCI
        cci = ta.trend.CCIIndicator(high, low, close, window=20)
        indicators['cci'] = float(cci.cci().iloc[-1])
        
        # ========== VOLATILITY INDICATORS ==========
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        indicators['bb_upper'] = float(bb.bollinger_hband().iloc[-1])
        indicators['bb_middle'] = float(bb.bollinger_mavg().iloc[-1])
        indicators['bb_lower'] = float(bb.bollinger_lband().iloc[-1])
        indicators['bb_width'] = float(bb.bollinger_wband().iloc[-1])
        
        # ATR
        atr = ta.volatility.AverageTrueRange(high, low, close, window=14)
        indicators['atr'] = float(atr.average_true_range().iloc[-1])
        
        # ========== VOLUME INDICATORS ==========
        
        # OBV
        obv = ta.volume.OnBalanceVolumeIndicator(close, volume)
        indicators['obv'] = float(obv.on_balance_volume().iloc[-1])
        
        # VWAP (calculate manually as ta doesn't have it)
        indicators['vwap'] = calculate_vwap(data)
        
        # Volume Ratio
        if len(volume) >= 20:
            avg_volume = volume.rolling(window=20).mean().iloc[-1]
            indicators['volume_ratio'] = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 1.0
        else:
            indicators['volume_ratio'] = 1.0
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        # Return default values on error
        return get_default_indicators(data)
    
    return indicators

def calculate_vwap(data: pd.DataFrame) -> float:
    """Calculate VWAP manually"""
    try:
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        vwap = (typical_price * data['volume']).sum() / data['volume'].sum()
        return float(vwap)
    except (KeyError, ZeroDivisionError, TypeError, ValueError) as e:
        logger.warning(f"VWAP calculation failed: {e}, using close price")
        return float(data['close'].iloc[-1])

def get_default_indicators(data: pd.DataFrame) -> Dict:
    """Return default indicator values when calculation fails"""
    close_price = float(data['close'].iloc[-1])
    volume = int(data['volume'].iloc[-1])
    
    return {
        'price': close_price,
        'volume': volume,
        'sma_20': close_price,
        'sma_50': close_price,
        'ema_12': close_price,
        'ema_26': close_price,
        'macd': 0.0,
        'macd_signal': 0.0,
        'macd_histogram': 0.0,
        'rsi': 50.0,
        'stoch_k': 50.0,
        'stoch_d': 50.0,
        'williams_r': -50.0,
        'cci': 0.0,
        'bb_upper': close_price * 1.02,
        'bb_middle': close_price,
        'bb_lower': close_price * 0.98,
        'bb_width': close_price * 0.04,
        'atr': close_price * 0.02,
        'obv': float(volume),
        'vwap': close_price,
        'volume_ratio': 1.0
    }

def generate_signal(indicators: Dict) -> Tuple[str, float]:
    """Generate trading signal from indicators"""
    signals = []
    score = 50  # Start neutral
    
    # RSI signals
    if indicators.get('rsi'):
        if indicators['rsi'] < 30:
            signals.append(("RSI_OVERSOLD", 20))
            score += 20
        elif indicators['rsi'] > 70:
            signals.append(("RSI_OVERBOUGHT", -20))
            score -= 20
    
    # MACD signals
    if indicators.get('macd') and indicators.get('macd_signal'):
        if indicators['macd'] > indicators['macd_signal']:
            signals.append(("MACD_BULLISH", 15))
            score += 15
        else:
            signals.append(("MACD_BEARISH", -15))
            score -= 15
    
    # Bollinger Band signals
    if indicators.get('price') and indicators.get('bb_lower') and indicators.get('bb_upper'):
        price = indicators['price']
        if price < indicators['bb_lower']:
            signals.append(("BB_OVERSOLD", 15))
            score += 15
        elif price > indicators['bb_upper']:
            signals.append(("BB_OVERBOUGHT", -15))
            score -= 15
    
    # Moving Average signals
    if indicators.get('price') and indicators.get('sma_20'):
        if indicators['price'] > indicators['sma_20']:
            signals.append(("ABOVE_SMA20", 10))
            score += 10
        else:
            signals.append(("BELOW_SMA20", -10))
            score -= 10
    
    # Stochastic signals
    if indicators.get('stoch_k'):
        if indicators['stoch_k'] < 20:
            signals.append(("STOCH_OVERSOLD", 10))
            score += 10
        elif indicators['stoch_k'] > 80:
            signals.append(("STOCH_OVERBOUGHT", -10))
            score -= 10
    
    # Volume signals
    if indicators.get('volume_ratio'):
        if indicators['volume_ratio'] > 1.5:
            signals.append(("HIGH_VOLUME", 5))
            score += 5
    
    # Normalize score
    score = max(0, min(100, score))
    
    # Determine signal
    if score >= 70:
        signal = "BUY"
    elif score <= 30:
        signal = "SELL"
    else:
        signal = "HOLD"
    
    signal_strength = score / 100.0
    
    return signal, signal_strength

# ============================================================================
# DATABASE HELPERS
# ============================================================================

async def get_security_id(symbol: str) -> int:
    """
    Get security_id from symbol using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_security() helper function.
    """
    async with db_pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT get_or_create_security($1)",
            symbol
        )
        if not result:
            raise ValueError(f"Failed to get security_id for {symbol}")
        return result

async def get_time_id() -> int:
    """
    Get or create time_id for current timestamp using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_time() helper function.
    """
    now = datetime.now()
    async with db_pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT get_or_create_time($1)",
            now
        )
        if not result:
            raise ValueError(f"Failed to get time_id for {now}")
        return result

async def fetch_price_data(symbol: str, timeframe: str, periods: int = 100) -> pd.DataFrame:
    """Fetch price data from database or yfinance"""
    
    # Try database first
    security_id = await get_security_id(symbol)
    
    async with db_pool.acquire() as conn:
        # Map timeframe to interval
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes", 
            "15m": "15 minutes",
            "1h": "1 hour",
            "1d": "1 day"
        }
        interval = interval_map.get(timeframe, "5 minutes")
        
        query = f"""
            SELECT 
                td.timestamp,
                th.open_price as open,
                th.high_price as high,
                th.low_price as low,
                th.close_price as close,
                th.volume
            FROM trading_history th
            JOIN time_dimension td ON td.time_id = th.time_id
            WHERE th.security_id = $1
                AND td.timestamp >= NOW() - INTERVAL '{periods} {interval}'
            ORDER BY td.timestamp ASC
        """
        
        rows = await conn.fetch(query, security_id)
    
    if len(rows) < 50:
        # Fallback to yfinance
        logger.info(f"Insufficient data in DB for {symbol}, using yfinance")
        
        period_map = {
            "1m": "1d",
            "5m": "5d",
            "15m": "5d",
            "1h": "1mo",
            "1d": "3mo"
        }
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period_map.get(timeframe, "1mo"), interval=timeframe)
        
        if df.empty:
            raise ValueError(f"No data available for {symbol}")
        
        # Standardize column names
        df.columns = [col.lower() for col in df.columns]
        return df
    
    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df.set_index('timestamp', inplace=True)
    return df

async def store_indicators(security_id: int, timeframe: str, indicators: Dict):
    """Store indicators in database"""

    try:
        time_id = await get_time_id()

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO technical_indicators (
                    security_id, time_id, timeframe,
                    rsi_14, macd, macd_signal, macd_histogram,
                    bollinger_upper, bollinger_middle, bollinger_lower,
                    sma_20, sma_50, ema_12, ema_26,
                    atr_14, obv, stochastic_k, stochastic_d,
                    calculated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                         $11, $12, $13, $14, $15, $16, $17, $18, NOW())
                ON CONFLICT (security_id, time_id, timeframe)
                DO UPDATE SET
                    rsi_14 = EXCLUDED.rsi_14,
                    macd = EXCLUDED.macd,
                    calculated_at = NOW()
                """,
                security_id, time_id, timeframe,
                indicators.get('rsi'),
                indicators.get('macd'),
                indicators.get('macd_signal'),
                indicators.get('macd_histogram'),
                indicators.get('bb_upper'),
                indicators.get('bb_middle'),
                indicators.get('bb_lower'),
                indicators.get('sma_20'),
                indicators.get('sma_50'),
                indicators.get('ema_12'),
                indicators.get('ema_26'),
                indicators.get('atr'),
                indicators.get('obv'),
                indicators.get('stoch_k'),
                indicators.get('stoch_d')
            )
    except asyncpg.PostgresError as e:
        logger.error(f"Database error storing indicators for security_id={security_id}, timeframe={timeframe}: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error storing indicators for security_id={security_id}, timeframe={timeframe}: {e}", exc_info=True)
        raise

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    
    db_status = "disconnected"
    redis_status = "disconnected"
    
    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "healthy"
    except (asyncpg.PostgresError, asyncpg.InterfaceError, ConnectionError) as e:
        logger.warning(f"Database health check failed: {e}")
        pass
    
    try:
        if redis_client:
            await redis_client.ping()
            redis_status = "healthy"
    except (redis.RedisError, ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis health check failed: {e}")
        pass
    
    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        timestamp=datetime.now(),
        database=db_status,
        redis=redis_status
    )

@app.post("/api/v1/indicators/calculate", response_model=TechnicalIndicators)
async def calculate_indicators_endpoint(request: TechnicalRequest):
    """Calculate technical indicators for a symbol"""
    
    try:
        # Check cache first
        cache_key = f"indicators:{request.symbol}:{request.timeframe}"
        if redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                return TechnicalIndicators(**json.loads(cached))
        
        # Fetch price data
        df = await fetch_price_data(request.symbol, request.timeframe, request.period)
        
        if len(df) < 20:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for {request.symbol}"
            )
        
        # Calculate indicators
        indicators = calculate_indicators(df)
        
        # Generate signal
        signal, signal_strength = generate_signal(indicators)
        
        # Get security_id
        security_id = await get_security_id(request.symbol)
        
        # Store in database
        await store_indicators(security_id, request.timeframe, indicators)
        
        # Create response
        response = TechnicalIndicators(
            symbol=request.symbol,
            security_id=security_id,
            timestamp=datetime.now(),
            price=indicators['price'],
            volume=indicators['volume'],
            sma_20=indicators.get('sma_20'),
            sma_50=indicators.get('sma_50'),
            ema_12=indicators.get('ema_12'),
            ema_26=indicators.get('ema_26'),
            macd=indicators.get('macd'),
            macd_signal=indicators.get('macd_signal'),
            macd_histogram=indicators.get('macd_histogram'),
            rsi=indicators.get('rsi'),
            stoch_k=indicators.get('stoch_k'),
            stoch_d=indicators.get('stoch_d'),
            williams_r=indicators.get('williams_r'),
            cci=indicators.get('cci'),
            bb_upper=indicators.get('bb_upper'),
            bb_middle=indicators.get('bb_middle'),
            bb_lower=indicators.get('bb_lower'),
            bb_width=indicators.get('bb_width'),
            atr=indicators.get('atr'),
            obv=indicators.get('obv'),
            vwap=indicators.get('vwap'),
            volume_ratio=indicators.get('volume_ratio'),
            signal=signal,
            signal_strength=signal_strength
        )
        
        # Cache the result
        if redis_client:
            await redis_client.setex(
                cache_key,
                60,  # 60 seconds TTL
                response.model_dump_json()
            )
        
        logger.info(f"Calculated indicators for {request.symbol}: {signal} ({signal_strength:.2f})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/indicators/{symbol}/latest", response_model=TechnicalIndicators)
async def get_latest_indicators(symbol: str, timeframe: str = "5m"):
    """Get latest indicators for a symbol"""
    
    request = TechnicalRequest(symbol=symbol, timeframe=timeframe)
    return await calculate_indicators_endpoint(request)

@app.post("/api/v1/indicators/batch")
async def calculate_batch(symbols: List[str], timeframe: str = "5m"):
    """Calculate indicators for multiple symbols"""
    
    results = []
    for symbol in symbols[:10]:  # Limit to 10 symbols
        try:
            request = TechnicalRequest(symbol=symbol, timeframe=timeframe)
            result = await calculate_indicators_endpoint(request)
            results.append(result.model_dump())
        except Exception as e:
            logger.warning(f"Failed to calculate indicators for {symbol}: {e}")
            results.append({
                "symbol": symbol,
                "error": str(e)
            })
    
    return {"results": results}

@app.get("/api/v1/support-resistance/{symbol}")
async def get_support_resistance(symbol: str, timeframe: str = "1d"):
    """Get support and resistance levels"""
    
    try:
        df = await fetch_price_data(symbol, timeframe, 100)
        
        # Calculate pivot points
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        close = df['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            "symbol": symbol,
            "current_price": float(close),
            "pivot_point": float(pivot),
            "resistance_levels": [float(r1), float(r2), float(r3)],
            "support_levels": [float(s1), float(s2), float(s3)],
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error calculating support/resistance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVICE_PORT,
        log_level="info"
    )