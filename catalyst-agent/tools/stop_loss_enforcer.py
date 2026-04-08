#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: stop_loss_enforcer.py
Version: 1.0.0
Last Updated: 2026-04-08
Purpose: Tool agent -- hard floor stop loss enforcement

REVISION HISTORY:
v1.0.0 (2026-04-08) - v2.4 architecture implementation
- Hard floor: always active regardless of AI model state
- Brute-force exit if pattern detection fails or model is offline
- Records: "exited on stop loss, AI pattern missed"
- THIS RECORDING IS THE MOST IMPORTANT SIGNAL IN THE SYSTEM

Description:
The Stop Loss Enforcer is the hard floor. It does not think -- it enforces.
If price hits the stop level, the position is closed. Period.

Every stop loss exit is a signal that the Position Monitor tool failed.
The candle model missed the reversal. This triggers the improvement cycle:
what candle sequence preceded this? Why didn't the model fire?

Principle p001: Every position must have a stop loss. No exceptions.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from shared.db import AgentDB
from shared.models import (
    Component, Severity, SignalDomain, SignalScope, ExitType,
)

logger = logging.getLogger("tool.stop_loss")


class StopLossEnforcerTool:
    """
    Stop Loss Enforcer Tool Agent -- the hard floor.

    - Always active regardless of AI model state
    - Brute-force exit if price hits stop level
    - Records "exited on stop loss" -- triggers model improvement cycle
    - This is the most important signal in the system
    """

    def __init__(self, db: AgentDB, broker):
        self.db = db
        self.broker = broker
        self.stop_levels: Dict[str, Dict[str, Any]] = {}

    def set_stop(
        self,
        symbol: str,
        stop_price: float,
        entry_price: float,
        side: str = "buy",
        neural_prediction: Optional[str] = None,
        neural_confidence: Optional[float] = None,
    ):
        """Set a stop loss level for a position."""
        self.stop_levels[symbol] = {
            "stop_price": stop_price,
            "entry_price": entry_price,
            "side": side,
            "neural_prediction": neural_prediction,
            "neural_confidence": neural_confidence,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Stop loss set: %s %s stop=%.2f entry=%.2f",
            side, symbol, stop_price, entry_price,
        )

    async def check_stops(self) -> List[Dict[str, Any]]:
        """
        Check all stop levels against current prices.
        Returns list of triggered stops.
        """
        triggered = []

        if not self.stop_levels:
            return triggered

        try:
            positions = self.broker.get_positions()
        except Exception as e:
            logger.error("Failed to get positions for stop check: %s", e)
            return triggered

        position_map = {p["symbol"]: p for p in positions}

        for symbol, stop_info in list(self.stop_levels.items()):
            pos = position_map.get(symbol)
            if not pos:
                # Position already closed (by Position Monitor or manually)
                del self.stop_levels[symbol]
                continue

            current_price = pos.get("current_price", 0)
            stop_price = stop_info["stop_price"]
            side = stop_info["side"]

            # Check if stop is hit
            stop_hit = False
            if side == "buy" and current_price <= stop_price:
                stop_hit = True
            elif side == "sell" and current_price >= stop_price:
                stop_hit = True

            if stop_hit:
                logger.warning(
                    "STOP LOSS HIT: %s current=%.2f stop=%.2f -- ENFORCING EXIT",
                    symbol, current_price, stop_price,
                )
                result = await self._enforce_exit(symbol, current_price, stop_info)
                triggered.append(result)

        return triggered

    async def _enforce_exit(
        self, symbol: str, current_price: float, stop_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enforce stop loss exit. No hesitation. No exceptions.
        """
        # Close position
        close_result = self.broker.close_position(symbol)

        entry_price = stop_info["entry_price"]
        return_pct = (current_price - entry_price) / entry_price
        if stop_info["side"] == "sell":
            return_pct = -return_pct

        # Get recent candles for retraining data
        candles_at_exit = None
        try:
            bars = self.broker.get_bars(symbol, timeframe="5m", count=10)
            if bars:
                candles_at_exit = json.dumps([b.to_dict() for b in bars])
        except Exception:
            pass

        # Record feedback -- THIS IS THE MOST IMPORTANT SIGNAL
        await self.db.record_trade_feedback(
            symbol=symbol,
            entry_price=entry_price,
            exit_price=current_price,
            return_pct=return_pct,
            exit_type=ExitType.STOP_LOSS.value,
            neural_prediction=stop_info.get("neural_prediction"),
            neural_confidence=stop_info.get("neural_confidence"),
            candles_at_exit=candles_at_exit,
            exit_source=Component.TOOL_STOP_LOSS.value,
            entry_at=stop_info.get("set_at"),
        )

        # Publish CRITICAL signal -- Position Monitor failed
        await self.db.publish_signal(
            severity=Severity.WARNING.value,
            domain=SignalDomain.TRADING.value,
            scope=SignalScope.BROADCAST.value,
            source=Component.TOOL_STOP_LOSS.value,
            content=f"STOP LOSS EXIT: {symbol} return={return_pct:.2%} -- AI pattern missed",
            data={
                "symbol": symbol,
                "exit_type": "STOP_LOSS",
                "return_pct": return_pct,
                "entry_price": entry_price,
                "exit_price": current_price,
                "stop_price": stop_info["stop_price"],
                "candles_at_exit": candles_at_exit,
                "flag": "Position Monitor tool needs improvement",
            },
        )

        # Clean up
        del self.stop_levels[symbol]

        return {
            "symbol": symbol,
            "exit_type": "STOP_LOSS",
            "return_pct": return_pct,
            "entry_price": entry_price,
            "exit_price": current_price,
            "close_result": close_result,
        }

    def remove_stop(self, symbol: str):
        """Remove a stop level (position closed by other means)."""
        if symbol in self.stop_levels:
            del self.stop_levels[symbol]
            logger.info("Stop removed: %s", symbol)
