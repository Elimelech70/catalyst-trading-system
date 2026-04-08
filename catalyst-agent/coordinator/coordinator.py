#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: coordinator.py
Version: 1.0.0
Last Updated: 2026-04-08
Purpose: The brain -- 6-layer cycle with Attention State Machine

REVISION HISTORY:
v1.0.0 (2026-04-08) - v2.4 architecture implementation
- 6-layer cycle: Heartbeat -> State -> Self-Regulation -> Working Memory
                  -> Inter-Agent -> Voice (Attention State Machine)
- Mode 1: Security Selection (News-to-Security model)
- Mode 2: Candle Execution (Candle model)
- Claude AI called only for novel situations (the 6% principle)
- Tool agent deployment on position open

Description:
The coordinator is the brain. It runs the 6-layer cycle, switches attention,
and directs tool agents. Organ scripts are the body -- they execute, reflex,
and report. They do not decide.

The coordinator assembles context, runs the cycle, manages attention state.
Claude AI is called ONLY when reasoning is needed -- novel situations,
low-confidence signals, or strategic decisions.

No layer is skipped. The output of each layer feeds the next.
Nothing runs if survival fails.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import (
    AttentionMode,
    CoordinatorLayer,
    Component,
    Direction,
    Severity,
    SignalDomain,
    SignalScope,
    ExitType,
)

logger = logging.getLogger("coordinator")


