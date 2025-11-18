#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: workflow-service.py
Version: 6.0.0
Last Updated: 2025-11-18
Purpose: Workflow orchestration service using v6.0 3NF normalized schema

REVISION HISTORY:
v6.0.0 (2025-11-18) - Initial v6.0 implementation
- Uses get_or_create_security() helper function where needed
- Proper JOINs with scan_results and securities tables
- Full 3NF normalized schema compliance
- Manages trading cycles and workflow orchestration

Description:
Workflow orchestration service that manages trading cycles and coordinates
between scanner, technical, and trading services.
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
from enum import Enum
import uvicorn

# ============================================================================
# SERVICE METADATA
# ============================================================================
SERVICE_NAME = "workflow"
SERVICE_VERSION = "6.0.0"
SERVICE_TITLE = "Workflow Service"
SCHEMA_VERSION = "v6.0 3NF normalized"
SERVICE_PORT = 5006

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(SERVICE_NAME)

# ============================================================================
# ENUMS
# ============================================================================
class CycleStatus(str, Enum):
    ACTIVE = "active"
    SCANNING = "scanning"
    COMPLETED = "completed"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

class CycleMode(str, Enum):
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"

# ============================================================================
# SERVICE STATE
# ============================================================================
class WorkflowState:
    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None

state = WorkflowState()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================
class CreateCycleRequest(BaseModel):
    mode: CycleMode = CycleMode.NORMAL
    max_positions: int = 5
    max_daily_loss: float = 2000.0
    scan_frequency: int = 300
    configuration: Optional[Dict] = None

class UpdateCycleRequest(BaseModel):
    status: Optional[CycleStatus] = None
    current_positions: Optional[int] = None
    configuration: Optional[Dict] = None

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
    description=f"Workflow orchestration with {SCHEMA_VERSION} schema compliance",
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
def generate_cycle_id() -> str:
    """Generate cycle_id in format YYYYMMDD-NNN"""
    today = datetime.utcnow().strftime('%Y%m%d')
    timestamp = datetime.utcnow().strftime('%H%M%S')
    return f"{today}-{timestamp}"

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

