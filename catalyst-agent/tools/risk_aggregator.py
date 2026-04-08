#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: risk_aggregator.py
Version: 1.0.0
Last Updated: 2026-04-08
Purpose: Tool agent -- portfolio risk aggregation and exposure monitoring

REVISION HISTORY:
v1.0.0 (2026-04-08) - v2.4 architecture implementation
- Tracks total portfolio heat across all open positions
- Monitors: total capital at risk, maximum drawdown, position correlation
- Signals coordinator if exposure exceeds configured limits
- Can instruct Position Monitor to tighten thresholds under high heat

Description:
The Risk Aggregator tracks the big picture across all positions.
Individual position risk is handled by Stop Loss Enforcer and Position Monitor.
This tool watches total portfolio exposure and concentration.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from shared.db import AgentDB
from shared.models import (
    Component, Severity, SignalDomain, SignalScope,
)

logger = logging.getLogger("tool.risk_aggregator")


class RiskAggregatorTool:
    """
    Risk Aggregator Tool Agent -- portfolio-level risk monitoring.

    - Tracks total portfolio heat across all open positions
    - Monitors total capital at risk, concentration, drawdown
    - Signals coordinator if exposure exceeds limits
    - Can tighten Position Monitor thresholds under high heat
    """

    def __init__(self, db: AgentDB, broker, config=None):
        self.db = db
        self.broker = broker
        self.config = config
        self.max_position_pct = config.max_position_pct if config else 0.25
        self.max_daily_loss_pct = config.max_daily_loss_pct if config else 0.03
        self.max_total_positions = 5
        self.max_sector_concentration = 0.5  # max 50% in one sector

    async def assess_risk(self) -> Dict[str, Any]:
        """
        Run full portfolio risk assessment.
        Returns risk summary with any limit breaches.
        """
        result = {
            "healthy": True,
            "breaches": [],
            "portfolio": {},
        }

        try:
            account = self.broker.get_account()
            positions = self.broker.get_positions()
        except Exception as e:
            logger.error("Failed to get account/positions: %s", e)
            result["healthy"] = False
            result["error"] = str(e)
            return result

        equity = account.get("equity", 0)
        if equity <= 0:
            result["healthy"] = False
            result["error"] = "zero_equity"
            return result

        # Portfolio metrics
        total_exposure = sum(abs(p.get("market_value", 0)) for p in positions)
        total_unrealized_pl = sum(p.get("unrealized_pl", 0) for p in positions)
        exposure_pct = total_exposure / equity if equity else 0
        daily_return_pct = total_unrealized_pl / equity if equity else 0

        result["portfolio"] = {
            "equity": equity,
            "total_exposure": total_exposure,
            "exposure_pct": exposure_pct,
            "total_unrealized_pl": total_unrealized_pl,
            "daily_return_pct": daily_return_pct,
            "open_positions": len(positions),
            "buying_power": account.get("buying_power", 0),
        }

        # Check: position count limit
        if len(positions) > self.max_total_positions:
            breach = {
                "type": "position_count",
                "current": len(positions),
                "limit": self.max_total_positions,
            }
            result["breaches"].append(breach)
            result["healthy"] = False

        # Check: individual position size
        for pos in positions:
            pos_pct = abs(pos.get("market_value", 0)) / equity
            if pos_pct > self.max_position_pct:
                breach = {
                    "type": "position_size",
                    "symbol": pos["symbol"],
                    "current_pct": pos_pct,
                    "limit_pct": self.max_position_pct,
                }
                result["breaches"].append(breach)
                result["healthy"] = False

        # Check: daily loss limit
        if daily_return_pct <= -self.max_daily_loss_pct:
            breach = {
                "type": "daily_loss",
                "current_pct": daily_return_pct,
                "limit_pct": -self.max_daily_loss_pct,
            }
            result["breaches"].append(breach)
            result["healthy"] = False

        # Check: single position unrealized loss
        for pos in positions:
            plpc = pos.get("unrealized_plpc", 0)
            if plpc <= -0.05:  # 5% unrealized loss on single position
                breach = {
                    "type": "position_loss",
                    "symbol": pos["symbol"],
                    "unrealized_plpc": plpc,
                    "threshold": -0.05,
                }
                result["breaches"].append(breach)

        # Publish signals for breaches
        if result["breaches"]:
            severity = Severity.CRITICAL if daily_return_pct <= -self.max_daily_loss_pct else Severity.WARNING
            await self.db.publish_signal(
                severity=severity.value,
                domain=SignalDomain.RISK.value,
                scope=SignalScope.BROADCAST.value,
                source=Component.TOOL_RISK_AGGREGATOR.value,
                content=f"Risk breaches detected: {len(result['breaches'])}",
                data={
                    "breaches": result["breaches"],
                    "portfolio": result["portfolio"],
                },
            )

        return result

    async def can_open_position(
        self, symbol: str, size_usd: float
    ) -> Dict[str, Any]:
        """
        Pre-trade risk check: can we open this position?
        """
        try:
            account = self.broker.get_account()
            positions = self.broker.get_positions()
        except Exception as e:
            return {"allowed": False, "reason": f"broker_error: {e}"}

        equity = account.get("equity", 0)

        # Check position count
        if len(positions) >= self.max_total_positions:
            return {"allowed": False, "reason": "max_positions_reached"}

        # Check position size
        if equity > 0 and (size_usd / equity) > self.max_position_pct:
            return {
                "allowed": False,
                "reason": "position_too_large",
                "max_size": equity * self.max_position_pct,
            }

        # Check if already holding this symbol
        for p in positions:
            if p["symbol"] == symbol:
                return {"allowed": False, "reason": "already_holding"}

        # Check daily loss limit
        total_pl = sum(p.get("unrealized_pl", 0) for p in positions)
        daily_return = total_pl / equity if equity else 0
        if daily_return <= -self.max_daily_loss_pct:
            return {"allowed": False, "reason": "daily_loss_limit"}

        return {
            "allowed": True,
            "equity": equity,
            "current_positions": len(positions),
            "max_allowed_size": equity * self.max_position_pct,
        }