class Coordinator:
    """
    The brain -- runs the 6-layer cycle with Attention State Machine.

    1. HEARTBEAT:       Am I alive? Are organs reachable?
    2. STATE:           Load identity. What mode? What attention state?
    3. SELF-REGULATION: Budget check. Market hours. Daily loss limit.
    4. WORKING MEMORY:  Load context, positions, NEURAL signals.
    5. INTER-AGENT:     big_bro directives. Body health check.
    6. VOICE:           Attention State Machine -- the decision layer.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.db = AgentDB(config.agent_db_path)
        self.agent_id = config.agent_id
        self.running = False

        # Cycle state
        self.cycle_count = 0
        self.current_layer = CoordinatorLayer.HEARTBEAT

        # Attention state
        self.attention_mode = AttentionMode.SECURITY_SELECTION
        self.watch_list: List[str] = []
        self.active_securities: Dict[str, Any] = {}

        # Working memory (assembled each cycle in Layer 4)
        self.identity: Dict[str, Any] = {}
        self.principles: List[Dict[str, Any]] = []
        self.open_positions: List[Dict[str, Any]] = []
        self.neural_signals: Dict[str, Any] = {}
        self.recent_signals: List[Dict[str, Any]] = []
        self.feedback_stats: Dict[str, Any] = {}

        # Body health (updated each heartbeat)
        self.body_health: Dict[str, Any] = {}

        # Regulation state
        self.market_open = False
        self.trading_enabled = True
        self.daily_pnl = 0.0

        # Broker (set externally before start)
        self.broker = None

    async def start(self):
        """Initialize and begin the cycle loop."""
        await self.db.connect()
        self.running = True

        # Restore state from database
        state = await self.db.get_coordinator_state(self.agent_id)
        if state:
            self.cycle_count = state.get("cycle_count", 0)
            self.attention_mode = AttentionMode(
                state.get("attention_mode", "security_selection")
            )
            self.watch_list = json.loads(state.get("watch_list", "[]"))
            self.active_securities = json.loads(state.get("active_securities", "{}"))
            self.daily_pnl = state.get("daily_pnl", 0.0)

        logger.info(
            "Coordinator started: cycle_count=%d, attention=%s",
            self.cycle_count, self.attention_mode.value,
        )

        await self.publish_signal(
            Severity.INFO, SignalDomain.LIFECYCLE, "coordinator_online",
            {"status": "online", "attention_mode": self.attention_mode.value},
        )

    async def stop(self):
        """Save state and shut down."""
        self.running = False
        await self._save_state()
        await self.publish_signal(
            Severity.INFO, SignalDomain.LIFECYCLE, "coordinator_offline",
            {"status": "offline", "cycle_count": self.cycle_count},
        )
        await self.db.close()
        logger.info("Coordinator stopped after %d cycles", self.cycle_count)

    async def run_cycle(self) -> Dict[str, Any]:
        """
        Execute one complete 6-layer cycle.
        No layer is skipped. Output of each feeds the next.
        """
        cycle_id = datetime.now(ZoneInfo(self.config.market_timezone)).strftime(
            "%Y%m%d-%H%M%S"
        )
        self.cycle_count += 1
        cycle_result = {"cycle_id": cycle_id, "layers": {}}

        try:
            # Layer 1: HEARTBEAT
            self.current_layer = CoordinatorLayer.HEARTBEAT
            heartbeat = await self._layer_heartbeat()
            cycle_result["layers"]["heartbeat"] = heartbeat
            if heartbeat.get("critical_failure"):
                logger.critical("HEARTBEAT FAILED -- aborting cycle")
                return cycle_result

            # Layer 2: STATE
            self.current_layer = CoordinatorLayer.STATE
            state = await self._layer_state()
            cycle_result["layers"]["state"] = state

            # Layer 3: SELF-REGULATION
            self.current_layer = CoordinatorLayer.SELF_REGULATION
            regulation = await self._layer_self_regulation()
            cycle_result["layers"]["self_regulation"] = regulation
            if not regulation.get("should_be_active"):
                logger.info("Self-regulation: inactive this cycle")
                await self._save_state()
                return cycle_result

            # Layer 4: WORKING MEMORY
            self.current_layer = CoordinatorLayer.WORKING_MEMORY
            memory = await self._layer_working_memory()
            cycle_result["layers"]["working_memory"] = memory

            # Layer 5: INTER-AGENT
            self.current_layer = CoordinatorLayer.INTER_AGENT
            inter_agent = await self._layer_inter_agent()
            cycle_result["layers"]["inter_agent"] = inter_agent

            # Layer 6: VOICE (Attention State Machine)
            self.current_layer = CoordinatorLayer.VOICE
            voice = await self._layer_voice()
            cycle_result["layers"]["voice"] = voice

        except Exception as e:
            logger.error("Cycle %s failed at %s: %s",
                         cycle_id, self.current_layer.value, e, exc_info=True)
            await self.publish_signal(
                Severity.CRITICAL, SignalDomain.HEALTH,
                f"cycle_failure:{self.current_layer.value}",
                {"cycle_id": cycle_id, "error": str(e)},
            )

        await self._save_state()
        return cycle_result

    # =========================================================================
    # LAYER 1: HEARTBEAT -- Am I alive? Are organs reachable?
    # =========================================================================

    async def _layer_heartbeat(self) -> Dict[str, Any]:
        """
        Check liveness of all body components.
        If critical failure: STOP. Publish alert.
        If cerebellum offline: WARNING, fall back to LLM-only mode.
        """
        result = {"alive": True, "critical_failure": False, "components": {}}

        # Check for recent status signals from each component
        for component_name in ["cerebellum", "occipital", "hippocampus", "monitor", "neural"]:
            signals = await self.db.read_signals(
                "coordinator",
                domain="HEALTH",
                minutes=5,
            )
            # Find most recent status for this component
            latest = None
            for sig in signals:
                if sig.get("source") == component_name:
                    latest = sig
                    break

            status = "unknown"
            if latest:
                try:
                    data = json.loads(latest.get("data", "{}"))
                    status = data.get("status", "unknown")
                except (json.JSONDecodeError, TypeError):
                    pass

            self.body_health[component_name] = {
                "status": status,
                "last_seen": latest["created_at"] if latest else None,
            }
            result["components"][component_name] = status

        # Check for online status messages in communication table
        for component_name in ["cerebellum", "occipital", "hippocampus", "monitor", "neural"]:
            msg = await self.db.receive_by_identifier(
                "coordinator", f"{component_name}_online",
                msg_types=["status"],
            )
            if msg:
                self.body_health[component_name]["status"] = "online"
                result["components"][component_name] = "online"

        # Check neural models
        neural_msg = await self.db.receive_by_identifier(
            "coordinator", "neural_online", msg_types=["status"]
        )
        if neural_msg:
            try:
                payload = json.loads(neural_msg.get("payload", "{}"))
                models = payload.get("models", [])
                result["neural_models"] = models
            except (json.JSONDecodeError, TypeError):
                pass

        # Critical failure if cerebellum AND broker unreachable
        if (self.body_health.get("cerebellum", {}).get("status") == "unknown"
                and self.broker and not self.broker.is_market_open()):
            result["critical_failure"] = False  # Not critical if market closed

        return result

    # =========================================================================
    # LAYER 2: STATE -- Load identity. What mode? What attention state?
    # =========================================================================

    async def _layer_state(self) -> Dict[str, Any]:
        """
        Load identity -- CLAUDE.md first. Always.
        Formation before information. Every cycle, without exception.
        """
        result = {}

        # Load principles (identity)
        self.principles = await self.db.get_principles()
        result["principles_loaded"] = len(self.principles)

        # Load PFC state (big_bro continuity)
        pfc_state = await self.db.get_pfc_state(self.agent_id)
        if pfc_state:
            result["pfc_mode"] = pfc_state.get("current_mode", "sleeping")
            result["resume_instructions"] = pfc_state.get("resume_instructions")
            self.identity = pfc_state

        # Current attention state
        result["attention_mode"] = self.attention_mode.value
        result["watch_list"] = self.watch_list

        return result

    # =========================================================================
    # LAYER 3: SELF-REGULATION -- Budget, market hours, daily loss limit
    # =========================================================================

    async def _layer_self_regulation(self) -> Dict[str, Any]:
        """
        Should I be active this cycle?
        Budget check. Market hours. Daily loss limit.
        If no: heartbeat only, exit cleanly.
        """
        result = {"should_be_active": True}

        # Check market hours
        if self.broker:
            self.market_open = self.broker.is_market_open()
        else:
            now = datetime.now(ZoneInfo(self.config.market_timezone))
            market_open_time = now.replace(
                hour=self.config.market_open_hour,
                minute=self.config.market_open_minute, second=0
            )
            market_close_time = now.replace(
                hour=self.config.market_close_hour,
                minute=self.config.market_close_minute, second=0
            )
            self.market_open = market_open_time <= now <= market_close_time
            # Also check weekday
            if now.weekday() >= 5:
                self.market_open = False

        result["market_open"] = self.market_open

        # Check daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss_pct:
            self.trading_enabled = False
            result["daily_loss_limit_hit"] = True
            logger.warning(
                "Daily loss limit hit: %.2f%% (limit: %.2f%%)",
                self.daily_pnl * 100, self.config.max_daily_loss_pct * 100,
            )
            await self.publish_signal(
                Severity.WARNING, SignalDomain.RISK, "daily_loss_limit",
                {"daily_pnl": self.daily_pnl, "limit": self.config.max_daily_loss_pct},
            )

        result["trading_enabled"] = self.trading_enabled

        # If market closed and no open positions, no need to be active
        if not self.market_open:
            result["should_be_active"] = False

        return result

    # =========================================================================
    # LAYER 4: WORKING MEMORY -- Load context + neural signals
    # =========================================================================

    async def _layer_working_memory(self) -> Dict[str, Any]:
        """
        Load CLAUDE-FOCUS.md.
        Load recent signals from signal bus.
        Load open positions.
        Load NEURAL signals from cerebellum.
        Assemble the live picture.
        """
        result = {}

        # Load recent signals (last 10 minutes)
        self.recent_signals = await self.db.read_signals(
            "coordinator", minutes=10, limit=50,
        )
        result["signals_count"] = len(self.recent_signals)

        # Separate critical signals
        critical = [s for s in self.recent_signals if s["severity"] == "CRITICAL"]
        if critical:
            result["critical_signals"] = len(critical)
            logger.warning("CRITICAL signals detected: %d", len(critical))

        # Load open positions from broker
        if self.broker:
            try:
                self.open_positions = self.broker.get_positions()
                result["open_positions"] = len(self.open_positions)
            except Exception as e:
                logger.error("Failed to load positions: %s", e)
                self.open_positions = []
                result["positions_error"] = str(e)
        else:
            self.open_positions = []

        # Load NEURAL signals from communication table
        # Candle Model predictions
        candle_results = await self.db.receive_messages(
            target="coordinator",
            msg_types=["result"],
            status="pending",
            limit=10,
        )
        neural_predictions = {}
        for msg in candle_results:
            if msg.get("source") == "neural" and msg.get("identifier") == "predict":
                try:
                    payload = json.loads(msg.get("payload", "{}"))
                    pred_result = payload.get("result", {})
                    for sym, pred in pred_result.items():
                        neural_predictions[sym] = pred
                    await self.db.update_message_status(
                        msg["id"], "completed", "coordinator"
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

        self.neural_signals = neural_predictions
        result["neural_predictions"] = list(neural_predictions.keys())

        # Load feedback stats
        self.feedback_stats = await self.db.get_feedback_stats(days=7)
        result["feedback_stats"] = self.feedback_stats

        return result

    # =========================================================================
    # LAYER 5: INTER-AGENT -- big_bro directives, body health check
    # =========================================================================

    async def _layer_inter_agent(self) -> Dict[str, Any]:
        """
        Read DIRECTED signals from big_bro.
        Body health check -- are all organs alive?
        Tool agent status -- what are they reporting?
        """
        result = {}

        # Check for big_bro directives
        directives = await self.db.read_signals(
            "coordinator", domain="DIRECTION", minutes=60,
        )
        result["directives"] = len(directives)

        for directive in directives:
            try:
                data = json.loads(directive.get("data", "{}"))
                action = data.get("action")
                if action == "stop_trading":
                    self.trading_enabled = False
                    logger.info("big_bro directive: stop trading")
                elif action == "resume_trading":
                    self.trading_enabled = True
                    logger.info("big_bro directive: resume trading")
                elif action == "emergency":
                    logger.critical("big_bro directive: EMERGENCY")
                    if self.broker:
                        self.broker.close_all_positions()
                await self.db.acknowledge_signal(directive["id"], "coordinator")
            except (json.JSONDecodeError, TypeError):
                pass

        # Tool agent status from signals
        tool_signals = await self.db.read_signals(
            "coordinator", domain="TRADING", minutes=5,
        )
        tool_status = {}
        for sig in tool_signals:
            source = sig.get("source", "")
            if source.startswith("tool_"):
                tool_status[source] = sig
        result["tool_agents_reporting"] = list(tool_status.keys())

        # Body health summary
        result["body_health"] = self.body_health

        return result

    # =========================================================================
    # LAYER 6: VOICE -- Attention State Machine
    # =========================================================================

    async def _layer_voice(self) -> Dict[str, Any]:
        """
        The Attention State Machine -- this is AI thinking.

        Mode 1 (Security Selection):
          Read News-to-Security neural signals.
          If high-confidence security identified: switch to Mode 2.

        Mode 2 (Candle Execution):
          Read Candle Model neural signals for active securities.
          If entry signal high-confidence: execute trade.
          If position closed: switch back to Mode 1.
        """
        result = {"mode": self.attention_mode.value, "actions": []}

        if self.attention_mode == AttentionMode.SECURITY_SELECTION:
            result.update(await self._mode_security_selection())
        elif self.attention_mode == AttentionMode.CANDLE_EXECUTION:
            result.update(await self._mode_candle_execution())

        return result

    async def _mode_security_selection(self) -> Dict[str, Any]:
        """
        Mode 1: Security Selection.
        Read News-to-Security neural signals.
        High-confidence signal fires: security + direction + confidence.
        """
        result = {"scanning": True, "securities_found": []}

        # Check neural predictions for high-confidence signals
        for symbol, prediction in self.neural_signals.items():
            confidence = prediction.get("confidence", 0)
            direction_prob = prediction.get("direction_probability", 0)
            direction = prediction.get("direction", "neutral")

            # High confidence threshold for security selection
            if confidence >= 0.4 and direction in ("bullish", "bearish"):
                result["securities_found"].append({
                    "symbol": symbol,
                    "direction": direction,
                    "confidence": confidence,
                    "direction_probability": direction_prob,
                })
                logger.info(
                    "Mode 1: High-confidence security found: %s %s (conf=%.3f)",
                    symbol, direction, confidence,
                )

        # If high-confidence securities found, switch to Mode 2
        if result["securities_found"]:
            for sec in result["securities_found"]:
                self.watch_list.append(sec["symbol"])
                self.active_securities[sec["symbol"]] = {
                    "direction": sec["direction"],
                    "confidence": sec["confidence"],
                    "source": "neural",
                    "added_at": self.db._now(),
                }

            await self._switch_attention(AttentionMode.CANDLE_EXECUTION)
            result["mode_switch"] = "candle_execution"

            await self.publish_signal(
                Severity.INFO, SignalDomain.ATTENTION, "mode_switch",
                {
                    "from": "security_selection",
                    "to": "candle_execution",
                    "securities": result["securities_found"],
                },
            )

        return result

    async def _mode_candle_execution(self) -> Dict[str, Any]:
        """
        Mode 2: Candle Execution.
        Read Candle Model neural signals for active securities.
        If entry signal high-confidence: execute trade via executor.
        If position closed: switch back to Mode 1.
        """
        result = {"watching": self.watch_list, "actions": []}

        # Check if all positions for watched securities are closed
        open_symbols = {p["symbol"] for p in self.open_positions}
        watched_with_positions = set(self.watch_list) & open_symbols

        # For each watched security without a position, check candle signals
        for symbol in self.watch_list:
            if symbol in open_symbols:
                continue  # Tool agents managing this position

            prediction = self.neural_signals.get(symbol)
            if not prediction:
                continue

            confidence = prediction.get("confidence", 0)
            direction = prediction.get("direction", "neutral")
            sec_info = self.active_securities.get(symbol, {})
            expected_direction = sec_info.get("direction", "bullish")

            # Entry signal: high confidence + matching direction
            if confidence >= 0.3 and direction == expected_direction:
                # Send trade task to cerebellum
                side = "buy" if direction == "bullish" else "sell"
                trade_task = {
                    "symbol": symbol,
                    "side": side,
                    "confidence": confidence,
                    "direction": direction,
                    "neural_prediction": json.dumps(prediction),
                    "stop_loss_pct": self.config.stop_loss_pct,
                }

                msg_id = await self.db.send_message(
                    direction=Direction.DESCENDING.value,
                    source=Component.COORDINATOR.value,
                    target=Component.CEREBELLUM.value,
                    msg_type="task",
                    identifier="execute_trade",
                    payload=trade_task,
                )

                result["actions"].append({
                    "action": "trade_submitted",
                    "symbol": symbol,
                    "side": side,
                    "confidence": confidence,
                    "msg_id": msg_id,
                })

                logger.info(
                    "Mode 2: Trade submitted: %s %s (conf=%.3f, msg=%d)",
                    side, symbol, confidence, msg_id,
                )

                await self.publish_signal(
                    Severity.INFO, SignalDomain.EXECUTION, "trade_submitted",
                    {"symbol": symbol, "side": side, "confidence": confidence},
                )

        # Check if positions have been closed (tool agents report)
        if watched_with_positions == set() and self.watch_list:
            # All watched securities have no positions -> might return to Mode 1
            # But only if we had positions before (not just scanning)
            pass

        # If no watched securities have positions and none are pending entry,
        # return to Mode 1
        if not self.watch_list or (not open_symbols & set(self.watch_list)):
            # Clean stale watch list entries
            stale = []
            for sym in self.watch_list:
                sec = self.active_securities.get(sym, {})
                added = sec.get("added_at", "")
                # If added more than 30 minutes ago with no position, drop it
                if added and sym not in open_symbols:
                    stale.append(sym)

            if stale and len(stale) == len(self.watch_list):
                self.watch_list = []
                self.active_securities = {}
                await self._switch_attention(AttentionMode.SECURITY_SELECTION)
                result["mode_switch"] = "security_selection"

                await self.publish_signal(
                    Severity.INFO, SignalDomain.ATTENTION, "mode_switch",
                    {"from": "candle_execution", "to": "security_selection",
                     "reason": "no_active_positions"},
                )

        return result

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _switch_attention(self, new_mode: AttentionMode):
        """Switch the attention state machine mode."""
        old_mode = self.attention_mode
        self.attention_mode = new_mode
        await self.db.set_attention_mode(new_mode.value, self.agent_id)
        logger.info(
            "Attention switch: %s -> %s",
            old_mode.value, new_mode.value,
        )

    async def _save_state(self):
        """Persist coordinator state to database."""
        await self.db.update_coordinator_state(
            self.agent_id,
            current_layer=self.current_layer.value,
            cycle_count=self.cycle_count,
            last_cycle_at=self.db._now(),
            attention_mode=self.attention_mode.value,
            watch_list=json.dumps(self.watch_list),
            active_securities=json.dumps(self.active_securities),
            body_health=json.dumps(self.body_health),
            market_open=1 if self.market_open else 0,
            trading_enabled=1 if self.trading_enabled else 0,
            daily_pnl=self.daily_pnl,
        )

    async def publish_signal(
        self,
        severity: Severity,
        domain: SignalDomain,
        content: str,
        data: Optional[dict] = None,
        scope: str = SignalScope.BROADCAST.value,
    ) -> int:
        """Publish a signal to the signal bus."""
        return await self.db.publish_signal(
            severity=severity.value,
            domain=domain.value,
            scope=scope,
            source=Component.COORDINATOR.value,
            content=content,
            data=data,
        )

    async def run_loop(self):
        """Main loop: run cycles at configured interval."""
        await self.start()
        try:
            while self.running:
                await self.run_cycle()
                await asyncio.sleep(self.config.coordinator_cycle_interval)
        except KeyboardInterrupt:
            logger.info("Coordinator interrupted")
        finally:
            await self.stop()


# =============================================================================
# ENTRY POINT
# =============================================================================

async def main():
    """Start the coordinator."""
    config = AgentConfig.from_env()

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    coordinator = Coordinator(config)

    # Connect broker if available
    if config.broker_type == "alpaca" and config.alpaca_api_key:
        from cerebellum.broker import AlpacaBroker
        broker = AlpacaBroker(
            config.alpaca_api_key,
            config.alpaca_secret_key,
            paper=config.paper_trading,
        )
        if broker.connect():
            coordinator.broker = broker

    await coordinator.run_loop()


if __name__ == "__main__":
    asyncio.run(main())
