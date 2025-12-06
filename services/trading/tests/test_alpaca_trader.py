#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: test_alpaca_trader.py
Version: 1.0.0
Last Updated: 2025-12-06
Purpose: Unit tests for alpaca_trader.py functions

REVISION HISTORY:
v1.0.0 (2025-12-06) - Initial test suite
- Tests for _normalize_side() function (12 tests)
- Tests for _round_price() function (6 tests)
- Tests for _validate_order_side_mapping() function (4 tests)

Description:
Comprehensive unit tests for the critical order-related helper functions
in alpaca_trader.py. These tests ensure the order side bug (v1.2.0) fix
remains intact and catches any regressions.
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.alpaca_trader import _normalize_side, _round_price
from alpaca.trading.enums import OrderSide


class TestNormalizeSide:
    """Test suite for _normalize_side() function."""

    # Buy/Long tests
    def test_normalize_buy_lowercase(self):
        """Test that 'buy' maps to OrderSide.BUY."""
        assert _normalize_side("buy") == OrderSide.BUY

    def test_normalize_buy_uppercase(self):
        """Test that 'BUY' maps to OrderSide.BUY (case insensitive)."""
        assert _normalize_side("BUY") == OrderSide.BUY

    def test_normalize_buy_mixed_case(self):
        """Test that 'Buy' maps to OrderSide.BUY (mixed case)."""
        assert _normalize_side("Buy") == OrderSide.BUY

    def test_normalize_long_lowercase(self):
        """Test that 'long' maps to OrderSide.BUY - THIS WAS THE BUG."""
        assert _normalize_side("long") == OrderSide.BUY

    def test_normalize_long_uppercase(self):
        """Test that 'LONG' maps to OrderSide.BUY (case insensitive)."""
        assert _normalize_side("LONG") == OrderSide.BUY

    def test_normalize_long_mixed_case(self):
        """Test that 'Long' maps to OrderSide.BUY (mixed case)."""
        assert _normalize_side("Long") == OrderSide.BUY

    # Sell/Short tests
    def test_normalize_sell_lowercase(self):
        """Test that 'sell' maps to OrderSide.SELL."""
        assert _normalize_side("sell") == OrderSide.SELL

    def test_normalize_sell_uppercase(self):
        """Test that 'SELL' maps to OrderSide.SELL (case insensitive)."""
        assert _normalize_side("SELL") == OrderSide.SELL

    def test_normalize_short_lowercase(self):
        """Test that 'short' maps to OrderSide.SELL."""
        assert _normalize_side("short") == OrderSide.SELL

    def test_normalize_short_uppercase(self):
        """Test that 'SHORT' maps to OrderSide.SELL (case insensitive)."""
        assert _normalize_side("SHORT") == OrderSide.SELL

    # Error cases
    def test_normalize_invalid_raises_error(self):
        """Test that invalid input raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _normalize_side("invalid")
        assert "Invalid order side" in str(exc_info.value)

    def test_normalize_empty_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _normalize_side("")
        assert "Invalid order side" in str(exc_info.value)

    def test_normalize_whitespace_raises_error(self):
        """Test that whitespace-padded input raises ValueError (not trimmed)."""
        with pytest.raises(ValueError) as exc_info:
            _normalize_side(" buy ")
        assert "Invalid order side" in str(exc_info.value)


class TestRoundPrice:
    """Test suite for _round_price() function."""

    def test_round_price_none(self):
        """Test that None returns None."""
        assert _round_price(None) is None

    def test_round_price_integer(self):
        """Test that integer is converted to float with 2 decimals."""
        result = _round_price(10)
        assert result == 10.0
        assert isinstance(result, float)

    def test_round_price_two_decimals(self):
        """Test that already-rounded price stays the same."""
        assert _round_price(10.55) == 10.55

    def test_round_price_many_decimals(self):
        """Test that floating-point precision errors are fixed."""
        # This was causing Alpaca sub-penny rejections
        assert _round_price(9.050000190734863) == 9.05

    def test_round_price_rounds_down(self):
        """Test standard rounding down."""
        assert _round_price(10.554) == 10.55

    def test_round_price_rounds_up(self):
        """Test standard rounding up."""
        assert _round_price(10.556) == 10.56

    def test_round_price_sub_penny(self):
        """Test that sub-penny precision is removed."""
        # The main goal is removing sub-penny precision, not perfect rounding
        # 10.555 could round to either 10.55 or 10.56 depending on float representation
        result = _round_price(10.555)
        assert result in (10.55, 10.56), f"Expected 10.55 or 10.56, got {result}"
        # Ensure exactly 2 decimal places
        assert len(str(result).split('.')[-1]) <= 2


class TestValidateOrderSideMapping:
    """Test suite for _validate_order_side_mapping() function."""

    def test_validate_long_buy_passes(self):
        """Test that long->BUY mapping passes validation."""
        from common.alpaca_trader import _validate_order_side_mapping
        # Should not raise
        _validate_order_side_mapping("long", OrderSide.BUY)

    def test_validate_buy_buy_passes(self):
        """Test that buy->BUY mapping passes validation."""
        from common.alpaca_trader import _validate_order_side_mapping
        # Should not raise
        _validate_order_side_mapping("buy", OrderSide.BUY)

    def test_validate_short_sell_passes(self):
        """Test that short->SELL mapping passes validation."""
        from common.alpaca_trader import _validate_order_side_mapping
        # Should not raise
        _validate_order_side_mapping("short", OrderSide.SELL)

    def test_validate_sell_sell_passes(self):
        """Test that sell->SELL mapping passes validation."""
        from common.alpaca_trader import _validate_order_side_mapping
        # Should not raise
        _validate_order_side_mapping("sell", OrderSide.SELL)

    def test_validate_long_sell_fails(self):
        """Test that long->SELL mapping raises RuntimeError (the bug case)."""
        from common.alpaca_trader import _validate_order_side_mapping
        with pytest.raises(RuntimeError) as exc_info:
            _validate_order_side_mapping("long", OrderSide.SELL)
        assert "Order side mismatch" in str(exc_info.value)

    def test_validate_short_buy_fails(self):
        """Test that short->BUY mapping raises RuntimeError."""
        from common.alpaca_trader import _validate_order_side_mapping
        with pytest.raises(RuntimeError) as exc_info:
            _validate_order_side_mapping("short", OrderSide.BUY)
        assert "Order side mismatch" in str(exc_info.value)


# Regression test - this exact scenario caused the bug
class TestOrderSideBugRegression:
    """Regression tests specifically for the order side bug (v1.2.0)."""

    def test_workflow_sends_long_gets_buy(self):
        """
        CRITICAL REGRESSION TEST

        The workflow coordinator sends side="long" for buy positions.
        This MUST map to OrderSide.BUY, not OrderSide.SELL.

        The original bug was:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        Which caused "long" to fall through to SELL.
        """
        result = _normalize_side("long")
        assert result == OrderSide.BUY, (
            "CRITICAL: 'long' must map to BUY! "
            "This regression would cause all long positions to become short sells."
        )

    def test_workflow_sends_short_gets_sell(self):
        """
        Verify that short positions correctly map to SELL.
        """
        result = _normalize_side("short")
        assert result == OrderSide.SELL, (
            "'short' must map to SELL for short-selling functionality."
        )
