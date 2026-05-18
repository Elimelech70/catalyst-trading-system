#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: position_monitor_service.py
Version: 1.0.0
Last Updated: 2026-01-16
Purpose: Persistent systemd service for continuous HKEX position monitoring

REVISION HISTORY:
v1.0.0 (2026-01-16) - Initial implementation
  - Persistent daemon for position monitoring
  - Checks ALL open positions every 5 minutes
  - Uses signals.py for exit detection
  - Haiku consultation for moderate signals
  - Consciousness integration for alerts

Description:
This service runs continuously during HKEX market hours, monitoring all
open positions for exit signals. Unlike the previous design where monitors
died when the entry process ended, this service ensures no position goes
unmonitored.

Usage:
    # Direct execution (testing)
    python3 position_monitor_service.py
    
    # As systemd service
    systemctl start position-monitor
    systemctl status position-monitor
    journalctl -u position-monitor -f

Environment Variables:
    DATABASE_URL          - PostgreSQL connection (catalyst_intl)
    RESEARCH_DATABASE_URL - PostgreSQL connection (catalyst_research)
    ANTHROPIC_API_KEY     - For Haiku consultations
    MONITOR_CHECK_INTERVAL - Check interval in seconds (default: 300)
    MONITOR_DRY_RUN       - If 'true', don't execute actual trades
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo

import asyncpg

# Optional imports - handle gracefully if not available
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

# ============================================================================
# CONFIGURATION
# ============================================================================

# Check interval (default 5 minutes)
CHECK_INTERVAL = int(os.getenv("MONITOR_CHECK_INTERVAL", "300"))

# Dry run mode (no actual trades)
DRY_RUN = os.getenv("MONITOR_DRY_RUN", "false").lower() == "true"

# Haiku settings
MAX_HAIKU_CALLS_PER_CYCLE = 5
HAIKU_MODEL = "claude-3-haiku-20240307"

# Hong Kong timezone
HK_TZ = ZoneInfo("Asia/Hong_Kong")

# Market hours (HKEX)
MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(12, 0)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(16, 0)

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('position-monitor')

# ============================================================================
# SIGNAL DETECTION (Embedded from signals.py)
# ============================================================================

class SignalStrength:
    """Signal strength levels."""
    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class SignalThresholds:
    """Configurable thresholds for signal detection."""
    
    def __init__(
        self,
        # P&L thresholds
        stop_loss_strong: float = -0.03,      # -3%
        stop_loss_moderate: float = -0.02,    # -2%
        stop_loss_weak: float = -0.01,        # -1%
        take_profit_strong: float = 0.08,     # +8%
        take_profit_moderate: float = 0.05,   # +5%
        # RSI thresholds
        rsi_overbought_strong: float = 85,
        rsi_overbought_moderate: float = 75,
        rsi_oversold_strong: float = 15,
        rsi_oversold_moderate: float = 25,
        # Volume thresholds (as ratio to entry volume)
        volume_collapse_strong: float = 0.25,
        volume_collapse_moderate: float = 0.40,
        # Trailing stop
        trailing_stop_pct: float = 0.02,      # 2% from high
    ):
        self.stop_loss_strong = stop_loss_strong
        self.stop_loss_moderate = stop_loss_moderate
        self.stop_loss_weak = stop_loss_weak
        self.take_profit_strong = take_profit_strong
        self.take_profit_moderate = take_profit_moderate
        self.rsi_overbought_strong = rsi_overbought_strong
        self.rsi_overbought_moderate = rsi_overbought_moderate
        self.rsi_oversold_strong = rsi_oversold_strong
        self.rsi_oversold_moderate = rsi_oversold_moderate
        self.volume_collapse_strong = volume_collapse_strong
        self.volume_collapse_moderate = volume_collapse_moderate
        self.trailing_stop_pct = trailing_stop_pct


DEFAULT_THRESHOLDS = SignalThresholds()


