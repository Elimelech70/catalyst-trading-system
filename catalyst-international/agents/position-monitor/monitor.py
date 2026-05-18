"""
Position Monitor Loop

Background monitoring loop that checks all open positions for exit signals.
Writes recommendations to position_monitor_status table.
NEVER executes trades or writes to positions table.

The coordinator reads recommendations via MCP and decides whether to act.

Version: 1.0.0
"""

import asyncio
import logging
import os
from datetime import datetime, time, timedelta
from typing import Dict, List, Any, Optional, Tuple
from zoneinfo import ZoneInfo

import asyncpg

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

logger = logging.getLogger("position-monitor.loop")

HK_TZ = ZoneInfo("Asia/Hong_Kong")

CHECK_INTERVAL = int(os.getenv("MONITOR_CHECK_INTERVAL", "300"))
MAX_HAIKU_CALLS_PER_CYCLE = 5
HAIKU_MODEL = "claude-haiku-4-5-20251001"

MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(12, 0)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(16, 0)


# ============================================================================
# SIGNAL DETECTION
# ============================================================================

class SignalThresholds:
    def __init__(
        self,
        stop_loss_strong=-0.03, stop_loss_moderate=-0.02,
        take_profit_strong=0.08, take_profit_moderate=0.05,
        rsi_overbought_strong=85, rsi_overbought_moderate=75,
        volume_collapse_strong=0.25, volume_collapse_moderate=0.40,
        trailing_stop_pct=0.02,
    ):
        self.stop_loss_strong = stop_loss_strong
        self.stop_loss_moderate = stop_loss_moderate
        self.take_profit_strong = take_profit_strong
        self.take_profit_moderate = take_profit_moderate
        self.rsi_overbought_strong = rsi_overbought_strong
        self.rsi_overbought_moderate = rsi_overbought_moderate
        self.volume_collapse_strong = volume_collapse_strong
        self.volume_collapse_moderate = volume_collapse_moderate
        self.trailing_stop_pct = trailing_stop_pct


DEFAULT_THRESHOLDS = SignalThresholds()


def analyze_signals(
    entry_price: float, current_price: float, high_watermark: float,
    entry_volume: float = 0, current_volume: float = 0,
    rsi: Optional[float] = None, macd_histogram: Optional[float] = None,
    thresholds: SignalThresholds = DEFAULT_THRESHOLDS,
) -> Dict[str, Any]:
    signals = []
    immediate_exit = False
    consult_ai = False
    strongest = None

    pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

    if pnl_pct <= thresholds.stop_loss_strong:
        signals.append("stop_loss:strong")
        immediate_exit = True
        strongest = f"Stop loss hit ({pnl_pct:.1%})"
    elif pnl_pct <= thresholds.stop_loss_moderate:
        signals.append("stop_loss:moderate")
        consult_ai = True
        strongest = strongest or f"Near stop loss ({pnl_pct:.1%})"

    if pnl_pct >= thresholds.take_profit_strong:
        signals.append("take_profit:strong")
        immediate_exit = True
        strongest = strongest or f"Take profit target ({pnl_pct:.1%})"
    elif pnl_pct >= thresholds.take_profit_moderate:
        signals.append("take_profit:moderate")
        consult_ai = True
        strongest = strongest or f"Near take profit ({pnl_pct:.1%})"

    if high_watermark > entry_price:
        drop = (high_watermark - current_price) / high_watermark
        if drop >= thresholds.trailing_stop_pct:
            signals.append("trailing_stop:moderate")
            consult_ai = True
            strongest = strongest or f"Trailing stop ({drop:.1%} from high)"

    if rsi is not None:
        if rsi >= thresholds.rsi_overbought_strong:
            signals.append("rsi_overbought:strong")
            immediate_exit = True
            strongest = strongest or f"RSI overbought ({rsi:.0f})"
        elif rsi >= thresholds.rsi_overbought_moderate:
            signals.append("rsi_overbought:moderate")
            consult_ai = True
            strongest = strongest or f"RSI elevated ({rsi:.0f})"

    if entry_volume > 0 and current_volume > 0:
        vol_ratio = current_volume / entry_volume
        if vol_ratio <= thresholds.volume_collapse_strong:
            signals.append("volume_collapse:strong")
            immediate_exit = True
            strongest = strongest or f"Volume collapsed ({vol_ratio:.0%})"
        elif vol_ratio <= thresholds.volume_collapse_moderate:
            signals.append("volume_collapse:moderate")
            consult_ai = True
            strongest = strongest or f"Volume fading ({vol_ratio:.0%})"

    if macd_histogram is not None and macd_histogram < -0.5:
        signals.append("macd_bearish:moderate")
        consult_ai = True
        strongest = strongest or "MACD bearish"

    now = datetime.now(HK_TZ)
    ct = now.time()
    if time(15, 50) <= ct < time(16, 0):
        signals.append("near_close:moderate")
        consult_ai = True
        strongest = strongest or "Market closing soon — coordinator decides"
    if time(11, 50) <= ct < time(12, 0):
        signals.append("lunch_break:moderate")
        consult_ai = True
        strongest = strongest or "Lunch break approaching"

    if immediate_exit:
        recommendation = "EXIT"
    elif consult_ai:
        recommendation = "CONSULT_AI"
    else:
        recommendation = "HOLD"

    return {
        "recommendation": recommendation,
        "signals": signals,
        "strongest_signal": strongest or "No significant signals",
        "pnl_pct": pnl_pct,
    }


