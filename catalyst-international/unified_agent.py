"""
Name of Application: Catalyst Trading System
Name of file: unified_agent.py
Version: 3.2.0
Last Updated: 2026-02-01
Purpose: Unified trading agent with Claude AI loop and workflow tracking

REVISION HISTORY:
v3.2.0 (2026-02-01) - CLEANUP & DATABASE LOGGING
- Removed consciousness framework integration
- Removed research_pool (now single trading DB)
- Removed email/alert sending
- Added database logging via db_logger.py
- All logs now go to agent_logs table

v3.1.0 (2026-01-20) - CRITICAL WORKFLOW FIXES
- Fixed missing DECIDE phase mapping (check_risk now triggers DECIDE)
- Fixed missing MONITOR phase trigger (after successful execute_trade)
- Added VALIDATE phase transition after check_risk result
- Added debug logging for blocked backward phase transitions

v3.0.0 (2026-01-17) - MERGED AGENT.PY FUNCTIONALITY
- Added WorkflowTracker class for 10-phase progress tracking
- Added SYSTEM_PROMPT with tiered entry criteria (Tier 1/2/3)
- Added Claude API tool-use loop (replaces stub implementations)
- Added progress bar display during execution
- Added --force and --live CLI flags
- Removed placeholder methods (now handled by Claude loop)

v2.0.0 (2026-01-10) - Ecosystem restructure
- Startup monitor integration
- Position monitor integration (auto-start on BUY)
- Config file support (YAML)
- Pattern-based signal detection

v1.0.0 (2026-01-05) - Initial unified agent

Description:
Single-agent architecture for HKEX trading. Handles:
- Market scanning and opportunity detection via Claude AI
- Entry decision making with tiered criteria
- Position monitoring with pattern-based exits
- Real-time workflow tracking with progress bar
- Database logging for observability

Usage:
    python unified_agent.py --mode trade --force
    python unified_agent.py --mode close
    python unified_agent.py --mode heartbeat
    python unified_agent.py --mode scan
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

import yaml
import asyncpg
import anthropic

from tools import TOOLS
from tool_executor import create_tool_executor
from data.database import get_database, init_database
from db_logger import setup_db_logging, set_db_handler, get_db_handler

# Local imports - adjust path as needed
try:
    from brokers.moomoo import MoomooClient, init_moomoo_client, get_moomoo_client
    from data.market import MarketData
    from safety import SafetyValidator
except ImportError:
    # Running standalone - mock imports
    MoomooClient = None
    init_moomoo_client = None
    get_moomoo_client = None
    MarketData = None
    SafetyValidator = None

from signals import analyze_position  # Thresholds now loaded from config/exit_context.yaml
from startup_monitor import run_startup_reconciliation, get_monitor_health_report

# Position monitoring now handled by position_monitor_service.py (systemd)
# Old position_monitor.py was removed due to DB constraint errors
try:
    from position_monitor import start_position_monitor
    POSITION_MONITOR_AVAILABLE = True
except ImportError:
    start_position_monitor = None
    POSITION_MONITOR_AVAILABLE = False
    logging.getLogger(__name__).info("Position monitor not available - using systemd service instead")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Timezone
HK_TZ = ZoneInfo("Asia/Hong_Kong")


# =============================================================================
# CONFIGURATION
# =============================================================================

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    
    # Default paths to check
    default_paths = [
        Path("config/agent_config.yaml"),
        Path("config/dev_claude_config.yaml"),
        Path("config/intl_claude_config.yaml"),
        Path("agent_config.yaml"),
    ]
    
    if config_path:
        default_paths.insert(0, Path(config_path))
    
    for path in default_paths:
        if path.exists():
            logger.info(f"Loading config from {path}")
            with open(path) as f:
                return yaml.safe_load(f)
    
    # Return defaults if no config found
    logger.warning("No config file found, using defaults")
    return {
        'agent': {'id': os.getenv('AGENT_ID', 'unified_agent')},
        'trading': {
            'max_positions': 15,
            'max_position_value_hkd': 10000,
            'daily_loss_limit_hkd': 16000,
        },
        'ai': {
            'daily_budget_usd': 5.00,
        }
    }


# =============================================================================
# WORKFLOW TRACKER - Real-time visibility into trading cycle
# =============================================================================

# All workflow phases in order
WORKFLOW_PHASES = ["INIT", "PORTFOLIO", "SCAN", "ANALYZE", "DECIDE", "VALIDATE", "EXECUTE", "MONITOR", "LOG", "COMPLETE"]


class WorkflowTracker:
    """Track workflow phases in real-time.

    Stores progress in agent_logs table for observability.
    """

    def __init__(self, cycle_id: str, agent_id: str = "intl_claude"):
        self.cycle_id = cycle_id
        self.agent_id = agent_id
        self.phases: List[Dict] = []
        self.current_phase: Optional[str] = None
        self.started_at = datetime.now(HK_TZ)

    async def connect(self):
        """Initialize tracker (no separate DB connection needed)."""
        logger.debug(f"WorkflowTracker initialized for cycle {self.cycle_id}")

    async def disconnect(self):
        """Cleanup tracker."""
        pass

    async def start_phase(self, phase: str, description: str = "", details: Dict[str, Any] = None):
        """Start a new workflow phase."""
        now = datetime.now(HK_TZ)

        record = {
            "phase": phase,
            "status": "started",
            "started_at": now.isoformat(),
            "completed_at": None,
            "duration_ms": None,
            "details": details or {"description": description},
            "error": None
        }
        self.phases.append(record)
        self.current_phase = phase

        logger.info(f"[{self.cycle_id}] ▶ Phase {phase}: {description}")
        self._print_progress_bar()

        await self._store_progress()

    async def complete_phase(self, phase: str, **results):
        """Complete a workflow phase."""
        now = datetime.now(HK_TZ)

        for record in reversed(self.phases):
            if record["phase"] == phase and record["status"] == "started":
                started = datetime.fromisoformat(record["started_at"])
                record["status"] = "completed"
                record["completed_at"] = now.isoformat()
                record["duration_ms"] = int((now - started).total_seconds() * 1000)
                if results:
                    record["details"] = {**(record["details"] or {}), **results}
                break

        result_str = ", ".join(f"{k}={v}" for k, v in results.items()) if results else ""
        logger.info(f"[{self.cycle_id}] ✓ Phase {phase} completed ({result_str})")
        self._print_progress_bar()

        await self._store_progress()

    async def error_phase(self, phase: str, error: str):
        """Mark a phase as errored."""
        now = datetime.now(HK_TZ)

        for record in reversed(self.phases):
            if record["phase"] == phase and record["status"] == "started":
                started = datetime.fromisoformat(record["started_at"])
                record["status"] = "error"
                record["completed_at"] = now.isoformat()
                record["duration_ms"] = int((now - started).total_seconds() * 1000)
                record["error"] = error
                break

        logger.error(f"[{self.cycle_id}] ✗ Phase {phase} error: {error}")

        await self._store_progress()

    async def _store_progress(self):
        """Log workflow progress (stored via db_logger)."""
        # Progress is automatically logged via the standard logger
        # which is connected to DatabaseLogHandler
        pass

    def _print_progress_bar(self):
        """Print a visual progress bar to console."""
        completed = {r["phase"] for r in self.phases if r["status"] == "completed"}
        current = self.current_phase

        bar = "["
        for phase in WORKFLOW_PHASES:
            if phase in completed:
                bar += "█"
            elif phase == current:
                bar += "▓"
            else:
                bar += "░"
        bar += "]"

        pct = (len(completed) / len(WORKFLOW_PHASES)) * 100
        print(f"\r{bar} {pct:.0f}% - {current or 'Starting...'}", end="", flush=True)
        if current == "COMPLETE" or pct == 100:
            print()  # Newline when done

    def get_summary(self) -> Dict[str, Any]:
        """Get workflow summary."""
        completed = [p for p in self.phases if p["status"] == "completed"]
        errors = [p for p in self.phases if p["status"] == "error"]
        total_duration = sum(p.get("duration_ms", 0) or 0 for p in self.phases)

        return {
            "cycle_id": self.cycle_id,
            "agent_id": self.agent_id,
            "started_at": self.started_at.isoformat(),
            "current_phase": self.current_phase,
            "phases_completed": len(completed),
            "phases_total": len(self.phases),
            "errors": len(errors),
            "total_duration_ms": total_duration,
            "phase_details": self.phases
        }


# =============================================================================
# DATABASE
# =============================================================================

class Database:
    """Database connection manager."""

    def __init__(self, trading_url: str):
        self.trading_url = trading_url
        self.trading_pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool."""
        self.trading_pool = await asyncpg.create_pool(
            self.trading_url, min_size=2, max_size=5
        )
        logger.info("Trading database pool created")

    async def close(self):
        """Close connection pool."""
        if self.trading_pool:
            await self.trading_pool.close()
        logger.info("Database pool closed")