@app.post("/api/v1/cycles")
async def create_cycle(request: CreateCycleRequest):
    """
    Create a new trading cycle.

    v6.0 Pattern: Cycle management doesn't directly use security_id,
    but queries that JOIN to other tables need to use proper schema.
    """
    try:
        cycle_id = generate_cycle_id()

        config = request.configuration or {}
        config["created_at"] = datetime.utcnow().isoformat()

        await state.db_pool.execute("""
            INSERT INTO trading_cycles (
                cycle_id,
                mode,
                status,
                max_positions,
                max_daily_loss,
                scan_frequency,
                started_at,
                configuration,
                current_positions,
                created_at,
                updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            cycle_id,
            request.mode.value,
            CycleStatus.ACTIVE.value,
            request.max_positions,
            request.max_daily_loss,
            request.scan_frequency,
            datetime.utcnow(),
            json.dumps(config),
            0,
            datetime.utcnow(),
            datetime.utcnow()
        )

        logger.info(f"Created trading cycle: {cycle_id}")

        return {
            "success": True,
            "cycle_id": cycle_id,
            "mode": request.mode.value,
            "status": CycleStatus.ACTIVE.value,
            "max_positions": request.max_positions
        }

    except Exception as e:
        logger.error(f"Failed to create cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/cycles/{cycle_id}")
async def get_cycle(cycle_id: str):
    """
    Get trading cycle details.

    v6.0 Pattern: Uses JOINs when querying related data.
    """
    try:
        cycle = await state.db_pool.fetchrow("""
            SELECT
                cycle_id,
                mode,
                status,
                max_positions,
                max_daily_loss,
                scan_frequency,
                started_at,
                stopped_at,
                current_positions,
                configuration,
                created_at,
                updated_at
            FROM trading_cycles
            WHERE cycle_id = $1
        """, cycle_id)

        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        result = dict(cycle)
        if result.get('configuration'):
            result['configuration'] = result['configuration']

        return {
            "success": True,
            "cycle": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/cycles")
async def list_cycles(
    status: Optional[CycleStatus] = None,
    limit: int = 10,
    offset: int = 0
):
    """
    List trading cycles with optional filtering.
    """
    try:
        if status:
            cycles = await state.db_pool.fetch("""
                SELECT
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    current_positions,
                    started_at,
                    stopped_at,
                    created_at
                FROM trading_cycles
                WHERE status = $1
                ORDER BY started_at DESC
                LIMIT $2 OFFSET $3
            """, status.value, limit, offset)
        else:
            cycles = await state.db_pool.fetch("""
                SELECT
                    cycle_id,
                    mode,
                    status,
                    max_positions,
                    current_positions,
                    started_at,
                    stopped_at,
                    created_at
                FROM trading_cycles
                ORDER BY started_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)

        results = [dict(row) for row in cycles]

        return {
            "success": True,
            "cycles": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Failed to list cycles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/v1/cycles/{cycle_id}")
async def update_cycle(cycle_id: str, request: UpdateCycleRequest):
    """
    Update a trading cycle.
    """
    try:
        # Build update query dynamically
        updates = []
        params = []
        param_num = 1

        if request.status:
            updates.append(f"status = ${param_num}")
            params.append(request.status.value)
            param_num += 1

            # If setting to stopped or completed, set stopped_at
            if request.status in [CycleStatus.STOPPED, CycleStatus.COMPLETED]:
                updates.append(f"stopped_at = ${param_num}")
                params.append(datetime.utcnow())
                param_num += 1

        if request.current_positions is not None:
            updates.append(f"current_positions = ${param_num}")
            params.append(request.current_positions)
            param_num += 1

        if request.configuration:
            updates.append(f"configuration = ${param_num}")
            params.append(json.dumps(request.configuration))
            param_num += 1

        # Always update updated_at
        updates.append(f"updated_at = ${param_num}")
        params.append(datetime.utcnow())
        param_num += 1

        # Add cycle_id as last parameter
        params.append(cycle_id)

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        query = f"""
            UPDATE trading_cycles
            SET {', '.join(updates)}
            WHERE cycle_id = ${param_num}
        """

        result = await state.db_pool.execute(query, *params)

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Cycle not found")

        logger.info(f"Updated cycle {cycle_id}")

        return {
            "success": True,
            "cycle_id": cycle_id,
            "message": "Cycle updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/cycles/{cycle_id}/performance")
async def get_cycle_performance(cycle_id: str):
    """
    Get performance metrics for a cycle.

    v6.0 Pattern: Uses JOINs with scan_results and positions tables.
    """
    try:
        perf = await state.db_pool.fetchrow("""
            SELECT
                tc.cycle_id,
                tc.mode,
                tc.status,
                tc.started_at,
                tc.stopped_at,
                COUNT(DISTINCT sr.security_id) as securities_scanned,
                COUNT(DISTINCT p.position_id) as positions_opened,
                COALESCE(SUM(p.realized_pnl), 0) as total_realized_pnl,
                COALESCE(SUM(p.unrealized_pnl), 0) as total_unrealized_pnl
            FROM trading_cycles tc
            LEFT JOIN scan_results sr ON sr.cycle_id = tc.cycle_id
            LEFT JOIN positions p ON p.cycle_id = tc.cycle_id
            WHERE tc.cycle_id = $1
            GROUP BY tc.cycle_id, tc.mode, tc.status, tc.started_at, tc.stopped_at
        """, cycle_id)

        if not perf:
            raise HTTPException(status_code=404, detail="Cycle not found")

        result = dict(perf)
        result['total_pnl'] = float(result['total_realized_pnl']) + float(result['total_unrealized_pnl'])

        return {
            "success": True,
            "performance": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cycle performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/cycles/{cycle_id}/candidates")
async def get_cycle_candidates(cycle_id: str, limit: int = 20):
    """
    Get scan candidates for a cycle.

    v6.0 Pattern: Uses JOINs to get symbol from securities table.
    """
    try:
        candidates = await state.db_pool.fetch("""
            SELECT
                sr.rank,
                s.symbol,
                s.company_name,
                sr.composite_score,
                sr.catalyst_score,
                sr.technical_score,
                sr.momentum_score,
                sr.volume_score,
                sr.price,
                sr.volume,
                sr.scan_timestamp
            FROM scan_results sr
            JOIN securities s ON s.security_id = sr.security_id
            WHERE sr.cycle_id = $1
            ORDER BY sr.rank
            LIMIT $2
        """, cycle_id, limit)

        results = [dict(row) for row in candidates]

        return {
            "success": True,
            "cycle_id": cycle_id,
            "candidates": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"Failed to get cycle candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "workflow-service:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
        log_level="info"
    )
