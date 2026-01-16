#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: workflow-coordinator.py
Version: 2.0.0
Last Updated: 2025-11-18
Purpose: HTTP service that orchestrates the AUTONOMOUS trading workflow pipeline

REVISION HISTORY:
v2.0.0 (2025-11-18) - AUTONOMOUS TRADING SUPPORT
- Integrated config_loader for YAML configuration loading
- Integrated alert_manager for email notifications
- Added autonomous mode enforcement (checks TRADING_SESSION_MODE)
- Sends informational alerts after trade execution
- Respects trading_config.yaml parameters
- Hot-reload configuration support

v1.0.1 (2025-10-16) - Bug fixes and improvements
- Fixed version typo (1.0.o -> 1.0.0)
- Added Pydantic model for workflow start request
- Proper JSON body parsing for mode and other parameters
- Enhanced parameter handling

v1.0.0 (2025-10-16) - Initial implementation
- Coordinates scanner → pattern → technical → risk → trading
- Implements the 100 → 35 → 20 → 10 → 5 candidate filtering
- Background task processing
- RESTful API for trigger and monitoring

Description:
This service handles the actual trading workflow coordination,
calling each service in sequence and filtering candidates.
Runs on port 5006 as a standard HTTP service.

AUTONOMOUS TRADING:
- Loads config/trading_config.yaml for session mode
- Checks if mode == "autonomous" before executing trades
- Sends email alerts after actions taken
- Respects risk limits from config/risk_parameters.yaml
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import aiohttp
import asyncio
import logging
import os
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import common utilities
from common.config_loader import (
    get_trading_config,
    get_risk_config,
    is_autonomous_mode,
    get_workflow_config
)
from common.alert_manager import (
    alert_manager,
    AlertType,
    AlertSeverity
)

SERVICE_NAME = "workflow"
SERVICE_VERSION = "2.0.0"  # AUTONOMOUS TRADING SUPPORT
SERVICE_PORT = 5006

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("workflow")

# ============================================================================
# REQUEST MODELS
# ============================================================================
class WorkflowStartRequest(BaseModel):
    """Request model for starting workflow"""
    mode: str = Field(default="normal", description="Trading mode: normal, conservative, aggressive")
    max_positions: Optional[int] = Field(default=5, description="Maximum positions to hold")
    scan_frequency: Optional[int] = Field(default=300, description="Scan frequency in seconds")
    risk_level: Optional[float] = Field(default=0.5, description="Risk level 0.0-1.0")

# ============================================================================
# CONFIGURATION
# ============================================================================
@dataclass
class Config:
    SERVICE_PORT = 5006  # Different from MCP orchestration (5000)
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Service URLs (internal Docker network)
    SCANNER_URL = os.getenv("SCANNER_URL", "http://scanner:5001")
    PATTERN_URL = os.getenv("PATTERN_URL", "http://pattern:5002")
    TECHNICAL_URL = os.getenv("TECHNICAL_URL", "http://technical:5003")
    RISK_URL = os.getenv("RISK_URL", "http://risk-manager:5004")
    TRADING_URL = os.getenv("TRADING_URL", "http://trading:5005")
    NEWS_URL = os.getenv("NEWS_URL", "http://news:5008")
    
    # Workflow parameters
    MAX_INITIAL_CANDIDATES = 100
    AFTER_NEWS_FILTER = 35
    AFTER_PATTERN_FILTER = 20
    AFTER_TECHNICAL_FILTER = 10
    FINAL_TRADING_CANDIDATES = 5
    
    # Timing
    WORKFLOW_TIMEOUT = 300  # 5 minutes
    SERVICE_TIMEOUT = 30    # 30 seconds per service call

config = Config()

