#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: monitor.py
Version: 1.0.0
Last Updated: 2026-04-06
Purpose: Position Monitor — proprioceptive organ (internal eyes)

REVISION HISTORY:
v1.0.0 (2026-04-06) - Initial creation — v8 architecture alignment
- P&L tracking via Alpaca positions
- Stop-loss trigger reflex (CRITICAL:RISK broadcast)
- Risk exposure broadcast (WARNING:RISK)
- Near-market-close flag (WARNING:TRADING)
- Exit signal detection

Description:
The monitor is proprioception — the brain's sense of its own body.
It continuously tracks open positions, P&L, and risk exposure.
It does NOT decide strategy. It feels pain and reports it.

Reflexes (no AI compute needed — firmware):
- Stop-loss trigger: position unrealized loss exceeds threshold → CRITICAL:RISK
- Risk exposure: total exposure exceeds limit → WARNING:RISK
- Near close: market closing soon with open positions → WARNING:TRADING
- Fill tracking: positions changed → INFO:TRADING

Communication:
- Reads positions from Alpaca via broker
- Publishes signals to the signal bus (severity × domain × scope)
- Reads tasks from communication table (target='monitor')
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import (
    Component, MessageType, Direction,
    Severity, SignalDomain, SignalScope,
)

# Import broker from cerebellum
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cerebellum"))
from broker import AlpacaBroker

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("monitor")

# Thresholds
STOP_LOSS_THRESHOLD = -0.03       # -3% unrealized P&L triggers CRITICAL
RISK_EXPOSURE_LIMIT = 0.25        # 25% total exposure triggers WARNING
NEAR_CLOSE_MINUTES = 15           # 15 min before close triggers WARNING
MONITOR_INTERVAL = 30.0           # Check every 30 seconds


