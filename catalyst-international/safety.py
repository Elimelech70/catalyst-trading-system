"""
Safety layer for the Catalyst Trading Agent.

Name of file: safety.py
Version: 1.1.0
Last Updated: 2026-01-08

This module validates all trading actions before execution to ensure
they comply with risk management rules. It acts as the last line of
defense before any order is submitted.

REVISION HISTORY:
v1.1.0 (2026-01-08) - Dynamic lot size support
- validate_trade() now accepts stock-specific lot_size parameter
- Fixes validation errors for stocks with non-100 lot sizes
- HKEX stocks have varying lot sizes (100, 500, 1000, etc.)

v1.0.0 (2025-12-06) - Initial implementation
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Hong Kong timezone
HK_TZ = ZoneInfo("Asia/Hong_Kong")


@dataclass
class RiskLimits:
    """Risk limit configuration."""

    max_positions: int = 15
    max_position_pct: float = 0.20
    min_position_value: float = 2000
    max_daily_loss_pct: float = 0.02
    warning_loss_pct: float = 0.015
    max_trade_loss_pct: float = 0.01
    max_daily_trades: int = 25
    min_risk_reward: float = 1.2
    max_stop_loss_pct: float = 0.05
    lot_size: int = 100


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""

    approved: bool
    reason: str
    warnings: list[str]
    details: dict[str, Any]


class SafetyValidator:
    """Validates all trading actions against risk limits."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self.daily_trades = 0
        self.trade_date = None

    def reset_daily_counters(self):
        """Reset daily trade counters."""
        today = datetime.now(HK_TZ).date()
        if self.trade_date != today:
            self.daily_trades = 0
            self.trade_date = today

    def is_market_open(self) -> tuple[bool, str]:
        """Check if HKEX market is currently open.

        Returns (is_open, reason)
        """
        now = datetime.now(HK_TZ)

        # Check if weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False, "Market closed: Weekend"

        current_time = now.time()

        # Morning session: 9:30 - 12:00
        morning_open = time(9, 30)
        morning_close = time(12, 0)

        # Afternoon session: 13:00 - 16:00
        afternoon_open = time(13, 0)
        afternoon_close = time(16, 0)

        if morning_open <= current_time < morning_close:
            return True, "Morning session"

        if afternoon_open <= current_time < afternoon_close:
            return True, "Afternoon session"

        if morning_close <= current_time < afternoon_open:
            return False, "Market closed: Lunch break (12:00-13:00)"

        if current_time < morning_open:
            return False, "Market closed: Before market open"

        return False, "Market closed: After market close"

    def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        portfolio_value: float,
        cash_available: float,
        current_positions: int,
        daily_pnl_pct: float,
        lot_size: int = 100,  # Stock-specific lot size
    ) -> SafetyCheckResult:
        """Validate a proposed trade against all risk limits.

        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell'
            quantity: Number of shares
            entry_price: Expected entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            portfolio_value: Total portfolio value
            cash_available: Available cash
            current_positions: Number of current positions
            daily_pnl_pct: Today's P&L as percentage (e.g., -0.01 for -1%)
            lot_size: Board lot size for this stock (default 100).
                HKEX stocks have varying lot sizes (100, 500, 1000, etc.)

        Returns:
            SafetyCheckResult with approval status and details
        """
        self.reset_daily_counters()
        warnings = []
        details = {}

        # Calculate position metrics
        position_value = quantity * entry_price
        portfolio_pct = position_value / portfolio_value if portfolio_value > 0 else 0
        risk_per_share = abs(entry_price - stop_loss)
        risk_amount = risk_per_share * quantity
        risk_pct = risk_amount / portfolio_value if portfolio_value > 0 else 0
        reward_per_share = abs(take_profit - entry_price)
        reward_amount = reward_per_share * quantity
        risk_reward = reward_per_share / risk_per_share if risk_per_share > 0 else 0
        stop_loss_pct = risk_per_share / entry_price if entry_price > 0 else 0

        details = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_value": round(position_value, 2),
            "portfolio_pct": round(portfolio_pct * 100, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_pct": round(risk_pct * 100, 2),
            "reward_amount": round(reward_amount, 2),
            "risk_reward": round(risk_reward, 2),
            "stop_loss_pct": round(stop_loss_pct * 100, 2),
        }

        # Check 1: Market hours
        market_open, market_status = self.is_market_open()
        if not market_open:
            return SafetyCheckResult(
                approved=False,
                reason=market_status,
                warnings=warnings,
                details=details,
            )

        # Check 2: Lot size (HKEX requires multiples of board lot - varies by stock)
        actual_lot_size = lot_size if lot_size else self.limits.lot_size
        if quantity % actual_lot_size != 0:
            return SafetyCheckResult(
                approved=False,
                reason=f"Quantity must be multiple of {actual_lot_size} (board lot for {symbol})",
                warnings=warnings,
                details=details,
            )

        # Check 3: Daily loss limit
        if daily_pnl_pct <= -self.limits.max_daily_loss_pct:
            return SafetyCheckResult(
                approved=False,
                reason=f"Daily loss limit reached ({daily_pnl_pct*100:.2f}% >= {self.limits.max_daily_loss_pct*100}%)",
                warnings=warnings,
                details=details,
            )

        # Check 3b: Warning level
        if daily_pnl_pct <= -self.limits.warning_loss_pct:
            warnings.append(
                f"Warning: Approaching daily loss limit ({daily_pnl_pct*100:.2f}%)"
            )

        # Check 4: Maximum positions
        if current_positions >= self.limits.max_positions:
            return SafetyCheckResult(
                approved=False,
                reason=f"Maximum positions reached ({current_positions}/{self.limits.max_positions})",
                warnings=warnings,
                details=details,
            )

        # Check 5: Position size limit
        if portfolio_pct > self.limits.max_position_pct:
            return SafetyCheckResult(
                approved=False,
                reason=f"Position too large ({portfolio_pct*100:.1f}% > {self.limits.max_position_pct*100}%)",
                warnings=warnings,
                details=details,
            )

        # Check 6: Minimum position value
        if position_value < self.limits.min_position_value:
            return SafetyCheckResult(
                approved=False,
                reason=f"Position too small (HKD {position_value:,.0f} < {self.limits.min_position_value:,.0f})",
                warnings=warnings,
                details=details,
            )

        # Check 7: Available cash (for buys)
        if side == "buy" and position_value > cash_available:
            return SafetyCheckResult(
                approved=False,
                reason=f"Insufficient cash (need HKD {position_value:,.0f}, have {cash_available:,.0f})",
                warnings=warnings,
                details=details,
            )

        # Check 8: Stop loss validation
        if side == "buy" and stop_loss >= entry_price:
            return SafetyCheckResult(
                approved=False,
                reason="Stop loss must be below entry price for long positions",
                warnings=warnings,
                details=details,
            )

        if side == "sell" and stop_loss <= entry_price:
            return SafetyCheckResult(
                approved=False,
                reason="Stop loss must be above entry price for short positions",
                warnings=warnings,
                details=details,
            )

        # Check 9: Maximum stop loss percentage
        if stop_loss_pct > self.limits.max_stop_loss_pct:
            return SafetyCheckResult(
                approved=False,
                reason=f"Stop loss too wide ({stop_loss_pct*100:.1f}% > {self.limits.max_stop_loss_pct*100}%)",
                warnings=warnings,
                details=details,
            )

        # Check 10: Minimum risk/reward ratio
        if risk_reward < self.limits.min_risk_reward:
            return SafetyCheckResult(
                approved=False,
                reason=f"Risk/reward too low ({risk_reward:.1f}:1 < {self.limits.min_risk_reward}:1)",
                warnings=warnings,
                details=details,
            )

        # Check 11: Maximum trade risk
        if risk_pct > self.limits.max_trade_loss_pct:
            return SafetyCheckResult(
                approved=False,
                reason=f"Trade risk too high ({risk_pct*100:.2f}% > {self.limits.max_trade_loss_pct*100}%)",
                warnings=warnings,
                details=details,
            )

        # Check 12: Daily trade limit
        if self.daily_trades >= self.limits.max_daily_trades:
            return SafetyCheckResult(
                approved=False,
                reason=f"Daily trade limit reached ({self.daily_trades}/{self.limits.max_daily_trades})",
                warnings=warnings,
                details=details,
            )

        # Check 13: Take profit validation
        if side == "buy" and take_profit <= entry_price:
            return SafetyCheckResult(
                approved=False,
                reason="Take profit must be above entry price for long positions",
                warnings=warnings,
                details=details,
            )

        if side == "sell" and take_profit >= entry_price:
            return SafetyCheckResult(
                approved=False,
                reason="Take profit must be below entry price for short positions",
                warnings=warnings,
                details=details,
            )

        # All checks passed
        return SafetyCheckResult(
            approved=True,
            reason="All risk checks passed",
            warnings=warnings,
            details=details,
        )

    def validate_close_position(
        self, symbol: str, has_position: bool
    ) -> SafetyCheckResult:
        """Validate a position close request."""
        if not has_position:
            return SafetyCheckResult(
                approved=False,
                reason=f"No position found for {symbol}",
                warnings=[],
                details={"symbol": symbol},
            )

        return SafetyCheckResult(
            approved=True,
            reason="Position close approved",
            warnings=[],
            details={"symbol": symbol},
        )

    def validate_close_all(
        self, daily_pnl_pct: float, reason: str
    ) -> SafetyCheckResult:
        """Validate close all positions request."""
        warnings = []

        # Emergency close is always allowed, but log if not at loss limit
        if daily_pnl_pct > -self.limits.warning_loss_pct:
            warnings.append(
                f"Close all triggered without loss limit breach (current: {daily_pnl_pct*100:.2f}%)"
            )

        return SafetyCheckResult(
            approved=True,
            reason=f"Emergency close approved: {reason}",
            warnings=warnings,
            details={"daily_pnl_pct": daily_pnl_pct, "reason": reason},
        )

    def record_trade(self):
        """Record that a trade was executed (for daily limit tracking)."""
        self.reset_daily_counters()
        self.daily_trades += 1

    def should_trigger_emergency_close(self, daily_pnl_pct: float) -> bool:
        """Check if emergency close should be triggered."""
        return daily_pnl_pct <= -self.limits.max_daily_loss_pct

    def get_conservative_mode_warning(self, daily_pnl_pct: float) -> str | None:
        """Get warning if in conservative mode (approaching loss limit)."""
        if (
            -self.limits.max_daily_loss_pct
            < daily_pnl_pct
            <= -self.limits.warning_loss_pct
        ):
            return (
                f"Conservative mode: Daily loss at {daily_pnl_pct*100:.2f}%, "
                f"limit is {self.limits.max_daily_loss_pct*100}%. "
                "Avoid new positions."
            )
        return None


# Singleton instance for global access
_validator: SafetyValidator | None = None


def get_safety_validator(limits: RiskLimits | None = None) -> SafetyValidator:
    """Get or create the safety validator singleton."""
    global _validator
    if _validator is None:
        _validator = SafetyValidator(limits)
    return _validator


def validate_trade_request(
    symbol: str,
    side: str,
    quantity: int,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    portfolio_value: float,
    cash_available: float,
    current_positions: int,
    daily_pnl_pct: float,
) -> dict[str, Any]:
    """Convenience function to validate a trade request.

    Returns dict with 'approved', 'reason', 'warnings', and 'details'.
    """
    validator = get_safety_validator()
    result = validator.validate_trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        portfolio_value=portfolio_value,
        cash_available=cash_available,
        current_positions=current_positions,
        daily_pnl_pct=daily_pnl_pct,
    )

    return {
        "approved": result.approved,
        "reason": result.reason,
        "warnings": result.warnings,
        **result.details,
    }