# ============================================================================
# STATE MANAGEMENT
# ============================================================================
class WorkflowStatus(str, Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    FILTERING_NEWS = "filtering_news"
    ANALYZING_PATTERNS = "analyzing_patterns"
    TECHNICAL_ANALYSIS = "technical_analysis"
    RISK_VALIDATION = "risk_validation"
    EXECUTING_TRADES = "executing_trades"
    COMPLETED = "completed"
    FAILED = "failed"

class WorkflowState:
    def __init__(self):
        self.current_cycle = None
        self.status = WorkflowStatus.IDLE
        self.last_run = None
        self.active_positions = []
        self.db_pool = None
        self.http_session = None
        self.current_mode = "normal"  # Track current mode
        self.current_params = {}      # Track current parameters

state = WorkflowState()

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting Workflow Coordinator v{SERVICE_VERSION}")
    
    # Initialize database
    if config.DATABASE_URL:
        state.db_pool = await asyncpg.create_pool(config.DATABASE_URL)
        logger.info("Database pool initialized")
    
    # Initialize HTTP session
    state.http_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=config.SERVICE_TIMEOUT)
    )
    logger.info("HTTP session initialized")
    
    logger.info(f"Workflow Coordinator ready on port {config.SERVICE_PORT}")
    
    yield
    
    # Shutdown
    if state.http_session:
        await state.http_session.close()
    if state.db_pool:
        await state.db_pool.close()
    logger.info("Workflow Coordinator shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title="Workflow Coordinator",
    version=SERVICE_VERSION,
    description="Orchestrates the trading workflow pipeline",
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
# WORKFLOW ORCHESTRATION
# ============================================================================
async def run_trading_workflow(cycle_id: str, mode: str = "normal", params: Dict = None):
    """
    Main workflow orchestration logic.
    Implements: Scanner → News → Pattern → Technical → Risk → Trading
    
    Modes affect filtering thresholds:
    - normal: Standard thresholds
    - conservative: Higher confidence requirements, lower risk
    - aggressive: Lower thresholds, higher risk tolerance
    """
    params = params or {}

    # Adjust thresholds based on mode - AGGRESSIVE for data collection
    # autonomous/aggressive mode uses very low thresholds to generate more trades
    sentiment_threshold = 0.3 if mode == "normal" else (0.5 if mode == "conservative" else 0.1)
    pattern_confidence_min = 0.6 if mode == "normal" else (0.7 if mode == "conservative" else 0.1)
    risk_multiplier = 1.0 if mode == "normal" else (0.5 if mode == "conservative" else 2.0)
    
    try:
        state.status = WorkflowStatus.SCANNING
        state.current_cycle = cycle_id
        state.current_mode = mode
        state.current_params = params
        
        workflow_result = {
            "cycle_id": cycle_id,
            "started_at": datetime.utcnow(),
            "mode": mode,
            "parameters": params,
            "stages": {}
        }
        
        logger.info(f"[{cycle_id}] Starting workflow in {mode} mode")
        
        # ========== STAGE 1: Market Scan (100 candidates) ==========
        logger.info(f"[{cycle_id}] Stage 1: Scanning market...")
        async with state.http_session.post(f"{config.SCANNER_URL}/api/v1/scan") as resp:
            if resp.status != 200:
                raise Exception(f"Scanner failed: HTTP {resp.status}")
            scan_data = await resp.json()

        # Use the database cycle_id from scanner for trading (required for position creation)
        db_cycle_id = scan_data.get("cycle_id")
        if db_cycle_id:
            logger.info(f"[{cycle_id}] Using database cycle_id: {db_cycle_id}")
            cycle_id = db_cycle_id  # Override with database cycle_id
            workflow_result["db_cycle_id"] = db_cycle_id
            state.current_cycle = cycle_id

        candidates = scan_data.get("picks", [])[:config.MAX_INITIAL_CANDIDATES]
        workflow_result["stages"]["scan"] = {
            "candidates": len(candidates),
            "duration": (datetime.utcnow() - workflow_result["started_at"]).total_seconds()
        }
        logger.info(f"[{cycle_id}] Scan complete: {len(candidates)} candidates")
        
        if not candidates:
            state.status = WorkflowStatus.COMPLETED
            workflow_result["status"] = "no_candidates"
            return workflow_result
        
        # ========== STAGE 2: News Filter (100 → 35) ==========
        state.status = WorkflowStatus.FILTERING_NEWS

        # Load workflow config for filter settings
        workflow_config = get_workflow_config()
        news_filter_config = workflow_config.get('filters', {}).get('news', {})
        news_enabled = news_filter_config.get('enabled', True)
        news_required = news_filter_config.get('required', False)  # Default to optional
        fallback_score = news_filter_config.get('fallback_score', 0.5)

        logger.info(
            f"[{cycle_id}] Stage 2: Filtering by news catalysts "
            f"(threshold: {sentiment_threshold}, required: {news_required})..."
        )

        news_candidates = []
        candidates_without_news = 0  # Track missing news

        for candidate in candidates:
            has_news = False
            sentiment = None

            try:
                async with state.http_session.get(
                    f"{config.NEWS_URL}/api/v1/news/{candidate['symbol']}?limit=5"
                ) as resp:
                    if resp.status == 200:
                        news_data = await resp.json()
                        # Check for positive catalysts
                        if news_data.get("news"):
                            has_news = True
                            sentiment = sum(
                                n.get("sentiment_score", 0) for n in news_data["news"]
                            ) / len(news_data["news"])

                            if sentiment > sentiment_threshold:
                                candidate["news_sentiment"] = sentiment
                                news_candidates.append(candidate)
                            else:
                                logger.debug(
                                    f"[{cycle_id}] {candidate['symbol']}: "
                                    f"sentiment {sentiment:.2f} below threshold {sentiment_threshold}"
                                )
            except Exception as e:
                logger.warning(
                    f"[{cycle_id}] News fetch failed for {candidate['symbol']}: {e}"
                )

            # ========== NEW: Graceful degradation logic ==========
            if not has_news:
                candidates_without_news += 1

                if not news_required:
                    # Proceed without news using fallback score
                    candidate["news_sentiment"] = fallback_score
                    candidate["news_available"] = False
                    news_candidates.append(candidate)

                    logger.info(
                        f"[{cycle_id}] {candidate['symbol']}: "
                        f"No news available, using fallback score {fallback_score}"
                    )
                else:
                    logger.debug(
                        f"[{cycle_id}] {candidate['symbol']}: "
                        f"Rejected (news required but unavailable)"
                    )

            if len(news_candidates) >= config.AFTER_NEWS_FILTER:
                break

        # ========== NEW: Log degraded mode warning ==========
        if candidates_without_news > 0:
            logger.warning(
                f"[{cycle_id}] News filter: {candidates_without_news}/{len(candidates)} "
                f"candidates had no news data (proceeding with fallback scores)"
            )

        workflow_result["stages"]["news"] = {
            "candidates": len(news_candidates),
            "filtered_out": len(candidates) - len(news_candidates),
            "threshold_used": sentiment_threshold,
            "candidates_without_news": candidates_without_news,  # NEW
            "degraded_mode": candidates_without_news > 0         # NEW
        }
        logger.info(f"[{cycle_id}] News filter: {len(news_candidates)} candidates remain")
        
        # ========== STAGE 3: Pattern Analysis (35 → 20) ==========
        state.status = WorkflowStatus.ANALYZING_PATTERNS
        logger.info(f"[{cycle_id}] Stage 3: Analyzing patterns (min confidence: {pattern_confidence_min})...")

        pattern_candidates = []

        # AGGRESSIVE MODE: Skip pattern analysis if threshold is very low (< 0.2)
        # This allows trades to execute even when market data is stale (weekends/after hours)
        if pattern_confidence_min < 0.2:
            logger.info(f"[{cycle_id}] AGGRESSIVE MODE: Bypassing pattern filter (threshold={pattern_confidence_min})")
            pattern_candidates = news_candidates.copy()
            for candidate in pattern_candidates:
                candidate["patterns"] = [{"name": "momentum", "confidence": 0.5}]
                candidate["pattern_confidence"] = 0.5
        else:
            for candidate in news_candidates:
                try:
                    async with state.http_session.post(
                        f"{config.PATTERN_URL}/api/v1/detect",
                        json={"symbol": candidate["symbol"], "timeframe": "5m", "min_confidence": pattern_confidence_min}
                    ) as resp:
                        if resp.status == 200:
                            pattern_data = await resp.json()
                            if pattern_data.get("patterns_found", 0) > 0:
                                candidate["patterns"] = pattern_data["patterns"]
                                candidate["pattern_confidence"] = max(
                                    p.get("confidence", 0) for p in pattern_data["patterns"]
                                )
                                pattern_candidates.append(candidate)
                except:
                    continue

                if len(pattern_candidates) >= config.AFTER_PATTERN_FILTER:
                    break

        # Sort by pattern confidence
        pattern_candidates.sort(key=lambda x: x.get("pattern_confidence", 0), reverse=True)
        pattern_candidates = pattern_candidates[:config.AFTER_PATTERN_FILTER]
        
        workflow_result["stages"]["patterns"] = {
            "candidates": len(pattern_candidates),
            "with_patterns": len([c for c in pattern_candidates if c.get("patterns")]),
            "min_confidence_used": pattern_confidence_min
        }
        logger.info(f"[{cycle_id}] Pattern analysis: {len(pattern_candidates)} candidates remain")
        
        # ========== STAGE 4: Technical Analysis (20 → 10) ==========
        state.status = WorkflowStatus.TECHNICAL_ANALYSIS
        logger.info(f"[{cycle_id}] Stage 4: Technical analysis...")

        technical_candidates = []

        # AGGRESSIVE MODE: Skip technical analysis if pattern threshold was very low
        if pattern_confidence_min < 0.2:
            logger.info(f"[{cycle_id}] AGGRESSIVE MODE: Bypassing technical filter")
            technical_candidates = pattern_candidates.copy()
            for candidate in technical_candidates:
                candidate["technical_score"] = 0.6  # Default score
        else:
            for candidate in pattern_candidates:
                try:
                    # Get technical indicators
                    async with state.http_session.get(
                        f"{config.TECHNICAL_URL}/api/v1/indicators/{candidate['symbol']}"
                    ) as resp:
                        if resp.status == 200:
                            tech_data = await resp.json()
                            # Calculate composite technical score
                            rsi = tech_data.get("rsi", 50)
                            macd_signal = tech_data.get("macd_signal", 0)

                            # Adjust RSI thresholds based on mode
                            rsi_lower = 30 if mode == "normal" else (35 if mode == "conservative" else 25)
                            rsi_upper = 70 if mode == "normal" else (65 if mode == "conservative" else 75)

                            # Bullish conditions
                            if rsi_lower < rsi < rsi_upper and macd_signal > 0:
                                candidate["technical_score"] = (
                                    (70 - abs(rsi - 50)) / 20 * 0.5 +  # RSI score
                                    min(macd_signal / 10, 1) * 0.5      # MACD score
                                )
                                technical_candidates.append(candidate)
                except:
                    continue

                if len(technical_candidates) >= config.AFTER_TECHNICAL_FILTER:
                    break

        # Sort by technical score
        technical_candidates.sort(key=lambda x: x.get("technical_score", 0), reverse=True)
        technical_candidates = technical_candidates[:config.AFTER_TECHNICAL_FILTER]
        
        workflow_result["stages"]["technical"] = {
            "candidates": len(technical_candidates),
            "avg_score": sum(c.get("technical_score", 0) for c in technical_candidates) / len(technical_candidates) if technical_candidates else 0
        }
        logger.info(f"[{cycle_id}] Technical analysis: {len(technical_candidates)} candidates remain")
        
        # ========== STAGE 5: Risk Validation (10 → 5) ==========
        state.status = WorkflowStatus.RISK_VALIDATION
        logger.info(f"[{cycle_id}] Stage 5: Risk validation (risk multiplier: {risk_multiplier})...")
        
        validated_candidates = []
        for candidate in technical_candidates:
            try:
                # Prepare position for risk validation
                base_quantity = 100 * risk_multiplier
                position_request = {
                    "cycle_id": cycle_id,
                    "symbol": candidate["symbol"],
                    "side": "long",
                    "quantity": int(base_quantity),
                    "entry_price": candidate.get("price", candidate.get("current_price", 100)),
                    "stop_price": candidate.get("price", candidate.get("current_price", 100)) * (0.98 if mode != "aggressive" else 0.95),
                    "target_price": candidate.get("price", candidate.get("current_price", 100)) * (1.05 if mode != "aggressive" else 1.10),
                    "mode": mode
                }
                
                async with state.http_session.post(
                    f"{config.RISK_URL}/api/v1/validate-position",
                    json=position_request
                ) as resp:
                    if resp.status == 200:
                        risk_data = await resp.json()
                        if risk_data.get("approved"):
                            # Calculate quantity from position_size_usd / entry_price
                            entry_price = candidate.get("price", candidate.get("current_price", 100))
                            position_size_usd = risk_data.get("position_size_usd", 2000)
                            candidate["position_size"] = max(1, int(position_size_usd / entry_price))
                            candidate["position_size_usd"] = position_size_usd
                            candidate["risk_score"] = risk_data.get("risk_level", "low")
                            candidate["risk_amount"] = risk_data.get("risk_amount_usd", 0)
                            validated_candidates.append(candidate)
            except:
                continue
            
            if len(validated_candidates) >= config.FINAL_TRADING_CANDIDATES:
                break
        
        workflow_result["stages"]["risk"] = {
            "validated": len(validated_candidates),
            "rejected": len(technical_candidates) - len(validated_candidates),
            "risk_multiplier": risk_multiplier
        }
        logger.info(f"[{cycle_id}] Risk validation: {len(validated_candidates)} candidates approved")
        
        # ========== STAGE 6: Execute Trades (Top 5) ==========
        state.status = WorkflowStatus.EXECUTING_TRADES
        logger.info(f"[{cycle_id}] Stage 6: Executing trades...")
        
        max_trades = params.get("max_positions", config.FINAL_TRADING_CANDIDATES)
        executed_trades = []
        for candidate in validated_candidates[:max_trades]:
            try:
                # Get price for position sizing
                entry_price = candidate.get("price", candidate.get("current_price", 100))
                stop_loss = entry_price * (0.95 if mode == "autonomous" else 0.98)
                take_profit = entry_price * (1.10 if mode == "autonomous" else 1.05)

                trade_request = {
                    "symbol": candidate["symbol"],
                    "side": "long",  # Trading service expects "long"/"short"
                    "quantity": int(candidate.get("position_size", 100)),
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit
                }

                # Use /api/v1/positions with cycle_id as query param
                async with state.http_session.post(
                    f"{config.TRADING_URL}/api/v1/positions?cycle_id={cycle_id}",
                    json=trade_request
                ) as resp:
                    if resp.status == 200:
                        trade_data = await resp.json()
                        executed_trades.append({
                            "symbol": candidate["symbol"],
                            "position_id": trade_data.get("position_id"),
                            "quantity": int(candidate.get("position_size", 100)),
                            "entry_price": entry_price
                        })
                        logger.info(f"[{cycle_id}] Trade executed: {candidate['symbol']} @ ${entry_price:.2f}")
                    else:
                        error_text = await resp.text()
                        logger.error(f"[{cycle_id}] Trade failed for {candidate['symbol']}: {resp.status} - {error_text}")
            except Exception as e:
                logger.error(f"Failed to execute trade for {candidate['symbol']}: {e}")
                continue
        
        workflow_result["stages"]["trading"] = {
            "executed": len(executed_trades),
            "trades": executed_trades
        }
        logger.info(f"[{cycle_id}] Trading complete: {len(executed_trades)} trades executed")

        # ===================================================================
        # SEND TRADES EXECUTED ALERT (AUTONOMOUS MODE)
        # ===================================================================
        if executed_trades:
            try:
                total_risk = sum(
                    candidate.get("risk_amount", 0) for candidate in validated_candidates[:len(executed_trades)]
                )

                await alert_manager.alert_trades_executed(
                    cycle_id=cycle_id,
                    trades=executed_trades,
                    total_risk=total_risk
                )
                logger.info(f"[{cycle_id}] Trades executed alert sent ({len(executed_trades)} trades)")
            except Exception as e:
                logger.warning(f"[{cycle_id}] Failed to send trades executed alert: {e}")
                # Don't fail workflow if alert fails

        # ========== COMPLETE ==========
        state.status = WorkflowStatus.COMPLETED
        workflow_result["completed_at"] = datetime.utcnow()
        workflow_result["total_duration"] = (
            workflow_result["completed_at"] - workflow_result["started_at"]
        ).total_seconds()
        workflow_result["status"] = "success"
        
        # Update cycle in database if available
        # Note: Scanner already created the cycle, we just update it
        if state.db_pool:
            try:
                # Don't update - scanner already handles the cycle lifecycle
                # The cycle was created and updated by scanner service
                pass
            except Exception as e:
                logger.error(f"Failed to store cycle results: {e}")
        
        return workflow_result
        
    except Exception as e:
        logger.error(f"[{cycle_id}] Workflow failed: {e}")
        state.status = WorkflowStatus.FAILED
        return {
            "cycle_id": cycle_id,
            "status": "failed",
            "error": str(e)
        }
    finally:
        state.last_run = datetime.utcnow()

# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "workflow-coordinator",
        "version": SERVICE_VERSION,
        "current_status": state.status,
        "last_run": state.last_run.isoformat() if state.last_run else None,
        "active_cycle": state.current_cycle
    }

