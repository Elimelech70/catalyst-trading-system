#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: reporting-service.py
Version: 5.1.1
Last Updated: 2025-10-13
Purpose: Reporting and analytics with normalized schema v5.0 and rigorous error handling

REVISION HISTORY:
v5.1.1 (2025-10-16) - Fix DATABASE_URL only Digital Ocean
v5.1.0 (2025-10-13) - Production Error Handling Upgrade
- NO Unicode emojis (ASCII only)
- Specific exception types (ValueError, asyncpg.PostgresError)
- Structured logging with exc_info
- HTTPException with proper status codes
- No silent failures - report generation errors tracked
- FastAPI lifespan
- All queries use JOINs for normalized schema

v5.0.0 (2025-10-06) - Normalized schema support

Description of Service:
Generate trading reports and analytics using normalized v5.0 schema.
All reports use JOINs (positions → securities → sectors).
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager
from decimal import Decimal
import asyncpg
import os
import logging
import json

SERVICE_NAME = "reporting"
SERVICE_VERSION = "5.1.0"
SERVICE_PORT = 5009

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(SERVICE_NAME)

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable required")
    POOL_MIN_SIZE = 2
    POOL_MAX_SIZE = 10

class ServiceState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.is_healthy = False

state = ServiceState()

class PerformanceMetrics(BaseModel):
    cycle_id: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: Optional[float]
    avg_r_multiple: Optional[float]

class DailyReportResponse(BaseModel):
    cycle_id: int
    date: str
    summary: Dict
    positions: List[Dict]
    patterns: List[Dict]
    sector_breakdown: List[Dict]
    risk_metrics: Dict

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[STARTUP] Reporting Service v{SERVICE_VERSION}")
    try:
        state.db_pool = await asyncpg.create_pool(
            Config.DATABASE_URL,
            min_size=Config.POOL_MIN_SIZE,
            max_size=Config.POOL_MAX_SIZE
        )
        logger.info("[STARTUP] Database connected")
        state.is_healthy = True
    except asyncpg.PostgresError as e:
        logger.critical(f"[STARTUP] Database connection failed: {e}", exc_info=True,
                       extra={'error_type': 'database'})
        state.is_healthy = False
    yield
    logger.info("[SHUTDOWN] Closing database")
    if state.db_pool:
        await state.db_pool.close()

app = FastAPI(
    title="Reporting Service",
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

def get_db():
    """Dependency to check database availability"""
    if not state.db_pool:
        raise HTTPException(
            status_code=503,
            detail={'error': 'Database unavailable', 'retry_after': 30}
        )
    return state.db_pool

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if state.is_healthy else "unhealthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "database": "connected" if state.db_pool else "disconnected"
    }

