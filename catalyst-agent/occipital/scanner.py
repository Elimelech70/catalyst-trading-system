#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: scanner.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Occipital lobe — pattern recognition engine

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- OccipitalScanner class with polling loop
- Candlestick and volume pattern matching
- Shape memory loading from JSON files
- Alpaca data integration for price/volume history

Description:
The occipital lobe is the brain's visual cortex. It recognises shapes
in market data — candlestick patterns, volume patterns, chart formations.
It holds its own shape memories (JSON files) and matches incoming data
against them. PFC doesn't tell it what patterns look like; it already
knows because the shapes are local memory.

Communication:
- Reads tasks from communication table (target='occipital')
- Writes results back (direction='ascending', source='occipital')
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

import aiosqlite

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import Component, MessageType, Direction

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("occipital")


class OccipitalScanner:
    """
    Pattern recognition engine — the brain's visual cortex.

    Watches communication table for scan tasks.
    Loads shape memories from local JSON files.
    Matches incoming price data against known shapes.
    Writes matched results back to communication table.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.db: Optional[AgentDB] = None
        self.shapes: Dict[str, Any] = {}
        self._running = False

    async def initialize(self):
        """Connect to agent.db and load shape memories."""
        self.db = AgentDB(self.config.agent_db_path)
        await self.db.connect()
        self._load_shapes()

        # Announce presence on the nervous system
        await self.db.send_message(
            direction=Direction.ASCENDING,
            source=Component.OCCIPITAL,
            target=None,
            msg_type=MessageType.STATUS,
            identifier="occipital_online",
            payload={"status": "online", "shapes_loaded": list(self.shapes.keys())},
        )
        logger.info("Occipital lobe online. Shapes loaded: %s", list(self.shapes.keys()))

    def _load_shapes(self):
        """Load pattern libraries from JSON files in shapes/ directory."""
        shapes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shapes")
        if not os.path.isdir(shapes_dir):
            logger.warning("Shapes directory not found: %s", shapes_dir)
            return

        for filename in os.listdir(shapes_dir):
            if filename.endswith(".json"):
                path = os.path.join(shapes_dir, filename)
                try:
                    with open(path) as f:
                        key = filename.replace(".json", "")
                        self.shapes[key] = json.load(f)
                        logger.info("Loaded shape memory: %s", key)
                except (json.JSONDecodeError, IOError) as e:
                    logger.error("Failed to load shape %s: %s", filename, e)

    async def run(self):
        """Main polling loop — watch for tasks, process, respond."""
        self._running = True
        logger.info("Occipital lobe entering polling loop (interval=%.1fs)", self.config.poll_interval)

        while self._running:
            try:
                # Check for tasks addressed to occipital
                messages = await self.db.receive_messages(
                    target=Component.OCCIPITAL,
                    msg_types=[MessageType.TASK],
                    limit=5,
                )
                for msg in messages:
                    await self._process_task(msg)

            except Exception as e:
                logger.error("Occipital loop error: %s", e, exc_info=True)

            await asyncio.sleep(self.config.poll_interval)

    async def _process_task(self, msg: Dict[str, Any]):
        """Process a task message from the communication table."""
        msg_id = msg["id"]
        identifier = msg.get("identifier", "")
        logger.info("Processing task msg_id=%d identifier=%s", msg_id, identifier)

        await self.db.update_message_status(msg_id, "processing", processed_by=Component.OCCIPITAL)

        try:
            payload = json.loads(msg["payload"]) if msg.get("payload") else {}
            result = {}

            if identifier == "scan_buy_patterns":
                result = await self._scan_buy_patterns(payload)
            elif identifier == "scan_sell_patterns":
                result = await self._scan_sell_patterns(payload)
            elif identifier == "scan_volume":
                result = self._analyze_volume(payload)
            elif identifier == "scan_all":
                result = await self._scan_all(payload)
            else:
                result = {"error": f"Unknown scan identifier: {identifier}"}
                logger.warning("Unknown identifier: %s", identifier)

            # Write result back to whoever sent the task
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.OCCIPITAL,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "result": result},
            )
            await self.db.update_message_status(msg_id, "completed", processed_by=Component.OCCIPITAL)
            logger.info("Task msg_id=%d completed", msg_id)

        except Exception as e:
            logger.error("Task msg_id=%d failed: %s", msg_id, e, exc_info=True)
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.OCCIPITAL,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "error": str(e)},
            )
            await self.db.update_message_status(msg_id, "failed", processed_by=Component.OCCIPITAL)

    async def _scan_buy_patterns(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scan symbols for buy (bullish) candlestick patterns."""
        symbols = payload.get("symbols", [])
        bars_data = payload.get("bars", {})
        matches = []

        buy_patterns = self.shapes.get("candlestick_patterns", {}).get("buy_patterns", {})

        for symbol in symbols:
            bars = bars_data.get(symbol, [])
            if len(bars) < 2:
                continue

            symbol_matches = self._match_candlestick_patterns(symbol, bars, buy_patterns)
            matches.extend(symbol_matches)

        return {
            "scan_type": "buy_patterns",
            "symbols_scanned": len(symbols),
            "matches": matches,
            "patterns_checked": list(buy_patterns.keys()),
        }

    async def _scan_sell_patterns(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Scan symbols for sell (bearish) candlestick patterns."""
        symbols = payload.get("symbols", [])
        bars_data = payload.get("bars", {})
        matches = []

        sell_patterns = self.shapes.get("candlestick_patterns", {}).get("sell_patterns", {})

        for symbol in symbols:
            bars = bars_data.get(symbol, [])
            if len(bars) < 2:
                continue

            symbol_matches = self._match_candlestick_patterns(symbol, bars, sell_patterns)
            matches.extend(symbol_matches)

        return {
            "scan_type": "sell_patterns",
            "symbols_scanned": len(symbols),
            "matches": matches,
            "patterns_checked": list(sell_patterns.keys()),
        }

    async def _scan_all(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Full scan — buy patterns + sell patterns + volume analysis."""
        buy_result = await self._scan_buy_patterns(payload)
        sell_result = await self._scan_sell_patterns(payload)
        volume_result = self._analyze_volume(payload)

        return {
            "scan_type": "full",
            "buy_matches": buy_result.get("matches", []),
            "sell_matches": sell_result.get("matches", []),
            "volume_analysis": volume_result,
        }

    def _match_candlestick_patterns(
        self,
        symbol: str,
        bars: List[Dict[str, Any]],
        patterns: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Match OHLCV bars against candlestick pattern library."""
        matches = []

        for pattern_name, pattern_def in patterns.items():
            rules = pattern_def.get("rules", {})
            candle_count = rules.get("candle_count", 2)

            if len(bars) < candle_count:
                continue

            # Check the most recent candles
            recent = bars[-candle_count:]
            matched = self._check_pattern_rules(recent, rules)

            if matched:
                matches.append({
                    "symbol": symbol,
                    "pattern": pattern_name,
                    "signal": pattern_def.get("signal", "unknown"),
                    "reliability": pattern_def.get("reliability", 0.5),
                    "description": pattern_def.get("description", ""),
                    "bar_index": len(bars) - 1,
                })

        return matches

    def _check_pattern_rules(
        self, candles: List[Dict[str, Any]], rules: Dict[str, Any]
    ) -> bool:
        """Check if candles match pattern rules."""
        if not candles:
            return False

        current = candles[-1]
        c_open = float(current.get("open", 0))
        c_high = float(current.get("high", 0))
        c_low = float(current.get("low", 0))
        c_close = float(current.get("close", 0))

        body = abs(c_close - c_open)
        total_range = c_high - c_low
        if total_range == 0:
            return False

        upper_shadow = c_high - max(c_open, c_close)
        lower_shadow = min(c_open, c_close) - c_low
        is_bullish = c_close > c_open
        is_bearish = c_close < c_open

        # Body-to-range ratio check (doji detection)
        if "body_to_range_ratio_max" in rules:
            if (body / total_range) > rules["body_to_range_ratio_max"]:
                return False

        # Lower shadow ratio check (hammer)
        if "lower_shadow_ratio_min" in rules:
            if body == 0:
                return False
            if (lower_shadow / body) < rules["lower_shadow_ratio_min"]:
                return False

        # Upper shadow ratio check (shooting star)
        if "upper_shadow_ratio_min" in rules:
            if body == 0:
                return False
            if (upper_shadow / body) < rules["upper_shadow_ratio_min"]:
                return False

        if "upper_shadow_ratio_max" in rules:
            if body > 0 and (upper_shadow / body) > rules["upper_shadow_ratio_max"]:
                return False

        if "lower_shadow_ratio_max" in rules:
            if body > 0 and (lower_shadow / body) > rules["lower_shadow_ratio_max"]:
                return False

        # Two-candle patterns (engulfing)
        if len(candles) >= 2:
            prior = candles[-2]
            p_open = float(prior.get("open", 0))
            p_close = float(prior.get("close", 0))
            p_is_bullish = p_close > p_open
            p_is_bearish = p_close < p_open

            if rules.get("prior_candle") == "bearish" and not p_is_bearish:
                return False
            if rules.get("prior_candle") == "bullish" and not p_is_bullish:
                return False
            if rules.get("current_candle") == "bullish" and not is_bullish:
                return False
            if rules.get("current_candle") == "bearish" and not is_bearish:
                return False

            if rules.get("current_open_below_prior_close") and c_open >= p_close:
                return False
            if rules.get("current_close_above_prior_open") and c_close <= p_open:
                return False
            if rules.get("current_open_above_prior_close") and c_open <= p_close:
                return False
            if rules.get("current_close_below_prior_open") and c_close >= p_open:
                return False

        # Three-candle patterns (morning/evening star)
        if rules.get("candle_count") == 3 and len(candles) >= 3:
            first = candles[-3]
            second = candles[-2]
            third = candles[-1]

            f_open = float(first.get("open", 0))
            f_close = float(first.get("close", 0))
            s_body = abs(float(second.get("close", 0)) - float(second.get("open", 0)))
            f_range = abs(f_close - f_open)

            # Small body check for second candle
            if rules.get("second_candle") == "small_body":
                if f_range > 0 and (s_body / f_range) > 0.3:
                    return False

            # Third candle midpoint check
            f_midpoint = (f_open + f_close) / 2
            if rules.get("third_closes_above_first_midpoint"):
                if c_close <= f_midpoint:
                    return False
            if rules.get("third_closes_below_first_midpoint"):
                if c_close >= f_midpoint:
                    return False

        return True

    def _analyze_volume(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volume patterns across symbols."""
        symbols = payload.get("symbols", [])
        bars_data = payload.get("bars", {})
        volume_patterns = self.shapes.get("volume_patterns", {})
        results = {}

        for symbol in symbols:
            bars = bars_data.get(symbol, [])
            if len(bars) < 5:
                continue

            volumes = [float(b.get("volume", 0)) for b in bars]
            if not volumes:
                continue

            # Calculate 20-day (or available) average
            lookback = min(20, len(volumes))
            avg_volume = sum(volumes[-lookback:]) / lookback if lookback > 0 else 0
            current_volume = volumes[-1] if volumes else 0

            if avg_volume == 0:
                continue

            ratio = current_volume / avg_volume
            detected = []

            for pattern_name, pattern_def in volume_patterns.items():
                threshold = pattern_def.get("threshold_multiplier")
                if threshold is not None:
                    if "min" in pattern_name or pattern_name in ("surge", "climax"):
                        if ratio >= threshold:
                            detected.append({
                                "pattern": pattern_name,
                                "signal": pattern_def.get("signal", ""),
                                "ratio": round(ratio, 2),
                                "reliability": pattern_def.get("reliability", 0.5),
                            })
                    elif pattern_name == "dry_up":
                        if ratio <= threshold:
                            detected.append({
                                "pattern": pattern_name,
                                "signal": pattern_def.get("signal", ""),
                                "ratio": round(ratio, 2),
                                "reliability": pattern_def.get("reliability", 0.5),
                            })

            results[symbol] = {
                "current_volume": current_volume,
                "avg_volume": round(avg_volume, 0),
                "volume_ratio": round(ratio, 2),
                "patterns_detected": detected,
            }

        return results

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self.db:
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.OCCIPITAL,
                target=None,
                msg_type=MessageType.STATUS,
                identifier="occipital_offline",
                payload={"status": "offline"},
            )
            await self.db.close()
        logger.info("Occipital lobe shutdown complete")


async def main():
    config = AgentConfig.from_env()
    scanner = OccipitalScanner(config)

    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s, shutting down...", sig)
        loop.create_task(scanner.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await scanner.initialize()
        await scanner.run()
    except asyncio.CancelledError:
        pass
    finally:
        await scanner.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
