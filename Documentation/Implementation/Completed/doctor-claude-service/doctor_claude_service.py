#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: doctor_claude_service.py
Version: 1.0.0
Last Updated: 2025-12-27
Purpose: Systemd service daemon for Doctor Claude monitoring

REVISION HISTORY:
v1.0.0 (2025-12-27) - Initial service implementation
  - Runs as systemd service
  - Market hours detection (US Eastern)
  - Graceful shutdown handling
  - Structured logging to journald

USAGE:
    # Direct execution (for testing)
    python3 doctor_claude_service.py
    
    # As systemd service
    systemctl start doctor-claude

ENVIRONMENT VARIABLES:
    DATABASE_URL          - PostgreSQL connection string (required)
    ALPACA_API_KEY        - Alpaca API key (required)
    ALPACA_SECRET_KEY     - Alpaca secret key (required)
    TRADING_MODE          - 'paper' or 'live' (default: paper)
    DOCTOR_CLAUDE_INTERVAL - Check interval in seconds (default: 300)
    DOCTOR_CLAUDE_VERBOSE  - Enable verbose logging (default: false)
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Optional
import subprocess

# ============================================================================
# CONFIGURATION
# ============================================================================

# Check interval (default 5 minutes)
CHECK_INTERVAL = int(os.getenv("DOCTOR_CLAUDE_INTERVAL", "300"))

# Verbose mode
VERBOSE = os.getenv("DOCTOR_CLAUDE_VERBOSE", "false").lower() == "true"

# Script paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHDOG_SCRIPT = os.path.join(SCRIPTS_DIR, "trade_watchdog.py")

# Market hours (US Eastern)
MARKET_OPEN = time(9, 30)   # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET

# Pre/post market buffer (start monitoring 15 min before open, 15 min after close)
PRE_MARKET_BUFFER = timedelta(minutes=15)
POST_MARKET_BUFFER = timedelta(minutes=15)

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Configure logging for systemd journal
logging.basicConfig(
    level=logging.DEBUG if VERBOSE else logging.INFO,
    format='%(levelname)s: %(message)s',  # Systemd adds timestamp
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('doctor-claude')

# ============================================================================
# TIMEZONE HANDLING
# ============================================================================

def get_eastern_time() -> datetime:
    """Get current time in US Eastern timezone."""
    try:
        from zoneinfo import ZoneInfo
        eastern = ZoneInfo("America/New_York")
        return datetime.now(eastern)
    except ImportError:
        # Fallback for older Python
        import subprocess
        result = subprocess.run(
            ["date", "+%H:%M", "-d", "TZ=\"America/New_York\""],
            capture_output=True, text=True
        )
        # Simple fallback - assume UTC-5 (EST) or UTC-4 (EDT)
        utc_now = datetime.utcnow()
        # Rough DST detection (March-November)
        if 3 <= utc_now.month <= 11:
            return utc_now - timedelta(hours=4)  # EDT
        else:
            return utc_now - timedelta(hours=5)  # EST


def is_market_hours() -> bool:
    """Check if we're within market hours (with buffer)."""
    now = get_eastern_time()
    
    # Check if weekday (Monday = 0, Sunday = 6)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    
    current_time = now.time()
    
    # Calculate buffered market hours
    open_with_buffer = (datetime.combine(now.date(), MARKET_OPEN) - PRE_MARKET_BUFFER).time()
    close_with_buffer = (datetime.combine(now.date(), MARKET_CLOSE) + POST_MARKET_BUFFER).time()
    
    return open_with_buffer <= current_time <= close_with_buffer


def get_next_market_open() -> datetime:
    """Calculate when market next opens."""
    now = get_eastern_time()
    
    # Start with today's market open
    next_open = datetime.combine(now.date(), MARKET_OPEN)
    
    # If we're past market close today, move to tomorrow
    if now.time() > MARKET_CLOSE:
        next_open += timedelta(days=1)
    
    # Skip weekends
    while next_open.weekday() >= 5:
        next_open += timedelta(days=1)
    
    # Subtract pre-market buffer
    next_open -= PRE_MARKET_BUFFER
    
    return next_open


# ============================================================================
# WATCHDOG EXECUTION
# ============================================================================

async def run_watchdog() -> dict:
    """Execute the trade watchdog script and return results."""
    try:
        # Run watchdog script
        process = await asyncio.create_subprocess_exec(
            sys.executable, WATCHDOG_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Parse JSON output
        try:
            result = json.loads(stdout.decode())
        except json.JSONDecodeError:
            result = {
                "status": "ERROR",
                "error": "Failed to parse watchdog output",
                "stdout": stdout.decode()[:500],
                "stderr": stderr.decode()[:500]
            }
        
        result["exit_code"] = process.returncode
        return result
        
    except FileNotFoundError:
        return {
            "status": "ERROR",
            "error": f"Watchdog script not found: {WATCHDOG_SCRIPT}"
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e)
        }


def log_watchdog_result(result: dict):
    """Log watchdog results in a structured way."""
    status = result.get("status", "UNKNOWN")
    
    if status == "HEALTHY":
        logger.info(
            f"✅ HEALTHY | "
            f"Orders: {result.get('orders', {}).get('total', 0)} | "
            f"Positions: {result.get('positions', {}).get('open', 0)} open | "
            f"Issues: {result.get('issue_summary', {}).get('total', 0)}"
        )
    elif status == "WARNING":
        issues = result.get("issues", [])
        logger.warning(
            f"⚠️  WARNING | "
            f"Issues: {len(issues)} | "
            f"Types: {[i.get('type') for i in issues[:3]]}"
        )
        for issue in issues[:5]:
            logger.warning(f"   - {issue.get('type')}: {issue.get('message', '')[:100]}")
    elif status == "CRITICAL":
        issues = result.get("issues", [])
        logger.error(
            f"🚨 CRITICAL | "
            f"Issues: {len(issues)}"
        )
        for issue in issues:
            logger.error(f"   - {issue.get('type')}: {issue.get('message', '')[:150]}")
    elif status == "ERROR":
        logger.error(f"❌ ERROR | {result.get('error', 'Unknown error')}")
    else:
        logger.info(f"Status: {status} | Result: {json.dumps(result)[:200]}")


# ============================================================================
# MAIN SERVICE LOOP
# ============================================================================

class DoctorClaudeService:
    """Doctor Claude monitoring service."""
    
    def __init__(self):
        self.running = True
        self.check_count = 0
        self.last_check: Optional[datetime] = None
        
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
    async def run(self):
        """Main service loop."""
        logger.info("=" * 60)
        logger.info("Doctor Claude Service Starting")
        logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
        logger.info(f"Watchdog script: {WATCHDOG_SCRIPT}")
        logger.info(f"Verbose mode: {VERBOSE}")
        logger.info("=" * 60)
        
        # Verify watchdog script exists
        if not os.path.exists(WATCHDOG_SCRIPT):
            logger.error(f"Watchdog script not found: {WATCHDOG_SCRIPT}")
            sys.exit(1)
        
        # Verify environment
        if not os.getenv("DATABASE_URL"):
            logger.error("DATABASE_URL environment variable not set")
            sys.exit(1)
            
        logger.info("Environment verified, entering main loop")
        
        while self.running:
            try:
                if is_market_hours():
                    # Run watchdog check
                    self.check_count += 1
                    self.last_check = datetime.now()
                    
                    logger.info(f"--- Check #{self.check_count} at {self.last_check.strftime('%H:%M:%S')} ---")
                    
                    result = await run_watchdog()
                    log_watchdog_result(result)
                    
                    # Sleep until next check
                    await asyncio.sleep(CHECK_INTERVAL)
                    
                else:
                    # Outside market hours - sleep longer
                    next_open = get_next_market_open()
                    now = get_eastern_time()
                    
                    # Calculate sleep time (max 1 hour to allow periodic wakeups)
                    if hasattr(next_open, 'tzinfo') and hasattr(now, 'tzinfo'):
                        sleep_seconds = min((next_open - now).total_seconds(), 3600)
                    else:
                        sleep_seconds = 3600  # Default 1 hour
                    
                    sleep_seconds = max(sleep_seconds, 60)  # At least 1 minute
                    
                    logger.info(
                        f"Outside market hours. "
                        f"Next check in {sleep_seconds/60:.0f} minutes. "
                        f"Market opens at {MARKET_OPEN} ET"
                    )
                    
                    await asyncio.sleep(sleep_seconds)
                    
            except asyncio.CancelledError:
                logger.info("Service cancelled")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                # Sleep before retry to avoid tight error loop
                await asyncio.sleep(60)
        
        logger.info("=" * 60)
        logger.info(f"Doctor Claude Service Stopped")
        logger.info(f"Total checks performed: {self.check_count}")
        logger.info("=" * 60)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Service entry point."""
    service = DoctorClaudeService()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, service.handle_shutdown)
    signal.signal(signal.SIGINT, service.handle_shutdown)
    
    # Run the async service
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