@app.post("/api/v1/workflow/start")
async def start_workflow(
    background_tasks: BackgroundTasks,
    request: WorkflowStartRequest  # Now properly using Pydantic model
):
    """
    Start a new trading workflow cycle with specified parameters.

    AUTONOMOUS MODE:
    - Checks if trading_session.mode == "autonomous" in config
    - If autonomous: executes trades immediately after risk validation
    - If supervised: raises 400 error (requires human approval)
    - Sends email alert when workflow starts
    """
    if state.status not in [WorkflowStatus.IDLE, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
        raise HTTPException(
            status_code=409,
            detail=f"Workflow already running: {state.status}"
        )

    # ===================================================================
    # AUTONOMOUS MODE CHECK
    # ===================================================================
    try:
        # Load trading configuration
        trading_config = get_trading_config()
        session_mode = trading_config.get('trading_session', {}).get('mode', 'supervised')

        logger.info(f"Trading session mode: {session_mode}")

        # Enforce autonomous mode requirement
        if session_mode != 'autonomous':
            logger.warning(
                f"Workflow start blocked: Trading mode is '{session_mode}' (requires 'autonomous')"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Supervised mode not supported via API",
                    "message": f"Current mode: '{session_mode}'. Change to 'autonomous' in config/trading_config.yaml",
                    "config_file": "config/trading_config.yaml",
                    "required_mode": "autonomous",
                    "current_mode": session_mode
                }
            )

        logger.info("✅ Autonomous mode confirmed - trades will execute automatically")

        # Load workflow config
        workflow_config = get_workflow_config()
        scan_frequency = workflow_config.get('scan_frequency_minutes', 30) * 60  # Convert to seconds

        # Override with request if provided
        if request.scan_frequency:
            scan_frequency = request.scan_frequency

        max_positions = workflow_config.get('execute_top_n', 3)
        if request.max_positions:
            max_positions = request.max_positions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config loading error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Configuration error: {str(e)}"
        )

    cycle_id = f"cycle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # ===================================================================
    # SEND WORKFLOW STARTED ALERT
    # ===================================================================
    try:
        await alert_manager.alert_workflow_started(
            cycle_id=cycle_id,
            mode=request.mode,
            scan_frequency=scan_frequency
        )
        logger.info(f"Workflow started alert sent for cycle: {cycle_id}")
    except Exception as e:
        logger.warning(f"Failed to send workflow started alert: {e}")
        # Don't fail workflow if alert fails

    # ===================================================================
    # START AUTONOMOUS WORKFLOW
    # ===================================================================
    # Start workflow in background with parsed parameters
    background_tasks.add_task(
        run_trading_workflow,
        cycle_id,
        request.mode,
        {
            **request.dict(),
            'session_mode': 'autonomous',
            'scan_frequency': scan_frequency,
            'max_positions': max_positions
        }
    )

    logger.info(
        f"Autonomous workflow started: {cycle_id} (mode: {request.mode}, "
        f"max_positions: {max_positions}, scan_freq: {scan_frequency}s)"
    )

    return {
        "success": True,
        "cycle_id": cycle_id,
        "status": "started",
        "mode": request.mode,
        "session_mode": "autonomous",
        "max_positions": max_positions,
        "risk_level": request.risk_level,
        "scan_frequency": scan_frequency,
        "message": "Autonomous workflow started - trades will execute automatically after risk validation"
    }