class PositionMonitor:
    """
    Proprioceptive organ — the brain's sense of its own body state.

    Tracks positions, P&L, risk. Publishes reflexive signals.
    Does NOT decide strategy. Feels pain and reports it.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.db: Optional[AgentDB] = None
        self.broker: Optional[AlpacaBroker] = None
        self._running = False
        self._last_positions: Dict[str, Dict] = {}
        self._near_close_warned = False

    async def initialize(self):
        """Connect to agent.db, initialize broker."""
        self.db = AgentDB(self.config.agent_db_path)
        await self.db.connect()

        self.broker = AlpacaBroker(
            api_key=self.config.alpaca_api_key,
            secret_key=self.config.alpaca_secret_key,
            paper=self.config.paper_trading,
        )
        if self.config.alpaca_api_key:
            self.broker.connect()
        else:
            logger.warning("No Alpaca API key — broker disabled")

        # Announce presence on the nervous system
        await self.db.send_message(
            direction=Direction.ASCENDING,
            source=Component.MONITOR,
            target=None,
            msg_type=MessageType.STATUS,
            identifier="monitor_online",
            payload={"status": "online"},
        )
        logger.info("Position Monitor online (proprioception active)")

    async def run(self):
        """Main monitoring loop — continuous proprioceptive sensing."""
        self._running = True
        logger.info("Monitor entering proprioceptive loop (interval=%.0fs)", MONITOR_INTERVAL)

        while self._running:
            try:
                # Process any direct tasks from PFC
                tasks = await self.db.receive_messages(
                    target=Component.MONITOR,
                    msg_types=[MessageType.TASK],
                    limit=5,
                )
                for task in tasks:
                    await self._process_task(task)

                # Core proprioceptive cycle
                if self.broker and self.broker.trading_client:
                    await self._proprioceptive_cycle()

            except Exception as e:
                logger.error("Monitor loop error: %s", e, exc_info=True)
                await self._publish_signal(
                    Severity.CRITICAL, SignalDomain.HEALTH, SignalScope.BROADCAST,
                    f"Monitor loop error: {str(e)[:200]}",
                    data={"error_type": type(e).__name__},
                )

            await asyncio.sleep(MONITOR_INTERVAL)

    async def _proprioceptive_cycle(self):
        """One proprioceptive sensing cycle — feel the body state."""
        try:
            positions = self.broker.get_positions()
            account = self.broker.get_account()
        except Exception as e:
            await self._publish_signal(
                Severity.CRITICAL, SignalDomain.HEALTH, SignalScope.BROADCAST,
                f"Monitor cannot reach broker: {str(e)[:200]}",
            )
            return

        equity = account.get("equity", 0)

        # 1. Check each position for stop-loss trigger
        for pos in positions:
            symbol = pos.get("symbol", "?")
            unrealized_plpc = pos.get("unrealized_plpc", 0)

            # REFLEX: Stop-loss trigger — position bleeding
            if unrealized_plpc <= STOP_LOSS_THRESHOLD:
                await self._publish_signal(
                    Severity.CRITICAL, SignalDomain.RISK, SignalScope.BROADCAST,
                    f"Stop-loss trigger: {symbol} at {unrealized_plpc:.1%} "
                    f"(threshold {STOP_LOSS_THRESHOLD:.1%})",
                    data={
                        "symbol": symbol,
                        "unrealized_plpc": unrealized_plpc,
                        "unrealized_pl": pos.get("unrealized_pl", 0),
                        "current_price": pos.get("current_price", 0),
                        "avg_entry_price": pos.get("avg_entry_price", 0),
                    },
                )

        # 2. Check total risk exposure
        total_exposure = sum(abs(p.get("market_value", 0)) for p in positions)
        exposure_ratio = total_exposure / equity if equity > 0 else 0

        if exposure_ratio > RISK_EXPOSURE_LIMIT:
            await self._publish_signal(
                Severity.WARNING, SignalDomain.RISK, SignalScope.BROADCAST,
                f"Risk exposure {exposure_ratio:.1%} exceeds limit {RISK_EXPOSURE_LIMIT:.1%}",
                data={
                    "exposure_ratio": round(exposure_ratio, 4),
                    "total_exposure": round(total_exposure, 2),
                    "equity": round(equity, 2),
                    "position_count": len(positions),
                },
            )

        # 3. Track position changes (fills, closes)
        current_symbols = {p["symbol"] for p in positions}
        last_symbols = set(self._last_positions.keys())

        # New positions = fills
        for symbol in current_symbols - last_symbols:
            pos = next(p for p in positions if p["symbol"] == symbol)
            await self._publish_signal(
                Severity.INFO, SignalDomain.TRADING, SignalScope.BROADCAST,
                f"New position: {pos.get('qty')} {symbol} @ {pos.get('avg_entry_price')}",
                data=pos,
            )

        # Closed positions
        for symbol in last_symbols - current_symbols:
            old_pos = self._last_positions[symbol]
            await self._publish_signal(
                Severity.INFO, SignalDomain.TRADING, SignalScope.BROADCAST,
                f"Position closed: {symbol} (was {old_pos.get('unrealized_plpc', 0):.1%})",
                data=old_pos,
            )

        self._last_positions = {p["symbol"]: p for p in positions}

        # 4. Near-market-close check
        await self._check_near_close(positions)

        # 5. Publish periodic portfolio summary
        total_unrealized = sum(p.get("unrealized_pl", 0) for p in positions)
        await self.db.send_message(
            direction=Direction.ASCENDING,
            source=Component.MONITOR,
            target=None,
            msg_type=MessageType.STATUS,
            identifier="portfolio_snapshot",
            payload={
                "position_count": len(positions),
                "total_unrealized_pl": round(total_unrealized, 2),
                "exposure_ratio": round(exposure_ratio, 4),
                "equity": round(equity, 2),
                "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
            },
        )

    async def _check_near_close(self, positions: List[Dict]):
        """REFLEX: Warn when market is about to close with open positions."""
        if not positions:
            self._near_close_warned = False
            return

        now_et = datetime.now(ZoneInfo("America/New_York"))
        # US market closes at 16:00 ET
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        minutes_to_close = (market_close - now_et).total_seconds() / 60

        if 0 < minutes_to_close <= NEAR_CLOSE_MINUTES and not self._near_close_warned:
            self._near_close_warned = True
            await self._publish_signal(
                Severity.WARNING, SignalDomain.TRADING, SignalScope.BROADCAST,
                f"Near market close: {minutes_to_close:.0f} min remaining "
                f"with {len(positions)} open position(s)",
                data={
                    "minutes_to_close": round(minutes_to_close),
                    "open_positions": len(positions),
                    "symbols": [p["symbol"] for p in positions],
                },
            )
        elif minutes_to_close > NEAR_CLOSE_MINUTES:
            self._near_close_warned = False

    async def _process_task(self, msg: Dict[str, Any]):
        """Handle tasks from PFC (e.g. get_portfolio_status)."""
        msg_id = msg["id"]
        identifier = msg.get("identifier", "")
        logger.info("Processing task msg_id=%d identifier=%s", msg_id, identifier)

        await self.db.update_message_status(msg_id, "processing", processed_by=Component.MONITOR)

        try:
            payload = json.loads(msg["payload"]) if msg.get("payload") else {}
            result = {}

            if identifier == "get_portfolio_status":
                result = self._get_portfolio_status()
            elif identifier == "get_position_detail":
                result = self._get_position_detail(payload.get("symbol", ""))
            else:
                result = {"error": f"Unknown task: {identifier}"}

            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.MONITOR,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "result": result},
            )
            await self.db.update_message_status(msg_id, "completed", processed_by=Component.MONITOR)

        except Exception as e:
            logger.error("Task msg_id=%d failed: %s", msg_id, e, exc_info=True)
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.MONITOR,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "error": str(e)},
            )
            await self.db.update_message_status(msg_id, "failed", processed_by=Component.MONITOR)

    def _get_portfolio_status(self) -> Dict[str, Any]:
        """Get full portfolio status for PFC."""
        if not self.broker or not self.broker.trading_client:
            return {"error": "Broker not connected"}

        positions = self.broker.get_positions()
        account = self.broker.get_account()
        equity = account.get("equity", 0)
        total_exposure = sum(abs(p.get("market_value", 0)) for p in positions)

        return {
            "account": account,
            "positions": positions,
            "exposure_ratio": round(total_exposure / equity, 4) if equity > 0 else 0,
            "total_unrealized_pl": round(sum(p.get("unrealized_pl", 0) for p in positions), 2),
        }

    def _get_position_detail(self, symbol: str) -> Dict[str, Any]:
        """Get detail for a specific position."""
        if not self.broker or not self.broker.trading_client:
            return {"error": "Broker not connected"}

        for pos in self.broker.get_positions():
            if pos["symbol"] == symbol:
                return pos
        return {"error": f"No position found for {symbol}"}

    async def _publish_signal(
        self, severity: str, domain: str, scope: str,
        content: str, data: dict = None,
    ):
        """Publish a signal to the signal bus."""
        try:
            await self.db.publish_signal(
                severity=severity,
                domain=domain,
                scope=scope,
                source=Component.MONITOR,
                content=content,
                data=data,
            )
            logger.info("Signal: %s:%s — %s", severity, domain, content[:100])
        except Exception as e:
            logger.error("Failed to publish signal: %s", e)

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self.broker:
            self.broker.disconnect()
        if self.db:
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.MONITOR,
                target=None,
                msg_type=MessageType.STATUS,
                identifier="monitor_offline",
                payload={"status": "offline"},
            )
            await self.db.close()
        logger.info("Position Monitor shutdown complete")


async def main():
    config = AgentConfig.from_env()
    monitor = PositionMonitor(config)

    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s, shutting down...", sig)
        loop.create_task(monitor.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await monitor.initialize()
        await monitor.run()
    except asyncio.CancelledError:
        pass
    finally:
        await monitor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