def analyze_position(
    entry_price: float,
    current_price: float,
    high_watermark: float,
    entry_volume: float = 0,
    current_volume: float = 0,
    rsi: Optional[float] = None,
    macd_histogram: Optional[float] = None,
    vwap: Optional[float] = None,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS
) -> Dict[str, Any]:
    """
    Analyze position for exit signals.
    
    Returns:
        {
            'immediate_exit': bool,      # STRONG signal - exit now
            'consult_ai': bool,          # MODERATE signal - ask Haiku
            'active_signals': List[str], # List of triggered signals
            'strongest_signal': str,     # Strongest signal description
            'pnl_pct': float,           # Current P&L percentage
        }
    """
    signals = []
    strongest = None
    immediate_exit = False
    consult_ai = False
    
    # Calculate P&L
    pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0
    
    # === P&L SIGNALS ===
    if pnl_pct <= thresholds.stop_loss_strong:
        signals.append(f"stop_loss:{SignalStrength.STRONG}")
        immediate_exit = True
        strongest = f"Stop loss hit ({pnl_pct:.1%})"
    elif pnl_pct <= thresholds.stop_loss_moderate:
        signals.append(f"stop_loss:{SignalStrength.MODERATE}")
        consult_ai = True
        strongest = strongest or f"Near stop loss ({pnl_pct:.1%})"
    elif pnl_pct <= thresholds.stop_loss_weak:
        signals.append(f"stop_loss:{SignalStrength.WEAK}")
        
    if pnl_pct >= thresholds.take_profit_strong:
        signals.append(f"take_profit:{SignalStrength.STRONG}")
        immediate_exit = True
        strongest = strongest or f"Take profit target ({pnl_pct:.1%})"
    elif pnl_pct >= thresholds.take_profit_moderate:
        signals.append(f"take_profit:{SignalStrength.MODERATE}")
        consult_ai = True
        strongest = strongest or f"Near take profit ({pnl_pct:.1%})"
        
    # === TRAILING STOP ===
    if high_watermark > entry_price:
        drop_from_high = (high_watermark - current_price) / high_watermark
        if drop_from_high >= thresholds.trailing_stop_pct:
            signals.append(f"trailing_stop:{SignalStrength.MODERATE}")
            consult_ai = True
            strongest = strongest or f"Trailing stop ({drop_from_high:.1%} from high)"
            
    # === RSI SIGNALS ===
    if rsi is not None:
        if rsi >= thresholds.rsi_overbought_strong:
            signals.append(f"rsi_overbought:{SignalStrength.STRONG}")
            immediate_exit = True
            strongest = strongest or f"RSI overbought ({rsi:.0f})"
        elif rsi >= thresholds.rsi_overbought_moderate:
            signals.append(f"rsi_overbought:{SignalStrength.MODERATE}")
            consult_ai = True
            strongest = strongest or f"RSI elevated ({rsi:.0f})"
            
    # === VOLUME SIGNALS ===
    if entry_volume > 0 and current_volume > 0:
        volume_ratio = current_volume / entry_volume
        if volume_ratio <= thresholds.volume_collapse_strong:
            signals.append(f"volume_collapse:{SignalStrength.STRONG}")
            immediate_exit = True
            strongest = strongest or f"Volume collapsed ({volume_ratio:.0%})"
        elif volume_ratio <= thresholds.volume_collapse_moderate:
            signals.append(f"volume_collapse:{SignalStrength.MODERATE}")
            consult_ai = True
            strongest = strongest or f"Volume fading ({volume_ratio:.0%})"
            
    # === MACD SIGNALS ===
    if macd_histogram is not None and macd_histogram < -0.5:
        signals.append(f"macd_bearish:{SignalStrength.MODERATE}")
        consult_ai = True
        strongest = strongest or "MACD bearish"
        
    # === TIME-BASED SIGNALS ===
    now = datetime.now(HK_TZ)
    current_time = now.time()
    
    # Near market close
    if time(15, 50) <= current_time < time(16, 0):
        signals.append(f"near_close:{SignalStrength.STRONG}")
        immediate_exit = True
        strongest = strongest or "Market closing soon"
        
    # Near lunch break
    if time(11, 50) <= current_time < time(12, 0):
        signals.append(f"lunch_break:{SignalStrength.MODERATE}")
        consult_ai = True
        strongest = strongest or "Lunch break approaching"
        
    return {
        'immediate_exit': immediate_exit,
        'consult_ai': consult_ai,
        'active_signals': signals,
        'strongest_signal': strongest or "No significant signals",
        'pnl_pct': pnl_pct,
    }