@app.get("/api/v1/workflow/status")
async def get_workflow_status():
    """Get current workflow status"""
    return {
        "status": state.status,
        "current_cycle": state.current_cycle,
        "current_mode": state.current_mode,
        "current_params": state.current_params,
        "last_run": state.last_run.isoformat() if state.last_run else None,
        "active_positions": len(state.active_positions)
    }

@app.post("/api/v1/workflow/stop")
async def stop_workflow():
    """Stop the current workflow"""
    if state.status in [WorkflowStatus.IDLE, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
        return {"success": False, "message": "No active workflow to stop"}
    
    old_status = state.status
    state.status = WorkflowStatus.IDLE
    logger.info(f"Workflow stopped (was: {old_status})")
    return {"success": True, "message": "Workflow stop requested", "previous_status": old_status}

@app.get("/api/v1/workflow/history")
async def get_workflow_history(limit: int = 10):
    """Get workflow run history"""
    if not state.db_pool:
        # Return empty history if no database
        return {"history": [], "message": "Database not configured"}
    
    try:
        rows = await state.db_pool.fetch("""
            SELECT cycle_id, start_time, end_time, status, mode,
                   initial_universe_size, final_candidates, trades_executed
            FROM trading_cycles
            ORDER BY start_time DESC
            LIMIT $1
        """, limit)
        
        return {
            "history": [dict(row) for row in rows],
            "total_cycles": len(rows)
        }
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return {"history": [], "error": str(e)}

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "workflow-coordinator:app",
        host="0.0.0.0",
        port=config.SERVICE_PORT,
        reload=False
    )
