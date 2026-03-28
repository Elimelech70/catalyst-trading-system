#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: executor.py
Version: 1.0.0
Last Updated: 2026-03-03
Purpose: Cerebellum — procedure execution engine

REVISION HISTORY:
v1.0.0 (2026-03-03) - Initial creation
- CerebellumExecutor class with polling loop
- Procedure loading and step-by-step execution
- Occipital lobe orchestration via communication table
- Risk checking and order execution via Alpaca
- Correlation ID based async result waiting

Description:
The cerebellum is the brain's learned behaviours. It knows HOW to execute
what the PFC intends. PFC says "find securities to buy", cerebellum runs
the procedure: scan → filter → risk check → execute.

It orchestrates the occipital lobe (sends scan tasks, waits for results)
and interfaces with the Alpaca API for trade execution.

Communication:
- Reads tasks from communication table (target='cerebellum')
- Sends sub-tasks to occipital (direction='descending')
- Writes results back to PFC (direction='ascending')
"""

import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

# Add parent to path for shared module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AgentConfig
from shared.db import AgentDB
from shared.models import Component, MessageType, Direction

from broker import AlpacaBroker

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cerebellum")


class CerebellumExecutor:
    """
    Procedure execution engine — the brain's learned behaviours.

    Reads tasks from PFC via communication table.
    Orchestrates occipital lobe for pattern scanning.
    Runs risk checks and executes trades via Alpaca.
    Reports results back to PFC.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.db: Optional[AgentDB] = None
        self.broker: Optional[AlpacaBroker] = None
        self.procedures: Dict[str, Any] = {}
        self._running = False

    async def initialize(self):
        """Connect to agent.db, initialize broker, load procedures."""
        self.db = AgentDB(self.config.agent_db_path)
        await self.db.connect()

        # Initialize Alpaca broker
        self.broker = AlpacaBroker(
            api_key=self.config.alpaca_api_key,
            secret_key=self.config.alpaca_secret_key,
            paper=self.config.paper_trading,
        )
        if self.config.alpaca_api_key:
            self.broker.connect()
        else:
            logger.warning("No Alpaca API key — broker disabled")

        self._load_procedures()

        # Announce presence
        await self.db.send_message(
            direction=Direction.ASCENDING,
            source=Component.CEREBELLUM,
            target=None,
            msg_type=MessageType.STATUS,
            identifier="cerebellum_online",
            payload={
                "status": "online",
                "procedures_loaded": list(self.procedures.keys()),
                "broker_connected": self.broker.trading_client is not None,
            },
        )
        logger.info(
            "Cerebellum online. Procedures: %s, Broker: %s",
            list(self.procedures.keys()),
            "connected" if self.broker.trading_client else "disabled",
        )

    def _load_procedures(self):
        """Load procedure JSONs from procedures/ directory."""
        proc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "procedures")
        if not os.path.isdir(proc_dir):
            logger.warning("Procedures directory not found: %s", proc_dir)
            return

        for filename in os.listdir(proc_dir):
            if filename.endswith(".json"):
                path = os.path.join(proc_dir, filename)
                try:
                    with open(path) as f:
                        proc = json.load(f)
                        name = proc.get("name", filename.replace(".json", ""))
                        self.procedures[name] = proc
                        logger.info("Loaded procedure: %s", name)
                except (json.JSONDecodeError, IOError) as e:
                    logger.error("Failed to load procedure %s: %s", filename, e)

    async def run(self):
        """Main polling loop — watch for tasks from PFC."""
        self._running = True
        logger.info("Cerebellum entering polling loop (interval=%.1fs)", self.config.poll_interval)

        while self._running:
            try:
                messages = await self.db.receive_messages(
                    target=Component.CEREBELLUM,
                    msg_types=[MessageType.TASK],
                    limit=5,
                )
                for msg in messages:
                    await self._process_task(msg)

            except Exception as e:
                logger.error("Cerebellum loop error: %s", e, exc_info=True)

            await asyncio.sleep(self.config.poll_interval)

    async def _process_task(self, msg: Dict[str, Any]):
        """Route a task to the appropriate handler."""
        msg_id = msg["id"]
        identifier = msg.get("identifier", "")
        logger.info("Processing task msg_id=%d identifier=%s", msg_id, identifier)

        await self.db.update_message_status(msg_id, "processing", processed_by=Component.CEREBELLUM)

        try:
            payload = json.loads(msg["payload"]) if msg.get("payload") else {}
            result = {}

            if identifier == "find_securities_to_buy":
                result = await self._execute_procedure("find_securities_to_buy", payload)
            elif identifier == "execute_procedure":
                proc_name = payload.get("procedure_name", "")
                result = await self._execute_procedure(proc_name, payload)
            elif identifier == "place_order":
                result = self._place_order(payload)
            elif identifier == "close_position":
                result = self._close_position(payload)
            elif identifier == "get_portfolio":
                result = self._get_portfolio()
            elif identifier == "get_account":
                result = self._get_account()
            elif identifier == "run_risk_check":
                result = self._run_risk_check(payload)
            elif identifier == "get_bars":
                result = self._get_bars(payload)
            else:
                result = {"error": f"Unknown task identifier: {identifier}"}
                logger.warning("Unknown identifier: %s", identifier)

            # Write result back to sender
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.CEREBELLUM,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "result": result},
            )
            await self.db.update_message_status(msg_id, "completed", processed_by=Component.CEREBELLUM)
            logger.info("Task msg_id=%d completed", msg_id)

        except Exception as e:
            logger.error("Task msg_id=%d failed: %s", msg_id, e, exc_info=True)
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.CEREBELLUM,
                target=msg["source"],
                msg_type=MessageType.RESULT,
                identifier=identifier,
                payload={"request_id": msg_id, "error": str(e)},
            )
            await self.db.update_message_status(msg_id, "failed", processed_by=Component.CEREBELLUM)

    async def _execute_procedure(self, proc_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a named procedure step-by-step."""
        procedure = self.procedures.get(proc_name)
        if not procedure:
            return {"error": f"Unknown procedure: {proc_name}"}

        logger.info("Executing procedure: %s (%d steps)", proc_name, len(procedure.get("steps", [])))
        step_results = {}

        for step in procedure.get("steps", []):
            step_name = step.get("name", f"step_{step.get('step', '?')}")
            step_type = step.get("type", "")
            logger.info("  Step %s: %s — %s", step.get("step"), step_name, step.get("description", ""))

            try:
                if step_type == "occipital_scan":
                    step_results[step_name] = await self._occipital_scan_step(step, inputs)
                elif step_type == "internal":
                    step_results[step_name] = self._internal_filter_step(step, step_results, inputs)
                elif step_type == "risk_check":
                    step_results[step_name] = self._run_risk_check({**inputs, **step})
                elif step_type == "broker_call":
                    step_results[step_name] = self._broker_step(step, step_results, inputs)
                else:
                    step_results[step_name] = {"skipped": f"Unknown step type: {step_type}"}

            except Exception as e:
                logger.error("Step %s failed: %s", step_name, e, exc_info=True)
                step_results[step_name] = {"error": str(e)}

                # Check escalation conditions
                if self._should_escalate(step, e, step_results):
                    await self._escalate(proc_name, step_name, str(e))
                    break

        return {"procedure": proc_name, "steps": step_results}

    async def _occipital_scan_step(self, step: Dict, inputs: Dict) -> Dict[str, Any]:
        """Send a scan task to the occipital lobe and wait for results."""
        identifier = step.get("identifier", "scan_buy_patterns")
        timeout = step.get("timeout", 30)

        # Get bars data for the symbols if we have broker access
        symbols = inputs.get("symbols", [])
        bars_data = {}
        if self.broker and self.broker.data_client and symbols:
            for symbol in symbols[:20]:  # Cap at 20 symbols
                try:
                    bars_data[symbol] = self.broker.get_bars(symbol, days=20)
                except Exception as e:
                    logger.warning("Failed to get bars for %s: %s", symbol, e)

        # Build the correlation identifier
        correlation_id = f"cerebellum-{uuid.uuid4().hex[:8]}"

        # Send task to occipital
        await self.db.send_message(
            direction=Direction.DESCENDING,
            source=Component.CEREBELLUM,
            target=Component.OCCIPITAL,
            msg_type=MessageType.TASK,
            identifier=identifier,
            payload={
                "symbols": symbols,
                "bars": bars_data,
                "correlation_id": correlation_id,
            },
        )
        logger.info("Sent scan task to occipital: %s (correlation=%s)", identifier, correlation_id)

        # Wait for result
        return await self._wait_for_result(
            Component.CEREBELLUM, identifier, timeout=timeout
        )

    async def _wait_for_result(
        self, target: str, identifier: str, timeout: float = 30
    ) -> Dict[str, Any]:
        """Poll communication table for a result matching our request."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            msg = await self.db.receive_by_identifier(
                target=target,
                identifier=identifier,
                msg_types=[MessageType.RESULT],
            )
            if msg:
                await self.db.update_message_status(msg["id"], "completed", processed_by=Component.CEREBELLUM)
                payload = json.loads(msg["payload"]) if msg.get("payload") else {}
                return payload.get("result", payload)

            await asyncio.sleep(0.5)

        logger.warning("Timeout waiting for result: identifier=%s", identifier)
        return {"error": "Timeout waiting for result", "identifier": identifier}

    def _internal_filter_step(
        self, step: Dict, prior_results: Dict, inputs: Dict
    ) -> Dict[str, Any]:
        """Internal filtering step (volume filter, etc.)."""
        criteria = step.get("criteria", "")
        min_volume_ratio = step.get("min_volume_ratio", 1.5)

        # Get scan results from prior step
        scan_result = prior_results.get("request_scan", {})
        matches = scan_result.get("result", {}).get("matches", [])

        if criteria == "volume_surge":
            # Filter by volume ratio from occipital's volume analysis
            filtered = [m for m in matches if m.get("reliability", 0) >= 0.6]
            return {
                "input_count": len(matches),
                "filtered_count": len(filtered),
                "candidates": filtered,
            }

        return {"candidates": matches, "filter": "passthrough"}

    def _run_risk_check(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate proposed trade against risk rules."""
        max_risk = data.get("max_risk_per_trade", 0.02)
        max_exposure = data.get("max_total_exposure", 0.10)

        if not self.broker or not self.broker.trading_client:
            return {"passed": False, "reason": "Broker not connected"}

        try:
            account = self.broker.get_account()
            positions = self.broker.get_positions()
            equity = account.get("equity", 0)
            buying_power = account.get("buying_power", 0)

            current_exposure = sum(abs(p.get("market_value", 0)) for p in positions)
            exposure_ratio = current_exposure / equity if equity > 0 else 0

            return {
                "passed": exposure_ratio < max_exposure,
                "equity": equity,
                "buying_power": buying_power,
                "current_positions": len(positions),
                "exposure_ratio": round(exposure_ratio, 4),
                "max_exposure": max_exposure,
                "max_risk_per_trade": max_risk,
                "max_position_value": round(equity * max_risk, 2),
            }
        except Exception as e:
            return {"passed": False, "reason": str(e)}

    def _broker_step(
        self, step: Dict, prior_results: Dict, inputs: Dict
    ) -> Dict[str, Any]:
        """Execute a broker call (order placement)."""
        if not self.broker or not self.broker.trading_client:
            return {"skipped": "Broker not connected"}

        # Get filtered candidates from prior steps
        risk_result = prior_results.get("risk_check", {})
        if not risk_result.get("passed", False):
            return {"skipped": "Risk check failed", "risk": risk_result}

        filter_result = prior_results.get("filter_volume", {})
        candidates = filter_result.get("candidates", [])

        if not candidates:
            return {"skipped": "No candidates after filtering"}

        orders = []
        max_position = risk_result.get("max_position_value", 5000)

        for candidate in candidates[:3]:  # Max 3 orders per procedure run
            symbol = candidate.get("symbol", "")
            if not symbol:
                continue

            try:
                bars = self.broker.get_bars(symbol, days=1)
                if not bars:
                    continue
                current_price = bars[-1]["close"]
                qty = max(1, int(max_position / current_price))

                # Calculate stop loss (2% below entry for buys)
                stop_price = round(current_price * 0.98, 2)

                order_result = self.broker.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="buy",
                    order_type=step.get("order_type", "market"),
                    limit_price=current_price if step.get("order_type") == "limit" else None,
                    stop_loss_price=stop_price if step.get("require_stop_loss") else None,
                )
                orders.append(order_result)

            except Exception as e:
                logger.error("Order failed for %s: %s", symbol, e)
                orders.append({"symbol": symbol, "error": str(e)})

        return {"orders_submitted": len(orders), "orders": orders}

    def _place_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct order placement from PFC."""
        if not self.broker or not self.broker.trading_client:
            return {"error": "Broker not connected"}

        return self.broker.submit_order(
            symbol=data.get("symbol", ""),
            qty=data.get("qty", 1),
            side=data.get("side", "buy"),
            order_type=data.get("order_type", "market"),
            limit_price=data.get("limit_price"),
            stop_loss_price=data.get("stop_loss_price"),
            take_profit_price=data.get("take_profit_price"),
        )

    def _close_position(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Close a position."""
        if not self.broker or not self.broker.trading_client:
            return {"error": "Broker not connected"}
        return self.broker.close_position(data.get("symbol", ""))

    def _get_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio."""
        if not self.broker or not self.broker.trading_client:
            return {"error": "Broker not connected"}
        return {
            "account": self.broker.get_account(),
            "positions": self.broker.get_positions(),
        }

    def _get_account(self) -> Dict[str, Any]:
        """Get account info."""
        if not self.broker or not self.broker.trading_client:
            return {"error": "Broker not connected"}
        return self.broker.get_account()

    def _get_bars(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical bars."""
        if not self.broker or not self.broker.data_client:
            return {"error": "Broker not connected"}
        return {
            "bars": self.broker.get_bars(
                symbol=data.get("symbol", ""),
                days=data.get("days", 20),
            )
        }

    def _should_escalate(self, step: Dict, error: Exception, results: Dict) -> bool:
        """Check if an error condition warrants escalation to PFC."""
        error_str = str(error).lower()
        if "api" in error_str or "broker" in error_str:
            return True
        failed_steps = sum(1 for r in results.values() if isinstance(r, dict) and "error" in r)
        return failed_steps >= 3

    async def _escalate(self, proc_name: str, step_name: str, error: str):
        """Send an escalation message to PFC."""
        await self.db.send_message(
            direction=Direction.ASCENDING,
            source=Component.CEREBELLUM,
            target=Component.PFC,
            msg_type=MessageType.ESCALATION,
            identifier="procedure_escalation",
            payload={
                "procedure": proc_name,
                "failed_step": step_name,
                "error": error,
                "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
            },
        )
        logger.warning("Escalated to PFC: %s / %s — %s", proc_name, step_name, error)

    async def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        if self.broker:
            self.broker.disconnect()
        if self.db:
            await self.db.send_message(
                direction=Direction.ASCENDING,
                source=Component.CEREBELLUM,
                target=None,
                msg_type=MessageType.STATUS,
                identifier="cerebellum_offline",
                payload={"status": "offline"},
            )
            await self.db.close()
        logger.info("Cerebellum shutdown complete")


async def main():
    config = AgentConfig.from_env()
    executor = CerebellumExecutor(config)

    loop = asyncio.get_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s, shutting down...", sig)
        loop.create_task(executor.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        await executor.initialize()
        await executor.run()
    except asyncio.CancelledError:
        pass
    finally:
        await executor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
