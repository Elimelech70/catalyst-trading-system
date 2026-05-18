"""
BRAIN COMPONENT: Discipline Gate
Biological parallel: Limbic system — drive, motivation, character.

This component runs AFTER survival, BEFORE the decision engine.
It checks whether the brain is being faithful with what it's been given.

Version: 1.0.0
"""

import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("brain.discipline")


class DisciplineGate:
    """
    Brain component that enforces trading character.

    Detects stagnation, idle capital, buried talent.
    Outputs context that shapes the Decision Engine's behaviour.

    Works with data from MCP tool calls (no direct DB access).
    """

    def __init__(self):
        self._last_trade_time: Optional[datetime] = None
        self._consecutive_passes = 0

    def record_trade(self):
        """Called when a trade is executed this cycle."""
        self._last_trade_time = datetime.now()
        self._consecutive_passes = 0

    def record_pass(self):
        """Called when a cycle completes with no trades."""
        self._consecutive_passes += 1

    def check(self, cash: float, total_capital: float,
              open_positions: int, max_positions: int,
              last_trade_time: Optional[datetime] = None) -> dict:
        """
        Run the discipline check. Returns context for the Decision Engine.

        Args:
            cash: Available cash
            total_capital: Total portfolio value
            open_positions: Number of open positions
            max_positions: Maximum allowed positions
            last_trade_time: Override for last trade timestamp (from DB)
        """
        if last_trade_time:
            self._last_trade_time = last_trade_time

        days_idle = self._days_since_last_trade()
        capital_util = (total_capital - cash) / total_capital if total_capital > 0 else 0
        position_util = open_positions / max_positions if max_positions > 0 else 0

        level = "NORMAL"
        force_tier = None
        context_parts = []

        # Stagnation checks
        if days_idle >= 3:
            level = "ALARM"
            force_tier = 3
            context_parts.append(
                f"DISCIPLINE ALARM: {days_idle} days without trading. "
                f"The talent is buried. Tier 3 MINIMUM. "
                f"You MUST attempt at least one trade this session."
            )
        elif days_idle >= 2:
            level = "WARNING"
            force_tier = 3
            context_parts.append(
                f"DISCIPLINE WARNING: {days_idle} days without trading. "
                f"Lower to Tier 3. Actively seek opportunities."
            )
        elif days_idle >= 1:
            context_parts.append(f"Last trade: {days_idle} day(s) ago. Stay active.")

        # Capital checks
        if capital_util < 0.05 and total_capital > 0:
            if level != "ALARM":
                level = "ALARM"
            context_parts.append(
                f"CAPITAL ALARM: {capital_util:.1%} deployed. "
                f"HKD {cash:,.0f} idle. The master gave talents to be TRADED."
            )
        elif capital_util < 0.10:
            if level == "NORMAL":
                level = "WARNING"
            context_parts.append(
                f"CAPITAL WARNING: {capital_util:.1%} deployed. Seek entries."
            )

        # Position slot checks
        if open_positions == 0:
            context_parts.append(
                f"ZERO positions open out of {max_positions} slots. Complete inaction."
            )

        # Consecutive pass checks
        if self._consecutive_passes >= 3:
            if level == "NORMAL":
                level = "WARNING"
            context_parts.append(
                f"{self._consecutive_passes} consecutive cycles with no trades. "
                f"The problem is ME, not the market."
            )

        result = {
            "days_idle": days_idle,
            "capital_utilisation": capital_util,
            "position_utilisation": position_util,
            "consecutive_passes": self._consecutive_passes,
            "level": level,
            "force_tier": force_tier,
            "context_for_decision_engine": "\n".join(context_parts),
        }

        if level != "NORMAL":
            log.warning(
                f"DISCIPLINE {level}: {days_idle}d idle, "
                f"{capital_util:.1%} deployed, "
                f"{open_positions}/{max_positions} positions, "
                f"{self._consecutive_passes} consecutive passes"
            )

        return result

    def format_alert(self, check_result: dict) -> str:
        """Format for logging."""
        return (
            f"DISCIPLINE {check_result['level']}: "
            f"{check_result['days_idle']}d idle, "
            f"{check_result['capital_utilisation']:.1%} capital deployed, "
            f"{check_result['position_utilisation']:.0%} positions used, "
            f"{check_result['consecutive_passes']} consecutive passes"
        )

    def _days_since_last_trade(self) -> int:
        """Calculate days since last trade."""
        if self._last_trade_time is None:
            return 999
        return (datetime.now() - self._last_trade_time).days