@app.get("/api/v1/reports/daily", response_model=DailyReportResponse)
async def get_daily_report(
    cycle_id: int,
    report_date: Optional[date] = None,
    conn: asyncpg.Pool = Depends(get_db)
):
    """
    Generate daily report for a cycle.
    
    Uses JOINs to get security/sector info.
    
    Raises:
        HTTPException 400: Invalid parameters
        HTTPException 503: Database unavailable
        HTTPException 500: Internal error
    """
    try:
        if cycle_id < 1:
            raise ValueError(f"Invalid cycle_id: {cycle_id}")
        
        if not report_date:
            report_date = date.today()
        
        # Get daily summary
        summary = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'open') as open_positions,
                COUNT(*) FILTER (WHERE status = 'closed' AND DATE(closed_at) = $2) as closed_today,
                COALESCE(SUM(realized_pnl) FILTER (WHERE status = 'closed' AND DATE(closed_at) = $2), 0) as realized_pnl,
                COALESCE(SUM(unrealized_pnl) FILTER (WHERE status = 'open'), 0) as unrealized_pnl,
                COUNT(*) FILTER (WHERE status = 'closed' AND DATE(closed_at) = $2 AND realized_pnl > 0) as winners_today,
                COUNT(*) FILTER (WHERE status = 'closed' AND DATE(closed_at) = $2 AND realized_pnl < 0) as losers_today
            FROM positions
            WHERE cycle_id = $1
        """, cycle_id, report_date)
        
        # Get positions with JOINs
        positions = await conn.fetch("""
            SELECT 
                p.*,
                s.symbol,
                s.company_name,
                sec.sector_name
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND (p.status = 'open' OR DATE(p.closed_at) = $2)
            ORDER BY p.created_at DESC
        """, cycle_id, report_date)
        
        # Get patterns detected today
        patterns = await conn.fetch("""
            SELECT 
                pa.*,
                s.symbol,
                td.timestamp as detected_at
            FROM pattern_analysis pa
            JOIN securities s ON s.security_id = pa.security_id
            JOIN time_dimension td ON td.time_id = pa.time_id
            WHERE DATE(td.timestamp) = $1
            ORDER BY pa.confidence_score DESC
            LIMIT 10
        """, report_date)
        
        # Sector breakdown
        sector_breakdown = await conn.fetch("""
            SELECT 
                sec.sector_name,
                COUNT(*) as position_count,
                SUM(p.quantity * p.entry_price) as exposure,
                SUM(p.realized_pnl) as sector_pnl
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE p.cycle_id = $1
            AND p.status = 'open'
            GROUP BY sec.sector_name
            ORDER BY exposure DESC
        """, cycle_id)
        
        # Risk metrics (placeholder)
        risk_metrics_row = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_positions
            FROM positions
            WHERE cycle_id = $1
            AND status = 'open'
        """, cycle_id)
        
        # Build response
        total_pnl = float(summary['realized_pnl'] or 0) + float(summary['unrealized_pnl'] or 0)
        winners = summary['winners_today'] or 0
        losers = summary['losers_today'] or 0
        win_rate = winners / (winners + losers) if (winners + losers) > 0 else 0
        
        logger.info(f"Daily report generated for cycle {cycle_id}",
                   extra={'cycle_id': cycle_id, 'date': str(report_date)})
        
        return DailyReportResponse(
            cycle_id=cycle_id,
            date=report_date.isoformat(),
            summary={
                'open_positions': summary['open_positions'],
                'closed_today': summary['closed_today'],
                'realized_pnl': float(summary['realized_pnl'] or 0),
                'unrealized_pnl': float(summary['unrealized_pnl'] or 0),
                'total_pnl': total_pnl,
                'winners_today': winners,
                'losers_today': losers,
                'win_rate_today': win_rate
            },
            positions=[dict(r) for r in positions],
            patterns=[dict(r) for r in patterns],
            sector_breakdown=[dict(r) for r in sector_breakdown],
            risk_metrics=dict(risk_metrics_row) if risk_metrics_row else {}
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'cycle_id': cycle_id, 'error_type': 'validation'})
        raise HTTPException(
            status_code=400,
            detail={'error': 'Invalid parameters', 'message': str(e)}
        )
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True,
                       extra={'cycle_id': cycle_id, 'error_type': 'database'})
        raise HTTPException(
            status_code=503,
            detail={'error': 'Database unavailable', 'retry_after': 30}
        )
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True,
                       extra={'cycle_id': cycle_id, 'error_type': 'unexpected'})
        raise HTTPException(
            status_code=500,
            detail={'error': 'Internal server error', 'message': 'Report generation failed'}
        )

