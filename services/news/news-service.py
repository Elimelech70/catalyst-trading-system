#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: news-service.py
Version: 6.0.1
Last Updated: 2025-12-05
Purpose: News sentiment analysis service using v6.0 3NF normalized schema

REVISION HISTORY:
v6.0.1 (2025-12-05) - FIX SCHEMA COLUMN NAMES
- Fixed time_dimension queries to use 'timestamp' instead of 'full_timestamp'
- The full_timestamp column does not exist in deployed schema

v6.0.0 (2025-11-18) - Initial v6.0 implementation
- Uses get_or_create_security() helper function
- Uses get_or_create_time() helper function
- Proper JOINs with securities and time_dimension tables
- Full 3NF normalized schema compliance

Description:
News sentiment analysis service that fetches news and analyzes sentiment.
Uses v6.0 3NF normalized schema with helper functions.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio
import asyncpg
import json
import os
import logging
from pydantic import BaseModel
import uvicorn

# ============================================================================
# SERVICE METADATA
# ============================================================================
SERVICE_NAME = "news"
SERVICE_VERSION = "6.0.0"
SERVICE_TITLE = "News Service"
SCHEMA_VERSION = "v6.0 3NF normalized"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "5008"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(SERVICE_NAME)

# ============================================================================
# SERVICE STATE
# ============================================================================
class NewsState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None

state = NewsState()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================
class NewsSentimentRequest(BaseModel):
    symbol: str
    headline: str
    source: Optional[str] = "API"
    url: Optional[str] = None
    sentiment_score: float
    is_catalyst: bool = False
    published_at: Optional[datetime] = None

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

        # Verify helper functions exist
        await verify_helper_functions()

    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        raise

    logger.info(f"{SERVICE_TITLE} ready on port {SERVICE_PORT}")

    yield

    # === SHUTDOWN ===
    logger.info(f"Shutting down {SERVICE_TITLE}")
    if state.db_pool:
        await state.db_pool.close()
    logger.info(f"{SERVICE_TITLE} shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title=SERVICE_TITLE,
    version=SERVICE_VERSION,
    description=f"News sentiment analysis with {SCHEMA_VERSION} schema compliance",
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
# HELPER FUNCTIONS
# ============================================================================
async def verify_helper_functions():
    """Verify v6.0 helper functions exist"""
    try:
        # Check for get_or_create_security
        has_security_helper = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_proc
                WHERE proname = 'get_or_create_security'
            )
        """)

        # Check for get_or_create_time
        has_time_helper = await state.db_pool.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_proc
                WHERE proname = 'get_or_create_time'
            )
        """)

        if not has_security_helper or not has_time_helper:
            missing = []
            if not has_security_helper:
                missing.append("get_or_create_security()")
            if not has_time_helper:
                missing.append("get_or_create_time()")
            error_msg = f"Required helper functions not found in database: {', '.join(missing)}"
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

        logger.info("✅ Helper functions verified")

    except Exception as e:
        logger.error(f"Helper function verification failed: {e}")

async def get_security_id(symbol: str) -> int:
    """
    Get or create security_id for symbol using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_security() helper function.
    """
    try:
        security_id = await state.db_pool.fetchval(
            "SELECT get_or_create_security($1)",
            symbol.upper()
        )

        if not security_id:
            raise ValueError(f"Failed to get security_id for {symbol}")

        return security_id

    except Exception as e:
        logger.error(f"Failed to get/create security_id for {symbol}: {e}")
        raise

async def get_time_id(timestamp: datetime) -> int:
    """
    Get or create time_id for timestamp using v6.0 helper function.

    v6.0 Pattern: Always use get_or_create_time() helper function.
    """
    try:
        time_id = await state.db_pool.fetchval(
            "SELECT get_or_create_time($1)",
            timestamp
        )

        if not time_id:
            raise ValueError(f"Failed to get time_id for {timestamp}")

        return time_id

    except Exception as e:
        logger.error(f"Failed to get/create time_id for {timestamp}: {e}")
        raise

# ============================================================================
# CORE NEWS LOGIC
# ============================================================================
async def save_news_sentiment(data: NewsSentimentRequest) -> int:
    """
    Save news sentiment using v6.0 normalized schema.

    v6.0 Pattern:
    - Use get_or_create_security() for security_id
    - Use get_or_create_time() for time_id
    - INSERT with FKs, not raw symbol/timestamp
    """
    try:
        # Get IDs using helper functions
        security_id = await get_security_id(data.symbol)

        published_at = data.published_at or datetime.utcnow()
        time_id = await get_time_id(published_at)

        # Insert news sentiment with FKs
        news_id = await state.db_pool.fetchval("""
            INSERT INTO news_sentiment (
                security_id,
                time_id,
                headline,
                source,
                url,
                sentiment_score,
                is_catalyst,
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING news_id
        """,
            security_id,
            time_id,
            data.headline,
            data.source,
            data.url,
            data.sentiment_score,
            data.is_catalyst,
            datetime.utcnow()
        )

        logger.info(f"Saved news sentiment {news_id} for {data.symbol}")
        return news_id

    except Exception as e:
        logger.error(f"Failed to save news sentiment: {e}", exc_info=True)
        raise