# =============================================================================
# SYSTEM PROMPT - Claude's Trading Instructions
# =============================================================================

SYSTEM_PROMPT = """You are an autonomous AI trading agent for the Hong Kong Stock Exchange (HKEX).

## Your Role
You make trading decisions during HKEX market hours using the tools available to you.
Every decision you make should be documented with clear reasoning for the audit trail.

## PAPER TRADING MODE - LEARNING FIRST
**This is paper trading. We are here to LEARN, not to be perfect.**

Philosophy:
- PREFER action over inaction when setups look reasonable
- A trade that loses teaches us something
- A missed trade teaches us nothing
- We learn by doing, not by waiting for perfection
- Document everything so we can analyze later

The goal is to generate LEARNING DATA, not to preserve fake capital.

## Market Hours (Hong Kong Time)
- Morning session: 09:30 - 12:00
- Lunch break: 12:00 - 13:00 (NO TRADING)
- Afternoon session: 13:00 - 16:00

## Trading Strategy
You are a momentum day trader. Your edge is:
1. Finding stocks with volume spikes (>1.5x average)
2. Confirming with bullish chart patterns OR positive catalysts
3. Using risk management (2:1 reward:risk minimum)

## Decision Making Process
For each trading cycle:
1. Check portfolio status first (get_portfolio)
2. Scan for candidates (scan_market)
3. For promising candidates:
   a. Get quote for current price
   b. Get technicals to assess setup
   c. Detect patterns for entry/exit levels
   d. Check news for catalysts
   e. EVALUATE using tiered criteria below
   f. If Tier 1 or Tier 2, check risk then trade
4. Monitor existing positions for exits
5. Log all decisions with reasoning

## Critical Rules (MUST FOLLOW)
1. **ALWAYS** call check_risk before execute_trade
2. **NEVER** trade if check_risk returns approved=false
3. **ALWAYS** provide reason for every trade and close
4. **ALWAYS** call log_decision to record your reasoning
5. **IMMEDIATELY** call close_all if daily loss exceeds 5% (paper mode)
6. **PREFER** limit orders over market orders
7. **CLOSE** positions before lunch break (12:00) unless strong conviction
8. **CHECK** max_positions from get_portfolio (currently configured for 15)
9. **MAXIMUM** HKD 10,000 per position (STRICTLY ENFORCED - trades larger than this will be rejected)
10. **POSITION SIZING**: Calculate quantity = floor(10000 / price). Round down to nearest lot size.

## TIERED ENTRY CRITERIA (Use ANY tier that matches)

### Tier 1 - Strong Setup (FULL SIZE = HKD 10,000)
Requirements (ALL of these):
- Volume ratio > 2.0x average
- RSI between 30-70
- Clear chart pattern with defined entry
- Positive news catalyst (sentiment > 0.2)
- Risk/reward ratio >= 2:1
- Position size: HKD 10,000 max

### Tier 2 - Good Setup (FULL SIZE = HKD 10,000)
Requirements:
- Volume ratio > 1.5x average
- RSI between 30-75
- EITHER: Clear pattern OR Positive catalyst (don't need both!)
- Risk/reward ratio >= 1.5:1
- Price within 1% of breakout level counts as "at breakout"
- Position size: HKD 10,000 max

### Tier 3 - Learning Trade (HALF SIZE = HKD 5,000)
Requirements:
- Volume ratio > 1.3x average
- RSI between 25-80 (wider range)
- Strong momentum (price up > 3% today)
- At least one of: pattern forming, news mention, sector strength
- Risk/reward ratio >= 1.5:1
- Log as "learning trade" for analysis
- Position size: HKD 5,000 max (half size for learning)

### When to PASS
Only skip a trade if:
- RSI > 80 (severely overbought) or < 20 (oversold crash)
- Volume is BELOW average (no interest)
- check_risk returns false
- Already at max_positions (check get_portfolio result)
- No clear stop loss level identifiable

## Pattern Detection - Relaxed Rules
- "Within 1% of breakout" = close enough, take it
- "Approaching resistance" = valid setup if volume confirms
- Don't require EXACT breakout - momentum traders anticipate

## News Catalyst - Relaxed Rules
- Sentiment > 0.0 (any positive) = acceptable catalyst for Tier 2/3
- Sector news counts (e.g., "tech sector rally" benefits tech stocks)
- No news is NOT a blocker if pattern is strong

## Exit Rules
- Take profit at pattern target
- Stop loss if price hits stop level
- Time stop: close if flat after 60 minutes
- Trail stop to breakeven after +2% gain
- CLOSE before lunch break unless conviction is high

## Response Format
Think step by step. After each tool call, analyze the result and decide
whether to continue gathering information, take action, or conclude.

When evaluating a candidate, explicitly state:
- Which TIER does this setup match?
- What's the specific entry trigger?
- What's the stop loss level?
- What's the profit target?

When you've completed all actions for this cycle, provide a summary of:
- Positions entered/exited (with tier classification)
- Key decisions made and WHY
- Candidates that almost qualified (for learning)
- Current portfolio status
- Any patterns noticed across candidates
"""