# ============================================================================
# BROKER INTERFACE (read-only)
# ============================================================================

class BrokerReader:
    def __init__(self):
        self.client = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from brokers.moomoo import init_moomoo_client, get_moomoo_client
            self.client = get_moomoo_client()
            if self.client is None:
                self.client = init_moomoo_client(paper_trading=True)
            if not self.client._connected:
                self.client.connect()
            self._connected = True
            logger.info("Broker connected (read-only)")
            return True
        except Exception as e:
            logger.error(f"Broker connection failed: {e}")
            return False

    def disconnect(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self._connected = False

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            return None
        try:
            return self.client.get_quote(symbol)
        except Exception as e:
            logger.error(f"Quote error for {symbol}: {e}")
            return None

    def get_technicals(self, symbol: str) -> Dict[str, Any]:
        if not self._connected:
            return {}
        try:
            from data.market import get_market_data
            md = get_market_data(self.client)
            return md.get_technicals(symbol) or {}
        except Exception as e:
            logger.warning(f"Technicals error for {symbol}: {e}")
            return {}


# ============================================================================
# MONITOR LOOP
# ============================================================================

class MonitorLoop:
    """
    Background monitoring loop. Checks open positions every CHECK_INTERVAL.
    Writes recommendations to position_monitor_status.
    NEVER executes trades or modifies positions table.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.broker = BrokerReader()
        self.anthropic_client = None
        self.thresholds = DEFAULT_THRESHOLDS
        self.check_count = 0
        self.haiku_calls_this_cycle = 0
        self.running = True

    async def _initialize(self):
        self.broker.connect()
        if ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                logger.info("Haiku client initialized")

    def _is_market_open(self) -> Tuple[bool, str]:
        now = datetime.now(HK_TZ)
        if now.weekday() >= 5:
            return False, "weekend"
        ct = now.time()
        if ct < MORNING_OPEN:
            return False, "pre_market"
        if MORNING_OPEN <= ct < MORNING_CLOSE:
            return True, "morning_session"
        if MORNING_CLOSE <= ct < AFTERNOON_OPEN:
            return False, "lunch_break"
        if AFTERNOON_OPEN <= ct < AFTERNOON_CLOSE:
            return True, "afternoon_session"
        return False, "after_hours"

    def _get_next_market_open(self) -> datetime:
        now = datetime.now(HK_TZ)
        if now.time() < MORNING_OPEN and now.weekday() < 5:
            return now.replace(hour=9, minute=30, second=0, microsecond=0)
        if MORNING_CLOSE <= now.time() < AFTERNOON_OPEN and now.weekday() < 5:
            return now.replace(hour=13, minute=0, second=0, microsecond=0)
        nxt = now + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        return nxt.replace(hour=9, minute=30, second=0, microsecond=0)

    async def _load_open_positions(self) -> List[Dict[str, Any]]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT position_id, symbol, side, quantity, entry_price,
                       stop_loss, take_profit, entry_reason, created_at,
                       high_watermark, entry_volume
                FROM positions WHERE status = 'open' ORDER BY created_at
            """)
            return [dict(r) for r in rows]

    async def _upsert_monitor_status(
        self, position_id: int, symbol: str,
        recommendation: str, reason: str,
        high_watermark: Optional[float] = None,
    ):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO position_monitor_status (
                    position_id, symbol, status, recommendation,
                    recommendation_reason, high_watermark,
                    last_check_at, checks_completed
                ) VALUES ($1, $2, 'monitoring', $3, $4, $5, NOW(), 1)
                ON CONFLICT (position_id) DO UPDATE SET
                    recommendation = $3,
                    recommendation_reason = $4,
                    high_watermark = GREATEST(
                        COALESCE(position_monitor_status.high_watermark, 0), $5
                    ),
                    last_check_at = NOW(),
                    checks_completed = position_monitor_status.checks_completed + 1,
                    status = 'monitoring',
                    metadata = CASE
                        WHEN position_monitor_status.recommendation != $3
                        THEN jsonb_set(
                            COALESCE(position_monitor_status.metadata, '{}'::jsonb),
                            '{acknowledged}', 'false'::jsonb
                        )
                        ELSE position_monitor_status.metadata
                    END,
                    updated_at = NOW()
            """, position_id, symbol, recommendation, reason, high_watermark)

    async def _update_service_health(self):
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO service_health (
                        service_name, status, last_heartbeat,
                        last_check_count, positions_monitored
                    ) VALUES ('position_monitor', 'running', NOW(), $1, $2)
                    ON CONFLICT (service_name) DO UPDATE SET
                        status = 'running', last_heartbeat = NOW(),
                        last_check_count = $1, positions_monitored = $2,
                        updated_at = NOW()
                """, self.check_count, 0)
        except Exception as e:
            logger.warning(f"Failed to update service health: {e}")

    async def _consult_haiku(self, position: Dict, signals: Dict, current_price: float) -> Dict[str, Any]:
        if not self.anthropic_client:
            return {"should_exit": False, "reason": "Haiku unavailable"}
        symbol = position["symbol"]
        entry_price = float(position["entry_price"])
        pnl_pct = signals["pnl_pct"] * 100
        sig_list = "\n".join(f"- {s}" for s in signals.get("signals", []))
        prompt = (
            f"You are monitoring an HKEX position. Quick decision needed.\n\n"
            f"POSITION:\n- Symbol: {symbol}\n- Entry: HKD {entry_price:.2f}\n"
            f"- Current: HKD {current_price:.2f}\n- P&L: {pnl_pct:+.2f}%\n"
            f"- Quantity: {position['quantity']}\n\nACTIVE SIGNALS:\n{sig_list}\n\n"
            f"ENTRY REASON: {position.get('entry_reason', 'Unknown')}\n\n"
            f"Should we EXIT or HOLD?\n"
            f"Respond with exactly one word on the first line: EXIT or HOLD\n"
            f"Then a brief reason (one sentence) on the second line."
        )
        try:
            response = self.anthropic_client.messages.create(
                model=HAIKU_MODEL, max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            self.haiku_calls_this_cycle += 1
            lines = text.split("\n")
            decision = lines[0].strip().upper()
            reason = lines[1].strip() if len(lines) > 1 else "Haiku decision"
            should_exit = decision.startswith("EXIT")
            logger.info(f"Haiku for {symbol}: {'EXIT' if should_exit else 'HOLD'} - {reason}")
            return {"should_exit": should_exit, "reason": reason}
        except Exception as e:
            logger.error(f"Haiku failed: {e}")
            return {"should_exit": False, "reason": f"Haiku error: {e}"}

    async def _check_position(self, position: Dict) -> Tuple[str, str]:
        symbol = position["symbol"]
        entry_price = float(position["entry_price"])

        quote = self.broker.get_quote(symbol)
        if not quote:
            return "HOLD", "No quote available"

        current_price = float(quote.get("last_price", 0))
        if current_price <= 0:
            return "HOLD", "Invalid price"

        technicals = self.broker.get_technicals(symbol)
        high_watermark = float(position.get("high_watermark") or entry_price)
        entry_volume = float(position.get("entry_volume") or 0)
        current_volume = float(quote.get("volume") or 0)

        if current_price > high_watermark:
            high_watermark = current_price

        signals = analyze_signals(
            entry_price=entry_price, current_price=current_price,
            high_watermark=high_watermark, entry_volume=entry_volume,
            current_volume=current_volume, rsi=technicals.get("rsi"),
            macd_histogram=technicals.get("macd_histogram"),
            thresholds=self.thresholds,
        )

        pnl_pct = signals["pnl_pct"] * 100
        logger.info(
            f"  {symbol}: HKD {current_price:.2f} ({pnl_pct:+.2f}%) "
            f"signals={len(signals['signals'])} rec={signals['recommendation']}"
        )

        recommendation = signals["recommendation"]
        reason = signals["strongest_signal"]

        if recommendation == "CONSULT_AI" and self.haiku_calls_this_cycle < MAX_HAIKU_CALLS_PER_CYCLE:
            haiku = await self._consult_haiku(position, signals, current_price)
            if haiku["should_exit"]:
                recommendation = "EXIT"
                reason = f"Haiku: {haiku['reason']}"

        await self._upsert_monitor_status(
            position_id=position["position_id"], symbol=symbol,
            recommendation=recommendation, reason=reason,
            high_watermark=high_watermark,
        )
        return recommendation, reason

    async def _run_cycle(self):
        self.check_count += 1
        self.haiku_calls_this_cycle = 0
        now = datetime.now(HK_TZ)
        logger.info("=" * 60)
        logger.info(f"Monitor Cycle #{self.check_count} - {now.strftime('%H:%M:%S %Z')}")
        logger.info("=" * 60)

        positions = await self._load_open_positions()
        if not positions:
            logger.info("No open positions to monitor")
            await self._update_service_health()
            return

        logger.info(f"Checking {len(positions)} open positions:")
        exit_count = 0
        for pos in positions:
            try:
                rec, _ = await self._check_position(pos)
                if rec == "EXIT":
                    exit_count += 1
            except Exception as e:
                logger.error(f"Error checking {pos['symbol']}: {e}")

        logger.info(f"Cycle complete: {len(positions)} positions, {exit_count} EXIT recommendations")
        await self._update_service_health()

    async def run(self):
        logger.info(f"Monitor loop starting (interval={CHECK_INTERVAL}s)")
        await self._initialize()

        while self.running:
            try:
                is_open, status = self._is_market_open()
                if is_open:
                    await self._run_cycle()
                    await asyncio.sleep(CHECK_INTERVAL)
                else:
                    nxt = self._get_next_market_open()
                    now = datetime.now(HK_TZ)
                    sleep_secs = min((nxt - now).total_seconds(), 3600)
                    sleep_secs = max(sleep_secs, 60)
                    logger.info(f"Market {status}. Next: {nxt.strftime('%H:%M')} HKT. Sleeping {sleep_secs/60:.0f} min.")
                    await asyncio.sleep(sleep_secs)
            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(60)

        self.broker.disconnect()
        logger.info("Monitor loop stopped")
