#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: position_monitor.py
Version: 1.0.0
Last Updated: 2026-04-08
Purpose: Tool agent -- monitors open positions using candle model

REVISION HISTORY:
v1.0.0 (2026-04-08) - v2.4 architecture implementation
- Loaded with current ONNX candle model
- Streams live candles for each open position
- Runs candle inference: is this still bullish?
- Exits early on pattern reversal BEFORE stop loss
- Records: "exited on AI pattern signal" with candle sequence

Description:
Tool agents are autonomous MCP tools deployed by the coordinator when
positions are open. They don't just execute commands -- they THINK
within their domain using the trained candle model.

The Position Monitor runs ONNX inference on live candles and can exit
a position early on pattern reversal. This exit data becomes high-value
training input for the next model retrain.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from shared.db import AgentDB
from shared.models import (
    Component, Direction, Severity, SignalDomain, SignalScope, ExitType,
)

logger = logging.getLogger("tool.position_monitor")


class PositionMonitorTool:
    """
    Position Monitor Tool Agent -- thinks within its domain.

    - Loaded with the current ONNX candle model
    - Streams live candles for each open position
    - Runs candle inference continuously: is this still bullish?
    - Exits early on pattern reversal -- before stop loss level is reached
    - Records exit with candle sequence that triggered it
    """

    def __init__(self, db: AgentDB, broker, onnx_session=None):
        self.db = db
        self.broker = broker
        self.onnx_session = onnx_session  # ONNX candle model session
        self.monitored_positions: Dict[str, Dict[str, Any]] = {}

    async def monitor_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        neural_prediction: Optional[str] = None,
        neural_confidence: Optional[float] = None,
    ):
        """Start monitoring a position."""
        self.monitored_positions[symbol] = {
            "side": side,
            "entry_price": entry_price,
            "neural_prediction": neural_prediction,
            "neural_confidence": neural_confidence,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "candle_history": [],
        }
        logger.info("Monitoring started: %s %s @ %.2f", side, symbol, entry_price)

    async def check_position(self, symbol: str) -> Dict[str, Any]:
        """
        Run one check cycle for a position.
        Fetches latest candles, runs inference, decides exit or hold.
        """
        position = self.monitored_positions.get(symbol)
        if not position:
            return {"action": "none", "reason": "not_monitored"}

        result = {"symbol": symbol, "action": "hold"}

        try:
            # Get latest candles from broker
            bars = self.broker.get_bars(symbol, timeframe="5m", count=20)

            if not bars:
                return {"action": "hold", "reason": "no_data"}

            # Store candle history for retraining data
            candle_dicts = [b.to_dict() for b in bars[-10:]]
            position["candle_history"] = candle_dicts

            # Run ONNX inference if model loaded
            if self.onnx_session:
                inference_result = self._run_inference(bars)
                result["inference"] = inference_result

                # Check for reversal signal
                direction = inference_result.get("direction", "neutral")
                confidence = inference_result.get("confidence", 0)
                expected = "bullish" if position["side"] == "buy" else "bearish"

                # Reversal detected: opposite direction with sufficient confidence
                opposite = "bearish" if expected == "bullish" else "bullish"
                if direction == opposite and confidence >= 0.3:
                    result["action"] = "exit"
                    result["reason"] = "pattern_reversal"
                    result["exit_type"] = ExitType.AI_PATTERN.value
                    result["reversal_confidence"] = confidence
                    result["candles_at_exit"] = json.dumps(candle_dicts)

                    logger.info(
                        "PATTERN REVERSAL detected: %s now %s (conf=%.3f) -- exiting",
                        symbol, direction, confidence,
                    )
            else:
                # No model loaded -- fall back to simple price monitoring
                current_price = bars[-1].close if bars else None
                if current_price:
                    position_return = (
                        (current_price - position["entry_price"]) / position["entry_price"]
                    )
                    if position["side"] == "sell":
                        position_return = -position_return
                    result["current_return"] = position_return

        except Exception as e:
            logger.error("Check failed for %s: %s", symbol, e)
            result["error"] = str(e)

        return result

    async def execute_exit(self, symbol: str, check_result: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an AI pattern exit and record feedback."""
        position = self.monitored_positions.get(symbol)
        if not position:
            return {"error": "position not found"}

        # Close position via broker
        close_result = self.broker.close_position(symbol)

        if "error" not in close_result:
            # Get exit price
            current_positions = self.broker.get_positions()
            exit_price = position["entry_price"]  # fallback
            for p in current_positions:
                if p["symbol"] == symbol:
                    exit_price = p["current_price"]
                    break

            return_pct = (exit_price - position["entry_price"]) / position["entry_price"]
            if position["side"] == "sell":
                return_pct = -return_pct

            # Record feedback -- this is high-value training data
            await self.db.record_trade_feedback(
                symbol=symbol,
                entry_price=position["entry_price"],
                exit_price=exit_price,
                return_pct=return_pct,
                exit_type=ExitType.AI_PATTERN.value,
                neural_prediction=position.get("neural_prediction"),
                neural_confidence=position.get("neural_confidence"),
                candles_at_exit=check_result.get("candles_at_exit"),
                exit_source=Component.TOOL_POSITION_MONITOR.value,
                entry_at=position.get("started_at"),
            )

            # Publish signal
            await self.db.publish_signal(
                severity=Severity.INFO.value,
                domain=SignalDomain.TRADING.value,
                scope=SignalScope.BROADCAST.value,
                source=Component.TOOL_POSITION_MONITOR.value,
                content=f"AI pattern exit: {symbol} return={return_pct:.2%}",
                data={
                    "symbol": symbol,
                    "exit_type": "AI_PATTERN",
                    "return_pct": return_pct,
                    "reversal_confidence": check_result.get("reversal_confidence"),
                },
            )

            # Remove from monitored
            del self.monitored_positions[symbol]

            return {
                "symbol": symbol,
                "exit_type": "AI_PATTERN",
                "return_pct": return_pct,
                "close_result": close_result,
            }

        return close_result

    def _run_inference(self, bars: list) -> Dict[str, Any]:
        """Run ONNX candle model inference on recent bars."""
        if not self.onnx_session or not bars:
            return {"direction": "neutral", "confidence": 0}

        try:
            import numpy as np

            # Prepare input: last N candles as OHLCV array
            candle_data = []
            for bar in bars[-20:]:
                candle_data.append([bar.open, bar.high, bar.low, bar.close, bar.volume])

            input_array = np.array([candle_data], dtype=np.float32)
            input_name = self.onnx_session.get_inputs()[0].name
            outputs = self.onnx_session.run(None, {input_name: input_array})

            # Parse model output (direction probabilities)
            probs = outputs[0][0] if len(outputs) > 0 else [0.33, 0.33, 0.34]
            directions = ["bullish", "bearish", "neutral"]
            max_idx = int(np.argmax(probs))

            return {
                "direction": directions[max_idx],
                "confidence": float(probs[max_idx]),
                "direction_probs": {
                    d: float(p) for d, p in zip(directions, probs)
                },
            }
        except Exception as e:
            logger.error("ONNX inference failed: %s", e)
            return {"direction": "neutral", "confidence": 0, "error": str(e)}

    def stop_monitoring(self, symbol: str):
        """Stop monitoring a position."""
        if symbol in self.monitored_positions:
            del self.monitored_positions[symbol]
            logger.info("Monitoring stopped: %s", symbol)