@app.get("/api/v1/reports/performance", response_model=PerformanceMetrics)
async def get_performance_metrics(
    cycle_id: int,
    days: int = 30,
    conn: asyncpg.Pool = Depends(get_db)
):
    """
    Get performance metrics for the cycle.
    
    Raises:
        HTTPException 400: Invalid parameters
        HTTPException 503: Database unavailable
        HTTPException 500: Internal error
    """
    try:
        if cycle_id < 1:
            raise ValueError(f"Invalid cycle_id: {cycle_id}")
        
        if days < 1 or days > 365:
            raise ValueError(f"days must be 1-365, got {days}")
        
        # Get closed positions
        metrics = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(*) FILTER (WHERE realized_pnl > 0) as winning_trades,
                COUNT(*) FILTER (WHERE realized_pnl < 0) as losing_trades,
                COALESCE(SUM(realized_pnl), 0) as total_pnl,
                AVG(realized_pnl) FILTER (WHERE realized_pnl > 0) as avg_win,
                AVG(realized_pnl) FILTER (WHERE realized_pnl < 0) as avg_loss,
                MAX(realized_pnl) as largest_win,
                MIN(realized_pnl) as largest_loss,
                SUM(realized_pnl) FILTER (WHERE realized_pnl > 0) as gross_profit,
                ABS(SUM(realized_pnl) FILTER (WHERE realized_pnl < 0)) as gross_loss,
                AVG(realized_pnl / NULLIF(risk_amount, 0)) as avg_r_multiple
            FROM positions
            WHERE cycle_id = $1
            AND status = 'closed'
            AND closed_at >= NOW() - INTERVAL '1 day' * $2
        """, cycle_id, days)
        
        if not metrics or metrics['total_trades'] == 0:
            return PerformanceMetrics(
                cycle_id=cycle_id,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                average_win=0.0,
                average_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                profit_factor=None,
                avg_r_multiple=None
            )
        
        # Calculate profit factor
        profit_factor = None
        gross_loss = metrics['gross_loss']
        if gross_loss and gross_loss > 0:
            profit_factor = float(metrics['gross_profit']) / float(gross_loss)
        
        win_rate = metrics['winning_trades'] / metrics['total_trades']
        
        logger.info(f"Performance metrics calculated for cycle {cycle_id}",
                   extra={'cycle_id': cycle_id, 'total_trades': metrics['total_trades']})
        
        return PerformanceMetrics(
            cycle_id=cycle_id,
            total_trades=metrics['total_trades'],
            winning_trades=metrics['winning_trades'],
            losing_trades=metrics['losing_trades'],
            win_rate=win_rate,
            total_pnl=float(metrics['total_pnl'] or 0),
            average_win=float(metrics['avg_win'] or 0),
            average_loss=float(metrics['avg_loss'] or 0),
            largest_win=float(metrics['largest_win'] or 0),
            largest_loss=float(metrics['largest_loss'] or 0),
            profit_factor=profit_factor,
            avg_r_multiple=float(metrics['avg_r_multiple']) if metrics['avg_r_multiple'] else None
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'cycle_id': cycle_id, 'error_type': 'validation'})
        raise HTTPException(status_code=400, detail={'error': 'Invalid parameters', 'message': str(e)})
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True, extra={'cycle_id': cycle_id, 'error_type': 'database'})
        raise HTTPException(status_code=503, detail={'error': 'Database unavailable', 'retry_after': 30})
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True, extra={'cycle_id': cycle_id, 'error_type': 'unexpected'})
        raise HTTPException(status_code=500, detail={'error': 'Internal server error'})

@app.get("/api/v1/reports/position-history/{symbol}")
async def get_position_history(
    symbol: str,
    cycle_id: int,
    limit: int = 50,
    conn: asyncpg.Pool = Depends(get_db)
):
    """
    Get position history for a symbol using security_id.
    
    Uses JOIN to resolve symbol → security_id.
    """
    try:
        if not symbol or len(symbol) > 10:
            raise ValueError(f"Invalid symbol: {symbol}")
        
        symbol = symbol.upper()
        
        # Query with JOIN
        positions = await conn.fetch("""
            SELECT 
                p.*,
                s.symbol,
                s.company_name,
                sec.sector_name
            FROM positions p
            JOIN securities s ON s.security_id = p.security_id
            JOIN sectors sec ON sec.sector_id = s.sector_id
            WHERE s.symbol = $1
            AND p.cycle_id = $2
            ORDER BY p.created_at DESC
            LIMIT $3
        """, symbol, cycle_id, limit)
        
        logger.info(f"Position history retrieved for {symbol}",
                   extra={'symbol': symbol, 'count': len(positions)})
        
        return {
            "symbol": symbol,
            "cycle_id": cycle_id,
            "count": len(positions),
            "positions": [dict(p) for p in positions]
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}", extra={'symbol': symbol, 'error_type': 'validation'})
        raise HTTPException(status_code=400, detail={'error': 'Invalid parameters', 'message': str(e)})
    except asyncpg.PostgresError as e:
        logger.critical(f"Database error: {e}", exc_info=True, extra={'symbol': symbol, 'error_type': 'database'})
        raise HTTPException(status_code=503, detail={'error': 'Database unavailable', 'retry_after': 30})
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True, extra={'symbol': symbol, 'error_type': 'unexpected'})
        raise HTTPException(status_code=500, detail={'error': 'Internal server error'})

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print(f"Catalyst Trading System - Reporting Service v{SERVICE_VERSION}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT, log_level="info")