# ============================================================================
# BROKER INTERFACE (Simplified)
# ============================================================================

class BrokerInterface:
    """
    Simplified broker interface for position monitoring.
    
    This class wraps the Moomoo client to provide the specific
    functionality needed for position monitoring.
    """
    
    def __init__(self):
        self.client = None
        self._connected = False
        
    def connect(self) -> bool:
        """Connect to broker."""
        try:
            # Import here to avoid issues if not installed
            from brokers.moomoo import get_moomoo_client
            self.client = get_moomoo_client()
            self._connected = True
            logger.info("Broker connected")
            return True
        except Exception as e:
            logger.error(f"Broker connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from broker."""
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self._connected = False
        
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current quote for symbol."""
        if not self._connected:
            return None
        try:
            return self.client.get_quote(symbol)
        except Exception as e:
            logger.error(f"Quote error for {symbol}: {e}")
            return None
            
    def get_technicals(self, symbol: str) -> Dict[str, Any]:
        """Get technical indicators for symbol."""
        if not self._connected:
            return {}
        try:
            # Try to get from market data
            from data.market import get_market_data
            market_data = get_market_data(self.client)
            return market_data.get_technicals(symbol) or {}
        except Exception as e:
            logger.warning(f"Technicals error for {symbol}: {e}")
            return {}
            
    def place_sell_order(
        self,
        symbol: str,
        quantity: int,
        order_type: str = "MARKET"
    ) -> Dict[str, Any]:
        """Place sell order."""
        if not self._connected:
            return {'status': 'error', 'message': 'Not connected'}
            
        if DRY_RUN:
            logger.info(f"[DRY RUN] Would sell {quantity} {symbol}")
            return {'status': 'filled', 'fill_price': 0, 'dry_run': True}
            
        try:
            return self.client.place_order(
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                order_type=order_type
            )
        except Exception as e:
            logger.error(f"Order error for {symbol}: {e}")
            return {'status': 'error', 'message': str(e)}


# ============================================================================
# POSITION MONITOR SERVICE
# ============================================================================

class PositionMonitorService:
    """
    Persistent position monitoring service.
    
    Runs as a systemd daemon, checking all open positions every
    CHECK_INTERVAL seconds during market hours.
    """
    
    def __init__(self):
        self.running = True
        self.check_count = 0
        
        # Connections
        self.db_pool: Optional[asyncpg.Pool] = None
        self.research_pool: Optional[asyncpg.Pool] = None
        self.broker = BrokerInterface()
        self.anthropic_client = None
        
        # Configuration
        self.thresholds = DEFAULT_THRESHOLDS
        
        # Statistics
        self.stats = {
            'positions_checked': 0,
            'exits_executed': 0,
            'haiku_calls': 0,
            'errors': 0,
            'started_at': None,
        }
        
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown signal."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        
    async def initialize(self) -> bool:
        """Initialize all connections."""
        logger.info("Initializing service...")
        
        # Database - trading
        db_url = os.getenv("DATABASE_URL") or os.getenv("INTL_DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL not set")
            return False
            
        try:
            self.db_pool = await asyncpg.create_pool(
                db_url,
                min_size=2,
                max_size=5,
                command_timeout=30
            )
            logger.info("Trading database connected")
        except Exception as e:
            logger.error(f"Trading database connection failed: {e}")
            return False
            
        # Database - research (optional, for consciousness)
        research_url = os.getenv("RESEARCH_DATABASE_URL")
        if research_url:
            try:
                self.research_pool = await asyncpg.create_pool(
                    research_url,
                    min_size=1,
                    max_size=2,
                    command_timeout=30
                )
                logger.info("Research database connected")
            except Exception as e:
                logger.warning(f"Research database connection failed: {e}")
                
        # Broker
        if not self.broker.connect():
            logger.error("Broker connection failed")
            return False
            
        # Anthropic (optional)
        if ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Anthropic client initialized")
            else:
                logger.warning("ANTHROPIC_API_KEY not set - Haiku disabled")
        else:
            logger.warning("anthropic package not installed - Haiku disabled")
            
        self.stats['started_at'] = datetime.now(HK_TZ)
        logger.info("Service initialization complete")
        return True
        
    async def shutdown(self):
        """Clean shutdown of all connections."""
        logger.info("Shutting down service...")
        
        if self.db_pool:
            await self.db_pool.close()
            
        if self.research_pool:
            await self.research_pool.close()
            
        self.broker.disconnect()
        
        logger.info("Service shutdown complete")
        
    # ========================================================================
    # MARKET HOURS
    # ========================================================================
    
    def is_market_open(self) -> Tuple[bool, str]:
        """
        Check if HKEX market is currently open.
        
        Returns:
            (is_open: bool, status: str)
        """
        now = datetime.now(HK_TZ)
        
        # Weekend
        if now.weekday() >= 5:
            return False, "weekend"
            
        current_time = now.time()
        
        # Pre-market
        if current_time < MORNING_OPEN:
            return False, "pre_market"
            
        # Morning session
        if MORNING_OPEN <= current_time < MORNING_CLOSE:
            return True, "morning_session"
            
        # Lunch break
        if MORNING_CLOSE <= current_time < AFTERNOON_OPEN:
            return False, "lunch_break"
            
        # Afternoon session
        if AFTERNOON_OPEN <= current_time < AFTERNOON_CLOSE:
            return True, "afternoon_session"
            
        # After hours
        return False, "after_hours"
        
    def get_next_market_open(self) -> datetime:
        """Calculate next market open time."""
        now = datetime.now(HK_TZ)
        
        # If before today's open
        if now.time() < MORNING_OPEN and now.weekday() < 5:
            return now.replace(
                hour=MORNING_OPEN.hour,
                minute=MORNING_OPEN.minute,
                second=0,
                microsecond=0
            )
            
        # If in lunch break
        if MORNING_CLOSE <= now.time() < AFTERNOON_OPEN and now.weekday() < 5:
            return now.replace(
                hour=AFTERNOON_OPEN.hour,
                minute=AFTERNOON_OPEN.minute,
                second=0,
                microsecond=0
            )
            
        # Next trading day
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
            
        return next_day.replace(
            hour=MORNING_OPEN.hour,
            minute=MORNING_OPEN.minute,
            second=0,
            microsecond=0
        )
        
    # ========================================================================
    # DATABASE OPERATIONS
    # ========================================================================
    
    async def load_open_positions(self) -> List[Dict[str, Any]]:
        """Load all open positions from database."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    position_id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    stop_loss,
                    take_profit,
                    entry_reason,
                    created_at,
                    high_watermark,
                    entry_volume
                FROM positions
                WHERE status = 'open'
                ORDER BY created_at
            """)
            return [dict(r) for r in rows]
            
    async def update_position_exit(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str,
        pnl: float
    ):
        """Update position as closed."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions SET
                    status = 'closed',
                    exit_price = $1,
                    exit_time = NOW(),
                    exit_reason = $2,
                    realized_pnl = $3,
                    updated_at = NOW()
                WHERE position_id = $4
            """, exit_price, exit_reason, pnl, position_id)
            
    async def record_exit_order(
        self,
        position_id: int,
        symbol: str,
        quantity: int,
        fill_price: float
    ):
        """Record exit order in database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orders (
                    position_id, symbol, side, order_type,
                    quantity, filled_price, filled_quantity,
                    status, created_at
                ) VALUES ($1, $2, 'sell', 'MARKET', $3, $4, $3, 'filled', NOW())
            """, position_id, symbol, quantity, fill_price)
            
    async def update_high_watermark(self, position_id: int, high_watermark: float):
        """Update position's high watermark."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE positions SET
                    high_watermark = GREATEST(COALESCE(high_watermark, 0), $1),
                    updated_at = NOW()
                WHERE position_id = $2
            """, high_watermark, position_id)
            
    async def update_service_health(self):
        """Update service health record."""
        if not self.db_pool:
            return
            
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO service_health (
                        service_name, status, last_heartbeat,
                        last_check_count, positions_monitored,
                        exits_executed, haiku_calls, started_at
                    ) VALUES (
                        'position_monitor', 'running', NOW(),
                        $1, $2, $3, $4, $5
                    )
                    ON CONFLICT (service_name) DO UPDATE SET
                        status = 'running',
                        last_heartbeat = NOW(),
                        last_check_count = $1,
                        positions_monitored = $2,
                        exits_executed = $3,
                        haiku_calls = $4,
                        updated_at = NOW()
                """,
                    self.check_count,
                    self.stats['positions_checked'],
                    self.stats['exits_executed'],
                    self.stats['haiku_calls'],
                    self.stats['started_at']
                )
        except Exception as e:
            logger.warning(f"Failed to update service health: {e}")
            
    # ========================================================================
    # CONSCIOUSNESS INTEGRATION
    # ========================================================================
    
    async def notify_consciousness(
        self,
        message: str,
        priority: str = 'normal',
        subject: str = 'Position Monitor Alert'
    ):
        """Send notification to consciousness framework."""
        if not self.research_pool:
            return
            
        try:
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_messages (
                        from_agent, to_agent, subject, body, 
                        priority, msg_type, status
                    ) VALUES (
                        'position_monitor', 'big_bro', $1, $2,
                        $3, 'alert', 'pending'
                    )
                """, subject, message, priority)
        except Exception as e:
            logger.warning(f"Failed to notify consciousness: {e}")
            
    async def record_observation(self, content: str, obs_type: str = 'trading'):
        """Record observation in consciousness."""
        if not self.research_pool:
            return
            
        try:
            async with self.research_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO claude_observations (
                        agent_id, observation_type, content
                    ) VALUES ('position_monitor', $1, $2)
                """, obs_type, content)
        except Exception as e:
            logger.warning(f"Failed to record observation: {e}")
            
    # ========================================================================
    # HAIKU CONSULTATION
    # ========================================================================
    
    async def consult_haiku(
        self,
        position: Dict[str, Any],
        signals: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """
        Consult Haiku for exit decision on moderate signals.
        
        Returns:
            {'should_exit': bool, 'reason': str}
        """
        if not self.anthropic_client:
            return {'should_exit': False, 'reason': 'Haiku unavailable'}
            
        symbol = position['symbol']
        entry_price = float(position['entry_price'])
        pnl_pct = signals['pnl_pct'] * 100
        
        prompt = f"""You are monitoring an HKEX position. Quick decision needed.

POSITION:
- Symbol: {symbol}
- Entry: HKD {entry_price:.2f}
- Current: HKD {current_price:.2f}
- P&L: {pnl_pct:+.2f}%
- Quantity: {position['quantity']}

ACTIVE SIGNALS:
{chr(10).join(f'- {s}' for s in signals.get('active_signals', []))}

ENTRY REASON: {position.get('entry_reason', 'Unknown')}

Should we EXIT or HOLD?

Respond with exactly one word on the first line: EXIT or HOLD
Then a brief reason (one sentence) on the second line.
"""
        
        try:
            response = self.anthropic_client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            self.stats['haiku_calls'] += 1
            
            lines = text.split('\n')
            decision = lines[0].strip().upper()
            reason = lines[1].strip() if len(lines) > 1 else "Haiku decision"
            
            should_exit = decision.startswith("EXIT")
            
            logger.info(f"Haiku decision for {symbol}: {'EXIT' if should_exit else 'HOLD'} - {reason}")
            
            return {'should_exit': should_exit, 'reason': reason}
            
        except Exception as e:
            logger.error(f"Haiku consultation failed: {e}")
            self.stats['errors'] += 1
            return {'should_exit': False, 'reason': f'Haiku error: {e}'}
            
    # ========================================================================
    # POSITION CHECKING
    # ========================================================================
    
    async def check_position(self, position: Dict[str, Any]) -> Optional[str]:
        """
        Check a single position for exit signals.
        
        Returns:
            Exit reason string if should exit, None if should hold
        """
        symbol = position['symbol']
        position_id = position['position_id']
        
        # Get current quote
        quote = self.broker.get_quote(symbol)
        if not quote:
            logger.warning(f"No quote for {symbol}, skipping")
            return None
            
        current_price = float(quote.get('price', 0))
        if current_price <= 0:
            logger.warning(f"Invalid price for {symbol}: {current_price}")
            return None
            
        # Get technicals
        technicals = self.broker.get_technicals(symbol)
        
        # Calculate values
        entry_price = float(position['entry_price'])
        high_watermark = float(position.get('high_watermark') or entry_price)
        entry_volume = float(position.get('entry_volume') or 0)
        current_volume = float(quote.get('volume') or 0)
        
        # Update high watermark if new high
        if current_price > high_watermark:
            high_watermark = current_price
            await self.update_high_watermark(position_id, high_watermark)
            
        # Analyze signals
        signals = analyze_position(
            entry_price=entry_price,
            current_price=current_price,
            high_watermark=high_watermark,
            entry_volume=entry_volume,
            current_volume=current_volume,
            rsi=technicals.get('rsi'),
            macd_histogram=technicals.get('macd_histogram'),
            vwap=technicals.get('vwap'),
            thresholds=self.thresholds
        )
        
        # Log position status
        pnl_pct = signals['pnl_pct'] * 100
        logger.info(
            f"  {symbol}: HKD {current_price:.2f} ({pnl_pct:+.2f}%) "
            f"signals={len(signals['active_signals'])}"
        )
        
        # Decision logic
        if signals['immediate_exit']:
            return signals['strongest_signal']
            
        if signals['consult_ai'] and self.stats['haiku_calls'] < MAX_HAIKU_CALLS_PER_CYCLE:
            decision = await self.consult_haiku(position, signals, current_price)
            if decision['should_exit']:
                return f"Haiku: {decision['reason']}"
                
        return None
        
    async def execute_exit(
        self,
        position: Dict[str, Any],
        reason: str
    ) -> bool:
        """Execute exit order for position."""
        symbol = position['symbol']
        quantity = int(position['quantity'])
        position_id = position['position_id']
        entry_price = float(position['entry_price'])
        
        logger.info(f"Executing exit: {symbol} x {quantity} - {reason}")
        
        # Place order
        result = self.broker.place_sell_order(symbol, quantity)
        
        if result.get('status') in ['filled', 'FILLED', 'submitted', 'SUBMITTED']:
            # Get fill price (use last quote if not in result)
            fill_price = float(result.get('fill_price', 0))
            if fill_price <= 0:
                quote = self.broker.get_quote(symbol)
                fill_price = float(quote.get('price', entry_price)) if quote else entry_price
                
            # Calculate P&L
            pnl = (fill_price - entry_price) * quantity
            pnl_pct = (fill_price - entry_price) / entry_price * 100
            
            # Update database
            await self.update_position_exit(position_id, fill_price, reason, pnl)
            await self.record_exit_order(position_id, symbol, quantity, fill_price)
            
            # Notify consciousness
            await self.notify_consciousness(
                f"Exited {symbol} x {quantity} @ HKD {fill_price:.2f}\n"
                f"Reason: {reason}\n"
                f"P&L: HKD {pnl:+.2f} ({pnl_pct:+.2f}%)",
                priority='high'
            )
            
            logger.info(
                f"Exit complete: {symbol} @ HKD {fill_price:.2f} "
                f"(P&L: HKD {pnl:+.2f} / {pnl_pct:+.2f}%)"
            )
            
            self.stats['exits_executed'] += 1
            return True
        else:
            logger.error(f"Exit order failed: {result}")
            self.stats['errors'] += 1
            return False
            
    # ========================================================================
    # MAIN MONITORING CYCLE
    # ========================================================================
    
    async def run_monitoring_cycle(self):
        """Run one complete monitoring cycle."""
        self.check_count += 1
        cycle_start = datetime.now(HK_TZ)
        haiku_calls_start = self.stats['haiku_calls']
        
        logger.info("=" * 60)
        logger.info(f"Monitoring Cycle #{self.check_count}")
        logger.info(f"Time: {cycle_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 60)
        
        # Load all open positions
        positions = await self.load_open_positions()
        
        if not positions:
            logger.info("No open positions to monitor")
            return
            
        logger.info(f"Checking {len(positions)} open positions:")
        
        exits_this_cycle = 0
        
        for position in positions:
            self.stats['positions_checked'] += 1
            
            try:
                exit_reason = await self.check_position(position)
                
                if exit_reason:
                    success = await self.execute_exit(position, exit_reason)
                    if success:
                        exits_this_cycle += 1
                        
            except Exception as e:
                logger.error(f"Error checking {position['symbol']}: {e}")
                self.stats['errors'] += 1
                
        # Cycle summary
        duration = (datetime.now(HK_TZ) - cycle_start).total_seconds()
        haiku_calls = self.stats['haiku_calls'] - haiku_calls_start
        
        logger.info("-" * 60)
        logger.info(
            f"Cycle complete: {len(positions)} positions, "
            f"{exits_this_cycle} exits, {haiku_calls} Haiku calls, "
            f"{duration:.1f}s"
        )
        
        # Update health status
        await self.update_service_health()
        
        # Record observation if exits occurred
        if exits_this_cycle > 0:
            await self.record_observation(
                f"Monitoring cycle #{self.check_count}: "
                f"{exits_this_cycle} exits from {len(positions)} positions"
            )
            
    # ========================================================================
    # MAIN SERVICE LOOP
    # ========================================================================
    
    async def run(self):
        """Main service loop."""
        logger.info("=" * 60)
        logger.info("HKEX Position Monitor Service")
        logger.info(f"Version: 1.0.0")
        logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
        logger.info(f"Dry run mode: {DRY_RUN}")
        logger.info("=" * 60)
        
        # Initialize
        if not await self.initialize():
            logger.error("Initialization failed, exiting")
            return
            
        # Notify startup
        await self.notify_consciousness(
            "Position Monitor Service started",
            priority='low',
            subject='Service Startup'
        )
        
        # Main loop
        while self.running:
            try:
                is_open, status = self.is_market_open()
                
                if is_open:
                    await self.run_monitoring_cycle()
                    await asyncio.sleep(CHECK_INTERVAL)
                else:
                    # Calculate sleep time
                    next_open = self.get_next_market_open()
                    now = datetime.now(HK_TZ)
                    sleep_seconds = (next_open - now).total_seconds()
                    
                    # Cap at 1 hour to allow periodic wakeups
                    sleep_seconds = min(sleep_seconds, 3600)
                    sleep_seconds = max(sleep_seconds, 60)
                    
                    logger.info(
                        f"Market {status}. "
                        f"Next: {next_open.strftime('%Y-%m-%d %H:%M')} HKT. "
                        f"Sleeping {sleep_seconds/60:.0f} min."
                    )
                    
                    await asyncio.sleep(sleep_seconds)
                    
            except asyncio.CancelledError:
                logger.info("Service cancelled")
                break
            except Exception as e:
                logger.error(f"Service error: {e}", exc_info=True)
                self.stats['errors'] += 1
                await asyncio.sleep(60)
                
        # Shutdown
        await self.notify_consciousness(
            f"Position Monitor Service stopped. "
            f"Cycles: {self.check_count}, Exits: {self.stats['exits_executed']}",
            priority='normal',
            subject='Service Shutdown'
        )
        
        await self.shutdown()
        
        # Final stats
        logger.info("=" * 60)
        logger.info("SERVICE STATISTICS")
        logger.info(f"  Monitoring cycles: {self.check_count}")
        logger.info(f"  Positions checked: {self.stats['positions_checked']}")
        logger.info(f"  Exits executed: {self.stats['exits_executed']}")
        logger.info(f"  Haiku calls: {self.stats['haiku_calls']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info("=" * 60)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Service entry point."""
    service = PositionMonitorService()
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, service.handle_shutdown)
    signal.signal(signal.SIGINT, service.handle_shutdown)
    
    # Run service
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