# =============================================================================
# UNIFIED AGENT
# =============================================================================

class UnifiedAgent:
    """
    Unified trading agent for HKEX.

    Handles scanning, trading, and monitoring with database logging.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        broker: Any,
        market_data: Any,
        anthropic_client: anthropic.Anthropic,
        db: Database,
    ):
        self.config = config
        self.broker = broker
        self.market_data = market_data
        self.anthropic = anthropic_client
        self.db = db

        self.agent_id = config['agent']['id']

        # Claude API configuration
        claude_config = config.get('claude', {})
        self.model = claude_config.get('model', 'claude-sonnet-4-20250514')
        self.max_tokens = claude_config.get('max_tokens', 4096)
        self.max_iterations = claude_config.get('max_iterations', 35)

        # Workflow tracking (initialized per-cycle)
        self.tracker: Optional[WorkflowTracker] = None
        self.cycle_id: Optional[str] = None

        # Database logging handler
        self.db_log_handler = None

        logger.info(f"UnifiedAgent initialized: {self.agent_id}, model={self.model}")

    async def initialize(self):
        """Initialize agent connections."""
        await self.db.connect()

        # Setup database logging (use URL, not pool - db_logger uses psycopg2)
        self.db_log_handler = setup_db_logging(
            self.db.trading_url,
            'unified_agent',
            level=logging.INFO
        )
        set_db_handler(self.db_log_handler)
        logger.info("Database logging initialized")

        # Connect broker
        if self.broker:
            self.broker.connect()

        logger.info("Agent initialized")
    
    async def shutdown(self):
        """Shutdown agent connections."""
        # Disconnect workflow tracker if active
        if self.tracker:
            await self.tracker.disconnect()

        if self.broker:
            self.broker.disconnect()

        # Stop database logging handler
        if self.db_log_handler:
            self.db_log_handler.stop()

        await self.db.close()
        logger.info("Agent shutdown complete")
    
    # =========================================================================
    # MODE HANDLERS
    # =========================================================================
    
    async def run_startup(self):
        """Run pre-market startup reconciliation."""
        logger.info("=" * 60)
        logger.info("RUNNING STARTUP RECONCILIATION")
        logger.info("=" * 60)

        # Run reconciliation
        result = await run_startup_reconciliation()

        # Log reconciliation result
        logger.info(
            f"Startup reconciliation: {result['reconciliation']['positions_found']} positions, "
            f"{len(result['reconciliation']['monitors_started'])} monitors started",
            extra={'context': result['reconciliation']}
        )

        return result
    
    async def run_trade_cycle(self):
        """Run full trading cycle with Claude AI loop."""
        # Generate cycle ID
        self.cycle_id = f"hk_{datetime.now(HK_TZ).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Set cycle_id for database logging correlation
        if self.db_log_handler:
            self.db_log_handler.set_cycle_id(self.cycle_id)

        # Initialize workflow tracker
        self.tracker = WorkflowTracker(self.cycle_id, self.agent_id)
        await self.tracker.connect()

        logger.info("=" * 60)
        logger.info("RUNNING TRADE CYCLE")
        logger.info(f"Cycle ID: {self.cycle_id}")
        logger.info(f"Time: {datetime.now(HK_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 60)

        # === PHASE 1: INIT ===
        await self.tracker.start_phase("INIT", "Agent initializing")

        # Check market hours
        if not self._is_market_open():
            await self.tracker.complete_phase("INIT", status="skipped", reason="market_closed")
            await self.tracker.disconnect()
            if self.db_log_handler:
                self.db_log_handler.clear_cycle_id()
            logger.info("Market closed, skipping trade cycle")
            return {'status': 'skipped', 'reason': 'market_closed'}

        # Start cycle in database (for audit trail and log_decision FK)
        try:
            db = get_database()
            db.start_agent_cycle(self.cycle_id, "HKEX")
        except Exception as e:
            logger.warning(f"Could not start cycle in DB: {e}")

        # Create tool executor (no alert_callback needed)
        executor = create_tool_executor(
            cycle_id=self.cycle_id,
            agent=self,
        )

        # Auto-sync positions with broker at start of cycle
        try:
            sync_result = executor.sync_positions_with_broker()
            if sync_result.get("errors"):
                logger.warning(f"Auto-sync had errors: {sync_result['errors']}")
        except Exception as e:
            logger.warning(f"Auto-sync failed: {e}")

        await self.tracker.complete_phase("INIT", model=self.model)

        # === RUN CLAUDE LOOP ===
        result = await self._run_claude_loop(executor)

        # === FINAL PHASES ===
        if not result.get('error'):
            await self.tracker.start_phase("COMPLETE", "Cycle finished")
            await self.tracker.complete_phase("COMPLETE",
                trades_executed=result.get('trades_executed', 0),
                duration_sec=int((datetime.now(HK_TZ) - self.tracker.started_at).total_seconds())
            )

        # Log cycle completion
        logger.info(
            f"Trade cycle {self.cycle_id}: {result.get('trades_executed', 0)} trades",
            extra={'context': {'cycle_id': self.cycle_id, **result}}
        )

        # Print summary
        print("\n" + "=" * 60)
        print("WORKFLOW SUMMARY")
        print("=" * 60)
        wf_summary = self.tracker.get_summary()
        print(f"Phases completed: {wf_summary['phases_completed']}/{len(WORKFLOW_PHASES)}")
        print(f"Total duration: {wf_summary['total_duration_ms']}ms")
        print(f"Errors: {wf_summary['errors']}")

        # Disconnect tracker and clear cycle_id
        await self.tracker.disconnect()
        if self.db_log_handler:
            self.db_log_handler.clear_cycle_id()

        return result
    
    async def run_close_cycle(self):
        """Review and optionally close positions."""
        logger.info("=" * 60)
        logger.info("RUNNING CLOSE CYCLE")
        logger.info("=" * 60)

        portfolio = await self._get_portfolio()
        positions = portfolio.get('positions', [])

        if not positions:
            logger.info("No open positions")
            return {'status': 'complete', 'positions_closed': 0}

        # For lunch break or EOD, consider closing positions with weak patterns
        current_time = datetime.now(HK_TZ).time()
        is_lunch = time(11, 50) <= current_time < time(12, 10)
        is_eod = current_time >= time(15, 50)

        closed = 0
        for pos in positions:
            # Get technicals for analysis
            technicals = self._get_technicals(pos['symbol'])

            analysis = analyze_position(
                position=pos,
                quote={'price': pos.get('current_price', pos['entry_price'])},
                technicals=technicals,
                market="hkex"  # Thresholds loaded from config/exit_context.yaml
            )

            should_close = False
            reason = ""

            if is_eod:
                # EOD - close unless very strong hold
                if analysis.recommendation != "HOLD" or not any(
                    s.strength.value == 'strong' for s in analysis.hold_signals
                ):
                    should_close = True
                    reason = "EOD close"
            elif is_lunch:
                # Lunch - close if any exit signals
                if analysis.exit_signals:
                    should_close = True
                    reason = "Lunch break - weak pattern"

            if should_close:
                result = await self._close_position(pos, reason)
                if result.get('success'):
                    closed += 1

        # Log close cycle result
        logger.info(
            f"Close cycle: {closed}/{len(positions)} positions closed",
            extra={'context': {'total': len(positions), 'closed': closed}}
        )

        return {'status': 'complete', 'positions_closed': closed}
    
    async def run_heartbeat(self):
        """Log heartbeat status."""
        logger.info("Running heartbeat")
        logger.info("Heartbeat complete - agent is alive")
        return {'status': 'complete'}
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _is_market_open(self) -> bool:
        """Check if HKEX is open."""
        import os
        if os.environ.get('FORCE_MARKET_OPEN'):
            return True

        now = datetime.now(HK_TZ)
        if now.weekday() >= 5:
            return False

        current_time = now.time()

        if time(9, 30) <= current_time < time(12, 0):
            return True
        if time(13, 0) <= current_time < time(16, 0):
            return True

        return False
    
    async def _get_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio state."""
        if not self.broker:
            return {'positions': []}
        
        try:
            positions = self.broker.get_positions()
            return {
                'positions': [
                    {
                        'symbol': p.symbol,
                        'quantity': p.quantity,
                        'entry_price': p.avg_cost,
                        'current_price': p.current_price,
                        'unrealized_pnl': p.unrealized_pnl,
                        'pnl_pct': p.unrealized_pnl_pct / 100 if p.unrealized_pnl_pct else 0,
                    }
                    for p in positions
                ]
            }
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return {'positions': []}

    # =========================================================================
    # CLAUDE API LOOP METHODS
    # =========================================================================

    async def _run_claude_loop(self, executor) -> Dict[str, Any]:
        """Execute Claude API tool use loop."""
        context = self._build_context()
        messages = [{"role": "user", "content": context}]
        tools_called = []
        final_response = ""
        error = None

        # Phase tracking
        current_phase = "PORTFOLIO"
        phase_started = False
        candidates_count = 0
        analyzed_count = 0
        trades_executed = 0

        try:
            for iteration in range(self.max_iterations):
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")

                # Call Claude
                response = self.anthropic.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )

                # Add assistant response to messages
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)

                # Check for tool use blocks
                tool_use_blocks = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]

                if not tool_use_blocks:
                    # No more tools - extract final text
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response = block.text
                    break

                # Execute tool calls
                tool_results = []
                for tool_block in tool_use_blocks:
                    tool_name = tool_block.name
                    tool_input = tool_block.input

                    # Update workflow phase based on tool
                    new_phase = self._tool_to_phase(tool_name, current_phase)
                    if new_phase != current_phase:
                        if phase_started:
                            await self._complete_current_phase(
                                current_phase, candidates_count, analyzed_count, trades_executed
                            )
                        current_phase = new_phase
                        await self.tracker.start_phase(new_phase, f"Running {tool_name}")
                        phase_started = True

                    logger.info(f"Tool call: {tool_name}")
                    tools_called.append({"tool": tool_name, "input": tool_input})

                    # Execute tool
                    result = executor.execute(tool_name, tool_input)

                    # Update counts for phase metadata
                    if tool_name == "scan_market" and isinstance(result, dict):
                        candidates_count = len(result.get("candidates", []))
                    elif tool_name in ["get_quote", "get_technicals", "detect_patterns", "get_news"]:
                        analyzed_count += 1
                    # === CRITICAL FIX: Handle DECIDE → VALIDATE → EXECUTE → MONITOR transitions ===
                    elif tool_name == "check_risk" and isinstance(result, dict):
                        # After DECIDE (check_risk), transition to VALIDATE with the result
                        if phase_started:
                            await self._complete_current_phase(current_phase, candidates_count, analyzed_count, trades_executed)
                        current_phase = "VALIDATE"
                        await self.tracker.start_phase("VALIDATE", "Risk validation")
                        await self.tracker.complete_phase("VALIDATE",
                            approved=result.get("approved", False),
                            reason=result.get("reason", "")
                        )
                        phase_started = False  # VALIDATE is immediately completed

                    elif tool_name == "execute_trade" and isinstance(result, dict):
                        if result.get("status") in ["filled", "success", "FILLED", "submitted", "SUBMITTED"]:
                            trades_executed += 1

                            # After successful EXECUTE, transition to MONITOR
                            if phase_started:
                                await self._complete_current_phase(current_phase, candidates_count, analyzed_count, trades_executed)

                            # Start and complete MONITOR phase
                            await self.tracker.start_phase("MONITOR", "Position monitoring started")
                            await self.tracker.complete_phase("MONITOR",
                                symbol=result.get("symbol"),
                                side=tool_input.get("side"),
                                quantity=tool_input.get("quantity"),
                                monitor_started=result.get("monitor_result") is not None
                            )
                            current_phase = "MONITOR"
                            phase_started = False  # MONITOR is immediately completed
                    # === END CRITICAL FIX ===

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result),
                    })

                # Add tool results
                messages.append({"role": "user", "content": tool_results})

                if response.stop_reason == "end_turn":
                    break

            # Complete final phase
            if phase_started:
                await self._complete_current_phase(
                    current_phase, candidates_count, analyzed_count, trades_executed
                )

            # LOG phase
            await self.tracker.start_phase("LOG", "Recording decisions")
            await self.tracker.complete_phase("LOG", tools_called=len(tools_called))

        except Exception as e:
            logger.error(f"Claude loop error: {e}", exc_info=True)
            error = str(e)
            await self.tracker.error_phase(current_phase, error)

        return {
            'cycle_id': self.cycle_id,
            'status': 'error' if error else 'completed',
            'trades_executed': trades_executed,
            'tools_called': len(tools_called),
            'candidates_found': candidates_count,
            'analyzed': analyzed_count,
            'final_response': final_response[:500] if final_response else None,
            'error': error,
        }

    def _build_context(self, mode: str = "trade") -> str:
        """Build initial context for Claude."""
        now = datetime.now(HK_TZ)

        context = f"""## Trading Cycle Context

**Date/Time**: {now.strftime('%Y-%m-%d %H:%M:%S')} HKT ({now.strftime('%A')})
**Cycle ID**: {self.cycle_id}
**Mode**: Paper Trading

## Your Task

Execute your trading strategy for this cycle:
1. Check current portfolio status
2. Scan for new opportunities
3. Analyze top candidates
4. Execute trades if criteria met
5. Monitor and manage existing positions
6. Log all decisions

Begin by checking the portfolio status, then scan the market for candidates.
Make sure to log your decisions and reasoning throughout.
"""

        if mode == "close":
            context += """
**SPECIAL MODE: CLOSE CYCLE**
Focus on reviewing existing positions for potential exits.
Check for positions that should be closed based on:
- P&L thresholds
- Time-based rules (lunch break, end of day)
- Pattern failures
"""

        return context

    def _tool_to_phase(self, tool_name: str, current_phase: str) -> str:
        """Map tool name to workflow phase.

        Phase order: INIT → PORTFOLIO → SCAN → ANALYZE → DECIDE → VALIDATE → EXECUTE → MONITOR → LOG → COMPLETE

        Note: DECIDE phase is triggered when check_risk is called (decision has been made).
        MONITOR phase is triggered after successful trade execution in the tool loop.
        """
        phase_map = {
            "get_portfolio": "PORTFOLIO",
            "scan_market": "SCAN",
            "get_quote": "ANALYZE",
            "get_technicals": "ANALYZE",
            "detect_patterns": "ANALYZE",
            "get_news": "ANALYZE",
            "check_risk": "DECIDE",      # FIXED: check_risk means a decision has been made
            "execute_trade": "EXECUTE",
            "close_position": "EXECUTE",
            "close_all": "EXECUTE",
            "send_alert": "LOG",
            "log_decision": "LOG",
        }

        new_phase = phase_map.get(tool_name, current_phase)

        # Don't go backwards in phases
        current_idx = WORKFLOW_PHASES.index(current_phase) if current_phase in WORKFLOW_PHASES else 0
        new_idx = WORKFLOW_PHASES.index(new_phase) if new_phase in WORKFLOW_PHASES else current_idx

        # Log blocked backward transitions for debugging
        if new_idx < current_idx:
            logger.debug(f"Blocked backward phase transition: {current_phase} → {new_phase} (tool: {tool_name})")

        return new_phase if new_idx >= current_idx else current_phase

    async def _complete_current_phase(self, phase: str, candidates: int, analyzed: int, trades: int):
        """Complete current workflow phase with appropriate metadata."""
        if phase == "SCAN":
            await self.tracker.complete_phase(phase, candidates=candidates)
        elif phase == "ANALYZE":
            await self.tracker.complete_phase(phase, analyzed=analyzed)
        elif phase == "DECIDE":
            await self.tracker.complete_phase(phase, decision_made=True)
        elif phase == "EXECUTE":
            await self.tracker.complete_phase(phase, trades=trades)
        elif phase == "MONITOR":
            await self.tracker.complete_phase(phase, monitoring_active=True)
        else:
            await self.tracker.complete_phase(phase)

    async def _close_position(
        self,
        position: Dict[str, Any],
        reason: str
    ) -> Dict[str, Any]:
        """Close a position."""
        symbol = position['symbol']
        quantity = position['quantity']
        
        try:
            result = self.broker.execute_trade(
                symbol=symbol,
                side='sell',
                quantity=quantity,
                order_type='market',
                reason=reason
            )
            
            if result and result.order_id and result.status not in ('FAILED', 'NO_POSITION'):
                logger.info(f"Closed {symbol}: {reason}")
                return {'success': True}
            else:
                return {'success': False}
                
        except Exception as e:
            logger.error(f"Close position error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_technicals(self, symbol: str) -> Dict[str, Any]:
        """Get technical indicators for symbol."""
        if not self.market_data:
            return {}
        
        try:
            return self.market_data.get_technicals(symbol) or {}
        except:
            return {}


# =============================================================================
# MAIN
# =============================================================================

async def main(mode: str, config_path: Optional[str] = None):
    """Main entry point."""

    # Load config
    config = load_config(config_path)
    agent_id = config['agent']['id']

    logger.info(f"Starting {agent_id} in {mode} mode")

    # Get database URL
    trading_url = os.getenv("DATABASE_URL") or os.getenv("INTL_DATABASE_URL") or os.getenv("DEV_DATABASE_URL")

    if not trading_url:
        logger.error("No DATABASE_URL set")
        sys.exit(1)

    # Create components
    db = Database(trading_url)

    # Initialize the synchronous database singleton (for tool_executor)
    init_database()

    # Create broker (if available) - use init_moomoo_client for singleton
    broker = None
    market_data = None
    if init_moomoo_client:
        try:
            broker = init_moomoo_client(paper_trading=True)
        except Exception as e:
            logger.warning(f"Could not initialize broker: {e}")
    
    # Create Anthropic client
    anthropic_client = anthropic.Anthropic()
    
    # Create agent
    agent = UnifiedAgent(
        config=config,
        broker=broker,
        market_data=market_data,
        anthropic_client=anthropic_client,
        db=db
    )
    
    try:
        await agent.initialize()
        
        # Run appropriate mode
        if mode == 'startup':
            result = await agent.run_startup()
        elif mode == 'trade':
            # Run startup first if first cycle of day
            result = await agent.run_trade_cycle()
        elif mode == 'close':
            result = await agent.run_close_cycle()
        elif mode == 'heartbeat':
            result = await agent.run_heartbeat()
        elif mode == 'scan':
            result = await agent.run_trade_cycle()  # Same as trade for now
        else:
            logger.error(f"Unknown mode: {mode}")
            result = {'error': f'Unknown mode: {mode}'}
        
        logger.info(f"Result: {result}")
        
    finally:
        await agent.shutdown()


def cli():
    """Command line interface."""
    parser = argparse.ArgumentParser(
        description='Unified Trading Agent for HKEX (v3.0.0 with Claude AI loop)'
    )
    parser.add_argument(
        '--mode',
        choices=['startup', 'scan', 'trade', 'close', 'heartbeat'],
        default='heartbeat',
        help='Operating mode'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config file'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Use live trading (default is paper)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Run even if market is closed'
    )

    args = parser.parse_args()

    # Set force flag in environment for market check
    if args.force:
        os.environ['FORCE_MARKET_OPEN'] = '1'

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    logger.info("=" * 60)
    logger.info("Catalyst Trading Agent - HKEX (v3.0.0 with Claude AI loop)")
    logger.info("=" * 60)

    asyncio.run(main(args.mode, args.config))


if __name__ == "__main__":
    cli()