# ============================================================================
# API ENDPOINTS
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
        "database": "connected" if state.db_pool else "disconnected"
    }

@app.post("/api/v1/sentiment")
async def create_sentiment(request: NewsSentimentRequest):
    """Create news sentiment entry"""
    try:
        news_id = await save_news_sentiment(request)

        return {
            "success": True,
            "news_id": news_id,
            "symbol": request.symbol,
            "sentiment_score": request.sentiment_score,
            "is_catalyst": request.is_catalyst
        }

    except Exception as e:
        logger.error(f"API error in create_sentiment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sentiment/{symbol}")
async def get_sentiment(symbol: str, hours: int = 24, limit: int = 10):
    """
    Get recent news sentiment for a symbol.

    v6.0 Pattern: Uses JOINs to get symbol and timestamp from FKs.
    """
    try:
        security_id = await get_security_id(symbol)

        # Query with JOINs
        news_items = await state.db_pool.fetch("""
            SELECT
                ns.news_id,
                s.symbol,
                td.timestamp as published_at,
                ns.headline,
                ns.source,
                ns.url,
                ns.sentiment_score,
                ns.catalyst_type,
                ns.catalyst_strength,
                ns.created_at
            FROM news_sentiment ns
            JOIN securities s ON s.security_id = ns.security_id
            JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE ns.security_id = $1
              AND td.timestamp >= NOW() - INTERVAL '1 hour' * $2
            ORDER BY td.timestamp DESC
            LIMIT $3
        """, security_id, hours, limit)

        results = [dict(row) for row in news_items]

        return {
            "success": True,
            "symbol": symbol,
            "count": len(results),
            "news": results
        }

    except Exception as e:
        logger.error(f"Failed to get sentiment for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/catalysts")
async def get_catalysts(hours: int = 24, limit: int = 20):
    """
    Get recent catalyst news across all symbols.

    v6.0 Pattern: Uses JOINs to retrieve symbol and timestamp.
    """
    try:
        catalysts = await state.db_pool.fetch("""
            SELECT
                ns.news_id,
                s.symbol,
                s.company_name,
                td.timestamp as published_at,
                ns.headline,
                ns.source,
                ns.sentiment_score,
                ns.catalyst_type,
                ns.catalyst_strength
            FROM news_sentiment ns
            JOIN securities s ON s.security_id = ns.security_id
            JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE ns.catalyst_type IS NOT NULL
              AND td.timestamp >= NOW() - INTERVAL '1 hour' * $1
            ORDER BY ns.sentiment_score DESC, td.timestamp DESC
            LIMIT $2
        """, hours, limit)

        results = [dict(row) for row in catalysts]

        return {
            "success": True,
            "count": len(results),
            "catalysts": results
        }

    except Exception as e:
        logger.error(f"Failed to get catalysts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sentiment/aggregate/{symbol}")
async def get_aggregate_sentiment(symbol: str, hours: int = 24):
    """
    Get aggregate sentiment statistics for a symbol.

    v6.0 Pattern: Aggregation query with JOINs.
    """
    try:
        security_id = await get_security_id(symbol)

        stats = await state.db_pool.fetchrow("""
            SELECT
                s.symbol,
                COUNT(*) as news_count,
                AVG(ns.sentiment_score) as avg_sentiment,
                MAX(ns.sentiment_score) as max_sentiment,
                MIN(ns.sentiment_score) as min_sentiment,
                COUNT(*) FILTER (WHERE ns.catalyst_type IS NOT NULL) as catalyst_count
            FROM news_sentiment ns
            JOIN securities s ON s.security_id = ns.security_id
            JOIN time_dimension td ON td.time_id = ns.time_id
            WHERE ns.security_id = $1
              AND td.timestamp >= NOW() - INTERVAL '1 hour' * $2
            GROUP BY s.symbol
        """, security_id, hours)

        if not stats:
            return {
                "success": True,
                "symbol": symbol,
                "news_count": 0,
                "avg_sentiment": 0,
                "message": "No news found"
            }

        return {
            "success": True,
            "symbol": symbol,
            "news_count": stats['news_count'],
            "avg_sentiment": float(stats['avg_sentiment'] or 0),
            "max_sentiment": float(stats['max_sentiment'] or 0),
            "min_sentiment": float(stats['min_sentiment'] or 0),
            "catalyst_count": stats['catalyst_count']
        }

    except Exception as e:
        logger.error(f"Failed to get aggregate sentiment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "news-service:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
        log_level="info"
    )
